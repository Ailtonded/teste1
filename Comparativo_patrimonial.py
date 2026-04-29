import streamlit as st
import pandas as pd

st.set_page_config(page_title="Excel Viewer", layout="wide")

with st.sidebar:
    st.header("Upload")
    arquivo1 = st.file_uploader("Arquivo Excel - Plano de Contas", type=["xlsx", "xls"])
    arquivo2 = st.file_uploader("Arquivo Excel - Posicao dos Titulos", type=["xlsx", "xls"])
    arquivo3 = st.file_uploader("Arquivo 3", type=["xlsx", "xls"])

st.title("Visualizador de Excel")

# Processar primeiro arquivo
df_contabil = None
if arquivo1:
    excel = pd.ExcelFile(arquivo1)
    
    # Procurar aba "Plano de contas"
    aba_selecionada = None
    for sheet in excel.sheet_names:
        if "Plano" in sheet or sheet == "Plano de contas":
            aba_selecionada = sheet
            break
    
    if aba_selecionada is None:
        aba_selecionada = excel.sheet_names[0]
    
    # Ler todos os dados sem cabeçalho
    df_raw = pd.read_excel(arquivo1, sheet_name=aba_selecionada, header=None, dtype=str)
    
    # Procurar linha com "Conta" e "Descricao"
    linha_header = None
    for i in range(len(df_raw)):
        col_a = str(df_raw.iloc[i, 0]) if pd.notna(df_raw.iloc[i, 0]) else ""
        col_b = str(df_raw.iloc[i, 1]) if pd.notna(df_raw.iloc[i, 1]) else ""
        
        if "Conta" in col_a and "Descricao" in col_b:
            linha_header = i
            break
    
    if linha_header is not None:
        # Usar linha encontrada como cabeçalho
        cabecalho = df_raw.iloc[linha_header]
        df = df_raw.iloc[linha_header + 1:].copy()
        df.columns = cabecalho
        
        # Tratamento da coluna Conta (apenas remover pontos)
        if "Conta" in df.columns:
            df["Conta"] = df["Conta"].astype(str).str.replace(".", "")
        
        # Manter apenas as colunas desejadas
        colunas_desejadas = ["Conta", "Descricao", "Saldo atual"]
        colunas_existentes = [col for col in colunas_desejadas if col in df.columns]
        
        if colunas_existentes:
            df = df[colunas_existentes]
        
        # Aplicar filtro com prefixo correto
        if "Conta" in df.columns:
            df_contabil = df[df["Conta"].astype(str).str.startswith("2103001")]
    else:
        # Se não encontrou, exibir normalmente
        df_contabil = pd.read_excel(arquivo1, sheet_name=aba_selecionada)

# Processar segundo arquivo
df_financeiro = None
if arquivo2:
    excel2 = pd.ExcelFile(arquivo2)
    
    # Procurar aba com "Posicao dos Titulos"
    aba_financeiro = None
    for sheet in excel2.sheet_names:
        if "Posicao" in sheet or "Titulos" in sheet:
            aba_financeiro = sheet
            break
    
    if aba_financeiro is None:
        aba_financeiro = excel2.sheet_names[0]
    
    # Ler dados crus
    df_financeiro = pd.read_excel(arquivo2, sheet_name=aba_financeiro, dtype=str)
    
    # Tratamento da coluna "Codigo-Nome do Fornecedor"
    if "Codigo-Nome do Fornecedor" in df_financeiro.columns:
        # Fazer split pelo hífen
        split_df = df_financeiro["Codigo-Nome do Fornecedor"].astype(str).str.split("-", expand=True)
        
        # Criar as novas colunas
        df_financeiro.insert(0, "Cod Fornecedor", split_df[0])
        df_financeiro.insert(1, "Loja", split_df[1])

# Processar terceiro arquivo
df_arquivo3 = None
if arquivo3:
    # Ler a primeira aba sem cabeçalho
    df_raw3 = pd.read_excel(arquivo3, sheet_name=0, header=None, dtype=str)
    
    # Procurar linha com "Codigo"
    linha_header3 = None
    for i in range(len(df_raw3)):
        for col in range(len(df_raw3.columns)):
            valor = str(df_raw3.iloc[i, col]) if pd.notna(df_raw3.iloc[i, col]) else ""
            if "Codigo" in valor:
                linha_header3 = i
                break
        if linha_header3 is not None:
            break
    
    if linha_header3 is not None:
        # Usar linha encontrada como cabeçalho
        cabecalho3 = df_raw3.iloc[linha_header3]
        df_arquivo3 = df_raw3.iloc[linha_header3 + 1:].copy()
        df_arquivo3.columns = cabecalho3
        
        # Remover espaços dos nomes das colunas
        df_arquivo3.columns = df_arquivo3.columns.str.strip()
    else:
        # Se não encontrou "Codigo", exibir dados crus
        df_arquivo3 = pd.read_excel(arquivo3, sheet_name=0, dtype=str)
        # Remover espaços dos nomes das colunas
        df_arquivo3.columns = df_arquivo3.columns.str.strip()

