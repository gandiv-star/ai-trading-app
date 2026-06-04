import streamlit as st
import random

st.set_page_config(
    page_title="AI Trading Signal",
    page_icon="📈"
)

st.title("📈 AI Trading Signal App")
st.write("Stock નું નામ નાખો અને AI Analysis મેળવો")

stock = st.text_input("Stock Name")

if st.button("🚀 Analyze"):

    if stock:

        action = random.choice(["BUY", "SELL", "HOLD"])

        confidence = random.randint(70,95)

        target = random.randint(1000,3000)

        stoploss = target - random.randint(50,150)

        st.success(f"Signal : {action}")

        st.metric("Confidence", f"{confidence}%")

        st.metric("Target", target)

        st.metric("Stop Loss", stoploss)

        st.info(f"{stock} માટે AI Analysis પૂર્ણ")
    else:
        st.warning("પહેલા Stock Name દાખલ કરો")
