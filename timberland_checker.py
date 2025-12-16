# timberland_checker.py
import json
import requests
import html
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from config import (
    TELEGRAM_BOT_TOKEN,
    USER_DATA_FILE,
    STATE_FILE,
    ENABLE_DEBUG_LOGS,
    SCAN_TIMEOUT,
    MAX_LOAD_MORE_CLICKS,
    LOAD_MORE_DELAY,
    SEND_HOURS_IL,
    SHOES_BASE,
    CLOTHING_BASE,
    SHOES_SIZE_MAP,
    CLOTHING_SIZE_MAP,
)

API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def log(msg: str):
    if ENABLE_DEBUG_LOGS:
        print(msg)


def send_message(chat_id: int, text: str):
    url = f"{API}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    r = requests.post(url, data=payload, timeout=30)
    log(f"send_message -> {r.status_code} {r.text[:120]}")
    return r


def send_photo(chat_id: int, photo_url: str, caption: str):
    url = f"{API}/sendPhoto"
    payload = {
        "chat_id": chat_id,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "HTML",
    }
    r = requests.post(url, data=payload, timeout=30)
    log(f"send_photo -> {r.status_code} {r.text[:120]}")
    return r


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


def il_now():
    # Israel timezone offset approximation (+02). If you need DST accuracy, we can switch to zoneinfo.
    return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=2)))


def in_send_window():
    now_il = il_now()
    return now_il.hour in SEND_HOURS_IL


def build_price_param(price_min: int, price_max: int) -> str:
    return f"{int(price_min)}_{int(price_max)}"


def build_shoes_url(gender: str, shoes_size: str, price_min: int, price_max: int):
    base = SHOES_BASE.get(gender)
    if not base:
        return None

    size_code = SHOES_SIZE_MAP.get(gender, {}).get(str(shoes_size))
    if not size_code:
        return None

    price_param = build_price_param(price_min, price_max)
    return f"{base}?price={price_param}&size={size_code}&product_list_order=low_to_high"


def build_clothing_url(gender: str, clothing_size: str, price_min: int, price_max: int):
    base = CLOTHING_BASE.get(gender)
    if not base:
        return None

    s = (clothing_size or "").upper()
    size_code = CLOTHING_SIZE_MAP.get(gender, {}).get(s)
    if not size_code:
        return None

    price_param = build_price_param(price_min, price_max)
    return f"{base}?price={price_param}&size={size_code}&product_list_order=low_to_high"


def extract_prices(text: str):
    # Extract all floats from a messy string containing ₪, sale/original prices, etc.
    vals = []
    cur = ""
    for ch in text:
        if ch.isdigit() or ch == ".":
            cur += ch
        else:
            if cur:
                vals.append(cur)
                cur = ""
    if cur:
        vals.append(cur)

    out = []
    for v in vals:
        try:
            f = float(v)
            if f > 0:
                out.append(f)
        except Exception:
            pass
    return out


def scrape_products(url: str):
    products = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="he-IL")
        page = context.new_page()
        page.goto(url, timeout=SCAN_TIMEOUT)

        # try "load more" if exists
        clicks = 0
        while clicks < MAX_LOAD_MORE_CLICKS:
            try:
                btn = page.query_selector("a.action.more")
                if not btn:
                    break
                btn.click()
                page.wait_for_timeout(LOAD_MORE_DELAY)
                clicks += 1
            except Exception:
                break

        soup = BeautifulSoup(page.content(), "html.parser")

        # Try different product selectors (Magento-like)
        cards = soup.select("li.product-item")
        if not cards:
            cards = soup.select("div.product")

        for card in cards:
            # Title
            title = None
            t = card.select_one("a.product-item-link")
            if t:
                title = t.get_text(" ", strip=True)
            if not title:
                img = card.select_one("img")
                if img and img.get("alt"):
                    title = img.get("alt").strip()
            if not title:
                title = "Item"

            # Link
            link = None
            a = card.select_one("a.product-item-link") or card.select_one("a")
            if a and a.get("href"):
                link = a["href"]
            if link and not link.startswith("http"):
                link = "https://www.timberland.co.il" + link

            if not link:
                continue

            # Image
            img_url = None
            img = card.select_one("img.product-image-photo") or card.select_one("img")
            if img and img.get("src"):
                img_url = img["src"]

            # Price
            price_spans = card.select("span.price")
            price_vals = []
            for sp in price_spans:
                txt = sp.get_text(" ", strip=True).replace("₪", " ")
                price_vals.extend(extract_prices(txt))

            if not price_vals:
                continue

            price = min(price_vals)

            products.append({
                "title": title,
                "link": link,
                "img_url": img_url,
                "price": price,
            })

        browser.close()

    # Dedup by link
    uniq = {}
    for p in products:
        uniq[p["link"]] = p

    return list(uniq.values())


def build_user_tasks(user: dict):
    """
    Returns list of dict tasks:
    [
      {"kind":"shoes","label":"...","url":"...","size_label":"..."},
      {"kind":"clothing",...}
    ]
    """
    gender = user.get("gender")
    category = user.get("category")
    price_min = int(user.get("price_min", 0))
    price_max = int(user.get("price_max", 0))

    tasks = []

    if category in ("shoes", "both"):
        shoes_size = user.get("shoes_size")
        url = build_shoes_url(gender, shoes_size, price_min, price_max)
        if url:
            tasks.append({
                "kind": "shoes",
                "label": "הנעלה",
                "url": url,
                "size_label": str(shoes_size),
            })

    if category in ("clothing", "both"):
        clothing_size = user.get("clothing_size")
        url = build_clothing_url(gender, clothing_size, price_min, price_max)
        if url:
            tasks.append({
                "kind": "clothing",
                "label": "ביגוד",
                "url": url,
                "size_label": str(clothing_size).upper(),
            })

    return tasks


