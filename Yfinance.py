"""
Sistema de Importação e Exportação de Plano de Contas para TOTVS Protheus
Versão: 4.0 - Simplificada e Direta
"""

import streamlit as st
import pandas as pd
from io import BytesIO
import json
from datetime import datetime

# ==================== CONFIGURAÇÃO ====================
st.set_page_config(page_title="Plano de Contas Protheus", page_icon="📊", layout="wide")

# Layout completo do CT1 (79 colunas)
CAMPOS = [
    'CT1_FILIAL', 'CT1_CONTA', 'CT1_DESC01', 'CT1_DESC02', 'CT1_DESC03',
    'CT1_DESC04', 'CT1_DESC05', 'CT1_CLASSE', 'CT1_NORMAL', 'CT1_RES',
    'CT1_BLOQ', 'CT1_DTBLIN', 'CT1_DTBLFI', 'CT1_DC', 'CT1_NCUSTO',
    'CT1_CC', 'CT1_CVD01', 'CT1_CVD02', 'CT1_CVD03', 'CT1_CVD04',
    'CT1_CVD05', 'CT1_CVC01', 'CT1_CVC02', 'CT1_CVC03', 'CT1_CVC04',
    'CT1_CVC05', 'CT1_CTASUP', 'CT1_HP', 'CT1_ACITEM', 'CT1_ACCUST',
    'CT1_ACCLVL', 'CT1_DTEXIS', 'CT1_CTAVM', 'CT1_CTARED', 'CT1_DTEXSF',
    'CT1_MOEDVM', 'CT1_CTALP', 'CT1_CTAPON', 'CT1_BOOK', 'CT1_GRUPO',
    'CT1_AGLSLD', 'CT1_RGNV1', 'CT1_RGNV2', 'CT1_RGNV3', 'CT1_CCOBRG',
    'CT1_ITOBRG', 'CT1_CLOBRG', 'CT1_CTLALU', 'CT1_TRNSEF', 'CT1_TPLALU',
    'CT1_AGLUT', 'CT1_LALHIR', 'CT1_LALUR', 'CT1_RATEIO', 'CT1_ESTOUR',
    'CT1_CODIMP', 'CT1_AJ_INF', 'CT1_DIOPS', 'CT1_NATCTA', 'CT1_ACATIV',
    'CT1_ATOBRG', 'CT1_ACET05', 'CT1_05OBRG', 'CT1_INDNAT', 'CT1_SPEDST',
    'CT1_NTSPED', 'CT1_ACAT01', 'CT1_AT01OB', 'CT1_ACAT02', 'CT1_AT02OB',
    'CT1_ACAT03', 'CT1_AT03OB', 'CT1_ACAT04', 'CT1_AT04OB', 'CT1_TPO01',
    'CT1_TPO02', 'CT1_TPO03', 'CT1_TPO04', 'CT1_INTP', 'CT1_PVARC', 'CT1_CTAORC'
]

