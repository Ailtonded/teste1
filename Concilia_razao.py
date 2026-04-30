import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import re

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

def extrair_primeiros_digitos(valor, num_digitos=6):
    """
    Extrai os primeiros N dígitos de um valor, ignorando caracteres não numéricos
    """
    try:
        # Converter para string
        valor_str = str(valor)
        
        # Remover caracteres não numéricos e pegar apenas números
        numeros = ''.join(filter(str.isdigit, valor_str))
        
        # Pegar os primeiros N dígitos
        if len(numeros) >= num_digitos:
            return numeros[:num_digitos]
        else:
            return numeros  # Retorna o que tem se for menor
    except:
        return ''

def extrair_nf(texto):
    """
    Extrai o número da Nota Fiscal a partir do texto do histórico.
    
    Regras:
    - Busca por padrões "NF." ou "TIT." seguido de números
    - Remove quebras de linha
    - Retorna apenas os dígitos encontrados
    
    Args:
        texto (str): Texto do histórico
        
    Returns:
        str: Número da NF extraído ou string vazia se não encontrar
    """
    # Verificar se o valor é nulo ou não é string
    if pd.isna(texto) or not isinstance(texto, str):
        return ""
    
    try:
        # Remover quebras de linha e espaços extras
        texto_limpo = texto.replace('\n', ' ').replace('\r', ' ').strip()
        
        # REGEX OTIMIZADA: busca por NF. ou TIT. seguido de opcional espaço e números
        # - (?:NF\.|TIT\.) : grupo não capturador para NF. ou TIT.
        # - \s* : zero ou mais espaços
        # - (\d+) : grupo capturador com um ou mais dígitos
        padrao = r'(?:NF\.|TIT\.)\s*(\d+)'
        
        # Procurar o padrão no texto
        match = re.search(padrao, texto_limpo, re.IGNORECASE)
        
        if match:
            # Retornar apenas os dígitos encontrados
            return match.group(1)
        else:
            return ""
            
    except Exception as e:
        # Em caso de erro, retornar vazio sem quebrar o sistema
        return ""

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
            try:
                credito = float(valor_credito)
            except:
                credito = 0
        
        if pd.notna(row[col_debito]) and row[col_debito] != '':
            valor_debito = str(row[col_debito]).replace(',', '.')
            try:
                debito = float(valor_debito)
            except:
                debito = 0
        
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
        
        # REMOVER COLUNAS ESPECÍFICAS
        colunas_para_remover = ['C CUSTO', 'ITEM CONTA', 'COD CL VAL']
        for col in colunas_para_remover:
            if col in df_dados.columns:
                df_dados = df_dados.drop(columns=[col])
        
        # EXTRAIR PRIMEIROS 6 DÍGITOS DA COLUNA 'LOTE/SUB/DOC/LINHA'
        col_lote = None
        for col in df_dados.columns:
            if 'LOTE/SUB/DOC/LINHA' in col or 'LOTE' in col:
                col_lote = col
                break
        
        if col_lote:
            df_dados[col_lote] = df_dados[col_lote].apply(lambda x: extrair_primeiros_digitos(x, 6))
        
        # FILTRAR COLUNA 'FILIAL DE ORIGEM' (remover linhas vazias)
        col_filial = None
        for col in df_dados.columns:
            if 'FILIAL DE ORIGEM' in col or 'FILIAL' in col:
                col_filial = col
                break
        
        if col_filial:
            # Remover linhas onde a coluna FILIAL está vazia
            df_dados = df_dados[df_dados[col_filial].str.strip() != '']
            df_dados = df_dados.reset_index(drop=True)
        
        # ========== NOVA FUNCIONALIDADE: EXTRAIR NF DO HISTORICO ==========
        # Detectar automaticamente a coluna "HISTORICO" (case insensitive)
        col_historico = None
        for col in df_dados.columns:
            if 'historico' in col.lower():
                col_historico = col
                break
        
        # Criar a coluna NF_EXTRAIDA se a coluna HISTORICO existir
        if col_historico:
            # Aplicar a função extrair_nf em todos os registros de forma vetorizada
            df_dados['NF_EXTRAIDA'] = df_dados[col_historico].apply(extrair_nf)
        else:
            # Se não encontrar a coluna HISTORICO, criar a coluna vazia como fallback
            df_dados['NF_EXTRAIDA'] = ""
            st.info("ℹ️ Coluna 'HISTORICO' não encontrada. Coluna NF_EXTRAIDA criada vazia.")
        # ========== FIM DA NOVA FUNCIONALIDADE ==========
        
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
            
            # Mostrar estatísticas após processamento
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📊 Total de Registros", len(df))
            with col2:
                # Contar quantas NFs foram extraídas com sucesso
                nfs_encontradas = df[df['NF_EXTRAIDA'] != ""].shape[0]
                st.metric("🏷️ NFs Extraídas", nfs_encontradas)
            with col3:
                st.metric("📋 Total de Colunas", len(df.columns))
        
        elif df is not None and df.empty:
            st.warning("⚠️ Nenhum dado encontrado após o processamento")
    
    else:
        # Mensagem quando nenhum arquivo foi carregado
        st.info("👈 Faça upload de um arquivo Excel na barra lateral para começar")

# Executar o aplicativo
if __name__ == "__main__":
    main()