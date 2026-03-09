import asyncio
import aiohttp
import datetime
import ssl

custom_ca_path = "/usr/local/etc/openssl@1.1/cert.pem"

# Replace with your Dash address
address = "XuCV7JRX1Bc4kAo9aKa9o18Lkf2TfTtoCr"

# Initialize the last processed transaction ID as None
last_txid = None

# Define the filename for the text file
file_name = "template/transaction_values.txt"

# Define the interval for checking new transactions (in seconds)
check_interval = 0.001  # Check every 0.1 seconds


async def fetch_utxos(address):
    api_url = f"https://insight.dash.org/insight-api/addr/{address}/utxo"
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl.create_default_context(cafile=custom_ca_path))) as session:
        async with session.get(api_url) as response:
            return await response.json()


async def fetch_transaction(txid):
    api_url = f"https://insight.dash.org/insight-api/tx/{txid}"
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl.create_default_context(cafile=custom_ca_path))) as session:
        async with session.get(api_url) as response:
            return await response.json()


def process_utxo(utxo):
    new_txid = utxo["txid"]
    return new_txid


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


def write_transaction_info_to_file(file_name, address, new_txid, received_value, sender_address, fee, total_inputs,
                                   total_outputs, modified_time_str):
    with open(file_name, "w") as file:  # Use "w" mode to overwrite the file
        file.write(f"{address}\n")
        file.write(f"{new_txid}\n")
        file.write(f"{modified_time_str}\n")
        file.write(f"{received_value:.8f}\n")
        file.write(f"{sender_address}\n")
        file.write(f"{fee:.8f}\n")
        file.write(f"{total_inputs:.8f}\n")
        file.write(f"{total_outputs:.8f}\n")


async def fetch_and_process_transaction(address, last_txid, file_name, check_interval):
    try:
        utxos = await fetch_utxos(address)
        if len(utxos) == 0:
            print("Waiting for transactions...")
            await asyncio.sleep(check_interval)
            return last_txid

        latest_utxo = utxos[0]
        new_txid = process_utxo(latest_utxo)
        if new_txid == last_txid:
            print("Waiting...")
            await asyncio.sleep(check_interval)
            return last_txid

        received_value = latest_utxo["satoshis"] / 1e8
        transaction_data = await fetch_transaction(new_txid)

        sender_address = transaction_data["vin"][0]["addr"]

        total_inputs = sum(float(input_tx["value"]) for input_tx in transaction_data["vin"])
        total_outputs = sum(float(output_tx["value"]) for output_tx in transaction_data["vout"])
        fee = (total_inputs - total_outputs)
        modified_time = datetime.datetime.now()
        modified_time_str = modified_time.strftime('%Y-%m-%d %H:%M:%S')

        print_transaction_info(
            address, new_txid, received_value, sender_address, fee, total_inputs, total_outputs,
            modified_time_str)
        write_transaction_info_to_file(
            file_name, address, new_txid, received_value, sender_address, fee, total_inputs,
            total_outputs, modified_time_str)

        return new_txid
    except Exception as e:
        print(f"Error: {e}")
        await asyncio.sleep(check_interval)
        return last_txid


async def main():
    global last_txid
    while True:
        last_txid = await fetch_and_process_transaction(address, last_txid, file_name, check_interval)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
