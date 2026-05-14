import streamlit as st
import streamlit.components.v1 as components
import json

st.set_page_config(
    page_title="Gerador de Prompts",
    layout="wide"
)

PROMPTS = {
    "Lançamento de OS": """
Reescreva o texto abaixo em tom de OS,
iniciando frases com verbos de ação no passado particípio.

Utilize linguagem técnica, clara e objetiva.
Corrija erros de ortografia, gramática e concordância.
""",

    "Comentário em Chamado": """
Reescreva em tom de comentário em histórico de chamado,
de forma clara, técnica, profissional e objetiva.
Corrija erros de ortografia, gramática e concordância.
""",

    "Situação Inicial": """
Reescreva em tom de situação inicial,
relatando o que o cliente está solicitando e apontando.

Utilize linguagem técnica e profissional,
com expressões como:
"Cliente reportou",
"Cliente informou",
"Cliente relatou",
"Foi identificado conforme relato do cliente".

Corrija erros de ortografia, gramática e concordância.
""",

    "Situação Final": """
Reescreva em tom de situação final,
relatando como foi realizada a análise,
o que foi identificado durante a investigação do problema,
indicando de forma clara a origem da inconsistência
e a solução aplicada.

Quando necessário, incluir recomendações,
orientações adicionais e próximos passos.

Utilize linguagem técnica, clara e profissional.
Corrija erros de ortografia, gramática e concordância.
"""
}

st.title("📝 Gerador de Prompts")

tipo = st.radio(
    "Selecione o tipo de texto:",
    list(PROMPTS.keys()),
    horizontal=True
)

texto_base = st.text_area(
    "Cole o texto base:",
    height=300,
    placeholder="Cole aqui o texto..."
)

resultado = f"""{PROMPTS[tipo].strip()}

[{texto_base.strip()}]
"""

col1, col2 = st.columns(2)

with col1:
    gerar = st.button("🚀 Gerar Prompt")

with col2:
    copiar = st.button("📋 Copiar Prompt")

if gerar:

    st.success("Prompt gerado com sucesso!")

    st.text_area(
        "Resultado:",
        value=resultado,
        height=350
    )

if copiar:

    texto_json = json.dumps(resultado)

    components.html(
        f"""
        <script>
            navigator.clipboard.writeText({texto_json});
        </script>

        <div style="
            padding:10px;
            background:#d4edda;
            color:#155724;
            border-radius:5px;
            font-weight:bold;
        ">
            ✅ Prompt copiado com sucesso!
        </div>
        """,
        height=60,
    )