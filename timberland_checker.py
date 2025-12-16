import os
import json
import html
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from datetime import datetime
from zoneinfo import ZoneInfo

from config import *

# ---------------- Token ----------------
BOT_TOKEN = (
    os.getenv("TELEGRAM_BOT_TOKEN")
    or os.getenv("TELEGRAM_TOKEN")
    or TELEGRAM_TOKEN
    or ""
).strip()

# ---------------- Helpers ----------------
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def safe_int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default

# ---------------- Time window logic ----------------
SEND_HOURS = [7, 19]  # 07:00, 19:00 Israel time

def should_run_checker_now():
    tz = ZoneInfo("Asia/Jerusalem")
    now = datetime.now(tz)

    # Manual GitHub run - always run
    if os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch":
        return True, now, "manual run"

    # Cron run - only exact hours
    if now.minute != 0:
        return False, now, "minute not 00"
    if now.hour not in SEND_HOURS:
        return False, now, "hour not in send window"

    return True, now, "in send window"

# ---------------- Telegram helpers ----------------
def send_telegram_message(text, chat_id=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id or ADMIN_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, data=payload, timeout=20)
        if ENABLE_DEBUG_LOGS:
            print(f"send_message -> {r.status_code} {r.text[:120]}")
    except Exception as e:
        print(f"Telegram send error: {e}")

def send_photo(image_url, caption, chat_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": chat_id,
        "photo": image_url or "https://via.placeholder.com/300",
        "caption": caption,
        "parse_mode": "HTML"
    }
    try:
        r = requests.post(url, data=payload, timeout=20)
        if ENABLE_DEBUG_LOGS:
            print(f"send_photo -> {r.status_code} {r.text[:120]}")
    except Exception as e:
        print(f"Telegram photo error: {e}")

# ---------------- Load mappings ----------------
# Shoes size map comes from size_map.json
SIZE_MAP = load_json(SIZE_MAP_FILE, {})

# Clothing URLs - fallback if not defined in config.py
CLOTHING_URLS = {
    "men": "https://www.timberland.co.il/men/clothing",
    "women": "https://www.timberland.co.il/women/clothing",
    "kids": "https://www.timberland.co.il/kids/clothing"
}

# Apparel size map - fallback (you can refine later)
# Based on your example: L -> size=4
APPAREL_SIZE_MAP = {
    "men": {
        "S": 2, "M": 3, "L": 4, "XL": 5, "XXL": 6, "XXXL": 7
    },
    "women": {
        "S": 2, "M": 3, "L": 4, "XL": 5, "XXL": 6, "XXXL": 7
    },
    "kids": {
        "S": 2, "M": 3, "L": 4, "XL": 5
    }
}

# ---------------- URL builders ----------------
def build_shoes_url(gender, size, price_min, price_max):
    if gender not in CATEGORIES:
        return None
    size_code = SIZE_MAP.get(gender, {}).get(str(size))
    if not size_code:
        return None
    return (
        f"{CATEGORIES[gender]['url']}?"
        f"price={price_min}_{price_max}&size={size_code}"
        f"&product_list_order=low_to_high"
    )

def build_clothing_url(gender, apparel_size, price_min, price_max):
    base_url = CLOTHING_URLS.get(gender)
    if not base_url:
        return None

    url = f"{base_url}?price={price_min}_{price_max}"

    # If we have a known apparel size code, add it.
    # If not (e.g., women page has no size filters), still allow scan without size param.
    size_code = APPAREL_SIZE_MAP.get(gender, {}).get(str(apparel_size).upper())
    if size_code:
        url += f"&size={size_code}"

    url += "&product_list_order=low_to_high"
    return url

