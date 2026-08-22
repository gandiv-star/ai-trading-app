"""
Gandiv AI Trading Terminal — app.py (Phase P: modular rebuild)

Purpose
-------
Per your Phase 18 requirement: app.py does ONLY initialization, page
configuration, and tab routing. Every tab's actual UI logic lives in
its own ui/*.py module — this file never contains business logic
itself.

What's in this version
------------------------
  * Dashboard — config/risk/universe overview (ui/dashboard.py)
  * Scanner — live universe scan using the central signal engine (ui/scanners.py)
  * Trading — live paper portfolio + manual trades (ui/trading.py)
  * Risk Manager — risk utilization + automated daily cycle trigger (ui/risk_manager.py)
  * Backtest & Analytics — full portfolio backtest (ui/analytics.py)

What's NOT in this version yet, and why
-------------------------------------------
AI Tools (Gemini) is not included. It depends on Phase M-adjacent
work (a central AI-assist service) that hasn't been scoped yet.
Telegram notifications (Phase M) also aren't wired in yet — the
paper engine runs silently for now; alerts will call into
notifications/telegram.py once that phase exists.
"""

from __future__ import annotations

import streamlit as st

from config.settings import APP_NAME, APP_VERSION
from ui.dashboard import render_dashboard_tab
from ui.scanners import render_scanners_tab
from ui.trading import render_trading_tab
from ui.risk_manager import render_risk_manager_tab
from ui.analytics import render_analytics_tab


def main() -> None:
    st.set_page_config(
        page_title=APP_NAME,
        page_icon="📈",
        layout="wide",
    )

    st.title(f"📈 {APP_NAME}")
    st.caption(f"v{APP_VERSION} — Modular rebuild — Paper Trading Research System")

    tab_dashboard, tab_scanner, tab_trading, tab_risk, tab_analytics = st.tabs([
        "📊 Dashboard",
        "🔍 Scanner",
        "💼 Trading",
        "🛡️ Risk Manager",
        "📈 Backtest & Analytics",
    ])

    with tab_dashboard:
        render_dashboard_tab()

    with tab_scanner:
        render_scanners_tab()

    with tab_trading:
        render_trading_tab()

    with tab_risk:
        render_risk_manager_tab()

    with tab_analytics:
        render_analytics_tab()


if __name__ == "__main__":
    main()

