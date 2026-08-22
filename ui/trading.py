"""
Gandiv AI Trading Terminal — ui/trading.py

Purpose
-------
The Trading tab: view the live paper portfolio (positions, pending
entries, recent trade history) and place MANUAL trades.

Manual vs automated entries — an important distinction
-----------------------------------------------------------
The automated daily cycle (paper/engine.py) follows the strict
COMPLETED-CANDLE + NEXT-CANDLE-EXECUTION rule: a signal from today's
close only ever fills at tomorrow's open. That rule exists to keep
the backtest and the automated paper engine perfectly comparable —
neither one is allowed to act on information it wouldn't really have
had yet.

A MANUAL trade placed here is different in kind: you are looking at
a live price right now and choosing to act on it immediately — there
is no "tomorrow's open" to wait for, because a human is the one
deciding, in real time. This still goes through the SAME risk engine
(core/risk_engine.evaluate_trade) and the SAME Portfolio ledger — it
is not a way to bypass risk limits, only a different, immediate
execution path. This distinction is stated here, not hidden, per
your Phase 23 requirement that manual trades save to the same
persistent storage as automated ones.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from config.universe import STOCK_UNIVERSE, get_sector
from config.trading_config import INDEX_SYMBOL
from core.data_loader import get_completed_ohlcv, get_live_price
from core.risk_engine import evaluate_trade
from strategy.unified_strategy import generate_signal
from storage.repository import PortfolioRepository


def render_trading_tab() -> None:
    st.subheader("💼 Trading")

    repository = PortfolioRepository()
    portfolio = repository.load()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cash", f"₹{portfolio.cash:,.0f}")
    c2.metric("Total Equity", f"₹{portfolio.total_equity:,.0f}")
    c3.metric("Total Return", f"{portfolio.total_return_pct:+.2f}%")
    c4.metric("Open Positions", len(portfolio.open_trades))

    st.markdown("---")

    st.markdown("#### 📂 Open Positions")
    if portfolio.open_trades:
        rows = [{
            "Symbol": t.symbol.replace(".NS", ""), "Sector": t.sector, "Qty": t.quantity,
            "Entry": t.entry_price, "Current": t.current_price,
            "Unrealized P&L": round(t.unrealized_pnl, 2),
            "SL": t.stop_loss, "Target": t.target, "Entry Date": t.entry_date,
        } for t in portfolio.open_trades]
        df = pd.DataFrame(rows)
        st.dataframe(df, width='stretch', hide_index=True)

        st.markdown("##### Close a Position Manually")
        symbol_to_close = st.selectbox(
            "Select position", options=[t.symbol for t in portfolio.open_trades],
            format_func=lambda s: s.replace(".NS", ""), key="close_select",
        )
        if st.button("🔴 Close at Current Market Price", key="close_btn"):
            live_price = get_live_price(symbol_to_close)
            if live_price is None:
                st.error(f"Could not fetch a live price for {symbol_to_close} — try again in a moment.")
            else:
                closed = portfolio.close_position(symbol_to_close, live_price, dt.date.today(), "MANUAL")
                repository.save(portfolio)
                st.success(f"Closed {symbol_to_close.replace('.NS','')} at ₹{closed.exit_price:.2f} — net P&L ₹{closed.net_pnl:,.0f}")
                st.rerun()
    else:
        st.caption("No open positions.")

    st.markdown("---")

    st.markdown("#### ⏳ Pending Entries (queued for next trading day's open)")
    if portfolio.pending_entries:
        pending_rows = [{
            "Symbol": e.symbol.replace(".NS", ""), "Sector": e.sector, "Qty": e.quantity,
            "SL": e.stop_loss, "Target": e.target, "Decided On": e.decided_on,
        } for e in portfolio.pending_entries]
        st.dataframe(pd.DataFrame(pending_rows), width='stretch', hide_index=True)
    else:
        st.caption("No pending entries. New ones are queued by the daily paper-trading cycle (Risk Manager tab) or a manual trade below.")

    st.markdown("---")

    st.markdown("#### ➕ Manual Trade")
    st.caption(
        "Executes IMMEDIATELY at the current live price (not next-candle-open — see this tab's note above). "
        "Still passes through the same risk engine and position-sizing caps as an automated signal."
    )
    held = {t.symbol for t in portfolio.open_trades} | {e.symbol for e in portfolio.pending_entries}
    available = [s for s in STOCK_UNIVERSE if s not in held]
    manual_symbol = st.selectbox("Symbol", options=available, format_func=lambda s: s.replace(".NS", ""), key="manual_symbol")

    if st.button("🔍 Check Signal & Risk", key="check_signal_btn"):
        with st.spinner("Fetching data and evaluating..."):
            df = get_completed_ohlcv(manual_symbol, period="1y", interval="1d")
            index_df = get_completed_ohlcv(INDEX_SYMBOL, period="1y", interval="1d")
            live_price = get_live_price(manual_symbol)

        if df is None or live_price is None:
            st.error("Could not fetch data for this symbol right now.")
        else:
            signal = generate_signal(manual_symbol, df, index_df)
            st.write(f"**Signal:** {signal.signal} (score={signal.score}) — live price: ₹{live_price:.2f}")
            st.json(signal.component_scores)

            sector = get_sector(manual_symbol)
            risk_state = portfolio.to_risk_state()
            decision = evaluate_trade(manual_symbol, sector, live_price, signal.suggested_sl, signal.suggested_target, risk_state)

            st.session_state["manual_decision"] = decision
            st.session_state["manual_live_price"] = live_price
            st.session_state["manual_symbol_checked"] = manual_symbol

            if decision.approved:
                st.success(f"Risk engine APPROVES: {decision.quantity} shares, risk ₹{decision.risk_amount:,.0f} (SL ₹{decision.stop_loss:.2f}, Target ₹{decision.target:.2f})")
                if decision.capped_by:
                    st.caption(f"Size reduced by: {', '.join(decision.capped_by)}")
            else:
                st.warning(f"Risk engine REJECTS this trade: {decision.reason}")

    decision = st.session_state.get("manual_decision")
    if decision is not None and decision.approved and st.session_state.get("manual_symbol_checked") == manual_symbol:
        if st.button("✅ Execute This Trade Now", key="execute_manual_btn", type="primary"):
            try:
                trade = portfolio.open_position(
                    symbol=manual_symbol, sector=get_sector(manual_symbol), quantity=decision.quantity,
                    reference_entry_price=st.session_state["manual_live_price"],
                    stop_loss=decision.stop_loss, target=decision.target, entry_date=dt.date.today(),
                )
                repository.save(portfolio)
                st.success(f"Opened {trade.quantity} shares of {manual_symbol.replace('.NS','')} @ ₹{trade.entry_price:.2f}")
                del st.session_state["manual_decision"]
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    st.markdown("---")

    st.markdown("#### 📜 Recent Closed Trades")
    if portfolio.closed_trades:
        recent = portfolio.closed_trades[-10:][::-1]
        rows = [{
            "Symbol": t.symbol.replace(".NS", ""), "Qty": t.quantity, "Entry": t.entry_price,
            "Exit": t.exit_price, "Reason": t.exit_reason, "Net P&L": t.net_pnl, "Exit Date": t.exit_date,
        } for t in recent]
        st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)
    else:
        st.caption("No closed trades yet.")
