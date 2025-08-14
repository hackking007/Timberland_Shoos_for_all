# main_bot.py
# Bot that auto-registers users on /start and stores their preferences in user_data.json.
# Supports: /start (register), /prefs (guided setup), /set men 43 0-300 (quick setup), /show (view prefs)
# Requires: python-telegram-bot ~= 13.x  (sync API)
# Reads TELEGRAM_TOKEN from config.py (which should read it from ENV)

import json
import os
from pathlib import Path
from typing import Dict, Any

from telegram import Update, ParseMode, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    ConversationHandler,
)

# ---- Project Config ----
# Expecting TELEGRAM_TOKEN inside config.py, e.g.:
# TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","").strip()
try:
    from config import TELEGRAM_TOKEN
except Exception:
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()

# Files
USER_DATA_FILE = "user_data.json"

# Defaults
DEFAULT_PREFS = {
    "gender": "men",     # valid: men/women/kids (must match your CATEGORIES keys in scraper)
    "size": "43",        # string preferred (maps via size_map.json)
    "price": "0-300",    # "min-max"
}

# States for Conversation (/prefs)
CHOOSE_CATEGORY, CHOOSE_SIZE, CHOOSE_PRICE = range(3)

# --------- Storage Helpers ---------
def load_users() -> Dict[str, Any]:
    """Load all users from user_data.json"""
    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception:
        return {}

def save_users(data: Dict[str, Any]) -> None:
    """Persist all users to user_data.json (human-readable)"""
    Path(USER_DATA_FILE).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

def get_or_create_user(chat_id: int) -> Dict[str, Any]:
    """Return a user entry, creating with defaults if missing"""
    users = load_users()
    key = str(chat_id)
    if key not in users:
        users[key] = {
            "chat_id": chat_id,
            **DEFAULT_PREFS
        }
        save_users(users)
    return users[key]

def set_user_prefs(chat_id: int, *, gender: str = None, size: str = None, price: str = None) -> Dict[str, Any]:
    """Update user preferences. Pass None to keep existing."""
    users = load_users()
    key = str(chat_id)
    if key not in users:
        users[key] = {"chat_id": chat_id, **DEFAULT_PREFS}
    if gender is not None:
        users[key]["gender"] = gender
    if size is not None:
        users[key]["size"] = size
    if price is not None:
        users[key]["price"] = price
    save_users(users)
    return users[key]

# --------- Utilities ---------
def format_prefs(u: Dict[str, Any]) -> str:
    """Return human-readable summary of preferences for Telegram."""
    return (
        f"*Your preferences:*\n"
        f"• Category: `{u.get('gender','-')}`\n"
        f"• Size: `{u.get('size','-')}`\n"
        f"• Price: `{u.get('price','-')}`"
    )

def parse_set_args(text: str):
    """
    Parse '/set men 43 0-300' style command.
    Returns (gender, size, price) or (None,None,None) if can't parse.
    """
    parts = text.strip().split()
    # Expected: ['/set', 'men', '43', '0-300']
    if len(parts) == 4 and parts[0].lower() == "/set":
        gender = parts[1].lower()
        size = parts[2]
        price = parts[3]
        if gender not in {"men", "women", "kids"}:
            return None, None, None
        if "-" not in price:
            return None, None, None
        return gender, size, price
    return None, None, None

# --------- Handlers ---------
def start(update: Update, context: CallbackContext):
    """Auto-register user on /start and show their preferences."""
    chat_id = update.effective_chat.id
    user = get_or_create_user(chat_id)

    msg = (
        f"✅ Registered! Your chat_id is `{chat_id}`\n\n"
        f"{format_prefs(user)}\n\n"
        f"You can update via:\n"
        f"• /prefs (guided)\n"
        f"• /set men 43 0-300 (quick)\n"
        f"• /show (show current)"
    )
    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

def show(update: Update, context: CallbackContext):
    """Show current user preferences."""
    chat_id = update.effective_chat.id
    user = get_or_create_user(chat_id)
    update.message.reply_text(format_prefs(user), parse_mode=ParseMode.MARKDOWN)

