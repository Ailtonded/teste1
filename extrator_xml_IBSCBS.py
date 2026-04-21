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
st.title("📦 Leitor de XML - Itens Completo")

arquivo = st.file_uploader("Selecione o XML", type=["xml"])

if arquivo:
    xml = arquivo.read().decode("utf-8", errors="ignore")

    # =========================
    # 🔹 EMITENTE
    # =========================
    emit = extrair_tag(xml, "emit")

    dados_emit = {
        "Emit_xFant": extrair_tag(emit, "xFant"),
        "Emit_CNPJ": extrair_tag(emit, "CNPJ"),
        "Emit_UF": extrair_tag(emit, "UF"),
        "Emit_IE": extrair_tag(emit, "IE"),
    }

    # =========================
    # 🔹 DESTINATÁRIO
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
    # 🔹 ITENS (DET)
    # =========================
    dets = extrair_blocos(xml, "det")

    linhas = []

    for det in dets:
        prod = extrair_tag(det, "prod")
        imposto = extrair_tag(det, "imposto")
        ibscbs = extrair_tag(imposto, "IBSCBS")

        linha = {}

        # 🔹 FIXOS
        linha.update(dados_emit)
        linha.update(dados_dest)
        linha.update(dados_ide)

        # 🔹 ITEM
        linha["nItem"] = extrair_tag(det, "nItem")

        # =========================
        # 🔹 PROD
        # =========================
        linha["cEAN"] = extrair_tag(prod, "cEAN")
        linha["cProd"] = extrair_tag(prod, "cProd")
        linha["xProd"] = extrair_tag(prod, "xProd")
        linha["NCM"] = extrair_tag(prod, "NCM")
        linha["CFOP"] = extrair_tag(prod, "CFOP")
        linha["CEST"] = extrair_tag(prod, "CEST")
        linha["cBenef"] = extrair_tag(prod, "cBenef")  # 👈 incluído
        linha["qCom"] = extrair_tag(prod, "qCom")
        linha["vUnCom"] = extrair_tag(prod, "vUnCom")
        linha["vProd"] = extrair_tag(prod, "vProd")
        linha["uCom"] = extrair_tag(prod, "uCom")
        linha["uTrib"] = extrair_tag(prod, "uTrib")
        linha["qTrib"] = extrair_tag(prod, "qTrib")
        linha["vUnTrib"] = extrair_tag(prod, "vUnTrib")

        # =========================
        # 🔹 IBSCBS COMPLETO
        # =========================
        linha["IBSCBS_CST"] = extrair_tag(ibscbs, "CST")
        linha["IBSCBS_cClassTrib"] = extrair_tag(ibscbs, "cClassTrib")

        # Base
        linha["IBSCBS_vBC"] = extrair_tag(ibscbs, "vBC")
        linha["IBSCBS_vIBS"] = extrair_tag(ibscbs, "vIBS")

        # CBS
        linha["IBSCBS_pCBS"] = extrair_tag(ibscbs, "pCBS")
        linha["IBSCBS_vCBS"] = extrair_tag(ibscbs, "vCBS")

        gCBS = extrair_tag(ibscbs, "gCBS")
        linha["IBSCBS_vDevTrib_CBS"] = extrair_tag(gCBS, "vDevTrib")

        # IBS UF
        linha["IBSCBS_pIBSUF"] = extrair_tag(ibscbs, "pIBSUF")
        linha["IBSCBS_vIBSUF"] = extrair_tag(ibscbs, "vIBSUF")

        gIBSUF = extrair_tag(ibscbs, "gIBSUF")
        linha["IBSCBS_vDevTrib_IBSUF"] = extrair_tag(gIBSUF, "vDevTrib")

        # IBS Municipal
        linha["IBSCBS_pIBSMun"] = extrair_tag(ibscbs, "pIBSMun")
        linha["IBSCBS_vIBSMun"] = extrair_tag(ibscbs, "vIBSMun")

        linhas.append(linha)

    df = pd.DataFrame(linhas)

    # =========================
    # 🔹 EXIBE
    # =========================
    st.subheader("📊 Itens da Nota")
    st.dataframe(df, use_container_width=True, height=500)