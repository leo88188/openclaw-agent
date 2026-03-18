#!/bin/bash
# OpenClaw Agent macOS 安装脚本
# 用法: bash install-mac.sh [--port 9966]
#
# Token 自动生成，安装完成后显示
# 使用 launchd 管理服务（macOS 原生）

set -e

INSTALL_DIR="$HOME/.openclaw-agent"
REPO_URL="https://raw.githubusercontent.com/leo88188/openclaw-agent/main"
PORT="9966"
LABEL="com.openclaw.agent"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"

while [[ $# -gt 0 ]]; do
    case $1 in
        --port)  PORT="$2"; shift 2 ;;
        *) shift ;;
    esac
done

TOKEN=$(openssl rand -hex 32)

echo ""
echo "========== 安装 OpenClaw Agent (macOS) =========="
echo "  目录: $INSTALL_DIR"
echo "  端口: $PORT"
echo ""

# 1. 停止旧服务
launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true

# 2. 下载文件
mkdir -p "$INSTALL_DIR"
echo "📦 下载文件..."
curl -sSL "${REPO_URL}/openclaw_agent.py" -o "${INSTALL_DIR}/openclaw_agent.py"
curl -sSL "${REPO_URL}/requirements.txt" -o "${INSTALL_DIR}/requirements.txt"
echo "  ✅ 下载完成"

# 3. 创建 venv 并安装依赖
echo "🔧 安装 Python 依赖..."
python3 -m venv "${INSTALL_DIR}/venv"
"${INSTALL_DIR}/venv/bin/pip" install -q -r "${INSTALL_DIR}/requirements.txt"
echo "  ✅ 依赖安装完成"

# 4. 检测 OpenClaw HOME
OPENCLAW_HOME="$HOME/.openclaw"
[ -d "$HOME/.openclaw-dev" ] && [ ! -d "$OPENCLAW_HOME" ] && OPENCLAW_HOME="$HOME/.openclaw-dev"
echo "  OpenClaw HOME: $OPENCLAW_HOME"

# 5. 配置 launchd
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${INSTALL_DIR}/venv/bin/python3</string>
        <string>${INSTALL_DIR}/openclaw_agent.py</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>OPENCLAW_AGENT_TOKEN</key>
        <string>${TOKEN}</string>
        <key>OPENCLAW_AGENT_PORT</key>
        <string>${PORT}</string>
        <key>OPENCLAW_HOME</key>
        <string>${OPENCLAW_HOME}</string>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${INSTALL_DIR}/agent.log</string>
    <key>StandardErrorPath</key>
    <string>${INSTALL_DIR}/agent.log</string>
</dict>
</plist>
EOF

# 6. 启动
launchctl bootstrap "gui/$(id -u)" "$PLIST"
sleep 2

# 7. 验证
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "127.0.0.1")
if curl -sf -m 3 "http://127.0.0.1:${PORT}/health" > /dev/null 2>&1; then
    echo ""
    echo "========================================="
    echo "✅ 安装成功！"
    echo ""
    echo "🔑 Token: $TOKEN"
    echo ""
    echo "在管理平台「新增实例」中填写:"
    echo "  Agent URL:   http://${LOCAL_IP}:${PORT}"
    echo "  Agent Token: ${TOKEN}"
    echo ""
    echo "管理命令:"
    echo "  查看状态: launchctl print gui/$(id -u)/${LABEL}"
    echo "  停止服务: launchctl bootout gui/$(id -u)/${LABEL}"
    echo "  启动服务: launchctl bootstrap gui/$(id -u) ${PLIST}"
    echo "  查看日志: tail -f ${INSTALL_DIR}/agent.log"
    echo "  卸载:     launchctl bootout gui/$(id -u)/${LABEL} && rm -rf ${INSTALL_DIR} ${PLIST}"
    echo "========================================="
else
    echo "❌ 启动失败，查看日志:"
    tail -20 "${INSTALL_DIR}/agent.log" 2>/dev/null || echo "(无日志)"
    exit 1
fi
