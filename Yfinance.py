"""
Sistema de Importação e Exportação de Plano de Contas para TOTVS Protheus
Autor: Senior Python Developer
Versão: 2.0.0 (Com Configurações Personalizadas)
"""

import streamlit as st
import pandas as pd
from io import StringIO, BytesIO
import json
import re
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
LAYOUT_FINAL = [
    'CT1_FILIAL', 'CT1_CONTA', 'CT1_DESC01', 'CT1_DESC02', 
    'CT1_DESC03', 'CT1_CLASSE', 'CT1_NORMAL', 'CT1_CTASUP', 'CT1_BLOQ'
]

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
    """
    Carrega configurações salvas do session_state
    """
    if 'configuracoes' not in st.session_state:
        st.session_state.configuracoes = {
            'filial_padrao': '',
            'aplicar_regras_auto': True,
            'validar_espacos': True,
            'classe_padrao': '',
            'normal_padrao': '1',
            'bloq_padrao': '2'
        }
    return st.session_state.configuracoes

def salvar_configuracoes(config: Dict[str, Any]):
    """
    Salva configurações no session_state
    """
    st.session_state.configuracoes = config
    
def exportar_configuracoes() -> str:
    """
    Exporta configurações para JSON
    """
    return json.dumps(st.session_state.configuracoes, indent=2, ensure_ascii=False)

def importar_configuracoes(json_str: str):
    """
    Importa configurações de JSON
    """
    try:
        config = json.loads(json_str)
        st.session_state.configuracoes = config
        return True, "Configurações importadas com sucesso!"
    except Exception as e:
        return False, f"Erro ao importar: {str(e)}"

def validar_conta(conta: str) -> Tuple[bool, str]:
    """
    Valida o formato da conta contábil
    Remove espaços e valida formato
    
    Args:
        conta: Número da conta
        
    Returns:
        Tuple (válido, mensagem/conta limpa)
    """
    if pd.isna(conta) or not str(conta).strip():
        return False, "Conta vazia ou inválida"
    
    # Remover espaços antes e depois
    conta_limpa = str(conta).strip()
    
    # Verificar se tem espaços no meio (opcional, você pode remover essa validação)
    # if ' ' in conta_limpa:
    #     return False, f"Conta '{conta}' contém espaços internos"
    
    return True, conta_limpa

def validar_classe(classe: str) -> Tuple[bool, str]:
    """
    Valida se a classe está nas opções permitidas
    """
    if pd.isna(classe) or str(classe).strip() == '':
        return True, ''  # Vazio é permitido (será preenchido automaticamente)
    
    classe_str = str(classe).strip()
    if classe_str not in OPCOES_CLASSE:
        return False, f"Classe '{classe}' inválida. Use: 1=Sintética ou 2=Analítica"
    
    return True, classe_str

def validar_normal(normal: str) -> Tuple[bool, str]:
    """
    Valida se a condição normal está nas opções permitidas
    """
    if pd.isna(normal) or str(normal).strip() == '':
        return False, "CT1_NORMAL é obrigatório"
    
    normal_str = str(normal).strip()
    if normal_str not in OPCOES_NORMAL:
        return False, f"CT1_NORMAL '{normal}' inválido. Use: 1=Devedora ou 2=Credora"
    
    return True, normal_str

def carregar_arquivo(uploaded_file) -> Optional[pd.DataFrame]:
    """
    Carrega arquivo Excel e realiza tratamento inicial dos dados
    
    Args:
        uploaded_file: Arquivo enviado pelo usuário
        
    Returns:
        DataFrame tratado ou None em caso de erro
    """
    try:
        # Ler arquivo Excel
        df = pd.read_excel(uploaded_file, dtype=str)
        
        # Remover espaços em branco dos nomes das colunas
        df.columns = df.columns.str.strip()
        
        # Remover espaços em branco dos dados (strings)
        df = df.map(lambda x: x.strip() if isinstance(x, str) else x)
        
        return df
    
    except Exception as e:
        st.error(f"❌ Erro ao carregar arquivo: {str(e)}")
        return None

