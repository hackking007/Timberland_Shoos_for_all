# telegram_onboarding.py - FIXED VERSION
import json
import os
import re
import time
import requests

USER_DATA_FILE = "user_data.json"
LAST_UPDATE_ID_FILE = "last_update_id.json"

TELEGRAM_BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or "").strip()
API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

ENABLE_DEBUG_LOGS = True

# FIXED: Increased message age limit to 24 hours
MAX_MESSAGE_AGE_SECONDS = 24 * 60 * 60  # 24 hours instead of 15 minutes

WELCOME_TEXT = (
    "👟 ברוך הבא לבוט טימברלנד\n\n"
    "כדי להגדיר מעקב מותאם אישית בהודעה אחת, שלחו לבוט הודעה בפורמט הבא:\n\n"
    "<gender> <type> <size> <min_price> <max_price>\n\n"
    "קידודים\n"
    "gender:\n"
    "1 - גברים\n"
    "2 - נשים\n"
    "3 - ילדים\n\n"
    "type:\n"
    "A - הנעלה\n"
    "B - ביגוד\n"
    "C - גם וגם\n\n"
    "דוגמה\n"
    "1 A 43 128 299\n\n"
    "שים לב לגבי C (גם וגם)\n"
    "כדי שלא נשבור מידות שונות, שלח מידה בפורמט shoeSize/clothingSize\n"
    "לדוגמה:\n"
    "2 C 40/L 0 800\n\n"
    "🕖 שעות שליחת מוצרים (שעון ישראל):\n"
    "07:00 ו-19:00"
)

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
        "disable_web_page_preview": True,
    }
    r = requests.post(url, data=payload, timeout=30)
    log(f"send_message to {chat_id} -> status {r.status_code}")
    return r

def parse_one_line(text: str):
    parts = text.strip().split()
    if len(parts) != 5:
        return None

    gender_code, type_code, size_raw, min_p, max_p = parts
    type_code = type_code.upper()

    if gender_code not in ("1", "2", "3"):
        return None
    if type_code not in ("A", "B", "C"):
        return None

    try:
        price_min = int(min_p)
        price_max = int(max_p)
        if price_min < 0 or price_max < 0 or price_min > price_max:
            return None
    except Exception:
        return None

    gender = {"1": "men", "2": "women", "3": "kids"}[gender_code]
    category = {"A": "shoes", "B": "clothing", "C": "both"}[type_code]

    shoes_size = None
    clothing_size = None

    if category == "shoes":
        if not re.fullmatch(r"\d{2}", size_raw):
            return None
        shoes_size = size_raw

    elif category == "clothing":
        s = size_raw.upper()
        if s not in ("XS", "S", "M", "L", "XL", "XXL", "XXXL"):
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
        if b not in ("XS", "S", "M", "L", "XL", "XXL", "XXXL"):
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
    if text == "":
        return

    log(f"Processing message from {chat_id}: {text}")

    user = user_data.get(str(chat_id), {"chat_id": chat_id, "state": "awaiting_setup", "welcome_sent": False})
    user_data[str(chat_id)] = user

    # Commands
    if text == "/reset":
        user_data[str(chat_id)] = {"chat_id": chat_id, "state": "awaiting_setup", "welcome_sent": False}
        send_message(chat_id, "鉁?讘讜爪注 讗讬驻讜住. 砖诇讞 /start 讜讗讝 讗转 讛讛讜讚注讛 讘驻讜专诪讟 讛谞讻讜谉.")
        return

    if text == "/stat":
        total = len(user_data)
        ready = sum(1 for v in user_data.values() if v.get("state") == "ready")
        awaiting = total - ready
        send_message(chat_id, f"馃搳 住讟讟讜住 讘讜讟\n\nTotal users: {total}\nReady: {ready}\nAwaiting setup: {awaiting}")
        return

    if text == "/start":
        send_message(chat_id, WELCOME_TEXT)
        user["welcome_sent"] = True
        return

    # Parse setup message
    parsed = parse_one_line(text)
    if not parsed:
        if user.get("state") != "ready":
            send_message(
                chat_id,
                "鉂?驻讜专诪讟 诇讗 转拽讬谉.\n\n"
                "讚讜讙诪讛: 1 A 43 128 299\n"
                "讚讜讙诪讛 诇-C: 2 C 40/L 0 800\n"
                "讗驻砖专 诇砖诇讜讞 /start 讻讚讬 诇专讗讜转 砖讜讘 讗转 讛讛讜专讗讜转."
            )
        return

    # Save user preferences
    user_data[str(chat_id)] = {
        "chat_id": chat_id,
        "state": "ready",
        "welcome_sent": True,
        "gender": parsed["gender"],
        "category": parsed["category"],
        "shoes_size": parsed.get("shoes_size"),
        "clothing_size": parsed.get("clothing_size"),
        "price_min": parsed["price_min"],
        "price_max": parsed["price_max"],
    }

    log(f"User {chat_id} registered: {parsed}")

    gender_label = {"men": "讙讘专讬诐", "women": "谞砖讬诐", "kids": "讬诇讚讬诐"}[parsed["gender"]]
    category_label = {"shoes": "讛谞注诇讛", "clothing": "讘讬讙讜讚", "both": "讙诐 讜讙诐"}[parsed["category"]]

    lines = [
        "鉁?讛讙讚专讜转 谞砖诪专讜 讘讛爪诇讞讛!",
        "",
        f"诪讙讚专: {gender_label}",
        f"住讜讙 诪讜爪专: {category_label}",
    ]
    if parsed["category"] in ("shoes", "both"):
        lines.append(f"诪讬讚讛 谞注诇讬讬诐: {parsed['shoes_size']}")
    if parsed["category"] in ("clothing", "both"):
        lines.append(f"诪讬讚讛 讘讬讙讜讚: {parsed['clothing_size']}")
    lines += [
        f"讟讜讜讞 诪讞讬专讬诐: {parsed['price_min']} - {parsed['price_max']} 鈧?,
        "",
        "馃晼 诪讜爪专讬诐 谞砖诇讞讬诐 驻注诪讬讬诐 讘讬讜诐 (砖注讜谉 讬砖专讗诇): 07:00 讜-19:00",
    ]
    send_message(chat_id, "\n".join(lines))

