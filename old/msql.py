from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# Your Telegram bot token
bot_token = '5404550008:AAFj-yg29UYxgsJ-tUWCGG4jIj2x7-tFgSI'

# Initialize the Telegram bot
bot = Bot(token=bot_token)

# Define a set to store unique chat IDs
chat_ids = set()

# Define a function to handle the /start command
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Send me your Dash address, and I will save it.')

# Define a function to handle text messages
def save_dash_address(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id

    # Check if the chat ID is not already in the set
    if user_id not in chat_ids:
        # Save the chat ID to the set and the file
        chat_ids.add(user_id)
        with open('chat_ids.txt', 'a') as file:
            file.write(f'{user_id}\n')

    dash_address = update.message.text

    # Save the Dash address to a file
    with open('addresses.txt', 'a') as file:
        file.write(f'{dash_address}\n')

    update.message.reply_text('Dash address and Chat ID saved!')

# Create an Updater and attach the command and message handlers
updater = Updater(token=bot_token, use_context=True)
dispatcher = updater.dispatcher

# Add command handler for /start
dispatcher.add_handler(CommandHandler('start', start))

# Add a message handler for text messages
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, save_dash_address))

# Start the bot
updater.start_polling()
updater.idle()
