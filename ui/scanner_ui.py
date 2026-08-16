"""
Gandiv AI Trading Terminal - Scanners UI Tab (v5.1 Quant Safe)
"""

import streamlit as st
import pandas as pd
from config import STOCK_UNIVERSE
from core.data_loader import fetch_technical_data


def get_val(data, keys, default=None):
    for k in keys:
        try:
            if isinstance(data, dict) and k in data:
                return data[k]
            elif hasattr(data, k):
                return getattr(data, k)
            elif hasattr(data, '__getitem__'):
                val = data[k]
                if val is not None:
                    return val
        except Exception:
            pass
    return default


def render_scanners_tab():
    st.markdown("### 🔍 Real-Time AI Stock Scanners")
    st.caption("v5.1 Multi-Factor Confluence & Regime Engine")

    if st.button("🔎 Scan Universe Now", key="scan_universe_main"):
        results = []
        prog = st.progress(0)
        total = max(len(STOCK_UNIVERSE), 1)

        for idx, sym in enumerate(STOCK_UNIVERSE):
            try:
                td = fetch_technical_data(sym)
                if td is not None:
                    score = get_val(td, ["score", "Quant Score", "Score"], 0)
                    regime = get_val(td, ["Regime", "regime", "Market Regime"], "UNKNOWN")
                    trend = get_val(td, ["Trend", "trend"], "Neutral")
                    price = get_val(td, ["current_price", "Price", "close", "Close"], 0.0)
                    rsi = get_val(td, ["rsi", "RSI"], 0.0)
                    atr = get_val(td, ["atr", "ATR"], 0.0)
                    reason = get_val(td, ["Reason", "reason", "AI Analysis"], "Technical Analysis Complete")

                    try:
                        score = float(score)
                    except Exception:
                        score = 0.0

                    if score >= 80 and regime != "SIDEWAYS":
                        signal = "🔥🔥 STRONG BUY"
                    elif score >= 65 and regime != "SIDEWAYS":
                        signal = "✅ BUY"
                    elif score >= 50:
                        signal = "👀 WATCHLIST"
                    else:
                        signal = "⚪ NEUTRAL"

                    results.append({
                        "Symbol": sym.replace(".NS", ""),
                        "Price (₹)": round(float(price), 2) if price else 0.0,
                        "Trend": str(trend),
                        "Market Regime": str(regime),
                        "Quant Score": f"{int(score)}/100",
                        "Signal": signal,
                        "RSI": round(float(rsi), 1) if rsi else 0.0,
                        "ATR (₹)": round(float(atr), 2) if atr else 0.0,
                        "AI Analysis": str(reason)
                    })
            except Exception:
                pass
            prog.progress((idx + 1) / total)

        if results:
            try:
                df = pd.DataFrame(results)
                if "Quant Score" in df.columns:
                    df["_sort_key"] = df["Quant Score"].str.extract(r"(\d+)").astype(float)
                    df = df.sort_values(by="_sort_key", ascending=False).drop(columns=["_sort_key"])
                st.success(f"✅ {len(df)} સ્ટોક્સ સ્કેન પૂર્ણ!")
                st.dataframe(df, use_container_width=True)
            except Exception as e:
                st.error(f"⚠️ Display error: {e}")
                st.dataframe(pd.DataFrame(results), use_container_width=True)
        else:
            st.warning("⚠️ કોઈ ડેટા મળ્યો નથી. ફરી પ્રયાસ કરો.")
