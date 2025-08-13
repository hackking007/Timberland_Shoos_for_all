import os
import json
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
)
from config import *

# שלבים בשיחה
START, GENDER, SIZE, PRICE = range(4)

# טעינת נתוני משתמשים מהקובץ (אם קיים)
if os.path.exists(USER_DATA_FILE):
    with open(USER_DATA_FILE, "r") as f:
        user_data = json.load(f)
else:
    user_data = {}

# שמירת נתוני המשתמשים לקובץ
def save_user_data():
    with open(USER_DATA_FILE, "w") as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)

# התחלת שיחה עם המשתמש
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name or "משתמש"
    keyboard = [["גברים", "נשים", "ילדים"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        f"👋 שלום {user_name}!\n\n🔔 אני אעזור לך לקבל התראות על נעלי טימברלנד חדשות!\n\n👟 באיזו קטגוריה אתה מעוניין?", 
        reply_markup=reply_markup
    )
    return GENDER

# בחירת מגדר
async def gender_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    category_map = {"גברים": "men", "נשים": "women", "ילדים": "kids"}
    gender_input = update.message.text.strip()
    if gender_input not in category_map:
        keyboard = [["גברים", "נשים", "ילדים"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("❌ אנא בחר מהאפשרויות:", reply_markup=reply_markup)
        return GENDER
    gender = category_map[gender_input]
    user_data[user_id] = {"gender": gender}
    save_user_data()
    category_names = {"men": "גברים", "women": "נשים", "kids": "ילדים"}
    valid_sizes = {
        "men": "40-45",
        "women": "36-41", 
        "kids": "28-35"
    }
    size_range = valid_sizes.get(gender, "40-45")
    await update.message.reply_text(
        f"📏 מה המידה שלך ב-{category_names.get(gender, '')}?\n\n🔢 מידות זמינות: {size_range}"
    )
    return SIZE

# בחירת מידה
async def size_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    size = update.message.text.strip()
    
    if not size.isdigit():
        await update.message.reply_text("❌ אנא הזן מספר תקין (למשל: 43)")
        return SIZE
    
    # בדיקת מידות תקינות לפי קטגוריה
    category = user_data[user_id]["gender"]
    valid_sizes = {
        "men": ["40", "41", "42", "43", "44", "45"],
        "women": ["36", "37", "38", "39", "40", "41"],
        "kids": ["28", "29", "30", "31", "32", "33", "34", "35"]
    }
    
    if size not in valid_sizes.get(category, []):
        category_names = {"men": "גברים", "women": "נשים", "kids": "ילדים"}
        available = ", ".join(valid_sizes[category])
        await update.message.reply_text(
            f"❌ מידה לא זמינה עבור {category_names[category]}\n\n📏 מידות זמינות: {available}"
        )
        return SIZE
    
    user_data[user_id]["size"] = size
    save_user_data()
    await update.message.reply_text("💰 מהו טווח המחירים? (למשל: 100-300)")
    return PRICE

# בחירת טווח מחיר
async def price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    price = update.message.text.strip()
    if "-" not in price or not all(p.strip().isdigit() for p in price.split("-")):
        await update.message.reply_text("❌ אנא כתוב טווח מחיר תקני\n\n📝 דוגמאות: 100-300, 0-200, 150-500")
        return PRICE
    
    # בדיקה שהמחיר המינימלי קטן מהמקסימלי
    min_price, max_price = map(int, price.split("-"))
    if min_price >= max_price:
        await update.message.reply_text("❌ המחיר המינימלי חייב להיות קטן מהמקסימלי")
        return PRICE
    user_data[user_id]["price"] = price
    save_user_data()
    await update.message.reply_text("✅ מעולה! ההעדפות נשמרו בהצלחה!\n\n🎯 תקבל התראות על נעליים חדשות פעמיים ביום\n📱 השתמש ב-/show כדי לראות את ההעדפות\n🔄 השתמש ב-/reset כדי לאפס")
    return ConversationHandler.END

# צפייה בהעדפות המשתמש
async def show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    prefs = user_data.get(user_id)
    if prefs:
        gender_map = {"men": "גברים", "women": "נשים", "kids": "ילדים"}
        gender = gender_map.get(prefs["gender"], "לא נבחר")
        await update.message.reply_text(
            f"👤 ההעדפות שלך:\n📂 קטגוריה: {gender}\n📏 מידה: {prefs['size']}\n💰 טווח מחיר: {prefs['price']} ש\"ח\n\n🔔 תקבל התראות פעמיים ביום על נעליים חדשות!"
        )
    else:
        await update.message.reply_text("❌ אין לך עדיין העדפות מוגדרות.\n\n🚀 שלח /start כדי להתחיל!")

# פקודת עזרה
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """🤖 *בוט מעקב נעלי טימברלנד*

📋 *פקודות זמינות:*
/start - הגדרת העדפות אישיות
/show - צפייה בהעדפות הנוכחיות
/reset - איפוס ההעדפות
/help - הצגת הודעה זו

🎯 *איך זה עובד?*
1. בחר קטגוריה (גברים/נשים/ילדים)
2. הזן את המידה שלך
3. קבע טווח מחירים
4. קבל התראות פעמיים ביום!

💡 *טיפ:* תוכל לשנות את ההעדפות בכל עת עם /start"""
    await update.message.reply_text(help_text, parse_mode="Markdown")

# איפוס העדפות
async def reset_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in user_data:
        del user_data[user_id]
        save_user_data()
        await update.message.reply_text("✅ ההעדפות שלך נמחקו. תוכל להתחיל מחדש עם /start")
    else:
        await update.message.reply_text("ℹ️ אין לך העדפות שמורות.")

# הגדרת הבוט והפעלה
def main():
    # אם אין טוקן במשתני סביבה, שים אותו כאן:
    token = TELEGRAM_TOKEN
    
    if not token:
        print("Error: TELEGRAM_TOKEN environment variable not set!")
        return
    
    app = ApplicationBuilder().token(token).build()
    
    # ניהול השיחה לפי השלבים
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, gender_handler)],
            SIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, size_handler)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, price_handler)],
        },
        fallbacks=[]
    )

    # הוספת הפקודות
    app.add_handler(conv)
    app.add_handler(CommandHandler("show", show))
    app.add_handler(CommandHandler("reset", reset_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.run_polling()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()