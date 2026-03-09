# swopex_login.py — Linux-ready
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from pathlib import Path
import asyncio

API_ID = 36812196
API_HASH = "766d43afec2b43e81075277bfa85b066"
SESSION_NAME = Path.home() / "vip" / "swopex_user.session"

async def main():
    client = TelegramClient(str(SESSION_NAME), API_ID, API_HASH)
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
        print("[login] ✅ Готово. Сессия swopex_user.session сохранена в ~/vip/")
    else:
        print("[login] ❌ Авторизация не выполнена.")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
