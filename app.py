import streamlit as st
from PIL import Image
import detectorAI6

st.title("DetectorAI Pro")

uploaded = st.file_uploader("Envie uma imagem")

if uploaded:
    img = Image.open(uploaded)
    st.image(img)

    st.write("Analisando imagem...")

    resultado = detectorAI6.analisar_imagem(img)

    st.write("Resultado da análise:")
    st.write(resultado)
