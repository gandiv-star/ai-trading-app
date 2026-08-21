"""
Gandiv AI Trading Terminal — ui/scanners.py

Purpose
-------
The Scanner tab: runs the SAME strategy/unified_strategy.generate_signal()
the backtester (and, eventually, the paper engine) use, across the
whole STOCK_UNIVERSE, on today's completed data.

This directly fixes two Phase 1 audit bugs from the old code:
  * render_scanners_tab() used to be called OUTSIDE the tab's `with`
    block, running on every single Streamlit rerun — here it only
    ever runs when the button below is clicked, and only from inside
    this tab's own render function.
  * A "Smart Money" style scan used to compute results and never
    display them — every scan run here always renders its table.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config.universe import STOCK_UNIVERSE, get_sector
from config.trading_config import INDEX_SYMBOL, MIN_SIGNAL_SCORE
from core.data_loader import get_completed_ohlcv, get_completed_batch
from strategy.unified_strategy import generate_signal


def render_scanners_tab() -> None:
    st.subheader("🔍 Universe Scanner")
    st.caption(
        f"Scans all {len(STOCK_UNIVERSE)} stocks using the same signal engine "
        f"the backtester uses — not a separate/duplicate scoring logic."
    )

    show_all = st.checkbox(
        "Show NO_BUY results too (default: only show BUY signals)", value=False
    )

    if not st.button("🚀 Scan Universe Now", type="primary"):
        st.info("Click the button to run a fresh scan. Nothing runs automatically on page load or on other tab interactions.")
        return

    with st.spinner(f"Fetching data and scoring {len(STOCK_UNIVERSE)} stocks..."):
        index_df = get_completed_ohlcv(INDEX_SYMBOL, period="1y", interval="1d")
        if index_df is None:
            st.warning(f"Could not fetch index data ({INDEX_SYMBOL}) — market regime and relative strength will show as neutral for every stock this scan.")

        batch = get_completed_batch(STOCK_UNIVERSE, period="1y", interval="1d")
        missing = [s for s in STOCK_UNIVERSE if s not in batch]

        rows = []
        for symbol, df in batch.items():
            try:
                signal = generate_signal(symbol, df, index_df)
            except ValueError as exc:
                st.warning(f"{symbol}: skipped — {exc}")
                continue

            if signal.signal == "NO_BUY" and not show_all:
                continue

            rows.append({
                "Symbol": symbol.replace(".NS", ""),
                "Sector": get_sector(symbol),
                "Signal": signal.signal,
                "Score": signal.score,
                "Trend": signal.component_scores.get("trend"),
                "Momentum": signal.component_scores.get("momentum"),
                "Volatility": signal.component_scores.get("volatility"),
                "Volume": signal.component_scores.get("volume"),
                "Mkt Regime": signal.component_scores.get("market_regime"),
                "Rel Strength": signal.component_scores.get("relative_strength"),
                "Close": signal.reference_close,
                "Suggested SL": signal.suggested_sl,
                "Suggested Target": signal.suggested_target,
            })

    if missing:
        st.caption(f"⚠️ No data for {len(missing)} symbol(s): {', '.join(s.replace('.NS','') for s in missing)}")

    if not rows:
        st.info(f"No {'results' if show_all else 'BUY signals'} found in this scan.")
        return

    results_df = pd.DataFrame(rows).sort_values("Score", ascending=False).reset_index(drop=True)

    buy_count = (results_df["Signal"] == "BUY").sum()
    st.success(f"Scan complete — {buy_count} BUY signal(s) out of {len(batch)} stocks scanned (threshold: score ≥ {MIN_SIGNAL_SCORE}).")

    st.dataframe(results_df, width='stretch', hide_index=True)

    csv = results_df.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Download scan results as CSV", data=csv, file_name="scan_results.csv", mime="text/csv")
