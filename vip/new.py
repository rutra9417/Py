# -*- coding: utf-8 -*-
import os
import asyncio
import aiohttp
import datetime
import ssl
import time
import warnings
import random
import math
from pathlib import Path

# .env опционально
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# PTB (async)
from telegram import Bot

# pyTelegramBotAPI
import telebot
from telebot import types, apihelper

# requests-ретраи для telebot long polling
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from PIL import Image

# --- heartbeat ---
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

# --------------------- Константы/пути ---------------------
BASE_PATH = Path.home() / "Documents" / "vip"
USDT_FILE = BASE_PATH / "usdt.txt"
ADDRESS_FILE = BASE_PATH / "addresses.txt"
TX_FILE = BASE_PATH / "transaction_values.txt"
CHAT_IDS_FILE = BASE_PATH / "chat_ids.txt"
OUTPUT_FILE = BASE_PATH / "main_oper.txt"

BOT_TOKEN_1 = "6263739899:AAH11lBg0hHj0jFuq2oWiCLzZXLMMWn3iuA"
BOT_TOKEN_2 = "6067244950:AAGbAHcyAPWjtsJHMOmvY1Uf6wfaW4KJo5w"

RATE_AMD = 407.0  # множитель для AMD

SSL_CONTEXT = ssl.create_default_context()

# округление USD: nearest|ceil
ROUND_MODE = (os.getenv("ROUND_MODE", "nearest") or "nearest").lower()

# --------------------- Утилиты ---------------------
def detect_format(path):
    try:
        with Image.open(path) as img:
            return img.format
    except Exception:
        return None

warnings.filterwarnings("ignore")

last_txids = {}
previous_transaction_ids = set()
monitored_addresses = set()
address_comments = {}

# ---------- telebot UI ----------
ui_bot = telebot.TeleBot(BOT_TOKEN_2, parse_mode="HTML")

# усилим стойкость к обрывам сети
_session = requests.Session()
_retries = Retry(
    total=5,
    connect=5,
    read=5,
    backoff_factor=1.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=frozenset(["GET", "POST"])
)
_adapter = HTTPAdapter(max_retries=_retries)
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)
apihelper.SESSION = _session

user_choices = {}
user_currency_amount = {}

@ui_bot.message_handler(commands=['start'])
def send_start_message(message):
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton('Գնել BTC', callback_data='buy_btc'),
        types.InlineKeyboardButton('Վաճառել BTC', callback_data='sell_btc')
    )
    markup.row(
        types.InlineKeyboardButton('Գնել DASH', callback_data='buy_dash'),
        types.InlineKeyboardButton('Վաճառել DASH', callback_data='sell_dash')
    )
    markup.row(
        types.InlineKeyboardButton('Գնել LTC', callback_data='buy_ltc'),
        types.InlineKeyboardButton('Վաճառել LTC', callback_data='sell_ltc')
    )
    markup.row(
        types.InlineKeyboardButton('Գնել USD-TRC20', callback_data='buy_usd'),
        types.InlineKeyboardButton('Վաճառել USDT', callback_data='sell_usd')
    )
    ui_bot.send_message(message.chat.id, '👨‍🚀 Ես ձեզ կօգնեմ գնել կամ վաճառել Bitcoin և Dash 💵', reply_markup=markup)

@ui_bot.callback_query_handler(func=lambda call: True)
def handle_inline_buttons(call):
    if not call.message:
        return
    cid = call.message.chat.id
    if call.data.startswith(('buy_', 'sell_')):
        user_choices[cid] = call.data
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton('🇦🇲 AMD', callback_data='amd'),
            types.InlineKeyboardButton('🇺🇸 USD', callback_data='usd'),
            types.InlineKeyboardButton('💰 BTC', callback_data='btc')
        )
        ui_bot.send_message(cid, 'Ի՞նչ արժույթով եք ցանկանում նշել DASH-ի քանակը', reply_markup=markup)

    elif call.data in ('amd', 'usd', 'btc'):
        user_choice = user_choices.get(cid)
        if user_choice:
            user_currency_amount[cid] = {'currency': call.data}
            show_amount_input_keyboard(cid)

    elif call.data in ('clear', 'del', 'done') or call.data.isdigit() or call.data == '.':
        if cid not in user_currency_amount:
            return
        entry = user_currency_amount[cid]
        amount = entry.get('amount', '')
        if call.data == 'clear':
            entry['amount'] = ''
        elif call.data == 'del':
            entry['amount'] = amount[:-1]
        elif call.data == 'done':
            if amount:
                action = 'Buy' if user_choices.get(cid, '').startswith('buy_') else 'Sell'
                currency = entry['currency'].upper()
                ui_bot.send_message(cid, f'{action} {amount} {currency}')
                user_choices.pop(cid, None)
                user_currency_amount.pop(cid, None)
            return
        else:
            entry['amount'] = (amount + call.data)[:32]
        show_amount_input_keyboard(cid, entry['amount'])

