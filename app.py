import streamlit as st
from PIL import Image

st.title("DetectorAI Pro")

uploaded = st.file_uploader("Envie uma imagem")

if uploaded:
    img = Image.open(uploaded)
    st.image(img)

    st.write("Imagem recebida! Analisando...")
