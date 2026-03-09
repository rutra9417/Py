# -*- coding: utf-8 -*-
"""
swopex.py — генерация чёрного чека + рассылка ОТ ИМЕНИ ПОЛЬЗОВАТЕЛЯ:
1) шлём фото+caption в SOURCE_PEER (канал/чат "Swopex Exchange"),
2) делаем обычный форвард этого сообщения адресатам из chat_ids.txt
   — у получателя будет стиль "Forwarded from Swopex Exchange" и большое фото.

Примечания:
- Числовые chat_id отсылаются ТОЛЬКО если у аккаунта есть активный диалог/участие.
- username / t.me/… резолвятся через сеть и шлются без ограничений (если доступно).
- Перед запуском один раз авторизуй user-сессию через swopex_login.py (создаст swopex_user.session).
"""

import os
import asyncio
from datetime import datetime, timedelta
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import requests

# --- heartbeat (опционально) ---
import threading, time, pathlib
HB_PATH = pathlib.Path.home() / "Documents" / "vip" / "hb_forwarder.txt"
def _hb():
    while True:
        try:
            HB_PATH.write_text(str(time.time()), encoding="utf-8")
        except Exception:
            pass
        time.sleep(15)
threading.Thread(target=_hb, daemon=True).start()
# --- /heartbeat ---

# --- Telethon (user account) ---
from telethon import TelegramClient, utils
from telethon.errors import RPCError

API_ID = 20380758
API_HASH = "a3666f6b9bd37af526d27130095ef791"
SESSION_NAME = "swopex_user"  # авторизуй через swopex_login.py

# ===== БРЕНДИНГ (источник пересылки) =====
# Канал/чат-источник, из которого будет пересылка (даёт "Forwarded from Swopex Exchange")
SOURCE_PEER = "@SwopexExchange"   # <- замени на реальный username твоего канала/чата
# ========================================

# Пути
base_dir = r"C:\Users\user\Documents\vip"
image_path = os.path.join(base_dir, "main_black.png")      # чёрный шаблон
font_path = os.path.join(base_dir, "arial.ttf")
transaction_file_path = os.path.join(base_dir, "transaction_values.txt")
output_image_path = os.path.join(base_dir, "outputScreenshot_20230909_0243320.png")
chat_ids_file = os.path.join(base_dir, "chat_ids.txt")

# ONE-строка caption
TX_URL = "https://insight.dash.org/insight/tx/0efabf26e59dba2376266bd609e582c4d45929d5ab4bcf86dbb9723b7fb3b799"
POST_PHOTO_MESSAGE = f"{TX_URL} Գործարքը կատարված է"  # одна строка

WHITE = (255, 255, 255)

