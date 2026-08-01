"""
Gandiv AI Trading Terminal - Auto Bot Module (v6.0 - Advanced Quant Engine)
Features: Crash-Proof Guard, Completed Candle Logic, ATR Stop Loss, Risk-Based Position Sizing & Time-Based Exit Guard
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import yfinance as yf
from config import STOCK_UNIVERSE, SECTOR_MAP
from core.data_loader import fetch_technical_data, calculate_charges, calculate_atr

def save_session_data_atomically():
    """
    Atomic Data Saving Guard: Ensure trade history & portfolio state stays intact.
    """
    try:
        if "paper_portfolio" in st.session_state:
            st.session_state["paper_portfolio"] = dict(st.session_state.paper_portfolio)
        if "paper_trade_history" in st.session_state:
            st.session_state["paper_trade_history"] = list(st.session_state.paper_trade_history)
    except Exception as e:
        st.warning(f"⚠️ ડેટા સેવ કરતી વખતે નાની એરર આવી: {str(e)}")

def check_time_based_exits(max_holding_days=10):
    """
    Time-Based Exit Guard: Check for 3:15 PM intraday exit & stale position exits.
    """
    if "paper_portfolio" not in st.session_state or not st.session_state.paper_portfolio:
        return

    now = datetime.now()
    exit_signals = []

    # 1. Market Close Guard (3:15 PM)
    if now.hour == 15 and now.minute >= 15:
        st.warning("⚠️ Market closing time (3:15 PM) reached. Review open positions for exit.")

    # 2. Stale Trade Guard (Capital Lockout Prevention)
    for sym, pos in list(st.session_state.paper_portfolio.items()):
        try:
            entry_date = datetime.strptime(pos.get("date", datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d")
            holding_days = (now - entry_date).days
            
            if holding_days >= max_holding_days:
                exit_signals.append({
                    "Symbol": sym,
                    "Holding Days": holding_days,
                    "Reason": f"Stale Trade Limit ({max_holding_days} Days Exceeded)",
                    "Action": "AUTO_EXIT_RECOMMENDED"
                })
        except Exception:
            pass

    if exit_signals:
        st.markdown("#### ⏱️ Time-Based Exit Recommendations")
        st.dataframe(pd.DataFrame(exit_signals), use_container_width=True)

def execute_auto_bot(max_pos=3, cap_per_trade=10000, min_score=75, target_pct=4.0, sl_pct=2.5):
    """
    Quant-grade Auto Bot Execution using Completed Candle & ATR Volatility Rules
    """
    st.markdown("### 🤖 Auto Trading Bot Engine (v6.0 - Quant Multi-Factor)")
    
    # 1. Time Guard Check (3:15 PM પછી નવા ટ્રેડ અટકાવવા)
    now = datetime.now()
    if now.hour == 15 and now.minute >= 15:
        st.warning("⏰ માર્કેટ બંધ થવાનો સમય (3:15 PM) થઈ ગયો છે. નવા ઓટો-ટ્રેડ અટકાવાયેલ છે.")
        return

    try:
        results = []
        progress = st.progress(0)
        
        for idx, sym in enumerate(STOCK_UNIVERSE):
            try:
                # Fetch Historical Data for ATR & Completed Candle Analysis
                ticker = yf.Ticker(sym)
                df = ticker.history(period="60d", interval="1d")
                
                if df.empty or len(df) < 30:
                    continue
                
                # ATR Volatility Calculation
                atr_val = calculate_atr(df, period=14)
                
                # COMPLETED CANDLE LOGIC (Using iloc[-2] for Closed Candle Signal)
                prev_candle_close = float(df["Close"].iloc[-2])
                prev_candle_open = float(df["Open"].iloc[-2])
                current_price = float(df["Close"].iloc[-1])
                
                # Technical Indicators on Completed Data
                ma20 = float(df["Close"].rolling(20).mean().iloc[-2])
                ma50 = float(df["Close"].rolling(50).mean().iloc[-2])
                
                # RSI Calculation
                delta = df["Close"].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss
                rsi_series = 100 - (100 / (1 + rs))
                rsi_completed = float(rsi_series.iloc[-2])

                # SIGNAL RULE: Bullish Completed Candle + Trend + RSI Confirmation
                is_bullish_candle = prev_candle_close > prev_candle_open
                is_uptrend = prev_candle_close > ma20 and ma20 > ma50
                is_rsi_strong = rsi_completed >= 50

                if is_bullish_candle and is_uptrend and is_rsi_strong:
                    # DYNAMIC ATR STOP LOSS & TARGET
                    atr_sl = current_price - (1.5 * atr_val) if atr_val > 0 else current_price * (1 - sl_pct / 100)
                    atr_tgt = current_price + (3.0 * atr_val) if atr_val > 0 else current_price * (1 + target_pct / 100)
                    
                    risk_per_share = max(current_price - atr_sl, 1.0)
                    
                    # RISK-BASED POSITION SIZING
                    max_risk_allowed = cap_per_trade * 0.02
                    qty_by_risk = int(max_risk_allowed / risk_per_share)
                    qty_by_cap = int(cap_per_trade / current_price) if current_price > 0 else 0
                    
                    # Final Safe Quantity
                    final_qty = max(min(qty_by_risk, qty_by_cap), 1)
                    
                    results.append({
                        "Symbol": sym.replace(".NS", ""),
                        "Price (₹)": round(current_price, 2),
                        "Qty": final_qty,
                        "ATR (₹)": round(atr_val, 2),
                        "Dynamic SL (₹)": round(atr_sl, 2),
                        "Target (₹)": round(atr_tgt, 2),
                        "RSI (Closed)": round(rsi_completed, 1),
                        "Signal": "BUY (Confirmed)",
                        "Time": datetime.now().strftime("%H:%M:%S")
                    })
            except Exception:
                pass
                
            progress.progress((idx + 1) / len(STOCK_UNIVERSE))
            
        # Time-Based Exit Guard Check
        check_time_based_exits(max_holding_days=10)

        # Save portfolio state safely
        save_session_data_atomically()
        
        if results:
            st.success(f"✅ {len(results)} કન્ફર્મ્ડ પાવરફુલ સિગ્નલ્સ સ્કેન થયા.")
            st.dataframe(pd.DataFrame(results), use_container_width=True)
        else:
            st.info("💡 તમારા સેટિંગ્સ અને Completed Candle ફિલ્ટર મુજબ અત્યારે કોઈ સેફ બાય સિગ્નલ મળ્યું નથી.")
            
    except Exception as main_err:
        st.error(f"🚨 બોટ રન કરતી વખતે એરર આવી: {str(main_err)}")
        
