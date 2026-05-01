"""
Sistema de Conciliação Contábil - versão 2.0 (Visão Unificada)
Autor: Desenvolvedor Sênior Python
Descrição: Conciliação automática e manual em interface unificada
"""

import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime
from typing import Optional, Tuple, List, Dict
import re

# ============================================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================================
st.set_page_config(
    page_title="Conciliação Contábil Unificada",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CONSTANTES E CONFIGURAÇÕES
# ============================================================================
CONFIG = {
    'score_valor_igual': 50,
    'score_valor_proximo': 30,
    'score_data_igual': 50,
    'score_data_proxima': 30,
    'score_minimo_sugestao': 60,
    'tolerancia_valor': 0.05,
    'tolerancia_dias': 2,
    'casas_decimais': 2
}

KEYWORDS = {
    'data': ['DATA', 'DT', 'DTPAG', 'DT_MOV', 'MOVIMENTACAO', 'EMISSAO'],
    'entrada': ['ENTRADA', 'CREDITO', 'CREDITOS', 'VR_ENTRADA', 'RECEITA', 'ENTRADAS'],
    'saida': ['SAIDA', 'DEBITO', 'DEBITOS', 'VR_SAIDA', 'DESPESA', 'SAIDAS'],
    'documento': ['DOCUMENTO', 'DOC', 'NUMDOC', 'NUM_DOC', 'NR_DOC', 'NUMERO', 'LOTE'],
    'historico': ['HISTORICO', 'HIST', 'DESCRICAO', 'DESC', 'OBSERVACAO', 'OBS', 'COMPLEMENTO', 'OPERACAO'],
    'conta': ['CONTA', 'CTA', 'CONTA_CONTABIL', 'COD_CONTA']
}

ABAS_ESPERADAS = {
    'EXTRATO': ['2-Totais', 'Totais', '2 - Totais', 'EXTRATO', 'MOVIMENTO'],
    'RAZAO': ['3-Lançamentos Contábeis', '3-Lancamentos Contabeis', 'Lançamentos Contábeis', 
              'Lancamentos Contabeis', '3-Lançamentos', '3-Lancamentos', 'RAZAO', 'LANCAMENTOS']
}

# ============================================================================
# FUNÇÕES UTILITÁRIAS
# ============================================================================

def normalizar_texto(texto: str) -> str:
    if pd.isna(texto): return ""
    texto = str(texto).upper().strip()
    mapeamento = {'Á': 'A', 'À': 'A', 'Ã': 'A', 'Â': 'A', 'Ä': 'A', 'É': 'E', 'È': 'E', 
                  'Ê': 'E', 'Ë': 'E', 'Í': 'I', 'Ì': 'I', 'Î': 'I', 'Ï': 'I', 'Ó': 'O', 
                  'Ò': 'O', 'Õ': 'O', 'Ô': 'O', 'Ö': 'O', 'Ú': 'U', 'Ù': 'U', 'Û': 'U', 
                  'Ü': 'U', 'Ç': 'C', 'Ñ': 'N'}
    for acento, sem_acento in mapeamento.items():
        texto = texto.replace(acento, sem_acento)
    return texto

def normalizar_nome_coluna(coluna: str) -> str:
    if pd.isna(coluna): return "COLUNA_VAZIA"
    coluna = normalizar_texto(str(coluna))
    coluna = re.sub(r'[^A-Z0-9]', '_', coluna)
    coluna = re.sub(r'_+', '_', coluna)
    return coluna.strip('_') if coluna.strip('_') else "COLUNA_SEM_NOME"

def encontrar_aba_correta(xls_file, tipo: str) -> Optional[str]:
    abas_disponiveis = xls_file.sheet_names
    abas_esperadas = ABAS_ESPERADAS.get(tipo, [])
    abas_normalizadas = {normalizar_texto(aba): aba for aba in abas_disponiveis}
    for aba_esperada in abas_esperadas:
        aba_norm = normalizar_texto(aba_esperada)
        if aba_norm in abas_normalizadas: return abas_normalizadas[aba_norm]
        for aba_disp_norm, aba_original in abas_normalizadas.items():
            if aba_norm in aba_disp_norm or aba_disp_norm in aba_norm: return aba_original
    return None

def detectar_linha_cabecalho(df: pd.DataFrame) -> Optional[int]:
    keywords_cabecalho = ['DATA', 'VALOR', 'ENTRADA', 'SAIDA', 'DEBITO', 'CREDITO', 'CONTA']
    for idx, row in df.iterrows():
        valores = [str(v).upper() for v in row.values if pd.notna(v)]
        matches = sum(1 for v in valores for kw in keywords_cabecalho if kw in v)
        if matches >= 2: return idx
    return None

def detectar_coluna(df: pd.DataFrame, tipo: str) -> Optional[str]:
    if tipo not in KEYWORDS: return None
    keywords = KEYWORDS[tipo]
    colunas_normalizadas = {col: normalizar_nome_coluna(col) for col in df.columns}
    for col_original, col_normalizada in colunas_normalizadas.items():
        for keyword in keywords:
            if keyword in col_normalizada: return col_original
    return None

def converter_valor_monetario(valor) -> float:
    if pd.isna(valor): return 0.0
    if isinstance(valor, (int, float)): return float(valor)
    valor_str = str(valor).strip()
    is_negativo = valor_str.startswith('(') and valor_str.endswith(')')
    valor_str = re.sub(r'[R$\s\(\)]', '', valor_str)
    if ',' in valor_str and '.' in valor_str: valor_str = valor_str.replace('.', '').replace(',', '.')
    elif ',' in valor_str: valor_str = valor_str.replace(',', '.')
    try:
        resultado = float(valor_str)
        return -resultado if is_negativo else resultado
    except ValueError: return 0.0

def formatar_data_para_exibicao(data) -> str:
    if pd.isna(data): return ""
    try: return data.strftime('%d/%m/%Y')
    except: return str(data)

def formatar_valor_para_exibicao(valor) -> str:
    if pd.isna(valor): return "R$ 0,00"
    try: return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except: return str(valor)

def processar_arquivo_excel(uploaded_file, nome_tipo: str) -> Tuple[Optional[pd.DataFrame], List[str]]:
    logs = []
    try:
        xls_file = pd.ExcelFile(uploaded_file)
        logs.append(f"📁 {nome_tipo}: Arquivo carregado")
        
        aba_correta = encontrar_aba_correta(xls_file, nome_tipo)
        if aba_correta is None:
            aba_correta = xls_file.sheet_names[0]
            logs.append(f"⚠️ Usando aba: '{aba_correta}'")
        else:
            logs.append(f"✅ Aba '{aba_correta}' selecionada")
        
        uploaded_file.seek(0)
        df_raw = pd.read_excel(uploaded_file, sheet_name=aba_correta, header=None, dtype=str)
        
        linha_cabecalho = detectar_linha_cabecalho(df_raw)
        if linha_cabecalho is None:
            logs.append(f"❌ Cabeçalho não detectado")
            return None, logs
        
        uploaded_file.seek(0)
        df = pd.read_excel(uploaded_file, sheet_name=aba_correta, header=linha_cabecalho)
        df = df.loc[:, ~df.columns.astype(str).str.startswith('Unnamed')]
        df.columns = [normalizar_nome_coluna(col) for col in df.columns]
        
        # Detectar e mapear colunas
        mapeamento = {
            'data': ('DATA', detectar_coluna(df, 'data')),
            'entrada': ('ENTRADAS', detectar_coluna(df, 'entrada')),
            'saida': ('SAIDAS', detectar_coluna(df, 'saida')),
            'historico': ('HISTORICO', detectar_coluna(df, 'historico')),
            'documento': ('DOCUMENTO', detectar_coluna(df, 'documento')),
            'conta': ('CONTA', detectar_coluna(df, 'conta'))
        }
        
        for key, (novo_nome, col_orig) in mapeamento.items():
            if col_orig:
                df = df.rename(columns={col_orig: novo_nome})
                logs.append(f"✅ '{col_orig}' → '{novo_nome}'")
            else:
                if key in ['data']: 
                    logs.append(f"❌ Coluna obrigatória {key} não encontrada")
                    return None, logs
                df[novo_nome] = '' if key != 'entrada' and key != 'saida' else 0.0
                logs.append(f"⚠️ {novo_nome} não detectado, criado vazio/zero")
        
        # Conversões
        df['DATA'] = pd.to_datetime(df['DATA'], errors='coerce', dayfirst=True)
        df = df.dropna(subset=['DATA'])
        
        df['ENTRADAS'] = df['ENTRADAS'].apply(converter_valor_monetario).fillna(0)
        df['SAIDAS'] = df['SAIDAS'].apply(converter_valor_monetario).fillna(0)
        
        df['MOV'] = (df['ENTRADAS'] - df['SAIDAS']).round(CONFIG['casas_decimais'])
        df['TP'] = nome_tipo
        df['CONTA'] = df.get('CONTA', '')
        
        # Chave para conciliação automática
        df['CHAVE'] = df['DATA'].dt.strftime('%Y-%m-%d') + '_' + df['MOV'].round(2).astype(str)
        
        # Remover movimento zero
        df = df[df['MOV'] != 0]
        
        logs.append(f"✅ {len(df)} registros processados")
        return df, logs
        
    except Exception as e:
        logs.append(f"❌ Erro: {str(e)}")
        return None, logs

def calcular_score_match(row1: pd.Series, row2: pd.Series) -> int:
    score = 0
    diff_valor = abs(abs(row1['MOV']) - abs(row2['MOV']))
    if diff_valor == 0: score += 50
    elif diff_valor <= CONFIG['tolerancia_valor']: score += 30
    
    if pd.notna(row1['DATA']) and pd.notna(row2['DATA']):
        diff_dias = abs((row1['DATA'] - row2['DATA']).days)
        if diff_dias == 0: score += 50
        elif diff_dias <= CONFIG['tolerancia_dias']: score += 30
    return score

# ============================================================================
# LÓGICA DE CONCILIAÇÃO E UNIFICAÇÃO
# ============================================================================

def executar_conciliacao_unificada(df_extrato, df_razao):
    """Executa a conciliação e retorna um DataFrame unificado com status."""
    
    # Preparar IDs únicos para rastreamento
    df_extrato = df_extrato.copy()
    df_razao = df_razao.copy()
    df_extrato['ID'] = ['EX_' + str(i) for i in range(len(df_extrato))]
    df_razao['ID'] = ['RZ_' + str(i) for i in range(len(df_razao))]
    
    # 1. Status inicial
    df_extrato['STATUS'] = 'Não Conciliado'
    df_razao['STATUS'] = 'Não Conciliado'
    
    # 2. Conciliação Automática (Exata)
    chaves_extrato = df_extrato['CHAVE'].value_counts().to_dict()
    chaves_razao = df_razao['CHAVE'].value_counts().to_dict()
    chaves_comuns = set(df_extrato['CHAVE']).intersection(set(df_razao['CHAVE']))
    
    ids_conciliados_ex = []
    ids_conciliados_rz = []
    
    for chave in chaves_comuns:
        qtd_e = chaves_extrato.get(chave, 0)
        qtd_r = chaves_razao.get(chave, 0)
        matches = min(qtd_e, qtd_r)
        
        idx_e = df_extrato[df_extrato['CHAVE'] == chave].index[:matches]
        idx_r = df_razao[df_razao['CHAVE'] == chave].index[:matches]
        
        df_extrato.loc[idx_e, 'STATUS'] = 'Conciliado'
        df_razao.loc[idx_r, 'STATUS'] = 'Conciliado'
        
        # Guardar pares conciliados (opcional, para futuro "desfazer")
    
    # 3. Sugestões
    # Marcar linhas que têm sugestões potenciais mas não foram conciliadas
    extrato_nc = df_extrato[df_extrato['STATUS'] == 'Não Conciliado']
    razao_nc = df_razao[df_razao['STATUS'] == 'Não Conciliado']
    
    # Otimização: indexar por valor para buscar sugestões
    ids_com_sugestao = set()
    
    if not extrato_nc.empty and not razao_nc.empty:
        # Criar índice simples de valor para busca rápida
        razao_nc_idx = razao_nc.copy()
        razao_nc_idx['_v_int'] = (razao_nc_idx['MOV'].abs() * 100).astype(int)
        extrato_nc_idx = extrato_nc.copy()
        extrato_nc_idx['_v_int'] = (extrato_nc_idx['MOV'].abs() * 100).astype(int)
        
        for idx_e, row_e in extrato_nc_idx.iterrows():
            v_int = row_e['_v_int']
            # Buscar razão com valor próximo
            candidatos = razao_nc_idx[(razao_nc_idx['_v_int'] >= v_int - 5) & (razao_nc_idx['_v_int'] <= v_int + 5)]
            
            for idx_r in candidatos.index:
                row_r = razao_nc_idx.loc[idx_r]
                score = calcular_score_match(row_e, row_r)
                if score >= CONFIG['score_minimo_sugestao']:
                    ids_com_sugestao.add(row_e['ID'])
                    ids_com_sugestao.add(razao_nc_idx.loc[idx_r, 'ID'])
                    break # Encontrou uma sugestão boa, marca e passa para o próximo
    
    # Atualizar status de sugestão
    df_extrato.loc[df_extrato['ID'].isin(ids_com_sugestao), 'STATUS'] = 'Sugestão'
    df_razao.loc[df_razao['ID'].isin(ids_com_sugestao), 'STATUS'] = 'Sugestão'
    
    # 4. Unificar DataFrames
    colunas_unificadas = ['ID', 'STATUS', 'TP', 'CONTA', 'DATA', 'HISTORICO', 'DOCUMENTO', 'ENTRADAS', 'SAIDAS', 'MOV', 'CHAVE']
    
    # Garantir que todas as colunas existam
    for col in colunas_unificadas:
        if col not in df_extrato: df_extrato[col] = ''
        if col not in df_razao: df_razao[col] = ''
    
    df_final = pd.concat([
        df_extrato[colunas_unificadas],
        df_razao[colunas_unificadas]
    ], ignore_index=True)
    
    # Adicionar coluna de seleção para o usuário
    df_final['SELECAO'] = False
    
    return df_final

def exportar_excel_unificado(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    # Remover colunas técnicas para exportação
    df_exp = df.drop(columns=['SELECAO'], errors='ignore')
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_exp.to_excel(writer, sheet_name='Conciliacao_Unificada', index=False)
    output.seek(0)
    return output.getvalue()

# ============================================================================
# INTERFACE STREAMLIT
# ============================================================================

def main():
    st.title("🔄 Conciliação Contábil - Visão Unificada")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("📋 Uploads e Filtros")
        st.markdown("**1. Carregar Arquivos**")
        arquivo_extrato = st.file_uploader("Extrato (Aba 2-Totais)", type=['xlsx', 'xls'], key="up_extrato")
        arquivo_razao = st.file_uploader("Razão (Aba 3-Lançamentos)", type=['xlsx', 'xls'], key="up_razao")
        
        st.markdown("---")
        st.markdown("**Sobre o Sistema:**")
        st.markdown("✅ Automático: DATA + VALOR exatos")
        st.markdown("🧠 Sugestão: Similaridade > 60pts")
        st.markdown("✋ Manual: Seleção do usuário")
    
    # Processamento Inicial
    if arquivo_extrato and arquivo_razao:
        if 'df_unificado' not in st.session_state or st.session_state.get('processar_novamente', False):
            with st.spinner("Processando arquivos..."):
                df_extrato, _ = processar_arquivo_excel(arquivo_extrato, "EXTRATO")
                df_razao, _ = processar_arquivo_excel(arquivo_razao, "RAZAO")
                
                if df_extrato is not None and df_razao is not None:
                    df_unificado = executar_conciliacao_unificada(df_extrato, df_razao)
                    st.session_state['df_unificado'] = df_unificado
                    st.session_state['processar_novamente'] = False
                else:
                    st.error("Erro ao processar arquivos. Verifique os logs.")
                    return

    # Main Area
    if 'df_unificado' in st.session_state:
        df_base = st.session_state['df_unificado'].copy()
        
        # 1. Filtros Superiores
        col_f1, col_f2, col_f3, col_f4 = st.columns([2, 2, 2, 2])
        
        with col_f1:
            filtro_status = st.multiselect(
                "Filtrar por Status:",
                options=['Conciliado', 'Sugestão', 'Não Conciliado'],
                default=['Conciliado', 'Sugestão', 'Não Conciliado']
            )
        
        with col_f2:
            filtro_tipo = st.multiselect(
                "Filtrar por Origem:",
                options=['EXTRATO', 'RAZAO'],
                default=['EXTRATO', 'RAZAO']
            )
        
        with col_f3:
            # Filtro rápido para ver o que sobrou
            if st.button("Mostrar Pendentes", use_container_width=True):
                filtro_status = ['Não Conciliado', 'Sugestão']
                st.session_state['filtro_status_pendentes'] = filtro_status
        
        # Aplicar Filtros
        df_filtrado = df_base[
            df_base['STATUS'].isin(filtro_status) & 
            df_base['TP'].isin(filtro_tipo)
        ].copy()
        
        # 2. Tabela de Edição (Data Editor)
        st.markdown(f"### 📊 Lançamentos ({len(df_filtrado)} exibidos)")
        
        # Configuração das colunas
        column_config = {
            "SELECAO": st.column_config.CheckboxColumn("Selecionar", default=False),
            "ID": None, # Ocultar ID técnico
            "DATA": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "ENTRADAS": st.column_config.NumberColumn("Entradas", format="R$ %.2f"),
            "SAIDAS": st.column_config.NumberColumn("Saídas", format="R$ %.2f"),
            "MOV": st.column_config.NumberColumn("Movimento", format="R$ %.2f"),
            "STATUS": st.column_config.TextColumn("Status"),
            "TP": st.column_config.TextColumn("Tipo"),
            "CONTA": st.column_config.TextColumn("Conta"),
            "HISTORICO": st.column_config.TextColumn("Histórico/Operação"),
            "DOCUMENTO": st.column_config.TextColumn("Documento"),
            "CHAVE": None # Ocultar chave técnica
        }
        
        # Reordenar colunas para exibição
        cols_ordem = ['SELECAO', 'STATUS', 'TP', 'CONTA', 'DATA', 'HISTORICO', 'DOCUMENTO', 'ENTRADAS', 'SAIDAS', 'MOV']
        # Filtrar apenas colunas que existem
        cols_existentes = [c for c in cols_ordem if c in df_filtrado.columns]
        df_display = df_filtrado[cols_existentes]
        
        edited_df = st.data_editor(
            df_display,
            column_config=column_config,
            use_container_width=True,
            hide_index=True,
            disabled=['DATA', 'MOV', 'STATUS', 'TP'], # Impede edição de dados brutos
            key="data_editor_main"
        )
        
        # 3. Ações de Conciliação Manual
        st.markdown("---")
        col_a1, col_a2, col_a3 = st.columns([1, 1, 4])
        
        with col_a1:
            if st.button("✅ Conciliar Selecionados", type="primary", use_container_width=True):
                # Identificar linhas selecionadas
                selecionados = edited_df[edited_df['SELECAO'] == True]
                
                if len(selecionados) < 2:
                    st.warning("Selecione pelo menos 2 linhas para conciliar manualmente.")
                else:
                    # Validar se tem pelo menos 1 de cada lado
                    tipos_sel = selecionados['TP'].unique()
                    if 'EXTRATO' not in tipos_sel or 'RAZAO' not in tipos_sel:
                        st.warning("Selecione pelo menos 1 item do EXTRATO e 1 do RAZÃO.")
                    else:
                        # Atualizar o DataFrame principal na sessão
                        # Encontrar índices no DF original baseado no ID (precisamos recuperar o ID)
                        # O data_editor remove colunas ocultas, mas mantém a ordem/índice original se não resetarmos
                        
                        # Como 'ID' foi ocultado, vamos usar o índice do df_display que corresponde ao df_filtrado
                        # Mas o data_editor retorna o DF modificado.
                        
                        # Abordagem segura: Recuperar IDs pelo índice original
                        # O df_filtrado tem o índice do df_base.
                        
                        indices_selecionados = selecionados.index
                        st.session_state['df_unificado'].loc[indices_selecionados, 'STATUS'] = 'Conciliado Manual'
                        st.session_state['df_unificado'].loc[indices_selecionados, 'SELECAO'] = False
                        
                        st.success(f"{len(selecionados)} itens conciliados manualmente com sucesso!")
                        st.rerun()

        with col_a2:
            if st.button("↩️ Desfazer Conciliação", use_container_width=True):
                selecionados = edited_df[edited_df['SELECAO'] == True]
                if len(selecionados) > 0:
                    indices_selecionados = selecionados.index
                    st.session_state['df_unificado'].loc[indices_selecionados, 'STATUS'] = 'Não Conciliado'
                    st.success("Status alterado para 'Não Conciliado'.")
                    st.rerun()
                else:
                    st.warning("Selecione linhas para desfazer a conciliação.")
        
        # 4. Resumo e Exportação
        st.markdown("### 📈 Resumo Atualizado")
        df_resumo = st.session_state['df_unificado']
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Conciliado", f"{len(df_resumo[df_resumo['STATUS'].isin(['Conciliado', 'Conciliado Manual'])])}")
        c2.metric("Sugestões", f"{len(df_resumo[df_resumo['STATUS'] == 'Sugestão'])}")
        c3.metric("Pendentes", f"{len(df_resumo[df_resumo['STATUS'] == 'Não Conciliado'])}")
        
        # Diferença financeira
        conciliados = df_resumo[df_resumo['STATUS'].isin(['Conciliado', 'Conciliado Manual'])]
        total_extrato = conciliados[conciliados['TP']=='EXTRATO']['MOV'].sum()
        total_razao = conciliados[conciliados['TP']=='RAZAO']['MOV'].sum()
        c4.metric("Diferença Conciliada", formatar_valor_para_exibicao(abs(total_extrato - total_razao)))
        
        # Exportação
        st.markdown("---")
        if st.button("📥 Exportar Excel"):
            excel_data = exportar_excel_unificado(st.session_state['df_unificado'])
            st.download_button(
                label="Clique para baixar",
                data=excel_data,
                file_name=f"conciliacao_unificada_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
    else:
        st.info("👆 Faça o upload dos arquivos na barra lateral para iniciar.")

if __name__ == "__main__":
    main()