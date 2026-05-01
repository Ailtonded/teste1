import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="Conciliação Contábil", layout="wide")

st.title("💰 Conciliação Contábil Inteligente")

# =============================
# 📥 Upload
# =============================
st.sidebar.header("📂 Upload")

file_extrato = st.sidebar.file_uploader("Extrato Financeiro", type=["xlsx"])
file_razao = st.sidebar.file_uploader("Razão Contábil", type=["xlsx"])

# =============================
# 🔧 FUNÇÕES BASE
# =============================

def normalizar_colunas(df):
    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
        .str.upper()
        .str.replace(" ", "_")
    )
    return df


def detectar_coluna(df, palavras):
    for p in palavras:
        cols = [c for c in df.columns if p in c]
        if cols:
            return cols[0]
    return None


# =============================
# 📊 EXTRATO
# =============================
def carregar_extrato(file):
    df = pd.read_excel(file)

    df = normalizar_colunas(df)

    st.write("🔍 Colunas Extrato:", df.columns.tolist())

    col_data = detectar_coluna(df, ["DATA"])
    col_entradas = detectar_coluna(df, ["ENTRADA"])
    col_saidas = detectar_coluna(df, ["SAIDA"])

    if not col_data:
        st.error("❌ Coluna DATA não encontrada no Extrato")
        st.stop()

    df['DATA'] = pd.to_datetime(df[col_data], errors='coerce')
    df['ENTRADAS'] = pd.to_numeric(df[col_entradas], errors='coerce').fillna(0) if col_entradas else 0
    df['SAIDAS'] = pd.to_numeric(df[col_saidas], errors='coerce').fillna(0) if col_saidas else 0

    df['MOV'] = df['ENTRADAS'] - df['SAIDAS']
    df['TP'] = 'EXTRATO'

    return df


# =============================
# 📘 RAZÃO
# =============================
def carregar_razao(file):
    df = pd.read_excel(file)

    df = normalizar_colunas(df)

    st.write("🔍 Colunas Razão:", df.columns.tolist())

    col_data = detectar_coluna(df, ["DATA"])
    col_debito = detectar_coluna(df, ["DEBITO"])
    col_credito = detectar_coluna(df, ["CREDITO"])
    col_entradas = detectar_coluna(df, ["ENTRADA"])
    col_saidas = detectar_coluna(df, ["SAIDA"])

    if not col_data:
        st.error("❌ Coluna DATA não encontrada no Razão")
        st.stop()

    df['DATA'] = pd.to_datetime(df[col_data], errors='coerce')

    if col_debito and col_credito:
        df['ENTRADAS'] = pd.to_numeric(df[col_debito], errors='coerce').fillna(0)
        df['SAIDAS'] = pd.to_numeric(df[col_credito], errors='coerce').fillna(0)
    else:
        df['ENTRADAS'] = pd.to_numeric(df[col_entradas], errors='coerce').fillna(0)
        df['SAIDAS'] = pd.to_numeric(df[col_saidas], errors='coerce').fillna(0)

    df['MOV'] = df['ENTRADAS'] - df['SAIDAS']
    df['TP'] = 'RAZAO'

    return df


# =============================
# 🔗 CHAVE
# =============================
def criar_chave(df):
    df['CHAVE'] = (
        df['DATA'].dt.strftime('%Y-%m-%d') + '_' +
        df['MOV'].round(2).astype(str)
    )
    return df


# =============================
# 🧠 SUGESTÕES
# =============================
def gerar_sugestoes(df_ext, df_raz):
    sugestoes = []

    for _, ext in df_ext.iterrows():
        for _, raz in df_raz.iterrows():

            score = 0

            # Valor
            if ext['MOV'] == raz['MOV']:
                score += 50
            elif abs(ext['MOV'] - raz['MOV']) <= 0.05:
                score += 30

            # Data
            if ext['DATA'] == raz['DATA']:
                score += 50
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


# =============================
# 📤 EXPORTAÇÃO
# =============================
def exportar_excel(dfs):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        for nome, df in dfs.items():
            df.to_excel(writer, sheet_name=nome, index=False)
    return output.getvalue()


# =============================
# 🚀 EXECUÇÃO
# =============================
if file_extrato and file_razao:

    df_ext = carregar_extrato(file_extrato)
    df_raz = carregar_razao(file_razao)

    df_ext = criar_chave(df_ext)
    df_raz = criar_chave(df_raz)

    # =============================
    # 📅 Filtro
    # =============================
    st.sidebar.header("📅 Período")

    data_ini = st.sidebar.date_input("Data Inicial", df_ext['DATA'].min())
    data_fim = st.sidebar.date_input("Data Final", df_ext['DATA'].max())

    df_ext = df_ext[(df_ext['DATA'] >= pd.to_datetime(data_ini)) & (df_ext['DATA'] <= pd.to_datetime(data_fim))]
    df_raz = df_raz[(df_raz['DATA'] >= pd.to_datetime(data_ini)) & (df_raz['DATA'] <= pd.to_datetime(data_fim))]

    # =============================
    # 🔗 MATCH
    # =============================
    conciliados = df_ext.merge(
        df_raz,
        on='CHAVE',
        suffixes=('_EXT', '_RAZ'),
        how='inner'
    )

    nao_ext = df_ext[~df_ext['CHAVE'].isin(conciliados['CHAVE'])]
    nao_raz = df_raz[~df_raz['CHAVE'].isin(conciliados['CHAVE'])]

    sugestoes = gerar_sugestoes(nao_ext, nao_raz)

    # =============================
    # 🖥️ UI
    # =============================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "✅ Conciliados",
        "🧠 Sugestões",
        "⚠️ Extrato",
        "⚠️ Razão",
        "📊 Resumo"
    ])

    with tab1:
        st.dataframe(conciliados, use_container_width=True)

    with tab2:
        st.dataframe(sugestoes.sort_values(by='SCORE', ascending=False), use_container_width=True)

    with tab3:
        st.dataframe(nao_ext, use_container_width=True)

    with tab4:
        st.dataframe(nao_raz, use_container_width=True)

    with tab5:
        st.metric("Total Extrato", f"{df_ext['MOV'].sum():,.2f}")
        st.metric("Total Razão", f"{df_raz['MOV'].sum():,.2f}")
        st.metric("Conciliado", f"{conciliados['MOV_EXT'].sum():,.2f}")
        st.metric("Diferença", f"{df_ext['MOV'].sum() - df_raz['MOV'].sum():,.2f}")

    # =============================
    # 📥 Download
    # =============================
    if st.sidebar.button("📤 Exportar Excel"):
        excel = exportar_excel({
            'Conciliados': conciliados,
            'Sugestoes': sugestoes,
            'Extrato': nao_ext,
            'Razao': nao_raz
        })

        st.sidebar.download_button(
            "Download",
            data=excel,
            file_name="conciliacao.xlsx"
        )

else:
    st.info("👆 Faça upload dos dois arquivos")