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

        # início de novo registro (linha começando com número)
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
            id_match = re.match(r'^(\d+)', texto)
            numero = id_match.group(1) if id_match else ""

            # REGRA
            regra_match = re.search(r'\b([A-Z]{4}\d{2})\b', texto)
            regra = regra_match.group(1) if regra_match else ""

            # TRIB e CODESC
            trib_match = re.search(r'\b(COFRET|COF|ICMS|IPI|PIS|ISS|INSS|IRF|CSL|DIFAL|CRDPRE)\b', texto)
            trib = trib_match.group(1) if trib_match else ""

            codesc_match = re.search(r'\b([A-Z]{3,5}\d{2})\b', texto)
            codesc = ""

            if codesc_match:
                # evita pegar a REGRA como CODESC
                if codesc_match.group(1) != regra:
                    codesc = codesc_match.group(1)

            # descrição = remove partes conhecidas
            desc = texto

            desc = re.sub(r'^\d+', '', desc)  # remove ID
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

    df = pd.DataFrame(dados)
    return df


if uploaded_file:
    conteudo = uploaded_file.read().decode("latin-1")

    df = processar_txt(conteudo)

    st.dataframe(df, use_container_width=True)

    # gerar excel
    output = BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')

    st.download_button(
        label="📥 Baixar Excel",
        data=output.getvalue(),
        file_name="resultado.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )