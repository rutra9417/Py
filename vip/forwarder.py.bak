# -*- coding: utf-8 -*-
import os
import re
import asyncio
import logging
from typing import List, Union, Optional, Dict

from dotenv import load_dotenv
from telethon import TelegramClient, events, functions, types, __version__ as TL_VER
from telethon.tl.custom.message import Message
from telethon.errors import (
    ChatWriteForbiddenError, UserIsBlockedError, ChannelPrivateError,
    FloodWaitError, UsernameInvalidError, UsernameNotOccupiedError,
    InviteHashExpiredError, InviteHashInvalidError, ChannelsTooMuchError
)

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION_NAME = os.getenv("SESSION_NAME", "exchange_userbot")

SOURCE_BOT = os.getenv("SOURCE_BOT", "").strip()
TARGETS_RAW = os.getenv("TARGETS", "").strip()

RESOLVE_GROUPS_RAW = os.getenv("RESOLVE_GROUPS", "").strip()  # @group1,-100...,t.me/...
RESOLVE_PART_LIMIT = int(os.getenv("RESOLVE_PART_LIMIT", "2000"))

assert API_ID and API_HASH, "API_ID/API_HASH не заданы"
assert SOURCE_BOT, "SOURCE_BOT не задан"
assert TARGETS_RAW, "TARGETS пуст"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("forwarder")

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

CTX = {
    "source_bot_id": None,
    "targets_entities": [],
}

INVITE_RX = re.compile(r"(https?://)?t\.me/(joinchat/\S+|\+\S+)", re.IGNORECASE)
ENTITY_CACHE: Dict[int, object] = {}  # user_id -> entity (кеш)


async def join_via_invite(url: str) -> Optional[types.TypePeer]:
    m = INVITE_RX.search(url)
    if not m:
        log.error(f"INVITE: ссылка не распознана: {url}")
        return None
    invite = m.group(2)
    try:
        res = await client(functions.messages.ImportChatInviteRequest(invite))
        chats = getattr(res, "chats", None) or ([getattr(res, "chat", None)] if hasattr(res, "chat") else [])
        chats = [c for c in chats if c]
        if not chats:
            log.warning(f"INVITE: вступили, но чата не видно: {url}")
            return None
        entity = chats[0]
        log.info(f"INVITE: вступил в {getattr(entity, 'title', entity)}")
        return entity
    except (InviteHashExpiredError, InviteHashInvalidError):
        log.error("INVITE: инвайт просрочен/некорректен")
    except ChannelsTooMuchError:
        log.error("INVITE: слишком много каналов, покинь что-то и повтори")
    except FloodWaitError as e:
        log.error(f"INVITE: FloodWait {e.seconds}s")
    except Exception as e:
        log.error(f"INVITE: не удалось вступить: {e}")
    return None


async def import_contact(phone: str) -> Optional[types.User]:
    phone = phone.replace("+", "").strip()
    if not phone.isdigit():
        log.error(f"PHONE: неверный формат номера: {phone}")
        return None
    try:
        res = await client(functions.contacts.ImportContactsRequest(
            contacts=[types.InputPhoneContact(client_id=0, phone=phone, first_name=".", last_name="")]
        ))
        if res and res.users:
            user = res.users[0]
            log.info(f"PHONE: импортирован контакт id={user.id}")
            return user
        log.warning("PHONE: контакт не найден в Telegram")
    except FloodWaitError as e:
        log.error(f"PHONE: FloodWait {e.seconds}s")
    except Exception as e:
        log.error(f"PHONE: не удалось импортировать контакт: {e}")
    return None


async def try_get_from_dialogs(uid: int):
    async for d in client.iter_dialogs():
        ent = d.entity
        if getattr(ent, "id", None) == uid:
            return ent
    return None


async def try_get_from_groups(uid: int):
    groups = [g.strip() for g in RESOLVE_GROUPS_RAW.split(",") if g.strip()]
    if not groups:
        return None
    for g in groups:
        try:
            if g.startswith("-100") and g[1:].isdigit():
                gen = await client.get_entity(int(g))
            else:
                gen = await client.get_entity(g)
        except Exception as e:
            log.warning(f"RESOLVE_GROUPS: не удалось открыть '{g}': {e}")
            continue

        log.info(f"RESOLVE_GROUPS: сканирую участников {getattr(gen, 'title', gen)} (limit={RESOLVE_PART_LIMIT})")
        try:
            participants = await client.get_participants(gen, limit=RESOLVE_PART_LIMIT)
        except FloodWaitError as e:
            log.error(f"Participants FloodWait {e.seconds}s на '{g}'")
            continue
        except Exception as e:
            log.warning(f"Не получил участников для '{g}': {e}")
            continue

        for p in participants:
            if getattr(p, "id", None) == uid:
                log.info(f"RESOLVE_GROUPS: найден пользователь {uid} в '{getattr(gen, 'title', gen)}'")
                return p
    return None


