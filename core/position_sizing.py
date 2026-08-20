"""
Gandiv AI Trading Terminal — core/position_sizing.py

Purpose
-------
The Phase 9 formula, as its own small, independently-testable module:

    risk_per_share = entry_price - stop_loss_price
    quantity = risk_capital / risk_per_share

This file does ONLY that arithmetic. It knows nothing about caps,
sector exposure, or available cash — core/risk_engine.py combines
this raw risk-based quantity with all the portfolio-level caps. That
separation keeps this file trivial to unit-test (pure math, no
portfolio state needed) and keeps risk_engine.py's cap-stacking logic
in one readable place instead of tangled into a sizing formula.
"""

from __future__ import annotations

import math


def calculate_risk_based_quantity(
    entry_price: float,
    stop_loss_price: float,
    risk_capital: float,
) -> int:
    """
    How many whole shares can be bought such that, if the stop-loss is
    hit, the loss equals (at most) `risk_capital`.

    Returns 0 for any invalid/degenerate input (SL at or above entry
    for a long position, non-positive prices, non-positive risk
    capital) rather than raising — an invalid setup should simply
    size to zero, not crash the caller.
    """
    if entry_price <= 0 or stop_loss_price <= 0 or risk_capital <= 0:
        return 0

    risk_per_share = entry_price - stop_loss_price
    if risk_per_share <= 0:
        return 0  # SL is not below entry — not a valid long setup

    raw_quantity = risk_capital / risk_per_share
    return math.floor(raw_quantity)


def calculate_risk_amount(quantity: int, entry_price: float, stop_loss_price: float) -> float:
    """Actual capital at risk for `quantity` shares if the stop-loss is hit."""
    if quantity <= 0:
        return 0.0
    return quantity * (entry_price - stop_loss_price)


def calculate_position_value(quantity: int, entry_price: float) -> float:
    """Total capital deployed to open this position at entry_price."""
    return quantity * entry_price


def calculate_reward_amount(quantity: int, entry_price: float, target_price: float) -> float:
    """Potential profit for `quantity` shares if the target is hit."""
    if quantity <= 0:
        return 0.0
    return quantity * (target_price - entry_price)


def risk_reward_ratio(entry_price: float, stop_loss_price: float, target_price: float) -> float:
    """
    Risk:Reward ratio (e.g. 2.0 means reward is 2x the risk). Returns
    0.0 for a degenerate setup (SL not below entry) instead of raising
    or dividing by zero.
    """
    risk = entry_price - stop_loss_price
    reward = target_price - entry_price
    if risk <= 0:
        return 0.0
    return reward / risk
