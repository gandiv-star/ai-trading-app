"""
Gandiv AI Trading Terminal - Scanners UI Tab (v5.0 Quant Safe)
"""

import streamlit as st
import pandas as pd
from config import STOCK_UNIVERSE
from core.data_loader import fetch_technical_data

def render_scanners_tab():
    st.markdown("### 🔍 Real-Time AI Stock Scanners")
    st.caption("v5.0 Multi-Factor Confluence & Regime Engine")

    if st.button("🔎 Scan Universe Now", key="scan_universe_main"):
        results = []
        prog = st.progress(0)

        for idx, sym in enumerate(STOCK_UNIVERSE):
            try:
                td = fetch_technical_data(sym)
                if td:
                    score = td.get("score", 0)
                    regime = td.get("Regime", td.get("regime", "UNKNOWN"))
                    trend = td.get("Trend", td.get("trend", "Neutral"))
                    price = td.get("current_price", td.get("Price", 0.0))
                    rsi = td.get("rsi", td.get("RSI", 0.0))
                    atr = td.get("atr", td.get("ATR", 0.0))
                    reason = td.get("Reason", "Technical Analysis Passed")

                    if score >= 80 and regime != "SIDEWAYS":
                        signal = "🔥🔥 STRONG BUY"
                    elif score >= 65 and regime != "SIDEWAYS":
                        signal = "✅ BUY"
                    elif score >= 50:
                        signal = "👀 WATCHLIST"
                    else:
                        signal = "⚪ NEUTRAL"

                    results.append({
                        "Symbol": td.get("Symbol", sym.replace(".NS", "")),
                        "Price (₹)": price,
                        "Trend": trend,
                        "Market Regime": regime,
                        "Quant Score": f"{score}/100",
                        "Signal": signal,
                        "RSI": rsi,
                        "ATR (₹)": atr,
                        "AI Analysis": reason
                    })
            except Exception:
                pass
            prog.progress((idx + 1) / len(STOCK_UNIVERSE))

        if results:
            df = pd.DataFrame(results)
            df = df.sort_values(by="Quant Score", ascending=False)
            st.success(f"✅ {len(df)} સ્ટોક્સ સ્કેન પૂર્ણ!")
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("⚠️ કોઈ ડેટા મળ્યો નથી. ફરી પ્રયાસ કરો.")
            
