import streamlit as st
import google.generativeai as genai
import yfinance as yf

st.set_page_config(
    page_title="Gandiv AI Stock Research",
    page_icon="📈"
)

# Gemini API
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

model = genai.GenerativeModel("gemini-2.5-flash")

st.title("📈 Gandiv AI Stock Research + Live Data")
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

                score = 100

                if pe and pe != 999:
                    if pe > 40:
                        score -= 20
                    elif pe > 30:
                        score -= 10

                if market_cap < 100000000000:
                    score -= 10

                results.append((symbol, score))

            except:
                pass

    results.sort(key=lambda x: x[1], reverse=True)

    st.subheader("🏆 Top Stocks Today")

    for rank, (symbol, score) in enumerate(results, start=1):

        st.write(f"{rank}. {symbol} → {score}/100")
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

            st.subheader("📊 Live Market Data")

            st.write(f"💰 Current Price: {current_price}")
            st.write(f"🏢 Market Cap: {market_cap}")
            st.write(f"📈 P/E Ratio: {pe_ratio}")

            prompt = f"""
તમે Professional Stock Market Analyst છો.

Stock: {symbol}

Current Price: {current_price}
Market Cap: {market_cap}
PE Ratio: {pe_ratio}

ગુજરાતીમાં જવાબ આપો.

1. કંપનીનું વિશ્લેષણ
2. મુખ્ય તકો
3. મુખ્ય જોખમો
4. લાંબા ગાળાનો અભિપ્રાય
5. Score /100
6. BUY / HOLD / AVOID

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

    st.success(f"Total Capital Invested: ₹{capital:,}")
