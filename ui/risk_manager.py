"""
Gandiv AI Trading Terminal — ui/risk_manager.py

Purpose
-------
The Risk Manager tab: shows how much of each risk limit is currently
USED (not just what the limits ARE — that's the Dashboard tab), and
is where the automated daily paper-trading cycle (paper/engine.py) is
manually triggered from the UI — the direct fix for the old app's
execute_auto_bot() signature-mismatch crash (Phase 1 audit finding).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config.universe import STOCK_UNIVERSE
from config.risk import (
    SINGLE_STOCK_CAP_PCT, MAX_PORTFOLIO_EXPOSURE_PCT, MAX_OPEN_POSITIONS,
    DAILY_LOSS_LIMIT_PCT, WEEKLY_LOSS_LIMIT_PCT, MAX_DRAWDOWN_PCT,
    MAX_CONSECUTIVE_LOSSES, get_sector_cap,
)
from storage.repository import PortfolioRepository
from paper.engine import run_daily_cycle


def _utilization_bar(label: str, used_pct: float, limit_pct: float) -> None:
    ratio = min(used_pct / limit_pct, 1.0) if limit_pct > 0 else 0.0
    st.write(f"**{label}**: {used_pct:.1f}% of {limit_pct:.1f}% limit")
    st.progress(ratio)


def render_risk_manager_tab() -> None:
    st.subheader("🛡️ Risk Manager")

    repository = PortfolioRepository()
    portfolio = repository.load()
    equity = portfolio.total_equity

    st.markdown("#### Current Utilization")

    exposure_pct = (portfolio.deployed_value / equity * 100) if equity > 0 else 0.0
    _utilization_bar("Portfolio Exposure", exposure_pct, MAX_PORTFOLIO_EXPOSURE_PCT)

    daily_loss_pct = max(0.0, -portfolio.realized_pnl_today / equity * 100) if equity > 0 else 0.0
    _utilization_bar("Today's Loss vs Daily Limit", daily_loss_pct, DAILY_LOSS_LIMIT_PCT)

    weekly_loss_pct = max(0.0, -portfolio.realized_pnl_this_week / equity * 100) if equity > 0 else 0.0
    _utilization_bar("This Week's Loss vs Weekly Limit", weekly_loss_pct, WEEKLY_LOSS_LIMIT_PCT)

    _utilization_bar("Drawdown vs Circuit Breaker", portfolio.current_drawdown_pct, MAX_DRAWDOWN_PCT)

    c1, c2 = st.columns(2)
    c1.metric("Open Positions", f"{len(portfolio.open_trades)} / {MAX_OPEN_POSITIONS}")
    c2.metric("Consecutive Losses", f"{portfolio.consecutive_losses} / {MAX_CONSECUTIVE_LOSSES}")

    if portfolio.open_trades:
        st.markdown("##### Per-Position / Per-Sector Exposure")
        sector_totals: dict = {}
        rows = []
        for t in portfolio.open_trades:
            pct = (t.current_value / equity * 100) if equity > 0 else 0.0
            rows.append({"Symbol": t.symbol.replace(".NS", ""), "Sector": t.sector,
                         "Value": round(t.current_value, 0), "% of Equity": round(pct, 2),
                         "Single-Stock Cap": f"{SINGLE_STOCK_CAP_PCT}%"})
            sector_totals[t.sector] = sector_totals.get(t.sector, 0.0) + t.current_value
        st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)

        sector_rows = [{
            "Sector": sec, "Value": round(val, 0),
            "% of Equity": round(val / equity * 100, 2) if equity > 0 else 0,
            "Sector Cap": f"{get_sector_cap(sec)}%",
        } for sec, val in sector_totals.items()]
        st.dataframe(pd.DataFrame(sector_rows), width='stretch', hide_index=True)

    st.markdown("---")
    st.markdown("#### 🤖 Automated Daily Cycle")
    st.caption(
        "Runs the same signal engine, risk engine, and exit rules as the backtester — "
        "fills yesterday's queued entries at today's open, checks exits, and queues new signals for tomorrow. "
        "Safe to click more than once: a duplicate run on the same date is automatically refused."
    )

    scan_universe = st.multiselect(
        "Universe to scan for new signals", options=STOCK_UNIVERSE,
        default=STOCK_UNIVERSE[:20], key="risk_mgr_universe",
    )

    if st.button("🚀 Run Paper Trading Cycle Now", type="primary"):
        with st.spinner("Running daily cycle..."):
            result = run_daily_cycle(symbols=scan_universe, repository=repository)

        if not result.ran:
            st.info(result.reason)
        else:
            st.success(result.reason)
            if result.entries_filled:
                st.write(f"✅ Entries filled: {', '.join(s.replace('.NS','') for s in result.entries_filled)}")
            if result.exits_triggered:
                st.write(f"🔴 Exits triggered: {', '.join(result.exits_triggered)}")
            if result.new_signals_queued:
                st.write(f"⏳ New signals queued for tomorrow: {', '.join(result.new_signals_queued)}")
            if not (result.entries_filled or result.exits_triggered or result.new_signals_queued):
                st.caption("No changes today — no entries filled, no exits, no new signals.")
            if result.warnings:
                with st.expander(f"{len(result.warnings)} warning(s)"):
                    for w in result.warnings:
                        st.caption(f"⚠️ {w}")
        st.rerun()
