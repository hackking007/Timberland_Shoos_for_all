import os
import re
import json
import requests
from datetime import datetime

# config.py חייב להכיל לפחות:
# USER_DATA_FILE = "user_data.json"
# LAST_UPDATE_ID_FILE = "last_update_id.json"
# ENABLE_DEBUG_LOGS = True/False
# ENABLE_ADMIN_NOTIFICATIONS = True/False
# ADMIN_CHAT_ID = <int>
# (אפשר גם TELEGRAM_TOKEN, אבל אנחנו נעדיף env בשם TELEGRAM_BOT_TOKEN)
from config import USER_DATA_FILE, LAST_UPDATE_ID_FILE, ENABLE_DEBUG_LOGS, ENABLE_ADMIN_NOTIFICATIONS, ADMIN_CHAT_ID

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")  # fallback אם יש לך משתנה אחר


# ---------------- Telegram helpers ----------------

def tg_api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"


def send_message(chat_id: int, text: str, disable_preview: bool = True) -> None:
    url = tg_api_url("sendMessage")
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": disable_preview,
    }
    try:
        resp = requests.post(url, data=payload, timeout=30)
        if ENABLE_DEBUG_LOGS:
            print(f"send_message to {chat_id} -> status {resp.status_code}")
    except Exception as e:
        if ENABLE_DEBUG_LOGS:
            print(f"send_message error: {e}")


def admin_notify(text: str) -> None:
    if not ENABLE_ADMIN_NOTIFICATIONS:
        return
    try:
        send_message(ADMIN_CHAT_ID, text)
    except Exception:
        pass


# ---------------- Persistence ----------------

def load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception as e:
        if ENABLE_DEBUG_LOGS:
            print(f"load_json error for {path}: {e}")
        return default


