import streamlit as st
import pandas as pd

st.set_page_config(page_title="Excel Viewer", layout="wide")

with st.sidebar:
    st.header("Upload")
    arquivo = st.file_uploader("Arquivo Excel", type=["xlsx", "xls"])

st.title("Visualizador de Excel")

if arquivo:
    excel = pd.ExcelFile(arquivo)
    aba = st.sidebar.selectbox("Aba", excel.sheet_names)
    df = pd.read_excel(arquivo, sheet_name=aba)
    st.dataframe(df.astype(str), use_container_width=True)
else:
    st.info("Envie um arquivo Excel na sidebar")