"""
Gandiv AI Trading Terminal — backtest/metrics.py

Purpose
-------
Every metric your master prompt's Phase 6 requires, computed from a
finished backtest's Portfolio (closed trades + equity curve) — never
just "Profit = X%".
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

from core.portfolio import Portfolio, Trade

TRADING_DAYS_PER_YEAR = 252


@dataclass
class BacktestMetrics:
    # Trade counts
    total_trades: int
    win_count: int
    loss_count: int
    win_rate_pct: float
    loss_rate_pct: float

    # Returns
    total_return_pct: float
    cagr_pct: float

    # Trade quality
    profit_factor: float          # gross profit / gross loss
    expectancy: float             # average net_pnl per trade (₹)
    average_win: float
    average_loss: float
    avg_risk_reward: float        # average_win / abs(average_loss)

    # Risk
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float

    # Behaviour
    avg_holding_days: float
    max_consecutive_wins: int
    max_consecutive_losses: int

    # Time series
    monthly_returns_pct: Dict[str, float] = field(default_factory=dict)
    yearly_returns_pct: Dict[str, float] = field(default_factory=dict)
    drawdown_curve: List[Dict[str, object]] = field(default_factory=list)

    # Context the person reading the report needs, not just the numbers
    open_positions_at_end: int = 0
    unrealized_pnl_at_end: float = 0.0


def _max_streak(sequence: List[bool]) -> int:
    """Longest run of consecutive True values in `sequence`."""
    best = current = 0
    for val in sequence:
        current = current + 1 if val else 0
        best = max(best, current)
    return best


def _equity_series(portfolio: Portfolio) -> "pd_like":
    """Returns (dates: List[date], equity: List[float]) from the recorded equity curve."""
    dates = [dt.date.fromisoformat(row["date"]) for row in portfolio.equity_history]
    equity = [float(row["equity"]) for row in portfolio.equity_history]
    return dates, equity


def _drawdown_curve(dates: List[dt.date], equity: List[float]) -> List[Dict[str, object]]:
    curve = []
    peak = equity[0] if equity else 0.0
    for d, e in zip(dates, equity):
        peak = max(peak, e)
        dd_pct = ((peak - e) / peak * 100) if peak > 0 else 0.0
        curve.append({"date": d.isoformat(), "equity": round(e, 2), "drawdown_pct": round(dd_pct, 2)})
    return curve


def _period_returns(dates: List[dt.date], equity: List[float], period: str) -> Dict[str, float]:
    """
    period: 'month' -> keys like '2026-01', 'year' -> keys like '2026'.
    Return % is computed from the last equity value carried INTO the
    period (previous period's closing equity) to that period's closing
    equity — the first period in the series uses its own first value
    as the baseline (no prior data to compare against).
    """
    if not dates:
        return {}

    def key_for(d: dt.date) -> str:
        return d.strftime("%Y-%m") if period == "month" else d.strftime("%Y")

    period_last_equity: Dict[str, float] = {}
    order: List[str] = []
    for d, e in zip(dates, equity):
        k = key_for(d)
        if k not in period_last_equity:
            order.append(k)
        period_last_equity[k] = e

    returns: Dict[str, float] = {}
    prev_equity = equity[0]
    for k in order:
        end_equity = period_last_equity[k]
        base = prev_equity if prev_equity > 0 else end_equity
        returns[k] = round((end_equity - base) / base * 100, 2) if base > 0 else 0.0
        prev_equity = end_equity
    return returns


def calculate_metrics(portfolio: Portfolio) -> BacktestMetrics:
    """
    THE single entry point. Computes the full metrics suite from a
    Portfolio that has already been walked through a backtest (or,
    identically, from a live paper-trading portfolio's history so far
    — the same function works for both, since Portfolio's shape never
    changes between contexts).
    """
    closed = portfolio.closed_trades
    total_trades = len(closed)

    wins = [t for t in closed if (t.net_pnl or 0) > 0]
    losses = [t for t in closed if (t.net_pnl or 0) <= 0]
    win_count, loss_count = len(wins), len(losses)
    win_rate = (win_count / total_trades * 100) if total_trades else 0.0
    loss_rate = (loss_count / total_trades * 100) if total_trades else 0.0

    gross_profit = sum(t.net_pnl for t in wins) if wins else 0.0
    gross_loss = abs(sum(t.net_pnl for t in losses)) if losses else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)

    expectancy = (sum(t.net_pnl for t in closed) / total_trades) if total_trades else 0.0
    average_win = (gross_profit / win_count) if win_count else 0.0
    average_loss = (-gross_loss / loss_count) if loss_count else 0.0
    avg_rr = (average_win / abs(average_loss)) if average_loss != 0 else 0.0

    avg_holding_days = (
        sum((t.exit_date - t.entry_date).days for t in closed) / total_trades
        if total_trades else 0.0
    )

    win_loss_sequence = [(t.net_pnl or 0) > 0 for t in closed]
    max_consec_wins = _max_streak(win_loss_sequence)
    max_consec_losses = _max_streak([not w for w in win_loss_sequence])

    dates, equity = _equity_series(portfolio)
    total_return_pct = portfolio.total_return_pct

    if dates and len(dates) > 1:
        days_elapsed = (dates[-1] - dates[0]).days
        years_elapsed = max(days_elapsed / 365.25, 1 / 365.25)
        cagr_pct = ((equity[-1] / portfolio.starting_capital) ** (1 / years_elapsed) - 1) * 100
    else:
        cagr_pct = 0.0

    if len(equity) > 1:
        equity_arr = np.array(equity)
        daily_returns = np.diff(equity_arr) / equity_arr[:-1]
        mean_ret = float(np.mean(daily_returns))
        std_ret = float(np.std(daily_returns, ddof=1)) if len(daily_returns) > 1 else 0.0
        sharpe = (mean_ret / std_ret * np.sqrt(TRADING_DAYS_PER_YEAR)) if std_ret > 0 else 0.0

        downside_returns = daily_returns[daily_returns < 0]
        downside_std = float(np.std(downside_returns, ddof=1)) if len(downside_returns) > 1 else 0.0
        sortino = (mean_ret / downside_std * np.sqrt(TRADING_DAYS_PER_YEAR)) if downside_std > 0 else 0.0
    else:
        sharpe, sortino = 0.0, 0.0

    dd_curve = _drawdown_curve(dates, equity)
    max_dd = max((row["drawdown_pct"] for row in dd_curve), default=0.0)

    calmar = (cagr_pct / max_dd) if max_dd > 0 else 0.0

    monthly = _period_returns(dates, equity, "month")
    yearly = _period_returns(dates, equity, "year")

    return BacktestMetrics(
        total_trades=total_trades,
        win_count=win_count,
        loss_count=loss_count,
        win_rate_pct=round(win_rate, 2),
        loss_rate_pct=round(loss_rate, 2),
        total_return_pct=round(total_return_pct, 2),
        cagr_pct=round(cagr_pct, 2),
        profit_factor=round(profit_factor, 2) if profit_factor != float("inf") else profit_factor,
        expectancy=round(expectancy, 2),
        average_win=round(average_win, 2),
        average_loss=round(average_loss, 2),
        avg_risk_reward=round(avg_rr, 2),
        max_drawdown_pct=round(max_dd, 2),
        sharpe_ratio=round(sharpe, 3),
        sortino_ratio=round(sortino, 3),
        calmar_ratio=round(calmar, 3),
        avg_holding_days=round(avg_holding_days, 1),
        max_consecutive_wins=max_consec_wins,
        max_consecutive_losses=max_consec_losses,
        monthly_returns_pct=monthly,
        yearly_returns_pct=yearly,
        drawdown_curve=dd_curve,
        open_positions_at_end=len(portfolio.open_trades),
        unrealized_pnl_at_end=round(sum(t.unrealized_pnl for t in portfolio.open_trades), 2),
    )
