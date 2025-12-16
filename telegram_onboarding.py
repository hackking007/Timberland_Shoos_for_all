import os
import json
import requests
from config import USER_DATA_FILE, LAST_UPDATE_ID_FILE, TELEGRAM_BOT_TOKEN

API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# ---------------------------------------------
# Telegram helpers
# ---------------------------------------------
def send_message(chat_id, text):
    url = f"{API_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, data=payload, timeout=20)
    except Exception:
        pass


# ---------------------------------------------
# State helpers
# ---------------------------------------------
def load_user_data():
    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_user_data(data):
    try:
        with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass


def load_last_update_id():
    try:
        with open(LAST_UPDATE_ID_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("last_update_id")
    except:
        return None


def save_last_update_id(update_id):
    try:
        with open(LAST_UPDATE_ID_FILE, "w", encoding="utf-8") as f:
            json.dump({"last_update_id": update_id}, f)
    except:
        pass


# ---------------------------------------------
# Parse user message into preferences
# ---------------------------------------------
def parse_preference_message(msg: str):
    """
    Expected format:
    <gender> <product_type> <size> <min_price> <max_price>

    gender:
        1 = men
        2 = women
        3 = kids

    product_type:
        A = shoes
        B = clothing
        C = both  (treat as shoes for now, unless you want different behavior)

    Example:
        "1 A 43 0 300"
    """

    parts = msg.strip().split()

    if len(parts) != 5:
        return None

    gender_raw, prod_raw, size_raw, min_p_raw, max_p_raw = parts

    # ---- gender ----
    gender_map = {
        "1": "men",
        "2": "women",
        "3": "kids"
    }

    gender = gender_map.get(gender_raw)
    if not gender:
        return None

    # ---- product type ----
    prod_map = {
        "A": "shoes",
        "B": "clothing",
        "C": "both"
    }

    product_type = prod_map.get(prod_raw.upper())
    if not product_type:
        return None

    # ---- size ----
    try:
        size = int(size_raw)
    except:
        return None

    # ---- price range ----
    try:
        min_price = int(min_p_raw)
        max_price = int(max_p_raw)
    except:
        return None

    price_range = f"{min_price}-{max_price}"

    return {
        "gender": gender,
        "product_type": product_type,
        "size": size,
        "price": price_range
    }


# ---------------------------------------------
# Main onboarding logic
# ---------------------------------------------
def process_updates():
    last_update_id = load_last_update_id()
    params = {"offset": last_update_id + 1} if last_update_id else {}

    r = requests.get(f"{API_URL}/getUpdates", params=params, timeout=20)
    data = r.json()

    if not data.get("ok"):
        return

    updates = data.get("result", [])
    if not updates:
        return

    user_data = load_user_data()

    for upd in updates:
        update_id = upd["update_id"]
        message = upd.get("message", {})
        text = message.get("text")
        chat_id = message.get("chat", {}).get("id")

        if not text or not chat_id:
            continue

        parsed = parse_preference_message(text)

        if not parsed:
            send_message(
                chat_id,
                "❗ פורמט לא תקין.\n"
                "שלחו הודעה אחת בלבד בפורמט:\n\n"
                "`<gender> <type> <size> <min> <max>`\n\n"
                "דוגמה:\n`1 A 43 0 300`\n\n"
                "מדריך קצר:\n"
                "1 = גברים | 2 = נשים | 3 = ילדים\n"
                "A = הנעלה | B = ביגוד | C = שניהם\n"
            )
        else:
            # Save user preferences
            user_data[str(chat_id)] = {
                "chat_id": chat_id,
                **parsed
            }

            save_user_data(user_data)

            send_message(
                chat_id,
                "🎉 ההגדרות נשמרו בהצלחה!\n"
                f"קטגוריה: {parsed['gender']}\n"
                f"סוג מוצר: {parsed['product_type']}\n"
                f"מידה: {parsed['size']}\n"
                f"טווח מחירים: {parsed['price']}\n\n"
                "הבוט יסרוק עבורך ויעדכן בהודעות הקרובות."
            )

        # Update the offset
        save_last_update_id(update_id)


if __name__ == "__main__":
    process_updates()
