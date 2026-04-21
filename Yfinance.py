"""
Sistema de Importação e Exportação de Plano de Contas para TOTVS Protheus
Autor: Senior Python Developer
Versão: 3.0.0 (Formato Protheus Oficial)
"""

import streamlit as st
import pandas as pd
from io import StringIO, BytesIO
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

# Layout final do Protheus (ordem correta das colunas)
LAYOUT_FINAL = [
    'CT1_FILIAL', 'CT1_CONTA', 'CT1_DESC01', 'CT1_DESC02', 
    'CT1_DESC03', 'CT1_CLASSE', 'CT1_NORMAL', 'CT1_CTASUP', 'CT1_BLOQ'
]

# Larguras máximas de cada campo (conforme padrão Protheus)
LARGURAS_CAMPOS = {
    'CT1_FILIAL': 2,
    'CT1_CONTA': 20,
    'CT1_DESC01': 40,
    'CT1_DESC02': 40,
    'CT1_DESC03': 40,
    'CT1_CLASSE': 1,
    'CT1_NORMAL': 1,
    'CT1_CTASUP': 20,
    'CT1_BLOQ': 1
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
    """Salva configurações no session_state"""
    st.session_state.configuracoes = config

def exportar_configuracoes() -> str:
    """Exporta configurações para JSON"""
    return json.dumps(st.session_state.configuracoes, indent=2, ensure_ascii=False)

def importar_configuracoes(json_str: str):
    """Importa configurações de JSON"""
    try:
        config = json.loads(json_str)
        st.session_state.configuracoes = config
        return True, "Configurações importadas com sucesso!"
    except Exception as e:
        return False, f"Erro ao importar: {str(e)}"

def validar_conta(conta: str) -> Tuple[bool, str]:
    """Valida o formato da conta contábil"""
    if pd.isna(conta) or not str(conta).strip():
        return False, "Conta vazia ou inválida"
    
    conta_limpa = str(conta).strip()
    return True, conta_limpa

def validar_classe(classe: str) -> Tuple[bool, str]:
    """Valida se a classe está nas opções permitidas"""
    if pd.isna(classe) or str(classe).strip() == '':
        return True, ''
    
    classe_str = str(classe).strip()
    if classe_str not in OPCOES_CLASSE:
        return False, f"Classe '{classe}' inválida. Use: 1=Sintética ou 2=Analítica"
    
    return True, classe_str

def validar_normal(normal: str) -> Tuple[bool, str]:
    """Valida se a condição normal está nas opções permitidas"""
    if pd.isna(normal) or str(normal).strip() == '':
        return False, "CT1_NORMAL é obrigatório"
    
    normal_str = str(normal).strip()
    if normal_str not in OPCOES_NORMAL:
        return False, f"CT1_NORMAL '{normal}' inválido. Use: 1=Devedora ou 2=Credora"
    
    return True, normal_str

def carregar_arquivo(uploaded_file) -> Optional[pd.DataFrame]:
    """Carrega arquivo Excel e realiza tratamento inicial"""
    try:
        df = pd.read_excel(uploaded_file, dtype=str)
        df.columns = df.columns.str.strip()
        df = df.map(lambda x: x.strip() if isinstance(x, str) else x)
        return df
    except Exception as e:
        st.error(f"❌ Erro ao carregar arquivo: {str(e)}")
        return None

def validar_colunas(df: pd.DataFrame) -> Tuple[bool, str]:
    """Valida se as colunas obrigatórias estão presentes"""
    colunas_df = set(df.columns)
    colunas_necessarias = set(COLUNAS_OBRIGATORIAS)
    colunas_faltando = colunas_necessarias - colunas_df
    
    if colunas_faltando:
        return False, f"Colunas obrigatórias faltando: {', '.join(colunas_faltando)}"
    
    return True, "✅ Colunas validadas com sucesso!"

def determinar_classe_automatica(conta: str) -> str:
    """Sempre retorna '2' (Analítica) como padrão"""
    return '2'

def transformar_para_protheus(df: pd.DataFrame, config: Dict[str, Any]) -> Tuple[pd.DataFrame, list]:
    """Transforma DataFrame para o layout do Protheus"""
    df_protheus = df.copy()
    erros = []
    
    # Garantir que todas as colunas do layout existam (preencher com vazio)
    for coluna in LAYOUT_FINAL:
        if coluna not in df_protheus.columns:
            df_protheus[coluna] = ''
    
    # Validar e aplicar regras de negócio
    for idx in df_protheus.index:
        linha_num = idx + 2
        
        # CT1_CONTA
        conta = df_protheus.at[idx, 'CT1_CONTA']
        valido, resultado = validar_conta(conta)
        if not valido:
            erros.append(f"Linha {linha_num}: {resultado}")
            df_protheus.at[idx, 'CT1_CONTA'] = ''
        else:
            df_protheus.at[idx, 'CT1_CONTA'] = resultado
        
        # CT1_FILIAL
        filial = df_protheus.at[idx, 'CT1_FILIAL']
        if pd.isna(filial) or str(filial).strip() == '':
            df_protheus.at[idx, 'CT1_FILIAL'] = config.get('filial_padrao', '')
        
        # CT1_CLASSE
        classe = df_protheus.at[idx, 'CT1_CLASSE']
        if pd.isna(classe) or str(classe).strip() == '':
            if config.get('aplicar_regras_auto', True):
                df_protheus.at[idx, 'CT1_CLASSE'] = determinar_classe_automatica(df_protheus.at[idx, 'CT1_CONTA'])
            elif config.get('classe_padrao', ''):
                df_protheus.at[idx, 'CT1_CLASSE'] = config.get('classe_padrao')
        else:
            valido, resultado = validar_classe(classe)
            if not valido:
                erros.append(f"Linha {linha_num}: {resultado}")
            else:
                df_protheus.at[idx, 'CT1_CLASSE'] = resultado
        
        # CT1_NORMAL
        normal = df_protheus.at[idx, 'CT1_NORMAL']
        if pd.isna(normal) or str(normal).strip() == '':
            df_protheus.at[idx, 'CT1_NORMAL'] = config.get('normal_padrao', '1')
        else:
            valido, resultado = validar_normal(normal)
            if not valido:
                erros.append(f"Linha {linha_num}: {resultado}")
            else:
                df_protheus.at[idx, 'CT1_NORMAL'] = resultado
        
        # CT1_BLOQ
        bloq = df_protheus.at[idx, 'CT1_BLOQ']
        if pd.isna(bloq) or str(bloq).strip() == '':
            df_protheus.at[idx, 'CT1_BLOQ'] = config.get('bloq_padrao', '2')
        
        # Limpar campos vazios
        for col in ['CT1_DESC02', 'CT1_DESC03', 'CT1_CTASUP']:
            if pd.isna(df_protheus.at[idx, col]):
                df_protheus.at[idx, col] = ''
    
    # Garantir ordem das colunas
    df_protheus = df_protheus[LAYOUT_FINAL]
    df_protheus = df_protheus.reset_index(drop=True)
    
    return df_protheus, erros

def formatar_valor_protheus(valor: str, largura: int) -> str:
    """
    Formata um valor para o padrão Protheus:
    - String com largura fixa (espaços à direita)
    - Valores vazios viram espaços
    """
    if pd.isna(valor) or valor is None:
        return ' ' * largura
    
    valor_str = str(valor).strip()
    if valor_str == '':
        return ' ' * largura
    
    # Se for maior que a largura, trunca
    if len(valor_str) > largura:
        valor_str = valor_str[:largura]
    
    # Preenche com espaços à direita
    return valor_str.ljust(largura)

def gerar_csv_protheus(df: pd.DataFrame) -> str:
    """
    Gera arquivo CSV no formato EXATO que o Protheus espera
    
    Formato:
    Linha 0: 0;CT1;CVD
    Linha 1: 1;CAMPO1;LARGURA1;CAMPO2;LARGURA2;...
    Linhas dados: 1;VALOR1_FORMATADO;VALOR2_FORMATADO;...
    Linha fim: 2;CVD_FILIAL;CVD_CONTA;... (opcional)
    """
    output_lines = []
    
    # Linha 0 - Cabeçalho do tipo de arquivo
    output_lines.append("0;CT1;CVD")
    
    # Linha 1 - Definição dos campos e suas larguras
    cabecalho_campos = ["1"]
    for col in LAYOUT_FINAL:
        largura = LARGURAS_CAMPOS.get(col, 20)
        cabecalho_campos.append(f"{col};{largura}")
    output_lines.append(";".join(cabecalho_campos))
    
    # Linhas de dados
    for idx, row in df.iterrows():
        linha_dados = ["1"]
        for col in LAYOUT_FINAL:
            valor = row[col] if col in row else ''
            valor_formatado = formatar_valor_protheus(valor, LARGURAS_CAMPOS.get(col, 20))
            linha_dados.append(valor_formatado)
        output_lines.append(";".join(linha_dados))
    
    # Linha final (opcional, mas bom ter)
    output_lines.append("2;CVD_FILIAL;CVD_CONTA;CVD_ENTREF;CVD_CODPLA;CVD_VERSAO;CVD_CTAREF;CVD_CUSTO;CVD_CLASSE;CVD_TPUTIL;CVD_NATCTA;CVD_CTASUP")
    
    return "\n".join(output_lines)

def aplicar_filtro(df: pd.DataFrame, termo_busca: str) -> pd.DataFrame:
    """Aplica filtro de busca em todas as colunas"""
    if not termo_busca:
        return df
    
    mask = df.astype(str).apply(
        lambda x: x.str.contains(termo_busca, case=False, na=False)
    ).any(axis=1)
    
    return df[mask]

def main():
    """Função principal do aplicativo"""
    config = carregar_configuracoes()
    
    st.title("📊 Sistema de Plano de Contas - TOTVS Protheus")
    st.markdown("---")
    
    # Sidebar - Configurações
    with st.sidebar:
        st.header("⚙️ Configurações Personalizadas")
        
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
        
        st.subheader("🔒 Bloqueio de Conta")
        bloq_padrao = st.selectbox(
            "CT1_BLOQ Padrão",
            options=['1', '2'],
            format_func=lambda x: f"{x} - {OPCOES_BLOQ[x]}",
            index=1 if config.get('bloq_padrao', '2') == '2' else 0,
            help="Valor usado quando CT1_BLOQ estiver vazio"
        )
        config['bloq_padrao'] = bloq_padrao
        
        salvar_configuracoes(config)
        
        st.markdown("---")
        
        st.subheader("💾 Salvar/Carregar Configurações")
        
        if st.button("📥 Exportar Configurações", use_container_width=True):
            config_json = exportar_configuracoes()
            st.download_button(
                label="💾 Baixar arquivo de configuração",
                data=config_json,
                file_name=f"config_protheus_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                use_container_width=True
            )
        
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
        
        with st.expander("📊 Resumo das Configurações Ativas"):
            st.markdown(f"""
            **Filial Padrão:** `{config['filial_padrao'] if config['filial_padrao'] else 'Vazio'}`
            
            **Classe:**
            - Auto-preencher: `{'Sim' if config['aplicar_regras_auto'] else 'Não'}`
            - Padrão: `{config.get('classe_padrao', 'N/A')}`
            
            **CT1_NORMAL:** `{config['normal_padrao']} - {OPCOES_NORMAL[config['normal_padrao']]}`
            
            **CT1_BLOQ:** `{config['bloq_padrao']} - {OPCOES_BLOQ[config['bloq_padrao']]}`
            """)
    
    # Área principal
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
        with st.spinner("Carregando arquivo..."):
            df_original = carregar_arquivo(uploaded_file)
        
        if df_original is not None:
            valido, mensagem = validar_colunas(df_original)
            
            if valido:
                st.success(mensagem)
                
                with st.spinner("Transformando dados para layout Protheus..."):
                    df_transformado, erros = transformar_para_protheus(df_original, config)
                    st.session_state.dados_transformados = df_transformado
                    st.session_state.erros_validacao = erros
                
                if erros:
                    st.error(f"⚠️ {len(erros)} erro(s) de validação encontrado(s):")
                    with st.expander("Ver erros detalhados"):
                        for erro in erros:
                            st.warning(erro)
                else:
                    st.success("✅ Todos os dados validados com sucesso!")
            else:
                st.error(mensagem)
                st.stop()
        else:
            st.error("❌ Não foi possível carregar o arquivo.")
            st.stop()
    
    # Exibir dados se existirem
    if st.session_state.dados_transformados is not None:
        df_transformado = st.session_state.dados_transformados
        
        tab1, tab2, tab3, tab4 = st.tabs([
            "✏️ Edição de Dados", 
            "👁️ Preview do Layout Final", 
            "📊 Estatísticas",
            "📋 Validações"
        ])
        
        with tab1:
            st.subheader("Dados Editáveis")
            st.caption(f"Total de registros: {len(df_transformado)}")
            
            busca = st.text_input("🔍 Buscar registros", placeholder="Digite para filtrar...")
            df_filtrado = aplicar_filtro(df_transformado, busca)
            
            if len(df_filtrado) < len(df_transformado):
                st.info(f"Mostrando {len(df_filtrado)} de {len(df_transformado)} registros")
            
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
            
            if not edited_df.equals(df_filtrado):
                # Atualizar dados transformados
                for idx_original in range(min(len(df_transformado), len(edited_df))):
                    if idx_original < len(df_transformado):
                        st.session_state.dados_transformados.iloc[idx_original] = edited_df.iloc[idx_original]
                st.rerun()
            
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
            st.caption("Layout que será exportado para o Protheus")
            st.dataframe(st.session_state.dados_transformados, use_container_width=True, height=400)
            
            st.markdown("**Formato do CSV para Protheus:**")
            st.code("""
Linha 0: 0;CT1;CVD
Linha 1: 1;CT1_FILIAL;2;CT1_CONTA;20;CT1_DESC01;40;...
Linhas dados: 1;VALOR;VALOR;...
Linha fim: 2;CVD_FILIAL;CVD_CONTA;...
            """, language="text")
        
        with tab3:
            st.subheader("Estatísticas dos Dados")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total de Registros", len(st.session_state.dados_transformados))
            
            with col2:
                df_temp = st.session_state.dados_transformados.copy()
                df_temp['CT1_CLASSE'] = df_temp['CT1_CLASSE'].replace('', pd.NA)
                classes = df_temp['CT1_CLASSE'].value_counts(dropna=True)
                st.metric("Classes Distintas", len(classes))
            
            with col3:
                normais = st.session_state.dados_transformados['CT1_NORMAL'].value_counts()
                st.metric("Naturezas Distintas", len(normais))
            
            with col4:
                vazios = (st.session_state.dados_transformados['CT1_CLASSE'] == '').sum()
                st.metric("Contas sem Classe", vazios)
            
            # Amostra
            st.subheader("Amostra de Dados (10 primeiros registros)")
            st.dataframe(st.session_state.dados_transformados.head(10), use_container_width=True)
        
        with tab4:
            st.subheader("Validações e Erros")
            
            if st.session_state.erros_validacao:
                st.error(f"❌ {len(st.session_state.erros_validacao)} erro(s) encontrado(s)")
                df_erros = pd.DataFrame({'Erro': st.session_state.erros_validacao})
                st.dataframe(df_erros, use_container_width=True)
                st.warning("⚠️ Corrija os erros antes de exportar o CSV")
            else:
                st.success("✅ Nenhum erro de validação encontrado!")
            
            st.subheader("Verificações Adicionais")
            
            contas_dup = st.session_state.dados_transformados['CT1_CONTA'].duplicated().sum()
            if contas_dup > 0:
                st.warning(f"⚠️ {contas_dup} conta(s) duplicada(s) encontrada(s)")
                df_dup = st.session_state.dados_transformados[
                    st.session_state.dados_transformados['CT1_CONTA'].duplicated(keep=False)
                ].sort_values('CT1_CONTA')
                st.dataframe(df_dup[['CT1_CONTA', 'CT1_DESC01']], use_container_width=True)
            else:
                st.success("✅ Nenhuma conta duplicada")
            
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
        pode_exportar = len(st.session_state.erros_validacao) == 0
        
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("📥 Gerar CSV para Protheus", type="primary", use_container_width=True, disabled=not pode_exportar):
                if not pode_exportar:
                    st.error("❌ Corrija os erros de validação antes de exportar")
                else:
                    try:
                        csv_data = gerar_csv_protheus(st.session_state.dados_transformados)
                        
                        b = BytesIO()
                        b.write(csv_data.encode('latin1'))
                        b.seek(0)
                        
                        st.download_button(
                            label="✅ Baixar arquivo CSV",
                            data=b,
                            file_name=f"plano_contas_protheus_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            use_container_width=True,
                            key="download_csv"
                        )
                        
                        st.success("✅ CSV gerado com sucesso! Pronto para importação no Protheus.")
                        
                        # Mostrar preview do formato gerado
                        with st.expander("🔍 Ver preview do CSV gerado"):
                            st.code(csv_data[:2000] + ("..." if len(csv_data) > 2000 else ""), language="text")
                    except Exception as e:
                        st.error(f"❌ Erro ao gerar CSV: {str(e)}")
            
            if not pode_exportar:
                st.warning("⚠️ Corrija os erros na aba 'Validações' para habilitar a exportação")
    
    else:
        st.info("👈 Configure o sistema na barra lateral e faça upload de um arquivo Excel para começar")
        
        with st.expander("📋 Ver exemplo de layout esperado"):
            st.markdown("""
            ### Colunas obrigatórias no Excel:
            - **CT1_CONTA**: Número da conta contábil
            - **CT1_DESC01**: Descrição da conta
            
            ### Exemplo:
            """)
            
            df_exemplo = pd.DataFrame({
                'CT1_CONTA': ['1.01.001', '1.01.002', '2.01.001'],
                'CT1_DESC01': ['Caixa', 'Bancos', 'Fornecedores'],
                'CT1_NORMAL': ['1', '1', '2']
            })
            st.dataframe(df_exemplo, use_container_width=True)

if __name__ == "__main__":
    main()