# app.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from difflib import SequenceMatcher
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
# FUNÇÕES DE DETECÇÃO E NORMALIZAÇÃO
# ============================================================================

def encontrar_linha_cabecalho(df, palavras_chave):
    """
    Detecta a linha que contém o cabeçalho baseado em palavras-chave.
    Retorna o índice da linha e os nomes das colunas encontradas.
    """
    for idx, row in df.iterrows():
        # Converte toda a linha para string para verificação
        linha_str = ' '.join([str(valor).upper() for valor in row.values if pd.notna(valor)])
        
        # Verifica se alguma palavra-chave está presente
        for palavra in palavras_chave:
            if palavra in linha_str:
                # Encontrou o cabeçalho
                cabecalho = [str(valor).strip().upper() if pd.notna(valor) else f"COL_{i}" 
                            for i, valor in enumerate(row.values)]
                return idx, cabecalho
    
    return None, None

def detectar_colunas(df):
    """
    Detecta automaticamente as colunas de DATA, ENTRADAS e SAIDAS
    baseado em palavras-chave.
    """
    colunas = {col: col for col in df.columns}
    
    # Palavras-chave para cada tipo de coluna
    padroes = {
        'DATA': ['DATA', 'DT', 'DATE', 'DIA', 'LANÇAMENTO', 'MOVIMENTO'],
        'ENTRADA': ['ENTRADA', 'DEBITO', 'DEB', 'RECEITA', 'CREDITO', 'DEPOSITO'],
        'SAIDA': ['SAIDA', 'CREDITO', 'CRED', 'DESPESA', 'DEBITO', 'RETIRADA', 'PAGAMENTO']
    }
    
    colunas_detectadas = {'DATA': None, 'ENTRADA': None, 'SAIDA': None}
    
    # Detectar cada tipo de coluna
    for tipo, padroes_tipo in padroes.items():
        for col in df.columns:
            col_upper = col.upper()
            for padrao in padroes_tipo:
                if padrao in col_upper:
                    colunas_detectadas[tipo] = col
                    break
            if colunas_detectadas[tipo]:
                break
    
    # Validação: pelo menos a coluna DATA deve ser encontrada
    if colunas_detectadas['DATA'] is None:
        raise ValueError("Não foi possível detectar a coluna de DATA. Verifique se o arquivo contém colunas como 'DATA', 'DT' ou 'DATE'.")
    
    return colunas_detectadas

def normalizar_dataframe(df, tipo_arquivo):
    """
    Normaliza o DataFrame completo: detecta cabeçalho, identifica colunas,
    trata dados e cria coluna MOV.
    """
    if df is None or df.empty:
        return None
    
    # Passo 1: Detectar linha de cabeçalho
    palavras_chave = ['DATA', 'DT', 'DATE', 'ENTRADA', 'SAIDA', 'DEBITO', 'CREDITO']
    linha_cabecalho, colunas_cabecalho = encontrar_linha_cabecalho(df, palavras_chave)
    
    if linha_cabecalho is None:
        st.error(f"❌ Não foi possível encontrar o cabeçalho no arquivo de {tipo_arquivo}")
        return None
    
    # Passo 2: Reconstruir DataFrame com cabeçalho correto
    df = df.iloc[linha_cabecalho + 1:].reset_index(drop=True)
    df.columns = colunas_cabecalho
    
    # Passo 3: Normalizar nomes das colunas
    df.columns = [str(col).strip().upper().replace(' ', '_') for col in df.columns]
    
    # Passo 4: Detectar colunas específicas
    try:
        colunas = detectar_colunas(df)
    except ValueError as e:
        st.error(f"❌ {str(e)}")
        return None
    
    # Passo 5: Renomear colunas para padrão
    df = df.rename(columns={
        colunas['DATA']: 'DATA',
        colunas['ENTRADA']: 'ENTRADAS' if colunas['ENTRADA'] else 'ENTRADAS',
        colunas['SAIDA']: 'SAIDAS' if colunas['SAIDA'] else 'SAIDAS'
    })
    
    # Passo 6: Garantir que as colunas existam
    if 'ENTRADAS' not in df.columns:
        df['ENTRADAS'] = 0
    if 'SAIDAS' not in df.columns:
        df['SAIDAS'] = 0
    
    # Passo 7: Tratar dados
    # Converter DATA
    df['DATA'] = pd.to_datetime(df['DATA'], errors='coerce', dayfirst=True)
    
    # Converter ENTRADAS e SAIDAS para numérico
    df['ENTRADAS'] = pd.to_numeric(df['ENTRADAS'], errors='coerce').fillna(0)
    df['SAIDAS'] = pd.to_numeric(df['SAIDAS'], errors='coerce').fillna(0)
    
    # Remover linhas sem DATA válida
    df = df.dropna(subset=['DATA']).reset_index(drop=True)
    
    # Passo 8: Criar coluna MOV (movimento líquido)
    df['MOV'] = df['ENTRADAS'] - df['SAIDAS']
    
    # Passo 9: Adicionar identificador de origem
    df['TP'] = tipo_arquivo.upper()
    
    # Passo 10: Criar chave de conciliação
    df['CHAVE'] = df['DATA'].dt.strftime('%Y-%m-%d') + '_' + df['MOV'].round(2).astype(str)
    
    return df

