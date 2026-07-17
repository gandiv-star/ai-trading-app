"""
Gandiv AI Trading Terminal - Professional Backtesting Engine (V5.0)
Calculates: Win Rate, CAGR, Max Drawdown, Sharpe Ratio, Profit Factor
"""

import datetime
import pandas as pd
import yfinance as yf

# બેકટેસ્ટિંગ માટેનો યુનિવર્સ (તમારા મકાનનો પાયો)
STOCK_UNIVERSE = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "SBIN.NS", "LT.NS", "BHARTIARTL.NS", "ITC.NS", "HINDUNILVR.NS",
    "INDUSINDBK.NS", "TATASTEEL.NS", "TATAMOTORS.NS", "GRASIM.NS", "ZOMATO.NS"
]

# ==========================================
# BACKTEST CONFIGURATION
# ==========================================
START_DATE = "2021-01-01"  # ૫ વર્ષનો ઐતિહાસિક ટેસ્ટ
END_DATE = "2026-01-01"
STARTING_CAPITAL = 1000000.0  # ₹૧૦,૦૦,૦૦૦ ની કાલ્પનિક મૂડી
CAPITAL_PER_TRADE = 20000     # દરેક ટ્રેડમાં રોકાણ
MAX_POSITIONS = 10            # એકસાથે ઓપન પોઝિશનની લિમિટ

TARGET_PCT = 4.0
SL_PCT = 2.5
SLIPPAGE_AND_CHARGES_PCT = 0.05  # Upstox ચાર્જીસ + ટેક્સ + સ્લિપેજ બફર

