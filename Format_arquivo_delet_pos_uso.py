import streamlit as st
import pandas as pd

# Configuração da página
st.set_page_config(layout="wide", initial_sidebar_state="collapsed")

# Inicializa dados na sessão se estiver vazio
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=["Código", "Descrição", "Tipo", "Conta Superior"])

# Variável de controle para o estado do formulário (None, 'incluir', 'editar')
if "modo" not in st.session_state:
    st.session_state.modo = None

# --- MENU LATERAL ---
with st.sidebar:
    st.title("Menu")
    st.button("Cadastros")
    st.button("Contas")

# --- INTERFACE PRINCIPAL ---
st.title("Cadastro de Contas")

# 1. BOTÕES DE AÇÃO
col1, col2, col3, col4 = st.columns([1, 1, 1, 6])
if col1.button("Incluir"):
    st.session_state.modo = "incluir"
    
if col2.button("Editar"):
    st.session_state.modo = "editar"

if col3.button("Deletar"):
    st.session_state.modo = "deletar"

st.divider()

# 2. LÓGICA E FORMULÁRIO

# Seleção de linha na tabela
selecao = st.dataframe(st.session_state.df, use_container_width=True, hide_index=True, on_select="rerun", key="tabela")
linhas_selecionadas = selecao.selection["rows"]

# MODO DELETAR
if st.session_state.modo == "deletar":
    if linhas_selecionadas:
        idx = linhas_selecionadas[0]
        st.session_state.df.drop(idx, inplace=True)
        st.session_state.df.reset_index(drop=True, inplace=True)
        st.success("Conta deletada com sucesso!")
        st.session_state.modo = None
        st.rerun()
    else:
        st.warning("Selecione uma linha para deletar.")
        st.session_state.modo = None

# MODO EDITAR (Verifica seleção antes de mostrar o formulário)
if st.session_state.modo == "editar" and not linhas_selecionadas:
    st.warning("Selecione uma linha na tabela para editar.")
    st.session_state.modo = None

# FORMULÁRIO (Incluir ou Editar)
if st.session_state.modo in ["incluir", "editar"]:
    # Dados iniciais (vazio para incluir, preenchido para editar)
    dados_iniciais = {"Código": "", "Descrição": "", "Tipo": "Sintética", "Conta Superior": None}
    idx_edit = 0
    
    if st.session_state.modo == "editar" and linhas_selecionadas:
        idx_edit = linhas_selecionadas[0]
        dados_iniciais = st.session_state.df.loc[idx_edit].to_dict()

    with st.form("form_conta"):
        c1, c2 = st.columns(2)
        codigo = c1.text_input("Código *", value=dados_iniciais["Código"])
        tipo = c1.selectbox("Tipo", ["Sintética", "Analítica"], index=0 if dados_iniciais["Tipo"] == "Sintética" else 1)
        
        descricao = c2.text_input("Descrição *", value=dados_iniciais["Descrição"])
        
        # Lista para o selectbox de Conta Superior
        lista_superiores = sorted(st.session_state.df["Código"].unique().tolist())
        # Na edição, remove a própria conta da lista de superiores para evitar ciclo
        if st.session_state.modo == "editar" and codigo in lista_superiores:
            lista_superiores.remove(codigo)
            
        conta_sup = c2.selectbox("Conta Superior", [None] + lista_superiores, index=0 if not dados_iniciais["Conta Superior"] else ([None] + lista_superiores).index(dados_iniciais["Conta Superior"]))
        
        salvar = st.form_submit_button("Salvar")
        cancelar = st.form_submit_button("Cancelar")
        
        if cancelar:
            st.session_state.modo = None
            st.rerun()
            
        if salvar:
            if not codigo or not descricao:
                st.error("Código e Descrição são obrigatórios.")
            else:
                # Verifica duplicidade (apenas na inclusão ou se alterou código na edição)
                duplicado = False
                if st.session_state.modo == "incluir":
                    if codigo in st.session_state.df["Código"].values:
                        duplicado = True
                elif st.session_state.modo == "editar":
                    # Verifica se o novo código já existe em outra linha
                    temp_df = st.session_state.df.drop(idx_edit)
                    if codigo in temp_df["Código"].values:
                        duplicado = True
                
                if duplicado:
                    st.error("Código já cadastrado.")
                else:
                    nova_linha = {"Código": codigo, "Descrição": descricao, "Tipo": tipo, "Conta Superior": conta_sup}
                    
                    if st.session_state.modo == "incluir":
                        st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([nova_linha])], ignore_index=True)
                        st.success("Conta incluída!")
                    else:
                        st.session_state.df.loc[idx_edit] = nova_linha
                        st.success("Conta atualizada!")
                    
                    st.session_state.modo = None
                    st.rerun()