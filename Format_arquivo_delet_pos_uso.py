import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

st.set_page_config(page_title="Sistema Contábil Profissional", layout="wide")

# -------------------------
# Inicialização do Estado
# -------------------------
def init_session_state():
    if "lancamentos" not in st.session_state:
        st.session_state.lancamentos = []
    
    if "contas" not in st.session_state:
        st.session_state.contas = ["Caixa", "Banco do Brasil", "Receita de Serviços", "Despesas Operacionais"]

init_session_state()

# -------------------------
# Funções de Lançamento
# -------------------------
def gerar_lancamentos_repetidos(data_base, debito, credito, historico, valor, repeticoes, periodicidade):
    lancamentos = []
    data_atual = data_base
    
    for i in range(repeticoes):
        if i > 0:
            if periodicidade == "Diário":
                data_atual = data_base + timedelta(days=i)
            elif periodicidade == "Semanal":
                data_atual = data_base + timedelta(weeks=i)
            elif periodicidade == "Mensal":
                data_atual = data_base + relativedelta(months=i)
            else:  # Único
                data_atual = data_base
        
        lancamentos.append({
            "data": data_atual.strftime("%Y-%m-%d"),
            "debito": debito,
            "credito": credito,
            "historico": f"{historico} ({'Original' if i==0 else f'Repetição {i}'})",
            "valor": valor
        })
    
    return lancamentos

def adicionar_lancamento(data, debito, credito, historico, valor, repeticoes, periodicidade):
    if debito == credito:
        return False, "Débito e Crédito não podem ser iguais!"
    
    novos_lancamentos = gerar_lancamentos_repetidos(data, debito, credito, historico, valor, repeticoes, periodicidade)
    st.session_state.lancamentos.extend(novos_lancamentos)
    return True, f"{len(novos_lancamentos)} lançamento(s) registrado(s) com sucesso!"

def excluir_lancamento(index):
    st.session_state.lancamentos.pop(index)

def filtrar_lancamentos(df, conta_filtro, data_inicio, data_fim):
    df_filtrado = df.copy()
    
    if conta_filtro and conta_filtro != "Todas":
        df_filtrado = df_filtrado[(df_filtrado["debito"] == conta_filtro) | (df_filtrado["credito"] == conta_filtro)]
    
    if data_inicio:
        df_filtrado = df_filtrado[pd.to_datetime(df_filtrado["data"]) >= pd.to_datetime(data_inicio)]
    
    if data_fim:
        df_filtrado = df_filtrado[pd.to_datetime(df_filtrado["data"]) <= pd.to_datetime(data_fim)]
    
    return df_filtrado

# -------------------------
# Funções do Plano de Contas
# -------------------------
def adicionar_conta(nome_conta):
    if nome_conta and nome_conta not in st.session_state.contas:
        st.session_state.contas.append(nome_conta)
        return True, "Conta adicionada com sucesso!"
    elif nome_conta in st.session_state.contas:
        return False, "Esta conta já existe!"
    else:
        return False, "Digite um nome para a conta!"

def remover_conta(conta):
    st.session_state.contas.remove(conta)

# -------------------------
# Funções do Balancete
# -------------------------
def calcular_balancete(df, contas):
    resultado = []
    
    for conta in contas:
        total_debito = df[df["debito"] == conta]["valor"].sum()
        total_credito = df[df["credito"] == conta]["valor"].sum()
        saldo = total_debito - total_credito
        
        resultado.append({
            "Conta": conta,
            "Débitos": total_debito,
            "Créditos": total_credito,
            "Saldo": saldo
        })
    
    return pd.DataFrame(resultado)

