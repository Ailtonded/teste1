"""
Sistema de Importação e Exportação de Plano de Contas para TOTVS Protheus
Versão: 5.0 - Processa dinamicamente qualquer campo CT1 da planilha
"""

import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime

# ==================== CONFIGURAÇÃO ====================
st.set_page_config(page_title="Plano de Contas Protheus", page_icon="📊", layout="wide")

# LISTA EXATA DOS CAMPOS DA TABELA CT1 (79 campos)
CAMPOS_CT1 = [
    'CT1_FILIAL', 'CT1_CONTA', 'CT1_DESC01', 'CT1_CLASSE', 'CT1_NORMAL',
    'CT1_CTASUP', 'CT1_GRUPO', 'CT1_RES', 'CT1_BLOQ', 'CT1_DTBLIN',
    'CT1_DTBLFI', 'CT1_DESC02', 'CT1_DESC03', 'CT1_DESC04', 'CT1_DESC05',
    'CT1_ACITEM', 'CT1_ACCUST', 'CT1_ACCLVL', 'CT1_CCOBRG', 'CT1_ITOBRG',
    'CT1_CLOBRG', 'CT1_NCUSTO', 'CT1_CC', 'CT1_CVD01', 'CT1_CVD02',
    'CT1_CVD03', 'CT1_CVD04', 'CT1_CVD05', 'CT1_CVC01', 'CT1_CVC02',
    'CT1_CVC03', 'CT1_CVC04', 'CT1_CVC05', 'CT1_CTAVM', 'CT1_CTARED',
    'CT1_CTALP', 'CT1_CTAPON', 'CT1_HP', 'CT1_DTEXIS', 'CT1_DTEXSF',
    'CT1_MOEDVM', 'CT1_BOOK', 'CT1_AGLSLD', 'CT1_RGNV1', 'CT1_RGNV2',
    'CT1_RGNV3', 'CT1_CTLALU', 'CT1_TRNSEF', 'CT1_TPLALU', 'CT1_AGLUT',
    'CT1_LALHIR', 'CT1_LALUR', 'CT1_RATEIO', 'CT1_ESTOUR', 'CT1_CODIMP',
    'CT1_AJ_INF', 'CT1_DIOPS', 'CT1_NATCTA', 'CT1_ACATIV', 'CT1_ATOBRG',
    'CT1_ACET05', 'CT1_05OBRG', 'CT1_INDNAT', 'CT1_SPEDST', 'CT1_NTSPED',
    'CT1_ACAT01', 'CT1_AT01OB', 'CT1_ACAT02', 'CT1_AT02OB', 'CT1_ACAT03',
    'CT1_AT03OB', 'CT1_ACAT04', 'CT1_AT04OB', 'CT1_TPO01', 'CT1_TPO02',
    'CT1_TPO03', 'CT1_TPO04', 'CT1_INTP', 'CT1_PVARC', 'CT1_CTAORC'
]

# Tamanho de cada campo (padrão Protheus)
TAMANHOS = {
    'CT1_FILIAL': 2, 'CT1_CONTA': 20, 'CT1_DESC01': 40, 'CT1_CLASSE': 1,
    'CT1_NORMAL': 1, 'CT1_CTASUP': 20, 'CT1_GRUPO': 20, 'CT1_RES': 10,
    'CT1_BLOQ': 1, 'CT1_DTBLIN': 8, 'CT1_DTBLFI': 8, 'CT1_DESC02': 40,
    'CT1_DESC03': 40, 'CT1_DESC04': 40, 'CT1_DESC05': 40, 'CT1_ACITEM': 1,
    'CT1_ACCUST': 1, 'CT1_ACCLVL': 1, 'CT1_CCOBRG': 1, 'CT1_ITOBRG': 1,
    'CT1_CLOBRG': 1, 'CT1_NCUSTO': 14, 'CT1_CC': 9, 'CT1_CVD01': 1,
    'CT1_CVD02': 1, 'CT1_CVD03': 1, 'CT1_CVD04': 1, 'CT1_CVD05': 1,
    'CT1_CVC01': 1, 'CT1_CVC02': 1, 'CT1_CVC03': 1, 'CT1_CVC04': 1,
    'CT1_CVC05': 1, 'CT1_CTAVM': 20, 'CT1_CTARED': 20, 'CT1_CTALP': 20,
    'CT1_CTAPON': 20, 'CT1_HP': 3, 'CT1_DTEXIS': 8, 'CT1_DTEXSF': 8,
    'CT1_MOEDVM': 2, 'CT1_BOOK': 20, 'CT1_AGLSLD': 2, 'CT1_RGNV1': 20,
    'CT1_RGNV2': 20, 'CT1_RGNV3': 20, 'CT1_CTLALU': 20, 'CT1_TRNSEF': 1,
    'CT1_TPLALU': 1, 'CT1_AGLUT': 2, 'CT1_LALHIR': 1, 'CT1_LALUR': 1,
    'CT1_RATEIO': 1, 'CT1_ESTOUR': 1, 'CT1_CODIMP': 20, 'CT1_AJ_INF': 1,
    'CT1_DIOPS': 1, 'CT1_NATCTA': 2, 'CT1_ACATIV': 1, 'CT1_ATOBRG': 1,
    'CT1_ACET05': 1, 'CT1_05OBRG': 1, 'CT1_INDNAT': 1, 'CT1_SPEDST': 2,
    'CT1_NTSPED': 1, 'CT1_ACAT01': 1, 'CT1_AT01OB': 1, 'CT1_ACAT02': 1,
    'CT1_AT02OB': 1, 'CT1_ACAT03': 1, 'CT1_AT03OB': 1, 'CT1_ACAT04': 1,
    'CT1_AT04OB': 1, 'CT1_TPO01': 2, 'CT1_TPO02': 2, 'CT1_TPO03': 2,
    'CT1_TPO04': 2, 'CT1_INTP': 1, 'CT1_PVARC': 2, 'CT1_CTAORC': 1
}

