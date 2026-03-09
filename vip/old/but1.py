import telebot
from telebot import types

# Create a bot instance with the specified token
bot = telebot.TeleBot('6067244950:AAGbAHcyAPWjtsJHMOmvY1Uf6wfaW4KJo5w')

# Dictionary to store user choices (buy or sell) for each user
user_choices = {}

# Dictionary to store the user's currency choice along with the amount they want to buy or sell
user_currency_amount = {}

# Handle the '/start' command
@bot.message_handler(commands=['start'])
def send_start_message(message):
    # Create inline keyboard markup with two buttons in each row
    markup = types.InlineKeyboardMarkup()

    # Add the first row of buttons
    row1_buttons = [
        types.InlineKeyboardButton('Գնել BTC', callback_data='buy_btc'),
        types.InlineKeyboardButton('Վաճառել BTC', callback_data='sell_btc')
    ]
    markup.row(*row1_buttons)

    # Add the second row of buttons
    row2_buttons = [
        types.InlineKeyboardButton('Գնել DASH', callback_data='buy_dash'),
        types.InlineKeyboardButton('Վաճառել DASH', callback_data='sell_dash')
    ]
    markup.row(*row2_buttons)

    # Add the third row of buttons
    row3_buttons = [
        types.InlineKeyboardButton('Գնել LTC', callback_data='buy_ltc'),
        types.InlineKeyboardButton('Վաճառել LTC', callback_data='sell_ltc')
    ]
    markup.row(*row3_buttons)

    # Add the fourth row of buttons
    row4_buttons = [
        types.InlineKeyboardButton('Գնել USD-TRC20', callback_data='buy_usd'),
        types.InlineKeyboardButton('Վաճառել USDT', callback_data='sell_usd')
    ]
    markup.row(*row4_buttons)

    # Send the inline keyboard markup
    bot.send_message(message.chat.id, '👨‍🚀 Ես ձեզ կօգնեմ գնել կամ վաճառել Bitcoin և Dash 💵', reply_markup=markup)

# Handle the callback data from inline buttons
@bot.callback_query_handler(func=lambda call: True)
def handle_inline_buttons(call):
    if call.message:
        if call.data.startswith(('buy_', 'sell_')):
            # Save the user's choice (buy or sell) for later use
            user_choices[call.message.chat.id] = call.data

            # Create a new inline keyboard markup for currency