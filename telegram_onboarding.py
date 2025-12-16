import os
import re
import json
import requests
from datetime import datetime

import config as cfg

USER_DATA_FILE = getattr(cfg, "USER_DATA_FILE", "user_data.json")
LAST_UPDATE_ID_FILE = getattr(cfg, "LAST_UPDATE_ID_FILE", "last_update_id.json")
ENABLE_DEBUG_LOGS = getattr(cfg, "ENABLE_DEBUG_LOGS", True)

BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or getattr(cfg, "TELEGRAM_TOKEN", "")).strip()
if not BOT_TOKEN:
    raise RuntimeError("Missing TELEGRAM token. Set TELEGRAM_BOT_TOKEN (recommended) or TELEGRAM_TOKEN.")

VALID_APPAREL_SIZES = {"XS", "S", "M", "L", "XL", "XXL", "XXXL"}


def tg_url(method: str) -> str:
    return f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"


def send_message(chat_id: int, text: str) -> None:
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    r = requests.post(tg_url("sendMessage"), data=payload, timeout=30)
    if ENABLE_DEBUG_LOGS:
        print(f"send_message to {chat_id} -> status {r.status_code}")


def load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception as e:
        if ENABLE_DEBUG_LOGS:
            print(f"load_json error for {path}: {e}")
        return default


