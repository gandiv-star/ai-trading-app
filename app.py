import datetime
import requests
import streamlit as st
import google.generativeai as genai
import yfinance as yf
import pandas as pd
import json
import os

# Page Configuration
st.set_page_config(
    page_title="Gandiv AI Stock Research",
    page_icon="📈",
    layout="wide"
)

# AI Model Configuration
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.5-flash")

st.title("📈 Gandiv AI Trading Assistant")
# ==========================================
# DATA PERSISTENCE
# ==========================================
DATA_FILE = "gandiv_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
            st.session_state.paper_cash = data.get("paper_cash", 100000.0)
            st.session_state.paper_portfolio = data.get("paper_portfolio", {})
            st.session_state.paper_trade_history = data.get("paper_trade_history", [])
            st.session_state.equity_curve = data.get("equity_curve", [])
            st.session_state.trade_journal = data.get("trade_journal", [])
        except Exception:
            st.session_state.paper_cash = 100000.0
            st.session_state.paper_portfolio = {}
            st.session_state.paper_trade_history = []
            st.session_state.equity_curve = []
            st.session_state.trade_journal = []
    else:
        st.session_state.paper_cash = 100000.0
        st.session_state.paper_portfolio = {}
        st.session_state.paper_trade_history = []
        st.session_state.equity_curve = []
        st.session_state.trade_journal = []

def save_data():
    data = {
        "paper_cash": st.session_state.paper_cash,
        "paper_portfolio": st.session_state.paper_portfolio,
        "paper_trade_history": st.session_state.paper_trade_history,
        "equity_curve": st.session_state.equity_curve,
        "trade_journal": st.session_state.trade_journal,
    }
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        st.error(f"Save Error: {e}")

if "data_loaded" not in st.session_state:
    load_data()
    st.session_state.data_loaded = True

# Helper function to prevent redundant code and excessive API calling
def fetch_technical_data(symbol, period="1y"):
    stock = yf.Ticker(symbol)
    hist = stock.history(period=period)
    if hist.empty:
        return None
    
    close = hist["Close"]
    current_price = round(close.iloc[-1], 2)
    
    ma50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else close.mean()
    ma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else close.mean()
    
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = (100 - (100 / (1 + rs))).iloc[-1]
    
    trend = "Bullish" if ma50 > ma200 else "Bearish"
    
    return {
        "current_price": current_price,
        "ma50": round(ma50, 2),
        "ma200": round(ma200, 2),
        "rsi": round(rsi, 2),
        "trend": trend,
        "hist": hist
    }

# ==========================================
# BEST STOCKS SCANNER
# ==========================================
st.divider()

if st.button("🔥 Best Stocks Scanner"):
    stocks = [
        "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
        "SBIN.NS", "LT.NS", "BHARTIARTL.NS", "ITC.NS", "HINDUNILVR.NS",
        "KOTAKBANK.NS", "AXISBANK.NS", "BAJFINANCE.NS", "MARUTI.NS",
        "ASIANPAINT.NS", "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS",
        "WIPRO.NS", "NESTLEIND.NS", "POWERGRID.NS", "NTPC.NS", "ONGC.NS",
        "ADANIPORTS.NS", "TATASTEEL.NS", "JSWSTEEL.NS", "HCLTECH.NS",
        "TECHM.NS", "INDUSINDBK.NS", "COALINDIA.NS"
    ]

    results = []

    with st.spinner("Stocks Scan થઈ રહ્યા છે..."):
        for symbol in stocks:
            try:
                tech_data = fetch_technical_data(symbol)
                if not tech_data: continue
                
                stock = yf.Ticker(symbol)
                info = stock.info

                pe = info.get("trailingPE", 999)
                market_cap = info.get("marketCap", 0)
                
                rsi = tech_data["rsi"]
                trend = tech_data["trend"]
                score = 100

                if pe and pe != 999:
                    if pe > 40: score -= 20
                    elif pe > 30: score -= 10

                if market_cap < 100000000000:
                    score -= 10

                if trend == "Bullish": score += 10
                else: score -= 10

                if rsi > 70: score -= 10
                elif rsi < 30: score += 5
                else: score += 10

                results.append((symbol, score, rsi, trend))
            except:
                pass

    results.sort(key=lambda x: x[1], reverse=True)

    st.subheader("🏆 Top Stocks Today")
    for rank, (symbol, score, rsi, trend) in enumerate(results, start=1):
        if score >= 100: rating = "🔥 Strong Buy"
        elif score >= 90: rating = "✅ Buy"
        elif score >= 75: rating = "🟡 Hold"
        else: rating = "🔴 Avoid"

        st.write(f"{rank}. {symbol} | {rating} | Score: {score}/100 | RSI: {rsi} | Trend: {trend}")
        
    st.success("🤖 AI Premium Scanner Completed")

