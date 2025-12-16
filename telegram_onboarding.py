import os
import json
import requests

# Telegram bot token from GitHub Secrets
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# State files
USER_DATA_FILE = "user_data.json"
OFFSET_FILE = "last_update_id.json"


def telegram_url(method: str) -> str:
    return f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"


def load_json(path, default):
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving {path}: {e}")


def send_message(chat_id, text):
    if not BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN is not set - cannot send_message")
        return

    try:
        resp = requests.post(
            telegram_url("sendMessage"),
            json={"chat_id": chat_id, "text": text},
            timeout=20,
        )
        print(f"send_message to {chat_id} -> status {resp.status_code}")
        if not resp.ok:
            print("send_message response text:", resp.text)
    except Exception as e:
        print(f"Error sending message to {chat_id}: {e}")


def send_instructions(chat_id):
    text = (
        "ברוך הבא לבוט טימברלנד 👟\n\n"
        "כדי להגדיר מעקב בהודעה אחת, שלח הודעה בפורמט הבא:\n\n"
        "<gender> <type> <size> <min_price> <max_price>\n\n"
        "הסבר:\n"
        "gender:\n"
        "  1 = גברים\n"
        "  2 = נשים\n"
        "  3 = ילדים\n\n"
        "type:\n"
        "  A = הנעלה\n"
        "  B = ביגוד\n"
        "  C = גם וגם\n\n"
        "דוגמה:\n"
        "1 A 43 0 300\n"
        "זה אומר: גברים, הנעלה, מידה 43, מחיר 0 עד 300 ₪."
    )
    send_message(chat_id, text)


def parse_combined_message(text):
    """
    מצפה לפורמט:
    <gender> <type> <size> <min_price> <max_price>

    gender:
        1 = men
        2 = women
        3 = kids

    type:
        A = shoes
        B = clothing
        C = both

    example:
        '1 A 43 0 300'
    """
    clean = text.strip().replace(",", " ")
    parts = [p for p in clean.split() if p]

    if len(parts) != 5:
        return None, (
            "❗ פורמט לא תקין.\n"
            "אנא השתמש בפורמט: 1 A 43 0 300\n"
            "gender: 1/2/3, type: A/B/C, מידה, מינימום, מקסימום."
        )

    gender_raw, type_raw, size_raw, min_raw, max_raw = parts

    gender_map = {"1": "men", "2": "women", "3": "kids"}
    gender = gender_map.get(gender_raw)
    if not gender:
        return None, "ערך gender לא תקין. השתמש ב-1 לגברים, 2 לנשים, 3 לילדים."

    type_map = {
        "A": "shoes",
        "B": "clothing",
        "C": "both",
    }
    category = type_map.get(type_raw.upper())
    if not category:
        return None, "ערך type לא תקין. השתמש ב-A/B/C."

    size = size_raw.strip()
    if not size:
        return None, "מידה לא תקינה."

    if not (min_raw.isdigit() and max_raw.isdigit()):
        return None, "המחירים חייבים להיות מספרים בלבד."

    price_min = int(min_raw)
    price_max = int(max_raw)
    if price_min > price_max:
        return None, "המחיר המינימלי לא יכול להיות גדול מהמקסימלי."

    prefs = {
        "gender": gender,          # men / women / kids
        "category": category,      # shoes / clothing / both
        "size": size,              # נשמר כמחרוזת
        "price_min": price_min,
        "price_max": price_max,
    }
    return prefs, None


def handle_message(chat_id, text, user_data):
    text = text.strip()
    chat_id_str = str(chat_id)

    print(f"handle_message: chat_id={chat_id_str}, text={text!r}")

    # /start רק שולח הסבר
    if text == "/start":
        send_instructions(chat_id)
        return

    prefs, error = parse_combined_message(text)
    if error:
        send_message(chat_id, error + "\n\nדוגמה: 1 A 43 0 300")
        return

    # שמירה בפורמט שה-checker מצפה לו
    user_data[chat_id_str] = {
        "chat_id": chat_id,
        "state": "ready",
        **prefs,
    }

    save_json(USER_DATA_FILE, user_data)

    gender_he = {"men": "גברים", "women": "נשים", "kids": "ילדים"}
    category_he = {
        "shoes": "הנעלה",
        "clothing": "ביגוד",
        "both": "הנעלה + ביגוד",
    }

    text_confirm = (
        "🎉 ההגדרות נשמרו בהצלחה!\n\n"
        f"מגדר: {gender_he.get(prefs['gender'], prefs['gender'])}\n"
        f"סוג מוצר: {category_he.get(prefs['category'], prefs['category'])}\n"
        f"מידה: {prefs['size']}\n"
        f"טווח מחירים: {prefs['price_min']} - {prefs['price_max']} ₪\n\n"
        "הבוט יסרוק עבורך בסבב הקרוב וישלח עדכונים 👟"
    )
    send_message(chat_id, text_confirm)


def main():
    print("=== telegram_onboarding.py starting ===")

    if not BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN is not set in environment!")
        return

    user_data = load_json(USER_DATA_FILE, {})
    offset_data = load_json(OFFSET_FILE, {"last_update_id": None})
    last_update_id = offset_data.get("last_update_id")

    params = {}
    if last_update_id is not None:
        params["offset"] = last_update_id + 1

    print("Calling getUpdates with params:", params)

    try:
        resp = requests.get(telegram_url("getUpdates"), params=params, timeout=20)
    except Exception as e:
        print("Error calling getUpdates:", e)
        return

    print("getUpdates HTTP status:", resp.status_code)
    try:
        data = resp.json()
    except Exception as e:
        print("Error decoding JSON from getUpdates:", e)
        return

    if not data.get("ok"):
        print("Error from Telegram (ok=false):", data)
        return

    updates = data.get("result", [])
    print(f"getUpdates returned {len(updates)} updates")

    if not updates:
        print("No new updates.")
        return

    max_update_id = last_update_id or 0

    for update in updates:
        u_id = update["update_id"]
        if u_id > max_update_id:
            max_update_id = u_id

        message = update.get("message") or update.get("edited_message")
        if not message:
            continue

        chat = message.get("chat", {})
        chat_id = chat.get("id")
        text = message.get("text", "")

        if not chat_id or not text:
            continue

        handle_message(chat_id, text, user_data)

    save_json(OFFSET_FILE, {"last_update_id": max_update_id})
    print("Onboarding sync done. New last_update_id:", max_update_id)


if __name__ == "__main__":
    main()
