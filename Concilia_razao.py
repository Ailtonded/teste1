import streamlit as st
import pandas as pd
import numpy as np

# Configuração da página
st.set_page_config(
    page_title="Visualizador de Lançamentos Contábeis",
    page_icon="📊",
    layout="wide"
)

def encontrar_aba_correta(excel_file):
    """
    Encontra a aba que contém "3-Lançamentos Contábeis" no nome.
    Se não encontrar, retorna a primeira aba.
    """
    try:
        # Obter todas as abas do arquivo
        abas = pd.ExcelFile(excel_file).sheet_names
        
        # Procurar aba com o nome específico
        for aba in abas:
            if "3-Lançamentos Contábeis" in aba:
                return aba
        
        # Se não encontrou, retorna a primeira aba
        return abas[0] if abas else None
    
    except Exception as e:
        st.error(f"Erro ao ler as abas do arquivo: {str(e)}")
        return None

def encontrar_linha_cabecalho(df):
    """
    Procura na coluna A (primeira coluna) uma célula que contenha a palavra "Conta".
    Retorna o índice da linha encontrada ou None se não encontrar.
    """
    if df.empty:
        return None
    
    # Converter a primeira coluna para string para facilitar a busca
    primeira_coluna = df.iloc[:, 0].astype(str)
    
    # Procurar por "Conta" (case-insensitive)
    for idx, valor in enumerate(primeira_coluna):
        if pd.notna(valor) and "conta" in str(valor).lower():
            return idx
    
    return None

def carregar_e_tratar_dados(arquivo, nome_aba):
    """
    Carrega a planilha, identifica o cabeçalho e trata os dados.
    """
    try:
        # Ler a planilha sem cabeçalho
        df_raw = pd.read_excel(arquivo, sheet_name=nome_aba, header=None)
        
        if df_raw.empty:
            st.warning("A planilha está vazia")
            return None
        
        # Encontrar a linha do cabeçalho
        linha_cabecalho = encontrar_linha_cabecalho(df_raw)
        
        if linha_cabecalho is None:
            st.warning("Coluna 'Conta' não encontrada na planilha")
            return None
        
        # Definir o cabeçalho a partir da linha encontrada
        cabecalho = df_raw.iloc[linha_cabecalho].astype(str).tolist()
        
        # Remover espaços dos nomes das colunas
        cabecalho = [str(col).strip() if pd.notna(col) else f"Coluna_{i}" 
                    for i, col in enumerate(cabecalho)]
        
        # Garantir que não haja colunas duplicadas
        for i, col in enumerate(cabecalho):
            if cabecalho.count(col) > 1:
                cabecalho[i] = f"{col}_{i}"
        
        # Criar DataFrame com os dados a partir da linha seguinte
        df_dados = df_raw.iloc[linha_cabecalho + 1:].copy()
        
        # Atribuir os cabeçalhos
        df_dados.columns = cabecalho
        
        # Remover linhas completamente vazias
        df_dados = df_dados.dropna(how='all')
        
        # Resetar o índice
        df_dados = df_dados.reset_index(drop=True)
        
        # Converter todas as colunas para string inicialmente
        for col in df_dados.columns:
            df_dados[col] = df_dados[col].astype(str)
            # Substituir 'nan' por string vazia
            df_dados[col] = df_dados[col].replace('nan', '')
        
        return df_dados
    
    except Exception as e:
        st.error(f"Erro ao processar os dados: {str(e)}")
        return None

def main():
    """
    Função principal do aplicativo Streamlit
    """
    # Título principal
    st.title("📊 Visualizador - Lançamentos Contábeis")
    st.markdown("---")
    
    # Sidebar para upload
    with st.sidebar:
        st.header("📂 Carregar Arquivo")
        uploaded_file = st.file_uploader(
            "Escolha um arquivo Excel",
            type=['xlsx', 'xls'],
            help="Upload de arquivos Excel com extensão .xlsx ou .xls"
        )
    
    # Área principal
    if uploaded_file is not None:
        with st.spinner("Processando arquivo..."):
            df = carregar_e_tratar_dados(uploaded_file, encontrar_aba_correta(uploaded_file))
        
        if df is not None and not df.empty:
            # Exibir DataFrame completo
            st.dataframe(df, use_container_width=True, height=500)
        
        elif df is not None and df.empty:
            st.warning("⚠️ Nenhum dado encontrado após o processamento")
    
    else:
        # Mensagem quando nenhum arquivo foi carregado
        st.info("👈 Faça upload de um arquivo Excel na barra lateral para começar")

# Executar o aplicativo
if __name__ == "__main__":
    main()