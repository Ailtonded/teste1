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
# PARSER SPED (C100 + C190 NA MESMA LINHA)
# =========================
def parse_sped(lines):
    dados_completos = []
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
                # Inicializa campos do C190 como vazios
                "CST_ICMS": "",
                "CFOP": "",
                "VL_OPR": 0.0,
                "VL_BC_ICMS": 0.0,
                "VL_ICMS": 0.0,
            }

        # =========================
        # C190 - ICMS (vincula à nota atual)
        # =========================
        elif reg == "C190" and nota_atual is not None:
            # Cria uma linha combinando C100 + C190
            linha_completa = nota_atual.copy()
            linha_completa.update({
                "CST_ICMS": get_part(parts, 2),
                "CFOP": get_part(parts, 3),
                "VL_OPR": to_float(get_part(parts, 4)),
                "VL_BC_ICMS": to_float(get_part(parts, 6)),
                "VL_ICMS": to_float(get_part(parts, 7)),
            })
            dados_completos.append(linha_completa)
            nota_atual = None  # Reseta após vincular

    df = pd.DataFrame(dados_completos)

    # =========================
    # TRATAR DATAS
    # =========================
    if not df.empty:
        df["DT_DOC"] = pd.to_datetime(
            df["DT_DOC"], format="%d%m%Y", errors="coerce"
        )

    return df


# =========================
# EXECUÇÃO
# =========================
if uploaded_file:

    content = uploaded_file.read().decode("latin-1")
    lines = content.splitlines()

    df_completo = parse_sped(lines)

    if df_completo.empty:
        st.warning("⚠️ Nenhum registro C100/C190 encontrado no arquivo!")
    else:
        # =========================
        # MOSTRAR DADOS COMPLETOS
        # =========================
        st.subheader("📄 Notas Fiscais + ICMS (C100 e C190 na mesma linha)")
        st.dataframe(df_completo, use_container_width=True)

        # =========================
        # FILTRO POR DATA
        # =========================
        st.subheader("🔎 Filtro por Data")

        min_date = df_completo["DT_DOC"].min()
        max_date = df_completo["DT_DOC"].max()

        col1, col2 = st.columns(2)

        with col1:
            data_ini = st.date_input("Data inicial", min_date)

        with col2:
            data_fim = st.date_input("Data final", max_date)

        df_filtrado = df_completo[
            (df_completo["DT_DOC"] >= pd.to_datetime(data_ini)) &
            (df_completo["DT_DOC"] <= pd.to_datetime(data_fim))
        ]

        st.subheader("📊 Dados Filtrados")
        st.dataframe(df_filtrado, use_container_width=True)

        # =========================
        # RESUMO POR CFOP/CST
        # =========================
        if not df_filtrado.empty:
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
            st.subheader("🧠 Validação (C100 vs C190)")

            total_notas = df_filtrado["VL_DOC"].sum()
            total_icms = df_filtrado["VL_OPR"].sum()

            col1, col2 = st.columns(2)

            col1.metric("Total Notas (C100)", f"R$ {total_notas:,.2f}")
            col2.metric("Total C190 (VL_OPR)", f"R$ {total_icms:,.2f}")

            if abs(total_notas - total_icms) > 1:
                st.error("⚠️ Diferença entre C100 e C190!")
            else:
                st.success("✅ Valores batem!")

            # =========================
            # DOWNLOAD
            # =========================
            st.download_button(
                "📥 Baixar Dados Completos CSV",
                df_filtrado.to_csv(index=False).encode("utf-8"),
                "sped_c100_c190.csv",
                "text/csv"
            )

            st.download_button(
                "📥 Baixar Resumo CSV",
                resumo.to_csv(index=False).encode("utf-8"),
                "resumo_sped.csv",
                "text/csv"
            )