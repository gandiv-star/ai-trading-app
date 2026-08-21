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
  * Backtest & Analytics — full portfolio backtest (ui/analytics.py)

What's NOT in this version yet, and why
-------------------------------------------
Trading (manual paper trading), Risk Manager (live position sizing +
Auto Bot trigger), and AI Tools (Gemini) tabs are not included here.
They depend on:
  * Phase J — paper/engine.py, paper/state.py (the live paper-trading
    loop and its persistent portfolio state)
  * Phase L — storage/repository.py (safe, atomic persistence —
    this is also where the Streamlit-Cloud-vs-GitHub-Actions
    dual-writer data-loss risk from the Phase 1 audit gets solved
    properly, instead of being patched around)
  * Phase M — notifications/telegram.py

Per your own "no placeholder/pseudo-code" rule, this file does not
fake those tabs with stub UI — they'll be added for real once those
phases exist, without needing to touch this file's structure again.
"""

from __future__ import annotations

import streamlit as st

from config.settings import APP_NAME, APP_VERSION
from ui.dashboard import render_dashboard_tab
from ui.scanners import render_scanners_tab
from ui.analytics import render_analytics_tab


def main() -> None:
    st.set_page_config(
        page_title=APP_NAME,
        page_icon="📈",
        layout="wide",
    )

    st.title(f"📈 {APP_NAME}")
    st.caption(f"v{APP_VERSION} — Modular rebuild — Paper Trading Research System")

    tab_dashboard, tab_scanner, tab_analytics = st.tabs([
        "📊 Dashboard",
        "🔍 Scanner",
        "📈 Backtest & Analytics",
    ])

    with tab_dashboard:
        render_dashboard_tab()

    with tab_scanner:
        render_scanners_tab()

    with tab_analytics:
        render_analytics_tab()


if __name__ == "__main__":
    main()
    
