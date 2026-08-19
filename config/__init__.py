"""
Gandiv AI Trading Terminal — config package

This turns the old single `config.py` file into a proper package
(config/settings.py, config/universe.py, config/risk.py,
config/trading_config.py) as required by the modular architecture.

Backward compatibility
-----------------------
Old code across the project does:

    from config import STOCK_UNIVERSE, SECTOR_MAP, SECTOR_CAPS, SINGLE_STOCK_CAP

Rather than forcing every file to be rewritten in this same phase
(which would violate the "one file at a time, verify compatibility"
rule in your master prompt), the most commonly used names are
re-exported here. As each module is migrated in later phases, it
should import directly from the specific submodule instead
(e.g. `from config.universe import STOCK_UNIVERSE`), and this
compatibility shim can eventually be trimmed down.
"""

from config.universe import (
    STOCK_UNIVERSE,
    SECTOR_MAP,
    get_sector,
    get_sector_grouping,
    get_symbols_in_sector,
)
from config.risk import (
    SECTOR_CAPS,
    SECTOR_CAP_DEFAULT,
    SINGLE_STOCK_CAP_PCT as SINGLE_STOCK_CAP,  # old name kept for compatibility
    MAX_OPEN_POSITIONS,
    RISK_PER_TRADE_PCT,
    get_sector_cap,
)
from config.trading_config import (
    STARTING_CAPITAL,
    MIN_SIGNAL_SCORE,
    TRADING_MODE,
    TIMEZONE,
    is_trading_day,
    is_market_holiday,
)
from config.settings import (
    APP_NAME,
    APP_VERSION,
    get_telegram_bot_token,
    get_telegram_chat_id,
    get_gemini_api_key,
    secrets_health_check,
)

__all__ = [
    "STOCK_UNIVERSE",
    "SECTOR_MAP",
    "get_sector",
    "get_sector_grouping",
    "get_symbols_in_sector",
    "SECTOR_CAPS",
    "SECTOR_CAP_DEFAULT",
    "SINGLE_STOCK_CAP",
    "MAX_OPEN_POSITIONS",
    "RISK_PER_TRADE_PCT",
    "get_sector_cap",
    "STARTING_CAPITAL",
    "MIN_SIGNAL_SCORE",
    "TRADING_MODE",
    "TIMEZONE",
    "is_trading_day",
    "is_market_holiday",
    "APP_NAME",
    "APP_VERSION",
    "get_telegram_bot_token",
    "get_telegram_chat_id",
    "get_gemini_api_key",
    "secrets_health_check",
]
