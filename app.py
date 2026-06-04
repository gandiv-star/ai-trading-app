import streamlit as st
import random

st.set_page_config(
    page_title="AI Trading Assistant",
    page_icon="📈"
)

st.title("📈 AI Trading Assistant")

stock = st.text_input("Stock Name")

if st.button("Analyze"):

    if stock:

        signals = [
            "Strong Buy",
            "Buy",
            "Hold",
            "Sell"
        ]

        signal = random.choice(signals)

        confidence = random.randint(75, 98)

        reasons = [
            "Positive Momentum",
            "Strong Volume",
            "Bullish Trend",
            "Support Zone Active",
            "Breakout Possible"
        ]

        reason = random.choice(reasons)

        st.success(f"Signal: {signal}")
        st.metric("Confidence", f"{confidence}%")

        st.subheader("AI Reason")

        st.write(reason)

    else:
        st.warning("Please enter stock name")
