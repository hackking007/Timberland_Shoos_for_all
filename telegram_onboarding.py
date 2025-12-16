import os
import json
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

USER_DATA_FILE = "user_data.json"
OFFSET_FILE = "last_update_id.json"


def telegram_url(method: str) -> str:
    return f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def send_message(chat_id, text):
    if not BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN is not set - cannot send_message")
        return

    try:
        resp = requests.post(
            telegram_url("sendMessage"),
            json={"chat_id": chat_id, "text": text},
            timeout=30
        )
        print(f"send_message to {chat_id} -> status {resp.status_code}")
        if not resp.ok:
            print("send_message response text:", resp.text)
    except Exception as e:
        print(f"Error sending message to {chat_id}: {e}")


def send_instructions(chat_id):
    text = (
        "ברוך הבא לבוט טימברלנד 👟\n\n"
        "כדי להגדיר מעקב בהודעה אחת, אנא שלח הודעה בפורמט הבא:\n\n"
        "מגדר, סוג מוצרים, מידה, מחיר מינימלי, מחיר מקסימלי\n\n"
        "קידודים:\n"
        "מגדר: 1=גברים, 2=נשים, 3=ילדים\n"
        "סוג מוצרים: A=הנעלה, B=ביגוד, C=גם וגם\n\n"
        "לדוגמה:\n"
        "1 A 43 0 300\n"
        "זה אומר: גברים, הנעלה, מידה 43, מחיר 0 עד 300.\n\n"
        "שלח עכשיו הודעה אחת בפורמט הזה 🙂"
    )
    send_message(chat_id, text)


def confirm_preferences(chat_id, prefs):
    gender_map_he = {"men": "גברים", "women": "נשים", "kids": "ילדים"}
    category_map_he = {
        "shoes": "הנעלה",
        "clothing": "ביגוד",
        "both": "הנעלה + ביגוד"
    }

    text = (
        "הגדרות המעקב שלך נשמרו ✅\n\n"
        f"קטגוריית קהל היעד: {gender_map_he.get(prefs.get('gender'), prefs.get('gender'))}\n"
        f"סוג מוצרים: {category_map_he.get(prefs.get('category'), prefs.get('category'))}\n"
        f"מידה: {prefs.get('size')}\n"
        f"מחיר: {prefs.get('price_min')} - {prefs.get('price_max')}\n\n"
        "מהיום תקבל התראות בהתאם להגדרות האלו 🚀\n"
        "כדי לעדכן הגדרות בכל רגע - שלח /start וענה שוב בפורמט החדש."
    )
    send_message(chat_id, text)


def parse_combined_message(text):
    """
    מצפה לפורמט:
    gender category size price_min price_max
    לדוגמה: 1 A 43 0 300
    מחזיר dict עם הערכים או None אם לא תקין.
    """
    # מחליף פסיקים ברווחים, מפרק לפי רווח
    clean = text.replace(",", " ")
    parts = [p for p in clean.split() if p]

    if len(parts) != 5:
        return None, "אנא הזן בדיוק 5 ערכים, לדוגמה: 1 A 43 0 300"

    gender_raw, category_raw, size_raw, price_min_raw, price_max_raw = parts

    # מגדר
    if gender_raw not in ("1", "2", "3"):
        return None, "מגדר לא תקין. השתמש ב-1 לגברים, 2 לנשים, 3 לילדים."

    gender_map = {"1": "men", "2": "women", "3": "kids"}
    gender = gender_map[gender_raw]

    # קטגוריה
    category_raw_upper = category_raw.upper()
    if category_raw_upper not in ("A", "B", "C"):
        return None, "סוג מוצרים לא תקין. השתמש ב-A להנעלה, B לביגוד, C גם וגם."

    category_map = {"A": "shoes", "B": "clothing", "C": "both"}
    category = category_map[category_raw_upper]

    # מידה - נשמור כטקסט, אתה כבר תמפה ל-size_id בטימברלנד
    size = size_raw

    # מחירים
    if not (price_min_raw.isdigit() and price_max_raw.isdigit()):
        return None, "מחירים חייבים להיות מספרים בלבד. לדוגמה: 0 300"

    price_min = int(price_min_raw)
    price_max = int(price_max_raw)

    if price_min > price_max:
        return None, "המחיר המינימלי לא יכול להיות גדול מהמחיר המקסימלי."

    prefs = {
        "gender": gender,
        "category": category,
        "size": size,
        "price_min": price_min,
        "price_max": price_max,
    }
    return prefs, None


def handle_message(chat_id, text, user_data):
    text = text.strip()
    chat_id_str = str(chat_id)

    print(f"handle_message: chat_id={chat_id_str}, text={text!r}")

    # אם אין משתמש - ניצור לו רשומה ונבקש הודעה משולבת
    if chat_id_str not in user_data:
        user_data[chat_id_str] = {
            "state": "awaiting_combined",
            "gender": None,
            "category": None,
            "size": None,
            "price_min": None,
            "price_max": None
        }
        send_instructions(chat_id)
        return

    user = user_data[chat_id_str]
    state = user.get("state", "awaiting_combined")
    print(f"Existing user state={state}")

    # התחלה מחדש
    if text == "/start":
        user.update({
            "state": "awaiting_combined",
            "gender": None,
            "category": None,
            "size": None,
            "price_min": None,
            "price_max": None
        })
        send_instructions(chat_id)
        return

    if state == "awaiting_combined":
        prefs, error = parse_combined_message(text)
        if error:
            send_message(chat_id, error + "\n\nנסה שוב בפורמט לדוגמה: 1 A 43 0 300")
            return

        # שמירת ההעדפות
        user.update(prefs)
        user["state"] = "ready"
        confirm_preferences(chat_id, user)
        return

    # כבר ready
    send_message(chat_id, "אתה כבר רשום. שלח /start כדי לעדכן הגדרות.")


def main():
    print("=== telegram_onboarding.py starting ===")
    if not BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN is not set in environment!")
        return

    print("BOT_TOKEN seems to be set (length:", len(BOT_TOKEN), ")")

    user_data = load_json(USER_DATA_FILE, {})
    print("Loaded user_data keys:", list(user_data.keys()))

    offset_data = load_json(OFFSET_FILE, {"last_update_id": None})
    last_update_id = offset_data.get("last_update_id")
    print("Last update id from file:", last_update_id)

    params = {}
    if last_update_id is not None:
        params["offset"] = last_update_id + 1

    print("Calling getUpdates with params:", params)

    try:
        resp = requests.get(telegram_url("getUpdates"), params=params, timeout=30)
    except Exception as e:
        print("Error calling getUpdates:", e)
        return

    print("getUpdates HTTP status:", resp.status_code)
    print("getUpdates raw text:", resp.text)

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
        print("Processing update_id:", u_id)
        if u_id > max_update_id:
            max_update_id = u_id

        message = update.get("message") or update.get("edited_message")
        if not message:
            print("Update has no message field, skipping.")
            continue

        chat = message.get("chat", {})
        chat_id = chat.get("id")
        text = message.get("text", "")

        print("Raw message from Telegram:", json.dumps(message, indent=2, ensure_ascii=False))

        if not chat_id or not text:
            print("Message has no chat_id or text, skipping.")
            continue

        handle_message(chat_id, text, user_data)

    save_json(USER_DATA_FILE, user_data)
    save_json(OFFSET_FILE, {"last_update_id": max_update_id})
    print("Onboarding sync done. New last_update_id:", max_update_id)


if __name__ == "__main__":
    main()
