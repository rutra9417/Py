#!/bin/bash
# start_all.sh — надежный автозапуск и мониторинг ботов

# --- venv ---
source ~/vip/venv/bin/activate

LOG_DIR=~/vip/logs
mkdir -p "$LOG_DIR"

# --- функция запуска с проверкой и автоперезапуском ---
run_bot() {
    local script=$1
    local logfile=$2

    while true
    do
        # проверка дубля
        if pgrep -f "$script" > /dev/null; then
            echo "[SKIP] $script уже запущен."
            sleep 10
            continue
        fi

        echo "[START] $script"
        # запускаем в фоне, nohup для логов
        nohup python3 ~/vip/$script > "$LOG_DIR/$logfile" 2>&1 &
        PID=$!
        echo "[PID $PID] $script запущен"

        # ждём завершения процесса, если упал — перезапуск
        wait $PID
        echo "[RESTART] $script упал или завершился. Перезапуск через 5s..."
        sleep 5
    done
}

# --- запуск всех ботов параллельно ---
run_bot "main.py" "exchange.log" &
run_bot "dash1.py" "dash1.log" &
run_bot "BtcKiosk.py" "btc.log" &
run_bot "swopex.py" "swopex.log" &

echo "✅ Все боты запущены с мониторингом на ошибки и автоперезапуском."