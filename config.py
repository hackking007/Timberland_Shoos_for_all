# config.py
import os

# -----------------------------
# Telegram
# -----------------------------
# תומך גם בשם הסיקרט הישן וגם החדש:
# - TELEGRAM_BOT_TOKEN (כמו שהיה אצלך)
# - TELEGRAM_TOKEN (שם קצר ונוח)
TELEGRAM_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or "").strip()

# אם תרצה התראות לאדמין (לא חובה)
_admin_env = (os.getenv("ADMIN_CHAT_ID") or os.getenv("CHAT_ID") or "").strip()
ADMIN_CHAT_ID = int(_admin_env) if _admin_env.isdigit() else None

# -----------------------------
# Files (STATE) - לא לשים בריפו, רק כ-artifact
# -----------------------------
USER_DATA_FILE = "user_data.json"
LAST_UPDATE_ID_FILE = "last_update_id.json"
STATE_FILE = "shoes_state.json"

# קובץ מיפוי מידות לנעליים (כן נמצא בריפו)
SIZE_MAP_FILE = "size_map.json"

# -----------------------------
# URLs (Timberland)
# -----------------------------
BASE = "https://www.timberland.co.il"

SHOES_URLS = {
    "men": f"{BASE}/men/footwear",
    "women": f"{BASE}/women/%D7%94%D7%A0%D7%A2%D7%9C%D7%94",
    "kids": f"{BASE}/kids/toddlers-0-5y",
}

CLOTHING_URLS = {
    "men": f"{BASE}/men/clothing",
    "women": f"{BASE}/women/clothing",
    "kids": f"{BASE}/kids/clothing",
}

# -----------------------------
# Clothing size codes (הנחה סבירה לפי מה שנתת: L -> 4)
# אם תרצה לשנות - זה המקום היחיד.
# -----------------------------
CLOTHING_SIZE_CODE = {
    "XS": 1,
    "S": 2,
    "M": 3,
    "L": 4,     # לפי הדוגמה שלך: size=4 עבור L
    "XL": 5,
    "XXL": 6,
    "XXXL": 7,
}

# -----------------------------
# Checker schedule logic (שעון ישראל)
# -----------------------------
SEND_HOURS_IL = [7, 19]  # 07:00 ו-19:00

# -----------------------------
# Playwright scan params
# -----------------------------
SCAN_TIMEOUT_MS = 60_000
MAX_LOAD_MORE_CLICKS = 10
LOAD_MORE_DELAY_MS = 1500

# -----------------------------
# Messaging
# -----------------------------
WELCOME_TEXT = (
    "👟 ברוך הבא לבוט טימברלנד\n\n"
    "כדי להגדיר מעקב מותאם אישית בהודעה אחת, שלחו לבוט הודעה בפורמט הבא:\n\n"
    "<gender> <type> <size> <min_price> <max_price>\n\n"
    "קידודים\n"
    "gender:\n"
    "1 - גברים\n"
    "2 - נשים\n"
    "3 - ילדים\n\n"
    "type:\n"
    "A - הנעלה\n"
    "B - ביגוד\n"
    "C - גם וגם\n\n"
    "דוגמה\n"
    "1 A 43 128 299\n\n"
    "שים לב לגבי C (גם וגם)\n"
    "כדי שלא נשבור מידות שונות, שלח מידה בפורמט shoeSize/clothingSize\n"
    "לדוגמה:\n"
    "2 C 40/L 0 800\n\n"
    "🕖 שעות שליחת מוצרים (שעון ישראל):\n"
    "07:00 ו-19:00"
)

# -----------------------------
# Logs
# -----------------------------
ENABLE_DEBUG_LOGS = True
ENABLE_ADMIN_NOTIFICATIONS = bool(ADMIN_CHAT_ID)
