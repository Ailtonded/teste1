# app.py - Versão Corrigida com Tratamento de Erros
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
        
        # Verifica se não é uma linha de título
        valores_linha = [v for v in row.values if pd.notna(v) and isinstance(v, str)]
        eh_titulo = any(v.upper().strip() in ['TOTAIS', 'LANÇAMENTOS CONTÁBEIS', 'EXTRATO', 'RAZÃO', 'PARAMETROS'] 
                       for v in valores_linha)
        
        if tem_todas and not eh_titulo and len(valores_linha) > 1:
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
    
    try:
        # Passo 1: Encontrar linha de cabeçalho
        linha_cabecalho, colunas_nomeadas = encontrar_linha_cabecalho_inteligente(df, palavras_chave_obrigatorias)
        
        if linha_cabecalho is None:
            st.error(f"❌ Não foi possível encontrar o cabeçalho no arquivo de {tipo_arquivo}")
            return None
        
        # Passo 2: Extrair dados a partir da linha após o cabeçalho
        df_limpo = []
        start_row = linha_cabecalho + 1
        
        for idx in range(start_row, min(start_row + 10000, len(df))):  # Limitar para performance
            row = df.iloc[idx]
            # Pula linhas vazias ou com apenas um valor não numérico
            valores_validos = [v for v in row.values if pd.notna(v) and str(v).strip()]
            
            # Linha de formatação: tem poucos valores e o primeiro é texto
            if len(valores_validos) == 1 and isinstance(row.iloc[0], str) and not re.search(r'\d', row.iloc[0]):
                continue
            
            # Linha válida - mantém
            if len(valores_validos) > 0:
                df_limpo.append(row.values[:len(colunas_nomeadas)])
        
        if not df_limpo:
            st.warning(f"⚠️ Nenhum dado encontrado após o cabeçalho em {tipo_arquivo}")
            return None
        
        # Criar novo DataFrame
        df_normalizado = pd.DataFrame(df_limpo, columns=colunas_nomeadas[:len(df_limpo[0])])
        
        # Passo 3: Renomear colunas para padrão
        df_normalizado.columns = [str(col).strip().upper().replace(' ', '_') for col in df_normalizado.columns]
        
        # Passo 4: Detectar colunas por palavras-chave
        coluna_data = None
        coluna_entrada = None
        coluna_saida = None
        
        for col in df_normalizado.columns:
            col_upper = col.upper()
            if 'DATA' in col_upper or 'DT_' in col_upper:
                coluna_data = col
            elif 'ENTRADA' in col_upper or 'DEBITO' in col_upper or 'DÉBITO' in col_upper:
                if coluna_entrada is None:
                    coluna_entrada = col
            elif 'SAIDA' in col_upper or 'CREDITO' in col_upper or 'CRÉDITO' in col_upper:
                if coluna_saida is None:
                    coluna_saida = col
        
        # Para razão que tem DÉBITO e CRÉDITO separados
        if 'DEBITO' in df_normalizado.columns and 'CREDITO' in df_normalizado.columns:
            coluna_entrada = 'DEBITO'
            coluna_saida = 'CREDITO'
        
        # Validar se encontrou DATA
        if coluna_data is None:
            st.error(f"❌ Coluna DATA não encontrada em {tipo_arquivo}")
            st.write(f"Colunas disponíveis: {list(df_normalizado.columns)}")
            return None
        
        # Passo 5: Padronizar colunas
        df_normalizado = df_normalizado.rename(columns={coluna_data: 'DATA'})
        
        if coluna_entrada:
            df_normalizado = df_normalizado.rename(columns={coluna_entrada: 'ENTRADAS'})
        else:
            df_normalizado['ENTRADAS'] = 0
            
        if coluna_saida:
            df_normalizado = df_normalizado.rename(columns={coluna_saida: 'SAIDAS'})
        else:
            df_normalizado['SAIDAS'] = 0
        
        # Passo 6: Converter tipos
        def converter_valor(valor):
            if pd.isna(valor):
                return 0.0
            if isinstance(valor, (int, float)):
                return float(valor)
            if isinstance(valor, str):
                # Remove espaços e substitui vírgula por ponto
                valor = valor.strip().replace('.', '').replace(',', '.')
                # Remove caracteres não numéricos exceto ponto e sinal negativo
                valor = re.sub(r'[^\d.-]', '', valor)
                try:
                    return float(valor) if valor else 0.0
                except:
                    return 0.0
            return 0.0
        
        # Converter DATA
        try:
            df_normalizado['DATA'] = pd.to_datetime(df_normalizado['DATA'], errors='coerce', dayfirst=True)
        except:
            try:
                df_normalizado['DATA'] = pd.to_datetime(df_normalizado['DATA'], errors='coerce')
            except:
                df_normalizado['DATA'] = pd.NaT
        
        # Converter ENTRADAS e SAIDAS
        df_normalizado['ENTRADAS'] = df_normalizado['ENTRADAS'].apply(converter_valor)
        df_normalizado['SAIDAS'] = df_normalizado['SAIDAS'].apply(converter_valor)
        
        # Remover linhas sem DATA válida
        df_normalizado = df_normalizado.dropna(subset=['DATA']).reset_index(drop=True)
        
        if df_normalizado.empty:
            st.warning(f"⚠️ Nenhuma data válida encontrada em {tipo_arquivo}")
            return None
        
        # Passo 7: Criar MOV
        df_normalizado['MOV'] = df_normalizado['ENTRADAS'] - df_normalizado['SAIDAS']
        
        # Passo 8: Criar chave de conciliação
        df_normalizado['CHAVE'] = df_normalizado['DATA'].dt.strftime('%Y-%m-%d') + '_' + df_normalizado['MOV'].round(2).astype(str)
        
        # Passo 9: Adicionar origem
        df_normalizado['TP'] = tipo_arquivo
        
        return df_normalizado
        
    except Exception as e:
        st.error(f"❌ Erro ao processar {tipo_arquivo}: {str(e)}")
        return None

