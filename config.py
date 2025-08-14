# הגדרות הבוט
import os

# --- טלגרם ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()  # חובה
# תמיכה גם ב-ADMIN_CHAT_ID וגם ב-CHAT_ID (לא חובה)
_admin_env = os.getenv("ADMIN_CHAT_ID", "").strip() or os.getenv("CHAT_ID", "").strip()
ADMIN_CHAT_ID = int(_admin_env) if _admin_env.isdigit() else None

# --- סריקה ---
SCAN_TIMEOUT = 60000           # ms (Playwright עובד במילישניות)
MAX_LOAD_MORE_CLICKS = 10
LOAD_MORE_DELAY = 1500         # ms

# --- קבצים ---
USER_DATA_FILE = "user_data.json"
STATE_FILE = "shoes_state.json"
SIZE_MAP_FILE = "size_map.json"

# --- קטגוריות ---
CATEGORIES = {
    "men": {
        "name": "גברים",
        "url": "https://www.timberland.co.il/men/footwear",
        "sizes": ["40", "41", "42", "43", "44", "45"]
    },
    "women": {
        "name": "נשים",
        "url": "https://www.timberland.co.il/women/%D7%94%D7%A0%D7%A2%D7%9C%D7%94",
        "sizes": ["36", "37", "38", "39", "40", "41"]
    },
    "kids": {
        "name": "ילדים",
        "url": "https://www.timberland.co.il/kids/toddlers-0-5y",
        "sizes": ["28", "29", "30", "31", "32", "33", "34", "35"]
    }
}

# --- הודעות ---
MESSAGES = {
    "welcome": "👋 שלום {name}!\n\n🔔 אני אעזור לך לקבל התראות על נעלי טימברלנד חדשות!\n\n👟 באיזו קטגוריה אתה מעוניין?",
    "size_prompt": "📏 מה המידה שלך ב-{category}?\n\n🔢 מידות זמינות: {size_range}",
    "price_prompt": "💰 מהו טווח המחירים? (למשל: 100-300)",
    "success": "✅ מעולה! ההעדפות נשמרו בהצלחה!\n\n🎯 תקבל התראות על נעליים חדשות פעמיים ביום\n📱 השתמש ב-/show כדי לראות את ההעדפות\n🔄 השתמש ב-/reset כדי לאפס",
    "no_prefs": "❌ אין לך עדיין העדפות מוגדרות.\n\n🚀 שלח /start כדי להתחיל!",
    "reset_success": "✅ ההעדפות שלך נמחקו. תוכל להתחיל מחדש עם /start",
    "reset_no_data": "ℹ️ אין לך העדפות שמורות."
}

# --- לוגים ---
ENABLE_DEBUG_LOGS = True
ENABLE_ADMIN_NOTIFICATIONS = bool(ADMIN_CHAT_ID)
