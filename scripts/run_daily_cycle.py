#!/usr/bin/env python3
"""
Gandiv AI Trading Terminal — scripts/run_daily_cycle.py

Purpose
-------
The entrypoint GitHub Actions runs once per trading day. It is a thin
wrapper around paper.engine.run_daily_cycle() — ALL the real logic
(completed-candle signals, risk checks, exits, Telegram alerts) lives
in the shared engine, not here. This script's only job is: call it,
log the result clearly, and turn any unexpected crash into both a
non-zero exit code (so the workflow shows red) AND a Telegram alert
(so you find out even if you don't check the Actions tab).
"""

from __future__ import annotations

import logging
import sys

from config.universe import STOCK_UNIVERSE
from paper.engine import run_daily_cycle
from notifications.telegram import system_error_alert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("scripts.run_daily_cycle")


def main() -> int:
    try:
        result = run_daily_cycle(symbols=STOCK_UNIVERSE)
    except Exception as exc:  # noqa: BLE001 — top-level entrypoint boundary, must not crash silently
        logger.exception("run_daily_cycle raised an unhandled exception")
        system_error_alert("scripts.run_daily_cycle", "main", str(exc))
        return 1

    logger.info("ran=%s | reason=%s", result.ran, result.reason)

    if not result.ran:
        # Not a trading day, or already processed today — both are
        # normal, expected outcomes, not failures.
        return 0

    logger.info("Entries filled: %s", result.entries_filled or "none")
    logger.info("Exits triggered: %s", result.exits_triggered or "none")
    logger.info("New signals queued: %s", result.new_signals_queued or "none")

    for warning in result.warnings:
        logger.warning(warning)

    if result.portfolio is not None:
        logger.info(
            "Portfolio: equity=%.2f | open=%d | closed=%d | win_rate=%.1f%%",
            result.portfolio.total_equity,
            len(result.portfolio.open_trades),
            len(result.portfolio.closed_trades),
            result.portfolio.win_rate_pct,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