# ---------------- Scraper ----------------
def scrape_products(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(locale="he-IL")
        page.goto(url, timeout=SCAN_TIMEOUT)
        page.wait_for_load_state("networkidle")

        for _ in range(MAX_LOAD_MORE_CLICKS):
            try:
                btn = page.query_selector("a.action.more")
                if not btn:
                    break
                btn.click()
                page.wait_for_timeout(LOAD_MORE_DELAY)
            except Exception:
                break

        soup = BeautifulSoup(page.content(), "html.parser")
        browser.close()

    products = []
    for card in soup.select("div.product"):
        a = card.select_one("a")
        img = card.select_one("img")
        prices = card.select("span.price")

        if not a or not prices:
            continue

        link = a.get("href", "")
        if not link:
            continue
        if not link.startswith("http"):
            link = "https://www.timberland.co.il" + link

        price_vals = []
        for p in prices:
            try:
                t = p.text.replace("₪", "").replace(",", "").strip()
                if t:
                    price_vals.append(float(t))
            except Exception:
                pass

        if not price_vals:
            continue

        products.append({
            "title": img.get("alt", "Item").strip() if img else "Item",
            "link": link,
            "img": img.get("src") if img else None,
            "price": min(price_vals)
        })

    return products

# ---------------- Main ----------------
def check_shoes():
    ok, now, reason = should_run_checker_now()
    if not ok:
        print(f"Not in send window (IL {now.strftime('%H:%M')}), skip. Reason: {reason}")
        return

    print(f"Checker running ({reason}) at {now.strftime('%H:%M')}")

    users = load_json(USER_DATA_FILE, {})
    prev_state = load_json(STATE_FILE, {})
    new_state = {}

    if ENABLE_DEBUG_LOGS:
        print(f"user_data loaded: {json.dumps(users, ensure_ascii=False, indent=2)[:1500]}")

    for uid, u in users.items():
        chat_id = u.get("chat_id")
        gender = u.get("gender")
        category = u.get("category")

        price_min = safe_int(u.get("price_min"), 0)
        price_max = safe_int(u.get("price_max"), 0)

        urls = []

        # shoes
        if category in ("shoes", "both"):
            shoes_url = build_shoes_url(gender, u.get("size"), price_min, price_max)
            if shoes_url:
                urls.append(("Shoes", shoes_url))
            else:
                if ENABLE_DEBUG_LOGS:
                    print(f"Could not build shoes URL for user {uid} (gender={gender}, size={u.get('size')})")

        # clothing
        if category in ("clothing", "both"):
            clothing_url = build_clothing_url(gender, u.get("apparel_size"), price_min, price_max)
            if clothing_url:
                urls.append(("Clothing", clothing_url))
            else:
                if ENABLE_DEBUG_LOGS:
                    print(f"Could not build clothing URL for user {uid} (gender={gender}, apparel_size={u.get('apparel_size')})")

        for label, url in urls:
            print(f"Launching browser for user {uid} - URL: {url}")
            products = scrape_products(url)
            print(f"Found {len(products)} products for user {uid} ({label})")

            if not products:
                msg = (
                    f"<b>לא נמצאו פריטים כרגע</b>\n"
                    f"User: <code>{html.escape(str(uid))}</code>\n"
                    f"Type: {html.escape(label)}\n"
                    f"<a href='{html.escape(url)}'>Search link</a>"
                )
                send_telegram_message(msg, chat_id=chat_id)
                continue

            sent_new = 0
            for p in products:
                key = f"{uid}:{label}:{p['link']}"
                new_state[key] = p

                if key not in prev_state:
                    caption = (
                        f"<b>{html.escape(p['title'][:120])}</b>\n"
                        f"₪{int(p['price'])}\n"
                        f"<a href='{html.escape(p['link'])}'>למוצר</a>"
                    )
                    send_photo(p.get("img"), caption, chat_id)
                    sent_new += 1

            # summary (safe HTML)
            summary_lines = []
            for i, p in enumerate(sorted(products, key=lambda x: x["price"])[:10], 1):
                summary_lines.append(
                    f"{i}. <b>{html.escape(p['title'][:60])}</b> - ₪{int(p['price'])}\n{html.escape(p['link'])}"
                )

            summary = (
                f"<b>סיכום תוצאות</b> ({html.escape(label)})\n"
                + "\n\n".join(summary_lines)
                + f"\n\n<a href='{html.escape(url)}'>Search link</a>"
            )

            send_telegram_message(summary, chat_id=chat_id)
            print(f"Sent {sent_new} new items to user {uid} ({label})")

    save_json(STATE_FILE, new_state)
    print(f"Saved current_state with {len(new_state)} items total.")

if __name__ == "__main__":
    check_shoes()