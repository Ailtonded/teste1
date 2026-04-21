import streamlit as st
import re
import pandas as pd

# 🔹 Layout tela cheia
st.set_page_config(layout="wide")

# 🔹 CSS para quebra de texto
st.markdown("""
<style>
[data-testid="stDataFrame"] div {
    white-space: normal !important;
}
</style>
""", unsafe_allow_html=True)

# 🔹 Funções
def extrair_tag(texto, tag):
    padrao = fr"<{tag}>(.*?)</{tag}>"
    resultado = re.search(padrao, texto, re.DOTALL)
    return resultado.group(1).strip() if resultado else ""

def extrair_bloco(texto, tag):
    padrao = fr"<{tag}>(.*?)</{tag}>"
    resultado = re.search(padrao, texto, re.DOTALL)
    return resultado.group(1) if resultado else ""

def tratar_data(valor):
    if valor and "T" in valor:
        return valor.split("T")[0]
    return valor

def traduz_indIEDest(valor):
    mapa = {
        "1": "1 - Contribuinte ICMS",
        "2": "2 - Isento de IE",
        "9": "9 - Não Contribuinte"
    }
    return mapa.get(valor, valor)

# 🔹 Interface
st.title("📄 Leitor de XML (Tabela Única)")

arquivo = st.file_uploader("Selecione o XML", type=["xml"])

if arquivo:
    xml = arquivo.read().decode("utf-8", errors="ignore")

    # =========================
    # 🔹 EMITENTE
    # =========================
    emit = extrair_bloco(xml, "emit")

    dados_emit = {
        "Emit_xFant": extrair_tag(emit, "xFant"),
        "Emit_CNPJ": extrair_tag(emit, "CNPJ"),
        "Emit_UF": extrair_tag(emit, "UF"),
        "Emit_IE": extrair_tag(emit, "IE"),
    }

    # =========================
    # 🔹 DESTINATÁRIO
    # =========================
    dest = extrair_bloco(xml, "dest")

    ind_ie = extrair_tag(dest, "indIEDest")

    dados_dest = {
        "Dest_Nome": extrair_tag(dest, "xNome"),
        "Dest_CNPJ": extrair_tag(dest, "CNPJ"),
        "Dest_UF": extrair_tag(dest, "UF"),
        "Dest_IndIEDest": traduz_indIEDest(ind_ie),
    }

    # =========================
    # 🔹 IDE (limpo)
    # =========================
    campos_ide = [
        "mod", "nNF",
        "dhEmi", "dhSaiEnt",
        "serie", "natOp"
    ]

    dados_ide = {}

    for tag in campos_ide:
        valor = extrair_tag(xml, tag)

        if tag in ["dhEmi", "dhSaiEnt"]:
            valor = tratar_data(valor)

        dados_ide[tag] = valor

    # =========================
    # 🔹 JUNTA TUDO
    # =========================
    dados_final = {**dados_emit, **dados_dest, **dados_ide}

    df = pd.DataFrame([dados_final])

    # =========================
    # 🔹 EXIBE
    # =========================
    st.subheader("📊 Dados da Nota")
    st.dataframe(df, use_container_width=True, height=300)