import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# Configuração da página
st.set_page_config(layout="wide", initial_sidebar_state="collapsed")

# --- INICIALIZAÇÃO DOS DADOS ---
# Inicializa contas
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=["Código", "Descrição", "Tipo", "Conta Superior"])

# Inicializa lançamentos
if "lancamentos" not in st.session_state:
    st.session_state.lancamentos = pd.DataFrame(columns=[
        "Data", "Tipo", "Conta Débito", "Conta Crédito", "Histórico", "Valor", "Repetição", "Qtd"
    ])

# Variáveis de controle
if "modo" not in st.session_state:
    st.session_state.modo = None
if "aba" not in st.session_state:
    st.session_state.aba = "contas"

# --- MENU LATERAL ---
with st.sidebar:
    st.title("Menu")
    if st.button("Cadastros"):
        st.session_state.aba = "contas"
    # Indentação visual para submenu
    if st.button("   → Contas"):
        st.session_state.aba = "contas"
    if st.button("Lançamentos"):
        st.session_state.aba = "lanc"

# --- ABA 1: CADASTRO DE CONTAS (PRESERVADO) ---
if st.session_state.aba == "contas":
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
    selecao = st.dataframe(st.session_state.df, use_container_width=True, hide_index=True, on_select="rerun", key="tabela_contas")
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

    # MODO EDITAR (Verifica seleção)
    if st.session_state.modo == "editar" and not linhas_selecionadas:
        st.warning("Selecione uma linha na tabela para editar.")
        st.session_state.modo = None

    # FORMULÁRIO (Incluir ou Editar)
    if st.session_state.modo in ["incluir", "editar"]:
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
            
            lista_superiores = sorted(st.session_state.df["Código"].unique().tolist())
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
                    duplicado = False
                    if st.session_state.modo == "incluir":
                        if codigo in st.session_state.df["Código"].values:
                            duplicado = True
                    elif st.session_state.modo == "editar":
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