# ============================================================================
# FUNÇÕES DE CARREGAMENTO
# ============================================================================

def carregar_extrato(uploaded_file):
    """
    Carrega o extrato da aba '2-Totais'
    """
    if uploaded_file is None:
        return None
    
    try:
        # Primeiro, verificar abas disponíveis
        xl = pd.ExcelFile(uploaded_file)
        
        # Tentar encontrar a aba correta
        aba_correta = None
        for sheet in xl.sheet_names:
            if '2' in sheet or 'Totais' in sheet or 'EXTRATO' in sheet.upper():
                aba_correta = sheet
                break
        
        if aba_correta is None:
            aba_correta = xl.sheet_names[0]
        
        st.info(f"📑 Carregando Extrato da aba: {aba_correta}")
        
        # Carregar a aba
        df = pd.read_excel(uploaded_file, sheet_name=aba_correta, header=None, dtype=str)
        return limpar_e_normalizar_dataframe(df, "EXTRATO", ['DATA'])
        
    except Exception as e:
        st.error(f"❌ Erro ao carregar Extrato: {str(e)}")
        return None

def carregar_razao(uploaded_file):
    """
    Carrega o razão da aba '3-Lançamentos Contábeis'
    """
    if uploaded_file is None:
        return None
    
    try:
        # Primeiro, verificar abas disponíveis
        xl = pd.ExcelFile(uploaded_file)
        
        # Tentar encontrar a aba correta
        aba_correta = None
        for sheet in xl.sheet_names:
            if '3' in sheet or 'Lançamentos' in sheet or 'RAZAO' in sheet.upper():
                aba_correta = sheet
                break
        
        if aba_correta is None:
            aba_correta = xl.sheet_names[0]
        
        st.info(f"📑 Carregando Razão da aba: {aba_correta}")
        
        # Carregar a aba
        df = pd.read_excel(uploaded_file, sheet_name=aba_correta, header=None, dtype=str)
        return limpar_e_normalizar_dataframe(df, "RAZAO", ['DATA'])
        
    except Exception as e:
        st.error(f"❌ Erro ao carregar Razão: {str(e)}")
        return None

# ============================================================================
# FUNÇÕES DE CONCILIAÇÃO
# ============================================================================

def conciliar_exato(df_extrato, df_razao):
    """
    Conciliação exata baseada na chave (DATA + MOV)
    Retorna sempre 4 valores (conciliados, extrato_nao, razao_nao, erro)
    """
    # Validação inicial
    if df_extrato is None or df_razao is None:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), "Dados não carregados"
    
    if df_extrato.empty or df_razao.empty:
        return pd.DataFrame(), df_extrato if df_extrato is not None else pd.DataFrame(), df_razao if df_razao is not None else pd.DataFrame(), None
    
    try:
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
            if not df.empty:
                if '_contador' in df.columns:
                    df.drop(columns=['_contador'], inplace=True)
                if 'CHAVE_UNICA' in df.columns:
                    df.drop(columns=['CHAVE_UNICA'], inplace=True)
        
        return conciliados, extrato_nao, razao_nao, None
        
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), str(e)

def sugerir_conciliacoes(df_extrato_nao, df_razao_nao):
    """
    Sugere conciliações baseadas em score
    """
    if df_extrato_nao is None or df_razao_nao is None:
        return pd.DataFrame()
    
    if df_extrato_nao.empty or df_razao_nao.empty:
        return pd.DataFrame()
    
    sugestoes = []
    
    try:
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
                        'DATA_EXTRATO': data_extrato.strftime('%Y-%m-%d'),
                        'MOV_EXTRATO': round(mov_extrato, 2),
                        'DATA_RAZAO': data_razao.strftime('%Y-%m-%d'),
                        'MOV_RAZAO': round(mov_razao, 2),
                        'SCORE': score,
                        'DIF_VALOR': round(diff_valor, 2),
                        'DIF_DIAS': diff_dias
                    })
        
        if sugestoes:
            df_sugestoes = pd.DataFrame(sugestoes)
            df_sugestoes = df_sugestoes.sort_values('SCORE', ascending=False)
            # Remover duplicatas
            df_sugestoes = df_sugestoes.drop_duplicates(subset=['DATA_EXTRATO', 'MOV_EXTRATO'], keep='first')
            return df_sugestoes
        
    except Exception as e:
        st.warning(f"Erro ao gerar sugestões: {str(e)}")
    
    return pd.DataFrame()

# ============================================================================
# INTERFACE STREAMLIT
# ============================================================================

