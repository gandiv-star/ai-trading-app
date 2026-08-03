"""
Gandiv AI Trading Terminal - Auto Bot Module (v5.0 Pro Engine)
Features: Market Regime Filter, Weighted 100-Point Confluence Score & AI Confidence Index
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import yfinance as yf
import requests
from config import STOCK_UNIVERSE
from core.data_loader import calculate_confluence_score, calculate_atr

# Safely import Telegram credentials
try:
    from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
except ImportError:
    import os
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

def send_telegram_alert(message):
    try:
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
            requests.post(url, json=payload, timeout=5)
    except Exception:
        pass

def save_session_data_atomically():
    try:
        if "paper_portfolio" in st.session_state:
            st.session_state["paper_portfolio"] = dict(st.session_state.paper_portfolio)
        if "paper_trade_history" in st.session_state:
            st.session_state["paper_trade_history"] = list(st.session_state.paper_trade_history)
    except Exception:
        pass

def execute_auto_bot(max_pos=25, cap_per_trade=10000, min_score=75, target_pct=4.0, sl_pct=2.5):
    st.markdown("### 🤖 Auto Trading Bot Engine (v5.0 - Pro Quant System)")
    st.caption("⚡ Powered by Market Regime Detection & 100-Point Confluence Scoring")

    now = datetime.now()
    if now.hour == 15 and now.minute >= 15:
        st.warning("⏰ માર્કેટ બંધ થવાનો સમય (3:15 PM) થઈ ગયો છે. નવા ઓટો-ટ્રેડ અટકાવાયેલ છે.")
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

                # V5.0 Pro Quant Scoring Engine
                score, confidence_reasons, regime, atr_val = calculate_confluence_score(df)
                current_price = float(df["Close"].iloc[-1])

                # SKIP Sideways Market / Low Confidence Signals (< min_score)
                if score >= min_score and regime != "SIDEWAYS":
                    atr_sl = current_price - (1.5 * atr_val) if atr_val > 0 else current_price * (1 - sl_pct / 100)
                    atr_tgt = current_price + (3.0 * atr_val) if atr_val > 0 else current_price * (1 + target_pct / 100)
                    
                    risk_per_share = max(current_price - atr_sl, 1.0)
                    max_risk_allowed = cap_per_trade * 0.02
                    final_qty = max(int(max_risk_allowed / risk_per_share), 1)
                    
                    stock_name = sym.replace(".NS", "")
                    
                    confidence_badge = "🔥🔥 [STRONG BUY]" if score >= 88 else "✅ [BUY]"
                    
                    results.append({
                        "Symbol": stock_name,
                        "Price (₹)": round(current_price, 2),
                        "AI Score": f"{score}/100",
                        "Regime": regime,
                        "Signal Quality": confidence_badge,
                        "Qty": final_qty,
                        "Dynamic SL (₹)": round(atr_sl, 2),
                        "Target (₹)": round(atr_tgt, 2),
                        "AI Reasons": confidence_reasons
                    })

                    # Telegram Notification
                    msg = (
                        f"🚀 <b>GANDIV QUANT ALERT (v5.0)</b> 🚀\n\n"
                        f"📌 <b>Stock:</b> {stock_name}\n"
                        f"🧠 <b>AI Score:</b> {score}/100 ({confidence_badge})\n"
                        f"🌐 <b>Regime:</b> {regime}\n"
                        f"💰 <b>Buy Price:</b> ₹{current_price:.2f}\n"
                        f"📦 <b>Qty:</b> {final_qty}\n"
                        f"🛑 <b>ATR Stop Loss:</b> ₹{atr_sl:.2f}\n"
                        f"🎯 <b>Target:</b> ₹{atr_tgt:.2f}\n"
                        f"💡 <b>Reasons:</b> {confidence_reasons}\n"
                        f"⏰ <b>Time:</b> {now.strftime('%I:%M %p')}"
                    )
                    send_telegram_alert(msg)

            except Exception:
                pass
                
            progress.progress((idx + 1) / len(STOCK_UNIVERSE))
            
        save_session_data_atomically()
        
        if results:
            st.success(f"✅ {len(results)} હાઇ-ક્વોલિટી પ્રો કન્ફર્મ્ડ સિગ્નલ્સ સ્કેન થયા!")
            st.dataframe(pd.DataFrame(results), use_container_width=True)
            
            summary_msg = (
                f"📊 <b>V5.0 QUANT RUN SUMMARY</b> 📊\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 <b>High-Score Signals:</b> {len(results)}\n"
                f"⚙️ <b>Min Score Threshold:</b> {min_score}/100\n"
                f"⏰ <b>Executed At:</b> {now.strftime('%d %b %Y, %I:%M %p')}"
            )
            send_telegram_alert(summary_msg)
        else:
            st.info("💡 અત્યારે માર્કેટ ફિલ્ટર અને 75+ Score સેટિંગ્સ મુજબ કોઈ સેફ સિગ્નલ મળ્યું નથી.")
            
    except Exception as main_err:
        st.error(f"🚨 બોટ એરર: {str(main_err)}")
                    