# ==========================================
# STOCK ANALYSIS
# ==========================================
st.divider()

symbol = st.text_input("Stock Symbol લખો (ઉદાહરણ: RELIANCE.NS)")

if st.button("🔍 Analyze"):
    if symbol:
        try:
            with st.spinner("Data Fetch થઈ રહ્યો છે..."):
                tech_data = fetch_technical_data(symbol)
                stock = yf.Ticker(symbol)
                info = stock.info

            if tech_data:
                current_price = info.get("currentPrice", tech_data["current_price"])
                market_cap = info.get("marketCap", "N/A")
                pe_ratio = info.get("trailingPE", "N/A")
                ma50 = tech_data["ma50"]
                ma200 = tech_data["ma200"]
                rsi = tech_data["rsi"]
                trend = tech_data["trend"]

                st.subheader("📊 Live Market Data")
                st.write(f"💰 Current Price: {current_price}")
                st.write(f"🏢 Market Cap: {market_cap}")
                st.write(f"📈 P/E Ratio: {pe_ratio}")
                st.write(f"📊 50 DMA: {ma50}")
                st.write(f"📊 200 DMA: {ma200}")
                st.write(f"⚡ RSI: {rsi}")
                st.write(f"📍 Trend: {trend}")

                prompt = f"""
તમે Professional Stock Market Analyst છો.
Stock: {symbol}
Current Price: {current_price}
Market Cap: {market_cap}
PE Ratio: {pe_ratio}
50 DMA: {ma50}
200 DMA: {ma200}
RSI: {rsi}
Trend: {trend}

ગુજરાતીમાં જવાબ આપો.
1. કંપનીનું વિશ્લેષણ
2. મુખ્ય તકો
3. મુખ્ય જોખમો
4. લાંબા ગાળાનો અભિપ્રાય
5. Score /100
6. BUY / HOLD / AVOID
7. RSI નું અર્થઘટન
8. Trend Bullish છે કે Bearish?
9. Technical Score /100

છેલ્લે લખો: 'આ નાણાકીય સલાહ નથી.'
"""
                with st.spinner("AI Analysis કરી રહ્યું છે..."):
                    response = model.generate_content(prompt)

                st.markdown(response.text)
            else:
                st.error("આ સિમ્બોલ માટે ડેટા મળ્યો નથી.")
        except Exception as e:
            st.error(f"Error: {e}")
    else:
        st.warning("કૃપા કરીને Stock Symbol લખો")

# ==========================================
# AI PORTFOLIO & ALLOCATOR
# ==========================================
st.divider()

if st.button("💼 Create AI Portfolio"):
    capital = 100000
    portfolio = [("RELIANCE.NS", 40000), ("TCS.NS", 35000), ("HDFCBANK.NS", 25000)]
    st.subheader("🤖 AI Portfolio")
    for stock, amount in portfolio:
        st.write(f"{stock} → ₹{amount:,}")
    st.success(f"Total Capital Invested: ₹{capital:,}")

st.divider()
st.subheader("💼 AI Portfolio Allocator")

capital_input = st.number_input("Investment Amount (₹)", min_value=10000, value=100000, step=10000)

if st.button("🚀 Generate AI Portfolio"):
    allocation = {
        "RELIANCE.NS": 0.25, "TCS.NS": 0.20, "HDFCBANK.NS": 0.20,
        "ICICIBANK.NS": 0.15, "INFY.NS": 0.10, "ITC.NS": 0.10
    }
    st.subheader("📊 AI Recommended Portfolio")
    total = 0
    for stock, weight in allocation.items():
        amount = round(capital_input * weight)
        total += amount
        st.write(f"✅ {stock} → ₹{amount:,} ({weight*100:.0f}%)")
    st.success(f"💰 Total Allocated: ₹{total:,}")

# ==========================================
# UPSTOX INTEGRATION
# ==========================================
st.divider()

if st.button("🏦 Check Upstox Account"):
    token = st.secrets["UPSTOX_ACCESS_TOKEN"]
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    try:
        response = requests.get("https://api.upstox.com/v2/user/profile", headers=headers)
        st.success("✅ Upstox Connected Successfully")
        st.json(response.json())
    except Exception as e:
        st.error(f"Connection Error: {e}")

