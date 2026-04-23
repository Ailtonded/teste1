import streamlit as st
import pandas as pd

st.set_page_config(page_title="SPED Fiscal - C100 e C190", layout="wide")

st.title("📄 Leitor SPED Fiscal (C100 + C190)")

uploaded_file = st.file_uploader("Envie o SPED (.txt)", type=["txt"])


def parse_sped(lines):
    notas = []
    impostos = []

    nota_atual = None

    for line in lines:
        parts = line.strip().split("|")

        if len(parts) < 2:
            continue

        reg = parts[1]

        # =========================
        # C100 - NOTA
        # =========================
        if reg == "C100":
            nota_atual = {
                "NUM_DOC": parts[8] if len(parts) > 8 else "",
                "SER": parts[7] if len(parts) > 7 else "",
                "DT_DOC": parts[10] if len(parts) > 10 else "",
                "VL_DOC": float(parts[12]) if len(parts) > 12 and parts[12] else 0,
            }

            notas.append(nota_atual)

        # =========================
        # C190 - ICMS POR CFOP/CST
        # =========================
        elif reg == "C190" and nota_atual is not None:
            impostos.append({
                "NUM_DOC": nota_atual["NUM_DOC"],
                "SER": nota_atual["SER"],
                "DT_DOC": nota_atual["DT_DOC"],
                "CST_ICMS": parts[2] if len(parts) > 2 else "",
                "CFOP": parts[3] if len(parts) > 3 else "",
                "VL_OPR": float(parts[4]) if len(parts) > 4 and parts[4] else 0,
                "VL_BC_ICMS": float(parts[6]) if len(parts) > 6 and parts[6] else 0,
                "VL_ICMS": float(parts[7]) if len(parts) > 7 and parts[7] else 0,
            })

    df_notas = pd.DataFrame(notas)
    df_impostos = pd.DataFrame(impostos)

    # Converter data
    if not df_notas.empty:
        df_notas["DT_DOC"] = pd.to_datetime(df_notas["DT_DOC"], format="%d%m%Y", errors="coerce")

    if not df_impostos.empty:
        df_impostos["DT_DOC"] = pd.to_datetime(df_impostos["DT_DOC"], format="%d%m%Y", errors="coerce")

    return df_notas, df_impostos


if uploaded_file:
    content = uploaded_file.read().decode("latin-1")
    lines = content.splitlines()

    df_notas, df_impostos = parse_sped(lines)

    st.subheader("📄 Notas Fiscais (C100)")
    st.dataframe(df_notas, use_container_width=True)

    st.subheader("📊 ICMS por CFOP/CST (C190)")
    st.dataframe(df_impostos, use_container_width=True)

    # =========================
    # FILTRO POR DATA
    # =========================
    if not df_notas.empty:
        st.subheader("🔎 Filtro por Data")

        min_date = df_notas["DT_DOC"].min()
        max_date = df_notas["DT_DOC"].max()

        col1, col2 = st.columns(2)

        with col1:
            data_ini = st.date_input("Data inicial", min_date)

        with col2:
            data_fim = st.date_input("Data final", max_date)

        df_filtrado = df_impostos[
            (df_impostos["DT_DOC"] >= pd.to_datetime(data_ini)) &
            (df_impostos["DT_DOC"] <= pd.to_datetime(data_fim))
        ]

        st.subheader("📊 ICMS Filtrado")
        st.dataframe(df_filtrado, use_container_width=True)

        # =========================
        # RESUMO
        # =========================
        resumo = df_filtrado.groupby(["CFOP", "CST_ICMS"]).agg({
            "VL_OPR": "sum",
            "VL_BC_ICMS": "sum",
            "VL_ICMS": "sum"
        }).reset_index()

        st.subheader("📈 Resumo por CFOP/CST")
        st.dataframe(resumo, use_container_width=True)

        st.download_button(
            "📥 Baixar resumo",
            resumo.to_csv(index=False).encode("utf-8"),
            "resumo_icms.csv",
            "text/csv"
        )