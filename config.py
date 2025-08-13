# הגדרות הבוט
import os

# הגדרות טלגרם
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.environ.get("CHAT_ID")  # אופציונלי - לקבלת הודעות מנהל

# הגדרות סריקה
SCAN_TIMEOUT = 60000  # זמן המתנה לטעינת עמוד (מילישניות)
MAX_LOAD_MORE_CLICKS = 10  # מקסימום לחיצות על "טען עוד"
LOAD_MORE_DELAY = 1500  # השהיה בין לחיצות (מילישניות)

# קבצי נתונים
USER_DATA_FILE = "user_data.json"
STATE_FILE = "shoes_state.json"
SIZE_MAP_FILE = "size_map.json"

# הגדרות מידות וקטגוריות
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

# הודעות הבוט
MESSAGES = {
    "welcome": "👋 שלום {name}!\n\n🔔 אני אעזור לך לקבל התראות על נעלי טימברלנד חדשות!\n\n👟 באיזו קטגוריה אתה מעוניין?",
    "size_prompt": "📏 מה המידה שלך ב-{category}?\n\n🔢 מידות זמינות: {size_range}",
    "price_prompt": "💰 מהו טווח המחירים? (למשל: 100-300)",
    "success": "✅ מעולה! ההעדפות נשמרו בהצלחה!\n\n🎯 תקבל התראות על נעליים חדשות פעמיים ביום\n📱 השתמש ב-/show כדי לראות את ההעדפות\n🔄 השתמש ב-/reset כדי לאפס",
    "no_prefs": "❌ אין לך עדיין העדפות מוגדרות.\n\n🚀 שלח /start כדי להתחיל!",
    "reset_success": "✅ ההעדפות שלך נמחקו. תוכל להתחיל מחדש עם /start",
    "reset_no_data": "ℹ️ אין לך העדפות שמורות."
}

# הגדרות לוגים
ENABLE_DEBUG_LOGS = True
ENABLE_ADMIN_NOTIFICATIONS = bool(ADMIN_CHAT_ID)