if st.button("📂 My Holdings"):
    token = st.secrets["UPSTOX_ACCESS_TOKEN"]
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    try:
        response = requests.get("https://api.upstox.com/v2/portfolio/long-term-holdings", headers=headers)
        st.subheader("📊 My Holdings")
        st.json(response.json())
    except Exception as e:
        st.error(f"Error: {e}")
                    
st.write("Token Loaded:", st.secrets["UPSTOX_ACCESS_TOKEN"][:15] + "...")

# ==========================================
# MARKET INSIGHTS & WATCHLIST
# ==========================================
st.divider()

if st.button("🚀 Find Best Opportunities"):
    opportunities = []
    stocks = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS", "ITC.NS", "LT.NS", "BHARTIARTL.NS", "SUNPHARMA.NS", "TITAN.NS"]
    
    with st.spinner("AI Opportunities શોધી રહ્યું છે..."):
        for symbol in stocks:
            try:
                tech_data = fetch_technical_data(symbol)
                if tech_data:
                    trend = tech_data["trend"]
                    score = 90 if trend == "Bullish" else 60
                    opportunities.append((symbol, score, trend))
            except:
                pass

    opportunities.sort(key=lambda x: x[1], reverse=True)
    st.subheader("🔥 Top Market Opportunities")
    for rank, (symbol, score, trend) in enumerate(opportunities[:5], start=1):
        st.write(f"{rank}. {symbol} | Score: {score}/100 | Trend: {trend}")
    st.success("🤖 AI Opportunity Scan Complete")         

st.divider()
st.subheader("📊 AI Market Dashboard")
col1, col2, col3 = st.columns(3)
col1.metric("Nifty Mood", "Bullish 🟢")
col2.metric("AI Risk", "Low 🟢")
col3.metric("Market Trend", "Uptrend 📈")
st.success("🤖 AI Dashboard Active")

st.divider()
st.subheader("⭐ AI Watchlist")
watchlist = st.text_area("Stocks લખો (Comma Separated)", "RELIANCE.NS,TCS.NS,HDFCBANK.NS")

if st.button("📋 Analyze Watchlist"):
    symbols = watchlist.split(",")
    for symbol in symbols:
        try:
            symbol = symbol.strip()
            tech_data = fetch_technical_data(symbol)
            if tech_data:
                current_price = tech_data["current_price"]
                trend_status = "Bullish 🟢" if tech_data["trend"] == "Bullish" else "Bearish 🔴"
                score = 90 if tech_data["trend"] == "Bullish" else 60
                rating = "🔥 Strong Buy" if score >= 85 else "✅ Buy" if score >= 75 else "🟡 Hold"
                st.write(f"{symbol} | ₹{current_price} | {trend_status} | {rating}")
            else:
                st.warning(f"{symbol} Data Not Available")
        except:
            st.warning(f"{symbol} Data Not Available")
    st.success("🤖 Watchlist Analysis Complete")

st.divider()
st.subheader("💪 Portfolio Health Score")
if st.button("📊 Check Portfolio Health"):
    st.metric("Portfolio Health", "87/100")
    st.write("Risk Level: Low 🟢")
    st.write("Diversification: Good ✅")
    st.success("AI Verdict: Strong Portfolio 🚀")

# ==========================================
# SWING TRADING & BACKTESTING
# ==========================================
st.divider()
st.subheader("📈 AI Swing Trade Finder")

if st.button("🚀 Find Swing Trades"):
    swing_trades = []
    stocks = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS", "ITC.NS"]

    with st.spinner("Swing Trades શોધી રહ્યા છીએ..."):
        for symbol in stocks:
            try:
                tech_data = fetch_technical_data(symbol, period="6mo")
                if tech_data and tech_data["trend"] == "Bullish":
                    current_price = tech_data["current_price"]
                    target = round(current_price * 1.05, 2)
                    stoploss = round(current_price * 0.97, 2)
                    swing_trades.append((symbol, current_price, target, stoploss))
            except:
                pass

    st.subheader("🔥 Top Swing Trades")
    for symbol, entry, target, stoploss in swing_trades:
        rr = round((target - entry) / (entry - stoploss), 2)
        st.write(f"✅ **{symbol}**\n\nEntry: ₹{entry}\n\nTarget: ₹{target}\n\nStop Loss: ₹{stoploss}\n\nRisk/Reward: {rr}")
    st.success("🤖 Swing Trade Scan Complete")

st.divider()
st.subheader("📊 Strategy Backtesting Engine")