# Tamanho de cada campo
TAMANHOS = {campo: 2 for campo in CAMPOS}  # Inicializa
TAMANHOS.update({
    'CT1_CONTA': 20, 'CT1_DESC01': 40, 'CT1_DESC02': 40, 'CT1_DESC03': 40,
    'CT1_DESC04': 40, 'CT1_DESC05': 40, 'CT1_CLASSE': 1, 'CT1_NORMAL': 1,
    'CT1_RES': 10, 'CT1_BLOQ': 1, 'CT1_DTBLIN': 8, 'CT1_DTBLFI': 8,
    'CT1_DC': 1, 'CT1_NCUSTO': 14, 'CT1_CC': 9, 'CT1_CTASUP': 20,
    'CT1_HP': 3, 'CT1_ACITEM': 1, 'CT1_ACCUST': 1, 'CT1_ACCLVL': 1,
    'CT1_DTEXIS': 8, 'CT1_CTAVM': 20, 'CT1_CTARED': 20, 'CT1_DTEXSF': 8,
    'CT1_MOEDVM': 2, 'CT1_CTALP': 20, 'CT1_CTAPON': 20, 'CT1_BOOK': 20,
    'CT1_GRUPO': 20, 'CT1_AGLSLD': 2, 'CT1_RGNV1': 20, 'CT1_RGNV2': 20,
    'CT1_RGNV3': 20, 'CT1_CCOBRG': 1, 'CT1_ITOBRG': 1, 'CT1_CLOBRG': 1,
    'CT1_CTLALU': 20, 'CT1_TRNSEF': 1, 'CT1_TPLALU': 1, 'CT1_AGLUT': 2,
    'CT1_LALHIR': 1, 'CT1_LALUR': 1, 'CT1_RATEIO': 1, 'CT1_ESTOUR': 1,
    'CT1_CODIMP': 20, 'CT1_AJ_INF': 1, 'CT1_DIOPS': 1, 'CT1_NATCTA': 2,
    'CT1_ACATIV': 1, 'CT1_ATOBRG': 1, 'CT1_ACET05': 1, 'CT1_05OBRG': 1,
    'CT1_INDNAT': 1, 'CT1_SPEDST': 2, 'CT1_NTSPED': 1, 'CT1_ACAT01': 1,
    'CT1_AT01OB': 1, 'CT1_ACAT02': 1, 'CT1_AT02OB': 1, 'CT1_ACAT03': 1,
    'CT1_AT03OB': 1, 'CT1_ACAT04': 1, 'CT1_AT04OB': 1, 'CT1_TPO01': 2,
    'CT1_TPO02': 2, 'CT1_TPO03': 2, 'CT1_TPO04': 2, 'CT1_INTP': 1,
    'CT1_PVARC': 2, 'CT1_CTAORC': 1
})

# Valores padrão
VALORES_PADRAO = {
    'CT1_DC': '7', 'CT1_DTEXIS': '19800101', 'CT1_ACITEM': '1',
    'CT1_ACCUST': '1', 'CT1_ACCLVL': '1', 'CT1_RES': '', 'CT1_HP': '   '
}

OPCOES_CLASSE = {'1': 'Sintética', '2': 'Analítica'}
OPCOES_NORMAL = {'1': 'Devedora', '2': 'Credora'}
OPCOES_BLOQ = {'1': 'Sim', '2': 'Não'}

# ==================== FUNÇÕES PRINCIPAIS ====================

def formatar_valor(valor, campo):
    """Formata valor com padding de espaços à direita"""
    if pd.isna(valor) or valor is None or str(valor).strip() == '':
        return ' ' * TAMANHOS[campo]
    
    valor_str = str(valor).strip()
    
    # Trata datas
    if 'DT' in campo and '/' in valor_str:
        partes = valor_str.split('/')
        if len(partes) == 3:
            valor_str = f"{partes[2]}{partes[1]}{partes[0]}"
    
    # Remove caracteres inválidos
    valor_str = ''.join(c for c in valor_str if c.isprintable())
    
    # Trunca e aplica padding
    if len(valor_str) > TAMANHOS[campo]:
        valor_str = valor_str[:TAMANHOS[campo]]
    
    return valor_str.ljust(TAMANHOS[campo])

def gerar_csv(df):
    """Gera CSV no formato exato do Protheus"""
    linhas = ["0;CT1;CVD"]
    
    # Cabeçalho (apenas nomes, sem tamanhos)
    linhas.append("1;" + ";".join(CAMPOS))
    
    # Dados
    for _, row in df.iterrows():
        linha = "1"
        for campo in CAMPOS:
            valor = row.get(campo, '')
            linha += ";" + formatar_valor(valor, campo)
        linhas.append(linha)
    
    # Linha final
    linhas.append("2;CVD_FILIAL;CVD_CONTA;CVD_ENTREF;CVD_CODPLA;CVD_VERSAO;CVD_CTAREF;CVD_CUSTO;CVD_CLASSE;CVD_TPUTIL;CVD_NATCTA;CVD_CTASUP")
    
    return "\n".join(linhas)

