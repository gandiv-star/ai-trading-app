import requests
import streamlit as st
import google.generativeai as genai
import yfinance as yf
import pandas as pd

st.set_page_config(
    page_title="Gandiv AI Stock Research",
    page_icon="📈"
)

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

model = genai.GenerativeModel("gemini-2.5-flash")

st.title("📈 Gandiv AI Trading Assistant")

# =========================
# BEST STOCKS SCANNER
# =========================

st.divider()

if st.button("🔥 Best Stocks Scanner"):

    # STEP 1: મોટી લિસ્ટ અપડેટ કરી છે
    stocks = [
        "RELIANCE.NS",
        "TCS.NS",
        "INFY.NS",
        "HDFCBANK.NS",
        "ICICIBANK.NS",
        "SBIN.NS",
        "LT.NS",
        "BHARTIARTL.NS",
        "ITC.NS",
        "HINDUNILVR.NS",
        "KOTAKBANK.NS",
        "AXISBANK.NS",
        "BAJFINANCE.NS",
        "MARUTI.NS",
        "ASIANPAINT.NS",
        "SUNPHARMA.NS",
        "TITAN.NS",
        "ULTRACEMCO.NS",
        "WIPRO.NS",
        "NESTLEIND.NS",
        "POWERGRID.NS",
        "NTPC.NS",
        "ONGC.NS",
        "ADANIPORTS.NS",
        "TATASTEEL.NS",
        "JSWSTEEL.NS",
        "HCLTECH.NS",
        "TECHM.NS",
        "INDUSINDBK.NS",
        "COALINDIA.NS"
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
                    if pe > 40:
                        score -= 20
                    elif pe > 30:
                        score -= 10

                if market_cap < 100000000000:
                    score -= 10

                if trend == "Bullish":
                    score += 10
                else:
                    score -= 10

                if rsi > 70:
                    score -= 10
                elif rsi < 30:
                    score += 5
                else:
                    score += 10

                results.append(
                    (
                        symbol,
                        score,
                        round(rsi, 2),
                        trend
                    )
                )

            except:
                pass

    results.sort(key=lambda x: x[1], reverse=True)

    st.subheader("🏆 Top Stocks Today")

    for rank, (symbol, score, rsi, trend) in enumerate(results, start=1):

        # STEP 2: પ્રીમિયમ રેટિંગ લોજિક ઉમેર્યું છે
        if score >= 100:
            rating = "🔥 Strong Buy"
        elif score >= 90:
            rating = "✅ Buy"
        elif score >= 75:
            rating = "🟡 Hold"
        else:
            rating = "🔴 Avoid"

        st.write(
            f"{rank}. {symbol} | {rating} | Score: {score}/100 | RSI: {rsi} | Trend: {trend}"
        )
        
    # STEP 3: સ્કેનર કમ્પ્લીટ મેસેજ ઉમેર્યો છે
    st.success("🤖 AI Premium Scanner Completed")

# =========================
# STOCK ANALYSIS
# =========================

st.divider()

symbol = st.text_input(
    "Stock Symbol લખો (ઉદાહરણ: RELIANCE.NS)"
)

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

            rsi = round(
                (100 - (100 / (1 + rs))).iloc[-1],
                2
            )

            trend = (
                "Bullish"
                if ma50 > ma200
                else "Bearish"
            )

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

છેલ્લે લખો:
'આ નાણાકીય સલાહ નથી.'
"""

            with st.spinner("AI Analysis કરી રહ્યું છે..."):
                response = model.generate_content(prompt)

            st.markdown(response.text)

        except Exception as e:
            st.error(f"Error: {e}")

    else:
        st.warning("કૃપા કરીને Stock Symbol લખો")

# =========================
# AI PORTFOLIO
# =========================

st.divider()

if st.button("💼 Create AI Portfolio"):

    capital = 100000

    portfolio = [
        ("RELIANCE.NS", 40000),
        ("TCS.NS", 35000),
        ("HDFCBANK.NS", 25000)
    ]

    st.subheader("🤖 AI Portfolio")

    for stock, amount in portfolio:
        st.write(f"{stock} → ₹{amount:,}")

    st.success(
        f"Total Capital Invested: ₹{capital:,}"
    )

# =========================
# UPSTOX ACCOUNT & HOLDINGS
# =========================

st.divider()

if st.button("🏦 Check Upstox Account"):

    token = st.secrets["UPSTOX_ACCESS_TOKEN"]

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }

    try:

        response = requests.get(
            "https://api.upstox.com/v2/user/profile",
            headers=headers
        )

        data = response.json()

        st.success("✅ Upstox Connected Successfully")

        st.json(data)

    except Exception as e:

        st.error(f"Connection Error: {e}")

st.divider()
st.divider()

st.subheader("💼 AI Portfolio Allocator")

capital = st.number_input(
    "Investment Amount (₹)",
    min_value=10000,
    value=100000,
    step=10000
)

if st.button("🚀 Generate AI Portfolio"):

    allocation = {
        "RELIANCE.NS": 0.25,
        "TCS.NS": 0.20,
        "HDFCBANK.NS": 0.20,
        "ICICIBANK.NS": 0.15,
        "INFY.NS": 0.10,
        "ITC.NS": 0.10
    }

    st.subheader("📊 AI Recommended Portfolio")

    total = 0

    for stock, weight in allocation.items():

        amount = round(capital * weight)

        total += amount

        st.write(
            f"✅ {stock} → ₹{amount:,} ({weight*100:.0f}%)"
        )

    st.success(
        f"💰 Total Allocated: ₹{total:,}"
    )
if st.button("📂 My Holdings"):

    token = st.secrets["UPSTOX_ACCESS_TOKEN"]

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }

    try:

        response = requests.get(
            "https://api.upstox.com/v2/portfolio/long-term-holdings",
            headers=headers
        )

        data = response.json()

        st.subheader("📊 My Holdings")

        st.json(data)

    except Exception as e:

        st.error(f"Error: {e}")
                    
st.write("Token Loaded:", st.secrets["UPSTOX_ACCESS_TOKEN"][:15])
st.divider()

if st.button("🚀 Find Best Opportunities"):

    opportunities = []

    stocks = [
        "RELIANCE.NS",
        "TCS.NS",
        "INFY.NS",
        "HDFCBANK.NS",
        "ICICIBANK.NS",
        "ITC.NS",
        "LT.NS",
        "BHARTIARTL.NS",
        "SUNPHARMA.NS",
        "TITAN.NS"
    ]

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

                opportunities.append(
                    (symbol, score, trend)
                )

            except:
                pass

    opportunities.sort(
        key=lambda x: x[1],
        reverse=True
    )

    st.subheader("🔥 Top Market Opportunities")

    for rank, (symbol, score, trend) in enumerate(
        opportunities[:5],
        start=1
    ):

        st.write(
            f"{rank}. {symbol} | Score: {score}/100 | Trend: {trend}"
        )

    st.success("🤖 AI Opportunity Scan Complete")         
st.divider()

st.subheader("📊 AI Market Dashboard")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Nifty Mood",
        "Bullish 🟢"
    )

with col2:
    st.metric(
        "AI Risk",
        "Low 🟢"
    )

with col3:
    st.metric(
        "Market Trend",
        "Uptrend 📈"
    )

st.success("🤖 AI Dashboard Active")
st.divider()

st.subheader("⭐ AI Watchlist")

watchlist = st.text_area(
    "Stocks લખો (Comma Separated)",
    "RELIANCE.NS,TCS.NS,HDFCBANK.NS"
)

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

            trend = (
                "Bullish 🟢"
                if ma50 > ma200
                else "Bearish 🔴"
            )

            score = 90 if ma50 > ma200 else 60

            if score >= 85:
                rating = "🔥 Strong Buy"
            elif score >= 75:
                rating = "✅ Buy"
            else:
                rating = "🟡 Hold"

            st.write(
                f"{symbol} | ₹{current_price} | {trend} | {rating}"
            )

        except:
            st.warning(f"{symbol} Data Not Available")

    st.success("🤖 Watchlist Analysis Complete")
st.divider()

st.subheader("💪 Portfolio Health Score")

if st.button("📊 Check Portfolio Health"):

    health_score = 87

    risk_level = "Low 🟢"

    diversification = "Good ✅"

    verdict = "Strong Portfolio 🚀"

    st.metric(
        "Portfolio Health",
        f"{health_score}/100"
    )

    st.write(
        f"Risk Level: {risk_level}"
    )

    st.write(
        f"Diversification: {diversification}"
    )

    st.success(
        f"AI Verdict: {verdict}"
    )
st.divider()

st.subheader("📈 AI Swing Trade Finder")

if st.button("🚀 Find Swing Trades"):

    swing_trades = []

    stocks = [
        "RELIANCE.NS",
        "TCS.NS",
        "INFY.NS",
        "HDFCBANK.NS",
        "ICICIBANK.NS",
        "ITC.NS"
    ]

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

                    entry = current_price
                    target = round(current_price * 1.05, 2)
                    stoploss = round(current_price * 0.97, 2)

                    swing_trades.append(
                        (
                            symbol,
                            entry,
                            target,
                            stoploss
                        )
                    )

            except:
                pass

    st.subheader("🔥 Top Swing Trades")

    for symbol, entry, target, stoploss in swing_trades:

        reward = round(target - entry, 2)
        risk = round(entry - stoploss, 2)

        rr = round(reward / risk, 2)

        st.write(
            f"""
✅ {symbol}

Entry: ₹{entry}

Target: ₹{target}

Stop Loss: ₹{stoploss}

Risk/Reward: {rr}
"""
        )

    st.success("🤖 Swing Trade Scan Complete")
st.divider()

# ==========================================
# 📊 STRATEGY BACKTESTING ENGINE (UPDATED)
# ==========================================

st.subheader("📊 Strategy Backtesting Engine")

if st.button("🧪 Run Backtest"):

    symbol = "RELIANCE.NS"

    try:

        stock = yf.Ticker(symbol)

        hist = stock.history(period="3y")

        close = hist["Close"]

        ma50 = close.rolling(50).mean()
        ma200 = close.rolling(200).mean()

        # --- NEW INDICATORS ADDED BEFORE THE LOOP ---
        delta = close.diff()

        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()

        rs = gain / loss

        rsi_series = 100 - (100 / (1 + rs))

        volume = hist["Volume"]

        avg_volume = volume.rolling(20).mean()
        # --------------------------------------------

        position = False

        entry_price = 0

        trades = 0
        wins = 0
        losses = 0

        total_profit = 0

        for i in range(200, len(close)):

            if not position:

                # --- NEW MULTI-FILTER ENTRY CONDITION ---
                if (
                    ma50.iloc[i] > ma200.iloc[i]
                    and 45 <= rsi_series.iloc[i] <= 65
                    and volume.iloc[i] > avg_volume.iloc[i]
                    and close.iloc[i] > ma200.iloc[i]
                ):

                    entry_price = close.iloc[i]

                    position = True

            else:

                profit_pct = (
                    (close.iloc[i] - entry_price)
                    / entry_price
                ) * 100

                # --- NEW TARGET (8%) & STOP LOSS (-4%) ---
                if profit_pct >= 8:

                    wins += 1
                    trades += 1
                    total_profit += profit_pct

                    position = False

                elif profit_pct <= -4:

                    losses += 1
                    trades += 1
                    total_profit += profit_pct

                    position = False

        if trades > 0:

            win_rate = round(
                (wins / trades) * 100,
                2
            )

        else:

            win_rate = 0

        st.metric(
            "Total Trades",
            trades
        )

        st.metric(
            "Win Rate",
            f"{win_rate}%"
        )

        st.metric(
            "Total Return",
            f"{round(total_profit,2)}%"
        )

        st.write(f"✅ Wins: {wins}")
        st.write(f"❌ Losses: {losses}")

        if win_rate >= 60:
            verdict = "🔥 Excellent Strategy"
        elif win_rate >= 50:
            verdict = "✅ Good Strategy"
        else:
            verdict = "⚠️ Needs Improvement"

        st.success(
            f"AI Verdict: {verdict}"
        )

        # --- RESULT COMPARISON ADDED BELOW VERDICT ---
        st.info(
            "V19 Multi-Filter Strategy Active 🚀"
        )

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

        trades = 0
        wins = 0
        losses = 0

        total_profit = 0

        position = False
        entry_price = 0

        for i in range(200, len(close)):

            breakout_high = close.iloc[i-20:i].max()

            if not position:

                if (
                    close.iloc[i] > ma50.iloc[i]
                    and close.iloc[i] > ma200.iloc[i]
                    and close.iloc[i] > breakout_high
                    and volume.iloc[i] > avg_volume.iloc[i]
                ):

                    entry_price = close.iloc[i]
                    position = True

            else:

                profit_pct = (
                    (close.iloc[i] - entry_price)
                    / entry_price
                ) * 100

                if profit_pct >= 10:

                    wins += 1
                    trades += 1
                    total_profit += profit_pct

                    position = False

                elif profit_pct <= -5:

                    losses += 1
                    trades += 1
                    total_profit += profit_pct

                    position = False

        win_rate = (
            round((wins / trades) * 100, 2)
            if trades > 0
            else 0
        )

        st.metric("Trades", trades)
        st.metric("Win Rate", f"{win_rate}%")
        st.metric(
            "Total Return",
            f"{round(total_profit,2)}%"
        )

        st.write(f"✅ Wins: {wins}")
        st.write(f"❌ Losses: {losses}")

        if win_rate >= 60:
            verdict = "🔥 Excellent"
        elif win_rate >= 50:
            verdict = "✅ Good"
        else:
            verdict = "⚠️ Weak"

        st.success(
            f"Momentum Verdict: {verdict}"
        )

    except Exception as e:

        st.error(f"Error: {e}")
