import os
import hashlib
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from telegram import Bot  # PTB v20+

import requests
import time
import threading

# --- heartbeat ---
HB_PATH = Path.home() / "vip" / "hb_forwarder.txt"
HB_PATH.parent.mkdir(exist_ok=True)
def _hb():
    while True:
        try:
            HB_PATH.write_text(str(time.time()), encoding="utf-8")
        except Exception:
            pass
        time.sleep(15)
threading.Thread(target=_hb, daemon=True).start()
# --- /heartbeat ---

# Пути
base_dir = Path.home() / "vip"
image_path = base_dir / "main_white.png"
font_path = base_dir / "arial.ttf"
transaction_file_path = base_dir / "transaction_values.txt"
output_image_path = base_dir / "outputScreenshot_20230909_0243320.png"
chat_ids_file = base_dir / "chat_ids.txt"

# Боты
bot_token_1 = "6143029111:AAE8_wMyTj7ZvIMWNr1TSQeEbCg2tpLiNDU"
bot_token_2 = "7524105753:AAFxqCrelnf4C0g2I2ig_RfmyPobng5idMA"

bot1 = Bot(token=bot_token_1)
bot2 = Bot(token=bot_token_2)

# --- Хеш-функция файла ---
def file_hash(filepath):
    if not filepath.exists():
        return None
    with open(filepath, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

# --- Получение курса DASH к USD ---
def get_usd_amount_online(dash_amount):
    try:
        resp = requests.get(
            'https://api.coingecko.com/api/v3/simple/price?ids=dash&vs_currencies=usd',
            timeout=8
        )
        resp.raise_for_status()
        price = resp.json().get('dash', {}).get('usd')
        if price:
            return dash_amount * price
    except Exception as e:
        print("Ошибка получения курса:", e)
    return None

# --- Добавление текста ---
def add_text_to_image(image, text, coordinates, font_size, font_color):
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(font_path), font_size)
    draw.text(coordinates, text, font=font, fill=font_color)

# --- Чтение chat_id ---
def read_chat_ids_from_file(filename):
    if not filename.exists():
        print(f"[BtcKiosk] chat_ids file not found: {filename}")
        return []
    with open(filename, "r", encoding="utf-8") as file:
        return [line.strip() for line in file if line.strip()]

# --- Генерация и отправка изображения ---
async def generate_and_send_image():
    try:
        if not transaction_file_path.exists():
            print("[BtcKiosk] transaction_values.txt not found")
            return

        with open(transaction_file_path, "r", encoding="utf-8") as file:
            lines = file.read().splitlines()

        if len(lines) < 6:
            print("[BtcKiosk] transaction_values.txt malformed (need >=6 lines)")
            return

        date_time_str = lines[2]
        formatted_datetime = datetime.strptime(date_time_str, "%d.%m.%Y %H:%M")
        adjusted_end_time = formatted_datetime - timedelta(minutes=2)
        month_names = ["января", "февраля", "марта", "апреля", "мая", "июня",
                       "июля", "августа", "сентября", "октября", "ноября", "декабря"]
        formatted_adjusted = f"{adjusted_end_time.day} {month_names[adjusted_end_time.month - 1]} {adjusted_end_time.strftime('%H:%M')}"

        if not image_path.exists():
            print(f"[BtcKiosk] base image not found: {image_path}")
            return
        if not font_path.exists():
            print(f"[BtcKiosk] font not found: {font_path}")
            return

        img = Image.open(image_path)

        dash = float(lines[3])
        s = f"{dash:.7f}"
        add_text_to_image(img, s[:-5], (80, 60), 75, (19, 18, 23))
        add_text_to_image(img, s[-5:], (230, 70), 62, (19, 18, 23))

        recipient = lines[0]
        sender = lines[4]
        def short(a): return a if len(a) <= 21 else (a[:9] + "..." + a[-9:])
        add_text_to_image(img, short(recipient), (385, 340), 30, (19, 18, 23))
        add_text_to_image(img, short(sender), (385, 250), 30, (19, 18, 23))

        fee = float(lines[5])
        add_text_to_image(img, f"{fee:.7f}"[:-5], (555, 431), 29, (19, 18, 23))
        add_text_to_image(img, f"{fee:.8f}"[-6:], (613, 435), 25, (19, 18, 23))

        add_text_to_image(img, formatted_adjusted, (500, 520), 28, (19, 18, 23))

        usd = get_usd_amount_online(dash)
        if usd is not None:
            add_text_to_image(img, f"{usd:.2f}", (75, 140), 30, (131, 142, 138))

        img.save(output_image_path)

        chat_ids = read_chat_ids_from_file(chat_ids_file)
        if not chat_ids:
            print("[BtcKiosk] no chat_ids")
            return

        with open(output_image_path, "rb") as image_file:
            image_bytes = image_file.read()

        for chat_id in chat_ids:
            try:
                await bot1.send_photo(chat_id=chat_id, photo=image_bytes)
                await bot2.send_photo(chat_id=chat_id, photo=image_bytes)
                print(f"✅ Отправлено обоими ботами: {chat_id}")
                await asyncio.sleep(1.0)
            except Exception as e:
                print(f"❌ Ошибка для {chat_id}: {e}")

    except Exception as e:
        print(f"Ошибка генерации или отправки: {e}")

# --- Основной мониторинг ---
async def monitor_file():
    print("👁‍🗨 Ожидание изменений transaction_values.txt...")
    last_hash = file_hash(transaction_file_path)

    while True:
        await asyncio.sleep(2)
        current_hash = file_hash(transaction_file_path)
        if current_hash != last_hash:
            print("🆕 Обнаружено изменение файла. Генерация изображения...")
            await generate_and_send_image()
            last_hash = current_hash

# --- Запуск ---
if __name__ == "__main__":
    try:
        asyncio.run(monitor_file())
    except KeyboardInterrupt:
        print("⛔ Завершено пользователем.")
