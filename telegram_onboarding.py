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

    # משתמש חדש - יצירת רשומה וה
