import streamlit as st
from PIL import Image
import pytesseract
import pandas as pd
import cv2
import numpy as np
import io

# Caso precise no Windows, descomente e ajuste:
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

st.set_page_config(page_title="OCR para Tabela", layout="wide")

st.title("📸 OCR de Imagem para Tabela")
st.write("Cole ou envie um print, clique em processar e obtenha os dados em formato tabela.")

# Upload de imagem
uploaded_file = st.file_uploader("📥 Cole ou selecione uma imagem", type=["png", "jpg", "jpeg"])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Imagem carregada", use_column_width=True)

    if st.button("🚀 Processar Imagem"):
        with st.spinner("Processando..."):

            # Converter para OpenCV
            img = np.array(image)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Melhorar leitura OCR
            thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)[1]

            # OCR
            text = pytesseract.image_to_string(thresh, lang='por')

            st.subheader("📄 Texto extraído")
            st.text_area("Resultado bruto", text, height=200)

            # Tentar converter em tabela
            linhas = text.split("\n")
            dados = [linha.split() for linha in linhas if linha.strip() != ""]

            if len(dados) > 1:
                df = pd.DataFrame(dados)

                st.subheader("📊 Tabela estruturada")
                st.dataframe(df)

                # Área copiável
                st.subheader("📋 Copiar como tabela")
                csv = df.to_csv(index=False)
                st.text_area("Copie aqui", csv, height=200)

                st.download_button(
                    label="⬇️ Baixar CSV",
                    data=csv,
                    file_name="tabela.csv",
                    mime="text/csv"
                )
            else:
                st.warning("Não foi possível estruturar como tabela automaticamente.")