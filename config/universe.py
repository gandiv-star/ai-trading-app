"""
Gandiv AI Trading Terminal — config/universe.py

Purpose
-------
ONE canonical stock universe and ONE canonical sector map.

Audit finding this file fixes
------------------------------
The old codebase had THREE different STOCK_UNIVERSE lists (15 stocks
in config.py, 39 in app.py, 50 in auto_trade_bot.py) and TWO different
SECTOR_MAP shapes ({symbol: sector} in config.py vs {sector: [symbols]}
in app.py). That is exactly the kind of "no central engine" problem
flagged in Phase 1 of the audit.

From now on:
  * STOCK_UNIVERSE is the single list every module imports.
  * SECTOR_MAP is always {symbol: sector} — flat, one direction only.
  * If code needs {sector: [symbols]} (e.g. a sector-rotation scanner),
    it calls get_sector_grouping() below instead of maintaining its
    own second copy of the mapping.

STOCK_UNIVERSE was built by taking the largest existing list
(auto_trade_bot.py's 50 symbols, which is a superset of the other two)
as the base. Nothing was silently dropped or added beyond that — this
is a straight consolidation, not a new stock-picking decision. Edit
this list directly to add/remove symbols; every other module will
pick up the change automatically.
"""

from __future__ import annotations

from typing import Dict, List

# --------------------------------------------------------------------
# STOCK UNIVERSE — single source of truth
# --------------------------------------------------------------------
STOCK_UNIVERSE: List[str] = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "SBIN.NS", "LT.NS", "BHARTIARTL.NS", "ITC.NS", "HINDUNILVR.NS",
    "KOTAKBANK.NS", "AXISBANK.NS", "BAJFINANCE.NS", "MARUTI.NS",
    "ASIANPAINT.NS", "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS",
    "WIPRO.NS", "NESTLEIND.NS", "POWERGRID.NS", "NTPC.NS", "ONGC.NS",
    "ADANIPORTS.NS", "TATASTEEL.NS", "JSWSTEEL.NS", "HCLTECH.NS",
    "TECHM.NS", "INDUSINDBK.NS", "COALINDIA.NS", "BAJAJFINSV.NS",
    "DRREDDY.NS", "CIPLA.NS", "GRASIM.NS", "HEROMOTOCO.NS",
    "EICHERMOT.NS", "DIVISLAB.NS", "M&M.NS", "BPCL.NS", "TATAMOTORS.NS",
    "ZOMATO.NS", "POLICYBZR.NS", "NYKAA.NS", "DMART.NS", "IRFC.NS",
    "RVNL.NS", "IRCTC.NS", "HAL.NS", "BEL.NS", "JIOFIN.NS",
]

# --------------------------------------------------------------------
# SECTOR MAP — flat {symbol: sector}. This is the ONLY shape allowed.
# --------------------------------------------------------------------
SECTOR_MAP: Dict[str, str] = {
    # Banking
    "HDFCBANK.NS": "Banking", "ICICIBANK.NS": "Banking", "SBIN.NS": "Banking",
    "KOTAKBANK.NS": "Banking", "AXISBANK.NS": "Banking", "INDUSINDBK.NS": "Banking",
    # IT
    "TCS.NS": "IT", "INFY.NS": "IT", "WIPRO.NS": "IT",
    "HCLTECH.NS": "IT", "TECHM.NS": "IT",
    # FMCG
    "HINDUNILVR.NS": "FMCG", "ITC.NS": "FMCG", "NESTLEIND.NS": "FMCG",
    # Auto
    "MARUTI.NS": "Auto", "TATAMOTORS.NS": "Auto", "M&M.NS": "Auto",
    "HEROMOTOCO.NS": "Auto", "EICHERMOT.NS": "Auto",
    # Pharma
    "SUNPHARMA.NS": "Pharma", "DRREDDY.NS": "Pharma",
    "CIPLA.NS": "Pharma", "DIVISLAB.NS": "Pharma",
    # Metals
    "TATASTEEL.NS": "Metals", "JSWSTEEL.NS": "Metals",
    # Energy
    "RELIANCE.NS": "Energy", "ONGC.NS": "Energy", "BPCL.NS": "Energy",
    "NTPC.NS": "Energy", "POWERGRID.NS": "Energy", "COALINDIA.NS": "Energy",
    # NBFC / Financial services
    "BAJFINANCE.NS": "NBFC", "BAJAJFINSV.NS": "NBFC", "JIOFIN.NS": "NBFC",
    # Infra / Capital goods / Cement
    "LT.NS": "Infra", "ULTRACEMCO.NS": "Infra",
    "GRASIM.NS": "Infra", "ADANIPORTS.NS": "Infra",
    # Telecom
    "BHARTIARTL.NS": "Telecom",
    # Paints
    "ASIANPAINT.NS": "Paints",
    # Retail / Consumer
    "TITAN.NS": "Retail", "DMART.NS": "Retail", "NYKAA.NS": "Retail",
    # Insurance / InsurTech
    "POLICYBZR.NS": "Insurance",
    # Defence
    "HAL.NS": "Defence", "BEL.NS": "Defence",
    # Railways (PSU theme — tends to move together)
    "IRFC.NS": "Railways", "RVNL.NS": "Railways", "IRCTC.NS": "Railways",
    # Services / New-age
    "ZOMATO.NS": "Services",
}

# Safety check: every symbol in STOCK_UNIVERSE must have a sector.
_missing = [s for s in STOCK_UNIVERSE if s not in SECTOR_MAP]
if _missing:
    raise ValueError(
        f"config/universe.py: {_missing} are in STOCK_UNIVERSE but "
        f"missing from SECTOR_MAP. Add them before importing this module."
    )


def get_sector(symbol: str) -> str:
    """Return the sector for a symbol, or 'Other' if unmapped."""
    return SECTOR_MAP.get(symbol, "Other")


def get_sector_grouping() -> Dict[str, List[str]]:
    """
    Build {sector: [symbols]} on demand from the canonical flat
    SECTOR_MAP. Use this instead of maintaining a second, separate
    {sector: [symbols]} dict anywhere else in the codebase (that
    duplication is exactly what caused the Phase 1 audit bug).
    """
    grouping: Dict[str, List[str]] = {}
    for symbol, sector in SECTOR_MAP.items():
        grouping.setdefault(sector, []).append(symbol)
    return grouping


def get_symbols_in_sector(sector: str) -> List[str]:
    """Return all symbols belonging to a given sector."""
    return [s for s, sec in SECTOR_MAP.items() if sec == sector]
