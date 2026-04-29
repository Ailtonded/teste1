import streamlit as st
import pandas as pd

# Configuração da página
st.set_page_config(page_title="Visualizador de Excel", layout="wide")

# Barra lateral
with st.sidebar:
    st.header("📁 Upload do Arquivo")
    arquivo = st.file_uploader("Carregar arquivo Excel", type=["xlsx", "xls"])

# Área principal
st.title("📊 Visualizador de Excel")

if arquivo is not None:
    # Ler o arquivo
    excel_file = pd.ExcelFile(arquivo)
    
    # Se houver múltiplas abas, permitir seleção
    if len(excel_file.sheet_names) > 1:
        aba = st.selectbox("Selecione a aba:", excel_file.sheet_names)
    else:
        aba = excel_file.sheet_names[0]
    
    # Ler e exibir os dados
    df = pd.read_excel(arquivo, sheet_name=aba)
    st.dataframe(df, use_container_width=True)
    
else:
    st.info("👈 Faça o upload de um arquivo Excel na barra lateral")