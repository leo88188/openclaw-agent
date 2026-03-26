#!/bin/bash
set -e
cd "$(dirname "$0")"
mkdir -p logs

# 杀掉占用 9998 和 9999 端口的进程
for port in 9998 9999; do
    pids=$(lsof -ti :$port 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "Killing processes on port $port: $pids"
        echo "$pids" | xargs kill -9 2>/dev/null || true
        sleep 1
    fi
done

# 启动后端
nohup python -m uvicorn server.main:app --host 0.0.0.0 --port 9999 > logs/backend.log 2>&1 &
echo "Backend started (PID: $!)"

# 启动前端
nohup python -m http.server 9998 --directory static > logs/frontend.log 2>&1 &
echo "Frontend started (PID: $!)"

sleep 2
echo "Done. Backend: http://localhost:9999  Frontend: http://localhost:9998"