def send_summary(chat_id: int, gender: str, kind_label: str, size_label: str, price_min: int, price_max: int, url: str, products: list, new_count: int):
    gender_label = {"men": "גברים", "women": "נשים", "kids": "ילדים"}.get(gender, gender)

    if not products:
        msg = (
            f"👟 <b>לא נמצאו פריטים</b>\n\n"
            f"מגדר: <b>{html.escape(gender_label)}</b>\n"
            f"קטגוריה: <b>{html.escape(kind_label)}</b>\n"
            f"מידה: <b>{html.escape(size_label)}</b>\n"
            f"טווח: <b>{price_min} - {price_max} ₪</b>\n\n"
            f"🔎 <a href='{html.escape(url)}'>פתח חיפוש באתר</a>"
        )
        send_message(chat_id, msg)
        return

    products.sort(key=lambda x: x["price"])
    top = products[:10]

    header = (
        f"👟 <b>סיכום תוצאות</b> ({html.escape(kind_label)})\n\n"
        f"מגדר: <b>{html.escape(gender_label)}</b>\n"
        f"מידה: <b>{html.escape(size_label)}</b>\n"
        f"טווח: <b>{price_min} - {price_max} ₪</b>\n"
        f"נמצאו: <b>{len(products)}</b> פריטים | חדשים עכשיו: <b>{new_count}</b>\n\n"
    )

    lines = []
    for i, p in enumerate(top, 1):
        title = html.escape(p["title"][:70])
        price = int(p["price"])
        link = html.escape(p["link"])
        lines.append(f"{i}. <b>{title}</b> - <b>₪{price}</b>\n<a href='{link}'>פתח מוצר</a>")

    footer = f"\n🔎 <a href='{html.escape(url)}'>פתח חיפוש באתר</a>"

    msg = header + "\n\n".join(lines) + footer
    send_message(chat_id, msg)


def check_all_users(force_run: bool = False):
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is missing. Set it in GitHub Secrets.")

    now_il = il_now()
    log(f"[{datetime.now()}] Starting check... IL time {now_il.strftime('%H:%M')}")

    if not force_run and not in_send_window():
        log(f"Not in send window, IL time is {now_il.strftime('%H:%M')}, skipping checker scan.")
        return

    user_data = load_json(USER_DATA_FILE, {})
    state = load_json(STATE_FILE, {})

    if not user_data:
        log("No registered users found in user_data.json")
        return

    log(f"Found {len(user_data)} registered users.")

    new_state = dict(state)

    for user_id, u in user_data.items():
        chat_id = u.get("chat_id")
        if not chat_id:
            continue

        if u.get("state") != "ready":
            log(f"Skipping user {user_id} because state is not ready: {u.get('state')}")
            continue

        gender = u.get("gender")
        price_min = int(u.get("price_min", 0))
        price_max = int(u.get("price_max", 0))

        tasks = build_user_tasks(u)
        if not tasks:
            send_message(
                int(chat_id),
                "❌ לא ניתן לבנות חיפוש לפי ההגדרות שלך.\n"
                "שלח /start והגדר מחדש.",
            )
            continue

        for t in tasks:
            url = t["url"]
            kind = t["kind"]
            kind_label = t["label"]
            size_label = t["size_label"]

            log(f"User {user_id} - {kind} - URL: {url}")

            try:
                products = scrape_products(url)
                log(f"Found {len(products)} products for user {user_id} ({kind})")

                new_count = 0
                for p in products:
                    key = f"{chat_id}_{kind}_{p['link']}"
                    is_new = key not in state
                    if is_new:
                        new_count += 1
                        new_state[key] = {
                            "title": p["title"],
                            "link": p["link"],
                            "price": p["price"],
                        }

                        # Send new item photo message (optional)
                        if p.get("img_url"):
                            caption = (
                                f"🆕 <b>{html.escape(p['title'][:80])}</b>\n"
                                f"מחיר: <b>₪{int(p['price'])}</b>\n"
                                f"<a href='{html.escape(p['link'])}'>פתח מוצר</a>"
                            )
                            send_photo(int(chat_id), p["img_url"], caption)

                send_summary(
                    chat_id=int(chat_id),
                    gender=gender,
                    kind_label=kind_label,
                    size_label=size_label,
                    price_min=price_min,
                    price_max=price_max,
                    url=url,
                    products=products,
                    new_count=new_count,
                )

            except Exception as e:
                log(f"Error scanning user {user_id} ({kind}): {str(e)}")
                continue

    save_json(STATE_FILE, new_state)
    log(f"Saved state with {len(new_state)} items total.")


if __name__ == "__main__":
    # If you want to force sending on manual runs:
    # set env FORCE_RUN=1 in workflow_dispatch
    force = os.getenv("FORCE_RUN", "0").strip() == "1"
    check_all_users(force_run=force)