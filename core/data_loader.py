"""
Gandiv AI Trading Terminal — core/data_loader.py

Purpose
-------
THE single data engine. Every other module (scanner, signal engine,
backtester, paper engine, GitHub Actions bot) fetches OHLCV data
through this file — never by calling yfinance directly.

Audit findings this file fixes
--------------------------------
  * Old code had 3 separate fetch_technical_data() implementations
    (data_loader.py, app.py's local copy, auto_trade_bot.py's
    fetch_advanced_technical_data) with different windows, different
    caching (or none), and — critically — different candle-index
    conventions (some used iloc[-1] / forming candle, some iloc[-2]).
  * app.py's scanner re-fetched data on every Streamlit rerun with no
    caching at all, risking yfinance rate limits.
  * No retry/backoff on API failures anywhere.
  * No stale-data or missing-candle detection anywhere.

The completed-candle rule
---------------------------
Per your Phase 5 requirement: SIGNAL = COMPLETED CANDLE ONLY.

This file enforces that split explicitly with two different function
families so it is structurally impossible to accidentally feed a
forming candle into a signal:

  * get_completed_ohlcv()  -> for indicators / signals / backtesting.
                               The last row is ALWAYS a fully closed
                               trading day. If today's candle is still
                               forming (market open, data fetched
                               mid-day), it is dropped.

  * get_live_price()        -> for UI display / "current price" only.
                               This is explicitly allowed to return
                               today's forming candle. Never pass this
                               into an indicator or scoring function.

Caching
-------
An in-memory (per-process) cache keyed by (symbol, period, interval).
This is intentionally NOT Streamlit's st.cache_data, because this
module must also run standalone inside the GitHub Actions bot where
no Streamlit runtime exists. Each process (one Streamlit session, one
GitHub Actions run) gets its own cache — that is sufficient to stop
the "50 stocks re-downloaded on every button click" problem inside a
single session, which was the actual Phase 8 complaint.
"""

from __future__ import annotations

import datetime as dt
import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf

from config.trading_config import TIMEZONE, MARKET_OPEN, MARKET_CLOSE, is_trading_day

logger = logging.getLogger(__name__)

# ======================================================================
# CACHE
# ======================================================================
_CACHE_TTL_SECONDS: int = 300  # 5 minutes — see module docstring
_cache: Dict[str, "CacheEntry"] = {}


@dataclass
class CacheEntry:
    df: pd.DataFrame
    fetched_at: float  # time.time()


def _cache_key(symbol: str, period: str, interval: str) -> str:
    return f"{symbol}|{period}|{interval}"


def clear_cache() -> None:
    """Manual cache clear — useful for tests and for a UI 'refresh data' button."""
    _cache.clear()


# ======================================================================
# LOW-LEVEL FETCH (with retry/backoff)
# ======================================================================
_MAX_RETRIES: int = 3
_BACKOFF_BASE_SECONDS: float = 1.0


def _fetch_raw(symbol: str, period: str, interval: str) -> Optional[pd.DataFrame]:
    """
    One retrying, logged call to yfinance for a single symbol.
    Returns None (never raises) if all retries fail — callers must
    handle None, which is different from "empty but valid" data.
    """
    last_error: Optional[Exception] = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval, auto_adjust=True)
            if df is None or df.empty:
                raise ValueError(f"yfinance returned empty data for {symbol}")
            return df
        except Exception as exc:  # noqa: BLE001 — intentional, bounded retry boundary
            last_error = exc
            logger.warning(
                "data_loader._fetch_raw: attempt %d/%d failed | symbol=%s | error=%s",
                attempt, _MAX_RETRIES, symbol, exc,
            )
            if attempt < _MAX_RETRIES:
                time.sleep(_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))

    logger.error(
        "data_loader._fetch_raw: all %d attempts failed | symbol=%s | last_error=%s",
        _MAX_RETRIES, symbol, last_error,
    )
    return None


