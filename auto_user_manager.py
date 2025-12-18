#!/usr/bin/env python3
# auto_user_manager.py - Auto-manage problematic users
import json
import os
import requests
from datetime import datetime, timedelta

USER_DATA_FILE = "user_data.json"
TELEGRAM_BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or "").strip()
API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def send_message(chat_id, text):
    url = f"{API}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        r = requests.post(url, data=payload, timeout=30)
        return r.status_code == 200
    except:
        return False

def auto_fix_users():
    """Automatically fix common user issues"""
    user_data = load_json(USER_DATA_FILE, {})
    
    if not user_data:
        print("No users found")
        return
    
    fixed_count = 0
    
    for user_id, user in user_data.items():
        chat_id = user.get("chat_id")
        state = user.get("state")
        
        # Fix 1: Users stuck in awaiting_setup for too long
        if state == "awaiting_setup":
            # Send helpful reminder
            reminder_msg = (
                "🔧 Setup Reminder\n\n"
                "You haven't completed your setup yet!\n\n"
                "Send a message like:\n"
                "1 A 43 100 500\n\n"
                "Format: <gender> <type> <size> <min_price> <max_price>\n\n"
                "1=Men, 2=Women, 3=Kids\n"
                "A=Shoes, B=Clothing, C=Both\n\n"
                "Need help? Send /start for full instructions"
            )
            
            if send_message(chat_id, reminder_msg):
                print(f"✅ Sent reminder to user {user_id}")
                fixed_count += 1
        
        # Fix 2: Users with invalid data
        elif state == "ready":
            issues = []
            
            # Check for missing required fields
            if not user.get("gender"):
                issues.append("missing gender")
            if not user.get("category"):
                issues.append("missing category")
            if user.get("category") in ("shoes", "both") and not user.get("shoes_size"):
                issues.append("missing shoe size")
            if user.get("category") in ("clothing", "both") and not user.get("clothing_size"):
                issues.append("missing clothing size")
            
            if issues:
                fix_msg = (
                    "⚠️ Setup Issue Detected\n\n"
                    f"Problems found: {', '.join(issues)}\n\n"
                    "Please reset and setup again:\n"
                    "1. Send /reset\n"
                    "2. Send your setup message like: 1 A 43 100 500\n\n"
                    "This will ensure you receive product updates!"
                )
                
                if send_message(chat_id, fix_msg):
                    print(f"✅ Sent fix message to user {user_id} (issues: {issues})")
                    fixed_count += 1
    
    print(f"Auto-fix completed. Helped {fixed_count} users.")

def send_mass_message():
    """Send message to all users (for maintenance/updates)"""
    user_data = load_json(USER_DATA_FILE, {})
    
    # Example maintenance message
    maintenance_msg = (
        "🔧 Bot Update\n\n"
        "The Timberland bot has been updated!\n\n"
        "If you're not receiving products:\n"
        "1. Send /reset\n"
        "2. Send your setup again (e.g., 1 A 43 100 500)\n\n"
        "Products are sent at 07:00 and 19:00 Israel time.\n\n"
        "Thanks for using our service! 👟"
    )
    
    sent_count = 0
    for user_id, user in user_data.items():
        chat_id = user.get("chat_id")
        if send_message(chat_id, maintenance_msg):
            sent_count += 1
    
    print(f"Maintenance message sent to {sent_count}/{len(user_data)} users")

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: Missing TELEGRAM_BOT_TOKEN")
        return
    
    print("=== Auto User Manager ===")
    
    # Run auto-fix for problematic users
    auto_fix_users()
    
    # Uncomment this line if you want to send maintenance message to all users
    # send_mass_message()

if __name__ == "__main__":
    main()
