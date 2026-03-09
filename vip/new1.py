import asyncio
import aiohttp
import aiofiles
import datetime
import ssl
import time
import warnings
import textwrap
import random
from telegram import Bot
from pathlib import Path
import telebot
from telebot import types

# Ignore warnings
warnings.filterwarnings("ignore")

# Paths (Windows version)
BASE_PATH = Path("C:/Users/user/Documents/vip")
USDT_FILE = BASE_PATH / "usdt.txt"
ADDRESS_FILE = BASE_PATH / "addresses.txt"
TX_FILE = BASE_PATH / "transaction_values.txt"
CHAT_IDS_FILE = BASE_PATH / "chat_ids.txt"
OUTPUT_FILE = BASE_PATH / "main_oper.txt"

# Telegram bot tokens
BOT_TOKEN_1 = "6263739899:AAH11lBg0hHj0jFuq2oWiCLzZXLMMWn3iuA"
BOT_TOKEN_2 = "6067244950:AAGbAHcyAPWjtsJHMOmvY1Uf6wfaW4KJo5w"

# Constants
RATE_AMD = 408.0

# Use default SSL context without specifying a custom cert (suitable for Windows)
SSL_CONTEXT = ssl.create_default_context()

# Globals
last_txids = {}
previous_transaction_ids = set()
monitored_addresses = {}
address_comments = {}

# UI Bot with inline buttons
ui_bot = telebot.TeleBot(BOT_TOKEN_2)
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
    if call.message:
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
                    action = 'Buy' if user_choices[cid].startswith('buy_') else 'Sell'
                    currency = entry['currency'].upper()
                    ui_bot.send_message(cid, f'{action} {amount} {currency}')
                    user_choices.pop(cid, None)
                    user_currency_amount.pop(cid, None)
                return
            else:
                entry['amount'] = amount + call.data
            show_amount_input_keyboard(cid, entry['amount'])

def show_amount_input_keyboard(chat_id, current="0"):
    markup = types.InlineKeyboardMarkup()
    number_buttons = [types.InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(1, 10)]
    markup.row(types.InlineKeyboardButton('C', callback_data='clear'), types.InlineKeyboardButton('⬅️', callback_data='del'))
    markup.row(*number_buttons[0:3])
    markup.row(*number_buttons[3:6])
    markup.row(*number_buttons[6:9])
    markup.row(types.InlineKeyboardButton('.', callback_data='.'), types.InlineKeyboardButton('0', callback_data='0'), types.InlineKeyboardButton('✅', callback_data='done'))
    ui_bot.send_message(chat_id, f'Որքա՞ն AMD-ի համարժեք DASH եք ցանկանում գնելը՝\nԳումար: {current or "0"}', reply_markup=markup)

TEMPLATE_1 = """
………………………………………………………….
To: {dash_address}
Amount: {amount:.8f} DASH (${usd_amount} / {amd_amount} AMD) 
Time: {date} {time}
DASH rate: ${dash_rate} (binance)
Sent by @BitcoinOperator
………………………………………………………….
Transaction: https://blockchair.com/dash/transaction/{transaction_id}
""".strip()

TEMPLATE_2 = textwrap.dedent("""
Գործարքի համար: {transaction_no}
Գործարքի տեսակ: Գնում
Գումարի չափ: {amd_amount} AMD
Կարգավիճակ։ հաջորդ
Ձեզ փոխանցվել է: {amount} DASH
Հաշիվ: {dash_address}
Ամսաթիվ: {date} {time}
Փոխանցում: {transaction_id}
Transaction Link: https://blockchair.com/dash/transaction/{transaction_id}
""")

def calculate_amounts(rate, amount):
    usd = round(rate * amount, 2)
    amd = round(amount * rate * RATE_AMD / 100) * 100
    return usd, amd, amd + 1500

async def fetch_price():
    url = 'https://api.binance.com/api/v3/ticker/price?symbol=DASHUSDT'
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, ssl=SSL_CONTEXT, timeout=10) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return float(data.get('price', 26.0))
    except Exception as e:
        print(f"[PRICE] Fetch error: {e}")
        return 23.0

def load_addresses():
    addresses = {}
    if not ADDRESS_FILE.exists():
        return addresses
    for line in ADDRESS_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.split('#')
        address = parts[0].strip()
        if not address:
            continue
        comment = parts[1].strip() if len(parts) > 1 else ""
        addresses[address] = comment
    return addresses

async def send_to_bots(address, txid, amount, dt, rate):
    if txid in previous_transaction_ids:
        return
    previous_transaction_ids.add(txid)
    usd, amd, total = calculate_amounts(rate, amount)
    tx_no = random.randint(100000, 999999)
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
    msg2 = TEMPLATE_2.format(
        transaction_no=tx_no,
        amd_amount=amd,
        amount=amount,
        dash_address=address,
        date=dt.strftime('%Y-%m-%d'),
        time=dt.strftime('%H:%M:%S'),
        transaction_id=txid
    )
    chat_ids = [int(line.strip()) for line in CHAT_IDS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    bot1 = Bot(token=BOT_TOKEN_1)
    bot2 = Bot(token=BOT_TOKEN_2)
    for cid in chat_ids:
        try:
            if comment:
                await bot1.send_message(chat_id=cid, text=f"Комментарий: {comment}")
                await bot2.send_message(chat_id=cid, text=f"Comment: {comment}")
            await bot1.send_message(chat_id=cid, text=msg1)
            await bot2.send_message(chat_id=cid, text=msg2)
            print(f"[BOT] Sent notifications for tx: {txid}")
        except Exception as e:
            print(f"[BOT] Send error: {e}")
    OUTPUT_FILE.write_text((f"Комментарий: {comment}\n" if comment else "") + msg1 + "\n" + msg2, encoding="utf-8")

async def monitor_transactions():
    print("[TX] Monitoring started.")
    global monitored_addresses, address_comments
    address_data = load_addresses()
    monitored_addresses = set(address_data.keys())
    address_comments = address_data
    while True:
        found_new_tx = False
        for address in monitored_addresses:
            try:
                print(f"[CHECK] Checking address: {address}")
                async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=SSL_CONTEXT)) as session:
                    async with session.get(f"https://insight.dash.org/insight-api/addr/{address}/utxo") as r:
                        utxos = await r.json()
                    if not utxos:
                        continue
                    latest = utxos[0]
                    txid = latest['txid']
                    if txid == last_txids.get(address):
                        continue
                    print(f"[TX] New transaction detected: {txid}")
                    async with session.get(f"https://insight.dash.org/insight-api/tx/{txid}") as r:
                        tx_data = await r.json()
                    value = latest['satoshis'] / 1e8
                    dt = datetime.datetime.now()
                    rate = await fetch_price()
                    await send_to_bots(address, txid, value, dt, rate)
                    last_txids[address] = txid
                    found_new_tx = True
            except Exception as e:
                print(f"[TX] Error on {address}: {e}")
        if not found_new_tx:
            print("[WAIT] No new transactions. Waiting...")
        updated_address_data = load_addresses()
        if updated_address_data != address_data:
            new_addresses = set(updated_address_data.keys()) - monitored_addresses
            if new_addresses:
                print(f"[UPDATE] New addresses detected: {', '.join(new_addresses)}")
            monitored_addresses = set(updated_address_data.keys())
            address_comments = updated_address_data
            address_data = updated_address_data
        await asyncio.sleep(5)

async def main():
    await asyncio.gather(monitor_transactions())

if __name__ == "__main__":
    import threading
    threading.Thread(target=ui_bot.polling, daemon=True).start()
    asyncio.run(main())
