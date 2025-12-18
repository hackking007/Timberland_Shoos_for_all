# timberland_checker.py
import json
import os
import time
import requests
from datetime import datetime, timezone, timedelta

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from coupon_fetcher import get_coupons
from smart_alerts import process_smart_alerts, get_price_history_summary, generate_share_link

USER_DATA_FILE = "user_data.json"
STATE_FILE = "shoes_state.json"
SHOES_SIZE_MAP_FILE = "size_map.json"
APPAREL_SIZE_MAP_FILE = "apparel_size_map.json"

TELEGRAM_BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or "").strip()
API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

ENABLE_DEBUG_LOGS = True

IL_TZ = timezone(timedelta(hours=2))  # Israel (no DST handling here)
SEND_HOURS_IL = {7, 19}

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
    return (os.getenv("GITHUB_EVENT_NAME") or "").strip() == "workflow_dispatch"

def build_shoes_url(gender: str, shoe_size: str, price_min: int, price_max: int, shoes_size_map: dict):
    base = {
        "men": "https://www.timberland.co.il/men/footwear",
        "women": "https://www.timberland.co.il/women/shoes",
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

def scrape_products(page_html: str, base_url: str):
    soup = BeautifulSoup(page_html, "html.parser")
    items = []

    products = soup.select("li.product-item") or soup.select(".product-item")
    for p in products:
        title_el = p.select_one(".product-item-link") or p.select_one("a")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)

        href = title_el.get("href") or ""
        if href and href.startswith("/"):
            link = "https://www.timberland.co.il" + href
        elif href.startswith("http"):
            link = href
        else:
            link = base_url

        img_el = p.select_one("img")
        img = ""
        if img_el:
            img = img_el.get("data-src") or img_el.get("src") or ""
            if img and img.startswith("//"):
                img = "https:" + img

        price_el = p.select_one(".price") or p.select_one(".special-price") or p.select_one("[data-price-amount]")
        price_text = price_el.get_text(" ", strip=True) if price_el else ""

        uid = link

        items.append({
            "id": uid,
            "title": title,
            "price": price_text,
            "link": link,
            "img": img,
        })

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
    page = browser.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2000)
    html = page.content()
    browser.close()
    return html

def check_and_send_for_user(pw, user_id: str, u: dict, global_state: dict, shoes_size_map: dict, apparel_size_map: dict):
    chat_id = u.get("chat_id")
    if not isinstance(chat_id, int):
        log(f"Skip user {user_id}: invalid chat_id")
        return

    if u.get("state") != "ready":
        log(f"Skip user {user_id}: state={u.get('state')}")
        return

    gender = u.get("gender")
    category = u.get("category")
    price_min = int(u.get("price_min", 0))
    price_max = int(u.get("price_max", 999999))

    urls = []

    if category in ("shoes", "both"):
        shoe_size = u.get("shoes_size") or u.get("size")
        if shoe_size:
            url = build_shoes_url(gender, str(shoe_size), price_min, price_max, shoes_size_map)
            if url:
                urls.append(("shoes", url))
            else:
                log(f"User {user_id}: could not build shoes url (gender={gender}, shoe_size={shoe_size})")

    if category in ("clothing", "both"):
        clothing_size = u.get("clothing_size")
        if clothing_size:
            url = build_clothing_url(gender, str(clothing_size), price_min, price_max, apparel_size_map)
            if url:
                urls.append(("clothing", url))
            else:
                log(f"User {user_id}: could not build clothing url (gender={gender}, clothing_size={clothing_size})")

    if not urls:
        send_message(chat_id, "❌ Cannot build URL from your settings. Try /reset and setup again.")
        return

    user_state = global_state.get(user_id, {})
    sent_ids = set(user_state.get("sent_ids", []))

    total_found = 0
    total_new = 0

    all_items = []  # Collect all items for smart alerts
    
    for kind, url in urls:
        log(f"User {user_id} scan {kind} URL: {url}")
        html = fetch_url_html(pw, url)
        items = scrape_products(html, url)
        total_found += len(items)
        all_items.extend(items)  # Add to smart alerts processing

        for it in items:
            if it["id"] in sent_ids:
                continue

            # Check if this is a price alert
            current_price = extract_price(it.get("price", ""))
            price_alert = ""
            
            if current_price and current_price <= price_max:
                from smart_alerts import update_price_history
                product_history = update_price_history(it["id"], current_price, it.get("title", ""))
                
                if current_price == product_history["lowest_price"]:
                    price_alert = "🔥 LOWEST PRICE EVER!\n"
                elif current_price < product_history.get("previous_lowest", 999999):
                    price_alert = "🔥 PRICE DROP ALERT!\n"
            
            # Enhanced caption with price history and alerts
            price_history = get_price_history_summary(it["id"])
            
            caption = f"{price_alert}{it['title']}\n{it['price']}\n{it['link']}\n\n"
            caption += f"{price_history}\n\n"
            caption += f"📤 Share: /share_{it['id'].split('/')[-1][:10]}"
            
            if it["img"]:
                send_photo(chat_id, it["img"], caption[:950])  # Telegram limit
            else:
                send_message(chat_id, caption[:950])

            sent_ids.add(it["id"])
            total_new += 1
            time.sleep(0.5)
    
    # Smart alerts are now integrated into individual product messages
    # No separate alert processing needed

    global_state[user_id] = {"sent_ids": list(sent_ids)}

    # Send coupons after products
    try:
        coupons = get_coupons(max_items=3)
        if coupons:
            coupon_text = "💰 DISCOUNT COUPONS:\n\n"
            for coupon in coupons:
                if coupon.get("code"):
                    coupon_text += f"🎫 {coupon['code']}\n"
                else:
                    coupon_text += f"📝 {coupon.get('title', 'Check site for offers')}\n"
            
            send_message(chat_id, coupon_text)
    except Exception as e:
        log(f"Error fetching coupons: {e}")
    
    if total_found == 0:
        send_message(chat_id, "No items found matching your criteria right now.")
    else:
        send_message(chat_id, f"Summary: Found {total_found} items. Sent {total_new} new ones.")

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("Missing TELEGRAM_BOT_TOKEN in GitHub Secrets.")

    log("Starting checker with smart alerts...")

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

    global_state = load_json(STATE_FILE, {})

    shoes_size_map = load_json(SHOES_SIZE_MAP_FILE, {})
    apparel_size_map = load_json(APPAREL_SIZE_MAP_FILE, {})

    with sync_playwright() as pw:
        for user_id, u in user_data.items():
            check_and_send_for_user(pw, user_id, u, global_state, shoes_size_map, apparel_size_map)

    save_json(STATE_FILE, global_state)
    log("Checker with smart alerts done.")

if __name__ == "__main__":
    main()
