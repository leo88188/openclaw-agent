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

# 自动搜索配置文件
if not os.path.isfile(CONFIG_PATH):
    _candidates = [
        os.path.join(OPENCLAW_HOME, ".openclaw", "openclaw.json"),
        os.path.expanduser("~/.openclaw/openclaw.json"),
        os.path.expanduser("~/.openclaw-dev/openclaw.json"),
        os.path.expanduser("~/.config/openclaw/openclaw.json"),
        "/etc/openclaw/openclaw.json",
    ]
    for _c in _candidates:
        if os.path.isfile(_c):
            CONFIG_PATH = _c
            OPENCLAW_DOT_DIR = os.path.dirname(_c)
            OPENCLAW_HOME = os.path.dirname(OPENCLAW_DOT_DIR)
            break
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
    # 从持久化文件恢复 ACP 环境变量
    for env_file in [os.path.join(home, ".openclaw", ".env"), os.path.join(home, ".profile")]:
        if os.path.isfile(env_file):
            try:
                for line in open(env_file).readlines():
                    line = line.strip()
                    if line.startswith("#") or "=" not in line:
                        continue
                    line = line.removeprefix("export ").strip()
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if k in ("ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY") and v and k not in env:
                        env[k] = v
            except Exception:
                pass
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


async def _can_reach(host: str, timeout: int = 15) -> bool:
    """检测是否能访问指定域名（用于判断是否需要国内镜像）"""
    r = await run_cmd(f"curl -s --connect-timeout {timeout} -o /dev/null -w '%{{http_code}}' https://{host}", timeout=timeout + 3)
    return r.get("stdout", "").strip() in ("200", "301", "302")


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


# ── 鉴权 ─────────────────────────────────────────────────
auth = Depends(verify_auth)


@app.get("/health", dependencies=[auth])
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
    "memory-index": "openclaw memory index",
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


def _parse_jsonl(jsonl_path: str, agent_label: str = ""):
    """Parse a session JSONL file into messages list and stats."""
    messages = []
    stats = {"total": 0, "user": 0, "assistant": 0, "tool": 0}
    _pending_tools = {}
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

                    if role == "toolResult":
                        stats["tool"] += 1
                        tool_text = ""
                        if isinstance(content, list):
                            for c in content:
                                if isinstance(c, dict) and c.get("type") == "text":
                                    tool_text = c.get("text", "")[:500]
                                    break
                        elif isinstance(content, str):
                            tool_text = content[:500]
                        tool_use_id = msg.get("toolUseId", "")
                        tool_name = _pending_tools.pop(tool_use_id, "") if tool_use_id else ""
                        summary = ""
                        try:
                            tr = json.loads(tool_text) if tool_text.strip().startswith("{") else None
                            if tr and isinstance(tr, dict):
                                parts = []
                                if tr.get("runId"): parts.append(f"runId={tr['runId'][:8]}…")
                                if tr.get("status"): parts.append(tr["status"])
                                if tr.get("error"): parts.append(tr["error"].replace("\n"," ")[:80])
                                elif tr.get("reply"): parts.append(tr["reply"].replace("\n"," ")[:80])
                                if parts: summary = " | ".join(parts)
                        except Exception:
                            pass
                        if not summary:
                            summary = tool_text.replace("\n", " ")[:120] if tool_text else "(空)"
                        prefix = f"🔧 {tool_name} → " if tool_name else ""
                        m = {"ts": ts[:19], "role": "tool", "text": f"{prefix}{summary}"}
                        if agent_label: m["agent"] = agent_label
                        messages.append(m)
                        continue

                    text = ""
                    tool_calls = []
                    if isinstance(content, list):
                        for c in content:
                            if isinstance(c, dict):
                                ct = c.get("type", "")
                                if ct == "text" and not text:
                                    text = c.get("text", "")
                                elif ct in ("toolCall", "tool_use"):
                                    tn = c.get("name", "?")
                                    tid = c.get("id", "")
                                    args = c.get("arguments", c.get("input", {}))
                                    if tid: _pending_tools[tid] = tn
                                    arg_s = ""
                                    if isinstance(args, dict):
                                        arg_s = " ".join(f"{k}={json.dumps(v,ensure_ascii=False)}" for k,v in list(args.items())[:3])[:120]
                                    tool_calls.append(f"{tn}({arg_s})")
                            elif isinstance(c, str) and not text:
                                text = c
                    elif isinstance(content, str):
                        text = content
                    if "<relevant-memories>" in text:
                        idx = text.find("</relevant-memories>")
                        text = text[idx+20:].strip() if idx >= 0 else ""
                    if text.startswith("Conversation info (untrusted metadata)"):
                        text = ""
                    if not text and role == "user":
                        text = "(系统上下文注入)"
                    text = text.replace("\n", " ")[:200]
                    if tool_calls and role == "assistant":
                        tc_text = "  ".join(f"🔨{t}" for t in tool_calls)
                        text = f"{text}  {tc_text}" if text else tc_text
                    m = {"ts": ts[:19], "role": role, "text": text}
                    if agent_label: m["agent"] = agent_label
                    messages.append(m)
                    stats["total"] += 1
                    if role == "user": stats["user"] += 1
                    elif role == "assistant": stats["assistant"] += 1
                elif t == "model_change":
                    m = {"ts": ts[:19], "role": "system", "text": f"模型切换 → {obj.get('provider','')}/{obj.get('modelId','')}"}
                    if agent_label: m["agent"] = agent_label
                    messages.append(m)
    except FileNotFoundError:
        pass
    except Exception as e:
        pass
    return messages, stats


def _read_session_meta(store_path: str, session_id: str, jsonl_path: str):
    try:
        store = json.loads(Path(store_path).read_text("utf-8"))
        for key, val in store.items():
            if val.get("sessionId") == session_id:
                return {
                    "key": key, "sessionId": session_id,
                    "updatedAt": val.get("updatedAt"),
                    "chatType": val.get("chatType"),
                    "subject": val.get("subject", ""),
                    "origin": val.get("origin", {}),
                    "compactionCount": val.get("compactionCount", 0),
                    "abortedLastRun": val.get("abortedLastRun", False),
                    "sessionFile": val.get("sessionFile", jsonl_path),
                }
    except Exception:
        pass
    return None


