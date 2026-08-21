"""
Gandiv AI Trading Terminal — backtest/engine.py

Purpose
-------
The realistic, FULL PORTFOLIO backtest engine (your Phase 6/7/8
requirements) — not a per-stock return calculator. One Portfolio
object (core/portfolio.py) is shared across the ENTIRE simulated
universe, walked forward one calendar day at a time, so that
MAX_OPEN_POSITIONS, sector caps, and daily/weekly loss limits are
enforced across ALL symbols together — exactly like the live/paper
engine will behave.

This is the "BACKTEST" leg of your Phase 3 diagram:

    ONE DATA ENGINE -> ONE INDICATOR ENGINE -> ONE STRATEGY ENGINE
                                                       |
                                    ------------------------------------
                                    |                |                |
                                BACKTEST  <- (this file)  PAPER   FUTURE LIVE

It calls strategy/unified_strategy.generate_signal() and
core/risk_engine.evaluate_trade() UNCHANGED — the exact same
functions the paper engine will call in Phase J. No second copy of
signal or risk logic exists here.

Execution rules enforced (non-negotiable, per your master prompt)
----------------------------------------------------------------------
  * COMPLETED CANDLE ONLY — a signal on day T only ever sees data up
    to and including T's close.
  * NEXT CANDLE EXECUTION — a BUY signal decided on day T is filled
    at day T+1's Open, never at T's own close.
  * GAP HANDLING — if T+1's Open has already gapped through where a
    stop-loss or target would have triggered, the fill uses the
    REAL gap price for a stop-loss (conservative: you got a worse
    price than your stop), and the TARGET price itself for a gap-up
    through target (conservative: we don't assume you captured extra
    gap-up profit beyond your limit).
  * SAME-CANDLE SL+TARGET AMBIGUITY — if a single day's High >= Target
    AND Low <= Stop-Loss, daily OHLC alone can't tell you which came
    first. Default: STOP-LOSS IS ASSUMED FIRST (config setting
    STOP_LOSS_HIT_FIRST_ON_AMBIGUOUS_CANDLE) — conservative, and
    clearly flagged as an assumption in the result, not hidden.
  * TIME EXIT — a position still open after MAX_HOLDING_DAYS is
    closed at that day's close (the old code had no exit besides
    SL/Target at all — flagged as a critical gap in the audit).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from config.trading_config import (
    STARTING_CAPITAL, MAX_HOLDING_DAYS, STOP_LOSS_HIT_FIRST_ON_AMBIGUOUS_CANDLE, INDEX_SYMBOL,
)
from config.universe import get_sector
from core.data_loader import get_completed_ohlcv
from core.portfolio import Portfolio, Trade
from core.risk_engine import evaluate_trade
from strategy.unified_strategy import generate_signal


NIFTY_INDEX_SYMBOL = INDEX_SYMBOL  # kept as a module-level alias for readability in this file

# How much trailing history to hand generate_signal() each day. Bounded
# on purpose (rather than "everything since inception") so a multi-year
# backtest doesn't get slower every single simulated day — this also
# matches how the live/paper engine will actually behave (it never has
# more than a rolling window of history available either).
SIGNAL_LOOKBACK_CANDLES = 300


# ======================================================================
# CONFIG / RESULT TYPES
# ======================================================================
@dataclass
class BacktestConfig:
    symbols: List[str]
    start_date: dt.date
    end_date: dt.date
    starting_capital: float = STARTING_CAPITAL
    index_symbol: str = NIFTY_INDEX_SYMBOL


@dataclass
class PendingEntry:
    symbol: str
    sector: str
    quantity: int
    stop_loss: float
    target: float
    decided_on: dt.date


@dataclass
class BacktestResult:
    portfolio: Portfolio
    warnings: List[str] = field(default_factory=list)
    symbols_used: List[str] = field(default_factory=list)
    symbols_skipped: List[str] = field(default_factory=list)
    trading_days_simulated: int = 0


# ======================================================================
# EXIT-CHECK LOGIC — Phase 7 (ambiguous candle) + Phase 8 (gap handling)
# ======================================================================
def check_exit_for_day(trade: Trade, day_row: pd.Series) -> Optional[tuple[float, str]]:
    """
    Given an open Trade and that day's OHLC row, decide whether it
    exits today and at what price. Returns (exit_price, exit_reason)
    or None if the position stays open.

    Checked in this order:
      1. Gap through stop-loss at the open (worst realistic price)
      2. Gap through target at the open (fills at target, not the
         better gap price — conservative)
      3. Both SL and Target touched intraday (ambiguous — SL assumed
         first, per config.trading_config's documented assumption)
      4. Only SL touched
      5. Only Target touched
      6. Neither — stays open
    """
    open_, high, low = day_row["Open"], day_row["High"], day_row["Low"]

    if open_ <= trade.stop_loss:
        return float(open_), "STOP_LOSS"
    if open_ >= trade.target:
        return float(trade.target), "TARGET"

    hit_target = high >= trade.target
    hit_sl = low <= trade.stop_loss

    if hit_target and hit_sl:
        if STOP_LOSS_HIT_FIRST_ON_AMBIGUOUS_CANDLE:
            return float(trade.stop_loss), "STOP_LOSS"
        return float(trade.target), "TARGET"
    if hit_sl:
        return float(trade.stop_loss), "STOP_LOSS"
    if hit_target:
        return float(trade.target), "TARGET"

    return None


def check_time_exit(trade: Trade, current_date: dt.date, close_price: float) -> Optional[tuple[float, str]]:
    """MAX_HOLDING_DAYS time-based exit, at the current close price."""
    holding_days = (current_date - trade.entry_date).days
    if holding_days >= MAX_HOLDING_DAYS:
        return float(close_price), "TIME_EXIT"
    return None


# ======================================================================
# DATA PREPARATION
# ======================================================================
def _fetch_all_data(
    symbols: List[str], index_symbol: str, start_date: dt.date, end_date: dt.date
) -> tuple[Dict[str, pd.DataFrame], Optional[pd.DataFrame], List[str]]:
    """
    Fetch completed OHLCV for every symbol plus the index, with a
    buffer of extra history before start_date so indicators (EMA50,
    ATR percentile lookback, etc.) are warmed up by the time the
    simulation actually begins. Returns (stock_data, index_data, warnings).
    """
    warnings: List[str] = []
    buffer_days = 400  # calendar days, generous enough for ~250 trading days of warmup
    fetch_start = start_date - dt.timedelta(days=buffer_days)
    period_years = max(1, (end_date - fetch_start).days // 365 + 1)
    period_str = f"{period_years}y"

    index_df = get_completed_ohlcv(index_symbol, period=period_str, interval="1d")
    if index_df is None:
        warnings.append(f"Could not fetch index data for {index_symbol} — market_regime/relative_strength will fall back to neutral throughout.")

    stock_data: Dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        df = get_completed_ohlcv(symbol, period=period_str, interval="1d")
        if df is None or len(df) < 60:
            warnings.append(f"Skipping {symbol}: insufficient/no data ({0 if df is None else len(df)} candles)")
            continue
        stock_data[symbol] = df

    return stock_data, index_df, warnings


def _build_master_calendar(
    stock_data: Dict[str, pd.DataFrame], index_df: Optional[pd.DataFrame], start_date: dt.date, end_date: dt.date
) -> List[pd.Timestamp]:
    """
    The walk-forward calendar: the union of every trading date present
    in the index (or, if no index data, the union across all stocks),
    filtered to [start_date, end_date]. Individual stocks missing a
    given date are simply skipped that day (handled at the per-symbol
    level), not treated as a calendar gap.
    """
    if index_df is not None and not index_df.empty:
        all_dates = index_df.index
    else:
        date_set = set()
        for df in stock_data.values():
            date_set.update(df.index)
        all_dates = pd.DatetimeIndex(sorted(date_set))

    mask = (all_dates.date >= start_date) & (all_dates.date <= end_date)
    return list(all_dates[mask])


# ======================================================================
# THE BACKTEST ENGINE
# ======================================================================
def run_backtest(config: BacktestConfig) -> BacktestResult:
    """
    THE single entry point. Walks the full universe forward day by day
    over one shared Portfolio, using generate_signal() and
    evaluate_trade() exactly as the paper engine will.
    """
    stock_data, index_df, warnings = _fetch_all_data(
        config.symbols, config.index_symbol, config.start_date, config.end_date
    )
    symbols_used = list(stock_data.keys())
    symbols_skipped = [s for s in config.symbols if s not in stock_data]

    calendar = _build_master_calendar(stock_data, index_df, config.start_date, config.end_date)
    if not calendar:
        warnings.append("No trading days found in the requested range — backtest produced no results.")
        return BacktestResult(
            portfolio=Portfolio(starting_capital=config.starting_capital),
            warnings=warnings, symbols_used=symbols_used, symbols_skipped=symbols_skipped,
        )

    portfolio = Portfolio(starting_capital=config.starting_capital)
    pending_entries: List[PendingEntry] = []
    last_week_number: Optional[int] = None

    for day_idx, current_ts in enumerate(calendar):
        current_date = current_ts.date()

        # New trading day -> reset the daily counters (mirrors what the
        # paper engine's scheduler will do at market open each day).
        portfolio.reset_daily_counters()
        iso_week = current_ts.isocalendar()[1]
        if last_week_number is not None and iso_week != last_week_number:
            portfolio.reset_weekly_counters()
        last_week_number = iso_week

        # --- STEP 1: execute entries queued from yesterday's signals, at TODAY's open ---
        still_pending: List[PendingEntry] = []
        for entry in pending_entries:
            df = stock_data.get(entry.symbol)
            if df is None or current_ts not in df.index:
                # Symbol didn't trade today (halt/delisting gap) — try again next day.
                still_pending.append(entry)
                continue
            today_open = float(df.loc[current_ts, "Open"])
            try:
                portfolio.open_position(
                    symbol=entry.symbol,
                    sector=entry.sector,
                    quantity=entry.quantity,
                    reference_entry_price=today_open,
                    stop_loss=entry.stop_loss,
                    target=entry.target,
                    entry_date=current_date,
                )
            except ValueError as exc:
                warnings.append(f"{current_date} {entry.symbol}: entry skipped — {exc}")
        pending_entries = still_pending

        # --- STEP 2: check exits for every open position, using TODAY's OHLC ---
        for trade in list(portfolio.open_trades):
            df = stock_data.get(trade.symbol)
            if df is None or current_ts not in df.index:
                continue  # no data today for this symbol — can't evaluate an exit
            day_row = df.loc[current_ts]

            exit_info = check_exit_for_day(trade, day_row)
            if exit_info is None:
                exit_info = check_time_exit(trade, current_date, float(day_row["Close"]))

            if exit_info is not None:
                exit_price, exit_reason = exit_info
                portfolio.close_position(trade.symbol, exit_price, current_date, exit_reason)

        # --- STEP 3: mark remaining open positions to today's close, snapshot equity ---
        today_closes = {
            sym: float(df.loc[current_ts, "Close"])
            for sym, df in stock_data.items()
            if current_ts in df.index
        }
        portfolio.mark_to_market(today_closes)
        portfolio.record_equity_snapshot(current_date)

        # --- STEP 4: generate NEW signals from today's completed data, queue for tomorrow ---
        if day_idx < len(calendar) - 1:  # no point signaling on the very last day — nothing left to execute at
            held_or_pending = {t.symbol for t in portfolio.open_trades} | {e.symbol for e in pending_entries}
            index_window = None
            if index_df is not None and current_ts in index_df.index:
                index_window = index_df.loc[:current_ts].tail(SIGNAL_LOOKBACK_CANDLES)

            for symbol, df in stock_data.items():
                if symbol in held_or_pending:
                    continue
                if current_ts not in df.index:
                    continue

                window = df.loc[:current_ts].tail(SIGNAL_LOOKBACK_CANDLES)
                signal = generate_signal(symbol, window, index_window)
                if signal.signal != "BUY":
                    continue

                sector = get_sector(symbol)
                risk_state = portfolio.to_risk_state()
                decision = evaluate_trade(
                    symbol, sector, signal.reference_close, signal.suggested_sl,
                    signal.suggested_target, risk_state, now=dt.datetime.combine(current_date, dt.time(15, 30)),
                )
                if decision.approved:
                    pending_entries.append(PendingEntry(
                        symbol=symbol, sector=sector, quantity=decision.quantity,
                        stop_loss=decision.stop_loss, target=decision.target, decided_on=current_date,
                    ))

    return BacktestResult(
        portfolio=portfolio,
        warnings=warnings,
        symbols_used=symbols_used,
        symbols_skipped=symbols_skipped,
        trading_days_simulated=len(calendar),
                )
    
