"""
Gandiv AI Trading Terminal — ui/analytics.py

Purpose
-------
The Backtest & Analytics tab: a real UI over backtest/engine.py +
backtest/metrics.py — the FULL PORTFOLIO simulation (Phase K), not a
per-stock return calculator, with every metric your Phase 6 spec asked
for, and an honest "NOT ready for real money" style summary rather
than an inflated headline number.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from config.universe import STOCK_UNIVERSE
from config.trading_config import STARTING_CAPITAL
from backtest.engine import BacktestConfig, run_backtest
from backtest.metrics import calculate_metrics


def render_analytics_tab() -> None:
    st.subheader("📈 Backtest & Analytics")
    st.caption(
        "Full portfolio simulation — one shared ₹ ledger across every symbol, "
        "with the SAME signal engine, risk engine, and charges the paper/live "
        "engine will use. Not a per-stock return estimate."
    )

    with st.form("backtest_form"):
        col1, col2 = st.columns(2)
        with col1:
            default_symbols = STOCK_UNIVERSE[:15]  # a reasonable default subset — full 50 is slower
            symbols = st.multiselect(
                "Stocks to include",
                options=STOCK_UNIVERSE,
                default=default_symbols,
                help="Fewer stocks = faster run. Full universe is supported but will take longer.",
            )
        with col2:
            capital = st.number_input("Starting Capital (₹)", min_value=10000, value=int(STARTING_CAPITAL), step=10000)

        col3, col4 = st.columns(2)
        with col3:
            start_date = st.date_input("Start Date", value=dt.date.today() - dt.timedelta(days=3 * 365))
        with col4:
            end_date = st.date_input("End Date", value=dt.date.today())

        submitted = st.form_submit_button("🚀 Run Backtest", type="primary")

    if not submitted:
        st.info("Configure the backtest above and click **Run Backtest**. Nothing runs automatically.")
        return

    if not symbols:
        st.error("Select at least one stock.")
        return
    if start_date >= end_date:
        st.error("Start date must be before end date.")
        return

    config = BacktestConfig(
        symbols=symbols, start_date=start_date, end_date=end_date, starting_capital=float(capital),
    )

    with st.spinner(f"Simulating {len(symbols)} stocks from {start_date} to {end_date}... this can take a few minutes for a large universe or long period."):
        result = run_backtest(config)

    if result.symbols_skipped:
        st.warning(f"Skipped (insufficient data): {', '.join(s.replace('.NS','') for s in result.symbols_skipped)}")
    for w in result.warnings[:10]:
        st.caption(f"⚠️ {w}")

    portfolio = result.portfolio
    if not portfolio.closed_trades and not portfolio.open_trades:
        st.info("No trades were generated in this period with the current signal/risk settings. Try a longer date range or more symbols.")
        return

    metrics = calculate_metrics(portfolio)

    st.markdown("---")
    st.markdown("#### Results")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Return", f"{metrics.total_return_pct:+.2f}%")
    c2.metric("CAGR", f"{metrics.cagr_pct:+.2f}%")
    c3.metric("Win Rate", f"{metrics.win_rate_pct:.1f}%")
    c4.metric("Total Trades", metrics.total_trades)

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Profit Factor", f"{metrics.profit_factor:.2f}" if metrics.profit_factor != float("inf") else "∞")
    c6.metric("Expectancy / Trade", f"₹{metrics.expectancy:,.0f}")
    c7.metric("Max Drawdown", f"{metrics.max_drawdown_pct:.2f}%")
    c8.metric("Avg Holding Days", f"{metrics.avg_holding_days:.1f}")

    c9, c10, c11, c12 = st.columns(4)
    c9.metric("Sharpe Ratio", f"{metrics.sharpe_ratio:.2f}")
    c10.metric("Sortino Ratio", f"{metrics.sortino_ratio:.2f}")
    c11.metric("Calmar Ratio", f"{metrics.calmar_ratio:.2f}")
    c12.metric("Avg Risk:Reward", f"1:{metrics.avg_risk_reward:.2f}")

    c13, c14, c15, c16 = st.columns(4)
    c13.metric("Avg Win", f"₹{metrics.average_win:,.0f}")
    c14.metric("Avg Loss", f"₹{metrics.average_loss:,.0f}")
    c15.metric("Max Consec. Wins", metrics.max_consecutive_wins)
    c16.metric("Max Consec. Losses", metrics.max_consecutive_losses)

    if metrics.open_positions_at_end > 0:
        st.caption(
            f"ℹ️ {metrics.open_positions_at_end} position(s) still open at the end of the backtest "
            f"(unrealized P&L: ₹{metrics.unrealized_pnl_at_end:,.0f}) — excluded from the win-rate/trade "
            f"stats above, which only count CLOSED trades."
        )

    st.markdown("---")
    st.markdown("#### Equity Curve")
    if portfolio.equity_history:
        eq_df = pd.DataFrame(portfolio.equity_history)
        eq_df["date"] = pd.to_datetime(eq_df["date"])
        st.line_chart(eq_df.set_index("date")["equity"])

    st.markdown("#### Drawdown Curve")
    if metrics.drawdown_curve:
        dd_df = pd.DataFrame(metrics.drawdown_curve)
        dd_df["date"] = pd.to_datetime(dd_df["date"])
        st.area_chart(dd_df.set_index("date")["drawdown_pct"])

    if metrics.yearly_returns_pct:
        st.markdown("#### Yearly Returns")
        st.dataframe(
            pd.DataFrame([{"Year": k, "Return %": v} for k, v in sorted(metrics.yearly_returns_pct.items())]),
            width='stretch', hide_index=True,
        )

    st.markdown("---")
    st.markdown("#### Trade Journal")
    if portfolio.closed_trades:
        journal_rows = [{
            "Symbol": t.symbol.replace(".NS", ""),
            "Sector": t.sector,
            "Qty": t.quantity,
            "Entry": t.entry_price,
            "Entry Date": t.entry_date,
            "Exit": t.exit_price,
            "Exit Date": t.exit_date,
            "Reason": t.exit_reason,
            "Charges": t.charges_total,
            "Net P&L": t.net_pnl,
        } for t in portfolio.closed_trades]
        journal_df = pd.DataFrame(journal_rows)
        st.dataframe(journal_df, width='stretch', hide_index=True)

        csv = journal_df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download Trade Journal (CSV)", data=csv, file_name=f"backtest_{dt.date.today()}.csv", mime="text/csv")
    else:
        st.caption("No closed trades yet.")

    st.markdown("---")
    st.caption(
        "⚠️ This is a PAPER-TRADING research backtest with realistic slippage and statutory "
        "charges applied — it is not a guarantee of future performance, and results here do "
        "not by themselves justify moving to real money. See your project's own out-of-sample "
        "/ walk-forward validation plan before treating any of these numbers as final."
    )
