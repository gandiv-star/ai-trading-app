"""
Gandiv AI Trading Terminal — notifications/telegram.py

Purpose
-------
THE single Telegram service (your Phase 17 requirement). Every alert
in the project — trade entry, trade exit, circuit breaker, daily
summary, system error — is sent through this file. There is no
second copy of "how do we talk to Telegram" anywhere else.

Design principles
-------------------
  * Secrets ONLY from config/settings.py (env vars / Streamlit
    secrets) — never hardcoded here, per Phase 28.
  * MUST NEVER crash the caller. A missing token, a network failure,
    or a Telegram API error all result in a logged warning and a
    `False` return — not an exception. Sending a Telegram alert is a
    side effect, not core trading logic; the paper engine must keep
    running correctly whether or not the message actually goes out.
  * Duplicate-alert protection: each alert type builds a `dedup_key`
    (symbol + event + date, generally) so if something calls the same
    alert twice in a short window — e.g. the risk engine rejecting
    every remaining symbol in the universe once a circuit breaker has
    already tripped — only the FIRST one actually sends.
  * Retry with backoff on transient network failures, same pattern as
    core/data_loader.py's yfinance retries — bounded, logged, never a
    silent `except: pass`.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
import time
from typing import Optional, Dict

import requests

from config.settings import get_telegram_bot_token, get_telegram_chat_id

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
_MAX_RETRIES = 3
_BACKOFF_BASE_SECONDS = 1.0
_DEDUP_WINDOW_SECONDS = 300  # 5 minutes — enough to absorb a burst of retries/re-runs

# In-memory only: this resets each process run (each GitHub Actions
# run, each Streamlit session). That is fine — the dedup window is
# short and meant to catch bursts within ONE run, not across days;
# cross-day duplicate protection instead comes from each alert's
# dedup_key including the date, combined with paper/engine.py's own
# duplicate-execution guard (Portfolio.last_processed_date).
_recent_sends: Dict[str, float] = {}


def _purge_expired(now: float) -> None:
    expired = [k for k, t in _recent_sends.items() if now - t > _DEDUP_WINDOW_SECONDS]
    for k in expired:
        del _recent_sends[k]


def _is_duplicate(dedup_key: str) -> bool:
    now = time.time()
    _purge_expired(now)
    return dedup_key in _recent_sends


def _mark_sent(dedup_key: str) -> None:
    _recent_sends[dedup_key] = time.time()


def clear_dedup_cache() -> None:
    """Manual reset — useful for tests."""
    _recent_sends.clear()


# ======================================================================
# LOW-LEVEL SEND
# ======================================================================
def send_telegram_message(text: str, dedup_key: Optional[str] = None, parse_mode: str = "HTML") -> bool:
    """
    THE single function that actually talks to Telegram. Returns True
    only if the message was genuinely sent this call — False for
    "not configured", "duplicate suppressed", or "failed after
    retries". Never raises.
    """
    token = get_telegram_bot_token()
    chat_id = get_telegram_chat_id()
    if not token or not chat_id:
        logger.warning(
            "notifications.telegram: not configured (missing bot token or chat id) — "
            "message not sent: %s", text[:80],
        )
        return False

    if dedup_key and _is_duplicate(dedup_key):
        logger.info("notifications.telegram: duplicate suppressed for key=%s", dedup_key)
        return False

    url = TELEGRAM_API_URL.format(token=token)
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}

    last_error: Optional[str] = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                if dedup_key:
                    _mark_sent(dedup_key)
                return True
            last_error = f"HTTP {response.status_code}: {response.text[:200]}"
        except Exception as exc:  # noqa: BLE001 — intentional, bounded retry boundary
            last_error = str(exc)

        logger.warning(
            "notifications.telegram: attempt %d/%d failed | error=%s",
            attempt, _MAX_RETRIES, last_error,
        )
        if attempt < _MAX_RETRIES:
            time.sleep(_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))

    logger.error("notifications.telegram: all %d attempts failed, message NOT sent | error=%s", _MAX_RETRIES, last_error)
    return False


def send_test_message() -> bool:
    """For a 'Test Telegram Connection' button in the UI."""
    return send_telegram_message(
        f"✅ Gandiv AI Trading Terminal — test message.\nTime: {dt.datetime.now():%Y-%m-%d %H:%M:%S}",
        dedup_key=None,  # a manual test should always attempt to send, never be suppressed
    )


# ======================================================================
# ALERT BUILDERS — one function per alert type from your Phase 17 spec
# ======================================================================
def trade_entry_alert(symbol: str, quantity: int, entry_price: float, stop_loss: float, target: float, score: float) -> bool:
    text = (
        f"🟢 <b>ENTRY</b>\n"
        f"Symbol: {symbol}\n"
        f"Qty: {quantity}\n"
        f"Entry: ₹{entry_price:,.2f}\n"
        f"Stop-Loss: ₹{stop_loss:,.2f}\n"
        f"Target: ₹{target:,.2f}\n"
        f"Signal Score: {score}\n"
        f"Time: {dt.datetime.now():%Y-%m-%d %H:%M}"
    )
    return send_telegram_message(text, dedup_key=f"entry:{symbol}:{dt.date.today()}")


def trade_exit_alert(symbol: str, quantity: int, exit_price: float, exit_reason: str, net_pnl: float) -> bool:
    emoji = "✅" if net_pnl > 0 else "🔴"
    text = (
        f"{emoji} <b>EXIT — {exit_reason}</b>\n"
        f"Symbol: {symbol}\n"
        f"Qty: {quantity}\n"
        f"Exit: ₹{exit_price:,.2f}\n"
        f"Net P&amp;L: ₹{net_pnl:,.2f}\n"
        f"Time: {dt.datetime.now():%Y-%m-%d %H:%M}"
    )
    return send_telegram_message(text, dedup_key=f"exit:{symbol}:{exit_reason}:{dt.date.today()}")


def circuit_breaker_alert(reason: str) -> bool:
    text = f"🚨 <b>CIRCUIT BREAKER TRIPPED</b>\n{reason}\nTime: {dt.datetime.now():%Y-%m-%d %H:%M}"
    return send_telegram_message(text, dedup_key=f"circuit_breaker:{dt.date.today()}")


def daily_summary_alert(
    equity: float, pnl_today: float, open_positions: int, closed_today: int, win_rate_pct: float,
) -> bool:
    emoji = "📈" if pnl_today >= 0 else "📉"
    text = (
        f"{emoji} <b>Daily Summary</b>\n"
        f"Equity: ₹{equity:,.2f}\n"
        f"Today's P&amp;L: ₹{pnl_today:,.2f}\n"
        f"Open Positions: {open_positions}\n"
        f"Trades Closed Today: {closed_today}\n"
        f"Overall Win Rate: {win_rate_pct:.1f}%\n"
        f"Time: {dt.datetime.now():%Y-%m-%d %H:%M}"
    )
    return send_telegram_message(text, dedup_key=f"daily_summary:{dt.date.today()}")


def system_error_alert(module: str, function: str, error: str) -> bool:
    """
    Per Phase 27: every captured error includes module + function +
    a timestamp. Deduplicated on the error's own content (a hash of
    the message) so a repeating error doesn't spam every few minutes,
    but two genuinely DIFFERENT errors both get through.
    """
    error_hash = hashlib.md5(error.encode("utf-8")).hexdigest()[:8]
    text = (
        f"⚠️ <b>SYSTEM ERROR</b>\n"
        f"Module: {module}\n"
        f"Function: {function}\n"
        f"Error: {error[:300]}\n"
        f"Time: {dt.datetime.now():%Y-%m-%d %H:%M}"
    )
    return send_telegram_message(text, dedup_key=f"error:{module}:{function}:{error_hash}")
