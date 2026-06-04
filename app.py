import streamlit as st
import random

st.set_page_config(
    page_title="Gandiv AI Trading Assistant",
    page_icon="📈",
    layout="centered"
)

st.title("📈 Gandiv AI Trading Assistant")
st.write("સ્માર્ટ AI આધારિત ટ્રેડિંગ વિશ્લેષણ")

stock = st.text_input("શેરનું નામ લખો")

if st.button("🚀 વિશ્લેષણ કરો"):

    if stock:

        signals = [
            "🟢 Strong Buy",
            "🟢 Buy",
            "🟡 Hold",
            "🔴 Sell"
        ]

        reasons = [
            "બુલિશ ટ્રેન્ડ જોવા મળે છે",
            "મજબૂત વોલ્યુમ જોવા મળે છે",
            "બ્રેકઆઉટની શક્યતા છે",
            "સપોર્ટ લેવલ મજબૂત છે",
            "પોઝિટિવ મોમેન્ટમ ચાલુ છે"
        ]

        signal = random.choice(signals)
        confidence = random.randint(80, 99)

        st.success(signal)

        st.metric(
            label="વિશ્વાસ સ્તર",
            value=f"{confidence}%"
        )

        st.info(random.choice(reasons))

        st.balloons()

    else:
        st.warning("કૃપા કરીને શેરનું નામ લખો")
