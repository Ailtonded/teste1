import streamlit as st
import pandas as pd
import re
from io import BytesIO

st.title("Conversor TXT → Excel")

uploaded_file = st.file_uploader("Envie o arquivo TXT", type=["txt"])


def processar_txt(conteudo):
    linhas = conteudo.splitlines()

    registros = []
    atual = []

    for linha in linhas:
        linha = linha.strip()

        if not linha:
            continue

        # ignora cabeçalho
        if "F2B_REGRA" in linha:
            continue

        # início de novo registro
        if re.match(r'^\d+\s', linha):
            if atual:
                registros.append(atual)
            atual = [linha]
        else:
            atual.append(linha)

    if atual:
        registros.append(atual)

    dados = []

    for bloco in registros:
        try:
            texto = " ".join(bloco)

            # ID
            numero = re.match(r'^(\d+)', texto)
            numero = numero.group(1) if numero else ""

            # REGRA
            regra_match = re.search(r'\b([A-Z]{4}\d{2})\b', texto)
            regra = regra_match.group(1) if regra_match else ""

            # TRIB + CODESC juntos (mais confiável)
            trib_codesc_match = re.search(
                r'\b(COFRET|COF|ICMS|IPI|PIS|ISS|INSS|IRF|CSL|DIFAL|CRDPRE)\s+([A-Z0-9]+)',
                texto
            )

            if trib_codesc_match:
                trib = trib_codesc_match.group(1)
                codesc = trib_codesc_match.group(2)
            else:
                trib = ""
                codesc = ""

            # descrição limpa
            desc = texto
            desc = re.sub(r'^\d+', '', desc)
            desc = desc.replace(regra, "")
            desc = desc.replace(trib, "")
            desc = desc.replace(codesc, "")
            desc = re.sub(r'Editar', '', desc, flags=re.IGNORECASE)
            desc = re.sub(r'—', '', desc)
            desc = re.sub(r'\s+', ' ', desc).strip()

            dados.append({
                "ID": numero,
                "REGRA": regra,
                "DESCRICAO": desc,
                "TRIB": trib,
                "CODESC": codesc
            })

        except:
            continue

    return pd.DataFrame(dados)


if uploaded_file:
    conteudo = uploaded_file.read().decode("latin-1")

    df = processar_txt(conteudo)

    st.dataframe(df, use_container_width=True)

    output = BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')

    st.download_button(
        label="📥 Baixar Excel",
        data=output.getvalue(),
        file_name="resultado.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )