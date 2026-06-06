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

    stocks = [
        "RELIANCE.NS",
        "TCS.NS",
        "INFY.NS",
        "HDFCBANK.NS",
        "ICICIBANK.NS",
        "SBIN.NS",
        "LT.NS",
        "BHARTIARTL.NS"
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

        st.write(
            f"{rank}. {symbol} | Score: {score}/100 | RSI: {rsi} | Trend: {trend}"
        )

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