def carregar_arquivo(uploaded_file, tipo_arquivo):
    """
    Carrega arquivo Excel de forma resiliente.
    """
    if uploaded_file is None:
        return None
    
    try:
        # Tentar carregar com header=None para detectar cabeçalho manualmente
        df = pd.read_excel(uploaded_file, header=None, dtype=str)
        return normalizar_dataframe(df, tipo_arquivo)
    except Exception as e:
        st.error(f"❌ Erro ao carregar {tipo_arquivo}: {str(e)}")
        return None

# ============================================================================
# FUNÇÕES DE CONCILIAÇÃO
# ============================================================================

def conciliar_exato(df_extrato, df_razao):
    """
    Conciliação exata baseada na chave (DATA + MOV).
    Retorna DataFrames conciliados e não conciliados.
    """
    if df_extrato is None or df_razao is None:
        return None, None, None, None
    
    # Criar chaves únicas para conciliação 1-para-1
    extrato_com_chave = df_extrato.copy()
    razao_com_chave = df_razao.copy()
    
    # Contador para evitar duplicatas
    extrato_com_chave['_contador'] = extrato_com_chave.groupby('CHAVE').cumcount()
    razao_com_chave['_contador'] = razao_com_chave.groupby('CHAVE').cumcount()
    
    extrato_com_chave['CHAVE_UNICA'] = extrato_com_chave['CHAVE'] + '_' + extrato_com_chave['_contador'].astype(str)
    razao_com_chave['CHAVE_UNICA'] = razao_com_chave['CHAVE'] + '_' + razao_com_chave['_contador'].astype(str)
    
    # Merge para conciliação
    conciliados = pd.merge(
        extrato_com_chave, 
        razao_com_chave,
        on='CHAVE_UNICA',
        suffixes=('_extrato', '_razao'),
        how='inner'
    )
    
    # Extrair não conciliados
    extrato_nao_conciliado = extrato_com_chave[~extrato_com_chave['CHAVE_UNICA'].isin(conciliados['CHAVE_UNICA'])].copy()
    razao_nao_conciliado = razao_com_chave[~razao_com_chave['CHAVE_UNICA'].isin(conciliados['CHAVE_UNICA'])].copy()
    
    # Remover colunas auxiliares
    for df in [conciliados, extrato_nao_conciliado, razao_nao_conciliado]:
        if df is not None and not df.empty:
            df.drop(columns=['_contador', 'CHAVE_UNICA'], inplace=True, errors='ignore')
    
    return conciliados, extrato_nao_conciliado, razao_nao_conciliado

