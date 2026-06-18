#!/usr/bin/env bash
# scripts/start_all.sh — Start all ai powered voice based 24.7 booking system services
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

[ -f .env ] && source .env || { echo "❌ .env not found. Run: ./scripts/generate_keys.sh"; exit 1; }

PID_DIR="$ROOT/pids"
LOG_DIR="$ROOT/logs"
mkdir -p "$PID_DIR" "$LOG_DIR" database

echo "=============================="
echo " ai powered voice based 24.7 booking system — Starting"
echo "=============================="

stop_service() {
  local name=$1 pidfile="$PID_DIR/$1.pid"
  if [ -f "$pidfile" ]; then
    local pid; pid=$(cat "$pidfile")
    kill "$pid" 2>/dev/null && echo "  Stopped $name (pid $pid)" || true
    rm -f "$pidfile"
  fi
}

# ── Stop existing ──────────────────────────────────────────────────────────
echo "Stopping existing services..."
stop_service "python_api"
stop_service "node_server"
stop_service "react_dev"
sleep 1

# ── Redis ─────────────────────────────────────────────────────────────────
if ! pgrep redis-server &>/dev/null; then
  echo "Starting Redis..."
  redis-server --daemonize yes \
    --requirepass "${REDIS_PASSWORD}" \
    --bind 127.0.0.1 \
    --rename-command FLUSHALL "" \
    --rename-command FLUSHDB  "" \
    --rename-command DEBUG    "" \
    --logfile "$LOG_DIR/redis.log"
  sleep 1
  echo "✅ Redis started"
else
  echo "✅ Redis already running"
fi

# ── Python AI Service ─────────────────────────────────────────────────────
echo "Starting Python AI service (port ${PYTHON_API_PORT:-8001})..."
cd "$ROOT"
nohup python3 -m uvicorn backend.python.main:app \
  --host 0.0.0.0 \
  --port "${PYTHON_API_PORT:-8001}" \
  --workers 1 \
  --log-level "${LOG_LEVEL:-info}" \
  > "$LOG_DIR/python_api.log" 2>&1 &
echo $! > "$PID_DIR/python_api.pid"
sleep 2

# Health check Python
if curl -sf "http://127.0.0.1:${PYTHON_API_PORT:-8001}/health" &>/dev/null; then
  echo "✅ Python AI service running"
else
  echo "⚠️  Python service may still be loading models (check logs/python_api.log)"
fi

# ── Node.js Server ────────────────────────────────────────────────────────
echo "Starting Node.js server (port ${NODE_SERVER_PORT:-8000})..."
cd "$ROOT/backend/node"
nohup node server.js \
  > "$ROOT/logs/node_server.log" 2>&1 &
echo $! > "$PID_DIR/node_server.pid"
cd "$ROOT"
sleep 2

if curl -sf "http://127.0.0.1:${NODE_SERVER_PORT:-8000}/health" &>/dev/null; then
  echo "✅ Node.js server running"
else
  echo "⚠️  Node.js server starting... (check logs/node_server.log)"
fi

# ── React Dashboard ───────────────────────────────────────────────────────
echo "Starting React dashboard (port ${REACT_PORT:-3000})..."
cd "$ROOT/frontend"
nohup npm run dev -- --port "${REACT_PORT:-3000}" \
  > "$ROOT/logs/react.log" 2>&1 &
echo $! > "$PID_DIR/react_dev.pid"
cd "$ROOT"
sleep 3

echo ""
echo "=============================="
echo " ✅ ai powered voice based 24.7 booking system Running"
echo "=============================="
echo "  Dashboard : http://localhost:${REACT_PORT:-3000}"
echo "  Node API  : http://localhost:${NODE_SERVER_PORT:-8000}"
echo "  Python AI : http://localhost:${PYTHON_API_PORT:-8001}"
echo "  WebSocket : ws://localhost:${WEBSOCKET_PORT:-8080}"
echo ""
echo "  Logs: ls logs/"
echo "  Stop: ./scripts/stop_all.sh"
echo ""
echo "Quick test (paste in dashboard input):"
echo "  I want 2 kg rice and 1 liter milk, my number is 9876543210"