@app.get("/session-detail", dependencies=[auth])
async def session_detail(agent: str = Query(...), session_id: str = Query(...), group: bool = Query(False)):
    """Read session detail. group=true merges all agents in the same group chat."""
    agents_dir = os.path.join(OPENCLAW_HOME, ".openclaw", "agents")
    store_path = os.path.join(agents_dir, agent, "sessions", "sessions.json")
    jsonl_path = os.path.join(agents_dir, agent, "sessions", f"{session_id}.jsonl")

    meta = _read_session_meta(store_path, session_id, jsonl_path)
    result = {"meta": meta, "messages": [], "stats": {"total": 0, "user": 0, "assistant": 0, "tool": 0}}

    if group and meta and meta.get("chatType") == "group" and meta.get("subject"):
        # Find all agents with sessions in the same group
        subject = meta["subject"]
        group_agents = []  # [(agent_name, session_id, jsonl_path)]
        try:
            for d in sorted(os.listdir(agents_dir)):
                sp = os.path.join(agents_dir, d, "sessions", "sessions.json")
                if not os.path.isfile(sp): continue
                st = json.loads(Path(sp).read_text("utf-8"))
                for k, v in st.items():
                    if v.get("subject") == subject and v.get("chatType") == "group":
                        sid = v["sessionId"]
                        jp = os.path.join(agents_dir, d, "sessions", f"{sid}.jsonl")
                        if os.path.isfile(jp):
                            group_agents.append((d, sid, jp))
                        break
        except Exception:
            pass
        result["groupAgents"] = [a[0] for a in group_agents]
        # Merge messages from all agents
        all_msgs = []
        agg_stats = {"total": 0, "user": 0, "assistant": 0, "tool": 0}
        seen_user = set()  # deduplicate user messages (same ts+text across agents)
        for a_name, a_sid, a_jp in group_agents:
            msgs, st = _parse_jsonl(a_jp, agent_label=a_name)
            for m in msgs:
                if m["role"] == "user":
                    key = (m["ts"], m["text"][:60])
                    if key in seen_user: continue
                    seen_user.add(key)
                all_msgs.append(m)
            agg_stats["assistant"] += st["assistant"]
            agg_stats["tool"] += st["tool"]
        # Sort by timestamp
        all_msgs.sort(key=lambda x: x["ts"])
        agg_stats["user"] = sum(1 for m in all_msgs if m["role"] == "user")
        agg_stats["total"] = agg_stats["user"] + agg_stats["assistant"]
        result["messages"] = all_msgs[-80:] if len(all_msgs) > 80 else all_msgs
        result["truncated"] = len(all_msgs) > 80
        result["stats"] = agg_stats
    else:
        msgs, stats = _parse_jsonl(jsonl_path)
        result["messages"] = msgs[-50:] if len(msgs) > 50 else msgs
        result["truncated"] = len(msgs) > 50
        result["stats"] = stats

    if not os.path.isfile(jsonl_path) and not result.get("messages"):
        result["error"] = "会话文件不存在"

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
    updated, backups = [], {}
    for f in files:
        url = f"{REPO_URL}/{f}?t={int(datetime.now().timestamp())}"
        local = os.path.join(INSTALL_DIR, f)
        try:
            old = Path(local).read_text(encoding="utf-8") if os.path.exists(local) else ""
            backups[f] = old
            urllib.request.urlretrieve(url, local)
            new = Path(local).read_text(encoding="utf-8")
            if old != new:
                updated.append(f)
        except Exception as e:
            return {"ok": False, "error": f"下载 {f} 失败: {e}"}
    if not updated:
        return {"ok": True, "msg": "已是最新版本", "updated": []}
    # 验证新代码
    if "openclaw_agent.py" in updated:
        agent_file = os.path.join(INSTALL_DIR, "openclaw_agent.py")
        try:
            import ast
            ast.parse(Path(agent_file).read_text(encoding="utf-8"))
        except SyntaxError as e:
            Path(agent_file).write_text(backups["openclaw_agent.py"], encoding="utf-8")
            return {"ok": False, "error": f"新代码语法错误，已回滚: {e}"}
        venv_py = os.path.join(INSTALL_DIR, "venv", "bin", "python3")
        py = venv_py if os.path.exists(venv_py) else "python3"
        chk = await run_cmd(f"cd {INSTALL_DIR} && {py} -c \"from uvicorn.importer import import_from_string; import_from_string('openclaw_agent:app'); print('ok')\"", timeout=15)
        if "ok" not in chk.get("stdout", ""):
            Path(agent_file).write_text(backups["openclaw_agent.py"], encoding="utf-8")
            return {"ok": False, "error": f"新代码验证失败，已回滚: {chk.get('stderr', '')[:200]}"}
    # 更新依赖
    venv_pip = os.path.join(INSTALL_DIR, "venv", "bin", "pip")
    if os.path.exists(venv_pip):
        result = await run_cmd(f"{venv_pip} install -q -r {os.path.join(INSTALL_DIR, 'requirements.txt')}")
        if not result["ok"]:
            return {"ok": False, "error": f"依赖安装失败: {result['stderr']}"}
    # 重启服务
    import platform
    if platform.system() == "Darwin":
        uid = os.getuid()
        label = "com.openclaw.agent"
        plist = os.path.expanduser(f"~/Library/LaunchAgents/{label}.plist")
        await run_cmd(f"launchctl kickstart -k gui/{uid}/{label}")
    else:
        await run_cmd("systemctl restart openclaw-agent")
    return {"ok": True, "msg": "更新完成，服务重启中", "updated": updated}


@app.get("/acp/detect", dependencies=[auth])
async def acp_detect():
    """检测 ACP 编程工具及基础依赖安装状态"""
    import platform
    is_mac = platform.system() == "Darwin"
    tools = {
        "kiro-cli":  {"install_cmd": "curl -fsSL https://kiro.dev/install.sh | bash", "desc": "Kiro CLI - AWS AI 编程助手"},
        "codex":     {"install_cmd": "npm install -g @openai/codex", "desc": "OpenAI Codex CLI"},
        "claude":    {"install_cmd": "npm install -g @anthropic-ai/claude-code @musistudio/claude-code-router", "desc": "Claude Code + Router（通过 CCR 支持多模型）"},
        "ccr":       {"install_cmd": "npm install -g @musistudio/claude-code-router", "desc": "Claude Code Router — Claude Code 多模型路由"},
        "gemini":    {"install_cmd": "npm install -g @google/gemini-cli", "desc": "Gemini CLI - Google 编程助手"},
        "opencode":  {"install_cmd": "npm install -g opencode", "desc": "OpenCode CLI"},
        "pi":        {"install_cmd": "npm install -g @anthropic-ai/pi", "desc": "Pi CLI"},
    }
    results = {}
    # 基础依赖检测
    node_r = await run_cmd("command -v node && node --version 2>/dev/null || echo NOT_FOUND", timeout=5)
    npm_r = await run_cmd("command -v npm && npm --version 2>/dev/null || echo NOT_FOUND", timeout=5)
    git_r = await run_cmd("command -v git && git --version 2>/dev/null || echo NOT_FOUND", timeout=5)
    brew_r = await run_cmd("command -v brew && brew --version 2>/dev/null | head -1 || echo NOT_FOUND", timeout=5) if is_mac else {"stdout": "N/A"}
    # npm 镜像
    npm_reg = await run_cmd("npm config get registry 2>/dev/null || echo unknown", timeout=5) if "NOT_FOUND" not in npm_r.get("stdout", "") else {"stdout": ""}
    results["_env"] = {
        "os": platform.system(),
        "arch": platform.machine(),
        "node": node_r.get("stdout", "").strip()[:100],
        "npm": npm_r.get("stdout", "").strip()[:100],
        "has_node": "NOT_FOUND" not in node_r.get("stdout", ""),
        "has_npm": "NOT_FOUND" not in npm_r.get("stdout", ""),
        "git": git_r.get("stdout", "").strip()[:100],
        "has_git": "NOT_FOUND" not in git_r.get("stdout", ""),
        "brew": brew_r.get("stdout", "").strip()[:100] if is_mac else None,
        "has_brew": "NOT_FOUND" not in brew_r.get("stdout", "") if is_mac else None,
        "npm_registry": npm_reg.get("stdout", "").strip()[:200],
    }
    for name, meta in tools.items():
        r = await run_cmd(f"command -v {name} 2>/dev/null", timeout=5)
        path = r.get("stdout", "").strip() if r.get("ok") else ""
        ver = ""
        if path:
            rv = await run_cmd(f"{name} --version 2>/dev/null || echo unknown", timeout=5)
            ver = rv.get("stdout", "").strip()[:80]
        results[name] = {"installed": bool(path), "path": path, "version": ver, **meta}
    # acpx CLI
    acpx_path = await _find_acpx()
    acpx_ver = ""
    if acpx_path:
        rv = await run_cmd(f"'{acpx_path}' --version 2>/dev/null", timeout=5)
        acpx_ver = rv.get("stdout", "").strip()[:80]
    results["_acpx_cli"] = {"installed": bool(acpx_path), "path": acpx_path, "version": acpx_ver}
    # acpx 插件
    acpx = await run_cmd("command -v openclaw >/dev/null 2>&1 && openclaw plugins list 2>/dev/null | grep -i acpx || echo ''", timeout=10)
    results["_acpx_plugin"] = {"installed": "acpx" in acpx.get("stdout", ""), "raw": acpx.get("stdout", "").strip()[:200]}
    # gstack 技能包
    gstack_dir = os.path.expanduser("~/.claude/skills/gstack")
    results["_gstack"] = {"installed": os.path.isdir(gstack_dir)}
    # CCR 服务状态
    ccr_port = await run_cmd("curl -s --connect-timeout 2 http://localhost:3456/health", timeout=5)
    ccr_cfg_exists = os.path.isfile(os.path.expanduser("~/.claude-code-router/config.json"))
    results["_ccr_service"] = {
        "running": "ok" in ccr_port.get("stdout", "").lower(),
        "config_exists": ccr_cfg_exists,
    }
    return results


