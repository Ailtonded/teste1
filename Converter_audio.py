# app.py
# =========================================================
# Transcritor de Áudio WhatsApp (.ogg) com análise de texto
#
# Instalação:
# pip install streamlit openai-whisper ffmpeg-python textblob pandas
#
# Também é necessário instalar o FFmpeg:
# Windows:
# https://www.gyan.dev/ffmpeg/builds/
#
# Executar:
# streamlit run app.py
# =========================================================

import streamlit as st
import whisper
import tempfile
import os
import pandas as pd
from textblob import TextBlob
from collections import Counter
import re

# =========================
# CONFIG STREAMLIT
# =========================
st.set_page_config(
    page_title="Transcritor WhatsApp",
    page_icon="🎙️",
    layout="wide"
)

st.title("🎙️ Transcritor de Áudio WhatsApp (.ogg)")
st.write("Envie um áudio do WhatsApp em formato `.ogg` para transcrever e analisar o conteúdo.")

# =========================
# CARREGAR MODELO WHISPER
# =========================
@st.cache_resource
def load_model():
    return whisper.load_model("base")

model = load_model()

# =========================
# FUNÇÕES
# =========================
def limpar_texto(texto):
    texto = texto.lower()
    texto = re.sub(r"[^\w\s]", "", texto)
    return texto

def analisar_texto(texto):
    texto_limpo = limpar_texto(texto)

    palavras = texto_limpo.split()

    total_palavras = len(palavras)
    palavras_unicas = len(set(palavras))

    palavras_comuns = Counter(palavras).most_common(10)

    blob = TextBlob(texto)

    sentimento = blob.sentiment.polarity

    if sentimento > 0:
        sentimento_desc = "😊 Positivo"
    elif sentimento < 0:
        sentimento_desc = "😠 Negativo"
    else:
        sentimento_desc = "😐 Neutro"

    return {
        "total_palavras": total_palavras,
        "palavras_unicas": palavras_unicas,
        "palavras_comuns": palavras_comuns,
        "sentimento": sentimento_desc,
        "score_sentimento": sentimento
    }

# =========================
# UPLOAD
# =========================
uploaded_file = st.file_uploader(
    "Escolha um arquivo .ogg",
    type=["ogg"]
)

if uploaded_file:

    st.audio(uploaded_file)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp_file:
        tmp_file.write(uploaded_file.read())
        temp_audio_path = tmp_file.name

    st.info("⏳ Transcrevendo áudio...")

    try:
        result = model.transcribe(temp_audio_path, language="pt")

        texto = result["text"]

        st.success("✅ Transcrição concluída!")

        # =========================
        # TEXTO TRANSCRITO
        # =========================
        st.subheader("📝 Texto Transcrito")

        st.text_area(
            "Resultado",
            texto,
            height=250
        )

        # =========================
        # ANÁLISE
        # =========================
        analise = analisar_texto(texto)

        st.subheader("📊 Análise do Texto")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total de palavras", analise["total_palavras"])

        with col2:
            st.metric("Palavras únicas", analise["palavras_unicas"])

        with col3:
            st.metric("Sentimento", analise["sentimento"])

        st.write("---")

        st.subheader("🔤 Palavras mais utilizadas")

        df = pd.DataFrame(
            analise["palavras_comuns"],
            columns=["Palavra", "Quantidade"]
        )

        st.dataframe(df, use_container_width=True)

        # =========================
        # DOWNLOAD TXT
        # =========================
        st.download_button(
            label="📥 Baixar transcrição",
            data=texto,
            file_name="transcricao.txt",
            mime="text/plain"
        )

    except Exception as e:
        st.error(f"Erro ao processar áudio: {e}")

    finally:
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)