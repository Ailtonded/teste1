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
    
    # Ler todos os dados sem cabeçalho
    df_raw = pd.read_excel(arquivo, sheet_name=aba, header=None)
    
    # Procurar linha com "Conta" na coluna A e "Descricao" na coluna B
    linha_header = None
    for i in range(len(df_raw)):
        col_a = str(df_raw.iloc[i, 0]) if pd.notna(df_raw.iloc[i, 0]) else ""
        col_b = str(df_raw.iloc[i, 1]) if pd.notna(df_raw.iloc[i, 1]) else ""
        
        if "Conta" in col_a and "Descricao" in col_b:
            linha_header = i
            break
    
    # Se encontrou, usar como cabeçalho
    if linha_header is not None:
        cabecalho = df_raw.iloc[linha_header]
        df = df_raw.iloc[linha_header + 1:].copy()
        df.columns = cabecalho
    else:
        # Se não encontrou, usar primeira linha como cabeçalho
        df = pd.read_excel(arquivo, sheet_name=aba)
    
    # Exibir dados
    st.dataframe(df.astype(str), use_container_width=True)
    
else:
    st.info("Envie um arquivo Excel na sidebar")