import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

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

def formatar_data(valor):
    """
    Tenta converter um valor para o formato de data brasileiro (DD/MM/YYYY)
    """
    try:
        # Se for string, tenta converter
        if isinstance(valor, str):
            # Tenta diferentes formatos
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d', '%d-%m-%Y']:
                try:
                    data = datetime.strptime(valor.strip(), fmt)
                    return data.strftime('%d/%m/%Y')
                except:
                    continue
            return valor
        # Se for datetime
        elif isinstance(valor, (datetime, pd.Timestamp)):
            return valor.strftime('%d/%m/%Y')
        # Se for número (Excel)
        elif isinstance(valor, (int, float)):
            try:
                data = pd.Timestamp.fromordinal(int(valor) - 693594)
                return data.strftime('%d/%m/%Y')
            except:
                return str(valor)
        else:
            return str(valor)
    except:
        return str(valor)

def calcular_movimento(row, col_credito, col_debito):
    """
    Calcula o movimento: Crédito - Débito
    """
    try:
        # Converter para número, tratando vírgula como separador decimal
        credito = 0
        debito = 0
        
        if pd.notna(row[col_credito]) and row[col_credito] != '':
            valor_credito = str(row[col_credito]).replace(',', '.')
            credito = float(valor_credito) if valor_credito.replace('.', '').replace('-', '').isdigit() else 0
        
        if pd.notna(row[col_debito]) and row[col_debito] != '':
            valor_debito = str(row[col_debito]).replace(',', '.')
            debito = float(valor_debito) if valor_debito.replace('.', '').replace('-', '').isdigit() else 0
        
        return credito - debito
    except:
        return 0

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
        
        # Identificar colunas de Crédito e Débito (case-insensitive)
        col_credito = None
        col_debito = None
        
        for col in df_dados.columns:
            if 'credito' in col.lower():
                col_credito = col
            elif 'debito' in col.lower():
                col_debito = col
        
        # Formatar coluna DATA se existir
        col_data = None
        for col in df_dados.columns:
            if 'data' in col.lower():
                col_data = col
                df_dados[col_data] = df_dados[col_data].apply(formatar_data)
                break
        
        # Calcular coluna Movimento
        if col_credito and col_debito:
            df_dados['Movimento'] = df_dados.apply(
                lambda row: calcular_movimento(row, col_credito, col_debito), 
                axis=1
            )
            # Formatar Movimento com 2 casas decimais
            df_dados['Movimento'] = df_dados['Movimento'].apply(lambda x: f"{x:.2f}".replace('.', ','))
        else:
            st.warning("Colunas 'Crédito' e/ou 'Débito' não encontradas para calcular o movimento")
        
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