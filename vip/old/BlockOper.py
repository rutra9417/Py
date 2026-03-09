from telegram import Bot, error as telegram_error

# Your bot token
bot_token = "6494531155:AAHKtOppKtO3OR9-7UKc0dae_3ZzcYoIbgo"

# File path for chat IDs
chat_ids_file = "src/template/chat_ids.txt"  # Replace with the actual file path

# ANSI color codes for red and reset
RED = "\033[91m"
RESET = "\033[0m"

async def check_chat_ids():
    bot = Bot(token=bot_token)

    with open(chat_ids_file, "r") as file:
        for line in file:
            chat_id = line.strip()
            try:
                chat_info = await bot.getChat(chat_id=chat_id)
                chat_username = chat_info.username

                if chat_username:
                    print(f"Chat ID {chat_id} (username: @{chat_username}) has not blocked the bot.")
                else:
                    print(f"Chat ID {chat_id} has not blocked the bot (no username).")
            except telegram_error.Forbidden:
                print(f"{RED}Chat ID {chat_id} has blocked the bot.{RESET}")
            except Exception as e:
                print(f"Error when checking chat ID {chat_id}: {e}")

if __name__ == "__main__":
    import trio
    trio.run(check_chat_ids)
