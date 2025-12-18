#!/usr/bin/env python3
# smart_alerts.py - Smart alerts system
import json
import os
import time
import requests
import re
from datetime import datetime

PRICE_HISTORY_FILE = "price_history.json"
STOCK_ALERTS_FILE = "stock_alerts.json"
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

def extract_price(price_text):
    """Extract numeric price from text like '299 ₪' or '₪299'"""
    if not price_text:
        return None
    
    # Find numbers in the price text
    numbers = re.findall(r'\d+', price_text.replace(',', ''))
    if numbers:
        return int(numbers[0])
    return None

def update_price_history(product_id, current_price, title=""):
    """Track price changes for products"""
    history = load_json(PRICE_HISTORY_FILE, {})
    now = int(time.time())
    
    if product_id not in history:
        history[product_id] = {
            "title": title,
            "prices": [],
            "lowest_price": current_price,
            "highest_price": current_price
        }
    
    product = history[product_id]
    
    # Add current price
    product["prices"].append({"price": current_price, "timestamp": now})
    
    # Keep only last 30 price points
    product["prices"] = product["prices"][-30:]
    
    # Update min/max
    if current_price < product["lowest_price"]:
        product["lowest_price"] = current_price
    if current_price > product["highest_price"]:
        product["highest_price"] = current_price
    
    save_json(PRICE_HISTORY_FILE, history)
    return product

def check_price_alerts(items, user_data):
    """Check if any prices dropped below user thresholds"""
    alerts_sent = []
    
    for item in items:
        current_price = extract_price(item.get("price", ""))
        if not current_price:
            continue
        
        product_id = item["id"]
        
        # Update price history
        product_history = update_price_history(product_id, current_price, item.get("title", ""))
        
        # Check alerts for each user
        for user_id, user in user_data.items():
            if user.get("state") != "ready":
                continue
                
            chat_id = user.get("chat_id")
            user_max_price = user.get("price_max", 999999)
            
            # Price drop alert
            if current_price <= user_max_price:
                lowest_ever = product_history["lowest_price"]
                
                alert_text = f"🔥 PRICE ALERT!\n\n"
                alert_text += f"📦 {item['title']}\n"
                alert_text += f"💰 Current: {current_price}₪\n"
                
                if current_price == lowest_ever:
                    alert_text += f"🎯 LOWEST PRICE EVER!\n"
                else:
                    alert_text += f"📊 Lowest ever: {lowest_ever}₪\n"
                
                alert_text += f"🔗 {item['link']}\n\n"
                alert_text += f"💡 Share with friend: /share_{product_id.split('/')[-1][:10]}"
                
                if send_message(chat_id, alert_text):
                    alerts_sent.append(f"Price alert sent to {user_id}")
    
    return alerts_sent

def check_stock_alerts():
    """Check for items back in stock"""
    stock_alerts = load_json(STOCK_ALERTS_FILE, {})
    user_data = load_json(USER_DATA_FILE, {})
    
    alerts_sent = []
    
    # This would be called when scanning products
    # For now, just return empty list
    return alerts_sent

def add_stock_alert(user_id, product_url, size):
    """Add user to stock alert list for specific product/size"""
    stock_alerts = load_json(STOCK_ALERTS_FILE, {})
    
    alert_key = f"{product_url}_{size}"
    
    if alert_key not in stock_alerts:
        stock_alerts[alert_key] = []
    
    if user_id not in stock_alerts[alert_key]:
        stock_alerts[alert_key].append(user_id)
    
    save_json(STOCK_ALERTS_FILE, stock_alerts)

def get_price_history_summary(product_id):
    """Get price history summary for a product"""
    history = load_json(PRICE_HISTORY_FILE, {})
    
    if product_id not in history:
        return "No price history available"
    
    product = history[product_id]
    lowest = product["lowest_price"]
    highest = product["highest_price"]
    
    recent_prices = product["prices"][-5:]  # Last 5 prices
    
    summary = f"📊 Price History:\n"
    summary += f"🔻 Lowest: {lowest}₪\n"
    summary += f"🔺 Highest: {highest}₪\n"
    
    if len(recent_prices) > 1:
        trend = "📈" if recent_prices[-1]["price"] > recent_prices[-2]["price"] else "📉"
        summary += f"{trend} Recent trend\n"
    
    return summary

def generate_share_link(product_id, title, price, url):
    """Generate shareable message for a product"""
    share_text = f"👟 Found this on Timberland!\n\n"
    share_text += f"📦 {title}\n"
    share_text += f"💰 {price}\n"
    share_text += f"🔗 {url}\n\n"
    share_text += f"🤖 Get your own alerts: @YourTimberlandBot"
    
    return share_text

def process_smart_alerts(items, user_data):
    """Main function to process all smart alerts"""
    results = {
        "price_alerts": [],
        "stock_alerts": [],
        "total_processed": len(items)
    }
    
    # Check price alerts
    results["price_alerts"] = check_price_alerts(items, user_data)
    
    # Check stock alerts
    results["stock_alerts"] = check_stock_alerts()
    
    return results
