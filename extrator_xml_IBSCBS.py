import streamlit as st
import re

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

    xFant = extrair_tag(emit, "xFant")
    CNPJ = extrair_tag(emit, "CNPJ")
    UF = extrair_tag(emit, "UF")
    IE = extrair_tag(emit, "IE")

    st.subheader("📄 Emitente")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("xFant", xFant)
    col2.metric("CNPJ", CNPJ)
    col3.metric("UF", UF)
    col4.metric("IE", IE)

    # =========================
    # 🔹 IDE
    # =========================
    st.subheader("🧾 Identificação")

    campos_ide = [
        "tpNF", "mod", "indPres", "tpImp", "nNF",
        "cMunFG", "procEmi", "finNFe", "dhEmi",
        "tpAmb", "indFinal", "dhSaiEnt",
        "serie", "natOp"
    ]

    valores = [extrair_tag(xml, tag) for tag in campos_ide]

    # quebra em linhas de 4 colunas
    for i in range(0, len(campos_ide), 4):
        cols = st.columns(4)
        for j in range(4):
            if i + j < len(campos_ide):
                cols[j].metric(campos_ide[i + j], valores[i + j])