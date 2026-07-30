"""
Gandiv AI Trading Terminal - Data Fetching & Indicators Core
"""

import pandas as pd
import yfinance as yf
import streamlit as st

@st.cache_data(ttl=300)
def fetch_technical_data(symbol):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="6m")
        if df.empty or len(df) < 50:
            return None
            
        df["MA20"] = df["Close"].rolling(20).mean()
        df["MA50"] = df["Close"].rolling(50).mean()
        
        delta = df["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df["RSI"] = 100 - (100 / (1 + rs))
        
        cp = float(df["Close"].iloc[-1])
        ma20 = float(df["MA20"].iloc[-1])
        ma50 = float(df["MA50"].iloc[-1])
        rsi = float(df["RSI"].iloc[-1])
        
        trend = "Bullish" if cp > ma20 and ma20 > ma50 else ("Bearish" if cp < ma20 else "Neutral")
        
        return {
            "current_price": round(cp, 2),
            "ma20": round(ma20, 2),
            "ma50": round(ma50, 2),
            "rsi": round(rsi, 2),
            "trend": trend
        }
    except Exception:
        return None

def calculate_charges(buy_price, sell_price, qty):
    turnover = (buy_price + sell_price) * qty
    gross_pnl = round((sell_price - buy_price) * qty, 2)
    stt = round(turnover * 0.001, 2)
    brokerage = round(min(40, turnover * 0.0003), 2)
    total_charges = round(stt + brokerage + 15, 2)
    net_pnl = round(gross_pnl - total_charges, 2)
    net_pnl_pct = round((net_pnl / (buy_price * qty)) * 100, 2) if (buy_price * qty) > 0 else 0
    
    return {
        "gross_pnl": gross_pnl,
        "total_charges": total_charges,
        "net_pnl": net_pnl,
        "net_pnl_pct": net_pnl_pct
    }
  
