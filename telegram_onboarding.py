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

# Message age limit - only process recent messages on first run
MAX_MESSAGE_AGE_SECONDS = 10 * 60  # 10 minutes for first run, then all messages

# Message age limit - only process recent messages on first run
MAX_MESSAGE_AGE_SECONDS = 10 * 60  # 10 minutes for first run, then all messages

WELCOME_TEXT = (
    "Welcome to Timberland Bot\n\n"
    "To set up personalized tracking, send a message in this format:\n\n"
    "<gender> <type> <size> <min_price> <max_price>\n\n"
    "Codes:\n"
    "gender:\n"
    "1 - Men\n"
    "2 - Women\n"
    "3 - Kids\n\n"
    "type:\n"
    "A - Shoes\n"
    "B - Clothing\n"
    "C - Both\n\n"
    "Example:\n"
    "1 A 43 128 299\n\n"
    "Note for C (both):\n"
    "Use format shoeSize/clothingSize\n"
    "Example:\n"
    "2 C 40/L 0 800\n\n"
    "Products sent twice daily (Israel time):\n"
    "07:00 and 19:00"
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
    except (OSError, PermissionError, json.JSONEncodeError) as e:
        log(f"Error saving {path}: {e}")

def send_message(chat_id: int, text: str):
    url = f"{API}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text[:4096],  # Telegram message limit
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, data=payload, timeout=30)
        log(f"send_message to {chat_id} -> status {r.status_code}")
        return r
    except requests.exceptions.RequestException as e:
        log(f"Error sending message to {chat_id}: {e}")
        return None

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
        if not re.fullmatch(r"\d{1,2}", size_raw):
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
        send_message(chat_id, "Reset completed. Send /start and then your setup message.")
        return

    if text == "/stat":
        total = len(user_data)
        ready = sum(1 for v in user_data.values() if v.get("state") == "ready")
        awaiting = total - ready
        send_message(chat_id, f"Bot Status\n\nTotal users: {total}\nReady: {ready}\nAwaiting setup: {awaiting}")
        return

    if text == "/help":
        help_text = (
            "馃 Bot Commands:\n\n"
            "/start - Setup instructions\n"
            "/reset - Reset your preferences\n"
            "/stat - Bot statistics\n"
            "/alerts - Manage price alerts\n"
            "/share_XXXXX - Share product with friends\n\n"
            "馃搳 Smart Features:\n"
            "鈥?Price history tracking\n"
            "鈥?Lowest price alerts\n"
            "鈥?Stock notifications\n"
            "鈥?Product sharing"
        )
        send_message(chat_id, help_text)
        return
    
    if text == "/alerts":
        alerts_text = (
            "馃敂 Smart Alerts Active:\n\n"
            "馃搲 Price tracking - Get notified when prices drop\n"
            "馃搳 Price history - See lowest/highest prices\n"
            "馃摝 Stock alerts - Know when items restock\n"
            "馃挕 Share products - Send deals to friends\n\n"
            "All alerts are automatic based on your preferences!"
        )
        send_message(chat_id, alerts_text)
        return
    
    if text.startswith("/share_"):
        product_id = text.replace("/share_", "")
        share_text = (
            "馃摛 Share this product:\n\n"
            "Copy and send this message to your friends:\n\n"
            "馃憻 Check out this Timberland deal I found!\n"
            f"馃敆 Product ID: {product_id}\n\n"
            "馃 Get your own alerts: @YourTimberlandBot"
        )
        send_message(chat_id, share_text)
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
                "Invalid format.\n\n"
                "Example: 1 A 43 128 299\n"
                "Example for C: 2 C 40/L 0 800\n"
                "Send /start to see instructions again."
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
    
    log(f"Starting with last_update_id: {last_update}")
    
    # Simple approach: if last_update is 0, only process very recent messages
    if last_update == 0:
        log("First run - will only process recent messages (last 10 minutes)")
        # This will be handled by the age check below

    # Get all updates
    updates = get_updates(last_update + 1)
    log(f"getUpdates returned {len(updates)} updates (last_update_id: {last_update})")

    if not updates:
        log("No new updates to process")
        return
    
    # Filter out old updates that we might have already processed
    new_updates = [upd for upd in updates if upd.get("update_id", 0) > last_update]
    
    if not new_updates:
        log("All updates were already processed")
        # Still update the max_update_id to prevent reprocessing
        max_update_id = max(upd.get("update_id", 0) for upd in updates)
        save_json(LAST_UPDATE_ID_FILE, {"last_update_id": max_update_id})
        return
    
    log(f"Processing {len(new_updates)} new updates")
    updates = new_updates  # Use only new updates

    # Process all messages (not just newest per chat)
    max_update_id = last_update
    now_ts = int(time.time())
    processed_count = 0

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
                log(f"Skipping old message from {chat_id} (age: {now_ts - msg_date}s)")
                continue
        
        # Skip if we've already processed this exact update (double check)
        if uid and uid <= last_update:
            log(f"Skipping already processed update {uid} (last_update: {last_update})")
            continue

        text = msg.get("text", "")
        handle_message(chat_id, text, user_data)
        processed_count += 1

    save_json(USER_DATA_FILE, user_data)
    save_json(LAST_UPDATE_ID_FILE, {"last_update_id": max_update_id})
    log(f"Onboarding done. Processed {processed_count} messages from {len(updates)} updates")
    log(f"Updated last_update_id from {last_update} to {max_update_id}")
    log(f"Total users: {len(user_data)}")
    
    if processed_count == 0:
        log("No messages were processed - likely all were duplicates or too old")
    
    # Force save already handled by save_json above
    log(f"State saved with last_update_id: {max_update_id}")

if __name__ == "__main__":
    main()