def show_amount_input_keyboard(chat_id, current="0"):
    markup = types.InlineKeyboardMarkup()
    number_buttons = [types.InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(1, 10)]
    markup.row(types.InlineKeyboardButton('C', callback_data='clear'), types.InlineKeyboardButton('⬅️', callback_data='del'))
    markup.row(*number_buttons[0:3])
    markup.row(*number_buttons[3:6])
    markup.row(*number_buttons[6:9])
    markup.row(types.InlineKeyboardButton('.', callback_data='.'), types.InlineKeyboardButton('0', callback_data='0'), types.InlineKeyboardButton('✅', callback_data='done'))
    ui_bot.send_message(chat_id, f'Որքա՞ն AMD-ի համարժեք DASH եք ցանկանում գնելը՝\nԳումար: {current if current else "0"}', reply_markup=markup)

# ---------- Шаблоны ----------
TEMPLATE_1 = (
    "……………………………………………………………\n"
    "To: {dash_address}\n"
    "Amount: {amount:.8f} DASH (${usd_amount:.0f} / {amd_amount} AMD)\n"
    "Time: {date} {time}\n"
    "DASH rate: ${dash_rate} (binance)\n"
    "Sent by @BitcoinOperator\n"
    "……………………………………………………………\n"
    "Transaction: https://blockchair.com/dash/transaction/{transaction_id}"
)

def calculate_amounts(rate, amount):
    usd_raw = rate * amount
    if ROUND_MODE == "ceil":
        usd = math.ceil(usd_raw)
    else:
        usd = round(usd_raw)
    amd = round(rate * amount * RATE_AMD)
    return usd, amd

def append_transaction_to_file(address, txid, dt, amount, sender, fee):
    TX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with TX_FILE.open("w", encoding="utf-8") as f:
        f.write(f"{address}\n{txid}\n{dt.strftime('%d.%m.%Y %H:%M')}\n{amount:.8f}\n{sender}\n{fee:.8f}\n\n")

# ---------- Цена с fallback’ами ----------
_last_rate = 23.0

async def fetch_price():
    global _last_rate
    # порядок источников
    urls = [
        "https://api.binance.com/api/v3/ticker/price?symbol=DASHUSDT",
        "https://api.binance.us/api/v3/ticker/price?symbol=DASHUSDT",
        "https://api.coingecko.com/api/v3/simple/price?ids=dash&vs_currencies=usd",
    ]
    timeout = aiohttp.ClientTimeout(total=10)
    for url in urls:
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, ssl=SSL_CONTEXT) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    if "coingecko" in url:
                        price = float(data["dash"]["usd"])
                    else:
                        price = float(data.get("price", 0) or 0)
                    if price > 0:
                        _last_rate = price
                        return price
        except Exception as e:
            print(f"[PRICE] Fetch error from {url}: {e}")
            await asyncio.sleep(1.5)
    # если всё упало — вернём последний или дефолт
    return _last_rate

# ---------- Адреса/чаты ----------
def load_addresses():
    addresses = {}
    if not ADDRESS_FILE.exists():
        return addresses
    for line in ADDRESS_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.split('#', 1)
        address = parts[0].strip()
        if not address:
            continue
        comment = parts[1].strip() if len(parts) > 1 else ""
        addresses[address] = comment
    return addresses

def read_chat_ids():
    if not CHAT_IDS_FILE.exists():
        print(f"[BOT] chat_ids file not found: {CHAT_IDS_FILE}")
        return []
    out = []
    for line in CHAT_IDS_FILE.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            out.append(int(s))
        except:
            pass
    return out

# ---------- Отправка ----------
async def send_to_bots(address, txid, amount, dt, rate):
    if txid in previous_transaction_ids:
        return
    previous_transaction_ids.add(txid)

    usd, amd = calculate_amounts(rate, amount)
    comment = address_comments.get(address, "")

    msg1 = TEMPLATE_1.format(
        dash_address=address,
        amount=amount,
        usd_amount=usd,
        amd_amount=amd,
        date=dt.strftime('%Y-%m-%d'),
        time=dt.strftime('%H:%M:%S'),
        dash_rate=round(rate, 2),
        transaction_id=txid
    )

    chat_ids = read_chat_ids()
    if not chat_ids:
        print("[BOT] No chat_ids to send")
        return

    bot1 = Bot(token=BOT_TOKEN_1)
    bot2 = Bot(token=BOT_TOKEN_2)

    for cid in chat_ids:
        try:
            if comment:
                await bot1.send_message(chat_id=cid, text=f"Комментарий: {comment}", disable_web_page_preview=False)
                await bot2.send_message(chat_id=cid, text=f"Comment: {comment}", disable_web_page_preview=False)
            await bot1.send_message(chat_id=cid, text=msg1, disable_web_page_preview=False)
            await bot2.send_message(chat_id=cid, text=msg1, disable_web_page_preview=False)
            print(f"[BOT] Sent notifications for tx: {txid} -> {cid}")
        except Exception as e:
            # типичные: blocked, user deactivated, chat not found
            print(f"[BOT] Send error ({cid}): {e}")

    OUTPUT_FILE.write_text((f"Комментарий: {comment}\n" if comment else "") + msg1, encoding="utf-8")

# ---------- Монитор ----------
async def monitor_transactions():
    print("[TX] Monitoring started.")
    global monitored_addresses, address_comments
    address_data = load_addresses()
    monitored_addresses = set(address_data.keys())
    address_comments = address_data

    while True:
        found_new_tx = False
        rate = await fetch_price()

        for address in list(monitored_addresses):
            try:
                print(f"[CHECK] {address}")
                async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=SSL_CONTEXT)) as session:
                    # источник может лагать; оставляем как есть
                    async with session.get(f"https://insight.dash.org/insight-api/addr/{address}/utxo") as r:
                        if r.status != 200:
                            print(f"[TX] UTXO fetch failed: {r.status}")
                            continue
                        utxos = await r.json()

                    if not utxos:
                        continue

                    latest = utxos[0]
                    txid = latest.get('txid')
                    if not txid:
                        continue

                    if txid == last_txids.get(address):
                        continue

                    print(f"[TX] New transaction: {txid}")

                    async with session.get(f"https://insight.dash.org/insight-api/tx/{txid}") as r:
                        if r.status != 200:
                            print(f"[TX] TX fetch failed: {r.status}")
                            continue
                        tx_data = await r.json()

                    timestamp = tx_data.get("time", int(time.time()))
                    dt = datetime.datetime.utcfromtimestamp(timestamp) + datetime.timedelta(hours=4)

                    value = latest.get('satoshis', 0) / 1e8
                    inputs = tx_data.get("vin", [])
                    from_address = inputs[0].get("addr", "unknown") if inputs else "unknown"
                    fee = tx_data.get("fees", 0.0) or 0.0

                    append_transaction_to_file(address, txid, dt, value, from_address, fee)
                    await send_to_bots(address, txid, value, dt, rate)
                    last_txids[address] = txid
                    found_new_tx = True
            except Exception as e:
                print(f"[TX] Error on {address}: {e}")

        if not found_new_tx:
            print("[WAIT] No new transactions. Waiting...")

        # Горячее обновление списка адресов
        updated_address_data = load_addresses()
        if updated_address_data != address_data:
            new_addresses = set(updated_address_data.keys()) - monitored_addresses
            if new_addresses:
                print(f"[UPDATE] New addresses detected: {', '.join(new_addresses)}")
            monitored_addresses = set(updated_address_data.keys())
            address_comments = updated_address_data
            address_data = updated_address_data

        await asyncio.sleep(5)

# ---------- Запуск ----------
async def main():
    await asyncio.gather(monitor_transactions())

if __name__ == "__main__":
    # устойчивый цикл polling для telebot
    import threading

    def run_ui_bot_forever():
        delay = 1
        while True:
            try:
                # infinity_polling сам делает reconnection, но бывает падает — ловим и рестартим
                ui_bot.infinity_polling(timeout=30, long_polling_timeout=30, allowed_updates=None)
                delay = 1  # если вышли чисто — сбросим бэкофф
            except Exception as e:
                print(f"[UI] polling error: {e}; restart in {delay}s")
                time.sleep(delay)
                delay = min(delay * 2, 60)

    threading.Thread(target=run_ui_bot_forever, daemon=True).start()
    asyncio.run(main())
