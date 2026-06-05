import streamlit as st
import google.generativeai as genai

st.set_page_config(
    page_title="Gandiv AI Assistant",
    page_icon="🤖"
)

api_key = st.secrets["GEMINI_API_KEY"]

genai.configure(api_key=api_key)

model = genai.GenerativeModel("gemini-2.5-flash")
st.title("🤖 Gandiv AI Assistant")

question = st.text_area("તમારો પ્રશ્ન લખો")

if st.button("પૂછો"):

    if question:

        with st.spinner("AI વિચારી રહ્યું છે..."):

            response = model.generate_content(question)

            st.write(response.text)
