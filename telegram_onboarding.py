# telegram_onboarding.py
import json
import os
import re
import requests

USER_DATA_FILE = "user_data.json"
LAST_UPDATE_ID_FILE = "last_update_id.json"

TELEGRAM_BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or "").strip()
ENABLE_DEBUG_LOGS = True

API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

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
    # IMPORTANT: no parse_mode to avoid "can't parse entities" errors
    url = f"{API}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    r = requests.post(url, data=payload, timeout=30)
    log(f"send_message to {chat_id} -> {r.status_code}")
    return r

def parse_one_line(text: str):
    """
    Expected:
    <gender> <type> <size> <min_price> <max_price>

    gender: 1/2/3
    type: A/B/C

    size:
    - A: shoe size numeric (e.g. 43)
    - B: clothing size (XS,S,M,L,XL,XXL,XXXL)
    - C: shoeSize/clothingSize e.g. 40/L
    """
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

    log(f"handle_message chat_id={chat_id} text='{text}'")

    # Ensure user entry exists
    user = user_data.get(str(chat_id), {"chat_id": chat_id})
    user_data[str(chat_id)] = user

    if text == "/reset":
        user_data[str(chat_id)] = {"chat_id": chat_id, "state": "awaiting_setup", "welcome_sent": False}
        send_message(chat_id, "✅ בוצע איפוס. שלח /start ואז את ההודעה בפורמט הנכון.")
        return

    if text == "/sync":
        # "mark and clear" - implemented in main by setting a flag
        user["request_sync"] = True
        send_message(chat_id, "✅ Sync requested. I will clear backlog on next run.")
        return

    if text == "/stat":
        total = len(user_data)
        ready = sum(1 for v in user_data.values() if v.get("state") == "ready")
        awaiting = total - ready
        send_message(
            chat_id,
            f"📊 סטטוס בוט\n\nTotal users: {total}\nReady: {ready}\nAwaiting setup: {awaiting}"
        )
        return

    if text == "/start":
        # Send welcome only once unless reset
        if not user.get("welcome_sent"):
            send_message(chat_id, WELCOME_TEXT)
            user["welcome_sent"] = True
            user["state"] = user.get("state") or "awaiting_setup"
        else:
            send_message(
                chat_id,
                "ℹ️ ההוראות כבר נשלחו בעבר.\n"
                "שלח הודעה בפורמט: 1 A 43 128 299\n"
                "או /reset כדי להתחיל מחדש."
            )
        return

    parsed = parse_one_line(text)
    if not parsed:
        send_message(
            chat_id,
            "❌ פורמט לא תקין.\n\n"
            "דוגמה: 1 A 43 128 299\n"
            "דוגמה ל-C: 2 C 40/L 0 800\n"
            "אפשר לשלוח /start כדי לראות שוב את ההוראות."
        )
        return

    user_data[str(chat_id)] = {
        "chat_id": chat_id,
        "state": "ready",
        "welcome_sent": True,
        "gender": parsed["gender"],
        "category": parsed["category"],
        "shoes_size": parsed["shoes_size"],
        "clothing_size": parsed["clothing_size"],
        "price_min": parsed["price_min"],
        "price_max": parsed["price_max"],
    }

    gender_label = {"men": "גברים", "women": "נשים", "kids": "ילדים"}[parsed["gender"]]
    category_label = {"shoes": "הנעלה", "clothing": "ביגוד", "both": "גם וגם"}[parsed["category"]]

    size_lines = []
    if parsed["category"] in ("shoes", "both"):
        size_lines.append(f"מידה נעליים: {parsed['shoes_size']}")
    if parsed["category"] in ("clothing", "both"):
        size_lines.append(f"מידה ביגוד: {parsed['clothing_size']}")

    confirm = (
        "✅ הגדרות נשמרו בהצלחה!\n\n"
        f"מגדר: {gender_label}\n"
        f"סוג מוצר: {category_label}\n"
        + "\n".join(size_lines) + "\n"
        f"טווח מחירים: {parsed['price_min']} - {parsed['price_max']} ₪\n\n"
        "🕖 מוצרים נשלחים פעמיים ביום (שעון ישראל): 07:00 ו-19:00"
    )
    send_message(chat_id, confirm)

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("Missing TELEGRAM_BOT_TOKEN in GitHub Secrets.")

    log("=== telegram_onboarding.py starting ===")

    user_data = load_json(USER_DATA_FILE, {})
    last_obj = load_json(LAST_UPDATE_ID_FILE, {"last_update_id": 0})

    last_update = last_obj.get("last_update_id")
    if not isinstance(last_update, int):
        last_update = 0

    # If any user requested /sync, we clear backlog by jumping to latest update_id
    sync_requested = any(v.get("request_sync") for v in user_data.values())

    if sync_requested:
        # Fetch latest updates without processing them, just to get max update_id
        r = requests.get(f"{API}/getUpdates", params={}, timeout=30)
        data = r.json()
        updates = data.get("result", [])
        max_update_id = last_update
        for upd in updates:
            uid = upd.get("update_id")
            if isinstance(uid, int):
                max_update_id = max(max_update_id, uid)

        # Clear sync flag and save
        for v in user_data.values():
            v.pop("request_sync", None)

        save_json(USER_DATA_FILE, user_data)
        save_json(LAST_UPDATE_ID_FILE, {"last_update_id": max_update_id})
        log(f"Sync done. Backlog cleared. last_update_id={max_update_id}")
        return

    params = {}
    if last_update >= 0:
        params["offset"] = last_update + 1

    log(f"Calling getUpdates with params: {params}")
    r = requests.get(f"{API}/getUpdates", params=params, timeout=30)
    log(f"getUpdates status: {r.status_code}")

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

        chat_id = (msg.get("chat") or {}).get("id")
        text = msg.get("text", "")

        if isinstance(chat_id, int):
            handle_message(chat_id, text, user_data)

    save_json(USER_DATA_FILE, user_data)
    save_json(LAST_UPDATE_ID_FILE, {"last_update_id": max_update_id})

    log(f"Onboarding done. last_update_id={max_update_id}")

if __name__ == "__main__":
    main()
