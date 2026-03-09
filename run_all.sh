#!/bin/bash

cd "$HOME/vip" || exit 1
source "$HOME/vip/venv/bin/activate"

echo "Starting bots..."

SESSION_NAME=main_userbot python main.py &
SESSION_NAME=forwarder_userbot python forwarder.py &
SESSION_NAME=dash1_userbot python dash1.py &
python swopex.py &
python BtcKiosk.py &
python new.py &

echo "All bots started."
