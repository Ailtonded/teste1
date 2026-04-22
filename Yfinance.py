"""
Sistema de Importação e Exportação de Plano de Contas para TOTVS Protheus
Versão: 6.2 - Interface Modernizada (CORRIGIDA)
"""

import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
import logging

# ==================== CONFIGURAÇÃO ====================
st.set_page_config(
    page_title="Plano de Contas Protheus", 
    page_icon="📊", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== CONSTANTES (NÃO ALTERAR) ====================
# ORDEM EXATA DOS CAMPOS CT1
CAMPOS_CT1 = [
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
TAMANHOS = {
    'CT1_FILIAL': 2, 'CT1_CONTA': 20, 'CT1_DESC01': 40, 'CT1_DESC02': 40,
    'CT1_DESC03': 40, 'CT1_DESC04': 40, 'CT1_DESC05': 40, 'CT1_CLASSE': 1,
    'CT1_NORMAL': 1, 'CT1_RES': 10, 'CT1_BLOQ': 1, 'CT1_DTBLIN': 8,
    'CT1_DTBLFI': 8, 'CT1_DC': 1, 'CT1_NCUSTO': 14, 'CT1_CC': 9,
    'CT1_CVD01': 1, 'CT1_CVD02': 1, 'CT1_CVD03': 1, 'CT1_CVD04': 1,
    'CT1_CVD05': 1, 'CT1_CVC01': 1, 'CT1_CVC02': 1, 'CT1_CVC03': 1,
    'CT1_CVC04': 1, 'CT1_CVC05': 1, 'CT1_CTASUP': 20, 'CT1_HP': 3,
    'CT1_ACITEM': 1, 'CT1_ACCUST': 1, 'CT1_ACCLVL': 1, 'CT1_DTEXIS': 8,
    'CT1_CTAVM': 20, 'CT1_CTARED': 20, 'CT1_DTEXSF': 8, 'CT1_MOEDVM': 2,
    'CT1_CTALP': 20, 'CT1_CTAPON': 20, 'CT1_BOOK': 20, 'CT1_GRUPO': 20,
    'CT1_AGLSLD': 2, 'CT1_RGNV1': 20, 'CT1_RGNV2': 20, 'CT1_RGNV3': 20,
    'CT1_CCOBRG': 1, 'CT1_ITOBRG': 1, 'CT1_CLOBRG': 1, 'CT1_CTLALU': 20,
    'CT1_TRNSEF': 1, 'CT1_TPLALU': 1, 'CT1_AGLUT': 2, 'CT1_LALHIR': 1,
    'CT1_LALUR': 1, 'CT1_RATEIO': 1, 'CT1_ESTOUR': 1, 'CT1_CODIMP': 20,
    'CT1_AJ_INF': 1, 'CT1_DIOPS': 1, 'CT1_NATCTA': 2, 'CT1_ACATIV': 1,
    'CT1_ATOBRG': 1, 'CT1_ACET05': 1, 'CT1_05OBRG': 1, 'CT1_INDNAT': 1,
    'CT1_SPEDST': 2, 'CT1_NTSPED': 2, 'CT1_ACAT01': 1, 'CT1_AT01OB': 1,
    'CT1_ACAT02': 1, 'CT1_AT02OB': 1, 'CT1_ACAT03': 1, 'CT1_AT03OB': 1,
    'CT1_ACAT04': 1, 'CT1_AT04OB': 1, 'CT1_TPO01': 2, 'CT1_TPO02': 2,
    'CT1_TPO03': 2, 'CT1_TPO04': 2, 'CT1_INTP': 1, 'CT1_PVARC': 2, 'CT1_CTAORC': 1
}

# Valores válidos para CT1_NTSPED
NTSPED_VALIDOS = ['01', '02', '03', '04', '05', '09']

# ==================== FUNÇÕES (NÃO ALTERAR LÓGICA) ====================

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
    
    # Linha 1: cabeçalho com todos os campos
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

@st.cache_data
def transformar(df):
    """Transforma dados do Excel para o layout Protheus"""
    df_out = pd.DataFrame(columns=CAMPOS_CT1)
    erros = []
    
    # Identifica campos válidos no Excel
    campos_validos = [col for col in df.columns if col in CAMPOS_CT1]
    campos_ignorados = [col for col in df.columns if col.startswith('CT1_') and col not in CAMPOS_CT1]
    
    if campos_ignorados:
        st.warning(f"⚠️ Campos ignorados: {', '.join(campos_ignorados)}")
    
    for idx, row in df.iterrows():
        linha = {}
        
        # Inicializa todos os campos como vazio
        for campo in CAMPOS_CT1:
            linha[campo] = ''
        
        # Processa campos válidos
        for campo in campos_validos:
            valor = row.get(campo, '')
            if pd.notna(valor) and str(valor).strip() != '':
                linha[campo] = str(valor).strip()
        
        # Validações obrigatórias
        if not linha.get('CT1_CONTA'):
            erros.append(f"Linha {idx+2}: CT1_CONTA vazio")
        if not linha.get('CT1_DESC01'):
            erros.append(f"Linha {idx+2}: CT1_DESC01 vazio")
        
        # Valida CT1_NTSPED (se veio da planilha)
        if linha.get('CT1_NTSPED'):
            ntsped = linha['CT1_NTSPED']
            if ntsped not in NTSPED_VALIDOS:
                erros.append(f"Linha {idx+2}: CT1_NTSPED='{ntsped}' inválido. Use: 01,02,03,04,05,09")
                linha['CT1_NTSPED'] = ''  # Limpa o valor inválido
        
        # Classe automática baseada nos níveis da conta
        if not linha.get('CT1_CLASSE'):
            niveis = linha.get('CT1_CONTA', '').count('.')
            linha['CT1_CLASSE'] = '1' if niveis <= 1 else '2'
        
        # Valores padrão obrigatórios (apenas para campos que não vieram da planilha)
        if not linha.get('CT1_DC'):
            linha['CT1_DC'] = '7'
        if not linha.get('CT1_DTEXIS'):
            linha['CT1_DTEXIS'] = '19800101'
        if not linha.get('CT1_ACITEM'):
            linha['CT1_ACITEM'] = '1'
        if not linha.get('CT1_ACCUST'):
            linha['CT1_ACCUST'] = '1'
        if not linha.get('CT1_ACCLVL'):
            linha['CT1_ACCLVL'] = '1'
        if not linha.get('CT1_BLOQ'):
            linha['CT1_BLOQ'] = '2'
        if not linha.get('CT1_NORMAL'):
            linha['CT1_NORMAL'] = '1'
        
        # NÃO preenche CT1_NTSPED automaticamente (deixa em branco)
        
        df_out.loc[len(df_out)] = linha
    
    return df_out, erros

@st.cache_data
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

# ==================== INTERFACE MODERNIZADA ====================

def main():
    # HEADER COMPACTO
    st.markdown("""
        <style>
            .main-header {
                padding: 0rem 0rem 1rem 0rem;
                border-bottom: 2px solid #f0f2f6;
                margin-bottom: 1rem;
            }
            .metric-card {
                background-color: #f8f9fa;
                padding: 0.8rem;
                border-radius: 0.5rem;
                text-align: center;
            }
            .stButton > button {
                width: 100%;
            }
        </style>
    """, unsafe_allow_html=True)
    
    col_logo, col_title = st.columns([1, 10])
    with col_logo:
        st.markdown("## 📊")
    with col_title:
        st.markdown("### Plano de Contas - TOTVS Protheus")
        st.caption(f"Sistema compatível com {len(CAMPOS_CT1)} campos do layout CT1")
    
    # SIDEBAR INTELIGENTE
    with st.sidebar:
        st.markdown("## 🎛️ Controles")
        st.markdown("---")
        
        # Upload de arquivo
        arquivo = st.file_uploader("📂 Importar Excel", type=['xlsx'], key="file_uploader")
        
        if arquivo and 'df_protheus' in st.session_state:
            st.markdown("---")
            st.markdown("### 🎨 Visualização")
            
            # Multiselect de colunas
            todas_colunas = st.session_state.df_protheus.columns.tolist()
            colunas_padrao = ['CT1_CONTA', 'CT1_DESC01', 'CT1_CLASSE', 'CT1_NORMAL', 'CT1_NTSPED']
            colunas_disponiveis = [c for c in colunas_padrao if c in todas_colunas]
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Selecionar tudo", use_container_width=True):
                    st.session_state.colunas_selecionadas = todas_colunas
                    st.rerun()
            with col2:
                if st.button("❌ Limpar tudo", use_container_width=True):
                    st.session_state.colunas_selecionadas = []
                    st.rerun()
            
            st.markdown("#### Colunas visíveis")
            colunas_selecionadas = st.multiselect(
                "Selecione as colunas para exibir",
                options=todas_colunas,
                default=st.session_state.get('colunas_selecionadas', colunas_disponiveis),
                key="multiselect_colunas"
            )
            st.session_state.colunas_selecionadas = colunas_selecionadas
        
        st.markdown("---")
        st.caption("💡 **Dica:** Use o multiselect para focar nas colunas importantes")
    
    # ÁREA PRINCIPAL
    if arquivo:
        df = carregar_arquivo(arquivo)
        
        if df is not None:
            colunas_ct1 = [col for col in df.columns if col in CAMPOS_CT1]
            
            # Processamento
            with st.spinner("🔄 Processando plano de contas..."):
                df_protheus, erros = transformar(df)
                st.session_state.df_protheus = df_protheus
                st.session_state.erros = erros
                st.session_state.total_registros = len(df_protheus)
                st.session_state.total_colunas_ct1 = len(colunas_ct1)
            
            # MÉTRICAS EM UMA LINHA
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📄 Total de Registros", st.session_state.total_registros)
            with col2:
                st.metric("📦 Colunas CT1", f"{st.session_state.total_colunas_ct1}/{len(CAMPOS_CT1)}")
            with col3:
                st.metric("⚠️ Erros Encontrados", len(erros), delta="Revisar" if erros else None)
            with col4:
                if 'CT1_NTSPED' in df_protheus.columns:
                    ntsped_preenchidos = df_protheus['CT1_NTSPED'].ne('').sum()
                    st.metric("🏷️ CT1_NTSPED", f"{ntsped_preenchidos} preenchidos")
            
            # Alerta de erros (resumido)
            if erros:
                with st.expander(f"⚠️ Detalhes dos {len(erros)} erro(s) encontrado(s)"):
                    for erro in erros[:15]:
                        st.warning(erro)
                    if len(erros) > 15:
                        st.info(f"... e mais {len(erros)-15} erros não exibidos")
            else:
                st.success(f"✅ Processamento concluído com sucesso! {st.session_state.total_registros} registros prontos para exportação.")
            
            # GRID OTIMIZADO
            st.markdown("---")
            st.markdown("### 📋 Visualização dos Dados")
            
            # Aplicar filtro de colunas da sidebar
            if st.session_state.get('colunas_selecionadas'):
                df_display = df_protheus[st.session_state.colunas_selecionadas]
            else:
                df_display = df_protheus[['CT1_CONTA', 'CT1_DESC01', 'CT1_CLASSE', 'CT1_NORMAL', 'CT1_NTSPED']]
            
            # Tabela com altura maior
            st.dataframe(
                df_display, 
                use_container_width=True, 
                height=500,
                hide_index=True
            )
            
            # BOTÃO DE EXPORTAÇÃO ALINHADO
            st.markdown("---")
            col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 1])
            
            with col_btn2:
                if st.button("📊 Ver CSV Bruto", use_container_width=True):
                    st.session_state.show_csv = not st.session_state.get('show_csv', False)
            
            with col_btn3:
                csv_data = gerar_csv(df_protheus)
                st.download_button(
                    "⬇️ Baixar CSV Protheus",
                    data=BytesIO(csv_data.encode('latin1')),
                    file_name=f"plano_contas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    type="primary"
                )
            
            # Preview do CSV quando solicitado
            if st.session_state.get('show_csv', False):
                with st.expander("🔍 Preview do CSV Gerado", expanded=True):
                    csv_data = gerar_csv(df_protheus)
                    linhas_preview = csv_data.split('\n')[:10]
                    st.code('\n'.join(linhas_preview), language='text')
                    st.caption(f"Arquivo completo com {len(df_protheus)} registros + cabeçalhos")
    
    else:
        # Estado inicial sem arquivo
        st.info("👈 **Comece carregando um arquivo Excel** na barra lateral")
        
        # Mostrar exemplo do formato esperado
        with st.expander("📖 Formato esperado do arquivo Excel"):
            st.markdown("""
            **Colunas obrigatórias:**
            - `CT1_CONTA` - Código da conta contábil (ex: 1.01.001)
            - `CT1_DESC01` - Descrição da conta
            
            **Colunas opcionais mais comuns:**
            - `CT1_FILIAL` - Filial (padrão: vazio)
            - `CT1_DESC02` a `CT1_DESC05` - Descrições adicionais
            - `CT1_NTSPED` - Natureza da conta SPED (01,02,03,04,05,09)
            - `CT1_CLASSE` - 1=Sintética, 2=Analítica
            - `CT1_NORMAL` - 1=Devedora, 2=Credora
            - `CT1_CTASUP` - Conta superior (hierarquia)
            
            **Exemplo mínimo:**
            """)
            
            df_exemplo = pd.DataFrame({
                'CT1_CONTA': ['1.01', '1.01.001', '1.01.002'],
                'CT1_DESC01': ['Ativo Circulante', 'Caixa', 'Bancos'],
                'CT1_NTSPED': ['01', '01', '01']
            })
            st.dataframe(df_exemplo, use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()
