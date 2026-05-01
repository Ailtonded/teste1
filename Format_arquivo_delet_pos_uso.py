import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

st.set_page_config(page_title="Sistema Contábil ERP", layout="wide")

# -------------------------
# Inicialização do Estado (PRESERVANDO DADOS EXISTENTES)
# -------------------------
def init_session_state():
    if "lancamentos" not in st.session_state:
        st.session_state.lancamentos = []
    
    if "contas" not in st.session_state:
        st.session_state.contas = ["Caixa", "Banco", "Receita", "Despesa"]
    
    # NOVO: Estrutura avançada de contas (compatível com antiga)
    if "contas_avancadas" not in st.session_state:
        # Converter contas antigas para novo formato
        st.session_state.contas_avancadas = {}
        for conta in st.session_state.contas:
            # Determinar tipo baseado no nome (heurística)
            tipo = "Ativo"
            conta_lower = conta.lower()
            if "receita" in conta_lower or "venda" in conta_lower:
                tipo = "Receita"
            elif "despesa" in conta_lower or "custo" in conta_lower:
                tipo = "Despesa"
            elif "passivo" in conta_lower or "fornecedor" in conta_lower:
                tipo = "Passivo"
            
            st.session_state.contas_avancadas[conta] = {
                "codigo": len(st.session_state.contas_avancadas) + 1,
                "descricao": conta,
                "tipo": tipo,
                "nome_original": conta
            }

init_session_state()

# -------------------------
# Funções de Plano de Contas (EVOLUÍDAS)
# -------------------------
def adicionar_conta_avancada(codigo, descricao, tipo):
    # Verificar código duplicado
    for conta, dados in st.session_state.contas_avancadas.items():
        if dados["codigo"] == codigo:
            return False, "Código já existe!"
    
    # Verificar campos obrigatórios
    if not codigo or not descricao:
        return False, "Código e descrição são obrigatórios!"
    
    # Adicionar conta
    st.session_state.contas_avancadas[descricao] = {
        "codigo": codigo,
        "descricao": descricao,
        "tipo": tipo,
        "nome_original": descricao
    }
    
    # Manter compatibilidade com lista antiga
    if descricao not in st.session_state.contas:
        st.session_state.contas.append(descricao)
    
    return True, "Conta adicionada com sucesso!"

def remover_conta_avancada(nome_conta):
    if nome_conta in st.session_state.contas_avancadas:
        # Verificar se conta tem lançamentos
        tem_lancamento = False
        for lanc in st.session_state.lancamentos:
            if lanc["debito"] == nome_conta or lanc["credito"] == nome_conta:
                tem_lancamento = True
                break
        
        if tem_lancamento:
            return False, "Não é possível excluir conta com lançamentos!"
        
        del st.session_state.contas_avancadas[nome_conta]
        if nome_conta in st.session_state.contas:
            st.session_state.contas.remove(nome_conta)
        return True, "Conta removida com sucesso!"
    return False, "Conta não encontrada!"

def get_tipo_conta(nome_conta):
    if nome_conta in st.session_state.contas_avancadas:
        return st.session_state.contas_avancadas[nome_conta]["tipo"]
    return "Ativo"