def quick_set(update: Update, context: CallbackContext):
    """Quick set via '/set men 43 0-300'"""
    chat_id = update.effective_chat.id
    gender, size, price = parse_set_args(update.message.text or "")
    if not all([gender, size, price]):
        update.message.reply_text(
            "Usage: `/set men 43 0-300`\n(valid genders: men/women/kids)",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    user = set_user_prefs(chat_id, gender=gender, size=size, price=price)
    update.message.reply_text(
        f"✅ Updated!\n\n{format_prefs(user)}",
        parse_mode=ParseMode.MARKDOWN,
    )

# ---- /prefs conversation (guided flow) ----
def prefs_start(update: Update, context: CallbackContext):
    """Start guided preferences setup."""
    chat_id = update.effective_chat.id
    get_or_create_user(chat_id)  # ensure user exists

    reply_kb = [["men", "women", "kids"]]
    update.message.reply_text(
        "Select category (men/women/kids):",
        reply_markup=ReplyKeyboardMarkup(reply_kb, one_time_keyboard=True, resize_keyboard=True),
    )
    return CHOOSE_CATEGORY

def prefs_choose_category(update: Update, context: CallbackContext):
    val = (update.message.text or "").strip().lower()
    if val not in {"men", "women", "kids"}:
        update.message.reply_text("Please choose one of: men / women / kids")
        return CHOOSE_CATEGORY
    context.user_data["gender"] = val
    update.message.reply_text("Enter size (e.g., 43):", reply_markup=ReplyKeyboardRemove())
    return CHOOSE_SIZE

def prefs_choose_size(update: Update, context: CallbackContext):
    val = (update.message.text or "").strip()
    if not val:
        update.message.reply_text("Please enter a size, e.g., 43")
        return CHOOSE_SIZE
    context.user_data["size"] = val
    update.message.reply_text("Enter price range (min-max), e.g., 0-300:")
    return CHOOSE_PRICE

def prefs_choose_price(update: Update, context: CallbackContext):
    val = (update.message.text or "").strip()
    if "-" not in val:
        update.message.reply_text("Please enter price as min-max, e.g., 0-300:")
        return CHOOSE_PRICE

    # Save all
    chat_id = update.effective_chat.id
    gender = context.user_data.get("gender", DEFAULT_PREFS["gender"])
    size = context.user_data.get("size", DEFAULT_PREFS["size"])
    price = val

    user = set_user_prefs(chat_id, gender=gender, size=size, price=price)
    update.message.reply_text(
        f"✅ Preferences saved!\n\n{format_prefs(user)}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END

def prefs_cancel(update: Update, context: CallbackContext):
    update.message.reply_text("Canceled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def help_cmd(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Commands:\n"
        "/start — register & show prefs\n"
        "/show — show current prefs\n"
        "/set men 43 0-300 — quick set\n"
        "/prefs — guided setup\n",
        parse_mode=ParseMode.MARKDOWN,
    )

# --------- Main ---------
def main():
    token = TELEGRAM_TOKEN.strip()
    if not token:
        raise SystemExit("TELEGRAM_TOKEN is missing. Set it in ENV or config.py")

    updater = Updater(token=token, use_context=True)
    dp = updater.dispatcher

    # Basic commands
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("show", show))
    dp.add_handler(CommandHandler("set", quick_set))
    dp.add_handler(CommandHandler("help", help_cmd))

    # /prefs conversation
    conv = ConversationHandler(
        entry_points=[CommandHandler("prefs", prefs_start)],
        states={
            CHOOSE_CATEGORY: [MessageHandler(Filters.text & ~Filters.command, prefs_choose_category)],
            CHOOSE_SIZE:     [MessageHandler(Filters.text & ~Filters.command, prefs_choose_size)],
            CHOOSE_PRICE:    [MessageHandler(Filters.text & ~Filters.command, prefs_choose_price)],
        },
        fallbacks=[CommandHandler("cancel", prefs_cancel)],
        allow_reentry=True,
    )
    dp.add_handler(conv)

    # Start bot (polling)
    updater.start_polling(clean=True)
    updater.idle()

if __name__ == "__main__":
    main()
