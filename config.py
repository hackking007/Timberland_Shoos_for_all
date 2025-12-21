import os

# Telegram Bot Configuration
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Base URLs and Site Configuration
TIMBERLAND_BASE_URL = "https://www.timberland.co.il"
SEARCH_URL = f"{TIMBERLAND_BASE_URL}/search"

# File paths
USER_DATA_FILE = "bot/data/user_data.json"
SIZE_MAP_FILE = "bot/mappings/size_map.json"
CATEGORY_MAP_FILE = "bot/mappings/category_map.json"

# Onboarding States
class OnboardingState:
    NOT_STARTED = "NOT_STARTED"
    SELECT_CATEGORY = "SELECT_CATEGORY"
    SELECT_SIZE = "SELECT_SIZE"
    SELECT_PRICE = "SELECT_PRICE"
    COMPLETED = "COMPLETED"

# Event Types
class EventType:
    NEW_PRODUCT = "NEW_PRODUCT"
    PRICE_DROP = "PRICE_DROP"
    REMOVED_PRODUCT = "REMOVED_PRODUCT"
