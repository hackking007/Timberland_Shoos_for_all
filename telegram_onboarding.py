# telegram_onboarding.py
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

# אם יש backlog ישן, לא רוצים לענות עליו ולהציף
# (רלוונטי במיוחד אם last_update_id התאפס בגלל artifact missing)
AUTO_CLEAR_BACKLOG_IF_LAST_ID_ZERO = True

# לא מעבדים הודעות ישנות מאוד (מונע "שיחזור" של ספאם)
# Telegram message.date הוא epoch seconds
MAX_MESSAGE_AGE_SECONDS = 24 * 60 * 60  # 24 hours

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
    """
    Expected:
    <gender> <type> <size> <min_price> <max_price>

    gender: 1/2/3
    type: A/B/C

    size:
    - A: 2 digits shoe size, e.g. 43
    - B: XS/S/M/L/XL/XXL/XXXL
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
        if not re.fullmatch(r"\d{1,2}", size_raw):
            return None
        # Validate reasonable shoe size range (including kids)
        size_num = int(size_raw)
        if size_num < 1 or size_num > 50:
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
        if not re.fullmatch(r"\d{1,2}", a):
            return None
        # Validate reasonable shoe size range (including kids)
        size_num = int(a)
        if size_num < 1 or size_num > 50:
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

    user = user_data.get(str(chat_id), {"chat_id": chat_id, "state": "awaiting_setup", "welcome_sent": False})
    user_data[str(chat_id)] = user

    # Commands (always)
    if text == "/reset":
        user_data[str(chat_id)] = {"chat_id": chat_id, "state": "awaiting_setup", "welcome_sent": False}
        send_message(chat_id, "Reset completed. Send /start and then your setup message.")
        return

    if text == "/stat":
        total = len(user_data)
        ready = sum(1 for v in user_data.values() if v.get("state") == "ready")
        awaiting = total - ready
        send_message(chat_id, f"Bot Status\n\nTotal users: {total}\nReady: {ready}\nAwaiting setup: {awaiting}")
        return

    if text == "/start":
        # רק אם לא נשלח בעבר, כדי לא להציף
        if not user.get("welcome_sent"):
            send_message(chat_id, WELCOME_TEXT)
            user["welcome_sent"] = True
        else:
            send_message(
                chat_id,
                "ℹ️ ההוראות כבר נשלחו בעבר.\n"
                "שלח הודעה בפורמט: 1 A 43 128 299\n"
                "או /reset כדי להתחיל מחדש."
            )
        return

    # אם המשתמש כבר READY - לא מציפים אותו ב"פורמט לא תקין" על הודעות ישנות/אקראיות
    # רק אם הוא שולח פורמט תקין - נעדכן. אחרת - נתעלם בשקט.
    parsed = parse_one_line(text)
    if not parsed:
        if user.get("state") != "ready":
            send_message(
                chat_id,
                "Invalid format.\n\n"
                "Example: 1 A 43 128 299\n"
                "Example for C: 2 C 40/L 0 800\n"
                "Send /start to see instructions again."
            )
        return

    # Save preferences
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

    gender_label = {"men": "Men", "women": "Women", "kids": "Kids"}[parsed["gender"]]
    category_label = {"shoes": "Shoes", "clothing": "Clothing", "both": "Both"}[parsed["category"]]

    lines = [
        "Settings saved successfully!",
        "",
        f"Gender: {gender_label}",
        f"Category: {category_label}",
    ]
    if parsed["category"] in ("shoes", "both"):
        lines.append(f"Shoe size: {parsed['shoes_size']}")
    if parsed["category"] in ("clothing", "both"):
        lines.append(f"Clothing size: {parsed['clothing_size']}")
    lines += [
        f"Price range: {parsed['price_min']} - {parsed['price_max']} NIS",
        "",
        "Products sent twice daily (Israel time): 07:00 and 19:00",
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
    log(f"getUpdates returned {len(updates)} updates (last_update_id: {last_update})")

    if not updates:
        log("No new updates to process")
        return

    # Process all messages (not just newest per chat)
    max_update_id = last_update
    now_ts = int(time.time())
    processed_count = 0
    
    # Check if this is first run with init_time
    init_time = last_obj.get("init_time")
    is_first_run = (last_update == 0 and init_time is not None)
    
    log(f"Processing mode: {'first_run' if is_first_run else 'normal'}, init_time: {init_time}")

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

        # Skip old messages based on different logic
        msg_date = msg.get("date")
        if isinstance(msg_date, int):
            if is_first_run and init_time:
                # On first run, only process messages from last hour
                if msg_date < init_time:
                    log(f"Skipping old message from {chat_id} (before init_time)")
                    continue
            elif last_update == 0:
                # Fallback: skip very old messages
                if now_ts - msg_date > MAX_MESSAGE_AGE_SECONDS:
                    log(f"Skipping old message from {chat_id} (age: {now_ts - msg_date}s)")
                    continue

        text = msg.get("text", "")
        handle_message(chat_id, text, user_data)
        processed_count += 1

    save_json(USER_DATA_FILE, user_data)
    save_json(LAST_UPDATE_ID_FILE, {"last_update_id": max_update_id})
    log(f"Onboarding done. Processed {processed_count} messages from {len(updates)} updates")
    log(f"Updated last_update_id from {last_update} to {max_update_id}")
    log(f"Total users: {len(user_data)}")
    
    # Debug: show user states
    for user_id, user in user_data.items():
        log(f"User {user_id}: state={user.get('state')}, ready={user.get('state') == 'ready'}")
    
    if processed_count == 0:
        log("No messages were processed - likely all were duplicates or too old")
    
    log(f"State saved with last_update_id: {max_update_id}")

if __name__ == "__main__":
    main()