def _is_today_forming(df: pd.DataFrame) -> bool:
    """
    True if the last row of df is TODAY's candle and the market is
    still within trading hours right now (IST) — i.e. that row has
    not fully closed yet.
    """
    if df.empty:
        return False

    last_ts = df.index[-1]
    last_date = last_ts.date() if hasattr(last_ts, "date") else last_ts

    now_ist = dt.datetime.now(dt.timezone.utc).astimezone(
        dt.timezone(dt.timedelta(hours=5, minutes=30))
    )
    today_ist = now_ist.date()

    if last_date != today_ist:
        return False  # last row is a previous day -> already fully closed

    current_time = now_ist.time()
    return MARKET_OPEN <= current_time < MARKET_CLOSE


# ======================================================================
# PUBLIC API — completed-candle path (use this for signals/backtests)
# ======================================================================
def get_completed_ohlcv(
    symbol: str,
    period: str = "1y",
    interval: str = "1d",
    use_cache: bool = True,
) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV data with the last row GUARANTEED to be a fully
    completed trading candle. If the most recent row is today's
    still-forming candle, it is dropped.

    This is the ONLY function the indicator engine, signal engine,
    and backtester are allowed to call.

    Returns None if data could not be fetched after retries.
    """
    key = _cache_key(symbol, period, interval)

    if use_cache and key in _cache:
        entry = _cache[key]
        if time.time() - entry.fetched_at < _CACHE_TTL_SECONDS:
            df = entry.df
        else:
            df = _fetch_raw(symbol, period, interval)
            if df is None:
                return None
            _cache[key] = CacheEntry(df=df, fetched_at=time.time())
    else:
        df = _fetch_raw(symbol, period, interval)
        if df is None:
            return None
        if use_cache:
            _cache[key] = CacheEntry(df=df, fetched_at=time.time())

    if interval == "1d" and _is_today_forming(df):
        df = df.iloc[:-1]

    if df.empty:
        logger.warning(
            "data_loader.get_completed_ohlcv: no completed candles left | symbol=%s",
            symbol,
        )
        return None

    return df


def get_completed_batch(
    symbols: List[str],
    period: str = "1y",
    interval: str = "1d",
    use_cache: bool = True,
) -> Dict[str, pd.DataFrame]:
    """
    Batch version of get_completed_ohlcv() for scanning the whole
    universe efficiently. Uses yfinance's multi-ticker download
    (fewer HTTP round-trips than one-symbol-at-a-time) for whichever
    symbols are not already cached, then applies the same
    completed-candle trimming to every result.

    Returns {symbol: DataFrame} — symbols that failed to fetch are
    simply absent from the result (check for missing keys rather
    than expecting an entry for every requested symbol).
    """
    results: Dict[str, pd.DataFrame] = {}
    to_download: List[str] = []

    if use_cache:
        for symbol in symbols:
            key = _cache_key(symbol, period, interval)
            entry = _cache.get(key)
            if entry and (time.time() - entry.fetched_at < _CACHE_TTL_SECONDS):
                results[symbol] = entry.df
            else:
                to_download.append(symbol)
    else:
        to_download = list(symbols)

    if to_download:
        try:
            raw = yf.download(
                tickers=to_download,
                period=period,
                interval=interval,
                group_by="ticker",
                auto_adjust=True,
                threads=True,
                progress=False,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "data_loader.get_completed_batch: batch download failed | "
                "symbols=%s | error=%s", to_download, exc,
            )
            raw = None

        if raw is not None and not raw.empty:
            for symbol in to_download:
                try:
                    if len(to_download) == 1:
                        df = raw  # yf.download does not add a ticker level for a single symbol
                    else:
                        df = raw[symbol].dropna(how="all")
                    if df is None or df.empty:
                        raise ValueError("empty frame for symbol in batch result")
                    _cache[_cache_key(symbol, period, interval)] = CacheEntry(
                        df=df, fetched_at=time.time()
                    )
                    results[symbol] = df
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "data_loader.get_completed_batch: symbol missing from batch "
                        "result, falling back to single fetch | symbol=%s | error=%s",
                        symbol, exc,
                    )
                    single = _fetch_raw(symbol, period, interval)
                    if single is not None:
                        _cache[_cache_key(symbol, period, interval)] = CacheEntry(
                            df=single, fetched_at=time.time()
                        )
                        results[symbol] = single
        else:
            # Whole batch call failed — fall back to per-symbol fetch
            # so one bad symbol/network blip doesn't blank the entire
            # scan.
            for symbol in to_download:
                single = _fetch_raw(symbol, period, interval)
                if single is not None:
                    _cache[_cache_key(symbol, period, interval)] = CacheEntry(
                        df=single, fetched_at=time.time()
                    )
                    results[symbol] = single

    # Apply completed-candle trimming to everything, cached or fresh.
    final: Dict[str, pd.DataFrame] = {}
    for symbol, df in results.items():
        trimmed = df.iloc[:-1] if (interval == "1d" and _is_today_forming(df)) else df
        if not trimmed.empty:
            final[symbol] = trimmed

    return final


# ======================================================================
# PUBLIC API — live price path (UI display ONLY, never for signals)
# ======================================================================
def get_live_price(symbol: str) -> Optional[float]:
    """
    Latest available price INCLUDING today's still-forming candle.
    For "current price" display in the UI only.

    Do NOT use this for indicator calculation, scoring, or any signal
    logic — use get_completed_ohlcv() for that. Mixing this into a
    signal is exactly the look-ahead-adjacent bug flagged in the
    Phase 1 audit (iloc[-1] vs iloc[-2] inconsistency).
    """
    df = _fetch_raw(symbol, period="5d", interval="1d")
    if df is None or df.empty:
        return None
    return float(df["Close"].iloc[-1])


# ======================================================================
# DATA QUALITY CHECKS
# ======================================================================
def is_data_stale(df: pd.DataFrame, as_of: Optional[dt.date] = None) -> bool:
    """
    True if the most recent row in df is older than the last expected
    trading day. Use this after get_completed_ohlcv() to detect a
    yfinance outage or a delisted/halted symbol instead of silently
    trading on old data.
    """
    if df is None or df.empty:
        return True

    as_of = as_of or dt.datetime.now(
        dt.timezone(dt.timedelta(hours=5, minutes=30))
    ).date()

    expected_last_trading_day = as_of
    while not is_trading_day(expected_last_trading_day):
        expected_last_trading_day -= dt.timedelta(days=1)

    # If "today" is itself a trading day but still before market open,
    # the correct expectation is the previous completed trading day.
    now_ist = dt.datetime.now(
        dt.timezone(dt.timedelta(hours=5, minutes=30))
    )
    if as_of == now_ist.date() and now_ist.time() < MARKET_OPEN:
        expected_last_trading_day -= dt.timedelta(days=1)
        while not is_trading_day(expected_last_trading_day):
            expected_last_trading_day -= dt.timedelta(days=1)

    last_ts = df.index[-1]
    last_date = last_ts.date() if hasattr(last_ts, "date") else last_ts

    return last_date < expected_last_trading_day


def detect_missing_candles(df: pd.DataFrame) -> List[dt.date]:
    """
    Return a list of expected-but-missing trading-day dates within the
    span of df (gaps that are NOT weekends/holidays — i.e. genuine
    data holes, such as a temporary yfinance outage).
    """
    if df is None or df.empty:
        return []

    start = df.index[0].date() if hasattr(df.index[0], "date") else df.index[0]
    end = df.index[-1].date() if hasattr(df.index[-1], "date") else df.index[-1]
    present_dates = {
        (ts.date() if hasattr(ts, "date") else ts) for ts in df.index
    }

    missing: List[dt.date] = []
    current = start
    while current <= end:
        if is_trading_day(current) and current not in present_dates:
            missing.append(current)
        current += dt.timedelta(days=1)

    return missing