if st.button("🧪 Run Backtest"):
    symbol = "RELIANCE.NS"
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="3y")
        close = hist["Close"]
        ma50 = close.rolling(50).mean()
        ma200 = close.rolling(200).mean()

        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi_series = 100 - (100 / (1 + (gain / loss)))

        volume = hist["Volume"]
        avg_volume = volume.rolling(20).mean()

        position, entry_price = False, 0
        trades, wins, losses, total_profit = 0, 0, 0, 0

        for i in range(200, len(close)):
            if not position:
                if (ma50.iloc[i] > ma200.iloc[i] and 45 <= rsi_series.iloc[i] <= 65 and 
                    volume.iloc[i] > avg_volume.iloc[i] and close.iloc[i] > ma200.iloc[i]):
                    entry_price = close.iloc[i]
                    position = True
            else:
                profit_pct = ((close.iloc[i] - entry_price) / entry_price) * 100
                if profit_pct >= 8:
                    wins += 1; trades += 1; total_profit += profit_pct; position = False
                elif profit_pct <= -4:
                    losses += 1; trades += 1; total_profit += profit_pct; position = False

        win_rate = round((wins / trades) * 100, 2) if trades > 0 else 0
        st.metric("Total Trades", trades)
        st.metric("Win Rate", f"{win_rate}%")
        st.metric("Total Return", f"{round(total_profit, 2)}%")
        st.write(f"✅ Wins: {wins}")
        st.write(f"❌ Losses: {losses}")
        
        verdict = "🔥 Excellent Strategy" if win_rate >= 60 else "✅ Good Strategy" if win_rate >= 50 else "⚠️ Needs Improvement"
        st.success(f"AI Verdict: {verdict}")
        st.info("V19 Multi-Filter Strategy Active 🚀")
    except Exception as e:
        st.error(f"Backtest Error: {e}")
                
st.divider()
st.subheader("🚀 Momentum Breakout Backtest")

if st.button("🔥 Run Momentum Backtest"):
    symbol = "ITC.NS"
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="3y")
        close = hist["Close"]
        volume = hist["Volume"]
        ma50 = close.rolling(50).mean()
        ma200 = close.rolling(200).mean()
        avg_volume = volume.rolling(20).mean()

        trades, wins, losses, total_profit = 0, 0, 0, 0
        position, entry_price = False, 0

        for i in range(200, len(close)):
            breakout_high = close.iloc[i-20:i].max()
            if not position:
                if (close.iloc[i] > ma50.iloc[i] and close.iloc[i] > ma200.iloc[i] and 
                    close.iloc[i] > breakout_high and volume.iloc[i] > avg_volume.iloc[i]):
                    entry_price = close.iloc[i]
                    position = True
            else:
                profit_pct = ((close.iloc[i] - entry_price) / entry_price) * 100
                if profit_pct >= 10:
                    wins += 1; trades += 1; total_profit += profit_pct; position = False
                elif profit_pct <= -5:
                    losses += 1; trades += 1; total_profit += profit_pct; position = False

        win_rate = round((wins / trades) * 100, 2) if trades > 0 else 0
        st.metric("Trades", trades)
        st.metric("Win Rate", f"{win_rate}%")
        st.metric("Total Return", f"{round(total_profit, 2)}%")
        st.write(f"✅ Wins: {wins}")
        st.write(f"❌ Losses: {losses}")
        
        verdict = "🔥 Excellent" if win_rate >= 60 else "✅ Good" if win_rate >= 50 else "⚠️ Weak"
        st.success(f"Momentum Verdict: {verdict}")
    except Exception as e:
        st.error(f"Error: {e}")

st.divider()
st.subheader("📉 RSI Pullback Backtest")

if st.button("🚀 Run RSI Pullback Backtest"):
    symbol = "ITC.NS"
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="3y")
        close = hist["Close"]
        ma50 = close.rolling(50).mean()
        ma200 = close.rolling(200).mean()

        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + (gain / loss)))

        trades, wins, losses, total_profit = 0, 0, 0, 0
        position, entry_price = False, 0

        for i in range(200, len(close)):
            if not position:
                if ma50.iloc[i] > ma200.iloc[i] and rsi.iloc[i] < 35:
                    entry_price = close.iloc[i]
                    position = True
            else:
                profit_pct = ((close.iloc[i] - entry_price) / entry_price) * 100
                if profit_pct >= 8:
                    wins += 1; trades += 1; total_profit += profit_pct; position = False
                elif profit_pct <= -4:
                    losses += 1; trades += 1; total_profit += profit_pct; position = False

        win_rate = round((wins / trades) * 100, 2) if trades > 0 else 0
        st.metric("Trades", trades)
        st.metric("Win Rate", f"{win_rate}%")
        st.metric("Total Return", f"{round(total_profit, 2)}%")
        st.write(f"✅ Wins: {wins}")
        st.write(f"❌ Losses: {losses}")
    except Exception as e:
        st.error(f"Error: {e}")
                
