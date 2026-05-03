import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
import base64
import hashlib

# --- FUNÇÕES DE CRIPTOGRAFIA ---
def gerar_chave(senha: str) -> bytes:
    return hashlib.sha256(senha.encode('utf-8')).digest()

def criptografar(texto: str, senha: str) -> str:
    try:
        chave = gerar_chave(senha)
        dados = texto.encode('utf-8')
        dados_cripto = bytes([d ^ chave[i % len(chave)] for i, d in enumerate(dados)])
        return base64.b64encode(dados_cripto).decode('utf-8')
    except Exception:
        return ""

def descriptografar(texto_cripto: str, senha: str) -> str | None:
    try:
        chave = gerar_chave(senha)
        dados = base64.b64decode(texto_cripto)
        dados_decripto = bytes([d ^ chave[i % len(chave)] for i, d in enumerate(dados)])
        return dados_decripto.decode('utf-8')
    except Exception:
        return None

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Sistema Contábil", layout="wide", initial_sidebar_state="expanded")

# --- INICIALIZAÇÃO DO ESTADO ---
if "df" not in st.session_state or not isinstance(st.session_state.df, pd.DataFrame):
    st.session_state.df = pd.DataFrame(columns=["Código", "Descrição", "Tipo", "Conta Superior", "Categoria"])

if "lancamentos" not in st.session_state:
    st.session_state.lancamentos = []
    st.session_state.next_id = 1

if "modo" not in st.session_state:
    st.session_state.modo = None
if "edit_id" not in st.session_state:
    st.session_state.edit_id = None

# --- MENU LATERAL (REFACTORED) ---
with st.sidebar:
    st.title("⚡ Menu Principal")
    
    menu_opcoes = [
        "Cadastro de Contas", 
        "Lançamentos", 
        "Balancete", 
        "DRE", 
        "Backup"
    ]
    
    selected = st.radio(
        "Navegação", 
        menu_opcoes, 
        label_visibility="collapsed"
    )

