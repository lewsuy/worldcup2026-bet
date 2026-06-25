#!/bin/bash
# 启动 2026 世界杯模拟盘服务
# 用法: ./run.sh [PORT]    默认 2026（年份）
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${1:-${PORT:-2026}}"
PID_FILE="$DIR/.wc-bet.pid"
LOG_FILE="$DIR/wc-bet.log"

cd "$DIR"

# 1) 优先通过 PID 文件杀掉旧实例
if [ -f "$PID_FILE" ]; then
  OLD_PID=$(cat "$PID_FILE" 2>/dev/null || echo "")
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "[run] stopping old instance (PID $OLD_PID)..."
    kill "$OLD_PID" 2>/dev/null || true
    sleep 1
  fi
  rm -f "$PID_FILE"
fi

# 2) 兜底：杀掉占端口的孤儿进程（pitfall #126 防范）
if command -v ss >/dev/null 2>&1; then
  PORT_PID=$(ss -tlnp 2>/dev/null | grep ":$PORT " | grep -oP 'pid=\K[0-9]+' | head -1 || true)
  if [ -n "$PORT_PID" ]; then
    echo "[run] killing port-conflicting process (PID $PORT_PID)..."
    kill "$PORT_PID" 2>/dev/null || true
    sleep 1
  fi
fi

# 3) 兜底：停掉 systemd transient 单元（如果存在）
if command -v systemctl >/dev/null 2>&1; then
  if systemctl is-active --quiet wc-bet-server.service 2>/dev/null; then
    echo "[run] stopping systemd unit wc-bet-server.service..."
    systemctl stop wc-bet-server.service 2>/dev/null || true
    sleep 1
  fi
fi

# 4) 启动新实例（nohup + disown，确保不因 shell 退出而终止）
echo "[run] starting 2026 世界杯模拟盘 on port $PORT..."
nohup python3 -m http.server "$PORT" --bind 0.0.0.0 > "$LOG_FILE" 2>&1 &
NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"
disown "$NEW_PID" 2>/dev/null || true

# 5) 验证（pitfall #125: bind 有 ~1s 延迟）
sleep 2
if curl -sI "http://127.0.0.1:$PORT/" -o /dev/null -w "%{http_code}" 2>/dev/null | grep -q 200; then
  IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")
  echo "[run] ✓ started successfully"
  echo "[run]   PID:  $NEW_PID"
  echo "[run]   log:  $LOG_FILE"
  echo "[run]   URL:  http://$IP:$PORT/"
else
  echo "[run] ✗ failed to start. Check log:"
  tail -20 "$LOG_FILE" || true
  exit 1
fi
