from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# Токен для бота-помощника
helper_bot_token = "6441930605:AAGOSKFRQgqJZl3C6Dtic5mJbar3l6hDjkE"

# Токен для основного бота
main_bot_token = "6494531155:AAHKtOppKtO3OR9-7UKc0dae_3ZzcYoIbgo"

# Создайте объекты Updater для ботов
helper_updater = Updater(token=helper_bot_token, use_context=True)
main_updater = Updater(token=main_bot_token, use_context=True)

# Обработчик команды /go
def go(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    # Сохраните user_id в базу данных или файл
    # В этом примере, мы просто выведем его на экран
    print(f"New subscriber with user_id: {user_id}")
    update.message.reply_text("Вы успешно подписались на бота!")

# Добавьте обработчик команды /go
helper_updater.dispatcher.add_handler(CommandHandler("go", go))

# Запустите бота-помощника
helper_updater.start_polling()
helper_updater.idle()
