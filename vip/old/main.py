import asyncio
import aiohttp
import datetime
import ssl
import time
import warnings
import textwrap
import random
from telegram import Bot
from pathlib import Path

# Ignore warnings
warnings.filterwarnings("ignore")

# Paths
BASE_PATH = Path("/storage/emulated/0/top")
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
SSL_CONTEXT = ssl.create_default_context(cafile="/data/data/com.termux/files/usr/etc/tls/cert.pem")

# Globals
last_txids = {}
previous_transaction_ids = set()
monitored_addresses = set()

# --------- Binance Price Fetch (Single Use) ---------
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

# --------- Save Transaction Details ---------
def save_transaction_details(address, txid, amount, sender_address, fee, total_inputs, total_outputs, timestamp):
    with open(TX_FILE, "w") as f:
        f.write(f"{address}\n")
        f.write(f"{txid}\n")
        f.write(f"{timestamp}\n")
        f.write(f"{amount:.8f}\n")
        f.write(f"{sender_address}\n")
        f.write(f"{fee:.8f}\n")
        f.write(f"{total_inputs:.8f}\n")
        f.write(f"{total_outputs:.8f}\n")

# --------- Monitor Transactions ---------
async def monitor_transactions():
    print("[TX] Monitoring started.")
    global monitored_addresses
    monitored_addresses = set(ADDRESS_FILE.read_text().splitlines())

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

                    # New transaction
                    print(f"[TX] New transaction detected: {txid}")
                    async with session.get(f"https://insight.dash.org/insight-api/tx/{txid}") as r:
                        tx_data = await r.json()
                    value = latest['satoshis'] / 1e8
                    dt = datetime.datetime.now()
                    rate = await fetch_price()
                    await send_to_bots(address, txid, value, dt, rate, tx_data)
                    last_txids[address] = txid
                    found_new_tx = True
            except Exception as e:
                print(f"[TX] Error on {address}: {e}")

        if not found_new_tx:
            print("[WAIT] No new transactions. Waiting...")

        updated_addresses = set(ADDRESS_FILE.read_text().splitlines())
        if updated_addresses != monitored_addresses:
            new_addresses = updated_addresses - monitored_addresses
            if new_addresses:
                print(f"[UPDATE] New addresses detected: {', '.join(new_addresses)}")
                monitored_addresses = updated_addresses

        await asyncio.sleep(5)

# --------- Send Notifications ---------
async def send_to_bots(address, txid, amount, dt, rate, tx_data):
    if txid in previous_transaction_ids:
        return
    previous_transaction_ids.add(txid)

    usd, amd, total = calculate_amounts(rate, amount)
    tx_no = random.randint(100000, 999999)

    msg1 = TEMPLATE_1.format(
        dash_address=address, amount=amount, usd_amount=usd, amd_amount=amd,
        date=dt.strftime('%Y-%m-%d'), time=dt.strftime('%H:%M:%S'),
        transaction_id=txid
    )

    msg2 = TEMPLATE_2.format(
        transaction_no=tx_no, amd_amount=amd, amount=amount,
        dash_address=address, date=dt.strftime('%Y-%m-%d'), time=dt.strftime('%H:%M:%S'),
        transaction_id=txid
    )

    try:
        sender = tx_data["vin"][0]["addr"]
        total_inputs = sum(float(vin["value"]) for vin in tx_data["vin"])
        total_outputs = sum(float(vout["value"]) for vout in tx_data["vout"])
        fee = total_inputs - total_outputs
        save_transaction_details(address, txid, amount, sender, fee, total_inputs, total_outputs, dt.strftime('%Y-%m-%d %H:%M:%S'))
    except Exception as e:
        print(f"[FILE] Error saving transaction details: {e}")

    chat_ids = [int(line.strip()) for line in CHAT_IDS_FILE.read_text().splitlines() if line.strip()]
    bot1 = Bot(token=BOT_TOKEN_1)
    bot2 = Bot(token=BOT_TOKEN_2)

    for cid in chat_ids:
        try:
            await bot1.send_message(chat_id=cid, text=msg1)
            await bot2.send_message(chat_id=cid, text=msg2)
            print(f"[BOT] Sent notifications for tx: {txid}")
        except Exception as e:
            print(f"[BOT] Send error: {e}")

    OUTPUT_FILE.write_text(msg1 + "\n" + msg2)

# --------- Helper Functions ---------
def calculate_amounts(rate, amount):
    usd = round(rate * amount, 2)
    amd = round(amount * rate * RATE_AMD / 100) * 100
    return usd, amd, amd + 1500

# --------- Templates ---------
TEMPLATE_1 = textwrap.dedent("""
-----------------------------------------------
To: {dash_address}
Amount: {amount:.8f} DASH (${usd_amount} / {amd_amount} AMD)
Time: {date} {time}
Sent by @BitcoinOperator
Transaction: https://blockchair.com/dash/transaction/{transaction_id}
-----------------------------------------------
""")

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

# --------- Run Main ---------
async def main():
    await monitor_transactions()

if __name__ == "__main__":
    asyncio.run(main())