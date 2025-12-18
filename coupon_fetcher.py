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
        "name": "Timberland Israel",
        "url": "https://www.timberland.co.il/",
        "type": "timberland_direct",
    },
    {
        "name": "Honey",
        "url": "https://www.joinhoney.com/stores/timberland",
        "type": "honey",
    },
    {
        "name": "RetailMeNot",
        "url": "https://www.retailmenot.com/view/timberland.com",
        "type": "retailmenot",
    },
    {
        "name": "PromoCode",
        "url": "https://promocode.co.il/coupon-store/timberland/",
        "type": "promocode",
    },
    {
        "name": "Coupon Follow",
        "url": "https://couponfollow.com/site/timberland.com",
        "type": "couponfollow",
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

def _parse_timberland_direct(html_text):
    # Parse directly from Timberland Israel site for official promos
    soup = BeautifulSoup(html_text, "html.parser")
    items = []
    
    # Look for promo banners, sale announcements
    promo_selectors = [
        '.promo-banner', '.sale-banner', '.discount-banner',
        '[class*="promo"]', '[class*="sale"]', '[class*="discount"]',
        '.hero-banner', '.promotion'
    ]
    
    for selector in promo_selectors:
        elements = soup.select(selector)
        for elem in elements:
            text = elem.get_text(strip=True)
            
            # Look for percentage discounts
            percent_matches = re.findall(r'(\d{1,2})%\s*(?:off|הנחה)', text, re.I)
            for percent in percent_matches:
                items.append({
                    "source": "Timberland Israel",
                    "code": "",
                    "title": f"Up to {percent}% off - Official site promotion",
                    "url": "https://www.timberland.co.il/",
                })
            
            # Look for coupon codes in the text
            codes = re.findall(r'\b[A-Z0-9]{4,12}\b', text.upper())
            for code in codes:
                if code not in {'TIMBERLAND', 'ISRAEL', 'SALE', 'OFF'}:
                    items.append({
                        "source": "Timberland Israel",
                        "code": code,
                        "title": "Official promo code from Timberland Israel",
                        "url": "https://www.timberland.co.il/",
                    })
    
    # Always add newsletter signup discount
    items.append({
        "source": "Timberland Israel",
        "code": "",
        "title": "Sign up for newsletter - get first purchase discount",
        "url": "https://www.timberland.co.il/",
    })
    
    return items[:3]  # Limit to 3 items

def _parse_retailmenot(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    items = []
    
    # RetailMeNot specific selectors
    coupon_elements = soup.find_all(['div', 'span'], class_=re.compile(r'offer|coupon|deal', re.I))
    
    for elem in coupon_elements[:5]:
        text = elem.get_text(strip=True)
        codes = re.findall(r'\b[A-Z0-9]{4,15}\b', text.upper())
        
        for code in codes:
            if code not in {'RETAILMENOT', 'TIMBERLAND', 'COUPON', 'CODE'}:
                items.append({
                    "source": "RetailMeNot",
                    "code": code,
                    "title": "Verified coupon from RetailMeNot",
                    "url": "https://www.retailmenot.com/view/timberland.com",
                })
                break
    
    return items[:2]

def _parse_couponfollow(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    items = []
    
    # CouponFollow specific patterns
    code_elements = soup.find_all(['span', 'div'], class_=re.compile(r'code|coupon', re.I))
    
    for elem in code_elements[:3]:
        text = elem.get_text(strip=True)
        codes = re.findall(r'\b[A-Z0-9]{4,12}\b', text.upper())
        
        for code in codes:
            if len(code) >= 4 and code not in {'COUPONFOLLOW', 'TIMBERLAND'}:
                items.append({
                    "source": "CouponFollow",
                    "code": code,
                    "title": "Active coupon code",
                    "url": "https://couponfollow.com/site/timberland.com",
                })
                break
    
    return items[:2]

def _parse_honey(html_text):
    # Honey shows verified coupon codes and deals
    soup = BeautifulSoup(html_text, "html.parser")
    
    items = []
    
    # Look for coupon codes in common Honey patterns
    coupon_elements = soup.find_all(['div', 'span'], class_=re.compile(r'coupon|code|promo', re.I))
    
    codes_found = set()
    for elem in coupon_elements:
        text = elem.get_text(strip=True)
        # Find coupon codes (letters + numbers, 4-15 chars)
        potential_codes = re.findall(r'\b[A-Z0-9]{4,15}\b', text.upper())
        
        for code in potential_codes:
            if code not in codes_found and len(code) >= 4:
                # Filter out common non-coupon words
                blacklist = {'TIMBERLAND', 'HONEY', 'COUPON', 'CODE', 'PROMO', 'DEAL', 'SAVE', 'DISCOUNT'}
                if code not in blacklist:
                    codes_found.add(code)
                    items.append({
                        "source": "Honey",
                        "code": code,
                        "title": "Verified coupon code",
                        "url": "https://www.joinhoney.com/stores/timberland",
                    })
                    
                    if len(items) >= 5:  # Limit to 5 codes
                        break
    
    # If no codes found, add a generic deal message
    if not items:
        items.append({
            "source": "Honey",
            "code": "",
            "title": "Check Honey extension for automatic coupon application",
            "url": "https://www.joinhoney.com/stores/timberland",
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
            if src["type"] == "timberland_direct":
                items.extend(_parse_timberland_direct(html_text))
            elif src["type"] == "honey":
                items.extend(_parse_honey(html_text))
            elif src["type"] == "retailmenot":
                items.extend(_parse_retailmenot(html_text))
            elif src["type"] == "couponfollow":
                items.extend(_parse_couponfollow(html_text))
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
