"""
Sistema de Importação e Exportação de Plano de Contas para TOTVS Protheus
Versão: 3.3.0 - Layout COMPLETO do Protheus (79 colunas)
"""

import streamlit as st
import pandas as pd
from io import BytesIO
import json
from typing import Tuple, Optional, Dict, Any
from datetime import datetime

# Configuração da página
st.set_page_config(
    page_title="Sistema Protheus - Plano de Contas",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constantes
COLUNAS_OBRIGATORIAS = ['CT1_CONTA', 'CT1_DESC01']

# LAYOUT COMPLETO DO PROTHEUS (TODAS AS 79 COLUNAS)
LAYOUT_FINAL_COMPLETO = [
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

# Larguras de cada campo (baseado no layout do Protheus)
LARGURAS_CAMPOS = {
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
    'CT1_SPEDST': 2, 'CT1_NTSPED': 1, 'CT1_ACAT01': 1, 'CT1_AT01OB': 1,
    'CT1_ACAT02': 1, 'CT1_AT02OB': 1, 'CT1_ACAT03': 1, 'CT1_AT03OB': 1,
    'CT1_ACAT04': 1, 'CT1_AT04OB': 1, 'CT1_TPO01': 2, 'CT1_TPO02': 2,
    'CT1_TPO03': 2, 'CT1_TPO04': 2, 'CT1_INTP': 1, 'CT1_PVARC': 2, 'CT1_CTAORC': 1
}

# Opções de validação
OPCOES_CLASSE = {
    '1': 'Sintética (Totalizadora)',
    '2': 'Analítica (Recebe Valores)'
}

OPCOES_NORMAL = {
    '1': 'Devedora',
    '2': 'Credora'
}

OPCOES_BLOQ = {
    '1': 'Sim (Bloqueada)',
    '2': 'Não (Ativa)'
}

def carregar_configuracoes() -> Dict[str, Any]:
    """Carrega configurações salvas do session_state"""
    if 'configuracoes' not in st.session_state:
        st.session_state.configuracoes = {
            'filial_padrao': '',
            'aplicar_regras_auto': True,
            'classe_padrao': '',
            'normal_padrao': '1',
            'bloq_padrao': '2'
        }
    return st.session_state.configuracoes

def salvar_configuracoes(config: Dict[str, Any]):
    st.session_state.configuracoes = config

def exportar_configuracoes() -> str:
    return json.dumps(st.session_state.configuracoes, indent=2, ensure_ascii=False)

def importar_configuracoes(json_str: str):
    try:
        config = json.loads(json_str)
        st.session_state.configuracoes = config
        return True, "Configurações importadas com sucesso!"
    except Exception as e:
        return False, f"Erro ao importar: {str(e)}"

def validar_conta(conta: str) -> Tuple[bool, str]:
    """Valida o código da conta contábil"""
    if pd.isna(conta) or not str(conta).strip():
        return False, "Código da conta vazio"
    
    conta_limpa = str(conta).strip()
    
    # Aceita números, pontos e vírgulas (vírgula pode ser separador decimal)
    if not all(c.isdigit() or c in ['.', ','] for c in conta_limpa):
        return False, f"Código '{conta_limpa}' contém caracteres inválidos"
    
    # Converter vírgula para ponto se necessário
    conta_limpa = conta_limpa.replace(',', '.')
    
    return True, conta_limpa

def validar_descricao(descricao: str) -> Tuple[bool, str]:
    """Valida a descrição da conta"""
    if pd.isna(descricao) or not str(descricao).strip():
        return False, "Descrição da conta vazia"
    return True, str(descricao).strip()

def validar_classe(classe: str) -> Tuple[bool, str]:
    if pd.isna(classe) or str(classe).strip() == '':
        return True, ''
    classe_str = str(classe).strip()
    if classe_str not in OPCOES_CLASSE:
        return False, f"Classe '{classe}' inválida. Use: 1=Sintética ou 2=Analítica"
    return True, classe_str

def validar_normal(normal: str) -> Tuple[bool, str]:
    if pd.isna(normal) or str(normal).strip() == '':
        return False, "CT1_NORMAL é obrigatório"
    normal_str = str(normal).strip()
    if normal_str not in OPCOES_NORMAL:
        return False, f"CT1_NORMAL '{normal}' inválido. Use: 1=Devedora ou 2=Credora"
    return True, normal_str

def carregar_arquivo(uploaded_file) -> Optional[pd.DataFrame]:
    try:
        df = pd.read_excel(uploaded_file, dtype=str)
        df.columns = df.columns.str.strip()
        df = df.map(lambda x: x.strip() if isinstance(x, str) else x)
        return df
    except Exception as e:
        st.error(f"❌ Erro ao carregar arquivo: {str(e)}")
        return None

def validar_colunas(df: pd.DataFrame) -> Tuple[bool, str]:
    colunas_df = set(df.columns)
    colunas_necessarias = set(COLUNAS_OBRIGATORIAS)
    colunas_faltando = colunas_necessarias - colunas_df
    
    if colunas_faltando:
        return False, f"Colunas obrigatórias faltando: {', '.join(colunas_faltando)}"
    
    return True, "✅ Colunas validadas com sucesso!"

def determinar_classe_automatica(conta: str) -> str:
    """Determina classe baseado no nível hierárquico"""
    if pd.isna(conta) or not str(conta).strip():
        return '2'
    conta_str = str(conta).strip()
    niveis = conta_str.count('.')
    if niveis <= 1:
        return '1'  # Sintética
    else:
        return '2'  # Analítica

def transformar_para_protheus(df: pd.DataFrame, config: Dict[str, Any]) -> Tuple[pd.DataFrame, list]:
    """Transforma DataFrame para o layout COMPLETO do Protheus"""
    # Criar DataFrame com TODAS as colunas do layout
    df_protheus = pd.DataFrame(columns=LAYOUT_FINAL_COMPLETO)
    
    erros = []
    
    # Para cada linha do arquivo original
    for idx, row in df.iterrows():
        linha_num = idx + 2
        nova_linha = {}
        
        # Inicializar todos os campos como vazio
        for col in LAYOUT_FINAL_COMPLETO:
            nova_linha[col] = ''
        
        # ========== MAPEAR CAMPOS DO EXCEL PARA O PROTHEUS ==========
        # CT1_CONTA (código da conta)
        if 'CT1_CONTA' in row:
            conta = row['CT1_CONTA']
            valido, resultado = validar_conta(conta)
            if not valido:
                erros.append(f"Linha {linha_num}: {resultado}")
                nova_linha['CT1_CONTA'] = ''
            else:
                nova_linha['CT1_CONTA'] = resultado
        
        # CT1_DESC01 (descrição)
        if 'CT1_DESC01' in row:
            descricao = row['CT1_DESC01']
            valido, resultado = validar_descricao(descricao)
            if not valido:
                erros.append(f"Linha {linha_num}: {resultado}")
                nova_linha['CT1_DESC01'] = ''
            else:
                nova_linha['CT1_DESC01'] = resultado
        
        # CT1_FILIAL
        if 'CT1_FILIAL' in row and row['CT1_FILIAL']:
            nova_linha['CT1_FILIAL'] = str(row['CT1_FILIAL']).strip()[:2]
        elif config.get('filial_padrao'):
            nova_linha['CT1_FILIAL'] = config['filial_padrao']
        
        # CT1_CLASSE
        if 'CT1_CLASSE' in row and row['CT1_CLASSE']:
            classe = row['CT1_CLASSE']
            valido, resultado = validar_classe(classe)
            if valido and resultado:
                nova_linha['CT1_CLASSE'] = resultado
        if not nova_linha['CT1_CLASSE'] and config.get('aplicar_regras_auto', True):
            nova_linha['CT1_CLASSE'] = determinar_classe_automatica(nova_linha['CT1_CONTA'])
        elif not nova_linha['CT1_CLASSE'] and config.get('classe_padrao'):
            nova_linha['CT1_CLASSE'] = config['classe_padrao']
        
        # CT1_NORMAL
        if 'CT1_NORMAL' in row and row['CT1_NORMAL']:
            normal = row['CT1_NORMAL']
            valido, resultado = validar_normal(normal)
            if valido:
                nova_linha['CT1_NORMAL'] = resultado
        if not nova_linha['CT1_NORMAL']:
            nova_linha['CT1_NORMAL'] = config.get('normal_padrao', '1')
        
        # CT1_BLOQ
        if 'CT1_BLOQ' in row and row['CT1_BLOQ']:
            nova_linha['CT1_BLOQ'] = str(row['CT1_BLOQ']).strip()
        if not nova_linha['CT1_BLOQ']:
            nova_linha['CT1_BLOQ'] = config.get('bloq_padrao', '2')
        
        # CT1_CTASUP (conta superior)
        if 'CT1_CTASUP' in row and row['CT1_CTASUP']:
            nova_linha['CT1_CTASUP'] = str(row['CT1_CTASUP']).strip()
        
        # Valores padrão para campos obrigatórios do Protheus
        nova_linha['CT1_RES'] = ''  # Reservado
        nova_linha['CT1_DC'] = '7'  # Débito/Crédito padrão
        nova_linha['CT1_HP'] = ''   # Histórico padrão
        nova_linha['CT1_DTEXIS'] = '19800101'  # Data de existência padrão
        nova_linha['CT1_ACITEM'] = '1'
        nova_linha['CT1_ACCUST'] = '1'
        nova_linha['CT1_ACCLVL'] = '1'
        
        # Adicionar linha ao DataFrame
        df_protheus.loc[len(df_protheus)] = nova_linha
    
    return df_protheus, erros

def formatar_valor_protheus(valor: str, largura: int) -> str:
    """Formata valor com largura fixa (espaços à direita)"""
    if pd.isna(valor) or valor is None:
        return ' ' * largura
    
    valor_str = str(valor).strip()
    if valor_str == '':
        return ' ' * largura
    
    if len(valor_str) > largura:
        valor_str = valor_str[:largura]
    
    return valor_str.ljust(largura)

def gerar_csv_protheus(df: pd.DataFrame) -> str:
    """
    Gera CSV no formato EXATO do Protheus com TODAS as 79 colunas
    """
    output_lines = []
    
    # Linha 0 - Cabeçalho
    output_lines.append("0;CT1;CVD")
    
    # Linha 1 - Definição dos campos (todos os 79 campos)
    cabecalho_campos = ["1"]
    for col in LAYOUT_FINAL_COMPLETO:
        largura = LARGURAS_CAMPOS.get(col, 20)
        cabecalho_campos.append(f"{col};{largura}")
    output_lines.append(";".join(cabecalho_campos))
    
    # Linhas de dados
    for idx, row in df.iterrows():
        linha_dados = ["1"]
        for col in LAYOUT_FINAL_COMPLETO:
            valor = row[col] if col in row else ''
            valor_formatado = formatar_valor_protheus(valor, LARGURAS_CAMPOS.get(col, 20))
            linha_dados.append(valor_formatado)
        output_lines.append(";".join(linha_dados))
    
    # Linha final
    output_lines.append("2;CVD_FILIAL;CVD_CONTA;CVD_ENTREF;CVD_CODPLA;CVD_VERSAO;CVD_CTAREF;CVD_CUSTO;CVD_CLASSE;CVD_TPUTIL;CVD_NATCTA;CVD_CTASUP")
    
    return "\n".join(output_lines)

def aplicar_filtro(df: pd.DataFrame, termo_busca: str) -> pd.DataFrame:
    if not termo_busca:
        return df
    mask = df.astype(str).apply(
        lambda x: x.str.contains(termo_busca, case=False, na=False)
    ).any(axis=1)
    return df[mask]

def main():
    config = carregar_configuracoes()
    
    st.title("📊 Sistema de Plano de Contas - TOTVS Protheus")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        st.subheader("🏢 Filial")
        filial_input = st.text_input(
            "Filial Padrão",
            value=config.get('filial_padrao', ''),
            max_chars=2,
            placeholder="Ex: 01"
        )
        config['filial_padrao'] = filial_input
        
        st.markdown("---")
        
        st.subheader("📋 Classe da Conta")
        aplicar_auto = st.checkbox(
            "Determinar classe automaticamente",
            value=config.get('aplicar_regras_auto', True)
        )
        config['aplicar_regras_auto'] = aplicar_auto
        
        if not aplicar_auto:
            classe_padrao_select = st.selectbox(
                "Classe Padrão",
                options=['', '1', '2'],
                format_func=lambda x: 'Não preencher' if x == '' else f"{x} - {OPCOES_CLASSE[x]}",
                index=0
            )
            config['classe_padrao'] = classe_padrao_select
        
        st.markdown("---")
        
        st.subheader("⚖️ Natureza da Conta")
        normal_padrao = st.selectbox(
            "CT1_NORMAL Padrão",
            options=['1', '2'],
            format_func=lambda x: f"{x} - {OPCOES_NORMAL[x]}",
            index=0 if config.get('normal_padrao', '1') == '1' else 1
        )
        config['normal_padrao'] = normal_padrao
        
        st.markdown("---")
        
        st.subheader("🔒 Bloqueio")
        bloq_padrao = st.selectbox(
            "CT1_BLOQ Padrão",
            options=['1', '2'],
            format_func=lambda x: f"{x} - {OPCOES_BLOQ[x]}",
            index=1 if config.get('bloq_padrao', '2') == '2' else 0
        )
        config['bloq_padrao'] = bloq_padrao
        
        salvar_configuracoes(config)
        
        st.markdown("---")
        
        with st.expander("📊 Resumo"):
            st.markdown(f"""
            **Filial:** `{config['filial_padrao'] or 'Vazio'}`
            **Classe:** `{'Automática' if config['aplicar_regras_auto'] else config.get('classe_padrao', 'N/A')}`
            **Natureza:** `{config['normal_padrao']}`
            **Bloqueio:** `{config['bloq_padrao']}`
            """)
    
    # Upload
    uploaded_file = st.file_uploader(
        "📂 Selecione o arquivo Excel (.xlsx)",
        type=['xlsx'],
        help="Colunas: CT1_CONTA (código) e CT1_DESC01 (descrição)"
    )
    
    if 'dados_transformados' not in st.session_state:
        st.session_state.dados_transformados = None
    if 'erros_validacao' not in st.session_state:
        st.session_state.erros_validacao = []
    
    if uploaded_file is not None:
        with st.spinner("Carregando arquivo..."):
            df_original = carregar_arquivo(uploaded_file)
        
        if df_original is not None:
            valido, mensagem = validar_colunas(df_original)
            
            if valido:
                st.success(mensagem)
                
                with st.spinner("Transformando dados..."):
                    df_transformado, erros = transformar_para_protheus(df_original, config)
                    st.session_state.dados_transformados = df_transformado
                    st.session_state.erros_validacao = erros
                
                if erros:
                    st.error(f"⚠️ {len(erros)} erro(s) encontrado(s):")
                    with st.expander("Ver erros"):
                        for erro in erros:
                            st.warning(erro)
                else:
                    st.success("✅ Dados validados com sucesso!")
            else:
                st.error(mensagem)
                st.stop()
    
    if st.session_state.dados_transformados is not None:
        df_transformado = st.session_state.dados_transformados
        
        # Mostrar apenas as colunas principais para preview
        colunas_preview = ['CT1_CONTA', 'CT1_DESC01', 'CT1_CLASSE', 'CT1_NORMAL', 'CT1_BLOQ', 'CT1_CTASUP']
        df_preview = df_transformado[colunas_preview]
        
        st.subheader("📋 Preview dos Dados")
        st.dataframe(df_preview, use_container_width=True)
        
        st.info(f"Total de registros: {len(df_transformado)} | Total de colunas no CSV: {len(LAYOUT_FINAL_COMPLETO)}")
        
        # Botão de exportação
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("📥 Gerar CSV para Protheus", type="primary", use_container_width=True):
                try:
                    csv_data = gerar_csv_protheus(st.session_state.dados_transformados)
                    
                    b = BytesIO()
                    b.write(csv_data.encode('latin1'))
                    b.seek(0)
                    
                    st.download_button(
                        label="✅ Baixar CSV",
                        data=b,
                        file_name=f"plano_contas_protheus_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True,
                        key="download_csv"
                    )
                    
                    st.success("✅ CSV gerado com sucesso!")
                    
                    with st.expander("🔍 Preview do CSV gerado (primeiras linhas)"):
                        linhas = csv_data.split('\n')[:5]
                        st.code('\n'.join(linhas), language="text")
                except Exception as e:
                    st.error(f"❌ Erro: {str(e)}")
    
    else:
        st.info("👈 Configure e faça upload de um arquivo Excel para começar")
        
        with st.expander("📋 Exemplo de arquivo válido"):
            st.markdown("""
            **Colunas necessárias no Excel:**
            - `CT1_CONTA` - Código da conta (ex: 1, 1.01, 1.01.001, 111111)
            - `CT1_DESC01` - Descrição da conta (ex: Ativo, Caixa, Bancos)
            
            **Colunas opcionais:**
            - `CT1_CLASSE` - 1=Sintética, 2=Analítica
            - `CT1_NORMAL` - 1=Devedora, 2=Credora
            - `CT1_CTASUP` - Conta superior
            - `CT1_BLOQ` - 1=Bloqueada, 2=Ativa
            - `CT1_FILIAL` - Código da filial
            """)
            
            df_exemplo = pd.DataFrame({
                'CT1_CONTA': ['1', '1.01', '1.01.001', '1.01.002'],
                'CT1_DESC01': ['Ativo', 'Ativo Circulante', 'Caixa', 'Bancos'],
                'CT1_CLASSE': ['1', '1', '2', '2'],
                'CT1_NORMAL': ['1', '1', '1', '1']
            })
            st.dataframe(df_exemplo, use_container_width=True)

if __name__ == "__main__":
    main()