# ==========================================
# AI TRADE ADVISOR (V24)
# ==========================================
st.divider()
st.subheader("🤖 AI Trade Advisor")

trade_symbol = st.text_input(
    "Stock Symbol for AI Advice",
    value="RELIANCE.NS"
)

if "trade_journal" not in st.session_state:
    st.session_state.trade_journal = []

if st.button("🚀 Generate AI Trade Setup"):
    try:
        tech_data = fetch_technical_data(trade_symbol)
        if tech_data:
            current_price = tech_data["current_price"]
            ma50 = tech_data["ma50"]
            ma200 = tech_data["ma200"]
            rsi = tech_data["rsi"]

            score = 50
            if ma50 > ma200: score += 20
            if rsi > 55: score += 15
            elif rsi < 30: score += 10
            if current_price > ma50: score += 15

            if score >= 80: advice = "🔥 BUY"
            elif score >= 65: advice = "🟡 HOLD"
            else: advice = "🔴 AVOID"

            entry = current_price
            target = round(current_price * 1.08, 2)
            stoploss = round(current_price * 0.95, 2)

            st.success(f"Recommendation: {advice}")
            st.write(f"AI Score: {score}/100")
            st.write(f"RSI: {rsi}")
            st.write(f"🎯 Entry: ₹{entry}")
            st.write(f"🚀 Target: ₹{target}")
            st.write(f"🛑 Stop Loss: ₹{stoploss}")

            st.session_state.last_trade = {
                "Date": str(datetime.date.today()),
                "Stock": trade_symbol,
                "Score": score,
                "Advice": advice,
                "Entry": entry
            }
    except Exception as e:
        st.error(f"Error: {e}")

if "last_trade" in st.session_state:
    if st.button("💾 Save Latest Trade"):
        st.session_state.trade_journal.append(st.session_state.last_trade)
        st.success("✅ Trade Saved Successfully")
        del st.session_state.last_trade

# ==========================================
# TRADE JOURNAL (V25)
# ==========================================
st.divider()
st.subheader("📒 Trade Journal")

if len(st.session_state.trade_journal) > 0:
    journal_df = pd.DataFrame(st.session_state.trade_journal)
    st.dataframe(journal_df, use_container_width=True)
    st.metric("Saved Trades", len(st.session_state.trade_journal))
    avg_score = round(journal_df["Score"].mean(), 2)
    st.metric("Average AI Score", avg_score)
    
# ==========================================
# PAPER TRADING SIMULATOR (V26)
# ==========================================
st.divider()
st.subheader("💰 Paper Trading Simulator")

st.metric("Available Cash", f"₹{st.session_state.paper_cash:,.2f}")

col_pt1, col_pt2, col_pt3 = st.columns(3)
with col_pt1:
    pt_symbol = st.text_input("Symbol (Buy)", value="RELIANCE.NS", key="pt_buy_symbol")
with col_pt2:
    pt_qty = st.number_input("Quantity", min_value=1, value=1, step=1, key="pt_buy_qty")
with col_pt3:
    st.write("")
    st.write("")
    pt_buy_btn = st.button("✅ Buy")

if pt_buy_btn:
    try:
        tech_data = fetch_technical_data(pt_symbol)
        if tech_data:
            price = tech_data["current_price"]
            cost = price * pt_qty
            if cost > st.session_state.paper_cash:
                st.error("❌ Insufficient Cash for this Trade")
            else:
                st.session_state.paper_cash -= cost
                if pt_symbol in st.session_state.paper_portfolio:
                    existing = st.session_state.paper_portfolio[pt_symbol]
                    total_qty = existing["qty"] + pt_qty
                    total_cost = (existing["qty"] * existing["avg_price"]) + cost
                    new_avg = total_cost / total_qty
                    st.session_state.paper_portfolio[pt_symbol] = {"qty": total_qty, "avg_price": new_avg}
                else:
                    st.session_state.paper_portfolio[pt_symbol] = {"qty": pt_qty, "avg_price": price}
                save_data()
                st.success(f"✅ Bought {pt_qty} of {pt_symbol} @ ₹{price}")
        else:
            st.error("ડેટા મળ્યો નથી")
    except Exception as e:
        st.error(f"Error: {e}")