# Realizar LEFT JOIN entre Saldo Financeiro e Arquivo 3
if df_financeiro is not None and df_arquivo3 is not None:
    # Garantir tipos como string e limpar espaços
    df_financeiro["Cod Fornecedor"] = df_financeiro["Cod Fornecedor"].astype(str).str.strip()
    df_financeiro["Loja"] = df_financeiro["Loja"].astype(str).str.strip()
    
    df_arquivo3["Codigo"] = df_arquivo3["Codigo"].astype(str).str.strip()
    df_arquivo3["Loja"] = df_arquivo3["Loja"].astype(str).str.strip()
    
    # LEFT JOIN com as colunas corretas
    df_financeiro = df_financeiro.merge(
        df_arquivo3[["Codigo", "Loja", "C Contabil"]],
        how="left",
        left_on=["Cod Fornecedor", "Loja"],
        right_on=["Codigo", "Loja"]
    )
    
    # Remover coluna duplicada do merge
    df_financeiro = df_financeiro.drop(columns=["Codigo"], errors="ignore")
    
    # Garantir as colunas finais na ordem correta
    colunas_final = [
        "Codigo-Nome do Fornecedor",
        "Cod Fornecedor",
        "Loja",
        "Valor Original",
        "C Contabil"
    ]
    
    df_financeiro = df_financeiro[[col for col in colunas_final if col in df_financeiro.columns]]

# ========== NOVA ABA: COMPARATIVO ==========
df_comp = None
if df_contabil is not None and df_financeiro is not None:
    # Preparar dados do Saldo Contábil
    df_comp_contabil = df_contabil.copy()
    df_comp_contabil["Conta"] = df_comp_contabil["Conta"].astype(str).str.strip()
    
    # Converter Saldo atual para numérico
    df_comp_contabil["Saldo atual"] = (
        df_comp_contabil["Saldo atual"]
        .astype(str)
        .str.replace(".", "")
        .str.replace(",", ".")
        .astype(float)
    )
    
    # Agrupar por Conta
    df_contabil_group = df_comp_contabil.groupby("Conta", as_index=False)["Saldo atual"].sum()
    df_contabil_group.rename(columns={"Saldo atual": "Saldo Contábil"}, inplace=True)
    
    # Preparar dados do Saldo Financeiro
    df_comp_financeiro = df_financeiro.copy()
    df_comp_financeiro["C Contabil"] = df_comp_financeiro["C Contabil"].astype(str).str.strip()
    
    # Converter Valor Original para numérico
    df_comp_financeiro["Valor Original"] = (
        df_comp_financeiro["Valor Original"]
        .astype(str)
        .str.replace(".", "")
        .str.replace(",", ".")
        .astype(float)
    )
    
    # Agrupar por C Contabil
    df_fin_group = df_comp_financeiro.groupby("C Contabil", as_index=False)["Valor Original"].sum()
    df_fin_group.rename(columns={"Valor Original": "Saldo Financeiro"}, inplace=True)
    
    # LEFT JOIN
    df_comp = df_contabil_group.merge(
        df_fin_group,
        how="left",
        left_on="Conta",
        right_on="C Contabil"
    )
    
    # Remover coluna duplicada
    df_comp = df_comp.drop(columns=["C Contabil"], errors="ignore")
    
    # Preencher NaN com 0
    df_comp["Saldo Financeiro"] = df_comp["Saldo Financeiro"].fillna(0)
    
    # Calcular diferença
    df_comp["Diferença"] = df_comp["Saldo Contábil"] - df_comp["Saldo Financeiro"]
    
    # Ordenar pela maior diferença
    df_comp = df_comp.sort_values(by="Diferença", ascending=False)
    
    # Selecionar colunas finais
    colunas_finais = ["Conta", "Saldo Contábil", "Saldo Financeiro", "Diferença"]
    df_comp = df_comp[colunas_finais]

# Exibir abas
if df_contabil is not None or df_financeiro is not None or df_arquivo3 is not None:
    tab1, tab2, tab3, tab4 = st.tabs(["Saldo Contabil", "Saldo Financeiro", "Arquivo 3", "Comparativo"])
    
    with tab1:
        if df_contabil is not None:
            st.subheader("📋 Saldo Contábil")
            st.dataframe(df_contabil, use_container_width=True)
        else:
            st.info("Nenhum arquivo de plano de contas carregado")
    
    with tab2:
        if df_financeiro is not None:
            st.subheader("📋 Saldo Financeiro")
            st.dataframe(df_financeiro, use_container_width=True)
        else:
            st.info("Nenhum arquivo de posição dos títulos carregado")
    
    with tab3:
        if df_arquivo3 is not None:
            st.subheader("📋 Arquivo 3")
            st.dataframe(df_arquivo3, use_container_width=True)
        else:
            st.info("Nenhum arquivo 3 carregado")
    
    with tab4:
        if df_comp is not None:
            st.subheader("📊 Comparativo Contábil vs Financeiro")
            st.dataframe(df_comp, use_container_width=True)
            
            # Exibir resumo
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Contábil", f"R$ {df_comp['Saldo Contábil'].sum():,.2f}")
            with col2:
                st.metric("Total Financeiro", f"R$ {df_comp['Saldo Financeiro'].sum():,.2f}")
            with col3:
                st.metric("Diferença Total", f"R$ {df_comp['Diferença'].sum():,.2f}")
        else:
            st.info("Carregue os arquivos de Saldo Contábil e Financeiro para visualizar o comparativo")
else:
    st.info("Envie os arquivos Excel na sidebar para visualizar os dados")