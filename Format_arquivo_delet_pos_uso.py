import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
import base64
import hashlib

# --- FUNÇÕES DE CRIPTOGRAFIA (SIMPLES) ---
def gerar_chave(senha: str) -> bytes:
    """Gera uma chave de 32 bytes a partir da senha usando SHA256."""
    return hashlib.sha256(senha.encode('utf-8')).digest()

def criptografar(texto: str, senha: str) -> str:
    """Criptografa texto usando XOR e retorna Base64."""
    try:
        chave = gerar_chave(senha)
        dados = texto.encode('utf-8')
        # XOR byte a byte
        dados_cripto = bytes([d ^ chave[i % len(chave)] for i, d in enumerate(dados)])
        return base64.b64encode(dados_cripto).decode('utf-8')
    except Exception:
        return ""

def descriptografar(texto_cripto: str, senha: str) -> str | None:
    """Descriptografa Base64 usando XOR. Retorna None se falhar."""
    try:
        chave = gerar_chave(senha)
        dados = base64.b64decode(texto_cripto)
        dados_decripto = bytes([d ^ chave[i % len(chave)] for i, d in enumerate(dados)])
        return dados_decripto.decode('utf-8')
    except Exception:
        return None

# Configuração da página
st.set_page_config(layout="wide", initial_sidebar_state="collapsed")

# --- INICIALIZAÇÃO DOS DADOS ---
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=["Código", "Descrição", "Tipo", "Conta Superior", "Categoria"])

if "lancamentos" not in st.session_state:
    st.session_state.lancamentos = []
    st.session_state.next_id = 1

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
    if st.button("DRE"):
        st.session_state.aba = "dre"
    
    st.divider()
    if st.button("Backup"):
        st.session_state.aba = "backup"

# --- ABA 1: CADASTRO DE CONTAS ---
if st.session_state.aba == "contas":
    st.title("Cadastro de Contas")

    col1, col2, col3, col4 = st.columns([1, 1, 1, 6])
    if col1.button("Incluir"):
        st.session_state.modo = "incluir"
        
    if col2.button("Editar"):
        st.session_state.modo = "editar"

    if col3.button("Deletar"):
        st.session_state.modo = "deletar"

    st.divider()

    selecao = st.dataframe(st.session_state.df, use_container_width=True, hide_index=True, on_select="rerun", key="tabela_contas")
    linhas_selecionadas = selecao.selection["rows"]

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

    if st.session_state.modo == "editar" and not linhas_selecionadas:
        st.warning("Selecione uma linha na tabela para editar.")
        st.session_state.modo = None

    if st.session_state.modo in ["incluir", "editar"]:
        dados_iniciais = {"Código": "", "Descrição": "", "Tipo": "Sintética", "Conta Superior": None, "Categoria": "Ativo"}
        idx_edit = 0
        
        if st.session_state.modo == "editar" and linhas_selecionadas:
            idx_edit = linhas_selecionadas[0]
            dados_iniciais = st.session_state.df.loc[idx_edit].to_dict()
            if pd.isna(dados_iniciais.get("Categoria")):
                dados_iniciais["Categoria"] = "Ativo"

        with st.form("form_conta"):
            c1, c2 = st.columns(2)
            codigo = c1.text_input("Código *", value=dados_iniciais["Código"])
            
            tipo_options = ["Sintética", "Analítica"]
            tipo_idx = 0 if dados_iniciais["Tipo"] == "Sintética" else 1
            tipo = c1.selectbox("Tipo", tipo_options, index=tipo_idx)

            cat_options = ["Ativo", "Passivo", "Receita", "Despesa"]
            cat_idx = cat_options.index(dados_iniciais["Categoria"]) if dados_iniciais["Categoria"] in cat_options else 0
            categoria = c1.selectbox("Categoria *", cat_options, index=cat_idx)

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
                        nova_linha = {
                            "Código": codigo, 
                            "Descrição": descricao, 
                            "Tipo": tipo, 
                            "Conta Superior": conta_sup,
                            "Categoria": categoria
                        }
                        
                        if st.session_state.modo == "incluir":
                            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([nova_linha])], ignore_index=True)
                            st.success("Conta incluída!")
                        else:
                            st.session_state.df.loc[idx_edit] = nova_linha
                            st.success("Conta atualizada!")
                        
                        st.session_state.modo = None
                        st.rerun()