# -------------------------
# Funções de Lançamento (PRESERVADAS E EVOLUÍDAS)
# -------------------------
def adicionar_lancamento(data, debito, credito, historico, valor):
    # Validações
    if debito == credito:
        return False, "Débito e Crédito não podem ser iguais!"
    
    if valor <= 0:
        return False, "Valor deve ser maior que zero!"
    
    # Adicionar lançamento
    st.session_state.lancamentos.append({
        "data": data.strftime("%Y-%m-%d"),
        "debito": debito,
        "credito": credito,
        "historico": historico,
        "valor": valor,
        "data_hora_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    return True, "Lançamento registrado com sucesso!"

def excluir_lancamento(index):
    if 0 <= index < len(st.session_state.lancamentos):
        st.session_state.lancamentos.pop(index)
        return True
    return False

# -------------------------
# Funções de Filtro
# -------------------------
def filtrar_por_periodo(df, data_inicio, data_fim):
    if data_inicio:
        df = df[pd.to_datetime(df["data"]) >= pd.to_datetime(data_inicio)]
    if data_fim:
        df = df[pd.to_datetime(df["data"]) <= pd.to_datetime(data_fim)]
    return df

def filtrar_por_conta(df, conta):
    if conta and conta != "Todas":
        df = df[(df["debito"] == conta) | (df["credito"] == conta)]
    return df

# -------------------------
# Funções do Demonstrativo de Saldos (NOVO)
# -------------------------
def calcular_saldo_periodo(data_inicio, data_fim):
    df_lancamentos = pd.DataFrame(st.session_state.lancamentos)
    if df_lancamentos.empty:
        return pd.DataFrame()
    
    df_lancamentos["data"] = pd.to_datetime(df_lancamentos["data"])
    
    # Saldo anterior (antes da data inicial)
    df_anterior = df_lancamentos[df_lancamentos["data"] < pd.to_datetime(data_inicio)]
    
    # Movimento do período
    df_periodo = df_lancamentos[(df_lancamentos["data"] >= pd.to_datetime(data_inicio)) & 
                                (df_lancamentos["data"] <= pd.to_datetime(data_fim))]
    
    resultado = []
    
    for conta, dados in st.session_state.contas_avancadas.items():
        # Saldo anterior
        debitos_anterior = df_anterior[df_anterior["debito"] == conta]["valor"].sum()
        creditos_anterior = df_anterior[df_anterior["credito"] == conta]["valor"].sum()
        saldo_anterior = debitos_anterior - creditos_anterior
        
        # Movimento do período
        debitos_periodo = df_periodo[df_periodo["debito"] == conta]["valor"].sum()
        creditos_periodo = df_periodo[df_periodo["credito"] == conta]["valor"].sum()
        
        # Saldo final
        saldo_final = saldo_anterior + debitos_periodo - creditos_periodo
        
        if saldo_anterior != 0 or debitos_periodo != 0 or creditos_periodo != 0:
            resultado.append({
                "Conta": conta,
                "Tipo": dados["tipo"],
                "Código": dados["codigo"],
                "Saldo Anterior": saldo_anterior,
                "Débitos (Período)": debitos_periodo,
                "Créditos (Período)": creditos_periodo,
                "Saldo Final": saldo_final
            })
    
    return pd.DataFrame(resultado)

# -------------------------
# Funções de Backup (MANTIDAS E EVOLUÍDAS)
# -------------------------
def exportar_dados():
    dados_export = {
        "versao": "2.0",
        "exportado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "contas_simples": st.session_state.contas,
        "contas_avancadas": st.session_state.contas_avancadas,
        "lancamentos": st.session_state.lancamentos
    }
    return json.dumps(dados_export, indent=2, ensure_ascii=False)

def importar_dados(arquivo_json):
    try:
        dados = json.load(arquivo_json)
        
        # Compatibilidade com versão antiga
        if "versao" not in dados or dados["versao"] == "1.0":
            # Versão antiga
            st.session_state.contas = dados.get("contas", [])
            st.session_state.lancamentos = dados.get("lancamentos", [])
            
            # Converter para novo formato
            st.session_state.contas_avancadas = {}
            for conta in st.session_state.contas:
                tipo = "Ativo"
                conta_lower = conta.lower()
                if "receita" in conta_lower or "venda" in conta_lower:
                    tipo = "Receita"
                elif "despesa" in conta_lower or "custo" in conta_lower:
                    tipo = "Despesa"
                elif "passivo" in conta_lower or "fornecedor" in conta_lower:
                    tipo = "Passivo"
                
                st.session_state.contas_avancadas[conta] = {
                    "codigo": len(st.session_state.contas_avancadas) + 1,
                    "descricao": conta,
                    "tipo": tipo,
                    "nome_original": conta
                }
        else:
            # Versão nova
            st.session_state.contas = dados.get("contas_simples", [])
            st.session_state.contas_avancadas = dados.get("contas_avancadas", {})
            st.session_state.lancamentos = dados.get("lancamentos", [])
        
        return True, "Dados importados com sucesso!"
    except Exception as e:
        return False, f"Erro ao importar: {str(e)}"

# -------------------------
# Interface Principal
# -------------------------
st.title("🏢 Sistema Contábil ERP")
st.markdown("---")

# Sidebar - Backup (MANTIDO)
with st.sidebar:
    st.header("💾 Backup e Recuperação")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📤 Exportar", use_container_width=True):
            json_data = exportar_dados()
            st.download_button(
                label="⬇️ Download JSON",
                data=json_data,
                file_name=f"erp_contabil_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )
    
    with col2:
        arquivo = st.file_uploader("📂 Importar", type="json", key="backup_import")
        if arquivo:
            sucesso, mensagem = importar_dados(arquivo)
            if sucesso:
                st.success(mensagem)
                st.rerun()
            else:
                st.error(mensagem)
    
    st.markdown("---")
    st.metric("Total Lançamentos", len(st.session_state.lancamentos))
    st.metric("Total Contas", len(st.session_state.contas_avancadas))

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📘 Plano de Contas", "➕ Novo Lançamento", "📋 Listagem de Lançamentos", "📊 Demonstrativo de Saldos"])

# -------------------------
# TAB 1: PLANO DE CONTAS (EVOLUÍDO)
# -------------------------
with tab1:
    st.subheader("📘 Plano de Contas")
    
    col_form, col_lista = st.columns([1, 2])
    
    with col_form:
        with st.expander("➕ Nova Conta", expanded=True):
            with st.form("form_nova_conta"):
                codigo = st.number_input("Código", min_value=1, step=1, value=len(st.session_state.contas_avancadas) + 1)
                descricao = st.text_input("Descrição", placeholder="Ex: Caixa, Banco, Fornecedores...")
                tipo = st.selectbox("Tipo", ["Ativo", "Passivo", "Receita", "Despesa"])
                
                submitted = st.form_submit_button("✅ Adicionar Conta", use_container_width=True)
                
                if submitted:
                    if not descricao:
                        st.error("Descrição é obrigatória!")
                    else:
                        sucesso, mensagem = adicionar_conta_avancada(codigo, descricao, tipo)
                        if sucesso:
                            st.success(mensagem)
                            st.rerun()
                        else:
                            st.error(mensagem)
    
    with col_lista:
        st.subheader("📋 Contas Cadastradas")
        
        if st.session_state.contas_avancadas:
            # Criar DataFrame para exibição
            contas_lista = []
            for nome, dados in st.session_state.contas_avancadas.items():
                contas_lista.append({
                    "Código": dados["codigo"],
                    "Descrição": nome,
                    "Tipo": dados["tipo"]
                })
            
            df_contas = pd.DataFrame(contas_lista)
            df_contas = df_contas.sort_values("Código")
            
            # Exibir tabela
            st.dataframe(df_contas, use_container_width=True, hide_index=True)
            
            # Botões de exclusão
            st.markdown("---")
            st.subheader("🗑️ Remover Conta")
            
            conta_remover = st.selectbox("Selecione a conta para remover", list(st.session_state.contas_avancadas.keys()))
            if st.button("Remover Conta", type="secondary", use_container_width=True):
                sucesso, mensagem = remover_conta_avancada(conta_remover)
                if sucesso:
                    st.success(mensagem)
                    st.rerun()
                else:
                    st.error(mensagem)
        else:
            st.info("Nenhuma conta cadastrada. Use o formulário ao lado para adicionar.")

# -------------------------
# TAB 2: NOVO LANÇAMENTO (PRESERVADO E EVOLUÍDO)
# -------------------------
with tab2:
    st.subheader("➕ Novo Lançamento")
    
    with st.form("form_lancamento", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            data = st.date_input("Data do Lançamento", datetime.today())
            debito = st.selectbox("Conta Débito", st.session_state.contas)
            historico = st.text_input("Histórico", placeholder="Descrição do lançamento...")
        
        with col2:
            valor = st.number_input("Valor (R$)", min_value=0.01, step=0.01, format="%.2f")
            credito = st.selectbox("Conta Crédito", st.session_state.contas)
        
        submitted = st.form_submit_button("✅ Registrar Lançamento", use_container_width=True)
        
        if submitted:
            sucesso, mensagem = adicionar_lancamento(data, debito, credito, historico, valor)
            if sucesso:
                st.success(mensagem)
                st.balloons()
                st.rerun()
            else:
                st.error(mensagem)

# -------------------------
# TAB 3: LISTAGEM DE LANÇAMENTOS (NOVA)
# -------------------------
with tab3:
    st.subheader("📋 Listagem de Lançamentos")
    
    if st.session_state.lancamentos:
        # Converter para DataFrame
        df_lancamentos = pd.DataFrame(st.session_state.lancamentos)
        df_lancamentos["data"] = pd.to_datetime(df_lancamentos["data"])
        df_lancamentos["valor_formatado"] = df_lancamentos["valor"].apply(lambda x: f"R$ {x:,.2f}")
        
        # Filtros
        st.markdown("### 🔍 Filtros")
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            data_inicio_filtro = st.date_input("Data Inicial", value=None, key="filtro_inicio")
        
        with col_f2:
            data_fim_filtro = st.date_input("Data Final", value=None, key="filtro_fim")
        
        with col_f3:
            contas_filtro = ["Todas"] + st.session_state.contas
            conta_filtro = st.selectbox("Conta", contas_filtro, key="filtro_conta")
        
        # Aplicar filtros
        df_filtrado = filtrar_por_periodo(df_lancamentos, data_inicio_filtro, data_fim_filtro)
        df_filtrado = filtrar_por_conta(df_filtrado, conta_filtro)
        
        # Ordenação
        df_filtrado = df_filtrado.sort_values("data", ascending=False)
        
        # Totais
        total_filtrado = df_filtrado["valor"].sum()
        st.metric("💰 Total dos Lançamentos Filtrados", f"R$ {total_filtrado:,.2f}")
        
        # Exibir tabela com botões de exclusão
        st.markdown("### 📊 Lançamentos")
        
        if not df_filtrado.empty:
            for idx, row in df_filtrado.iterrows():
                with st.container():
                    cols = st.columns([1.2, 2, 2, 2.5, 1.5, 0.5])
                    
                    with cols[0]:
                        st.write(row["data"].strftime("%d/%m/%Y"))
                    with cols[1]:
                        st.write(row["debito"])
                    with cols[2]:
                        st.write(row["credito"])
                    with cols[3]:
                        historico_texto = row["historico"] if len(row["historico"]) <= 40 else row["historico"][:40] + "..."
                        st.write(historico_texto)
                    with cols[4]:
                        st.write(f"R$ {row['valor']:,.2f}")
                    with cols[5]:
                        if st.button("🗑️", key=f"del_{idx}_{row['data']}_{row['valor']}"):
                            # Encontrar índice original
                            indice_original = st.session_state.lancamentos.index(
                                next(l for l in st.session_state.lancamentos 
                                     if l["data"] == row["data"].strftime("%Y-%m-%d") 
                                     and l["debito"] == row["debito"]
                                     and l["credito"] == row["credito"]
                                     and l["valor"] == row["valor"])
                            )
                            if excluir_lancamento(indice_original):
                                st.success("Lançamento excluído!")
                                st.rerun()
                    
                    st.divider()
        else:
            st.info("Nenhum lançamento encontrado com os filtros selecionados.")
    else:
        st.info("📭 Nenhum lançamento registrado ainda. Use a aba 'Novo Lançamento' para começar!")

# -------------------------
# TAB 4: DEMONSTRATIVO DE SALDOS (NOVA)
# -------------------------
with tab4:
    st.subheader("📊 Demonstrativo de Saldos")
    
    if st.session_state.lancamentos:
        # Definir período padrão (mês atual)
        hoje = datetime.now()
        primeiro_dia_mes = datetime(hoje.year, hoje.month, 1)
        ultimo_dia_mes = datetime(hoje.year, hoje.month + 1, 1) - timedelta(days=1) if hoje.month < 12 else datetime(hoje.year, 12, 31)
        
        col_p1, col_p2 = st.columns(2)
        
        with col_p1:
            data_inicio_demo = st.date_input("Data Inicial", primeiro_dia_mes, key="demo_inicio")
        
        with col_p2:
            data_fim_demo = st.date_input("Data Final", ultimo_dia_mes, key="demo_fim")
        
        if st.button("📊 Calcular Demonstrativo", use_container_width=True):
            with st.spinner("Calculando saldos..."):
                df_resultado = calcular_saldo_periodo(data_inicio_demo, data_fim_demo)
                
                if not df_resultado.empty:
                    # Formatar valores
                    for col in ["Saldo Anterior", "Débitos (Período)", "Créditos (Período)", "Saldo Final"]:
                        df_resultado[col] = df_resultado[col].apply(lambda x: f"R$ {x:,.2f}" if x >= 0 else f"R$ ({abs(x):,.2f})")
                    
                    # Aplicar cor aos saldos negativos via CSS
                    st.markdown("""
                    <style>
                    .negative-saldo {
                        color: red;
                        font-weight: bold;
                    }
                    </style>
                    """, unsafe_allow_html=True)
                    
                    # Exibir tabela
                    st.dataframe(df_resultado, use_container_width=True, hide_index=True)
                    
                    # Totais gerais
                    st.markdown("---")
                    st.subheader("📈 Totais do Período")
                    
                    df_calculo = calcular_saldo_periodo(data_inicio_demo, data_fim_demo)
                    if not df_calculo.empty:
                        total_debitos = df_calculo["Débitos (Período)"].sum()
                        total_creditos = df_calculo["Créditos (Período)"].sum()
                        diferenca = total_debitos - total_creditos
                        
                        col_t1, col_t2, col_t3 = st.columns(3)
                        
                        with col_t1:
                            st.metric("Total Débitos no Período", f"R$ {total_debitos:,.2f}")
                        
                        with col_t2:
                            st.metric("Total Créditos no Período", f"R$ {total_creditos:,.2f}")
                        
                        with col_t3:
                            cor_delta = "inverse" if diferenca < 0 else "normal"
                            st.metric("Diferença (D - C)", f"R$ {diferenca:,.2f}", delta_color=cor_delta)
                        
                        if abs(diferenca) > 0.01:
                            st.warning("⚠️ Diferença detectada! Verifique os lançamentos.")
                        else:
                            st.success("✅ Sistema em equilíbrio contábil!")
                else:
                    st.info("Nenhum movimento encontrado no período selecionado.")
    else:
        st.info("📭 Nenhum lançamento registrado. Cadastre lançamentos para visualizar o demonstrativo.")

# -------------------------
# Rodapé
# -------------------------
st.markdown("---")
st.caption(f"🏢 Sistema Contábil ERP v2.0 | Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")