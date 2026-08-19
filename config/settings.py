"""
Gandiv AI Trading Terminal — config/settings.py

Purpose
-------
Single source of truth for:
  1. Secrets (Telegram, Gemini, future broker tokens) — read ONLY from
     environment variables / Streamlit secrets. Never hardcoded here.
  2. App-level settings (app name, version, timezone, data directory,
     log level).

Why this file exists
---------------------
Old code (auto_trade_bot.py, auto_bot.py, app.py) each read
TELEGRAM_BOT_TOKEN / CHAT_ID / GEMINI_API_KEY independently, with
inconsistent fallback logic. That is now centralised here so every
module (Streamlit app, GitHub Actions bot, backtester) asks this file
for secrets instead of touching os.environ directly.

No secret ever has a literal fallback value in this file. If a secret
is missing, the getter returns None / empty string and the caller
(e.g. notifications/telegram.py) must handle that gracefully — the
app must never crash just because Telegram is not configured.
"""

from __future__ import annotations

import os
from typing import Optional

# --------------------------------------------------------------------
# APP METADATA
# --------------------------------------------------------------------
APP_NAME: str = "Gandiv AI Trading Terminal"
APP_VERSION: str = "6.0.0"  # bumped for the modular rebuild

# --------------------------------------------------------------------
# TIMEZONE
# --------------------------------------------------------------------
# All market-time logic (holidays, candle timing, cron alignment) must
# use this constant instead of a hardcoded "Asia/Kolkata" string
# scattered across files.
TIMEZONE: str = "Asia/Kolkata"

# --------------------------------------------------------------------
# STORAGE PATHS
# --------------------------------------------------------------------
# Kept as a plain relative filename for now (Phase L / storage layer
# will decide the final persistence mechanism — see risk note in the
# Phase 1 audit about Streamlit Cloud's ephemeral filesystem).
DATA_DIR: str = os.environ.get("GANDIV_DATA_DIR", "data")
PORTFOLIO_STATE_FILE: str = os.path.join(DATA_DIR, "gandiv_data.json")
BACKUP_DIR: str = os.path.join(DATA_DIR, "backups")

# --------------------------------------------------------------------
# LOGGING
# --------------------------------------------------------------------
LOG_LEVEL: str = os.environ.get("GANDIV_LOG_LEVEL", "INFO")
LOG_DIR: str = os.path.join(DATA_DIR, "logs")


def _read_secret(key: str) -> Optional[str]:
    """
    Read a secret by name, checking (in order):
      1. Environment variable (works in GitHub Actions and most hosts)
      2. Streamlit's st.secrets, if Streamlit is available and a
         secrets.toml is configured (works on Streamlit Cloud even
         when the value was not also exported as an env var)

    Returns None if not found anywhere. Never raises — callers must
    handle a missing secret themselves.
    """
    value = os.environ.get(key)
    if value:
        return value

    try:
        import streamlit as st  # local import: keeps this module usable
        # in plain-Python contexts (GitHub Actions) with no Streamlit
        # installed dependency assumption beyond what's already in
        # requirements.txt.
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        # No Streamlit runtime, no secrets.toml, or key not present.
        # This is expected in the GitHub Actions environment.
        pass

    return None


# --------------------------------------------------------------------
# SECRETS — accessed only through these getters, never hardcoded.
# --------------------------------------------------------------------
def get_telegram_bot_token() -> Optional[str]:
    """Telegram bot token, or None if not configured."""
    return _read_secret("TELEGRAM_BOT_TOKEN")


def get_telegram_chat_id() -> Optional[str]:
    """Telegram chat ID to send alerts to, or None if not configured."""
    return _read_secret("TELEGRAM_CHAT_ID")


def get_gemini_api_key() -> Optional[str]:
    """Google Gemini API key for the AI Tools tab, or None if missing."""
    return _read_secret("GEMINI_API_KEY")


def get_broker_token() -> Optional[str]:
    """
    Reserved for future LIVE broker integration (e.g. Upstox).
    Returns None today — paper trading does not need this.
    Do not wire this into any order-placement code until the project
    has explicitly moved past the paper-trading phase.
    """
    return _read_secret("BROKER_ACCESS_TOKEN")


def secrets_health_check() -> dict:
    """
    Returns which secrets ARE configured (booleans only — never the
    actual values) so the UI (e.g. a Settings/Diagnostics panel) can
    warn the user without ever printing a token to screen or logs.
    """
    return {
        "telegram_bot_token": bool(get_telegram_bot_token()),
        "telegram_chat_id": bool(get_telegram_chat_id()),
        "gemini_api_key": bool(get_gemini_api_key()),
        "broker_access_token": bool(get_broker_token()),
    }