def get_updates(offset: int):
    params = {"offset": offset}
    r = requests.get(f"{API}/getUpdates", params=params, timeout=30)
    data = r.json()
    if not data.get("ok"):
        raise SystemExit(f"Telegram getUpdates failed: {data}")
    return data.get("result", [])

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("Missing TELEGRAM_BOT_TOKEN in GitHub Secrets.")

    log("=== telegram_onboarding.py starting ===")

    user_data = load_json(USER_DATA_FILE, {})
    last_obj = load_json(LAST_UPDATE_ID_FILE, {"last_update_id": 0})

    last_update = last_obj.get("last_update_id")
    if not isinstance(last_update, int):
        last_update = 0

    # Get all updates
    updates = get_updates(last_update + 1)
    log(f"getUpdates returned {len(updates)} updates")

    if not updates:
        return

    # Process all messages (not just newest per chat)
    max_update_id = last_update
    now_ts = int(time.time())

    for upd in updates:
        uid = upd.get("update_id")
        if isinstance(uid, int):
            max_update_id = max(max_update_id, uid)

        msg = upd.get("message") or upd.get("edited_message")
        if not msg:
            continue

        chat_id = (msg.get("chat") or {}).get("id")
        if not isinstance(chat_id, int):
            continue

        msg_date = msg.get("date")
        if isinstance(msg_date, int):
            if now_ts - msg_date > MAX_MESSAGE_AGE_SECONDS:
                log(f"Skipping old message from {chat_id}")
                continue

        text = msg.get("text", "")
        handle_message(chat_id, text, user_data)

    save_json(USER_DATA_FILE, user_data)
    save_json(LAST_UPDATE_ID_FILE, {"last_update_id": max_update_id})
    log(f"Onboarding done. last_update_id={max_update_id}, users={len(user_data)}")

if __name__ == "__main__":
    main()
