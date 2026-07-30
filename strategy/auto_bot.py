"""
Gandiv AI Trading Terminal - Modular Auto Bot Strategy (v6.0)
"""

import datetime
import streamlit as st
from config import STOCK_UNIVERSE, SECTOR_MAP, SECTOR_CAPS, SINGLE_STOCK_CAP
from core.data_loader import fetch_technical_data, calculate_charges

def execute_auto_bot(at_max, at_cap, at_score, at_target_pct, at_sl_pct, save_data_func):
    if st.session_state.get("circuit_breaker_triggered", False):
        st.error("🚨 Circuit Breaker Active! Trading Blocked.")
        return

    # ----------------------------------------------------
    # STEP 1: Dynamic Trailing SL & Position Check
    # ----------------------------------------------------
    st.markdown("**Step 1: Checking Holdings & Trailing SL...**")
    for sym, pos in list(st.session_state.paper_portfolio.items()):
        try:
            td = fetch_technical_data(sym)
            if not td: continue
            cp = td["current_price"]
            chg = ((cp - pos["avg_price"]) / pos["avg_price"]) * 100
            charges = calculate_charges(pos["avg_price"], cp, pos["qty"])

            # Trailing SL Logic
            if chg >= (at_target_pct / 2) and not pos.get("sl_trailed", False):
                pos["sl_trailed"] = True
                st.info(f"🛡️ TRAILING SL ACTIVATED: {sym.replace('.NS','')} SL shifted to Entry Price (₹{pos['avg_price']})")

            # Target Hit
            if chg >= at_target_pct:
                st.session_state.paper_cash += cp * pos["qty"]
                st.session_state.paper_trade_history.append({
                    "Date": str(datetime.date.today()),
                    "Stock": sym.replace(".NS",""),
                    "Qty": pos["qty"],
                    "Buy Price": round(pos["avg_price"], 2),
                    "Sell Price": cp,
                    "Gross P&L": charges["gross_pnl"],
                    "Charges": charges["total_charges"],
                    "Net P&L": charges["net_pnl"],
                    "Net %": charges["net_pnl_pct"]
                })
                del st.session_state.paper_portfolio[sym]
                st.success(f"🎯 TARGET HIT: SOLD {sym.replace('.NS','')} @ ₹{cp} | Net P&L: ₹{charges['net_pnl']}")

            # SL Hit
            elif (pos.get("sl_trailed", False) and cp <= pos["avg_price"]) or (chg <= -at_sl_pct):
                st.session_state.paper_cash += cp * pos["qty"]
                st.session_state.paper_trade_history.append({
                    "Date": str(datetime.date.today()),
                    "Stock": sym.replace(".NS",""),
                    "Qty": pos["qty"],
                    "Buy Price": round(pos["avg_price"], 2),
                    "Sell Price": cp,
                    "Gross P&L": charges["gross_pnl"],
                    "Charges": charges["total_charges"],
                    "Net P&L": charges["net_pnl"],
                    "Net %": charges["net_pnl_pct"]
                })
                del st.session_state.paper_portfolio[sym]
                st.error(f"🛑 STOP LOSS HIT: SOLD {sym.replace('.NS','')} @ ₹{cp} | Net P&L: ₹{charges['net_pnl']}")
        except Exception:
            pass

    # ----------------------------------------------------
    # STEP 2: Portfolio Sector & Capital Optimization
    # ----------------------------------------------------
    st.markdown("**Step 2: Portfolio Sector & Capital Optimization...**")
    
    total_portfolio_val = st.session_state.paper_cash + sum(p["qty"] * p["avg_price"] for p in st.session_state.paper_portfolio.values())
    sector_exposure = {}
    for s_sym, s_pos in st.session_state.paper_portfolio.items():
        sec = SECTOR_MAP.get(s_sym, "Other")
        sec_val = s_pos["qty"] * s_pos["avg_price"]
        sector_exposure[sec] = sector_exposure.get(sec, 0) + sec_val

    slots = at_max - len(st.session_state.paper_portfolio)
    if slots <= 0:
        st.warning(f"Portfolio Full ({at_max}/{at_max})")
    else:
        candidates = []
        with st.spinner("Scanning Stocks with Sector Limits..."):
            for sym in STOCK_UNIVERSE:
                if sym in st.session_state.paper_portfolio: continue
                
                sec = SECTOR_MAP.get(sym, "Other")
                curr_sec_val = sector_exposure.get(sec, 0)
                sec_cap_limit = total_portfolio_val * SECTOR_CAPS.get(sec, 0.15)
                
                if curr_sec_val + at_cap > sec_cap_limit:
                    continue  # Sector Limit Hit
                    
                try:
                    td = fetch_technical_data(sym)
                    if not td: continue
                    score = 50
                    if td["trend"] == "Bullish": score += 20
                    if 45 <= td["rsi"] <= 65: score += 20
                    elif td["rsi"] < 30: score += 5
                    if td["current_price"] > td["ma50"]: score += 10
                    
                    if score >= at_score:
                        candidates.append({
                            "sym": sym,
                            "score": score,
                            "price": td["current_price"],
                            "sector": sec
                        })
                except Exception:
                    pass

        candidates.sort(key=lambda x: x["score"], reverse=True)
        bought = 0
        for c in candidates[:slots]:
            qty = int(at_cap / c["price"])
            if qty < 1: continue
            cost = qty * c["price"]
            
            if cost > (total_portfolio_val * SINGLE_STOCK_CAP):
                qty = int((total_portfolio_val * SINGLE_STOCK_CAP) / c["price"])
                cost = qty * c["price"]

            stamp = round(cost * 0.00015, 2)
            total_cost = round(cost + stamp, 2)
            if total_cost > st.session_state.paper_cash: continue
            
            st.session_state.paper_cash -= total_cost
            st.session_state.paper_portfolio[c["sym"]] = {
                "qty": qty, 
                "avg_price": c["price"],
                "sl_trailed": False
            }
                
            st.success(f"✅ BOUGHT {qty}x {c['sym'].replace('.NS','')} [{c['sector']}] @ ₹{c['price']} | Score: {c['score']}/100")
            bought += 1

        if bought == 0 and len(candidates) == 0:
            st.info("કોઈ qualifying stock નથી અથવા Sector Limit પૂરી થઈ ગઈ છે.")

    save_data_func()
    st.session_state.last_auto_trade_run = str(datetime.datetime.now())

    bot1, bot2 = st.columns(2)
    bot1.metric("Open Positions", len(st.session_state.paper_portfolio))
    bot2.metric("Available Cash", f"₹{st.session_state.paper_cash:,.2f}")
  
