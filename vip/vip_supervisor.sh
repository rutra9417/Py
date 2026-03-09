#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$HOME/vip/vip"
VENV_ACT="$APP_DIR/venv/bin/activate"
LOG_DIR="$APP_DIR/logs"
RUN_DIR="$APP_DIR/run"

mkdir -p "$LOG_DIR" "$RUN_DIR"
cd "$APP_DIR"
source "$VENV_ACT"

start_proc() {
  local name="$1"
  local cmd="$2"
  local pidfile="$RUN_DIR/${name}.pid"
  local logfile="$LOG_DIR/${name}.log"

  # если pidfile есть и процесс жив — ничего не делаем
  if [[ -f "$pidfile" ]]; then
    local pid
    pid="$(cat "$pidfile" || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      return 0
    fi
  fi

  echo "[$(date '+%F %T')] START $name" >> "$logfile"
  nohup bash -lc "cd '$APP_DIR' && source '$VENV_ACT' && exec $cmd" >>"$logfile" 2>&1 &
  echo $! > "$pidfile"
  sleep 1
}

stop_all() {
  for f in "$RUN_DIR"/*.pid; do
    [[ -e "$f" ]] || continue
    pid="$(cat "$f" || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
    rm -f "$f"
  done
}

trap stop_all SIGINT SIGTERM

# бесконечный мониторинг
while true; do
  start_proc "dash1"  "python dash1.py"
  start_proc "swopex" "python swopex.py"
  start_proc "main"   "python main.py"
  start_proc "new"    "python new.py"
  sleep 5
done
