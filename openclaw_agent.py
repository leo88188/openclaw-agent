"""
OpenClaw Agent - 轻量远程管理服务

部署在每台 OpenClaw 实例上，提供 HTTP API 供管理平台调用，替代 SSH 方式。
"""
import os
import json
import asyncio
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── 配置 ─────────────────────────────────────────────────
AGENT_TOKEN = os.getenv("OPENCLAW_AGENT_TOKEN", "changeme")
OPENCLAW_HOME = os.getenv("OPENCLAW_HOME", os.path.expanduser("~/.openclaw"))
CONFIG_PATH = os.getenv("OPENCLAW_CONFIG", os.path.join(OPENCLAW_HOME, "config.json"))
ENV_CONF_PATH = os.getenv(
    "OPENCLAW_ENV_CONF",
    os.path.expanduser("~/.config/systemd/user/openclaw-gateway.service.d/provider-models.conf"),
)
LOG_DIR = os.getenv("OPENCLAW_LOG_DIR", "/tmp/openclaw")

app = FastAPI(title="OpenClaw Agent", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── 认证 ─────────────────────────────────────────────────
def verify_token(authorization: str = Header("")):
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    if token != AGENT_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


# ── 工具 ─────────────────────────────────────────────────
async def run_cmd(cmd: str, timeout: int = 60) -> dict:
    """执行本地命令"""
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {
            "ok": proc.returncode == 0,
            "code": proc.returncode,
            "stdout": stdout.decode("utf-8", errors="replace").strip(),
            "stderr": stderr.decode("utf-8", errors="replace").strip(),
        }
    except asyncio.TimeoutError:
        return {"ok": False, "code": -1, "stdout": "", "stderr": "Command timed out"}
    except Exception as e:
        return {"ok": False, "code": -1, "stdout": "", "stderr": str(e)}


# ── 健康检查 ─────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.now().isoformat()}


# ── 配置文件管理 ─────────────────────────────────────────
@app.get("/config")
async def config_get(authorization: str = Header("")):
    verify_token(authorization)
    try:
        return json.loads(Path(CONFIG_PATH).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise HTTPException(404, "Config file not found")
    except json.JSONDecodeError as e:
        raise HTTPException(500, f"Invalid JSON: {e}")


class ConfigSaveReq(BaseModel):
    config: dict
    backup: bool = True


@app.post("/config")
async def config_save(req: ConfigSaveReq, authorization: str = Header("")):
    verify_token(authorization)
    path = Path(CONFIG_PATH)
    if req.backup and path.exists():
        bak = path.with_suffix(f".bak.{datetime.now().strftime('%Y%m%d%H%M%S')}")
        bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    path.write_text(json.dumps(req.config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"ok": True}


@app.post("/config/validate")
async def config_validate(authorization: str = Header("")):
    verify_token(authorization)
    return await run_cmd("openclaw config validate")


# ── 网关控制 ─────────────────────────────────────────────
@app.post("/gateway/restart")
async def gateway_restart(authorization: str = Header("")):
    verify_token(authorization)
    return await run_cmd("openclaw gateway restart", timeout=90)


# ── 命令执行 ─────────────────────────────────────────────
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
    command: str  # SAFE_COMMANDS key 或 "custom"
    custom_cmd: Optional[str] = None


@app.post("/run")
async def run_command(req: RunReq, authorization: str = Header("")):
    verify_token(authorization)
    if req.command == "custom":
        cmd = (req.custom_cmd or "").strip()
        if not cmd:
            raise HTTPException(400, "Empty command")
        if not cmd.startswith("openclaw "):
            raise HTTPException(403, "Only openclaw commands allowed")
    else:
        cmd = SAFE_COMMANDS.get(req.command)
        if not cmd:
            raise HTTPException(400, f"Unknown command: {req.command}")
    result = await run_cmd(cmd)
    result["command"] = cmd
    return result


# ── 日志 ─────────────────────────────────────────────────
@app.get("/logs")
async def get_logs(
    date: str = Query("", description="YYYY-MM-DD, empty=today"),
    lines: int = Query(200, ge=10, le=5000),
    authorization: str = Header(""),
):
    verify_token(authorization)
    log_date = date or datetime.now().strftime("%Y-%m-%d")
    log_path = os.path.join(LOG_DIR, f"openclaw-{log_date}.log")
    try:
        # 用 tail 避免读大文件
        result = await run_cmd(f"tail -n {lines} {log_path}")
        return {"date": log_date, "path": log_path, "content": result["stdout"]}
    except Exception as e:
        return {"date": log_date, "path": log_path, "content": f"[Error: {e}]"}


# ── 环境变量 (API Keys) ─────────────────────────────────
@app.get("/env-keys")
async def env_keys_get(authorization: str = Header("")):
    verify_token(authorization)
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
    keys: list  # [{"name": "KEY", "value": "val"}, ...]


@app.post("/env-keys")
async def env_keys_save(req: EnvKeysSaveReq, authorization: str = Header("")):
    verify_token(authorization)
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


# ── 工作区文件 ───────────────────────────────────────────
def _resolve_workspace(agent_id: str = "main") -> str:
    """从 config.json 解析 agent 的 workspace 路径"""
    default_ws = os.path.join(OPENCLAW_HOME, "workspace")
    try:
        cfg = json.loads(Path(CONFIG_PATH).read_text(encoding="utf-8"))
        for ag in cfg.get("agents", {}).get("list", []):
            if ag.get("id") == agent_id:
                return ag.get("workspace", default_ws)
    except Exception:
        pass
    return default_ws


@app.get("/workspace/files")
async def workspace_files(
    agent_id: str = Query("main"),
    authorization: str = Header(""),
):
    verify_token(authorization)
    ws = _resolve_workspace(agent_id)
    key_files = ["AGENTS.md", "SOUL.md", "USER.md", "IDENTITY.md", "MEMORY.md",
                 "TOOLS.md", "HEARTBEAT.md", "BOOTSTRAP.md"]
    result = []
    for f in key_files:
        p = os.path.join(ws, f)
        result.append({"name": f, "exists": os.path.isfile(p),
                        "size": os.path.getsize(p) if os.path.isfile(p) else 0})
    # memory 日志
    mem_dir = os.path.join(ws, "memory")
    mem_files = []
    if os.path.isdir(mem_dir):
        mem_files = sorted(
            [f for f in os.listdir(mem_dir) if f.endswith(".md")], reverse=True
        )[:20]
    return {"agent_id": agent_id, "workspace": ws, "files": result, "memory_files": mem_files}


@app.get("/workspace/file")
async def workspace_file_read(
    filename: str = Query(...),
    agent_id: str = Query("main"),
    authorization: str = Header(""),
):
    verify_token(authorization)
    if ".." in filename or filename.startswith("/"):
        raise HTTPException(403, "Invalid path")
    ws = _resolve_workspace(agent_id)
    path = os.path.join(ws, filename)
    try:
        return {"filename": filename, "content": Path(path).read_text(encoding="utf-8")}
    except FileNotFoundError:
        raise HTTPException(404, "File not found")


class FileSaveReq(BaseModel):
    filename: str
    content: str
    agent_id: str = "main"


@app.post("/workspace/file")
async def workspace_file_save(req: FileSaveReq, authorization: str = Header("")):
    verify_token(authorization)
    if ".." in req.filename or req.filename.startswith("/"):
        raise HTTPException(403, "Invalid path")
    ws = _resolve_workspace(req.agent_id)
    path = Path(os.path.join(ws, req.filename))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(req.content, encoding="utf-8")
    return {"ok": True}


# ── 启动 ─────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("OPENCLAW_AGENT_PORT", "9966"))
    uvicorn.run(app, host="0.0.0.0", port=port)
