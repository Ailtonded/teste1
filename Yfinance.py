"""
Sistema de Importação e Exportação de Plano de Contas para TOTVS Protheus11
Autor: Senior Python Developer
Versão: 1.1.0 (Corrigida)
"""

import streamlit as st
import pandas as pd
from io import StringIO, BytesIO
import re
from typing import Tuple, Optional, Dict, Any

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

VALORES_PADRAO = {
    'CT1_FILIAL': '01',
    'CT1_DESC02': '',
    'CT1_DESC03': '',
    'CT1_NORMAL': '1',
    'CT1_BLOQ': '2',
    'CT1_CTASUP': ''
}

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
        
        # Remover espaços em branco dos dados (strings) - CORRIGIDO: map ao invés de applymap
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

def determinar_classe(conta: str) -> str:
    """
    Determina a classe da conta baseado no primeiro dígito
    
    Args:
        conta: Número da conta
        
    Returns:
        Classe da conta
    """
    if pd.isna(conta) or not str(conta).strip():
        return ''
    
    primeiro_digito = str(conta).strip()[0]
    
    # Regras de classe baseadas no primeiro dígito
    mapeamento_classe = {
        '1': '1',  # Ativo
        '2': '2',  # Passivo
        '3': '3',  # Patrimônio Líquido
        '4': '4',  # Receita
        '5': '5',  # Despesa
        '6': '6',  # Custo
        '7': '7',  # Resultado
        '8': '8',  # Compensação
        '9': '9'   # Contas de Controle
    }
    
    return mapeamento_classe.get(primeiro_digito, '')

