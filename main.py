# -*- coding: utf-8 -*-
"""
main.py — Telegram бот на PTB v20+ с клавиатурой для ввода суммы DASH/AMD
Автозапуск и логирование ошибок
"""

import os
import asyncio
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# --- Настройки ---
BOT_TOKEN = "6455033711:AAHrCXCg1XRgqroEfyZKGUq5_QGqW1czo68"  # <- замени на свой токен
LOG_DIR = os.path.expanduser("~/vip/logs")
os.makedirs(LOG_DIR, exist_ok=True)

# --- Логи ---
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "exchange.log"),
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Стейт бота ---
user_currency_amount = {}
user_choices = {}

# --- Клавиатура для ввода суммы ---
def show_amount_input_keyboard(current="0"):
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("C", callback_data="clear"), InlineKeyboardButton("⬅️", callback_data="del")],
        [InlineKeyboardButton("1", callback_data="1"), InlineKeyboardButton("2", callback_data="2"), InlineKeyboardButton("3", callback_data="3")],
        [InlineKeyboardButton("4", callback_data="4"), InlineKeyboardButton("5", callback_data="5"), InlineKeyboardButton("6", callback_data="6")],
        [InlineKeyboardButton("7", callback_data="7"), InlineKeyboardButton("8", callback_data="8"), InlineKeyboardButton("9", callback_data="9")],
        [InlineKeyboardButton(".", callback_data="."), InlineKeyboardButton("0", callback_data="0"), InlineKeyboardButton("✅", callback_data="done")],
    ])
    return markup

# --- Обработчик кнопок ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cid = query.message.chat_id

    if cid not in user_currency_amount:
        user_currency_amount[cid] = {"amount": "", "currency": "DASH"}

    entry = user_currency_amount[cid]
    data = query.data

    if data == "clear":
        entry["amount"] = ""
    elif data == "del":
        entry["amount"] = entry["amount"][:-1]
    elif data == "done":
        if entry["amount"]:
            action = "Buy" if user_choices.get(cid, "").startswith("buy_") else "Sell"
            currency = entry["currency"].upper()
            await query.message.reply_text(f"{action} {entry['amount']} {currency}")
            user_choices.pop(cid, None)
            user_currency_amount.pop(cid, None)
        return
    else:
        entry["amount"] = (entry["amount"] + data)[:32]

    # Обновляем клавиатуру
    await query.message.edit_text(
        f"Որքա՞ն AMD-ի համարժեք DASH եք ցանկանում գնելը՝\nԳումար: {entry['amount'] if entry['amount'] else '0'}",
        reply_markup=show_amount_input_keyboard(entry["amount"])
    )

# --- Старт команды ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.message.chat_id
    await update.message.reply_text(
        "Բարև 🙈 Որքա՞ն DASH/AMD ուզում եք փոխանակել:",
        reply_markup=show_amount_input_keyboard("0")
    )

# --- Основной запуск ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), start))  # все текстовые сообщения → старт

    # Запуск
    logger.info("Бот запущен...")
    try:
        app.run_polling()
    except Exception as e:
        logger.exception("FATAL ERROR: ")
        # Автоперезапуск через asyncio
        import time
        time.sleep(5)
        main()

if __name__ == "__main__":
    main()