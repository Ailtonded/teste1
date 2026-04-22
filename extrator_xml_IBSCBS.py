import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from io import BytesIO

st.set_page_config(layout="wide")
st.title("📦 Leitor de XML - SUPER ROBUSTO")

uploaded_file = st.file_uploader("Selecione o XML", type="xml")

# -------------------------------
# FUNÇÕES AUXILIARES
# -------------------------------
def remove_namespace(tag):
    return tag.split("}")[-1]

def formatar_data(data):
    if data:
        return data.split("T")[0]
    return ""

def indIEDest_desc(valor):
    mapa = {
        "1": "1 - Contribuinte ICMS",
        "2": "2 - Isento",
        "9": "9 - Não Contribuinte"
    }
    return mapa.get(valor, valor)

def get_text(node, tag):
    el = node.find(tag)
    return el.text if el is not None else ""

# -------------------------------
# PROCESSAMENTO
# -------------------------------
if uploaded_file:
    tree = ET.parse(uploaded_file)
    root = tree.getroot()

    # REMOVE NAMESPACE (CRUCIAL)
    for elem in root.iter():
        elem.tag = remove_namespace(elem.tag)

    # GARANTE INFNFE
    infNFe = root.find(".//infNFe")

    ide = infNFe.find("ide")
    emit = infNFe.find("emit")
    dest = infNFe.find("dest")

    # EMITENTE
    emit_xFant = get_text(emit, "xFant")
    emit_CNPJ = get_text(emit, "CNPJ")
    emit_UF = get_text(emit.find("enderEmit"), "UF") if emit.find("enderEmit") else ""
    emit_IE = get_text(emit, "IE")

    # DESTINATÁRIO
    dest_nome = get_text(dest, "xNome")
    dest_CNPJ = get_text(dest, "CNPJ")
    dest_UF = get_text(dest.find("enderDest"), "UF") if dest.find("enderDest") else ""
    dest_indIE = indIEDest_desc(get_text(dest, "indIEDest"))

    # IDE
    mod = get_text(ide, "mod")
    nNF = get_text(ide, "nNF")
    dhEmi = formatar_data(get_text(ide, "dhEmi"))
    dhSaiEnt = formatar_data(get_text(ide, "dhSaiEnt"))
    serie = get_text(ide, "serie")
    natOp = get_text(ide, "natOp")

    dados = []

    # ITENS
    for det in infNFe.findall("det"):
        nItem = get_text(det, "nItem")

        prod = det.find("prod")

        imposto = det.find("imposto")

        # PRODUTO
        item = {
            "Emit_xFant": emit_xFant,
            "Emit_CNPJ": emit_CNPJ,
            "Emit_UF": emit_UF,
            "Emit_IE": emit_IE,
            "Dest_Nome": dest_nome,
            "Dest_CNPJ": dest_CNPJ,
            "Dest_UF": dest_UF,
            "Dest_IndIEDest": dest_indIE,
            "mod": mod,
            "nNF": nNF,
            "dhEmi": dhEmi,
            "dhSaiEnt": dhSaiEnt,
            "serie": serie,
            "natOp": natOp,
            "nItem": nItem,
            "cEAN": get_text(prod, "cEAN"),
            "cProd": get_text(prod, "cProd"),
            "xProd": get_text(prod, "xProd"),
            "NCM": get_text(prod, "NCM"),
            "CFOP": get_text(prod, "CFOP"),
            "CEST": get_text(prod, "CEST"),
            "cBenef": get_text(prod, "cBenef"),
            "qCom": get_text(prod, "qCom"),
            "vUnCom": get_text(prod, "vUnCom"),
            "vProd": get_text(prod, "vProd"),
            "uCom": get_text(prod, "uCom"),
            "uTrib": get_text(prod, "uTrib"),
            "qTrib": get_text(prod, "qTrib"),
            "vUnTrib": get_text(prod, "vUnTrib"),
        }

        # ---------------- IBSCBS ----------------
        ibscbs = imposto.find("IBSCBS") if imposto is not None else None
        if ibscbs is not None:
            g = ibscbs.find("gIBSCBS")

            item.update({
                "IBSCBS_CST": get_text(ibscbs, "CST"),
                "IBSCBS_cClassTrib": get_text(ibscbs, "cClassTrib"),
                "IBSCBS_vBC": get_text(g, "vBC") if g else "",
                "IBSCBS_vIBS": get_text(g, "vIBS") if g else "",
            })

            # CBS
            gCBS = g.find("gCBS") if g is not None else None
            if gCBS is not None:
                item["IBSCBS_pCBS"] = get_text(gCBS, "pCBS")
                item["IBSCBS_vCBS"] = get_text(gCBS, "vCBS")
                item["IBSCBS_vDevTrib_CBS"] = get_text(gCBS.find("gDevTrib"), "vDevTrib") if gCBS.find("gDevTrib") else ""

            # IBS UF
            gIBSUF = g.find("gIBSUF") if g is not None else None
            if gIBSUF is not None:
                item["IBSCBS_pIBSUF"] = get_text(gIBSUF, "pIBSUF")
                item["IBSCBS_vIBSUF"] = get_text(gIBSUF, "vIBSUF")
                item["IBSCBS_vDevTrib_IBSUF"] = get_text(gIBSUF.find("gDevTrib"), "vDevTrib") if gIBSUF.find("gDevTrib") else ""

            # IBS Mun
            gIBSMun = g.find("gIBSMun") if g is not None else None
            if gIBSMun is not None:
                item["IBSCBS_pIBSMun"] = get_text(gIBSMun, "pIBSMun")
                item["IBSCBS_vIBSMun"] = get_text(gIBSMun, "vIBSMun")

        # ---------------- ICMS DINÂMICO ----------------
        icms = imposto.find("ICMS") if imposto is not None else None
        if icms is not None and list(icms):
            tipo_icms = list(icms)[0]
            for child in tipo_icms:
                item[f"ICMS_{remove_namespace(tipo_icms.tag)}_{child.tag}"] = child.text

        dados.append(item)

    df = pd.DataFrame(dados)

    st.subheader("📊 Itens da Nota")
    st.dataframe(df, use_container_width=True)

    # ---------------- EXPORTAR EXCEL ----------------
    output = BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')

    st.download_button(
        label="📥 Baixar XLSX",
        data=output.getvalue(),
        file_name="nota_fiscal.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )