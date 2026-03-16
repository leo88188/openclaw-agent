#!/bin/bash
# OpenClaw Agent 一键远程安装
# 用法: curl -sSL https://raw.githubusercontent.com/leo88188/openclaw-agent/main/install-remote.sh | bash
#
# 参数:
#   --port  PORT    监听端口（默认 9966）
#
# Token 自动生成（openssl rand -hex 32），安装完成后显示

set -e

INSTALL_DIR="/opt/openclaw-agent"
REPO_URL="https://raw.githubusercontent.com/leo88188/openclaw-agent/main"
PORT="9966"

while [[ $# -gt 0 ]]; do
    case $1 in
        --port)  PORT="$2"; shift 2 ;;
        *) shift ;;
    esac
done

TOKEN=$(openssl rand -hex 32)
echo "🔑 Token: $TOKEN"

echo ""
echo "========== 安装 OpenClaw Agent =========="
echo "  目录: $INSTALL_DIR"
echo "  端口: $PORT"
echo ""

# 1. 下载文件
mkdir -p "$INSTALL_DIR"
echo "📦 下载文件..."
curl -sSL "${REPO_URL}/openclaw_agent.py" -o "${INSTALL_DIR}/openclaw_agent.py"
curl -sSL "${REPO_URL}/requirements.txt" -o "${INSTALL_DIR}/requirements.txt"
echo "  ✅ 下载完成"

# 2. 创建 venv 并安装依赖
echo "🔧 安装 Python 依赖..."
apt-get install -y -qq python3-venv > /dev/null 2>&1 || true
python3 -m venv "${INSTALL_DIR}/venv"
"${INSTALL_DIR}/venv/bin/pip" install -q -r "${INSTALL_DIR}/requirements.txt"
echo "  ✅ 依赖安装完成"

# 3. 检测 OpenClaw 运行用户
OPENCLAW_USER=$(ps -eo user,comm 2>/dev/null | grep -m1 openclaw | awk '{print $1}' || echo "")
[ -z "$OPENCLAW_USER" ] && OPENCLAW_USER=$(whoami)
OPENCLAW_HOME=$(eval echo ~${OPENCLAW_USER})
echo "  OpenClaw 用户: ${OPENCLAW_USER}, HOME: ${OPENCLAW_HOME}"

# 4. 配置 systemd
cat > /etc/systemd/system/openclaw-agent.service <<EOF
[Unit]
Description=OpenClaw Agent - Remote Management Service
After=network.target

[Service]
Type=simple
User=${OPENCLAW_USER}
Environment=OPENCLAW_AGENT_TOKEN=${TOKEN}
Environment=OPENCLAW_AGENT_PORT=${PORT}
Environment=OPENCLAW_HOME=${OPENCLAW_HOME}
ExecStart=${INSTALL_DIR}/venv/bin/python3 ${INSTALL_DIR}/openclaw_agent.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 5. 启动
systemctl daemon-reload
systemctl enable openclaw-agent
systemctl restart openclaw-agent
sleep 2

# 6. 验证
IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")
if systemctl is-active --quiet openclaw-agent; then
    echo ""
    echo "========================================="
    echo "✅ 安装成功！"
    echo ""
    echo "在管理平台「新增实例」中填写:"
    echo "  Agent URL:   http://${IP}:${PORT}"
    echo "  Agent Token: ${TOKEN}"
    echo ""
    echo "⚠️  请确保安全组/防火墙已放行 TCP ${PORT}"
    echo "========================================="
else
    echo "❌ 启动失败"
    journalctl -u openclaw-agent -n 10 --no-pager
    exit 1
fi
