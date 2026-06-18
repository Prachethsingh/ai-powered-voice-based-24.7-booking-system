#!/usr/bin/env bash
# scripts/stop_all.sh — Stop all ai powered voice based 24.7 booking system services
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PID_DIR="$ROOT/pids"

echo "Stopping ai powered voice based 24.7 booking system services..."

for service in python_api node_server react_dev; do
  pidfile="$PID_DIR/$service.pid"
  if [ -f "$pidfile" ]; then
    pid=$(cat "$pidfile")
    if kill "$pid" 2>/dev/null; then
      echo "  ✅ Stopped $service (pid $pid)"
    fi
    rm -f "$pidfile"
  fi
done

echo "Done."
