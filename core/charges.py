"""
Gandiv AI Trading Terminal — core/charges.py

Purpose
-------
THE single charges engine (your Phase 16 requirement). Every rupee of
brokerage/STT/exchange/SEBI/GST/stamp-duty/slippage anywhere in this
project — backtester, paper engine, future live engine — is computed
here, using the rates from config/trading_config.py. There is no
second calculate_charges() anywhere else.

This fixes the old bug where data_loader.py had a flat 0.12% charge
estimate that didn't match the detailed STT/GST/stamp-duty breakdown
used in app.py and auto_trade_bot.py — two different "true costs" for
the same trade, silently drifting apart.

Quantity-aware
---------------
Per your Phase 16 spec, the public function takes quantity explicitly:

    calculate_charges(buy_price, sell_price, quantity)

and computes exact charges from the real transaction value — not a
flat estimate independent of trade size.
"""

from __future__ import annotations

from dataclasses import dataclass

from config.trading_config import (
    BROKERAGE_PCT,
    STT_PCT,
    EXCHANGE_TXN_PCT,
    SEBI_PCT,
    GST_PCT,
    STAMP_DUTY_PCT,
    SLIPPAGE_PCT,
)


# ======================================================================
# RESULT TYPE
# ======================================================================
@dataclass
class ChargesBreakdown:
    buy_value: float
    sell_value: float
    brokerage: float
    stt: float
    exchange_txn: float
    sebi_charges: float
    gst: float
    stamp_duty: float
    total_charges: float

    @property
    def total_charges_pct_of_turnover(self) -> float:
        """Total charges as a % of round-trip turnover — a useful
        sanity-check number ('am I losing 0.1% or 2% to friction?')."""
        turnover = self.buy_value + self.sell_value
        return (self.total_charges / turnover * 100) if turnover > 0 else 0.0


# ======================================================================
# SLIPPAGE — applied to the EXECUTION price, before charges
# ======================================================================
def apply_buy_slippage(reference_price: float) -> float:
    """
    Realistic buy fill price: you pay slightly MORE than the reference
    price (the market moves against you fractionally while your order
    fills). Use this to turn a signal's reference/T+1-open price into
    a realistic execution price before computing charges or P&L.
    """
    return reference_price * (1 + SLIPPAGE_PCT / 100)


def apply_sell_slippage(reference_price: float) -> float:
    """Realistic sell fill price: slightly LESS than the reference price."""
    return reference_price * (1 - SLIPPAGE_PCT / 100)


# ======================================================================
# THE CHARGES ENGINE
# ======================================================================
def calculate_charges(buy_price: float, sell_price: float, quantity: int) -> ChargesBreakdown:
    """
    THE single entry point. Computes every statutory charge for one
    complete round-trip trade (buy + sell) of `quantity` shares.

    Rates come from config/trading_config.py (Upstox equity-delivery
    rates, consolidated from the old code's 3 drifted implementations)
    — this function has no rate numbers of its own.

    buy_price / sell_price should already be the SLIPPAGE-ADJUSTED
    execution prices (see apply_buy_slippage / apply_sell_slippage)
    if you want slippage reflected in the charge base too — this
    function itself does not apply slippage, it only computes
    statutory charges on whatever prices you give it.
    """
    if quantity <= 0:
        return ChargesBreakdown(0, 0, 0, 0, 0, 0, 0, 0, 0)

    buy_value = buy_price * quantity
    sell_value = sell_price * quantity
    turnover = buy_value + sell_value

    brokerage = turnover * BROKERAGE_PCT
    stt = turnover * STT_PCT
    exchange_txn = turnover * EXCHANGE_TXN_PCT
    sebi_charges = turnover * SEBI_PCT
    gst = (brokerage + exchange_txn + sebi_charges) * GST_PCT
    stamp_duty = buy_value * STAMP_DUTY_PCT  # buy-side only, per Indian stamp duty rules

    total_charges = brokerage + stt + exchange_txn + sebi_charges + gst + stamp_duty

    return ChargesBreakdown(
        buy_value=round(buy_value, 2),
        sell_value=round(sell_value, 2),
        brokerage=round(brokerage, 2),
        stt=round(stt, 2),
        exchange_txn=round(exchange_txn, 2),
        sebi_charges=round(sebi_charges, 2),
        gst=round(gst, 2),
        stamp_duty=round(stamp_duty, 2),
        total_charges=round(total_charges, 2),
    )


# ======================================================================
# CONVENIENCE — net P&L including slippage AND charges in one call
# ======================================================================
@dataclass
class TradeEconomics:
    quantity: int
    reference_entry: float
    reference_exit: float
    executed_entry: float   # after slippage
    executed_exit: float    # after slippage
    gross_pnl: float        # before charges, using EXECUTED prices
    charges: ChargesBreakdown
    net_pnl: float          # gross_pnl - total_charges


def calculate_trade_economics(
    reference_entry: float,
    reference_exit: float,
    quantity: int,
    apply_slippage: bool = True,
) -> TradeEconomics:
    """
    One-stop calculation the backtester and paper engine both call:
    given the signal's reference entry/exit prices, apply realistic
    slippage, compute statutory charges on the executed prices, and
    return the fully realistic net P&L for this trade. This is what
    replaces the old backtester's "no charges/no slippage modeled at
    all" gap — every simulated trade now pays the same real-world
    friction a live trade would.
    """
    executed_entry = apply_buy_slippage(reference_entry) if apply_slippage else reference_entry
    executed_exit = apply_sell_slippage(reference_exit) if apply_slippage else reference_exit

    gross_pnl = quantity * (executed_exit - executed_entry)
    charges = calculate_charges(executed_entry, executed_exit, quantity)
    net_pnl = gross_pnl - charges.total_charges

    return TradeEconomics(
        quantity=quantity,
        reference_entry=reference_entry,
        reference_exit=reference_exit,
        executed_entry=round(executed_entry, 2),
        executed_exit=round(executed_exit, 2),
        gross_pnl=round(gross_pnl, 2),
        charges=charges,
        net_pnl=round(net_pnl, 2),
    )
