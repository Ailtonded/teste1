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

# 1. Criamos uma função para montar o prompt. 
# Isso garante que pegamos o texto e o tipo ATUAL.
def montar_prompt(tipo, texto):
    if not texto.strip():
        return ""
    return f"""
{PROMPTS[tipo].strip()}

[{texto.strip()}]
"""

if "resultado" not in st.session_state:
    st.session_state.resultado = ""

st.title("📝 Gerador de Prompts")

tipo = st.radio(
    "Selecione o tipo de texto:",
    list(PROMPTS.keys()),
    horizontal=True
)

texto_base = st.text_area(
    "Cole o texto base:",
    height=300
)

col1, col2 = st.columns(2)

with col1:
    if st.button("🚀 Gerar Prompt"):
        # Atualiza o estado com o texto atual
        st.session_state.resultado = montar_prompt(tipo, texto_base)

with col2:
    if st.button("📋 Copiar Prompt"):
        # Gera o texto baseado no que está na tela AGORA
        texto_para_copiar = montar_prompt(tipo, texto_base)
        
        if texto_para_copiar:
            # Atualiza o estado para que o texto apareça na área abaixo se não estiver
            st.session_state.resultado = texto_para_copiar
            
            texto_json = json.dumps(texto_para_copiar)

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
        else:
            st.warning("Cole um texto base antes de copiar.")

# Exibe o resultado na tela
if st.session_state.resultado:
    st.success("Prompt gerado com sucesso!")
    st.text_area(
        "Resultado:",
        value=st.session_state.resultado,
        height=350
    )