import streamlit as st
import pandas as pd

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Gestão Plano de Contas")

# --- INICIALIZAÇÃO DO SESSION_STATE ---
# Verifica se o DataFrame já existe na sessão, se não, cria um vazio.
if 'df_contas' not in st.session_state:
    data = {
        'Código': [],
        'Descrição': [],
        'Tipo': [],
        'Conta Superior': []
    }
    st.session_state.df_contas = pd.DataFrame(data)

# --- FUNÇÕES AUXILIARES ---
def salvar_conta(codigo, descricao, tipo, conta_superior):
    """Adiciona uma nova conta ao DataFrame na sessão."""
    novo_registro = {
        'Código': codigo,
        'Descrição': descricao,
        'Tipo': tipo,
        'Conta Superior': conta_superior if conta_superior else None
    }
    # Concatena o novo registro ao DataFrame existente
    st.session_state.df_contas = pd.concat(
        [st.session_state.df_contas, pd.DataFrame([novo_registro])], 
        ignore_index=True
    )

def get_contas_superiores():
    """Retorna uma lista de códigos para o selectbox de conta superior."""
    if st.session_state.df_contas.empty:
        return []
    # Retorna apenas códigos únicos para evitar duplicidades na lista
    return sorted(st.session_state.df_contas['Código'].unique().tolist())

# --- INTERFACE PRINCIPAL ---
st.title("📊 Gestão de Plano de Contas Contábil")
st.markdown("Sistema simples para cadastro e visualização de contas patrimoniais.")

tab1, tab2 = st.tabs(["📝 Cadastro", "🔍 Visualização"])

# --- ABA 1: CADASTRO ---
with tab1:
    st.subheader("Cadastrar Nova Conta")
    
    with st.form("form_cadastro", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            codigo_input = st.text_input("Código da Conta *", placeholder="Ex: 1.1.01")
            descricao_input = st.text_input("Descrição *", placeholder="Ex: Caixa")
        
        with col2:
            tipo_input = st.selectbox("Tipo da Conta *", ["", "Sintética", "Analítica"])
            
            # Lista dinâmica de contas superiores baseada no DF atual
            lista_superiores = get_contas_superiores()
            # Adiciona opção vazia no início
            opcoes_superior = ["Nenhuma (Conta Raiz)"] + lista_superiores
            
            conta_superior_input = st.selectbox("Conta Superior", options=opcoes_superior)
        
        # Botão de envio
        submit_button = st.form_submit_button("💾 Salvar Conta", use_container_width=True)
        
        # Lógica de validação e salvamento
        if submit_button:
            # 1. Validar campos obrigatórios
            if not codigo_input or not descricao_input or not tipo_input:
                st.error("❌ Erro: Código, Descrição e Tipo são obrigatórios.")
            
            # 2. Validar duplicidade de código
            elif codigo_input in st.session_state.df_contas['Código'].values:
                st.error(f"❌ Erro: O código '{codigo_input}' já está cadastrado.")
            
            # 3. Salvar se tudo estiver correto
            else:
                # Define None se a opção selecionada for a vazia
                superior_final = None if conta_superior_input == "Nenhuma (Conta Raiz)" else conta_superior_input
                
                salvar_conta(codigo_input, descricao_input, tipo_input, superior_final)
                st.success(f"✅ Sucesso: Conta '{descricao_input}' cadastrada com sucesso!")
                # Força a atualização da interface para refletir no selectbox se necessário
                st.rerun()

# --- ABA 2: VISUALIZAÇÃO ---
with tab2:
    st.subheader("Contas Cadastradas")
    
    df = st.session_state.df_contas
    
    if df.empty:
        st.info("ℹ️ Nenhuma conta cadastrada ainda. Vá para a aba 'Cadastro' para começar.")
    else:
        # Exibe o dataframe ordenado pelo código
        df_exibicao = df.sort_values(by='Código').reset_index(drop=True)
        
        # Configuração visual do dataframe
        st.dataframe(
            df_exibicao, 
            use_container_width=True,
            column_config={
                "Código": st.column_config.TextColumn("Código", width="small"),
                "Descrição": st.column_config.TextColumn("Descrição", width="medium"),
                "Tipo": st.column_config.TextColumn("Tipo", width="small"),
                "Conta Superior": st.column_config.TextColumn("Superior", width="small")
            },
            hide_index=True
        )
        
        # Métricas simples
        st.divider()
        col_metric1, col_metric2 = st.columns(2)
        with col_metric1:
            st.metric(label="Total de Contas", value=len(df))
        with col_metric2:
            # Conta quantas são raiz (sem superior)
            raiz_count = df['Conta Superior'].isna().sum()
            st.metric(label="Contas Raiz", value=raiz_count)

# --- RODAPÉ ---
st.markdown("---")
st.caption("Desenvolvido com Streamlit para fins demonstrativos.")