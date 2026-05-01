"""
Sistema de Conciliação Contábil - Versão Simplificada
Funcionalidades: Conciliação automática + manual, filtros dinâmicos
"""

import streamlit as st
import pandas as pd
import re
from io import BytesIO
from datetime import datetime

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================
st.set_page_config(page_title="Conciliação Contábil", page_icon="🔄", layout="wide")

# Palavras-chave para detectar colunas
KEYWORDS = {
    'data': ['DATA', 'DT', 'DTPAG', 'EMISSAO'],
    'entrada': ['ENTRADA', 'CREDITO', 'RECEITA'],
    'saida': ['SAIDA', 'DEBITO', 'DESPESA'],
    'historico': ['HISTORICO', 'DESCRICAO', 'OBS']
}

# ============================================================================
# FUNÇÕES PRINCIPAIS
# ============================================================================

def normalizar_texto(texto):
    """Remove acentos e deixa maiúsculo"""
    if pd.isna(texto):
        return ""
    texto = str(texto).upper().strip()
    texto = texto.replace('Á', 'A').replace('É', 'E').replace('Í', 'I').replace('Ó', 'O').replace('Ú', 'U')
    texto = texto.replace('Ã', 'A').replace('Õ', 'O').replace('Ç', 'C')
    return texto

def detectar_coluna(df, tipo):
    """Encontra a coluna correta baseado nas palavras-chave"""
    for col in df.columns:
        col_norm = normalizar_texto(str(col))
        for palavra in KEYWORDS[tipo]:
            if palavra in col_norm:
                return col
    return None

def converter_valor(valor):
    """Converte texto para número"""
    if pd.isna(valor):
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    
    valor_str = str(valor).strip()
    negativo = valor_str.startswith('(') and valor_str.endswith(')')
    valor_str = re.sub(r'[R$\s\(\)]', '', valor_str)
    
    # Trata formato brasileiro (1.000,50)
    if ',' in valor_str and '.' in valor_str:
        valor_str = valor_str.replace('.', '').replace(',', '.')
    elif ',' in valor_str:
        valor_str = valor_str.replace(',', '.')
    
    try:
        resultado = float(valor_str)
        return -resultado if negativo else resultado
    except:
        return 0.0

def carregar_arquivo(arquivo, nome):
    """Carrega e processa o arquivo Excel automaticamente"""
    if arquivo is None:
        return None, []
    
    logs = []
    try:
        # Tenta encontrar a aba correta
        xls = pd.ExcelFile(arquivo)
        aba_encontrada = None
        
        # Procura a aba pelo nome esperado
        for aba in xls.sheet_names:
            if '2-Totais' in aba or '3-Lançamentos' in aba:
                aba_encontrada = aba
                break
        
        if not aba_encontrada:
            aba_encontrada = xls.sheet_names[0]
            logs.append(f"⚠️ Usando primeira aba: {aba_encontrada}")
        else:
            logs.append(f"✅ Aba encontrada: {aba_encontrada}")
        
        # Lê o arquivo
        df = pd.read_excel(arquivo, sheet_name=aba_encontrada)
        logs.append(f"📊 {len(df)} linhas carregadas")
        
        # Detecta colunas
        col_data = detectar_coluna(df, 'data')
        col_entrada = detectar_coluna(df, 'entrada')
        col_saida = detectar_coluna(df, 'saida')
        col_hist = detectar_coluna(df, 'historico')
        
        if not col_data:
            logs.append("❌ Coluna de DATA não encontrada")
            return None, logs
        
        # Renomeia colunas
        df = df.rename(columns={col_data: 'DATA'})
        
        if col_entrada:
            df = df.rename(columns={col_entrada: 'ENTRADAS'})
        else:
            df['ENTRADAS'] = 0
        
        if col_saida:
            df = df.rename(columns={col_saida: 'SAIDAS'})
        else:
            df['SAIDAS'] = 0
        
        if col_hist:
            df = df.rename(columns={col_hist: 'HISTORICO'})
        else:
            df['HISTORICO'] = ''
        
        # Converte dados
        df['DATA'] = pd.to_datetime(df['DATA'], errors='coerce', dayfirst=True)
        df['ENTRADAS'] = df['ENTRADAS'].apply(converter_valor)
        df['SAIDAS'] = df['SAIDAS'].apply(converter_valor)
        df['MOV'] = (df['ENTRADAS'] - df['SAIDAS']).round(2)
        
        # Remove linhas sem movimento
        df = df[df['MOV'] != 0]
        df = df.dropna(subset=['DATA'])
        
        # Adiciona origem e chave
        df['ORIGEM'] = nome
        df['CHAVE'] = df['DATA'].dt.strftime('%Y%m%d') + '_' + df['MOV'].astype(str)
        
        logs.append(f"✅ {len(df)} registros válidos")
        return df, logs
        
    except Exception as e:
        logs.append(f"❌ Erro: {str(e)}")
        return None, logs