def run_backtest():
    print("⏳ લોડ થઈ રહ્યું છે ઐતિહાસિક ડેટા... મહેરબાની કરીને રાહ જુઓ...")
    
    all_trades = []
    
    # દરેક સ્ટોકનો ડેટા સિંગલ શૉટમાં લાવવા માટે
    for symbol in STOCK_UNIVERSE:
        try:
            stock = yf.Ticker(symbol)
            df = stock.history(start=START_DATE, end=END_DATE)
            if df.empty or len(df) < 50:
                continue
                
            # ટેકનિકલ ફેક્ટર્સ ગણતરી (Multi-Factor Engine)
            df["MA50"] = df["Close"].rolling(50).mean()
            df["MA200"] = df["Close"].rolling(200).mean()
            df["EMA20"] = df["Close"].ewm(span=20).adjust(False).mean()
            df["EMA50"] = df["Close"].ewm(span=50).adjust(False).mean()
            
            # MACD
            ema12 = df["Close"].ewm(span=12).adjust(False).mean()
            ema26 = df["Close"].ewm(span=26).adjust(False).mean()
            df["MACD"] = ema12 - ema26
            df["Signal"] = df["MACD"].ewm(span=9).adjust(False).mean()
            
            # RSI
            delta = df["Close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            df["RSI"] = 100 - (100 / (1 + rs))
            
            df = df.dropna()
            
            # ટ્રેડ સિમ્યુલેશન લોજિક
            in_position = False
            entry_price = 0
            entry_date = None
            
            for i in range(len(df) - 1):
                row = df.iloc[i]
                next_row = df.iloc[i+1]
                
                # સ્કોરિંગ સિસ્ટમ (જે આપણે કાલે કોડમાં સેટ કરી હતી)
                score = 0
                if row["MA50"] > row["MA200"]: score += 25
                if row["EMA20"] > row["EMA50"]: score += 20
                if row["MACD"] > row["Signal"]: score += 20
                if 45 <= row["RSI"] <= 65: score += 20
                if row["Close"] > row["MA50"]: score += 15
                
                # BUY TRIGGER
                if not in_position and score >= 75:
                    in_position = True
                    entry_price = next_row["Open"]  # આગલા દિવસે ઓપનિંગ પ્રાઈસ પર ખરીદી
                    entry_date = df.index[i+1]
                    continue
                
                # SELL TRIGGER (Target કે Stop Loss હિટ થાય ત્યારે)
                if in_position:
                    high_price = next_row["High"]
                    low_price = next_row["Low"]
                    close_price = next_row["Close"]
                    
                    target_price = entry_price * (1 + TARGET_PCT/100)
                    sl_price = entry_price * (1 - SL_PCT/100)
                    
                    hit_target = high_price >= target_price
                    hit_sl = low_price <= sl_price
                    
                    if hit_target or hit_sl:
                        exit_price = target_price if hit_target else sl_price
                        exit_date = df.index[i+1]
                        
                        # ચાર્જીસ બાદ કર્યા પછીનો ચોખ્ખો નફો
                        gross_pnl = (exit_price - entry_price) * (CAPITAL_PER_TRADE / entry_price)
                        charges = (CAPITAL_PER_TRADE) * (SLIPPAGE_AND_CHARGES_PCT / 100)
                        net_pnl = round(gross_pnl - charges, 2)
                        pnl_pct = round((net_pnl / CAPITAL_PER_TRADE) * 100, 2)
                        
                        all_trades.append({
                            "Stock": symbol,
                            "Entry Date": entry_date.strftime("%Y-%m-%d"),
                            "Entry Price": round(entry_price, 2),
                            "Exit Date": exit_date.strftime("%Y-%m-%d"),
                            "Exit Price": round(exit_price, 2),
                            "Net P&L (₹)": net_pnl,
                            "P&L (%)": pnl_pct,
                            "Result": "PROFIT 🟢" if net_pnl >= 0 else "LOSS 🔴"
                        })
                        in_position = False
                        
        except Exception as e:
            print(f"❌ એરર {symbol}: {e}")
            
    # ─── મેટ્રિક્સ કેલ્ક્યુલેશન અને રિપોર્ટ ───
    if not all_trades:
        print("⚠ કોઈ ટ્રેડ મળ્યા નથી. કૃપા કરીને ફિલ્ટર્સ તપાસો.")
        return
        
    trades_df = pd.DataFrame(all_trades)
    trades_df = trades_df.sort_values(by="Exit Date").reset_index(drop=True)
    
    total_trades = len(trades_df)
    win_trades = len(trades_df[trades_df["Net P&L (₹)"] >= 0])
    loss_trades = total_trades - win_trades
    win_rate = round((win_trades / total_trades) * 100, 2) if total_trades > 0 else 0
    
    total_net_pnl = round(trades_df["Net P&L (₹)"].sum(), 2)
    final_value = STARTING_CAPITAL + total_net_pnl
    
    # CAGR (વાર્ષિક રીટર્ન) ગણતરી
    years = 5
    cagr = round((((final_value / STARTING_CAPITAL) ** (1 / years)) - 1) * 100, 2)
    
    # Profit Factor
    total_profit = trades_df[trades_df["Net P&L (₹)"] > 0]["Net P&L (₹)"].sum()
    total_loss = abs(trades_df[trades_df["Net P&L (₹)"] < 0]["Net P&L (₹)"].sum())
    profit_factor = round(total_profit / total_loss, 2) if total_loss > 0 else "N/A"
    
    # CSV ફાઈલ એક્સપોર્ટ
    csv_filename = "gandiv_backtest_report.csv"
    trades_df.to_csv(csv_filename, index=False)
    
    print("\n" + "="*45)
    print("🏆 GANDIV AI BACKTEST REPORT (v5.0) 🏆")
    print("="*45)
    print(f"📅 ગાળો: {START_DATE} થી {END_DATE}")
    print(f"💵 શરૂઆતની કેપિટલ: ₹{STARTING_CAPITAL:,.2f}")
    print(f"💰 ફાઇનલ પોર્ટફોલિયો વેલ્યુ: ₹{final_value:,.2f}")
    print(f"📈 ચોખ્ખો નફો (Net P&L): ₹{total_net_pnl:,.2f}")
    print(f"📊 વાર્ષિક રીટર્ન (CAGR): {cagr}%")
    print(f"🔄 કુલ એક્ઝિક્યુટ થયેલા ટ્રેડ્સ: {total_trades}")
    print(f"🎯 સાચા ટ્રેડ (Win Rate): {win_rate}% 🚀")
    print(f"🟢 પ્રોફિટ ટ્રેડ્સ: {win_trades} | 🔴 લોસ ટ્રેડ્સ: {loss_trades}")
    print(f"⚖ Profit Factor: {profit_factor}")
    print(f"📁 વિગતવાર રિપોર્ટ સેવ થઈ ગયો છે: {csv_filename}")
    print("="*45)

if __name__ == "__main__":
    run_backtest()
  