# 安装命令映射（macOS 和 Linux 通用）
_ACP_INSTALL = {
    "kiro-cli": "curl -fsSL https://kiro.dev/install.sh | bash",
    "codex":    "npm install -g @openai/codex",
    "claude":   "npm install -g @anthropic-ai/claude-code @musistudio/claude-code-router",
    "ccr":      "npm install -g @musistudio/claude-code-router",
    "gemini":   "npm install -g @google/gemini-cli",
    "opencode": "npm install -g opencode",
    "pi":       "npm install -g @anthropic-ai/pi",
    "acpx":     "command -v openclaw >/dev/null && openclaw plugins install acpx && openclaw config set plugins.entries.acpx.enabled true",
}


@app.post("/acp/install", dependencies=[auth])
async def acp_install(req: dict):
    """安装 ACP 工具，npm 安装前自动检测镜像"""
    name = req.get("tool", "")
    if name not in _ACP_INSTALL:
        raise HTTPException(400, f"不支持安装: {name}")
    cmd = _ACP_INSTALL[name]
    mirror_used = ""
    # npm install 类命令：先确保镜像可用
    if "npm install" in cmd:
        reg = await run_cmd("npm config get registry 2>/dev/null", timeout=5)
        cur_reg = reg.get("stdout", "").strip()
        if "npmmirror" not in cur_reg and "mirrors" not in cur_reg:
            if not await _can_reach("registry.npmjs.org"):
                await run_cmd("npm config set registry https://registry.npmmirror.com", timeout=5)
                mirror_used = "npmmirror（自动设置）"
    result = await run_cmd(cmd, timeout=120)
    if mirror_used:
        result["mirror"] = mirror_used
    # 安装涉及 acpx 的工具后，自动设置 acpx 插件路径
    if name in ("acpx", "claude", "ccr") and result.get("ok"):
        await _ensure_acpx_config()
    # 安装 claude/ccr 后自动确保 CCR systemd 守护 + 环境变量持久化
    if name in ("claude", "ccr") and result.get("ok"):
        if os.path.isfile(os.path.expanduser("~/.claude-code-router/config.json")):
            if await _ensure_ccr_service():
                result["ccr_service"] = "已创建 systemd 守护"
        _persist_ccr_env()
        # Linux: systemd override
        import platform
        if platform.system() != "Darwin":
            ovr = os.path.expanduser("~/.config/systemd/user/openclaw-gateway.service.d/override.conf")
            os.makedirs(os.path.dirname(ovr), exist_ok=True)
            content = Path(ovr).read_text("utf-8") if os.path.isfile(ovr) else "[Service]\n"
            changed = False
            if "ANTHROPIC_API_KEY" not in content:
                content += "Environment=ANTHROPIC_API_KEY=sk-ant-placeholder-for-ccr\n"
                changed = True
            if "ANTHROPIC_BASE_URL" not in content:
                content += "Environment=ANTHROPIC_BASE_URL=http://localhost:3456\n"
                changed = True
            if changed:
                Path(ovr).write_text(content, "utf-8")
                result["env_override"] = "已写入 systemd override"
    return result


@app.post("/acp/install-brew", dependencies=[auth])
async def acp_install_brew():
    """安装 Homebrew（仅 macOS），大陆网络自动使用清华镜像"""
    import platform
    if platform.system() != "Darwin":
        return {"ok": True, "msg": "非 macOS，无需安装 Homebrew", "skipped": True}
    chk = await run_cmd("command -v brew", timeout=3)
    if chk.get("ok"):
        ver = await run_cmd("brew --version 2>/dev/null | head -1", timeout=5)
        return {"ok": True, "msg": f"Homebrew 已安装: {ver.get('stdout', '').strip()}", "skipped": True}
    mirror_used = ""
    if await _can_reach("raw.githubusercontent.com"):
        r = await run_cmd('NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"', timeout=300)
    else:
        # 大陆镜像：清华源
        mirror_used = "清华镜像"
        r = await run_cmd(
            'export HOMEBREW_BREW_GIT_REMOTE="https://mirrors.tuna.tsinghua.edu.cn/git/homebrew/brew.git" '
            'HOMEBREW_CORE_GIT_REMOTE="https://mirrors.tuna.tsinghua.edu.cn/git/homebrew/homebrew-core.git" '
            'HOMEBREW_INSTALL_FROM_API=1 NONINTERACTIVE=1 && '
            '/bin/bash -c "$(curl -fsSL https://mirrors.tuna.tsinghua.edu.cn/git/homebrew/install/raw/HEAD/install.sh)"',
            timeout=300
        )
    # Apple Silicon 需要加 PATH
    await run_cmd('[ -f /opt/homebrew/bin/brew ] && echo \'eval "$(/opt/homebrew/bin/brew shellenv)"\' >> ~/.zprofile && eval "$(/opt/homebrew/bin/brew shellenv)"', timeout=5)
    ver = await run_cmd("brew --version 2>/dev/null | head -1", timeout=5)
    ok = ver.get("ok", False)
    return {"ok": ok, "msg": ver.get("stdout", "").strip() if ok else "安装失败", "mirror": mirror_used, "detail": r.get("stderr", "")[:500]}