# Valores padrão para campos obrigatórios
VALORES_PADRAO = {
    'CT1_DC': '7',
    'CT1_DTEXIS': '19800101',
    'CT1_ACITEM': '1',
    'CT1_ACCUST': '1',
    'CT1_ACCLVL': '1'
}

OPCOES_CLASSE = {'1': 'Sintética', '2': 'Analítica'}
OPCOES_NORMAL = {'1': 'Devedora', '2': 'Credora'}
OPCOES_BLOQ = {'1': 'Sim', '2': 'Não'}

# ==================== FUNÇÕES ====================

def formatar_valor(valor, campo):
    """Formata valor com padding de espaços à direita"""
    if pd.isna(valor) or valor is None or str(valor).strip() == '':
        return ' ' * TAMANHOS.get(campo, 20)
    
    valor_str = str(valor).strip()
    
    # Trata datas (DD/MM/YYYY -> YYYYMMDD)
    if 'DT' in campo and '/' in valor_str:
        partes = valor_str.split('/')
        if len(partes) == 3:
            valor_str = f"{partes[2]}{partes[1]}{partes[0]}"
    
    # Remove caracteres não imprimíveis
    valor_str = ''.join(c for c in valor_str if c.isprintable())
    
    # Trunca se necessário
    tamanho = TAMANHOS.get(campo, 20)
    if len(valor_str) > tamanho:
        valor_str = valor_str[:tamanho]
    
    return valor_str.ljust(tamanho)

def gerar_csv(df):
    """Gera CSV no formato exato do Protheus"""
    linhas = ["0;CT1;CVD"]
    
    # Linha 1: cabeçalho com todos os campos (SEM tamanhos)
    linhas.append("1;" + ";".join(CAMPOS_CT1))
    
    # Linhas de dados
    for _, row in df.iterrows():
        linha = "1"
        for campo in CAMPOS_CT1:
            valor = row.get(campo, '')
            linha += ";" + formatar_valor(valor, campo)
        linhas.append(linha)
    
    # Linha final
    linhas.append("2;CVD_FILIAL;CVD_CONTA;CVD_ENTREF;CVD_CODPLA;CVD_VERSAO;CVD_CTAREF;CVD_CUSTO;CVD_CLASSE;CVD_TPUTIL;CVD_NATCTA;CVD_CTASUP")
    
    return "\n".join(linhas)

