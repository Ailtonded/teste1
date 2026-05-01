"""
Sistema de Conciliação Contábil - versão 2.5 (Usabilidade e ID Sugestões)
Autor: Desenvolvedor Sênior Python
Descrição: Adicionado ID_SUGESTAO, botão inverter seleção e totais filtrados.
"""

import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime, timedelta
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
                df[novo_nome] = '' if key not in ['entrada', 'saida'] else 0.0
                logs.append(f"⚠️ {novo_nome} não detectado")
        
        df['DATA'] = pd.to_datetime(df['DATA'], errors='coerce', dayfirst=True)
        df = df.dropna(subset=['DATA'])
        
        df['ENTRADAS'] = df['ENTRADAS'].apply(converter_valor_monetario).fillna(0)
        df['SAIDAS'] = df['SAIDAS'].apply(converter_valor_monetario).fillna(0)
        
        df['MOV'] = (df['ENTRADAS'] - df['SAIDAS']).round(CONFIG['casas_decimais'])
        df['TP'] = nome_tipo
        df['CONTA'] = df.get('CONTA', '')
        
        df['CHAVE'] = df['DATA'].dt.strftime('%Y-%m-%d') + '_' + df['MOV'].round(2).astype(str)
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
# LÓGICA DE CONCILIAÇÃO
# ============================================================================

def executar_conciliacao_unificada(df_extrato, df_razao):
    df_extrato = df_extrato.copy()
    df_razao = df_razao.copy()
    df_extrato['ID'] = ['EX_' + str(i) for i in range(len(df_extrato))]
    df_razao['ID'] = ['RZ_' + str(i) for i in range(len(df_razao))]
    
    df_extrato['STATUS'] = 'Não Conciliado'
    df_razao['STATUS'] = 'Não Conciliado'
    
    df_extrato['ID_CONCILIACAO'] = None
    df_razao['ID_CONCILIACAO'] = None
    
    # NOVO: Inicializar ID_SUGESTAO
    df_extrato['ID_SUGESTAO'] = None
    df_razao['ID_SUGESTAO'] = None
    
    chaves_extrato = df_extrato['CHAVE'].value_counts().to_dict()
    chaves_razao = df_razao['CHAVE'].value_counts().to_dict()
    chaves_comuns = set(df_extrato['CHAVE']).intersection(set(df_razao['CHAVE']))
    
    contador_id_conc = 0
    
    for chave in chaves_comuns:
        qtd_e = chaves_extrato.get(chave, 0)
        qtd_r = chaves_razao.get(chave, 0)
        matches = min(qtd_e, qtd_r)
        
        idx_e = df_extrato[df_extrato['CHAVE'] == chave].index[:matches]
        idx_r = df_razao[df_razao['CHAVE'] == chave].index[:matches]
        
        df_extrato.loc[idx_e, 'STATUS'] = 'Conciliado'
        df_razao.loc[idx_r, 'STATUS'] = 'Conciliado'
        
        contador_id_conc += 1
        novo_id = f"CONC_{contador_id_conc}"
        df_extrato.loc[idx_e, 'ID_CONCILIACAO'] = novo_id
        df_razao.loc[idx_r, 'ID_CONCILIACAO'] = novo_id
    
    extrato_nc = df_extrato[df_extrato['STATUS'] == 'Não Conciliado']
    razao_nc = df_razao[df_razao['STATUS'] == 'Não Conciliado']
    
    # NOVO: Contador para ID de Sugestão
    contador_sug_id = 0
    
    if not extrato_nc.empty and not razao_nc.empty:
        razao_nc_idx = razao_nc.copy()
        razao_nc_idx['_v_int'] = (razao_nc_idx['MOV'].abs() * 100).astype(int)
        
        for idx_e, row_e in extrato_nc.iterrows():
            v_int = int(abs(row_e['MOV']) * 100)
            candidatos = razao_nc_idx[(razao_nc_idx['_v_int'] >= v_int - 5) & (razao_nc_idx['_v_int'] <= v_int + 5)]
            
            for idx_r in candidatos.index:
                score = calcular_score_match(row_e, razao_nc_idx.loc[idx_r])
                if score >= CONFIG['score_minimo_sugestao']:
                    df_extrato.loc[idx_e, 'STATUS'] = 'Sugestão'
                    df_razao.loc[idx_r, 'STATUS'] = 'Sugestão'
                    
                    # NOVO: Gerar ID de Sugestão
                    contador_sug_id += 1
                    novo_sug_id = f"SUG_{contador_sug_id}"
                    df_extrato.loc[idx_e, 'ID_SUGESTAO'] = novo_sug_id
                    df_razao.loc[idx_r, 'ID_SUGESTAO'] = novo_sug_id
                    
                    break
    
    # NOVO: Adicionado ID_SUGESTAO às colunas unificadas
    colunas_unificadas = ['ID', 'STATUS', 'ID_CONCILIACAO', 'ID_SUGESTAO', 'TP', 'CONTA', 'DATA', 'HISTORICO', 'DOCUMENTO', 'ENTRADAS', 'SAIDAS', 'MOV', 'CHAVE']
    for col in colunas_unificadas:
        if col not in df_extrato: df_extrato[col] = ''
        if col not in df_razao: df_razao[col] = ''
    
    df_final = pd.concat([df_extrato[colunas_unificadas], df_razao[colunas_unificadas]], ignore_index=True)
    df_final['SELECAO'] = False
    
    return df_final

