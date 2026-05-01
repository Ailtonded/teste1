# app.py - Versão com limpeza inteligente de cabeçalhos
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import io
import re

# Configuração da página
st.set_page_config(
    page_title="Sistema de Conciliação Contábil",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# FUNÇÕES DE DETECÇÃO E LIMPEZA
# ============================================================================

def encontrar_linha_cabecalho_inteligente(df, palavras_chave_obrigatorias=['DATA']):
    """
    Encontra a linha que contém todas as palavras-chave obrigatórias.
    Remove linhas de título e formatação automaticamente.
    """
    for idx, row in df.iterrows():
        # Converte a linha para string e upper
        linha_str = ' '.join([str(valor).upper() if pd.notna(valor) else '' for valor in row.values])
        
        # Verifica se todas as palavras obrigatórias estão presentes
        tem_todas = all(palavra in linha_str for palavra in palavras_chave_obrigatorias)
        
        # Verifica se não é uma linha de título (como "TOTAIS", "LANÇAMENTOS CONTÁBEIS")
        eh_titulo = len([v for v in row.values if pd.notna(v) and isinstance(v, str) and v.upper().strip() in ['TOTAIS', 'LANÇAMENTOS CONTÁBEIS', 'EXTRATO', 'RAZÃO', 'PARAMETROS']]) > 0
        
        if tem_todas and not eh_titulo:
            # Encontrou o cabeçalho
            cabecalho = []
            for col_value in row.values:
                if pd.notna(col_value):
                    # Limpa o nome da coluna
                    col_name = str(col_value).strip().upper()
                    col_name = re.sub(r'[^\w\s]', '', col_name)  # Remove pontuação
                    col_name = col_name.replace(' ', '_')
                    cabecalho.append(col_name)
                else:
                    cabecalho.append(f"COL_{len(cabecalho)}")
            
            return idx, cabecalho
    
    return None, None

def limpar_e_normalizar_dataframe(df, tipo_arquivo, palavras_chave_obrigatorias=['DATA']):
    """
    Limpa e normaliza o DataFrame completo.
    """
    if df is None or df.empty:
        return None
    
    # Passo 1: Encontrar linha de cabeçalho
    linha_cabecalho, colunas_nomeadas = encontrar_linha_cabecalho_inteligente(df, palavras_chave_obrigatorias)
    
    if linha_cabecalho is None:
        st.error(f"❌ Não foi possível encontrar o cabeçalho no arquivo de {tipo_arquivo}. Verifique se há uma coluna 'DATA'.")
        return None
    
    # Passo 2: Reconstruir DataFrame a partir da linha após o cabeçalho
    # Pular linhas que são apenas formatação (como linhas com apenas um texto solto)
    df_limpo = []
    start_row = linha_cabecalho + 1
    
    for idx in range(start_row, len(df)):
        row = df.iloc[idx]
        # Pula linhas vazias ou com apenas um valor não numérico (linhas de formatação)
        valores_validos = [v for v in row.values if pd.notna(v) and str(v).strip()]
        
        # Linha de formatação: tem poucos valores e o primeiro é texto não numérico
        if len(valores_validos) == 1 and isinstance(row.iloc[0], str) and not re.search(r'\d', row.iloc[0]):
            continue
        
        # Linha válida - mantém
        df_limpo.append(row.values)
    
    # Criar novo DataFrame
    df_normalizado = pd.DataFrame(df_limpo, columns=colunas_nomeadas[:len(df_limpo[0])] if df_limpo else colunas_nomeadas)
    
    # Passo 3: Renomear colunas padrão
    df_normalizado.columns = [str(col).strip().upper().replace(' ', '_') for col in df_normalizado.columns]
    
    # Passo 4: Detectar colunas por palavras-chave
    mapeamento = {}
    
    for col in df_normalizado.columns:
        col_upper = col.upper()
        if 'DATA' in col_upper or 'DT_' in col_upper:
            mapeamento['DATA'] = col
        elif 'ENTRADA' in col_upper or 'DEBITO' in col_upper or 'DÉBITO' in col_upper:
            if 'ENTRADA' not in mapeamento:
                mapeamento['ENTRADA'] = col
        elif 'SAIDA' in col_upper or 'CREDITO' in col_upper or 'CRÉDITO' in col_upper:
            if 'SAIDA' not in mapeamento:
                mapeamento['SAIDA'] = col
    
    # Para razão que tem DÉBITO e CRÉDITO separados
    if 'DEBITO' in df_normalizado.columns and 'CREDITO' in df_normalizado.columns:
        mapeamento['ENTRADA'] = 'DEBITO'
        mapeamento['SAIDA'] = 'CREDITO'
    
    # Validar se encontrou DATA
    if 'DATA' not in mapeamento:
        st.error(f"❌ Coluna DATA não encontrada em {tipo_arquivo}. Colunas disponíveis: {list(df_normalizado.columns)}")
        return None
    
    # Passo 5: Renomear para padrão
    if 'ENTRADA' in mapeamento:
        df_normalizado = df_normalizado.rename(columns={mapeamento['ENTRADA']: 'ENTRADAS'})
    
    if 'SAIDA' in mapeamento:
        df_normalizado = df_normalizado.rename(columns={mapeamento['SAIDA']: 'SAIDAS'})
    
    # Garantir colunas existam
    if 'ENTRADAS' not in df_normalizado.columns:
        df_normalizado['ENTRADAS'] = 0
    if 'SAIDAS' not in df_normalizado.columns:
        df_normalizado['SAIDAS'] = 0
    
    # Passo 6: Tratar tipos de dados
    # Converter DATA
    df_normalizado['DATA'] = pd.to_datetime(df_normalizado[mapeamento['DATA']], errors='coerce', dayfirst=True)
    
    # Converter ENTRADAS e SAIDAS para numérico
    def converter_valor(valor):
        if pd.isna(valor):
            return 0
        if isinstance(valor, str):
            # Remove pontos de milhar e substitui vírgula por ponto
            valor = valor.replace('.', '').replace(',', '.')
        try:
            return float(valor)
        except:
            return 0
    
    df_normalizado['ENTRADAS'] = df_normalizado['ENTRADAS'].apply(converter_valor)
    df_normalizado['SAIDAS'] = df_normalizado['SAIDAS'].apply(converter_valor)
    
    # Remover linhas sem DATA válida
    df_normalizado = df_normalizado.dropna(subset=['DATA']).reset_index(drop=True)
    
    # Passo 7: Criar MOV (movimento líquido)
    df_normalizado['MOV'] = df_normalizado['ENTRADAS'] - df_normalizado['SAIDAS']
    
    # Passo 8: Criar chave de conciliação
    df_normalizado['CHAVE'] = df_normalizado['DATA'].dt.strftime('%Y-%m-%d') + '_' + df_normalizado['MOV'].round(2).astype(str)
    
    # Passo 9: Adicionar origem
    df_normalizado['TP'] = tipo_arquivo
    
    return df_normalizado

# ============================================================================
# FUNÇÕES DE CARREGAMENTO ESPECÍFICAS
# ============================================================================

def carregar_extrato(uploaded_file):
    """
    Carrega o extrato da aba '2-Totais'
    """
    if uploaded_file is None:
        return None
    
    try:
        # Carregar aba específica
        df = pd.read_excel(uploaded_file, sheet_name='2-Totais', header=None, dtype=str)
        return limpar_e_normalizar_dataframe(df, "EXTRATO", ['DATA'])
    except Exception as e:
        st.error(f"❌ Erro ao carregar Extrato: {str(e)}")
        
        # Tentar listar abas disponíveis
        xl = pd.ExcelFile(uploaded_file)
        st.info(f"Abas disponíveis no arquivo: {xl.sheet_names}")
        return None

def carregar_razao(uploaded_file):
    """
    Carrega o razão da aba '3-Lançamentos Contábeis'
    """
    if uploaded_file is None:
        return None
    
    try:
        # Carregar aba específica
        df = pd.read_excel(uploaded_file, sheet_name='3-Lançamentos Contábeis', header=None, dtype=str)
        return limpar_e_normalizar_dataframe(df, "RAZAO", ['DATA'])
    except Exception as e:
        st.error(f"❌ Erro ao carregar Razão: {str(e)}")
        
        # Tentar listar abas disponíveis
        xl = pd.ExcelFile(uploaded_file)
        st.info(f"Abas disponíveis no arquivo: {xl.sheet_names}")
        return None

# ============================================================================
# FUNÇÕES DE CONCILIAÇÃO
# ============================================================================

def conciliar_exato(df_extrato, df_razao):
    """
    Conciliação exata baseada na chave (DATA + MOV)
    """
    if df_extrato is None or df_razao is None:
        return None, None, None, None
    
    if df_extrato.empty or df_razao.empty:
        return None, df_extrato, df_razao, None
    
    # Preparar para merge
    extrato_merge = df_extrato.copy()
    razao_merge = df_razao.copy()
    
    # Adicionar contador para evitar duplicatas
    extrato_merge['_contador'] = extrato_merge.groupby('CHAVE').cumcount()
    razao_merge['_contador'] = razao_merge.groupby('CHAVE').cumcount()
    
    extrato_merge['CHAVE_UNICA'] = extrato_merge['CHAVE'] + '_' + extrato_merge['_contador'].astype(str)
    razao_merge['CHAVE_UNICA'] = razao_merge['CHAVE'] + '_' + razao_merge['_contador'].astype(str)
    
    # Merge
    conciliados = pd.merge(
        extrato_merge, razao_merge,
        on='CHAVE_UNICA',
        suffixes=('_EXTRATO', '_RAZAO'),
        how='inner'
    )
    
    # Não conciliados
    extrato_nao = extrato_merge[~extrato_merge['CHAVE_UNICA'].isin(conciliados['CHAVE_UNICA'])].copy()
    razao_nao = razao_merge[~razao_merge['CHAVE_UNICA'].isin(conciliados['CHAVE_UNICA'])].copy()
    
    # Remover colunas auxiliares
    for df in [conciliados, extrato_nao, razao_nao]:
        if df is not None and not df.empty:
            df.drop(columns=['_contador', 'CHAVE_UNICA'], inplace=True, errors='ignore')
    
    return conciliados, extrato_nao, razao_nao

def sugerir_conciliacoes(df_extrato_nao, df_razao_nao):
    """
    Sugere conciliações baseadas em score (valor + data)
    """
    if df_extrato_nao is None or df_razao_nao is None:
        return pd.DataFrame()
    
    if df_extrato_nao.empty or df_razao_nao.empty:
        return pd.DataFrame()
    
    sugestoes = []
    
    # Para cada item não conciliado do extrato
    for _, extrato_row in df_extrato_nao.iterrows():
        data_extrato = extrato_row['DATA']
        mov_extrato = extrato_row['MOV']
        
        # Buscar candidatos no razão
        for _, razao_row in df_razao_nao.iterrows():
            data_razao = razao_row['DATA']
            mov_razao = razao_row['MOV']
            
            # Calcular diferenças
            diff_valor = abs(mov_razao - mov_extrato)
            diff_dias = abs((data_razao - data_extrato).days)
            
            # Calcular score
            score = 0
            
            # Valor
            if diff_valor == 0:
                score += 50
            elif diff_valor <= 0.05:
                score += 30
            
            # Data
            if diff_dias == 0:
                score += 50
            elif diff_dias <= 2:
                score += 30
            
            if score >= 60:
                sugestoes.append({
                    'DATA_EXTRATO': data_extrato,
                    'MOV_EXTRATO': mov_extrato,
                    'DATA_RAZAO': data_razao,
                    'MOV_RAZAO': mov_razao,
                    'SCORE': score,
                    'DIF_VALOR': diff_valor,
                    'DIF_DIAS': diff_dias
                })
    
    if sugestoes:
        df_sugestoes = pd.DataFrame(sugestoes)
        df_sugestoes = df_sugestoes.sort_values('SCORE', ascending=False)
        # Remover duplicatas
        df_sugestoes = df_sugestoes.drop_duplicates(subset=['DATA_EXTRATO', 'MOV_EXTRATO'], keep='first')
        return df_sugestoes
    
    return pd.DataFrame()

# ============================================================================
# INTERFACE STREAMLIT
# ============================================================================

def main():
    st.title("📊 Sistema de Conciliação Contábil")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("📁 Upload")
        
        extrato_file = st.file_uploader(
            "📄 Extrato Bancário (aba '2-Totais')",
            type=['xlsx', 'xls']
        )
        
        razao_file = st.file_uploader(
            "📒 Razão Contábil (aba '3-Lançamentos Contábeis')",
            type=['xlsx', 'xls']
        )
        
        st.markdown("---")
        st.header("📅 Período")
        
        data_inicio = st.date_input("Data Inicial", datetime(2026, 4, 1))
        data_fim = st.date_input("Data Final", datetime(2026, 5, 1))
        
        st.markdown("---")
        processar = st.button("🚀 Conciliar", type="primary", use_container_width=True)
    
    # Processamento
    if processar and extrato_file and razao_file:
        with st.spinner("🔄 Processando..."):
            # Carregar
            df_extrato = carregar_extrato(extrato_file)
            df_razao = carregar_razao(razao_file)
            
            if df_extrato is not None and df_razao is not None:
                # Filtrar por período
                df_extrato = df_extrato[(df_extrato['DATA'] >= pd.Timestamp(data_inicio)) & 
                                       (df_extrato['DATA'] <= pd.Timestamp(data_fim))]
                df_razao = df_razao[(df_razao['DATA'] >= pd.Timestamp(data_inicio)) & 
                                   (df_razao['DATA'] <= pd.Timestamp(data_fim))]
                
                # Conciliação
                conciliados, extrato_nao, razao_nao = conciliar_exato(df_extrato, df_razao)
                sugestoes = sugerir_conciliacoes(extrato_nao, razao_nao)
                
                # Salvar na sessão
                st.session_state['conciliados'] = conciliados
                st.session_state['sugestoes'] = sugestoes
                st.session_state['extrato_nao'] = extrato_nao
                st.session_state['razao_nao'] = razao_nao
                st.session_state['df_extrato'] = df_extrato
                st.session_state['df_razao'] = df_razao
                st.session_state['processado'] = True
                
                st.success("✅ Conciliação concluída!")
                
                # Mostrar resumo
                st.info(f"📊 Extrato: {len(df_extrato)} linhas | Razão: {len(df_razao)} linhas | Conciliados: {len(conciliados) if conciliados is not None else 0}")
    
    # Exibir resultados
    if st.session_state.get('processado', False):
        conciliados = st.session_state.get('conciliados')
        sugestoes = st.session_state.get('sugestoes')
        extrato_nao = st.session_state.get('extrato_nao')
        razao_nao = st.session_state.get('razao_nao')
        df_extrato = st.session_state.get('df_extrato')
        df_razao = st.session_state.get('df_razao')
        
        # Abas
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "✅ Conciliados", "🧠 Sugestões", "⚠️ Extrato Não Conc.", 
            "⚠️ Razão Não Conc.", "📊 Resumo"
        ])
        
        with tab1:
            if conciliados is not None and not conciliados.empty:
                st.dataframe(conciliados[['DATA_EXTRATO', 'MOV_EXTRATO', 'DATA_RAZAO', 'MOV_RAZAO']])
                st.metric("Total", len(conciliados))
            else:
                st.info("Nenhum lançamento conciliado")
        
        with tab2:
            if sugestoes is not None and not sugestoes.empty:
                st.dataframe(sugestoes)
            else:
                st.info("Nenhuma sugestão encontrada")
        
        with tab3:
            if extrato_nao is not None and not extrato_nao.empty:
                st.dataframe(extrato_nao[['DATA', 'MOV']])
                st.metric("Total", len(extrato_nao))
            else:
                st.success("Todos conciliados!")
        
        with tab4:
            if razao_nao is not None and not razao_nao.empty:
                st.dataframe(razao_nao[['DATA', 'MOV']])
                st.metric("Total", len(razao_nao))
            else:
                st.success("Todos conciliados!")
        
        with tab5:
            col1, col2, col3 = st.columns(3)
            with col1:
                total_extrato = df_extrato['MOV'].sum()
                st.metric("Total Extrato", f"R$ {total_extrato:,.2f}")
            with col2:
                total_razao = df_razao['MOV'].sum()
                st.metric("Total Razão", f"R$ {total_razao:,.2f}")
            with col3:
                diferenca = total_extrato - total_razao
                st.metric("Diferença", f"R$ {diferenca:,.2f}")

if __name__ == "__main__":
    main()