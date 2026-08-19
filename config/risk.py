"""
Gandiv AI Trading Terminal — config/risk.py

Purpose
-------
Every hard risk limit in ONE place. The future risk_engine.py (Phase F)
reads only from here — it must never hardcode a number itself.

Design principle (per your Phase 11 requirement)
--------------------------------------------------
The risk engine is INDEPENDENT of the strategy. The signal engine is
allowed to say "BUY" — that alone must never place an order. Every
signal passes through these limits before it can become a trade:

    SIGNAL  ->  RISK CHECK (this file's limits)  ->  POSITION SIZE  ->  EXECUTION

All values here are starting defaults for paper trading with
₹1,00,000 capital. They are intentionally conservative. Tune them
only after you have out-of-sample paper-trading evidence that a
looser limit is still safe — do not loosen these because a backtest
looked good (see anti-overfitting rule in your master prompt).
"""

from __future__ import annotations

from typing import Dict

# --------------------------------------------------------------------
# POSITION SIZING RISK (per-trade)
# --------------------------------------------------------------------
# % of total capital risked on a single trade if its stop-loss is hit.
# Position size = (CAPITAL * RISK_PER_TRADE_PCT / 100) / (entry - SL per share)
RISK_PER_TRADE_PCT: float = 1.0          # 1% of capital per trade
MIN_RISK_PER_TRADE_PCT: float = 0.5      # floor, for future dynamic sizing
MAX_RISK_PER_TRADE_PCT: float = 1.0      # ceiling, for future dynamic sizing

# --------------------------------------------------------------------
# PORTFOLIO-LEVEL LIMITS
# --------------------------------------------------------------------
MAX_OPEN_POSITIONS: int = 5              # configurable; matches your ₹1L paper plan
MAX_PORTFOLIO_EXPOSURE_PCT: float = 80.0  # max % of capital deployed at once
SINGLE_STOCK_CAP_PCT: float = 8.0         # max % of capital in one stock (carried over from old config.py)

# --------------------------------------------------------------------
# SECTOR EXPOSURE CAPS (% of total capital)
# --------------------------------------------------------------------
# Keys must match sectors used in config/universe.py's SECTOR_MAP.
# Any sector not listed here falls back to SECTOR_CAP_DEFAULT.
SECTOR_CAPS: Dict[str, float] = {
    "Banking": 20.0,
    "IT": 20.0,
    "Pharma": 15.0,
    "FMCG": 15.0,
    "Auto": 15.0,
    "Energy": 15.0,
    "Infra": 15.0,
    "NBFC": 15.0,
    "Metals": 10.0,
    "Telecom": 10.0,
    "Paints": 10.0,
    "Retail": 10.0,
    "Defence": 10.0,
    "Railways": 10.0,
    "Insurance": 8.0,
    "Services": 8.0,
}
SECTOR_CAP_DEFAULT: float = 10.0  # fallback for any sector not listed above

# --------------------------------------------------------------------
# LOSS PROTECTION (capital preservation — your #1 stated priority)
# --------------------------------------------------------------------
DAILY_LOSS_LIMIT_PCT: float = 3.0        # halt new trades if today's loss hits this %
WEEKLY_LOSS_LIMIT_PCT: float = 6.0       # flag/halt if this week's loss hits this %
MAX_DRAWDOWN_PCT: float = 15.0           # circuit breaker: stop trading entirely
MAX_CONSECUTIVE_LOSSES: int = 4          # losing-streak protection trigger

# --------------------------------------------------------------------
# TRADE FREQUENCY / COOLDOWN CONTROLS
# --------------------------------------------------------------------
MAX_DAILY_TRADES: int = 6                # avoid overtrading
COOLDOWN_MINUTES_AFTER_SL: int = 60      # pause before re-entering same symbol after a stop-out

# --------------------------------------------------------------------
# DUPLICATE / SAFETY CONTROLS
# --------------------------------------------------------------------
MIN_MINUTES_BETWEEN_BOT_RUNS: int = 15   # duplicate-execution guard, works with
                                          # GitHub Actions concurrency group


def get_sector_cap(sector: str) -> float:
    """Sector exposure cap as a percentage of capital, with fallback."""
    return SECTOR_CAPS.get(sector, SECTOR_CAP_DEFAULT)