# -------------------------
# Funções de Backup
# -------------------------
def exportar_dados():
    return json.dumps({
        "contas": st.session_state.contas,
        "lancamentos": st.session_state.lancamentos,
        "versao": "1.0",
        "exportado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }, indent=2)

def importar_dados(arquivo_json):
    try:
        dados = json.load(arquivo_json)
        st.session_state.contas = dados["contas"]
        st.session_state.lancamentos = dados["lancamentos"]
        return True, "Dados importados com sucesso!"
    except Exception as e:
        return False, f"Erro ao importar: {str(e)}"

# -------------------------
# Interface Principal
# -------------------------
st.title("💰 Sistema Contábil Profissional")
st.markdown("---")

# Sidebar - Backup
with st.sidebar:
    st.header("💾 Backup e Recuperação")
    
    col_exp, col_imp = st.columns(2)
    
    with col_exp:
        if st.button("📤 Exportar JSON", use_container_width=True):
            json_data = exportar_dados()
            st.download_button(
                label="⬇️ Download",
                data=json_data,
                file_name=f"backup_contabil_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )
    
    with col_imp:
        arquivo = st.file_uploader("📂 Importar JSON", type="json", key="import_uploader")
        if arquivo:
            sucesso, mensagem = importar_dados(arquivo)
            if sucesso:
                st.success(mensagem)
                st.rerun()
            else:
                st.error(mensagem)
    
    st.markdown("---")
    st.caption(f"📊 Total de Lançamentos: {len(st.session_state.lancamentos)}")
    st.caption(f"📘 Total de Contas: {len(st.session_state.contas)}")

# Tabs principais
tab_lancamentos, tab_contas, tab_balancete = st.tabs(["🧾 Lançamentos", "📘 Plano de Contas", "📊 Balancete"])

# -------------------------
# ABA 1: LANÇAMENTOS
# -------------------------
with tab_lancamentos:
    col_form, col_lista = st.columns([1, 2])
    
    with col_form:
        st.subheader("➕ Novo Lançamento")
        
        with st.form("form_lancamento", clear_on_submit=True):
            data = st.date_input("Data", datetime.today())
            
            col_cred, col_deb = st.columns(2)
            with col_deb:
                debito = st.selectbox("Conta Débito", st.session_state.contas, key="debito_select")
            with col_cred:
                credito = st.selectbox("Conta Crédito", st.session_state.contas, key="credito_select")
            
            historico = st.text_input("Histórico", placeholder="Descrição do lançamento...")
            valor = st.number_input("Valor (R$)", min_value=0.01, step=0.01, format="%.2f")
            
            st.markdown("---")
            st.caption("🔄 Repetições")
            
            repeticoes = st.number_input("Quantidade de repetições", min_value=1, max_value=365, value=1)
            periodicidade = st.selectbox("Periodicidade", ["Único", "Diário", "Semanal", "Mensal"])
            
            submitted = st.form_submit_button("✅ Registrar Lançamento", use_container_width=True)
            
            if submitted:
                sucesso, mensagem = adicionar_lancamento(data, debito, credito, historico, valor, repeticoes, periodicidade)
                if sucesso:
                    st.success(mensagem)
                    st.rerun()
                else:
                    st.error(mensagem)
    
    with col_lista:
        st.subheader("📋 Listagem de Lançamentos")
        
        if st.session_state.lancamentos:
            df_lancamentos = pd.DataFrame(st.session_state.lancamentos)
            df_lancamentos["data"] = pd.to_datetime(df_lancamentos["data"])
            df_lancamentos = df_lancamentos.sort_values("data", ascending=False)
            
            # Filtros
            st.markdown("### 🔍 Filtros")
            col_filtro1, col_filtro2, col_filtro3 = st.columns(3)
            
            with col_filtro1:
                contas_filtro = ["Todas"] + st.session_state.contas
                conta_selecionada = st.selectbox("Filtrar por conta", contas_filtro)
            
            with col_filtro2:
                data_inicio = st.date_input("Data inicial", value=None)
            
            with col_filtro3:
                data_fim = st.date_input("Data final", value=None)
            
            df_filtrado = filtrar_lancamentos(df_lancamentos, conta_selecionada, data_inicio, data_fim)
            
            # Totalizador
            total_valor = df_filtrado["valor"].sum()
            st.metric("💰 Total dos lançamentos filtrados", f"R$ {total_valor:,.2f}")
            
            # Tabela com botões de exclusão
            st.markdown("### 📊 Lançamentos")
            
            for idx, row in df_filtrado.iterrows():
                with st.container():
                    col1, col2, col3, col4, col5, col6 = st.columns([1.5, 2, 2, 2.5, 1.5, 0.5])
                    
                    with col1:
                        st.write(row["data"].strftime("%d/%m/%Y"))
                    with col2:
                        st.write(row["debito"])
                    with col3:
                        st.write(row["credito"])
                    with col4:
                        st.write(row["historico"][:30] + "..." if len(row["historico"]) > 30 else row["historico"])
                    with col5:
                        st.write(f"R$ {row['valor']:,.2f}")
                    with col6:
                        if st.button("🗑️", key=f"del_{idx}"):
                            excluir_lancamento(df_lancamentos[df_lancamentos["data"] == row["data"]].index[0])
                            st.rerun()
                    
                    st.divider()
        else:
            st.info("📭 Nenhum lançamento registrado ainda. Use o formulário ao lado para começar!")

# -------------------------
# ABA 2: PLANO DE CONTAS
# -------------------------
with tab_contas:
    col_add, col_lista = st.columns([1, 2])
    
    with col_add:
        st.subheader("➕ Adicionar Conta")
        
        with st.form("form_conta", clear_on_submit=True):
            nova_conta = st.text_input("Nome da nova conta", placeholder="Ex: Investimentos, Salários, etc.")
            submitted = st.form_submit_button("Adicionar Conta", use_container_width=True)
            
            if submitted:
                sucesso, mensagem = adicionar_conta(nova_conta)
                if sucesso:
                    st.success(mensagem)
                    st.rerun()
                else:
                    st.error(mensagem)
    
    with col_lista:
        st.subheader("📋 Contas Cadastradas")
        
        if st.session_state.contas:
            df_contas = pd.DataFrame({"Contas": st.session_state.contas})
            df_contas.index = range(1, len(df_contas) + 1)
            
            for idx, row in df_contas.iterrows():
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"**{idx}.** {row['Contas']}")
                with col2:
                    if st.button("🗑️ Excluir", key=f"remove_{row['Contas']}"):
                        remover_conta(row['Contas'])
                        st.rerun()
        else:
            st.warning("⚠️ Nenhuma conta cadastrada. Adicione contas para começar!")

# -------------------------
# ABA 3: BALANCETE
# -------------------------
with tab_balancete:
    st.subheader("📊 Demonstrativo de Saldos")
    
    if st.session_state.lancamentos:
        df_lancamentos = pd.DataFrame(st.session_state.lancamentos)
        balancete_df = calcular_balancete(df_lancamentos, st.session_state.contas)
        
        # Aplicar formatação
        balancete_df["Débitos"] = balancete_df["Débitos"].apply(lambda x: f"R$ {x:,.2f}")
        balancete_df["Créditos"] = balancete_df["Créditos"].apply(lambda x: f"R$ {x:,.2f}")
        
        # Destacar saldos negativos
        def formatar_saldo(row):
            valor = row["Saldo"]
            if valor < 0:
                return f'<span style="color: red;">R$ {valor:,.2f}</span>'
            else:
                return f'R$ {valor:,.2f}'
        
        balancete_df["Saldo"] = balancete_df.apply(formatar_saldo, axis=1)
        
        st.dataframe(balancete_df, use_container_width=True, hide_index=True)
        
        # Totais gerais
        st.markdown("---")
        st.subheader("📈 Totais Gerais")
        
        total_debitos_geral = df_lancamentos["valor"].sum()
        total_creditos_geral = df_lancamentos["valor"].sum()
        diferenca = total_debitos_geral - total_creditos_geral
        
        col_tot1, col_tot2, col_tot3 = st.columns(3)
        
        with col_tot1:
            st.metric("Total Débitos", f"R$ {total_debitos_geral:,.2f}")
        
        with col_tot2:
            st.metric("Total Créditos", f"R$ {total_creditos_geral:,.2f}")
        
        with col_tot3:
            cor_diferenca = "inverse" if diferenca != 0 else "off"
            st.metric("Diferença (D - C)", f"R$ {diferenca:,.2f}", delta_color=cor_diferenca)
        
        if abs(diferenca) > 0.01:
            st.warning("⚠️ Atenção: A soma dos débitos é diferente da soma dos créditos! Verifique os lançamentos.")
        else:
            st.success("✅ Sistema em equilíbrio: Débitos = Créditos")
    
    else:
        st.info("📭 Nenhum lançamento registrado. Cadastre lançamentos para visualizar o balancete!")

# -------------------------
# Rodapé
# -------------------------
st.markdown("---")
st.caption(f"📅 Sistema atualizado em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} | Desenvolvido com Streamlit")