def save_json(path: str, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        if ENABLE_DEBUG_LOGS:
            print(f"save_json error for {path}: {e}")


def load_user_data() -> dict:
    return load_json(USER_DATA_FILE, {})


def save_user_data(d: dict) -> None:
    save_json(USER_DATA_FILE, d)


def load_last_update_id():
    raw = load_json(LAST_UPDATE_ID_FILE, None)
    if raw is None:
        return None
    if isinstance(raw, dict) and "last_update_id" in raw:
        return raw.get("last_update_id")
    if isinstance(raw, int):
        return raw
    return None


def save_last_update_id(x: int) -> None:
    save_json(LAST_UPDATE_ID_FILE, {"last_update_id": x})


def map_gender(code: str) -> str:
    return {"1": "men", "2": "women", "3": "kids"}.get(code, "men")


def map_category(code: str) -> str:
    c = code.upper()
    return {"A": "shoes", "B": "clothing", "C": "both"}.get(c, "shoes")


def welcome_text() -> str:
    return (
        "👟 <b>Timberland Tracker</b>\n\n"
        "📬 עדכוני מוצרים נשלחים פעמיים ביום בשעות <b>07:00</b> ו-<b>19:00</b> (שעון ישראל).\n\n"
        "כדי להגדיר מעקב בהודעה אחת, שלח בפורמט הבא:\n\n"
        "<b>מגדר</b> <b>סוג</b> <b>מידות</b> <b>מחיר מינ</b> <b>מחיר מקס</b>\n\n"
        "מגדר:\n"
        "1 - גברים\n"
        "2 - נשים\n"
        "3 - ילדים\n\n"
        "סוג:\n"
        "A - הנעלה\n"
        "B - ביגוד\n"
        "C - גם וגם\n\n"
        "דוגמאות:\n"
        "<code>1 A 43 128 299</code>\n"
        "<code>1 B L 68 1001</code>\n"
        "<code>1 C 43 L 68 1001</code>\n\n"
        "בביגוד המידות הן: XS, S, M, L, XL, XXL, XXXL\n"
        "סטטוס משתמשים: <code>/stat</code>"
    )


# Regex:
# A: "1 A 43 128 299"
ONE_SHOT_SHOES = re.compile(r"^\s*([123])\s+([Aa])\s+(\d{1,2})\s+(\d+)\s+(\d+)\s*$")
# B: "1 B L 68 1001"
ONE_SHOT_CLOTH = re.compile(r"^\s*([123])\s+([Bb])\s+(XS|S|M|L|XL|XXL|XXXL)\s+(\d+)\s+(\d+)\s*$", re.IGNORECASE)
# C: "1 C 43 L 68 1001"
ONE_SHOT_BOTH = re.compile(r"^\s*([123])\s+([Cc])\s+(\d{1,2})\s+(XS|S|M|L|XL|XXL|XXXL)\s+(\d+)\s+(\d+)\s*$", re.IGNORECASE)


def ensure_user(user_data: dict, chat_id: int) -> dict:
    key = str(chat_id)
    if key not in user_data:
        user_data[key] = {"chat_id": chat_id, "state": "ready"}
    user_data[key]["chat_id"] = chat_id
    return user_data[key]


def parse_one_shot(text: str):
    t = text.strip()

    m = ONE_SHOT_BOTH.match(t)
    if m:
        g, c, shoe_size, apparel_size, pmin, pmax = m.groups()
        return {
            "gender": map_gender(g),
            "category": "both",
            "size": str(int(shoe_size)),
            "apparel_size": apparel_size.upper(),
            "price_min": int(pmin),
            "price_max": int(pmax),
        }

    m = ONE_SHOT_SHOES.match(t)
    if m:
        g, c, shoe_size, pmin, pmax = m.groups()
        return {
            "gender": map_gender(g),
            "category": "shoes",
            "size": str(int(shoe_size)),
            "apparel_size": None,
            "price_min": int(pmin),
            "price_max": int(pmax),
        }

    m = ONE_SHOT_CLOTH.match(t)
    if m:
        g, c, apparel_size, pmin, pmax = m.groups()
        return {
            "gender": map_gender(g),
            "category": "clothing",
            "size": None,
            "apparel_size": apparel_size.upper(),
            "price_min": int(pmin),
            "price_max": int(pmax),
        }

    return None


def get_updates(offset=None):
    params = {}
    if offset is not None:
        params["offset"] = offset
    if ENABLE_DEBUG_LOGS:
        print(f"Calling getUpdates with params: {params}")
    r = requests.get(tg_url("getUpdates"), params=params, timeout=30)
    if ENABLE_DEBUG_LOGS:
        print(f"getUpdates HTTP status: {r.status_code}")
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram error: {data}")
    return data.get("result", [])


def main():
    print("=== telegram_onboarding.py starting ===")

    user_data = load_user_data()
    last_update_id = load_last_update_id()

    updates = get_updates(offset=(last_update_id + 1) if isinstance(last_update_id, int) else None)
    print(f"getUpdates returned {len(updates)} updates")

    new_last_update_id = last_update_id

    for upd in updates:
        upd_id = upd.get("update_id")
        if isinstance(upd_id, int):
            if new_last_update_id is None or upd_id > new_last_update_id:
                new_last_update_id = upd_id

        msg = upd.get("message") or upd.get("edited_message")
        if not msg:
            continue

        chat_id = msg.get("chat", {}).get("id")
        text = (msg.get("text") or "").strip()

        if not chat_id:
            continue

        if ENABLE_DEBUG_LOGS:
            print(f"handle_message: chat_id={chat_id}, text={repr(text)}")

        if text.lower() == "/start":
            send_message(chat_id, welcome_text())
            continue

        if text.lower() == "/stat":
            send_message(chat_id, f"📊 <b>Users registered</b>: <b>{len(user_data)}</b>")
            continue

        parsed = parse_one_shot(text)
        if not parsed:
            send_message(chat_id, "❌ פורמט לא תקין. שלח /start כדי לקבל דוגמאות פורמט.")
            continue

        # normalize prices
        if parsed["price_min"] > parsed["price_max"]:
            parsed["price_min"], parsed["price_max"] = parsed["price_max"], parsed["price_min"]

        # validate apparel
        if parsed["category"] in ("clothing", "both"):
            a = (parsed.get("apparel_size") or "").upper()
            if a not in VALID_APPAREL_SIZES:
                send_message(chat_id, "❌ מידה לביגוד לא תקינה. השתמש ב: XS,S,M,L,XL,XXL,XXXL")
                continue

        prefs = ensure_user(user_data, chat_id)
        prefs["state"] = "ready"
        prefs["gender"] = parsed["gender"]
        prefs["category"] = parsed["category"]
        prefs["price_min"] = parsed["price_min"]
        prefs["price_max"] = parsed["price_max"]

        # shoes size
        if parsed["category"] in ("shoes", "both"):
            prefs["size"] = parsed["size"]

        # apparel size
        if parsed["category"] in ("clothing", "both"):
            prefs["apparel_size"] = parsed["apparel_size"]

        # cleanup fields if not used
        if parsed["category"] == "shoes":
            prefs.pop("apparel_size", None)
        if parsed["category"] == "clothing":
            prefs.pop("size", None)

        save_user_data(user_data)

        msg_ok = (
            "✅ נשמר!\n\n"
            f"מגדר: <b>{prefs.get('gender')}</b>\n"
            f"סוג: <b>{prefs.get('category')}</b>\n"
            f"מחיר: <b>{prefs.get('price_min')}-{prefs.get('price_max')}</b>\n"
        )
        if prefs.get("size"):
            msg_ok += f"נעליים - מידה: <b>{prefs.get('size')}</b>\n"
        if prefs.get("apparel_size"):
            msg_ok += f"ביגוד - מידה: <b>{prefs.get('apparel_size')}</b>\n"
        msg_ok += "\n📬 תקבל עדכונים ב-07:00 וב-19:00 (שעון ישראל)."

        send_message(chat_id, msg_ok)

    if isinstance(new_last_update_id, int):
        save_last_update_id(new_last_update_id)

    print(f"Onboarding sync done. New last_update_id: {new_last_update_id}")


if __name__ == "__main__":
    main()