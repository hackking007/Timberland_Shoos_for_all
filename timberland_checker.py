# timberland_checker.py
import json
import os
import time
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ---------------- Files (must match bot.yml artifact paths) ----------------
USER_DATA_FILE = "user_data.json"
SHOES_STATE_FILE = "shoes_state.json"          # match bot.yml
SHOES_SIZE_MAP_FILE = "size_map.json"
APPAREL_SIZE_MAP_FILE = "apparel_size_map.json"  # you must have this file in repo

# ---------------- Telegram ----------------
TELEGRAM_BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or "").strip()
API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# ---------------- Behavior ----------------
ENABLE_DEBUG_LOGS = True

IL_TZ = ZoneInfo("Asia/Jerusalem")
SEND_HOURS_IL = {7, 19}  # 07:00 and 19:00 IL time

# Hard limits to avoid flooding
MAX_NEW_ITEMS_PER_USER_PER_RUN = 12
SLEEP_BETWEEN_SENDS_SEC = 0.4

def log(msg: str):
    if ENABLE_DEBUG_LOGS:
        print(msg)

def load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
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
    log(f"send_message -> {r.status_code}")
    return r

def send_photo(chat_id: int, photo_url: str, caption: str):
    url = f"{API}/sendPhoto"
    payload = {
        "chat_id": chat_id,
        "photo": photo_url,
        "caption": caption[:950],
        "disable_web_page_preview": True,
    }
    r = requests.post(url, data=payload, timeout=30)
    log(f"send_photo -> {r.status_code}")
    return r

def in_send_window():
    now_il = datetime.now(IL_TZ)
    return now_il.hour in SEND_HOURS_IL, now_il

def is_manual_run():
    # GitHub Actions sets this env for workflow_dispatch
    return (os.getenv("GITHUB_EVENT_NAME") or "").strip() == "workflow_dispatch"

def build_shoes_url(gender: str, shoe_size: str, price_min: int, price_max: int, shoes_size_map: dict):
    base = {
        "men": "https://www.timberland.co.il/men/footwear",
        "women": "https://www.timberland.co.il/women/%D7%94%D7%A0%D7%A2%D7%9C%D7%94",
        "kids": "https://www.timberland.co.il/kids/toddlers-0-5y",
    }.get(gender)

    if not base:
        return None

    size_code = shoes_size_map.get(gender, {}).get(str(shoe_size))
    if not size_code:
        return None

    return f"{base}?price={price_min}_{price_max}&size={size_code}&product_list_order=low_to_high"

def build_clothing_url(gender: str, clothing_size: str, price_min: int, price_max: int, apparel_size_map: dict):
    base = {
        "men": "https://www.timberland.co.il/men/clothing",
        "women": "https://www.timberland.co.il/women/clothing",
        "kids": "https://www.timberland.co.il/kids/clothing",
    }.get(gender)

    if not base:
        return None

    size_code = apparel_size_map.get(gender, {}).get(clothing_size.upper())
    if not size_code:
        return None

    return f"{base}?price={price_min}_{price_max}&size={size_code}&product_list_order=low_to_high"

def normalize_link(href: str, fallback: str):
    href = (href or "").strip()
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return "https://www.timberland.co.il" + href
    return fallback

def extract_price_text(product_node):
    # try multiple patterns
    candidates = []
    for sel in [".special-price .price", ".price", ".price-wrapper", "[data-price-amount]"]:
        el = product_node.select_one(sel)
        if not el:
            continue
        txt = el.get_text(" ", strip=True)
        if txt:
            candidates.append(txt)
    if candidates:
        return candidates[0]
    return ""

def scrape_products(page_html: str, page_url: str):
    soup = BeautifulSoup(page_html, "html.parser")
    items = []

    # Timberland pages may vary:
    # - li.product-item (Magento)
    # - div.product (older layout)
    products = soup.select("li.product-item")
    if not products:
        products = soup.select("div.product")

    for p in products:
        # Title + link
        a = p.select_one("a.product-item-link") or p.select_one("a")
        if not a:
            continue

        title = a.get_text(strip=True) or ""
        href = a.get("href") or ""
        link = normalize_link(href, page_url)

        # Image
        img_el = p.select_one("img")
        img = ""
        if img_el:
            img = img_el.get("data-src") or img_el.get("src") or ""
            if img.startswith("//"):
                img = "https:" + img

        price_text = extract_price_text(p)

        uid = link  # stable dedupe key
        items.append({
            "id": uid,
            "title": title[:140],
            "price": price_text[:80],
            "link": link,
            "img": img,
        })

    # de-dup by id
    seen = set()
    out = []
    for it in items:
        if it["id"] in seen:
            continue
        seen.add(it["id"])
        out.append(it)
    return out