def save_json(path: str, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        if ENABLE_DEBUG_LOGS:
            print(f"save_json error for {path}: {e}")


def load_user_data() -> dict:
    return load_json(USER_DATA_FILE, {})


def save_user_data(data: dict) -> None:
    save_json(USER_DATA_FILE, data)


def load_last_update_id():
    # נשתדל לתמוך גם בפורמט {"last_update_id": 123} וגם במספר חשוף
    raw = load_json(LAST_UPDATE_ID_FILE, None)
    if raw is None:
        return None
    if isinstance(raw, dict) and "last_update_id" in raw:
        return raw.get("last_update_id")
    if isinstance(raw, int):
        return raw
    return None


def save_last_update_id(update_id: int) -> None:
    save_json(LAST_UPDATE_ID_FILE, {"last_update_id": update_id})


# ---------------- Parsing ----------------

ONE_SHOT_RE = re.compile(r"^\s*([123])\s+([ABCabc])\s+(\d{1,2})\s+(\d+)\s+(\d+)\s*$")


def map_gender(code: str) -> str:
    return {"1": "men", "2": "women", "3": "kids"}.get(code, "men")


def map_category(code: str) -> str:
    code = code.upper()
    return {"A": "shoes", "B": "clothing", "C": "both"}.get(code, "shoes")


def welcome_text() -> str:
    return (
        "👟 <b>ברוך הבא לבוט מעקב טימברלנד!</b>\n\n"
        "הבוט יסרוק את Timberland.co.il וישלח לך מוצרים שמתאימים להעדפות שלך.\n\n"
        "📬 <b>עדכוני מוצרים נשלחים פעמיים ביום</b> - בערך בשעות <b>07:00</b> ו-<b>19:00</b> (שעון ישראל).\n\n"
        "כדי להגדיר מעקב מותאם אישית בהודעה אחת, שלח את ההודעה בפורמט:\n\n"
        "<b>מגדר</b> <b>סוג מוצר</b> <b>מידה</b> <b>מחיר מינימלי</b> <b>מחיר מקסימלי</b>\n\n"
        "קידודים:\n"
        "1 - גברים\n"
        "2 - נשים\n"
        "3 - ילדים\n\n"
        "A - הנעלה\n"
        "B - ביגוד\n"
        "C - גם וגם\n\n"
        "דוגמה:\n"
        "<code>1 A 43 128 299</code>\n\n"
        "אפשר גם להגדיר בהודעות נפרדות אם נוח לך - הבוט יוביל אותך שלב-שלב.\n\n"
        "סטטוס משתמשים: שלח <code>/stat</code>"
    )


def stat_text(user_data: dict) -> str:
    total = len(user_data)
    ids = list(user_data.keys())[:20]
    return (
        f"📊 <b>Stats</b>\n"
        f"Users registered: <b>{total}</b>\n"
        f"Sample IDs: <code>{', '.join(ids)}</code>"
    )


# ---------------- Legacy step-by-step flow ----------------
# נשמור "שלב" למשתמש כדי לתמוך באפשרות הישנה (1 -> size -> min -> max)
# state values:
# - awaiting_gender
# - awaiting_category
# - awaiting_size
# - awaiting_price_min
# - awaiting_price_max
# - ready

def ensure_user(user_data: dict, chat_id: int) -> dict:
    key = str(chat_id)
    if key not in user_data:
        user_data[key] = {"chat_id": chat_id, "state": "awaiting_gender"}
    if "chat_id" not in user_data[key]:
        user_data[key]["chat_id"] = chat_id
    if "state" not in user_data[key]:
        user_data[key]["state"] = "awaiting_gender"
    return user_data[key]


def handle_one_shot(user_data: dict, chat_id: int, text: str) -> bool:
    m = ONE_SHOT_RE.match(text)
    if not m:
        return False

    g_code, c_code, size, pmin, pmax = m.groups()
    prefs = ensure_user(user_data, chat_id)

    prefs["gender"] = map_gender(g_code)
    prefs["category"] = map_category(c_code)
    prefs["size"] = str(int(size))
    prefs["price_min"] = int(pmin)
    prefs["price_max"] = int(pmax)
    prefs["state"] = "ready"

    send_message(
        chat_id,
        "✅ נשמר!\n\n"
        f"מגדר: <b>{prefs['gender']}</b>\n"
        f"סוג מוצר: <b>{prefs['category']}</b>\n"
        f"מידה: <b>{prefs['size']}</b>\n"
        f"טווח: <b>{prefs['price_min']}-{prefs['price_max']}</b>\n\n"
        "תתחיל לקבל עדכונים אוטומטית בשעות 07:00 ו-19:00 (שעון ישראל)."
    )
    return True


def handle_step_by_step(user_data: dict, chat_id: int, text: str) -> None:
    prefs = ensure_user(user_data, chat_id)
    state = prefs.get("state", "awaiting_gender")

    # התחלה מחדש
    if text.strip().lower() in ["/start", "start", "start/", "/restart"]:
        prefs["state"] = "awaiting_gender"
        send_message(chat_id, welcome_text())
        send_message(chat_id, "בחר מגדר: 1-גברים, 2-נשים, 3-ילדים")
        return

    if text.strip().lower() == "/stat":
        send_message(chat_id, stat_text(user_data))
        return

    # אם הגיעו הודעות בפורמט "one shot", נטפל בזה כאן (גם בתוך step flow)
    if handle_one_shot(user_data, chat_id, text):
        return

    # זרימה ישנה
    if state == "awaiting_gender":
        if text.strip() in ["1", "2", "3"]:
            prefs["gender"] = map_gender(text.strip())
            prefs["state"] = "awaiting_category"
            send_message(chat_id, "סוג מוצר: A-הנעלה, B-ביגוד, C-גם וגם")
        else:
            send_message(chat_id, "אנא בחר מגדר: 1-גברים, 2-נשים, 3-ילדים")
        return

    if state == "awaiting_category":
        c = text.strip().upper()
        if c in ["A", "B", "C"]:
            prefs["category"] = map_category(c)
            prefs["state"] = "awaiting_size"
            send_message(chat_id, "אנא הזן מידה (לדוגמה 43)")
        else:
            send_message(chat_id, "אנא בחר: A-הנעלה, B-ביגוד, C-גם וגם")
        return

    if state == "awaiting_size":
        if text.strip().isdigit():
            prefs["size"] = str(int(text.strip()))
            prefs["state"] = "awaiting_price_min"
            send_message(chat_id, "אנא הזן מחיר מינימלי (לדוגמה 0)")
        else:
            send_message(chat_id, "מידה לא תקינה. נסה שוב (מספר בלבד).")
        return

    if state == "awaiting_price_min":
        if text.strip().isdigit():
            prefs["price_min"] = int(text.strip())
            prefs["state"] = "awaiting_price_max"
            send_message(chat_id, "אנא הזן מחיר מקסימלי (לדוגמה 300)")
        else:
            send_message(chat_id, "מחיר מינימלי לא תקין. נסה שוב (מספר בלבד).")
        return

    if state == "awaiting_price_max":
        if text.strip().isdigit():
            prefs["price_max"] = int(text.strip())
            # נוודא מינימום <= מקסימום
            if prefs["price_min"] > prefs["price_max"]:
                prefs["price_min"], prefs["price_max"] = prefs["price_max"], prefs["price_min"]
            prefs["state"] = "ready"
            send_message(
                chat_id,
                "✅ נשמר!\n\n"
                f"מגדר: <b>{prefs.get('gender')}</b>\n"
                f"סוג מוצר: <b>{prefs.get('category')}</b>\n"
                f"מידה: <b>{prefs.get('size')}</b>\n"
                f"טווח: <b>{prefs.get('price_min')}-{prefs.get('price_max')}</b>\n\n"
                "תתחיל לקבל עדכונים אוטומטית בשעות 07:00 ו-19:00 (שעון ישראל).\n"
                "אם תרצה לעדכן הכל בהודעה אחת, שלח לדוגמה: <code>1 A 43 128 299</code>"
            )
        else:
            send_message(chat_id, "מחיר מקסימלי לא תקין. נסה שוב (מספר בלבד).")
        return

    # ready
    send_message(
        chat_id,
        "אני כבר מוגדר ומוכן. כדי לעדכן הגדרות שלח שוב הודעה בפורמט:\n"
        "<code>1 A 43 128 299</code>\n"
        "או שלח /start כדי להתחיל מחדש."
    )


# ---------------- Telegram polling ----------------

def get_updates(offset=None):
    url = tg_api_url("getUpdates")
    params = {}
    if offset is not None:
        params["offset"] = offset
    if ENABLE_DEBUG_LOGS:
        print(f"Calling getUpdates with params: {params}")
    resp = requests.get(url, params=params, timeout=30)
    if ENABLE_DEBUG_LOGS:
        print(f"getUpdates HTTP status: {resp.status_code}")
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram error: {data}")
    return data.get("result", [])


def extract_message(update: dict):
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return None, None
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    text = msg.get("text", "")
    return chat_id, text


def main():
    print("=== telegram_onboarding.py starting ===")
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    user_data = load_user_data()
    last_update_id = load_last_update_id()

    updates = get_updates(offset=(last_update_id + 1) if isinstance(last_update_id, int) else None)
    print(f"getUpdates returned {len(updates)} updates")

    new_last_update_id = last_update_id

    for upd in updates:
        upd_id = upd.get("update_id")
        if isinstance(upd_id, int):
            new_last_update_id = upd_id if (new_last_update_id is None or upd_id > new_last_update_id) else new_last_update_id

        chat_id, text = extract_message(upd)
        if not chat_id:
            continue

        text = text or ""
        print(f"handle_message: chat_id={chat_id}, text={repr(text)}")

        try:
            # תמיכה גם ב-/start וגם ב-flow/one-shot
            if text.strip().lower() == "/start":
                prefs = ensure_user(user_data, chat_id)
                prefs["state"] = "awaiting_gender"
                send_message(chat_id, welcome_text())
                send_message(chat_id, "בחר מגדר: 1-גברים, 2-נשים, 3-ילדים")
            elif text.strip().lower() == "/stat":
                send_message(chat_id, stat_text(user_data))
            else:
                handle_step_by_step(user_data, chat_id, text)
        except Exception as e:
            if ENABLE_DEBUG_LOGS:
                print(f"Error handling message for chat_id={chat_id}: {e}")
            send_message(chat_id, "אירעה שגיאה בעיבוד ההודעה. נסה שוב או שלח /start.")

    # שמירה
    save_user_data(user_data)
    if isinstance(new_last_update_id, int):
        save_last_update_id(new_last_update_id)

    print(f"Onboarding sync done. New last_update_id: {new_last_update_id}")


if __name__ == "__main__":
    main()
