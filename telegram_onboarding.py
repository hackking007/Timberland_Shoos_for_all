import os
import json
import requests

from config import *

# ---------------- Token ----------------
BOT_TOKEN = (
    os.getenv("TELEGRAM_BOT_TOKEN")
    or os.getenv("TELEGRAM_TOKEN")
    or TELEGRAM_TOKEN
    or ""
).strip()

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ---------------- IO helpers ----------------
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------------- Telegram helpers ----------------
def send(chat_id, text):
    try:
        r = requests.post(f"{API}/sendMessage", data={"chat_id": chat_id, "text": text}, timeout=20)
        if ENABLE_DEBUG_LOGS:
            print(f"send_message to {chat_id} -> {r.status_code}")
    except Exception as e:
        print(f"send_message error: {e}")

def safe_int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default

# ---------------- Load state ----------------
users = load_json(USER_DATA_FILE, {})

last_update_obj = load_json("last_update_id.json", {})
last_update = safe_int(last_update_obj.get("last_update_id", 0), 0)

if ENABLE_DEBUG_LOGS:
    print("=== telegram_onboarding.py starting ===")
    print(f"Loaded users: {len(users)}")
    print(f"Last update id: {last_update}")

# ---------------- Fetch updates ----------------
params = {"offset": last_update + 1}
try:
    resp = requests.get(f"{API}/getUpdates", params=params, timeout=30).json()
except Exception as e:
    print(f"getUpdates failed: {e}")
    raise SystemExit(1)

updates = resp.get("result", [])
if ENABLE_DEBUG_LOGS:
    print(f"getUpdates returned {len(updates)} updates")

# ---------------- Process ----------------
for u in updates:
    update_id = u.get("update_id")
    if isinstance(update_id, int):
        last_update = update_id

    msg = u.get("message", {}) or {}
    chat = msg.get("chat", {}) or {}
    chat_id = chat.get("id")
    text = (msg.get("text") or "").strip()

    if not chat_id:
        continue

    if ENABLE_DEBUG_LOGS:
        print(f"handle_message: chat_id={chat_id}, text='{text}'")

    if text == "/start":
        send(
            chat_id,
            "👋 ברוך הבא לבוט Timberland!\n\n"
            "📦 מוצרים נשלחים פעמיים ביום:\n"
            "07:00 בבוקר\n"
            "19:00 בערב\n\n"
            "כדי להגדיר מעקב בהודעה אחת, שלחו בפורמט:\n"
            "<gender> <type> <size> <min_price> <max_price>\n\n"
            "gender:\n"
            "1 = גברים\n"
            "2 = נשים\n"
            "3 = ילדים\n\n"
            "type:\n"
            "A = הנעלה\n"
            "B = ביגוד\n"
            "C = גם וגם\n\n"
            "דוגמה:\n"
            "1 A 43 0 300"
        )
        users[str(chat_id)] = users.get(str(chat_id), {"chat_id": chat_id})
        continue

    # Expected format: "1 A 43 0 300"
    parts = text.split()
    if len(parts) == 5:
        g, c, size, pmin, pmax = parts

        gender_map = {"1": "men", "2": "women", "3": "kids"}
        cat_map = {"A": "shoes", "B": "clothing", "C": "both"}

        gender = gender_map.get(g)
        category = cat_map.get(c.upper())

        if not gender or not category:
            send(chat_id, "❌ פורמט לא תקין. נסה שוב לפי הדוגמה: 1 A 43 0 300")
            continue

        price_min = safe_int(pmin, 0)
        price_max = safe_int(pmax, 0)

        users[str(chat_id)] = {
            "chat_id": int(chat_id),
            "state": "ready",
            "gender": gender,
            "category": category,
            # כרגע אנחנו שומרים גם size וגם apparel_size באותו שדה,
            # בהמשך נפריד מידות ביגוד (S-XXXL) ממידות נעליים.
            "size": str(size),
            "apparel_size": str(size).upper(),
            "price_min": price_min,
            "price_max": price_max,
        }

        send(chat_id, "✅ ההעדפות נשמרו! תקבל מוצרים ב-07:00 וב-19:00")
        continue

# ---------------- Save state ----------------
save_json(USER_DATA_FILE, users)
save_json("last_update_id.json", {"last_update_id": last_update})

if ENABLE_DEBUG_LOGS:
    print(f"Onboarding sync done. New last_update_id: {last_update}")