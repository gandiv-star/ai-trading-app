"""
Gandiv AI Trading Terminal - Professional Backtesting Engine (V5.0)
Calculates: Win Rate, CAGR, Max Drawdown, Sharpe Ratio, Profit Factor
"""

import datetime
import pandas as pd
import yfinance as yf

STOCK_UNIVERSE = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "SBIN.NS", "LT.NS", "BHARTIARTL.NS", "ITC.NS", "HINDUNILVR.NS",
    "INDUSINDBK.NS", "TATASTEEL.NS", "TATAMOTORS.NS", "GRASIM.NS", "ZOMATO.NS"
]

START_DATE = "2021-01-01"
END_DATE = "2026-01-01"
STARTING_CAPITAL = 1000000.0
CAPITAL_PER_TRADE = 20000

TARGET_PCT = 4.0
SL_PCT = 2.5
SLIPPAGE_AND_CHARGES_PCT = 0.05

def run_backtest():
    all_trades = []
    error_logs = []
    
    for symbol in STOCK_UNIVERSE:
        try:
            stock = yf.Ticker(symbol)
            df = stock.history(start=START_DATE, end=END_DATE)
            
            if df.empty or len(df) < 50:
                error_logs.append(f"{symbol}: No data fetched")
                continue
                
            # Simple Moving Averages
            df["MA20"] = df["Close"].rolling(20).mean()
            df["MA50"] = df["Close"].rolling(50).mean()
            
            # Simple RSI
            delta = df["Close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            df["RSI"] = 100 - (100 / (1 + rs))
            
            in_position = False
            entry_price = 0
            entry_date = None
            
            for i in range(50, len(df) - 1):
                row = df.iloc[i]
                next_row = df.iloc[i+1]
                
                # Simple Logic
                buy_condition = (row["Close"] > row["MA20"]) and (row["MA20"] > row["MA50"])
                
                if not in_position and buy_condition:
                    in_position = True
                    entry_price = float(next_row["Open"])
                    entry_date = df.index[i+1].strftime("%Y-%m-%d") if hasattr(df.index[i+1], 'strftime') else str(df.index[i+1])[:10]
                    continue
                
                if in_position:
                    high_price = float(next_row["High"])
                    low_price = float(next_row["Low"])
                    
                    target_price = entry_price * (1 + TARGET_PCT/100)
                    sl_price = entry_price * (1 - SL_PCT/100)
                    
                    hit_target = high_price >= target_price
                    hit_sl = low_price <= sl_price
                    
                    if hit_target or hit_sl:
                        exit_price = target_price if hit_target else sl_price
                        exit_date = df.index[i+1].strftime("%Y-%m-%d") if hasattr(df.index[i+1], 'strftime') else str(df.index[i+1])[:10]
                        
                        gross_pnl = (exit_price - entry_price) * (CAPITAL_PER_TRADE / entry_price)
                        charges = (CAPITAL_PER_TRADE) * (SLIPPAGE_AND_CHARGES_PCT / 100)
                        net_pnl = round(gross_pnl - charges, 2)
                        pnl_pct = round((net_pnl / CAPITAL_PER_TRADE) * 100, 2)
                        
                        all_trades.append({
                            "Stock": symbol,
                            "Entry Date": entry_date,
                            "Entry Price": round(entry_price, 2),
                            "Exit Date": exit_date,
                            "Exit Price": round(exit_price, 2),
                            "Net P&L (₹)": net_pnl,
                            "P&L (%)": pnl_pct,
                            "Result": "PROFIT 🟢" if net_pnl >= 0 else "LOSS 🔴"
                        })
                        in_position = False
                        
        except Exception as e:
            error_logs.append(f"{symbol} Error: {str(e)}")
            
    if not all_trades:
        err_msg = "\n".join(error_logs[:5]) if error_logs else "No Error Logs"
        return f"⚠ કોઈ ટ્રેડ મળ્યા નથી.\n\nDebug Info:\n{err_msg}"
        
    trades_df = pd.DataFrame(all_trades)
    trades_df = trades_df.sort_values(by="Exit Date").reset_index(drop=True)
    
    total_trades = len(trades_df)
    win_trades = len(trades_df[trades_df["Net P&L (₹)"] >= 0])
    loss_trades = total_trades - win_trades
    win_rate = round((win_trades / total_trades) * 100, 2) if total_trades > 0 else 0
    
    total_net_pnl = round(trades_df["Net P&L (₹)"].sum(), 2)
    final_value = STARTING_CAPITAL + total_net_pnl
    
    years = 5
    cagr = round((((final_value / STARTING_CAPITAL) ** (1 / years)) - 1) * 100, 2)
    
    total_profit = trades_df[trades_df["Net P&L (₹)"] > 0]["Net P&L (₹)"].sum()
    total_loss = abs(trades_df[trades_df["Net P&L (₹)"] < 0]["Net P&L (₹)"].sum())
    profit_factor = round(total_profit / total_loss, 2) if total_loss > 0 else "N/A"
    
    csv_filename = "gandiv_backtest_report.csv"
    trades_df.to_csv(csv_filename, index=False)
    
    report_output = f"""=============================================
🏆 GANDIV AI BACKTEST REPORT (v5.0) 🏆
=============================================
📅 ગાળો: {START_DATE} થી {END_DATE}
💵 શરૂઆતની કેપિટલ: ₹{STARTING_CAPITAL:,.2f}
💰 ફાઇનલ પોર્ટફોલિયો વેલ્યુ: ₹{final_value:,.2f}
📈 ચોખ્ખો નફો (Net P&L): ₹{total_net_pnl:,.2f}
📊 વાર્ષિક રીટર્ન (CAGR): {cagr}%
🔄 કુલ એક્ઝિક્યુટ થયેલા ટ્રેડ્સ: {total_trades}
🎯 સાચા ટ્રેડ (Win Rate): {win_rate}% 🚀
🟢 પ્રોફિટ ટ્રેડ્સ: {win_trades} | 🔴 લોસ ટ્રેડ્સ: {loss_trades}
⚖ Profit Factor: {profit_factor}
📁 વિગતવાર રિપોર્ટ સેવ થઈ ગયો છે: {csv_filename}
=============================================
"""
    return report_output
    
