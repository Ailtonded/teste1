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
    
    # Campo Conciliar
    conciliar = st.sidebar.selectbox(
        "Conciliar",
        ["Adiantamento de fornecedor", "Fornecedor", "Cliente"]
    )
    
    # Ler todos os dados sem cabeçalho, garantindo que todas as colunas sejam texto
    df_raw = pd.read_excel(arquivo, sheet_name=aba, header=None, dtype=str)
    
    # Procurar linha com "Conta" e "Descricao"
    linha_header = None
    for i in range(len(df_raw)):
        col_a = str(df_raw.iloc[i, 0]) if pd.notna(df_raw.iloc[i, 0]) else ""
        col_b = str(df_raw.iloc[i, 1]) if pd.notna(df_raw.iloc[i, 1]) else ""
        
        if "Conta" in col_a and "Descricao" in col_b:
            linha_header = i
            break
    
    if linha_header is not None:
        # Usar linha encontrada como cabeçalho
        cabecalho = df_raw.iloc[linha_header]
        df = df_raw.iloc[linha_header + 1:].copy()
        df.columns = cabecalho
        
        # Limpar pontos da coluna Conta (já está como string)
        if "Conta" in df.columns:
            df["Conta"] = df["Conta"].astype(str).str.replace(".", "")
        
        # Manter apenas as colunas desejadas
        colunas_desejadas = ["Conta", "Descricao", "Saldo atual"]
        colunas_existentes = [col for col in colunas_desejadas if col in df.columns]
        
        if colunas_existentes:
            df = df[colunas_existentes]
        
        # Aplicar filtro se selecionar "Fornecedor"
        if conciliar == "Fornecedor" and "Conta" in df.columns:
            df = df[df["Conta"].astype(str).str.startswith("2103001001")]
    else:
        # Se não encontrou, exibir normalmente
        df = pd.read_excel(arquivo, sheet_name=aba)
    
    # Exibir dados
    st.dataframe(df.astype(str), use_container_width=True)
    
else:
    st.info("Envie um arquivo Excel na sidebar")