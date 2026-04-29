import streamlit as st
import pandas as pd

st.set_page_config(page_title="Excel Viewer", layout="wide")

with st.sidebar:
    st.header("Upload")
    arquivo1 = st.file_uploader("Arquivo Excel - Plano de Contas", type=["xlsx", "xls"])
    arquivo2 = st.file_uploader("Arquivo Excel - Posicao dos Titulos", type=["xlsx", "xls"])

st.title("Visualizador de Excel")

# Processar primeiro arquivo
df_contabil = None
if arquivo1:
    excel = pd.ExcelFile(arquivo1)
    
    # Procurar aba "Plano de contas"
    aba_selecionada = None
    for sheet in excel.sheet_names:
        if "Plano" in sheet or sheet == "Plano de contas":
            aba_selecionada = sheet
            break
    
    if aba_selecionada is None:
        aba_selecionada = excel.sheet_names[0]
    
    # Ler todos os dados sem cabeçalho
    df_raw = pd.read_excel(arquivo1, sheet_name=aba_selecionada, header=None, dtype=str)
    
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
        
        # Tratamento da coluna Conta (apenas remover pontos)
        if "Conta" in df.columns:
            df["Conta"] = df["Conta"].astype(str).str.replace(".", "")
        
        # Manter apenas as colunas desejadas
        colunas_desejadas = ["Conta", "Descricao", "Saldo atual"]
        colunas_existentes = [col for col in colunas_desejadas if col in df.columns]
        
        if colunas_existentes:
            df = df[colunas_existentes]
        
        # Aplicar filtro com prefixo correto
        if "Conta" in df.columns:
            df_contabil = df[df["Conta"].astype(str).str.startswith("2103001")]
    else:
        # Se não encontrou, exibir normalmente
        df_contabil = pd.read_excel(arquivo1, sheet_name=aba_selecionada)

# Processar segundo arquivo
df_financeiro = None
if arquivo2:
    excel2 = pd.ExcelFile(arquivo2)
    
    # Procurar aba com "Posicao dos Titulos"
    aba_financeiro = None
    for sheet in excel2.sheet_names:
        if "Posicao" in sheet or "Titulos" in sheet:
            aba_financeiro = sheet
            break
    
    if aba_financeiro is None:
        aba_financeiro = excel2.sheet_names[0]
    
    # Ler dados crus
    df_financeiro = pd.read_excel(arquivo2, sheet_name=aba_financeiro, dtype=str)
    
    # Tratamento da coluna "Codigo-Nome do Fornecedor"
    if "Codigo-Nome do Fornecedor" in df_financeiro.columns:
        # Fazer split pelo hífen
        split_df = df_financeiro["Codigo-Nome do Fornecedor"].astype(str).str.split("-", expand=True)
        
        # Criar as novas colunas
        df_financeiro.insert(0, "Cod Fornecedor", split_df[0])
        df_financeiro.insert(1, "Loja", split_df[1])

# Exibir abas
if df_contabil is not None or df_financeiro is not None:
    tab1, tab2 = st.tabs(["Saldo Contabil", "Saldo Financeiro"])
    
    with tab1:
        if df_contabil is not None:
            st.subheader("📋 Saldo Contábil")
            st.dataframe(df_contabil, use_container_width=True)
        else:
            st.info("Nenhum arquivo de plano de contas carregado")
    
    with tab2:
        if df_financeiro is not None:
            st.subheader("📋 Saldo Financeiro")
            st.dataframe(df_financeiro, use_container_width=True)
        else:
            st.info("Nenhum arquivo de posição dos títulos carregado")
else:
    st.info("Envie os dois arquivos Excel na sidebar para visualizar os dados")