@app.post("/acp/install-node", dependencies=[auth])
async def acp_install_node():
    """安装 Node.js 20 LTS，大陆网络自动使用 npmmirror 兜底"""
    import platform
    is_mac = platform.system() == "Darwin"
    # 已安装则跳过
    chk = await run_cmd("command -v node && node --version 2>/dev/null", timeout=5)
    if chk.get("ok") and chk.get("stdout", "").strip():
        return {"ok": True, "msg": f"Node.js 已安装: {chk['stdout'].strip()}", "skipped": True}
    mirror_used = ""
    if is_mac:
        if not (await run_cmd("command -v brew", timeout=3)).get("ok"):
            return {"ok": False, "msg": "macOS 需要先安装 Homebrew，请调用 /acp/install-brew"}
        r = await run_cmd("brew install node@20 && brew link node@20 --force --overwrite 2>/dev/null || true", timeout=180)
    else:
        has_apt = (await run_cmd("command -v apt-get", timeout=3)).get("ok")
        has_yum = (await run_cmd("command -v yum", timeout=3)).get("ok")
        has_dnf = (await run_cmd("command -v dnf", timeout=3)).get("ok")
        can_reach_ns = await _can_reach("deb.nodesource.com")
        if can_reach_ns:
            # 海外源可达，用 NodeSource
            if has_apt:
                r = await run_cmd("curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs", timeout=180)
            elif has_dnf:
                r = await run_cmd("curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash - && sudo dnf install -y nodejs", timeout=180)
            elif has_yum:
                r = await run_cmd("curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash - && sudo yum install -y nodejs", timeout=180)
            else:
                return {"ok": False, "msg": "未检测到 apt/yum/dnf 包管理器"}
        else:
            # 大陆网络：用 npmmirror 的 node 二进制安装
            mirror_used = "npmmirror"
            r = await run_cmd(
                'ARCH=$(uname -m | sed "s/x86_64/x64/;s/aarch64/arm64/") && '
                'curl -fsSL "https://npmmirror.com/mirrors/node/v20.18.0/node-v20.18.0-linux-${ARCH}.tar.xz" -o /tmp/node.tar.xz && '
                'sudo tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1 && '
                'rm -f /tmp/node.tar.xz',
                timeout=180
            )
    # 验证
    ver = await run_cmd("node --version 2>/dev/null", timeout=5)
    ok = ver.get("ok", False)
    return {"ok": ok, "msg": ver.get("stdout", "").strip() if ok else "安装失败", "mirror": mirror_used, "detail": r.get("stderr", "")[:500]}


@app.post("/acp/install-git", dependencies=[auth])
async def acp_install_git():
    """安装 Git（macOS 用 brew，Linux 用系统包管理器）"""
    import platform
    is_mac = platform.system() == "Darwin"
    chk = await run_cmd("command -v git && git --version 2>/dev/null", timeout=5)
    if chk.get("ok") and chk.get("stdout", "").strip():
        return {"ok": True, "msg": f"Git 已安装: {chk['stdout'].strip()}", "skipped": True}
    if is_mac:
        if not (await run_cmd("command -v brew", timeout=3)).get("ok"):
            return {"ok": False, "msg": "macOS 需要先安装 Homebrew，请调用 /acp/install-brew"}
        r = await run_cmd("brew install git", timeout=120)
    else:
        has_apt = (await run_cmd("command -v apt-get", timeout=3)).get("ok")
        has_yum = (await run_cmd("command -v yum", timeout=3)).get("ok")
        has_dnf = (await run_cmd("command -v dnf", timeout=3)).get("ok")
        if has_apt:
            r = await run_cmd("sudo apt-get install -y git", timeout=120)
        elif has_dnf:
            r = await run_cmd("sudo dnf install -y git", timeout=120)
        elif has_yum:
            r = await run_cmd("sudo yum install -y git", timeout=120)
        else:
            return {"ok": False, "msg": "未检测到 apt/yum/dnf 包管理器"}
    ver = await run_cmd("git --version 2>/dev/null", timeout=5)
    ok = ver.get("ok", False)
    return {"ok": ok, "msg": ver.get("stdout", "").strip() if ok else "安装失败"}


@app.post("/acp/npm-mirror", dependencies=[auth])
async def acp_npm_mirror(req: dict = {}):
    """检测 npm 源并可选设置国内镜像"""
    action = req.get("action", "detect")  # detect | set | reset
    if action == "set":
        mirror = req.get("mirror", "https://registry.npmmirror.com")
        r = await run_cmd(f"npm config set registry {mirror}", timeout=10)
        cur = await run_cmd("npm config get registry 2>/dev/null", timeout=5)
        return {"ok": r.get("ok", False), "registry": cur.get("stdout", "").strip()}
    elif action == "reset":
        r = await run_cmd("npm config set registry https://registry.npmjs.org", timeout=10)
        return {"ok": r.get("ok", False), "registry": "https://registry.npmjs.org"}
    # detect — 检测当前源和连通性
    cur = await run_cmd("npm config get registry 2>/dev/null", timeout=5)
    registry = cur.get("stdout", "").strip()
    # 测试官方源连通性
    test = await run_cmd("curl -s --connect-timeout 5 -o /dev/null -w '%{http_code}' https://registry.npmjs.org", timeout=10)
    npm_ok = test.get("stdout", "").strip() == "200"
    return {"registry": registry, "npm_reachable": npm_ok, "suggest_mirror": not npm_ok}


@app.post("/acp/install-gstack", dependencies=[auth])
async def acp_install_gstack():
    """安装 gstack 技能包，大陆网络自动使用 ghproxy 镜像"""
    gstack_dir = os.path.expanduser("~/.claude/skills/gstack")
    skills_dir = os.path.expanduser("~/.claude/skills")
    os.makedirs(skills_dir, exist_ok=True)
    if os.path.isdir(gstack_dir):
        r = await run_cmd(f"cd {gstack_dir} && git pull 2>&1", timeout=30)
        return {"ok": True, "msg": "gstack 已更新", "detail": r.get("stdout", "").strip()[:300]}
    # 先尝试 GitHub，不通则用 ghproxy 镜像
    mirror_used = ""
    if await _can_reach("github.com"):
        repo_url = "https://github.com/garrytan/gstack.git"
    else:
        mirror_used = "ghproxy"
        repo_url = "https://ghproxy.com/https://github.com/garrytan/gstack.git"
    r = await run_cmd(f"git clone {repo_url} {gstack_dir} 2>&1", timeout=60)
    ok = os.path.isdir(gstack_dir)
    return {"ok": ok, "msg": "gstack 安装成功" if ok else "安装失败", "mirror": mirror_used, "detail": r.get("stdout", r.get("stderr", "")).strip()[:500]}


@app.post("/acp/clean-env", dependencies=[auth])
async def acp_clean_env():
    """完整清理旧环境 — 停止 CCR、清理端口、清理认证缓存、清理环境变量"""
    results = []
    # 停止 CCR
    await run_cmd("command -v ccr >/dev/null && ccr stop 2>/dev/null || true", timeout=5)
    results.append("CCR 已停止")
    # 清理端口
    await run_cmd("lsof -ti :3456 | xargs kill -9 2>/dev/null || true", timeout=5)
    results.append("端口 3456 已清理")
    # 清理认证缓存
    await run_cmd("rm -rf ~/.claude/auth* ~/.claude/.credentials* ~/.claude/statsig* ~/.claude/oauth* ~/.claude/session* ~/.claude/settings.local.json 2>/dev/null || true", timeout=5)
    results.append("Claude 认证缓存已清理")
    # 清理环境变量
    for key in ["ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL"]:
        os.environ.pop(key, None)
        _ENV.pop(key, None)
    results.append("环境变量已清理")
    return {"ok": True, "results": results}


