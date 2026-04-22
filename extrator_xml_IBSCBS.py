import streamlit as st
import re
import pandas as pd

# =========================
# 🔹 LAYOUT
# =========================
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

def limpar_tags(valor):
    return re.sub(r"<.*?>", "", valor).strip() if valor else ""

def extrair_tag(texto, tag):
    if not texto:
        return ""
    padrao = fr"<{tag}[^>]*>(.*?)</{tag}>"
    resultado = re.search(padrao, texto, re.DOTALL | re.IGNORECASE)
    return limpar_tags(resultado.group(1)) if resultado else ""

def extrair_blocos(texto, tag):
    if not texto:
        return []
    padrao = fr"<{tag}[^>]*>(.*?)</{tag}>"
    return re.findall(padrao, texto, re.DOTALL | re.IGNORECASE)

def tratar_data(valor):
    return valor.split("T")[0] if valor and "T" in valor else valor

def traduz_indIEDest(valor):
    mapa = {
        "1": "1 - Contribuinte ICMS",
        "2": "2 - Isento de IE",
        "9": "9 - Não Contribuinte"
    }
    return mapa.get(valor, valor)

def to_float(valor):
    try:
        return float(valor.replace(",", "."))
    except:
        return None

# =========================
# 🔹 ICMS DINÂMICO
# =========================
def extrair_icms(imposto):
    icms = extrair_tag(imposto, "ICMS")

    tipos = [
        "ICMS00","ICMS10","ICMS20","ICMS30",
        "ICMS40","ICMS51","ICMS60","ICMS70","ICMS90"
    ]

    for tipo in tipos:
        bloco = extrair_tag(icms, tipo)
        if bloco:
            dados = {"ICMS_Tipo": tipo}

            campos = [
                "orig","CST","modBC","pRedBC","vBC","pICMS","vICMS",
                "pST","pRedBCEfet","vBCEfet","vBCSTRet",
                "vICMSEfet","vICMSSubstituto","vICMSSTRet","pICMSEfet"
            ]

            for campo in campos:
                dados[f"{tipo}_{campo}"] = extrair_tag(bloco, campo)

            return dados

    return {}

# =========================
# 🔹 IBSCBS FLEXÍVEL
# =========================
def extrair_ibscbs(imposto):
    ibs = extrair_tag(imposto, "IBSCBS")
    g = extrair_tag(ibs, "gIBSCBS")

    dados = {}

    dados["IBSCBS_CST"] = extrair_tag(ibs, "CST")
    dados["IBSCBS_cClassTrib"] = extrair_tag(ibs, "cClassTrib")

    dados["IBSCBS_vBC"] = extrair_tag(g, "vBC")
    dados["IBSCBS_vIBS"] = extrair_tag(g, "vIBS")

    # CBS
    gCBS = extrair_tag(g, "gCBS")
    dados["IBSCBS_pCBS"] = extrair_tag(gCBS, "pCBS")
    dados["IBSCBS_vCBS"] = extrair_tag(gCBS, "vCBS")
    dados["IBSCBS_vDevTrib_CBS"] = extrair_tag(gCBS, "vDevTrib")

    # IBS UF
    gUF = extrair_tag(g, "gIBSUF")
    dados["IBSCBS_pIBSUF"] = extrair_tag(gUF, "pIBSUF")
    dados["IBSCBS_vIBSUF"] = extrair_tag(gUF, "vIBSUF")
    dados["IBSCBS_vDevTrib_IBSUF"] = extrair_tag(gUF, "vDevTrib")

    # IBS MUN
    gMun = extrair_tag(g, "gIBSMun")
    dados["IBSCBS_pIBSMun"] = extrair_tag(gMun, "pIBSMun")
    dados["IBSCBS_vIBSMun"] = extrair_tag(gMun, "vIBSMun")

    return dados

# =========================
# 🔹 APP
# =========================

st.title("📦 Leitor de XML - SUPER ROBUSTO")

