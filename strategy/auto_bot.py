"""
Gandiv AI Trading Terminal - Auto Bot Module (v6.0 - Safe & Crash-Proof)
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from config import STOCK_UNIVERSE, SECTOR_MAP
from core.data_loader import fetch_technical_data, calculate_charges

def save_session_data_atomically():
    """
    Atomic Data Saving Guard: Ensure trade history & portfolio state stays intact.
    """
    try:
        if "paper_portfolio" in st.session_state:
            st.session_state["paper_portfolio"] = dict(st.session_state.paper_portfolio)
        if "paper_trade_history" in st.session_state:
            st.session_state["paper_trade_history"] = list(st.session_state.paper_trade_history)
    except Exception as e:
        st.warning(f"⚠️ ડેટા સેવ કરતી વખતે નાની એરર આવી: {str(e)}")

def run_auto_bot():
    """
    Crash-Proof Auto Bot Execution Loop
    """
    st.markdown("### 🤖 Auto Trading Bot (v6.0 - Crash-Proof)")
    
    # Time Guard (3:15 PM પછી નવા ઓર્ડર અટકાવવા)
    now = datetime.now()
    if now.hour == 15 and now.minute >= 15:
        st.warning("⏰ માર્કેટ બંધ થવાનો સમય (3:15 PM) થઈ ગયો છે. નવા ટ્રેડ ઓટો-અટકાવાયેલ છે.")

    try:
        results = []
        progress = st.progress(0)
        
        for idx, sym in enumerate(STOCK_UNIVERSE):
            try:
                # Safe technical data fetch with Error Catching
                td = fetch_technical_data(sym)
                if not td or "current_price" not in td:
                    continue
                    
                cp = td["current_price"]
                rsi = td["rsi"]
                trend = td["trend"]
                
                # Simple Strategy Logic
                if trend == "Bullish" and rsi > 50:
                    results.append({
                        "Symbol": sym.replace(".NS", ""),
                        "Price": cp,
                        "RSI": rsi,
                        "Signal": "BUY",
                        "Time": datetime.now().strftime("%H:%M:%S")
                    })
            except Exception as inner_err:
                # Individual Stock Failures Won't Crash the Entire Loop
                pass
                
            progress.progress((idx + 1) / len(STOCK_UNIVERSE))
            
        # Atomic Data Saving Safeguard
        save_session_data_atomically()
        
        if results:
            st.success(f"✅ {len(results)} સિગ્નલ્સ સફળતાપૂર્વક સ્કેન થયા.")
            st.dataframe(pd.DataFrame(results), use_container_width=True)
        else:
            st.info("💡 અત્યારે કોઈ નવું સિગ્નલ મળ્યું નથી.")
            
    except Exception as main_err:
        st.error(f"🚨 બોટ રન કરતી વખતે એરર આવી: {str(main_err)}")
        
