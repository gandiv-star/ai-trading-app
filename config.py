"""
Gandiv AI Trading Terminal - Central Configuration
"""

# Base Universe
STOCK_UNIVERSE = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "SBIN.NS", "LT.NS", "BHARTIARTL.NS", "ITC.NS", "HINDUNILVR.NS",
    "INDUSINDBK.NS", "TATASTEEL.NS", "TATAMOTORS.NS", "GRASIM.NS", "ZOMATO.NS"
]

# Sector Mapping
SECTOR_MAP = {
    "RELIANCE.NS": "Energy", "TCS.NS": "IT", "INFY.NS": "IT",
    "HDFCBANK.NS": "Banking", "ICICIBANK.NS": "Banking", "SBIN.NS": "Banking",
    "INDUSINDBK.NS": "Banking", "LT.NS": "Capital Goods", "BHARTIARTL.NS": "Telecom",
    "ITC.NS": "FMCG", "HINDUNILVR.NS": "FMCG", "TATASTEEL.NS": "Metals",
    "TATAMOTORS.NS": "Auto", "GRASIM.NS": "Cement", "ZOMATO.NS": "Services"
}

# Sector Caps & Risk Rules
SECTOR_CAPS = {
    "Banking": 0.20,
    "IT": 0.20,
    "Pharma": 0.15,
    "FMCG": 0.15,
    "Auto": 0.15,
    "Other": 0.15
}

SINGLE_STOCK_CAP = 0.08  # Max 8% per stock
