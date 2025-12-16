import os
import json
import urllib.parse
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

USER_DATA_FILE = "user_data.json"
SIZE_MAP_FILE = "size_map.json"

# שים פה את ה-BASE_URL האמיתי שלך לטימברלנד
# לדוגמה: URL של חיפוש כללי שניתן לסנן ע"י פרמטרים
BASE_URL = "https://www.timberland.co.il/search"


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
        resp = requests.post(
            TELEGRAM_API_URL + "/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=30
        )
        print(f"send_message to {chat_id} -> status {resp.status_code}")
        if not resp.ok:
            print("send_message response text:", resp.text)
    except Exception as e:
        print(f"Error sending message to {chat_id}: {e}")


# מיפוי מגדר -> ערך לפרמטר (או לנתיב) לפי איך שהאתר עובד אצלך
GENDER_PARAM_MAP = {
    "men": "men",
    "women": "women",
    "kids": "kids",
}

# מיפוי סוג מוצר -> ערך לפרמטר (או לנתיב)
CATEGORY_PARAM_MAP = {
    "shoes": "shoes",
    "clothing": "clothing",
    "both": "all",  # למשל "all" או מה שמתאים אצלך
}


def build_tim_url(prefs, size_map):
    """
    prefs: ההעדפות של המשתמש מתוך user_data.json
    size_map: מיפוי ממידה אנושית (למשל "43") ל-size_id באתר (למשל "794").
    מחזיר URL מלא לטימברלנד בהתאמה אישית.
    """
    gender = prefs.get("gender")
    category = prefs.get("category")
    size = prefs.get("size")
    price_min = prefs.get("price_min", 0)
    price_max = prefs.get("price_max", 9999)

    params = {}

    # מגדר
    if gender in GENDER_PARAM_MAP:
        params["gender"] = GENDER_PARAM_MAP[gender]

    # סוג מוצר
    if category in CATEGORY_PARAM_MAP:
        params["category"] = CATEGORY_PARAM_MAP[category]

    # מיפוי מידה -> קוד size
    if size and size_map:
        size_code = size_map.get(str(size))
        if size_code:
            params["size"] = size_code

    # טווח מחירים
    params["price"] = f"{price_min}_{price_max}"

    query = urllib.parse.urlencode(params)
    return f"{BASE_URL}?{query}"


def scrape_products(url):
    """
    פונקציית placeholder בשלב זה.
    כאן בעתיד נלביש את Playwright / BeautifulSoup האמיתיים שלך.

    כרגע: רק מחזירה dict קטן עם ה-URL, כדי שנוכל לבדוק שהכל עובד.
    """
    # TODO: להחליף במימוש האמיתי שלך (Playwright/BS4)
    print(f"scrape_products called with URL: {url}")
    return {
        "url": url,
        "products": []  # בעתיד: רשימת מוצרים אמיתית
    }


def format_message_for_user(prefs, result):
    """
    יוצר טקסט יפה למשתמש לפי ההעדפות שלו + ה-URL שנסרק.
    כרגע בלי פירוט מוצרים, רק וידוא שהכל מותאם אישית.
    """
    gender_map_he = {"men": "גברים", "women": "נשים", "kids": "ילדים"}
    category_map_he = {
        "shoes": "הנעלה",
        "clothing": "ביגוד",
        "both": "הנעלה + ביגוד"
    }

    gender_he = gender_map_he.get(prefs.get("gender"), prefs.get("gender"))
    category_he = category_map_he.get(prefs.get("category"), prefs.get("category"))
    size = prefs.get("size")
    price_min = prefs.get("price_min")
    price_max = prefs.get("price_max")

    text = (
        "עדכון הגדרות המעקב שלך בטימברלנד ✅\n\n"
        f"קטגוריית קהל היעד: {gender_he}\n"
        f"סוג מוצרים: {category_he}\n"
        f"מידה: {size}\n"
        f"טווח מחיר: {price_min} - {price_max} ₪\n\n"
        "זה ה-URL הספציפי שאני סורק עבורך:\n"
        f"{result['url']}\n\n"
        "בשלב הבא נוסיף כאן גם רשימת מוצרים שמתאימים לך בפועל 👟"
    )
    return text


def run_for_all_users():
    if not BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN is not set")
        return

    user_data = load_json(USER_DATA_FILE, {})
    size_map = load_json(SIZE_MAP_FILE, {})

    if not user_data:
        print("No users found in user_data.json")
        return

    print("Found users:", list(user_data.keys()))

    for chat_id, prefs in user_data.items():
        state = prefs.get("state")
        if state != "ready":
            print(f"Skipping {chat_id}, state={state}")
            continue

        url = build_tim_url(prefs, size_map)
        result = scrape_products(url)

        message = format_message_for_user(prefs, result)
        send_message(chat_id, message)


def main():
    print("=== timberland_checker.py starting ===")
    run_for_all_users()
    print("=== timberland_checker.py finished ===")


if __name__ == "__main__":
    main()
