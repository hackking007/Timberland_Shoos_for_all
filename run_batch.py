# run_batch.py
# Purpose: Twice-daily batch runner for all users' preferences.
# - Reads user preferences from user_data.json
# - Builds per-user Timberland URL (category + size + price range)
# - Runs the scraper (via main_playwright.py) per user
# - Sends Telegram messages per user only on new/changed results
#
# Notes:
# * Works even if main_playwright.py does not expose a function.
#   It will try to import a callable first; if not found, it falls back to subprocess.
# * Keeps lightweight state in state/last_hash.json to avoid duplicate notifications.

import json, os, hashlib, subprocess, sys, time
from pathlib import Path
from typing import Dict, Any, List

# ---------- Config ----------
STATE_DIR = Path("state")
STATE_DIR.mkdir(exist_ok=True)
LAST_HASH_PATH = STATE_DIR / "last_hash.json"
OUTPUT_DIR = Path("out")
OUTPUT_DIR.mkdir(exist_ok=True)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
API_BASE = "https://api.telegram.org/bot{}/sendMessage".format(TELEGRAM_TOKEN)

SIZE_MAP_PATH = Path("size_map.json")  # expects mapping like {"43": "794", "37": "799"}

# ---------- Helpers ----------

def load_json(path: Path, default):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception:
        return default

def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def sha1_of(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()

def build_url(category: str, size_code: str, price_min: int, price_max: int) -> str:
    """
    Builds Timberland IL query URL. Adjust path/params if your scraper expects a different endpoint.
    We rely on your known params: size=<code>, price=0_300 (or 0_305).
    """
    # You can tweak base path to exact Timberland IL category route you scrape today.
    # Using placeholder 'men'/'women'/'kids' switch below.
    base_by_cat = {
        "men":   "https://www.timberland.co.il/men?size={size}&price={pmin}_{pmax}",
        "women": "https://www.timberland.co.il/women?size={size}&price={pmin}_{pmax}",
        "kids":  "https://www.timberland.co.il/kids?size={size}&price={pmin}_{pmax}",
    }
    base = base_by_cat.get(category.lower(), base_by_cat["men"])
    return base.format(size=size_code, pmin=price_min, pmax=price_max)

def send_telegram(chat_id: int, text: str, disable_web_page_preview=True) -> None:
    import urllib.parse, urllib.request
    if not TELEGRAM_TOKEN:
        print("WARN: TELEGRAM_TOKEN missing; skipping Telegram send.")
        return
    params = {
        "chat_id": str(chat_id),
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true" if disable_web_page_preview else "false",
    }
    url = API_BASE + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            _ = resp.read()
    except Exception as e:
        print(f"WARN: Telegram send failed for {chat_id}: {e}")

def extract_items_from_stdout(stdout: str) -> List[Dict[str, Any]]:
    """
    Minimal parser: if your main_playwright prints JSON on a line (e.g. after scraping),
    we try to load it. Otherwise, we fallback to extracting lines that look like items.
    Recommended: make main_playwright print one JSON line like:
    >>> print(json.dumps({"items":[...]}))
    """
    # Try JSON object line
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("{") and line.endswith("}"):
            try:
                obj = json.loads(line)
                if isinstance(obj, dict) and "items" in obj and isinstance(obj["items"], list):
                    return obj["items"]
            except Exception:
                pass
    # Fallback: naive extraction (customize for your output)
    items = []
    for line in stdout.splitlines():
        if "http" in line:
            items.append({"title": line.strip()[:120], "url": line.strip()})
    return items

def run_scraper_via_subprocess(url: str, user_id: str) -> List[Dict[str, Any]]:
    """
    Calls main_playwright.py with --url (if supported). If not, just runs without args.
    Captures stdout and tries to parse items.
    """
    cmds = [
        ["python", "main_playwright.py", "--url", url],
        ["python", "main_playwright.py"]  # fallback
    ]
    for cmd in cmds:
        try:
            print(f"Running: {' '.join(cmd)} (user={user_id})")
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                check=False
            )
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            if proc.returncode != 0:
                print(f"Scraper exit code={proc.returncode}. stderr:\n{stderr[:500]}")
            items = extract_items_from_stdout(stdout)
            if items:
                # Persist raw results for inspection
                save_json(OUTPUT_DIR / f"{user_id}.json", {"url": url, "items": items})
                return items
        except Exception as e:
            print(f"WARN: Subprocess scrape failed ({cmd}): {e}")
    return []

def build_user_summary(user_id: str, prefs: Dict[str, Any], items: List[Dict[str, Any]], url: str) -> str:
    title = f"👟 Timberland — {prefs.get('category','men')}, size {prefs.get('size')}, up to {prefs.get('max_price')}"
    if not items:
        return f"{title}\n\nNo matching items right now.\n\n🔎 Query: {url}"
    lines = [title, ""]
    for i, it in enumerate(items[:10], 1):
        t = it.get("title") or it.get("name") or "Item"
        link = it.get("url") or it.get("link") or url
        price = it.get("price") or it.get("amount") or ""
        lines.append(f"{i}. {t[:80]}{' — ' + str(price) if price else ''}\n{link}")
    if len(items) > 10:
        lines.append(f"\n(+{len(items)-10} more…) 🔎 {url}")
    else:
        lines.append(f"\n🔎 Query: {url}")
    return "\n".join(lines)

# ---------- Main batch ----------

def main():
    # Load maps and state
    size_map = load_json(SIZE_MAP_PATH, {})
    last_hash = load_json(LAST_HASH_PATH, {})

    # user_data.json schema expected like:
    # {
    #   "<user_id>": {
    #       "chat_id": 123456789,
    #       "category": "men"|"women"|"kids",
    #       "size": "43",
    #       "price_min": 0,
    #       "price_max": 300
    #   },
    #   ...
    # }
    user_data = load_json(Path("user_data.json"), {})

    if not user_data:
        print("No users found in user_data.json — nothing to do.")
        return

    for user_id, prefs in user_data.items():
        try:
            chat_id = int(prefs.get("chat_id") or user_id)
        except Exception:
            chat_id = None

        category = (prefs.get("category") or "men").lower()
        size_str = str(prefs.get("size") or "")
        price_min = int(prefs.get("price_min") or 0)
        price_max = int(prefs.get("price_max") or 300)

        size_code = size_map.get(size_str)
        if not size_code:
            print(f"WARN: size {size_str} has no mapping in size_map.json — skipping user {user_id}")
            continue

        url = build_url(category, size_code, price_min, price_max)

        # --- scrape ---
        items = run_scraper_via_subprocess(url, user_id)

        # --- compute hash to dedupe notifications ---
        payload_for_hash = json.dumps({"url": url, "items": items}, ensure_ascii=False, sort_keys=True)
        curr_hash = sha1_of(payload_for_hash)
        prev_hash = last_hash.get(user_id)

        if curr_hash == prev_hash:
            print(f"No changes for user {user_id} — skipping notify.")
            continue

        # --- build message & send ---
        text = build_user_summary(user_id, prefs, items, url)

        if chat_id:
            send_telegram(chat_id, text)
            print(f"Sent update to user {user_id} (chat_id {chat_id}).")
        else:
            print(f"User {user_id} has no chat_id; printing message instead:\n{text}")

        last_hash[user_id] = curr_hash
        time.sleep(1.5)  # tiny gap to avoid Telegram flood

    save_json(LAST_HASH_PATH, last_hash)
    print("Batch completed.")

if __name__ == "__main__":
    main()
