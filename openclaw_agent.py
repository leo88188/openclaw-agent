"""
OpenClaw Agent - 轻量远程管理服务

部署在每台 OpenClaw 实例上，提供 HTTP API 供管理平台调用，替代 SSH 方式。
鉴权: Bearer Token + 可选 HMAC-SHA256 签名（防重放、防篡改）
"""
import os
import json
import hmac
import hashlib
import asyncio
import time
import threading
import subprocess
import shlex
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Depends, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── 配置 ─────────────────────────────────────────────────
AGENT_TOKEN = os.getenv("OPENCLAW_AGENT_TOKEN", "changeme")
OPENCLAW_HOME = os.getenv("OPENCLAW_HOME", os.path.expanduser("~"))
OPENCLAW_DOT_DIR = os.path.join(OPENCLAW_HOME, ".openclaw")
CONFIG_PATH = os.getenv("OPENCLAW_CONFIG", os.path.join(OPENCLAW_DOT_DIR, "openclaw.json"))
LOG_DIR = os.getenv("OPENCLAW_LOG_DIR", os.path.join(OPENCLAW_DOT_DIR, "logs"))
ENV_CONF_PATH = os.getenv(
    "OPENCLAW_ENV_CONF",
    os.path.expanduser("~/.config/systemd/user/openclaw-gateway.service.d/provider-models.conf"),
)
TIMESTAMP_TOLERANCE = int(os.getenv("OPENCLAW_AGENT_TIMESTAMP_TOLERANCE", "300"))  # 秒

