"""
Gandiv AI Trading Terminal — storage/repository.py

Purpose
-------
The Portfolio-specific persistence layer: bridges core/portfolio.py's
to_dict()/from_dict() with storage/json_store.py's atomic-write
primitives. paper/engine.py (and eventually a live engine) talk only
to this class — never to json_store or the filesystem directly.

Schema versioning
-------------------
Every saved file includes a "schema_version" field (from
Portfolio.to_dict()). If a future phase changes the Portfolio shape,
add a migration branch in _migrate() rather than breaking old saved
files — this is the "version field" + "schema validation" part of
your Phase 12 requirement.
"""

from __future__ import annotations

import logging
from typing import Optional

from config.settings import PORTFOLIO_STATE_FILE
from config.trading_config import STARTING_CAPITAL
from core.portfolio import Portfolio
from storage.json_store import save_json, load_json, CorruptionError

logger = logging.getLogger(__name__)

CURRENT_SCHEMA_VERSION = 1


def _migrate(data: dict) -> dict:
    """
    Upgrade an older saved schema to the current one. Currently a
    no-op (schema_version 1 is the first version) — this function
    exists so the FIRST time the schema changes, there's already a
    clear place to add the migration instead of needing to invent
    this pattern under pressure.
    """
    version = data.get("schema_version", 1)
    if version == CURRENT_SCHEMA_VERSION:
        return data
    raise ValueError(
        f"storage.repository: saved file has schema_version={version}, "
        f"expected {CURRENT_SCHEMA_VERSION}, and no migration path exists yet."
    )


class PortfolioRepository:
    """
    Loads/saves a single Portfolio to a single JSON file path, with
    atomic writes + automatic backup-recovery (via json_store).
    """

    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path or PORTFOLIO_STATE_FILE

    def load(self) -> Portfolio:
        """
        Returns the saved Portfolio, or a FRESH Portfolio (starting_capital
        from config) if no saved state exists yet — the very first run
        of the paper engine has nothing to load, and that is not an error.
        """
        try:
            data = load_json(self.file_path)
        except CorruptionError:
            logger.error(
                "PortfolioRepository.load: %s is unrecoverable — "
                "starting a FRESH portfolio. Manual investigation of the "
                "corrupted file/backups is strongly recommended before "
                "trusting new results.", self.file_path,
            )
            return Portfolio(starting_capital=STARTING_CAPITAL)

        if data is None:
            logger.info("PortfolioRepository.load: no saved state at %s — starting fresh.", self.file_path)
            return Portfolio(starting_capital=STARTING_CAPITAL)

        data = _migrate(data)
        return Portfolio.from_dict(data)

    def save(self, portfolio: Portfolio) -> None:
        """Atomically persist `portfolio`, rotating a backup of the previous version first."""
        save_json(self.file_path, portfolio.to_dict())
        logger.info(
            "PortfolioRepository.save: saved portfolio to %s (equity=%.2f, open=%d, closed=%d)",
            self.file_path, portfolio.total_equity, len(portfolio.open_trades), len(portfolio.closed_trades),
        )
