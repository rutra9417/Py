import asyncio
import aiohttp
import datetime
import ssl
from pathlib import Path

# Set up file paths
BASE_PATH = Path("/storage/emulated/0/top")
file_name = BASE_PATH / "transaction_values.txt"
address_file_path = BASE_PATH / "addresses.txt"
custom_ca_path = "/data/data/com.termux/files/usr/etc/tls/cert.pem"  # Adjust if using a different CA path in Termux

# Initialize the last processed transaction IDs as a global dictionary
last_txids = {}

# Define the interval for checking new transactions (in seconds)
check_interval = 0.1  # Check every 0.1 seconds


async def fetch_utxos(address):
    api_url = f"https://insight.dash.org/insight-api/addr/{address}/utxo"
    async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=ssl.create_default_context(cafile=custom_ca_path))) as session:
        async with session.get(api_url) as response:
            return await response.json()


async def fetch_transaction(txid):
    api_url = f"https://insight.dash.org/insight-api/tx/{txid}"
    async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=ssl.create_default_context(cafile=custom_ca_path))) as session:
        async with session.get(api_url) as response:
            return await response.json()


def process_utxo(utxo):
    return utxo["txid"]


def print_transaction_info(address, new_txid, received_value, sender_address, fee, total_inputs, total_outputs,
                           modified_time_str):
    print(f"Dash Address: {address}")
    print(f"Transaction ID: {new_txid}")
    print(f"Modified Time: {modified_time_str}")
    print(f"Received Value: {received_value:.8f} DASH")
    print(f"Sender Address: {sender_address}")
    print(f"Transaction Fee: {fee:.8f} DASH")
    print(f"Total Inputs: {total_inputs:.8f}")
    print(f"Total Outputs: {total_outputs:.8f}")


def write_transaction_info_to_file(file_path, address, new_txid, received_value, sender_address, fee, total_inputs,
                                   total_outputs, modified_time_str):
    with open(file_path, "w") as file:
        file.write(f"{address}\n")
        file.write(f"{new_txid}\n")
        file.write(f"{modified_time_str}\n")
        file.write(f"{received_value:.8f}\n")
        file.write(f"{sender_address}\n")
        file.write(f"{fee:.8f}\n")
        file.write(f"{total_inputs:.8f}\n")
        file.write(f"{total_outputs:.8f}\n")


async def fetch_and_process_transaction(address, last_txids, file_path, check_interval):
    try:
        utxos = await fetch_utxos(address)
        if not utxos:
            print(f"Waiting for transactions for address {address}...")
            await asyncio.sleep(check_interval)
            return last_txids

        latest_utxo = utxos[0]
        new_txid = process_utxo(latest_utxo)
        if new_txid == last_txids.get(address):
            print(f"Waiting for transactions for address {address}...")
            await asyncio.sleep(check_interval)
            return last_txids

        received_value = latest_utxo["satoshis"] / 1e8
        transaction_data = await fetch_transaction(new_txid)

        sender_address = transaction_data["vin"][0]["addr"]
        total_inputs = sum(float(vin["value"]) for vin in transaction_data["vin"])
        total_outputs = sum(float(vout["value"]) for vout in transaction_data["vout"])
        fee = total_inputs - total_outputs
        modified_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        print_transaction_info(address, new_txid, received_value, sender_address, fee, total_inputs, total_outputs,
                               modified_time)
        write_transaction_info_to_file(file_path, address, new_txid, received_value, sender_address, fee,
                                       total_inputs, total_outputs, modified_time)

        last_txids[address] = new_txid
        return last_txids
    except Exception as e:
        print(f"Error: {e}")
        await asyncio.sleep(check_interval)
        return last_txids


async def main():
    with open(address_file_path, "r") as address_file:
        addresses = address_file.read().splitlines()

    for address in addresses:
        last_txids[address] = None

    while True:
        for address in addresses:
            await fetch_and_process_transaction(address, last_txids, file_name, check_interval)


if __name__ == "__main__":
    asyncio.run(main())