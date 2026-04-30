import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import re

# Configuração da página - LAYOUT WIDE E OTIMIZADO
st.set_page_config(
    page_title="Visualizador de Lançamentos Contábeis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS PERSONALIZADO PARA MELHORAR VISUAL
st.markdown("""
<style>
    /* Remover espaços em branco */
    .main > div {
        padding-top: 0rem;
        padding-bottom: 0rem;
    }
    
    /* Ajustar containers */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
        max-width: 100%;
    }
    
    /* Estilo para diferença positiva (pendência de débito) */
    .diferenca-positiva {
        color: #dc3545;
        font-weight: bold;
    }
    
    /* Estilo para diferença negativa (pendência de crédito) */
    .diferenca-negativa {
        color: #ffc107;
        font-weight: bold;
    }
    
    /* Cards de métricas */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    
    /* Título dos filtros */
    .filters-title {
        font-size: 1.2rem;
        font-weight: bold;
        margin-bottom: 1rem;
        color: #2c3e50;
    }
    
    /* DataFrame com altura maior */
    .stDataFrame {
        height: auto !important;
    }
    
    /* Customização das tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
        background-color: #f8f9fa;
        padding: 0.5rem;
        border-radius: 10px;
    }
    
    .stTabs [data-baseweb="tab"] {
        font-size: 1rem;
        font-weight: bold;
        padding: 0.5rem 1rem;
    }
    
    /* Highlight para linhas da tabela de pendências */
    .dataframe tbody tr:hover {
        background-color: #f0f2f6;
        cursor: pointer;
    }
</style>
""", unsafe_allow_html=True)

def encontrar_aba_correta(excel_file):
    """
    Encontra a aba que contém "3-Lançamentos Contábeis" no nome.
    Se não encontrar, retorna a primeira aba.
    """
    try:
        abas = pd.ExcelFile(excel_file).sheet_names
        for aba in abas:
            if "3-Lançamentos Contábeis" in aba:
                return aba
        return abas[0] if abas else None
    except Exception as e:
        st.error(f"Erro ao ler as abas do arquivo: {str(e)}")
        return None

def encontrar_linha_cabecalho(df):
    """
    Procura na coluna A (primeira coluna) uma célula que contenha a palavra "Conta".
    """
    if df.empty:
        return None
    
    primeira_coluna = df.iloc[:, 0].astype(str)
    
    for idx, valor in enumerate(primeira_coluna):
        if pd.notna(valor) and "conta" in str(valor).lower():
            return idx
    
    return None

def formatar_data(valor):
    """
    Tenta converter um valor para o formato de data brasileiro (DD/MM/YYYY)
    """
    try:
        if isinstance(valor, str):
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d', '%d-%m-%Y']:
                try:
                    data = datetime.strptime(valor.strip(), fmt)
                    return data.strftime('%d/%m/%Y')
                except:
                    continue
            return valor
        elif isinstance(valor, (datetime, pd.Timestamp)):
            return valor.strftime('%d/%m/%Y')
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
        valor_str = str(valor)
        numeros = ''.join(filter(str.isdigit, valor_str))
        if len(numeros) >= num_digitos:
            return numeros[:num_digitos]
        else:
            return numeros
    except:
        return ''

def extrair_nf(texto):
    """
    Extrai o número da Nota Fiscal a partir do texto do histórico.
    """
    if pd.isna(texto) or not isinstance(texto, str):
        return ""
    
    try:
        texto_limpo = texto.replace('\n', ' ').replace('\r', ' ').strip()
        padrao = r'(?:NF\.|TIT\.)\s*(\d+)'
        match = re.search(padrao, texto_limpo, re.IGNORECASE)
        if match:
            return match.group(1)
        else:
            return ""
    except Exception as e:
        return ""

def calcular_movimento(row, col_credito, col_debito):
    """
    Calcula o movimento: Crédito - Débito
    """
    try:
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

def converter_para_float(valor):
    """
    Converte string com vírgula para float
    """
    try:
        if isinstance(valor, str):
            valor = valor.replace(',', '.')
            return float(valor)
        elif isinstance(valor, (int, float)):
            return float(valor)
        else:
            return 0.0
    except:
        return 0.0

def aplicar_filtros(df, filtros):
    """
    Aplica os filtros dinâmicos no DataFrame
    """
    df_filtrado = df.copy()
    
    # Filtro Conta (contains)
    if filtros.get('conta') and filtros['conta'] != '':
        if 'Conta' in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado['Conta'].str.contains(filtros['conta'], case=False, na=False)]
    
    # Filtro Lote
    if filtros.get('lote') and filtros['lote'] != '':
        col_lote = None
        for col in df_filtrado.columns:
            if 'lote' in col.lower():
                col_lote = col
                break
        if col_lote:
            df_filtrado = df_filtrado[df_filtrado[col_lote].astype(str).str.contains(filtros['lote'], case=False, na=False)]
    
    # Filtro Data (intervalo)
    if filtros.get('data_inicio') and filtros.get('data_fim'):
        col_data = None
        for col in df_filtrado.columns:
            if 'data' in col.lower():
                col_data = col
                break
        if col_data:
            df_filtrado['data_temp'] = pd.to_datetime(df_filtrado[col_data], format='%d/%m/%Y', errors='coerce')
            data_inicio = pd.to_datetime(filtros['data_inicio'])
            data_fim = pd.to_datetime(filtros['data_fim'])
            df_filtrado = df_filtrado[(df_filtrado['data_temp'] >= data_inicio) & (df_filtrado['data_temp'] <= data_fim)]
            df_filtrado = df_filtrado.drop(columns=['data_temp'])
    
    # Filtro NF_EXTRAIDA
    if filtros.get('nf_extraida') and filtros['nf_extraida'] != '':
        if 'NF_EXTRAIDA' in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado['NF_EXTRAIDA'].astype(str).str.contains(filtros['nf_extraida'], case=False, na=False)]
    
    # Filtro Movimento (faixa)
    if 'Movimento' in df_filtrado.columns:
        if filtros.get('movimento_min') is not None and filtros['movimento_min'] != '':
            df_filtrado['movimento_num'] = df_filtrado['Movimento'].str.replace(',', '.').astype(float)
            df_filtrado = df_filtrado[df_filtrado['movimento_num'] >= float(filtros['movimento_min'])]
        if filtros.get('movimento_max') is not None and filtros['movimento_max'] != '':
            if 'movimento_num' not in df_filtrado.columns:
                df_filtrado['movimento_num'] = df_filtrado['Movimento'].str.replace(',', '.').astype(float)
            df_filtrado = df_filtrado[df_filtrado['movimento_num'] <= float(filtros['movimento_max'])]
        if 'movimento_num' in df_filtrado.columns:
            df_filtrado = df_filtrado.drop(columns=['movimento_num'])
    
    # Filtro Débito
    col_debito = None
    for col in df_filtrado.columns:
        if 'debito' in col.lower():
            col_debito = col
            break
    
    if col_debito:
        if filtros.get('debito_min') is not None and filtros['debito_min'] != '':
            df_filtrado['debito_num'] = df_filtrado[col_debito].astype(str).str.replace(',', '.').astype(float)
            df_filtrado = df_filtrado[df_filtrado['debito_num'] >= float(filtros['debito_min'])]
        if filtros.get('debito_max') is not None and filtros['debito_max'] != '':
            if 'debito_num' not in df_filtrado.columns:
                df_filtrado['debito_num'] = df_filtrado[col_debito].astype(str).str.replace(',', '.').astype(float)
            df_filtrado = df_filtrado[df_filtrado['debito_num'] <= float(filtros['debito_max'])]
        if 'debito_num' in df_filtrado.columns:
            df_filtrado = df_filtrado.drop(columns=['debito_num'])
    
    # Filtro Crédito
    col_credito = None
    for col in df_filtrado.columns:
        if 'credito' in col.lower():
            col_credito = col
            break
    
    if col_credito:
        if filtros.get('credito_min') is not None and filtros['credito_min'] != '':
            df_filtrado['credito_num'] = df_filtrado[col_credito].astype(str).str.replace(',', '.').astype(float)
            df_filtrado = df_filtrado[df_filtrado['credito_num'] >= float(filtros['credito_min'])]
        if filtros.get('credito_max') is not None and filtros['credito_max'] != '':
            if 'credito_num' not in df_filtrado.columns:
                df_filtrado['credito_num'] = df_filtrado[col_credito].astype(str).str.replace(',', '.').astype(float)
            df_filtrado = df_filtrado[df_filtrado['credito_num'] <= float(filtros['credito_max'])]
        if 'credito_num' in df_filtrado.columns:
            df_filtrado = df_filtrado.drop(columns=['credito_num'])
    
    return df_filtrado

