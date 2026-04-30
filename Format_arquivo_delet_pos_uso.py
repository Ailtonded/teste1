import streamlit as st
import pandas as pd
import json
from datetime import datetime

st.set_page_config(page_title="Sistema Contábil", layout="wide")

# -------------------------
# Estado inicial
# -------------------------
if "lancamentos" not in st.session_state:
    st.session_state.lancamentos = []

if "contas" not in st.session_state:
    st.session_state.contas = ["Caixa", "Banco", "Receita", "Despesa"]

# -------------------------
# Cadastro de contas
# -------------------------
st.sidebar.header("📘 Plano de Contas")

nova_conta = st.sidebar.text_input("Nova conta")

if st.sidebar.button("Adicionar Conta"):
    if nova_conta:
        st.session_state.contas.append(nova_conta)
        st.sidebar.success("Conta adicionada!")

# -------------------------
# Lançamentos
# -------------------------
st.sidebar.header("🧾 Novo Lançamento")

data = st.sidebar.date_input("Data", datetime.today())
debito = st.sidebar.selectbox("Conta Débito", st.session_state.contas)
credito = st.sidebar.selectbox("Conta Crédito", st.session_state.contas)
historico = st.sidebar.text_input("Histórico")
valor = st.sidebar.number_input("Valor", min_value=0.0)

if st.sidebar.button("Lançar"):
    if debito == credito:
        st.sidebar.error("Débito e Crédito não podem ser iguais!")
    else:
        st.session_state.lancamentos.append({
            "data": str(data),
            "debito": debito,
            "credito": credito,
            "historico": historico,
            "valor": valor
        })
        st.sidebar.success("Lançamento registrado!")

# -------------------------
# Tabela de lançamentos
# -------------------------
st.title("📊 Lançamentos")

df = pd.DataFrame(st.session_state.lancamentos)

if not df.empty:
    st.dataframe(df, use_container_width=True)

# -------------------------
# Balancete (SOMASE)
# -------------------------
st.title("📈 Balancete")

if not df.empty:
    contas = st.session_state.contas

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

    balancete = pd.DataFrame(resultado)

    st.dataframe(balancete, use_container_width=True)

# -------------------------
# Exportar JSON
# -------------------------
st.sidebar.header("💾 Backup")

if st.sidebar.button("Exportar JSON"):
    json_data = json.dumps({
        "contas": st.session_state.contas,
        "lancamentos": st.session_state.lancamentos
    })
    st.download_button("Download", json_data, "dados.json")

# -------------------------
# Importar JSON
# -------------------------
arquivo = st.sidebar.file_uploader("Importar JSON", type="json")

if arquivo:
    dados = json.load(arquivo)
    st.session_state.contas = dados["contas"]
    st.session_state.lancamentos = dados["lancamentos"]
    st.sidebar.success("Dados carregados!")