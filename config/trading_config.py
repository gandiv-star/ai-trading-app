"""
Gandiv AI Trading Terminal — config/trading_config.py

Purpose
-------
Everything about HOW a trade is sized, exited, charged, and WHEN the
market is open. This is what Phase B–K (data, strategy, backtest,
paper engine) will read instead of hardcoding numbers inline.

Sections in this file
----------------------
  1. Capital & mode          (paper vs live — paper only, for now)
  2. Signal quality threshold
  3. Stop-loss / Target      (ATR-based, per your "Completed Candle +
                               ATR position sizing" requirement)
  4. Charges                  (ONE set of rates — was duplicated 3x
                               across app.py / auto_trade_bot.py /
                               data_loader.py with different numbers
                               in the old code)
  5. Market hours & timezone
  6. NSE holiday calendar     (was MISSING entirely in the old
                               GitHub Actions workflow — it only
                               skipped weekends)
  7. Signal engine weights    (configurable, not blindly hardcoded
                               25+20+20+20+15 as flagged in your prompt)
"""

from __future__ import annotations

import datetime as dt
from typing import Dict, Set

# ======================================================================
# 1. CAPITAL & MODE
# ======================================================================
TRADING_MODE: str = "PAPER"  # "PAPER" only for now — LIVE is out of
                              # scope until this system has passed
                              # backtest -> out-of-sample -> paper
                              # -> small-capital validation (Phase 19
                              # of your original audit prompt).

STARTING_CAPITAL: float = 100_000.0  # ₹1,00,000 as specified

# ======================================================================
# 2. SIGNAL QUALITY THRESHOLD
# ======================================================================
# Confluence score (0-100) a signal must clear before the risk engine
# will even consider it. Carried over from the existing MIN_SCORE=75
# used in auto_trade_bot.py — kept as-is so behaviour doesn't silently
# change; tune later with actual paper-trading evidence.
MIN_SIGNAL_SCORE: int = 75

# ======================================================================
# 3. STOP-LOSS / TARGET — ATR-based (primary), fixed % (fallback only)
# ======================================================================
# Position sizing formula (Phase 9 of your spec):
#   risk_per_share = entry_price - stop_loss_price
#   quantity = (STARTING_CAPITAL * RISK_PER_TRADE_PCT / 100) / risk_per_share
#
# Stop-loss and target distance are derived from ATR (Average True
# Range) of the completed candle, NOT a blind fixed percentage. This
# adapts to each stock's own volatility instead of using one SL% for
# a calm FMCG stock and a volatile small-cap alike.
ATR_PERIOD: int = 14
ATR_SL_MULTIPLIER: float = 1.5    # Stop-loss = entry - (1.5 x ATR)
ATR_TARGET_MULTIPLIER: float = 3.0  # Target   = entry + (3.0 x ATR)  -> 1:2 risk:reward by default

# Time-based exit: close a position after this many trading days even
# if neither SL nor Target has been hit. The old code had NO exit
# mechanism at all besides SL/Target — a position that just drifts
# sideways forever would sit open indefinitely, tying up capital and
# a slot in MAX_OPEN_POSITIONS for no purpose. This was flagged as a
# critical gap in the original audit.
MAX_HOLDING_DAYS: int = 20  # roughly one month of trading days

# Fallback ONLY if ATR cannot be computed (e.g. insufficient history
# for a newly listed stock). Matches the old TARGET_PCT/SL_PCT values
# so behaviour is a safe superset, not a silent change.
FALLBACK_TARGET_PCT: float = 4.0
FALLBACK_SL_PCT: float = 2.5

# Intraday same-candle SL+Target edge case (Phase 7 of your spec):
# if High >= Target AND Low <= SL on the same candle, we cannot know
# which was hit first from daily OHLC alone. Conservative default:
STOP_LOSS_HIT_FIRST_ON_AMBIGUOUS_CANDLE: bool = True

# Execution timing rule (Phase 5 of your spec): a signal on candle T
# is never executed at candle T's close. It executes at candle T+1's
# open. No same-candle execution anywhere in backtest or paper engine.
EXECUTION_RULE: str = "NEXT_CANDLE_OPEN"

