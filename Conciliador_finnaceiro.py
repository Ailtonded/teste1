import streamlit as st
import pandas as pd
import numpy as np
from datetime import timedelta
from io import BytesIO

st.set_page_config(page_title="Conciliação Contábil", layout="wide")

st.title("💰 Conciliação Contábil Inteligente")

# =============================
# 📥 Upload
# =============================
st.sidebar.header("📂 Upload de Arquivos")

file_extrato = st.sidebar.file_uploader("Extrato Financeiro", type=["xlsx"])
file_razao = st.sidebar.file_uploader("Razão Contábil", type=["xlsx"])

# =============================
# 🔧 Funções
# =============================

def carregar_extrato(file):
    df = pd.read_excel(file)

    df = df.rename(columns={
        'DATA': 'DATA',
        'ENTRADAS': 'ENTRADAS',
        'SAIDAS': 'SAIDAS'
    })

    df['DATA'] = pd.to_datetime(df['DATA'], errors='coerce')
    df['ENTRADAS'] = pd.to_numeric(df['ENTRADAS'], errors='coerce').fillna(0)
    df['SAIDAS'] = pd.to_numeric(df['SAIDAS'], errors='coerce').fillna(0)

    df['MOV'] = df['ENTRADAS'] - df['SAIDAS']
    df['TP'] = 'EXTRATO'

    return df


def carregar_razao(file):
    df = pd.read_excel(file)

    df['DATA'] = pd.to_datetime(df['DATA'], errors='coerce')
    df['ENTRADAS'] = pd.to_numeric(df.get('ENTRADAS', 0), errors='coerce').fillna(0)
    df['SAIDAS'] = pd.to_numeric(df.get('SAIDAS', 0), errors='coerce').fillna(0)

    # Caso venha como DEBITO/CREDITO
    if 'DEBITO' in df.columns and 'CREDITO' in df.columns:
        df['ENTRADAS'] = pd.to_numeric(df['DEBITO'], errors='coerce').fillna(0)
        df['SAIDAS'] = pd.to_numeric(df['CREDITO'], errors='coerce').fillna(0)

    df['MOV'] = df['ENTRADAS'] - df['SAIDAS']
    df['TP'] = 'RAZAO'

    return df


def criar_chave(df):
    df['CHAVE'] = (
        df['DATA'].dt.strftime('%Y-%m-%d') + '_' +
        df['MOV'].round(2).astype(str)
    )
    return df


def gerar_sugestoes(df_ext, df_raz):
    sugestoes = []

    for i, ext in df_ext.iterrows():
        for j, raz in df_raz.iterrows():

            score = 0

            # Valor exato
            if ext['MOV'] == raz['MOV']:
                score += 50

            # Valor próximo
            elif abs(ext['MOV'] - raz['MOV']) <= 0.05:
                score += 30

            # Mesma data
            if ext['DATA'] == raz['DATA']:
                score += 50

            # Data próxima
            elif abs((ext['DATA'] - raz['DATA']).days) <= 2:
                score += 30

            if score >= 60:
                sugestoes.append({
                    'DATA_EXT': ext['DATA'],
                    'MOV_EXT': ext['MOV'],
                    'DATA_RAZ': raz['DATA'],
                    'MOV_RAZ': raz['MOV'],
                    'SCORE': score
                })

    return pd.DataFrame(sugestoes)


def exportar_excel(df_dict):
    output = BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        for nome, df in df_dict.items():
            df.to_excel(writer, sheet_name=nome, index=False)

    return output.getvalue()


# =============================
# 🚀 PROCESSAMENTO
# =============================

if file_extrato and file_razao:

    df_ext = carregar_extrato(file_extrato)
    df_raz = carregar_razao(file_razao)

    df_ext = criar_chave(df_ext)
    df_raz = criar_chave(df_raz)

    # =============================
    # 📅 Filtro de Data
    # =============================
    st.sidebar.header("📅 Filtro")

    data_ini = st.sidebar.date_input("Data Inicial", df_ext['DATA'].min())
    data_fim = st.sidebar.date_input("Data Final", df_ext['DATA'].max())

    df_ext = df_ext[(df_ext['DATA'] >= pd.to_datetime(data_ini)) & (df_ext['DATA'] <= pd.to_datetime(data_fim))]
    df_raz = df_raz[(df_raz['DATA'] >= pd.to_datetime(data_ini)) & (df_raz['DATA'] <= pd.to_datetime(data_fim))]

    # =============================
    # 🔗 MATCH EXATO
    # =============================
    conciliados = df_ext.merge(
        df_raz,
        on='CHAVE',
        suffixes=('_EXT', '_RAZ'),
        how='inner'
    )

    # =============================
    # ❌ NÃO CONCILIADOS
    # =============================
    nao_ext = df_ext[~df_ext['CHAVE'].isin(conciliados['CHAVE'])]
    nao_raz = df_raz[~df_raz['CHAVE'].isin(conciliados['CHAVE'])]

    # =============================
    # 🧠 SUGESTÕES
    # =============================
    sugestoes = gerar_sugestoes(nao_ext, nao_raz)

    # =============================
    # 📊 TABS
    # =============================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "✅ Conciliados",
        "🧠 Sugestões",
        "⚠️ Extrato",
        "⚠️ Razão",
        "📊 Resumo"
    ])

    with tab1:
        st.subheader("Conciliados")
        st.dataframe(conciliados, use_container_width=True)

    with tab2:
        st.subheader("Sugestões")
        st.dataframe(sugestoes.sort_values(by='SCORE', ascending=False), use_container_width=True)

    with tab3:
        st.subheader("Não conciliados - Extrato")
        st.dataframe(nao_ext, use_container_width=True)

    with tab4:
        st.subheader("Não conciliados - Razão")
        st.dataframe(nao_raz, use_container_width=True)

    with tab5:
        st.subheader("Resumo")

        total_ext = df_ext['MOV'].sum()
        total_raz = df_raz['MOV'].sum()
        total_conc = conciliados['MOV_EXT'].sum()

        st.metric("Total Extrato", f"{total_ext:,.2f}")
        st.metric("Total Razão", f"{total_raz:,.2f}")
        st.metric("Total Conciliado", f"{total_conc:,.2f}")
        st.metric("Diferença", f"{(total_ext - total_raz):,.2f}")

    # =============================
    # 📤 EXPORTAÇÃO
    # =============================
    st.sidebar.header("📤 Exportar")

    if st.sidebar.button("Exportar Excel"):
        excel = exportar_excel({
            'Conciliados': conciliados,
            'Sugestoes': sugestoes,
            'Extrato_Nao_Conciliado': nao_ext,
            'Razao_Nao_Conciliado': nao_raz
        })

        st.sidebar.download_button(
            label="Download",
            data=excel,
            file_name="conciliacao.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

else:
    st.info("👆 Faça upload dos dois arquivos para começar")