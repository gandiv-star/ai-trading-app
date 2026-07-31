"""
Gandiv AI Trading Terminal - Stock Scanners UI Module (v6.0)
"""

import streamlit as st
import pandas as pd
from config import STOCK_UNIVERSE, SECTOR_MAP
from core.data_loader import fetch_technical_data

def render_scanners_tab():
    st.markdown("### 🔍 Real-Time AI Stock Scanners")
    
    scan_btn = st.button("🔎 Scan Universe Now", key="v6_scan_universe_btn")
    
    if scan_btn:
        results = []
        progress = st.progress(0)
        
        for idx, sym in enumerate(STOCK_UNIVERSE):
            td = fetch_technical_data(sym)
            if td:
                score = 50
                if td["trend"] == "Bullish": score += 20
                if 45 <= td["rsi"] <= 65: score += 20
                elif td["rsi"] < 30: score += 5
                if td["current_price"] > td["ma50"]: score += 10
                
                results.append({
                    "Stock": sym.replace(".NS", ""),
                    "Sector": SECTOR_MAP.get(sym, "Other"),
                    "Price (₹)": td["current_price"],
                    "RSI": td["rsi"],
                    "Trend": td["trend"],
                    "AI Score": score
                })
            progress.progress((idx + 1) / len(STOCK_UNIVERSE))
            
        if results:
            df_res = pd.DataFrame(results)
            df_res = df_res.sort_values(by="AI Score", ascending=False)
            st.dataframe(df_res, use_container_width=True)
            st.success(f"✅ કુલ {len(results)} સ્ટોક્સનું સ્કેનિંગ પૂર્ણ થયું.")
        else:
            st.warning("સ્કેન દરમિયાન કોઈ સ્ટોકની વિગતો મળી નથી.")
          