def transformar_para_protheus(
    df: pd.DataFrame, 
    aplicar_regras_auto: bool = True
) -> pd.DataFrame:
    """
    Transforma DataFrame para o layout do Protheus
    
    Args:
        df: DataFrame original
        aplicar_regras_auto: Aplicar regras automáticas de classe
        
    Returns:
        DataFrame transformado
    """
    # Criar cópia para não modificar original
    df_protheus = df.copy()
    
    # Garantir que todas as colunas do layout existam
    for coluna in LAYOUT_FINAL:
        if coluna not in df_protheus.columns:
            df_protheus[coluna] = VALORES_PADRAO.get(coluna, '')
    
    # Aplicar regras de negócio - CORRIGIDO: usando iterrows de forma mais eficiente
    for idx in df_protheus.index:
        # CT1_FILIAL (padrão 01 se vazio)
        if pd.isna(df_protheus.at[idx, 'CT1_FILIAL']) or str(df_protheus.at[idx, 'CT1_FILIAL']).strip() == '':
            df_protheus.at[idx, 'CT1_FILIAL'] = '01'
        
        # CT1_NORMAL (padrão 1 se vazio)
        if pd.isna(df_protheus.at[idx, 'CT1_NORMAL']) or str(df_protheus.at[idx, 'CT1_NORMAL']).strip() == '':
            df_protheus.at[idx, 'CT1_NORMAL'] = '1'
        
        # CT1_BLOQ (padrão 2 se vazio)
        if pd.isna(df_protheus.at[idx, 'CT1_BLOQ']) or str(df_protheus.at[idx, 'CT1_BLOQ']).strip() == '':
            df_protheus.at[idx, 'CT1_BLOQ'] = '2'
        
        # Limpar campos vazios
        for col in ['CT1_DESC02', 'CT1_DESC03', 'CT1_CTASUP']:
            if pd.isna(df_protheus.at[idx, col]):
                df_protheus.at[idx, col] = ''
        
        # Determinar classe automaticamente se habilitado
        if aplicar_regras_auto:
            if pd.isna(df_protheus.at[idx, 'CT1_CLASSE']) or str(df_protheus.at[idx, 'CT1_CLASSE']).strip() == '':
                classe = determinar_classe(df_protheus.at[idx, 'CT1_CONTA'])
                df_protheus.at[idx, 'CT1_CLASSE'] = classe
    
    # Garantir ordem das colunas
    df_protheus = df_protheus[LAYOUT_FINAL]
    
    # Resetar índice para evitar problemas com filtros
    df_protheus = df_protheus.reset_index(drop=True)
    
    return df_protheus

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
    # Título e descrição
    st.title("📊 Sistema de Plano de Contas - TOTVS Protheus")
    st.markdown("---")
    
    # Sidebar - Configurações
    with st.sidebar:
        st.header("⚙️ Configurações")
        aplicar_regras = st.checkbox(
            "Aplicar regras automáticas",
            value=True,
            help="Determinar automaticamente a classe da conta baseado no primeiro dígito"
        )
        
        st.markdown("---")
        st.header("📋 Regras de Negócio")
        st.markdown("""
        - **CT1_FILIAL**: Padrão '01'
        - **CT1_NORMAL**: Padrão '1'
        - **CT1_BLOQ**: Padrão '2'
        - **CT1_CLASSE**: Determinado pelo 1º dígito da conta
            - 1 → Ativo
            - 2 → Passivo
            - 3 → PL
            - 4 → Receita
            - 5 → Despesa
            - 6 → Custo
            - 7 → Resultado
            - 8 → Compensação
            - 9 → Contas de Controle
        """)
        
        st.markdown("---")
        st.header("📤 Exportação")
        st.markdown("""
        Formato do CSV:
        - Separador: `;`
        - Encoding: `latin1`
        - Colunas fixas ordenadas
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
                    df_transformado = transformar_para_protheus(
                        df_original, 
                        aplicar_regras_auto=aplicar_regras
                    )
                    st.session_state.dados_transformados = df_transformado
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
            tab1, tab2, tab3 = st.tabs([
                "✏️ Edição de Dados", 
                "👁️ Preview do Layout Final", 
                "📊 Estatísticas"
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
                
                # Editor de dados - CORRIGIDO: melhor gestão de edições
                edited_df = st.data_editor(
                    df_filtrado,
                    use_container_width=True,
                    height=400,
                    num_rows="dynamic",
                    column_config={
                        "CT1_CONTA": st.column_config.TextColumn("Conta", required=True),
                        "CT1_DESC01": st.column_config.TextColumn("Descrição", required=True),
                        "CT1_CLASSE": st.column_config.TextColumn("Classe", help="1-9: Classe da conta"),
                        "CT1_FILIAL": st.column_config.TextColumn("Filial"),
                        "CT1_NORMAL": st.column_config.TextColumn("Normal", help="1=Débito, 2=Crédito"),
                        "CT1_BLOQ": st.column_config.TextColumn("Bloqueada", help="1=Sim, 2=Não"),
                    },
                    key="data_editor"
                )
                
                # Atualizar dados transformados - CORRIGIDO: lógica simplificada
                if not edited_df.equals(df_filtrado):
                    if busca:
                        # Com filtro: atualizar apenas os registros visíveis
                        st.session_state.dados_transformados = df_transformado.copy()
                        for idx in edited_df.index:
                            if idx < len(st.session_state.dados_transformados):
                                st.session_state.dados_transformados.iloc[idx] = edited_df.iloc[idx]
                    else:
                        # Sem filtro: substituir todos os dados
                        st.session_state.dados_transformados = edited_df.copy()
                
                # Botão de ação
                if st.button("🔄 Reaplicar Regras de Classe", use_container_width=True):
                    with st.spinner("Reaplicando regras..."):
                        st.session_state.dados_transformados = transformar_para_protheus(
                            st.session_state.dados_transformados,
                            aplicar_regras_auto=True
                        )
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
                
                col1_stat, col2_stat, col3_stat = st.columns(3)
                
                with col1_stat:
                    st.metric("Total de Registros", len(st.session_state.dados_transformados))
                
                with col2_stat:
                    # Contar contas por classe - CORRIGIDO: tratamento de valores vazios
                    df_temp = st.session_state.dados_transformados.copy()
                    df_temp['CT1_CLASSE'] = df_temp['CT1_CLASSE'].replace('', pd.NA)
                    classes = df_temp['CT1_CLASSE'].value_counts(dropna=True)
                    st.metric("Classes Distintas", len(classes))
                
                with col3_stat:
                    # Verificar registros com classe vazia - CORRIGIDO
                    vazios = (st.session_state.dados_transformados['CT1_CLASSE'] == '').sum()
                    st.metric("Contas sem Classe", vazios)
                
                # Distribuição de classes
                if len(classes) > 0:
                    st.subheader("Distribuição por Classe")
                    # Criar DataFrame com nomes das classes
                    nomes_classes = {
                        '1': 'Ativo',
                        '2': 'Passivo',
                        '3': 'PL',
                        '4': 'Receita',
                        '5': 'Despesa',
                        '6': 'Custo',
                        '7': 'Resultado',
                        '8': 'Compensação',
                        '9': 'Contas de Controle'
                    }
                    df_classes = pd.DataFrame({
                        'Classe': [f"{k} - {nomes_classes.get(k, 'Outros')}" for k in classes.index],
                        'Quantidade': classes.values
                    })
                    st.bar_chart(df_classes.set_index('Classe'))
                
                # Amostra de dados
                st.subheader("Amostra de Dados (10 primeiros registros)")
                st.dataframe(
                    st.session_state.dados_transformados.head(10),
                    use_container_width=True
                )
            
            # Botão de exportação
            st.markdown("---")
            col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
            
            with col_btn2:
                if st.button("📥 Gerar CSV para Protheus", type="primary", use_container_width=True):
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
                            file_name="plano_contas_protheus.csv",
                            mime="text/csv",
                            use_container_width=True,
                            key="download_csv"
                        )
                        
                        st.success("✅ CSV gerado com sucesso! Pronto para importação no Protheus.")
                    except Exception as e:
                        st.error(f"❌ Erro ao gerar CSV: {str(e)}")
    
    else:
        # Exibir instruções quando nenhum arquivo foi carregado
        st.info("👈 Faça upload de um arquivo Excel para começar")
        
        # Exemplo de layout esperado
        with st.expander("📋 Ver exemplo de layout esperado"):
            st.markdown("""
            ### Colunas obrigatórias:
            - **CT1_CONTA**: Número da conta contábil
            - **CT1_DESC01**: Descrição da conta
            
            ### Colunas opcionais (com valores padrão):
            - CT1_FILIAL (padrão: '01')
            - CT1_DESC02 (padrão: vazio)
            - CT1_DESC03 (padrão: vazio)
            - CT1_CLASSE (pode ser automático)
            - CT1_NORMAL (padrão: '1')
            - CT1_CTASUP (padrão: vazio)
            - CT1_BLOQ (padrão: '2')
            
            ### Exemplo de arquivo válido:
            """)
            
            # Criar exemplo de DataFrame
            df_exemplo = pd.DataFrame({
                'CT1_CONTA': ['1.01.001', '1.01.002', '2.01.001', '4.01.001'],
                'CT1_DESC01': ['Caixa', 'Bancos', 'Fornecedores', 'Vendas de Produtos'],
                'CT1_CLASSE': ['1', '1', '2', '4']
            })
            
            st.dataframe(df_exemplo, use_container_width=True)
            
            st.markdown("""
            💡 **Dica**: Você pode criar este arquivo no Excel com as colunas acima e salvá-lo como .xlsx
            """)

if __name__ == "__main__":
    main()
