import streamlit as st
import speech_recognition as sr
import soundfile as sf
import tempfile
import scipy.io.wavfile as wavfile

st.title("🎙️ Transcrição de Áudio WhatsApp")

arquivo = st.file_uploader(
    "Envie um áudio .ogg",
    type=["ogg"]
)

if arquivo:

    st.audio(arquivo)

    # salvar ogg temporário
    with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as temp_ogg:
        temp_ogg.write(arquivo.read())
        ogg_path = temp_ogg.name

    # converter usando soundfile
    data, samplerate = sf.read(ogg_path)

    wav_path = ogg_path.replace(".ogg", ".wav")

    wavfile.write(
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

        # palavras mais comuns
        frequencia = {}

        for p in palavras:
            p = p.lower()

            if p in frequencia:
                frequencia[p] += 1
            else:
                frequencia[p] = 1

        top = sorted(
            frequencia.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        st.write("### 🔥 Palavras mais usadas")

        for palavra, qtd in top:
            st.write(f"{palavra}: {qtd}")

    except Exception as e:
        st.error(f"Erro ao transcrever: {e}")