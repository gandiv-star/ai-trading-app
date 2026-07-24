"""
Gandiv AI Trading Terminal - Backtesting Engine
"""

import pandas as pd
import yfinance as yf

# Top 5 Highly Liquid Stocks (તુરંત ડાઉનલોડ થશે)
STOCK_UNIVERSE = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "SBIN.NS"
]

STARTING_CAPITAL = 1000000.0
CAPITAL_PER_TRADE = 20000

TARGET_PCT = 4.0
SL_PCT = 2.5
SLIPPAGE_AND_CHARGES_PCT = 0.05

def run_backtest():
    all_trades = []
    
    for symbol in STOCK_UNIVERSE:
        try:
            # 2 વર્ષનો ડેટા એકદમ ફાસ્ટ ડાઉનલોડ થશે
            df = yf.download(symbol, period="2y", interval="1d", progress=False)
            
            if df.empty:
                continue
                
            # Flatten MultiIndex columns if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            df["MA20"] = df["Close"].rolling(20).mean()
            df["MA50"] = df["Close"].rolling(50).mean()
            
            in_position = False
            entry_price = 0
            entry_date = None
            
            for i in range(50, len(df) - 1):
                close_val = float(df["Close"].iloc[i])
                ma20_val = float(df["MA20"].iloc[i])
                ma50_val = float(df["MA50"].iloc[i])
                
                # Simple Golden Crossover Condition
                buy_condition = (close_val > ma20_val) and (ma20_val > ma50_val)
                
                if not in_position and buy_condition:
                    in_position = True
                    entry_price = float(df["Open"].iloc[i+1])
                    entry_date = str(df.index[i+1])[:10]
                    continue
                
                if in_position:
                    high_price = float(df["High"].iloc[i+1])
                    low_price = float(df["Low"].iloc[i+1])
                    
                    target_price = entry_price * (1 + TARGET_PCT/100)
                    sl_price = entry_price * (1 - SL_PCT/100)
                    
                    hit_target = high_price >= target_price
                    hit_sl = low_price <= sl_price
                    
                    if hit_target or hit_sl:
                        exit_price = target_price if hit_target else sl_price
                        exit_date = str(df.index[i+1])[:10]
                        
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
            pass
            
    if not all_trades:
        return "⚠ કોઈ ટ્રેડ મળ્યા નથી."
        
    trades_df = pd.DataFrame(all_trades)
    trades_df = trades_df.sort_values(by="Exit Date").reset_index(drop=True)
    
    total_trades = len(trades_df)
    win_trades = len(trades_df[trades_df["Net P&L (₹)"] >= 0])
    loss_trades = total_trades - win_trades
    win_rate = round((win_trades / total_trades) * 100, 2) if total_trades > 0 else 0
    
    total_net_pnl = round(trades_df["Net P&L (₹)"].sum(), 2)
    final_value = STARTING_CAPITAL + total_net_pnl
    
    years = 2
    cagr = round((((final_value / STARTING_CAPITAL) ** (1 / years)) - 1) * 100, 2)
    
    total_profit = trades_df[trades_df["Net P&L (₹)"] > 0]["Net P&L (₹)"].sum()
    total_loss = abs(trades_df[trades_df["Net P&L (₹)"] < 0]["Net P&L (₹)"].sum())
    profit_factor = round(total_profit / total_loss, 2) if total_loss > 0 else "N/A"
    
    csv_filename = "gandiv_backtest_report.csv"
    trades_df.to_csv(csv_filename, index=False)
    
    report_output = f"""=============================================
🏆 GANDIV AI BACKTEST REPORT (v5.0) 🏆
=============================================
📅 ગાળો: છેલ્લા ૨ વર્ષ (2-Year Historical Data)
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
    
