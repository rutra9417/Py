#!/bin/bash
cd "$HOME/vip"

source venv/bin/activate

python new.py &
python BtcKiosk.py &

SESSION_NAME=main_userbot python main.py &
SESSION_NAME=forwarder_userbot python forwarder.py &
SESSION_NAME=dash1_userbot python dash1.py &

python swopex.py &
