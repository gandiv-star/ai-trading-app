"""
Gandiv AI Trading Terminal — ui/dashboard.py

Purpose
-------
The Dashboard tab: a read-only overview of how the system is
currently configured — capital, risk limits, the stock universe and
its sector breakdown, the market holiday calendar, and whether
secrets (Telegram/Gemini) are configured. No trading state lives here
yet (that needs Phase J's paper engine + Phase L's storage layer) —
this tab is purely "what would the system do, given current config".
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from config.settings import APP_NAME, APP_VERSION, secrets_health_check
from config.trading_config import (
    STARTING_CAPITAL,
    TRADING_MODE,
    MIN_SIGNAL_SCORE,
    ATR_SL_MULTIPLIER,
    ATR_TARGET_MULTIPLIER,
    MAX_HOLDING_DAYS,
    NSE_HOLIDAYS,
)
from config.risk import (
    RISK_PER_TRADE_PCT,
    MAX_OPEN_POSITIONS,
    SINGLE_STOCK_CAP_PCT,
    MAX_PORTFOLIO_EXPOSURE_PCT,
    DAILY_LOSS_LIMIT_PCT,
    WEEKLY_LOSS_LIMIT_PCT,
    MAX_DRAWDOWN_PCT,
    MAX_CONSECUTIVE_LOSSES,
    SECTOR_CAPS,
)
from config.universe import STOCK_UNIVERSE, get_sector_grouping


def render_dashboard_tab() -> None:
    st.subheader(f"{APP_NAME} — v{APP_VERSION}")
    st.caption(f"Mode: **{TRADING_MODE}** — real-money execution is not implemented; this is a paper-trading research system.")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Starting Capital", f"₹{STARTING_CAPITAL:,.0f}")
    col2.metric("Risk per Trade", f"{RISK_PER_TRADE_PCT}%")
    col3.metric("Max Open Positions", MAX_OPEN_POSITIONS)
    col4.metric("Min Signal Score", MIN_SIGNAL_SCORE)

    st.markdown("---")

    st.markdown("#### 🛡️ Risk Limits")
    risk_table = pd.DataFrame([
        {"Limit": "Single-stock cap", "Value": f"{SINGLE_STOCK_CAP_PCT}% of equity"},
        {"Limit": "Max portfolio exposure", "Value": f"{MAX_PORTFOLIO_EXPOSURE_PCT}% of equity"},
        {"Limit": "Daily loss circuit breaker", "Value": f"{DAILY_LOSS_LIMIT_PCT}% of equity"},
        {"Limit": "Weekly loss circuit breaker", "Value": f"{WEEKLY_LOSS_LIMIT_PCT}% of equity"},
        {"Limit": "Max drawdown circuit breaker", "Value": f"{MAX_DRAWDOWN_PCT}% of equity"},
        {"Limit": "Consecutive-loss circuit breaker", "Value": f"{MAX_CONSECUTIVE_LOSSES} losses"},
        {"Limit": "Stop-Loss distance", "Value": f"{ATR_SL_MULTIPLIER} x ATR"},
        {"Limit": "Target distance", "Value": f"{ATR_TARGET_MULTIPLIER} x ATR"},
        {"Limit": "Max holding period", "Value": f"{MAX_HOLDING_DAYS} trading days"},
    ])
    st.dataframe(risk_table, width='stretch', hide_index=True)

    st.markdown("#### 🏷️ Sector Exposure Caps")
    sector_caps_table = pd.DataFrame(
        [{"Sector": k, "Cap (% of equity)": v} for k, v in sorted(SECTOR_CAPS.items())]
    )
    st.dataframe(sector_caps_table, width='stretch', hide_index=True)

    st.markdown("---")

    st.markdown("#### 📈 Stock Universe")
    grouping = get_sector_grouping()
    st.caption(f"{len(STOCK_UNIVERSE)} stocks across {len(grouping)} sectors")
    sector_counts = pd.DataFrame(
        [{"Sector": k, "Stocks": len(v)} for k, v in sorted(grouping.items(), key=lambda kv: -len(kv[1]))]
    )
    c1, c2 = st.columns([1, 2])
    with c1:
        st.dataframe(sector_counts, width='stretch', hide_index=True)
    with c2:
        st.bar_chart(sector_counts.set_index("Sector"))

    with st.expander("View full stock list by sector"):
        for sector, symbols in sorted(grouping.items()):
            st.markdown(f"**{sector}** ({len(symbols)}): {', '.join(s.replace('.NS','') for s in symbols)}")

    st.markdown("---")

    st.markdown("#### 📅 Upcoming NSE Holidays")
    today = dt.date.today()
    upcoming = sorted(
        d for year_holidays in NSE_HOLIDAYS.values() for d in year_holidays if d >= today
    )[:6]
    if upcoming:
        st.dataframe(
            pd.DataFrame({"Date": [d.strftime("%d %b %Y (%a)") for d in upcoming]}),
            width='stretch', hide_index=True,
        )
    else:
        st.caption("No holiday data available beyond the configured calendar years.")

    st.markdown("---")

    st.markdown("#### 🔐 Secrets Status")
    st.caption("Booleans only — actual token/key values are never displayed.")
    health = secrets_health_check()
    cols = st.columns(len(health))
    for col, (key, ok) in zip(cols, health.items()):
        col.metric(key.replace("_", " ").title(), "✅ Set" if ok else "⚠️ Missing")
