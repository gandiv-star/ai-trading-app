"""
Gandiv AI Trading Terminal — core/market_regime.py

Purpose
-------
Classify the "regime" of any completed-candle OHLCV series (the NIFTY
index, a sector, or a single stock) along three independent axes:

  1. DIRECTION  — Bullish / Bearish / Neutral   (EMA structure)
  2. STRENGTH   — Weak / Developing / Strong    (ADX)
  3. VOLATILITY — Low / Normal / High           (ATR percentile vs its
                                                  own recent history)

Per your Phase 4 requirement, this file does NOT fetch data itself —
it classifies whatever completed-candle DataFrame it is given. The
caller (strategy engine, scanner, UI) is responsible for fetching via
core/data_loader.py and computing indicators via core/indicators.py
first. This keeps market_regime.py fetch-agnostic and easy to unit
test with synthetic data, and avoids yet another module making its
own yfinance calls (the exact problem Phase 1 flagged).

How this feeds the strategy engine
------------------------------------
strategy/unified_strategy.py calls classify_regime() on:
  * the NIFTY index (market-wide regime)
  * the stock itself (stock regime)
and uses regime_alignment_score() to turn "does this stock's trend
agree with the market's trend" into the market_regime component of
the final signal score. Sector-level regime is supported the same
way via aggregate_regime() if the caller has sector-peer data handy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from core.indicators import calculate_ema, calculate_atr, calculate_adx


# ======================================================================
# RESULT TYPE
# ======================================================================
@dataclass
class RegimeResult:
    direction: str      # "Bullish" | "Bearish" | "Neutral"
    strength: str        # "Weak" | "Developing" | "Strong"
    volatility: str       # "Low" | "Normal" | "High"
    label: str            # human-readable combined label, e.g. "Strong Bullish Trend (High Volatility)"
    direction_score: float  # -1.0 (fully bearish) .. +1.0 (fully bullish)
    adx: float
    atr_percentile: float   # 0-100, current ATR's rank vs its own trailing history


# ======================================================================
# THRESHOLDS — configurable in one place, not scattered magic numbers
# ======================================================================
ADX_WEAK_THRESHOLD: float = 20.0
ADX_STRONG_THRESHOLD: float = 25.0

ATR_LOW_PERCENTILE: float = 30.0
ATR_HIGH_PERCENTILE: float = 70.0
ATR_LOOKBACK: int = 100  # trading days used to rank current ATR


# ======================================================================
# CLASSIFICATION
# ======================================================================
def _classify_direction(df: pd.DataFrame, ema_fast: int = 20, ema_slow: int = 50, sensitivity: float = 3.0) -> float:
    """
    Direction score in [-1, +1], CONTINUOUS (not a hard threshold on
    EMA ordering) — this matters because a binary "close>ema20>ema50
    => +1.0" rule treats a genuinely flat, noisy stock (where the two
    EMAs sit a fraction of a percent apart, purely from noise) exactly
    the same as a stock in a clean, wide, established uptrend. That
    is wrong: a trivial EMA gap should score near-neutral, not fully
    bullish.

    Formula: tanh( (close - ema_slow) / ema_slow * 100 / sensitivity ).
    `sensitivity` controls how many percent above/below EMA50 it takes
    to approach a saturated +-1 score (default 3.0 means roughly a
    +-6-9% move away from EMA50 saturates the score). This makes the
    direction score reflect the SIZE of the trend, not merely its sign.
    """
    close = df["Close"]
    ema_s = calculate_ema(close, ema_slow)

    last_close = close.iloc[-1]
    last_ema_s = ema_s.iloc[-1]

    if pd.isna(last_ema_s):
        return 0.0
    if last_ema_s <= 0:
        # A non-positive EMA means the series itself is degenerate
        # (should never happen for a real, currently-listed stock —
        # prices are always > 0 — but guards against feeding this
        # function synthetic/corrupted data without a sign-flip bug:
        # dividing by a negative denominator would otherwise invert
        # a genuine downtrend into a false "bullish" reading).
        return -1.0

    pct_from_slow_ema = (last_close - last_ema_s) / last_ema_s * 100
    return float(np.tanh(pct_from_slow_ema / sensitivity))


def _classify_strength(df: pd.DataFrame, period: int = 14) -> tuple[str, float]:
    """Returns (strength_label, adx_value) using Wilder's ADX."""
    adx_df = calculate_adx(df, period)
    adx_value = adx_df["adx"].iloc[-1]

    if pd.isna(adx_value):
        return "Weak", 0.0
    if adx_value < ADX_WEAK_THRESHOLD:
        return "Weak", float(adx_value)
    if adx_value < ADX_STRONG_THRESHOLD:
        return "Developing", float(adx_value)
    return "Strong", float(adx_value)


