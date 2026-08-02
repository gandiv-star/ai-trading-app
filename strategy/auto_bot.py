"""
Gandiv AI Trading Terminal - Auto Bot Module (v6.0 - Telegram Alert Integrated)
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import yfinance as yf
import requests
from config import STOCK_UNIVERSE

# Safely get Telegram credentials from config or environment variables
try:
    from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
except ImportError:
    import os
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

from core.data_loader import fetch_technical_data, calculate_atr

def send_telegram_alert(message):
    """
    Sends automated message to Telegram Bot
    """
    try:
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
            requests.post(url, json=payload, timeout=5)
    except Exception as e:
        st.warning(f"⚠️ ટેલીગ્રામ નોટિફિકેશન મોકલવામાં એરર: {str(e)}")

def save_session_data_atomically():
    try:
        if "paper_portfolio" in st.session_state:
            st.session_state["paper_portfolio"] = dict(st.session_state.paper_portfolio)
        if "paper_trade_history" in st.session_state:
            st.session_state["paper_trade_history"] = list(st.session_state.paper_trade_history)
    except Exception as e:
        pass

def execute_auto_bot(max_pos=25, cap_per_trade=10000, min_score=75, target_pct=4.0, sl_pct=2.5):
    """
    Quant Auto Bot with Telegram Alert Engine
    """
    st.markdown("### 🤖 Auto Trading Bot Engine (v6.0 - Telegram Enabled)")
    
    now = datetime.now()
    if now.hour == 15 and now.minute >= 15:
        st.warning("⏰ માર્કેટ બંધ થવાનો સમય (3:15 PM) થઈ ગયો છે.")
        return

    try:
        results = []
        progress = st.progress(0)
        
        for idx, sym in enumerate(STOCK_UNIVERSE):
            try:
                ticker = yf.Ticker(sym)
                df = ticker.history(period="60d", interval="1d")
                
                if df.empty or len(df) < 30:
                    continue
                
                atr_val = calculate_atr(df, period=14)
                
                prev_candle_close = float(df["Close"].iloc[-2])
                prev_candle_open = float(df["Open"].iloc[-2])
                current_price = float(df["Close"].iloc[-1])
                
                ma20 = float(df["Close"].rolling(20).mean().iloc[-2])
                ma50 = float(df["Close"].rolling(50).mean().iloc[-2])
                
                delta = df["Close"].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss
                rsi_series = 100 - (100 / (1 + rs))
                rsi_completed = float(rsi_series.iloc[-2])

                is_bullish = prev_candle_close > prev_candle_open
                is_uptrend = prev_candle_close > ma20 and ma20 > ma50
                is_rsi_strong = rsi_completed >= 50

                if is_bullish and is_uptrend and is_rsi_strong:
                    atr_sl = current_price - (1.5 * atr_val) if atr_val > 0 else current_price * (1 - sl_pct / 100)
                    atr_tgt = current_price + (3.0 * atr_val) if atr_val > 0 else current_price * (1 + target_pct / 100)
                    
                    risk_per_share = max(current_price - atr_sl, 1.0)
                    max_risk_allowed = cap_per_trade * 0.02
                    qty = int(max_risk_allowed / risk_per_share)
                    final_qty = max(qty, 1)
                    
                    stock_name = sym.replace(".NS", "")
                    
                    results.append({
                        "Symbol": stock_name,
                        "Price (₹)": round(current_price, 2),
                        "Qty": final_qty,
                        "Dynamic SL (₹)": round(atr_sl, 2),
                        "Target (₹)": round(atr_tgt, 2),
                        "Signal": "BUY"
                    })
                    
                    # Telegram Message Formation
                    msg = (
                        f"🚀 <b>GANDIV TRADE ALERT</b> 🚀\n\n"
                        f"📌 <b>Stock:</b> {stock_name}\n"
                        f"💰 <b>Buy Price:</b> ₹{current_price:.2f}\n"
                        f"📦 <b>Qty:</b> {final_qty}\n"
                        f"🛑 <b>ATR Stop Loss:</b> ₹{atr_sl:.2f}\n"
                        f"🎯 <b>Target:</b> ₹{atr_tgt:.2f}\n"
                        f"⏰ <b>Time:</b> {now.strftime('%I:%M %p')}"
                    )
                    send_telegram_alert(msg)

            except Exception:
                pass
                
            progress.progress((idx + 1) / len(STOCK_UNIVERSE))
            
        save_session_data_atomically()
        
        if results:
            st.success(f"✅ {len(results)} નવા સિગ્નલ્સ મળ્યા અને ટેલીગ્રામમાં મોકલાયા!")
            st.dataframe(pd.DataFrame(results), use_container_width=True)
            
            # Run Summary Telegram Message
            summary_msg = (
                f"📊 <b>RUN SUMMARY</b> 📊\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⚙️ <b>Mode:</b> PAPER\n"
                f"🎯 <b>New Signals Generated:</b> {len(results)}\n"
                f"⏰ <b>Executed At:</b> {now.strftime('%d %b %Y, %I:%M %p')}"
            )
            send_telegram_alert(summary_msg)
        else:
            st.info("💡 અત્યારે કોઈ નવું સિગ્નલ મળ્યું નથી.")
            
    except Exception as main_err:
        st.error(f"🚨 એરર આવી: {str(main_err)}")
                               
