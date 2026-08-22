"""
Gandiv AI Trading Terminal — strategy/unified_strategy.py

Purpose
-------
THE single signal engine. This is the architectural centerpiece your
master prompt asked for:

    ONE DATA ENGINE -> ONE INDICATOR ENGINE -> ONE STRATEGY ENGINE
                                                       |
                                    ------------------------------------
                                    |                |                |
                                BACKTEST           PAPER          FUTURE LIVE

Backtest, paper trading, and any future live engine all call
generate_signal() from this exact file. There is no second copy of
this logic anywhere else — that duplication (with silently drifted
formulas) is the #1 problem the Round 2 audit found in the old code.

Purity contract (important for correctness)
----------------------------------------------
generate_signal() is a PURE function: given the same completed-candle
data, the same market regime, and the same weights, it always returns
the same SignalResult. It does not fetch data, does not know what day
"today" is, does not touch any file or network. This is what makes it
safe to reuse identically inside a backtest loop (iterating through
history) and inside a live paper-trading run (called once per symbol
per day) without behaving differently in the two contexts.

Strategy engine vs risk engine — a hard boundary
----------------------------------------------------
Per your Phase 11 requirement, this file NEVER checks position limits,
available cash, sector exposure, or daily loss limits. It only answers
"is this a good signal, on its own technical merits?". Whether that
signal is ALLOWED to become a trade is core/risk_engine.py's job
(Phase F, not yet built) — this file must stay ignorant of portfolio
state so the two concerns can never accidentally merge.

Completed-candle / next-candle-execution contract
------------------------------------------------------
The input DataFrame's last row is treated as candle T (fully closed —
enforced by core/data_loader.get_completed_ohlcv(), not by this file).
generate_signal() evaluates the signal AS OF that close. It is the
caller's (backtester's / paper engine's) responsibility to execute at
T+1's open, never at T's own close — this file has no opinion on
execution price at all, only on the signal itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from config.trading_config import (
    SIGNAL_WEIGHTS,
    MIN_SIGNAL_SCORE,
    ATR_SL_MULTIPLIER,
    ATR_TARGET_MULTIPLIER,
    FALLBACK_SL_PCT,
    FALLBACK_TARGET_PCT,
)
from core.indicators import compute_all_indicators
from core.market_regime import RegimeResult, classify_regime, regime_alignment_score


# ======================================================================
# RESULT TYPE
# ======================================================================
@dataclass
class SignalResult:
    symbol: str
    as_of_date: object          # the completed candle's date this signal is based on
    signal: str                  # "BUY" | "NO_BUY"
    score: float                 # final weighted score, 0-100
    component_scores: Dict[str, float] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)

    # Reference numbers for downstream sizing/exit — NOT execution
    # prices. The caller decides the actual fill (T+1 open, with
    # slippage) using core/charges.py and the paper/backtest engines.
    reference_close: float = 0.0
    atr: float = 0.0
    suggested_sl: float = 0.0
    suggested_target: float = 0.0


# ======================================================================
# COMPONENT SCORERS — each returns 0-100, each independently testable
# ======================================================================
def score_trend(row: pd.Series) -> float:
    """
    Trend component: reward Close > EMA20 > EMA50 (clean bullish
    stack) and penalize the inverse. Partial credit for a mixed
    structure, scaled by how far price sits from EMA50.
    """
    close, ema20, ema50 = row["Close"], row["ema_20"], row["ema_50"]
    if pd.isna(ema20) or pd.isna(ema50) or ema50 == 0:
        return 50.0  # neutral — not enough history to judge yet

    if close > ema20 > ema50:
        # Bonus for how far above ema50 (capped) — a fresh breakout
        # scores higher than a stock that's been extended for a while.
        extension_pct = (close - ema50) / ema50 * 100
        return float(np.clip(70 + extension_pct * 3, 70, 100))

    if close < ema20 < ema50:
        return float(np.clip(30 - abs(close - ema50) / ema50 * 100 * 3, 0, 30))

    # Mixed structure — scale from the relative position
    position = (close - ema50) / abs(ema20 - ema50) if ema20 != ema50 else 0
    return float(np.clip(50 + position * 20, 0, 100))


def score_momentum(row: pd.Series) -> float:
    """
    Momentum component: RSI in a healthy "room to run" zone (45-65)
    scores highest — not overbought, not oversold, not stalling.
    MACD histogram > 0 and rising adds confirmation.
    """
    rsi = row.get("rsi", np.nan)
    macd_hist = row.get("macd_histogram", np.nan)

    if pd.isna(rsi):
        rsi_score = 50.0
    elif 45 <= rsi <= 65:
        rsi_score = 100.0
    elif rsi > 65:
        # Overbought — score decays as RSI pushes further past 65
        rsi_score = float(np.clip(100 - (rsi - 65) * 4, 0, 100))
    else:  # rsi < 45
        # Below the sweet spot but not necessarily bad — decays toward
        # oversold territory
        rsi_score = float(np.clip(100 - (45 - rsi) * 2.5, 0, 100))

    macd_score = 50.0
    if not pd.isna(macd_hist):
        macd_score = 70.0 if macd_hist > 0 else 30.0

    return float(0.7 * rsi_score + 0.3 * macd_score)


def score_volatility(row: pd.Series, atr_percentile: Optional[float]) -> float:
    """
    Volatility-regime-fit component: a stock trading in its OWN
    "normal" volatility band (neither unusually quiet nor unusually
    wild, relative to its own recent history) scores highest. This is
    "does this stock's current volatility make it tradeable right
    now", not "is this stock generally volatile" — see
    core/market_regime.py for the percentile-ranking logic.
    """
    if atr_percentile is None or pd.isna(atr_percentile):
        return 50.0
    # Peak score at the 50th percentile, decaying toward both extremes.
    distance_from_mid = abs(atr_percentile - 50)
    return float(np.clip(100 - distance_from_mid * 1.4, 0, 100))


def score_volume(row: pd.Series) -> float:
    """
    Volume confirmation component: reward above-average volume on the
    completed candle (participation confirms the move); a ratio of
    ~1.0 (average) is treated as neutral, well below average is
    penalized (low-conviction move).
    """
    ratio = row.get("volume_ratio", np.nan)
    if pd.isna(ratio):
        return 50.0
    if ratio >= 2.0:
        return 100.0
    if ratio >= 1.0:
        # Linear scale 1.0x -> 60, 2.0x -> 100
        return float(60 + (ratio - 1.0) * 40)
    # Below-average volume — linear scale down to 20 at 0.3x and below
    return float(np.clip(60 * (ratio / 1.0), 20, 60))


def score_relative_strength(stock_df: pd.DataFrame, index_df: Optional[pd.DataFrame], lookback: int = 20) -> float:
    """
    Relative strength component: stock's trailing `lookback`-day
    return compared to the index's (NIFTY) return over the same
    window. Outperformance scores above 50, underperformance below.

    Returns 50 (neutral) if no index data was supplied — this
    component becomes a no-op rather than crashing when the caller
    hasn't fetched NIFTY data (e.g. a quick single-stock check).
    """
    if index_df is None or len(stock_df) < lookback + 1 or len(index_df) < lookback + 1:
        return 50.0

    stock_return = (stock_df["Close"].iloc[-1] / stock_df["Close"].iloc[-lookback - 1] - 1) * 100
    index_return = (index_df["Close"].iloc[-1] / index_df["Close"].iloc[-lookback - 1] - 1) * 100

    outperformance = stock_return - index_return
    # +10 percentage points of outperformance -> score 100; -10 -> score 0
    return float(np.clip(50 + outperformance * 5, 0, 100))


# ======================================================================
# THE SIGNAL ENGINE
# ======================================================================
def generate_signal(
    symbol: str,
    completed_ohlcv: pd.DataFrame,
    index_completed_ohlcv: Optional[pd.DataFrame] = None,
    weights: Optional[Dict[str, float]] = None,
    min_score: Optional[float] = None,
) -> SignalResult:
    """
    THE single entry point for signal generation. Called identically
    by the backtester (once per historical candle, walking forward)
    and by the paper-trading engine (once per symbol per trading day).

    Parameters
    ----------
    symbol : the stock symbol (for labeling the result only)
    completed_ohlcv : completed-candle OHLCV for the stock, from
        core/data_loader.get_completed_ohlcv(). Must have enough
        history for the indicators to warm up (>= ~60 rows recommended).
    index_completed_ohlcv : completed-candle OHLCV for NIFTY (or
        whatever market index you use), same contract. Optional —
        if omitted, market_regime and relative_strength components
        fall back to neutral (50) instead of failing.
    weights : override for config.trading_config.SIGNAL_WEIGHTS
        (mainly for testing / walk-forward weight tuning).
    min_score : override for config.trading_config.MIN_SIGNAL_SCORE.

    Returns
    -------
    SignalResult — never raises for "normal" bad-but-valid inputs
    (e.g. too little history); returns a NO_BUY with an explanatory
    reason instead. Only truly malformed input (missing OHLCV columns)
    will raise, since that indicates a caller bug, not a market
    condition.
    """
    weights = weights or SIGNAL_WEIGHTS
    min_score = MIN_SIGNAL_SCORE if min_score is None else min_score

    required_cols = {"Open", "High", "Low", "Close", "Volume"}
    if not required_cols.issubset(completed_ohlcv.columns):
        raise ValueError(
            f"generate_signal: completed_ohlcv missing required columns "
            f"{required_cols - set(completed_ohlcv.columns)} for symbol={symbol}"
        )

    if len(completed_ohlcv) < 55:
        return SignalResult(
            symbol=symbol,
            as_of_date=completed_ohlcv.index[-1] if len(completed_ohlcv) else None,
            signal="NO_BUY",
            score=0.0,
            reasons=[f"Insufficient history ({len(completed_ohlcv)} candles, need >= 55 for EMA50 warmup)"],
        )

    enriched = compute_all_indicators(completed_ohlcv)
    last_row = enriched.iloc[-1]

    # --- Market regime (optional — neutral fallback if no index data) ---
    market_regime: Optional[RegimeResult] = None
    stock_regime = classify_regime(completed_ohlcv)
    if index_completed_ohlcv is not None and len(index_completed_ohlcv) >= 55:
        market_regime = classify_regime(index_completed_ohlcv)
        regime_component = regime_alignment_score(stock_regime, market_regime)
    else:
        regime_component = 50.0

    # --- Component scores ---
    components = {
        "trend": score_trend(last_row),
        "momentum": score_momentum(last_row),
        "volatility": score_volatility(last_row, stock_regime.atr_percentile),
        "volume": score_volume(last_row),
        "market_regime": regime_component,
        "relative_strength": score_relative_strength(completed_ohlcv, index_completed_ohlcv),
    }

    missing_weight_keys = set(components) - set(weights)
    if missing_weight_keys:
        raise ValueError(
            f"generate_signal: SIGNAL_WEIGHTS is missing keys {missing_weight_keys} "
            f"used by the component scorers — check config/trading_config.py"
        )

    final_score = sum(components[k] * weights[k] for k in components)

    signal = "BUY" if final_score >= min_score else "NO_BUY"

    reasons: List[str] = [
        f"Trend={components['trend']:.0f} (stock regime: {stock_regime.label})",
        f"Momentum={components['momentum']:.0f} (RSI={last_row.get('rsi', float('nan')):.1f})",
        f"Volatility fit={components['volatility']:.0f} (ATR percentile={stock_regime.atr_percentile:.0f})",
        f"Volume={components['volume']:.0f} (ratio={last_row.get('volume_ratio', float('nan')):.2f}x)",
        f"Market regime={components['market_regime']:.0f}"
        + (f" (market: {market_regime.label})" if market_regime else " (no index data supplied)"),
        f"Relative strength={components['relative_strength']:.0f}",
        f"Final weighted score={final_score:.1f} vs threshold={min_score}",
    ]

    # --- ATR-based SL/Target reference (Phase 9 sizing formula input) ---
    atr = last_row.get("atr", np.nan)
    close = float(last_row["Close"])
    if pd.isna(atr) or atr <= 0:
        # Fallback to fixed % if ATR isn't available yet (e.g. very
        # short history) — matches config.trading_config's documented
        # fallback behaviour, not a silent divergence from it.
        suggested_sl = close * (1 - FALLBACK_SL_PCT / 100)
        suggested_target = close * (1 + FALLBACK_TARGET_PCT / 100)
        atr = 0.0
        reasons.append("ATR unavailable — used fallback fixed-% SL/Target")
    else:
        suggested_sl = close - (atr * ATR_SL_MULTIPLIER)
        suggested_target = close + (atr * ATR_TARGET_MULTIPLIER)

    return SignalResult(
        symbol=symbol,
        as_of_date=completed_ohlcv.index[-1],
        signal=signal,
        score=round(final_score, 2),
        component_scores={k: round(v, 2) for k, v in components.items()},
        reasons=reasons,
        reference_close=close,
        atr=round(float(atr), 4),
        suggested_sl=round(suggested_sl, 2),
        suggested_target=round(suggested_target, 2),
    )