# --- LÓGICA DE NAVEGAÇÃO ---
if selected == "Cadastro de Contas":
    # --- CABEÇALHO ---
    st.title("📒 Cadastro de Contas")
    st.markdown("Gerencie o Plano de Contas (Ativo, Passivo, Receitas, Despesas).")

    # --- AÇÕES ---
    col1, col2, col3, _ = st.columns([1, 1, 1, 6])
    
    # Usamos session_state para controlar o fluxo sem poluir a tela
    if col1.button("➕ Incluir", use_container_width=True):
        st.session_state.modo = "incluir"
        
    if col2.button("✏️ Editar", use_container_width=True):
        st.session_state.modo = "editar"

    if col3.button("🗑️ Deletar", use_container_width=True):
        st.session_state.modo = "deletar"

    st.divider()

    # --- TABELA ---
    st.subheader("Contas Cadastradas")
    
    # Configuração visual da tabela
    df_display = st.session_state.df.style.format({"Categoria": lambda x: x if pd.notna(x) else "-"})
    
    selecao = st.dataframe(
        st.session_state.df, 
        use_container_width=True, 
        hide_index=True, 
        on_select="rerun", 
        key="tabela_contas",
        column_config={
            "Código": st.column_config.TextColumn("Código", width="small"),
            "Descrição": st.column_config.TextColumn("Descrição", width="medium"),
            "Tipo": st.column_config.TextColumn("Tipo", width="small"),
            "Categoria": st.column_config.TextColumn("Categoria", width="small")
        }
    )
    
    linhas_selecionadas = selecao.selection["rows"]

    # --- LÓGICA DE AÇÕES ---
    if st.session_state.modo == "deletar":
        if linhas_selecionadas:
            idx = linhas_selecionadas[0]
            conta_nome = st.session_state.df.loc[idx, 'Descrição']
            st.warning(f"⚠️ Confirmação: Deseja deletar a conta **{conta_nome}**?")
            col_del, _ = st.columns([1, 5])
            if col_del.button("Confirmar Exclusão", type="primary"):
                st.session_state.df.drop(idx, inplace=True)
                st.session_state.df.reset_index(drop=True, inplace=True)
                st.session_state.modo = None
                st.success("✅ Conta removida com sucesso!")
                st.rerun()
        else:
            st.toast("⚠️ Selecione uma linha na tabela para deletar.", icon="⚠️")
            st.session_state.modo = None

    if st.session_state.modo == "editar":
        if not linhas_selecionadas:
            st.toast("⚠️ Selecione uma linha na tabela para editar.", icon="⚠️")
            st.session_state.modo = None

    # --- FORMULÁRIO (EXPANDER) ---
    if st.session_state.modo in ["incluir", "editar"]:
        titulo_form = "📝 Novo Cadastro" if st.session_state.modo == "incluir" else "✏️ Editar Cadastro"
        
        with st.expander(titulo_form, expanded=True):
            dados_iniciais = {"Código": "", "Descrição": "", "Tipo": "Sintética", "Conta Superior": None, "Categoria": "Ativo"}
            idx_edit = 0
            
            if st.session_state.modo == "editar" and linhas_selecionadas:
                idx_edit = linhas_selecionadas[0]
                dados_iniciais = st.session_state.df.loc[idx_edit].to_dict()
                if pd.isna(dados_iniciais.get("Categoria")): dados_iniciais["Categoria"] = "Ativo"

            with st.form("form_conta"):
                c1, c2 = st.columns(2)
                
                codigo = c1.text_input("Código *", value=dados_iniciais["Código"], placeholder="Ex: 1.1.01")
                descricao = c2.text_input("Descrição *", value=dados_iniciais["Descrição"], placeholder="Ex: Caixa")
                
                tipo = c1.selectbox("Tipo *", ["Sintética", "Analítica"], index=0 if dados_iniciais["Tipo"] == "Sintética" else 1)
                categoria = c2.selectbox("Categoria *", ["Ativo", "Passivo", "Receita", "Despesa"], 
                                         index=["Ativo", "Passivo", "Receita", "Despesa"].index(dados_iniciais["Categoria"]))

                lista_superiores = sorted(st.session_state.df["Código"].unique().tolist())
                if st.session_state.modo == "editar" and codigo in lista_superiores:
                    lista_superiores.remove(codigo)
                
                conta_sup = st.selectbox("Conta Superior", [None] + lista_superiores, 
                                         index=0 if not dados_iniciais["Conta Superior"] else ([None] + lista_superiores).index(dados_iniciais["Conta Superior"]))
                
                st.divider()
                col_btn, _ = st.columns([1, 5])
                submit = col_btn.form_submit_button("💾 Salvar", type="primary", use_container_width=True)
                
                if submit:
                    if not codigo or not descricao:
                        st.error("❌ Código e Descrição são obrigatórios.")
                    else:
                        # Validação duplicidade
                        duplicado = False
                        if st.session_state.modo == "incluir" and codigo in st.session_state.df["Código"].values:
                            duplicado = True
                        elif st.session_state.modo == "editar":
                            if codigo in st.session_state.df.drop(idx_edit)["Código"].values:
                                duplicado = True
                        
                        if duplicado:
                            st.error("❌ Código já cadastrado.")
                        else:
                            nova_linha = {"Código": codigo, "Descrição": descricao, "Tipo": tipo, 
                                          "Conta Superior": conta_sup, "Categoria": categoria}
                            
                            if st.session_state.modo == "incluir":
                                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([nova_linha])], ignore_index=True)
                            else:
                                st.session_state.df.loc[idx_edit] = nova_linha
                            
                            st.session_state.modo = None
                            st.success("✅ Operação realizada com sucesso!")
                            st.rerun()

elif selected == "Lançamentos":
    st.title("💸 Lançamentos Contábeis")
    st.markdown("Registre movimentações de débito e crédito.")

    col1, col2, col3, _ = st.columns([1, 1, 1, 6])
    if col1.button("➕ Incluir", key="btn_inc_lanc", use_container_width=True):
        st.session_state.modo = "incluir"
        st.session_state.edit_id = None
        
    if col2.button("✏️ Editar", key="btn_edit_lanc", use_container_width=True):
        st.session_state.modo = "editar"

    if col3.button("🗑️ Deletar", key="btn_del_lanc", use_container_width=True):
        st.session_state.modo = "deletar"

    st.divider()

    # Preparação da Visualização
    rows_view = []
    total_debitos_geral = 0.0
    total_creditos_geral = 0.0
    
    for l in st.session_state.lancamentos:
        debitos = [f"{x['Conta']} (R$ {x['Valor']:,.2f})" for x in l['itens'] if x['Tipo'] == 'Débito']
        creditos = [f"{x['Conta']} (R$ {x['Valor']:,.2f})" for x in l['itens'] if x['Tipo'] == 'Crédito']
        valor_lanc = sum([x['Valor'] for x in l['itens'] if x['Tipo'] == 'Débito'])
        
        total_debitos_geral += valor_lanc
        total_creditos_geral += valor_lanc # Já validado que são iguais
        
        rows_view.append({
            "ID": l['id'],
            "Data": l['data'].strftime("%d/%m/%Y"),
            "Histórico": l['historico'],
            "Débitos": ", ".join(debitos),
            "Créditos": ", ".join(creditos),
            "Valor": valor_lanc
        })
        
    df_view = pd.DataFrame(rows_view)

    # Métricas no Topo
    if not df_view.empty:
        m1, m2 = st.columns(2)
        m1.metric("Total Débitos (Período)", f"R$ {total_debitos_geral:,.2f}")
        m2.metric("Total Créditos (Período)", f"R$ {total_creditos_geral:,.2f}")
        st.divider()

    # Tabela
    if df_view.empty:
        st.info("ℹ️ Nenhum lançamento encontrado. Clique em **Incluir** para começar.")
        if st.session_state.modo in ["deletar", "editar"]: st.session_state.modo = None
    else:
        st.subheader("Lançamentos Recentes")
        selecao_lanc = st.dataframe(
            df_view, 
            use_container_width=True, 
            hide_index=True, 
            on_select="rerun", 
            selection_mode="single-row",
            key="sel_lanc",
            column_config={"Valor": st.column_config.NumberColumn("Valor", format="R$ %,.2f")}
        )
        linhas_sel_lanc = selecao_lanc.selection["rows"]

        # Ações
        if st.session_state.modo == "deletar":
            if linhas_sel_lanc:
                id_sel = df_view.iloc[linhas_sel_lanc[0]]['ID']
                if st.button("Confirmar Exclusão do Lançamento", type="primary"):
                    st.session_state.lancamentos = [x for x in st.session_state.lancamentos if x['id'] != id_sel]
                    st.session_state.modo = None
                    st.success("✅ Lançamento deletado!")
                    st.rerun()
            else:
                st.toast("⚠️ Selecione um lançamento.", icon="⚠️")
                st.session_state.modo = None

        if st.session_state.modo == "editar":
            if linhas_sel_lanc:
                st.session_state.edit_id = df_view.iloc[linhas_sel_lanc[0]]['ID']
            else:
                st.toast("⚠️ Selecione um lançamento.", icon="⚠️")
                st.session_state.modo = None

    # Formulário
    if st.session_state.modo in ["incluir", "editar"]:
        titulo_form = "📝 Novo Lançamento" if st.session_state.modo == "incluir" else "✏️ Editar Lançamento"
        
        with st.expander(titulo_form, expanded=True):
            data_padrao = datetime.now().date()
            hist_padrao = ""
            itens_padrao = []
            
            if st.session_state.modo == "editar" and st.session_state.edit_id is not None:
                for l in st.session_state.lancamentos:
                    if l['id'] == st.session_state.edit_id:
                        data_padrao = l['data']
                        hist_padrao = l['historico']
                        itens_padrao = l['itens']
                        break

            with st.form("form_lancamento"):
                c1, c2 = st.columns([1, 3])
                data_lanc = c1.date_input("Data", value=data_padrao)
                historico = c2.text_input("Histórico", value=hist_padrao, placeholder="Descrição da operação")
                
                st.markdown("**Entrada de Valores (Partida Dobrada)**")
                
                df_itens = pd.DataFrame(itens_padrao)
                if df_itens.empty:
                    df_itens = pd.DataFrame({"Tipo": ["Débito", "Crédito"], "Conta": ["", ""], "Valor": [0.0, 0.0]})
                    
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
                
                total_debito = editor_result[editor_result['Tipo'] == 'Débito']['Valor'].sum()
                total_credito = editor_result[editor_result['Tipo'] == 'Crédito']['Valor'].sum()
                
                col_t1, col_t2 = st.columns(2)
                col_t1.metric("Total Débitos", f"R$ {total_debito:,.2f}")
                col_t2.metric("Total Créditos", f"R$ {total_credito:,.2f}")
                
                # Validação visual antes do submit
                if total_debito != total_credito:
                    st.error(f"⚠️ Diferença: R$ {abs(total_debito - total_credito):,.2f} (Débitos devem ser iguais aos Créditos)")
                
                st.divider()
                col_btn, _ = st.columns([1, 5])
                submit = col_btn.form_submit_button("💾 Salvar Lançamento", type="primary", use_container_width=True)
                
                if submit:
                    valido = True
                    if total_debito != total_credito or (total_debito == 0 and total_credito == 0):
                        st.error("❌ Valores não zerados ou vazios.")
                        valido = False
                    
                    df_check = editor_result.dropna(how='all')
                    if df_check.empty or df_check.isnull().values.any():
                        st.error("❌ Preencha todos os campos corretamente.")
                        valido = False
                    
                    tipos = df_check['Tipo'].unique()
                    if "Débito" not in tipos or "Crédito" not in tipos:
                        st.error("❌ Lançamento deve conter ao menos um Débito e um Crédito.")
                        valido = False

                    if valido:
                        lista_itens = df_check.to_dict('records')
                        
                        if st.session_state.modo == "incluir":
                            novo = {
                                "id": st.session_state.next_id,
                                "data": data_lanc,
                                "historico": historico,
                                "itens": lista_itens
                            }
                            st.session_state.lancamentos.append(novo)
                            st.session_state.next_id += 1
                        else:
                            for i, l in enumerate(st.session_state.lancamentos):
                                if l['id'] == st.session_state.edit_id:
                                    st.session_state.lancamentos[i] = {
                                        "id": st.session_state.edit_id,
                                        "data": data_lanc,
                                        "historico": historico,
                                        "itens": lista_itens
                                    }
                                    break
                        
                        st.session_state.modo = None
                        st.session_state.edit_id = None
                        st.success("✅ Lançamento salvo com sucesso!")
                        st.rerun()

elif selected == "Balancete":
    st.title("📊 Balancete de Verificação")
    
    col_f1, col_f2 = st.columns(2)
    hoje = datetime.now().date()
    f_data_ini = col_f1.date_input("Data Inicial", value=hoje - timedelta(days=365), key="b_ini")
    f_data_fim = col_f2.date_input("Data Final", value=hoje, key="b_fim")
    
    st.divider()
    
    if st.session_state.df.empty:
        st.warning("⚠️ Nenhuma conta cadastrada.")
    else:
        saldos = {cod: {"Debito": 0.0, "Credito": 0.0} for cod in st.session_state.df['Código']}
        
        for l in st.session_state.lancamentos:
            if f_data_ini <= l['data'] <= f_data_fim:
                for item in l['itens']:
                    conta = item['Conta']
                    if conta in saldos:
                        if item['Tipo'] == "Débito":
                            saldos[conta]['Debito'] += item['Valor']
                        else:
                            saldos[conta]['Credito'] += item['Valor']
        
        # Cálculo hierárquico
        codigos_ordenados = sorted(st.session_state.df['Código'].unique(), key=lambda x: x.count('.'), reverse=True)
        
        for cod_pai in codigos_ordenados:
            if st.session_state.df.loc[st.session_state.df['Código'] == cod_pai, 'Tipo'].values[0] == "Sintética":
                prefixo = cod_pai + "."
                nivel_pai = cod_pai.count('.')
                
                filhas = [c for c in saldos if c.startswith(prefixo) and c.count('.') == nivel_pai + 1]
                
                saldos[cod_pai]['Debito'] = sum([saldos[f]['Debito'] for f in filhas])
                saldos[cod_pai]['Credito'] = sum([saldos[f]['Credito'] for f in filhas])
        
        lista_balancete = []
        total_geral_d, total_geral_c = 0.0, 0.0
        
        for cod in sorted(st.session_state.df['Código'].unique()):
            row = st.session_state.df.loc[st.session_state.df['Código'] == cod].iloc[0]
            val_d, val_c = saldos[cod]['Debito'], saldos[cod]['Credito']
            
            lista_balancete.append({
                "Código": cod, "Descrição": row['Descrição'], "Tipo": row['Tipo'],
                "Débito": val_d, "Crédito": val_c, "Saldo": val_d - val_c
            })
            total_geral_d += val_d
            total_geral_c += val_c
            
        df_balancete = pd.DataFrame(lista_balancete)
        
        st.dataframe(
            df_balancete.style.format({"Débito": "R$ {:,.2f}", "Crédito": "R$ {:,.2f}", "Saldo": "R$ {:,.2f}"}),
            use_container_width=True, hide_index=True
        )
        
        st.divider()
        col_t1, col_t2 = st.columns(2)
        col_t1.metric("Total Débitos", f"R$ {total_geral_d:,.2f}")
        col_t2.metric("Total Créditos", f"R$ {total_geral_c:,.2f}")
        
        if abs(total_geral_d - total_geral_c) < 0.01:
            st.success("✅ Balancete validado (D = C)")
        else:
            st.error("❌ Balancete com diferença!")

elif selected == "DRE":
    st.title("📈 Demonstração do Resultado do Exercício (DRE)")
    
    col_f1, col_f2 = st.columns(2)
    hoje = datetime.now().date()
    f_data_ini = col_f1.date_input("Data Inicial", value=hoje - timedelta(days=365), key="dre_ini")
    f_data_fim = col_f2.date_input("Data Final", value=hoje, key="dre_fim")
    
    st.divider()
    
    if st.session_state.df.empty or not st.session_state.lancamentos:
        st.info("ℹ️ Dados insuficientes para gerar DRE.")
    else:
        contas_resultado = {}
        
        for l in st.session_state.lancamentos:
            if f_data_ini <= l['data'] <= f_data_fim:
                for item in l['itens']:
                    conta_cod = item['Conta']
                    info = st.session_state.df.loc[st.session_state.df['Código'] == conta_cod]
                    
                    if not info.empty and info.iloc[0]['Categoria'] in ["Receita", "Despesa"]:
                        cat = info.iloc[0]['Categoria']
                        valor = item['Valor']
                        tipo_lanc = item['Tipo']
                        
                        if conta_cod not in contas_resultado:
                            contas_resultado[conta_cod] = {'Descricao': info.iloc[0]['Descrição'], 'Categoria': cat, 'Valor': 0.0}
                        
                        # Lógica: Receita Credito +, Despesa Debito +
                        if (cat == "Receita" and tipo_lanc == "Crédito") or (cat == "Despesa" and tipo_lanc == "Débito"):
                            contas_resultado[conta_cod]['Valor'] += valor
                        else:
                            contas_resultado[conta_cod]['Valor'] -= valor
        
        lista_rec, lista_desp = [], []
        total_rec, total_desp = 0.0, 0.0
        
        for cod, dados in contas_resultado.items():
            if dados['Valor'] != 0:
                linha = {"Código": cod, "Descrição": dados['Descricao'], "Valor": abs(dados['Valor'])}
                if dados['Categoria'] == "Receita":
                    lista_rec.append(linha)
                    total_rec += dados['Valor']
                else:
                    lista_desp.append(linha)
                    total_desp += dados['Valor']
        
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Receitas")
            if lista_rec:
                st.dataframe(pd.DataFrame(lista_rec).style.format({"Valor": "R$ {:,.2f}"}), hide_index=True)
            else:
                st.write("*Sem receitas no período*")
                
        with c2:
            st.subheader("Despesas")
            if lista_desp:
                st.dataframe(pd.DataFrame(lista_desp).style.format({"Valor": "R$ {:,.2f}"}), hide_index=True)
            else:
                st.write("*Sem despesas no período*")
        
        st.divider()
        resultado = total_rec - total_desp
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Receitas", f"R$ {total_rec:,.2f}")
        m2.metric("Total Despesas", f"R$ {total_desp:,.2f}")
        
        cor_resultado = "normal" if resultado >= 0 else "inverse"
        m3.metric("Resultado Líquido", f"R$ {resultado:,.2f}", delta_color=cor_resultado)

