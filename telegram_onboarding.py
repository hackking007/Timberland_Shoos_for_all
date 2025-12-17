import json
import re
import time
import requests

from config import (
    USER_DATA_FILE,
    LAST_UPDATE_ID_FILE,
    TELEGRAM_TOKEN,
    WELCOME_TEXT,
    ENABLE_DEBUG_LOGS,
)

API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# כמה זמן אחורה נחשב "backlog" ולא נענה עליו בכלל (בשניות)
BACKLOG_IGNORE_SECONDS = 600  # 10 דקות


def log(msg: str):
    if ENABLE_DEBUG_LOGS:
        print(msg)


def load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path: str, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def send_message(chat_id: int, text: str):
    url = f"{API}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    r = requests.post(url, data=payload, timeout=30)
    log(f"send_message to {chat_id} -> status {r.status_code}")
    return r


def parse_one_line(text: str):
    """
    Expected:
    <gender> <type> <size> <min_price> <max_price>

    gender: 1/2/3
    type: A/B/C

    size:
    - A: numeric shoe size (2 digits)
    - B: XS/S/M/L/XL/XXL/XXXL
    - C: shoeSize/clothingSize e.g. 40/L
    """
    parts = text.strip().split()
    if len(parts) != 5:
        return None

    gender_code, type_code, size_raw, min_p, max_p = parts

    if gender_code not in ("1", "2", "3"):
        return None
    if type_code.upper() not in ("A", "B", "C"):
        return None

    try:
        price_min = int(min_p)
        price_max = int(max_p)
        if price_min < 0 or price_max < 0 or price_min > price_max:
            return None
    except Exception:
        return None

    gender = {"1": "men", "2": "women", "3": "kids"}[gender_code]
    category = {"A": "shoes", "B": "clothing", "C": "both"}[type_code.upper()]

    shoes_size = None
    clothing_size = None

    if category == "shoes":
        if not re.fullmatch(r"\d{2}", size_raw):
            return None
        shoes_size = size_raw

    elif category == "clothing":
        s = size_raw.upper()
        if s not in ("XS", "S", "M", "L", "XL", "XXL", "XXXL"):
            return None
        clothing_size = s

    else:
        if "/" not in size_raw:
            return None
        a, b = size_raw.split("/", 1)
        a = a.strip()
        b = b.strip().upper()
        if not re.fullmatch(r"\d{2}", a):
            return None
        if b not in ("XS", "S", "M", "L", "XL", "XXL", "XXXL"):
            return None
        shoes_size = a
        clothing_size = b

    return {
        "gender": gender,
        "category": category,
        "shoes_size": shoes_size,
        "clothing_size": clothing_size,
        "price_min": price_min,
        "price_max": price_max,
    }


def ensure_user(user_data: dict, chat_id: int):
    k = str(chat_id)
    if k not in user_data:
        user_data[k] = {"chat_id": chat_id, "state": "awaiting_setup", "welcome_sent": False}
    if "welcome_sent" not in user_data[k]:
        user_data[k]["welcome_sent"] = False


def fetch_updates(offset: int | None):
    params = {}
    if offset is not None:
        params["offset"] = offset
    r = requests.get(f"{API}/getUpdates", params=params, timeout=30)
    data = r.json()
    if not data.get("ok"):
        raise SystemExit(f"Telegram getUpdates failed: {data}")
    return data.get("result", [])


