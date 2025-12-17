# timberland_checker.py
import json
import os
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from config import (
    TELEGRAM_BOT_TOKEN,
    USER_DATA_FILE,
    STATE_FILE,
    SHOES_SIZE_MAP_FILE,
    APPAREL_SIZE_MAP_FILE,
    SCAN_TIMEOUT,
    MAX_LOAD_MORE_CLICKS,
    LOAD_MORE_DELAY,
    ENABLE_DEBUG_LOGS,
    SEND_HOURS_IL,
)


BASE = "https://www.timberland.co.il"


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
    # Plain text - no markdown/html to avoid Telegram entity parse errors
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    r = requests.post(url, data=payload, timeout=30)
    log(f"send_message -> {r.status_code} {r.text[:120]}")
    return r


def send_photo(chat_id: int, photo_url: str, caption: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": chat_id,
        "photo": photo_url,
        "caption": caption[:900],  # keep safe
    }
    r = requests.post(url, data=payload, timeout=30)
    log(f"send_photo -> {r.status_code} {r.text[:120]}")
    return r


def il_hour_now():
    # IL is UTC+2 normally; but DST changes. We'll use pytz-free approach:
    # GitHub runner UTC time + env TZ can be used. Instead, keep it simple:
    # If you need perfect DST - we'll add zoneinfo.
    from datetime import datetime, timezone, timedelta

    il = datetime.now(timezone.utc) + timedelta(hours=2)
    return il.hour, il.strftime("%H:%M")


def should_send_now():
    # Allow manual runs to send immediately
    if os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch":
        return True, "manual run"

    h, hm = il_hour_now()
    if h in SEND_HOURS_IL:
        return True, f"send window {hm}"
    return False, f"not in send window, IL time is {hm}"


def normalize_user(user_id: str, u: dict):
    """
    Backward compatible: if old keys exist (size/price "128-299"), convert to new format.
    """
    out = dict(u or {})
    out["chat_id"] = int(out.get("chat_id") or int(user_id))

    # New format expected:
    # gender: men/women/kids
    # category: shoes/clothing/both
    # shoes_size, clothing_size
    # price_min, price_max

    # If old 'size' used for shoes
    if "shoes_size" not in out and "size" in out:
        out["shoes_size"] = str(out.get("size"))

    # If old 'category' maybe 'shoes'
    if out.get("category") in ("A", "B", "C"):
        out["category"] = {"A": "shoes", "B": "clothing", "C": "both"}[out["category"]]

    # If old price string "128-299"
    if "price_min" not in out or "price_max" not in out:
        p = out.get("price")
        if isinstance(p, str) and "-" in p:
            a, b = p.split("-", 1)
            try:
                out["price_min"] = int(a)
                out["price_max"] = int(b)
            except Exception:
                pass

    # Default state
    if "state" not in out:
        out["state"] = "ready"

    return out


def build_shoes_url(gender: str, shoe_size: str, price_min: int, price_max: int, shoes_map: dict):
    # routes for shoes
    base = {
        "men": f"{BASE}/men/footwear",
        "women": f"{BASE}/women/%D7%94%D7%A0%D7%A2%D7%9C%D7%94",
        "kids": f"{BASE}/kids/toddlers-0-5y",
    }.get(gender)

    if not base:
        return None

    size_code = shoes_map.get(gender, {}).get(str(shoe_size))
    if not size_code:
        return None

    return f"{base}?price={price_min}_{price_max}&size={size_code}&product_list_order=low_to_high"


def build_clothing_url(gender: str, clothing_size: str, price_min: int, price_max: int, apparel_map: dict):
    base = {
        "men": f"{BASE}/men/clothing",
        "women": f"{BASE}/women/clothing",
        "kids": None,  # unknown route - skip for now
    }.get(gender)

    if not base:
        return None

    size_code = apparel_map.get(gender, {}).get(str(clothing_size).upper())
    if not size_code:
        return None

    return f"{base}?price={price_min}_{price_max}&size={size_code}&product_list_order=low_to_high"


def scrape_url(page, url: str):
    page.goto(url, timeout=SCAN_TIMEOUT)

    # Load more products
    clicks = 0
    while True:
        try:
            load_more = page.query_selector("a.action.more")
            if load_more:
                load_more.click()
                page.wait_for_timeout(LOAD_MORE_DELAY)
                clicks += 1
                if clicks >= MAX_LOAD_MORE_CLICKS:
                    break
            else:
                break
        except Exception:
            break

    soup = BeautifulSoup(page.content(), "html.parser")
    cards = soup.select("div.product")
    return cards


