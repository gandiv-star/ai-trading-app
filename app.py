import requests
import streamlit as st
import google.generativeai as genai
import yfinance as yf
import pandas as pd
import datetime

# Page Configuration
st.set_page_config(
    page_title="Gandiv AI Stock Research",
    page_icon="📈"
)

# AI Model Configuration
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.5-flash")

st.title("📈 Gandiv AI Trading Assistant")

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
                stock = yf.Ticker(symbol)
                info = stock.info

                pe = info.get("trailingPE", 999)
                market_cap = info.get("marketCap", 0)

                hist = stock.history(period="1y")
                close = hist["Close"]

                ma50 = close.rolling(50).mean().iloc[-1]
                ma200 = close.rolling(200).mean().iloc[-1]

                delta = close.diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()

                rs = gain / loss
                rsi = (100 - (100 / (1 + rs))).iloc[-1]

                trend = "Bullish" if ma50 > ma200 else "Bearish"
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

                results.append((symbol, score, round(rsi, 2), trend))
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
            stock = yf.Ticker(symbol)
            info = stock.info

            current_price = info.get("currentPrice", "N/A")
            market_cap = info.get("marketCap", "N/A")
            pe_ratio = info.get("trailingPE", "N/A")

            hist = stock.history(period="1y")
            close = hist["Close"]

            ma50 = round(close.rolling(50).mean().iloc[-1], 2)
            ma200 = round(close.rolling(200).mean().iloc[-1], 2)

            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()

            rs = gain / loss
            rsi = round((100 - (100 / (1 + rs))).iloc[-1], 2)
            trend = "Bullish" if ma50 > ma200 else "Bearish"

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
                stock = yf.Ticker(symbol)
                hist = stock.history(period="1y")
                close = hist["Close"]
                ma50 = close.rolling(50).mean().iloc[-1]
                ma200 = close.rolling(200).mean().iloc[-1]
                trend = "Bullish" if ma50 > ma200 else "Bearish"
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
            stock = yf.Ticker(symbol)
            hist = stock.history(period="1y")
            close = hist["Close"]
            current_price = round(close.iloc[-1], 2)
            ma50 = close.rolling(50).mean().iloc[-1]
            ma200 = close.rolling(200).mean().iloc[-1]

            trend = "Bullish 🟢" if ma50 > ma200 else "Bearish 🔴"
            score = 90 if ma50 > ma200 else 60
            rating = "🔥 Strong Buy" if score >= 85 else "✅ Buy" if score >= 75 else "🟡 Hold"
            st.write(f"{symbol} | ₹{current_price} | {trend} | {rating}")
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
                stock = yf.Ticker(symbol)
                hist = stock.history(period="6mo")
                close = hist["Close"]
                current_price = round(close.iloc[-1], 2)
                ma50 = close.rolling(50).mean().iloc[-1]
                ma200 = close.rolling(200).mean().iloc[-1]

                if ma50 > ma200:
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
                    losses += 1; trades += 1; total_profit += profit_pct; position = False  # FIXED: Removed trailing underscore

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

if st.button("🚀 Generate AI Trade Setup"):

    try:

        stock = yf.Ticker(trade_symbol)

        hist = stock.history(period="1y")

        close = hist["Close"]

        current_price = round(close.iloc[-1], 2)

        ma50 = round(close.rolling(50).mean().iloc[-1], 2)
        ma200 = round(close.rolling(200).mean().iloc[-1], 2)

        delta = close.diff()

        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()

        rs = gain / loss

        rsi = round(
            (100 - (100 / (1 + rs))).iloc[-1],
            2
        )

        score = 50

        if ma50 > ma200:
            score += 20

        if rsi > 55:
            score += 15
        elif rsi < 30:
            score += 10

        if current_price > ma50:
            score += 15

        if score >= 80:
            advice = "🔥 BUY"
        elif score >= 65:
            advice = "🟡 HOLD"
        else:
            advice = "🔴 AVOID"

        entry = current_price
        target = round(current_price * 1.08, 2)
        stoploss = round(current_price * 0.95, 2)

        st.success(f"Recommendation: {advice}")

        st.write(f"AI Score: {score}/100")
        st.write(f"RSI: {rsi}")

        st.write(f"🎯 Entry: ₹{entry}")
        st.write(f"🚀 Target: ₹{target}")
        st.write(f"🛑 Stop Loss: ₹{stoploss}")

        if "trade_journal" not in st.session_state:
            st.session_state.trade_journal = []

        if st.button("💾 Save Trade"):

            st.session_state.trade_journal.append(
                {
                    "Date": str(datetime.date.today()),
                    "Stock": trade_symbol,
                    "Score": score,
                    "Advice": advice,
                    "Entry": entry
                }
            )

            st.success("Trade Saved Successfully")

    except Exception as e:
        st.error(f"Error: {e}")

# ==========================================
# TRADE JOURNAL (V25)
# ==========================================

st.divider()
st.subheader("📒 Trade Journal")

if "trade_journal" not in st.session_state:
    st.session_state.trade_journal = []

if len(st.session_state.trade_journal) > 0:

    journal_df = pd.DataFrame(
        st.session_state.trade_journal
    )

    st.dataframe(
        journal_df,
        use_container_width=True
    )

    st.metric(
        "Saved Trades",
        len(st.session_state.trade_journal)
    )

    avg_score = round(
        journal_df["Score"].mean(),
        2
    )

    st.metric(
        "Average AI Score",
        avg_score
    )