# --- ABA 2: LANÇAMENTOS ---
elif st.session_state.aba == "lanc":
    st.title("Lançamentos")

    col1, col2, col3, col4 = st.columns([1, 1, 1, 6])
    if col1.button("Incluir", key="btn_inc_lanc"):
        st.session_state.modo = "incluir"
        st.session_state.edit_id = None
        
    if col2.button("Editar", key="btn_edit_lanc"):
        st.session_state.modo = "editar"

    if col3.button("Deletar", key="btn_del_lanc"):
        st.session_state.modo = "deletar"

    st.divider()

    rows_view = []
    hoje = datetime.now().date()
    for l in st.session_state.lancamentos:
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
        st.info("Nenhum lançamento cadastrado.")
        if st.session_state.modo in ["deletar", "editar"]:
            st.warning("Nada para selecionar.")
            st.session_state.modo = None
    else:
        selecao_lanc = st.dataframe(
            df_view, 
            use_container_width=True, 
            hide_index=True, 
            on_select="rerun", 
            selection_mode="single-row",
            key="sel_lanc"
        )
        linhas_sel_lanc = selecao_lanc.selection["rows"]

        if st.session_state.modo == "deletar":
            if linhas_sel_lanc:
                idx_sel = linhas_sel_lanc[0]
                id_selecionado = df_view.iloc[idx_sel]['ID']
                st.session_state.lancamentos = [x for x in st.session_state.lancamentos if x['id'] != id_selecionado]
                st.success("Lançamento deletado!")
                st.session_state.modo = None
                st.rerun()
            else:
                st.warning("Selecione uma linha para deletar.")
                st.session_state.modo = None

        if st.session_state.modo == "editar":
            if linhas_sel_lanc:
                idx_sel = linhas_sel_lanc[0]
                st.session_state.edit_id = df_view.iloc[idx_sel]['ID']
            else:
                st.warning("Selecione uma linha na tabela para editar.")
                st.session_state.modo = None

    if st.session_state.modo in ["incluir", "editar"]:
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
            col1, col2 = st.columns([1, 3])
            data_lanc = col1.date_input("Data", value=data_padrao)
            historico = col2.text_input("Histórico", value=hist_padrao)
            
            st.markdown("**Itens do Lançamento**")
            
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
            
            total_debito = editor_result[editor_result['Tipo'] == 'Débito']['Valor'].sum()
            total_credito = editor_result[editor_result['Tipo'] == 'Crédito']['Valor'].sum()
            
            col_t1, col_t2 = st.columns(2)
            col_t1.metric("Total Débitos", f"R$ {total_debito:,.2f}")
            col_t2.metric("Total Créditos", f"R$ {total_credito:,.2f}")
            
            if total_debito != total_credito:
                st.error("⚠️ As somas de Débito e Crédito devem ser iguais para salvar.")
            
            col_btn = st.columns([1, 1, 4])
            btn_salvar = col_btn[0].form_submit_button("Salvar", type="primary")
            btn_cancelar = col_btn[1].form_submit_button("Cancelar")
            
            if btn_cancelar:
                st.session_state.modo = None
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
                    
                    if st.session_state.modo == "incluir":
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
                    
                    st.session_state.modo = None
                    st.session_state.edit_id = None
                    st.rerun()