app = FastAPI(title="OpenClaw Agent", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── 缓存 body 供签名校验 ─────────────────────────────────
@app.middleware("http")
async def cache_body(request: Request, call_next):
    if request.method == "POST":
        request.state.body = await request.body()
    else:
        request.state.body = b""
    return await call_next(request)


# ── 认证: Bearer Token + 可选 HMAC 签名 ─────────────────
async def verify_auth(
    request: Request,
    authorization: str = Header(""),
    x_timestamp: str = Header(""),
    x_nonce: str = Header(""),
    x_signature: str = Header(""),
):
    """
    双重鉴权:
    1. Bearer Token — 必须
    2. HMAC-SHA256 签名 — 可选（有 X-Signature 头时校验）
       签名算法: hmac_sha256(token, "{timestamp}\\n{nonce}\\n{md5(body)}")
    """
    token = authorization.removeprefix("Bearer ").strip()
    if token != AGENT_TOKEN:
        raise HTTPException(401, "Unauthorized")
    if not x_signature:
        return
    try:
        ts = int(x_timestamp)
    except (ValueError, TypeError):
        raise HTTPException(401, "Invalid timestamp")
    if abs(time.time() - ts) > TIMESTAMP_TOLERANCE:
        raise HTTPException(401, "Request expired")
    body_raw = getattr(request.state, "body", b"")
    body_md5 = hashlib.md5(body_raw).hexdigest() if body_raw else ""
    sign_payload = f"{x_timestamp}\n{x_nonce}\n{body_md5}"
    expected = hmac.new(AGENT_TOKEN.encode(), sign_payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(x_signature, expected):
        raise HTTPException(401, "Invalid signature")


# ── 工具 ─────────────────────────────────────────────────
# 扩展 PATH 确保能找到 openclaw (npm global)
def _build_env():
    env = os.environ.copy()
    home = os.path.expanduser("~")
    extra = ["/usr/local/bin", "/usr/bin", "/snap/bin", f"{home}/.local/bin"]
    # nvm node
    nvm_dir = f"{home}/.nvm/versions/node"
    if os.path.isdir(nvm_dir):
        versions = sorted(os.listdir(nvm_dir), reverse=True)
        if versions:
            extra.append(os.path.join(nvm_dir, versions[0], "bin"))
    # 常见全局包管理器路径
    for p in [f"{home}/.npm-global/bin", f"{home}/.local/share/pnpm", f"{home}/.yarn/bin", f"{home}/.volta/bin"]:
        if os.path.isdir(p):
            extra.append(p)
    env["PATH"] = ":".join(extra) + ":" + env.get("PATH", "")
    env["OPENCLAW_HOME"] = OPENCLAW_HOME
    return env

_ENV = _build_env()


async def run_cmd(cmd: str, timeout: int = 60) -> dict:
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=_ENV
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {
            "ok": proc.returncode == 0, "code": proc.returncode,
            "stdout": stdout.decode("utf-8", errors="replace").strip(),
            "stderr": stderr.decode("utf-8", errors="replace").strip(),
        }
    except asyncio.TimeoutError:
        return {"ok": False, "code": -1, "stdout": "", "stderr": "Command timed out"}
    except Exception as e:
        return {"ok": False, "code": -1, "stdout": "", "stderr": str(e)}


def _resolve_workspace(agent_id: str = "main") -> str:
    default_ws = os.path.join(OPENCLAW_HOME, "workspace")
    try:
        cfg = json.loads(Path(CONFIG_PATH).read_text(encoding="utf-8"))
        agents = cfg.get("agents", {})
        for ag in agents.get("list", []):
            if ag.get("id") == agent_id and ag.get("workspace"):
                return ag["workspace"]
        dw = agents.get("defaults", {}).get("workspace")
        if dw:
            return dw
    except Exception:
        pass
    return default_ws


# ── 健康检查（无需鉴权）────────────────────────────────
@app.get("/health")
async def health():
    # 检测 openclaw 进程是否在运行
    result = await run_cmd("pgrep -f 'openclaw' > /dev/null 2>&1 && echo running || echo stopped", timeout=5)
    openclaw_running = "running" in result.get("stdout", "")
    return {
        "status": "ok",
        "time": datetime.now().isoformat(),
        "openclaw": "running" if openclaw_running else "stopped",
    }


# ── 以下接口均需鉴权 ─────────────────────────────────────
auth = Depends(verify_auth)


@app.get("/config", dependencies=[auth])
async def config_get():
    try:
        return json.loads(Path(CONFIG_PATH).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise HTTPException(404, "Config file not found")
    except json.JSONDecodeError as e:
        raise HTTPException(500, f"Invalid JSON: {e}")


class ConfigSaveReq(BaseModel):
    config: dict
    backup: bool = True


@app.post("/config", dependencies=[auth])
async def config_save(req: ConfigSaveReq):
    path = Path(CONFIG_PATH)
    if req.backup and path.exists():
        bak = path.with_suffix(f".bak.{datetime.now().strftime('%Y%m%d%H%M%S')}")
        bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    path.write_text(json.dumps(req.config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"ok": True}


@app.post("/config/validate", dependencies=[auth])
async def config_validate():
    return await run_cmd("openclaw config validate")


@app.post("/gateway/restart", dependencies=[auth])
async def gateway_restart():
    r = await run_cmd("openclaw gateway restart", timeout=90)
    if r["ok"]:
        return r
    # fallback: kill + nohup run
    await run_cmd("pkill -f openclaw-gateway || true", timeout=10)
    await asyncio.sleep(1)
    r2 = await run_cmd("nohup openclaw gateway run --force </dev/null >>/tmp/openclaw-gw.log 2>&1 &", timeout=10)
    await asyncio.sleep(2)
    chk = await run_cmd("pgrep -f openclaw-gateway && echo ok || echo fail", timeout=5)
    return {"ok": "ok" in chk.get("stdout", ""), "stdout": "fallback restart: " + chk.get("stdout", ""), "stderr": r.get("stderr", "")}


SAFE_COMMANDS = {
    "status": "openclaw status",
    "doctor": "openclaw doctor --deep --yes",
    "channels-status": "openclaw channels status --probe",
    "models-status": "openclaw models status --probe",
    "models-list": "openclaw models list --all",
    "memory-index": "openclaw memory index --all",
    "pairing-list": "openclaw pairing list",
    "cron-list": "openclaw cron list",
    "hooks-list": "openclaw hooks list",
    "hooks-check": "openclaw hooks check",
    "config-validate": "openclaw config validate",
    "gateway-restart": "openclaw gateway restart",
}


class RunReq(BaseModel):
    command: str
    custom_cmd: Optional[str] = None


@app.post("/run", dependencies=[auth])
async def run_command(req: RunReq):
    if req.command == "custom":
        cmd = (req.custom_cmd or "").strip()
        if not cmd:
            raise HTTPException(400, "Empty command")
    else:
        cmd = SAFE_COMMANDS.get(req.command)
        if not cmd:
            raise HTTPException(400, f"Unknown command: {req.command}")
    result = await run_cmd(cmd)
    result["command"] = cmd
    return result


@app.get("/logs", dependencies=[auth])
async def get_logs(
    lines: int = Query(200, ge=10, le=5000),
    channel: str = Query("", description="渠道名: feishu/telegram/all 等，空=全部日志"),
    json_fmt: bool = Query(False, alias="json", description="JSON格式输出"),
):
    if channel:
        cmd = f"openclaw channels logs --channel {channel} --lines {lines}"
    else:
        cmd = f"openclaw logs --limit {lines}"
    if json_fmt:
        cmd += " --json"
    result = await run_cmd(cmd, timeout=30)
    return {"channel": channel or "all", "content": result["stdout"], "stderr": result.get("stderr", "")}


# ── Auth Profiles ──────────────────────────────────────────
@app.get("/auth-profiles", dependencies=[auth])
async def auth_profiles_get():
    """Read all agent auth-profiles, return unified provider key list."""
    agents_dir = os.path.join(OPENCLAW_HOME, ".openclaw", "agents")
    profiles = {}  # provider:profileId -> {key, agents:[]}
    for ap in Path(agents_dir).glob("*/agent/auth-profiles.json"):
        agent_id = ap.parent.parent.name
        try:
            data = json.loads(ap.read_text("utf-8"))
        except Exception:
            continue
        for pid, p in data.get("profiles", {}).items():
            if p.get("type") != "api_key":
                continue
            provider = p.get("provider", pid.split(":")[0])
            key = p.get("key", "")
            if pid not in profiles:
                profiles[pid] = {"provider": provider, "key": key, "agents": []}
            profiles[pid]["agents"].append(agent_id)
    return {"profiles": profiles}


class AuthProfilesSaveReq(BaseModel):
    profiles: list  # [{provider, key}]


@app.post("/auth-profiles", dependencies=[auth])
async def auth_profiles_save(req: AuthProfilesSaveReq):
    """Write provider API keys to ALL agent auth-profiles.json."""
    agents_dir = os.path.join(OPENCLAW_HOME, ".openclaw", "agents")
    new_profiles = {}
    for item in req.profiles:
        provider = item.get("provider", "").strip()
        key = item.get("key", "").strip()
        if not provider or not key:
            continue
        pid = f"{provider}:default"
        new_profiles[pid] = {"type": "api_key", "provider": provider, "key": key}
    updated = []
    for ap in Path(agents_dir).glob("*/agent/auth-profiles.json"):
        try:
            data = json.loads(ap.read_text("utf-8"))
        except Exception:
            data = {"version": 1, "profiles": {}}
        # Remove old api_key profiles that are being replaced
        for pid in list(data.get("profiles", {}).keys()):
            if data["profiles"][pid].get("type") == "api_key" and pid in new_profiles:
                pass  # will be overwritten
        data.setdefault("profiles", {}).update(new_profiles)
        ap.write_text(json.dumps(data, indent=2), "utf-8")
        updated.append(ap.parent.parent.name)
    return {"ok": True, "updated": updated}


@app.get("/env-keys", dependencies=[auth])
async def env_keys_get():
    try:
        content = Path(ENV_CONF_PATH).read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"raw": "", "keys": []}
    keys = []
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("Environment="):
            kv = line[len("Environment="):]
            eq = kv.find("=")
            if eq > 0:
                keys.append({"name": kv[:eq], "value": kv[eq + 1:]})
    return {"raw": content, "keys": keys}


class EnvKeysSaveReq(BaseModel):
    keys: list


@app.post("/env-keys", dependencies=[auth])
async def env_keys_save(req: EnvKeysSaveReq):
    lines = ["[Service]"]
    for item in req.keys:
        name = item.get("name", "").strip()
        value = item.get("value", "").strip()
        if name:
            lines.append(f"Environment={name}={value}")
    content = "\n".join(lines) + "\n"
    path = Path(ENV_CONF_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    await run_cmd("systemctl --user daemon-reload")
    return {"ok": True}


@app.get("/workspace/files", dependencies=[auth])
async def workspace_files(agent_id: str = Query("main")):
    ws = _resolve_workspace(agent_id)
    key_files = ["AGENTS.md", "SOUL.md", "USER.md", "IDENTITY.md", "MEMORY.md",
                 "TOOLS.md", "HEARTBEAT.md", "BOOTSTRAP.md"]
    result = []
    for f in key_files:
        p = os.path.join(ws, f)
        result.append({"name": f, "exists": os.path.isfile(p),
                        "size": os.path.getsize(p) if os.path.isfile(p) else 0})
    mem_dir = os.path.join(ws, "memory")
    mem_files = []
    if os.path.isdir(mem_dir):
        mem_files = sorted([f for f in os.listdir(mem_dir) if f.endswith(".md")], reverse=True)[:20]
    return {"agent_id": agent_id, "workspace": ws, "files": result, "memory_files": mem_files}


@app.get("/workspace/file", dependencies=[auth])
async def workspace_file_read(filename: str = Query(...), agent_id: str = Query("main")):
    if ".." in filename or filename.startswith("/"):
        raise HTTPException(403, "Invalid path")
    path = os.path.join(_resolve_workspace(agent_id), filename)
    try:
        return {"filename": filename, "content": Path(path).read_text(encoding="utf-8")}
    except FileNotFoundError:
        raise HTTPException(404, "File not found")


class FileSaveReq(BaseModel):
    filename: str
    content: str
    agent_id: str = "main"


@app.post("/workspace/file", dependencies=[auth])
async def workspace_file_save(req: FileSaveReq):
    if ".." in req.filename or req.filename.startswith("/"):
        raise HTTPException(403, "Invalid path")
    path = Path(os.path.join(_resolve_workspace(req.agent_id), req.filename))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(req.content, encoding="utf-8")
    return {"ok": True}


# ── 飞书长连接临时监听 ───────────────────────────────────
_feishu_proc: Optional[subprocess.Popen] = None
_feishu_log: list = []          # 最近日志行
_feishu_cfg: dict = {}          # 当前运行参数
_feishu_lock = threading.Lock()
_FEISHU_LOG_MAX = 200


def _feishu_reader(proc: subprocess.Popen):
    """后台线程读取子进程 stdout/stderr"""
    for stream in (proc.stdout, proc.stderr):
        if not stream:
            continue
        for raw in stream:
            line = raw.decode("utf-8", errors="replace").rstrip("\n")
            with _feishu_lock:
                _feishu_log.append(line)
                if len(_feishu_log) > _FEISHU_LOG_MAX:
                    _feishu_log.pop(0)


class FeishuStartReq(BaseModel):
    app_id: str
    app_secret: str
    log_level: str = "INFO"


@app.post("/feishu/start", dependencies=[auth])
async def feishu_start(req: FeishuStartReq):
    global _feishu_proc, _feishu_cfg
    if _feishu_proc and _feishu_proc.poll() is None:
        raise HTTPException(409, "飞书监听已在运行中，请先停止")
    # 写临时脚本文件
    import tempfile
    script = f"""import json, sys, signal
import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

def handle(data):
    e = data.event
    m = e.message if e else None
    s = e.sender if e else None
    sid = getattr(s.sender_id, 'open_id', '') if s and s.sender_id else ''
    print(json.dumps({{
        'event_type': getattr(data.header, 'event_type', ''),
        'message_id': getattr(m, 'message_id', ''),
        'chat_id': getattr(m, 'chat_id', ''),
        'chat_type': getattr(m, 'chat_type', ''),
        'message_type': getattr(m, 'message_type', ''),
        'sender_id': sid,
        'content': getattr(m, 'content', ''),
    }}, ensure_ascii=False), flush=True)

signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
eh = lark.EventDispatcherHandler.builder('', '', lark.LogLevel.{req.log_level.upper()}).register_p2_im_message_receive_v1(handle).build()
c = lark.ws.Client(app_id='{req.app_id}', app_secret='{req.app_secret}', log_level=lark.LogLevel.{req.log_level.upper()}, event_handler=eh)
print('[feishu-ws] starting...', flush=True)
c.start()
"""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, prefix="feishu_ws_")
    tmp.write(script)
    tmp.close()
    with _feishu_lock:
        _feishu_log.clear()
    _feishu_proc = subprocess.Popen(
        ["python3", tmp.name],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    _feishu_cfg = {"app_id": req.app_id, "log_level": req.log_level, "pid": _feishu_proc.pid, "_script": tmp.name}
    t = threading.Thread(target=_feishu_reader, args=(_feishu_proc,), daemon=True)
    t.start()
    return {"ok": True, "pid": _feishu_proc.pid}


@app.post("/feishu/stop", dependencies=[auth])
async def feishu_stop():
    global _feishu_proc, _feishu_cfg
    if not _feishu_proc or _feishu_proc.poll() is not None:
        _feishu_proc = None
        return {"ok": True, "msg": "未在运行"}
    _feishu_proc.terminate()
    try:
        _feishu_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _feishu_proc.kill()
    # 清理临时脚本
    sf = _feishu_cfg.get("_script")
    if sf:
        try: os.unlink(sf)
        except OSError: pass
    _feishu_proc = None
    _feishu_cfg = {}
    return {"ok": True}


@app.get("/feishu/status", dependencies=[auth])
async def feishu_status():
    running = _feishu_proc is not None and _feishu_proc.poll() is None
    with _feishu_lock:
        logs = list(_feishu_log)
    return {"running": running, "config": _feishu_cfg if running else None, "logs": logs}


# ── 模型管理 ─────────────────────────────────────────────
def _load_config() -> dict:
    try:
        return json.loads(Path(CONFIG_PATH).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_auth_profiles() -> dict:
    """加载所有 agent 的 auth-profiles，返回 {provider: apiKey}"""
    agents_dir = os.path.join(OPENCLAW_DOT_DIR, "agents")
    keys = {}
    for ap in Path(agents_dir).glob("*/agent/auth-profiles.json"):
        try:
            data = json.loads(ap.read_text("utf-8"))
            for pid, p in data.get("profiles", {}).items():
                provider = p.get("provider", "")
                key = p.get("apiKey") or p.get("key") or ""
                if provider and key and provider not in keys:
                    keys[provider] = key
        except Exception:
            continue
    return keys


@app.get("/models/list", dependencies=[auth])
async def models_list_api():
    """从配置文件读取模型池，返回所有已配置的模型"""
    cfg = _load_config()
    providers = cfg.get("models", {}).get("providers", {})
    models = []
    for provider_name, provider_cfg in providers.items():
        base_url = provider_cfg.get("baseUrl", "")
        for m in provider_cfg.get("models", []):
            model_id = m.get("id") or m.get("name") or (m if isinstance(m, str) else "")
            if model_id:
                models.append({
                    "model": f"{provider_name}/{model_id}",
                    "provider": provider_name,
                    "model_id": model_id,
                    "base_url": base_url,
                })
    return {"models": models, "total": len(models)}


# ── 实时状态 ──────────────────────────────────────────────

@app.get("/status", dependencies=[auth])
async def agent_status():
    """获取 openclaw status --json 并结构化返回"""
    result = await run_cmd("openclaw status --json", timeout=30)
    stdout = result.get("stdout", "")
    # 提取 JSON
    start = stdout.find("{")
    if start < 0:
        return {"raw": stdout, "parsed": False}
    try:
        data = json.loads(stdout[start:])
        return {"parsed": True, **data}
    except json.JSONDecodeError:
        return {"raw": stdout[start:], "parsed": False}


# ── Pairing 配对管理 ──────────────────────────────────────

@app.get("/pairing/list", dependencies=[auth])
async def pairing_list():
    """获取待审批配对请求和已授权用户列表"""
    import glob
    cred_dir = os.path.join(OPENCLAW_DOT_DIR, "credentials")
    # 待审批
    pairing_file = os.path.join(cred_dir, "feishu-pairing.json")
    requests = []
    if os.path.exists(pairing_file):
        with open(pairing_file) as f:
            requests = json.load(f).get("requests", [])
    # 已授权
    allowed = {}
    for fp in glob.glob(os.path.join(cred_dir, "feishu-*-allowFrom.json")):
        name = os.path.basename(fp).replace("feishu-", "").replace("-allowFrom.json", "")
        with open(fp) as f:
            allowed[name] = json.load(f).get("allowFrom", [])
    return {"requests": requests, "allowed": allowed}


class PairingApproveReq(BaseModel):
    code: str
    account: Optional[str] = None


@app.post("/pairing/approve", dependencies=[auth])
async def pairing_approve(req: PairingApproveReq):
    """审批配对请求"""
    cmd = f"openclaw pairing approve feishu {shlex.quote(req.code)}"
    if req.account:
        cmd += f" --account {shlex.quote(req.account)}"
    cmd += " --notify"
    result = await run_cmd(cmd, timeout=30)
    return result


@app.get("/models/probe", dependencies=[auth])
async def models_probe_api(models: Optional[str] = Query(None)):
    """批量探测模型，可选传 models 参数（逗号分隔）指定探测哪些模型"""
    cmd = "openclaw models status --probe --status-plain"
    if models:
        for m in models.split(","):
            m = m.strip()
            if m:
                cmd += f" {shlex.quote(m)}"
    result = await run_cmd(cmd, timeout=120)
    return result


class ProbeOneReq(BaseModel):
    model: str  # 格式: provider/model_id


@app.post("/models/probe-one", dependencies=[auth])
async def models_probe_one_api(req: ProbeOneReq):
    """探测单个模型 — agent 本地读配置并直接请求 provider"""
    import urllib.request
    import urllib.error
    import ssl

    parts = req.model.split("/", 1)
    if len(parts) < 2:
        return {"status": "error", "latency_ms": 0, "error": f"模型格式应为 provider/model_id，收到: {req.model}"}

    provider, model_id = parts[0], parts[1]
    cfg = _load_config()
    providers = cfg.get("models", {}).get("providers", {})
    p = providers.get(provider, {})
    base_url = p.get("baseUrl", "")
    if not base_url:
        return {"status": "error", "latency_ms": 0, "error": f"Provider {provider} 未配置 baseUrl"}

    auth_keys = _load_auth_profiles()
    api_key = auth_keys.get(provider, "")
    if not api_key:
        return {"status": "error", "latency_ms": 0, "error": f"Provider {provider} 未配置 API Key"}

    url = base_url.rstrip("/") + "/chat/completions"
    body = json.dumps({"model": model_id, "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": 1, "stream": False}).encode()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    ctx = ssl._create_unverified_context()
    req_obj = urllib.request.Request(url, data=body, headers=headers)

    t0 = time.time()
    try:
        resp = urllib.request.urlopen(req_obj, timeout=30, context=ctx)
        data = json.loads(resp.read())
        ms = int((time.time() - t0) * 1000)
        if data.get("choices") or data.get("id"):
            return {"status": "ok", "latency_ms": ms, "error": ""}
        return {"status": "error", "latency_ms": ms, "error": str(data)[:300]}
    except urllib.error.HTTPError as e:
        ms = int((time.time() - t0) * 1000)
        body_text = e.read().decode("utf-8", "ignore")[:500]
        try:
            err = json.loads(body_text).get("error", {})
            msg = err.get("message", "") if isinstance(err, dict) else str(err)
        except Exception:
            msg = body_text
        return {"status": "error", "latency_ms": ms, "error": msg}
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        return {"status": "error", "latency_ms": ms, "error": str(e)[:300]}


# ── Sessions ─────────────────────────────────────────────
@app.get("/sessions", dependencies=[auth])
async def sessions(active: int = 0):
    cmd = "openclaw sessions --all-agents --json"
    if active > 0:
        cmd += f" --active {active}"
    return await run_cmd(cmd)


@app.get("/session-detail", dependencies=[auth])
async def session_detail(agent: str = Query(...), session_id: str = Query(...)):
    """Read session metadata + conversation summary from jsonl."""
    import re
    agents_dir = os.path.join(OPENCLAW_HOME, ".openclaw", "agents")
    store_path = os.path.join(agents_dir, agent, "sessions", "sessions.json")
    jsonl_path = os.path.join(agents_dir, agent, "sessions", f"{session_id}.jsonl")

    result = {"meta": None, "messages": [], "stats": {"total": 0, "user": 0, "assistant": 0, "tool": 0}}

    # Read metadata from sessions.json
    try:
        store = json.loads(Path(store_path).read_text("utf-8"))
        for key, val in store.items():
            if val.get("sessionId") == session_id:
                result["meta"] = {
                    "key": key, "sessionId": session_id,
                    "updatedAt": val.get("updatedAt"),
                    "chatType": val.get("chatType"),
                    "origin": val.get("origin", {}),
                    "compactionCount": val.get("compactionCount", 0),
                    "abortedLastRun": val.get("abortedLastRun", False),
                    "sessionFile": val.get("sessionFile", jsonl_path),
                }
                break
    except Exception:
        pass

    # Read jsonl conversation
    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                t = obj.get("type", "")
                ts = obj.get("timestamp", "")

                if t == "message":
                    msg = obj.get("message", {})
                    role = msg.get("role", "")
                    content = msg.get("content", [])

                    # toolResult role → parse as tool call
                    if role == "toolResult":
                        result["stats"]["tool"] += 1
                        tool_text = ""
                        if isinstance(content, list):
                            for c in content:
                                if isinstance(c, dict) and c.get("type") == "text":
                                    tool_text = c.get("text", "")[:300]
                                    break
                        elif isinstance(content, str):
                            tool_text = content[:300]
                        summary = "[工具调用结果]"
                        try:
                            tr = json.loads(tool_text) if tool_text.startswith("{") else {}
                            parts = []
                            if tr.get("runId"): parts.append(f"runId={tr['runId'][:8]}…")
                            if tr.get("status"): parts.append(tr["status"])
                            if tr.get("reply"): parts.append(tr["reply"].replace("\n"," ")[:80])
                            if parts: summary = " | ".join(parts)
                        except Exception:
                            summary = tool_text.replace("\n"," ")[:100] if tool_text else "[工具调用结果]"
                        result["messages"].append({"ts": ts[:19], "role": "tool", "text": summary})
                        continue

                    # Extract text preview
                    text = ""
                    if isinstance(content, list):
                        for c in content:
                            if isinstance(c, dict):
                                if c.get("type") == "text":
                                    text = c.get("text", "")
                                    break
                                elif c.get("type") == "tool_use":
                                    text = f"[tool: {c.get('name', '?')}]"
                                    break
                            elif isinstance(c, str):
                                text = c
                                break
                    elif isinstance(content, str):
                        text = content
                    # Strip injected prefixes
                    if "<relevant-memories>" in text:
                        idx = text.find("</relevant-memories>")
                        text = text[idx+20:].strip() if idx >= 0 else ""
                    if text.startswith("Conversation info (untrusted metadata)"):
                        text = ""
                    if not text and role == "user":
                        text = "(系统上下文注入)"
                    text = text.replace("\n", " ")[:200]
                    result["messages"].append({"ts": ts[:19], "role": role, "text": text})
                    result["stats"]["total"] += 1
                    if role == "user":
                        result["stats"]["user"] += 1
                    elif role == "assistant":
                        result["stats"]["assistant"] += 1
                elif t == "model_change":
                    result["messages"].append({"ts": ts[:19], "role": "system", "text": f"模型切换 → {obj.get('provider','')}/{obj.get('modelId','')}"})

        # Only keep last 50 messages for display
        if len(result["messages"]) > 50:
            result["messages"] = result["messages"][-50:]
            result["truncated"] = True
    except FileNotFoundError:
        result["error"] = "会话文件不存在"
    except Exception as e:
        result["error"] = str(e)

    return result


# ── Cron ─────────────────────────────────────────────────
@app.get("/cron", dependencies=[auth])
async def cron_list():
    return await run_cmd("openclaw cron list --all --json")

@app.post("/cron/enable", dependencies=[auth])
async def cron_enable(req: dict):
    return await run_cmd(f"openclaw cron enable {req['id']}")

@app.post("/cron/disable", dependencies=[auth])
async def cron_disable(req: dict):
    return await run_cmd(f"openclaw cron disable {req['id']}")

@app.post("/cron/run", dependencies=[auth])
async def cron_run(req: dict):
    return await run_cmd(f"openclaw cron run {req['id']}", timeout=120)

@app.post("/cron/rm", dependencies=[auth])
async def cron_rm(req: dict):
    return await run_cmd(f"openclaw cron rm {req['id']}")

@app.post("/cron/edit", dependencies=[auth])
async def cron_edit(req: dict):
    job_id = req.pop("id")
    parts = [f"openclaw cron edit {job_id}"]
    for k, v in req.items():
        if k == "name":        parts.append(f"--name {shlex.quote(str(v))}")
        elif k == "cron":      parts.append(f"--cron {shlex.quote(str(v))}")
        elif k == "tz":        parts.append(f"--tz {shlex.quote(str(v))}")
        elif k == "message":   parts.append(f"--message {shlex.quote(str(v))}")
        elif k == "description": parts.append(f"--description {shlex.quote(str(v))}")
        elif k == "agent":     parts.append(f"--agent {shlex.quote(str(v))}")
        elif k == "model":     parts.append(f"--model {shlex.quote(str(v))}")
        elif k == "timeout_seconds": parts.append(f"--timeout-seconds {int(v)}")
    return await run_cmd(" ".join(parts))

@app.get("/cron/runs", dependencies=[auth])
async def cron_runs(id: str = "", limit: int = 20):
    cmd = f"openclaw cron runs --limit {limit}"
    if id:
        cmd += f" --id {id}"
    return await run_cmd(cmd)


# ── 自更新 ───────────────────────────────────────────────
REPO_URL = "https://raw.githubusercontent.com/leo88188/openclaw-agent/main"
INSTALL_DIR = os.path.dirname(os.path.abspath(__file__))


@app.post("/upgrade", dependencies=[auth])
async def upgrade():
    """从 GitHub 拉取最新代码并重启服务"""
    import urllib.request
    files = ["openclaw_agent.py", "requirements.txt"]
    updated = []
    for f in files:
        url = f"{REPO_URL}/{f}?t={int(datetime.now().timestamp())}"
        local = os.path.join(INSTALL_DIR, f)
        try:
            old = Path(local).read_text(encoding="utf-8") if os.path.exists(local) else ""
            urllib.request.urlretrieve(url, local)
            new = Path(local).read_text(encoding="utf-8")
            if old != new:
                updated.append(f)
        except Exception as e:
            return {"ok": False, "error": f"下载 {f} 失败: {e}"}
    if not updated:
        return {"ok": True, "msg": "已是最新版本", "updated": []}
    # 更新依赖
    venv_pip = os.path.join(INSTALL_DIR, "venv", "bin", "pip")
    if os.path.exists(venv_pip):
        result = await run_cmd(f"{venv_pip} install -q -r {os.path.join(INSTALL_DIR, 'requirements.txt')}")
        if not result["ok"]:
            return {"ok": False, "error": f"依赖安装失败: {result['stderr']}"}
    # 重启服务
    await run_cmd("systemctl restart openclaw-agent")
    return {"ok": True, "msg": "更新完成，服务重启中", "updated": updated}


@app.get("/version", dependencies=[auth])
async def version():
    """返回当前代码的最后修改时间作为版本标识"""
    agent_file = os.path.join(INSTALL_DIR, "openclaw_agent.py")
    mtime = os.path.getmtime(agent_file) if os.path.exists(agent_file) else 0
    return {"version": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S"), "install_dir": INSTALL_DIR}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("OPENCLAW_AGENT_PORT", "9966"))
    uvicorn.run(app, host="0.0.0.0", port=port)