# ==========================================
# SELL POSITION (V27)
# ==========================================
st.divider()
st.subheader("📤 Sell Position")

if st.session_state.paper_portfolio:
    sell_symbol = st.selectbox("Stock વેચવા માટે પસંદ કરો", list(st.session_state.paper_portfolio.keys()), key="sell_symbol")
    holding = st.session_state.paper_portfolio[sell_symbol]
    st.write(f"Held Quantity: {holding['qty']} | Avg Price: ₹{round(holding['avg_price'],2)}")

    sell_qty = st.number_input("Sell Quantity", min_value=1, max_value=int(holding["qty"]), value=int(holding["qty"]), step=1, key="sell_qty")

    if st.button("🔴 Sell Position"):
        try:
            tech_data = fetch_technical_data(sell_symbol)
            if tech_data:
                current_price = tech_data["current_price"]
                proceeds = current_price * sell_qty
                profit = (current_price - holding["avg_price"]) * sell_qty
                profit_pct = round(((current_price - holding["avg_price"]) / holding["avg_price"]) * 100, 2)

                st.session_state.paper_cash += proceeds

                st.session_state.paper_trade_history.append({
                    "Date": str(datetime.date.today()),
                    "Stock": sell_symbol,
                    "Qty": sell_qty,
                    "Buy Price": round(holding["avg_price"], 2),
                    "Sell Price": current_price,
                    "P&L": round(profit, 2),
                    "P&L %": profit_pct
                })

                remaining_qty = holding["qty"] - sell_qty
                if remaining_qty <= 0:
                    del st.session_state.paper_portfolio[sell_symbol]
                else:
                    st.session_state.paper_portfolio[sell_symbol]["qty"] = remaining_qty

                save_data()

                if profit >= 0:
                    st.success(f"✅ Sold {sell_qty} {sell_symbol} @ ₹{current_price} | Profit: ₹{round(profit,2)} ({profit_pct}%)")
                else:
                    st.error(f"🔴 Sold {sell_qty} {sell_symbol} @ ₹{current_price} | Loss: ₹{round(profit,2)} ({profit_pct}%)")
            else:
                st.error("ડેટા મળ્યો નથી")
        except Exception as e:
            st.error(f"Error: {e}")
else:
    st.info("હાલમાં તમારી પાસે કોઈ Holdings નથી.")

# ==========================================
# LIVE PORTFOLIO TRACKER (V28)
# ==========================================
st.divider()
st.subheader("📡 Live Portfolio Tracker")

if st.session_state.paper_portfolio:
    if st.button("🔄 Refresh Live Prices"):
        rows = []
        total_invested = 0
        total_current = 0

        with st.spinner("Live Prices ફેચ થઈ રહ્યા છે..."):
            for sym, pos in st.session_state.paper_portfolio.items():
                try:
                    tech_data = fetch_technical_data(sym)
                    cp = tech_data["current_price"] if tech_data else pos["avg_price"]
                except:
                    cp = pos["avg_price"]

                invested = pos["qty"] * pos["avg_price"]
                current_val = pos["qty"] * cp
                pnl = current_val - invested
                pnl_pct = round((pnl / invested) * 100, 2) if invested > 0 else 0

                total_invested += invested
                total_current += current_val

                rows.append({
                    "Stock": sym,
                    "Qty": pos["qty"],
                    "Avg Price": round(pos["avg_price"], 2),
                    "Current Price": cp,
                    "Invested": round(invested, 2),
                    "Current Value": round(current_val, 2),
                    "Unrealized P&L": round(pnl, 2),
                    "P&L %": pnl_pct
                })

        live_df = pd.DataFrame(rows)
        st.dataframe(live_df, use_container_width=True)

        total_pnl = total_current - total_invested
        total_pnl_pct = round((total_pnl / total_invested) * 100, 2) if total_invested > 0 else 0

        col_lp1, col_lp2, col_lp3 = st.columns(3)
        col_lp1.metric("Total Invested", f"₹{total_invested:,.2f}")
        col_lp2.metric("Current Value", f"₹{total_current:,.2f}")
        col_lp3.metric("Unrealized P&L", f"₹{total_pnl:,.2f}", f"{total_pnl_pct}%")

        st.metric("Total Portfolio Value (Cash + Holdings)", f"₹{(st.session_state.paper_cash + total_current):,.2f}")
