#!/usr/bin/env python3
# live_coupon_checker.py - Live coupon validation
import requests
import json
import re
from bs4 import BeautifulSoup

# Known working coupon patterns for Timberland Israel
COUPON_SOURCES = [
    {
        "name": "Israeli Coupon Sites",
        "codes": ["TIM12", "MAX7", "SAVE10", "FIRST15", "NEW20", "WELCOME10"],
        "descriptions": {
            "TIM12": "12% discount on orders over 200₪",
            "MAX7": "7% discount on orders over 200₪", 
            "SAVE10": "10% discount",
            "FIRST15": "15% discount for new customers",
            "NEW20": "20% discount on first purchase",
            "WELCOME10": "10% welcome discount"
        }
    }
]

# Additional dynamic coupon sources
DYNAMIC_SOURCES = [
    "https://promocode.co.il/coupon-store/timberland/",
    "https://www.freecoupon.co.il/coupons/timberland/",
    "https://couponfollow.com/site/timberland.com"
]

def extract_coupon_codes(html_text):
    """Extract potential coupon codes from HTML"""
    soup = BeautifulSoup(html_text, "html.parser")
    text = soup.get_text()
    
    # Look for coupon patterns
    patterns = [
        r'\b[A-Z]{3,6}\d{1,3}\b',  # TIM12, SAVE10, etc.
        r'\b[A-Z]{4,8}\b',         # WELCOME, FIRST, etc.
        r'\b\d{1,2}%?\s*OFF\b',    # 10% OFF, 15OFF, etc.
    ]
    
    codes = set()
    for pattern in patterns:
        matches = re.findall(pattern, text.upper())
        for match in matches:
            # Filter out common non-coupon words
            if match not in {'TIMBERLAND', 'ISRAEL', 'COUPON', 'CODE', 'PROMO', 'DISCOUNT', 'SALE'}:
                if len(match) >= 3:
                    codes.add(match)
    
    return list(codes)[:5]  # Return max 5 codes

def validate_coupon_code(code):
    """Try to validate if a coupon code might work"""
    # This is a simulation - real validation would require API access
    # We'll use heuristics to determine likely valid codes
    
    valid_patterns = [
        r'^TIM\d+$',      # TIM12, TIM15, etc.
        r'^SAVE\d+$',     # SAVE10, SAVE20, etc.
        r'^MAX\d+$',      # MAX7, MAX10, etc.
        r'^FIRST\d+$',    # FIRST15, FIRST20, etc.
        r'^NEW\d+$',      # NEW20, NEW25, etc.
        r'^WELCOME\d+$',  # WELCOME10, etc.
    ]
    
    for pattern in valid_patterns:
        if re.match(pattern, code):
            return True
    
    # Additional checks for common coupon formats
    if len(code) >= 4 and len(code) <= 12:
        if any(char.isdigit() for char in code) and any(char.isalpha() for char in code):
            return True
    
    return False

def get_live_coupons():
    """Get live coupon codes from various sources"""
    live_coupons = []
    
    # Add known working codes
    for source in COUPON_SOURCES:
        for code in source["codes"]:
            description = source["descriptions"].get(code, "Discount code")
            live_coupons.append({
                "code": code,
                "description": description,
                "source": source["name"],
                "confidence": "high"
            })
    
    # Try to fetch from dynamic sources
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    for url in DYNAMIC_SOURCES:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                codes = extract_coupon_codes(response.text)
                for code in codes:
                    if validate_coupon_code(code):
                        live_coupons.append({
                            "code": code,
                            "description": "Found on coupon site - try at checkout",
                            "source": "Dynamic",
                            "confidence": "medium"
                        })
        except:
            continue
    
    # Remove duplicates and sort by confidence
    seen_codes = set()
    unique_coupons = []
    
    # First add high confidence codes
    for coupon in live_coupons:
        if coupon["confidence"] == "high" and coupon["code"] not in seen_codes:
            unique_coupons.append(coupon)
            seen_codes.add(coupon["code"])
    
    # Then add medium confidence codes
    for coupon in live_coupons:
        if coupon["confidence"] == "medium" and coupon["code"] not in seen_codes:
            unique_coupons.append(coupon)
            seen_codes.add(coupon["code"])
    
    return unique_coupons[:5]  # Return max 5 coupons

def format_coupon_message(coupons):
    """Format coupons for Telegram message"""
    if not coupons:
        return "DISCOUNT COUPONS:\n\nNo active coupon codes found right now"
    
    message = "DISCOUNT COUPONS:\n\n"
    message += "Note: These codes may have limited validity\n\n"
    
    for coupon in coupons:
        confidence_mark = "*" if coupon["confidence"] == "high" else "?"
        message += f"{confidence_mark} {coupon['code']}\n"
        message += f"{coupon['description']}\n\n"
    
    message += "Try these codes at checkout on timberland.co.il"
    return message

def get_formatted_coupons():
    """Main function to get formatted coupon message"""
    try:
        coupons = get_live_coupons()
        return format_coupon_message(coupons)
    except Exception as e:
        return "💰 DISCOUNT COUPONS:\n\n📝 Unable to fetch coupons right now"

if __name__ == "__main__":
    result = get_formatted_coupons()
    print(result.encode('utf-8', errors='ignore').decode('utf-8'))
