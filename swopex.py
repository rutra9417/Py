# -*- coding: utf-8 -*-
"""
swopex.py — генерация чёрного чека + рассылка от имени пользователя на Linux
"""
import os
import asyncio
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import requests
import threading
import time

from telethon import TelegramClient, utils
from telethon.errors import RPCError

# ---------- Paths ----------
BASE_DIR = Path.home() / "vip"
BASE_DIR.mkdir(exist_ok=True)
image_path = BASE_DIR / "main_black.png"
font_path = BASE_DIR / "arial.ttf"
transaction_file_path = BASE_DIR / "transaction_values.txt"
output_image_path = BASE_DIR / "outputScreenshot.png"
chat_ids_file = BASE_DIR / "chat_ids.txt"

# ---------- Heartbeat ----------
HB_PATH = BASE_DIR / "hb_forwarder.txt"
def _hb():
    while True:
        try:
            HB_PATH.write_text(str(time.time()), encoding="utf-8")
        except:
            pass
        time.sleep(15)
threading.Thread(target=_hb, daemon=True).start()

# ---------- Telethon ----------
API_ID = 36812196
API_HASH = "766d43afec2b43e81075277bfa85b066"
SESSION_NAME = BASE_DIR / "swopex_user.session"  # авторизуй через swopex_login.py
SOURCE_PEER = "@SwopexExchange"  # канал-источник пересылки

# ---------- Caption ----------
TX_URL = "https://insight.dash.org/insight/tx/0efabf26e59dba2376266bd609e582c4d45929d5ab4bcf86dbb9723b7fb3b799"
POST_PHOTO_MESSAGE = f"{TX_URL} Գործարքը կատարված է"
WHITE = (255, 255, 255)

# ---------- Helpers ----------
def file_hash(filepath: Path):
    if not filepath.exists():
        return None
    import hashlib
    with open(filepath, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def get_usd_amount_online(dash_amount: float):
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=dash&vs_currencies=usd",
            timeout=8
        )
        r.raise_for_status()
        price = r.json().get("dash", {}).get("usd")
        return dash_amount * price if price else None
    except Exception as e:
        print("Ошибка получения курса:", e)
        return None

def add_text_to_image(image, text, coordinates, font_size, font_color=WHITE):
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(font_path), font_size)
    draw.text(coordinates, text, font=font, fill=font_color)

def read_chat_ids_from_file(filename: Path):
    if not filename.exists():
        print(f"[BtcKiosk] chat_ids file not found: {filename}")
        return []
    ids = []
    for ln in filename.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        ids.append(ln)
    return ids

def _is_numeric_chat_id(s: str) -> bool:
    if s.startswith("-"):
        s = s[1:]
    return s.isdigit()