def transformar(df, config):
    """Transforma dados do Excel para o layout Protheus"""
    df_out = pd.DataFrame(columns=CAMPOS)
    erros = []
    
    for idx, row in df.iterrows():
        linha = {}
        
        # Mapeia campos básicos
        linha['CT1_CONTA'] = str(row.get('CT1_CONTA', '')).strip()
        linha['CT1_DESC01'] = str(row.get('CT1_DESC01', '')).strip()
        linha['CT1_FILIAL'] = str(row.get('CT1_FILIAL', config.get('filial_padrao', ''))).strip()[:2]
        linha['CT1_NORMAL'] = str(row.get('CT1_NORMAL', config.get('normal_padrao', '1'))).strip()
        linha['CT1_BLOQ'] = str(row.get('CT1_BLOQ', config.get('bloq_padrao', '2'))).strip()
        linha['CT1_CTASUP'] = str(row.get('CT1_CTASUP', '')).strip()
        
        # Classe automática
        if config.get('aplicar_regras_auto', True):
            niveis = linha['CT1_CONTA'].count('.')
            linha['CT1_CLASSE'] = '1' if niveis <= 1 else '2'
        else:
            linha['CT1_CLASSE'] = str(row.get('CT1_CLASSE', config.get('classe_padrao', '2'))).strip()
        
        # Validações básicas
        if not linha['CT1_CONTA']:
            erros.append(f"Linha {idx+2}: CT1_CONTA vazio")
        if not linha['CT1_DESC01']:
            erros.append(f"Linha {idx+2}: CT1_DESC01 vazio")
        if linha['CT1_NORMAL'] not in OPCOES_NORMAL:
            erros.append(f"Linha {idx+2}: CT1_NORMAL inválido: {linha['CT1_NORMAL']}")
        
        # Aplica valores padrão
        for campo, valor in VALORES_PADRAO.items():
            linha[campo] = valor
        
        df_out.loc[len(df_out)] = linha
    
    return df_out, erros

def carregar_arquivo(arquivo):
    """Carrega arquivo Excel"""
    try:
        df = pd.read_excel(arquivo, dtype=str)
        df.columns = df.columns.str.strip()
        df = df.map(lambda x: x.strip() if isinstance(x, str) else x)
        return df
    except Exception as e:
        st.error(f"Erro: {e}")
        return None

# ==================== INTERFACE ====================

def main():
    st.title("📊 Plano de Contas - TOTVS Protheus")
    
    # Configurações na sidebar
    with st.sidebar:
        st.header("⚙️ Configurações")
        filial = st.text_input("Filial Padrão", max_chars=2)
        auto_classe = st.checkbox("Classe automática", True)
        classe = st.selectbox("Classe padrão", ['', '1', '2'], format_func=lambda x: OPCOES_CLASSE.get(x, 'Auto')) if not auto_classe else None
        normal = st.selectbox("Natureza padrão", ['1', '2'], format_func=lambda x: OPCOES_NORMAL[x])
        bloq = st.selectbox("Bloqueio padrão", ['2', '1'], format_func=lambda x: OPCOES_BLOQ[x])
    
    config = {
        'filial_padrao': filial,
        'aplicar_regras_auto': auto_classe,
        'classe_padrao': classe if classe else '2',
        'normal_padrao': normal,
        'bloq_padrao': bloq
    }
    
    # Upload
    arquivo = st.file_uploader("Arquivo Excel", type=['xlsx'])
    
    if arquivo:
        df = carregar_arquivo(arquivo)
        
        if df is not None:
            if not all(col in df.columns for col in ['CT1_CONTA', 'CT1_DESC01']):
                st.error("Faltam colunas obrigatórias: CT1_CONTA e CT1_DESC01")
                return
            
            with st.spinner("Processando..."):
                df_protheus, erros = transformar(df, config)
            
            if erros:
                for erro in erros[:5]:
                    st.warning(erro)
            
            st.success(f"✅ {len(df_protheus)} registros processados")
            
            # Preview
            st.dataframe(df_protheus[['CT1_CONTA', 'CT1_DESC01', 'CT1_CLASSE', 'CT1_NORMAL']].head(10))
            
            # Exportar
            if st.button("📥 Gerar CSV", type="primary"):
                csv_data = gerar_csv(df_protheus)
                
                # Preview do CSV gerado
                with st.expander("Preview do CSV"):
                    st.code('\n'.join(csv_data.split('\n')[:5]), language='text')
                
                st.download_button(
                    "✅ Baixar CSV",
                    data=BytesIO(csv_data.encode('latin1')),
                    file_name=f"plano_contas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )

if __name__ == "__main__":
    main()