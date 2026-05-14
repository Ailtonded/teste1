import streamlit as st
import speech_recognition as sr
import soundfile as sf
import tempfile
import numpy as np
from scipy.io.wavfile import write

st.title("🎙️ Transcrição de Áudio WhatsApp")

arquivo = st.file_uploader(
    "Envie um áudio .ogg",
    type=["ogg"]
)

if arquivo:

    st.audio(arquivo)

    # salvar arquivo temporário
    with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as temp_ogg:
        temp_ogg.write(arquivo.read())
        ogg_path = temp_ogg.name

    # ler ogg
    data, samplerate = sf.read(ogg_path)

    # converter para PCM 16 bits
    data = (data * 32767).astype(np.int16)

    wav_path = ogg_path.replace(".ogg", ".wav")

    # salvar wav
    write(
        wav_path,
        samplerate,
        data
    )

    recognizer = sr.Recognizer()

    with sr.AudioFile(wav_path) as source:
        audio = recognizer.record(source)

    try:

        texto = recognizer.recognize_google(
            audio,
            language="pt-BR"
        )

        st.success("✅ Transcrição concluída!")

        st.text_area(
            "Texto Transcrito",
            texto,
            height=300
        )

        # análise
        palavras = texto.split()

        st.subheader("📊 Análise")

        st.write(f"Total de palavras: {len(palavras)}")
        st.write(f"Total de caracteres: {len(texto)}")

    except Exception as e:
        st.error(f"Erro ao transcrever: {e}")