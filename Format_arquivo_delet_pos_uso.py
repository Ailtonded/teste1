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
if "lancamentos" not in st.session_state:
    st.session_state.lancamentos = []
    st.session_state.next_id = 1

# Variáveis de controle
if "modo" not in st.session_state:
    st.session_state.modo = None
if "aba" not in st.session_state:
    st.session_state.aba = "contas"
if "edit_id" not in st.session_state:
    st.session_state.edit_id = None

# --- MENU LATERAL ---
with st.sidebar:
    st.title("Menu")
    if st.button("Cadastros"):
        st.session_state.aba = "contas"
    if st.button("   → Contas"):
        st.session_state.aba = "contas"
    if st.button("Lançamentos"):
        st.session_state.aba = "lanc"
    if st.button("Balancete"):
        st.session_state.aba = "balancete"

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

# --- ABA 2: LANÇAMENTOS (COM EXPANDER) ---
elif st.session_state.aba == "lanc":
    st.title("Lançamentos")

    # --- 1. ÁREA DE CADASTRO (DENTRO DO EXPANDER) ---
    # Se estiver editando, o expander deve vir aberto
    expanded_state = True if st.session_state.edit_id is not None else False
    
    with st.expander("Cadastrar Novo Lançamento", expanded=expanded_state):
        
        # Estado inicial do formulário
        data_padrao = datetime.now().date()
        hist_padrao = ""
        itens_padrao = []
        
        # Se estiver em modo edição, carrega dados
        if st.session_state.edit_id is not None:
            st.info(f"Editando Lançamento ID: {st.session_state.edit_id}")
            for l in st.session_state.lancamentos:
                if l['id'] == st.session_state.edit_id:
                    data_padrao = l['data']
                    hist_padrao = l['historico']
                    itens_padrao = l['itens']
                    break
        
        # Formulário
        with st.form("form_lancamento"):
            col1, col2 = st.columns([1, 3])
            data_lanc = col1.date_input("Data", value=data_padrao)
            historico = col2.text_input("Histórico", value=hist_padrao)
            
            st.markdown("**Itens do Lançamento**")
            
            # Grid Editável
            df_itens = pd.DataFrame(itens_padrao)
            if df_itens.empty:
                df_itens = pd.DataFrame({"Tipo": ["", ""], "Conta": ["", ""], "Valor": [0.0, 0.0]})
                
            lista_contas = sorted(st.session_state.df["Código"].unique().tolist())
            
            editor_result = st.data_editor(
                df_itens,
                column_config={
                    "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Débito", "Crédito"], required=True),
                    "Conta": st.column_config.SelectboxColumn("Conta", options=lista_contas, required=True),
                    "Valor": st.column_config.NumberColumn("Valor", format="R$ %.2f", min_value=0.0, required=True)
                },
                num_rows="dynamic",
                hide_index=True,
                use_container_width=True,
                key="editor_lanc"
            )
            
            # Cálculo dos totais
            total_debito = editor_result[editor_result['Tipo'] == 'Débito']['Valor'].sum()
            total_credito = editor_result[editor_result['Tipo'] == 'Crédito']['Valor'].sum()
            
            col_t1, col_t2 = st.columns(2)
            col_t1.metric("Total Débitos", f"R$ {total_debito:,.2f}")
            col_t2.metric("Total Créditos", f"R$ {total_credito:,.2f}")
            
            if total_debito != total_credito:
                st.error("⚠️ As somas de Débito e Crédito devem ser iguais para salvar.")
            
            # Botões
            col_btn = st.columns([1, 1, 4])
            btn_salvar = col_btn[0].form_submit_button("Salvar", type="primary")
            btn_cancelar = col_btn[1].form_submit_button("Cancelar")
            
            if btn_cancelar:
                st.session_state.edit_id = None
                st.rerun()
                
            if btn_salvar:
                valido = True
                if total_debito != total_credito:
                    valido = False
                    st.error("Débitos diferente de Créditos.")
                
                df_check = editor_result.dropna(how='all')
                if df_check.empty:
                    valido = False
                    st.error("Nenhum item informado.")
                else:
                    if df_check.isnull().values.any():
                        valido = False
                        st.error("Preencha todos os campos das linhas.")
                    
                    tipos = df_check['Tipo'].unique()
                    if "Débito" not in tipos or "Crédito" not in tipos:
                        valido = False
                        st.error("Lançamento deve ter pelo menos um Débito e um Crédito.")

                if valido:
                    lista_itens = df_check.to_dict('records')
                    
                    if st.session_state.edit_id is None:
                        novo = {
                            "id": st.session_state.next_id,
                            "data": data_lanc,
                            "historico": historico,
                            "itens": lista_itens
                        }
                        st.session_state.lancamentos.append(novo)
                        st.session_state.next_id += 1
                        st.success("Lançamento salvo!")
                    else:
                        for i, l in enumerate(st.session_state.lancamentos):
                            if l['id'] == st.session_state.edit_id:
                                st.session_state.lancamentos[i]['data'] = data_lanc
                                st.session_state.lancamentos[i]['historico'] = historico
                                st.session_state.lancamentos[i]['itens'] = lista_itens
                                break
                        st.success("Lançamento atualizado!")
                        st.session_state.edit_id = None
                    
                    st.rerun()

    st.divider()

    # --- 2. GRID DE VISUALIZAÇÃO (FORA DO EXPANDER) ---
    st.subheader("Lançamentos Gravados")
    
    # Filtros
    col_f1, col_f2 = st.columns(2)
    hoje = datetime.now().date()
    f_data_ini = col_f1.date_input("Data Inicial (>=)", value=hoje - timedelta(days=30), key="f_ini")
    f_data_fim = col_f2.date_input("Data Final (<=)", value=hoje, key="f_fim")
    
    # Botões de Ação
    col_ac1, col_ac2, col_ac3 = st.columns([1, 1, 6])
    if col_ac1.button("Editar Selecionado"):
        if "sel_lanc" in st.session_state and st.session_state.sel_lanc and st.session_state.sel_lanc['selection']['rows']:
            # Pega o ID da linha selecionada
            idx_sel = st.session_state.sel_lanc['selection']['rows'][0]
            # Como o dataframe de visualização é filtrado, precisamos mapear o ID correto
            # Simplificação: o dataframe de visualição tem coluna ID
            # O indice da seleção é o indice do df_view, não o ID.
            # Para simplificar, vamos recriar a lógica de visualização aqui para pegar o ID
            
            # Reconstrói view para pegar o ID correto
            temp_rows = []
            for l in st.session_state.lancamentos:
                if f_data_ini <= l['data'] <= f_data_fim:
                    temp_rows.append({"ID": l['id']})
            
            if temp_rows:
                df_temp_ids = pd.DataFrame(temp_rows)
                id_selecionado = df_temp_ids.iloc[idx_sel]['ID']
                st.session_state.edit_id = id_selecionado
                st.rerun()
        else:
            st.warning("Selecione uma linha.")
            
    if col_ac2.button("Deletar Selecionado"):
        if "sel_lanc" in st.session_state and st.session_state.sel_lanc and st.session_state.sel_lanc['selection']['rows']:
            idx_sel = st.session_state.sel_lanc['selection']['rows'][0]
            # Lógica similar ao editar para encontrar o ID
            temp_rows = []
            for l in st.session_state.lancamentos:
                if f_data_ini <= l['data'] <= f_data_fim:
                    temp_rows.append({"ID": l['id']})
            
            if temp_rows:
                df_temp_ids = pd.DataFrame(temp_rows)
                id_selecionado = df_temp_ids.iloc[idx_sel]['ID']
                st.session_state.lancamentos = [x for x in st.session_state.lancamentos if x['id'] != id_selecionado]
                st.success("Deletado!")
                st.rerun()
        else:
            st.warning("Selecione uma linha.")

    # Preparar dados para exibição
    rows_view = []
    for l in st.session_state.lancamentos:
        if f_data_ini <= l['data'] <= f_data_fim:
            debitos = [f"{x['Conta']} ({x['Valor']:.2f})" for x in l['itens'] if x['Tipo'] == 'Débito']
            creditos = [f"{x['Conta']} ({x['Valor']:.2f})" for x in l['itens'] if x['Tipo'] == 'Crédito']
            total = sum([x['Valor'] for x in l['itens'] if x['Tipo'] == 'Débito'])
            
            rows_view.append({
                "ID": l['id'],
                "Data": l['data'].strftime("%d/%m/%Y"),
                "Histórico": l['historico'],
                "Débitos": ", ".join(debitos),
                "Créditos": ", ".join(creditos),
                "Valor Total": total
            })
            
    df_view = pd.DataFrame(rows_view)
    
    if df_view.empty:
        st.info("Nenhum lançamento encontrado.")
    else:
        st.dataframe(
            df_view, 
            use_container_width=True, 
            hide_index=True, 
            on_select="rerun", 
            selection_mode="single-row",
            key="sel_lanc"
        )

# --- ABA 3: BALANCETE (NOVO) ---
elif st.session_state.aba == "balancete":
    st.title("Balancete de Verificação")
    
    # Filtros
    col_f1, col_f2 = st.columns(2)
    hoje = datetime.now().date()
    f_data_ini = col_f1.date_input("Data Inicial", value=hoje - timedelta(days=365), key="b_ini")
    f_data_fim = col_f2.date_input("Data Final", value=hoje, key="b_fim")
    
    st.divider()
    
    if st.session_state.df.empty:
        st.warning("Nenhuma conta cadastrada.")
    else:
        # 1. Inicializar dicionário de saldos
        saldos = {}
        for cod in st.session_state.df['Código']:
            saldos[cod] = {"Debito": 0.0, "Credito": 0.0}
        
        # 2. Calcular valores das contas ANALÍTICAS (diretamente dos lançamentos)
        for l in st.session_state.lancamentos:
            if f_data_ini <= l['data'] <= f_data_fim:
                for item in l['itens']:
                    conta = item['Conta']
                    valor = item['Valor']
                    tipo = item['Tipo']
                    
                    # Verifica se a conta existe no cadastro (segurança)
                    if conta in saldos:
                        if tipo == "Débito":
                            saldos[conta]['Debito'] += valor
                        else:
                            saldos[conta]['Credito'] += valor
        
        # 3. Calcular valores das contas SINTÉTICAS (hierarquia)
        # Ordenar códigos do maior nível para o menor (inverso)
        # Nível = quantidade de pontos + 1
        codigos_ordenados = sorted(
            st.session_state.df['Código'].unique(), 
            key=lambda x: x.count('.'), 
            reverse=True
        )
        
        # Mapear contas para encontrar filhas
        # Para cada conta, somar os valores das filhas DIRETAS
        
        for cod_pai in codigos_ordenados:
            # Encontra o tipo da conta
            tipo_conta = st.session_state.df.loc[st.session_state.df['Código'] == cod_pai, 'Tipo'].values[0]
            
            if tipo_conta == "Sintética":
                # Zera valores atuais (para garantir soma limpa, embora analíticas já tenham valor)
                # Para sintéticas, vamos calcular "bottom-up"
                
                # Lógica para encontrar filhas diretas:
                # Filhas começam com cod_pai + "." e tem apenas um nível a mais
                
                filhas_diretas = []
                nivel_pai = cod_pai.count('.')
                prefixo_pai = cod_pai + "."
                
                for cod_filha in saldos.keys():
                    if cod_filha.startswith(prefixo_pai):
                        nivel_filha = cod_filha.count('.')
                        if nivel_filha == nivel_pai + 1:
                            filhas_diretas.append(cod_filha)
                
                # Somar valores das filhas
                soma_d = 0.0
                soma_c = 0.0
                for filha in filhas_diretas:
                    soma_d += saldos[filha]['Debito']
                    soma_c += saldos[filha]['Credito']
                
                saldos[cod_pai]['Debito'] = soma_d
                saldos[cod_pai]['Credito'] = soma_c
        
        # 4. Montar DataFrame de visualização
        lista_balancete = []
        total_geral_d = 0.0
        total_geral_c = 0.0
        
        # Ordenar por código para exibição
        codigos_exibicao = sorted(st.session_state.df['Código'].unique())
        
        for cod in codigos_exibicao:
            # Pega descrição e tipo
            row_conta = st.session_state.df.loc[st.session_state.df['Código'] == cod].iloc[0]
            desc = row_conta['Descrição']
            tipo = row_conta['Tipo']
            
            val_d = saldos[cod]['Debito']
            val_c = saldos[cod]['Credito']
            saldo = val_d - val_c
            
            # Adicionar linha
            lista_balancete.append({
                "Código": cod,
                "Descrição": desc,
                "Tipo": tipo,
                "Débito": val_d if val_d > 0 else 0.0, # Mostrar 0 ou valor
                "Crédito": val_c if val_c > 0 else 0.0,
                "Saldo": saldo
            })
            
            # Totalizar (apenas para visualização, se necessário)
            # Em balancete, o total geral soma tudo (incluindo sintéticas se não for filtrado)
            # Para balancete correto, somamos apenas as contas de nível mais alto (raízes) ou todas se quisermos o total movimentado.
            # Aqui vamos somar tudo para conferência do duplo registro (Total Déb == Total Cred)
            total_geral_d += val_d
            total_geral_c += val_c
            
        df_balancete = pd.DataFrame(lista_balancete)
        
        # Exibir
        st.dataframe(
            df_balancete.style.format({"Débito": "R$ {:,.2f}", "Crédito": "R$ {:,.2f}", "Saldo": "R$ {:,.2f}"}),
            use_container_width=True,
            hide_index=True
        )
        
        st.divider()
        col_t1, col_t2 = st.columns(2)
        col_t1.metric("Total Débitos", f"R$ {total_geral_d:,.2f}")
        col_t2.metric("Total Créditos", f"R$ {total_geral_c:,.2f}")
        
        if abs(total_geral_d - total_geral_c) < 0.01:
            st.success("Balancete OK (D = C)")
        else:
            st.error("Balancete com diferença!")