def exportar_excel_unificado(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    df_exp = df.copy()
    if 'DATA' in df_exp.columns:
        df_exp['DATA'] = df_exp['DATA'].apply(lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) else '')
    
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
        st.header("📂 1. Upload de Arquivos")
        arquivo_extrato = st.file_uploader("Extrato (Aba 2-Totais)", type=['xlsx', 'xls'], key="up_extrato")
        arquivo_razao = st.file_uploader("Razão (Aba 3-Lançamentos)", type=['xlsx', 'xls'], key="up_razao")
        
        st.markdown("---")
        st.header("📅 2. Filtro de Período")
        
        data_min_global = datetime.now() - timedelta(days=365)
        data_max_global = datetime.now()
        
        if 'df_unificado' in st.session_state and not st.session_state['df_unificado'].empty:
            df_temp = st.session_state['df_unificado']
            if 'DATA' in df_temp.columns and not df_temp['DATA'].isna().all():
                datas_validas = pd.to_datetime(df_temp['DATA'], errors='coerce').dropna()
                if not datas_validas.empty:
                    data_min_global = datas_validas.min().to_pydatetime()
                    data_max_global = datas_validas.max().to_pydatetime()
        
        delta = (data_max_global - data_min_global).days
        if delta > 2:
            default_start = data_max_global - timedelta(days=2)
            default_end = data_max_global
        else:
            default_start = data_min_global
            default_end = data_max_global

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            data_ini = st.date_input("Início", value=default_start, key="d_ini")
        with col_f2:
            data_fim = st.date_input("Fim", value=default_end, key="d_fim")
            
        st.markdown("---")
        st.markdown("**Legenda:**")
        st.markdown("✅ Conciliado Automático")
        st.markdown("🧠 Sugestão (Score ≥ 60)")
        st.markdown("⚠️ Não Conciliado")
    
    # Processamento Inicial
    if arquivo_extrato and arquivo_razao:
        if 'df_unificado' not in st.session_state or st.session_state.get('processar_novamente', False):
            with st.spinner("Processando arquivos... Isso pode levar alguns segundos."):
                df_extrato, _ = processar_arquivo_excel(arquivo_extrato, "EXTRATO")
                df_razao, _ = processar_arquivo_excel(arquivo_razao, "RAZAO")
                
                if df_extrato is not None and df_razao is not None:
                    df_unificado = executar_conciliacao_unificada(df_extrato, df_razao)
                    st.session_state['df_unificado'] = df_unificado
                    st.session_state['processar_novamente'] = False
                else:
                    st.error("Erro ao processar arquivos. Verifique o formato.")
                    return

    # Main Area
    if 'df_unificado' in st.session_state:
        df_base = st.session_state['df_unificado'].copy()
        
        df_base['DATA'] = pd.to_datetime(df_base['DATA'], errors='coerce')
        
        mask = (df_base['DATA'].dt.date >= data_ini) & (df_base['DATA'].dt.date <= data_fim)
        df_filtrado_periodo = df_base.loc[mask]
        
        st.markdown(f"### 📊 Lançamentos no Período: {data_ini.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}")
        st.caption(f"Exibindo {len(df_filtrado_periodo)} registros de um total de {len(df_base)}.")
        
        col_f1, col_f2 = st.columns([1, 1])
        
        with col_f1:
            filtro_status = st.multiselect(
                "Filtrar por Status:",
                options=['Conciliado', 'Sugestão', 'Não Conciliado', 'Conciliado Manual'],
                default=['Conciliado', 'Sugestão', 'Não Conciliado', 'Conciliado Manual']
            )
        
        # REMOVIDO: Filtro por Origem (col_f2)
        # Sempre considerar os dois lados
        filtro_tipo = ['EXTRATO', 'RAZAO']
        
        df_display = df_filtrado_periodo[
            df_filtrado_periodo['STATUS'].isin(filtro_status) & 
            df_filtrado_periodo['TP'].isin(filtro_tipo)
        ].copy()
        
        df_display['DATA'] = df_display['DATA'].dt.strftime('%d/%m/%Y')
        
        df_display = df_display.fillna('')
        for col in ['ENTRADAS', 'SAIDAS', 'MOV']:
            if col in df_display.columns:
                df_display[col] = pd.to_numeric(df_display[col], errors='coerce').fillna(0.0)

        if 'SELECAO' not in df_display.columns:
            df_display['SELECAO'] = False
            
        # NOVO: Adicionado ID_SUGESTAO à ordem
        cols_ordem = ['SELECAO', 'STATUS', 'ID_CONCILIACAO', 'ID_SUGESTAO', 'TP', 'CONTA', 'DATA', 'HISTORICO', 'DOCUMENTO', 'ENTRADAS', 'SAIDAS', 'MOV']
        cols_existentes = [c for c in cols_ordem if c in df_display.columns]
        cols_existentes += [c for c in df_display.columns if c not in cols_existentes]
        
        df_editor_ready = df_display[cols_existentes]
        
        column_config = {
            "SELECAO": st.column_config.CheckboxColumn("Selecionar", default=False),
            "DATA": st.column_config.TextColumn("Data"), 
            "ENTRADAS": st.column_config.NumberColumn("Entradas", format="R$ %.2f"),
            "SAIDAS": st.column_config.NumberColumn("Saídas", format="R$ %.2f"),
            "MOV": st.column_config.NumberColumn("Movimento", format="R$ %.2f"),
            "STATUS": st.column_config.TextColumn("Status"),
            "ID_CONCILIACAO": st.column_config.TextColumn("ID Conciliação"),
            "ID_SUGESTAO": st.column_config.TextColumn("ID Sugestão"),
            "TP": st.column_config.TextColumn("Tipo"),
            "CONTA": st.column_config.TextColumn("Conta"),
            "HISTORICO": st.column_config.TextColumn("Histórico"),
            "DOCUMENTO": st.column_config.TextColumn("Documento"),
            "CHAVE": None 
        }
        
        edited_df = st.data_editor(
            df_editor_ready,
            column_config=column_config,
            use_container_width=True,
            hide_index=True,
            disabled=['DATA', 'MOV', 'STATUS', 'TP', 'ENTRADAS', 'SAIDAS', 'CHAVE', 'ID_CONCILIACAO', 'ID_SUGESTAO'], 
            key="data_editor_main"
        )
        
        # =====================================================================
        # VALIDAÇÃO E AÇÕES MANUAIS
        # =====================================================================
        
        st.markdown("---")
        st.subheader("Validação da Conciliação Manual")
        
        selecionados = edited_df[edited_df['SELECAO'] == True]
        
        sel_extrato = selecionados[selecionados['TP'] == 'EXTRATO']
        sel_razao = selecionados[selecionados['TP'] == 'RAZAO']
        
        total_entrada_extrato = sel_extrato['ENTRADAS'].sum()
        total_saida_extrato = sel_extrato['SAIDAS'].sum()
        
        total_entrada_razao = sel_razao['ENTRADAS'].sum()
        total_saida_razao = sel_razao['SAIDAS'].sum()
        
        saldo_conciliacao = (total_entrada_extrato - total_entrada_razao) + (total_saida_extrato - total_saida_razao)
        
        col_val1, col_val2, col_val3, col_val4 = st.columns([2, 1, 1, 1])
        
        with col_val1:
            st.markdown(f"### Saldo da conciliação: **{formatar_valor_para_exibicao(saldo_conciliacao)}**")
            if len(selecionados) > 0 and saldo_conciliacao != 0:
                st.error("A soma dos lançamentos deve ser zero para conciliar")
        
        with col_val2:
            btn_conciliar = st.button("✅ Conciliar Selecionados", type="primary", use_container_width=True)
        
        with col_val3:
            btn_desfazer = st.button("↩️ Desfazer Seleção", use_container_width=True)
            
        # NOVO: Botão Inverter Seleção
        with col_val4:
            btn_inverter = st.button("🔃 Inverter Seleção", use_container_width=True)

        # Lógica dos botões
        if btn_conciliar:
            if len(selecionados) < 2:
                st.warning("Selecione pelo menos 2 linhas.")
            else:
                tipos_sel = selecionados['TP'].unique()
                if 'EXTRATO' not in tipos_sel or 'RAZAO' not in tipos_sel:
                    st.warning("Selecione pelo menos 1 item do EXTRATO e 1 do RAZÃO.")
                else:
                    if saldo_conciliacao != 0:
                        st.error("A soma dos lançamentos deve ser zero para conciliar")
                    else:
                        indices_para_atualizar = selecionados.index
                        
                        ids_existentes = st.session_state['df_unificado']['ID_CONCILIACAO'].dropna()
                        max_id_num = 0
                        for id_val in ids_existentes:
                            if str(id_val).startswith('CONC_'):
                                try:
                                    num = int(str(id_val).split('_')[1])
                                    if num > max_id_num: max_id_num = num
                                except: pass
                        
                        novo_id_manual = f"CONC_{max_id_num + 1}"
                        
                        st.session_state['df_unificado'].loc[indices_para_atualizar, 'STATUS'] = 'Conciliado Manual'
                        st.session_state['df_unificado'].loc[indices_para_atualizar, 'ID_CONCILIACAO'] = novo_id_manual
                        st.session_state['df_unificado'].loc[indices_para_atualizar, 'SELECAO'] = False
                        
                        st.success(f"{len(selecionados)} itens conciliados manualmente com ID {novo_id_manual}!")
                        st.rerun()

        if btn_desfazer:
            if len(selecionados) > 0:
                indices_para_atualizar = selecionados.index
                st.session_state['df_unificado'].loc[indices_para_atualizar, 'STATUS'] = 'Não Conciliado'
                st.session_state['df_unificado'].loc[indices_para_atualizar, 'ID_CONCILIACAO'] = None
                st.success("Status alterado para 'Não Conciliado'.")
                st.rerun()
        
        # NOVO: Lógica Inverter Seleção
        if btn_inverter:
            # O edited_df reflete o estado atual do grid (filtrado)
            indices_visiveis = edited_df.index
            
            # Inverte a lógica: True vira False, False vira True
            # Importante: pegar o estado ATUAL do edited_df
            current_selection = edited_df['SELECAO']
            inverted_selection = ~current_selection
            
            # Atualizar o dataframe global apenas nos indices visiveis
            st.session_state['df_unificado'].loc[indices_visiveis, 'SELECAO'] = inverted_selection
            st.rerun()
        
        # =====================================================================
        # NOVO: INFORMAÇÕES NA PARTE INFERIOR (FILTRADO)
        # =====================================================================
        
        st.markdown("---")
        st.subheader("📊 Totais da Tela Atual (Filtrados)")
        
        # Cálculos baseados no df_display (que reflete os filtros aplicados)
        total_deb_razao = df_display[df_display['TP'] == 'RAZAO']['ENTRADAS'].sum()
        total_cred_razao = df_display[df_display['TP'] == 'RAZAO']['SAIDAS'].sum()
        
        total_deb_extrato = df_display[df_display['TP'] == 'EXTRATO']['ENTRADAS'].sum()
        total_cred_extrato = df_display[df_display['TP'] == 'EXTRATO']['SAIDAS'].sum()
        
        t_col1, t_col2 = st.columns(2)
        
        with t_col1:
            st.markdown("**RAZÃO**")
            st.metric("Soma Débitos Razão", formatar_valor_para_exibicao(total_deb_razao))
            st.metric("Soma Créditos Razão", formatar_valor_para_exibicao(total_cred_razao))
            
        with t_col2:
            st.markdown("**EXTRATO**")
            st.metric("Soma Débitos Financeiro", formatar_valor_para_exibicao(total_deb_extrato))
            st.metric("Soma Créditos Financeiro", formatar_valor_para_exibicao(total_cred_extrato))

        # Resumo Geral
        st.markdown("---")
        st.markdown("### 📈 Resumo Geral (Período Inteiro)")
        df_resumo = st.session_state['df_unificado']
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Conciliado", f"{len(df_resumo[df_resumo['STATUS'].isin(['Conciliado', 'Conciliado Manual'])])}")
        c2.metric("Sugestões", f"{len(df_resumo[df_resumo['STATUS'] == 'Sugestão'])}")
        c3.metric("Pendentes", f"{len(df_resumo[df_resumo['STATUS'] == 'Não Conciliado'])}")
        
        # Exportação
        st.markdown("---")
        if st.button("📥 Exportar Excel (Dados Completos)"):
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