def sugerir_conciliacoes(df_extrato_nao, df_razao_nao):
    """
    Algoritmo de scoring para sugerir conciliações possíveis.
    Evita O(n²) usando merge baseado em data e valor aproximado.
    """
    if df_extrato_nao is None or df_razao_nao is None:
        return pd.DataFrame()
    
    if df_extrato_nao.empty or df_razao_nao.empty:
        return pd.DataFrame()
    
    sugestoes = []
    
    # Para cada lançamento não conciliado do extrato, buscar possíveis matches no razão
    for idx_extrato, row_extrato in df_extrato_nao.iterrows():
        data_extrato = row_extrato['DATA']
        mov_extrato = row_extrato['MOV']
        
        # Filtrar razão por data próxima (±2 dias) e valor próximo (±0.05)
        mask_data = (df_razao_nao['DATA'] >= data_extrato - timedelta(days=2)) & \
                    (df_razao_nao['DATA'] <= data_extrato + timedelta(days=2))
        mask_valor = (df_razao_nao['MOV'] >= mov_extrato - 0.05) & \
                     (df_razao_nao['MOV'] <= mov_extrato + 0.05)
        
        candidates = df_razao_nao[mask_data & mask_valor]
        
        for idx_razao, row_razao in candidates.iterrows():
            # Calcular score
            score = 0
            
            # Score por valor
            if row_razao['MOV'] == mov_extrato:
                score += 50
            elif abs(row_razao['MOV'] - mov_extrato) <= 0.05:
                score += 30
            
            # Score por data
            if row_razao['DATA'] == data_extrato:
                score += 50
            elif abs((row_razao['DATA'] - data_extrato).days) <= 2:
                score += 30
            
            if score >= 60:
                sugestoes.append({
                    'DATA_EXTRATO': data_extrato,
                    'MOV_EXTRATO': mov_extrato,
                    'DESC_EXTRATO': row_extrato.get('DESCRICAO', 'N/A') if 'DESCRICAO' in df_extrato_nao.columns else 'N/A',
                    'DATA_RAZAO': row_razao['DATA'],
                    'MOV_RAZAO': row_razao['MOV'],
                    'DESC_RAZAO': row_razao.get('DESCRICAO', 'N/A') if 'DESCRICAO' in df_razao_nao.columns else 'N/A',
                    'SCORE': score,
                    'DIF_VALOR': abs(row_razao['MOV'] - mov_extrato),
                    'DIF_DIAS': abs((row_razao['DATA'] - data_extrato).days)
                })
    
    if sugestoes:
        df_sugestoes = pd.DataFrame(sugestoes)
        df_sugestoes = df_sugestoes.sort_values('SCORE', ascending=False).drop_duplicates(
            subset=['DATA_EXTRATO', 'MOV_EXTRATO'], keep='first'
        )
        return df_sugestoes
    
    return pd.DataFrame()

# ============================================================================
# FUNÇÕES DE INTERFACE E EXPORTAÇÃO
# ============================================================================

def aplicar_filtro_periodo(df, data_inicio, data_fim):
    """
    Aplica filtro de período no DataFrame.
    """
    if df is None or df.empty:
        return df
    
    mask = (df['DATA'] >= data_inicio) & (df['DATA'] <= data_fim)
    return df[mask].copy()

def exportar_resultados(conciliados, sugestoes, extrato_nao, razao_nao):
    """
    Exporta os resultados para Excel com múltiplas abas.
    """
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if conciliados is not None and not conciliados.empty:
            conciliados.to_excel(writer, sheet_name='Conciliados', index=False)
        
        if sugestoes is not None and not sugestoes.empty:
            sugestoes.to_excel(writer, sheet_name='Sugestoes', index=False)
        
        if extrato_nao is not None and not extrato_nao.empty:
            extrato_nao.to_excel(writer, sheet_name='Extrato_nao_conciliado', index=False)
        
        if razao_nao is not None and not razao_nao.empty:
            razao_nao.to_excel(writer, sheet_name='Razao_nao_conciliado', index=False)
    
    output.seek(0)
    return output

def formatar_valor(valor):
    """
    Formata valor para exibição.
    """
    if pd.isna(valor):
        return "R$ 0,00"
    return f"R$ {valor:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

# ============================================================================
# INTERFACE PRINCIPAL STREAMLIT
# ============================================================================

