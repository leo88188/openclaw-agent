#!/bin/bash
# restart-dashboard.sh - 重启 Pipeline Dashboard 服务
# 兼容 macOS 和 Linux

PORT=${1:-9988}
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
SERVER="$HOME/.kiro/hooks/pipeline-server.py"

# 停止旧进程
lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
sleep 1

# 启动
nohup python3 "$SERVER" "$PROJECT_ROOT" "$PORT" > /dev/null 2>&1 &
echo "✅ Dashboard 已启动: http://localhost:$PORT (PID: $!)"
