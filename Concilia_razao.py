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

# CSS PERSONALIZADO
st.markdown("""
<style>
    .main > div { padding-top: 0rem; padding-bottom: 0rem; }
    .block-container { padding-top: 1rem; padding-bottom: 0rem; max-width: 100%; }
    .stTabs [data-baseweb="tab-list"] { gap: 2rem; background-color: #f8f9fa; padding: 0.5rem; border-radius: 10px; }
    .stTabs [data-baseweb="tab"] { font-size: 1rem; font-weight: bold; padding: 0.5rem 1rem; }
    .footer-stats { font-size: 0.75rem; color: #666; text-align: center; padding: 1rem; margin-top: 2rem; border-top: 1px solid #ddd; background-color: #f8f9fa; border-radius: 5px; }
    .footer-stats span { margin: 0 1rem; }
    .streamlit-expanderHeader { background-color: #f0f2f6; border-radius: 5px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ==================================================
# FUNÇÃO CRÍTICA: CONVERSÃO MONETÁRIA ROBUSTA
# ==================================================
def converter_para_float(valor):
    """
    Converte string monetária para float de forma robusta.
    
    Trata:
    - Separaadores de milhar (1.234,56 -> 1234.56)
    - Vírgula decimal (87,80 -> 87.80)
    - Valores vazios, nulos ou inválidos
    - Diferentes formatos de entrada
    
    Args:
        valor: Valor a ser convertido (string, int, float, None)
    
    Returns:
        float: Valor convertido ou 0.0 em caso de erro
    """
    if pd.isna(valor) or valor == '' or valor is None:
        return 0.0
    
    try:
        # Se já for número, retorna como float
        if isinstance(valor, (int, float)):
            return float(valor)
        
        # Converte para string e remove espaços
        valor_str = str(valor).strip()
        
        if not valor_str or valor_str == 'nan':
            return 0.0
        
        # REGRA CRÍTICA: Remover separadores de milhar (pontos)
        # Mas preservar a última vírgula que é o separador decimal
        # Estratégia: Remove todos os pontos, depois troca vírgula por ponto
        valor_limpo = valor_str.replace('.', '')  # Remove separadores de milhar
        valor_limpo = valor_limpo.replace(',', '.')  # Converte vírgula decimal para ponto
        
        # Converte para float
        return float(valor_limpo)
    
    except (ValueError, TypeError, AttributeError):
        # Fallback seguro - nunca quebra o sistema
        return 0.0

# ==================================================
# FUNÇÕES AUXILIARES DE CONVERSÃO SEGURA
# ==================================================
def converter_coluna_para_numerico(df, coluna):
    """
    Converte uma coluna para numérico de forma segura usando pandas.
    
    Args:
        df: DataFrame
        coluna: Nome da coluna
    
    Returns:
        Series com valores numéricos (NaN para inválidos)
    """
    if coluna not in df.columns:
        return pd.Series([0.0] * len(df), index=df.index)
    
    # Usando pandas to_numeric com coerce para evitar erros
    return pd.to_numeric(df[coluna], errors='coerce').fillna(0.0)

def formatar_valor_brasileiro(valor):
    """
    Formata um valor float para o padrão brasileiro (R$ 1.234,56)
    
    Args:
        valor: float
    
    Returns:
        str: Valor formatado
    """
    if pd.isna(valor):
        return "R$ 0,00"
    
    # Formata com 2 casas decimais e separadores
    return f"R$ {valor:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

# ==================================================
# FUNÇÕES ORIGINAIS CORRIGIDAS
# ==================================================
def encontrar_aba_correta(excel_file):
    """Encontra a aba correta no arquivo Excel"""
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
    """Procura a linha do cabeçalho pela palavra 'Conta'"""
    if df.empty:
        return None
    
    primeira_coluna = df.iloc[:, 0].astype(str)
    
    for idx, valor in enumerate(primeira_coluna):
        if pd.notna(valor) and "conta" in str(valor).lower():
            return idx
    
    return None

def formatar_data_seguro(valor):
    """
    Converte valores para data de forma segura (dayfirst=True)
    
    FIX: Substituído o loop de formatos por dayfirst=True, que é mais robusto
    """
    if pd.isna(valor) or valor == '':
        return ''
    
    try:
        # Se for datetime, formata direto
        if isinstance(valor, (datetime, pd.Timestamp)):
            return valor.strftime('%d/%m/%Y')
        
        # Se for string ou número, usa dayfirst=True
        data_convertida = pd.to_datetime(valor, dayfirst=True, errors='coerce')
        
        if pd.notna(data_convertida):
            return data_convertida.strftime('%d/%m/%Y')
        else:
            return str(valor)
    
    except Exception:
        return str(valor)

def extrair_primeiros_digitos(valor, num_digitos=6):
    """Extrai os primeiros N dígitos de um valor"""
    try:
        valor_str = str(valor)
        numeros = ''.join(filter(str.isdigit, valor_str))
        return numeros[:num_digitos] if len(numeros) >= num_digitos else numeros
    except:
        return ''

def extrair_nf(texto):
    """
    Extrai número da NF do histórico usando regex otimizada.
    
    Busca padrões: NF.XXXXX ou TIT.XXXXX
    """
    if pd.isna(texto) or not isinstance(texto, str):
        return ""
    
    try:
        texto_limpo = texto.replace('\n', ' ').replace('\r', ' ').strip()
        padrao = r'(?:NF\.|TIT\.)\s*(\d+)'
        match = re.search(padrao, texto_limpo, re.IGNORECASE)
        return match.group(1) if match else ""
    except Exception:
        return ""

# ==================================================
# CÁLCULO DO MOVIMENTO - OPERAÇÃO VETORIZADA
# ==================================================
def calcular_movimento_vetorizado(df, col_credito, col_debito):
    """
    Calcula o movimento de forma VETORIZADA (sem apply).
    
    REGRA CONTÁBIL CORRETA: Movimento = Débito - Crédito
    - Positivo: Saldo devedor (must pay)
    - Negativo: Saldo credor (overpaid)
    - Zero: Conciliado
    
    Args:
        df: DataFrame
        col_credito: Nome da coluna de crédito
        col_debito: Nome da coluna de débito
    
    Returns:
        Series com os valores do movimento
    """
    # Converte as colunas para numérico de forma segura
    debito_num = converter_coluna_para_numerico(df, col_debito)
    credito_num = converter_coluna_para_numerico(df, col_credito)
    
    # Operação vetorizada (muito mais rápida que apply)
    movimento = debito_num - credito_num
    
    return movimento

# ==================================================
# FILTROS CORRIGIDOS COM CONVERSÃO SEGURA
# ==================================================
def aplicar_filtros(df, filtros, col_debito, col_credito):
    """
    Aplica filtros de forma segura, tratando valores vazios e colunas inexistentes
    
    Args:
        df: DataFrame original
        filtros: Dicionário com valores dos filtros
        col_debito: Nome da coluna de débito
        col_credito: Nome da coluna de crédito
    
    Returns:
        DataFrame filtrado
    """
    df_filtrado = df.copy()
    
    # Filtro Conta
    if filtros.get('conta') and filtros['conta'] != '':
        if 'Conta' in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado['Conta'].str.contains(filtros['conta'], case=False, na=False)]
    
    # Filtro Lote
    if filtros.get('lote') and filtros['lote'] != '':
        col_lote = next((col for col in df_filtrado.columns if 'lote' in col.lower()), None)
        if col_lote:
            df_filtrado = df_filtrado[df_filtrado[col_lote].astype(str).str.contains(filtros['lote'], case=False, na=False)]
    
    # Filtro Data (usando dayfirst=True)
    if filtros.get('data_inicio') and filtros.get('data_fim'):
        col_data = next((col for col in df_filtrado.columns if 'data' in col.lower()), None)
        if col_data:
            df_filtrado['data_temp'] = pd.to_datetime(df_filtrado[col_data], dayfirst=True, errors='coerce')
            data_inicio = pd.to_datetime(filtros['data_inicio'])
            data_fim = pd.to_datetime(filtros['data_fim'])
            df_filtrado = df_filtrado[(df_filtrado['data_temp'] >= data_inicio) & (df_filtrado['data_temp'] <= data_fim)]
            df_filtrado = df_filtrado.drop(columns=['data_temp'])
    
    # Filtro NF_EXTRAIDA
    if filtros.get('nf_extraida') and filtros['nf_extraida'] != '':
        if 'NF_EXTRAIDA' in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado['NF_EXTRAIDA'].astype(str).str.contains(filtros['nf_extraida'], case=False, na=False)]
    
    # Filtro Movimento (usando valores numéricos)
    if 'Movimento' in df_filtrado.columns and filtros.get('movimento_min') and filtros['movimento_min'] != '':
        movimento_num = converter_coluna_para_numerico(df_filtrado, 'Movimento')
        df_filtrado = df_filtrado[movimento_num >= converter_para_float(filtros['movimento_min'])]
    
    if 'Movimento' in df_filtrado.columns and filtros.get('movimento_max') and filtros['movimento_max'] != '':
        movimento_num = converter_coluna_para_numerico(df_filtrado, 'Movimento')
        df_filtrado = df_filtrado[movimento_num <= converter_para_float(filtros['movimento_max'])]
    
    # Filtro Débito
    if col_debito:
        debito_num = converter_coluna_para_numerico(df_filtrado, col_debito)
        
        if filtros.get('debito_min') and filtros['debito_min'] != '':
            df_filtrado = df_filtrado[debito_num >= converter_para_float(filtros['debito_min'])]
        
        if filtros.get('debito_max') and filtros['debito_max'] != '':
            df_filtrado = df_filtrado[debito_num <= converter_para_float(filtros['debito_max'])]
    
    # Filtro Crédito
    if col_credito:
        credito_num = converter_coluna_para_numerico(df_filtrado, col_credito)
        
        if filtros.get('credito_min') and filtros['credito_min'] != '':
            df_filtrado = df_filtrado[credito_num >= converter_para_float(filtros['credito_min'])]
        
        if filtros.get('credito_max') and filtros['credito_max'] != '':
            df_filtrado = df_filtrado[credito_num <= converter_para_float(filtros['credito_max'])]
    
    return df_filtrado

# ==================================================
# ANÁLISE DE PENDÊNCIAS - CORRIGIDA E ROBUSTA
# ==================================================
def analisar_pendencias(df, col_debito, col_credito):
    """
    Analisa pendências por Nota Fiscal.
    
    REGRA: SOMA(DÉBITO) - SOMA(CRÉDITO) ≠ 0
    
    Args:
        df: DataFrame
        col_debito: Nome da coluna débito
        col_credito: Nome da coluna crédito
    
    Returns:
        Tuple (df_pendencias, col_debito, col_credito) ou None
    """
    if not col_debito or not col_credito:
        st.warning("Colunas de Débito ou Crédito não encontradas")
        return None
    
    # Filtra apenas NFs válidas
    df_analise = df[df['NF_EXTRAIDA'] != ""].copy()
    
    if df_analise.empty:
        st.info("Nenhuma Nota Fiscal encontrada para análise")
        return None
    
    # CONVERSÃO SEGURA usando a função robusta
    df_analise['DEBITO_NUM'] = df_analise[col_debito].apply(converter_para_float)
    df_analise['CREDITO_NUM'] = df_analise[col_credito].apply(converter_para_float)
    
    # Agrupamento otimizado com agg
    df_group = df_analise.groupby('NF_EXTRAIDA').agg({
        'DEBITO_NUM': 'sum',
        'CREDITO_NUM': 'sum'
    }).reset_index()
    
    # Cálculo da diferença
    df_group['DIFERENCA'] = df_group['DEBITO_NUM'] - df_group['CREDITO_NUM']
    
    # Arredondamento para evitar erros de precisão (2 casas decimais)
    df_group['DIFERENCA'] = df_group['DIFERENCA'].round(2)
    
    # Filtra apenas pendências (diferença ≠ 0)
    # Usar tolerância para evitar erros de ponto flutuante
    df_pendencias = df_group[np.abs(df_group['DIFERENCA']) > 0.01].copy()
    
    # Ordena por maior diferença absoluta
    df_pendencias['ABS_DIF'] = df_pendencias['DIFERENCA'].abs()
    df_pendencias = df_pendencias.sort_values('ABS_DIF', ascending=False)
    df_pendencias = df_pendencias.drop(columns=['ABS_DIF'])
    df_pendencias = df_pendencias.reset_index(drop=True)
    
    return df_pendencias

# ==================================================
# EXIBIÇÃO DE ESTATÍSTICAS
# ==================================================
def exibir_estatisticas_rodape(df, col_debito, col_credito):
    """Exibe estatísticas no rodapé"""
    total_registros = len(df)
    
    soma_debito = df[col_debito].apply(converter_para_float).sum() if col_debito in df.columns else 0
    soma_credito = df[col_credito].apply(converter_para_float).sum() if col_credito in df.columns else 0
    
    soma_movimento = 0
    if 'Movimento' in df.columns:
        soma_movimento = df['Movimento'].apply(converter_para_float).sum()
    
    stats_html = f"""
    <div class="footer-stats">
        <span>📊 <strong>Estatísticas</strong></span>
        <span>📄 Total de Registros: <strong>{total_registros:,}</strong></span>
        <span>💸 Total Débito: <strong>{formatar_valor_brasileiro(soma_debito)}</strong></span>
        <span>💳 Total Crédito: <strong>{formatar_valor_brasileiro(soma_credito)}</strong></span>
        <span>💰 Total Movimento: <strong>{formatar_valor_brasileiro(soma_movimento)}</strong></span>
    </div>
    """
    st.markdown(stats_html, unsafe_allow_html=True)

# ==================================================
# PROCESSAMENTO PRINCIPAL - CORRIGIDO
# ==================================================
def carregar_e_tratar_dados(arquivo, nome_aba):
    """
    Carrega e processa o arquivo Excel.
    
    Fluxo:
    1. Lê a planilha sem cabeçalho
    2. Identifica linha do cabeçalho pela palavra "Conta"
    3. Aplica transformações
    4. Calcula movimento (vetorizado)
    5. Retorna DataFrame processado
    """
    try:
        df_raw = pd.read_excel(arquivo, sheet_name=nome_aba, header=None)
        
        if df_raw.empty:
            st.warning("A planilha está vazia")
            return None, None, None
        
        linha_cabecalho = encontrar_linha_cabecalho(df_raw)
        
        if linha_cabecalho is None:
            st.warning("Coluna 'Conta' não encontrada na planilha")
            return None, None, None
        
        # Define cabeçalho
        cabecalho = df_raw.iloc[linha_cabecalho].astype(str).tolist()
        cabecalho = [str(col).strip() if pd.notna(col) else f"Coluna_{i}" 
                    for i, col in enumerate(cabecalho)]
        
        # Remove duplicatas nos cabeçalhos
        for i, col in enumerate(cabecalho):
            if cabecalho.count(col) > 1:
                cabecalho[i] = f"{col}_{i}"
        
        # Cria DataFrame com dados
        df_dados = df_raw.iloc[linha_cabecalho + 1:].copy()
        df_dados.columns = cabecalho
        df_dados = df_dados.dropna(how='all')
        df_dados = df_dados.reset_index(drop=True)
        
        # Converte tudo para string e remove 'nan'
        for col in df_dados.columns:
            df_dados[col] = df_dados[col].astype(str).replace('nan', '')
        
        # Remove colunas específicas
        colunas_para_remover = ['C CUSTO', 'ITEM CONTA', 'COD CL VAL']
        for col in colunas_para_remover:
            if col in df_dados.columns:
                df_dados = df_dados.drop(columns=[col])
        
        # Extrai primeiros 6 dígitos do LOTE
        col_lote = next((col for col in df_dados.columns if 'LOTE/SUB/DOC/LINHA' in col or 'LOTE' in col), None)
        if col_lote:
            df_dados[col_lote] = df_dados[col_lote].apply(lambda x: extrair_primeiros_digitos(x, 6))
        
        # Filtra FILIAL DE ORIGEM
        col_filial = next((col for col in df_dados.columns if 'FILIAL DE ORIGEM' in col or 'FILIAL' in col), None)
        if col_filial:
            df_dados = df_dados[df_dados[col_filial].str.strip() != '']
            df_dados = df_dados.reset_index(drop=True)
        
        # Extrai NF do HISTORICO
        col_historico = next((col for col in df_dados.columns if 'historico' in col.lower()), None)
        if col_historico:
            df_dados['NF_EXTRAIDA'] = df_dados[col_historico].apply(extrair_nf)
        else:
            df_dados['NF_EXTRAIDA'] = ""
        
        # Identifica colunas de Crédito e Débito
        col_credito = next((col for col in df_dados.columns if 'credito' in col.lower()), None)
        col_debito = next((col for col in df_dados.columns if 'debito' in col.lower()), None)
        
        # Formata DATA (usando dayfirst=True)
        col_data = next((col for col in df_dados.columns if 'data' in col.lower()), None)
        if col_data:
            df_dados[col_data] = df_dados[col_data].apply(formatar_data_seguro)
        
        # CALCULA MOVIMENTO (VETORIZADO - SEM APPLY!)
        if col_credito and col_debito:
            movimento_num = calcular_movimento_vetorizado(df_dados, col_credito, col_debito)
            # Formata para exibição (com 2 casas decimais)
            df_dados['Movimento'] = movimento_num.apply(lambda x: f"{x:.2f}".replace('.', ','))
            # Cria versão numérica para cálculos futuros
            df_dados['Movimento_Num'] = movimento_num
        
        return df_dados, col_debito, col_credito
    
    except Exception as e:
        st.error(f"Erro ao processar os dados: {str(e)}")
        return None, None, None

# ==================================================
# MAIN - APLICAÇÃO STREAMLIT
# ==================================================
def main():
    """Função principal do aplicativo"""
    
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
    
    if uploaded_file is not None:
        with st.spinner("Processando arquivo..."):
            df_original, col_debito, col_credito = carregar_e_tratar_dados(
                uploaded_file, 
                encontrar_aba_correta(uploaded_file)
            )
        
        if df_original is not None and not df_original.empty:
            
            # Cria TABS
            tab1, tab2 = st.tabs(["📋 Lançamentos", "⚠️ Pendências por NF"])
            
            # ========== TAB 1: LANÇAMENTOS ==========
            with tab1:
                # Filtros expansíveis
                with st.expander("🔍 Filtrar Dados", expanded=False):
                    st.markdown("### Aplicar Filtros")
                    
                    col1, col2, col3 = st.columns(3)
                    col4, col5, col6 = st.columns(3)
                    
                    filtros = {}
                    
                    with col1:
                        filtros['conta'] = st.text_input("📋 Conta (contém)", key="filtro_conta", placeholder="Digite parte da conta...")
                        filtros['lote'] = st.text_input("🔢 Lote", key="filtro_lote", placeholder="Número do lote...")
                    
                    with col2:
                        col_data = next((col for col in df_original.columns if 'data' in col.lower()), None)
                        if col_data:
                            datas_validas = pd.to_datetime(df_original[col_data], dayfirst=True, errors='coerce').dropna()
                            if not datas_validas.empty:
                                filtros['data_inicio'] = st.date_input("📅 Data inicial", value=datas_validas.min().date())
                                filtros['data_fim'] = st.date_input("📅 Data final", value=datas_validas.max().date())
                            else:
                                filtros['data_inicio'] = st.date_input("📅 Data inicial")
                                filtros['data_fim'] = st.date_input("📅 Data final")
                        else:
                            filtros['data_inicio'] = st.date_input("📅 Data inicial")
                            filtros['data_fim'] = st.date_input("📅 Data final")
                    
                    with col3:
                        filtros['nf_extraida'] = st.text_input("🏷️ NF Extraída", key="filtro_nf", placeholder="Número da NF...")
                    
                    with col4:
                        st.markdown("**💰 Movimento**")
                        c1, c2 = st.columns(2)
                        with c1:
                            filtros['movimento_min'] = st.text_input("Mínimo", placeholder="0,00")
                        with c2:
                            filtros['movimento_max'] = st.text_input("Máximo", placeholder="999.999,99")
                    
                    with col5:
                        st.markdown("**💸 Débito**")
                        c1, c2 = st.columns(2)
                        with c1:
                            filtros['debito_min'] = st.text_input("Mínimo", key="deb_min", placeholder="0,00")
                        with c2:
                            filtros['debito_max'] = st.text_input("Máximo", key="deb_max", placeholder="999.999,99")
                    
                    with col6:
                        st.markdown("**💳 Crédito**")
                        c1, c2 = st.columns(2)
                        with c1:
                            filtros['credito_min'] = st.text_input("Mínimo", key="cred_min", placeholder="0,00")
                        with c2:
                            filtros['credito_max'] = st.text_input("Máximo", key="cred_max", placeholder="999.999,99")
                    
                    _, col_btn, _ = st.columns([1, 2, 1])
                    with col_btn:
                        if st.button("🧹 Limpar todos os filtros", use_container_width=True):
                            st.rerun()
                
                # Aplica filtros
                df_filtrado = aplicar_filtros(df_original, filtros, col_debito, col_credito)
                
                # Exibe DataFrame
                st.subheader("📋 Dados Detalhados")
                altura_grid = min(800, max(400, 200 + (len(df_filtrado) * 35)))
                
                st.dataframe(
                    df_filtrado, 
                    use_container_width=True, 
                    height=altura_grid,
                    hide_index=True
                )
                
                # Estatísticas no rodapé
                exibir_estatisticas_rodape(df_filtrado, col_debito, col_credito)
            
            # ========== TAB 2: PENDÊNCIAS ==========
            with tab2:
                st.subheader("⚠️ Notas Fiscais com Pendências")
                st.markdown("Identifica NFs onde **Débito - Crédito ≠ 0** (regra contábil)")
                
                with st.spinner("Analisando pendências..."):
                    df_pendencias = analisar_pendencias(df_original, col_debito, col_credito)
                    
                    if df_pendencias is not None and not df_pendencias.empty:
                        # Métricas
                        total_pendencias = len(df_pendencias)
                        total_diferenca = df_pendencias['DIFERENCA'].round(2).sum()
                        
                        col_a, col_b, col_c, col_d = st.columns(4)
                        with col_a:
                            st.metric("⚠️ NFs com Pendência", total_pendencias)
                        with col_b:
                            st.metric("💰 Débito Pendente", formatar_valor_brasileiro(df_pendencias['DEBITO_NUM'].sum()))
                        with col_c:
                            st.metric("💳 Crédito Pendente", formatar_valor_brasileiro(df_pendencias['CREDITO_NUM'].sum()))
                        with col_d:
                            delta_color = "inverse" if total_diferenca < 0 else "normal"
                            st.metric("📊 Diferença Total", formatar_valor_brasileiro(total_diferenca), delta_color=delta_color)
                        
                        st.markdown("---")
                        
                        # Tabela formatada
                        df_exibicao = df_pendencias.copy()
                        df_exibicao['DEBITO_NUM'] = df_exibicao['DEBITO_NUM'].apply(formatar_valor_brasileiro)
                        df_exibicao['CREDITO_NUM'] = df_exibicao['CREDITO_NUM'].apply(formatar_valor_brasileiro)
                        df_exibicao['DIFERENCA'] = df_exibicao['DIFERENCA'].apply(formatar_valor_brasileiro)
                        df_exibicao.columns = ['NF', 'Débito Total', 'Crédito Total', 'Diferença']
                        
                        st.dataframe(df_exibicao, use_container_width=True, height=400, hide_index=True)
                        
                        # Detalhamento por NF
                        st.markdown("---")
                        st.subheader("🔍 Detalhamento por NF")
                        
                        nf_selecionada = st.selectbox(
                            "Selecione uma NF para ver os lançamentos:",
                            options=df_pendencias['NF_EXTRAIDA'].tolist()
                        )
                        
                        if nf_selecionada:
                            df_detalhes = df_original[df_original['NF_EXTRAIDA'] == nf_selecionada].copy()
                            st.markdown(f"**Detalhes da NF: {nf_selecionada}**")
                            st.markdown(f"📄 Total de lançamentos: {len(df_detalhes)}")
                            
                            # Métricas da NF
                            soma_debito = df_detalhes[col_debito].apply(converter_para_float).sum()
                            soma_credito = df_detalhes[col_credito].apply(converter_para_float).sum()
                            
                            col_e, col_f, col_g = st.columns(3)
                            with col_e:
                                st.metric("💸 Débito Total", formatar_valor_brasileiro(soma_debito))
                            with col_f:
                                st.metric("💳 Crédito Total", formatar_valor_brasileiro(soma_credito))
                            with col_g:
                                st.metric("⚠️ Diferença", formatar_valor_brasileiro(soma_debito - soma_credito))
                            
                            st.dataframe(df_detalhes, use_container_width=True, height=300, hide_index=True)
                    
                    elif df_pendencias is not None and df_pendencias.empty:
                        total_nfs = df_original[df_original['NF_EXTRAIDA'] != ""]['NF_EXTRAIDA'].nunique()
                        st.success(f"🎉 Todas as {total_nfs} NFs estão conciliadas!")
    
    else:
        st.info("👈 Faça upload de um arquivo Excel na barra lateral para começar")

if __name__ == "__main__":
    main()