def main():
    st.title("📊 Sistema de Conciliação Contábil")
    st.markdown("---")
    
    # Sidebar para uploads
    with st.sidebar:
        st.header("📁 Upload dos Arquivos")
        
        extrato_file = st.file_uploader(
            "📄 Extrato Bancário",
            type=['xlsx', 'xls'],
            help="Upload do arquivo de extrato bancário"
        )
        
        razao_file = st.file_uploader(
            "📒 Razão Contábil",
            type=['xlsx', 'xls'],
            help="Upload do arquivo de razão contábil"
        )
        
        st.markdown("---")
        st.header("📅 Período de Análise")
        
        col1, col2 = st.columns(2)
        with col1:
            data_inicio = st.date_input("Data Inicial", datetime.now() - timedelta(days=30))
        with col2:
            data_fim = st.date_input("Data Final", datetime.now())
        
        st.markdown("---")
        processar = st.button("🚀 Processar Conciliação", type="primary", use_container_width=True)
    
    # Processamento principal
    if processar and extrato_file and razao_file:
        with st.spinner("🔄 Processando arquivos..."):
            # Carregar e normalizar dados
            df_extrato = carregar_arquivo(extrato_file, "EXTRATO")
            df_razao = carregar_arquivo(razao_file, "RAZAO")
            
            if df_extrato is not None and df_razao is not None:
                # Aplicar filtro de período
                df_extrato_filtrado = aplicar_filtro_periodo(df_extrato, data_inicio, data_fim)
                df_razao_filtrado = aplicar_filtro_periodo(df_razao, data_inicio, data_fim)
                
                # Executar conciliação
                conciliados, extrato_nao, razao_nao = conciliar_exato(df_extrato_filtrado, df_razao_filtrado)
                sugestoes = sugerir_conciliacoes(extrato_nao, razao_nao)
                
                # Armazenar na sessão
                st.session_state['conciliados'] = conciliados
                st.session_state['sugestoes'] = sugestoes
                st.session_state['extrato_nao'] = extrato_nao
                st.session_state['razao_nao'] = razao_nao
                st.session_state['df_extrato'] = df_extrato_filtrado
                st.session_state['df_razao'] = df_razao_filtrado
                st.session_state['processado'] = True
                
                st.success("✅ Conciliação concluída com sucesso!")
            else:
                st.error("❌ Erro ao processar os arquivos. Verifique o formato.")
    
    # Exibir resultados se processados
    if st.session_state.get('processado', False):
        conciliados = st.session_state.get('conciliados')
        sugestoes = st.session_state.get('sugestoes')
        extrato_nao = st.session_state.get('extrato_nao')
        razao_nao = st.session_state.get('razao_nao')
        df_extrato = st.session_state.get('df_extrato')
        df_razao = st.session_state.get('df_razao')
        
        # Abas para resultados
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "✅ Conciliados", "🧠 Sugestões", "⚠️ Extrato Não Conciliado", 
            "⚠️ Razão Não Conciliado", "📊 Resumo"
        ])
        
        with tab1:
            st.subheader("Lançamentos Conciliados")
            if conciliados is not None and not conciliados.empty:
                st.dataframe(
                    conciliados[['DATA_extrato', 'ENTRADAS_extrato', 'SAIDAS_extrato', 'MOV_extrato', 
                                'DATA_razao', 'ENTRADAS_razao', 'SAIDAS_razao', 'MOV_razao']],
                    use_container_width=True,
                    height=400
                )
                st.metric("Total de itens conciliados", len(conciliados))
            else:
                st.info("Nenhum lançamento conciliado encontrado.")
        
        with tab2:
            st.subheader("Sugestões de Conciliação")
            st.caption("Lançamentos com alta probabilidade de correspondência (score ≥ 60)")
            
            if sugestoes is not None and not sugestoes.empty:
                # Formatar para exibição
                display_sugestoes = sugestoes.copy()
                display_sugestoes['SCORE'] = display_sugestoes['SCORE'].astype(int)
                
                st.dataframe(
                    display_sugestoes,
                    use_container_width=True,
                    height=400,
                    column_config={
                        "SCORE": st.column_config.ProgressColumn("Score", min_value=0, max_value=100),
                        "DIF_VALOR": st.column_config.NumberColumn("Diferença R$", format="R$ %.2f"),
                        "DIF_DIAS": st.column_config.NumberColumn("Diferença Dias", format="%d dias")
                    }
                )
                st.info(f"🧠 Encontradas {len(sugestoes)} sugestões de conciliação")
            else:
                st.success("✅ Não há sugestões pendentes. Todas as diferenças são significativas.")
        
        with tab3:
            st.subheader("Lançamentos do Extrato sem Conciliação")
            if extrato_nao is not None and not extrato_nao.empty:
                st.dataframe(
                    extrato_nao[['DATA', 'ENTRADAS', 'SAIDAS', 'MOV']],
                    use_container_width=True,
                    height=400
                )
                st.warning(f"⚠️ {len(extrato_nao)} lançamentos do extrato não conciliados")
                st.metric("Valor total não conciliado", formatar_valor(extrato_nao['MOV'].sum()))
            else:
                st.success("✅ Todos os lançamentos do extrato foram conciliados!")
        
        with tab4:
            st.subheader("Lançamentos do Razão sem Conciliação")
            if razao_nao is not None and not razao_nao.empty:
                st.dataframe(
                    razao_nao[['DATA', 'ENTRADAS', 'SAIDAS', 'MOV']],
                    use_container_width=True,
                    height=400
                )
                st.warning(f"⚠️ {len(razao_nao)} lançamentos do razão não conciliados")
                st.metric("Valor total não conciliado", formatar_valor(razao_nao['MOV'].sum()))
            else:
                st.success("✅ Todos os lançamentos do razão foram conciliados!")
        
        with tab5:
            st.subheader("Resumo da Conciliação")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_extrato = df_extrato['MOV'].sum() if df_extrato is not None else 0
                st.metric("💰 Total Extrato", formatar_valor(total_extrato))
            
            with col2:
                total_razao = df_razao['MOV'].sum() if df_razao is not None else 0
                st.metric("📚 Total Razão", formatar_valor(total_razao))
            
            with col3:
                total_conciliado = conciliados['MOV_extrato'].sum() if conciliados is not None and not conciliados.empty else 0
                st.metric("✅ Total Conciliado", formatar_valor(total_conciliado))
            
            with col4:
                diferenca = total_extrato - total_razao
                st.metric(
                    "📊 Diferença", 
                    formatar_valor(diferenca),
                    delta=f"{abs(diferenca):.2f}" if diferenca != 0 else None,
                    delta_color="inverse" if diferenca != 0 else "off"
                )
            
            st.markdown("---")
            
            # Métricas adicionais
            col1, col2, col3 = st.columns(3)
            
            with col1:
                taxa_cobertura = (len(conciliados) / max(len(df_extrato), 1)) * 100 if conciliados is not None else 0
                st.progress(taxa_cobertura / 100)
                st.caption(f"Taxa de cobertura: {taxa_cobertura:.1f}%")
            
            with col2:
                st.info(f"📊 Período analisado: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}")
            
            with col3:
                st.info(f"📈 Total de lançamentos: {len(df_extrato) if df_extrato is not None else 0} (Extrato) | {len(df_razao) if df_razao is not None else 0} (Razão)")
        
        # Botão de exportação
        st.markdown("---")
        col_export1, col_export2, col_export3 = st.columns([1, 2, 1])
        
        with col_export2:
            if st.button("📥 Exportar Resultados para Excel", type="secondary", use_container_width=True):
                excel_file = exportar_resultados(conciliados, sugestoes, extrato_nao, razao_nao)
                st.download_button(
                    label="💾 Baixar Arquivo Excel",
                    data=excel_file,
                    file_name=f"conciliacao_contabil_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
    
    elif processar:
        if not extrato_file or not razao_file:
            st.warning("⚠️ Por favor, faça upload dos dois arquivos (Extrato e Razão) antes de processar.")

if __name__ == "__main__":
    main()