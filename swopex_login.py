# swopex_login.py
# Одноразовая авторизация Telethon, создаёт swopex_user.session рядом с файлом.
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

API_ID = 36812196
API_HASH = "766d43afec2b43e81075277bfa85b066"
SESSION_NAME = "swopex_user"

async def main():
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.connect()

    if await client.is_user_authorized():
        print("[login] Уже авторизовано. Сессия существует.")
        await client.disconnect()
        return

    phone = input("Введите номер телефона в международном формате (+374…): ").strip()
    print("[login] Отправляю код…")
    await client.send_code_request(phone)

    code = input("Введите код из Telegram (без пробелов): ").strip()

    try:
        await client.sign_in(phone=phone, code=code)
    except SessionPasswordNeededError:
        pwd = input("Включена 2FA. Введите пароль: ").strip()
        await client.sign_in(password=pwd)

    if await client.is_user_authorized():
        print("[login] ✅ Готово. Сессия swopex_user.session сохранена.")
    else:
        print("[login] ❌ Авторизация не выполнена.")

    await client.disconnect()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
