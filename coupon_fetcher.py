import json
import time
import re
import requests
from bs4 import BeautifulSoup

CACHE_FILE = "coupons_cache.json"
CACHE_TTL_SECONDS = 12 * 60 * 60  # 12 hours

# מקורות "סבירים" לקופונים. לא 100% תמיד עובד - לכן עושים fallback
SOURCES = [
    {
        "name": "Cashyo",
        "url": "https://www.cashyo.co.il/retailer/timberland",
        "type": "cashyo",
    },
    {
        "name": "PromoCode",
        "url": "https://promocode.co.il/coupon-store/timberland/",
        "type": "promocode",
    },
    {
        "name": "FreeCoupon",
        "url": "https://www.freecoupon.co.il/coupons/timberland/",
        "type": "generic",
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (GitHubActions; TimberlandBot/1.0)"
}

def _load_cache():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _save_cache(data):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _fetch_html(url, timeout=25):
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.text

def _dedupe_keep_order(items):
    seen = set()
    out = []
    for it in items:
        key = (it.get("code") or "").strip().upper() + "|" + (it.get("title") or "").strip()
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out

def _parse_cashyo(html_text):
    # Cashyo מציג רשימות של "קוד קופון" + תיאור. אין תמיד HTML יציב,
    # לכן זה parser "רך": מחפשים טקסטים שנראים כמו קוד.
    soup = BeautifulSoup(html_text, "html.parser")
    text = soup.get_text("\n", strip=True)

    # קודי קופון לרוב A-Z0-9 באורך 3-12
    codes = re.findall(r"\b[A-Z0-9]{3,12}\b", text)
    # ננסה להשאיר רק "סביר" ולא מילים כלליות
    blacklist = {"HTTPS", "TIMBERLAND", "ISRAEL", "SALE", "OFF", "NEW"}
    codes = [c for c in codes if c not in blacklist]

    items = []
    for c in codes[:10]:
        items.append({
            "source": "Cashyo",
            "code": c,
            "title": "Coupon code (verify at checkout)",
            "url": "https://www.cashyo.co.il/retailer/timberland",
        })
    return items

def _parse_promocode(html_text):
    soup = BeautifulSoup(html_text, "html.parser")

    # באתר הזה לפעמים מופיע "צפייה בקוד XXX"
    text = soup.get_text("\n", strip=True)
    candidates = re.findall(r"צפייה\s+בקוד\s+([A-Z0-9]{3,12})", text)
    items = []
    for c in candidates[:10]:
        items.append({
            "source": "PromoCode",
            "code": c,
            "title": "Coupon code (details on page)",
            "url": "https://promocode.co.il/coupon-store/timberland/",
        })
    return items

def _parse_generic(html_text, source_name, source_url):
    soup = BeautifulSoup(html_text, "html.parser")
    text = soup.get_text("\n", strip=True)

    # חיפוש קוד "נראה כמו" TIM12 וכו'
    candidates = re.findall(r"\b[A-Z]{2,6}\d{1,4}\b", text)
    items = []
    for c in candidates[:10]:
        items.append({
            "source": source_name,
            "code": c,
            "title": "Coupon code (verify at checkout)",
            "url": source_url,
        })
    return items

def get_coupons(force_refresh=False, max_items=5):
    """
    מחזיר רשימת קופונים אחידה:
    [{"source":"Cashyo","code":"TIM12","title":"...","url":"..."}]
    """
    now = int(time.time())

    if not force_refresh:
        cached = _load_cache()
        if cached and (now - int(cached.get("ts", 0)) <= CACHE_TTL_SECONDS):
            return cached.get("items", [])[:max_items]

    items = []
    for src in SOURCES:
        try:
            html_text = _fetch_html(src["url"])
            if src["type"] == "cashyo":
                items.extend(_parse_cashyo(html_text))
            elif src["type"] == "promocode":
                items.extend(_parse_promocode(html_text))
            else:
                items.extend(_parse_generic(html_text, src["name"], src["url"]))
        except Exception:
            continue

    # תוספת "רשמית" קבועה - ניוזלטר/מבצעים באתר
    items.append({
        "source": "Timberland",
        "code": "",
        "title": "Join newsletter for a first purchase discount (see site promos)",
        "url": "https://www.timberland.co.il/",
    })

    items = _dedupe_keep_order(items)

    payload = {"ts": now, "items": items}
    _save_cache(payload)

    return items[:max_items]