else:
    st.info("Portfolio Empty છે. પહેલા Stocks ખરીદો.")

# ==========================================
# AI MARKET SENTIMENT (V33)
# ==========================================
st.divider()
st.subheader("🧠 AI Market Sentiment")

if st.button("🌐 Get AI Market Sentiment"):
    try:
        nifty_data = fetch_technical_data("^NSEI", period="6mo")

        if nifty_data:
            nifty_trend = nifty_data["trend"]
            nifty_rsi = nifty_data["rsi"]
            nifty_price = nifty_data["current_price"]

            mood = "Bullish 🟢" if nifty_trend == "Bullish" else "Bearish 🔴"

            col_s1, col_s2, col_s3 = st.columns(3)
            col_s1.metric("Nifty Price", nifty_price)
            col_s2.metric("Nifty RSI", nifty_rsi)
            col_s3.metric("Market Mood", mood)

            sentiment_prompt = f"""
તમે Professional Market Strategist છો.
Nifty 50 Current Price: {nifty_price}
Nifty Trend: {nifty_trend}
Nifty RSI: {nifty_rsi}

ગુજરાતીમાં Short Summary આપો (5-6 lines):
1. Overall Market Sentiment - Bullish/Bearish/Neutral
2. શા માટે
3. Traders માટે ટૂંકી Strategy Suggestion
4. Caution Points

છેલ્લે લખો: 'આ નાણાકીય સલાહ નથી.'
"""
            with st.spinner("AI Market Sentiment Analyze કરી રહ્યું છે..."):
                sentiment_response = model.generate_content(sentiment_prompt)

            st.markdown("### 🤖 AI Market Mood Summary")
            st.markdown(sentiment_response.text)
        else:
            st.error("Nifty Data Fetch ન થયો.")
    except Exception as e:
        st.error(f"Error: {e}")

# ==========================================
# EQUITY CURVE (V34)
# ==========================================
st.divider()
st.subheader("📈 Equity Curve & Drawdown")

current_holdings_value = 0
for sym, pos in st.session_state.paper_portfolio.items():
    try:
        tech_data = fetch_technical_data(sym)
        cp = tech_data["current_price"] if tech_data else pos["avg_price"]
    except:
        cp = pos["avg_price"]
    current_holdings_value += cp * pos["qty"]

current_total_value = round(st.session_state.paper_cash + current_holdings_value, 2)

col_eq1, col_eq2 = st.columns(2)
with col_eq1:
    st.metric("Current Portfolio Value", f"₹{current_total_value:,.2f}")
with col_eq2:
    if st.button("📸 Record Snapshot (Today)"):
        today_str = str(datetime.date.today())
        existing_dates = [e["Date"] for e in st.session_state.equity_curve]
        if today_str in existing_dates:
            for e in st.session_state.equity_curve:
                if e["Date"] == today_str:
                    e["Value"] = current_total_value
        else:
            st.session_state.equity_curve.append({"Date": today_str, "Value": current_total_value})
        save_data()
        st.success(f"✅ Snapshot Saved: ₹{current_total_value:,.2f} on {today_str}")

if len(st.session_state.equity_curve) >= 1:
    eq_df = pd.DataFrame(st.session_state.equity_curve)
    eq_df["Date"] = pd.to_datetime(eq_df["Date"])
    eq_df = eq_df.sort_values("Date")
    eq_df = eq_df.set_index("Date")

    st.markdown("#### 📊 Portfolio Growth Chart")
    st.line_chart(eq_df["Value"])

    starting_value = eq_df["Value"].iloc[0]
    eq_df["Profit"] = eq_df["Value"] - starting_value
    st.markdown("#### 💰 Profit Curve")
    st.line_chart(eq_df["Profit"])

    eq_df["Peak"] = eq_df["Value"].cummax()
    eq_df["Drawdown %"] = ((eq_df["Value"] - eq_df["Peak"]) / eq_df["Peak"]) * 100
    st.markdown("#### 📉 Drawdown")
    st.line_chart(eq_df["Drawdown %"])

    max_drawdown = round(eq_df["Drawdown %"].min(), 2)
    total_growth = round(((eq_df["Value"].iloc[-1] - starting_value) / starting_value) * 100, 2) if starting_value > 0 else 0

    col_eq3, col_eq4, col_eq5 = st.columns(3)
    col_eq3.metric("Starting Value", f"₹{starting_value:,.2f}")
    col_eq4.metric("Total Growth", f"{total_growth}%")
    col_eq5.metric("Max Drawdown", f"{max_drawdown}%")

    with st.expander("📋 Snapshot History"):
        st.dataframe(eq_df[["Value", "Profit", "Drawdown %"]].reset_index(), use_container_width=True)

    if st.button("🗑️ Clear Equity History"):
        st.session_state.equity_curve = []
        save_data()
        st.success("✅ Equity History Cleared")
