import os
import json
import html
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from zoneinfo import ZoneInfo
from datetime import datetime

from config import *

# ---------------- Token ----------------
BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or TELEGRAM_TOKEN or "").strip()

# ---------------- Telegram helpers (HTML mode) ----------------

def send_telegram_message(text, chat_id=None, disable_preview=True):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    target_chat = chat_id or ADMIN_CHAT_ID
    payload = {
        "chat_id": target_chat,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": disable_preview
    }
    try:
        r = requests.post(url, data=payload, timeout=30)
        if ENABLE_DEBUG_LOGS:
            print(f"send_telegram_message -> {r.status_code} {r.text[:200]}")
    except Exception as e:
        if ENABLE_DEBUG_LOGS:
            print(f"send_telegram_message error: {e}")


def send_photo_with_caption(image_url, caption_html, chat_id=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    target_chat = chat_id or ADMIN_CHAT_ID
    payload = {
        "chat_id": target_chat,
        "photo": image_url,
        "caption": caption_html,
        "parse_mode": "HTML"
    }
    try:
        r = requests.post(url, data=payload, timeout=30)
        if ENABLE_DEBUG_LOGS:
            print(f"send_photo_with_caption -> {r.status_code} {r.text[:200]}")
    except Exception as e:
        if ENABLE_DEBUG_LOGS:
            print(f"send_photo_with_caption error: {e}")

# ---------------- JSON helpers ----------------

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception as e:
        if ENABLE_DEBUG_LOGS:
            print(f"load_json error for {path}: {e}")
        return default


def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        if ENABLE_DEBUG_LOGS:
            print(f"save_json error for {path}: {e}")

# ---------------- State / config helpers ----------------

def load_previous_state():
    return load_json(STATE_FILE, {})


def save_current_state(state):
    save_json(STATE_FILE, state)


def load_user_preferences():
    return load_json(USER_DATA_FILE, {})


def load_size_mapping():
    return load_json(SIZE_MAP_FILE, {})


def load_apparel_size_mapping():
    # אם הקובץ לא קיים - נחזיר ריק, וביגוד ירוץ בלי פילטר size
    path = globals().get("APPAREL_SIZE_MAP_FILE", "apparel_size_map.json")
    return load_json(path, {})


def size_to_code(size, gender):
    m = load_size_mapping()
    return str(m.get(gender, {}).get(str(size), ""))


def apparel_size_to_code(apparel_size, gender):
    m = load_apparel_size_mapping()
    return str(m.get(gender, {}).get(str(apparel_size).upper(), ""))

# ---------------- URL builders ----------------

def build_shoes_url(gender, shoe_size, price_min, price_max):
    if gender not in CATEGORIES:
        return None
    base_url = CATEGORIES[gender]["url"]
    size_code = size_to_code(shoe_size, gender)
    if not size_code:
        return None
    return f"{base_url}?price={int(price_min)}_{int(price_max)}&size={size_code}&product_list_order=low_to_high"


def build_clothing_url(gender, apparel_size, price_min, price_max):
    """
    גברים ביגוד עובד כך (דוגמה שלך):
    https://www.timberland.co.il/men/clothing?price=68_1001&size=4

    נשים כרגע: אם אין מוצרים/אין פילטר מידות - אין size_code.
    במקרה כזה נריץ בלי size כדי לא "לשבור" ונקבל תוצאות אם יש מלאי לפי מחיר.
    """
    if gender not in CLOTHING_URLS:
        return None

    base_url = CLOTHING_URLS[gender]

    # אם המשתמש לא נתן מידה לביגוד - נריץ בלי פילטר size
    if not apparel_size:
        return f"{base_url}?price={int(price_min)}_{int(price_max)}&product_list_order=low_to_high"

    size_code = apparel_size_to_code(apparel_size, gender)

    # אם אין מיפוי/אין פילטר (לדוגמה נשים כרגע) - ריצה בלי size
    if not size_code:
        return f"{base_url}?price={int(price_min)}_{int(price_max)}&product_list_order=low_to_high"

    return f"{base_url}?price={int(price_min)}_{int(price_max)}&size={size_code}&product_list_order=low_to_high"

# ---------------- Scheduling guard ----------------

def should_run_checker_now():
    """
    הסריקה רצה רק ב-07:00 וב-19:00 שעון ישראל.
    (ה-workflow יכול לרוץ כל 30 דקות, אבל checker ידלג אם זה לא חלון זמן).
    """
    tz = ZoneInfo("Asia/Jerusalem")
    now = datetime.now(tz)
    send_hours = [7, 19]

    if now.minute != 0:
        return False, now
    if now.hour not in send_hours:
        return False, now
    return True, now

# ---------------- Playwright scan ----------------

def scan_url_with_playwright(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="he-IL")
        page = context.new_page()

        page.goto(url, timeout=SCAN_TIMEOUT)
        page.wait_for_load_state("networkidle", timeout=SCAN_TIMEOUT)
        page.wait_for_timeout(1200)

        clicks = 0
        while True:
            try:
                load_more = page.query_selector("a.action.more")
                if load_more:
                    load_more.click()
                    page.wait_for_timeout(LOAD_MORE_DELAY)
                    clicks += 1
                    if clicks > MAX_LOAD_MORE_CLICKS:
                        break
                else:
                    break
            except Exception:
                break

        soup = BeautifulSoup(page.content(), "html.parser")
        product_cards = soup.select("div.product")

        browser.close()
        return product_cards

# ---------------- Parsing products ----------------

def extract_products(product_cards):
    items = []
    for card in product_cards:
        link_tag = card.select_one("a")
        img_tag = card.select_one("img")
        price_tags = card.select("span.price")

        title = img_tag["alt"].strip() if img_tag and img_tag.has_attr("alt") else "ללא שם"
        link = link_tag["href"] if link_tag and link_tag.has_attr("href") else None
        if not link:
            continue
        if not link.startswith("http"):
            link = "https://www.timberland.co.il" + link

        img_url = img_tag["src"] if img_tag and img_tag.has_attr("src") else None

        prices = []
        for tag in price_tags:
            try:
                text = tag.text.strip().replace("\xa0", "").replace("₪", "").replace(",", "")
                val = float(text)
                if val > 0:
                    prices.append(val)
            except Exception:
                continue

        if not prices:
            continue

        price_val = min(prices)
        items.append({"title": title, "link": link, "price": price_val, "img_url": img_url})

    return items

# ---------------- Send items ----------------

def send_items_to_user(user_id, chat_id, kind_label, url, items, previous_state, current_state):
    new_count = 0
    all_items = []

    for it in items:
        key = f"{user_id}_{kind_label}_{it['link']}"
        current_state[key] = it

        is_new = key not in previous_state
        all_items.append({**it, "is_new": is_new})

        if is_new:
            safe_title = html.escape(it["title"])
            safe_link = html.escape(it["link"])
            caption = f"<b>{safe_title}</b> - ₪{int(it['price'])}\n<a href=\"{safe_link}\">לינק למוצר</a>"
            send_photo_with_caption(it["img_url"] or "https://via.placeholder.com/300", caption, chat_id=chat_id)
            new_count += 1

    if all_items:
        all_items.sort(key=lambda x: x["price"])
        subset = all_items[:15]

        header = f"👟 <b>תוצאות</b> - <b>{html.escape(kind_label)}</b>\n"
        lines = []
        for i, it in enumerate(subset, 1):
            mark = "🆕 " if it["is_new"] else ""
            lines.append(
                f"{i}. {mark}<b>{html.escape(it['title'][:60])}</b> - ₪{int(it['price'])}\n{html.escape(it['link'])}"
            )

        if len(all_items) > len(subset):
            lines.append(f"\nועוד {len(all_items) - len(subset)} פריטים...")

        lines.append(f"\n🔎 {html.escape(url)}")

        send_telegram_message(header + "\n".join(lines), chat_id=chat_id)
    else:
        send_telegram_message(
            f"👟 <b>לא נמצאו פריטים</b> - <b>{html.escape(kind_label)}</b>\n\n🔎 {html.escape(url)}",
            chat_id=chat_id
        )

    return new_count, len(all_items)

# ---------------- Main logic ----------------

def check_shoes():
    ok, now = should_run_checker_now()
    if not ok:
        if ENABLE_DEBUG_LOGS:
            print(f"Not in send window, IL time is {now.strftime('%H:%M')}, skipping checker scan.")
        return

    if ENABLE_DEBUG_LOGS:
        print(f"[{datetime.now()}] Starting shoe check...")
        print(f"BOT_TOKEN length: {len(BOT_TOKEN)}")

    previous_state = load_previous_state()
    current_state = {}
    user_data = load_user_preferences()

    if ENABLE_DEBUG_LOGS:
        print(f"user_data loaded: {json.dumps(user_data, ensure_ascii=False, indent=2)}")

    if not user_data:
        send_telegram_message("⚠️ אין משתמשים רשומים ב user_data.json.")
        return

    if ENABLE_DEBUG_LOGS:
        print(f"Found {len(user_data)} registered users.")

    for user_id, prefs in user_data.items():
        gender = prefs.get("gender", "men")
        cat = prefs.get("category", "shoes")
        chat_id = prefs.get("chat_id", int(user_id) if str(user_id).isdigit() else user_id)

        price_min = prefs.get("price_min", 0)
        price_max = prefs.get("price_max", 300)
        if price_min > price_max:
            price_min, price_max = price_max, price_min

        tasks = []

        if cat in ("shoes", "both"):
            shoe_size = prefs.get("size")
            url = build_shoes_url(gender, shoe_size, price_min, price_max)
            tasks.append(("Shoes", url))

        if cat in ("clothing", "both"):
            apparel_size = prefs.get("apparel_size")
            url = build_clothing_url(gender, apparel_size, price_min, price_max)
            tasks.append(("Clothing", url))

        for kind_label, url in tasks:
            if not url:
                send_telegram_message(
                    f"❌ הגדרות לא תקינות עבור <b>{html.escape(kind_label)}</b>. שלח /start והגדר מחדש.",
                    chat_id=chat_id
                )
                continue

            if ENABLE_DEBUG_LOGS:
                print(f"Launching browser for user {user_id} - {kind_label} URL: {url}")

            try:
                cards = scan_url_with_playwright(url)
                if ENABLE_DEBUG_LOGS:
                    print(f"Found {len(cards)} products for user {user_id} ({kind_label})")

                items = extract_products(cards)
                new_count, total_count = send_items_to_user(
                    user_id=user_id,
                    chat_id=chat_id,
                    kind_label=kind_label,
                    url=url,
                    items=items,
                    previous_state=previous_state,
                    current_state=current_state
                )

                if ENABLE_DEBUG_LOGS:
                    print(f"Completed scan for user {user_id} ({kind_label}) new={new_count} total={total_count}")

            except Exception as e:
                if ENABLE_DEBUG_LOGS:
                    print(f"Error scanning for user {user_id} ({kind_label}): {e}")
                send_telegram_message(
                    f"❌ שגיאה בסריקה עבור <b>{html.escape(kind_label)}</b>: {html.escape(str(e))}",
                    chat_id=chat_id
                )

    save_current_state(current_state)
    if ENABLE_DEBUG_LOGS:
        print(f"Saved current_state with {len(current_state)} items total.")


if __name__ == "__main__":
    check_shoes()