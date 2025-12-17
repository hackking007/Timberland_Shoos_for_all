# timberland_checker.py
import json
import os
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from config import (
    TELEGRAM_BOT_TOKEN,
    USER_DATA_FILE,
    STATE_FILE,
    SIZE_MAP_FILE,
    ENABLE_DEBUG_LOGS,
    SHOES_URLS,
    CLOTHING_URLS,
    CLOTHING_SIZE_MAP,
    SEND_HOURS_IL,
    SCAN_TIMEOUT,
    MAX_LOAD_MORE_CLICKS,
    LOAD_MORE_DELAY,
)

API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


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


def html_escape(s: str) -> str:
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def send_message(chat_id: int, text: str):
    url = f"{API}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    r = requests.post(url, data=payload, timeout=30)
    log(f"send_message -> {r.status_code} {r.text[:200]}")
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
    log(f"send_photo -> {r.status_code} {r.text[:200]}")
    return r


def il_hour_now() -> int:
    # GitHub runner is UTC. Israel is UTC+2 in winter, UTC+3 in summer.
    # We keep it simple: read local time from TZ if set, otherwise assume UTC and shift by env IL_OFFSET.
    # Default winter offset +2.
    offset = int(os.getenv("IL_UTC_OFFSET", "2"))
    now_utc = datetime.now(timezone.utc)
    il = now_utc.replace(tzinfo=timezone.utc).astimezone(timezone.utc)
    # manual offset without pytz:
    il_hour = (now_utc.hour + offset) % 24
    return il_hour


def in_send_window() -> bool:
    # Manual run should always run
    if os.getenv("GITHUB_EVENT_NAME", "") == "workflow_dispatch":
        return True
    if os.getenv("FORCE_CHECKER", "").strip() ==