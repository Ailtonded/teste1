import streamlit as st
import pandas as pd

st.set_page_config(page_title="SPED Fiscal", layout="wide")

st.title("📊 Leitor SPED Fiscal (C100 + C190)")

uploaded_file = st.file_uploader("Envie o arquivo SPED (.txt)", type=["txt"])


# =========================
# FUNÇÕES AUXILIARES
# =========================
def to_float(valor):
    try:
        if valor is None:
            return 0.0
        valor = str(valor).replace(",", ".").strip()
        return float(valor) if valor else 0.0
    except:
        return 0.0


def get_part(parts, index):
    return parts[index] if len(parts) > index else ""


# =========================
# PARSER SPED
# =========================
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
                "NUM_DOC": get_part(parts, 8),
                "SER": get_part(parts, 7),
                "DT_DOC": get_part(parts, 10),
                "VL_DOC": to_float(get_part(parts, 12)),
                "CHAVE_NFE": get_part(parts, 9),
            }

            notas.append(nota_atual)

        # =========================
        # C190 - ICMS
        # =========================
        elif reg == "C190" and nota_atual is not None:
            impostos.append({
                "NUM_DOC": nota_atual["NUM_DOC"],
                "SER": nota_atual["SER"],
                "DT_DOC": nota_atual["DT_DOC"],
                "CHAVE_NFE": nota_atual["CHAVE_NFE"],

                "CST_ICMS": get_part(parts, 2),
                "CFOP": get_part(parts, 3),

                "VL_OPR": to_float(get_part(parts, 4)),
                "VL_BC_ICMS": to_float(get_part(parts, 6)),
                "VL_ICMS": to_float(get_part(parts, 7)),
            })

    df_notas = pd.DataFrame(notas)
    df_impostos = pd.DataFrame(impostos)

    # =========================
    # TRATAR DATAS
    # =========================
    if not df_notas.empty:
        df_notas["DT_DOC"] = pd.to_datetime(
            df_notas["DT_DOC"], format="%d%m%Y", errors="coerce"
        )

    if not df_impostos.empty:
        df_impostos["DT_DOC"] = pd.to_datetime(
            df_impostos["DT_DOC"], format="%d%m%Y", errors="coerce"
        )

    return df_notas, df_impostos


# =========================
# EXECUÇÃO
# =========================
if uploaded_file:

    content = uploaded_file.read().decode("latin-1")
    lines = content.splitlines()

    df_notas, df_impostos = parse_sped(lines)

    # =========================
    # MOSTRAR DADOS
    # =========================
    st.subheader("📄 Notas (C100)")
    st.dataframe(df_notas, use_container_width=True)

    st.subheader("📊 ICMS (C190)")
    st.dataframe(df_impostos, use_container_width=True)

    # =========================
    # FILTRO
    # =========================
    if not df_impostos.empty:
        st.subheader("🔎 Filtro por Data")

        min_date = df_impostos["DT_DOC"].min()
        max_date = df_impostos["DT_DOC"].max()

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

        # =========================
        # VALIDAÇÃO
        # =========================
        st.subheader("🧠 Validação (C190 vs Nota)")

        total_notas = df_notas["VL_DOC"].sum()
        total_icms = df_impostos["VL_OPR"].sum()

        col1, col2 = st.columns(2)

        col1.metric("Total Notas", f"R$ {total_notas:,.2f}")
        col2.metric("Total C190 (VL_OPR)", f"R$ {total_icms:,.2f}")

        if abs(total_notas - total_icms) > 1:
            st.error("⚠️ Diferença entre C100 e C190!")
        else:
            st.success("✅ Valores batem!")

        # =========================
        # DOWNLOAD
        # =========================
        st.download_button(
            "📥 Baixar Resumo CSV",
            resumo.to_csv(index=False).encode("utf-8"),
            "resumo_sped.csv",
            "text/csv"
        )