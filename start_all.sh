#!/bin/bash

BASE_DIR="/home/rutra/vip"
VENV_PY="$BASE_DIR/venv/bin/python"
LOG_DIR="$BASE_DIR/logs"

mkdir -p "$LOG_DIR"
cd "$BASE_DIR" || exit 1

echo "Stopping old processes..."

pkill -f "main.py"
pkill -f "forwarder.py"
pkill -f "dash1.py"
pkill -f "swopex.py"
pkill -f "BtcKiosk.py"
pkill -f "new.py"

sleep 3

echo "Checking that old processes are gone..."
ps aux | egrep "main.py|forwarder.py|dash1.py|swopex.py|BtcKiosk.py|new.py" | grep -v egrep

echo "Starting bots from: $BASE_DIR"
echo "Using Python: $VENV_PY"

nohup "$VENV_PY" -u main.py > "$LOG_DIR/main.log" 2>&1 &
sleep 1

nohup "$VENV_PY" -u forwarder.py > "$LOG_DIR/forwarder.log" 2>&1 &
sleep 1

nohup "$VENV_PY" -u dash1.py > "$LOG_DIR/dash1.log" 2>&1 &
sleep 1

nohup "$VENV_PY" -u swopex.py > "$LOG_DIR/swopex.log" 2>&1 &
sleep 1

nohup "$VENV_PY" -u BtcKiosk.py > "$LOG_DIR/BtcKiosk.log" 2>&1 &
sleep 1

nohup "$VENV_PY" -u new.py > "$LOG_DIR/new.log" 2>&1 &

sleep 3

echo "Started processes:"
ps aux | egrep "main.py|forwarder.py|dash1.py|swopex.py|BtcKiosk.py|new.py" | grep -v egrep
echo
echo "Logs folder: $LOG_DIR"
