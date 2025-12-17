# config.py
import os

# ---------------- Telegram ----------------
# Support both secret names:
# - TELEGRAM_BOT_TOKEN (recommended)
# - TELEGRAM_TOKEN (legacy)
TELEGRAM_BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or "").strip()

# Optional admin chat id (not required)
_admin_env = (os.getenv("ADMIN_CHAT_ID") or os.getenv("CHAT_ID") or "").strip()
ADMIN_CHAT_ID = int(_admin_env) if _admin_env.isdigit() else None

# ---------------- Files ----------------
USER_DATA_FILE = "user_data.json"
LAST_UPDATE_ID_FILE = "last_update_id.json"

# Global state for "new products only"
STATE_FILE = "state.json"

# Size maps
# Shoes map is your existing file: size_map.json
SHOES_SIZE_MAP_FILE = "size_map.json"

# Apparel size map (S/M/L/XL...) - you said you created apparel_size_map.json
APPAREL_SIZE_MAP_FILE = "apparel_size_map.json"

# Backward-compat aliases (so old code won't break if exists anywhere)
SIZE_MAP_FILE = SHOES_SIZE_MAP_FILE

# ---------------- Scan tuning ----------------
SCAN_TIMEOUT = 60000           # ms
MAX_LOAD_MORE_CLICKS = 10
LOAD_MORE_DELAY = 1500         # ms
ENABLE_DEBUG_LOGS = True

# ---------------- Send windows ----------------
# Twice a day (Israel time)
SEND_HOURS_IL = [7, 19]

# ---------------- Texts ----------------
WELCOME_TEXT = (
    "👟 <b>ברוך הבא לבוט טימברלנד</b>\n\n"
    "כדי להגדיר מעקב מותאם אישית בהודעה אחת, שלחו לבוט הודעה בפורמט הבא:\n\n"
    "<code>&lt;gender&gt; &lt;type&gt; &lt;size&gt; &lt;min_price&gt; &lt;max_price&gt;</code>\n\n"
    "<b>קידודים</b>\n"
    "<b>gender:</b>\n"
    "1 - גברים\n"
    "2 - נשים\n"
    "3 - ילדים\n\n"
    "<b>type:</b>\n"
    "A - הנעלה\n"
    "B - ביגוד\n"
    "C - גם וגם\n\n"
    "<b>דוגמה</b>\n"
    "<code>1 A 43 128 299</code>\n\n"
    "שים לב לגבי <b>C</b> (גם וגם)\n"
    "כדי שלא נשבור מידות שונות, שלח מידה בפורמט <code>shoeSize/clothingSize</code>\n"
    "לדוגמה:\n"
    "<code>2 C 40/L 0 800</code>\n\n"
    "🕖 <b>שעות שליחת מוצרים (שעון ישראל):</b>\n"
    "07:00 ו-19:00\n"
)