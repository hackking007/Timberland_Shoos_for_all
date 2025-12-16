# config.py
import os

# ---------------- Telegram ----------------

# Support both env names, prefer TELEGRAM_BOT_TOKEN
TELEGRAM_BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN", "") or os.getenv("TELEGRAM_TOKEN", "")).strip()

_admin_env = (os.getenv("ADMIN_CHAT_ID", "") or os.getenv("CHAT_ID", "")).strip()
ADMIN_CHAT_ID = int(_admin_env) if _admin_env.isdigit() else None

# ---------------- Files ----------------

USER_DATA_FILE = "user_data.json"
LAST_UPDATE_ID_FILE = "last_update_id.json"

# State file for products "already sent"
STATE_FILE = "state.json"

# ---------------- Playwright / Scraping ----------------

SCAN_TIMEOUT = 60000  # ms
MAX_LOAD_MORE_CLICKS = 10
LOAD_MORE_DELAY = 1500  # ms

# ---------------- Sending window (Israel time) ----------------
SEND_HOURS_IL = [7, 19]

# ---------------- Categories / URLs ----------------

SHOES_BASE = {
    "men": "https://www.timberland.co.il/men/footwear",
    "women": "https://www.timberland.co.il/women/%D7%94%D7%A0%D7%A2%D7%9C%D7%94",
    "kids": "https://www.timberland.co.il/kids/toddlers-0-5y",
}

CLOTHING_BASE = {
    "men": "https://www.timberland.co.il/men/clothing",
    "women": "https://www.timberland.co.il/women/clothing",
    "kids": "https://www.timberland.co.il/kids/clothing",
}

SHOES_SIZE_MAP = {
    "men": {"40": "791", "41": "792", "42": "793", "43": "794", "44": "795", "45": "796"},
    "women": {"36": "798", "37": "799", "38": "800", "39": "801", "40": "802", "41": "803"},
    "kids": {"28": "230", "29": "231", "30": "232", "31": "233", "32": "234", "33": "235", "34": "236", "35": "237"},
}

# Clothing size mapping - based on your example: men clothing size L -> size=4
CLOTHING_SIZE_MAP = {
    "men":   {"XS": "1", "S": "2", "M": "3", "L": "4", "XL": "5", "XXL": "6", "XXXL": "7"},
    "women": {"XS": "1", "S": "2", "M": "3", "L": "4", "XL": "5", "XXL": "6", "XXXL": "7"},
    "kids":  {"2": "2", "3": "3", "4": "4", "5": "5", "6": "6", "7": "7", "8": "8", "10": "10", "12": "12"},
}

# ---------------- Messages ----------------

WELCOME_TEXT = (
    "👟 <b>ברוך הבא לבוט טימברלנד</b>\n\n"
    "כדי להגדיר מעקב מותאם אישית בהודעה אחת, שלחו לבוט הודעה בפורמט הבא:\n\n"
    "<code>&lt;gender&gt; &lt;type&gt; &lt;size&gt; &lt;min_price&gt; &lt;max_price&gt;</code>\n\n"
    "<b>קידודים</b>\n"
    "gender:\n"
    "1 - גברים\n"
    "2 - נשים\n"
    "3 - ילדים\n\n"
    "type:\n"
    "A - הנעלה\n"
    "B - ביגוד\n"
    "C - גם וגם\n\n"
    "<b>דוגמה</b>\n"
    "<code>1 A 43 128 299</code>\n\n"
    "<b>שים לב לגבי C (גם וגם)</b>\n"
    "כדי שלא נשבור מידות שונות, שלח מידה בפורמט <code>shoeSize/clothingSize</code>\n"
    "לדוגמה:\n"
    "<code>2 C 40/L 0 800</code>\n\n"
    "🕖 <b>שעות שליחת מוצרים</b> (שעון ישראל):\n"
    "07:00 ו-19:00\n"
)

ENABLE_DEBUG_LOGS = True