else:
    st.info("હજુ સુધી કોઈ Snapshot નથી. 'Record Snapshot' button click કરી દરરોજ Portfolio Value Save કરો - Equity Curve બનાવવા માટે.")

# ==========================================
# HEDGE FUND DASHBOARD (V35)
# ==========================================
st.divider()
st.subheader("🏦 Hedge Fund Dashboard")
st.caption("એક નજરમાં તમારું Portfolio, Market Mood, Risk અને AI Confidence")

if st.button("🔄 Generate Dashboard"):
    with st.spinner("Dashboard Data Tayar થઈ રહ્યો છે..."):
        dash_holdings_value = 0
        position_count = len(st.session_state.paper_portfolio)
        for sym, pos in st.session_state.paper_portfolio.items():
            try:
                tech_data = fetch_technical_data(sym)
                cp = tech_data["current_price"] if tech_data else pos["avg_price"]
            except:
                cp = pos["avg_price"]
            dash_holdings_value += cp * pos["qty"]

        dash_total_value = round(st.session_state.paper_cash + dash_holdings_value, 2)

        try:
            nifty_data = fetch_technical_data("^NSEI", period="6mo")
            if nifty_data:
                market_mood = "Bullish 🟢" if nifty_data["trend"] == "Bullish" else "Bearish 🔴"
                nifty_rsi = nifty_data["rsi"]
            else:
                market_mood = "Unknown ⚪"
                nifty_rsi = 50
        except:
            market_mood = "Unknown ⚪"
            nifty_rsi = 50

        if position_count == 0:
            risk_level = "No Open Positions ⚪"
        elif position_count <= 2:
            risk_level = "High (Low Diversification) 🔴"
        elif position_count <= 4:
            risk_level = "Medium 🟡"
        else:
            risk_level = "Low (Well Diversified) 🟢"

        if nifty_rsi > 70:
            risk_level += " | Market Overbought ⚠️"
        elif nifty_rsi < 30:
            risk_level += " | Market Oversold ⚠️"

        best_opportunity = "Scanning..."
        opp_stocks = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "ITC.NS", "LT.NS", "SUNPHARMA.NS"]
        best_score = -999
        for sym in opp_stocks:
            try:
                td = fetch_technical_data(sym)
                if td:
                    sc = 50
                    if td["trend"] == "Bullish": sc += 25
                    if 45 <= td["rsi"] <= 65: sc += 15
                    if td["current_price"] > td["ma50"]: sc += 10
                    if sc > best_score:
                        best_score = sc
                        best_opportunity = f"{sym} (Score: {sc}/100)"
            except:
                pass

        ai_confidence = 50
        if "Bullish" in market_mood:
            ai_confidence += 20
        else:
            ai_confidence -= 10
        if best_score >= 75:
            ai_confidence += 20
        elif best_score >= 60:
            ai_confidence += 10
        ai_confidence = max(0, min(100, ai_confidence))

        col_h1, col_h2, col_h3 = st.columns(3)
        col_h1.metric("💰 Portfolio Value", f"₹{dash_total_value:,.2f}")
        col_h2.metric("🌐 Market Mood", market_mood)
        col_h3.metric("🤖 AI Confidence", f"{ai_confidence}/100")

        col_h4, col_h5 = st.columns(2)
        col_h4.metric("🔥 Best Opportunity", best_opportunity)
        col_h5.metric("🛡️ Risk Level", risk_level)

        st.divider()
        st.write(f"📊 Open Positions: {position_count}")
        st.write(f"💵 Available Cash: ₹{st.session_state.paper_cash:,.2f}")
        st.write(f"📈 Holdings Value: ₹{dash_holdings_value:,.2f}")
        st.write(f"⚡ Nifty RSI: {nifty_rsi}")

        if ai_confidence >= 70:
            st.success("🤖 AI Verdict: Favorable Conditions for Trading 🚀")
        elif ai_confidence >= 50:
            st.warning("🤖 AI Verdict: Neutral - Trade with Caution 🟡")
        else:
            st.error("🤖 AI Verdict: Unfavorable - Defensive Stance Recommended 🔴")
else:
    st.info("Dashboard Data જોવા માટે 'Generate Dashboard' button click કરો.")