elif selected == "Backup":
    st.title("🔒 Backup e Segurança")
    
    tab1, tab2 = st.tabs(["📤 Exportar", "📥 Restaurar"])
    
    with tab1:
        st.subheader("Gerar Backup Criptografado")
        senha_exp = st.text_input("Definir Senha", type="password", key="senha_exp")
        
        if st.button("Preparar Arquivo", disabled=not senha_exp):
            dados = {
                "contas": st.session_state.df.to_dict(orient='records'),
                "lancamentos": st.session_state.lancamentos,
                "next_id": st.session_state.next_id
            }
            json_str = json.dumps(dados, indent=4, default=str)
            dados_cripto = criptografar(json_str, senha_exp)
            
            if dados_cripto:
                st.download_button(
                    label="📥 Baixar backup_contabil.enc",
                    data=dados_cripto,
                    file_name="backup_contabil.enc",
                    mime="application/octet-stream",
                    use_container_width=True
                )
            else:
                st.error("❌ Erro ao gerar backup.")

    with tab2:
        st.subheader("Restaurar Backup")
        senha_imp = st.text_input("Senha do Arquivo", type="password", key="senha_imp")
        arquivo = st.file_uploader("Selecione o arquivo .enc", type=["enc"])
        
        if arquivo and senha_imp:
            try:
                conteudo = arquivo.read().decode('utf-8')
                json_dec = descriptografar(conteudo, senha_imp)
                
                if json_dec:
                    dados = json.loads(json_dec)
                    if all(k in dados for k in ["contas", "lancamentos", "next_id"]):
                        st.success("✅ Arquivo válido e descriptografado!")
                        
                        if st.button("⚠️ Restaurar Dados", type="primary"):
                            st.session_state.df = pd.DataFrame(dados['contas'])
                            st.session_state.lancamentos = dados['lancamentos']
                            st.session_state.next_id = dados['next_id']
                            
                            for l in st.session_state.lancamentos:
                                if isinstance(l['data'], str):
                                    l['data'] = datetime.strptime(l['data'], "%Y-%m-%d").date()
                            
                            st.success("✅ Dados restaurados com sucesso!")
                            st.rerun()
                    else:
                        st.error("❌ Estrutura do arquivo inválida.")
                else:
                    st.error("❌ Senha incorreta ou arquivo corrompido.")
            except Exception:
                st.error("❌ Erro ao processar o arquivo.")