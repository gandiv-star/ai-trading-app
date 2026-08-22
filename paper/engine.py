"""
Gandiv AI Trading Terminal — paper/engine.py

Purpose
-------
The LIVE side of your Phase 3 diagram:

    ONE DATA ENGINE -> ONE INDICATOR ENGINE -> ONE STRATEGY ENGINE
                                                       |
                                    ------------------------------------
                                    |                |                |
                                BACKTEST          PAPER  <- (this file)  FUTURE LIVE

This is meant to be called ONCE PER TRADING DAY — by a GitHub Actions
cron job after market close, or by a manual "Run Paper Trading Cycle"
button in the Streamlit app. It calls the EXACT SAME functions the
backtester uses:
  * strategy.unified_strategy.generate_signal()
  * core.risk_engine.evaluate_trade()
  * backtest.engine.check_exit_for_day() / check_time_exit()
There is no second copy of signal, risk, or exit logic here.

Because this runs as a separate process each day (unlike the
backtester's single continuous loop), pending entries and the
"have I already processed today" guard are PERSISTED on the Portfolio
itself (core/portfolio.py's pending_entries / last_processed_date
fields) via storage/repository.py — see that module's docstring for
why this file never touches the filesystem directly.

One daily cycle does, in order
----------------------------------
  1. Refuse to run twice on the same date (duplicate-execution guard —
     your Phase 10 concern, and the audit's "no duplicate trades" rule)
  2. Fill any pending entries from YESTERDAY's signals, at TODAY's open
  3. Check exits for every open position, using TODAY's completed candle
  4. Mark remaining positions to market, record an equity snapshot
  5. Generate fresh signals from TODAY's completed data, risk-check
     them, and queue approved ones as tomorrow's pending entries
  6. Persist the updated portfolio
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from config.trading_config import INDEX_SYMBOL, is_trading_day
from config.universe import get_sector
from core.data_loader import get_completed_ohlcv
from core.portfolio import Portfolio, PendingEntry
from core.risk_engine import evaluate_trade
from strategy.unified_strategy import generate_signal
from backtest.engine import check_exit_for_day, check_time_exit
from storage.repository import PortfolioRepository
from notifications.telegram import trade_entry_alert, trade_exit_alert, circuit_breaker_alert, daily_summary_alert

logger = logging.getLogger(__name__)


@dataclass
class DailyCycleResult:
    ran: bool
    reason: str
    portfolio: Optional[Portfolio] = None
    entries_filled: List[str] = field(default_factory=list)
    exits_triggered: List[str] = field(default_factory=list)
    new_signals_queued: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def run_daily_cycle(
    symbols: List[str],
    repository: Optional[PortfolioRepository] = None,
    index_symbol: str = INDEX_SYMBOL,
    as_of: Optional[dt.date] = None,
) -> DailyCycleResult:
    """
    THE single entry point — safe to call from a GitHub Actions
    workflow, a Streamlit button, or a test. Loads the persisted
    portfolio, processes one trading day, saves it back, and returns
    a summary. Never raises for ordinary "nothing to do" conditions
    (not a trading day, already processed, no signals) — those are
    reported in the result, not exceptions.
    """
    repository = repository or PortfolioRepository()
    today = as_of or dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).date()

    if not is_trading_day(today):
        return DailyCycleResult(ran=False, reason=f"{today} is not an NSE trading day (weekend/holiday).")

    portfolio = repository.load()

    if portfolio.last_processed_date == today:
        return DailyCycleResult(
            ran=False,
            reason=f"Already processed {today} — refusing to run twice (duplicate-execution guard).",
            portfolio=portfolio,
        )

    warnings: List[str] = []
    entries_filled: List[str] = []
    exits_triggered: List[str] = []
    new_signals_queued: List[str] = []

    portfolio.reset_daily_counters()
    iso_week = today.isocalendar()[1]
    last_week = portfolio.last_processed_date.isocalendar()[1] if portfolio.last_processed_date else None
    if last_week is not None and iso_week != last_week:
        portfolio.reset_weekly_counters()

    # --- STEP 1: fill pending entries from yesterday's signals, at TODAY's open ---
    still_pending: List[PendingEntry] = []
    for entry in portfolio.pending_entries:
        df = get_completed_ohlcv(entry.symbol, period="5d", interval="1d")
        if df is None or df.index[-1].date() != today:
            warnings.append(f"{entry.symbol}: no fresh data for {today} yet — entry stays pending.")
            still_pending.append(entry)
            continue
        today_open = float(df.iloc[-1]["Open"])
        try:
            portfolio.open_position(
                symbol=entry.symbol, sector=entry.sector, quantity=entry.quantity,
                reference_entry_price=today_open, stop_loss=entry.stop_loss,
                target=entry.target, entry_date=today,
            )
            entries_filled.append(entry.symbol)
            trade_entry_alert(entry.symbol, entry.quantity, portfolio.get_position(entry.symbol).entry_price,
                              entry.stop_loss, entry.target, score=entry.signal_score)
        except ValueError as exc:
            warnings.append(f"{entry.symbol}: entry skipped — {exc}")
    portfolio.pending_entries = still_pending

    # --- STEP 2: check exits for every open position, using TODAY's completed candle ---
    for trade in list(portfolio.open_trades):
        df = get_completed_ohlcv(trade.symbol, period="5d", interval="1d")
        if df is None or df.index[-1].date() != today:
            warnings.append(f"{trade.symbol}: no fresh data for {today} — cannot check exit today.")
            continue
        day_row = df.iloc[-1]

        exit_info = check_exit_for_day(trade, day_row)
        if exit_info is None:
            exit_info = check_time_exit(trade, today, float(day_row["Close"]))

        if exit_info is not None:
            exit_price, exit_reason = exit_info
            closed_trade_qty = trade.quantity
            portfolio.close_position(trade.symbol, exit_price, today, exit_reason)
            exits_triggered.append(f"{trade.symbol} ({exit_reason} @ {exit_price:.2f})")
            closed = portfolio.closed_trades[-1]
            trade_exit_alert(trade.symbol, closed_trade_qty, closed.exit_price, exit_reason, closed.net_pnl)

    # --- STEP 3: mark remaining positions to market, snapshot equity ---
    today_closes = {}
    for trade in portfolio.open_trades:
        df = get_completed_ohlcv(trade.symbol, period="5d", interval="1d")
        if df is not None and df.index[-1].date() == today:
            today_closes[trade.symbol] = float(df.iloc[-1]["Close"])
    portfolio.mark_to_market(today_closes)
    portfolio.record_equity_snapshot(today)

    # --- STEP 4: generate new signals from today's completed data, queue for tomorrow ---
    index_df = get_completed_ohlcv(index_symbol, period="1y", interval="1d")
    if index_df is None:
        warnings.append(f"Could not fetch index data ({index_symbol}) — market regime/relative strength neutral today.")

    held_or_pending = {t.symbol for t in portfolio.open_trades} | {e.symbol for e in portfolio.pending_entries}
    for symbol in symbols:
        if symbol in held_or_pending:
            continue
        df = get_completed_ohlcv(symbol, period="1y", interval="1d")
        if df is None:
            warnings.append(f"{symbol}: no data available — skipped for signal generation today.")
            continue

        try:
            signal = generate_signal(symbol, df, index_df)
        except ValueError as exc:
            warnings.append(f"{symbol}: signal generation failed — {exc}")
            continue

        if signal.signal != "BUY":
            continue

        sector = get_sector(symbol)
        risk_state = portfolio.to_risk_state()
        decision = evaluate_trade(
            symbol, sector, signal.reference_close, signal.suggested_sl,
            signal.suggested_target, risk_state,
            now=dt.datetime.combine(today, dt.time(15, 30)),
        )
        if decision.approved:
            portfolio.pending_entries.append(PendingEntry(
                symbol=symbol, sector=sector, quantity=decision.quantity,
                stop_loss=decision.stop_loss, target=decision.target, decided_on=today,
                signal_score=signal.score,
            ))
            new_signals_queued.append(f"{symbol} (qty={decision.quantity}, score={signal.score})")
        elif "CIRCUIT BREAKER" in decision.reason:
            circuit_breaker_alert(decision.reason)

    # --- STEP 5: mark today as processed, persist ---
    portfolio.last_processed_date = today
    repository.save(portfolio)

    closed_today_count = sum(1 for t in portfolio.closed_trades if t.exit_date == today)
    daily_summary_alert(
        equity=portfolio.total_equity,
        pnl_today=portfolio.realized_pnl_today,
        open_positions=len(portfolio.open_trades),
        closed_today=closed_today_count,
        win_rate_pct=portfolio.win_rate_pct,
    )

    return DailyCycleResult(
        ran=True,
        reason=f"Processed {today} successfully.",
        portfolio=portfolio,
        entries_filled=entries_filled,
        exits_triggered=exits_triggered,
        new_signals_queued=new_signals_queued,
        warnings=warnings,
    )
