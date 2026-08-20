"""
Gandiv AI Trading Terminal — core/risk_engine.py

Purpose
-------
The independent risk gate between "the strategy engine says BUY" and
"an order actually gets sized and placed" — your Phase 11 requirement:

    SIGNAL  ->  RISK CHECK  ->  POSITION SIZE  ->  EXECUTION

This file NEVER decides whether a setup is technically good (that is
strategy/unified_strategy.py's job, and only its job). It only asks:
given everything already committed in the portfolio right now, is
this new trade SAFE to take, and if so, how big should it be?

Portfolio state is passed in, not fetched
--------------------------------------------
This file has no idea whether it's being called from the backtester
(simulated portfolio) or the paper engine (real persisted state) or a
future live engine (broker account state). It only knows the
PortfolioState dataclass below. That is what makes the SAME risk
logic usable identically in all three contexts — the actual
persistence/storage layer is somebody else's problem (paper/state.py,
Phase J).

Check order
------------
1. Circuit breaker (daily loss / weekly loss / drawdown / consecutive
   losses) — if ANY of these have tripped, reject EVERYTHING, no
   exceptions, regardless of how good the signal looks.
2. Duplicate position guard — already holding this symbol? reject.
3. Max open positions / max daily trades — reject if at the limit.
4. Cooldown — this symbol was just stopped out recently? reject.
5. Position sizing — compute the risk-based quantity, then reduce it
   (never reject solely for this) through single-stock cap, sector
   cap, portfolio exposure cap, and available cash, in that order.
   If every cap collectively squeezes the size to zero shares, THAT
   becomes a rejection (nothing meaningful left to buy).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from config.risk import (
    RISK_PER_TRADE_PCT,
    MAX_OPEN_POSITIONS,
    MAX_PORTFOLIO_EXPOSURE_PCT,
    SINGLE_STOCK_CAP_PCT,
    DAILY_LOSS_LIMIT_PCT,
    WEEKLY_LOSS_LIMIT_PCT,
    MAX_DRAWDOWN_PCT,
    MAX_CONSECUTIVE_LOSSES,
    MAX_DAILY_TRADES,
    COOLDOWN_MINUTES_AFTER_SL,
    get_sector_cap,
)
from core.position_sizing import calculate_risk_based_quantity, calculate_risk_amount, calculate_position_value


# ======================================================================
# PORTFOLIO STATE — the only thing this file needs from the outside
# ======================================================================
@dataclass
class Position:
    symbol: str
    sector: str
    quantity: int
    entry_price: float
    current_price: float

    @property
    def current_value(self) -> float:
        return self.quantity * self.current_price


@dataclass
class PortfolioState:
    cash: float
    peak_equity: float                          # highest total_equity ever reached — for drawdown calc
    open_positions: List[Position] = field(default_factory=list)
    trades_today: int = 0
    realized_pnl_today: float = 0.0
    realized_pnl_this_week: float = 0.0
    consecutive_losses: int = 0
    last_stop_loss_time: Dict[str, dt.datetime] = field(default_factory=dict)  # symbol -> when it was last stopped out

    @property
    def total_equity(self) -> float:
        return self.cash + sum(p.current_value for p in self.open_positions)

    @property
    def current_drawdown_pct(self) -> float:
        if self.peak_equity <= 0:
            return 0.0
        return max(0.0, (self.peak_equity - self.total_equity) / self.peak_equity * 100)

    @property
    def deployed_value(self) -> float:
        return sum(p.current_value for p in self.open_positions)

    def sector_exposure_value(self, sector: str) -> float:
        return sum(p.current_value for p in self.open_positions if p.sector == sector)

    def has_position(self, symbol: str) -> bool:
        return any(p.symbol == symbol for p in self.open_positions)


# ======================================================================
# RESULT TYPE
# ======================================================================
@dataclass
class RiskDecision:
    approved: bool
    symbol: str
    reason: str
    quantity: int = 0
    entry_price: float = 0.0
    stop_loss: float = 0.0
    target: float = 0.0
    risk_amount: float = 0.0
    position_value: float = 0.0
    capped_by: List[str] = field(default_factory=list)


# ======================================================================
# STEP 1 — CIRCUIT BREAKER (checked first, blocks everything if tripped)
# ======================================================================
def check_circuit_breaker(portfolio: PortfolioState) -> Optional[str]:
    """
    Returns a rejection reason string if trading should be halted
    entirely right now, or None if it's safe to continue evaluating
    this trade. This is checked before anything symbol-specific.
    """
    if portfolio.current_drawdown_pct >= MAX_DRAWDOWN_PCT:
        return (
            f"CIRCUIT BREAKER: drawdown {portfolio.current_drawdown_pct:.1f}% "
            f"has reached the {MAX_DRAWDOWN_PCT}% limit — all new trades halted"
        )

    if portfolio.peak_equity > 0:
        daily_loss_pct = -portfolio.realized_pnl_today / portfolio.peak_equity * 100
        if daily_loss_pct >= DAILY_LOSS_LIMIT_PCT:
            return (
                f"CIRCUIT BREAKER: today's loss {daily_loss_pct:.1f}% has reached "
                f"the {DAILY_LOSS_LIMIT_PCT}% daily limit — no new trades today"
            )

        weekly_loss_pct = -portfolio.realized_pnl_this_week / portfolio.peak_equity * 100
        if weekly_loss_pct >= WEEKLY_LOSS_LIMIT_PCT:
            return (
                f"CIRCUIT BREAKER: this week's loss {weekly_loss_pct:.1f}% has reached "
                f"the {WEEKLY_LOSS_LIMIT_PCT}% weekly limit — no new trades this week"
            )

    if portfolio.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
        return (
            f"CIRCUIT BREAKER: {portfolio.consecutive_losses} consecutive losses "
            f"has reached the {MAX_CONSECUTIVE_LOSSES}-loss losing-streak limit"
        )

    return None


# ======================================================================
# STEP 2-4 — PER-SYMBOL GATES
# ======================================================================
def check_symbol_gates(
    symbol: str,
    portfolio: PortfolioState,
    now: Optional[dt.datetime] = None,
) -> Optional[str]:
    """Returns a rejection reason, or None if the symbol clears every gate."""
    now = now or dt.datetime.now()

    if portfolio.has_position(symbol):
        return f"Already holding an open position in {symbol} — duplicate order blocked"

    if len(portfolio.open_positions) >= MAX_OPEN_POSITIONS:
        return f"Max open positions ({MAX_OPEN_POSITIONS}) already reached"

    if portfolio.trades_today >= MAX_DAILY_TRADES:
        return f"Max daily trades ({MAX_DAILY_TRADES}) already reached for today"

    last_sl = portfolio.last_stop_loss_time.get(symbol)
    if last_sl is not None:
        minutes_since = (now - last_sl).total_seconds() / 60
        if minutes_since < COOLDOWN_MINUTES_AFTER_SL:
            remaining = COOLDOWN_MINUTES_AFTER_SL - minutes_since
            return (
                f"{symbol} is in cooldown after a recent stop-loss "
                f"({remaining:.0f} more minutes before re-entry is allowed)"
            )

    return None


# ======================================================================
# STEP 5 — POSITION SIZING WITH STACKED CAPS
# ======================================================================
def size_position(
    symbol: str,
    sector: str,
    entry_price: float,
    stop_loss_price: float,
    portfolio: PortfolioState,
) -> tuple[int, List[str]]:
    """
    Returns (final_quantity, capped_by) where capped_by lists which
    caps actually reduced the size below the pure risk-based quantity
    (for transparency/logging — Phase 27's "explainable decisions").
    """
    equity = portfolio.total_equity
    capped_by: List[str] = []

    risk_capital = equity * (RISK_PER_TRADE_PCT / 100)
    qty = calculate_risk_based_quantity(entry_price, stop_loss_price, risk_capital)
    if qty <= 0:
        return 0, ["invalid_setup (stop-loss not below entry, or zero risk capital)"]

    # Single-stock cap
    max_stock_value = equity * (SINGLE_STOCK_CAP_PCT / 100)
    max_qty_stock = int(max_stock_value // entry_price)
    if max_qty_stock < qty:
        qty = max_qty_stock
        capped_by.append(f"single_stock_cap ({SINGLE_STOCK_CAP_PCT}%)")

    # Sector cap
    sector_cap_pct = get_sector_cap(sector)
    max_sector_value = equity * (sector_cap_pct / 100)
    remaining_sector_room = max(0.0, max_sector_value - portfolio.sector_exposure_value(sector))
    max_qty_sector = int(remaining_sector_room // entry_price)
    if max_qty_sector < qty:
        qty = max_qty_sector
        capped_by.append(f"sector_cap:{sector} ({sector_cap_pct}%)")

    # Portfolio exposure cap
    max_deployed_value = equity * (MAX_PORTFOLIO_EXPOSURE_PCT / 100)
    remaining_exposure_room = max(0.0, max_deployed_value - portfolio.deployed_value)
    max_qty_exposure = int(remaining_exposure_room // entry_price)
    if max_qty_exposure < qty:
        qty = max_qty_exposure
        capped_by.append(f"portfolio_exposure_cap ({MAX_PORTFOLIO_EXPOSURE_PCT}%)")

    # Available cash (hard constraint — can never buy more than cash on hand)
    max_qty_cash = int(portfolio.cash // entry_price)
    if max_qty_cash < qty:
        qty = max_qty_cash
        capped_by.append("available_cash")

    return max(0, qty), capped_by


# ======================================================================
# THE RISK ENGINE — single entry point
# ======================================================================
def evaluate_trade(
    symbol: str,
    sector: str,
    entry_price: float,
    stop_loss_price: float,
    target_price: float,
    portfolio: PortfolioState,
    now: Optional[dt.datetime] = None,
) -> RiskDecision:
    """
    THE single entry point: SIGNAL -> RISK CHECK -> POSITION SIZE.

    Call this with a strategy/unified_strategy.SignalResult's
    reference_close / suggested_sl / suggested_target (only ever call
    this at all when that signal was "BUY" — this function assumes
    the caller already decided the setup is technically worth
    considering; it only judges whether it's SAFE and how big).
    """
    breaker_reason = check_circuit_breaker(portfolio)
    if breaker_reason:
        return RiskDecision(approved=False, symbol=symbol, reason=breaker_reason)

    gate_reason = check_symbol_gates(symbol, portfolio, now)
    if gate_reason:
        return RiskDecision(approved=False, symbol=symbol, reason=gate_reason)

    quantity, capped_by = size_position(symbol, sector, entry_price, stop_loss_price, portfolio)

    if quantity <= 0:
        return RiskDecision(
            approved=False,
            symbol=symbol,
            reason="Position sizing reduced quantity to 0 shares after applying risk/exposure caps",
            capped_by=capped_by,
        )

    return RiskDecision(
        approved=True,
        symbol=symbol,
        reason="Approved" if not capped_by else f"Approved (reduced by: {', '.join(capped_by)})",
        quantity=quantity,
        entry_price=entry_price,
        stop_loss=stop_loss_price,
        target=target_price,
        risk_amount=round(calculate_risk_amount(quantity, entry_price, stop_loss_price), 2),
        position_value=round(calculate_position_value(quantity, entry_price), 2),
        capped_by=capped_by,
    )
