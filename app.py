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