# --- ABA 2: LANÇAMENTOS (NOVO) ---
elif st.session_state.aba == "lanc":
    st.title("Lançamentos")

    # 1. FILTROS
    col_f1, col_f2, col_f3 = st.columns([2, 2, 4])
    hoje = datetime.now().date()
    data_ini = col_f1.date_input("Data Inicial", value=hoje - timedelta(days=30))
    data_fim = col_f2.date_input("Data Final", value=hoje)

    st.divider()

    # 2. BOTÕES DE AÇÃO
    col1, col2, col3, col4 = st.columns([1, 1, 1, 6])
    if col1.button("Incluir", key="btn_inc_lanc"):
        st.session_state.modo = "incluir"
        
    if col2.button("Editar", key="btn_edit_lanc"):
        st.session_state.modo = "editar"

    if col3.button("Deletar", key="btn_del_lanc"):
        st.session_state.modo = "deletar"

    st.divider()

    # Filtragem dos dados para exibição
    df_lanc = st.session_state.lancamentos.copy()
    if not df_lanc.empty:
        # Garante que a coluna Data é datetime para comparação
        df_lanc["Data"] = pd.to_datetime(df_lanc["Data"])
        mask = (df_lanc["Data"].dt.date >= data_ini) & (df_lanc["Data"].dt.date <= data_fim)
        df_view = df_lanc.loc[mask]
    else:
        df_view = df_lanc

    # 3. TABELA
    selecao_lanc = st.dataframe(df_view, use_container_width=True, hide_index=True, on_select="rerun", key="tabela_lanc")
    linhas_sel_lanc = selecao_lanc.selection["rows"]

    # Lógica Deletar
    if st.session_state.modo == "deletar":
        if linhas_sel_lanc:
            idx = linhas_sel_lanc[0]
            st.session_state.lancamentos.drop(idx, inplace=True)
            st.session_state.lancamentos.reset_index(drop=True, inplace=True)
            st.success("Lançamento deletado!")
            st.session_state.modo = None
            st.rerun()
        else:
            st.warning("Selecione um lançamento para deletar.")
            st.session_state.modo = None

    # Lógica Editar (verifica seleção)
    if st.session_state.modo == "editar" and not linhas_sel_lanc:
        st.warning("Selecione um lançamento para editar.")
        st.session_state.modo = None

    # FORMULÁRIO DE LANÇAMENTOS
    if st.session_state.modo in ["incluir", "editar"]:
        dados_lanc = {
            "Data": hoje, "Tipo": "Partida Dobrada", "Conta Débito": None, 
            "Conta Crédito": None, "Histórico": "", "Valor": 0.0, 
            "Repetição": None, "Qtd": 1
        }
        idx_edit_lanc = 0

        if st.session_state.modo == "editar" and linhas_sel_lanc:
            # Pega o índice real do dataframe original (considerando filtro)
            # O índice retornado é da view filtrada, precisamos mapear para o original se usarmos filtro
            # Simplificação: O índice retornado é o índice do df_view.
            idx_edit_lanc = df_view.index[linhas_sel_lanc[0]]
            dados_lanc = st.session_state.lancamentos.loc[idx_edit_lanc].to_dict()
            # Converte data para date se necessário
            if pd.notnull(dados_lanc["Data"]):
                dados_lanc["Data"] = pd.to_datetime(dados_lanc["Data"]).date()

        with st.form("form_lanc"):
            col_a, col_b = st.columns(2)
            data_lanc = col_a.date_input("Data", value=dados_lanc["Data"])
            tipo_lanc = col_a.selectbox("Tipo", ["Partida Dobrada", "Débito", "Crédito"], 
                                        index=["Partida Dobrada", "Débito", "Crédito"].index(dados_lanc["Tipo"]))
            
            historico = col_b.text_input("Histórico", value=dados_lanc["Histórico"])
            
            # Lista de contas
            contas_lista = sorted(st.session_state.df["Código"].unique().tolist())

            # Lógica de exibição baseada no tipo
            if tipo_lanc == "Partida Dobrada":
                debito = st.selectbox("Conta Débito", [None] + contas_lista, 
                                      index=0 if not dados_lanc["Conta Débito"] else ([None] + contas_lista).index(dados_lanc["Conta Débito"]))
                credito = st.selectbox("Conta Crédito", [None] + contas_lista,
                                       index=0 if not dados_lanc["Conta Crédito"] else ([None] + contas_lista).index(dados_lanc["Conta Crédito"]))
                valor = st.number_input("Valor", value=float(dados_lanc["Valor"]), min_value=0.0)
                
                # Estrutura para salvar
                dados_para_salvar = {
                    "Data": data_lanc, "Tipo": tipo_lanc, "Conta Débito": debito, 
                    "Conta Crédito": credito, "Histórico": historico, "Valor": valor,
                    "Repetição": None, "Qtd": 1
                }

            else:
                # Tipos Débito ou Crédito: Grid simples
                st.info(f"Modo {tipo_lanc}: Informe as contas e valores abaixo.")
                
                # Simulação de grid simples com múltiplos inputs (simplificado)
                # Não usar data_editor para manter simplicidade de código como solicitado
                
                # Recupera dados existentes se for edição (apenas 1 linha para simplicidade)
                # Se fosse edição de múltiplos, precisaria de lógica mais complexa. 
                # Mantendo simples: 1 conta/valor no formulário principal para edição/inclusão simples.
                
                if tipo_lanc == "Débito":
                    debito = st.selectbox("Conta Débito", [None] + contas_lista, 
                                          index=0 if not dados_lanc["Conta Débito"] else ([None] + contas_lista).index(dados_lanc["Conta Débito"]))
                    credito = None
                else: # Crédito
                    credito = st.selectbox("Conta Crédito", [None] + contas_lista, 
                                           index=0 if not dados_lanc["Conta Crédito"] else ([None] + contas_lista).index(dados_lanc["Conta Crédito"]))
                    debito = None
                
                valor = st.number_input("Valor", value=float(dados_lanc["Valor"]), min_value=0.0)
                st.write(f"Total: {valor:,.2f}")

                dados_para_salvar = {
                    "Data": data_lanc, "Tipo": tipo_lanc, "Conta Débito": debito, 
                    "Conta Crédito": credito, "Histórico": historico, "Valor": valor,
                    "Repetição": None, "Qtd": 1
                }

            # Repetição
            col_r1, col_r2 = st.columns(2)
            rep = col_r1.selectbox("Repetição", [None, "Diário", "Semanal", "Mensal"], 
                                   index=0 if not dados_lanc["Repetição"] else [None, "Diário", "Semanal", "Mensal"].index(dados_lanc["Repetição"]))
            qtd = col_r2.number_input("Quantidade", value=int(dados_lanc["Qtd"]) if dados_lanc["Qtd"] else 1, min_value=1)

            dados_para_salvar["Repetição"] = rep
            dados_para_salvar["Qtd"] = qtd if rep else 1

            salvar = st.form_submit_button("Salvar")
            cancelar = st.form_submit_button("Cancelar")

            if cancelar:
                st.session_state.modo = None
                st.rerun()
            
            if salvar:
                # Validações básicas
                if tipo_lanc == "Partida Dobrada" and (not debito or not credito):
                    st.error("Partida Dobrada exige Conta Débito e Crédito.")
                elif tipo_lanc == "Débito" and not debito:
                    st.error("Informe a Conta Débito.")
                elif tipo_lanc == "Crédito" and not credito:
                    st.error("Informe a Conta Crédito.")
                elif valor <= 0:
                    st.error("Valor deve ser maior que zero.")
                else:
                    # Lógica de repetição (simples)
                    lista_inserir = []
                    dt_base = data_lanc
                    
                    for i in range(dados_para_salvar["Qtd"]):
                        novo = dados_para_salvar.copy()
                        novo["Data"] = dt_base
                        
                        lista_inserir.append(novo)
                        
                        # Incrementa data
                        if rep == "Diário":
                            dt_base = dt_base + timedelta(days=1)
                        elif rep == "Semanal":
                            dt_base = dt_base + timedelta(days=7)
                        elif rep == "Mensal":
                            # Simplificação: adiciona 30 dias
                            dt_base = dt_base + timedelta(days=30)

                    if st.session_state.modo == "editar":
                        # Na edição simples, atualiza apenas a linha base (remove repetições antigas se houver)
                        # Mantendo simples: atualiza apenas o registro selecionado
                        st.session_state.lancamentos.loc[idx_edit_lanc] = dados_para_salvar
                        st.success("Lançamento atualizado!")
                    else:
                        # Inclusão
                        df_novos = pd.DataFrame(lista_inserir)
                        st.session_state.lancamentos = pd.concat([st.session_state.lancamentos, df_novos], ignore_index=True)
                        st.success(f"{len(lista_inserir)} lançamento(s) incluído(s)!")
                    
                    st.session_state.modo = None
                    st.rerun()