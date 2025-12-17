# timberland_checker.py
import json
import time
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from config import (
    TELEGRAM_TOKEN,
    USER_DATA_FILE,
    STATE_FILE,
    SIZE_MAP_FILE,
    SHOES_URLS,
    CLOTHING_URLS,
    CLOTHING_SIZE_CODE,
    SEND_HOURS_IL,
    SCAN_TIMEOUT_MS,
    MAX_LOAD_MORE_CLICKS,
    LOAD_MORE_DELAY_MS,
    ENABLE_DEBUG_LOGS,
)


API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


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
    log(f"send_message -> {r.status_code} {r.text[:180]}")
    return r


def send_photo(chat_id: int, image_url: str, caption: str):
    url = f"{API}/sendPhoto"
    payload = {
        "chat_id": chat_id,
        "photo": image_url,
        "caption": caption,
        "disable_web_page_preview": True,
    }
    r = requests.post(url, data=payload, timeout=30)
    log(f"send_photo -> {r.status_code} {r.text[:180]}")
    return r


def is_send_window_now_il(manual: bool) -> bool:
    if manual:
        log("Checker allowed: manual run")
        return True
    now = datetime.now()  # runner time is UTC בדרך כלל - אבל אתה רץ סביב זה בכל מקרה
    # כדי להימנע מסיבוך TZ, אנחנו מסתמכים על cron של GitHub שתכוון לשעות הנכונות אצלך,
    # ובודקים רק שעה "מספרית" לפי local של ה-runner.
    # אם אתה רוצה דיוק מוחלט ל-IL TZ - נגיד וזה השלב הבא.
    return now.hour in SEND_HOURS_IL and now.minute < 10


def build_shoes_url(gender: str, shoe_size: str, price_min: int, price_max: int):
    base = SHOES_URLS.get(gender)
    if not base:
        return None

    size_map = load_json(SIZE_MAP_FILE, {})
    size_code = str((size_map.get(gender) or {}).get(str(shoe_size), ""))

    if not size_code:
        return None

    return f"{base}?price={price_min}_{price_max}&size={size_code}&product_list_order=low_to_high"


def build_clothing_url(gender: str, clothing_size: str, price_min: int, price_max: int):
    base = CLOTHING_URLS.get(gender)
    if not base:
        return None

    code = CLOTHING_SIZE_CODE.get((clothing_size or "").upper())
    if not code:
        return None

    return f"{base}?price={price_min}_{price_max}&size={code}&product_list_order=low_to_high"


def scrape_products(page) -> list:
    soup = BeautifulSoup(page.content(), "html.parser")
    product_cards = soup.select("div.product")
    results = []

    for card in product_cards:
        link_tag = card.select_one("a")
        img_tag = card.select_one("img")
        price_tags = card.select("span.price")

        title = img_tag.get("alt", "").strip() if img_tag else ""
        link = link_tag.get("href") if link_tag else None
        if not link:
            continue
        if not link.startswith("http"):
            link = "https://www.timberland.co.il" + link

        img_url = img_tag.get("src") if img_tag else None

        prices = []
        for tag in price_tags:
            try:
                txt = tag.get_text(" ", strip=True).replace("\xa0", "").replace("₪", "").replace(",", "")
                val = float(txt)
                if val > 0:
                    prices.append(val)
            except Exception:
                continue

        if not prices:
            continue

        price_val = min(prices)
        results.append({"title": title or "ללא שם", "link": link, "price": price_val, "img_url": img_url})

    return results


def run_scan_once(url: str) -> list:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="he-IL")
        page = context.new_page()
        page.goto(url, timeout=SCAN_TIMEOUT_MS)

        # Load more
        clicks = 0
        while True:
            try:
                load_more = page.query_selector("a.action.more")
                if load_more:
                    load_more.click()
                    page.wait_for_timeout(LOAD_MORE_DELAY_MS)
                    clicks += 1
                    if clicks >= MAX_LOAD_MORE_CLICKS:
                        break
                else:
                    break
            except Exception:
                break

        items = scrape_products(page)
        browser.close()
        return items


