import streamlit as st
import re
import pandas as pd

st.set_page_config(layout="wide")

st.markdown("""
<style>
[data-testid="stDataFrame"] div {
    white-space: normal !important;
}
</style>
""", unsafe_allow_html=True)

# =========================
# 🔹 FUNÇÕES
# =========================
def extrair_tag(texto, tag):
    padrao = fr"<{tag}>(.*?)</{tag}>"
    resultado = re.search(padrao, texto, re.DOTALL)
    return resultado.group(1).strip() if resultado else ""

def extrair_blocos(texto, tag):
    padrao = fr"<{tag}>(.*?)</{tag}>"
    return re.findall(padrao, texto, re.DOTALL)

def tratar_data(valor):
    return valor.split("T")[0] if valor and "T" in valor else valor

def traduz_indIEDest(valor):
    mapa = {
        "1": "1 - Contribuinte ICMS",
        "2": "2 - Isento de IE",
        "9": "9 - Não Contribuinte"
    }
    return mapa.get(valor, valor)

# =========================
# 🔹 INTERFACE
# =========================
st.title("📦 Leitor de XML - Itens")

arquivo = st.file_uploader("Selecione o XML", type=["xml"])

if arquivo:
    xml = arquivo.read().decode("utf-8", errors="ignore")

    # =========================
    # 🔹 EMIT
    # =========================
    emit = extrair_tag(xml, "emit")

    dados_emit = {
        "Emit_xFant": extrair_tag(emit, "xFant"),
        "Emit_CNPJ": extrair_tag(emit, "CNPJ"),
        "Emit_UF": extrair_tag(emit, "UF"),
        "Emit_IE": extrair_tag(emit, "IE"),
    }

    # =========================
    # 🔹 DEST
    # =========================
    dest = extrair_tag(xml, "dest")

    dados_dest = {
        "Dest_Nome": extrair_tag(dest, "xNome"),
        "Dest_CNPJ": extrair_tag(dest, "CNPJ"),
        "Dest_UF": extrair_tag(dest, "UF"),
        "Dest_IndIEDest": traduz_indIEDest(extrair_tag(dest, "indIEDest")),
    }

    # =========================
    # 🔹 IDE
    # =========================
    dados_ide = {
        "mod": extrair_tag(xml, "mod"),
        "nNF": extrair_tag(xml, "nNF"),
        "dhEmi": tratar_data(extrair_tag(xml, "dhEmi")),
        "dhSaiEnt": tratar_data(extrair_tag(xml, "dhSaiEnt")),
        "serie": extrair_tag(xml, "serie"),
        "natOp": extrair_tag(xml, "natOp"),
    }

    # =========================
    # 🔹 DET (ITENS)
    # =========================
    dets = extrair_blocos(xml, "det")

    linhas = []

    for det in dets:
        prod = extrair_tag(det, "prod")
        imposto = extrair_tag(det, "imposto")
        ibscbs = extrair_tag(imposto, "IBSCBS")

        linha = {}

        # 🔹 Dados fixos
        linha.update(dados_emit)
        linha.update(dados_dest)
        linha.update(dados_ide)

        # 🔹 Item
        linha["nItem"] = extrair_tag(det, "nItem")

        # 🔹 PROD
        linha["cProd"] = extrair_tag(prod, "cProd")
        linha["xProd"] = extrair_tag(prod, "xProd")
        linha["NCM"] = extrair_tag(prod, "NCM")
        linha["CFOP"] = extrair_tag(prod, "CFOP")
        linha["qCom"] = extrair_tag(prod, "qCom")
        linha["vUnCom"] = extrair_tag(prod, "vUnCom")
        linha["vProd"] = extrair_tag(prod, "vProd")

        # 🔹 IBSCBS
        linha["CST_IBS"] = extrair_tag(ibscbs, "CST")
        linha["vBC_IBS"] = extrair_tag(ibscbs, "vBC")
        linha["pCBS"] = extrair_tag(ibscbs, "pCBS")
        linha["vCBS"] = extrair_tag(ibscbs, "vCBS")
        linha["pIBSUF"] = extrair_tag(ibscbs, "pIBSUF")
        linha["vIBSUF"] = extrair_tag(ibscbs, "vIBSUF")

        linhas.append(linha)

    df = pd.DataFrame(linhas)

    # =========================
    # 🔹 EXIBE
    # =========================
    st.subheader("📊 Itens da Nota")
    st.dataframe(df, use_container_width=True, height=400)