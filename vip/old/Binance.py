import aiohttp
import aiofiles
import asyncio
import time
import ssl
from pathlib import Path

# Constants
OUTPUT_FILE = Path('/storage/emulated/0/top/usdt.txt')
FETCH_INTERVAL = 1  # seconds
MAX_LINES = 1

# SSL context setup (system certs usually work in Termux)
ssl_context = ssl.create_default_context()

# Get formatted current time
def get_formatted_time() -> str:
    return time.strftime('%H:%M:%S', time.localtime())

# Fetch DASH/USDT price from Binance
async def get_dashusdt_price(session: aiohttp.ClientSession) -> str | None:
    url = 'https://api.binance.com/api/v3/ticker/price?symbol=DASHUSDT'
    try:
        async with session.get(url, ssl=ssl_context, timeout=10) as response:
            response.raise_for_status()
            data = await response.json()
            return data.get('price')
    except Exception as e:
        print(f"[{get_formatted_time()}] Request error: {e}")
        return None

# Save last N prices to file
async def save_price(price: str, filename: Path, max_lines: int = MAX_LINES):
    try:
        # Ensure output directory exists
        filename.parent.mkdir(parents=True, exist_ok=True)

        lines = []
        if filename.exists():
            async with aiofiles.open(filename, 'r') as file:
                lines = await file.readlines()

        timestamp = get_formatted_time()
        lines.append(f"{price} {timestamp}\n")
        lines = lines[-max_lines:]

        async with aiofiles.open(filename, 'w') as file:
            await file.writelines(lines)

        print(f"Saved: {price} at {timestamp}")
    except Exception as e:
        print(f"File error: {e}")

# Main loop
async def main():
    async with aiohttp.ClientSession() as session:
        while True:
            price = await get_dashusdt_price(session)
            if price:
                await save_price(price, OUTPUT_FILE)
            await asyncio.sleep(FETCH_INTERVAL)

# Run
if __name__ == "__main__":
    asyncio.run(main())