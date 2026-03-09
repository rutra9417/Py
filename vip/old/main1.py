import asyncio
import aiohttp
import datetime
import ssl

custom_ca_path = "/usr/local/etc/openssl@1.1/cert.pem"

# Initialize the last processed transaction IDs as a global dictionary
last_txids = {}

# Define the filename for the text file
file_name = "/Users/artur/PycharmProjects/verjinoper/src/template/transaction_values.txt"

# Define the interval for checking new transactions (in seconds)
check_interval = 0.1  # Check every 0.1 seconds

async def fetch_utxos(address):
    # ... (rest of the code remains the same)

async def fetch_and_process_transaction(address, last_txids, file_name, check_interval):
    try:
        utxos = await fetch_utxos(address)
        if len(utxos) == 0:
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

        total_inputs = sum(float(input_tx["value"]) for input_tx in transaction_data["vin"])
        total_outputs = sum(float(output_tx["value"]) for output_tx in transaction_data["vout"])
        fee = (total_inputs - total_outputs)
        modified_time = datetime.datetime.now()
        modified_time_str = modified_time.strftime('%Y-%m-%d %H:%M:%S')

        print_transaction_info(address, new_txid, received_value, sender_address, fee, total_inputs, total_outputs, modified_time_str)
        write_transaction_info_to_file(file_name, address, new_txid, received_value, sender_address, fee, total_inputs, total_outputs, modified_time_str)

        last_txids[address] = new_txid
        return last_txids
    except Exception as e:
        print(f"Error: {e}")
        await asyncio.sleep(check_interval)
        return last_txids

async def main():
    with open("/Users/artur/PycharmProjects/verjinoper/src/template/addresses.txt", "r") as address_file:
        addresses = address_file.read().splitlines()

    for address in addresses:
        last_txids[address] = None

    while True:
        for address in addresses:
            last_txids = await fetch_and_process_transaction(address, last_txids, file_name, check_interval)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