# --- ABA 3: BALANCETE ---
elif st.session_state.aba == "balancete":
    st.title("Balancete de Verificação")
    
    col_f1, col_f2 = st.columns(2)
    hoje = datetime.now().date()
    f_data_ini = col_f1.date_input("Data Inicial", value=hoje - timedelta(days=365), key="b_ini")
    f_data_fim = col_f2.date_input("Data Final", value=hoje, key="b_fim")
    
    st.divider()
    
    if st.session_state.df.empty:
        st.warning("Nenhuma conta cadastrada.")
    else:
        saldos = {}
        for cod in st.session_state.df['Código']:
            saldos[cod] = {"Debito": 0.0, "Credito": 0.0}
        
        for l in st.session_state.lancamentos:
            if f_data_ini <= l['data'] <= f_data_fim:
                for item in l['itens']:
                    conta = item['Conta']
                    valor = item['Valor']
                    tipo = item['Tipo']
                    
                    if conta in saldos:
                        if tipo == "Débito":
                            saldos[conta]['Debito'] += valor
                        else:
                            saldos[conta]['Credito'] += valor
        
        codigos_ordenados = sorted(
            st.session_state.df['Código'].unique(), 
            key=lambda x: x.count('.'), 
            reverse=True
        )
        
        for cod_pai in codigos_ordenados:
            tipo_conta = st.session_state.df.loc[st.session_state.df['Código'] == cod_pai, 'Tipo'].values[0]
            
            if tipo_conta == "Sintética":
                filhas_diretas = []
                nivel_pai = cod_pai.count('.')
                prefixo_pai = cod_pai + "."
                
                for cod_filha in saldos.keys():
                    if cod_filha.startswith(prefixo_pai):
                        nivel_filha = cod_filha.count('.')
                        if nivel_filha == nivel_pai + 1:
                            filhas_diretas.append(cod_filha)
                
                soma_d = 0.0
                soma_c = 0.0
                for filha in filhas_diretas:
                    soma_d += saldos[filha]['Debito']
                    soma_c += saldos[filha]['Credito']
                
                saldos[cod_pai]['Debito'] = soma_d
                saldos[cod_pai]['Credito'] = soma_c
        
        lista_balancete = []
        total_geral_d = 0.0
        total_geral_c = 0.0
        
        codigos_exibicao = sorted(st.session_state.df['Código'].unique())
        
        for cod in codigos_exibicao:
            row_conta = st.session_state.df.loc[st.session_state.df['Código'] == cod].iloc[0]
            desc = row_conta['Descrição']
            tipo = row_conta['Tipo']
            
            val_d = saldos[cod]['Debito']
            val_c = saldos[cod]['Credito']
            saldo = val_d - val_c
            
            lista_balancete.append({
                "Código": cod,
                "Descrição": desc,
                "Tipo": tipo,
                "Débito": val_d if val_d > 0 else 0.0,
                "Crédito": val_c if val_c > 0 else 0.0,
                "Saldo": saldo
            })
            
            total_geral_d += val_d
            total_geral_c += val_c
            
        df_balancete = pd.DataFrame(lista_balancete)
        
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

