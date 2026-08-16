"""
Gandiv AI Trading Terminal - Backtesting Engine
"""

import pandas as pd
import numpy as np
import yfinance as yf

INITIAL_CAPITAL = 100000
RISK_PER_TRADE = 0.05

def run_backtest(symbols, strategy_name="Combined", target_pct=8.0, sl_pct=4.0, period="5y", st=None):
    return run_streamlit_backtest(symbols, strategy_name, target_pct, sl_pct, period, st)

def run_backtest_engine(symbols, strategy_name="Combined", target_pct=8.0, sl_pct=4.0, period="5y", st=None):
    return run_streamlit_backtest(symbols, strategy_name, target_pct, sl_pct, period, st)

def run_streamlit_backtest(symbols, strategy_name="Combined", target_pct=8.0, sl_pct=4.0, period="5y", st=None):
    all_trades = []
    failed_stocks = []
    stock_summary = []
    progress = st.progress(0) if st else None

    for idx, sym in enumerate(symbols):
        try:
            df = yf.Ticker(sym).history(period=period, interval="1d")
            if df.empty or len(df) < 50:
                failed_stocks.append(sym)
                continue

            close = df["Close"]
            ema20 = close.ewm(span=20).mean()
            ema50 = close.ewm(span=50).mean()
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / (loss + 1e-6)
            rsi = 100 - (100 / (1 + rs))

            trades = 0
            wins = 0
            in_pos = False
            entry_price = 0
            entry_date = None

            for i in range(50, len(df)):
                c_price = close.iloc[i]
                c_date = df.index[i]
                if not in_pos:
                    if close.iloc[i] > ema20.iloc[i] > ema50.iloc[i] and 45 <= rsi.iloc[i] <= 65:
                        in_pos = True
                        entry_price = c_price
                        entry_date = c_date
                        trades += 1
                else:
                    target = entry_price * (1 + target_pct / 100)
                    sl = entry_price * (1 - sl_pct / 100)
                    if c_price >= target:
                        wins += 1
                        in_pos = False
                        all_trades.append({"Symbol": sym.replace(".NS", ""), "Entry Date": entry_date, "Exit Date": c_date, "Return (%)": target_pct, "Result": "WIN"})
                    elif c_price <= sl:
                        in_pos = False
                        all_trades.append({"Symbol": sym.replace(".NS", ""), "Entry Date": entry_date, "Exit Date": c_date, "Return (%)": -sl_pct, "Result": "LOSS"})

            win_rate = round((wins / trades * 100), 1) if trades > 0 else 0.0
            stock_summary.append({"Symbol": sym.replace(".NS", ""), "Trades": trades, "Win Rate (%)": win_rate, "Status": "Profitable" if win_rate >= 50 else "Neutral"})
        except Exception:
            failed_stocks.append(sym)

        if progress:
            progress.progress((idx + 1) / len(symbols))

    trades_df = pd.DataFrame(all_trades)

    if not trades_df.empty:
        trades_df = trades_df.sort_values("Exit Date").reset_index(drop=True)
        capital = INITIAL_CAPITAL
        equity_points = []
        for _, row in trades_df.iterrows():
            capital *= (1 + (row["Return (%)"] / 100) * RISK_PER_TRADE)
            equity_points.append({"Date": row["Exit Date"], "Equity": round(capital, 2)})
        equity_df = pd.DataFrame(equity_points).set_index("Date")

        daily_ret = equity_df["Equity"].pct_change().dropna()
        sharpe = round((daily_ret.mean() / (daily_ret.std() + 1e-9)) * np.sqrt(252), 2) if len(daily_ret) > 1 else 0.0
        downside = daily_ret[daily_ret < 0]
        sortino = round((daily_ret.mean() / (downside.std() + 1e-9)) * np.sqrt(252), 2) if len(downside) > 1 else 0.0
        running_max = equity_df["Equity"].cummax()
        drawdown = (equity_df["Equity"] - running_max) / running_max
        max_dd = round(abs(drawdown.min()) * 100, 2)
        years = max((trades_df["Exit Date"].max() - trades_df["Entry Date"].min()).days / 365.25, 0.1)
        cagr = round(((capital / INITIAL_CAPITAL) ** (1 / years) - 1) * 100, 2)
        total_trades = len(trades_df)
        wins_total = len(trades_df[trades_df["Result"] == "WIN"])
        win_rate_total = round((wins_total / total_trades) * 100, 1) if total_trades > 0 else 0.0
        gross_win = trades_df[trades_df["Return (%)"] > 0]["Return (%)"].sum()
        gross_loss = abs(trades_df[trades_df["Return (%)"] < 0]["Return (%)"].sum())
        profit_factor = round(gross_win / (gross_loss + 1e-6), 2)
        total_net_pnl = round(capital - INITIAL_CAPITAL, 2)
    else:
        equity_df = pd.DataFrame({"Equity": [INITIAL_CAPITAL]})
        sharpe = sortino = max_dd = cagr = win_rate_total = profit_factor = total_net_pnl = 0.0
        total_trades = 0

    metrics = {
        "CAGR (%)": cagr, "Sharpe Ratio": sharpe, "Sortino Ratio": sortino,
        "Max Drawdown (%)": max_dd, "Total Trades": total_trades,
        "Win Rate (%)": win_rate_total, "Profit Factor": profit_factor,
        "Total Net PnL (₹)": total_net_pnl
    }

    csv_data = trades_df.to_csv(index=False).encode('utf-8') if not trades_df.empty else b""

    return {
        "trades_df": trades_df, "metrics": metrics, "equity_df": equity_df,
        "stock_summary": stock_summary, "csv_data": csv_data,
        "failed_stocks": failed_stocks, "total_stocks": len(symbols) - len(failed_stocks)
                        }
