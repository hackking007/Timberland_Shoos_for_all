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
            print(f"send_message -> {r.status_code}")
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
            print(f"send_photo -> {r.status_code}")
    except Exception as e:
        print(f"Telegram photo error: {e}")

# ---------------- Load / save ----------------
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

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
    if gender not in CLOTHING_URLS:
        return None

    base = f"{CLOTHING_URLS[gender]}?price={price_min}_{price_max}"
    size_code = APPAREL_SIZE_MAP.get(gender, {}).get(str(apparel_size).upper())

    if size_code:
        base += f"&size={size_code}"

    return base + "&product_list_order=low_to_high"

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

        link = a.get("href")
        if not link.startswith("http"):
            link = "https://www.timberland.co.il" + link

        price_vals = []
        for p in prices:
            try:
                price_vals.append(float(
                    p.text.replace("₪", "").replace(",", "").strip()
                ))
            except Exception:
                pass

        if not price_vals:
            continue

        products.append({
            "title": img.get("alt", "Item"),
            "link": link,
            "img": img.get("src"),
            "price": min(price_vals)
        })

    return products

# ---------------- Main ----------------
def check_shoes():
    ok, now, reason = should_run_checker_now()
    if not ok:
        print(f"Not in send window ({now.strftime('%H:%M')}), skip. Reason: {reason}")
        return

    print(f"Checker running ({reason}) at {now.strftime('%H:%M')}")

    users = load_json(USER_DATA_FILE, {})
    prev_state = load_json(STATE_FILE, {})
    new_state = {}

    for uid, u in users.items():
        chat_id = u.get("chat_id")
        gender = u.get("gender")
        category = u.get("category")
        price_min = u.get("price_min")
        price_max = u.get("price_max")

        urls = []

        if category in ("shoes", "both"):
            url = build_shoes_url(gender, u.get("size"), price_min, price_max)
            if url:
                urls.append(("Shoes", url))

        if category in ("clothing", "both"):
            url = build_clothing_url(gender, u.get("apparel_size"), price_min, price_max)
            if url:
                urls.append(("Clothing", url))

        for label, url in urls:
            print(f"Scanning {label} for user {uid}")
            products = scrape_products(url)

            for p in products:
                key = f"{uid}:{label}:{p['link']}"
                new_state[key] = p

                if key not in prev_state:
                    caption = (
                        f"<b>{html.escape(p['title'])}</b>\n"
                        f"₪{int(p['price'])}\n"
                        f"<a href='{p['link']}'>למוצר</a>"
                    )
                    send_photo(p["img"], caption, chat_id)

    save_json(STATE_FILE, new_state)

if __name__ == "__main__":
    check_shoes()