# ======================================================================
# 4. CHARGES — single source of truth
# ======================================================================
# These are the exact rates already used in the old app.py /
# auto_trade_bot.py (Upstox equity delivery). Consolidated here so
# core/charges.py (Phase H) has exactly ONE place to read from,
# instead of 3 separate calculate_charges() implementations that had
# drifted out of sync with each other (data_loader.py's version was
# a flat 0.12% and did not match these at all).
BROKERAGE_PCT: float = 0.0          # Upstox: free equity delivery
STT_PCT: float = 0.001              # Securities Transaction Tax: 0.1% of buy+sell value
EXCHANGE_TXN_PCT: float = 0.0000335  # NSE transaction charge: 0.00335%
SEBI_PCT: float = 0.000001          # SEBI turnover fee: 0.0001%
GST_PCT: float = 0.18               # 18% GST on (brokerage + exchange + SEBI charges)
STAMP_DUTY_PCT: float = 0.00015     # 0.015% of buy-side value only
SLIPPAGE_PCT: float = 0.02          # 0.02% assumed slippage on both legs

# ======================================================================
# 5. MARKET HOURS & TIMEZONE
# ======================================================================
TIMEZONE: str = "Asia/Kolkata"

MARKET_PRE_OPEN: dt.time = dt.time(9, 0)
MARKET_OPEN: dt.time = dt.time(9, 15)
MARKET_CLOSE: dt.time = dt.time(15, 30)