# --- helpers ---
def file_hash(filepath):
    if not os.path.exists(filepath):
        return None
    import hashlib
    with open(filepath, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

def get_usd_amount_online(dash_amount):
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
    font = ImageFont.truetype(font_path, font_size)
    draw.text(coordinates, text, font=font, fill=font_color)

def read_chat_ids_from_file(filename):
    if not os.path.exists(filename):
        print(f"[BtcKiosk] chat_ids file not found: {filename}")
        return []
    ids = []
    with open(filename, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            ids.append(ln)
    return ids

def _is_numeric_chat_id(s: str) -> bool:
    if s.startswith("-"):
        s = s[1:]
    return s.isdigit()

# --- отправка: постим в SOURCE, затем форвардим адресатам (сохраняем "Forwarded from") ---
async def send_branded_forward(image_bytes: bytes, caption: str, raw_chat_ids: list[str]):
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        await client.disconnect()
        raise RuntimeError("User-сессия не авторизована. Сначала запусти 'swopex_login.py' и пройди вход.")

    # 1) Резолвим источник
    try:
        source = await client.get_entity(SOURCE_PEER)
    except Exception as e:
        await client.disconnect()
        raise RuntimeError(f"Не удалось найти SOURCE_PEER='{SOURCE_PEER}': {e}")

    # 2) Отправляем в источник фото с caption (одно сообщение, 'большое фото')
    with BytesIO(image_bytes) as bio:
        bio.name = "receipt.png"
        src_msg = await client.send_file(
            source,
            bio,
            caption=caption,
            force_document=False,     # важно: как фото
            supports_streaming=True
        )
    print(f"[Brand] Оригинал отправлен в {SOURCE_PEER}: message_id={src_msg.id}")

    # 3) Карта активных диалогов для числовых id
    dialogs_map = {}
    async for d in client.iter_dialogs():
        pid = utils.get_peer_id(d.entity)
        dialogs_map[pid] = d.entity

    async def _forward_to(entity, label: str):
        # Обычный форвард — без параметра as_copy (его нет у Telethon)
        await client.forward_messages(entity, src_msg)
        print(f"[Brand] ✅ Переслано (с шапкой): {label}")
        await asyncio.sleep(0.25)

    # 4) Форвард адресатам из chat_ids.txt
    for raw in raw_chat_ids:
        try:
            if _is_numeric_chat_id(raw):
                cid = int(raw)
                entity = dialogs_map.get(cid)
                if not entity:
                    # пробуем альты для -100... и без него
                    if str(cid).startswith("-100"):
                        alt = int(str(cid)[4:])
                        entity = dialogs_map.get(alt)
                    else:
                        alt = int("-100" + str(cid))
                        entity = dialogs_map.get(alt)
                if entity:
                    await _forward_to(entity, raw)
                else:
                    print(f"[Brand] ⏭ Пропуск {raw}: нет активного диалога/канала у аккаунта.")
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
                print(f"[Brand] ⏭ Пропуск {raw}: не удалось резолвить username/ссылку ({ie})")

        except RPCError as e:
            print(f"[Brand] ❌ RPCError для {raw}: {e}")
        except Exception as e:
            print(f"[Brand] ❌ Ошибка для {raw}: {e}")

    await client.disconnect()

# --- генерация и рассылка ---
async def generate_and_send_image():
    try:
        if not os.path.exists(transaction_file_path):
            print("[BtcKiosk] transaction_values.txt not found")
            return

        with open(transaction_file_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()

        if len(lines) < 6:
            print("[BtcKiosk] transaction_values.txt malformed (need >=6 lines)")
            return

        # Дата
        date_time_str = lines[2]
        formatted_datetime = datetime.strptime(date_time_str, "%d.%m.%Y %H:%M")
        adjusted_end_time = formatted_datetime - timedelta(minutes=2)
        month_names = ["января", "февраля", "марта", "апреля", "мая", "июня",
                       "июля", "августа", "сентября", "октября", "ноября", "декабря"]
        formatted_adjusted = f"{adjusted_end_time.day} {month_names[adjusted_end_time.month - 1]} {adjusted_end_time.strftime('%H:%M')}"

        # Базовые ресурсы
        if not os.path.exists(image_path):
            print(f"[BtcKiosk] base image not found: {image_path}")
            return
        if not os.path.exists(font_path):
            print(f"[BtcKiosk] font not found: {font_path}")
            return

        # Рендер чека (чёрный фон + белый шрифт)
        img = Image.open(image_path)
        dash = float(lines[3])
        s = f"{dash:.7f}"
        add_text_to_image(img, s[:-5], (80, 60), 75, WHITE)
        add_text_to_image(img, s[-5:], (230, 70), 62, WHITE)

        recipient = lines[0]
        sender = lines[4]
        def short(a):
            return a if len(a) <= 21 else (a[:9] + "..." + a[-9:])
        add_text_to_image(img, short(recipient), (385, 340), 30, WHITE)
        add_text_to_image(img, short(sender), (385, 250), 30, WHITE)

        fee = float(lines[5])
        add_text_to_image(img, f"{fee:.7f}"[:-5], (555, 431), 29, WHITE)
        add_text_to_image(img, f"{fee:.8f}"[-6:], (613, 435), 25, WHITE)

        add_text_to_image(img, formatted_adjusted, (500, 520), 28, WHITE)

        usd = get_usd_amount_online(dash)
        if usd is not None:
            add_text_to_image(img, f"{usd:.2f}", (75, 140), 30, WHITE)

        # Сохранить картинку
        img.save(output_image_path)

        # Получатели
        raw_chat_ids = read_chat_ids_from_file(chat_ids_file)
        if not raw_chat_ids:
            print("[BtcKiosk] no chat_ids")
            return

        with open(output_image_path, "rb") as f:
            image_bytes = f.read()

        # Отправка: в SOURCE -> форвард адресатам
        await send_branded_forward(image_bytes, POST_PHOTO_MESSAGE, raw_chat_ids)

    except Exception as e:
        print(f"Ошибка генерации или отправки: {e}")

# --- мониторинг файла ---
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

if __name__ == "__main__":
    try:
        asyncio.run(monitor_file())
    except KeyboardInterrupt:
        print("⛔ Завершено пользователем.")
