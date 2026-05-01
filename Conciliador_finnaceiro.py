"""
Sistema de Conciliação Contábil - versão Enterprise
Autor: Desenvolvedor Sênior Python
Descrição: Conciliação automática entre Extrato Bancário e Razão Contábil
Adaptado para layouts específicos: aba "2-Totais" (Extrato) e "3-Lançamentos Contábeis" (Razão)
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
    page_title="Conciliação Contábil",
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

# Palavras-chave para detecção de colunas
# IMPORTANTE: No Razão de banco, CRÉDITO = Entrada e DÉBITO = Saída
KEYWORDS = {
    'data': ['DATA', 'DT', 'DTPAG', 'DT_MOV', 'MOVIMENTACAO', 'EMISSAO'],
    'entrada': ['ENTRADA', 'CREDITO', 'CREDITOS', 'VR_ENTRADA', 'RECEITA', 'ENTRADAS'],
    'saida': ['SAIDA', 'DEBITO', 'DEBITOS', 'VR_SAIDA', 'DESPESA', 'SAIDAS'],
    'documento': ['DOCUMENTO', 'DOC', 'NUMDOC', 'NUM_DOC', 'NR_DOC', 'NUMERO', 'LOTE'],
    'historico': ['HISTORICO', 'HIST', 'DESCRICAO', 'DESC', 'OBSERVACAO', 'OBS', 'COMPLEMENTO', 'OPERACAO']
}

# Nomes esperados das abas
ABAS_ESPERADAS = {
    'EXTRATO': ['2-Totais', 'Totais', '2 - Totais', 'EXTRATO', 'MOVIMENTO'],
    'RAZAO': ['3-Lançamentos Contábeis', '3-Lancamentos Contabeis', 'Lançamentos Contábeis', 
              'Lancamentos Contabeis', '3-Lançamentos', '3-Lancamentos', 'RAZAO', 'LANCAMENTOS']
}

# ============================================================================
# FUNÇÕES UTILITÁRIAS
# ============================================================================

def normalizar_texto(texto: str) -> str:
    """
    Normaliza texto removendo acentos e caracteres especiais.
    """
    if pd.isna(texto):
        return ""
    
    texto = str(texto).upper().strip()
    
    # Mapeamento de acentos
    mapeamento = {
        'Á': 'A', 'À': 'A', 'Ã': 'A', 'Â': 'A', 'Ä': 'A',
        'É': 'E', 'È': 'E', 'Ê': 'E', 'Ë': 'E',
        'Í': 'I', 'Ì': 'I', 'Î': 'I', 'Ï': 'I',
        'Ó': 'O', 'Ò': 'O', 'Õ': 'O', 'Ô': 'O', 'Ö': 'O',
        'Ú': 'U', 'Ù': 'U', 'Û': 'U', 'Ü': 'U',
        'Ç': 'C', 'Ñ': 'N'
    }
    
    for acento, sem_acento in mapeamento.items():
        texto = texto.replace(acento, sem_acento)
    
    return texto


def normalizar_nome_coluna(coluna: str) -> str:
    """
    Normaliza o nome da coluna: uppercase, remove acentos, espaços viram underscore.
    """
    if pd.isna(coluna):
        return "COLUNA_VAZIA"
    
    coluna = normalizar_texto(str(coluna))
    
    # Substituir espaços e caracteres especiais por underscore
    coluna = re.sub(r'[^A-Z0-9]', '_', coluna)
    
    # Remover underscores duplicados
    coluna = re.sub(r'_+', '_', coluna)
    
    # Remover underscores no início e fim
    coluna = coluna.strip('_')
    
    return coluna if coluna else "COLUNA_SEM_NOME"


def encontrar_aba_correta(xls_file, tipo: str) -> Optional[str]:
    """
    Encontra a aba correta no arquivo Excel baseado no tipo (EXTRATO ou RAZAO).
    """
    abas_disponiveis = xls_file.sheet_names
    abas_esperadas = ABAS_ESPERADAS.get(tipo, [])
    
    # Normalizar nomes das abas disponíveis para comparação
    abas_normalizadas = {normalizar_texto(aba): aba for aba in abas_disponiveis}
    
    for aba_esperada in abas_esperadas:
        aba_norm = normalizar_texto(aba_esperada)
        
        # Busca exata
        if aba_norm in abas_normalizadas:
            return abas_normalizadas[aba_norm]
        
        # Busca parcial (contém o termo)
        for aba_disp_norm, aba_original in abas_normalizadas.items():
            if aba_norm in aba_disp_norm or aba_disp_norm in aba_norm:
                return aba_original
    
    return None


def detectar_linha_cabecalho(df: pd.DataFrame) -> Optional[int]:
    """
    Detecta automaticamente a linha que contém o cabeçalho da tabela.
    Procura por palavras-chave como 'DATA', 'VALOR', etc.
    """
    keywords_cabecalho = ['DATA', 'VALOR', 'ENTRADA', 'SAIDA', 'DEBITO', 'CREDITO', 'MOV', 'CONTA']
    
    for idx, row in df.iterrows():
        # Converter todos os valores da linha para string e uppercase
        valores = [str(v).upper() for v in row.values if pd.notna(v)]
        
        # Contar quantas keywords existem nesta linha
        matches = sum(1 for v in valores for kw in keywords_cabecalho if kw in v)
        
        # Se encontrou pelo menos 2 keywords, provavelmente é o cabeçalho
        if matches >= 2:
            return idx
    
    return None


def detectar_coluna(df: pd.DataFrame, tipo: str) -> Optional[str]:
    """
    Detecta a coluna correspondente ao tipo informado usando palavras-chave.
    """
    if tipo not in KEYWORDS:
        return None
    
    keywords = KEYWORDS[tipo]
    colunas_normalizadas = {col: normalizar_nome_coluna(col) for col in df.columns}
    
    for col_original, col_normalizada in colunas_normalizadas.items():
        for keyword in keywords:
            if keyword in col_normalizada:
                return col_original
    
    return None


def converter_valor_monetario(valor) -> float:
    """
    Converte um valor monetário para float, lidando com diferentes formatos.
    Suporta valores entre parênteses como negativos (padrão contábil).
    """
    if pd.isna(valor):
        return 0.0
    
    if isinstance(valor, (int, float)):
        return float(valor)
    
    # Converter para string
    valor_str = str(valor).strip()
    
    # Verificar se é valor negativo (entre parênteses)
    is_negativo = valor_str.startswith('(') and valor_str.endswith(')')
    
    # Remover parênteses, símbolos monetários e espaços
    valor_str = re.sub(r'[R$\s\(\)]', '', valor_str)
    
    # Tratar diferentes formatos de separador decimal
    if ',' in valor_str and '.' in valor_str:
        # Formato brasileiro: 1.000,50 -> 1000.50
        valor_str = valor_str.replace('.', '').replace(',', '.')
    elif ',' in valor_str:
        # Apenas vírgula como separador decimal
        valor_str = valor_str.replace(',', '.')
    
    # Tentar converter
    try:
        resultado = float(valor_str)
        return -resultado if is_negativo else resultado
    except ValueError:
        return 0.0


def processar_arquivo_excel(uploaded_file, nome_tipo: str) -> Tuple[Optional[pd.DataFrame], List[str]]:
    """
    Processa um arquivo Excel, detectando aba correta, cabeçalho e normalizando dados.
    """
    logs = []
    
    try:
        # Abrir o arquivo para ler as abas
        xls_file = pd.ExcelFile(uploaded_file)
        logs.append(f"📁 {nome_tipo}: Arquivo carregado com {len(xls_file.sheet_names)} aba(s)")
        logs.append(f"📋 {nome_tipo}: Abas disponíveis: {', '.join(xls_file.sheet_names)}")
        
        # Encontrar a aba correta
        aba_correta = encontrar_aba_correta(xls_file, nome_tipo)
        
        if aba_correta is None:
            # Se não encontrou, tentar usar a primeira aba
            aba_correta = xls_file.sheet_names[0]
            logs.append(f"⚠️ {nome_tipo}: Aba específica não encontrada, usando: '{aba_correta}'")
        else:
            logs.append(f"✅ {nome_tipo}: Aba '{aba_correta}' selecionada")
        
        # Ler a aba selecionada sem assumir cabeçalho
        uploaded_file.seek(0)
        df_raw = pd.read_excel(uploaded_file, sheet_name=aba_correta, header=None, dtype=str)
        logs.append(f"📊 {nome_tipo}: {len(df_raw)} linhas lidas")
        
        # Detectar linha do cabeçalho
        linha_cabecalho = detectar_linha_cabecalho(df_raw)
        
        if linha_cabecalho is None:
            logs.append(f"❌ {nome_tipo}: Não foi possível detectar o cabeçalho automaticamente")
            return None, logs
        
        logs.append(f"✅ {nome_tipo}: Cabeçalho detectado na linha {linha_cabecalho + 1}")
        
        # Reler o arquivo com o cabeçalho correto
        uploaded_file.seek(0)
        df = pd.read_excel(uploaded_file, sheet_name=aba_correta, header=linha_cabecalho)
        
        # Remover colunas sem nome
        df = df.loc[:, ~df.columns.astype(str).str.startswith('Unnamed')]
        
        # Normalizar nomes das colunas
        df.columns = [normalizar_nome_coluna(col) for col in df.columns]
        logs.append(f"✅ {nome_tipo}: {len(df.columns)} colunas normalizadas - {list(df.columns)}")
        
        # Detectar coluna de data
        col_data = detectar_coluna(df, 'data')
        if col_data is None:
            logs.append(f"❌ {nome_tipo}: Coluna de DATA não encontrada")
            return None, logs
        
        df = df.rename(columns={col_data: 'DATA'})
        logs.append(f"✅ {nome_tipo}: Coluna '{col_data}' → 'DATA'")
        
        # Detectar colunas de entrada e saída
        col_entrada = detectar_coluna(df, 'entrada')
        col_saida = detectar_coluna(df, 'saida')
        
        # Mapear colunas detectadas
        if col_entrada:
            df = df.rename(columns={col_entrada: 'ENTRADAS'})
            logs.append(f"✅ {nome_tipo}: Coluna '{col_entrada}' → 'ENTRADAS'")
        else:
            df['ENTRADAS'] = 0.0
            logs.append(f"⚠️ {nome_tipo}: Coluna de ENTRADAS não detectada, criada com valor 0")
        
        if col_saida:
            df = df.rename(columns={col_saida: 'SAIDAS'})
            logs.append(f"✅ {nome_tipo}: Coluna '{col_saida}' → 'SAIDAS'")
        else:
            df['SAIDAS'] = 0.0
            logs.append(f"⚠️ {nome_tipo}: Coluna de SAIDAS não detectada, criada com valor 0")
        
        # Detectar coluna de histórico
        col_hist = detectar_coluna(df, 'historico')
        if col_hist:
            df = df.rename(columns={col_hist: 'HISTORICO'})
            logs.append(f"✅ {nome_tipo}: Coluna '{col_hist}' → 'HISTORICO'")
        else:
            df['HISTORICO'] = ''
        
        # Detectar coluna de documento
        col_doc = detectar_coluna(df, 'documento')
        if col_doc:
            df = df.rename(columns={col_doc: 'DOCUMENTO'})
            logs.append(f"✅ {nome_tipo}: Coluna '{col_doc}' → 'DOCUMENTO'")
        else:
            df['DOCUMENTO'] = ''
        
        # Converter DATA para datetime
        df['DATA'] = pd.to_datetime(df['DATA'], errors='coerce', dayfirst=True)
        
        # Remover linhas com data inválida
        linhas_antes = len(df)
        df = df.dropna(subset=['DATA'])
        linhas_depois = len(df)
        
        if linhas_antes != linhas_depois:
            logs.append(f"⚠️ {nome_tipo}: {linhas_antes - linhas_depois} linhas removidas por data inválida")
        
        # Converter valores monetários
        df['ENTRADAS'] = df['ENTRADAS'].apply(converter_valor_monetario)
        df['SAIDAS'] = df['SAIDAS'].apply(converter_valor_monetario)
        
        # Preencher NaN com 0
        df['ENTRADAS'] = df['ENTRADAS'].fillna(0)
        df['SAIDAS'] = df['SAIDAS'].fillna(0)
        
        # Criar coluna MOV (movimento líquido)
        df['MOV'] = df['ENTRADAS'] - df['SAIDAS']
        df['MOV'] = df['MOV'].round(CONFIG['casas_decimais'])
        
        # Identificar origem
        df['TP'] = nome_tipo
        
        # Criar chave de conciliação
        df['CHAVE'] = df['DATA'].dt.strftime('%Y-%m-%d') + '_' + df['MOV'].round(2).astype(str)
        
        # Remover linhas com MOV = 0 (sem movimento)
        mov_antes = len(df)
        df = df[df['MOV'] != 0]
        mov_depois = len(df)
        
        if mov_antes != mov_depois:
            logs.append(f"ℹ️ {nome_tipo}: {mov_antes - mov_depois} linhas sem movimento removidas")
        
        logs.append(f"✅ {nome_tipo}: Processamento concluído com {len(df)} registros válidos")
        
        # Log de totais
        total_entradas = df['ENTRADAS'].sum()
        total_saidas = df['SAIDAS'].sum()
        logs.append(f"💰 {nome_tipo}: Total Entradas: {formatar_valor_para_exibicao(total_entradas)}")
        logs.append(f"💰 {nome_tipo}: Total Saídas: {formatar_valor_para_exibicao(total_saidas)}")
        logs.append(f"💰 {nome_tipo}: Saldo Líquido: {formatar_valor_para_exibicao(total_entradas - total_saidas)}")
        
        return df, logs
        
    except Exception as e:
        logs.append(f"❌ {nome_tipo}: Erro no processamento - {str(e)}")
        import traceback
        logs.append(f"🔍 Detalhes: {traceback.format_exc()}")
        return None, logs


def conciliar_dados(df_extrato: pd.DataFrame, df_razao: pd.DataFrame) -> Dict:
    """
    Realiza a conciliação automática entre extrato e razão.
    Retorna um dicionário com os DataFrames de resultados.
    """
    resultados = {}
    
    # Marcar quais registros já foram conciliados
    df_extrato = df_extrato.copy()
    df_razao = df_razao.copy()
    df_extrato['CONCILIADO'] = False
    df_razao['CONCILIADO'] = False
    
    # Contar ocorrências de cada chave
    contagem_extrato = df_extrato['CHAVE'].value_counts().to_dict()
    contagem_razao = df_razao['CHAVE'].value_counts().to_dict()
    
    # Encontrar chaves comuns
    chaves_extrato = set(df_extrato['CHAVE'])
    chaves_razao = set(df_razao['CHAVE'])
    chaves_comuns = chaves_extrato.intersection(chaves_razao)
    
    registros_conciliados = []
    
    for chave in chaves_comuns:
        # Quantos registros de cada lado
        qtd_extrato = contagem_extrato.get(chave, 0)
        qtd_razao = contagem_razao.get(chave, 0)
        
        # Número de matches possíveis (1 para 1)
        matches = min(qtd_extrato, qtd_razao)
        
        # Selecionar os registros
        idx_extrato = df_extrato[df_extrato['CHAVE'] == chave].index[:matches]
        idx_razao = df_razao[df_razao['CHAVE'] == chave].index[:matches]
        
        # Marcar como conciliados
        df_extrato.loc[idx_extrato, 'CONCILIADO'] = True
        df_razao.loc[idx_razao, 'CONCILIADO'] = True
        
        # Criar registros de conciliação
        for i, (idx_e, idx_r) in enumerate(zip(idx_extrato, idx_razao)):
            row_extrato = df_extrato.loc[idx_e]
            row_razao = df_razao.loc[idx_r]
            
            registro = {
                'DATA_EXTRATO': row_extrato['DATA'],
                'MOV_EXTRATO': row_extrato['MOV'],
                'HISTORICO_EXTRATO': row_extrato.get('HISTORICO', ''),
                'DOCUMENTO_EXTRATO': row_extrato.get('DOCUMENTO', ''),
                'DATA_RAZAO': row_razao['DATA'],
                'MOV_RAZAO': row_razao['MOV'],
                'HISTORICO_RAZAO': row_razao.get('HISTORICO', ''),
                'DOCUMENTO_RAZAO': row_razao.get('DOCUMENTO', ''),
                'CHAVE': chave,
                'TIPO_MATCH': 'Exato'
            }
            registros_conciliados.append(registro)
    
    resultados['conciliados'] = pd.DataFrame(registros_conciliados) if registros_conciliados else pd.DataFrame()
    resultados['extrato_nao_conciliado'] = df_extrato[~df_extrato['CONCILIADO']].copy()
    resultados['razao_nao_conciliado'] = df_razao[~df_razao['CONCILIADO']].copy()
    
    return resultados


def calcular_score_match(row_extrato: pd.Series, row_razao: pd.Series) -> int:
    """
    Calcula o score de compatibilidade entre dois registros.
    """
    score = 0
    
    # Score por valor
    valor_extrato = abs(row_extrato['MOV'])
    valor_razao = abs(row_razao['MOV'])
    diff_valor = abs(valor_extrato - valor_razao)
    
    if diff_valor == 0:
        score += CONFIG['score_valor_igual']
    elif diff_valor <= CONFIG['tolerancia_valor']:
        score += CONFIG['score_valor_proximo']
    
    # Score por data
    data_extrato = row_extrato['DATA']
    data_razao = row_razao['DATA']
    
    if pd.notna(data_extrato) and pd.notna(data_razao):
        diff_dias = abs((data_extrato - data_razao).days)
        
        if diff_dias == 0:
            score += CONFIG['score_data_igual']
        elif diff_dias <= CONFIG['tolerancia_dias']:
            score += CONFIG['score_data_proxima']
    
    return score


def gerar_sugestoes(df_extrato: pd.DataFrame, df_razao: pd.DataFrame) -> pd.DataFrame:
    """
    Gera sugestões de conciliação para registros não conciliados.
    Usa scoring para encontrar matches parciais.
    """
    sugestoes = []
    
    # Registros não conciliados
    extrato_nc = df_extrato[~df_extrato['CONCILIADO']].copy()
    razao_nc = df_razao[~df_razao['CONCILIADO']].copy()
    
    if len(extrato_nc) == 0 or len(razao_nc) == 0:
        return pd.DataFrame()
    
    # Otimização: agrupar por valor aproximado para reduzir comparações
    razao_nc['_valor_int'] = (razao_nc['MOV'].abs() * 100).round().astype(int)
    extrato_nc['_valor_int'] = (extrato_nc['MOV'].abs() * 100).round().astype(int)
    
    # Para cada registro do extrato, encontrar melhores matches
    for idx_e, row_e in extrato_nc.iterrows():
        valor_int_e = row_e['_valor_int']
        
        # Buscar valores próximos (tolerância de 5 centavos)
        candidatos_idx = razao_nc[
            (razao_nc['_valor_int'] >= valor_int_e - 5) & 
            (razao_nc['_valor_int'] <= valor_int_e + 5)
        ].index
        
        for idx_r in candidatos_idx:
            row_r = razao_nc.loc[idx_r]
            
            score = calcular_score_match(row_e, row_r)
            
            if score >= CONFIG['score_minimo_sugestao']:
                sugestao = {
                    'SCORE': score,
                    'DATA_EXTRATO': row_e['DATA'],
                    'MOV_EXTRATO': row_e['MOV'],
                    'HISTORICO_EXTRATO': row_e.get('HISTORICO', ''),
                    'DOCUMENTO_EXTRATO': row_e.get('DOCUMENTO', ''),
                    'DATA_RAZAO': row_r['DATA'],
                    'MOV_RAZAO': row_r['MOV'],
                    'HISTORICO_RAZAO': row_r.get('HISTORICO', ''),
                    'DOCUMENTO_RAZAO': row_r.get('DOCUMENTO', ''),
                    'DIFERENCA_VALOR': abs(row_e['MOV'] - row_r['MOV']),
                    'DIFERENCA_DIAS': abs((row_e['DATA'] - row_r['DATA']).days) if pd.notna(row_e['DATA']) and pd.notna(row_r['DATA']) else None
                }
                sugestoes.append(sugestao)
    
    if not sugestoes:
        return pd.DataFrame()
    
    df_sugestoes = pd.DataFrame(sugestoes)
    df_sugestoes = df_sugestoes.sort_values('SCORE', ascending=False)
    
    # Remover sugestões duplicadas para o mesmo par (manter o melhor score)
    df_sugestoes = df_sugestoes.drop_duplicates(
        subset=['DATA_EXTRATO', 'MOV_EXTRATO', 'DATA_RAZAO', 'MOV_RAZAO'],
        keep='first'
    )
    
    return df_sugestoes


def exportar_excel_resultados(resultados: Dict) -> bytes:
    """
    Exporta os resultados para um arquivo Excel com múltiplas abas.
    """
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Aba de conciliados
        if not resultados.get('conciliados', pd.DataFrame()).empty:
            resultados['conciliados'].to_excel(writer, sheet_name='Conciliados', index=False)
        else:
            pd.DataFrame({'Mensagem': ['Nenhum registro conciliado']}).to_excel(
                writer, sheet_name='Conciliados', index=False
            )
        
        # Aba de sugestões
        if not resultados.get('sugestoes', pd.DataFrame()).empty:
            resultados['sugestoes'].to_excel(writer, sheet_name='Sugestoes', index=False)
        else:
            pd.DataFrame({'Mensagem': ['Nenhuma sugestão disponível']}).to_excel(
                writer, sheet_name='Sugestoes', index=False
            )
        
        # Aba extrato não conciliado
        if not resultados.get('extrato_nao_conciliado', pd.DataFrame()).empty:
            cols_export = ['DATA', 'MOV', 'ENTRADAS', 'SAIDAS', 'HISTORICO', 'DOCUMENTO', 'CHAVE']
            cols_disponiveis = [c for c in cols_export if c in resultados['extrato_nao_conciliado'].columns]
            resultados['extrato_nao_conciliado'][cols_disponiveis].to_excel(
                writer, sheet_name='Extrato_Nao_Conciliado', index=False
            )
        else:
            pd.DataFrame({'Mensagem': ['Todos os registros do extrato foram conciliados']}).to_excel(
                writer, sheet_name='Extrato_Nao_Conciliado', index=False
            )
        
        # Aba razão não conciliado
        if not resultados.get('razao_nao_conciliado', pd.DataFrame()).empty:
            cols_export = ['DATA', 'MOV', 'ENTRADAS', 'SAIDAS', 'HISTORICO', 'DOCUMENTO', 'CHAVE']
            cols_disponiveis = [c for c in cols_export if c in resultados['razao_nao_conciliado'].columns]
            resultados['razao_nao_conciliado'][cols_disponiveis].to_excel(
                writer, sheet_name='Razao_Nao_Conciliado', index=False
            )
        else:
            pd.DataFrame({'Mensagem': ['Todos os registros do razão foram conciliados']}).to_excel(
                writer, sheet_name='Razao_Nao_Conciliado', index=False
            )
    
    output.seek(0)
    return output.getvalue()


def formatar_data_para_exibicao(data) -> str:
    """
    Formata uma data para exibição no formato brasileiro.
    """
    if pd.isna(data):
        return ""
    try:
        return data.strftime('%d/%m/%Y')
    except:
        return str(data)


def formatar_valor_para_exibicao(valor) -> str:
    """
    Formata um valor monetário para exibição.
    """
    if pd.isna(valor):
        return "R$ 0,00"
    try:
        return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except:
        return str(valor)


# ============================================================================
# INTERFACE STREAMLIT
# ============================================================================

def main():
    """
    Função principal do aplicativo Streamlit.
    """
    
    # Título principal
    st.title("🔄 Sistema de Conciliação Contábil")
    st.markdown("---")
    
    # Sidebar com instruções
    with st.sidebar:
        st.header("📋 Instruções")
        st.markdown("""
        ### Como usar:
        
        1. **Upload do Extrato**  
           Arquivo Excel do extrato bancário  
           📍 Aba esperada: `2-Totais`
        
        2. **Upload do Razão**  
           Arquivo Excel do razão contábil  
           📍 Aba esperada: `3-Lançamentos Contábeis`
        
        3. **Configurar Período**  
           Selecione o intervalo de datas
        
        4. **Processar**  
           Clique em "Realizar Conciliação"
        
        ---
        
        ### ⚠️ Sobre os arquivos:
        
        O sistema detecta automaticamente:
        - A aba correta no arquivo
        - A linha do cabeçalho
        - Colunas de data, entradas e saídas
        - Diferentes formatos de valores
        
        ---
        
        ### 📊 Mapeamento de Colunas:
        
        **Extrato (aba 2-Totais):**
        - ENTRADAS → Entradas
        - SAIDAS → Saídas
        
        **Razão (aba 3-Lançamentos):**
        - CREDITO → Entradas
        - DEBITO → Saídas
        
        ---
        
        ### 🎯 Critérios de conciliação:
        
        **Match Exato:**
        - Mesma DATA + mesmo MOV
        
        **Sugestões (Score ≥ 60):**
        - Valor igual: +50 pontos
        - Valor similar (±0,05): +30 pontos
        - Data igual: +50 pontos
        - Data próxima (±2 dias): +30 pontos
        """)
        
        st.markdown("---")
        st.caption("Desenvolvido por Especialista Python")
    
    # ============================================================================
    # SEÇÃO DE UPLOAD
    # ============================================================================
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📥 Extrato Bancário")
        st.caption("Aba esperada: `2-Totais`")
        arquivo_extrato = st.file_uploader(
            "Selecione o arquivo Excel do extrato",
            type=['xlsx', 'xls'],
            key="upload_extrato",
            help="O sistema buscará a aba '2-Totais' automaticamente"
        )
    
    with col2:
        st.subheader("📥 Razão Contábil")
        st.caption("Aba esperada: `3-Lançamentos Contábeis`")
        arquivo_razao = st.file_uploader(
            "Selecione o arquivo Excel do razão",
            type=['xlsx', 'xls'],
            key="upload_razao",
            help="O sistema buscará a aba '3-Lançamentos Contábeis' automaticamente"
        )
    
    # ============================================================================
    # PROCESSAMENTO DOS ARQUIVOS
    # ============================================================================
    
    df_extrato = None
    df_razao = None
    logs_extrato = []
    logs_razao = []
    
    # Processar extrato
    if arquivo_extrato:
        with st.spinner("Processando extrato bancário..."):
            df_extrato, logs_extrato = processar_arquivo_excel(arquivo_extrato, "EXTRATO")
    
    # Processar razão
    if arquivo_razao:
        with st.spinner("Processando razão contábil..."):
            df_razao, logs_razao = processar_arquivo_excel(arquivo_razao, "RAZAO")
    
    # Exibir logs de processamento
    if logs_extrato or logs_razao:
        with st.expander("🔧 Logs de Processamento", expanded=False):
            col_log1, col_log2 = st.columns(2)
            
            with col_log1:
                st.markdown("**EXTRATO:**")
                for log in logs_extrato:
                    if '✅' in log:
                        st.markdown(f"<span style='color:green'>{log}</span>", unsafe_allow_html=True)
                    elif '❌' in log:
                        st.markdown(f"<span style='color:red'>{log}</span>", unsafe_allow_html=True)
                    elif '⚠️' in log:
                        st.markdown(f"<span style='color:orange'>{log}</span>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"- {log}")
            
            with col_log2:
                st.markdown("**RAZÃO:**")
                for log in logs_razao:
                    if '✅' in log:
                        st.markdown(f"<span style='color:green'>{log}</span>", unsafe_allow_html=True)
                    elif '❌' in log:
                        st.markdown(f"<span style='color:red'>{log}</span>", unsafe_allow_html=True)
                    elif '⚠️' in log:
                        st.markdown(f"<span style='color:orange'>{log}</span>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"- {log}")
    
    # ============================================================================
    # FILTRO POR PERÍODO
    # ============================================================================
    
    st.markdown("---")
    st.subheader("📅 Filtro por Período")
    
    data_min = None
    data_max = None
    
    if df_extrato is not None and len(df_extrato) > 0:
        data_min = df_extrato['DATA'].min()
        data_max = df_extrato['DATA'].max()
    
    if df_razao is not None and len(df_razao) > 0:
        if data_min is None or df_razao['DATA'].min() < data_min:
            data_min = df_razao['DATA'].min()
        if data_max is None or df_razao['DATA'].max() > data_max:
            data_max = df_razao['DATA'].max()
    
    if data_min and data_max:
        col_data1, col_data2 = st.columns(2)
        
        with col_data1:
            data_inicial = st.date_input(
                "Data Inicial",
                value=data_min.date() if pd.notna(data_min) else datetime.today().date(),
                key="data_inicial"
            )
        
        with col_data2:
            data_final = st.date_input(
                "Data Final",
                value=data_max.date() if pd.notna(data_max) else datetime.today().date(),
                key="data_final"
            )
        
        # Aplicar filtro
        if df_extrato is not None:
            df_extrato = df_extrato[
                (df_extrato['DATA'] >= pd.Timestamp(data_inicial)) & 
                (df_extrato['DATA'] <= pd.Timestamp(data_final))
            ]
        
        if df_razao is not None:
            df_razao = df_razao[
                (df_razao['DATA'] >= pd.Timestamp(data_inicial)) & 
                (df_razao['DATA'] <= pd.Timestamp(data_final))
            ]
    
    # ============================================================================
    # BOTÃO DE PROCESSAMENTO
    # ============================================================================
    
    st.markdown("---")
    
    processar = st.button(
        "🔄 Realizar Conciliação",
        type="primary",
        use_container_width=True,
        disabled=(df_extrato is None or df_razao is None or len(df_extrato) == 0 or len(df_razao) == 0)
    )
    
    # ============================================================================
    # PROCESSAMENTO E RESULTADOS
    # ============================================================================
    
    if processar and df_extrato is not None and df_razao is not None:
        
        # Verificar se há dados após filtro
        if len(df_extrato) == 0:
            st.warning("⚠️ Nenhum registro no extrato para o período selecionado.")
            st.stop()
        
        if len(df_razao) == 0:
            st.warning("⚠️ Nenhum registro no razão para o período selecionado.")
            st.stop()
        
        # Realizar conciliação
        with st.spinner("Realizando conciliação automática..."):
            resultados = conciliar_dados(df_extrato, df_razao)
        
        # Gerar sugestões
        with st.spinner("Gerando sugestões inteligentes..."):
            df_extrato_marked = df_extrato.copy()
            df_razao_marked = df_razao.copy()
            df_extrato_marked['CONCILIADO'] = df_extrato_marked['CHAVE'].isin(
                resultados['conciliados']['CHAVE'] if len(resultados['conciliados']) > 0 else []
            )
            df_razao_marked['CONCILIADO'] = df_razao_marked['CHAVE'].isin(
                resultados['conciliados']['CHAVE'] if len(resultados['conciliados']) > 0 else []
            )
            sugestoes = gerar_sugestoes(df_extrato_marked, df_razao_marked)
            resultados['sugestoes'] = sugestoes
        
        # Calcular totais
        total_extrato = df_extrato['MOV'].sum()
        total_razao = df_razao['MOV'].sum()
        total_conciliado_extrato = resultados['conciliados']['MOV_EXTRATO'].sum() if len(resultados['conciliados']) > 0 else 0
        total_conciliado_razao = resultados['conciliados']['MOV_RAZAO'].sum() if len(resultados['conciliados']) > 0 else 0
        diferenca = abs(total_extrato - total_razao)
        
        # Armazenar resultados na sessão
        st.session_state['resultados'] = resultados
        st.session_state['total_extrato'] = total_extrato
        st.session_state['total_razao'] = total_razao
        st.session_state['total_conciliado_extrato'] = total_conciliado_extrato
        st.session_state['total_conciliado_razao'] = total_conciliado_razao
        st.session_state['diferenca'] = diferenca
        st.session_state['df_extrato_filtrado'] = df_extrato
        st.session_state['df_razao_filtrado'] = df_razao
        
        st.success("✅ Conciliação realizada com sucesso!")
    
    # ============================================================================
    # EXIBIÇÃO DOS RESULTADOS
    # ============================================================================
    
    if 'resultados' in st.session_state:
        resultados = st.session_state['resultados']
        total_extrato = st.session_state['total_extrato']
        total_razao = st.session_state['total_razao']
        total_conciliado_extrato = st.session_state['total_conciliado_extrato']
        total_conciliado_razao = st.session_state['total_conciliado_razao']
        diferenca = st.session_state['diferenca']
        df_extrato_filtrado = st.session_state['df_extrato_filtrado']
        df_razao_filtrado = st.session_state['df_razao_filtrado']
        
        # ============================================================================
        # ABA DE RESUMO
        # ============================================================================
        
        st.markdown("---")
        st.subheader("📊 Resumo da Conciliação")
        
        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
        
        with col_r1:
            st.metric(
                "Total Extrato",
                formatar_valor_para_exibicao(total_extrato),
                f"{len(df_extrato_filtrado)} registros"
            )
        
        with col_r2:
            st.metric(
                "Total Razão",
                formatar_valor_para_exibicao(total_razao),
                f"{len(df_razao_filtrado)} registros"
            )
        
        with col_r3:
            qtd_conciliados = len(resultados['conciliados'])
            st.metric(
                "Conciliados",
                formatar_valor_para_exibicao(total_conciliado_extrato),
                f"{qtd_conciliados} matches"
            )
        
        with col_r4:
            st.metric(
                "Diferença",
                formatar_valor_para_exibicao(diferenca),
                delta_color="inverse"
            )
        
        # Indicadores visuais
        st.markdown("### 📈 Indicadores")
        
        col_i1, col_i2, col_i3 = st.columns(3)
        
        with col_i1:
            taxa_conciliacao_extrato = (total_conciliado_extrato / total_extrato * 100) if total_extrato != 0 else 0
            st.progress(min(taxa_conciliacao_extrato / 100, 1.0))
            st.caption(f"Taxa de Conciliação Extrato: **{taxa_conciliacao_extrato:.1f}%**")
        
        with col_i2:
            taxa_conciliacao_razao = (total_conciliado_razao / total_razao * 100) if total_razao != 0 else 0
            st.progress(min(taxa_conciliacao_razao / 100, 1.0))
            st.caption(f"Taxa de Conciliação Razão: **{taxa_conciliacao_razao:.1f}%**")
        
        with col_i3:
            qtd_sugestoes = len(resultados.get('sugestoes', pd.DataFrame()))
            st.info(f"🧠 **{qtd_sugestoes}** sugestões disponíveis")
        
        st.markdown("---")
        
        # ============================================================================
        # ABAS DE DETALHAMENTO
        # ============================================================================
        
        tab1, tab2, tab3, tab4 = st.tabs([
            "✅ Conciliados",
            "🧠 Sugestões",
            "⚠️ Extrato Não Conciliado",
            "⚠️ Razão Não Conciliado"
        ])
        
        # ABA 1: Conciliados
        with tab1:
            st.subheader("✅ Lançamentos Conciliados")
            
            if len(resultados['conciliados']) > 0:
                df_conc = resultados['conciliados'].copy()
                
                # Formatar para exibição
                df_display = df_conc.copy()
                if 'DATA_EXTRATO' in df_display.columns:
                    df_display['DATA_EXTRATO'] = df_display['DATA_EXTRATO'].apply(formatar_data_para_exibicao)
                if 'DATA_RAZAO' in df_display.columns:
                    df_display['DATA_RAZAO'] = df_display['DATA_RAZAO'].apply(formatar_data_para_exibicao)
                if 'MOV_EXTRATO' in df_display.columns:
                    df_display['MOV_EXTRATO'] = df_display['MOV_EXTRATO'].apply(formatar_valor_para_exibicao)
                if 'MOV_RAZAO' in df_display.columns:
                    df_display['MOV_RAZAO'] = df_display['MOV_RAZAO'].apply(formatar_valor_para_exibicao)
                
                st.dataframe(
                    df_display,
                    use_container_width=True,
                    hide_index=True
                )
                
                st.info(f"Total de **{len(df_conc)}** lançamentos conciliados automaticamente.")
            else:
                st.warning("Nenhum lançamento foi conciliado automaticamente.")
        
        # ABA 2: Sugestões
        with tab2:
            st.subheader("🧠 Sugestões de Conciliação")
            
            if len(resultados.get('sugestoes', pd.DataFrame())) > 0:
                df_sug = resultados['sugestoes'].copy()
                
                # Formatar para exibição
                df_display = df_sug.copy()
                df_display['SCORE'] = df_display['SCORE'].apply(lambda x: f"⭐ {int(x)} pts")
                if 'DATA_EXTRATO' in df_display.columns:
                    df_display['DATA_EXTRATO'] = df_display['DATA_EXTRATO'].apply(formatar_data_para_exibicao)
                if 'DATA_RAZAO' in df_display.columns:
                    df_display['DATA_RAZAO'] = df_display['DATA_RAZAO'].apply(formatar_data_para_exibicao)
                if 'MOV_EXTRATO' in df_display.columns:
                    df_display['MOV_EXTRATO'] = df_display['MOV_EXTRATO'].apply(formatar_valor_para_exibicao)
                if 'MOV_RAZAO' in df_display.columns:
                    df_display['MOV_RAZAO'] = df_display['MOV_RAZAO'].apply(formatar_valor_para_exibicao)
                if 'DIFERENCA_VALOR' in df_display.columns:
                    df_display['DIFERENCA_VALOR'] = df_display['DIFERENCA_VALOR'].apply(formatar_valor_para_exibicao)
                
                st.dataframe(
                    df_display,
                    use_container_width=True,
                    hide_index=True
                )
                
                st.info(f"Total de **{len(df_sug)}** sugestões com score ≥ {CONFIG['score_minimo_sugestao']} pontos.")
            else:
                st.info("Nenhuma sugestão disponível para os registros não conciliados.")
        
        # ABA 3: Extrato Não Conciliado
        with tab3:
            st.subheader("⚠️ Lançamentos do Extrato Não Conciliados")
            
            if len(resultados['extrato_nao_conciliado']) > 0:
                df_enc = resultados['extrato_nao_conciliado'].copy()
                
                # Selecionar colunas relevantes
                cols_display = ['DATA', 'MOV', 'ENTRADAS', 'SAIDAS', 'HISTORICO', 'DOCUMENTO', 'CHAVE']
                cols_disponiveis = [c for c in cols_display if c in df_enc.columns]
                
                df_display = df_enc[cols_disponiveis].copy()
                if 'DATA' in df_display.columns:
                    df_display['DATA'] = df_display['DATA'].apply(formatar_data_para_exibicao)
                if 'MOV' in df_display.columns:
                    df_display['MOV'] = df_display['MOV'].apply(formatar_valor_para_exibicao)
                if 'ENTRADAS' in df_display.columns:
                    df_display['ENTRADAS'] = df_display['ENTRADAS'].apply(formatar_valor_para_exibicao)
                if 'SAIDAS' in df_display.columns:
                    df_display['SAIDAS'] = df_display['SAIDAS'].apply(formatar_valor_para_exibicao)
                
                st.dataframe(
                    df_display,
                    use_container_width=True,
                    hide_index=True
                )
                
                total_nao_conc = df_enc['MOV'].sum()
                st.warning(f"Total de **{len(df_enc)}** lançamentos não conciliados. Soma: {formatar_valor_para_exibicao(total_nao_conc)}")
            else:
                st.success("🎉 Todos os lançamentos do extrato foram conciliados!")
        
        # ABA 4: Razão Não Conciliado
        with tab4:
            st.subheader("⚠️ Lançamentos do Razão Não Conciliados")
            
            if len(resultados['razao_nao_conciliado']) > 0:
                df_rnc = resultados['razao_nao_conciliado'].copy()
                
                # Selecionar colunas relevantes
                cols_display = ['DATA', 'MOV', 'ENTRADAS', 'SAIDAS', 'HISTORICO', 'DOCUMENTO', 'CHAVE']
                cols_disponiveis = [c for c in cols_display if c in df_rnc.columns]
                
                df_display = df_rnc[cols_disponiveis].copy()
                if 'DATA' in df_display.columns:
                    df_display['DATA'] = df_display['DATA'].apply(formatar_data_para_exibicao)
                if 'MOV' in df_display.columns:
                    df_display['MOV'] = df_display['MOV'].apply(formatar_valor_para_exibicao)
                if 'ENTRADAS' in df_display.columns:
                    df_display['ENTRADAS'] = df_display['ENTRADAS'].apply(formatar_valor_para_exibicao)
                if 'SAIDAS' in df_display.columns:
                    df_display['SAIDAS'] = df_display['SAIDAS'].apply(formatar_valor_para_exibicao)
                
                st.dataframe(
                    df_display,
                    use_container_width=True,
                    hide_index=True
                )
                
                total_nao_conc = df_rnc['MOV'].sum()
                st.warning(f"Total de **{len(df_rnc)}** lançamentos não conciliados. Soma: {formatar_valor_para_exibicao(total_nao_conc)}")
            else:
                st.success("🎉 Todos os lançamentos do razão foram conciliados!")
        
        # ============================================================================
        # EXPORTAÇÃO
        # ============================================================================
        
        st.markdown("---")
        st.subheader("📤 Exportar Resultados")
        
        col_exp1, col_exp2 = st.columns([2, 1])
        
        with col_exp1:
            st.markdown("""
            Clique no botão ao lado para baixar um arquivo Excel contendo:
            - **Conciliados**: Todos os matches exatos encontrados
            - **Sugestões**: Matches parciais com score ≥ 60
            - **Extrato Não Conciliado**: Registros pendentes do extrato
            - **Razão Não Conciliado**: Registros pendentes do razão
            """)
        
        with col_exp2:
            excel_bytes = exportar_excel_resultados(resultados)
            
            st.download_button(
                label="📥 Baixar Excel",
                data=excel_bytes,
                file_name=f"conciliacao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )


# ============================================================================
# EXECUÇÃO
# ============================================================================

if __name__ == "__main__":
    main()