# ======================================================================
# 6. NSE TRADING HOLIDAYS — 2022 through 2026
# ======================================================================
# Sources: NSE India official circulars (Capital Market Segment):
#   2022 -> NSE/CMTR/50560, Dec 10, 2021
#   2023 -> NSE/CMTR/54757, Dec 08, 2022
#   2024 -> NSE/CMTR/59722, Dec 12, 2023  (+ one ad-hoc holiday added
#           mid-year: Jan 22, 2024, Maharashtra state holiday for the
#           Ram Mandir consecration — NSE observed it too, confirmed
#           via contemporaneous news reports; it was NOT in the
#           original December circular, so don't be surprised it's
#           "extra" compared to that PDF)
#   2025 -> NSE/CMTR/65587, Dec 13, 2024
#   2026 -> NSE/CMTR/71775, Dec 12, 2025
# https://nsearchives.nseindia.com/content/circulars/
#
# 2022-2026 covers a full 5-year backtest window run any time in 2026
# (your Phase 6 requirement). Add 2021 the same way if you ever need
# to backtest further back.
#
# IMPORTANT: this list must be updated every December when NSE
# publishes the next year's circular. The old GitHub Actions workflow
# only checked for weekends — it had NO holiday awareness at all,
# meaning the bot would try to fetch/trade on days like Diwali or
# Republic Day and could act on stale data. This dict is the fix.
#
# Keyed by year so future years can be added without touching old
# ones, and so is_trading_day() below can raise a clear error instead
# of silently treating an un-listed year as "no holidays".
NSE_HOLIDAYS: Dict[int, Set[dt.date]] = {
    2022: {
        dt.date(2022, 1, 26),   # Republic Day
        dt.date(2022, 3, 1),    # Mahashivratri
        dt.date(2022, 3, 18),   # Holi
        dt.date(2022, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti / Mahavir Jayanti
        dt.date(2022, 4, 15),   # Good Friday
        dt.date(2022, 5, 3),    # Id-Ul-Fitr (Ramzan Id)
        dt.date(2022, 8, 9),    # Muharram
        dt.date(2022, 8, 15),   # Independence Day
        dt.date(2022, 8, 31),   # Ganesh Chaturthi
        dt.date(2022, 10, 5),   # Dussehra
        dt.date(2022, 10, 24),  # Diwali - Laxmi Pujan
        dt.date(2022, 10, 26),  # Diwali - Balipratipada
        dt.date(2022, 11, 8),   # Gurunanak Jayanti
    },
    2023: {
        dt.date(2023, 1, 26),   # Republic Day
        dt.date(2023, 3, 7),    # Holi
        dt.date(2023, 3, 30),   # Ram Navami
        dt.date(2023, 4, 4),    # Mahavir Jayanti
        dt.date(2023, 4, 7),    # Good Friday
        dt.date(2023, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti
        dt.date(2023, 5, 1),    # Maharashtra Day
        dt.date(2023, 6, 28),   # Bakri Id
        dt.date(2023, 8, 15),   # Independence Day
        dt.date(2023, 9, 19),   # Ganesh Chaturthi
        dt.date(2023, 10, 2),   # Mahatma Gandhi Jayanti
        dt.date(2023, 10, 24),  # Dussehra
        dt.date(2023, 11, 14),  # Diwali - Balipratipada
        dt.date(2023, 11, 27),  # Gurunanak Jayanti
        dt.date(2023, 12, 25),  # Christmas
    },
    2024: {
        dt.date(2024, 1, 22),   # Ram Mandir consecration — ad-hoc Maharashtra holiday, NSE observed
        dt.date(2024, 1, 26),   # Republic Day
        dt.date(2024, 3, 8),    # Mahashivratri
        dt.date(2024, 3, 25),   # Holi
        dt.date(2024, 3, 29),   # Good Friday
        dt.date(2024, 4, 11),   # Id-Ul-Fitr (Ramadan Eid)
        dt.date(2024, 4, 17),   # Shri Ram Navami
        dt.date(2024, 5, 1),    # Maharashtra Day
        dt.date(2024, 6, 17),   # Bakri Id
        dt.date(2024, 7, 17),   # Muharram
        dt.date(2024, 8, 15),   # Independence Day / Parsi New Year
        dt.date(2024, 10, 2),   # Mahatma Gandhi Jayanti
        dt.date(2024, 11, 1),   # Diwali - Laxmi Pujan
        dt.date(2024, 11, 15),  # Gurunanak Jayanti
        dt.date(2024, 12, 25),  # Christmas
    },
    2025: {
        dt.date(2025, 2, 26),   # Mahashivratri
        dt.date(2025, 3, 14),   # Holi
        dt.date(2025, 3, 31),   # Id-Ul-Fitr (Ramadan Eid)
        dt.date(2025, 4, 10),   # Shri Mahavir Jayanti
        dt.date(2025, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti
        dt.date(2025, 4, 18),   # Good Friday
        dt.date(2025, 5, 1),    # Maharashtra Day
        dt.date(2025, 8, 15),   # Independence Day
        dt.date(2025, 8, 27),   # Ganesh Chaturthi
        dt.date(2025, 10, 2),   # Mahatma Gandhi Jayanti / Dussehra
        dt.date(2025, 10, 21),  # Diwali Laxmi Pujan
        dt.date(2025, 10, 22),  # Diwali - Balipratipada
        dt.date(2025, 11, 5),   # Prakash Gurpurb Sri Guru Nanak Dev
        dt.date(2025, 12, 25),  # Christmas
    },
    2026: {
        dt.date(2026, 1, 26),   # Republic Day
        dt.date(2026, 3, 3),    # Holi
        dt.date(2026, 3, 26),   # Shri Ram Navami
        dt.date(2026, 3, 31),   # Shri Mahavir Jayanti
        dt.date(2026, 4, 3),    # Good Friday
        dt.date(2026, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti
        dt.date(2026, 5, 1),    # Maharashtra Day
        dt.date(2026, 5, 28),   # Bakri Id
        dt.date(2026, 6, 26),   # Muharram
        dt.date(2026, 9, 14),   # Ganesh Chaturthi
        dt.date(2026, 10, 2),   # Mahatma Gandhi Jayanti
        dt.date(2026, 10, 20),  # Dussehra
        dt.date(2026, 11, 10),  # Diwali - Balipratipada
        dt.date(2026, 11, 24),  # Prakash Gurpurb Sri Guru Nanak Dev
        dt.date(2026, 12, 25),  # Christmas
    },
}


def is_market_holiday(date: dt.date) -> bool:
    """
    True if `date` is a declared NSE trading holiday.
    Raises ValueError if the year isn't in NSE_HOLIDAYS yet, so a
    missing yearly update fails loudly instead of silently assuming
    "no holidays this year".
    """
    if date.year not in NSE_HOLIDAYS:
        raise ValueError(
            f"NSE_HOLIDAYS has no entry for {date.year}. "
            f"Add that year's holiday list to config/trading_config.py "
            f"(check https://www.nseindia.com for the official circular) "
            f"before running the bot in {date.year}."
        )
    return date in NSE_HOLIDAYS[date.year]


def is_trading_day(date: dt.date) -> bool:
    """True if the market is open on `date` — not a weekend, not a holiday."""
    if date.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    return not is_market_holiday(date)


# ======================================================================
# 7. SIGNAL ENGINE WEIGHTS — configurable, not blindly hardcoded
# ======================================================================
# Final score = sum of (component_score * weight) for each factor
# below, normalised to 0-100. These starting weights are a reasonable
# baseline, NOT a statistically validated result. Per your Phase 24/25
# requirement, these should eventually be tuned using walk-forward
# validation on out-of-sample data — not by eyeballing one backtest.
SIGNAL_WEIGHTS: Dict[str, float] = {
    "trend": 0.25,       # EMA/price structure alignment
    "momentum": 0.20,    # MACD / RSI
    "volatility": 0.15,  # ATR-based regime fit
    "volume": 0.15,      # volume confirmation
    "market_regime": 0.15,  # NIFTY / sector trend alignment
    "relative_strength": 0.10,  # stock vs sector/index
}
assert abs(sum(SIGNAL_WEIGHTS.values()) - 1.0) < 1e-9, (
    "SIGNAL_WEIGHTS must sum to 1.0 — check config/trading_config.py"
)
