import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from io import BytesIO

st.set_page_config(layout="wide")

st.title("📄 Leitor XML NF-e → Excel")

# =========================
# FUNÇÃO SAFE GET
# =========================
def get_text(parent, tag):
    if parent is None:
        return ""
    el = parent.find(f".//{tag}")
    return el.text if el is not None else ""


# =========================
# PARSER XML
# =========================
def parse_xml(xml_content):

    try:
        root = ET.fromstring(xml_content)
    except:
        return []

    # Remove namespace
    for elem in root.iter():
        if "}" in elem.tag:
            elem.tag = elem.tag.split("}", 1)[1]

    infNFe = root.find(".//infNFe")
    if infNFe is None:
        return []

    emit = infNFe.find("emit")
    dest = infNFe.find("dest")
    ide  = infNFe.find("ide")

    dets = infNFe.findall("det")

    linhas = []

    for det in dets:
        prod = det.find("prod")
        ibscbs = det.find(".//IBSCBS")

        linhas.append({
            "Emit_xFant": get_text(emit, "xFant"),
            "Emit_CNPJ": get_text(emit, "CNPJ"),
            "Emit_UF": get_text(emit, "UF"),
            "Emit_IE": get_text(emit, "IE"),

            "Dest_Nome": get_text(dest, "xNome"),
            "Dest_CNPJ": get_text(dest, "CNPJ"),
            "Dest_UF": get_text(dest, "UF"),
            "Dest_IndIEDest": get_text(dest, "indIEDest"),

            "mod": get_text(ide, "mod"),
            "nNF": get_text(ide, "nNF"),
            "dhEmi": get_text(ide, "dhEmi"),
            "dhSaiEnt": get_text(ide, "dhSaiEnt"),
            "serie": get_text(ide, "serie"),
            "natOp": get_text(ide, "natOp"),

            "nItem": det.attrib.get("nItem", ""),

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

            "IBSCBS_CST": get_text(ibscbs, "CST"),
            "IBSCBS_cClassTrib": get_text(ibscbs, "cClassTrib"),
            "IBSCBS_vBC": get_text(ibscbs, "vBC"),
            "IBSCBS_vIBS": get_text(ibscbs, "vIBS"),

            "IBSCBS_pCBS": get_text(ibscbs, "pCBS"),
            "IBSCBS_vCBS": get_text(ibscbs, "vCBS"),

            "IBSCBS_vDevTrib_CBS": get_text(ibscbs, "vDevTrib"),

            "IBSCBS_pIBSUF": get_text(ibscbs, "pIBSUF"),
            "IBSCBS_vIBSUF": get_text(ibscbs, "vIBSUF"),

            "IBSCBS_vDevTrib_IBSUF": get_text(ibscbs, "vDevTrib"),

            "IBSCBS_pIBSMun": get_text(ibscbs, "pIBSMun"),
            "IBSCBS_vIBSMun": get_text(ibscbs, "vIBSMun"),
        })

    return linhas


# =========================
# UPLOAD DE ARQUIVOS
# =========================
st.subheader("📂 Upload de XMLs")
uploaded_files = st.file_uploader(
    "Selecione um ou mais XMLs",
    type=["xml"],
    accept_multiple_files=True
)

dados = []

if uploaded_files:
    for file in uploaded_files:
        content = file.read().decode("utf-8")
        dados.extend(parse_xml(content))

    st.success(f"{len(dados)} itens carregados")


# =========================
# COLAR XML
# =========================
st.subheader("📋 Ou cole o XML")

xml_text = st.text_area("Cole aqui o XML")

if st.button("Ler XML colado"):
    dados = parse_xml(xml_text)
    st.success(f"{len(dados)} itens carregados")


# =========================
# MOSTRAR TABELA
# =========================
if dados:
    df = pd.DataFrame(dados)

    st.subheader("📊 Preview")
    st.dataframe(df, use_container_width=True)

    # =========================
    # DOWNLOAD XLSX
    # =========================
    output = BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")

    st.download_button(
        label="💾 Baixar Excel",
        data=output.getvalue(),
        file_name="nfe.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )