import os
import math
import asyncio
import datetime
import time
import threading
from pathlib import Path
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

import aiohttp
import ssl

# ---------- Paths ----------
BASE_DIR = Path.home() / "vip"
BASE_DIR.mkdir(exist_ok=True)
TX_FILE = BASE_DIR / "transaction_values.txt"
OUTPUT_FILE = BASE_DIR / "output.txt"
ADDRESS_FILE = BASE_DIR / "addresses.txt"
CHAT_IDS_FILE = BASE_DIR / "chat_ids.txt"

# ---------- Bot tokens ----------
BOT_TOKEN_1 = "6143029111:AAE8_wMyTj7ZvIMWNr1TSQeEbCg2tpLiNDU"
BOT_TOKEN_2 = "7524105753:AAFxqCrelnf4C0g2I2ig_RfmyPobng5idMA"
ui_bot = Bot(token=BOT_TOKEN_1)

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

# ---------- State ----------
user_currency_amount = {}
user_choices = {}
previous_transaction_ids = set()
monitored_addresses = set()
address_comments = {}
last_txids = {}
SSL_CONTEXT = ssl.create_default_context()

# ---------- UI Amount Keyboard ----------
def show_amount_input_keyboard(chat_id, current="0"):
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton('C', callback_data='clear'), InlineKeyboardButton('⬅️', callback_data='del')],
        [InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(1, 4)],
        [InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(4, 7)],
        [InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(7, 10)],
        [InlineKeyboardButton('.', callback_data='.'), InlineKeyboardButton('0', callback_data='0'), InlineKeyboardButton('✅', callback_data='done')]
    ])
    ui_bot.send_message(chat_id, f'Որքա՞ն AMD-ի համարժեք DASH եք ցանկանում գնելը՝\nԳումար: {current if current else "0"}', reply_markup=markup)

def handle_amount_input(call):
    cid = call.message.chat.id
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

# ---------- Templates ----------
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

# ---------- Calculations ----------
RATE_AMD = 408.0
ROUND_MODE = "round"

def calculate_amounts(rate, amount):
    usd_raw = rate * amount
    usd = math.ceil(usd_raw) if ROUND_MODE=="ceil" else round(usd_raw)
    amd = round(rate * amount * RATE_AMD)
    return usd, amd

def append_transaction_to_file(address, txid, dt, amount, sender, fee):
    TX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with TX_FILE.open("w", encoding="utf-8") as f:
        f.write(f"{address}\n{txid}\n{dt.strftime('%d.%m.%Y %H:%M')}\n{amount:.8f}\n{sender}\n{fee:.8f}\n\n")

# ---------- Price fetch ----------
_last_rate = 23.0
async def fetch_price():
    global _last_rate
    urls = [
        "https://api.binance.com/api/v3/ticker/price?symbol=DASHUSDT",
        "https://api.binance.us/api/v3/ticker/price?symbol=DASHUSDT",
        "https://api.coingecko.com/api/v3/simple/price?ids=dash&vs_currencies=usd",
    ]
    timeout = aiohttp.ClientTimeout(total=10)
    for url in urls:
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, ssl=SSL_CONTEXT) as r:
                    r.raise_for_status()
                    data = await r.json()
                    price = float(data.get("price") if "binance" in url else data["dash"]["usd"])
                    if price > 0:
                        _last_rate = price
                        return price
        except Exception as e:
            print(f"[PRICE] Fetch error from {url}: {e}")
            await asyncio.sleep(1.5)
    return _last_rate

# ---------- Addresses ----------
def load_addresses():
    addresses = {}
    if not ADDRESS_FILE.exists():
        return addresses
    for line in ADDRESS_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.split('#', 1)
        addr = parts[0].strip()
        if not addr: continue
        comment = parts[1].strip() if len(parts)>1 else ""
        addresses[addr] = comment
    return addresses

def read_chat_ids():
    if not CHAT_IDS_FILE.exists(): return []
    out = []
    for line in CHAT_IDS_FILE.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s:
            try: out.append(int(s))
            except: pass
    return out

# ---------- Send ----------
async def send_to_bots(address, txid, amount, dt, rate):
    if txid in previous_transaction_ids: return
    previous_transaction_ids.add(txid)
    usd, amd = calculate_amounts(rate, amount)
    comment = address_comments.get(address,"")
    msg1 = TEMPLATE_1.format(
        dash_address=address,
        amount=amount,
        usd_amount=usd,
        amd_amount=amd,
        date=dt.strftime('%Y-%m-%d'),
        time=dt.strftime('%H:%M:%S'),
        dash_rate=round(rate,2),
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
                await bot1.send_message(cid, f"Комментарий: {comment}")
                await bot2.send_message(cid, f"Comment: {comment}")
            await bot1.send_message(cid, msg1)
            await bot2.send_message(cid, msg1)
            print(f"[BOT] Sent notifications for tx: {txid} -> {cid}")
        except Exception as e:
            print(f"[BOT] Send error ({cid}): {e}")

# ---------- Monitor ----------
async def monitor_transactions():
    global monitored_addresses, address_comments, last_txids
    address_data = load_addresses()
    monitored_addresses = set(address_data.keys())
    address_comments = address_data
    while True:
        rate = await fetch_price()
        for address in list(monitored_addresses):
            try:
                async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=SSL_CONTEXT)) as session:
                    async with session.get(f"https://insight.dash.org/insight-api/addr/{address}/utxo") as r:
                        if r.status!=200: continue
                        utxos = await r.json()
                    if not utxos: continue
                    latest = utxos[0]
                    txid = latest.get("txid")
                    if not txid or txid==last_txids.get(address): continue
                    async with session.get(f"https://insight.dash.org/insight-api/tx/{txid}") as r:
                        if r.status!=200: continue
                        tx_data = await r.json()
                    timestamp = tx_data.get("time", int(time.time()))
                    dt = datetime.datetime.utcfromtimestamp(timestamp) + datetime.timedelta(hours=4)
                    value = latest.get("satoshis",0)/1e8
                    inputs = tx_data.get("vin",[])
                    sender = inputs[0].get("addr","unknown") if inputs else "unknown"
                    append_transaction_to_file(address, txid, dt, value, sender, tx_data.get("fees",0.0))
                    await send_to_bots(address, txid, value, dt, rate)
                    last_txids[address] = txid
            except Exception as e:
                print(f"[TX] Error on {address}: {e}")
        await asyncio.sleep(5)

# ---------- Main ----------
async def main():
    await asyncio.gather(monitor_transactions())

if __name__ == "__main__":
    import threading
    def run_ui_bot_forever():
        delay = 1
        while True:
            try:
                ui_bot.infinity_polling(timeout=30)
                delay = 1
            except Exception as e:
                print(f"[UI] polling error: {e}; restart in {delay}s")
                time.sleep(delay)
                delay = min(delay*2, 60)
    threading.Thread(target=run_ui_bot_forever, daemon=True).start()
    asyncio.run(main())