def fetch_url_html(playwright, url: str):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(locale="he-IL")
    page = context.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2000)

    # Try "load more" if exists
    clicks = 0
    while clicks < 8:
        btn = page.query_selector("a.action.more") or page.query_selector("button.action.more")
        if not btn:
            break
        try:
            btn.click()
            page.wait_for_timeout(1200)
            clicks += 1
        except Exception:
            break

    html = page.content()
    browser.close()
    return html

def check_and_send_for_user(pw, user_id: str, u: dict, global_state: dict, shoes_size_map: dict, apparel_size_map: dict):
    chat_id = u.get("chat_id")
    if not isinstance(chat_id, int):
        return

    if u.get("state") != "ready":
        return

    gender = u.get("gender")
    category = u.get("category")

    try:
        price_min = int(u.get("price_min", 0))
        price_max = int(u.get("price_max", 999999))
    except Exception:
        price_min, price_max = 0, 999999

    urls = []

    if category in ("shoes", "both"):
        shoe_size = u.get("shoes_size") or u.get("size")
        if shoe_size:
            url = build_shoes_url(gender, str(shoe_size), price_min, price_max, shoes_size_map)
            if url:
                urls.append(("shoes", url))

    if category in ("clothing", "both"):
        clothing_size = u.get("clothing_size")
        if clothing_size:
            url = build_clothing_url(gender, str(clothing_size), price_min, price_max, apparel_size_map)
            if url:
                urls.append(("clothing", url))

    # IMPORTANT: do NOT spam user with errors here.
    # If no url can be built, we silently skip.
    if not urls:
        log(f"User {user_id}: cannot build URL (gender={gender}, category={category}) - skip")
        return

    user_state = global_state.get(user_id, {})
    sent_ids = set(user_state.get("sent_ids", []))

    new_sent = 0

    for kind, url in urls:
        log(f"User {user_id} scan {kind} URL: {url}")

        html = fetch_url_html(pw, url)
        items = scrape_products(html, url)

        for it in items:
            if it["id"] in sent_ids:
                continue

            caption = f"{it['title']}\n{it['price']}\n{it['link']}".strip()

            if it["img"]:
                send_photo(chat_id, it["img"], caption)
            else:
                send_message(chat_id, caption)

            sent_ids.add(it["id"])
            new_sent += 1

            time.sleep(SLEEP_BETWEEN_SENDS_SEC)

            if new_sent >= MAX_NEW_ITEMS_PER_USER_PER_RUN:
                break

        if new_sent >= MAX_NEW_ITEMS_PER_USER_PER_RUN:
            break

    # Save updated state
    global_state[user_id] = {"sent_ids": list(sent_ids)}

    # IMPORTANT: no summary, no "no items" message.
    log(f"User {user_id}: new_sent={new_sent}")

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("Missing TELEGRAM_BOT_TOKEN in GitHub Secrets.")

    log("Starting checker...")

    allowed, now_il = in_send_window()
    manual = is_manual_run()

    if not allowed and not manual:
        log(f"Not in send window, IL time is {now_il.strftime('%H:%M')}, skipping checker scan.")
        return

    if manual:
        log("Checker allowed: manual run")
    else:
        log(f"Checker allowed: send window {now_il.strftime('%H:%M')}")

    user_data = load_json(USER_DATA_FILE, {})
    log(f"user_data loaded keys: {list(user_data.keys())}")

    if not user_data:
        log("No registered users found in user_data.json")
        return

    global_state = load_json(SHOES_STATE_FILE, {})
    shoes_size_map = load_json(SHOES_SIZE_MAP_FILE, {})
    apparel_size_map = load_json(APPAREL_SIZE_MAP_FILE, {})

    with sync_playwright() as pw:
        for user_id, u in user_data.items():
            check_and_send_for_user(pw, user_id, u, global_state, shoes_size_map, apparel_size_map)

    save_json(SHOES_STATE_FILE, global_state)
    log("Checker done.")

if __name__ == "__main__":
    main()
