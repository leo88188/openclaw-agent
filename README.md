# OpenClaw Agent

轻量远程管理服务，部署在每台 OpenClaw 实例上，供管理平台通过 HTTP API 调用，替代 SSH 方式。

## 为什么需要

管理平台需要远程管理 OpenClaw 实例（读写配置、执行命令、查看日志等）。SSH 方式存在以下问题：

- 需要管理 SSH 密钥分发
- 防火墙规则复杂
- 无法细粒度控制权限（SSH 拿到的是完整 shell）
- 不适合容器化部署

OpenClaw Agent 提供标准化 HTTP API，只暴露必要的管理接口，通过 Token 认证。

## 功能

| 接口 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/config` | GET | 读取 config.json |
| `/config` | POST | 保存 config.json（自动备份） |
| `/config/validate` | POST | 执行 `openclaw config validate` |
| `/gateway/restart` | POST | 执行 `openclaw gateway restart` |
| `/run` | POST | 执行预置或自定义 openclaw 命令 |
| `/logs` | GET | 读取运行日志 |
| `/env-keys` | GET | 读取模型供应商 API Key 环境变量 |
| `/env-keys` | POST | 保存 API Key 环境变量 + daemon-reload |
| `/workspace/files` | GET | 列出工作区关键文件 |
| `/workspace/file` | GET | 读取工作区文件 |
| `/workspace/file` | POST | 保存工作区文件 |

## 安装

### 方式一：一键远程安装（推荐）

在目标 Linux 服务器上执行一条命令即可完成安装，Token 自动生成：

```bash
# 需要 root 权限（Linux 服务器）
curl -sSL https://raw.githubusercontent.com/leo88188/openclaw-agent/main/install-remote.sh | sudo bash
```

指定端口：

```bash
curl -sSL https://raw.githubusercontent.com/leo88188/openclaw-agent/main/install-remote.sh | sudo bash -s -- --port 9966
```

> ⚠️ 此脚本仅支持 Linux（使用 systemd 管理服务），不支持 macOS。macOS 请使用方式三手动安装。

安装完成后会显示 Agent URL 和 Token，直接复制到管理平台「新增实例」中即可。

自动完成的操作：
- 下载 Agent 到 `/opt/openclaw-agent/`
- 创建 Python venv 并安装依赖
- 自动检测 OpenClaw 运行用户和 HOME 目录
- 配置 systemd 服务并启动
- 生成随机 Token（openssl rand -hex 32）

### 方式二：克隆仓库安装

```bash
# 在 OpenClaw 实例上执行
git clone https://github.com/leo88188/openclaw-agent.git
cd openclaw-agent
bash install.sh --token YOUR_SECRET_TOKEN --port 9966
```

### 方式二：克隆仓库安装

```bash
# 在 OpenClaw 实例上执行
git clone https://github.com/leo88188/openclaw-agent.git
cd openclaw-agent
bash install.sh --token YOUR_SECRET_TOKEN --port 9966
```

### 方式三：手动安装

```bash
pip install fastapi uvicorn
export OPENCLAW_AGENT_TOKEN="your-secret-token"
python openclaw_agent.py
```

### 方式四：Docker

```bash
docker build -t openclaw-agent .
docker run -d \
  --name openclaw-agent \
  -p 9966:9966 \
  -e OPENCLAW_AGENT_TOKEN=your-secret-token \
  -v /root/.openclaw:/root/.openclaw \
  -v /tmp/openclaw:/tmp/openclaw \
  -v /root/.config/systemd/user:/root/.config/systemd/user \
  openclaw-agent
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPENCLAW_AGENT_TOKEN` | `changeme` | 认证 Token（必须修改） |
| `OPENCLAW_AGENT_PORT` | `9966` | 监听端口 |
| `OPENCLAW_HOME` | `~/.openclaw` | OpenClaw 主目录 |
| `OPENCLAW_CONFIG` | `~/.openclaw/config.json` | 配置文件路径 |
| `OPENCLAW_ENV_CONF` | `~/.config/systemd/user/openclaw-gateway.service.d/provider-models.conf` | 环境变量配置路径 |
| `OPENCLAW_LOG_DIR` | `/tmp/openclaw` | 日志目录 |

## API 使用示例

```bash
TOKEN="your-secret-token"
URL="http://10.0.0.1:9966"

# 健康检查
curl $URL/health

# 读取配置
curl -H "Authorization: Bearer $TOKEN" $URL/config

# 保存配置
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"config": {...}, "backup": true}' \
  $URL/config

# 执行命令
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command": "status"}' \
  $URL/run

# 自定义命令
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command": "custom", "custom_cmd": "openclaw models list --all"}' \
  $URL/run

# 查看日志
curl -H "Authorization: Bearer $TOKEN" "$URL/logs?date=2026-03-16&lines=100"

# 读取工作区文件
curl -H "Authorization: Bearer $TOKEN" "$URL/workspace/file?filename=SOUL.md&agent_id=main"
```

## 在管理平台中使用

在管理平台的 OpenClaw 实例管理中，填写：

- **Agent URL**: `http://<实例IP>:9966`
- **Agent Token**: 安装时设置的 Token

管理平台会通过 HTTP API 替代 SSH 来管理实例。

## 安全建议

- 务必修改默认 Token
- 建议通过内网访问，不暴露到公网
- 如需公网访问，建议配合 Nginx + HTTPS
- Agent 仅允许执行 `openclaw` 开头的命令

## License

MIT