arquivo = st.file_uploader("Selecione o XML", type=["xml"])

if arquivo:
    xml = arquivo.read().decode("utf-8", errors="ignore")

    # 🔹 EMITENTE
    emit = extrair_tag(xml, "emit")

    dados_emit = {
        "Emit_xFant": extrair_tag(emit, "xFant"),
        "Emit_CNPJ": extrair_tag(emit, "CNPJ"),
        "Emit_UF": extrair_tag(emit, "UF"),
        "Emit_IE": extrair_tag(emit, "IE"),
    }

    # 🔹 DESTINATÁRIO
    dest = extrair_tag(xml, "dest")

    dados_dest = {
        "Dest_Nome": extrair_tag(dest, "xNome"),
        "Dest_CNPJ": extrair_tag(dest, "CNPJ"),
        "Dest_UF": extrair_tag(dest, "UF"),
        "Dest_IndIEDest": traduz_indIEDest(extrair_tag(dest, "indIEDest")),
    }

    # 🔹 IDE
    dados_ide = {
        "mod": extrair_tag(xml, "mod"),
        "nNF": extrair_tag(xml, "nNF"),
        "dhEmi": tratar_data(extrair_tag(xml, "dhEmi")),
        "dhSaiEnt": tratar_data(extrair_tag(xml, "dhSaiEnt")),
        "serie": extrair_tag(xml, "serie"),
        "natOp": extrair_tag(xml, "natOp"),
    }

    # 🔹 ITENS
    dets = extrair_blocos(xml, "det")

    linhas = []

    for det in dets:
        prod = extrair_tag(det, "prod")
        imposto = extrair_tag(det, "imposto")

        linha = {}

        # 🔹 FIXOS
        linha.update(dados_emit)
        linha.update(dados_dest)
        linha.update(dados_ide)

        # 🔹 ITEM
        linha["nItem"] = extrair_tag(det, "nItem")

        # 🔹 PROD
        linha["cEAN"] = extrair_tag(prod, "cEAN")
        linha["cProd"] = extrair_tag(prod, "cProd")
        linha["xProd"] = extrair_tag(prod, "xProd")
        linha["NCM"] = extrair_tag(prod, "NCM")
        linha["CFOP"] = extrair_tag(prod, "CFOP")
        linha["CEST"] = extrair_tag(prod, "CEST")
        linha["cBenef"] = extrair_tag(prod, "cBenef")
        linha["qCom"] = extrair_tag(prod, "qCom")
        linha["vUnCom"] = extrair_tag(prod, "vUnCom")
        linha["vProd"] = extrair_tag(prod, "vProd")
        linha["uCom"] = extrair_tag(prod, "uCom")
        linha["uTrib"] = extrair_tag(prod, "uTrib")
        linha["qTrib"] = extrair_tag(prod, "qTrib")
        linha["vUnTrib"] = extrair_tag(prod, "vUnTrib")

        # 🔹 IBSCBS
        linha.update(extrair_ibscbs(imposto))

        # 🔹 ICMS
        linha.update(extrair_icms(imposto))

        linhas.append(linha)

    df = pd.DataFrame(linhas)

    # 🔹 CONVERSÃO NUMÉRICA AUTOMÁTICA
    for col in df.columns:
        if any(x in col for x in ["v", "p", "q"]):
            df[col] = df[col].apply(to_float)

    # =========================
    # 🔹 EXIBE
    # =========================
    st.subheader("📊 Itens da Nota")
    st.dataframe(df, use_container_width=True, height=600)

    # =========================
    # 🔹 EXPORTAR EXCEL
    # =========================
    def gerar_excel(df):
        from io import BytesIO
        output = BytesIO()
        df.to_excel(output, index=False)
        return output.getvalue()

    excel = gerar_excel(df)

    st.download_button(
        "📥 Baixar Excel",
        data=excel,
        file_name="nota_fiscal.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )