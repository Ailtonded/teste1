import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# Configuração da página
st.set_page_config(layout="wide", initial_sidebar_state="collapsed")

# --- INICIALIZAÇÃO DOS DADOS ---
# Inicializa contas
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=["Código", "Descrição", "Tipo", "Conta Superior"])

# Inicializa lançamentos (lista de dicionários)
# Estrutura: {'id': int, 'data': date, 'historico': str, 'linhas': list[dict]}
if "lancamentos" not in st.session_state:
    st.session_state.lancamentos = []
    st.session_state.next_id = 1

# Variáveis de controle de interface
if "modo" not in st.session_state:
    st.session_state.modo = None
if "aba" not in st.session_state:
    st.session_state.aba = "contas"

# --- MENU LATERAL ---
with st.sidebar:
    st.title("Menu")
    if st.button("Cadastros"):
        st.session_state.aba = "contas"
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

# --- ABA 2: LANÇAMENTOS (CORRIGIDO) ---
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
        # Limpa dados de edição anteriores
        if "edit_lanc_id" in st.session_state:
            del st.session_state.edit_lanc_id
        
    if col2.button("Editar", key="btn_edit_lanc"):
        st.session_state.modo = "editar"

    if col3.button("Deletar", key="btn_del_lanc"):
        st.session_state.modo = "deletar"

    st.divider()

    # Prepara DataFrame para visualização
    # Converte a lista de lançamentos para um DataFrame plano para exibição
    rows = []
    for lanc in st.session_state.lancamentos:
        rows.append({
            "ID": lanc['id'],
            "Data": lanc['data'],
            "Histórico": lanc['historico'],
            "Linhas": f"{len(lanc['linhas'])} itens"
        })
    
    df_view_lanc = pd.DataFrame(rows)
    if not df_view_lanc.empty:
        df_view_lanc["Data"] = pd.to_datetime(df_view_lanc["Data"])
        mask = (df_view_lanc["Data"].dt.date >= data_ini) & (df_view_lanc["Data"].dt.date <= data_fim)
        df_view_lanc = df_view_lanc.loc[mask]
        # Converter de volta para string para exibição limpa
        df_view_lanc["Data"] = df_view_lanc["Data"].dt.strftime("%d/%m/%Y")

    # 3. TABELA DE VISUALIZAÇÃO
    # Exibe ID, Data, Histórico e Resumo
    selecao_lanc = st.dataframe(
        df_view_lanc[["ID", "Data", "Histórico", "Linhas"]] if not df_view_lanc.empty else pd.DataFrame(columns=["ID", "Data", "Histórico", "Linhas"]), 
        use_container_width=True, 
        hide_index=True, 
        on_select="rerun", 
        key="tabela_lanc"
    )
    linhas_sel_lanc = selecao_lanc.selection["rows"]

    # Lógica Deletar
    if st.session_state.modo == "deletar":
        if linhas_sel_lanc:
            # Pega o ID real pelo índice da view filtrada
            id_del = df_view_lanc.iloc[linhas_sel_lanc[0]]["ID"]
            # Filtra a lista original removendo o ID
            st.session_state.lancamentos = [x for x in st.session_state.lancamentos if x['id'] != id_del]
            st.success("Lançamento deletado!")
            st.session_state.modo = None
            st.rerun()
        else:
            st.warning("Selecione um lançamento para deletar.")
            st.session_state.modo = None

    # Lógica Editar (verifica seleção)
    if st.session_state.modo == "editar":
        if linhas_sel_lanc:
            # Guarda o ID que está sendo editado
            id_edit = df_view_lanc.iloc[linhas_sel_lanc[0]]["ID"]
            st.session_state.edit_lanc_id = id_edit
        else:
            st.warning("Selecione um lançamento para editar.")
            st.session_state.modo = None

    # FORMULÁRIO DE LANÇAMENTOS (INCLUIR / EDITAR)
    if st.session_state.modo in ["incluir", "editar"]:
        titulo_form = "Novo Lançamento"
        dados_form = {"data": hoje, "historico": ""}
        linhas_iniciais = []

        # Se for edição, carrega dados
        if st.session_state.modo == "editar" and "edit_lanc_id" in st.session_state:
            titulo_form = "Editar Lançamento"
            # Busca dados originais
            for l in st.session_state.lancamentos:
                if l['id'] == st.session_state.edit_lanc_id:
                    dados_form = l
                    linhas_iniciais = l['linhas']
                    break
        
        with st.form("form_lanc"):
            col_cab = st.columns([2, 6])
            data_lanc = col_cab[0].date_input("Data", value=dados_form['data'])
            historico = col_cab[1].text_input("Histórico", value=dados_form['historico'])

            st.subheader("Itens do Lançamento")
            
            # GRID EDITÁVEL
            # Define colunas
            column_config = {
                "Tipo": st.column_config.SelectboxColumn(
                    options=["Débito", "Crédito"],
                    required=True,
                    width="small"
                ),
                "Conta": st.column_config.SelectboxColumn(
                    options=sorted(st.session_state.df["Código"].unique().tolist()),
                    required=True,
                    width="medium"
                ),
                "Valor": st.column_config.NumberColumn(
                    format="R$ %.2f",
                    required=True,
                    min_value=0.0,
                    width="medium"
                )
            }

            # Dataframe temporário para o editor
            df_editor = pd.DataFrame(linhas_iniciais)
            if df_editor.empty:
                # Cria linhas vazias padrão para começar
                df_editor = pd.DataFrame({"Tipo": ["", ""], "Conta": ["", ""], "Valor": [0.0, 0.0]})

            # Exibe o editor
            df_itens = st.data_editor(
                df_editor,
                column_config=column_config,
                num_rows="dynamic", # Permite adicionar/remover linhas
                use_container_width=True,
                hide_index=True,
                key="editor_grid"
            )

            # Cálculo dos totais
            total_debito = df_itens[df_itens['Tipo'] == 'Débito']['Valor'].sum()
            total_credito = df_itens[df_itens['Tipo'] == 'Crédito']['Valor'].sum()

            # Exibe totais
            col_tot1, col_tot2, col_tot3 = st.columns([2, 2, 4])
            col_tot1.metric("Total Débito", f"R$ {total_debito:,.2f}")
            col_tot2.metric("Total Crédito", f"R$ {total_credito:,.2f}")

            # Validação visual
            if total_debito != total_credito:
                col_tot1.error("Diferente!")
                col_tot2.error("Diferente!")
            
            st.divider()

            # Botões do form
            salvar = st.form_submit_button("Salvar", type="primary")
            cancelar = st.form_submit_button("Cancelar")

            if cancelar:
                # Limpa estado
                st.session_state.modo = None
                if "edit_lanc_id" in st.session_state:
                    del st.session_state.edit_lanc_id
                st.rerun()

            if salvar:
                # VALIDAÇÃO FINAL
                erro = False
                
                # 1. Valida Soma
                if total_debito != total_credito:
                    st.error("❌ Erro: A soma dos Débitos deve ser igual a soma dos Créditos.")
                    erro = True
                
                # 2. Valida preenchimento
                # Remove linhas completamente vazias
                df_valid = df_itens.dropna(how='all')
                # Verifica se sobrou algo
                if df_valid.empty:
                    st.error("❌ Erro: Adicione pelo menos uma linha de débito e uma de crédito.")
                    erro = True
                else:
                    # Verifica campos nulos nas linhas preenchidas parcialmente
                    if df_valid[['Tipo', 'Conta', 'Valor']].isnull().values.any():
                        st.error("❌ Erro: Preencha todos os campos (Tipo, Conta, Valor) em todas as linhas.")
                        erro = True
                
                # 3. Validação de partidas dobradas (lógica simples)
                tipos_presentes = df_valid['Tipo'].unique()
                if len(df_valid) > 0 and ("Débito" not in tipos_presentes or "Crédito" not in tipos_presentes):
                    st.error("❌ Erro: O lançamento deve conter pelo menos um débito e um crédito.")
                    erro = True

                if not erro:
                    # Prepara lista de linhas
                    novas_linhas = df_valid.to_dict('records')
                    
                    if st.session_state.modo == "incluir":
                        novo = {
                            "id": st.session_state.next_id,
                            "data": data_lanc,
                            "historico": historico,
                            "linhas": novas_linhas
                        }
                        st.session_state.lancamentos.append(novo)
                        st.session_state.next_id += 1
                        st.success("Lançamento salvo com sucesso!")
                    else:
                        # Atualiza existente
                        for i, l in enumerate(st.session_state.lancamentos):
                            if l['id'] == st.session_state.edit_lanc_id:
                                st.session_state.lancamentos[i] = {
                                    "id": st.session_state.edit_lanc_id,
                                    "data": data_lanc,
                                    "historico": historico,
                                    "linhas": novas_linhas
                                }
                                break
                        st.success("Lançamento atualizado com sucesso!")
                    
                    # Limpa estado e recarrega
                    st.session_state.modo = None
                    if "edit_lanc_id" in st.session_state:
                        del st.session_state.edit_lanc_id
                    st.rerun()