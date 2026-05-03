import streamlit as st

st.set_page_config(page_title="Gerador CBNF", layout="wide")

# =========================
# STATE (memória da sessão)
# =========================
if "motor" not in st.session_state:
    st.session_state.motor = None

if "pagina" not in st.session_state:
    st.session_state.pagina = "home"

# =========================
# FUNÇÕES DE NAVEGAÇÃO
# =========================
def ir_para(pagina):
    st.session_state.pagina = pagina


# =========================
# TELA HOME
# =========================
def tela_home():
    st.title("⚙️ Gerador de Código CBNF")

    st.markdown("### Escolha o motor de cálculo")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🧾 Motor Legado", use_container_width=True):
            st.session_state.motor = "legado"
            ir_para("legado_home")

    with col2:
        if st.button("🚀 FISA 140", use_container_width=True):
            st.session_state.motor = "fisa140"
            ir_para("fisa_home")


# =========================
# FLUXO LEGADO
# =========================
def tela_legado_home():
    st.title("🧾 Motor Legado")

    st.info("Aqui vão entrar as telas do motor legado (você vai construir depois).")

    if st.button("➡️ Ir para Página 1 (Legado)"):
        ir_para("legado_pagina1")

    if st.button("🔙 Voltar"):
        ir_para("home")


def tela_legado_pagina1():
    st.title("📄 Página 1 - Legado")

    st.write("Conteúdo do legado aqui (configurações, regras, etc).")

    if st.button("🔙 Voltar"):
        ir_para("legado_home")


# =========================
# FLUXO FISA 140
# =========================
def tela_fisa_home():
    st.title("🚀 FISA 140")

    st.success("Aqui você pode configurar o novo motor.")

    # Exemplo de inputs
    empresa = st.text_input("Empresa")
    filial = st.text_input("Filial")
    tipo_operacao = st.selectbox("Tipo de Operação", ["Entrada", "Saída"])

    st.markdown("---")

    if st.button("⚙️ Gerar Configuração"):
        st.code(f"""
# Exemplo de saída CBNF
EMPRESA = {empresa}
FILIAL = {filial}
TIPO = {tipo_operacao}
        """, language="python")

    if st.button("🔙 Voltar"):
        ir_para("home")


# =========================
# ROTEADOR (controle de telas)
# =========================
if st.session_state.pagina == "home":
    tela_home()

elif st.session_state.pagina == "legado_home":
    tela_legado_home()

elif st.session_state.pagina == "legado_pagina1":
    tela_legado_pagina1()

elif st.session_state.pagina == "fisa_home":
    tela_fisa_home()