def main():
    st.title("📊 Sistema de Conciliação Contábil")
    st.markdown("---")
    
    # Inicializar session state
    if 'processado' not in st.session_state:
        st.session_state['processado'] = False
        st.session_state['conciliados'] = pd.DataFrame()
        st.session_state['sugestoes'] = pd.DataFrame()
        st.session_state['extrato_nao'] = pd.DataFrame()
        st.session_state['razao_nao'] = pd.DataFrame()
    
    # Sidebar
    with st.sidebar:
        st.header("📁 Upload")
        
        extrato_file = st.file_uploader(
            "📄 Extrato Bancário",
            type=['xlsx', 'xls'],
            key="extrato"
        )
        
        razao_file = st.file_uploader(
            "📒 Razão Contábil",
            type=['xlsx', 'xls'],
            key="razao"
        )
        
        st.markdown("---")
        st.header("📅 Período")
        
        col1, col2 = st.columns(2)
        with col1:
            data_inicio = st.date_input("Data Inicial", datetime(2026, 4, 1))
        with col2:
            data_fim = st.date_input("Data Final", datetime(2026, 5, 1))
        
        st.markdown("---")
        processar = st.button("🚀 Conciliar", type="primary", use_container_width=True)
    
    # Processamento
    if processar:
        if not extrato_file or not razao_file:
            st.warning("⚠️ Por favor, faça upload dos dois arquivos")
        else:
            with st.spinner("🔄 Processando arquivos..."):
                # Carregar dados
                df_extrato = carregar_extrato(extrato_file)
                df_razao = carregar_razao(razao_file)
                
                if df_extrato is not None and df_razao is not None:
                    # Mostrar informações básicas
                    st.success(f"✅ Extrato carregado: {len(df_extrato)} registros")
                    st.success(f"✅ Razão carregado: {len(df_razao)} registros")
                    
                    # Filtrar por período
                    df_extrato = df_extrato[(df_extrato['DATA'] >= pd.Timestamp(data_inicio)) & 
                                           (df_extrato['DATA'] <= pd.Timestamp(data_fim))]
                    df_razao = df_razao[(df_razao['DATA'] >= pd.Timestamp(data_inicio)) & 
                                       (df_razao['DATA'] <= pd.Timestamp(data_fim))]
                    
                    st.info(f"📅 Período filtrado: Extrato {len(df_extrato)} | Razão {len(df_razao)}")
                    
                    # Conciliação
                    conciliados, extrato_nao, razao_nao, erro = conciliar_exato(df_extrato, df_razao)
                    
                    if erro:
                        st.error(f"Erro na conciliação: {erro}")
                    else:
                        sugestoes = sugerir_conciliacoes(extrato_nao, razao_nao)
                        
                        # Salvar na sessão
                        st.session_state['conciliados'] = conciliados
                        st.session_state['sugestoes'] = sugestoes
                        st.session_state['extrato_nao'] = extrato_nao
                        st.session_state['razao_nao'] = razao_nao
                        st.session_state['df_extrato'] = df_extrato
                        st.session_state['df_razao'] = df_razao
                        st.session_state['processado'] = True
                        
                        st.success(f"✅ Conciliação concluída! {len(conciliados)} itens conciliados")
                else:
                    if df_extrato is None:
                        st.error("❌ Falha ao carregar o arquivo de Extrato")
                    if df_razao is None:
                        st.error("❌ Falha ao carregar o arquivo de Razão")
    
    # Exibir resultados
    if st.session_state['processado']:
        conciliados = st.session_state.get('conciliados', pd.DataFrame())
        sugestoes = st.session_state.get('sugestoes', pd.DataFrame())
        extrato_nao = st.session_state.get('extrato_nao', pd.DataFrame())
        razao_nao = st.session_state.get('razao_nao', pd.DataFrame())
        df_extrato = st.session_state.get('df_extrato', pd.DataFrame())
        df_razao = st.session_state.get('df_razao', pd.DataFrame())
        
        # Abas
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "✅ Conciliados", "🧠 Sugestões", "⚠️ Extrato Não Conc.", 
            "⚠️ Razão Não Conc.", "📊 Resumo"
        ])
        
        with tab1:
            st.subheader("Lançamentos Conciliados")
            if not conciliados.empty:
                # Selecionar colunas para exibição
                colunas_exibir = [c for c in ['DATA_EXTRATO', 'MOV_EXTRATO', 'DATA_RAZAO', 'MOV_RAZAO'] 
                                if c in conciliados.columns]
                st.dataframe(conciliados[colunas_exibir], use_container_width=True)
                st.metric("Total de itens conciliados", len(conciliados))
            else:
                st.info("Nenhum lançamento conciliado encontrado")
        
        with tab2:
            st.subheader("Sugestões de Conciliação")
            if not sugestoes.empty:
                st.dataframe(sugestoes, use_container_width=True)
                st.info(f"🧠 Encontradas {len(sugestoes)} sugestões")
            else:
                st.success("✅ Nenhuma sugestão pendente")
        
        with tab3:
            st.subheader("Extrato não conciliado")
            if not extrato_nao.empty:
                st.dataframe(extrato_nao[['DATA', 'MOV']], use_container_width=True)
                st.warning(f"⚠️ {len(extrato_nao)} lançamentos não conciliados")
                st.metric("Valor total", f"R$ {extrato_nao['MOV'].sum():,.2f}")
            else:
                st.success("✅ Todos os lançamentos do extrato foram conciliados!")
        
        with tab4:
            st.subheader("Razão não conciliado")
            if not razao_nao.empty:
                st.dataframe(razao_nao[['DATA', 'MOV']], use_container_width=True)
                st.warning(f"⚠️ {len(razao_nao)} lançamentos não conciliados")
                st.metric("Valor total", f"R$ {razao_nao['MOV'].sum():,.2f}")
            else:
                st.success("✅ Todos os lançamentos do razão foram conciliados!")
        
        with tab5:
            st.subheader("Resumo da Conciliação")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_extrato = df_extrato['MOV'].sum() if not df_extrato.empty else 0
                st.metric("💰 Total Extrato", f"R$ {total_extrato:,.2f}")
            
            with col2:
                total_razao = df_razao['MOV'].sum() if not df_razao.empty else 0
                st.metric("📚 Total Razão", f"R$ {total_razao:,.2f}")
            
            with col3:
                total_conciliado = conciliados['MOV_EXTRATO'].sum() if not conciliados.empty else 0
                st.metric("✅ Total Conciliado", f"R$ {total_conciliado:,.2f}")
            
            with col4:
                diferenca = total_extrato - total_razao
                st.metric(
                    "📊 Diferença",
                    f"R$ {diferenca:,.2f}",
                    delta=f"{diferenca:,.2f}" if diferenca != 0 else None
                )
            
            # Métricas adicionais
            st.markdown("---")
            if not df_extrato.empty:
                taxa = (len(conciliados) / len(df_extrato)) * 100
                st.progress(taxa / 100)
                st.caption(f"Taxa de conciliação: {taxa:.1f}% ({len(conciliados)} de {len(df_extrato)})")

if __name__ == "__main__":
    main()