def handle_message(chat_id: int, text: str, user_data: dict):
    text = (text or "").strip()
    if not text:
        return

    ensure_user(user_data, chat_id)

    t = text.lower()

    # /start - שולחים הוראות פעם אחת בלבד, ואחר כך שקט (בלי ספאם)
    if t == "/start":
        if not user_data[str(chat_id)].get("welcome_sent", False):
            send_message(chat_id, WELCOME_TEXT)
            user_data[str(chat_id)]["welcome_sent"] = True
        return

    if t == "/reset":
        u = user_data[str(chat_id)]
        u.update({
            "state": "awaiting_setup",
            "category": None,
            "gender": None,
            "shoes_size": None,
            "clothing_size": None,
            "price_min": None,
            "price_max": None,
        })
        send_message(chat_id, "✅ בוצע איפוס. שלח /start ואז הודעה בפורמט הנכון.")
        return

    if t == "/stat":
        total = len(user_data)
        ready = sum(1 for _, v in user_data.items() if v.get("state") == "ready")
        awaiting = total - ready
        send_message(
            chat_id,
            f"📊 סטטוס בוט\n\n"
            f"Total users: {total}\n"
            f"Ready: {ready}\n"
            f"Awaiting setup: {awaiting}"
        )
        return

    parsed = parse_one_line(text)
    if not parsed:
        # אם המשתמש לא ראה /start - לא נענה בכלל
        if user_data[str(chat_id)].get("welcome_sent", False):
            send_message(
                chat_id,
                "❌ פורמט לא תקין.\n\n"
                "דוגמה: 1 A 43 128 299\n"
                "דוגמה ל-C: 2 C 40/L 0 800"
            )
        return

    user_data[str(chat_id)] = {
        **user_data[str(chat_id)],
        "chat_id": chat_id,
        "state": "ready",
        "gender": parsed["gender"],
        "category": parsed["category"],
        "shoes_size": parsed["shoes_size"],
        "clothing_size": parsed["clothing_size"],
        "price_min": parsed["price_min"],
        "price_max": parsed["price_max"],
    }

    gender_label = {"men": "גברים", "women": "נשים", "kids": "ילדים"}[parsed["gender"]]
    category_label = {"shoes": "הנעלה", "clothing": "ביגוד", "both": "גם וגם"}[parsed["category"]]

    size_part = []
    if parsed["category"] in ("shoes", "both"):
        size_part.append(f"נעליים: {parsed['shoes_size']}")
    if parsed["category"] in ("clothing", "both"):
        size_part.append(f"ביגוד: {parsed['clothing_size']}")

    send_message(
        chat_id,
        "✅ הגדרות נשמרו בהצלחה!\n\n"
        f"מגדר: {gender_label}\n"
        f"סוג מוצר: {category_label}\n"
        f"מידה: {' | '.join(size_part)}\n"
        f"טווח מחירים: {parsed['price_min']} - {parsed['price_max']} ₪\n\n"
        "🕖 מוצרים נשלחים פעמיים ביום (שעון ישראל): 07:00 ו-19:00"
    )


def main():
    if not TELEGRAM_TOKEN:
        raise SystemExit("TELEGRAM_TOKEN is missing. Set it in GitHub Secrets.")

    log("=== telegram_onboarding.py starting ===")

    user_data = load_json(USER_DATA_FILE, {})
    last_obj = load_json(LAST_UPDATE_ID_FILE, {"last_update_id": 0})
    last_update = last_obj.get("last_update_id", 0)
    if not isinstance(last_update, int):
        last_update = 0

    offset = last_update + 1 if last_update > 0 else None
    updates = fetch_updates(offset=offset)
    log(f"getUpdates returned {len(updates)} updates")

    # אם יש /sync בתוך ה-batch הזה - ננקה backlog מיידית בלי לעבד שום דבר נוסף
    # (כדי לעצור את הספאם כבר באותה ריצה)
    saw_sync = False
    max_update_id = last_update

    for upd in updates:
        uid = upd.get("update_id")
        if isinstance(uid, int):
            max_update_id = max(max_update_id, uid)

        msg = upd.get("message") or upd.get("edited_message")
        if not msg:
            continue

        chat_id = (msg.get("chat") or {}).get("id")
        text = (msg.get("text") or "").strip()

        if not isinstance(chat_id, int):
            continue

        if text.lower() == "/sync":
            saw_sync = True
            ensure_user(user_data, chat_id)
            user_data[str(chat_id)]["welcome_sent"] = user_data[str(chat_id)].get("welcome_sent", False)
            # נענה פעם אחת בלבד
            send_message(chat_id, "✅ Sync done. Backlog cleared.")
            break

    if saw_sync:
        save_json(USER_DATA_FILE, user_data)
        save_json(LAST_UPDATE_ID_FILE, {"last_update_id": max_update_id})
        log(f"Backlog cleared via /sync. last_update_id set to {max_update_id}")
        return

    now = int(time.time())

    for upd in updates:
        uid = upd.get("update_id")
        if isinstance(uid, int):
            max_update_id = max(max_update_id, uid)

        msg = upd.get("message") or upd.get("edited_message")
        if not msg:
            continue

        msg_date = msg.get("date")
        if isinstance(msg_date, int):
            # לא עונים על backlog ישן (מפסיק ספאם)
            if now - msg_date > BACKLOG_IGNORE_SECONDS:
                continue

        chat_id = (msg.get("chat") or {}).get("id")
        text = msg.get("text", "")

        if not isinstance(chat_id, int):
            continue

        handle_message(chat_id, text, user_data)

    save_json(USER_DATA_FILE, user_data)
    save_json(LAST_UPDATE_ID_FILE, {"last_update_id": max_update_id})
    log(f"Onboarding sync done. New last_update_id: {max_update_id}")


if __name__ == "__main__":
    main()