def analisar_pendencias(df):
    """
    Analisa pendências por Nota Fiscal
    Retorna DataFrame com NFs que não fecham (débito - crédito ≠ 0)
    """
    # Identificar colunas de Débito e Crédito
    col_debito = None
    col_credito = None
    
    for col in df.columns:
        if 'debito' in col.lower():
            col_debito = col
        elif 'credito' in col.lower():
            col_credito = col
    
    if not col_debito or not col_credito:
        st.warning("Colunas de Débito ou Crédito não encontradas para análise de pendências")
        return None
    
    # Criar uma cópia para análise
    df_analise = df[df['NF_EXTRAIDA'] != ""].copy()
    
    if df_analise.empty:
        st.info("Nenhuma Nota Fiscal encontrada para análise")
        return None
    
    # Converter valores para float de forma otimizada
    df_analise['DEBITO_NUM'] = df_analise[col_debito].astype(str).str.replace(',', '.').astype(float)
    df_analise['CREDITO_NUM'] = df_analise[col_credito].astype(str).str.replace(',', '.').astype(float)
    
    # Agrupar por NF_EXTRAIDA
    df_group = df_analise.groupby('NF_EXTRAIDA').agg({
        'DEBITO_NUM': 'sum',
        'CREDITO_NUM': 'sum'
    }).reset_index()
    
    # Calcular diferença
    df_group['DIFERENCA'] = df_group['DEBITO_NUM'] - df_group['CREDITO_NUM']
    
    # Arredondar para evitar problemas de precisão
    df_group['DIFERENCA'] = df_group['DIFERENCA'].round(2)
    
    # Filtrar apenas onde diferença ≠ 0
    df_pendencias = df_group[df_group['DIFERENCA'] != 0].copy()
    
    # Ordenar pelo maior valor absoluto da diferença
    df_pendencias['ABS_DIF'] = df_pendencias['DIFERENCA'].abs()
    df_pendencias = df_pendencias.sort_values('ABS_DIF', ascending=False)
    df_pendencias = df_pendencias.drop(columns=['ABS_DIF'])
    
    # Resetar índice
    df_pendencias = df_pendencias.reset_index(drop=True)
    
    return df_pendencias, col_debito, col_credito

