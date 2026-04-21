import streamlit as st
import re
import pandas as pd

def extrair_tag(texto, tag):
    padrao = fr"<{tag}>(.*?)</{tag}>"
    resultado = re.search(padrao, texto, re.DOTALL)
    return resultado.group(1).strip() if resultado else ""

def extrair_bloco(texto, tag):
    padrao = fr"<{tag}>(.*?)</{tag}>"
    resultado = re.search(padrao, texto, re.DOTALL)
    return resultado.group(1) if resultado else ""

st.title("Leitor de XML (modo texto)")

arquivo = st.file_uploader("Selecione o XML", type=["xml"])

if arquivo:
    xml = arquivo.read().decode("utf-8", errors="ignore")

    # =========================
    # 🔹 EMIT
    # =========================
    emit = extrair_bloco(xml, "emit")

    dados_emit = {
        "xFant": extrair_tag(emit, "xFant"),
        "CNPJ": extrair_tag(emit, "CNPJ"),
        "UF": extrair_tag(emit, "UF"),
        "IE": extrair_tag(emit, "IE"),
    }

    df_emit = pd.DataFrame([dados_emit])  # 👈 uma linha

    # =========================
    # 🔹 IDE
    # =========================
    campos_ide = [
        "tpNF", "mod", "indPres", "tpImp", "nNF",
        "cMunFG", "procEmi", "finNFe", "dhEmi",
        "tpAmb", "indFinal", "dhSaiEnt",
        "serie", "natOp"
    ]

    dados_ide = {tag: extrair_tag(xml, tag) for tag in campos_ide}

    df_ide = pd.DataFrame([dados_ide])  # 👈 horizontal

    # =========================
    # 🔹 EXIBIÇÃO
    # =========================
    st.subheader("📄 Emitente")
    st.dataframe(df_emit, use_container_width=True)

    st.subheader("🧾 Identificação da Nota")
    st.dataframe(df_ide, use_container_width=True)