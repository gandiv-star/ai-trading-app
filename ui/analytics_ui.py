"""
Gandiv AI Trading Terminal - Analytics UI Module (v6.0)
"""

import pandas as pd
import streamlit as st
from config import SECTOR_MAP

def render_analytics_tab():
    st.markdown("### 📊 Advanced Portfolio Analytics (v6.0)")

    if not st.session_state.paper_trade_history and not st.session_state.paper_portfolio:
        st.info("💡 હજુ સુધી કોઈ ટ્રેડ હિસ્ટ્રી કે ઓપન પોઝિશન નથી. ઓટો બોટ રન કર્યા પછી અહીં ચાર્ટ્સ દેખાશે.")
    else:
        # ----------------------------------------------------
        # 1. SECTOR ALLOCATION CHART
        # ----------------------------------------------------
        st.markdown("#### 🍩 Current Sector Allocation")
        
        sector_data = {}
        for sym, pos in st.session_state.paper_portfolio.items():
            sec = SECTOR_MAP.get(sym, "Other")
            val = pos["qty"] * pos["avg_price"]
            sector_data[sec] = sector_data.get(sec, 0) + val
        
        if st.session_state.paper_cash > 0:
            sector_data["Cash"] = st.session_state.paper_cash

        if sector_data:
            sec_df = pd.DataFrame(list(sector_data.items()), columns=["Sector", "Value (₹)"])
            st.bar_chart(sec_df.set_index("Sector"))

        st.divider()

        # ----------------------------------------------------
        # 2. CLOSED TRADES ANALYTICS & WIN/LOSS RATIO
        # ----------------------------------------------------
        if st.session_state.paper_trade_history:
            st.markdown("#### 🎯 Trade Performance Metrics")
            th_df = pd.DataFrame(st.session_state.paper_trade_history)
            
            pnl_col = "Net P&L" if "Net P&L" in th_df.columns else ("Gross P&L" if "Gross P&L" in th_df.columns else None)
            
            if pnl_col:
                tot_trades = len(th_df)
                win_trades = len(th_df[th_df[pnl_col] > 0])
                win_rate = round((win_trades / tot_trades) * 100, 1) if tot_trades > 0 else 0
                total_net_profit = round(th_df[pnl_col].sum(), 2)
                avg_trade_pnl = round(total_net_profit / tot_trades, 2) if tot_trades > 0 else 0
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Total Trades", tot_trades)
                m2.metric("Win Rate", f"{win_rate}%")
                m3.metric("Net Realized P&L", f"₹{total_net_profit:,.2f}")
                m4.metric("Avg P&L / Trade", f"₹{avg_trade_pnl:,.2f}")

                # Cumulative P&L Curve Chart
                st.markdown("#### 📈 Equity / Profit Growth Curve")
                th_df["Cumulative P&L"] = th_df[pnl_col].cumsum()
                if "Date" in th_df.columns:
                    st.line_chart(th_df.set_index("Date")["Cumulative P&L"])
                else:
                    st.line_chart(th_df["Cumulative P&L"])

            # Trade History Table
            st.markdown("#### 📜 Trade Journal")
            st.dataframe(th_df, use_container_width=True)
          
