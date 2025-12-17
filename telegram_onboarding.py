# telegram_onboarding.py
import json
import re
import requests

from config import (
    USER_DATA_FILE,
    LAST_UPDATE_ID_FILE,
    TELEGRAM_BOT_TOKEN,
    WELCOME_TEXT,
    ENABLE_DEBUG_LOGS,
    CLOTHING_SIZE_MAP,
)

API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def log(msg: str):
    if ENABLE_DEBUG_LOGS:
        print(msg)


def load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception:
        return default


def save_json(path: str, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def send_message(chat_id: int, text: str):
    url = f"{API}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    r = requests.post(url, data=payload, timeout=30)
    log(f"send_message to {chat_id} -> status {r.status_code}")
    return r


def parse_one_line(text: str):
    parts = (text or "").strip().split()
    if len(parts) != 5:
        return None

    gender_code, type_code, size_raw, min_p, max_p = parts

    if gender_code not in ("1", "2", "3"):
        return None
    if type_code.upper() not in ("A", "B", "C"):
        return None

    try:
        price_min = int(min_p)
        price_max = int(max_p)
        if price_min < 0 or price_max < 0 or price_min > price_max:
            return None
    except Exception:
        return None

    gender = {"1": "men", "2": "women", "3": "kids"}[gender_code]
    category = {"A": "shoes", "B": "clothing", "C": "both"}[type_code.upper()]

    shoes_size = None
    clothing_size = None

    if category == "shoes":
        if not re.fullmatch(r"\d{2}", size_raw):
            return None
        shoes_size = size_raw

    elif category == "clothing":
        s = size_raw.upper()
        if s not in CLOTHING_SIZE_MAP:
            return None
        clothing_size = s

    else:
        if "/" not in size_raw:
            return None
        a, b = size_raw.split("/", 1)
        a = a.strip()
        b = b.strip().upper()

        if not re.fullmatch(r"\d{2}", a):
            return None
        if b not in CLOTHING_SIZE_MAP:
            return None

        shoes_size = a
        clothing_size = b

    return {
        "gender": gender,
        "category": category,
        "shoes_size": shoes_size,
        "clothing_size": clothing_size,
        "price_min": price_min,
        "price_max": price_max,
    }


def handle_message(chat_id: int, text: str, user_data: dict):
    text = (text or "").strip()
    if not text:
        return

    current = user_data.get(str(chat_id), {})
    state = current.get("state")

    if text.lower() in ("/start", "start"):
        # Anti-spam: if user already ready, do NOT resend full welcome each automation run
        if state == "ready":
            send_message(
                chat_id,
                "✅ אתה כבר מוגדר ומקבל מוצרים ב-07:00 וב-19:00 (שעון ישראל).\n"
                "כדי לשנות הגדרות - שלח פורמט חדש כמו:\n"
                "<code>1 A 43 128 299</code>\n"
                "או שלח /reset (אם קיים אצלך) ואז /start."
            )
            return

        send_message(chat_id, WELCOME_TEXT)
        if str(chat_id) not in user_data:
            user_data[str(chat_id)] = {"chat_id": chat_id, "state": "awaiting_setup"}
        return

    if text == "/stat":
        total = len(user_data)
        ready = sum(1 for _, v in user_data.items() if v.get("state") == "ready")
        awaiting = total - ready
        send_message(
            chat_id,
            "📊 <b>סטטוס בוט</b>\n\n"
            f"Total users: <b>{total}</b>\n"
            f"Ready: <b>{ready}</b>\n"
            f"Awaiting setup: <b>{awaiting}</b>\n"
        )
        return

    parsed = parse_one_line(text)
    if not parsed:
        # If user is ready, ignore bad texts (prevents spam from old updates)
        if state == "ready":
            return

        send_message(
            chat_id,
            "❌ <b>פורמט לא תקין.</b>\n\n"
            "שלח /start כדי לראות שוב את ההוראות.\n"
            "דוגמה: <code>1 A 43 128 299</code>\n"
            "דוגמה ל-C: <code>2 C 40/L 0 800</code>"
        )
        return

    user_data[str(chat_id)] = {
        "chat_id": chat_id,
        "state": "ready",
        "gender": parsed["gender"],
        "category": parsed["category"],
        "shoes_size": parsed["shoes_size"],
        "clothing_size": parsed["clothing_size"],
        "price_min": parsed["price_min"],
        "price_max": parsed["price_max"],
    }

    gender_label = {"men": "גברים", "women": "נשים", "kids": "ילדים"}[parsed["gender"]]
    category_label = {"shoes": "הנעלה", "clothing": "ביגוד", "both": "גם וגם"}[parsed["category"]]

    size_part = []
    if parsed["category"] in ("shoes", "both"):
        size_part.append(f"נעליים: {parsed['shoes_size']}")
    if parsed["category"] in ("clothing", "both"):
        size_part.append(f"ביגוד: {parsed['clothing_size']}")

    send_message(
        chat_id,
        "✅ <b>הגדרות נשמרו בהצלחה!</b>\n\n"
        f"מגדר: <b>{gender_label}</b>\n"
        f"סוג מוצר: <b>{category_label}</b>\n"
        f"מידה: <b>{' | '.join(size_part)}</b>\n"
        f"טווח מחירים: <b>{parsed['price_min']} - {parsed['price_max']} ₪</b>\n\n"
        "🕖 מוצרים נשלחים פעמיים ביום (שעון ישראל): <b>07:00</b> ו-<b>19:00</b>\n"
    )


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is missing. Set it in GitHub Secrets.")

    log("=== telegram_onboarding.py starting ===")

    user_data = load_json(USER_DATA_FILE, {})
    last_obj = load_json(LAST_UPDATE_ID_FILE, {"last_update_id": 0})

    last_update = last_obj.get("last_update_id")
    if not isinstance(last_update, int):
        last_update = 0

    params = {"offset": last_update + 1, "allowed_updates": ["message"]}

    log(f"Calling getUpdates with params: {params}")
    r = requests.get(f"{API}/getUpdates", params=params, timeout=30)
    log(f"getUpdates HTTP status: {r.status_code}")

    data = r.json()
    if not data.get("ok"):
        raise SystemExit(f"Telegram getUpdates failed: {data}")

    updates = data.get("result", [])
    log(f"getUpdates returned {len(updates)} updates")

    max_update_id = last_update

    for upd in updates:
        uid = upd.get("update_id")
        if isinstance(uid, int):
            max_update_id = max(max_update_id, uid)

        msg = upd.get("message") or upd.get("edited_message")
        if not msg:
            continue

        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        text = msg.get("text", "")

        if not isinstance(chat_id, int):
            continue

        handle_message(chat_id, text, user_data)

    save_json(USER_DATA_FILE, user_data)
    save_json(LAST_UPDATE_ID_FILE, {"last_update_id": max_update_id})

    log(f"Onboarding sync done. New last_update_id: {max_update_id}")


if __name__ == "__main__":
    main()