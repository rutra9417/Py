import os
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.constants import MessageOriginType

BOT_TOKEN = '6455033711:AAHrCXCg1XRgqroEfyZKGUq5_QGqW1czo68'
ADDRESSES_FILE = 'addresses.txt'
CHAT_IDS_FILE = 'chat_ids.txt'
SHOPS_FILE = 'shops.txt'
DASH_ADDRESS_REGEX = r'X[1-9A-HJ-NP-Za-km-z]{33}'

def save_to_file(filename: str, data: str, check_duplicates: bool = True) -> None:
    try:
        if not os.path.exists(filename):
            with open(filename, 'w'): pass

        if check_duplicates:
            with open(filename, 'r') as f:
                if data in f.read():
                    return

        with open(filename, 'a') as f:
            f.write(data + '\n')
    except Exception as e:
        print(f"Ошибка записи в {filename}: {str(e)}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user = update.effective_user
        chat_id = update.effective_chat.id
        save_to_file(CHAT_IDS_FILE, str(chat_id))

        keyboard = [
            [InlineKeyboardButton("📋 Просмотреть адреса", callback_data='view_addresses')],
            [InlineKeyboardButton("➕ Добавить адрес вручную", callback_data='manual_input')],
            [InlineKeyboardButton("🛍️ Магазины", callback_data='view_shops')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Բարև 🙈 🙉 🙊\nհաշիվը forward արա ինդզ: 💰 💰 💰\nՈՒ հենց մի բան լինի կիմանաս ⏳️⏳️⏳ Առաջինը ՉՏԱՍ 🛑 🛑 🛑\n\nԴԵ ՔԵԶ ՏԵՆԱՄ ԲՐԱԴՐ 😎",
            reply_markup=reply_markup
        )
    except Exception as e:
        print(f"Ошибка в /start: {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        if not update.message or not update.message.text:
            return

        if context.user_data.get('awaiting_manual_input'):
            await handle_manual_input(update, context)
            return

        if 'edit_index' in context.user_data:
            await handle_edit_tag(update, context)
            return

        if 'edit_shop_index' in context.user_data:
            await handle_edit_shop(update, context)
            return

        if 'adding_shop' in context.user_data:
            await handle_add_shop(update, context)
            return

        user = update.effective_user
        chat_id = update.effective_chat.id
        text = update.message.text

        if not update.message.forward_origin:
            addresses = re.findall(DASH_ADDRESS_REGEX, text)
            if addresses:
                await process_addresses(update, context, addresses, f"#{user.username}" if user.username else "#manual_input")
                return
            await update.message.reply_text("⚠️ Пожалуйста, перешлите сообщение с адресом или просто отправьте адрес!")
            return

        origin = update.message.forward_origin
        username = "#forwarded_message"

        if origin.type == MessageOriginType.USER:
            sender = origin.sender_user
            username = f"#{sender.username}" if sender.username else "#unknown_username"
            save_to_file(SHOPS_FILE, username)

        addresses = re.findall(DASH_ADDRESS_REGEX, text)
        if not addresses:
            await update.message.reply_text("❌ В сообщении не найден Dash-адрес!")
            return

        await process_addresses(update, context, addresses, username)

    except Exception as e:
        print(f"Ошибка: {str(e)}")
        await update.message.reply_text("⚠️ Ошибка при обработке!")

async def process_addresses(update: Update, context: ContextTypes.DEFAULT_TYPE, addresses: list, username: str) -> None:
    chat_id = update.effective_chat.id
    save_to_file(CHAT_IDS_FILE, str(chat_id))

    for addr in addresses:
        save_to_file(ADDRESSES_FILE, f"{addr}\t{username}")

    keyboard = [
        [InlineKeyboardButton("📋 Просмотреть адреса", callback_data='view_addresses')],
        [InlineKeyboardButton("➕ Добавить адрес вручную", callback_data='manual_input')],
        [InlineKeyboardButton("🛍️ Магазины", callback_data='view_shops')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"✅ Сохранено адресов: {len(addresses)}\n📌 Источник: {username}\nПример: {addresses[0][:10]}...",
        reply_markup=reply_markup
    )

async def handle_edit_tag(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        index = context.user_data.pop('edit_index', None)
        new_tag = update.message.text.strip()

        if index is None or not new_tag:
            await update.message.reply_text("❌ Тег не может быть пустым!")
            return

        with open(ADDRESSES_FILE, 'r') as f:
            lines = f.readlines()

        if index < 0 or index >= len(lines):
            await update.message.reply_text("⚠️ Неверный ID")
            return

        parts = lines[index].strip().split('\t')
        lines[index] = f"{parts[0]}\t#{new_tag}\n"

        with open(ADDRESSES_FILE, 'w') as f:
            f.writelines(lines)

        await update.message.reply_text(f"✅ Тег обновлён: #{new_tag}")

    except Exception as e:
        print(f"Ошибка редактирования: {str(e)}")
        await update.message.reply_text("⚠️ Ошибка при обновлении тега")

async def delete_address(update: Update, context: ContextTypes.DEFAULT_TYPE, address_id: int) -> None:
    try:
        with open(ADDRESSES_FILE, 'r') as f:
            addresses = f.readlines()

        if address_id < 0 or address_id >= len(addresses):
            await update.callback_query.message.reply_text("⚠️ Неверный ID адреса!")
            return

        deleted_address = addresses.pop(address_id)

        with open(ADDRESSES_FILE, 'w') as f:
            f.writelines(addresses)

        await update.callback_query.message.reply_text(f"✅ Адрес удалён:\n{deleted_address.strip()}")
    except Exception as e:
        print(f"Ошибка при удалении адреса: {str(e)}")
        await update.callback_query.message.reply_text("⚠️ Ошибка при удалении адреса!")

async def view_addresses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        if not os.path.exists(ADDRESSES_FILE):
            await update.callback_query.message.reply_text("📭 Список адресов пуст!")
            return

        with open(ADDRESSES_FILE, 'r') as f:
            addresses = f.readlines()

        if not addresses:
            await update.callback_query.message.reply_text("📭 Список адресов пуст!")
            return

        keyboard = []
        for idx, line in enumerate(addresses[:50]):
            parts = line.strip().split('\t')
            address = parts[0]
            info = parts[1] if len(parts) > 1 else ""
            display_text = f"{address} ({info})" if info else address
            keyboard.append([InlineKeyboardButton(display_text, callback_data='noop')])
            keyboard.append([
                InlineKeyboardButton("❌ Удалить", callback_data=f'delete_{idx}'),
                InlineKeyboardButton("✏️ Изменить тег", callback_data=f'edit_{idx}')
            ])

        keyboard.append([
            InlineKeyboardButton("➕ Добавить адрес", callback_data='manual_input'),
            InlineKeyboardButton("🔙 Назад", callback_data='start')
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.reply_text(
            f"📋 Всего адресов: {len(addresses)}\nВыберите адрес для управления:",
            reply_markup=reply_markup
        )
    except Exception as e:
        print(f"Ошибка при просмотре адресов: {str(e)}")
        await update.callback_query.message.reply_text("⚠️ Ошибка при загрузке адресов!")

async def view_shops(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        if not os.path.exists(SHOPS_FILE):
            open(SHOPS_FILE, 'w').close()

        with open(SHOPS_FILE, 'r') as f:
            shops = f.readlines()

        keyboard = []
        for idx, line in enumerate(shops[:50]):
            shop = line.strip()
            keyboard.append([InlineKeyboardButton(f"🛒 {shop}", callback_data='noop')])
            keyboard.append([
                InlineKeyboardButton("✏️ Изменить", callback_data=f'editshop_{idx}'),
                InlineKeyboardButton("❌ Удалить", callback_data=f'deleteshop_{idx}')
            ])

        keyboard.append([
            InlineKeyboardButton("➕ Добавить магазин", callback_data='add_shop'),
            InlineKeyboardButton("🔙 Назад", callback_data='start')
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.reply_text(
            f"🛍️ Всего магазинов: {len(shops)}",
            reply_markup=reply_markup
        )
    except Exception as e:
        print(f"Ошибка при просмотре магазинов: {str(e)}")
        await update.callback_query.message.reply_text("⚠️ Ошибка при загрузке магазинов!")

async def handle_edit_shop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        index = context.user_data.pop('edit_shop_index', None)
        new_shop = update.message.text.strip()

        if index is None or not new_shop:
            await update.message.reply_text("❌ Название магазина не может быть пустым!")
            return

        with open(SHOPS_FILE, 'r') as f:
            lines = f.readlines()

        if index < 0 or index >= len(lines):
            await update.message.reply_text("⚠️ Неверный ID")
            return

        lines[index] = f"{new_shop}\n"

        with open(SHOPS_FILE, 'w') as f:
            f.writelines(lines)

        await update.message.reply_text(f"✅ Название магазина обновлено: {new_shop}")
    except Exception as e:
        print(f"Ошибка редактирования магазина: {str(e)}")
        await update.message.reply_text("⚠️ Ошибка при обновлении магазина")

async def handle_add_shop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        new_shop = update.message.text.strip()
        if not new_shop:
            await update.message.reply_text("❌ Название магазина не может быть пустым!")
            return

        save_to_file(SHOPS_FILE, new_shop)
        context.user_data.pop('adding_shop', None)
        await update.message.reply_text(f"✅ Добавлен магазин: {new_shop}")
    except Exception as e:
        print(f"Ошибка при добавлении магазина: {str(e)}")
        await update.message.reply_text("⚠️ Ошибка при добавлении магазина!")

async def delete_shop(update: Update, context: ContextTypes.DEFAULT_TYPE, shop_index: int) -> None:
    try:
        with open(SHOPS_FILE, 'r') as f:
            shops = f.readlines()

        if shop_index < 0 or shop_index >= len(shops):
            await update.callback_query.message.reply_text("⚠️ Неверный ID магазина!")
            return

        deleted = shops.pop(shop_index)

        with open(SHOPS_FILE, 'w') as f:
            f.writelines(shops)

        await update.callback_query.message.reply_text(f"🗑️ Удалён магазин: {deleted.strip()}")
    except Exception as e:
        print(f"Ошибка удаления магазина: {str(e)}")
        await update.callback_query.message.reply_text("⚠️ Ошибка при удалении!")

async def start_manual_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data['awaiting_manual_input'] = True
    await update.callback_query.message.reply_text(
        "✍️ Пожалуйста, отправьте Dash-адрес вручную:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отменить", callback_data='cancel_manual_input')]])
    )

async def handle_manual_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        text = update.message.text
        addresses = re.findall(DASH_ADDRESS_REGEX, text)

        if not addresses:
            await update.message.reply_text("❌ Адрес не найден! Повторите попытку.")
            return

        user = update.effective_user
        username = f"#{user.username}" if user.username else "#manual_input"

        for addr in addresses:
            save_to_file(ADDRESSES_FILE, f"{addr}\t{username}")

        context.user_data.pop('awaiting_manual_input', None)

        await update.message.reply_text(f"✅ Добавлено {len(addresses)} адресов вручную.")
    except Exception as e:
        print(f"Ошибка ручного ввода: {str(e)}")
        await update.message.reply_text("⚠️ Ошибка при обработке ручного ввода!")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == 'view_addresses':
        await view_addresses(update, context)
    elif query.data == 'view_shops':
        await view_shops(update, context)
    elif query.data.startswith('delete_'):
        index = int(query.data.split('_')[1])
        await delete_address(update, context, index)
    elif query.data.startswith('edit_'):
        index = int(query.data.split('_')[1])
        context.user_data['edit_index'] = index
        await query.message.reply_text("✏️ Введите новый тег:")
    elif query.data.startswith('editshop_'):
        index = int(query.data.split('_')[1])
        context.user_data['edit_shop_index'] = index
        await query.message.reply_text("✏️ Введите новое имя магазина:")
    elif query.data.startswith('deleteshop_'):
        index = int(query.data.split('_')[1])
        await delete_shop(update, context, index)
    elif query.data == 'add_shop':
        context.user_data['adding_shop'] = True
        await query.message.reply_text("➕ Введите имя нового магазина:")
    elif query.data == 'manual_input':
        await start_manual_input(update, context)
    elif query.data == 'cancel_manual_input':
        context.user_data.pop('awaiting_manual_input', None)
        await query.message.reply_text("❌ Ввод отменён.")
        await start(update, context)

def main() -> None:
    try:
        app = Application.builder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(CallbackQueryHandler(button_callback))
        print("Бот запущен...")
        app.run_polling()
    except Exception as e:
        print(f"FATAL ERROR: {str(e)}")

if __name__ == '__main__':
    main()
