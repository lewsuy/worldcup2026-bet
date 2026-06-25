#!/bin/bash
# 停止 2026 世界杯模拟盘服务
# 用法: ./stop.sh [PORT]   默认 2026
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${1:-${PORT:-2026}}"
PID_FILE="$DIR/.wc-bet.pid"
STOPPED=0

# 1) 优先通过 PID 文件
if [ -f "$PID_FILE" ]; then
  PID=$(cat "$PID_FILE" 2>/dev/null || echo "")
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    sleep 1
    if kill -0 "$PID" 2>/dev/null; then
      kill -9 "$PID" 2>/dev/null || true
    fi
    echo "[stop] killed process (PID $PID)"
    STOPPED=1
  else
    echo "[stop] PID file exists but process $PID not running"
  fi
  rm -f "$PID_FILE"
fi

# 2) 兜底：停 systemd transient 单元
if command -v systemctl >/dev/null 2>&1; then
  if systemctl is-active --quiet wc-bet-server.service 2>/dev/null; then
    systemctl stop wc-bet-server.service
    echo "[stop] stopped systemd unit wc-bet-server.service"
    STOPPED=1
  fi
fi

# 3) 兜底：杀掉占端口的进程
if command -v ss >/dev/null 2>&1; then
  PORT_PID=$(ss -tlnp 2>/dev/null | grep ":$PORT " | grep -oP 'pid=\K[0-9]+' | head -1 || true)
  if [ -n "$PORT_PID" ]; then
    if kill "$PORT_PID" 2>/dev/null; then
      echo "[stop] killed port-conflicting process (PID $PORT_PID)"
      STOPPED=1
    fi
  fi
fi

# 4) 兜底：pkill by name（用 [h] 转义避免 pkill 命令自身命令行匹配自杀）
if pkill -f "[h]ttp.server $PORT" 2>/dev/null; then
  echo "[stop] killed via pkill"
  STOPPED=1
fi

if [ "$STOPPED" -eq 0 ]; then
  echo "[stop] no running instance found on port $PORT"
fi
