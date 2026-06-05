import streamlit as st
import google.generativeai as genai

st.set_page_config(
    page_title="Gandiv AI Stock Research",
    page_icon="📈"
)

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

model = genai.GenerativeModel("gemini-2.5-flash")

st.title("📈 Gandiv AI Stock Research Engine")

stock = st.text_input("શેર / કંપનીનું નામ લખો")

if st.button("🔍 Research"):

    if stock:

        prompt = f"""
તમે Professional Stock Market Research Analyst છો.

કંપની: {stock}

ગુજરાતીમાં જવાબ આપો.

આ મુદ્દાઓ આપો:

1. કંપની શું કરે છે?
2. મુખ્ય તકો (Opportunities)
3. મુખ્ય જોખમો (Risks)
4. લાંબા ગાળાનો અભિપ્રાય
5. 100 માંથી Score
6. BUY / HOLD / AVOID

જવાબ સરળ ગુજરાતી ભાષામાં આપો.
આ નાણાકીય સલાહ નથી તે પણ લખો.
"""

        with st.spinner("AI Research કરી રહ્યું છે..."):
            response = model.generate_content(prompt)

        st.markdown(response.text)

    else:
        st.warning("કંપનીનું નામ લખો")
