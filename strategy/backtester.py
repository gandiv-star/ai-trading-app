"""
Gandiv AI Trading Terminal - Professional Quant Backtesting Engine (v6.0)
Mission 1: Quant Metrics, Equity Curve, Drawdown & Monthly Matrix
"""

import pandas as pd
import numpy as np
import yfinance as yf
from config import STOCK_UNIVERSE
from core.data_loader import calculate_charges

def run_backtest_engine(period_years=5, target_pct=4.0, sl_pct=2.5, initial_capital=100000):
    """
    Executes historical simulation and computes advanced quantitative risk/return metrics.
    Preserves existing strategy buy/sell triggers.
    """
    trades = []
    end_date = pd.Timestamp.now()
    start_date = end_date - pd.DateOffset(years=period_years)
    
    # Track daily portfolio value for Equity Curve & Quant Metrics
    dates = pd.date_range(start=start_date, end=end_date, freq='B')
    equity_df = pd.DataFrame(index=dates)
    equity_df['Daily PnL'] = 0.0

    for sym in STOCK_UNIVERSE:
        try:
            df = yf.download(sym, start=start_date, end=end_date, progress=False)
            if df.empty or len(df) < 50:
                continue
                
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            # Existing Strategy Technical Indicators
            df["MA20"] = df["Close"].rolling(20).mean()
            df["MA50"] = df["Close"].rolling(50).mean()
            
            delta = df["Close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            df["RSI"] = 100 - (100 / (1 + rs))
            
            in_position = False
            buy_price = 0.0
            buy_date = None
            
            for i in range(50, len(df)):
                cp = float(df["Close"].iloc[i])
                dt = df.index[i]
                dt_str = dt.strftime("%Y-%m-%d")
                
                if not in_position:
                    # Strategy Entry Trigger (Preserved)
                    if df["Close"].iloc[i] > df["MA20"].iloc[i] and df["MA20"].iloc[i] > df["MA50"].iloc[i] and df["RSI"].iloc[i] > 50:
                        in_position = True
                        buy_price = cp
                        buy_date = dt_str
                else:
                    chg = ((cp - buy_price) / buy_price) * 100
                    
                    # Target Hit or Stop Loss Hit
                    if chg >= target_pct or chg <= -sl_pct:
                        chg_info = calculate_charges(buy_price, cp, 100)
                        net_pnl = chg_info["net_pnl"]
                        
                        trades.append({
                            "Stock": sym.replace(".NS", ""),
                            "Buy Date": buy_date,
                            "Buy Price": round(buy_price, 2),
                            "Sell Date": dt_str,
                            "Sell Price": round(cp, 2),
                            "Gross P&L": chg_info["gross_pnl"],
                            "Charges": chg_info["total_charges"],
                            "Net P&L": net_pnl,
                            "Net %": chg_info["net_pnl_pct"],
                            "Exit Type": "Target" if chg >= target_pct else "Stop Loss"
                        })
                        
                        if dt in equity_df.index:
                            equity_df.loc[dt, 'Daily PnL'] += net_pnl
                            
                        in_position = False
        except Exception:
            pass

    trades_df = pd.DataFrame(trades)
    
    # ----------------------------------------------------
    # QUANT METRICS CALCULATION ENGINE
    # ----------------------------------------------------
    metrics = {}
    
    if not trades_df.empty:
        total_trades = len(trades_df)
        winning_trades = trades_df[trades_df["Net P&L"] > 0]
        losing_trades = trades_df[trades_df["Net P&L"] <= 0]
        
        win_rate = (len(winning_trades) / total_trades) * 100
        gross_profit = winning_trades["Net P&L"].sum()
        gross_loss = abs(losing_trades["Net P&L"].sum())
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else float('inf')
        
        total_net_pnl = trades_df["Net P&L"].sum()
        final_capital = initial_capital + total_net_pnl
        
        # Equity Curve
        equity_df['Equity'] = initial_capital + equity_df['Daily PnL'].cumsum()
        equity_df['Peak'] = equity_df['Equity'].cummax()
        equity_df['Drawdown'] = (equity_df['Equity'] - equity_df['Peak']) / equity_df['Peak'] * 100
        
        max_drawdown = equity_df['Drawdown'].min()
        
        # CAGR Calculation
        cagr = (((final_capital / initial_capital) ** (1 / period_years)) - 1) * 100
        
        # Sharpe & Sortino Ratio (Assuming Risk-free rate = 5%)
        daily_returns = equity_df['Equity'].pct_change().dropna()
        rf_daily = 0.05 / 252
        excess_returns = daily_returns - rf_daily
        
        std_dev = daily_returns.std()
        sharpe_ratio = round((excess_returns.mean() / std_dev) * np.sqrt(252), 2) if std_dev > 0 else 0
        
        downside_returns = daily_returns[daily_returns < 0]
        downside_std = downside_returns.std()
        sortino_ratio = round((excess_returns.mean() / downside_std) * np.sqrt(252), 2) if downside_std > 0 else 0

        metrics = {
            "Total Trades": total_trades,
            "Win Rate (%)": round(win_rate, 2),
            "Profit Factor": profit_factor,
            "Total Net PnL (₹)": round(total_net_pnl, 2),
            "CAGR (%)": round(cagr, 2),
            "Sharpe Ratio": sharpe_ratio,
            "Sortino Ratio": sortino_ratio,
            "Max Drawdown (%)": round(max_drawdown, 2)
        }
    
    return trades_df, metrics, equity_df
    