def validar_colunas(df: pd.DataFrame) -> Tuple[bool, str]:
    """
    Valida se as colunas obrigatórias estão presentes no DataFrame
    
    Args:
        df: DataFrame a ser validado
        
    Returns:
        Tuple (válido, mensagem)
    """
    colunas_df = set(df.columns)
    colunas_necessarias = set(COLUNAS_OBRIGATORIAS)
    
    colunas_faltando = colunas_necessarias - colunas_df
    
    if colunas_faltando:
        return False, f"Colunas obrigatórias faltando: {', '.join(colunas_faltando)}"
    
    return True, "✅ Colunas validadas com sucesso!"

def determinar_classe_automatica(conta: str) -> str:
    """
    Determina a classe da conta baseado no primeiro dígito
    SEMPRE retorna '2' (Analítica) como padrão
    
    Args:
        conta: Número da conta
        
    Returns:
        Classe da conta (sempre '2' para analítica)
    """
    if pd.isna(conta) or not str(conta).strip():
        return '2'
    
    # Sempre retorna Analítica como padrão
    # Se precisar de lógica diferente, pode ajustar aqui
    return '2'

def transformar_para_protheus(
    df: pd.DataFrame, 
    config: Dict[str, Any]
) -> Tuple[pd.DataFrame, list]:
    """
    Transforma DataFrame para o layout do Protheus
    
    Args:
        df: DataFrame original
        config: Configurações do usuário
        
    Returns:
        Tuple (DataFrame transformado, lista de erros)
    """
    # Criar cópia para não modificar original
    df_protheus = df.copy()
    erros = []
    
    # Garantir que todas as colunas do layout existam
    for coluna in LAYOUT_FINAL:
        if coluna not in df_protheus.columns:
            df_protheus[coluna] = ''
    
    # Validar e aplicar regras de negócio
    for idx in df_protheus.index:
        linha_num = idx + 2  # +2 porque Excel começa em 1 e tem cabeçalho
        
        # === CT1_CONTA - OBRIGATÓRIO E SEM ESPAÇOS ===
        conta = df_protheus.at[idx, 'CT1_CONTA']
        valido, resultado = validar_conta(conta)
        if not valido:
            erros.append(f"Linha {linha_num}: {resultado}")
        else:
            df_protheus.at[idx, 'CT1_CONTA'] = resultado
        
        # === CT1_FILIAL ===
        filial = df_protheus.at[idx, 'CT1_FILIAL']
        if pd.isna(filial) or str(filial).strip() == '':
            # Usa configuração do usuário
            df_protheus.at[idx, 'CT1_FILIAL'] = config.get('filial_padrao', '')
        
        # === CT1_CLASSE - Validar e auto-preencher ===
        classe = df_protheus.at[idx, 'CT1_CLASSE']
        if pd.isna(classe) or str(classe).strip() == '':
            # Se vazio e regras automáticas ativas
            if config.get('aplicar_regras_auto', True):
                classe_auto = determinar_classe_automatica(df_protheus.at[idx, 'CT1_CONTA'])
                df_protheus.at[idx, 'CT1_CLASSE'] = classe_auto
            elif config.get('classe_padrao', ''):
                df_protheus.at[idx, 'CT1_CLASSE'] = config.get('classe_padrao')
        else:
            # Validar se está correto
            valido, resultado = validar_classe(classe)
            if not valido:
                erros.append(f"Linha {linha_num}: {resultado}")
            else:
                df_protheus.at[idx, 'CT1_CLASSE'] = resultado
        
        # === CT1_NORMAL - OBRIGATÓRIO ===
        normal = df_protheus.at[idx, 'CT1_NORMAL']
        if pd.isna(normal) or str(normal).strip() == '':
            # Usar padrão da configuração
            df_protheus.at[idx, 'CT1_NORMAL'] = config.get('normal_padrao', '1')
        else:
            # Validar
            valido, resultado = validar_normal(normal)
            if not valido:
                erros.append(f"Linha {linha_num}: {resultado}")
            else:
                df_protheus.at[idx, 'CT1_NORMAL'] = resultado
        
        # === CT1_BLOQ ===
        bloq = df_protheus.at[idx, 'CT1_BLOQ']
        if pd.isna(bloq) or str(bloq).strip() == '':
            df_protheus.at[idx, 'CT1_BLOQ'] = config.get('bloq_padrao', '2')
        
        # === Limpar campos vazios ===
        for col in ['CT1_DESC02', 'CT1_DESC03', 'CT1_CTASUP']:
            if pd.isna(df_protheus.at[idx, col]):
                df_protheus.at[idx, col] = ''
    
    # Garantir ordem das colunas
    df_protheus = df_protheus[LAYOUT_FINAL]
    
    # Resetar índice para evitar problemas com filtros
    df_protheus = df_protheus.reset_index(drop=True)
    
    return df_protheus, erros

def gerar_csv(df: pd.DataFrame) -> str:
    """
    Gera CSV no formato exigido pelo Protheus
    
    Args:
        df: DataFrame a ser exportado
        
    Returns:
        String CSV formatada
    """
    # Substituir NaN por string vazia
    df = df.fillna('')
    
    # Gerar CSV com separador ; e encoding latin1
    output = StringIO()
    df.to_csv(
        output, 
        sep=';', 
        encoding='latin1', 
        index=False,
        quoting=1,  # QUOTE_ALL para garantir compatibilidade
        quotechar='"'
    )
    
    return output.getvalue()

def aplicar_filtro(df: pd.DataFrame, termo_busca: str) -> pd.DataFrame:
    """
    Aplica filtro de busca em todas as colunas
    
    Args:
        df: DataFrame original
        termo_busca: Termo a ser buscado
        
    Returns:
        DataFrame filtrado
    """
    if not termo_busca:
        return df
    
    # Criar máscara de busca em todas as colunas
    mask = df.astype(str).apply(
        lambda x: x.str.contains(termo_busca, case=False, na=False)
    ).any(axis=1)
    
    return df[mask]

def main():
    """
    Função principal do aplicativo
    """
    # Carregar configurações
    config = carregar_configuracoes()
    
    # Título e descrição
    st.title("📊 Sistema de Plano de Contas - TOTVS Protheus")
    st.markdown("---")
    
    # Sidebar - Configurações
    with st.sidebar:
        st.header("⚙️ Configurações Personalizadas")
        
        # === CONFIGURAÇÃO DE FILIAL ===
        st.subheader("🏢 Filial")
        filial_input = st.text_input(
            "Filial Padrão",
            value=config.get('filial_padrao', ''),
            help="Deixe em branco se não quiser preencher automaticamente",
            max_chars=2,
            placeholder="Ex: 01"
        )
        config['filial_padrao'] = filial_input
        
        st.markdown("---")
        
        # === CONFIGURAÇÃO DE CLASSE ===
        st.subheader("📋 Classe da Conta")
        aplicar_auto = st.checkbox(
            "Preencher automaticamente como Analítica",
            value=config.get('aplicar_regras_auto', True),
            help="Preenche automaticamente CT1_CLASSE = 2 (Analítica) quando vazio"
        )
        config['aplicar_regras_auto'] = aplicar_auto
        
        if not aplicar_auto:
            classe_padrao_select = st.selectbox(
                "Classe Padrão (se vazio no Excel)",
                options=['', '1', '2'],
                format_func=lambda x: 'Não preencher' if x == '' else f"{x} - {OPCOES_CLASSE[x]}",
                index=0
            )
            config['classe_padrao'] = classe_padrao_select
        
        st.info("**Opções válidas:**\n- 1 = Sintética (Totalizadora)\n- 2 = Analítica (Recebe Valores)")
        
        st.markdown("---")
        
        # === CONFIGURAÇÃO DE NORMAL ===
        st.subheader("⚖️ Condição Normal (Natureza)")
        normal_padrao = st.selectbox(
            "CT1_NORMAL Padrão",
            options=['1', '2'],
            format_func=lambda x: f"{x} - {OPCOES_NORMAL[x]}",
            index=0 if config.get('normal_padrao', '1') == '1' else 1,
            help="Valor usado quando CT1_NORMAL estiver vazio"
        )
        config['normal_padrao'] = normal_padrao
        
        st.info("**Opções válidas:**\n- 1 = Devedora\n- 2 = Credora")
        
        st.markdown("---")
        
        # === CONFIGURAÇÃO DE BLOQUEIO ===
        st.subheader("🔒 Bloqueio de Conta")
        bloq_padrao = st.selectbox(
            "CT1_BLOQ Padrão",
            options=['1', '2'],
            format_func=lambda x: f"{x} - {OPCOES_BLOQ[x]}",
            index=1 if config.get('bloq_padrao', '2') == '2' else 0,
            help="Valor usado quando CT1_BLOQ estiver vazio"
        )
        config['bloq_padrao'] = bloq_padrao
        
        st.markdown("---")
        
        # === VALIDAÇÕES ===
        st.subheader("✅ Validações")
        validar_espacos = st.checkbox(
            "Validar espaços em CT1_CONTA",
            value=config.get('validar_espacos', True),
            help="Remove espaços antes e depois do número da conta"
        )
        config['validar_espacos'] = validar_espacos
        
        # Salvar configurações
        salvar_configuracoes(config)
        
        st.markdown("---")
        
        # === EXPORTAR/IMPORTAR CONFIGURAÇÕES ===
        st.subheader("💾 Salvar/Carregar Configurações")
        
        # Exportar
        if st.button("📥 Exportar Configurações", use_container_width=True):
            config_json = exportar_configuracoes()
            st.download_button(
                label="💾 Baixar arquivo de configuração",
                data=config_json,
                file_name=f"config_protheus_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                use_container_width=True
            )
        
        # Importar
        uploaded_config = st.file_uploader(
            "📤 Importar Configurações",
            type=['json'],
            help="Carregar arquivo de configuração previamente salvo"
        )
        
        if uploaded_config:
            config_str = uploaded_config.read().decode('utf-8')
            sucesso, msg = importar_configuracoes(config_str)
            if sucesso:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
        
        st.markdown("---")
        
        # === RESUMO DAS CONFIGURAÇÕES ===
        with st.expander("📊 Resumo das Configurações Ativas"):
            st.markdown(f"""
            **Filial Padrão:** `{config['filial_padrao'] if config['filial_padrao'] else 'Vazio'}`
            
            **Classe:**
            - Auto-preencher: `{'Sim' if config['aplicar_regras_auto'] else 'Não'}`
            - Padrão: `{config.get('classe_padrao', 'N/A')}`
            
            **CT1_NORMAL:** `{config['normal_padrao']} - {OPCOES_NORMAL[config['normal_padrao']]}`
            
            **CT1_BLOQ:** `{config['bloq_padrao']} - {OPCOES_BLOQ[config['bloq_padrao']]}`
            
            **Validar Espaços:** `{'Sim' if config['validar_espacos'] else 'Não'}`
            """)
    
    # Área principal - Upload
    col1, col2 = st.columns([2, 1])
    
    with col1:
        uploaded_file = st.file_uploader(
            "📂 Selecione o arquivo Excel (.xlsx)",
            type=['xlsx'],
            help="Arquivo deve conter pelo menos as colunas: CT1_CONTA e CT1_DESC01"
        )
    
    # Inicializar estados da sessão
    if 'dados_transformados' not in st.session_state:
        st.session_state.dados_transformados = None
    if 'erros_validacao' not in st.session_state:
        st.session_state.erros_validacao = []
    
    # Processar arquivo
    if uploaded_file is not None:
        # Carregar arquivo
        with st.spinner("Carregando arquivo..."):
            df_original = carregar_arquivo(uploaded_file)
        
        if df_original is not None:
            # Validar colunas
            valido, mensagem = validar_colunas(df_original)
            
            if valido:
                st.success(mensagem)
                
                # Transformar dados
                with st.spinner("Transformando dados para layout Protheus..."):
                    df_transformado, erros = transformar_para_protheus(df_original, config)
                    st.session_state.dados_transformados = df_transformado
                    st.session_state.erros_validacao = erros
                
                # Mostrar erros se houver
                if erros:
                    st.error(f"⚠️ {len(erros)} erro(s) de validação encontrado(s):")
                    with st.expander("Ver erros detalhados"):
                        for erro in erros:
                            st.warning(erro)
                else:
                    st.success("✅ Todos os dados validados com sucesso!")
                    
            else:
                st.error(mensagem)
                st.info("Por favor, verifique se o arquivo contém as colunas necessárias.")
                st.stop()
        else:
            st.error("❌ Não foi possível carregar o arquivo. Verifique o formato e tente novamente.")
            st.stop()
    
    # Exibir dados se existirem
    if st.session_state.dados_transformados is not None:
        df_transformado = st.session_state.dados_transformados
        
        # Tabs para visualização
        tab1, tab2, tab3, tab4 = st.tabs([
            "✏️ Edição de Dados", 
            "👁️ Preview do Layout Final", 
            "📊 Estatísticas",
            "📋 Validações"
        ])
        
        with tab1:
            st.subheader("Dados Editáveis")
            st.caption(f"Total de registros: {len(df_transformado)}")
            
            # Campo de busca
            busca = st.text_input("🔍 Buscar registros", placeholder="Digite para filtrar...")
            
            # Aplicar filtro
            df_filtrado = aplicar_filtro(df_transformado, busca)
            
            if len(df_filtrado) < len(df_transformado):
                st.info(f"Mostrando {len(df_filtrado)} de {len(df_transformado)} registros")
            
            # Editor de dados
            edited_df = st.data_editor(
                df_filtrado,
                use_container_width=True,
                height=400,
                num_rows="dynamic",
                column_config={
                    "CT1_FILIAL": st.column_config.TextColumn("Filial", max_chars=2),
                    "CT1_CONTA": st.column_config.TextColumn("Conta", required=True, max_chars=20),
                    "CT1_DESC01": st.column_config.TextColumn("Descrição", required=True),
                    "CT1_CLASSE": st.column_config.TextColumn("Classe", help="1=Sintética, 2=Analítica", max_chars=1),
                    "CT1_NORMAL": st.column_config.TextColumn("Normal", help="1=Devedora, 2=Credora", max_chars=1),
                    "CT1_BLOQ": st.column_config.TextColumn("Bloqueada", help="1=Sim, 2=Não", max_chars=1),
                    "CT1_CTASUP": st.column_config.TextColumn("Conta Superior", max_chars=20),
                },
                key="data_editor"
            )
            
            # Atualizar dados transformados
            if not edited_df.equals(df_filtrado):
                if busca:
                    st.session_state.dados_transformados = df_transformado.copy()
                    for idx in edited_df.index:
                        if idx < len(st.session_state.dados_transformados):
                            st.session_state.dados_transformados.iloc[idx] = edited_df.iloc[idx]
                else:
                    st.session_state.dados_transformados = edited_df.copy()
            
            # Botão de ação
            if st.button("🔄 Reaplicar Regras e Validações", use_container_width=True):
                with st.spinner("Reaplicando regras..."):
                    df_revalidado, erros = transformar_para_protheus(
                        st.session_state.dados_transformados,
                        config
                    )
                    st.session_state.dados_transformados = df_revalidado
                    st.session_state.erros_validacao = erros
                    
                    if erros:
                        st.warning(f"⚠️ {len(erros)} erro(s) encontrado(s)")
                    else:
                        st.success("✅ Regras reaplicadas com sucesso!")
                    st.rerun()
        
        with tab2:
            st.subheader("Preview do Layout Final")
            st.caption("Layout exato que será exportado para o Protheus")
            
            # Mostrar preview
            st.dataframe(
                st.session_state.dados_transformados,
                use_container_width=True,
                height=400
            )
            
            # Informações do layout
            st.markdown("**Ordem das colunas no CSV final:**")
            colunas_info = ", ".join(LAYOUT_FINAL)
            st.code(colunas_info, language="text")
        
        with tab3:
            st.subheader("Estatísticas dos Dados")
            
            col1_stat, col2_stat, col3_stat, col4_stat = st.columns(4)
            
            with col1_stat:
                st.metric("Total de Registros", len(st.session_state.dados_transformados))
            
            with col2_stat:
                # Contar classes
                df_temp = st.session_state.dados_transformados.copy()
                df_temp['CT1_CLASSE'] = df_temp['CT1_CLASSE'].replace('', pd.NA)
                classes = df_temp['CT1_CLASSE'].value_counts(dropna=True)
                st.metric("Classes Distintas", len(classes))
            
            with col3_stat:
                # Contar normais
                normais = st.session_state.dados_transformados['CT1_NORMAL'].value_counts()
                st.metric("Naturezas Distintas", len(normais))
            
            with col4_stat:
                # Contas sem classe
                vazios = (st.session_state.dados_transformados['CT1_CLASSE'] == '').sum()
                st.metric("Contas sem Classe", vazios)
            
            # Distribuição de classes
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                if len(classes) > 0:
                    st.subheader("Distribuição por Classe")
                    df_classes = pd.DataFrame({
                        'Classe': [f"{k} - {OPCOES_CLASSE.get(k, 'Outro')}" for k in classes.index],
                        'Quantidade': classes.values
                    })
                    st.bar_chart(df_classes.set_index('Classe'))
            
            with col_chart2:
                if len(normais) > 0:
                    st.subheader("Distribuição por Natureza")
                    df_normais = pd.DataFrame({
                        'Normal': [f"{k} - {OPCOES_NORMAL.get(k, 'Outro')}" for k in normais.index],
                        'Quantidade': normais.values
                    })
                    st.bar_chart(df_normais.set_index('Normal'))
            
            # Amostra de dados
            st.subheader("Amostra de Dados (10 primeiros registros)")
            st.dataframe(
                st.session_state.dados_transformados.head(10),
                use_container_width=True
            )
        
        with tab4:
            st.subheader("Validações e Erros")
            
            if st.session_state.erros_validacao:
                st.error(f"❌ {len(st.session_state.erros_validacao)} erro(s) encontrado(s)")
                
                # Mostrar erros em DataFrame
                df_erros = pd.DataFrame({
                    'Erro': st.session_state.erros_validacao
                })
                st.dataframe(df_erros, use_container_width=True)
                
                st.warning("⚠️ Corrija os erros antes de exportar o CSV")
            else:
                st.success("✅ Nenhum erro de validação encontrado!")
                st.info("Todos os dados estão prontos para exportação.")
            
            # Verificações adicionais
            st.subheader("Verificações Adicionais")
            
            # Contas duplicadas
            contas_dup = st.session_state.dados_transformados['CT1_CONTA'].duplicated().sum()
            if contas_dup > 0:
                st.warning(f"⚠️ {contas_dup} conta(s) duplicada(s) encontrada(s)")
                df_dup = st.session_state.dados_transformados[
                    st.session_state.dados_transformados['CT1_CONTA'].duplicated(keep=False)
                ].sort_values('CT1_CONTA')
                st.dataframe(df_dup[['CT1_CONTA', 'CT1_DESC01']], use_container_width=True)
            else:
                st.success("✅ Nenhuma conta duplicada")
            
            # Campos vazios obrigatórios
            campos_vazios = []
            if (st.session_state.dados_transformados['CT1_CONTA'] == '').any():
                campos_vazios.append("CT1_CONTA")
            if (st.session_state.dados_transformados['CT1_DESC01'] == '').any():
                campos_vazios.append("CT1_DESC01")
            
            if campos_vazios:
                st.error(f"❌ Campos obrigatórios vazios: {', '.join(campos_vazios)}")
            else:
                st.success("✅ Todos os campos obrigatórios preenchidos")
        
        # Botão de exportação
        st.markdown("---")
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
        
        with col_btn2:
            # Verificar se pode exportar
            pode_exportar = len(st.session_state.erros_validacao) == 0
            
            if st.button(
                "📥 Gerar CSV para Protheus", 
                type="primary", 
                use_container_width=True,
                disabled=not pode_exportar
            ):
                if not pode_exportar:
                    st.error("❌ Corrija os erros de validação antes de exportar")
                else:
                    try:
                        # Gerar CSV
                        csv_data = gerar_csv(st.session_state.dados_transformados)
                        
                        # Criar arquivo para download
                        b = BytesIO()
                        b.write(csv_data.encode('latin1'))
                        b.seek(0)
                        
                        # Botão de download
                        st.download_button(
                            label="✅ Clique aqui para baixar o arquivo",
                            data=b,
                            file_name=f"plano_contas_protheus_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            use_container_width=True,
                            key="download_csv"
                        )
                        
                        st.success("✅ CSV gerado com sucesso! Pronto para importação no Protheus.")
                    except Exception as e:
                        st.error(f"❌ Erro ao gerar CSV: {str(e)}")
            
            if not pode_exportar:
                st.warning("⚠️ Corrija os erros na aba 'Validações' para habilitar a exportação")
    
    else:
        # Exibir instruções quando nenhum arquivo foi carregado
        st.info("👈 Configure o sistema na barra lateral e faça upload de um arquivo Excel para começar")
        
        # Exemplo de layout esperado
        with st.expander("📋 Ver exemplo de layout esperado"):
            st.markdown("""
            ### Colunas obrigatórias no Excel:
            - **CT1_CONTA**: Número da conta contábil (sem espaços antes/depois)
            - **CT1_DESC01**: Descrição da conta
            
            ### Colunas opcionais (serão preenchidas automaticamente conforme configurações):
            - **CT1_FILIAL**: Filial (conforme configuração)
            - **CT1_CLASSE**: 1=Sintética, 2=Analítica
            - **CT1_NORMAL**: 1=Devedora, 2=Credora (obrigatório)
            - **CT1_BLOQ**: 1=Bloqueada, 2=Ativa
            - **CT1_CTASUP**: Conta Superior (hierarquia)
            - **CT1_DESC02**: Descrição complementar
            - **CT1_DESC03**: Descrição complementar
            
            ### Exemplo de arquivo válido:
            """)
            
            # Criar exemplo de DataFrame
            df_exemplo = pd.DataFrame({
                'CT1_CONTA': ['1.01.001', '1.01.002', '2.01.001', '4.01.001'],
                'CT1_DESC01': ['Caixa', 'Bancos', 'Fornecedores', 'Vendas de Produtos'],
                'CT1_CLASSE': ['2', '2', '2', '2'],
                'CT1_NORMAL': ['1', '1', '2', '2'],
                'CT1_CTASUP': ['1.01', '1.01', '2.01', '4.01']
            })
            
            st.dataframe(df_exemplo, use_container_width=True)
            
            st.markdown("""
            💡 **Dicas importantes:**
            - Configure a filial e valores padrão na barra lateral
            - O sistema remove automaticamente espaços das contas
            - CT1_NORMAL é obrigatório (1=Devedora ou 2=Credora)
            - CT1_CLASSE pode ser preenchido automaticamente
            - Salve suas configurações para reutilizar depois
            """)

if __name__ == "__main__":
    main()