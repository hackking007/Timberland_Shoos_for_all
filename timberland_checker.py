import os
import json
import urllib.parse
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

USER_DATA_FILE = "user_data.json"

# בסיס לדוגמה - תחליף ל-URL האמיתי שלך כיום
BASE_URL = "https://www.timberland.co.il/men/shoes"


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def send_message(chat_id, text):
    if not BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN is not set")
        return

    try:
        requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=30
        )
    except Exception as e:
        print(f"Error sending message to {chat_id}: {e}")


# כאן תכניס את המיפויים האמיתיים לפי מה שאתה כבר יודע מהפרויקט הנוכחי שלך
GENDER_PARAM_MAP = {
    "men": "men",       # TODO: להתאים לפרמטרים האמיתיים ב-URL
    "women": "women",
    "kids": "kids"
}

CATEGORY_PARAM_MAP = {
    "shoes": "shoes",        # TODO: להתאים למבנה האתר
    "clothing": "clothing",
    "both": "all"
}

SIZE_MAP = {
    # כאן כבר ידוע לנו:
    "43": "794",
    "37": "799"
    # תוכל להוסיף עוד מידות לפי מה שכבר גילית
}


def build_tim_url(prefs):
    """
    prefs: dict מתוך user_data.json עבור משתמש בודד
    מחזיר URL מותאם עבורו.
    """
    gender = prefs.get("gender")
    category = prefs.get("category")
    size = prefs.get("size")
    price_min = prefs.get("price_min", 0)
    price_max = prefs.get("price_max", 9999)

    params = {}

    # מיפוי גברים/נשים/ילדים לפרמטר המתאים
    if gender in GENDER_PARAM_MAP:
        params["gender"] = GENDER_PARAM_MAP[gender]

    # מיפוי סוג מוצר
    if category in CATEGORY_PARAM_MAP:
        params["category"] = CATEGORY_PARAM_MAP[category]

    # מיפוי מידה לערך size האמיתי ב-URL של טימברלנד
    if size in SIZE_MAP:
        params["size"] = SIZE_MAP[size]

    # טווח מחירים
    params["price"] = f"{price_min}_{price_max}"

    query = urllib.parse.urlencode(params)
    return f"{BASE_URL}?{query}"


def scrape_products(url):
    """
    פונקציה זמנית - כרגע רק מחזירה את ה-URL.
    בשלב הבא נחבר לכאן את Playwright/BeautifulSoup כמו שיש לך בפרויקט המקורי.
    """
    # TODO: להחליף במימוש הסריקה האמיתי שלך
    return {"url": url}


def run_for_all_users():
    if not BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN is not set")
        return

    user_data = load_json(USER_DATA_FILE, {})
    if not user_data:
        print("No users found in user_data.json")
        return

    for chat_id, prefs in user_data.items():
        state = prefs.get("state")
        if state != "ready":
            print(f"Skipping {chat_id}, state={state}")
            continue

        url = build_tim_url(prefs)
        result = scrape_products(url)

        # בינתיים נשלח למשתמש רק את ה-URL שהותאם לו - כדי לוודא שהכל עובד
        text = (
            "עדכנתי את מעקב טימברלנד לפי ההעדפות שלך ✅\n\n"
            f"זה ה-URL שאני סורק עבורך כרגע:\n{result['url']}\n\n"
            "בשלב הבא נוסיף לכאן הופעה של מוצרים אמיתיים לפי הסינון."
        )
        send_message(chat_id, text)


def main():
    run_for_all_users()


if __name__ == "__main__":
    main()
