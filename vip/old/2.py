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
from PIL import Image, ImageDraw, ImageFont

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
IMAGE_BOT_TOKEN = "6143029111:AAE8_wMyTj7ZvIMWNr1TSQeEbCg2tpLiNDU"

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
                    await send_to_bots(address, txid, value, dt, rate)
                    last_txids[address] = txid
                    found_new_tx = True
            except Exception as e:
                print(f"[TX] Error on {address}: {e}")

        if not found_new_tx:
            print("[WAIT] No new transactions. Waiting...")

        # Check for updates to addresses.txt
        updated_addresses = set(ADDRESS_FILE.read_text().splitlines())
        if updated_addresses != monitored_addresses:
            new_addresses = updated_addresses - monitored_addresses
            if new_addresses:
                print(f"[UPDATE] New addresses detected: {', '.join(new_addresses)}")
                monitored_addresses = updated_addresses

        await asyncio.sleep(5)

# --------- Send Notifications ---------
async def send_to_bots(address, txid, amount, dt, rate):
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

    # Save data to transaction file
    TX_FILE.write_text("\n".join([address, str(amount), dt.strftime('%Y-%m-%d %H:%M:%S'), str(amount), address, "0.00001"]))

    # Generate and send image
    await generate_and_send_image()

# --------- Image Generator and Sender ---------
async def generate_and_send_image():
    try:
        img = Image.open(f"{BASE_PATH}/main_white.png")
        font_path = f"{BASE_PATH}/arial.ttf"
        with open(TX_FILE, "r") as file:
            lines = file.read().splitlines()

        date_time_str = lines[2]
        formatted_datetime = datetime.datetime.strptime(date_time_str, "%Y-%m-%d %H:%M:%S")
        adjusted_time = formatted_datetime - datetime.timedelta(minutes=2)
        month_names = ["января", "февраля", "марта", "апреля", "мая", "июня",
                       "июля", "августа", "сентября", "октября", "ноября", "декабря"]
        formatted_adjusted = adjusted_time.strftime(f"%-d {month_names[adjusted_time.month - 1]} %I:%M")

        def add_text(img, text, pos, size, color):
            draw = ImageDraw.Draw(img)
            font = ImageFont.truetype(font_path, size)
            draw.text(pos, text, font=font, fill=color)

        dash = float(lines[3])
        fee = float(lines[5])
        usd = dash * await fetch_price()
        recipient = lines[0][:9] + "..." + lines[0][-9:]
        sender = lines[4][:9] + "..." + lines[4][-9:]

        add_text(img, formatted_adjusted, (500, 520), 28, (19, 18, 23))
        add_text(img, "{:.7f}".format(dash)[:-5], (80, 60), 75, (19, 18, 23))
        add_text(img, "{:.7f}".format(dash)[-5:], (230, 70), 62, (19, 18, 23))
        add_text(img, recipient, (385, 340), 30, (19, 18, 23))
        add_text(img, sender, (385, 250), 30, (19, 18, 23))
        add_text(img, "{:.7f}".format(fee)[:-5], (555, 431), 29, (19, 18, 23))
        add_text(img, "{:.8f}".format(fee)[-6:], (613, 435), 25, (19, 18, 23))
        add_text(img, f"{usd:.2f}", (75, 140), 30, (131, 142, 138))

        output_path = f"{BASE_PATH}/outputScreenshot_20230909_0243320.png"
        img.save(output_path)

        # Send image
        bot = Bot(token=IMAGE_BOT_TOKEN)
        chat_ids = [int(line.strip()) for line in CHAT_IDS_FILE.read_text().splitlines()]
        for cid in chat_ids:
            with open(output_path, "rb") as image_file:
                await bot.send_photo(chat_id=cid, photo=image_file)
                print(f"[IMG] Sent image to {cid}")
    except Exception as e:
        print(f"[IMG] Error generating/sending image: {e}")

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