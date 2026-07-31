"""
Gandiv AI Trading Terminal - Backtesting Engine Module (v6.0)
"""

import pandas as pd
import yfinance as yf
import streamlit as st
from config import STOCK_UNIVERSE
from core.data_loader import calculate_charges

def run_backtest_engine(period_years, target_pct, sl_pct):
    st.info(f"⏳ {period_years} વર્ષનો ઐતિહાસિક ડેટા ડાઉનલોડ અને એનાલિસિસ ચાલુ છે...")
    
    trades = []
    end_date = pd.Timestamp.now()
    start_date = end_date - pd.DateOffset(years=period_years)
    
    progress = st.progress(0)
    for idx, sym in enumerate(STOCK_UNIVERSE):
        try:
            df = yf.download(sym, start=start_date, end=end_date, progress=False)
            if df.empty or len(df) < 50:
                continue
                
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            df["MA20"] = df["Close"].rolling(20).mean()
            df["MA50"] = df["Close"].rolling(50).mean()
            
            delta = df["Close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            df["RSI"] = 100 - (100 / (1 + rs))
            
            in_position = False
            buy_price = 0
            buy_date = None
            
            for i in range(50, len(df)):
                cp = float(df["Close"].iloc[i])
                dt = df.index[i].strftime("%Y-%m-%d")
                
                if not in_position:
                    # Entry Buy Condition
                    if df["Close"].iloc[i] > df["MA20"].iloc[i] and df["MA20"].iloc[i] > df["MA50"].iloc[i] and df["RSI"].iloc[i] > 50:
                        in_position = True
                        buy_price = cp
                        buy_date = dt
                else:
                    chg = ((cp - buy_price) / buy_price) * 100
                    
                    # Target Hit
                    if chg >= target_pct:
                        chg_info = calculate_charges(buy_price, cp, 100)
                        trades.append({
                            "Stock": sym.replace(".NS", ""),
                            "Buy Date": buy_date,
                            "Buy Price": round(buy_price, 2),
                            "Sell Date": dt,
                            "Sell Price": round(cp, 2),
                            "Gross P&L": chg_info["gross_pnl"],
                            "Charges": chg_info["total_charges"],
                            "Net P&L": chg_info["net_pnl"],
                            "Net %": chg_info["net_pnl_pct"]
                        })
                        in_position = False
                    # SL Hit
                    elif chg <= -sl_pct:
                        chg_info = calculate_charges(buy_price, cp, 100)
                        trades.append({
                            "Stock": sym.replace(".NS", ""),
                            "Buy Date": buy_date,
                            "Buy Price": round(buy_price, 2),
                            "Sell Date": dt,
                            "Sell Price": round(cp, 2),
                            "Gross P&L": chg_info["gross_pnl"],
                            "Charges": chg_info["total_charges"],
                            "Net P&L": chg_info["net_pnl"],
                            "Net %": chg_info["net_pnl_pct"]
                        })
                        in_position = False
        except Exception:
            pass
            
        progress.progress((idx + 1) / len(STOCK_UNIVERSE))
        
    return pd.DataFrame(trades)
                      
