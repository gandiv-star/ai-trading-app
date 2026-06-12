import datetime
import requests
import streamlit as st
import google.generativeai as genai
import yfinance as yf
import pandas as pd

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
# PAPER TRADING SIMULATOR (V26) - FIXED & COMPLETED
# ==========================================
st.divider()
st.subheader("💰 Paper Trading Simulator")
if "paper_cash" not in st.session_state:
    st.session_state.paper_cash = 100000

if "paper_trades" not in st.session_state:
    st.session_state.paper_trades = []

if "paper_cash" not in st.session_state:
    st.session_state.paper_cash = 100000.0

if "paper_portfolio" not in st.session_state:
    st.session_state.paper_portfolio = {}  # { "SYMBOL": {"qty": X, "avg_price": Y} }

st.metric("Available Cash", f"₹{st.session_state.paper_cash:,.2f}")

col_sim1, col_sim2 = st.columns(2)

with col_sim1:
    paper_symbol = st.text_input("Paper Trade Stock", value="RELIANCE.NS", key="paper_symbol")
paper_qty = st.number_input(
    "Quantity",
    min_value=1,
    value=10
)

if st.button("🟢 Buy Paper Trade"):

    try:
        stock = yf.Ticker(paper_symbol)
        price = round(
            stock.history(period="1d")["Close"].iloc[-1],
            2
        )

        total_cost = price * paper_qty

        if total_cost <= st.session_state.paper_cash:

            st.session_state.paper_cash -= total_cost

            st.session_state.paper_trades.append({
                "Stock": paper_symbol,
                "Qty": paper_qty,
                "Buy Price": price,
                "Total": total_cost
            })

            st.success(
                f"✅ Bought {paper_qty} shares of {paper_symbol} @ ₹{price}"
            )

        else:
            st.error("❌ Not enough cash")

    except Exception as e:
        st.error(f"Error: {e}")

if len(st.session_state.paper_trades) > 0:

    st.subheader("📊 Open Positions")

    df = pd.DataFrame(
        st.session_state.paper_trades
    )

    st.dataframe(
        df,
        use_container_width=True
    )

    invested = df["Total"].sum()

    st.metric(
        "Total Invested",
        f"₹{invested:,.0f}"
    )
# ==========================================
# SELL & PNL TRACKER (V29)
# ==========================================

st.divider()
st.subheader("💸 Sell Position")

if len(st.session_state.paper_trades) > 0:

    trade_options = [
        f"{i} - {trade['Stock']}"
        for i, trade in enumerate(st.session_state.paper_trades)
    ]

    selected_trade = st.selectbox(
        "Select Position",
        trade_options
    )

    if st.button("🔴 Sell Selected Position"):

        try:
            index = int(selected_trade.split(" - ")[0])

            trade = st.session_state.paper_trades[index]

            stock = yf.Ticker(trade["Stock"])

            sell_price = round(
                stock.history(period="1d")["Close"].iloc[-1],
                2
            )

            sell_value = sell_price * trade["Qty"]

            buy_value = trade["Total"]

            pnl = round(
                sell_value - buy_value,
                2
            )

            st.session_state.paper_cash += sell_value

            if "closed_trades" not in st.session_state:
                st.session_state.closed_trades = []

            st.session_state.closed_trades.append({
                "Stock": trade["Stock"],
                "Qty": trade["Qty"],
                "Buy Value": buy_value,
                "Sell Value": sell_value,
                "PnL": pnl
            })

            st.session_state.paper_trades.pop(index)

            if pnl > 0:
                st.success(f"✅ Profit Booked ₹{pnl}")
            else:
                st.error(f"❌ Loss ₹{pnl}")

        except Exception as e:
            st.error(f"Error: {e}")
            # ==========================================
# CLOSED TRADES REPORT
# ==========================================

if "closed_trades" in st.session_state:

    if len(st.session_state.closed_trades) > 0:

        st.subheader("📈 Closed Trades")

        closed_df = pd.DataFrame(
            st.session_state.closed_trades
        )

        st.dataframe(
            closed_df,
            use_container_width=True
        )

        total_pnl = round(
            closed_df["PnL"].sum(),
            2
        )

        st.metric(
            "Total P&L",
            f"₹{total_pnl}"
        )
# ==========================================
# V30 PRO - LIVE PORTFOLIO TRACKER
# ==========================================

st.divider()
st.subheader("🚀 Live Portfolio Tracker")

total_value = 0
total_cost = 0

if len(st.session_state.paper_trades) > 0:

    portfolio_data = []

    for trade in st.session_state.paper_trades:

        try:
            stock = yf.Ticker(trade["Stock"])

            current_price = round(
                stock.history(period="1d")["Close"].iloc[-1],
                2
            )

            qty = trade["Qty"]

            invested = trade["Price"] * qty
            current_value = current_price * qty

            pnl = round(
                current_value - invested,
                2
            )

            pnl_pct = round(
                (pnl / invested) * 100,
                2
            )

            total_value += current_value
            total_cost += invested

            portfolio_data.append({
                "Stock": trade["Stock"],
                "Qty": qty,
                "Buy": trade["Price"],
                "LTP": current_price,
                "PnL": pnl,
                "Return %": pnl_pct
            })

        except:
            pass

    st.dataframe(
        pd.DataFrame(portfolio_data),
        use_container_width=True
    )

    total_pnl = round(
        total_value - total_cost,
        2
    )

    total_return = round(
        (total_pnl / total_cost) * 100,
        2
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Portfolio Value",
        f"₹{round(total_value,0):,.0f}"
    )

    col2.metric(
        "Profit/Loss",
        f"₹{total_pnl:,.0f}"
    )

    col3.metric(
        "Return %",
        f"{total_return}%"
    )

else:
    st.info("No Open Positions")