async def resolve_entity(identifier: str):
    ident = identifier.strip()
    if not ident:
        return None

    if ident.lower() == "@me":
        return "me"

    if ident.upper().startswith("PHONE:"):
        phone = ident.split(":", 1)[1].strip()
        return await import_contact(phone)

    if ident.upper().startswith("INVITE:"):
        url = ident.split(":", 1)[1].strip()
        return await join_via_invite(url)

    if ident.startswith("-100") and ident[1:].isdigit():
        try:
            return await client.get_entity(int(ident))
        except Exception as e:
            log.error(f"ID канала/чата '{ident}' не резолвится: {e}. Убедись, что ты УЧАСТНИК.")
            return None

    if ident.isdigit():
        uid = int(ident)

        if uid in ENTITY_CACHE:
            return ENTITY_CACHE[uid]

        # 1) tg://user?id=...
        try:
            ent = await client.get_entity(f"tg://user?id={uid}")
            ENTITY_CACHE[uid] = ent
            return ent
        except Exception:
            pass

        # 2) мои диалоги
        ent = await try_get_from_dialogs(uid)
        if ent:
            ENTITY_CACHE[uid] = ent
            return ent

        # 3) участники из RESOLVE_GROUPS
        ent = await try_get_from_groups(uid)
        if ent:
            ENTITY_CACHE[uid] = ent
            return ent

        log.error(
            f"Не удалось резолвнуть user_id '{uid}'. Нужен username, телефон (PHONE:+...), "
            f"общий чат в RESOLVE_GROUPS, или чтобы пользователь сначала написал тебе в ЛС."
        )
        return None

    try:
        return await client.get_entity(ident)  # @username / ссылки
    except UsernameInvalidError:
        log.error(f"Неверный username: {ident}")
    except UsernameNotOccupiedError:
        log.error(f"Username не занят: {ident}")
    except Exception as e:
        log.error(f"Не удалось резолвнуть '{ident}': {e}")
    return None


async def resolve_targets(raw: str) -> List[Union[str, object]]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    targets = []
    for p in parts:
        ent = await resolve_entity(p)
        if ent:
            targets.append(ent)
        else:
            log.warning(f"Пропускаю TARGET '{p}' — не найден/недоступен")
    return targets


async def is_dm_with_source(event: events.NewMessage.Event, source_id: int) -> bool:
    return event.is_private and (event.chat_id == source_id)


async def send_plain_text(msg: Message, target: Union[str, object]):
    """
    Всегда отправляем только текст (msg.raw_text).
    Любые медиа/документы/карточки — игнорируем.
    """
    if msg.action:
        return  # сервисные события (join/leave/и т.п.) — пропускаем

    text = (msg.raw_text or "").strip()
    if not text:
        # если текста нет — ничего не шлём (по ТЗ "нужно простое сообщение")
        return
    await client.send_message(target, text, link_preview=True)


async def fanout_text(msg: Message, targets: List[Union[str, object]]):
    for t in targets:
        try:
            await send_plain_text(msg, t)
            log.info(f"Text → {get_target_name(t)}")
        except (ChatWriteForbiddenError, UserIsBlockedError, ChannelPrivateError) as e:
            log.warning(f"Нет прав писать в '{get_target_name(t)}': {e}")
        except FloodWaitError as e:
            log.error(f"Text FloodWait {e.seconds}s")
        except Exception as e:
            log.error(f"Ошибка отправки текста в '{get_target_name(t)}': {e}")


def get_target_name(t: Union[str, object]) -> str:
    if isinstance(t, str):
        return t
    for attr in ("username", "title", "id"):
        v = getattr(t, attr, None)
        if v:
            return str(v)
    return str(t)


@client.on(events.NewMessage(incoming=True))
async def handler(event: events.NewMessage.Event):
    if CTX["source_bot_id"] is None or not CTX["targets_entities"]:
        return
    if not await is_dm_with_source(event, CTX["source_bot_id"]):
        return
    try:
        await fanout_text(event.message, CTX["targets_entities"])
    except Exception as e:
        log.error(f"Сбой обработки сообщения: {e}")


async def main():
    log.info("Запуск…")
    await client.start()
    me = await client.get_me()
    log.info(f"Telethon={TL_VER}")
    log.info(f"Клиент: @{getattr(me, 'username', None) or me.id}")

    source_ent = await resolve_entity(SOURCE_BOT)
    assert source_ent is not None, f"Не найден SOURCE_BOT: {SOURCE_BOT}"
    source_bot_id = source_ent.id if hasattr(source_ent, "id") else me.id

    targets_entities = await resolve_targets(TARGETS_RAW)
    assert targets_entities, "Ни одна цель из TARGETS не валидна/доступна"

    CTX["source_bot_id"] = source_bot_id
    CTX["targets_entities"] = targets_entities

    log.info(f"Источник: {SOURCE_BOT} (id={source_bot_id}) | Режим: plain-text")
    log.info(f"Целей: {len(targets_entities)}")
    for t in targets_entities:
        log.info(f"→ целевой peer: {get_target_name(t)}")

    log.info("Готов. Слежу за ЛС от источника и ретранслирую…")
    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Остановка по запросу.")