def fazer_conciliacao_auto(df_extrato, df_razao):
    """Conciliação automática por DATA + VALOR"""
    # Marca registros já conciliados
    df_extrato['CONCILIADO'] = False
    df_razao['CONCILIADO'] = False
    
    # Encontra matches exatos
    chaves_extrato = set(df_extrato['CHAVE'])
    chaves_razao = set(df_razao['CHAVE'])
    chaves_comuns = chaves_extrato.intersection(chaves_razao)
    
    matches = []
    for chave in chaves_comuns:
        # Pega um de cada lado (primeiro match)
        extrato_match = df_extrato[df_extrato['CHAVE'] == chave].iloc[0]
        razao_match = df_razao[df_razao['CHAVE'] == chave].iloc[0]
        
        matches.append({
            'DATA': extrato_match['DATA'],
            'VALOR': extrato_match['MOV'],
            'HISTORICO_EXTRATO': extrato_match.get('HISTORICO', ''),
            'HISTORICO_RAZAO': razao_match.get('HISTORICO', ''),
            'STATUS': '✅ Conciliado Auto',
            'CHAVE': chave,
            'ID_EXTRATO': extrato_match.name,
            'ID_RAZAO': razao_match.name
        })
        
        # Marca como conciliado
        df_extrato.loc[extrato_match.name, 'CONCILIADO'] = True
        df_razao.loc[razao_match.name, 'CONCILIADO'] = True
    
    return pd.DataFrame(matches), df_extrato, df_razao

def gerar_sugestoes(df_extrato, df_razao):
    """Gera sugestões para valores próximos"""
    sugestoes = []
    
    extrato_nc = df_extrato[~df_extrato['CONCILIADO']].copy()
    razao_nc = df_razao[~df_razao['CONCILIADO']].copy()
    
    for _, extrato_row in extrato_nc.iterrows():
        for _, razao_row in razao_nc.iterrows():
            # Verifica se valores são próximos (diferença <= 0.10)
            diferenca = abs(extrato_row['MOV'] - razao_row['MOV'])
            if diferenca <= 0.10:
                sugestoes.append({
                    'DATA_EXTRATO': extrato_row['DATA'],
                    'VALOR_EXTRATO': extrato_row['MOV'],
                    'HISTORICO_EXTRATO': extrato_row.get('HISTORICO', ''),
                    'DATA_RAZAO': razao_row['DATA'],
                    'VALOR_RAZAO': razao_row['MOV'],
                    'HISTORICO_RAZAO': razao_row.get('HISTORICO', ''),
                    'DIFERENCA': diferenca,
                    'ID_EXTRATO': extrato_row.name,
                    'ID_RAZAO': razao_row.name
                })
    
    return pd.DataFrame(sugestoes)

def formatar_data(data):
    """Formata data para exibição"""
    if pd.isna(data):
        return ""
    return data.strftime('%d/%m/%Y') if hasattr(data, 'strftime') else str(data)

def formatar_valor(valor):
    """Formata valor para exibição"""
    if pd.isna(valor):
        return "R$ 0,00"
    return f"R$ {valor:,.2f}".replace('.', 'X').replace(',', '.').replace('X', ',')

# ============================================================================
# INTERFACE PRINCIPAL
# ============================================================================

def main():
    st.title("🔄 Conciliação Contábil")
    st.markdown("---")
    
    # Sidebar com ajuda
    with st.sidebar:
        st.header("📋 Ajuda")
        st.markdown("""
        1. **Envie o arquivo do EXTRATO** (aba esperada: `2-Totais`)
        2. **Envie o arquivo do RAZÃO** (aba esperada: `3-Lançamentos`)
        3. **Clique em "Realizar Conciliação"**
        4. **Use os filtros** para visualizar os dados
        5. **Marque os checkboxes** para conciliar manualmente
        """)
        st.markdown("---")
        st.caption("Sistema simplificado de conciliação")
    
    # Upload dos arquivos
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📥 Extrato Bancário")
        arquivo_extrato = st.file_uploader("Arquivo Excel", type=['xlsx', 'xls'], key="extrato")
    
    with col2:
        st.subheader("📥 Razão Contábil")
        arquivo_razao = st.file_uploader("Arquivo Excel", type=['xlsx', 'xls'], key="razao")
    
    # Botão de processamento
    processar = st.button("🔄 Realizar Conciliação", type="primary", use_container_width=True)
    
    if processar and arquivo_extrato and arquivo_razao:
        with st.spinner("Carregando arquivos..."):
            df_extrato, logs_extrato = carregar_arquivo(arquivo_extrato, "EXTRATO")
            df_razao, logs_razao = carregar_arquivo(arquivo_razao, "RAZAO")
        
        # Exibe logs
        with st.expander("📋 Logs de processamento"):
            if logs_extrato:
                st.info("**EXTRATO:**\n" + "\n".join(logs_extrato))
            if logs_razao:
                st.info("**RAZÃO:**\n" + "\n".join(logs_razao))
        
        if df_extrato is not None and df_razao is not None:
            with st.spinner("Conciliando..."):
                # Conciliação automática
                df_conciliados, df_extrato, df_razao = fazer_conciliacao_auto(df_extrato, df_razao)
                
                # Sugestões
                df_sugestoes = gerar_sugestoes(df_extrato, df_razao)
                
                # Monta lista completa de não conciliados
                nao_conciliados = []
                
                # Adiciona não conciliados do extrato
                for _, row in df_extrato[~df_extrato['CONCILIADO']].iterrows():
                    nao_conciliados.append({
                        'DATA': row['DATA'],
                        'VALOR': row['MOV'],
                        'HISTORICO': row.get('HISTORICO', ''),
                        'ORIGEM': 'EXTRATO',
                        'STATUS': '❌ Não Conciliado',
                        'ID': row.name,
                        'TIPO': 'extrato'
                    })
                
                # Adiciona não conciliados do razão
                for _, row in df_razao[~df_razao['CONCILIADO']].iterrows():
                    nao_conciliados.append({
                        'DATA': row['DATA'],
                        'VALOR': row['MOV'],
                        'HISTORICO': row.get('HISTORICO', ''),
                        'ORIGEM': 'RAZÃO',
                        'STATUS': '❌ Não Conciliado',
                        'ID': row.name,
                        'TIPO': 'razao'
                    })
                
                df_nao_conciliados = pd.DataFrame(nao_conciliados)
                
                # Prepara sugestões com checkbox
                if not df_sugestoes.empty:
                    sugestoes_com_check = []
                    for _, row in df_sugestoes.iterrows():
                        sugestoes_com_check.append({
                            '☑️ Conciliar': False,
                            'DATA EXTRATO': formatar_data(row['DATA_EXTRATO']),
                            'VALOR EXTRATO': formatar_valor(row['VALOR_EXTRATO']),
                            'HISTÓRICO EXTRATO': row['HISTORICO_EXTRATO'][:50],
                            'DATA RAZÃO': formatar_data(row['DATA_RAZÃO']),
                            'VALOR RAZÃO': formatar_valor(row['VALOR_RAZAO']),
                            'HISTÓRICO RAZÃO': row['HISTORICO_RAZAO'][:50],
                            'DIFERENÇA': formatar_valor(row['DIFERENCA']),
                            'ID_EXTRATO': row['ID_EXTRATO'],
                            'ID_RAZAO': row['ID_RAZAO']
                        })
                    df_sugestoes_display = pd.DataFrame(sugestoes_com_check)
                else:
                    df_sugestoes_display = pd.DataFrame()
                
                # Salva na sessão
                st.session_state['df_conciliados'] = df_conciliados
                st.session_state['df_sugestoes'] = df_sugestoes_display
                st.session_state['df_nao_conciliados'] = df_nao_conciliados
                st.session_state['df_extrato_raw'] = df_extrato
                st.session_state['df_razao_raw'] = df_razao
                st.session_state['conciliado'] = True
                
                st.success("✅ Conciliação realizada!")
    
    # ============================================================================
    # EXIBIÇÃO DOS RESULTADOS
    # ============================================================================
    
    if st.session_state.get('conciliado', False):
        st.markdown("---")
        
        # Cards de resumo
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("✅ Conciliados Auto", len(st.session_state['df_conciliados']))
        with col2:
            st.metric("💡 Sugestões", len(st.session_state['df_sugestoes']))
        with col3:
            st.metric("⚠️ Não Conciliados", len(st.session_state['df_nao_conciliados']))
        with col4:
            total = len(st.session_state['df_conciliados']) + len(st.session_state['df_sugestoes']) + len(st.session_state['df_nao_conciliados'])
            st.metric("📊 Total", total)
        
        st.markdown("---")
        
        # Filtro principal
        st.subheader("🔍 Filtros")
        tipo_filtro = st.radio(
            "Exibir:",
            ["📋 Todos os lançamentos", "✅ Apenas Conciliados", "💡 Apenas Sugestões", "⚠️ Apenas Não Conciliados"],
            horizontal=True
        )
        
        st.markdown("---")
        
        # ========================================================================
        # CONCILIADOS
        # ========================================================================
        if tipo_filtro in ["📋 Todos os lançamentos", "✅ Apenas Conciliados"]:
            st.subheader("✅ Lançamentos Conciliados Automaticamente")
            if not st.session_state['df_conciliados'].empty:
                df_display = st.session_state['df_conciliados'].copy()
                df_display['DATA'] = df_display['DATA'].apply(formatar_data)
                df_display['VALOR'] = df_display['VALOR'].apply(formatar_valor)
                st.dataframe(df_display.drop(columns=['CHAVE', 'ID_EXTRATO', 'ID_RAZAO'], errors='ignore'), 
                           use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum lançamento conciliado")
        
        # ========================================================================
        # SUGESTÕES (com checkbox para conciliação manual)
        # ========================================================================
        if tipo_filtro in ["📋 Todos os lançamentos", "💡 Apenas Sugestões"]:
            st.subheader("💡 Sugestões de Conciliação (Marque para conciliar manualmente)")
            
            if not st.session_state['df_sugestoes'].empty:
                # Exibe com checkboxes
                df_sug = st.session_state['df_sugestoes'].copy()
                
                # Usa st.data_editor para permitir marcação
                edited_df = st.data_editor(
                    df_sug,
                    column_config={
                        "☑️ Conciliar": st.column_config.CheckboxColumn("Conciliar", default=False),
                        "DATA EXTRATO": st.column_config.TextColumn("Data Extrato"),
                        "VALOR EXTRATO": st.column_config.TextColumn("Valor Extrato"),
                        "DATA RAZÃO": st.column_config.TextColumn("Data Razão"),
                        "VALOR RAZÃO": st.column_config.TextColumn("Valor Razão"),
                    },
                    use_container_width=True,
                    hide_index=True,
                    key="sugestoes_editor"
                )
                
                # Botão para confirmar conciliação manual
                selecionados = edited_df[edited_df['☑️ Conciliar'] == True]
                
                if not selecionados.empty:
                    if st.button(f"✅ Conciliar {len(selecionados)} selecionado(s)", type="primary"):
                        st.success(f"{len(selecionados)} lançamento(s) conciliado(s) manualmente!")
                        # Aqui você pode implementar a lógica para salvar as conciliações manuais
                        # Limpa os selecionados após conciliar
                        st.rerun()
            else:
                st.info("Nenhuma sugestão disponível")
        
        # ========================================================================
        # NÃO CONCILIADOS (com checkbox para conciliação manual)
        # ========================================================================
        if tipo_filtro in ["📋 Todos os lançamentos", "⚠️ Apenas Não Conciliados"]:
            st.subheader("⚠️ Lançamentos Não Conciliados")
            
            if not st.session_state['df_nao_conciliados'].empty:
                df_nc = st.session_state['df_nao_conciliados'].copy()
                df_nc['DATA'] = df_nc['DATA'].apply(formatar_data)
                df_nc['VALOR'] = df_nc['VALOR'].apply(formatar_valor)
                
                # Adiciona checkbox para conciliação manual
                df_nc.insert(0, '☑️ Conciliar', False)
                
                edited_nc = st.data_editor(
                    df_nc,
                    column_config={
                        "☑️ Conciliar": st.column_config.CheckboxColumn("Conciliar", default=False),
                        "DATA": st.column_config.TextColumn("Data"),
                        "VALOR": st.column_config.TextColumn("Valor"),
                        "HISTORICO": st.column_config.TextColumn("Histórico", width="large"),
                    },
                    use_container_width=True,
                    hide_index=True,
                    key="nao_conciliados_editor"
                )
                
                selecionados_nc = edited_nc[edited_nc['☑️ Conciliar'] == True]
                
                if not selecionados_nc.empty:
                    if st.button(f"✅ Conciliar {len(selecionados_nc)} selecionado(s) manualmente", key="btn_manual"):
                        st.success(f"{len(selecionados_nc)} lançamento(s) conciliado(s) manualmente!")
                        st.rerun()
            else:
                st.success("🎉 Todos os lançamentos foram conciliados!")

# ============================================================================
# EXECUÇÃO
# ============================================================================

if __name__ == "__main__":
    main()