@echo off
setlocal
cd /d "%USERPROFILE%\Documents\vip"
set SESSION_NAME=exchange_userbot
call .venv\Scripts\activate.bat >nul 2>&1
:loop
python -u main.py 1>> "logs\userbot.log" 2>&1
timeout /t 30 /nobreak >nul
goto loop
