# config.py
import os

# ---------------- Telegram ----------------
# Support both TELEGRAM_BOT_TOKEN and TELEGRAM_TOKEN (backward compatible)
TELEGRAM_BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN", "") or os.getenv("TELEGRAM_TOKEN", "")).strip()

# Optional admin chat id (for debug notifications)
_admin_env = (os.getenv("ADMIN_CHAT_ID", "") or os.getenv("CHAT_ID", "")).strip()
ADMIN_CHAT_ID = int(_admin_env) if _admin_env.isdigit() else None

# ---------------- Playwright / Scan ----------------
SCAN_TIMEOUT = 60000           # ms
MAX_LOAD_MORE_CLICKS = 10
LOAD_MORE_DELAY = 1500         # ms

# ---------------- Files ----------------
USER_DATA_FILE = "user_data.json"
LAST_UPDATE_ID_FILE = "last_update_id.json"
STATE_FILE = "state.json"          # IMPORTANT: matches bot.yml artifact paths
SIZE_MAP_FILE = "size_map.json"

# ---------------- URLs ----------------
# Shoes pages
SHOES_URLS = {
    "men": "https://www.timberland.co.il/men/footwear",
    "women": "https://www.timberland.co.il/women/%D7%94%D7%A0%D7%A2%D7%9C%D7%94",
    "kids": "https://www.timberland.co.il/kids/toddlers-0-5y",
}

# Clothing pages (you confirmed men works like: /men/clothing?price=68_1001&size=4)
CLOTHING_URLS = {
    "men": "https://www.timberland.co.il/men/clothing",
    "women": "https://www.timberland.co.il/women/clothing",
    "kids": "https://www.timberland.co.il/kids/clothing",
}

# Clothing size mapping (example: L -> 4, as you verified)
CLOTHING_SIZE_MAP = {
    "XS": 1,
    "S": 2,
    "M": 3,
    "L": 4,
    "XL": 5,
    "XXL": 6,
    "XXXL": 7,
}

# ---------------- Scheduling ----------------
# Products are sent twice a day (Israel time)
SEND_HOURS_IL = [7, 19]

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
    "🕖 <b>שעות שליחת מוצרים (שעון ישראל):</b>\n"
    "07:00 ו-19:00\n"
)

# ---------------- Logs ----------------
ENABLE_DEBUG_LOGS = True
ENABLE_ADMIN_NOTIFICATIONS = bool(ADMIN_CHAT_ID)