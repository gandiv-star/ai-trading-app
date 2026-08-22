"""
Gandiv AI Trading Terminal — core/portfolio.py

Purpose
-------
The actual trading ledger: cash, open positions, closed-trade journal,
and equity history. This is what turns an approved RiskDecision (from
core/risk_engine.py) into a real accounting record — and it's the
SAME Portfolio class the backtester walks through history and the
paper engine updates day-by-day (your Phase 23 requirement: paper and
future-live share the same interfaces).

Relationship to core/risk_engine.py
--------------------------------------
risk_engine.py works off a small read-only PortfolioState snapshot so
it stays decoupled from how the ledger is actually implemented. This
file (Portfolio) is the real, mutable ledger — call
Portfolio.to_risk_state() to get the snapshot risk_engine.evaluate_trade()
needs before opening any new position.

Persistence
------------
This class is intentionally storage-agnostic: to_dict() / from_dict()
give a plain-JSON-serializable snapshot. Phase L (storage layer) will
decide HOW that dict gets saved safely (atomic writes, backups,
handling the Streamlit-Cloud-vs-GitHub-Actions dual-writer problem
flagged in the Phase 1 audit) — this file doesn't know or care where
its state is persisted, only how to represent it.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.charges import calculate_trade_economics, apply_sell_slippage, calculate_charges
from core.risk_engine import PortfolioState as RiskPortfolioState, Position as RiskPosition


# ======================================================================
# PENDING ENTRY — a signal approved today, waiting to fill at the
# next trading day's open. Shared by backtest/engine.py (kept only in
# memory for the duration of one backtest run) and paper/engine.py
# (persisted between daily runs via storage/repository.py) — ONE
# definition, not two.
# ======================================================================
@dataclass
class PendingEntry:
    symbol: str
    sector: str
    quantity: int
    stop_loss: float
    target: float
    decided_on: dt.date
    signal_score: float = 0.0

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["decided_on"] = self.decided_on.isoformat()
        return d

    @staticmethod
    def from_dict(d: dict) -> "PendingEntry":
        d = dict(d)
        d["decided_on"] = dt.date.fromisoformat(d["decided_on"])
        return PendingEntry(**d)


# ======================================================================
# TRADE RECORD
# ======================================================================
@dataclass
class Trade:
    symbol: str
    sector: str
    quantity: int
    entry_price: float          # actual executed (slippage-applied) entry price
    entry_date: dt.date
    stop_loss: float
    target: float
    current_price: float = 0.0   # updated by mark_to_market while open

    exit_price: Optional[float] = None
    exit_date: Optional[dt.date] = None
    exit_reason: Optional[str] = None  # "TARGET" | "STOP_LOSS" | "MANUAL" | "TIME_EXIT"
    charges_total: float = 0.0
    gross_pnl: Optional[float] = None
    net_pnl: Optional[float] = None

    def __post_init__(self) -> None:
        if self.current_price == 0.0:
            self.current_price = self.entry_price

    @property
    def is_open(self) -> bool:
        return self.exit_price is None

    @property
    def current_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        return self.quantity * (self.current_price - self.entry_price) if self.is_open else 0.0

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["entry_date"] = self.entry_date.isoformat()
        d["exit_date"] = self.exit_date.isoformat() if self.exit_date else None
        return d

    @staticmethod
    def from_dict(d: dict) -> "Trade":
        d = dict(d)
        d["entry_date"] = dt.date.fromisoformat(d["entry_date"])
        d["exit_date"] = dt.date.fromisoformat(d["exit_date"]) if d.get("exit_date") else None
        return Trade(**d)


# ======================================================================
# PORTFOLIO
# ======================================================================
class Portfolio:
    """
    The trading ledger. `starting_capital` is fixed at construction
    (₹1,00,000 per your spec) and never changes — it's the reference
    point for CAGR/return-% calculations. Everything else (cash,
    positions, history) evolves as trades happen.
    """

    def __init__(self, starting_capital: float):
        self.starting_capital = starting_capital
        self.cash = starting_capital
        self.peak_equity = starting_capital

        self.open_trades: List[Trade] = []
        self.closed_trades: List[Trade] = []
        self.equity_history: List[Dict[str, object]] = []  # [{"date": ..., "equity": ...}, ...]

        # Entries approved today, waiting for tomorrow's open (paper
        # engine only — the backtester keeps this in a local variable
        # since it never stops mid-run, but the paper engine's daily
        # cycle is a fresh process each day and MUST persist this).
        self.pending_entries: List[PendingEntry] = []

        # The last calendar date run_daily_cycle() successfully
        # processed — guards against accidentally processing the same
        # day twice (e.g. a GitHub Actions re-run, or a manual button
        # double-click), which would double-count trades_today and
        # could duplicate entries. None until the first cycle ever runs.
        self.last_processed_date: Optional[dt.date] = None

        # Risk-engine-facing counters — reset by the caller (paper
        # engine's daily/weekly driver) at day/week boundaries via
        # reset_daily_counters() / reset_weekly_counters() below.
        self.trades_today: int = 0
        self.realized_pnl_today: float = 0.0
        self.realized_pnl_this_week: float = 0.0
        self.consecutive_losses: int = 0
        self.last_stop_loss_time: Dict[str, dt.datetime] = {}

    # ------------------------------------------------------------------
    # DERIVED PROPERTIES
    # ------------------------------------------------------------------
    @property
    def deployed_value(self) -> float:
        return sum(t.current_value for t in self.open_trades)

    @property
    def total_equity(self) -> float:
        return self.cash + self.deployed_value

    @property
    def total_return_pct(self) -> float:
        return (self.total_equity - self.starting_capital) / self.starting_capital * 100

    @property
    def current_drawdown_pct(self) -> float:
        if self.peak_equity <= 0:
            return 0.0
        return max(0.0, (self.peak_equity - self.total_equity) / self.peak_equity * 100)

    @property
    def win_count(self) -> int:
        return sum(1 for t in self.closed_trades if (t.net_pnl or 0) > 0)

    @property
    def loss_count(self) -> int:
        return sum(1 for t in self.closed_trades if (t.net_pnl or 0) <= 0)

    @property
    def win_rate_pct(self) -> float:
        total = len(self.closed_trades)
        return (self.win_count / total * 100) if total > 0 else 0.0

    def has_position(self, symbol: str) -> bool:
        return any(t.symbol == symbol for t in self.open_trades)

    def get_position(self, symbol: str) -> Optional[Trade]:
        return next((t for t in self.open_trades if t.symbol == symbol), None)

    # ------------------------------------------------------------------
    # OPENING / CLOSING POSITIONS
    # ------------------------------------------------------------------
    def open_position(
        self,
        symbol: str,
        sector: str,
        quantity: int,
        reference_entry_price: float,
        stop_loss: float,
        target: float,
        entry_date: dt.date,
        apply_slippage: bool = True,
    ) -> Trade:
        """
        Opens a new position. `reference_entry_price` is the signal's
        clean reference price (e.g. T+1 open) — slippage is applied
        here to get the realistic executed price, matching exactly
        what the backtester and paper engine both do via
        core/charges.py, so neither one can silently diverge on how
        fills are simulated.

        Cash is reduced by quantity * executed_entry_price only.
        Round-trip charges (which need both entry AND exit prices) are
        deducted once, at close_position(), not split across both
        legs — this keeps the accounting simple and exactly
        reconciles: net_pnl at exit equals the total cash impact of
        the trade.
        """
        if self.has_position(symbol):
            raise ValueError(f"Portfolio.open_position: already holding {symbol}")
        if quantity <= 0:
            raise ValueError(f"Portfolio.open_position: quantity must be > 0, got {quantity}")

        from core.charges import apply_buy_slippage
        executed_entry = apply_buy_slippage(reference_entry_price) if apply_slippage else reference_entry_price

        cost = quantity * executed_entry
        if cost > self.cash + 1e-6:  # tiny epsilon for float rounding
            raise ValueError(
                f"Portfolio.open_position: insufficient cash for {symbol} "
                f"(need {cost:.2f}, have {self.cash:.2f}) — risk_engine should "
                f"have prevented this; check the caller's cap-stacking."
            )

        trade = Trade(
            symbol=symbol,
            sector=sector,
            quantity=quantity,
            entry_price=executed_entry,
            entry_date=entry_date,
            stop_loss=stop_loss,
            target=target,
        )
        self.cash -= cost
        self.open_trades.append(trade)
        self.trades_today += 1

        return trade

    def close_position(
        self,
        symbol: str,
        reference_exit_price: float,
        exit_date: dt.date,
        exit_reason: str,
        apply_slippage: bool = True,
    ) -> Trade:
        """
        Closes an open position: applies exit slippage, computes the
        full round-trip charges (entry + exit together), realizes
        P&L, and updates the risk-engine-facing counters (consecutive
        losses, cooldown timer if stopped out).

        trade.entry_price is ALREADY the slippage-adjusted executed
        price from open_position() — so only exit-side slippage is
        applied here, never entry-side again (that would double-count
        it).
        """
        trade = self.get_position(symbol)
        if trade is None:
            raise ValueError(f"Portfolio.close_position: no open position in {symbol}")

        executed_exit = apply_sell_slippage(reference_exit_price) if apply_slippage else reference_exit_price
        charges = calculate_charges(trade.entry_price, executed_exit, trade.quantity)
        gross_pnl = trade.quantity * (executed_exit - trade.entry_price)
        net_pnl = gross_pnl - charges.total_charges

        trade.exit_price = executed_exit
        trade.exit_date = exit_date
        trade.exit_reason = exit_reason
        trade.charges_total = charges.total_charges
        trade.gross_pnl = round(gross_pnl, 2)
        trade.net_pnl = round(net_pnl, 2)

        self.cash += trade.quantity * executed_exit - charges.total_charges

        self.open_trades.remove(trade)
        self.closed_trades.append(trade)

        self.realized_pnl_today += net_pnl
        self.realized_pnl_this_week += net_pnl

        if net_pnl > 0:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1

        if exit_reason == "STOP_LOSS":
            self.last_stop_loss_time[symbol] = dt.datetime.combine(exit_date, dt.time(15, 30))

        self.peak_equity = max(self.peak_equity, self.total_equity)

        return trade

    # ------------------------------------------------------------------
    # MARK-TO-MARKET / EQUITY TRACKING
    # ------------------------------------------------------------------
    def mark_to_market(self, prices: Dict[str, float]) -> None:
        """Update current_price on every open trade from a {symbol: price} map."""
        for trade in self.open_trades:
            if trade.symbol in prices:
                trade.current_price = prices[trade.symbol]
        self.peak_equity = max(self.peak_equity, self.total_equity)

    def record_equity_snapshot(self, as_of: dt.date) -> None:
        self.equity_history.append({"date": as_of.isoformat(), "equity": round(self.total_equity, 2)})
        self.peak_equity = max(self.peak_equity, self.total_equity)

    # ------------------------------------------------------------------
    # DAY / WEEK ROLLOVER — called by the paper engine's driver loop
    # ------------------------------------------------------------------
    def reset_daily_counters(self) -> None:
        self.trades_today = 0
        self.realized_pnl_today = 0.0

    def reset_weekly_counters(self) -> None:
        self.realized_pnl_this_week = 0.0

    # ------------------------------------------------------------------
    # BRIDGE TO RISK ENGINE
    # ------------------------------------------------------------------
    def to_risk_state(self) -> RiskPortfolioState:
        """
        Build the read-only snapshot core/risk_engine.evaluate_trade()
        needs. Call this fresh right before every risk check — it
        always reflects the ledger's current state.
        """
        return RiskPortfolioState(
            cash=self.cash,
            peak_equity=self.peak_equity,
            open_positions=[
                RiskPosition(
                    symbol=t.symbol,
                    sector=t.sector,
                    quantity=t.quantity,
                    entry_price=t.entry_price,
                    current_price=t.current_price,
                )
                for t in self.open_trades
            ],
            trades_today=self.trades_today,
            realized_pnl_today=self.realized_pnl_today,
            realized_pnl_this_week=self.realized_pnl_this_week,
            consecutive_losses=self.consecutive_losses,
            last_stop_loss_time=dict(self.last_stop_loss_time),
        )

    # ------------------------------------------------------------------
    # SERIALIZATION (storage-agnostic — Phase L decides how/where)
    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "schema_version": 1,
            "starting_capital": self.starting_capital,
            "cash": self.cash,
            "peak_equity": self.peak_equity,
            "open_trades": [t.to_dict() for t in self.open_trades],
            "closed_trades": [t.to_dict() for t in self.closed_trades],
            "equity_history": self.equity_history,
            "pending_entries": [e.to_dict() for e in self.pending_entries],
            "last_processed_date": self.last_processed_date.isoformat() if self.last_processed_date else None,
            "trades_today": self.trades_today,
            "realized_pnl_today": self.realized_pnl_today,
            "realized_pnl_this_week": self.realized_pnl_this_week,
            "consecutive_losses": self.consecutive_losses,
            "last_stop_loss_time": {
                k: v.isoformat() for k, v in self.last_stop_loss_time.items()
            },
        }

    @staticmethod
    def from_dict(d: dict) -> "Portfolio":
        p = Portfolio(starting_capital=d["starting_capital"])
        p.cash = d["cash"]
        p.peak_equity = d["peak_equity"]
        p.open_trades = [Trade.from_dict(t) for t in d["open_trades"]]
        p.closed_trades = [Trade.from_dict(t) for t in d["closed_trades"]]
        p.equity_history = d["equity_history"]
        p.pending_entries = [PendingEntry.from_dict(e) for e in d.get("pending_entries", [])]
        lpd = d.get("last_processed_date")
        p.last_processed_date = dt.date.fromisoformat(lpd) if lpd else None
        p.trades_today = d["trades_today"]
        p.realized_pnl_today = d["realized_pnl_today"]
        p.realized_pnl_this_week = d["realized_pnl_this_week"]
        p.consecutive_losses = d["consecutive_losses"]
        p.last_stop_loss_time = {
            k: dt.datetime.fromisoformat(v) for k, v in d["last_stop_loss_time"].items()
        }
        return p
