import streamlit as st
import pandas as pd
import re
from io import BytesIO

st.title("Conversor TXT → Excel")

uploaded_file = st.file_uploader("Envie o arquivo TXT", type=["txt"])

def processar_txt(conteudo):
    linhas = conteudo.splitlines()

    registros = []
    atual = ""

    # Junta linhas até encontrar novo registro (linha começando com número)
    for linha in linhas:
        linha = linha.strip()

        if not linha:
            continue

        if re.match(r'^\d+\t', linha):
            if atual:
                registros.append(atual)
            atual = linha
        else:
            atual += " " + linha

    if atual:
        registros.append(atual)

    dados = []

    for reg in registros:
        partes = reg.split("\t")

        try:
            numero = partes[0]
            regra = partes[1]

            # descrição fica no meio bagunçado
            resto = " ".join(partes[2:])

            # tenta separar descrição do resto final
            match = re.search(r'(COFRET|COF|ICMS|IPI|PIS|ISS|INSS|IRF|CSL|DIFAL|CRDPRE)\s+(\S+)', resto)

            if match:
                desc = resto[:match.start()].strip()
                trib = match.group(1)
                codesc = match.group(2)
            else:
                desc = resto
                trib = ""
                codesc = ""

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

    st.dataframe(df)

    # gerar excel
    output = BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')

    st.download_button(
        label="📥 Baixar Excel",
        data=output.getvalue(),
        file_name="resultado.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )