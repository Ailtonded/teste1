import streamlit as st
import pandas as pd

# --- CONFIGURAÇÕES DA PÁGINA ---
# Layout wide e sidebar recolhida conforme requisitos
st.set_page_config(
    layout="wide", 
    page_title="Plano de Contas",
    initial_sidebar_state="collapsed",
    page_icon="📊"
)

# --- ESTILOS CSS CUSTOMIZADOS (UX/ERP) ---
# Melhora a aparência dos botões e tabela para parecer um sistema ERP
st.markdown("""
<style>
    /* Botões de ação maiores e com margem */
    .stButton button {
        min-width: 120px;
        font-weight: bold;
        margin-right: 10px;
    }
    /* Destaque para linhas selecionadas não é nativo, mas melhoramos o dataframe */
    .stDataFrame {
        border: 1px solid #ddd;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# --- INICIALIZAÇÃO DO SESSION_STATE ---
if 'df_contas' not in st.session_state:
    st.session_state.df_contas = pd.DataFrame(columns=['Código', 'Descrição', 'Tipo', 'Conta Superior'])

# Variáveis de controle de estado do formulário
if 'form_mode' not in st.session_state:
    st.session_state.form_mode = None  # Valores: None, 'incluir', 'editar'
    
# ID da conta sendo editada (índice do DataFrame)
if 'edit_index' not in st.session_state:
    st.session_state.edit_index = None

# --- FUNÇÕES DE LÓGICA ---

def obter_contas_superiores(codigo_atual=None):
    """Retorna lista de códigos para o dropdown 'Conta Superior'.
    Remove a própria conta atual para evitar autorreferência na edição."""
    df = st.session_state.df_contas
    if df.empty:
        return []
    
    # Pega todas as contas, mas remove a conta que está sendo editada (se houver)
    lista = df['Código'].unique().tolist()
    if st.session_state.form_mode == 'editar' and codigo_atual in lista:
        lista.remove(codigo_atual)
        
    return sorted(lista)

def incluir_conta(codigo, descricao, tipo, conta_superior):
    """Adiciona nova conta ao DataFrame."""
    novo_registro = {
        'Código': codigo,
        'Descrição': descricao,
        'Tipo': tipo,
        'Conta Superior': conta_superior if conta_superior else None
    }
    st.session_state.df_contas = pd.concat(
        [st.session_state.df_contas, pd.DataFrame([novo_registro])], 
        ignore_index=True
    )

def atualizar_conta(index, codigo, descricao, tipo, conta_superior):
    """Atualiza uma conta existente pelo índice."""
    st.session_state.df_contas.at[index, 'Código'] = codigo
    st.session_state.df_contas.at[index, 'Descrição'] = descricao
    st.session_state.df_contas.at[index, 'Tipo'] = tipo
    st.session_state.df_contas.at[index, 'Conta Superior'] = conta_superior if conta_superior else None

def deletar_conta(index):
    """Remove uma conta pelo índice."""
    st.session_state.df_contas.drop(index, inplace=True)
    st.session_state.df_contas.reset_index(drop=True, inplace=True)

def resetar_formulario():
    """Reseta o estado do formulário para o inicial."""
    st.session_state.form_mode = None
    st.session_state.edit_index = None

# --- MENU LATERAL (SIDEBAR) ---
with st.sidebar:
    st.title("⚙️ Menu")
    st.divider()
    # Usando st.navigation ou menu simples para simular a estrutura "Cadastros -> Contas"
    menu_selecionado = st.radio(
        "Navegação",
        options=["Cadastros", "Sair"],
        index=0,
        label_visibility="collapsed"
    )
    
    if menu_selecionado == "Cadastros":
        st.subheader("Cadastros")
        if st.button("Contas", use_container_width=True, type="primary"):
            # Mantém na mesma tela (neste app simples, não há navegação entre páginas)
            pass
    
    st.divider()
    st.caption("v1.0.0")

# --- CORPO PRINCIPAL DO APLICATIVO ---

st.title("Cadastro de Contas Contábeis")
st.markdown("Gerencie o plano de contas do balanço patrimonial.")

# 1. TOPO DA TELA (AÇÕES)
col_acoes = st.columns([1, 1, 1, 6])
with col_acoes[0]:
    if st.button("➕ Incluir", type="primary"):
        resetar_formulario() # Limpa estado anterior
        st.session_state.form_mode = 'incluir'

with col_acoes[1]:
    # Botão Editar só ativa se uma linha estiver selecionada (implementado via dataframe abaixo)
    # Como st.dataframe não retorna seleção nativa facilmente, usaremos um estado temporário para seleção
    btn_editar = st.button("✏️ Editar")
    
with col_acoes[2]:
    btn_deletar = st.button("🗑️ Deletar", type="secondary")

st.divider()

# 2. MANIPULAÇÃO DE DADOS E EXIBIÇÃO DO FORMULÁRIO

# Lógica para capturar seleção do dataframe (usando o novo recurso on_select)
# 'ignore' evita erros se clicar fora
selection = st.dataframe(
    st.session_state.df_contas,
    use_container_width=True,
    hide_index=True,
    column_config={"Código": st.column_config.TextColumn(width="small")},
    on_select="rerun", # Recarrega o app ao selecionar linha
    key="df_selection"
)

# Verifica se há linhas selecionadas
indices_selecionados = selection['selection']['rows']

# Lógica do Botão Editar
if btn_editar:
    if not indices_selecionados:
        st.warning("⚠️ Selecione uma linha na tabela para editar.")
    else:
        resetar_formulario()
        st.session_state.form_mode = 'editar'
        st.session_state.edit_index = indices_selecionados[0]
        st.rerun() # Força atualização para mostrar o formulário

# Lógica do Botão Deletar
if btn_deletar:
    if not indices_selecionados:
        st.warning("⚠️ Selecione uma linha na tabela para deletar.")
    else:
        idx_del = indices_selecionados[0]
        conta_removida = st.session_state.df_contas.at[idx_del, 'Código']
        deletar_conta(idx_del)
        resetar_formulario()
        st.success(f"✅ Conta '{conta_removida}' removida com sucesso!")
        st.rerun()

# --- FORMULÁRIO (INCLUIR / EDITAR) ---
# Só exibe o formulário se o modo estiver ativo
if st.session_state.form_mode in ['incluir', 'editar']:
    
    # Carrega dados existentes se for edição
    dados_conta = {
        'Código': '',
        'Descrição': '',
        'Tipo': 'Sintética',
        'Conta Superior': None
    }
    
    if st.session_state.form_mode == 'editar' and st.session_state.edit_index is not None:
        idx = st.session_state.edit_index
        if idx in st.session_state.df_contas.index:
            dados_conta = st.session_state.df_contas.loc[idx].to_dict()
    
    # Container do Formulário (destacado)
    with st.container(border=True):
        titulo_form = "🆕 Nova Conta" if st.session_state.form_mode == 'incluir' else f"✏️ Editando Conta: {dados_conta['Código']}"
        st.subheader(titulo_form)
        
        with st.form("form_conta", clear_on_submit=False):
            col1, col2 = st.columns(2)
            
            with col1:
                # Se estiver editando, o código pode ser readonly ou editável (definido como editável aqui)
                input_codigo = st.text_input("Código *", value=dados_conta['Código'], placeholder="Ex: 1.1.01")
                input_tipo = st.selectbox("Tipo *", ["Sintética", "Analítica"], index=0 if dados_conta['Tipo'] == 'Sintética' else 1)
            
            with col2:
                input_desc = st.text_input("Descrição *", value=dados_conta['Descrição'], placeholder="Ex: Ativo Circulante")
                
                # Lista de superiores (excluindo a si mesmo na edição)
                lista_sup = obter_contas_superiores(dados_conta['Código'])
                # Prepara o índice padrão do selectbox
                index_sup = 0
                if dados_conta['Conta Superior'] in lista_sup:
                    index_sup = lista_sup.index(dados_conta['Conta Superior']) + 1 # +1 por causa da opção vazia
                elif dados_conta['Conta Superior'] is None:
                    index_sup = 0
                
                input_superior = st.selectbox(
                    "Conta Superior", 
                    options=[None] + lista_sup,
                    index=index_sup,
                    help="Selecione a conta pai ou deixe vazio para conta raiz."
                )
            
            # Botões do Formulário
            col_btn = st.columns([1, 1, 4])
            submitted = st.form_submit_button("💾 Salvar", type="primary", use_container_width=True)
            cancelar = col_btn[1].form_submit_button("❌ Cancelar", use_container_width=True)
            
            if cancelar:
                resetar_formulario()
                st.rerun()
                
            if submitted:
                # VALIDAÇÕES
                if not input_codigo or not input_desc:
                    st.error("❌ Código e Descrição são obrigatórios.")
                else:
                    # Verifica duplicidade de código (apenas para inclusão ou se mudou o código na edição)
                    is_duplicated = False
                    if st.session_state.form_mode == 'incluir':
                        if input_codigo in st.session_state.df_contas['Código'].values:
                            is_duplicated = True
                    elif st.session_state.form_mode == 'editar':
                        # Verifica se o novo código já existe em outra linha
                        df_temp = st.session_state.df_contas.drop(st.session_state.edit_index)
                        if input_codigo in df_temp['Código'].values:
                            is_duplicated = True
                    
                    if is_duplicated:
                        st.error(f"❌ O código '{input_codigo}' já está em uso.")
                    else:
                        # SALVAR
                        if st.session_state.form_mode == 'incluir':
                            incluir_conta(input_codigo, input_desc, input_tipo, input_superior)
                            st.success(f"✅ Conta '{input_codigo}' incluída com sucesso!")
                        else:
                            atualizar_conta(st.session_state.edit_index, input_codigo, input_desc, input_tipo, input_superior)
                            st.success(f"✅ Conta '{input_codigo}' atualizada com sucesso!")
                        
                        resetar_formulario()
                        st.rerun()