def parse_products(cards):
    items = []
    for card in cards:
        link_tag = card.select_one("a")
        img_tag = card.select_one("img")
        price_tags = card.select("span.price")

        title = img_tag.get("alt", "").strip() if img_tag else ""
        if not title:
            title = "No title"

        link = link_tag.get("href") if link_tag else None
        if not link:
            continue
        if not link.startswith("http"):
            link = BASE + link

        img_url = img_tag.get("src") if img_tag else None

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

        items.append(
            {
                "title": title,
                "link": link,
                "price": price_val,
                "img_url": img_url,
            }
        )
    return items


def check_shoes():
    log("Starting checker...")

    ok, reason = should_send_now()
    if not ok:
        log(reason)
        print(reason)
        return
    log(f"Checker allowed: {reason}")

    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("Missing TELEGRAM_BOT_TOKEN")

    user_data_raw = load_json(USER_DATA_FILE, {})
    log(f"user_data loaded keys: {list(user_data_raw.keys())}")

    if not user_data_raw:
        print("No registered users found in user_data.json")
        return

    previous_state = load_json(STATE_FILE, {})
    current_state = {}

    shoes_map = load_json(SHOES_SIZE_MAP_FILE, {})
    apparel_map = load_json(APPAREL_SIZE_MAP_FILE, {})

    users = []
    for uid, u in user_data_raw.items():
        users.append((uid, normalize_user(uid, u)))

    print(f"Found {len(users)} registered users.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="he-IL")
        page = context.new_page()

        for uid, u in users:
            if u.get("state") != "ready":
                log(f"Skipping user {uid} because state={u.get('state')}")
                continue

            chat_id = int(u["chat_id"])
            gender = u.get("gender")
            category = u.get("category")
            price_min = int(u.get("price_min", 0))
            price_max = int(u.get("price_max", 9999))

            urls = []

            if category == "shoes":
                url = build_shoes_url(gender, u.get("shoes_size"), price_min, price_max, shoes_map)
                if url:
                    urls.append(("shoes", url))
            elif category == "clothing":
                url = build_clothing_url(gender, u.get("clothing_size"), price_min, price_max, apparel_map)
                if url:
                    urls.append(("clothing", url))
            elif category == "both":
                url1 = build_shoes_url(gender, u.get("shoes_size"), price_min, price_max, shoes_map)
                url2 = build_clothing_url(gender, u.get("clothing_size"), price_min, price_max, apparel_map)
                if url1:
                    urls.append(("shoes", url1))
                if url2:
                    urls.append(("clothing", url2))

            if not urls:
                send_message(
                    chat_id,
                    f"❌ לא הצלחתי לבנות URL לפי ההעדפות שלך.\n"
                    f"gender={gender}, category={category}\n"
                    f"נסה לשלוח שוב /start ולהגדיר מחדש.",
                )
                continue

            all_items = []
            for kind, url in urls:
                log(f"User {uid} scanning {kind}: {url}")
                cards = scrape_url(page, url)
                items = parse_products(cards)
                # tag kind
                for it in items:
                    it["kind"] = kind
                    it["url"] = url
                all_items.extend(items)

            # Deduplicate by link
            seen = set()
            dedup = []
            for it in all_items:
                if it["link"] in seen:
                    continue
                seen.add(it["link"])
                dedup.append(it)

            dedup.sort(key=lambda x: x["price"])

            # Per-item state tracking
            new_count = 0
            for it in dedup:
                key = f"{uid}|{it['link']}"
                current_state[key] = it
                if key not in previous_state:
                    new_count += 1
                    caption = f"{it['title']} - ₪{int(it['price'])}\n{it['link']}"
                    send_photo(chat_id, it.get("img_url") or "https://via.placeholder.com/600", caption)

            # Always send summary (even if 0 products)
            if dedup:
                top = dedup[:15]
                lines = []
                for i, it in enumerate(top, 1):
                    mark = "NEW " if f"{uid}|{it['link']}" not in previous_state else ""
                    lines.append(f"{i}. {mark}{it['title'][:80]} - ₪{int(it['price'])}\n{it['link']}")
                if len(dedup) > len(top):
                    lines.append(f"\n...and {len(dedup) - len(top)} more items")

                header = (
                    f"👟 Results updated\n"
                    f"Gender: {gender} | Category: {category}\n"
                    f"Price: {price_min}-{price_max} ₪\n"
                    f"New items this run: {new_count}\n\n"
                )
                send_message(chat_id, header + "\n".join(lines))
            else:
                send_message(
                    chat_id,
                    f"👟 No items found right now.\n"
                    f"Gender: {gender} | Category: {category}\n"
                    f"Price: {price_min}-{price_max} ₪\n"
                    f"(Sometimes Timberland has empty pages - try later.)",
                )

        browser.close()

    save_json(STATE_FILE, current_state)
    print(f"Saved current_state with {len(current_state)} items total.")


if __name__ == "__main__":
    check_shoes()