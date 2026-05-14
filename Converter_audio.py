import streamlit as st
import speech_recognition as sr
from pydub import AudioSegment
import tempfile

st.title("Transcrição de Áudio WhatsApp")

audio_file = st.file_uploader(
    "Envie um áudio .ogg",
    type=["ogg"]
)

if audio_file:

    st.audio(audio_file)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as temp_ogg:
        temp_ogg.write(audio_file.read())
        ogg_path = temp_ogg.name

    wav_path = ogg_path.replace(".ogg", ".wav")

    # converter ogg -> wav
    audio = AudioSegment.from_ogg(ogg_path)
    audio.export(wav_path, format="wav")

    recognizer = sr.Recognizer()

    with sr.AudioFile(wav_path) as source:
        audio_data = recognizer.record(source)

    try:
        texto = recognizer.recognize_google(
            audio_data,
            language="pt-BR"
        )

        st.success("Transcrição concluída!")

        st.text_area(
            "Texto",
            texto,
            height=300
        )

        # análise simples
        palavras = texto.split()

        st.write("### Análise")
        st.write(f"Quantidade de palavras: {len(palavras)}")
        st.write(f"Quantidade de caracteres: {len(texto)}")

    except Exception as e:
        st.error(f"Erro: {e}")