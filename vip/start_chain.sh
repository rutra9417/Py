#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$HOME/vip/vip"
VENV_ACT="$APP_DIR/venv/bin/activate"
LOG_DIR="$APP_DIR/logs"

mkdir -p "$LOG_DIR"
cd "$APP_DIR"

# активируем окружение
source "$VENV_ACT"

start_one () {
  local name="$1"
  local cmd="$2"
  local log="$LOG_DIR/${name}.log"

  # если уже запущено — не дублируем
  if pgrep -f "$cmd" >/dev/null 2>&1; then
    echo "[SKIP] $name already running"
    return 0
  fi

  echo "[START] $name"
  nohup bash -lc "cd '$APP_DIR' && source '$VENV_ACT' && $cmd" \
    >>"$log" 2>&1 &
  sleep 1
}

# Стартуем строго в нужном порядке
start_one "dash1"  "python dash1.py"
start_one "swopex" "python swopex.py"
start_one "main"   "python main.py"
start_one "new"    "python new.py"

echo "✅ Started chain. Logs: $LOG_DIR"
