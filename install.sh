#!/bin/bash
# OpenClaw Agent 一键安装脚本
# 用法: curl -sSL <url>/install.sh | bash -s -- --token YOUR_TOKEN

set -e

INSTALL_DIR="/opt/openclaw-agent"
PORT="${OPENCLAW_AGENT_PORT:-9966}"
TOKEN=""

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --token) TOKEN="$2"; shift 2 ;;
        --port)  PORT="$2"; shift 2 ;;
        *) shift ;;
    esac
done

if [ -z "$TOKEN" ]; then
    TOKEN=$(openssl rand -hex 24)
    echo "⚠️  未指定 token，已自动生成: $TOKEN"
fi

echo "========== 安装 OpenClaw Agent =========="
echo "安装目录: $INSTALL_DIR"
echo "端口: $PORT"

# 创建目录
mkdir -p "$INSTALL_DIR"

# 复制文件（如果是从仓库目录运行）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/openclaw_agent.py" ]; then
    cp "$SCRIPT_DIR/openclaw_agent.py" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"
fi

# 安装依赖
echo "安装 Python 依赖..."
pip3 install -q -r "$INSTALL_DIR/requirements.txt"

# 配置 systemd
cat > /etc/systemd/system/openclaw-agent.service << EOF
[Unit]
Description=OpenClaw Agent - Remote Management Service
After=network.target

[Service]
Type=simple
User=root
Environment=OPENCLAW_AGENT_TOKEN=$TOKEN
Environment=OPENCLAW_AGENT_PORT=$PORT
ExecStart=/usr/bin/python3 $INSTALL_DIR/openclaw_agent.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 启动
systemctl daemon-reload
systemctl enable openclaw-agent
systemctl restart openclaw-agent

sleep 2

# 验证
if systemctl is-active --quiet openclaw-agent; then
    echo ""
    echo "========== 安装完成 =========="
    echo "✅ 服务已启动"
    echo "   地址: http://$(hostname -I | awk '{print $1}'):$PORT"
    echo "   Token: $TOKEN"
    echo ""
    echo "在管理平台中填写:"
    echo "   Agent URL:   http://<IP>:$PORT"
    echo "   Agent Token: $TOKEN"
    echo ""
    echo "测试: curl -H 'Authorization: Bearer $TOKEN' http://127.0.0.1:$PORT/health"
else
    echo "❌ 启动失败，请检查: journalctl -u openclaw-agent -n 20"
    exit 1
fi
