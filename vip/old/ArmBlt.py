import trio
from datetime import datetime
from telegram import Bot
import textwrap
import warnings
import random
from pathlib import Path

# Ignore runtime warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, module="trio")

# Base directory for files
BASE_DIR = Path("/storage/emulated/0/top")

# Read chat IDs from the file
chat_ids_file = BASE_DIR / "chat_ids.txt"
with open(chat_ids_file, "r") as file:
    bot_chat_ids = [int(line.strip()) for line in file if line.strip()]

# Read the rate from usdt.txt file (extract only numeric part)
try:
    with open(BASE_DIR / "usdt.txt", "r") as rate_file:
        first_line = rate_file.readline().strip()
        rate_str = first_line.split()[0]  # Take only the first part before space
        rate = float(rate_str)
except (FileNotFoundError, ValueError):
    rate = 26  # Default rate if file not found or conversion fails

bot_token = "6067244950:AAGbAHcyAPWjtsJHMOmvY1Uf6wfaW4KJo5w"
rateamd = 413.0

# Read transaction_no from the file
try:
    with open(BASE_DIR / "transaction_no.txt", "r") as file:
        transaction_no = int(file.read().strip())
except FileNotFoundError:
    transaction_no = 263842

async def get_transaction_data():
    values_file = BASE_DIR / "transaction_values.txt"
    with open(values_file, "r") as file:
        lines = file.readlines()
        if len(lines) >= 4:
            dash_address = lines[0].strip()
            transaction_id = lines[1].strip()
            date_time_str = lines[2].strip()
            amount = float(lines[3].strip())
            return dash_address, transaction_id, date_time_str, amount
    return None

def calculate_amounts(rate, amount):
    usd_amount = round(rate * amount, 2)
    amd_amount = round(amount * rate * rateamd / 100) * 100
    bot_amount = amd_amount + 1500
    return usd_amount, amd_amount, bot_amount

def format_output(template, dash_address, amount, usd_amount, amd_amount, date_time, transaction_id, transaction_counter):
    return template.format(
        dash_address=dash_address,
        amount=amount,
        usd_amount=usd_amount,
        amd_amount=amd_amount,
        date=date_time.strftime('%Y-%m-%d'),
        time=date_time.strftime('%H:%M:%S'),
        transaction_id=transaction_id,
        transaction_no=transaction_counter
    )

async def retry_with_delay(func, delay=60):
    while True:
        try:
            await func()
            return
        except Exception as e:
            print("Error occurred during transaction generation:", e)
            await trio.sleep(delay)

previous_transaction_ids = set()

async def generate_transaction(template):
    while True:
        current_rate = rate
        if current_rate is None:
            await trio.sleep(120)
            continue
        transaction_data = await get_transaction_data()
        if transaction_data is None:
            await trio.sleep(120)
            continue

        dash_address, transaction_id, date_time_str, amount = transaction_data

        if transaction_id not in previous_transaction_ids:
            previous_transaction_ids.add(transaction_id)
            date_time = datetime.strptime(date_time_str, '%Y-%m-%d %H:%M:%S')
            usd_amount, amd_amount, bot_amount = calculate_amounts(current_rate, amount)
            transaction_counter = random.randint(100000, 999999)
            output = format_output(template, dash_address, amount, usd_amount, amd_amount, date_time, transaction_id, transaction_counter)
            print(output)

            bot = Bot(token=bot_token)
            for chat_id in bot_chat_ids[:]:  # copy to safely remove inside loop
                try:
                    await bot.send_message(chat_id=chat_id, text=output)
                except Exception as e:
                    print(f"Error sending message to {chat_id}: {e}")
                    bot_chat_ids.remove(chat_id)

        await trio.sleep(2)

async def run_trio_loop():
    print("Generating transactions using the provided values...")
    print("Template 1:")
    template1 = textwrap.dedent("""
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

    async with trio.open_nursery() as nursery:
        nursery.start_soon(generate_transaction, template1)

if __name__ == "__main__":
    trio.run(run_trio_loop)