import trio
from datetime import datetime
from telegram import Bot, error as telegram_error
import warnings
import time
from pathlib import Path

warnings.filterwarnings("ignore", category=RuntimeWarning, module="trio")

# Base path
BASE_PATH = Path("/storage/emulated/0/top")

# File paths
CHAT_IDS_FILE = BASE_PATH / "chat_ids.txt"
RATE_FILE = BASE_PATH / "usdt.txt"
TRANSACTION_FILE = BASE_PATH / "transaction_values.txt"
OUTPUT_FILE = BASE_PATH / "main_oper.txt"

# Load chat IDs
with CHAT_IDS_FILE.open("r") as file:
    bot_chat_ids = [int(line.strip()) for line in file if line.strip()]

# Helper function to read USDT rate
def read_usdt_rate(file_path: Path, default: float = 26.0) -> float:
    try:
        with file_path.open("r") as f:
            line = f.readline().strip()
            return float(line.split()[0]) if line else default
    except Exception:
        return default

# Load default rate
rate = read_usdt_rate(RATE_FILE)

bot_token = "6263739899:AAH11lBg0hHj0jFuq2oWiCLzZXLMMWn3iuA"
rateamd = 413.0

# Read transaction values
async def get_transaction_data():
    with TRANSACTION_FILE.open("r") as values_file:
        lines = values_file.readlines()
        if len(lines) >= 4:
            dash_address = lines[0].strip()
            transaction_id = lines[1].strip()
            date_time_str = lines[2].strip()
            amount = float(lines[3].strip())
            return dash_address, transaction_id, date_time_str, amount
    return None

def calculate_amounts(rate, amount):
    usd_amount = round(rate * amount, 2)
    amd_amount = round(amount * rate * rateamd)
    return usd_amount, amd_amount, amd_amount + 1500

def format_usd_amount(amount):
    if amount % 1 != 0:
        formatted = f"${amount:.1f}".rstrip('0').rstrip('.')
    else:
        formatted = f"${int(amount)}"
    return formatted

def format_output(template, dash_address, amount, usd_amount, amd_amount, date_time, rate, txid):
    return template.format(
        dash_address=dash_address,
        amount=amount,
        usd_amount_str=format_usd_amount(usd_amount),
        amd_amount=amd_amount,
        date_time=date_time,
        rate=rate,
        txid=txid
    )

async def retry_with_delay(func, delay=60):
    while True:
        try:
            await func()
            return
        except Exception as e:
            print("Error occurred:", e)
            await trio.sleep(delay)

previous_transaction_ids = set()

async def generate_transaction(template):
    while True:
        current_rate = read_usdt_rate(RATE_FILE)

        transaction_data = await get_transaction_data()
        if not transaction_data:
            await retry_with_delay(lambda: generate_transaction(template))
            continue

        dash_address, transaction_id, date_time_str, amount = transaction_data

        if transaction_id not in previous_transaction_ids:
            previous_transaction_ids.add(transaction_id)
            date_time = datetime.strptime(date_time_str, '%Y-%m-%d %H:%M:%S')
            usd_amount, amd_amount, bot_amount = calculate_amounts(current_rate, amount)
            txid = transaction_id
            output = format_output(template, dash_address, amount, usd_amount, amd_amount, date_time, current_rate, txid)
            print(output)
            await send_transaction_messages(output)

        await trio.sleep(10)

template = """
-----------------------------------------------
To: {dash_address}
Amount: {amount:.8f} DASH ({usd_amount_str} / {amd_amount:.0f} AMD) 
Time: {date_time}
DASH rate: ${rate:.2f} (binance)
Sent by @BitcoinOperator
-----------------------------------------------
Transaction: https://blockchair.com/dash/transaction/{txid}
"""

async def send_transaction_messages(output):
    bot = Bot(token=bot_token)
    for chat_id in bot_chat_ids:
        try:
            chat_info = await bot.getChat(chat_id=chat_id)
            chat_username = chat_info.username
            if chat_username:
                print(f"Sending message to: @{chat_username}")
            else:
                print(f"Chat ID {chat_id} has no username.")
            await bot.send_message(chat_id=chat_id, text=output)
        except telegram_error.TimedOut:
            print(f"Timed out, retrying...")
            time.sleep(2)
            await bot.send_message(chat_id=chat_id, text=output)
        except telegram_error.BadRequest as e:
            print(f"BadRequest for chat ID {chat_id}: {e}")

    with OUTPUT_FILE.open("w") as output_file:
        output_file.write(output + "\n")

async def run_trio_loop():
    print("Generating transactions using the provided values...")
    async with trio.open_nursery() as nursery:
        nursery.start_soon(generate_transaction, template)

if __name__ == "__main__":
    trio.run(run_trio_loop)