# ---------- Send ----------
async def send_branded_forward(image_bytes: bytes, caption: str, raw_chat_ids: list[str]):
    client = TelegramClient(str(SESSION_NAME), API_ID, API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        await client.disconnect()
        raise RuntimeError("User-сессия не авторизована. Сначала swopex_login.py")

    # 1) Резолв источника
    try:
        source = await client.get_entity(SOURCE_PEER)
    except Exception as e:
        await client.disconnect()
        raise RuntimeError(f"Не удалось найти SOURCE_PEER='{SOURCE_PEER}': {e}")

    # 2) Отправка фото в SOURCE
    with BytesIO(image_bytes) as bio:
        bio.name = "receipt.png"
        src_msg = await client.send_file(
            source, bio, caption=caption, force_document=False, supports_streaming=True
        )
    print(f"[Brand] Отправлено в {SOURCE_PEER}: message_id={src_msg.id}")

    # 3) Карта активных диалогов
    dialogs_map = {}
    async for d in client.iter_dialogs():
        pid = utils.get_peer_id(d.entity)
        dialogs_map[pid] = d.entity

    async def _forward_to(entity, label: str):
        await client.forward_messages(entity, src_msg)
        print(f"[Brand] ✅ Переслано: {label}")
        await asyncio.sleep(0.25)

    # 4) Форвард адресатам
    for raw in raw_chat_ids:
        try:
            if _is_numeric_chat_id(raw):
                cid = int(raw)
                entity = dialogs_map.get(cid)
                if not entity:
                    if str(cid).startswith("-100"):
                        alt = int(str(cid)[4:])
                        entity = dialogs_map.get(alt)
                    else:
                        alt = int("-100" + str(cid))
                        entity = dialogs_map.get(alt)
                if entity:
                    await _forward_to(entity, raw)
                else:
                    print(f"[Brand] ⏭ Пропуск {raw}: нет активного диалога")
                continue

            # username / ссылка
            label = raw
            if raw.startswith("https://t.me/") or raw.startswith("t.me/"):
                uname = raw.split("/", 1)[1]
                label = "@" + uname.split("?")[0]
            try:
                entity = await client.get_entity(label)
                await _forward_to(entity, label)
            except Exception as ie:
                print(f"[Brand] ⏭ Пропуск {raw}: не удалось резолвить ({ie})")

        except RPCError as e:
            print(f"[Brand] ❌ RPCError {raw}: {e}")
        except Exception as e:
            print(f"[Brand] ❌ Ошибка {raw}: {e}")

    await client.disconnect()

# ---------- Generate and send image ----------
async def generate_and_send_image():
    try:
        if not transaction_file_path.exists():
            print("[BtcKiosk] transaction_values.txt not found")
            return
        lines = transaction_file_path.read_text(encoding="utf-8").splitlines()
        if len(lines) < 6:
            print("[BtcKiosk] transaction_values.txt malformed")
            return

        # Дата
        date_time_str = lines[2]
        dt_obj = datetime.strptime(date_time_str, "%d.%m.%Y %H:%M")
        adjusted = dt_obj - timedelta(minutes=2)
        month_names = ["января","февраля","марта","апреля","мая","июня",
                       "июля","августа","сентября","октября","ноября","декабря"]
        formatted_date = f"{adjusted.day} {month_names[adjusted.month-1]} {adjusted.strftime('%H:%M')}"

        # Базовые ресурсы
        if not image_path.exists() or not font_path.exists():
            print("[BtcKiosk] image or font missing")
            return
        img = Image.open(image_path)
        dash = float(lines[3])
        s = f"{dash:.7f}"
        add_text_to_image(img, s[:-5], (80, 60), 75, WHITE)
        add_text_to_image(img, s[-5:], (230, 70), 62, WHITE)

        recipient, sender, fee = lines[0], lines[4], float(lines[5])
        def short(a): return a if len(a)<=21 else (a[:9]+"..."+a[-9:])
        add_text_to_image(img, short(recipient), (385,340), 30, WHITE)
        add_text_to_image(img, short(sender), (385,250), 30, WHITE)
        add_text_to_image(img, f"{fee:.7f}"[:-5], (555,431), 29, WHITE)
        add_text_to_image(img, f"{fee:.8f}"[-6:], (613,435), 25, WHITE)
        add_text_to_image(img, formatted_date, (500,520), 28, WHITE)

        usd = get_usd_amount_online(dash)
        if usd is not None:
            add_text_to_image(img, f"{usd:.2f}", (75,140), 30, WHITE)

        # Сохранение
        img.save(output_image_path)
        raw_chat_ids = read_chat_ids_from_file(chat_ids_file)
        if not raw_chat_ids:
            print("[BtcKiosk] no chat_ids")
            return

        with open(output_image_path, "rb") as f:
            image_bytes = f.read()
        await send_branded_forward(image_bytes, POST_PHOTO_MESSAGE, raw_chat_ids)
    except Exception as e:
        print(f"Ошибка генерации или отправки: {e}")

# ---------- Monitor ----------
async def monitor_file():
    print("👁‍🗨 Ожидание изменений transaction_values.txt...")
    last_hash = file_hash(transaction_file_path)
    while True:
        await asyncio.sleep(2)
        current_hash = file_hash(transaction_file_path)
        if current_hash != last_hash:
            print("🆕 Файл изменён, генерируем изображение...")
            await generate_and_send_image()
            last_hash = current_hash

# ---------- Run ----------
if __name__ == "__main__":
    try:
        asyncio.run(monitor_file())
    except KeyboardInterrupt:
        print("⛔ Завершено пользователем.")
