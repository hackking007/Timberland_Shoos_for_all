# main_bot.py (PTB v20+ async)
# Auto-register chat_id on /start and store user preferences in user_data.json.
# Commands:
#   /start  -> registers user (chat_id) and shows prefs
#   /show   -> show current prefs
#   /set men 43 0-300  -> quick setup
#   /prefs  -> guided setup (category -> size -> price)
#   /help   -> command help
#
# Requires:
#   python-telegram-bot >= 20.0
#   config.py that exposes TELEGRAM_TOKEN (recommended to read from ENV)
#
# Example config.py:
#   import os
#   TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()

import json
from pathlib import Path
from typing import Dict, Any, Tuple

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, constants
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ---- Load token from config.py (fallback to ENV if needed) ----
try:
    from config import TELEGRAM_TOKEN  # should read from ENV inside config.py
except Exception:
    import os
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()

USER_DATA_FILE = "user_data.json"

# Defaults (must match your scraper's expectations)
DEFAULT_PREFS = {
    "gender": "men",    # men / women / kids
    "size": "43",       # as string; mapped via size_map.json
    "price": "0-300",   # "min-max"
}

# Conversation states
CHOOSE_CATEGORY, CHOOSE_SIZE, CHOOSE_PRICE = range(3)


# ---------------- Storage helpers ----------------
def load_users() -> Dict[str, Any]:
    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def save_users(data: Dict[str, Any]) -> None:
    Path(USER_DATA_FILE).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_or_create_user(chat_id: int) -> Dict[str, Any]:
    users = load_users()
    key = str(chat_id)
    if key not in users:
        users[key] = {"chat_id": chat_id, **DEFAULT_PREFS}
        save_users(users)
    return users[key]


def set_user_prefs(
    chat_id: int, *, gender: str | None = None, size: str | None = None, price: str | None = None
) -> Dict[str, Any]:
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


# ---------------- Utilities ----------------
def format_prefs(u: Dict[str, Any]) -> str:
    return (
        "*Your preferences:*\n"
        f"• Category: `{u.get('gender','-')}`\n"
        f"• Size: `{u.get('size','-')}`\n"
        f"• Price: `{u.get('price','-')}`"
    )


def parse_set_args(text: str) -> Tuple[str | None, str | None, str | None]:
    # Expected: "/set men 43 0-300"
    parts = (text or "").strip().split()
    if len(parts) == 4 and parts[0].lower() == "/set":
        gender, size, price = parts[1].lower(), parts[2], parts[3]
        if gender not in {"men", "women", "kids"}:
            return None, None, None
        if "-" not in price:
            return None, None, None
        return gender, size, price
    return None, None, None


# ---------------- Handlers (async) ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Auto-register user on /start and show prefs."""
    chat_id = update.effective_chat.id
    user = get_or_create_user(chat_id)

    msg = (
        f"✅ Registered! Your chat_id is `{chat_id}`\n\n"
        f"{format_prefs(user)}\n\n"
        "You can update via:\n"
        "• /prefs (guided)\n"
        "• /set men 43 0-300 (quick)\n"
        "• /show (show current)"
    )
    await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)


async def show(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = get_or_create_user(chat_id)
    await update.message.reply_text(format_prefs(user), parse_mode=constants.ParseMode.MARKDOWN)


async def quick_set(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    gender, size, price = parse_set_args(update.message.text or "")
    if not all([gender, size, price]):
        await update.message.reply_text(
            "Usage: `/set men 43 0-300`\n(valid genders: men / women / kids)",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return
    user = set_user_prefs(chat_id, gender=gender, size=size, price=price)
    await update.message.reply_text(
        f"✅ Updated!\n\n{format_prefs(user)}",
        parse_mode=constants.ParseMode.MARKDOWN,
    )


# ---- /prefs conversation ----
async def prefs_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    get_or_create_user(chat_id)  # ensure user exists

    reply_kb = [["men", "women", "kids"]]
    await update.message.reply_text(
        "Select category (men / women / kids):",
        reply_markup=ReplyKeyboardMarkup(reply_kb, one_time_keyboard=True, resize_keyboard=True),
    )
    return CHOOSE_CATEGORY


async def prefs_choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    val = (update.message.text or "").strip().lower()
    if val not in {"men", "women", "kids"}:
        await update.message.reply_text("Please choose one of: men / women / kids")
        return CHOOSE_CATEGORY
    context.user_data["gender"] = val
    await update.message.reply_text("Enter size (e.g., 43):", reply_markup=ReplyKeyboardRemove())
    return CHOOSE_SIZE


async def prefs_choose_size(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    val = (update.message.text or "").strip()
    if not val:
        await update.message.reply_text("Please enter a size, e.g., 43")
        return CHOOSE_SIZE
    context.user_data["size"] = val
    await update.message.reply_text("Enter price range (min-max), e.g., 0-300:")
    return CHOOSE_PRICE


async def prefs_choose_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    val = (update.message.text or "").strip()
    if "-" not in val:
        await update.message.reply_text("Please enter price as min-max, e.g., 0-300:")
        return CHOOSE_PRICE

    chat_id = update.effective_chat.id
    gender = context.user_data.get("gender", DEFAULT_PREFS["gender"])
    size = context.user_data.get("size", DEFAULT_PREFS["size"])
    price = val

    user = set_user_prefs(chat_id, gender=gender, size=size, price=price)
    await update.message.reply_text(
        f"✅ Preferences saved!\n\n{format_prefs(user)}",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


async def prefs_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Canceled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Commands:\n"
        "/start — register & show prefs\n"
        "/show — show current prefs\n"
        "/set men 43 0-300 — quick set\n"
        "/prefs — guided setup\n",
        parse_mode=constants.ParseMode.MARKDOWN,
    )


# ---------------- App bootstrap ----------------
def build_app() -> Application:
    if not TELEGRAM_TOKEN:
        raise SystemExit("TELEGRAM_TOKEN is missing. Set it in ENV or config.py")
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Basic commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("show", show))
    app.add_handler(CommandHandler("set", quick_set))
    app.add_handler(CommandHandler("help", help_cmd))

    # /prefs conversation
    conv = ConversationHandler(
        entry_points=[CommandHandler("prefs", prefs_start)],
        states={
            CHOOSE_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, prefs_choose_category)],
            CHOOSE_SIZE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, prefs_choose_size)],
            CHOOSE_PRICE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, prefs_choose_price)],
        },
        fallbacks=[CommandHandler("cancel", prefs_cancel)],
        allow_reentry=True,
    )
    app.add_handler(conv)

    return app


def main() -> None:
    app = build_app()
    app.run_polling(allowed_updates=constants.Update.ALL_TYPES)


if __name__ == "__main__":
    main()