@app.post("/acp/ccr/config", dependencies=[auth])
async def acp_ccr_config(req: dict):
    """生成 Claude Code Router 配置文件
    接收 providers 数组和 router 配置，写入 ~/.claude-code-router/config.json
    """
    providers = req.get("providers", [])
    router = req.get("router", {})
    if not providers:
        raise HTTPException(400, "至少需要一个 provider")
    ccr_dir = os.path.expanduser("~/.claude-code-router")
    os.makedirs(ccr_dir, exist_ok=True)
    config = {
        "LOG": True,
        "LOG_LEVEL": "info",
        "API_TIMEOUT_MS": req.get("timeout", 600000),
        "Providers": providers,
        "Router": router or {"default": f"{providers[0]['name']},{providers[0].get('models',[''])[0]}"},
    }
    cfg_path = os.path.join(ccr_dir, "config.json")
    # 备份旧配置
    if os.path.isfile(cfg_path):
        bak = cfg_path + f".bak.{int(time.time())}"
        os.rename(cfg_path, bak)
    with open(cfg_path, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    return {"ok": True, "path": cfg_path, "providers": len(providers)}


@app.post("/acp/ccr/stop", dependencies=[auth])
async def acp_ccr_stop():
    """停止 CCR 服务"""
    await run_cmd("command -v ccr >/dev/null && ccr stop 2>/dev/null || true", timeout=5)
    await run_cmd("lsof -ti :3456 | xargs kill -9 2>/dev/null || true", timeout=5)
    chk = await run_cmd("lsof -i :3456 -sTCP:LISTEN -t 2>/dev/null || ss -tln 2>/dev/null | grep ':3456'", timeout=3)
    stopped = not chk.get("stdout", "").strip()
    if stopped:
        os.environ.pop("ANTHROPIC_BASE_URL", None)
        _ENV.pop("ANTHROPIC_BASE_URL", None)
    return {"ok": stopped, "msg": "已停止" if stopped else "端口 3456 仍在监听"}

def _persist_ccr_env():
    """将 CCR 环境变量持久化到所有需要的位置，并写入内存"""
    import platform
    pairs = {"ANTHROPIC_BASE_URL": "http://localhost:3456", "ANTHROPIC_API_KEY": "sk-ant-placeholder-for-ccr"}
    # 写内存
    for k, v in pairs.items():
        os.environ[k] = v
        _ENV[k] = v
    # 写 ~/.openclaw/.env
    env_file = os.path.expanduser("~/.openclaw/.env")
    os.makedirs(os.path.dirname(env_file), exist_ok=True)
    existing = Path(env_file).read_text("utf-8") if os.path.isfile(env_file) else ""
    changed = False
    for k, v in pairs.items():
        if k not in existing:
            existing += f"\n{k}={v}"
            changed = True
    if changed:
        Path(env_file).write_text(existing.strip() + "\n", "utf-8")
    # 写 ~/.profile
    profile = os.path.expanduser("~/.profile")
    try:
        pf = open(profile).read() if os.path.isfile(profile) else ""
        lines = []
        for k, v in pairs.items():
            if k not in pf:
                lines.append(f'export {k}="{v}"')
        if lines:
            with open(profile, "a") as f:
                f.write("\n# Claude Code Router\n" + "\n".join(lines) + "\n")
    except Exception:
        pass
    # macOS: 注入 gateway plist
    if platform.system() == "Darwin":
        plist_path = os.path.expanduser("~/Library/LaunchAgents/ai.openclaw.gateway.plist")
        if os.path.isfile(plist_path):
            try:
                import plistlib
                with open(plist_path, "rb") as f:
                    plist = plistlib.load(f)
                env_dict = plist.setdefault("EnvironmentVariables", {})
                plist_changed = False
                for k, v in pairs.items():
                    if env_dict.get(k) != v:
                        env_dict[k] = v
                        plist_changed = True
                if plist_changed:
                    with open(plist_path, "wb") as f:
                        plistlib.dump(plist, f)
            except Exception:
                pass


async def _ensure_ccr_service():
    """Linux: 确保 CCR 有 systemd service（自动重启守护）。返回是否新创建。"""
    import platform
    if platform.system() == "Darwin":
        return False
    svc_path = "/etc/systemd/system/ccr.service"
    if os.path.isfile(svc_path):
        return False
    ccr_bin = (await run_cmd("command -v ccr", timeout=3)).get("stdout", "").strip()
    if not ccr_bin:
        return False
    svc = (
        "[Unit]\nDescription=Claude Code Router\nAfter=network.target\n\n"
        f"[Service]\nType=simple\nExecStart={ccr_bin} start\n"
        "Restart=always\nRestartSec=3\n"
        f"Environment=HOME={os.path.expanduser('~')}\n"
        "Environment=PATH=/usr/local/bin:/usr/bin:/bin\n\n"
        "[Install]\nWantedBy=multi-user.target\n"
    )
    Path(svc_path).write_text(svc, encoding="utf-8")
    await run_cmd("systemctl daemon-reload && systemctl enable ccr", timeout=10)
    return True


async def _ensure_acpx_config():
    """确保 openclaw.json 里 acpx 插件的 command 和 expectedVersion 已设置"""
    acpx_path = await _find_acpx()
    if not acpx_path:
        return False
    try:
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        pc = cfg.setdefault("plugins", {}).setdefault("entries", {}).setdefault("acpx", {}).setdefault("config", {})
        if pc.get("command") == acpx_path and pc.get("expectedVersion") == "any":
            return False
        pc["command"] = acpx_path
        pc["expectedVersion"] = "any"
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


@app.post("/acp/ccr/start", dependencies=[auth])
async def acp_ccr_start(req: dict = {}):
    """启动/重启 Claude Code Router 服务"""
    import platform
    is_mac = platform.system() == "Darwin"
    # 先停掉已有的
    await run_cmd("command -v ccr >/dev/null && ccr stop 2>/dev/null || true", timeout=5)
    await run_cmd("lsof -ti :3456 | xargs kill -9 2>/dev/null || true", timeout=5)
    await asyncio.sleep(1)
    # 清理 claude 认证缓存（避免冲突）
    if req.get("clean_auth", False):
        await run_cmd("rm -rf ~/.claude/auth* ~/.claude/.credentials* ~/.claude/statsig* ~/.claude/oauth* ~/.claude/session* 2>/dev/null || true", timeout=3)
    # Linux 优先用 systemctl
    if not is_mac:
        await _ensure_ccr_service()
        svc_r = await run_cmd("systemctl cat ccr 2>/dev/null", timeout=3)
        if svc_r.get("ok") and "ccr" in svc_r.get("stdout", ""):
            await run_cmd("systemctl restart ccr", timeout=10)
            for i in range(10):
                await asyncio.sleep(1)
                chk = await run_cmd("curl -s --connect-timeout 1 http://localhost:3456/health", timeout=3)
                if "ok" in chk.get("stdout", "").lower():
                    _persist_ccr_env()
                    os.environ["ANTHROPIC_BASE_URL"] = "http://localhost:3456"
                    _ENV["ANTHROPIC_BASE_URL"] = "http://localhost:3456"
                    return {"ok": True, "msg": "CCR 服务已启动 (systemd, 端口 3456)"}
            log = await run_cmd("journalctl -u ccr --no-pager -n 20", timeout=3)
            return {"ok": False, "msg": "CCR 启动超时", "log": log.get("stdout", "").strip()[:2000]}
    # macOS 或无 systemd：Popen detach
    import subprocess
    log_path = os.path.expanduser("~/.claude-code-router/ccr.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    log_f = open(log_path, "w")
    subprocess.Popen(
        "exec ccr start", shell=True,
        stdout=log_f, stderr=log_f, stdin=subprocess.DEVNULL,
        start_new_session=True, env={**os.environ, **({"PATH": _ENV["PATH"]} if "PATH" in _ENV else {})}
    )
    # 轮询健康检查
    for i in range(15):
        await asyncio.sleep(1)
        chk = await run_cmd("curl -s --connect-timeout 1 http://localhost:3456/health", timeout=3)
        if "ok" in chk.get("stdout", "").lower():
            # CCR 启动成功，持久化环境变量
            _persist_ccr_env()
            os.environ["ANTHROPIC_BASE_URL"] = "http://localhost:3456"
            _ENV["ANTHROPIC_BASE_URL"] = "http://localhost:3456"
            # 重启 gateway 让环境变量生效
            if is_mac:
                await run_cmd("launchctl kickstart -k gui/$(id -u)/ai.openclaw.gateway 2>/dev/null || true", timeout=10)
            return {"ok": True, "msg": "CCR 服务已启动 (端口 3456)"}
    # 失败时读取日志
    log = await run_cmd(f"tail -30 {log_path} 2>/dev/null || echo '日志文件不存在'", timeout=3)
    return {"ok": False, "msg": "CCR 启动超时", "log": log.get("stdout", "").strip()[:2000]}


@app.get("/acp/ccr/status", dependencies=[auth])
async def acp_ccr_status():
    """检查 CCR 服务状态"""
    chk = await run_cmd("curl -s --connect-timeout 2 http://localhost:3456/health", timeout=5)
    running = "ok" in chk.get("stdout", "").lower()
    cfg_path = os.path.expanduser("~/.claude-code-router/config.json")
    cfg_exists = os.path.isfile(cfg_path)
    cfg = {}
    if cfg_exists:
        try:
            with open(cfg_path) as f:
                cfg = json.load(f)
        except Exception:
            pass
    return {
        "running": running,
        "config_exists": cfg_exists,
        "providers": [p.get("name") for p in cfg.get("Providers", [])],
        "router": cfg.get("Router", {}),
    }


@app.get("/version", dependencies=[auth])
async def version():
    """返回当前代码的最后修改时间作为版本标识"""
    agent_file = os.path.join(INSTALL_DIR, "openclaw_agent.py")
    mtime = os.path.getmtime(agent_file) if os.path.exists(agent_file) else 0
    return {"version": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S"), "install_dir": INSTALL_DIR}


# ── TUI / Agent 对话 ────────────────────────────────────

@app.post("/agent/send", dependencies=[auth])
async def agent_send(req: dict):
    """向指定 agent 发送消息并返回 JSON 结果"""
    agent = req.get("agent", "").strip()
    message = req.get("message", "").strip()
    if not agent or not message:
        raise HTTPException(400, "agent 和 message 不能为空")
    session_id = req.get("session_id", "").strip() or f"debug-{int(datetime.now().timestamp())}"
    thinking = req.get("thinking", "")
    timeout_sec = min(int(req.get("timeout", 120)), 300)
    safe_msg = message.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")
    cmd = f'openclaw agent --agent {agent} --session-id {session_id} --message "{safe_msg}" --json --timeout {timeout_sec}'
    if thinking:
        cmd += f' --thinking {thinking}'
    cmd += ' 2>&1'
    result = await run_cmd(cmd, timeout=timeout_sec + 10)
    stdout = result.get("stdout", "")
    # 从末尾找最大 JSON 对象
    reply_text, meta, warnings = "", {}, []
    if "falling back to embedded" in stdout:
        warnings.append("Gateway 连接失败，已回退到 embedded 模式")
    if "Unknown agent id" in stdout:
        import re
        m = re.search(r'Unknown agent id "([^"]+)"', stdout)
        warnings.append(f"未知 Agent: {m.group(1) if m else agent}")
    data = _find_last_json(stdout)
    if data:
        for p in data.get("payloads", []):
            if p.get("text"):
                reply_text += p["text"]
        am = data.get("meta", {}).get("agentMeta", {})
        if am:
            usage = am.get("usage", {})
            meta = {
                "model": am.get("model", ""),
                "provider": am.get("provider", ""),
                "sessionId": am.get("sessionId", ""),
                "durationMs": data.get("meta", {}).get("durationMs"),
                "inputTokens": usage.get("input"),
                "outputTokens": usage.get("output"),
                "cacheRead": usage.get("cacheRead"),
                "totalTokens": usage.get("total"),
                "stopReason": data.get("meta", {}).get("stopReason", ""),
            }
    if not reply_text and not data:
        reply_text = stdout[:2000] if stdout else ""
    return {"reply": reply_text, "session_id": session_id, "meta": meta, "warnings": warnings, "raw_length": len(stdout)}


@app.post("/sessions/close", dependencies=[auth])
async def sessions_close(req: dict):
    """关闭（删除）指定会话"""
    agent_id = req.get("agent", "").strip()
    session_key = req.get("key", "").strip()
    if not agent_id or not session_key:
        raise HTTPException(400, "agent 和 key 不能为空")
    agents_dir = os.path.join(OPENCLAW_HOME, ".openclaw", "agents")
    store_path = os.path.join(agents_dir, agent_id, "sessions", "sessions.json")
    if not os.path.isfile(store_path):
        return {"ok": False, "error": "会话存储文件不存在"}
    try:
        with open(store_path) as f:
            store = json.load(f)
        entry = store.pop(session_key, None)
        with open(store_path, "w") as f:
            json.dump(store, f, indent=2, ensure_ascii=False)
        sid = entry.get("sessionId", "") if entry else ""
        transcript = os.path.join(agents_dir, agent_id, "sessions", f"{sid}.jsonl") if sid else ""
        removed = bool(transcript and os.path.exists(transcript))
        if removed:
            os.remove(transcript)
        return {"ok": bool(entry), "sessionId": sid, "transcriptRemoved": removed}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def _find_acpx() -> str:
    """查找 acpx 可执行文件路径，优先全局 PATH，再找 OpenClaw 内置路径"""
    r = await run_cmd("command -v acpx 2>/dev/null", timeout=3)
    if r.get("ok") and r.get("stdout", "").strip():
        return r["stdout"].strip()
    # OpenClaw 内置路径（macOS brew / Linux npm global）
    candidates = [
        "/opt/homebrew/lib/node_modules/openclaw/extensions/acpx/node_modules/.bin/acpx",
        "/usr/local/lib/node_modules/openclaw/extensions/acpx/node_modules/.bin/acpx",
        "/usr/lib/node_modules/openclaw/extensions/acpx/node_modules/.bin/acpx",
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    # 兜底：find
    r2 = await run_cmd("find /opt/homebrew /usr/local/lib /usr/lib -path '*/openclaw/extensions/acpx/node_modules/.bin/acpx' 2>/dev/null | head -1", timeout=5)
    return r2.get("stdout", "").strip()


@app.get("/acp/health", dependencies=[auth])
async def acp_health():
    """ACP 链路健康检查"""
    import platform
    is_mac = platform.system() == "Darwin"
    checks = []
    # 1. acpx CLI + 版本对比
    acpx_path = await _find_acpx()
    if acpx_path:
        ver_r = await run_cmd(f"'{acpx_path}' --version 2>/dev/null", timeout=5)
        local_ver = ver_r.get("stdout", "").strip()[:50]
        latest_r = await run_cmd("npm view acpx version 2>/dev/null", timeout=10)
        latest_ver = latest_r.get("stdout", "").strip()[:50]
        upgradable = bool(latest_ver) and latest_ver != local_ver
        detail = f"已安装 ({local_ver})"
        if upgradable:
            detail += f" → 最新 {latest_ver}"
        checks.append({"name": "acpx CLI", "ok": True, "detail": detail, "upgradable": upgradable, "local_version": local_ver, "latest_version": latest_ver})
    else:
        checks.append({"name": "acpx CLI", "ok": False, "detail": "未找到 acpx"})
    # 2. CCR 服务（仅当配置存在时检查，非必须项）
    ccr_cfg_exists = os.path.isfile(os.path.expanduser("~/.claude-code-router/config.json"))
    ccr_r = await run_cmd("curl -s --connect-timeout 3 http://localhost:3456/health", timeout=5)
    ccr_ok = "ok" in ccr_r.get("stdout", "").lower()
    ccr_detail = ccr_r.get("stdout", "").strip()[:100] if ccr_cfg_exists else "未配置（非必须）"
    if ccr_cfg_exists and not is_mac:
        has_svc = os.path.isfile("/etc/systemd/system/ccr.service")
        ccr_detail += " (systemd 守护)" if has_svc else " ⚠ 无 systemd 守护，可能意外退出"
    checks.append({"name": "CCR 服务", "ok": ccr_ok or not ccr_cfg_exists, "detail": ccr_detail, "optional": not ccr_cfg_exists})
    # 3. Gateway 环境变量
    gw_pid_r = await run_cmd("pgrep -f 'openclaw.*gateway' | head -1", timeout=3)
    gw_pid = gw_pid_r.get("stdout", "").strip()
    base_url_ok, api_key_ok = False, False
    if gw_pid:
        if platform.system() == "Darwin":
            env_r = await run_cmd(f"ps eww -p {gw_pid} 2>/dev/null", timeout=3)
        else:
            env_r = await run_cmd(f"cat /proc/{gw_pid}/environ 2>/dev/null | tr '\\0' '\\n'", timeout=3)
        env_out = env_r.get("stdout", "")
        base_url_ok = "ANTHROPIC_BASE_URL" in env_out
        api_key_ok = "ANTHROPIC_API_KEY" in env_out
    checks.append({"name": "ANTHROPIC_BASE_URL", "ok": base_url_ok, "detail": "localhost:3456" if base_url_ok else "未设置"})
    checks.append({"name": "ANTHROPIC_API_KEY", "ok": api_key_ok, "detail": "已设置" if api_key_ok else "未设置"})
    # 4. acpx 插件
    plugin_r = await run_cmd("openclaw plugins list 2>/dev/null | grep -i acpx", timeout=10)
    plugin_ok = "acpx" in plugin_r.get("stdout", "").lower() and "loaded" in plugin_r.get("stdout", "").lower()
    checks.append({"name": "acpx 插件", "ok": plugin_ok, "detail": plugin_r.get("stdout", "").strip()[:150]})
    # 5. ACP 配置
    acp_cfg, acpx_plugin_cfg = {}, {}
    try:
        with open(CONFIG_PATH) as f:
            full_cfg = json.load(f)
            acp_cfg = full_cfg.get("acp", {})
            acpx_plugin_cfg = full_cfg.get("plugins", {}).get("entries", {}).get("acpx", {}).get("config", {})
    except Exception:
        pass
    acp_ok = acp_cfg.get("enabled", False) and acp_cfg.get("backend") == "acpx"
    checks.append({"name": "ACP 配置", "ok": acp_ok, "detail": json.dumps(acp_cfg)[:200] if acp_cfg else "未配置"})
    # 6. acpx 插件 command 配置（避免 pnpm 深层路径问题）
    acpx_cmd = acpx_plugin_cfg.get("command", "")
    acpx_ver = acpx_plugin_cfg.get("expectedVersion", "")
    cmd_ok = bool(acpx_cmd) and acpx_ver == "any"
    checks.append({"name": "acpx 插件路径", "ok": cmd_ok, "detail": f"command={acpx_cmd or '未设置'}, expectedVersion={acpx_ver or '未设置'}"})
    # all_ok 不计 optional 项
    all_ok = all(c["ok"] for c in checks if not c.get("optional"))
    return {"checks": checks, "all_ok": all_ok}


@app.post("/acp/fix", dependencies=[auth])
async def acp_fix():
    """ACP 一键修复"""
    import platform
    is_mac = platform.system() == "Darwin"
    results = []
    # 1. acpx symlink — 从 OpenClaw 内置路径查找
    acpx_path = await _find_acpx()
    if acpx_path and "/usr/local/bin" not in acpx_path:
        # 解析真实路径
        if is_mac:
            real_r = await run_cmd(f"python3 -c \"import os;print(os.path.realpath('{acpx_path}'))\"", timeout=3)
        else:
            real_r = await run_cmd(f"readlink -f '{acpx_path}'", timeout=3)
        real_path = real_r.get("stdout", "").strip()
        if real_path and os.path.isfile(real_path):
            await run_cmd(f"sudo ln -sf '{real_path}' /usr/local/bin/acpx 2>/dev/null || ln -sf '{real_path}' /usr/local/bin/acpx", timeout=5)
            results.append(f"acpx symlink → {real_path}")
    elif not acpx_path:
        results.append("⚠ acpx 未找到，请确认 OpenClaw 已安装")
    # 2. 环境变量持久化
    _persist_ccr_env()
    if not is_mac:
        ovr = os.path.expanduser("~/.config/systemd/user/openclaw-gateway.service.d/override.conf")
        os.makedirs(os.path.dirname(ovr), exist_ok=True)
        content = Path(ovr).read_text("utf-8") if os.path.isfile(ovr) else "[Service]\n"
        changed = False
        if "ANTHROPIC_API_KEY" not in content:
            content += "Environment=ANTHROPIC_API_KEY=sk-ant-placeholder-for-ccr\n"
            changed = True
        if "ANTHROPIC_BASE_URL" not in content:
            content += "Environment=ANTHROPIC_BASE_URL=http://localhost:3456\n"
            changed = True
        if changed:
            Path(ovr).write_text(content, "utf-8")
            results.append("环境变量已写入 systemd override")
    # 3. ACP allowedAgents + acpx 插件 command
    try:
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        changed = False
        acp = cfg.get("acp", {})
        aa = set(acp.get("allowedAgents", []))
        need = {"claude", "claude-code", "codex", "gemini"}
        if not need.issubset(aa):
            acp["allowedAgents"] = sorted(aa | need)
            cfg["acp"] = acp
            changed = True
            results.append("allowedAgents 已修复")
        # acpx 插件 command 配置
        acpx_path = await _find_acpx()
        if acpx_path:
            pc = cfg.setdefault("plugins", {}).setdefault("entries", {}).setdefault("acpx", {}).setdefault("config", {})
            if pc.get("command") != acpx_path or pc.get("expectedVersion") != "any":
                pc["command"] = acpx_path
                pc["expectedVersion"] = "any"
                changed = True
                results.append(f"acpx 插件路径 → {acpx_path}")
        if changed:
            with open(CONFIG_PATH, "w") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
    # 4. CCR（仅当配置存在时）
    ccr_cfg = os.path.expanduser("~/.claude-code-router/config.json")
    if os.path.isfile(ccr_cfg):
        if await _ensure_ccr_service():
            results.append("CCR systemd service 已创建并启用")
        # 启动 CCR
        ccr_r = await run_cmd("curl -s --connect-timeout 2 http://localhost:3456/health", timeout=3)
        if "ok" not in ccr_r.get("stdout", "").lower():
            if is_mac:
                await run_cmd("nohup ccr start > /tmp/ccr.log 2>&1 &", timeout=3)
            else:
                await run_cmd("systemctl restart ccr 2>/dev/null || nohup ccr start > /tmp/ccr.log 2>&1 &", timeout=10)
            results.append("CCR 已启动")
    # 5. 重启 gateway
    if is_mac:
        await run_cmd("GW=$(pgrep -f 'openclaw.*gateway' | head -1); [ -n \"$GW\" ] && kill $GW; sleep 2; nohup openclaw gateway > /tmp/oc-gw.log 2>&1 &", timeout=10)
    else:
        await run_cmd("XDG_RUNTIME_DIR=/run/user/$(id -u) systemctl --user daemon-reload; XDG_RUNTIME_DIR=/run/user/$(id -u) systemctl --user restart openclaw-gateway", timeout=10)
    results.append("Gateway 已重启")
    return {"ok": True, "results": results}


@app.post("/acp/upgrade-acpx", dependencies=[auth])
async def acp_upgrade_acpx():
    """更新 OpenClaw（连带更新内嵌 acpx）"""
    # 检测包管理器
    pnpm_r = await run_cmd("command -v pnpm && pnpm list -g openclaw 2>/dev/null | grep openclaw", timeout=10)
    if "openclaw" in pnpm_r.get("stdout", ""):
        cmd = "pnpm add -g openclaw@latest"
    else:
        cmd = "npm install -g openclaw@latest"
    # 镜像检测
    mirror = ""
    if "npm" in cmd:
        reg = await run_cmd("npm config get registry 2>/dev/null", timeout=5)
        if "npmmirror" not in reg.get("stdout", "") and not await _can_reach("registry.npmjs.org"):
            await run_cmd("npm config set registry https://registry.npmmirror.com", timeout=5)
            mirror = "npmmirror"
    result = await run_cmd(cmd, timeout=180)
    # 更新后重建 symlink
    acpx_path = await _find_acpx()
    if acpx_path and "/usr/local/bin" not in acpx_path:
        real_r = await run_cmd(f"readlink -f '{acpx_path}' 2>/dev/null || python3 -c \"import os;print(os.path.realpath('{acpx_path}'))\"", timeout=3)
        real = real_r.get("stdout", "").strip()
        if real and os.path.isfile(real):
            await run_cmd(f"ln -sf '{real}' /usr/local/bin/acpx 2>/dev/null || sudo ln -sf '{real}' /usr/local/bin/acpx", timeout=5)
    # 新版本号
    ver_r = await run_cmd("acpx --version 2>/dev/null", timeout=5)
    result["new_version"] = ver_r.get("stdout", "").strip()[:50]
    if mirror:
        result["mirror"] = mirror
    return result


_ACPX_CLIENTS = {"codex", "claude", "gemini", "opencode", "pi"}


@app.post("/acp/acpx/exec", dependencies=[auth])
async def acpx_exec(req: dict):
    """通过 acpx 调用外部编程助手（codex/claude/gemini 等）"""
    client = req.get("client", "").strip()
    task = req.get("task", "").strip()
    if client not in _ACPX_CLIENTS:
        raise HTTPException(400, f"不支持的客户端: {client}，可选: {', '.join(sorted(_ACPX_CLIENTS))}")
    if not task:
        raise HTTPException(400, "task 不能为空")
    acpx_path = await _find_acpx()
    if not acpx_path:
        return {"ok": False, "error": "acpx 未找到，请先运行 ACP 修复"}
    session = req.get("session", "").strip()
    cwd = req.get("cwd", "").strip()
    approve = req.get("approve", "all")  # all | reads | deny
    timeout_sec = min(int(req.get("timeout", 120)), 300)
    safe_task = task.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")
    # 构建命令 — 注入 CCR 环境变量（如果 CCR 在运行）
    env_prefix = ""
    if os.environ.get("ANTHROPIC_BASE_URL") or _ENV.get("ANTHROPIC_BASE_URL"):
        base_url = os.environ.get("ANTHROPIC_BASE_URL") or _ENV.get("ANTHROPIC_BASE_URL")
        api_key = os.environ.get("ANTHROPIC_API_KEY") or _ENV.get("ANTHROPIC_API_KEY") or "sk-ant-placeholder-for-ccr"
        env_prefix = f'ANTHROPIC_BASE_URL="{base_url}" ANTHROPIC_API_KEY="{api_key}" '
    approve_flag = {"all": "--approve-all", "reads": "--approve-reads", "deny": "--deny-all"}.get(approve, "--approve-all")
    cmd = f"{env_prefix}'{acpx_path}' {approve_flag} --timeout {timeout_sec}"
    if session:
        cmd += f" {client} -s {session}"
    else:
        cmd += f" {client} exec"
    if cwd:
        cmd += f" --cwd '{cwd}'"
    cmd += f' "{safe_task}" 2>&1'
    result = await run_cmd(cmd, timeout=timeout_sec + 15)
    stdout = result.get("stdout", "")
    # 过滤 acpx 元信息，提取实际回复
    lines = stdout.split("\n")
    reply_lines = [l for l in lines if not l.startswith("[client]") and not l.startswith("[tool]") and not l.startswith("[thinking]") and l.strip() != "[done] end_turn"]
    reply = "\n".join(reply_lines).strip()
    return {
        "ok": result.get("ok", False),
        "reply": reply,
        "raw": stdout[:5000],
        "client": client,
        "session": session,
    }


@app.post("/acp/acpx/sessions", dependencies=[auth])
async def acpx_sessions(req: dict):
    """管理 acpx 会话（list/new/close/ensure）"""
    client = req.get("client", "").strip()
    action = req.get("action", "list").strip()  # list | new | close | ensure
    if client not in _ACPX_CLIENTS:
        raise HTTPException(400, f"不支持的客户端: {client}")
    acpx_path = await _find_acpx()
    if not acpx_path:
        return {"ok": False, "error": "acpx 未找到"}
    # CCR 环境变量
    env_prefix = ""
    if os.environ.get("ANTHROPIC_BASE_URL") or _ENV.get("ANTHROPIC_BASE_URL"):
        base_url = os.environ.get("ANTHROPIC_BASE_URL") or _ENV.get("ANTHROPIC_BASE_URL")
        api_key = os.environ.get("ANTHROPIC_API_KEY") or _ENV.get("ANTHROPIC_API_KEY") or "sk-ant-placeholder-for-ccr"
        env_prefix = f'ANTHROPIC_BASE_URL="{base_url}" ANTHROPIC_API_KEY="{api_key}" '
    acpx = f"{env_prefix}'{acpx_path}'"
    name = req.get("name", "").strip()
    if action == "list":
        r = await run_cmd(f"{acpx} {client} sessions 2>&1", timeout=15)
    elif action == "new":
        if not name:
            name = f"oc-{client}-{int(datetime.now().timestamp())}"
        r = await run_cmd(f"{acpx} {client} sessions new --name {name} 2>&1", timeout=15)
    elif action == "close":
        if not name:
            raise HTTPException(400, "关闭会话需要 name")
        r = await run_cmd(f"{acpx} {client} sessions close {name} 2>&1", timeout=15)
    elif action == "ensure":
        if not name:
            raise HTTPException(400, "ensure 需要 name")
        r = await run_cmd(f"{acpx} {client} sessions ensure --name {name} 2>&1", timeout=15)
    else:
        raise HTTPException(400, f"不支持的操作: {action}")
    return {"ok": r.get("ok", False), "output": r.get("stdout", "").strip()[:3000], "action": action, "client": client, "name": name}


def _find_last_json(text: str) -> dict:
    """从末尾反向查找包含 payloads/meta/sessions 的最大 JSON"""
    rpos = len(text) - 1
    while rpos >= 0:
        if text[rpos] == '}':
            depth = 0
            for i in range(rpos, -1, -1):
                if text[i] == '}': depth += 1
                elif text[i] == '{': depth -= 1
                if depth == 0:
                    try:
                        d = json.loads(text[i:rpos + 1])
                        if isinstance(d, dict) and ("payloads" in d or "meta" in d or "sessions" in d):
                            return d
                    except Exception:
                        pass
                    break
        rpos -= 1
    return {}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("OPENCLAW_AGENT_PORT", "9966"))
    print(f"📂 CONFIG_PATH: {CONFIG_PATH} ({'✅ found' if os.path.isfile(CONFIG_PATH) else '❌ not found'})")
    print(f"📂 OPENCLAW_HOME: {OPENCLAW_HOME}")
    uvicorn.run(app, host="0.0.0.0", port=port)