def _classify_volatility(df: pd.DataFrame, period: int = 14) -> tuple[str, float]:
    """
    Returns (volatility_label, atr_percentile). The current ATR is
    ranked against its own trailing ATR_LOOKBACK-day history (percentile
    rank, 0-100) rather than compared to a fixed number — this makes
    the classification meaningful across stocks with very different
    absolute price levels and baseline volatility.
    """
    atr = calculate_atr(df, period)
    recent = atr.tail(ATR_LOOKBACK).dropna()

    if len(recent) < max(20, period * 2):
        return "Normal", 50.0  # not enough history to rank confidently

    current = recent.iloc[-1]
    percentile = float((recent < current).mean() * 100)

    if percentile < ATR_LOW_PERCENTILE:
        return "Low", percentile
    if percentile > ATR_HIGH_PERCENTILE:
        return "High", percentile
    return "Normal", percentile


def classify_regime(df: pd.DataFrame, ema_fast: int = 20, ema_slow: int = 50) -> RegimeResult:
    """
    Classify a single completed-candle OHLCV DataFrame (NIFTY, a
    sector proxy, or one stock) into direction / strength / volatility.

    Input MUST already be completed-candle data — see the module
    docstring. This function does not fetch or trim anything itself.
    """
    direction_score = _classify_direction(df, ema_fast, ema_slow)
    strength_label, adx_value = _classify_strength(df)
    volatility_label, atr_pct = _classify_volatility(df)

    if direction_score > 0.3:
        direction = "Bullish"
    elif direction_score < -0.3:
        direction = "Bearish"
    else:
        direction = "Neutral"

    if direction == "Neutral" or strength_label == "Weak":
        base_label = "Sideways / Range-bound"
    else:
        base_label = f"{strength_label} {direction} Trend"

    label = f"{base_label} ({volatility_label} Volatility)"

    return RegimeResult(
        direction=direction,
        strength=strength_label,
        volatility=volatility_label,
        label=label,
        direction_score=direction_score,
        adx=adx_value,
        atr_percentile=atr_pct,
    )


# ======================================================================
# ALIGNMENT — how well does a stock's regime agree with the market's?
# ======================================================================
def regime_alignment_score(stock_regime: RegimeResult, market_regime: RegimeResult) -> float:
    """
    Returns a 0-100 alignment score used as the strategy engine's
    "market_regime" component (config.trading_config.SIGNAL_WEIGHTS).

    Logic: reward the stock for trending in the SAME direction as the
    broader market, scaled by how strong the market's own trend is.
    A stock that's bullish while the market is bullish scores high; a
    stock that's bullish while the market is bearish scores low
    (fighting the tape); a genuinely neutral market caps the score at
    a middling value regardless of the stock, since there's no strong
    market tailwind either way.
    """
    market_conviction = abs(market_regime.direction_score)  # 0..1

    if market_regime.direction == "Neutral":
        # No clear market tailwind — score reflects the stock's own
        # direction only, capped at 60 since there's no macro support.
        return float(np.clip(50 + stock_regime.direction_score * 10, 0, 60))

    same_direction = (
        (market_regime.direction == "Bullish" and stock_regime.direction_score > 0)
        or (market_regime.direction == "Bearish" and stock_regime.direction_score < 0)
    )

    agreement = stock_regime.direction_score * market_regime.direction_score  # >0 if same sign
    base = 50 + (agreement * 50)  # ranges roughly 0..100 depending on conviction/agreement
    score = base * (0.5 + 0.5 * market_conviction)  # weaker market trend -> pull toward neutral 50-ish

    return float(np.clip(score, 0, 100))


def aggregate_regime(regimes: Dict[str, RegimeResult]) -> Optional[RegimeResult]:
    """
    Combine several RegimeResults (e.g. every stock in a sector) into
    one representative RegimeResult by averaging direction_score and
    picking the most common strength/volatility label. Used for an
    optional sector-level regime when the caller has already computed
    per-stock regimes (e.g. during a scan) and doesn't want a second
    round of fetching/classification just for the sector view.

    Returns None if given an empty dict.
    """
    if not regimes:
        return None

    values = list(regimes.values())
    avg_direction_score = float(np.mean([r.direction_score for r in values]))
    avg_adx = float(np.mean([r.adx for r in values]))
    avg_atr_pct = float(np.mean([r.atr_percentile for r in values]))

    strengths = [r.strength for r in values]
    volatilities = [r.volatility for r in values]
    strength_label = max(set(strengths), key=strengths.count)
    volatility_label = max(set(volatilities), key=volatilities.count)

    if avg_direction_score > 0.3:
        direction = "Bullish"
    elif avg_direction_score < -0.3:
        direction = "Bearish"
    else:
        direction = "Neutral"

    if direction == "Neutral" or strength_label == "Weak":
        base_label = "Sideways / Range-bound"
    else:
        base_label = f"{strength_label} {direction} Trend"

    return RegimeResult(
        direction=direction,
        strength=strength_label,
        volatility=volatility_label,
        label=f"{base_label} ({volatility_label} Volatility) [aggregate of {len(values)}]",
        direction_score=avg_direction_score,
        adx=avg_adx,
        atr_percentile=avg_atr_pct,
    )
