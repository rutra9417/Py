cd /d %USERPROFILE%\Documents\vip

rem === start_forwarder.bat ===
>start_forwarder.bat echo @echo off
>>start_forwarder.bat echo setlocal
>>start_forwarder.bat echo cd /d "%%USERPROFILE%%\Documents\vip"
>>start_forwarder.bat echo set SESSION_NAME=exchange_forwarder
>>start_forwarder.bat echo call .venv\Scripts\activate.bat ^>nul 2^>^&1
>>start_forwarder.bat echo :loop
>>start_forwarder.bat echo echo [%%date%% %%time%%] start forwarder>>"logs\forwarder.log"
>>start_forwarder.bat echo python -u forwarder.py 1^>^> "logs\forwarder.log" 2^>^&1
>>start_forwarder.bat echo echo [%%date%% %%time%%] stopped, restart in 30s>>"logs\forwarder.log"
>>start_forwarder.bat echo timeout /t 30 /nobreak ^>nul
>>start_forwarder.bat echo goto loop

rem === start_userbot.bat ===
>start_userbot.bat echo @echo off
>>start_userbot.bat echo setlocal
>>start_userbot.bat echo cd /d "%%USERPROFILE%%\Documents\vip"
>>start_userbot.bat echo set SESSION_NAME=exchange_userbot
>>start_userbot.bat echo call .venv\Scripts\activate.bat ^>nul 2^>^&1
>>start_userbot.bat echo :loop
>>start_userbot.bat echo echo [%%date%% %%time%%] start userbot>>"logs\userbot.log"
>>start_userbot.bat echo python -u main.py 1^>^> "logs\userbot.log" 2^>^&1
>>start_userbot.bat echo echo [%%date%% %%time%%] stopped, restart in 30s>>"logs\userbot.log"
>>start_userbot.bat echo timeout /t 30 /nobreak ^>nul
>>start_userbot.bat echo goto loop
