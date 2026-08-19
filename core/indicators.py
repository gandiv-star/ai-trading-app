"""
Gandiv AI Trading Terminal — core/indicators.py

Purpose
-------
THE single indicator engine. Every EMA/RSI/MACD/ATR/ADX/Volume
calculation in the whole project goes through this file.

Audit finding this file fixes
-------------------------------
Old code computed indicators in 3 different places (data_loader.py,
app.py, auto_trade_bot.py) with inconsistent windows and, in one
case, a formula that didn't match "standard financial definition"
(a plain SMA-based ATR instead of Wilder's smoothing). This file is
the single, tested replacement.

Input contract
---------------
Every function here expects a DataFrame that has ALREADY been passed
through core/data_loader.get_completed_ohlcv() — i.e. the last row is
a fully completed candle, never a forming one. This module does not
re-check that itself (it has no way to know); enforcing it is
data_loader's job. Columns expected: 'Open', 'High', 'Low', 'Close',
'Volume' (yfinance's standard column names).

Every function returns a pandas Series aligned to the input's index,
so results can be attached back onto the OHLCV DataFrame with
`df['rsi'] = calculate_rsi(df)`.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd


# ======================================================================
# TREND — EMA / SMA
# ======================================================================
def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average — standard definition (span=period)."""
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=period, min_periods=period).mean()


# ======================================================================
# MOMENTUM — RSI (Wilder), MACD
# ======================================================================
def calculate_rsi(df: pd.Series | pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Relative Strength Index, Wilder's original smoothing method
    (not a plain SMA of gains/losses — that is a common shortcut that
    does not match the standard definition traders expect).

    Accepts either a Close price Series directly, or a DataFrame with
    a 'Close' column.
    """
    close = df["Close"] if isinstance(df, pd.DataFrame) else df

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # Wilder smoothing = EWM with alpha = 1/period
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    # Where avg_loss is 0 (no down days at all), RSI is defined as 100.
    rsi = rsi.where(avg_loss != 0, 100)
    return rsi


def calculate_macd(
    df: pd.Series | pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """
    MACD line, signal line, and histogram — standard 12/26/9 EMA
    definition. Returns a DataFrame with columns: macd, signal, histogram.
    """
    close = df["Close"] if isinstance(df, pd.DataFrame) else df

    ema_fast = calculate_ema(close, fast)
    ema_slow = calculate_ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line

    return pd.DataFrame({
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram,
    })


# ======================================================================
# VOLATILITY — ATR (Wilder), True Range
# ======================================================================
def calculate_true_range(df: pd.DataFrame) -> pd.Series:
    """
    True Range = max(
        high - low,
        abs(high - previous_close),
        abs(low - previous_close)
    )
    """
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Average True Range, Wilder's smoothing (RMA) — the standard
    definition. A plain SMA of True Range is a common but non-standard
    shortcut; this uses the correct Wilder method.
    """
    tr = calculate_true_range(df)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


# ======================================================================
# TREND STRENGTH — ADX (Wilder)
# ======================================================================
def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Average Directional Index with +DI / -DI, Wilder's method.
    Returns a DataFrame with columns: plus_di, minus_di, adx.

    ADX measures trend STRENGTH (0-100), not direction. +DI > -DI
    suggests bullish trend pressure and vice versa; ADX itself is
    typically read as: <20 weak/no trend, >25 trending.
    """
    high, low, close = df["High"], df["Low"], df["Close"]

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    plus_dm = pd.Series(plus_dm, index=df.index)
    minus_dm = pd.Series(minus_dm, index=df.index)

    tr = calculate_true_range(df)
    atr = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    plus_di = 100 * (
        plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr
    )
    minus_di = 100 * (
        minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr
    )

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    return pd.DataFrame({"plus_di": plus_di, "minus_di": minus_di, "adx": adx})


# ======================================================================
# VOLUME
# ======================================================================
def calculate_volume_ratio(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """
    Today's (i.e. the latest COMPLETED candle's) volume divided by the
    trailing average volume over `period` days, EXCLUDING today's own
    volume from that average (otherwise a volume spike inflates its
    own baseline, understating how unusual it actually was).

    A value of 2.0 means "today's volume was 2x the recent average".
    """
    volume = df["Volume"]
    avg_volume = volume.shift(1).rolling(window=period, min_periods=period).mean()
    return volume / avg_volume.replace(0, np.nan)


def calculate_rolling_vwap(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """
    Rolling Volume-Weighted Average Price over `period` DAILY candles.

    Caveat: true VWAP is an INTRADAY concept computed from tick/minute
    data within a single session. yfinance daily bars do not provide
    that, so this is a volume-weighted average of daily typical prices
    over a trailing window — useful as a "value area" reference, but
    it is not the same number a broker's intraday VWAP indicator would
    show. Do not present this to the user as session VWAP without that
    distinction.
    """
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
    pv = typical_price * df["Volume"]
    return (
        pv.rolling(window=period, min_periods=period).sum()
        / df["Volume"].rolling(window=period, min_periods=period).sum()
    )


# ======================================================================
# CONVENIENCE — compute everything at once
# ======================================================================
def compute_all_indicators(
    df: pd.DataFrame,
    ema_fast: int = 20,
    ema_slow: int = 50,
    rsi_period: int = 14,
    atr_period: int = 14,
    adx_period: int = 14,
    volume_period: int = 20,
) -> pd.DataFrame:
    """
    Attach every standard indicator this file supports onto a copy of
    the input OHLCV DataFrame and return it. This is the function the
    strategy/signal engine (Phase E) will call.

    Input MUST already be completed-candle-only data from
    core/data_loader.get_completed_ohlcv().
    """
    out = df.copy()

    out[f"ema_{ema_fast}"] = calculate_ema(out["Close"], ema_fast)
    out[f"ema_{ema_slow}"] = calculate_ema(out["Close"], ema_slow)
    out["rsi"] = calculate_rsi(out, rsi_period)

    macd_df = calculate_macd(out)
    out["macd"] = macd_df["macd"]
    out["macd_signal"] = macd_df["signal"]
    out["macd_histogram"] = macd_df["histogram"]

    out["atr"] = calculate_atr(out, atr_period)

    adx_df = calculate_adx(out, adx_period)
    out["plus_di"] = adx_df["plus_di"]
    out["minus_di"] = adx_df["minus_di"]
    out["adx"] = adx_df["adx"]

    out["volume_ratio"] = calculate_volume_ratio(out, volume_period)

    return out
