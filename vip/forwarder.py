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
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
# Приоритет: переменная процесса SESSION_NAME (например, из батника) -> .env -> дефолт
SESSION_NAME = os.getenv("SESSION_NAME", os.getenv("SESSION_NAME_FORWARDER", "exchange_forwarder"))

# Источник сообщений: @username или числовой ID (обязательно)
SOURCE = (os.getenv("SOURCE_BOT") or os.getenv("SOURCE") or "").strip()

# Список получателей. Разделители: запятая/точка с запятой/пробел/перевод строки.
_targets_raw = os.getenv("TARGETS", "")
TARGETS: List[str] = [t.strip() for t in re.split(r"[,\s;]+", _targets_raw) if t.strip()]

# Режим: copy (копируем только текст) или forward (пересылаем сообщение целиком)
MODE = (os.getenv("MODE", "copy") or "copy").strip().lower()

# Уровень логов
LOG_LEVEL = (os.getenv("LOG_LEVEL", "INFO") or "INFO").upper()

# ---------- Логирование ----------
# В strftime нет %f — используем %(msecs)03d для миллисекунд
logging.basicConfig(
    format="%(asctime)s,%(msecs)03d | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=getattr(logging, LOG_LEVEL, logging.INFO),
)
log = logging.getLogger("forwarder")

# ---------- Утилиты ----------
def is_numeric_id(s: str) -> bool:
    return s.isdigit()

def normalize_token(token: str) -> str:
    token = token.strip()
    if token.startswith("t.me/"):
        token = token.split("/", 1)[-1]
    if token.startswith("@"):
        token = token[1:]
    return token

async def resolve_entity_safe(client: TelegramClient, token: str):
    """
    Пытаемся получить сущность:
      - username (строка) — работает всегда, если username существует
      - числовой id — сработает только если уже есть диалог/контакт
    Возвращает (entity, err|None).
    """
    try:
        if is_numeric_id(token):
            ent = await client.get_entity(int(token))
            return ent, None
        else:
            ent = await client.get_entity(token)
            return ent, None
    except Exception as e:
        return None, str(e)

async def warmup_dialogs(client: TelegramClient):
    # Лёгкий прогрев кэша диалогов
    async for _ in client.iter_dialogs(limit=100):
        pass
    log.info("Warmup: диалоги подгружены.")

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

    await client.connect()
    if not await client.is_user_authorized():
        # При первом запуске Telethon спросит код/2FA в консоли
        await client.start()

    await warmup_dialogs(client)

    # Разрешаем источник
    src_token = normalize_token(SOURCE)
    src_entity, err = await resolve_entity_safe(client, src_token)
    if not src_entity:
        log.error(f"Источник не найден '{SOURCE}': {err}")
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
            log.error(f"Failed to resolve '{raw}': {e}")

    log.info("MODE=%s | SOURCE=%s | TARGETS_OK=%s", MODE, getattr(src_entity, 'id', src_token), list(resolved.keys()))
    if pending:
        log.warning("Pending (нет диалога/контакта или закрыт доступ): %s", pending)
        log.warning("Подсказка: укажи @username или дождись входящего от них — тогда ID разрешится.")

    # Хэндлер: новые сообщения от источника
    @client.on(events.NewMessage(from_users=src_entity))
    async def handler(ev: events.NewMessage.Event):
        try:
            msg = ev.message
            text = msg.message or ""

            if MODE == "copy":
                # Только текст. ВАЖНО: включаем превью ссылок.
                if not text:
                    return
                for label, dst in list(resolved.items()):
                    try:
                        await client.send_message(
                            dst,
                            text,
                            link_preview=True,                 # <-- включаем карточку ссылки
                            formatting_entities=msg.entities,  # переносим entities, если есть
                        )
                        log.info("Text → %s", label)
                    except ChatWriteForbiddenError:
                        log.error("Нет прав писать → %s", label)
                    except UserIsBlockedError:
                        log.error("Юзер заблокировал → %s", label)
                    except FloodWaitError as fw:
                        log.error("FloodWait %ss → %s", int(fw.seconds), label)
                        await asyncio.sleep(int(fw.seconds) + 1)
                    except Exception as e:
                        log.error("Send fail → %s | %s", label, e)

            elif MODE == "forward":
                # Форвард целиком. Превью у форвардов строится по исходнику.
                for label, dst in list(resolved.items()):
                    try:
                        await client.forward_messages(dst, msg)
                        log.info("Forward → %s", label)
                    except Exception as e:
                        log.error("Forward fail → %s | %s", label, e)

        except Exception as e:
            log.exception("Handler error: %s", e)

    log.info("Ready. Listening…")
    await client.run_until_disconnected()

# ---------- Точка входа ----------
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