def check_user(chat_id: int, user: dict, prev_state: dict, cur_state: dict):
    gender = user.get("gender")
    category = user.get("category")
    price_min = int(user.get("price_min", 0))
    price_max = int(user.get("price_max", 9999))

    shoe_size = user.get("shoes_size") or user.get("size")
    clothing_size = user.get("clothing_size")

    jobs = []

    if category == "shoes":
        url = build_shoes_url(gender, str(shoe_size), price_min, price_max)
        if url:
            jobs.append(("👟 הנעלה", url))
        else:
            send_message(chat_id, "❌ לא הצלחתי לבנות URL להנעלה - בדוק מידה/מגדר והגדר מחדש עם /start")

    elif category == "clothing":
        url = build_clothing_url(gender, str(clothing_size), price_min, price_max)
        if url:
            jobs.append(("👕 ביגוד", url))
        else:
            send_message(chat_id, "❌ לא הצלחתי לבנות URL לביגוד - בדוק מידה (XS-XXXL) והגדר מחדש עם /start")

    elif category == "both":
        url1 = build_shoes_url(gender, str(shoe_size), price_min, price_max)
        url2 = build_clothing_url(gender, str(clothing_size), price_min, price_max)

        if url1:
            jobs.append(("👟 הנעלה", url1))
        else:
            send_message(chat_id, "⚠️ (גם וגם) לא הצלחתי לבנות URL להנעלה - בדוק מידה לנעליים")

        if url2:
            jobs.append(("👕 ביגוד", url2))
        else:
            send_message(chat_id, "⚠️ (גם וגם) לא הצלחתי לבנות URL לביגוד - בדוק מידה לביגוד (XS-XXXL)")

    else:
        return

    for label, url in jobs:
        log(f"Scanning {chat_id} {label} -> {url}")
        items = run_scan_once(url)
        log(f"Found {len(items)} items for {chat_id} {label}")

        if not items:
            send_message(chat_id, f"{label} - לא נמצאו פריטים כרגע.\n{url}")
            continue

        # state per item per user per category
        new_items = []
        for it in items:
            key = f"{chat_id}|{label}|{it['link']}"
            cur_state[key] = it
            if key not in prev_state:
                new_items.append(it)

        # שליחה של חדשים עם תמונה (כדי לא להציף)
        for it in new_items[:10]:
            caption = f"{label}\n{it['title']}\n₪{int(it['price'])}\n{it['link']}"
            send_photo(chat_id, it.get("img_url") or "https://via.placeholder.com/300", caption)
            time.sleep(0.4)

        # סיכום מרוכז (טקסט רגיל - בלי markdown/html)
        items_sorted = sorted(items, key=lambda x: x["price"])[:15]
        lines = [f"{label} - תוצאות עדכניות (מחיר {price_min}-{price_max})"]
        for i, it in enumerate(items_sorted, 1):
            lines.append(f"{i}. {it['title'][:70]} - ₪{int(it['price'])}")
            lines.append(it["link"])
        lines.append(f"\nחיפוש: {url}")
        send_message(chat_id, "\n".join(lines))


def main():
    if not TELEGRAM_TOKEN:
        raise SystemExit("TELEGRAM token is missing. Set TELEGRAM_BOT_TOKEN (or TELEGRAM_TOKEN) in GitHub Secrets.")

    manual = True  # אם אתה מריץ ידנית זה יישאר True אצלך. כרונולוגית נבדיל לפי env בהמשך אם תרצה.
    log("Starting checker...")

    if not is_send_window_now_il(manual=manual):
        log("Not in send window, skipping checker scan.")
        return

    user_data = load_json(USER_DATA_FILE, {})
    log(f"user_data loaded keys: {list(user_data.keys())}")

    if not user_data:
        log("No registered users found in user_data.json")
        return

    prev_state = load_json(STATE_FILE, {})
    cur_state = {}

    for k, user in user_data.items():
        chat_id = user.get("chat_id")
        if not isinstance(chat_id, int):
            try:
                chat_id = int(k)
            except Exception:
                continue

        if user.get("state") != "ready":
            # לא שולחים מוצרים למי שלא סיים setup
            continue

        check_user(chat_id, user, prev_state, cur_state)

    save_json(STATE_FILE, cur_state)
    log(f"Saved {len(cur_state)} items to {STATE_FILE}")


if __name__ == "__main__":
    main()
