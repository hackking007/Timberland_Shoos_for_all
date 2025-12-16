import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from config import *  # משתמש בכל ה-STATE_FILE, USER_DATA_FILE, SIZE_MAP_FILE, CATEGORIES וכו'

# ---------------- Telegram helpers ----------------

# נעדיף את ה-TOKEN מה-ENV (שמגיע מה-GitHub Secret), ואם אין - ניפול ל-TELEGRAM_TOKEN מה-config
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", None) or TELEGRAM_TOKEN


def send_telegram_message(text, chat_id=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    target_chat = chat_id or ADMIN_CHAT_ID
    payload = {
        "chat_id": target_chat,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        requests.post(url, data=payload, timeout=30)
    except Exception as e:
        if ENABLE_DEBUG_LOGS:
            print(f"Error sending message: {e}")


def send_photo_with_caption(image_url, caption, chat_id=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    target_chat = chat_id or ADMIN_CHAT_ID
    payload = {
        "chat_id": target_chat,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "Markdown",
    }
    try:
        requests.post(url, data=payload, timeout=30)
    except Exception as e:
        if ENABLE_DEBUG_LOGS:
            print(f"Error sending photo: {e}")


# ---------------- State / config helpers ----------------

def load_previous_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def save_current_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        if ENABLE_DEBUG_LOGS:
            print(f"Error saving state: {e}")


def load_user_preferences():
    """
    user_data.json בפורמט החדש:
    {
      "123456": {
         "state": "ready",
         "gender": "men",
         "category": "shoes" | "clothing" | "both",
         "size": "43",
         "price_min": 0,
         "price_max": 300
      },
      ...
    }
    """
    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def load_size_mapping():
    try:
        with open(SIZE_MAP_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # ברירת מחדל אם הקובץ לא קיים
        return {
            "men": {"40": 791, "41": 792, "42": 793, "43": 794, "44": 795, "45": 796},
            "women": {"36": 798, "37": 799, "38": 800, "39": 801, "40": 802, "41": 803},
            "kids": {
                "28": 230,
                "29": 231,
                "30": 232,
                "31": 233,
                "32": 234,
                "33": 235,
                "34": 236,
                "35": 237,
            },
        }
    except Exception:
        return {}


def size_to_code(size, gender):
    """
    size: מחרוזת מידה (למשל "43")
    gender: "men" / "women" / "kids"
    """
    size_mapping = load_size_mapping()
    return str(size_mapping.get(gender, {}).get(str(size), ""))


def build_url_for_user(gender, size, price_min, price_max):
    """
    gender: men / women / kids
    size: מחרוזת מידה
    price_min / price_max: מספרים (int)
    משתמש ב-CATEGORIES מה-config (בדומה לקוד הישן שלך)
    """
    if gender not in CATEGORIES:
        return None

    base_url = CATEGORIES[gender]["url"]  # לדוגמה: URL לנעלי גברים באתר
    size_code = size_to_code(size, gender)
    if not size_code:
        return None

    price_param = f"{price_min}_{price_max}"  # למשל 0_300
    return f"{base_url}?price={price_param}&size={size_code}&product_list_order=low_to_high"


# ---------------- Main logic ----------------

def run_checker():
    if ENABLE_DEBUG_LOGS:
        from datetime import datetime
        print(f"[{datetime.now()}] Starting shoe check...")

    previous_state = load_previous_state()
    current_state = {}
    user_data = load_user_preferences()

    if not user_data:
        if ENABLE_DEBUG_LOGS:
            print("No registered users found.")
        if ENABLE_ADMIN_NOTIFICATIONS:
            send_telegram_message("⚠️ אין משתמשים רשומים.")
        return

    if ENABLE_DEBUG_LOGS:
        print(f"Found {len(user_data)} registered users.")

    for user_id, prefs in user_data.items():
        state = prefs.get("state")
        if state != "ready":
            if ENABLE_DEBUG_LOGS:
                print(f"Skipping user {user_id} because state={state}")
            continue

        # מה-onboarding החדש
        gender = prefs.get("gender", "men")       # men / women / kids
        product_type = prefs.get("category", "shoes")  # shoes / clothing / both (כרגע רק ללוג/להמשך)
        size = prefs.get("size", "43")
        price_min = prefs.get("price_min", 0)
        price_max = prefs.get("price_max", 300)
        chat_id = prefs.get("chat_id", user_id)  # אם בעתיד נרצה chat_id שונה

        url = build_url_for_user(gender, size, price_min, price_max)

        if ENABLE_ADMIN_NOTIFICATIONS:
            debug_msg = (
                f"🔍 *בודק למשתמש:* `{user_id}`\n"
                f"מגדר: {gender} | סוג מוצר: {product_type} | מידה: {size} | טווח: {price_min}-{price_max}\n\n{url}"
            )
            send_telegram_message(debug_msg)

        if ENABLE_DEBUG_LOGS:
            print(
                f"Checking for user {user_id}: gender={gender}, "
                f"type={product_type}, size={size}, price={price_min}-{price_max}"
            )

        if not url:
            if ENABLE_DEBUG_LOGS:
                print(f"Error generating URL for user {user_id}")
            if ENABLE_ADMIN_NOTIFICATIONS:
                send_telegram_message(
                    f"❌ שגיאה ביצירת URL למשתמש `{user_id}`", chat_id=chat_id
                )
            continue

        try:
            with sync_playwright() as p:
                if ENABLE_DEBUG_LOGS:
                    print(f"Launching browser for user {user_id}...")
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(locale="he-IL")
                page = context.new_page()
                page.goto(url, timeout=SCAN_TIMEOUT)

                # טעינת כל המוצרים (לחיצה על "עוד")
                products_loaded = 0
                while True:
                    try:
                        load_more = page.query_selector("a.action.more")
                        if load_more:
                            load_more.click()
                            page.wait_for_timeout(LOAD_MORE_DELAY)
                            products_loaded += 1
                            if products_loaded > MAX_LOAD_MORE_CLICKS:
                                break
                        else:
                            break
                    except Exception as e:
                        if ENABLE_DEBUG_LOGS:
                            print(f"Error loading more products: {str(e)}")
                        break

                soup = BeautifulSoup(page.content(), "html.parser")
                product_cards = soup.select("div.product")
                if ENABLE_DEBUG_LOGS:
                    print(f"Found {len(product_cards)} products for user {user_id}")

                all_items = []
                new_products = 0

                for card in product_cards:
                    link_tag = card.select_one("a")
                    img_tag = card.select_one("img")
                    price_tags = card.select("span.price")

                    title = (
                        img_tag["alt"].strip()
                        if img_tag and img_tag.has_attr("alt")
                        else "ללא שם"
                    )
                    link = (
                        link_tag["href"]
                        if link_tag and link_tag.has_attr("href")
                        else None
                    )
                    if not link:
                        continue
                    if not link.startswith("http"):
                        link = "https://www.timberland.co.il" + link

                    img_url = img_tag["src"] if img_tag and img_tag.has_attr("src") else None

                    prices = []
                    for tag in price_tags:
                        try:
                            text = (
                                tag.text.strip()
                                .replace("\xa0", "")
                                .replace("₪", "")
                                .replace(",", "")
                            )
                            price_val = float(text)
                            if price_val > 0:
                                prices.append(price_val)
                        except Exception:
                            continue
                    if not prices:
                        continue

                    price_val = min(prices)

                    key = f"{user_id}_{link}"
                    current_state[key] = {
                        "title": title,
                        "link": link,
                        "price": price_val,
                        "img_url": img_url,
                    }

                    all_items.append(
                        {
                            "title": title,
                            "link": link,
                            "price": price_val,
                            "img_url": img_url,
                            "is_new": key not in previous_state,
                        }
                    )

                    if key not in previous_state:
                        caption = f"*{title}* - ₪{int(price_val)}\n[לינק למוצר]({link})"
                        try:
                            send_photo_with_caption(
                                img_url or "https://via.placeholder.com/300",
                                caption,
                                chat_id,
                            )
                            if ENABLE_DEBUG_LOGS:
                                print(f"Sent NEW item to user {user_id}: {title}")
                            new_products += 1
                        except Exception as e:
                            if ENABLE_DEBUG_LOGS:
                                print(
                                    f"Failed to send photo message to user {user_id}: {str(e)}"
                                )

                # סיכום מרוכז
                if all_items:
                    all_items.sort(key=lambda x: x["price"])
                    subset = all_items[:15]
                    header = (
                        f"*👟 תוצאות עדכניות* — {gender}, מידה {size}, "
                        f"טווח {price_min}-{price_max}\n"
                    )
                    lines = []
                    for i, it in enumerate(subset, 1):
                        mark = "🆕 " if it["is_new"] else ""
                        lines.append(
                            f"{i}. {mark}*{it['title'][:60]}* — ₪{int(it['price'])}\n{it['link']}"
                        )
                    if len(all_items) > len(subset):
                        lines.append(f"\nועוד {len(all_items) - len(subset)} פריטים…")
                    lines.append(f"\n🔎 חיפוש: {url}")
                    msg = header + "\n".join(lines)
                    send_telegram_message(msg, chat_id=chat_id)
                    if ENABLE_DEBUG_LOGS:
                        print(
                            f"Sent summary to user {user_id} with {len(subset)} items "
                            f"(total {len(all_items)})."
                        )
                else:
                    send_telegram_message(
                        f"*👟 לא נמצאו פריטים כרגע* — {gender}, מידה {size}, "
                        f"טווח {price_min}-{price_max}\n\n🔎 {url}",
                        chat_id=chat_id,
                    )
                    if ENABLE_DEBUG_LOGS:
                        print(
                            f"No items found for user {user_id}, sent empty summary."
                        )

                browser.close()
                if ENABLE_DEBUG_LOGS:
                    print(
                        f"Completed scan for user {user_id} "
                        f"(new={new_products}, total={len(all_items)})"
                    )

        except Exception as e:
            if ENABLE_DEBUG_LOGS:
                print(f"Error scanning for user {user_id}: {str(e)}")
            if ENABLE_ADMIN_NOTIFICATIONS:
                send_telegram_message(
                    f"❌ שגיאה בסריקה למשתמש `{user_id}`: {str(e)}", chat_id=chat_id
                )
            continue

    save_current_state(current_state)
    if ENABLE_DEBUG_LOGS:
        from datetime import datetime
        print(
            f"[{datetime.now()}] Shoe check completed. "
            f"Stored {len(current_state)} items total."
        )


if __name__ == "__main__":
    try:
        run_checker()
    except KeyboardInterrupt:
        if ENABLE_DEBUG_LOGS:
            print("\nScan interrupted by user.")
    except Exception as e:
        if ENABLE_DEBUG_LOGS:
            print(f"Fatal error: {str(e)}")
        if ENABLE_ADMIN_NOTIFICATIONS:
            send_telegram_message(f"❌ שגיאה בסריקה: {str(e)}")