# --- ABA 4: DRE ---
elif st.session_state.aba == "dre":
    st.title("Demonstração do Resultado do Exercício (DRE)")
    
    col_f1, col_f2 = st.columns(2)
    hoje = datetime.now().date()
    f_data_ini = col_f1.date_input("Data Inicial", value=hoje - timedelta(days=365), key="dre_ini")
    f_data_fim = col_f2.date_input("Data Final", value=hoje, key="dre_fim")
    
    st.divider()
    
    if st.session_state.df.empty:
        st.warning("Nenhuma conta cadastrada.")
    elif not st.session_state.lancamentos:
        st.warning("Nenhum lançamento encontrado.")
    else:
        contas_resultado = {}
        
        for l in st.session_state.lancamentos:
            if f_data_ini <= l['data'] <= f_data_fim:
                for item in l['itens']:
                    conta_cod = item['Conta']
                    info_conta = st.session_state.df.loc[st.session_state.df['Código'] == conta_cod]
                    
                    if not info_conta.empty:
                        categoria = info_conta.iloc[0]['Categoria']
                        
                        if categoria in ["Receita", "Despesa"]:
                            valor = item['Valor']
                            tipo_lanc = item['Tipo']
                            
                            if conta_cod not in contas_resultado:
                                contas_resultado[conta_cod] = {
                                    'Descricao': info_conta.iloc[0]['Descrição'],
                                    'Categoria': categoria,
                                    'Valor': 0.0
                                }
                            
                            if categoria == "Receita":
                                if tipo_lanc == "Crédito":
                                    contas_resultado[conta_cod]['Valor'] += valor
                                else:
                                    contas_resultado[conta_cod]['Valor'] -= valor
                            
                            elif categoria == "Despesa":
                                if tipo_lanc == "Débito":
                                    contas_resultado[conta_cod]['Valor'] += valor
                                else:
                                    contas_resultado[conta_cod]['Valor'] -= valor
        
        lista_receitas = []
        lista_despesas = []
        total_receitas = 0.0
        total_despesas = 0.0
        
        for cod, dados in contas_resultado.items():
            if dados['Valor'] != 0:
                linha = {
                    "Código": cod,
                    "Descrição": dados['Descricao'],
                    "Categoria": dados['Categoria'],
                    "Valor": dados['Valor']
                }
                
                if dados['Categoria'] == "Receita":
                    lista_receitas.append(linha)
                    total_receitas += dados['Valor']
                else:
                    lista_despesas.append(linha)
                    total_despesas += dados['Valor']
        
        st.subheader("RECEITAS")
        if lista_receitas:
            df_rec = pd.DataFrame(lista_receitas)
            st.dataframe(
                df_rec.style.format({"Valor": "R$ {:,.2f}"}),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.write("Nenhuma receita no período.")
        
        st.write("")
        
        st.subheader("DESPESAS")
        if lista_despesas:
            df_desp = pd.DataFrame(lista_despesas)
            st.dataframe(
                df_desp.style.format({"Valor": "R$ {:,.2f}"}),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.write("Nenhuma despesa no período.")
        
        st.divider()
        
        resultado = total_receitas - total_despesas
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Receitas", f"R$ {total_receitas:,.2f}")
        c2.metric("Total Despesas", f"R$ {total_despesas:,.2f}")
        
        delta_color = "normal" if resultado >= 0 else "inverse"
        c3.metric("Resultado do Período", f"R$ {resultado:,.2f}", delta_color=delta_color)

# --- ABA 5: BACKUP COM CRIPTOGRAFIA SIMPLES ---
elif st.session_state.aba == "backup":
    st.title("Backup e Restauração Segura")
    
    st.markdown("Os backups são protegidos por senha usando criptografia XOR (SHA256 + Base64).")
    
    st.divider()
    
    # --- 1. EXPORTAR BACKUP CRIPTOGRAFADO ---
    st.subheader("1. Gerar Backup Criptografado")
    
    senha_export = st.text_input("Definir Senha do Backup", type="password", key="senha_exp")
    
    # Prepara dados
    dados_exportacao = {
        "contas": st.session_state.df.to_dict(orient='records'),
        "lancamentos": st.session_state.lancamentos,
        "next_id": st.session_state.next_id
    }
    json_str = json.dumps(dados_exportacao, indent=4, default=str)
    
    if not senha_export:
        st.button("📥 Baixar backup_contabil.enc", disabled=True)
        st.warning("Digite uma senha para gerar o backup.")
    else:
        # Criptografa
        dados_cripto = criptografar(json_str, senha_export)
        
        st.download_button(
            label="📥 Baixar backup_contabil.enc",
            data=dados_cripto,
            file_name="backup_contabil.enc",
            mime="application/octet-stream",
            use_container_width=True
        )
        st.info("ℹ️ Guarde a senha em segurança. Sem ela, não é possível restaurar o backup.")
    
    st.divider()
    
    # --- 2. IMPORTAR BACKUP CRIPTOGRAFADO ---
    st.subheader("2. Restaurar Backup")
    
    senha_import = st.text_input("Senha do Arquivo", type="password", key="senha_imp")
    arquivo_upload = st.file_uploader("Selecione o arquivo .enc", type=["enc"], key="upload_backup")
    
    if arquivo_upload is not None:
        if not senha_import:
            st.warning("Digite a senha para descriptografar o arquivo.")
        else:
            try:
                # Lê o arquivo
                conteudo = arquivo_upload.read().decode('utf-8')
                
                # Tenta descriptografar
                json_decodificado = descriptografar(conteudo, senha_import)
                
                if json_decodificado is None:
                    st.error("❌ Falha ao descriptografar. Senha incorreta ou arquivo corrompido.")
                else:
                    # Valida JSON
                    dados_importados = json.loads(json_decodificado)
                    
                    if "contas" in dados_importados and "lancamentos" in dados_importados and "next_id" in dados_importados:
                        st.success("✅ Arquivo descriptografado com sucesso!")
                        
                        if st.button("⚠️ Restaurar Dados", type="primary"):
                            st.session_state.df = pd.DataFrame(dados_importados['contas'])
                            st.session_state.lancamentos = dados_importados['lancamentos']
                            st.session_state.next_id = dados_importados['next_id']
                            
                            # Converte datas
                            for l in st.session_state.lancamentos:
                                if isinstance(l['data'], str):
                                    l['data'] = datetime.strptime(l['data'], "%Y-%m-%d").date()
                                    
                            st.success("Dados restaurados com sucesso!")
                            st.rerun()
                    else:
                        st.error("❌ Estrutura do arquivo JSON inválida.")
                        
            except json.JSONDecodeError:
                st.error("❌ Erro: O arquivo descriptografado não é um JSON válido.")
            except Exception as e:
                st.error(f"❌ Erro inesperado: {e}")