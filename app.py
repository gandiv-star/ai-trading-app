import streamlit as st
import random

st.title("AI Trading Signal App")

stock = st.text_input("Stock Name")

if st.button("Analyze"):

    action = random.choice(["BUY", "SELL", "HOLD"])

    confidence = random.randint(60,95)

    target = random.randint(100,500)

    stoploss = random.randint(50,99)

    st.success(f"Action : {action}")
    st.write(f"Confidence : {confidence}%")
    st.write(f"Target : {target}")
    st.write(f"Stop Loss : {stoploss}")
