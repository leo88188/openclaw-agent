#!/bin/bash
# 远程部署 openclaw-agent 到目标服务器
# 用法: ./deploy.sh <IP> [--token TOKEN] [--port PORT] [--user USER]
#
# 示例:
#   ./deploy.sh 43.160.227.148
#   ./deploy.sh 43.160.227.148 --token mytoken123 --port 9966 --user root

set -e

IP="$1"; shift || { echo "用法: $0 <IP> [--token TOKEN] [--port PORT] [--user USER]"; exit 1; }
TOKEN=""
PORT="9966"
USER="root"

while [[ $# -gt 0 ]]; do
    case $1 in
        --token) TOKEN="$2"; shift 2 ;;
        --port)  PORT="$2"; shift 2 ;;
        --user)  USER="$2"; shift 2 ;;
        *) shift ;;
    esac
done

[ -z "$TOKEN" ] && TOKEN=$(openssl rand -hex 16) && echo "🔑 自动生成 Token: $TOKEN"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REMOTE_DIR="/opt/openclaw-agent"

echo ""
echo "========== 部署 openclaw-agent =========="
echo "  目标: ${USER}@${IP}"
echo "  端口: ${PORT}"
echo "  Token: ${TOKEN}"
echo ""

# 1. 传文件
echo "📦 上传文件..."
ssh ${USER}@${IP} "mkdir -p ${REMOTE_DIR}"
scp -q "${SCRIPT_DIR}/openclaw_agent.py" "${SCRIPT_DIR}/requirements.txt" ${USER}@${IP}:${REMOTE_DIR}/

# 2. 远程安装
echo "🔧 安装依赖并配置服务..."
ssh ${USER}@${IP} bash -s <<REMOTE
set -e
cd ${REMOTE_DIR}
pip3 install -q -r requirements.txt 2>/dev/null || pip install -q -r requirements.txt

# 检测 openclaw 用户的 home 目录
OPENCLAW_USER=\$(ps -eo user,comm 2>/dev/null | grep -m1 openclaw | awk '{print \$1}' || echo "root")
OPENCLAW_HOME=\$(eval echo ~\${OPENCLAW_USER})
echo "  OpenClaw 用户: \${OPENCLAW_USER}, HOME: \${OPENCLAW_HOME}"

# systemd 服务
cat > /etc/systemd/system/openclaw-agent.service <<EOF
[Unit]
Description=OpenClaw Agent
After=network.target

[Service]
Type=simple
User=\${OPENCLAW_USER}
Environment=OPENCLAW_AGENT_TOKEN=${TOKEN}
Environment=OPENCLAW_AGENT_PORT=${PORT}
Environment=OPENCLAW_HOME=\${OPENCLAW_HOME}
ExecStart=/usr/bin/python3 ${REMOTE_DIR}/openclaw_agent.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable openclaw-agent
systemctl restart openclaw-agent
sleep 2
systemctl is-active --quiet openclaw-agent && echo "✅ 服务启动成功" || echo "❌ 启动失败"
REMOTE

# 3. 验证
echo ""
echo "🔍 验证连接..."
sleep 1
HEALTH=$(curl -sf -m 5 -H "Authorization: Bearer ${TOKEN}" "http://${IP}:${PORT}/health" 2>/dev/null || echo "FAIL")

if echo "$HEALTH" | grep -q '"ok"'; then
    echo "✅ 部署成功！"
else
    echo "⚠️  远程健康检查失败（可能需要开放端口 ${PORT}）"
    echo "   请在云服务器安全组/防火墙放行 TCP ${PORT}"
fi

echo ""
echo "========================================="
echo "在管理平台「新增实例」中填写:"
echo "  Agent URL:   http://${IP}:${PORT}"
echo "  Agent Token: ${TOKEN}"
echo "========================================="