def transformar(df, config):
    """
    Transforma dados do Excel para o layout Protheus.
    Processa apenas campos que existem na lista CAMPOS_CT1.
    """
    # Criar DataFrame com todos os campos CT1 vazios
    df_out = pd.DataFrame(columns=CAMPOS_CT1)
    erros = []
    campos_ignorados = []
    
    # Identificar quais campos do Excel são válidos
    colunas_excel = df.columns.tolist()
    campos_validos = [col for col in colunas_excel if col in CAMPOS_CT1]
    campos_invalidos = [col for col in colunas_excel if col not in CAMPOS_CT1 and col.startswith('CT1_')]
    
    if campos_invalidos:
        st.warning(f"⚠️ Campos ignorados (não existem na tabela CT1): {', '.join(campos_invalidos)}")
    
    for idx, row in df.iterrows():
        linha = {}
        
        # Inicializa todos os campos como vazio
        for campo in CAMPOS_CT1:
            linha[campo] = ''
        
        # Processa apenas campos válidos que existem no Excel
        for campo in campos_validos:
            valor = row.get(campo, '')
            if pd.notna(valor) and str(valor).strip() != '':
                linha[campo] = str(valor).strip()
        
        # Validações obrigatórias
        if not linha.get('CT1_CONTA'):
            erros.append(f"Linha {idx+2}: CT1_CONTA vazio")
        if not linha.get('CT1_DESC01'):
            erros.append(f"Linha {idx+2}: CT1_DESC01 vazio")
        
        # Aplica classe automática se necessário
        if config.get('aplicar_regras_auto', True) and not linha.get('CT1_CLASSE'):
            niveis = linha.get('CT1_CONTA', '').count('.')
            linha['CT1_CLASSE'] = '1' if niveis <= 1 else '2'
        
        # Aplica valores padrão da configuração
        if config.get('filial_padrao') and not linha.get('CT1_FILIAL'):
            linha['CT1_FILIAL'] = config['filial_padrao']
        if config.get('normal_padrao') and not linha.get('CT1_NORMAL'):
            linha['CT1_NORMAL'] = config['normal_padrao']
        if config.get('bloq_padrao') and not linha.get('CT1_BLOQ'):
            linha['CT1_BLOQ'] = config['bloq_padrao']
        
        # Aplica valores padrão do sistema
        for campo, valor in VALORES_PADRAO.items():
            if campo not in linha or not linha.get(campo):
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
        st.error(f"Erro ao carregar: {e}")
        return None

# ==================== INTERFACE ====================

def main():
    st.title("📊 Plano de Contas - TOTVS Protheus")
    st.caption(f"Total de campos disponíveis: {len(CAMPOS_CT1)} campos CT1")
    
    # Configurações na sidebar
    with st.sidebar:
        st.header("⚙️ Configurações")
        filial = st.text_input("Filial Padrão", max_chars=2, placeholder="Ex: 01")
        auto_classe = st.checkbox("Determinar classe automaticamente", value=True)
        normal = st.selectbox("Natureza padrão (CT1_NORMAL)", ['1', '2'], 
                              format_func=lambda x: OPCOES_NORMAL[x])
        bloq = st.selectbox("Bloqueio padrão (CT1_BLOQ)", ['2', '1'], 
                            format_func=lambda x: OPCOES_BLOQ[x])
    
    config = {
        'filial_padrao': filial,
        'aplicar_regras_auto': auto_classe,
        'normal_padrao': normal,
        'bloq_padrao': bloq
    }
    
    # Upload
    arquivo = st.file_uploader("📂 Selecione o arquivo Excel", type=['xlsx'])
    
    if arquivo:
        df = carregar_arquivo(arquivo)
        
        if df is not None:
            # Mostrar campos encontrados
            colunas_ct1 = [col for col in df.columns if col in CAMPOS_CT1]
            st.info(f"📌 Campos CT1 encontrados no Excel: {', '.join(colunas_ct1) if colunas_ct1 else 'Nenhum'}")
            
            if 'CT1_CONTA' not in df.columns or 'CT1_DESC01' not in df.columns:
                st.error("❌ Colunas obrigatórias faltando: CT1_CONTA e CT1_DESC01")
                return
            
            with st.spinner("Processando..."):
                df_protheus, erros = transformar(df, config)
            
            if erros:
                for erro in erros[:5]:
                    st.warning(erro)
                if len(erros) > 5:
                    st.warning(f"... e mais {len(erros)-5} erros")
            
            st.success(f"✅ {len(df_protheus)} registros processados")
            
            # Preview dos campos preenchidos
            campos_preenchidos = [c for c in CAMPOS_CT1 if (df_protheus[c] != '').any()]
            st.caption(f"Campos preenchidos: {len(campos_preenchidos)} de {len(CAMPOS_CT1)}")
            
            # Mostrar apenas colunas que têm dados
            colunas_para_mostrar = ['CT1_CONTA', 'CT1_DESC01', 'CT1_CLASSE', 'CT1_NORMAL', 'CT1_CTASUP']
            colunas_existentes = [c for c in colunas_para_mostrar if c in df_protheus.columns]
            st.dataframe(df_protheus[colunas_existentes].head(10), use_container_width=True)
            
            # Exportar
            if st.button("📥 Gerar CSV para Protheus", type="primary"):
                csv_data = gerar_csv(df_protheus)
                
                with st.expander("🔍 Preview do CSV gerado"):
                    st.code('\n'.join(csv_data.split('\n')[:4]), language='text')
                
                st.download_button(
                    "✅ Baixar CSV",
                    data=BytesIO(csv_data.encode('latin1')),
                    file_name=f"plano_contas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )

if __name__ == "__main__":
    main()