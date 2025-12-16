import os
import json
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

USER_DATA_FILE = "user_data.json"
OFFSET_FILE = "last_update_id.json"


def telegram_url(method: str) -> str:
    """בונה URL לקריאה ל-Telegram API."""
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


def ask_gender(chat_id):
    text = (
        "ברוך הבא לבוט טימברלנד 👟\n\n"
        "בחר קטגוריית קהל היעד:\n"
        "1 - גברים\n"
        "2 - נשים\n"
        "3 - ילדים"
    )
    send_message(chat_id, text)


def ask_category(chat_id):
    text = (
        "מה תרצה לעקוב?\n"
        "1 - הנעלה בלבד\n"
        "2 - ביגוד בלבד\n"
        "3 - גם וגם"
    )
    send_message(chat_id, text)


def ask_size(chat_id):
    text = "הקלד את המידה שלך (למשל: 43):"
    send_message(chat_id, text)


def ask_price_min(chat_id):
    text = "הקלד מחיר מינימלי (למשל: 0):"
    send_message(chat_id, text)


def ask_price_max(chat_id):
    text = "הקלד מחיר מקסימלי (למשל: 300):"
    send_message(chat_id, text)


def confirm_preferences(chat_id, prefs):
    text = (
        "הגדרות המעקב שלך נשמרו ✅\n\n"
        f"קטגוריית קהל היעד: {prefs.get('gender')}\n"
        f"סוג מוצרים: {prefs.get('category')}\n"
        f"מידה: {prefs.get('size')}\n"
        f"מחיר: {prefs.get('price_min')} - {prefs.get('price_max')}\n\n"
        "מהיום תקבל התראות בהתאם להגדרות האלו 🚀\n"
        "כדי לעדכן הגדרות בכל רגע - שלח /start"
    )
    send_message(chat_id, text)


def handle_message(chat_id, text, user_data):
    text = text.strip()
    chat_id_str = str(chat_id)

    print(f"handle_message: chat_id={chat_id_str}, text={text!r}")

    # משתמש חדש - יצירת רשומה והתחלת שאלון
    if chat_id_str not in user_data:
        print(f"New user detected: {chat_id_str}")
        user_data[chat_id_str] = {
            "state": "awaiting_gender",
            "gender": None,
            "category": None,
            "size": None,
            "price_min": None,
            "price_max": None
        }
        ask_gender(chat_id)
        return

    user = user_data[chat_id_str]
    state = user.get("state", "awaiting_gender")
    print(f"Existing user state={state}")

    # התחלה מחדש
    if text == "/start":
        print(f"Resetting user {chat_id_str} to start state")
        user.update({
            "state": "awaiting_gender",
            "gender": None,
            "category": None,
            "size": None,
            "price_min": None,
            "price_max": None
        })
        ask_gender(chat_id)
        return

    if state == "awaiting_gender":
        if text == "1":
            user["gender"] = "men"
        elif text == "2":
            user["gender"] = "women"
        elif text == "3":
            user["gender"] = "kids"
        else:
            send_message(chat_id, "אנא בחר 1, 2 או 3.")
            return

        user["state"] = "awaiting_category"
        ask_category(chat_id)

    elif state == "awaiting_category":
        if text == "1":
            user["category"] = "shoes"
        elif text == "2":
            user["category"] = "clothing"
        elif text == "3":
            user["category"] = "both"
        else:
            send_message(chat_id, "אנא בחר 1, 2 או 3.")
            return

        user["state"] = "awaiting_size"
        ask_size(chat_id)

    elif state == "awaiting_size":
        user["size"] = text
        user["state"] = "awaiting_price_min"
        ask_price_min(chat_id)

    elif state == "awaiting_price_min":
        if not text.isdigit():
            send_message(chat_id, "אנא הקלד מספר בלבד (למשל 0).")
            return
        user["price_min"] = int(text)
        user["state"] = "awaiting_price_max"
        ask_price_max(chat_id)

    elif state == "awaiting_price_max":
        if not text.isdigit():
            send_message(chat_id, "אנא הקלד מספר בלבד (למשל 300).")
            return
        user["price_max"] = int(text)
        user["state"] = "ready"
        confirm_preferences(chat_id, user)

    else:
        # משתמש שסיים onboarding
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