def carregar_e_tratar_dados(arquivo, nome_aba):
    """
    Carrega a planilha, identifica o cabeçalho e trata os dados.
    """
    try:
        df_raw = pd.read_excel(arquivo, sheet_name=nome_aba, header=None)
        
        if df_raw.empty:
            st.warning("A planilha está vazia")
            return None
        
        linha_cabecalho = encontrar_linha_cabecalho(df_raw)
        
        if linha_cabecalho is None:
            st.warning("Coluna 'Conta' não encontrada na planilha")
            return None
        
        cabecalho = df_raw.iloc[linha_cabecalho].astype(str).tolist()
        cabecalho = [str(col).strip() if pd.notna(col) else f"Coluna_{i}" 
                    for i, col in enumerate(cabecalho)]
        
        for i, col in enumerate(cabecalho):
            if cabecalho.count(col) > 1:
                cabecalho[i] = f"{col}_{i}"
        
        df_dados = df_raw.iloc[linha_cabecalho + 1:].copy()
        df_dados.columns = cabecalho
        df_dados = df_dados.dropna(how='all')
        df_dados = df_dados.reset_index(drop=True)
        
        for col in df_dados.columns:
            df_dados[col] = df_dados[col].astype(str)
            df_dados[col] = df_dados[col].replace('nan', '')
        
        # Remover colunas específicas
        colunas_para_remover = ['C CUSTO', 'ITEM CONTA', 'COD CL VAL']
        for col in colunas_para_remover:
            if col in df_dados.columns:
                df_dados = df_dados.drop(columns=[col])
        
        # Extrair primeiros 6 dígitos do LOTE
        col_lote = None
        for col in df_dados.columns:
            if 'LOTE/SUB/DOC/LINHA' in col or 'LOTE' in col:
                col_lote = col
                break
        
        if col_lote:
            df_dados[col_lote] = df_dados[col_lote].apply(lambda x: extrair_primeiros_digitos(x, 6))
        
        # Filtrar FILIAL DE ORIGEM
        col_filial = None
        for col in df_dados.columns:
            if 'FILIAL DE ORIGEM' in col or 'FILIAL' in col:
                col_filial = col
                break
        
        if col_filial:
            df_dados = df_dados[df_dados[col_filial].str.strip() != '']
            df_dados = df_dados.reset_index(drop=True)
        
        # Extrair NF do HISTORICO
        col_historico = None
        for col in df_dados.columns:
            if 'historico' in col.lower():
                col_historico = col
                break
        
        if col_historico:
            df_dados['NF_EXTRAIDA'] = df_dados[col_historico].apply(extrair_nf)
        else:
            df_dados['NF_EXTRAIDA'] = ""
        
        # Identificar colunas de Crédito e Débito
        col_credito = None
        col_debito = None
        
        for col in df_dados.columns:
            if 'credito' in col.lower():
                col_credito = col
            elif 'debito' in col.lower():
                col_debito = col
        
        # Formatar DATA
        col_data = None
        for col in df_dados.columns:
            if 'data' in col.lower():
                col_data = col
                df_dados[col_data] = df_dados[col_data].apply(formatar_data)
                break
        
        # Calcular Movimento
        if col_credito and col_debito:
            df_dados['Movimento'] = df_dados.apply(
                lambda row: calcular_movimento(row, col_credito, col_debito), 
                axis=1
            )
            df_dados['Movimento'] = df_dados['Movimento'].apply(lambda x: f"{x:.2f}".replace('.', ','))
        
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
    
    # Sidebar para upload do arquivo
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
            df_original = carregar_e_tratar_dados(uploaded_file, encontrar_aba_correta(uploaded_file))
        
        if df_original is not None and not df_original.empty:
            
            # Criar TABS
            tab1, tab2 = st.tabs(["📋 Lançamentos", "⚠️ Pendências por NF"])
            
            # ========== TAB 1: LANÇAMENTOS (ORIGINAL) ==========
            with tab1:
                # Bloco de Filtros
                st.subheader("🔍 Filtros Dinâmicos")
                
                # Organizar filtros em colunas
                col1, col2, col3 = st.columns(3)
                col4, col5, col6 = st.columns(3)
                
                # Dicionário para armazenar valores dos filtros
                filtros = {}
                
                with col1:
                    st.markdown("**📋 Conta**")
                    filtros['conta'] = st.text_input("Conta (contém)", key="filtro_conta", placeholder="Digite parte da conta...")
                    
                    st.markdown("**🔢 Lote**")
                    filtros['lote'] = st.text_input("Lote", key="filtro_lote", placeholder="Número do lote...")
                
                with col2:
                    st.markdown("**📅 Data**")
                    col_data_atual = None
                    for col in df_original.columns:
                        if 'data' in col.lower():
                            col_data_atual = col
                            break
                    
                    if col_data_atual:
                        datas_validas = pd.to_datetime(df_original[col_data_atual], format='%d/%m/%Y', errors='coerce').dropna()
                        if not datas_validas.empty:
                            min_data = datas_validas.min().date()
                            max_data = datas_validas.max().date()
                            
                            filtros['data_inicio'] = st.date_input("Data inicial", value=min_data, key="filtro_data_ini")
                            filtros['data_fim'] = st.date_input("Data final", value=max_data, key="filtro_data_fim")
                        else:
                            filtros['data_inicio'] = st.date_input("Data inicial", key="filtro_data_ini")
                            filtros['data_fim'] = st.date_input("Data final", key="filtro_data_fim")
                    else:
                        filtros['data_inicio'] = st.date_input("Data inicial", key="filtro_data_ini")
                        filtros['data_fim'] = st.date_input("Data final", key="filtro_data_fim")
                
                with col3:
                    st.markdown("**🏷️ NF Extraída**")
                    filtros['nf_extraida'] = st.text_input("Número da NF", key="filtro_nf", placeholder="Digite o número da NF...")
                
                with col4:
                    st.markdown("**💰 Movimento**")
                    col1_min, col1_max = st.columns(2)
                    with col1_min:
                        filtros['movimento_min'] = st.text_input("Mínimo", key="filtro_mov_min", placeholder="0,00")
                    with col1_max:
                        filtros['movimento_max'] = st.text_input("Máximo", key="filtro_mov_max", placeholder="999.999,99")
                
                with col5:
                    st.markdown("**💸 Débito**")
                    col2_min, col2_max = st.columns(2)
                    with col2_min:
                        filtros['debito_min'] = st.text_input("Mínimo", key="filtro_deb_min", placeholder="0,00")
                    with col2_max:
                        filtros['debito_max'] = st.text_input("Máximo", key="filtro_deb_max", placeholder="999.999,99")
                
                with col6:
                    st.markdown("**💳 Crédito**")
                    col3_min, col3_max = st.columns(2)
                    with col3_min:
                        filtros['credito_min'] = st.text_input("Mínimo", key="filtro_cred_min", placeholder="0,00")
                    with col3_max:
                        filtros['credito_max'] = st.text_input("Máximo", key="filtro_cred_max", placeholder="999.999,99")
                
                # Botão para limpar filtros
                if st.button("🧹 Limpar todos os filtros", key="limpar_filtros", use_container_width=True):
                    st.rerun()
                
                st.markdown("---")
                
                # Aplicar filtros
                df_filtrado = aplicar_filtros(df_original, filtros)
                
                # Bloco de Métricas
                st.subheader("📊 Estatísticas")
                
                # Calcular métricas
                total_registros = len(df_filtrado)
                
                # Somar Débito
                col_debito = None
                for col in df_filtrado.columns:
                    if 'debito' in col.lower():
                        col_debito = col
                        break
                
                soma_debito = 0
                if col_debito:
                    soma_debito = df_filtrado[col_debito].astype(str).str.replace(',', '.').astype(float).sum()
                
                # Somar Crédito
                col_credito = None
                for col in df_filtrado.columns:
                    if 'credito' in col.lower():
                        col_credito = col
                        break
                
                soma_credito = 0
                if col_credito:
                    soma_credito = df_filtrado[col_credito].astype(str).str.replace(',', '.').astype(float).sum()
                
                # Somar Movimento
                soma_movimento = 0
                if 'Movimento' in df_filtrado.columns:
                    soma_movimento = df_filtrado['Movimento'].str.replace(',', '.').astype(float).sum()
                
                # Exibir métricas em 4 colunas
                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    st.metric("📄 Total de Registros", f"{total_registros:,}".replace(",", "."))
                with m2:
                    st.metric("💸 Total Débito", f"R$ {soma_debito:,.2f}".replace(",", "v").replace(".", ",").replace("v", "."))
                with m3:
                    st.metric("💳 Total Crédito", f"R$ {soma_credito:,.2f}".replace(",", "v").replace(".", ",").replace("v", "."))
                with m4:
                    st.metric("💰 Total Movimento", f"R$ {soma_movimento:,.2f}".replace(",", "v").replace(".", ",").replace("v", "."))
                
                st.markdown("---")
                
                # Bloco do Grid
                st.subheader("📋 Dados Detalhados")
                
                # Configurar altura dinâmica do DataFrame
                altura_grid = min(800, 200 + (len(df_filtrado) * 35))
                altura_grid = max(400, altura_grid)
                
                # Exibir DataFrame
                st.dataframe(
                    df_filtrado, 
                    use_container_width=True, 
                    height=altura_grid,
                    hide_index=True
                )
                
                st.caption(f"✅ Exibindo {len(df_filtrado)} de {len(df_original)} registros | 📊 {len(df_filtrado.columns)} colunas")
            
            # ========== TAB 2: PENDÊNCIAS POR NF ==========
            with tab2:
                st.subheader("⚠️ Notas Fiscais com Pendências")
                st.markdown("Identifica automaticamente NFs onde a soma dos débitos não equivale à soma dos créditos")
                
                # Analisar pendências
                with st.spinner("Analisando pendências por NF..."):
                    resultado = analisar_pendencias(df_original)
                    
                    if resultado is not None:
                        df_pendencias, col_debito, col_credito = resultado
                        
                        if not df_pendencias.empty:
                            # Métricas das pendências
                            total_nfs_pendentes = len(df_pendencias)
                            total_diferenca = df_pendencias['DIFERENCA'].sum()
                            total_debito_pendente = df_pendencias['DEBITO_NUM'].sum()
                            total_credito_pendente = df_pendencias['CREDITO_NUM'].sum()
                            
                            # Exibir métricas
                            col_a, col_b, col_c, col_d = st.columns(4)
                            with col_a:
                                st.metric("⚠️ NFs com Pendência", f"{total_nfs_pendentes}")
                            with col_b:
                                st.metric("💰 Total Débito Pendente", f"R$ {total_debito_pendente:,.2f}".replace(",", "v").replace(".", ",").replace("v", "."))
                            with col_c:
                                st.metric("💳 Total Crédito Pendente", f"R$ {total_credito_pendente:,.2f}".replace(",", "v").replace(".", ",").replace("v", "."))
                            with col_d:
                                cor_diferenca = "inverse" if total_diferenca < 0 else "normal"
                                st.metric("📊 Diferença Total", f"R$ {total_diferenca:,.2f}".replace(",", "v").replace(".", ",").replace("v", "."), delta_color=cor_diferenca)
                            
                            st.markdown("---")
                            
                            # Formatar DataFrame para exibição
                            df_exibicao = df_pendencias.copy()
                            df_exibicao['DEBITO_NUM'] = df_exibicao['DEBITO_NUM'].apply(lambda x: f"R$ {x:,.2f}".replace(",", "v").replace(".", ",").replace("v", "."))
                            df_exibicao['CREDITO_NUM'] = df_exibicao['CREDITO_NUM'].apply(lambda x: f"R$ {x:,.2f}".replace(",", "v").replace(".", ",").replace("v", "."))
                            df_exibicao['DIFERENCA'] = df_exibicao['DIFERENCA'].apply(lambda x: f"R$ {x:,.2f}".replace(",", "v").replace(".", ",").replace("v", "."))
                            
                            # Renomear colunas
                            df_exibicao.columns = ['NF', 'Débito Total', 'Crédito Total', 'Diferença']
                            
                            # Exibir tabela de pendências
                            st.dataframe(
                                df_exibicao,
                                use_container_width=True,
                                height=400,
                                hide_index=True
                            )
                            
                            # Diferencial: Permitir ver detalhes da NF
                            st.markdown("---")
                            st.subheader("🔍 Detalhamento por NF")
                            st.markdown("Clique no botão abaixo para ver os lançamentos de uma NF específica:")
                            
                            # Selectbox para escolher NF
                            nf_selecionada = st.selectbox(
                                "Selecione uma NF para visualizar os detalhes:",
                                options=df_pendencias['NF_EXTRAIDA'].tolist(),
                                key="select_nf"
                            )
                            
                            if nf_selecionada:
                                # Filtrar lançamentos da NF selecionada
                                df_detalhes = df_original[df_original['NF_EXTRAIDA'] == nf_selecionada].copy()
                                
                                st.markdown(f"**Detalhes da NF: {nf_selecionada}**")
                                st.markdown(f"📄 Total de lançamentos: {len(df_detalhes)}")
                                
                                # Exibir métricas da NF específica
                                col_e, col_f, col_g = st.columns(3)
                                
                                # Calcular totais da NF
                                soma_debito_nf = df_detalhes[col_debito].astype(str).str.replace(',', '.').astype(float).sum()
                                soma_credito_nf = df_detalhes[col_credito].astype(str).str.replace(',', '.').astype(float).sum()
                                diferenca_nf = soma_debito_nf - soma_credito_nf
                                
                                with col_e:
                                    st.metric("💸 Débito Total", f"R$ {soma_debito_nf:,.2f}".replace(",", "v").replace(".", ",").replace("v", "."))
                                with col_f:
                                    st.metric("💳 Crédito Total", f"R$ {soma_credito_nf:,.2f}".replace(",", "v").replace(".", ",").replace("v", "."))
                                with col_g:
                                    st.metric("⚠️ Diferença", f"R$ {diferenca_nf:,.2f}".replace(",", "v").replace(".", ",").replace("v", "."), 
                                             delta_color="inverse" if diferenca_nf < 0 else "normal")
                                
                                # Exibir lançamentos detalhados
                                st.markdown("**Lançamentos detalhados:**")
                                st.dataframe(
                                    df_detalhes,
                                    use_container_width=True,
                                    height=300,
                                    hide_index=True
                                )
                            
                        else:
                            st.success("🎉 Todas as Notas Fiscais estão conciliadas! Nenhuma pendência encontrada.")
                            
                            # Mostrar estatísticas de NFs processadas
                            total_nfs = df_original[df_original['NF_EXTRAIDA'] != ""]['NF_EXTRAIDA'].nunique()
                            st.info(f"📊 Total de NFs processadas: {total_nfs} - Todas estão regulares!")
                    
                    else:
                        st.warning("Não foi possível analisar pendências devido à falta de colunas necessárias")
        
        elif df_original is not None and df_original.empty:
            st.warning("⚠️ Nenhum dado encontrado após o processamento")
    
    else:
        # Mensagem quando nenhum arquivo foi carregado
        st.info("👈 Faça upload de um arquivo Excel na barra lateral para começar")
        
        # Mostrar exemplo do layout
        with st.expander("ℹ️ Como funciona a análise de pendências?"):
            st.markdown("""
            ### 🔍 Conciliação Contábil Automática
            
            A análise de pendências identifica automaticamente Notas Fiscais onde os valores não estão conciliados:
            
            **Regra de negócio:**