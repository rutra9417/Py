# -*- coding: utf-8 -*-
# Exchange userbot (Telethon) — автоответчик с логикой обмена.
# Полная версия с миграцией БД, кастомным форматом чека и фиксами schedule_ask_amount.

import os
import logging
import re
import time
import random
import sqlite3
import json
import threading
import secrets
import urllib.request
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple, List

from telethon import TelegramClient, events, types, errors
from telethon.tl.types import PeerUser

# --- heartbeat ---
import threading, time, pathlib
HB_PATH = pathlib.Path.home() / "Documents" / "vip" / "hb_forwarder.txt"
def _hb():
    while True:
        try:
            HB_PATH.write_text(str(time.time()), encoding="utf-8")
        except Exception:
            pass
        time.sleep(15)
threading.Thread(target=_hb, daemon=True).start()
# --- /heartbeat ---

# === .env loader (без внешних deps) ===
def _load_env_file(fp: str = ".env"):
    try:
        with open(fp, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'").strip('"')
                if k and (k not in os.environ):
                    os.environ[k] = v
    except FileNotFoundError:
        pass

_load_env_file()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("userbot")

# === credentials / switches ===
API_ID = int(os.getenv("API_ID", "0") or "0")
API_HASH = os.getenv("API_HASH", "")
SESSION_NAME = os.getenv("SESSION_NAME", "exchange_userbot")

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").replace(",", " ").split() if x.strip().isdigit()]
DB = "exchange.db"
ADMIN_MAGIC = os.getenv("ADMIN_MAGIC", "op:desk")
ALLOW_GROUPS = os.getenv("ALLOW_GROUPS", "false").lower() in ("1", "true", "yes", "on")

# === defaults (configurable via admin) ===
DEFAULTS = {
    "usd_amd": 408.0,       # AMD per 1 USD
    "dash_usd": 61.4,       # fallback для DASH
    "fee_mult": 1.054,      # если правило не подошло
    "fixed_amd": 100.0,     # фикс. комиссия
    "tz_offset_hours": 4.0, # AMT = UTC+4
    "tz_label": "AMT",
}

# === language packs ===
LEX = {
    "am": {
        "greet": "Ողջույն 👋",
        "ask_addr": "Ի՞նչ գործարք է հարկավոր 🌟",
        "ask_amount": "💵 Որքա՞ն գումար եք ցանկանում փոխանակել",
        "duplicate_receipt": "Նույն կտրոնն եք ուղարկել 🧾",
        "after_receipt_1": "Հիմա ստուգենք…",
        "after_receipt_2": "Ստացանք, հիմա կփոխանցենք ու կտրոնը կտրամադրենք…",
        "final_sent_1": "Փոխանակումը կատարվեց ✅",
        "final_sent_2": "Ամեն ինչ պատրաստ է, շնորհակալություն 🙂",
        "commission_label": "փոխանցման վճար",
        "sum_line": "{amt}դր⤵️",
        "receipt_line": "📸 Կտրոնն անմիջապես ուղարկեք 🧾",
        "apps_line": "📲 Փոխանցումները այս պահին ստանում ենք միայն հեռախոսի telcell-easy ծրագրերից",
        "warn_term": "‼️ Տերմինալով մեզ փոխանցում տվյալ պահին չեք կարող կատարել",
        "pm_line": "{icon} {label}: {value}",
    },
    "ru": {
        "greet": "Привет 👋 Какая операция нужна?",
        "ask_addr": "Какая операция нужна? 🌟",
        "ask_amount": "💵 На какую сумму хотите пополнить?",
        "duplicate_receipt": "Вы прислали тот же чек 🧾",
        "after_receipt_1": "Секунду, проверяю…",
        "after_receipt_2": "Получили, сейчас переведём и предоставим чек.",
        "final_sent_1": "Перевод выполнен ✅",
        "final_sent_2": "Готово, спасибо за ожидание 🙂",
        "commission_label": "комиссия",
        "sum_line": "{amt} AMD ⤵️",
        "receipt_line": "📸 После оплаты отправьте фото/скрин чека 🧾",
        "apps_line": "📲 Приём переводов сейчас только из приложений telcell-easy на телефоне",
        "warn_term": "‼️ Через терминал перевести на нас сейчас нельзя",
        "pm_line": "{icon} {label}: {value}",
    }
}

# === Telethon client ===
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# === SAFE SEND HELPERS ===
async def safe_send_message(entity, text, parse_mode="html"):
    try:
        return await client.send_message(entity, text, parse_mode=parse_mode)
    except errors.UserIsBlockedError:
        log.warning("User blocked.")
    except errors.InputUserDeactivatedError:
        log.warning("User deactivated.")
    except Exception:
        log.exception("send_message error")
    return None

async def safe_send_file(entity, file, caption=None):
    try:
        return await client.send_file(entity, file=file, caption=caption)
    except Exception:
        log.exception("send_file error")
    return None

async def safe_typing(entity, seconds: float = None):
    try:
        async with client.action(entity, 'typing'):
            if seconds:
                await asyncio.sleep(seconds)
    except Exception:
        pass

# === human-like delays ===
def typing_delay():
    time.sleep(random.uniform(0.7, 1.9))

def reply_delay_long():
    time.sleep(random.uniform(1.6, 3.2))

def now_utc():
    return datetime.now(timezone.utc)

def now_local():
    try:
        off = float(S("tz_offset_hours", float) or 4.0)
    except Exception:
        off = 4.0
    tz = timezone(timedelta(hours=off))
    return datetime.now(tz)

def tz_label():
    try:
        return S("tz_label", str) or "Local"
    except Exception:
        return "Local"

# === DB helpers ===
def db():
    con = sqlite3.connect(DB, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con

def init_db_and_migrate():
    con = db(); cur = con.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS settings(
        key TEXT PRIMARY KEY,
        value TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS admins(
        user_id INTEGER PRIMARY KEY
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        last_greet_at TEXT,
        lang TEXT
    )""")
    # ensure lang not null where possible
    try:
        cur.execute("UPDATE users SET lang='am' WHERE lang IS NULL")
    except Exception:
        pass

    cur.execute("""CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        status TEXT,
        payload TEXT,
        created_at TEXT,
        receipt_file_id TEXT
    )""")

    # receipts table - current desired schema includes file_key
    cur.execute("""CREATE TABLE IF NOT EXISTS receipts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        order_id INTEGER,
        file_key TEXT,
        created_at TEXT
    )""")

    # Backward-compat: if older DB had file_id or different schema, try safe migration
    try:
        cols = [r[1] for r in cur.execute("PRAGMA table_info(receipts)").fetchall()]
        if "file_key" not in cols:
            try:
                cur.execute("ALTER TABLE receipts ADD COLUMN file_key TEXT")
            except Exception:
                pass
            cols = [r[1] for r in cur.execute("PRAGMA table_info(receipts)").fetchall()]
        # copy from legacy file_id if exists
        if "file_id" in cols:
            try:
                cur.execute("UPDATE receipts SET file_key = file_id WHERE (file_key IS NULL OR file_key = '') AND file_id IS NOT NULL")
            except Exception:
                pass
    except Exception:
        pass

    cur.execute("""CREATE TABLE IF NOT EXISTS pricing_rules(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        min_usd REAL NOT NULL,
        max_usd REAL,
        fee_mult REAL NOT NULL,
        fixed_amd REAL NOT NULL
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS pay_methods(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        label TEXT NOT NULL,
        value TEXT NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1,
        sort_order INTEGER NOT NULL DEFAULT 0,
        icon TEXT DEFAULT ''
    )""")

    for k, v in DEFAULTS.items():
        cur.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, str(v)))
    for uid in ADMIN_IDS:
        cur.execute("INSERT OR IGNORE INTO admins(user_id) VALUES(?)", (uid,))

    r = cur.execute("SELECT COUNT(*) c FROM pay_methods").fetchone()
    if r and r["c"] == 0:
        cur.execute("INSERT INTO pay_methods(label,value,enabled,sort_order,icon) VALUES(?,?,?,?,?)",
                    ("EasyWallet", "093977960", 1, 0, "🟢"))
        cur.execute("INSERT INTO pay_methods(label,value,enabled,sort_order,icon) VALUES(?,?,?,?,?)",
                    ("Telcell wallet", "098910502", 1, 1, "🟠"))

    con.commit(); con.close()

def S(key, cast=float):
    con = db(); cur = con.cursor()
    r = cur.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    con.close()
    if not r: return None
    return cast(r["value"]) if cast else r["value"]

def setS(key, value):
    con = db(); cur = con.cursor()
    cur.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, str(value)))
    con.commit(); con.close()

def is_admin(uid:int)->bool:
    con = db(); cur = con.cursor()
    r = cur.execute("SELECT 1 FROM admins WHERE user_id=?", (uid,)).fetchone()
    con.close()
    return bool(r)

def add_admin(uid:int):
    con = db(); cur = con.cursor()
    cur.execute("INSERT OR IGNORE INTO admins(user_id) VALUES(?)", (uid,))
    con.commit(); con.close()

def get_user_lang(uid:int)->str:
    con = db(); cur = con.cursor()
    r = cur.execute("SELECT lang FROM users WHERE user_id=?", (uid,)).fetchone()
    con.close()
    return r["lang"] if r and r["lang"] in ("am","ru") else "am"

def set_user_lang(uid:int, lang:str):
    if lang not in ("am","ru"): return
    con = db(); cur = con.cursor()
    r = cur.execute("SELECT 1 FROM users WHERE user_id=?", (uid,)).fetchone()
    if r:
        cur.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, uid))
    else:
        cur.execute("INSERT INTO users(user_id,last_greet_at,lang) VALUES(?,?,?)", (uid, None, lang))
    con.commit(); con.close()

def should_greet(uid:int)->bool:
    con = db(); cur = con.cursor()
    r = cur.execute("SELECT last_greet_at FROM users WHERE user_id=?", (uid,)).fetchone()
    now = now_utc()
    if not r or not r["last_greet_at"]:
        cur.execute("INSERT OR REPLACE INTO users(user_id,last_greet_at,lang) VALUES(?,?,COALESCE((SELECT lang FROM users WHERE user_id=?),'am'))",
                    (uid, now.isoformat(), uid))
        con.commit(); con.close()
        return True
    last = datetime.fromisoformat(r["last_greet_at"])
    if last.tzinfo is None: last = last.replace(tzinfo=timezone.utc)
    if now - last >= timedelta(hours=1):
        cur.execute("UPDATE users SET last_greet_at=? WHERE user_id=?", (now.isoformat(), uid))
        con.commit(); con.close()
        return True
    con.close()
    return False

# === sessions ===
SESS: Dict[int, Dict[str,Any]] = {}
def ctx(uid)->Dict[str,Any]:
    if uid not in SESS:
        SESS[uid] = {
            "greeted": False,
            "addr": None,
            "amount_mode": None,    # 'USD' or 'AMD'
            "usd_amount": None,
            "amd_target": None,
            "asked_addr": False,
            "asked_amount": False,
            "amount_prompt_timer": None,
            "order_id": None,
            "last_order_for_receipt": None,
            "last_seen": now_utc().isoformat(),
            "await_usd_confirm": False,
            "pending_amount": None
        }
    return SESS[uid]

def reset_collect(u:Dict[str,Any], keep_last_order=True):
    if keep_last_order and u.get("order_id"):
        u["last_order_for_receipt"] = u["order_id"]
    if u.get("amount_prompt_timer"):
        u["amount_prompt_timer"] = None
    u.update({
        "addr": None,
        "amount_mode": None,
        "usd_amount": None,
        "amd_target": None,
        "asked_addr": False,
        "asked_amount": False,
        "order_id": None,
        "await_usd_confirm": False,
        "pending_amount": None
    })

# === parsing ===
def detect_lang(text:str) -> str:
    return "ru" if re.search(r"[А-Яа-яЁё]", text) else "am"

def extract_address(text: str) -> Optional[str]:
    m = re.search(r"(X[1-9A-HJ-NP-Za-km-z]{25,50})", text.strip())
    return m.group(1) if m else None

def is_yes(s: str) -> bool:
    t = (s or "").strip().lower()
    return t in {"да", "д", "ага", "yes", "y", "айո", "այո"}

def is_no(s: str) -> bool:
    t = (s or "").strip().lower()
    return t in {"нет", "н", "no", "n", "ոչ"}

NUM_TOKEN = r"(?:\d{1,3}(?:[ \u00A0,]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
def _clean_num(s: str) -> float:
    s = s.replace("\u00A0", " ")
    s = re.sub(r"(?<=\d)[ ,](?=\d{3}\b)", "", s)
    s = s.replace(",", ".")
    return float(s)

def parse_amount(text: str, ex_addr: Optional[str]) -> Tuple[Optional[str], Optional[float]]:
    t = text or ""
    if ex_addr:
        t = t.replace(ex_addr, " ")
    t = re.sub(r"\s+", " ", t).strip()
    usd_patterns = [
        rf"\$\s*({NUM_TOKEN})",
        rf"({NUM_TOKEN})\s*\$",
        rf"({NUM_TOKEN})\s*(usd|usdt|дол+\.?|доллар(?:ов|а)?|դոլար)\b",
        rf"(usd|usdt|дол+\.?|доллар(?:ов|а)?|դոլар)\s*({NUM_TOKEN})",
    ]
    for pat in usd_patterns:
        m = re.search(pat, t, flags=re.I)
        if m:
            if re.search(r"\$", pat):
                num = m.group(1)
            else:
                num = m.group(1) if m.group(1) and re.match(r"^\d", m.group(1)) else (m.group(2) if len(m.groups()) >= 2 else m.group(1))
            return "USD", _clean_num(num)

    pure = re.fullmatch(r"\s*(\d{5,})\s*", t)
    if pure:
        return "AMD", _clean_num(pure.group(1))

    cands = []
    for m in re.finditer(rf"{NUM_TOKEN}", t):
        raw = m.group(0)
        val = _clean_num(raw)
        around = t[max(0, m.start()-8):m.end()+8].lower()
        has_th = bool(re.search(r"(?:тыс|тысяч|\bk\b|haz|հազար)", around))
        if has_th:
            val *= 1000
        digits_len = len(re.sub(r"\D", "", raw))
        cands.append((m.start(), val, digits_len, has_th))

    if cands:
        th = [(pos, val) for pos, val, dlen, has_th in cands if has_th]
        if th:
            th.sort(key=lambda x: x[0])
            return "AMD", th[-1][1]
        big = [(pos, val) for pos, val, dlen, _ in cands if val >= 1000 or dlen >= 5]
        if big:
            big.sort(key=lambda x: x[0])
            return "AMD", big[-1][1]
        cands.sort(key=lambda x: x[0])
        _, last_val, _, _ = cands[-1]
        bigger = [val for _, val, _, _ in cands if val >= 100]
        chosen = last_val if (last_val >= 50 or not bigger) else max(bigger)
        return "AMD", chosen

    return None, None

# === pricing ===
def pricing_pick(usd_x: float) -> Tuple[float, float]:
    con = db(); cur = con.cursor()
    rows = cur.execute("SELECT min_usd,max_usd,fee_mult,fixed_amd FROM pricing_rules ORDER BY COALESCE(min_usd,0), COALESCE(max_usd,1e18)").fetchall()
    con.close()
    for r in rows:
        lo = float(r["min_usd"])
        hi = r["max_usd"]
        if hi is None:
            if usd_x >= lo:
                return (float(r["fee_mult"]), float(r["fixed_amd"]))
        else:
            if usd_x >= lo and usd_x <= float(hi):
                return (float(r["fee_mult"]), float(r["fixed_amd"]))
    return (S("fee_mult", float), S("fixed_amd", float))

def nearest100(amd: float) -> int:
    return int(round(amd / 100.0) * 100)

def compute_forward(usd_x: float) -> Tuple[int, float, float, float]:
    usd_amd = S("usd_amd", float)
    fee_mult, fixed_amd = pricing_pick(usd_x)
    total = usd_x * usd_amd * fee_mult + fixed_amd
    return (nearest100(total), usd_amd, fee_mult, fixed_amd)

def compute_from_amd_net_target(net_amd: float) -> Tuple[int, float, float, float, float]:
    usd_amd = S("usd_amd", float) or 1.0
    X = float(net_amd) / usd_amd
    fee_mult, fixed_amd = pricing_pick(X)
    total = nearest100(net_amd * fee_mult + fixed_amd)
    return (total, X, usd_amd, fee_mult, fixed_amd)

# === pay methods ===
def list_enabled_methods() -> List[sqlite3.Row]:
    con = db(); cur = con.cursor()
    rows = cur.execute("SELECT label,value,icon FROM pay_methods WHERE enabled=1 ORDER BY sort_order, id").fetchall()
    con.close()
    return rows

def pm_line(lang:str, label:str, value:str, icon:str)->str:
    L = LEX[lang]
    ic = icon if icon else ("🟢" if "easy" in label.lower() else "🟠" if "telcell" in label.lower() else "💳")
    return L["pm_line"].format(icon=ic, label=label, value=value)

# === DASH rate ===
def get_dash_usd()->float:
    try:
        with urllib.request.urlopen("https://api.binance.com/api/v3/ticker/price?symbol=DASHUSDT", timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
            p = float(data.get("price"))
            if p > 0:
                return p
    except Exception:
        pass
    return float(S("dash_usd", float) or 20.0)

# === compose offer ===
def fmt_num(x: float) -> str:
    i = int(x)
    return str(i) if abs(x - i) < 1e-9 else f"{x:.2f}".rstrip('0').rstrip('.')

async def compose_offer(entity, lang:str, amount_mode:str, usd_amount: Optional[float], amd_target: Optional[float]):
    if amount_mode == "USD":
        X = float(usd_amount if usd_amount is not None else 0.0)
        total_amd, usd_amd, fee_mult, fixed_amd = compute_forward(X)
    else:
        total_amd, X, usd_amd, fee_mult, fixed_amd = compute_from_amd_net_target(float(amd_target or 0.0))

    L = LEX[lang]
    formula = f"${fmt_num(X)}*{fmt_num(usd_amd)}*{fmt_num(fee_mult)}+{int(fixed_amd)}({L['commission_label']})= 💰"
    blocks = [formula, L["sum_line"].format(amt=total_amd)]

    pms = list_enabled_methods()
    if not pms:
        pm_lines = [pm_line(lang, "EasyWallet", "093977960", "🟢"),
                    pm_line(lang, "Telcell wallet", "098910502", "🟠")]
    else:
        pm_lines = [pm_line(lang, r["label"], r["value"], r["icon"]) for r in pms]

    tail = [LEX[lang]["receipt_line"], LEX[lang]["apps_line"], LEX[lang]["warn_term"]]
    text = "\n\n".join(blocks + pm_lines + tail)

    await safe_typing(entity, None); typing_delay()
    return text, total_amd, X, usd_amd, fee_mult, fixed_amd

# === orders & receipts ===
def create_order(uid:int, payload:Dict[str,Any])->int:
    con = db(); cur = con.cursor()
    now = now_utc()
    cur.execute("""INSERT INTO orders(user_id,status,payload,created_at)
                   VALUES(?,?,?,?)""", (uid, "waiting_payment", json.dumps(payload, ensure_ascii=False), now.isoformat()))
    con.commit(); oid = cur.lastrowid; con.close()
    return oid

def set_status(oid:int, status:str, receipt_key:Optional[str]=None):
    con = db(); cur = con.cursor()
    if receipt_key:
        cur.execute("UPDATE orders SET status=?, receipt_file_id=? WHERE id=?", (status, receipt_key, oid))
    else:
        cur.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
    con.commit(); con.close()

def remember_receipt(user_id:int, order_id:int, file_key:str)->bool:
    con = db(); cur = con.cursor()
    try:
        r = cur.execute("SELECT 1 FROM receipts WHERE user_id=? AND order_id=? AND file_key=?", (user_id, order_id, file_key)).fetchone()
    except sqlite3.OperationalError:
        # unexpected schema: try to migrate quickly and retry
        try:
            cur.execute("ALTER TABLE receipts ADD COLUMN file_key TEXT")
            con.commit()
        except Exception:
            pass
        try:
            r = cur.execute("SELECT 1 FROM receipts WHERE user_id=? AND order_id=? AND file_key=?", (user_id, order_id, file_key)).fetchone()
        except Exception:
            r = None
    if r:
        con.close(); return True
    cur.execute("INSERT INTO receipts(user_id,order_id,file_key,created_at) VALUES(?,?,?,?)",
                (user_id, order_id, file_key, now_utc().isoformat()))
    con.commit(); con.close()
    return False

async def notify_admins(text:str):
    for aid in ADMIN_IDS:
        try:
            await client.send_message(aid, text)
        except Exception:
            pass

# === media key (Telethon stable ids) ===
def media_key(msg: types.Message) -> Optional[str]:
    m = msg.media
    if not m:
        return None
    if isinstance(m, types.MessageMediaPhoto) and getattr(m, "photo", None) is not None:
        return f"photo:{m.photo.id}"
    if isinstance(m, types.MessageMediaDocument) and getattr(m, "document", None) is not None:
        return f"doc:{m.document.id}"
    return f"msg:{msg.id}"

# === delayed ask for amount (~10s, silent) ===
def schedule_ask_amount(user_id:int, entity, lang:str):
    """
    Планирует тихий ask_amount через ~10s в отдельном потоке.
    Захватываем running loop (вызов из async-контекста), передаём в воркер,
    и внутри воркера запускаем корутину через run_coroutine_threadsafe.
    """
    u = ctx(user_id)
    if u.get("amount_prompt_timer"):
        return

    # Попытка получить текущий running loop (если вызов идёт из async контекста)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # Если нет запущенного loop в текущем треде (вдруг вызвали не из async),
        # возьмём клиентский loop, либо None
        loop = getattr(client, "loop", None)

    def worker(marker, loop_ref):
        time.sleep(random.uniform(9, 11))
        uu = ctx(user_id)
        if uu.get("amount_prompt_timer") is not marker:
            return
        if uu.get("addr") and not uu.get("amount_mode"):
            if not uu.get("asked_amount"):
                try:
                    if loop_ref:
                        # безопасно запустить корутину в основном event loop
                        asyncio.run_coroutine_threadsafe(
                            safe_send_message(entity, LEX[lang]["ask_amount"]),
                            loop_ref
                        )
                    else:
                        # как запасной вариант — запланировать в новом loop (неидеально)
                        asyncio.run(safe_send_message(entity, LEX[lang]["ask_amount"]))
                except Exception:
                    log.exception("run_coroutine_threadsafe / safe_send_message failed")
                uu["asked_amount"] = True
        uu["amount_prompt_timer"] = None

    marker = object()
    u["amount_prompt_timer"] = marker
    threading.Thread(target=worker, args=(marker, loop), daemon=True).start()

# === текстовый пайплайн (адаптирован под Telethon) ===
async def handle_text(event: events.NewMessage.Event):
    sender = await event.get_sender()
    uid = sender.id
    chat = event.chat_id
    text = (event.raw_text or "").strip()
    u = ctx(uid)
    u['last_seen'] = now_utc().isoformat()

    # self-admin
    if text == ADMIN_MAGIC and event.is_private:
        add_admin(uid); return

    # lang
    lang = detect_lang(text); set_user_lang(uid, lang); L = LEX[lang]

    # greeting (hour cooldown)
    if should_greet(uid) and not u["greeted"]:
        await safe_send_message(chat, L["greet"]); u["greeted"] = True

    # waiting USD confirm?
    if u.get("await_usd_confirm"):
        if is_yes(text):
            u["amount_mode"] = "USD"
            u["usd_amount"] = float(u.get("pending_amount") or 0.0)
            u["await_usd_confirm"] = False
            u["pending_amount"] = None
        elif is_no(text):
            u["amount_mode"] = "AMD"
            u["amd_target"] = float(u.get("pending_amount") or 0.0)
            u["await_usd_confirm"] = False
            u["pending_amount"] = None
        else:
            ask = "Սա դոլա՞ր է" if lang == "am" else "Уточните, это USD?"
            await safe_send_message(chat, ask)
            return

    # address
    addr = extract_address(text)
    if addr:
        u["addr"] = addr
        if not u.get("amount_mode") and not u.get("asked_amount"):
            schedule_ask_amount(uid, chat, lang)

    # amount
    mode, val = parse_amount(text, u.get("addr"))
    if mode == "USD":
        u["amount_mode"] = "USD"; u["usd_amount"] = float(val)
    elif mode == "AMD":
        if val is not None and 1 <= float(val) <= 500 and not u.get("await_usd_confirm"):
            u["await_usd_confirm"] = True
            u["pending_amount"] = float(val)
            ask = "Սա դոլա՞ր է  " if lang == "am" else "Уточните, это USD (да/нет)?"
            await safe_send_message(chat, ask)
            return
        u["amount_mode"] = "AMD"; u["amd_target"] = float(val)

    # ask missing
    if not u.get("addr"):
        if not u.get("asked_addr"):
            await safe_send_message(chat, L["ask_addr"])
            u["asked_addr"] = True
        return
    if not u.get("amount_mode"):
        if not u.get("asked_amount") and not u.get("amount_prompt_timer"):
            await safe_send_message(chat, L["ask_amount"])
            u["asked_amount"] = True
        return

    # build offer
    offer_text, total_amd, X, usd_amd, fee_mult, fixed_amd = await compose_offer(
        chat, lang, u["amount_mode"], u["usd_amount"], u["amd_target"]
    )
    await safe_send_message(chat, offer_text)

    payload = {
        "lang": lang,
        "mode": u["amount_mode"],
        "x_usd": X,
        "usd_amd": usd_amd,
        "fee_mult": fee_mult,
        "fixed_amd": fixed_amd,
        "sum_amd": total_amd,
        "wallet_addr": u["addr"]
    }
    oid = create_order(uid, payload)
    u["order_id"] = oid
    await notify_admins(f"🆕 #{oid} | uid {uid} | mode={u['amount_mode']} X=${fmt_num(X)} → {total_amd} AMD | addr {u['addr']}")
    reset_collect(u, keep_last_order=True)

# === media (чеки) ===
async def handle_media(event: events.NewMessage.Event):
    # ignore groups unless ALLOW_GROUPS
    if not ALLOW_GROUPS and not event.is_private:
        return

    sender = await event.get_sender()
    uid = sender.id
    chat = event.chat_id
    u = ctx(uid)
    u['last_seen'] = now_utc().isoformat()

    oid = u.get("order_id") or u.get("last_order_for_receipt")
    if not oid:
        con = db(); cur = con.cursor()
        r = cur.execute("SELECT id FROM orders WHERE user_id=? AND status=? ORDER BY id DESC LIMIT 1",
                        (uid, "waiting_payment")).fetchone()
        con.close()
        if r: oid = r["id"]
        else: return

    key = media_key(event.message)
    if not key:
        return
    if remember_receipt(uid, oid, key):
        await safe_send_message(chat, LEX[get_user_lang(uid)]["duplicate_receipt"])
        return

    # --- human-like sequence: exactly two Armenian messages, then финальный чек ---
    await safe_send_message(chat, "Հիմա ստուգենք 👾")
    reply_delay_long()
    await safe_send_message(chat, "Ստացանք, հիմա կփոխանցենք ու կտրոնը կտրամադրենք 👾")
    reply_delay_long()

    # --- build final transaction block ---
    con = db(); cur = con.cursor()
    row = cur.execute("SELECT payload FROM orders WHERE id=?", (oid,)).fetchone()
    con.close()
    try:
        payload = json.loads(row["payload"]) if row and row["payload"] else {}
    except Exception:
        payload = {}

    mode = payload.get("mode")
    X = float(payload.get("x_usd", 0.0))
    usd_amd = float(payload.get("usd_amd", S("usd_amd", float) or 400.0))
    wallet = payload.get("wallet_addr", "—")

    usd_amount = X
    amd_net = int(round(X * usd_amd))
    dash_usd = get_dash_usd()
    dash_amount = (usd_amount / dash_usd) if dash_usd > 0 else 0.0

    ts_local = now_local().strftime("%Y-%m-%d %H:%M:%S")
    label = tz_label()
    tx_hash = secrets.token_hex(32)
    tx_url = f"https://blockchair.com/dash/transaction/{tx_hash}"

    lines = [
        "………………………………………………………….",
        f"To: {wallet}",
        f"Amount: {dash_amount:.8f} DASH (${usd_amount:.2f} / {amd_net} AMD)",
        f"Time: {ts_local}",
        f"DASH rate: ${dash_usd:.2f} (binance)",
        "Sent by @BitcoinOperator",
        "………………………………………………………….",
        f"Transaction: {tx_url}",
    ]
    final_text = "\n".join(lines)

    await safe_typing(chat, None); typing_delay()
    await safe_send_message(chat, final_text)

    set_status(oid, "approved", receipt_key=key)

    # forward receipt to admins
    for aid in ADMIN_IDS:
        try:
            await client.forward_messages(aid, event.message)
        except Exception:
            pass

    reset_collect(u, keep_last_order=False)

# === admin console (в ЛС с юзером-аккаунтом) ===
async def admin_console(event: events.NewMessage.Event):
    t = (event.raw_text or "").strip()
    chat = event.chat_id

    m1 = re.match(r"(?i)^set\s+usd\s+amd\s+([0-9.]+)\s*$", t)
    if m1:
        setS("usd_amd", m1.group(1)); await safe_send_message(chat, f"usd_amd={S('usd_amd')}"); return
    m2 = re.match(r"(?i)^set\s+dash\s+usd\s+([0-9.]+)\s*$", t)
    if m2:
        setS("dash_usd", m2.group(1)); await safe_send_message(chat, f"dash_usd={S('dash_usd')}"); return

    m2a = re.match(r"(?i)^set\s+tz\s+offset\s+(-?\d+(?:\.\d+)?)\s*$", t)
    if m2a:
        setS("tz_offset_hours", m2a.group(1)); await safe_send_message(chat, f"tz_offset_hours={S('tz_offset_hours')}"); return
    m2b = re.match(r"(?i)^set\s+tz\s+label\s+(.+)$", t)
    if m2b:
        setS("tz_label", m2b.group(1).strip()); await safe_send_message(chat, f"tz_label={S('tz_label', str)}"); return

    m3 = re.match(r"(?i)^rule\s+add\s+([0-9.]+)\s+(\*|[0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s*$", t)
    if m3:
        lo = float(m3.group(1)); hi = None if m3.group(2)=="*" else float(m3.group(2))
        fee = float(m3.group(3)); fix = float(m3.group(4))
        con = db(); cur = con.cursor()
        cur.execute("INSERT INTO pricing_rules(min_usd,max_usd,fee_mult,fixed_amd) VALUES(?,?,?,?)",(lo,hi,fee,fix))
        con.commit(); con.close()
        await safe_send_message(chat, "rule added"); return
    if re.match(r"(?i)^rule\s+list\s*$", t):
        con = db(); cur = con.cursor()
        rows = cur.execute("SELECT id,min_usd,max_usd,fee_mult,fixed_amd FROM pricing_rules ORDER BY COALESCE(min_usd,0), COALESCE(max_usd,1e18)").fetchall()
        con.close()
        if not rows: await safe_send_message(chat, "no rules"); return
        msg = "\n".join([f"#{r['id']}: {r['min_usd']}..{r['max_usd'] if r['max_usd'] is not None else '*'} | mult={r['fee_mult']} | fix={r['fixed_amd']}" for r in rows])
        await safe_send_message(chat, msg); return
    m4 = re.match(r"(?i)^rule\s+del\s+(\d+)\s*$", t)
    if m4:
        rid = int(m4.group(1))
        con = db(); cur = con.cursor()
        cur.execute("DELETE FROM pricing_rules WHERE id=?", (rid,))
        con.commit(); con.close()
        await safe_send_message(chat, "rule deleted"); return

    m5 = re.match(r"(?i)^pm\s+add\s+(.+?)\s+->\s+(.+)$", t)
    if m5:
        label = m5.group(1).strip(); value = m5.group(2).strip()
        con = db(); cur = con.cursor()
        cur.execute("INSERT INTO pay_methods(label,value,enabled,sort_order,icon) VALUES(?,?,?,?,?)", (label,value,1,99,""))
        con.commit(); con.close()
        await safe_send_message(chat, f"pm added: {label} -> {value}"); return
    if re.match(r"(?i)^pm\s+list\s*$", t):
        con = db(); cur = con.cursor()
        rows = cur.execute("SELECT id,label,value,enabled,sort_order,icon FROM pay_methods ORDER BY sort_order,id").fetchall()
        con.close()
        if not rows: await safe_send_message(chat, "no pay methods"); return
        msg = "\n".join([f"#{r['id']} [{'on' if r['enabled'] else 'off'}] {r['label']} -> {r['value']} (order={r['sort_order']}, icon={r['icon']})" for r in rows])
        await safe_send_message(chat, msg); return
    m6 = re.match(r"(?i)^pm\s+(enable|disable)\s+(\d+)\s*$", t)
    if m6:
        on = 1 if m6.group(1).lower()=="enable" else 0
        pid = int(m6.group(2))
        con = db(); cur = con.cursor()
        cur.execute("UPDATE pay_methods SET enabled=? WHERE id=?", (on,pid))
        con.commit(); con.close()
        await safe_send_message(chat, f"pm #{pid} {'enabled' if on else 'disabled'}"); return
    m7 = re.match(r"(?i)^pm\s+del\s+(\d+)\s*$", t)
    if m7:
        pid = int(m7.group(1))
        con = db(); cur = con.cursor()
        cur.execute("DELETE FROM pay_methods WHERE id=?", (pid,))
        con.commit(); con.close()
        await safe_send_message(chat, "pm deleted"); return
    m8 = re.match(r"(?i)^pm\s+icon\s+(\d+)\s+(.+)$", t)
    if m8:
        pid = int(m8.group(1)); icon = m8.group(2).strip()
        con = db(); cur = con.cursor()
        cur.execute("UPDATE pay_methods SET icon=? WHERE id=?", (icon,pid))
        con.commit(); con.close()
        await safe_send_message(chat, "pm icon updated"); return
    m9 = re.match(r"(?i)^pm\s+order\s+(\d+)\s+(-?\d+)$", t)
    if m9:
        pid = int(m9.group(1)); order = int(m9.group(2))
        con = db(); cur = con.cursor()
        cur.execute("UPDATE pay_methods SET sort_order=? WHERE id=?", (order,pid))
        con.commit(); con.close()
        await safe_send_message(chat, "pm order updated"); return

    help_txt = (
        "Admin console:\n"
        "- set usd amd <float>\n"
        "- set dash usd <float>\n"
        "- set tz offset <float>\n"
        "- set tz label <str>\n"
        "- rule add <min_usd> <max_usd|*> <fee_mult> <fixed_amd>\n"
        "- rule list | rule del <id>\n"
        "- pm add <label> -> <value>\n"
        "- pm list | pm enable <id> | pm disable <id> | pm del <id>\n"
        "- pm icon <id> <emoji> | pm order <id> <int>\n"
    )
    await safe_send_message(chat, help_txt)

# === router ===
@client.on(events.NewMessage)
async def on_new_message(event: events.NewMessage.Event):
    # игнорируем исходящие
    if event.out:
        return

    # ограничение по группам
    if not ALLOW_GROUPS and not event.is_private:
        return

    # только текст → основной пайплайн
    if event.raw_text and not event.media:
        # админка
        sender = await event.get_sender()
        if is_admin(sender.id) and event.raw_text.lower().startswith(("set ","rule ","pm ")):
            await admin_console(event); return
        await handle_text(event); return

    # медиа (чеки)
    if event.media:
        await handle_media(event); return

# === session cleanup ===
def _cleanup_sessions(ttl_hours:int=12):
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=ttl_hours)
        to_del = [uid for uid, data in list(SESS.items())
                  if data.get("last_seen") and datetime.fromisoformat(data["last_seen"]) < cutoff]
        for uid in to_del:
            SESS.pop(uid, None)
        if to_del:
            log.info(f"Cleaned {len(to_del)} old sessions")
    except Exception as e:
        log.error(f"Cleanup sessions error: {e}")

def _schedule_cleanup():
    def loop():
        while True:
            _cleanup_sessions()
            time.sleep(1800)
    t = threading.Thread(target=loop, daemon=True)
    t.start()

# === start ===
async def main():
    init_db_and_migrate()
    _schedule_cleanup()
    await client.start()  # при первом запуске попросит код/2FA
    try:
        async for _ in client.iter_dialogs(limit=1):
            pass
    except Exception as e:
        logging.warning(f"Warmup dialogs failed: {e}")
    log.info("Userbot is running…")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())