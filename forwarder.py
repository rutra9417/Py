#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import asyncio
import logging
from typing import List, Dict

from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, ChatWriteForbiddenError, UserIsBlockedError
from telethon.utils import get_display_name

# ---------- .env (опционально) ----------
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ---------- Конфиг из окружения ----------
API_ID = 36812196
API_HASH = "766d43afec2b43e81075277bfa85b066"

# Используем отдельную сессию именно для forwarder
SESSION_NAME = (
    os.getenv("FORWARDER_SESSION_NAME")
    or os.getenv("SESSION_NAME_FORWARDER")
    or "forwarder_userbot"
)

# Для явной авторизации:
PHONE = (os.getenv("PHONE") or os.getenv("TG_PHONE") or "").strip()
BOT_TOKEN = (os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()

# Источник сообщений: @username или числовой ID
SOURCE = (os.getenv("SOURCE_BOT") or os.getenv("SOURCE") or "").strip()

# Список получателей
_targets_raw = os.getenv("TARGETS", "")
TARGETS: List[str] = [t.strip() for t in re.split(r"[,\s;]+", _targets_raw) if t.strip()]

# Режим: copy | forward
MODE = (os.getenv("MODE", "copy") or "copy").strip().lower()

# Уровень логов
LOG_LEVEL = (os.getenv("LOG_LEVEL", "INFO") or "INFO").upper()

# ---------- Логирование ----------
logging.basicConfig(
    format="%(asctime)s,%(msecs)03d | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=getattr(logging, LOG_LEVEL, logging.INFO),
)
log = logging.getLogger("forwarder")


# ---------- Утилиты ----------
def is_numeric_id(s: str) -> bool:
    s = s.strip()
    if s.startswith("-"):
        return s[1:].isdigit()
    return s.isdigit()


def normalize_token(token: str) -> str:
    token = token.strip()
    if token.startswith("https://t.me/"):
        token = token.replace("https://t.me/", "", 1)
    elif token.startswith("http://t.me/"):
        token = token.replace("http://t.me/", "", 1)
    elif token.startswith("t.me/"):
        token = token.split("/", 1)[-1]
    if token.startswith("@"):
        token = token[1:]
    return token.strip()


async def resolve_entity_safe(client: TelegramClient, token: str):
    """
    Пытаемся получить сущность:
      - username
      - числовой ID (если Telegram уже знает этот объект)
    Возвращает (entity, err|None).
    """
    try:
        if is_numeric_id(token):
            ent = await client.get_entity(int(token))
            return ent, None
        ent = await client.get_entity(token)
        return ent, None
    except Exception as e:
        return None, str(e)


async def warmup_dialogs(client: TelegramClient):
    """
    Прогрев кэша диалогов.
    Делать только для user-сессии.
    """
    async for _ in client.iter_dialogs(limit=100):
        pass
    log.info("Warmup: диалоги подгружены.")


async def send_copy_text(ev: events.NewMessage.Event, resolved: Dict[str, object]):
    msg = ev.message
    text = msg.message or ""
    if not text:
        return

    for label, dst in list(resolved.items()):
        try:
            await ev.client.send_message(
                dst,
                text,
                link_preview=True,
            )
            log.info("COPY -> %s | ok", label)
        except FloodWaitError as e:
            log.warning("COPY -> %s | FloodWait %ss", label, e.seconds)
            await asyncio.sleep(e.seconds + 1)
        except (ChatWriteForbiddenError, UserIsBlockedError) as e:
            log.error("COPY -> %s | forbidden/blocked: %s", label, e)
        except Exception as e:
            log.exception("COPY -> %s | error: %s", label, e)


async def forward_full_message(ev: events.NewMessage.Event, resolved: Dict[str, object]):
    for label, dst in list(resolved.items()):
        try:
            await ev.client.forward_messages(dst, ev.message)
            log.info("FORWARD -> %s | ok", label)
        except FloodWaitError as e:
            log.warning("FORWARD -> %s | FloodWait %ss", label, e.seconds)
            await asyncio.sleep(e.seconds + 1)
        except (ChatWriteForbiddenError, UserIsBlockedError) as e:
            log.error("FORWARD -> %s | forbidden/blocked: %s", label, e)
        except Exception as e:
            log.exception("FORWARD -> %s | error: %s", label, e)


# ---------- Основная логика ----------
async def main():
    if not API_ID or not API_HASH:
        log.error("API_ID/API_HASH не заданы. Проверь .env")
        return

    if not SOURCE:
        log.error("SOURCE_BOT/SOURCE не задан. Укажи @username или числовой ID источника в .env")
        return

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    log.info("Starting forwarder…")
    log.info("SESSION_NAME=%s", SESSION_NAME)

    await client.connect()

    if not await client.is_user_authorized():
        log.info("Session is not authorized yet.")

        if BOT_TOKEN:
            log.info("Authorizing as BOT via BOT_TOKEN...")
            await client.start(bot_token=BOT_TOKEN)
        elif PHONE:
            log.info("Authorizing as USER via PHONE...")
            await client.start(phone=PHONE)
        else:
            log.info("Interactive authorization...")
            await client.start()

    me = await client.get_me()
    is_bot = bool(getattr(me, "bot", False))
    who = getattr(me, "username", None) or getattr(me, "id", "unknown")

    log.info("Authorized as %s | bot=%s", who, is_bot)

    # Прогрев только для user-сессии
    if not is_bot:
        await warmup_dialogs(client)
    else:
        log.info("Bot session detected: warmup_dialogs skipped.")

    # Разрешаем источник
    src_token = normalize_token(SOURCE)
    src_entity, err = await resolve_entity_safe(client, src_token)
    if not src_entity:
        log.error("Источник не найден '%s': %s", SOURCE, err)
        return

    # Разрешаем цели
    resolved: Dict[str, object] = {}
    pending: List[str] = []

    for raw in TARGETS:
        tok = normalize_token(raw)
        ent, e = await resolve_entity_safe(client, tok)
        if ent:
            resolved[raw] = ent
        else:
            pending.append(raw)
            log.error("Failed to resolve '%s': %s", raw, e)

    if not resolved:
        log.error("Не удалось разрешить ни одной цели из TARGETS. Forwarder не сможет отправлять сообщения.")
    else:
        log.info(
            "MODE=%s | SOURCE=%s | TARGETS_OK=%s",
            MODE,
            getattr(src_entity, "id", src_token),
            list(resolved.keys()),
        )

    if pending:
        log.warning("Pending (нет диалога/контакта или закрыт доступ): %s", pending)
        log.warning("Подсказка: используй @username или сначала открой чат с этим аккаунтом/ботом.")

    @client.on(events.NewMessage(from_users=src_entity))
    async def handler(ev: events.NewMessage.Event):
        try:
            if MODE == "copy":
                await send_copy_text(ev, resolved)
            else:
                await forward_full_message(ev, resolved)

        except Exception as e:
            log.exception("Handler error: %s", e)

    log.info("Forwarder is running…")
    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Stopped by user.")
