import os
import json
import requests

from config import *

BOT_TOKEN = (
    os.getenv("TELEGRAM_BOT_TOKEN")
    or os.getenv("TELEGRAM_TOKEN")
    or TELEGRAM_TOKEN
).strip()

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send(chat_id, text):
    requests.post(f"{API}/sendMessage", data={
        "chat_id": chat_id,
        "text": text
    })

def load(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

users = load(USER_DATA_FILE, {})
last_update = load("last_update_id.json", {}).get("last_update_id", 0)

resp = requests.get(f"{API}/getUpdates", params={"offset": last_update + 1}).json()
updates = resp.get("result", [])

for u in updates:
    last_update = u["update_id"]

    msg = u.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = (msg.get("text") or "").strip()

    if not chat_id:
        continue

    if text == "/start":
        send(chat_id,
            "👋 ברוך הבא לבוט Timberland!\n\n"
            "📦 אתה תקבל מוצרים *פעמיים ביום בלבד*:\n"
            "🕖 07:00 בבוקר\n"
            "🕖 19:00 בערב\n\n"
            "כדי להגדיר מעקב – שלח:\n"
            "מגדר, סוג, מידה, מחיר מינימום, מחיר מקסימום\n\n"
            "דוגמה:\n"
            "1 A 43 0 300"
        )
        users[str(chat_id)] = {"chat_id": chat_id}
        continue

    parts = text.split()
    if len(parts) == 5:
        g, c, size, pmin, pmax = parts
        users[str(chat_id)] = {
            "chat_id": chat_id,
            "gender": {"1": "men", "2": "women", "3": "kids"}.get(g),
            "category": {"A": "shoes", "B": "clothing", "C": "both"}.get(c),
            "size": size,
            "apparel_size": size,
            "price_min": int(pmin),
            "price_max": int(pmax),
        }
        send(chat_id, "✅ ההעדפות נשמרו! תקבל מוצרים ב־07:00 וב־19:00")

save(USER_DATA_FILE, users)
save("last_update_id.json", {"last_update_id": last_update})