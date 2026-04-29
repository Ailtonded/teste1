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
    else:
        # Se não encontrou "Codigo", exibir dados crus
        df_arquivo3 = pd.read_excel(arquivo3, sheet_name=0, dtype=str)

# Realizar LEFT JOIN entre Saldo Financeiro e Arquivo 3
if df_financeiro is not None and df_arquivo3 is not None:
    # Verificar nomes das colunas do arquivo3
    st.subheader("🔍 Diagnóstico do JOIN")
    st.write("**Colunas encontradas no Arquivo 3:**")
    st.write(list(df_arquivo3.columns))
    
    # Identificar a coluna de conta contábil
    coluna_contabil = None
    for col in df_arquivo3.columns:
        if "Contabil" in col or "Contábil" in col:
            coluna_contabil = col
            break
    
    if coluna_contabil:
        st.write(f"**Coluna de conta contábil identificada:** '{coluna_contabil}'")
    else:
        st.warning("Coluna 'C Contabil' ou similar não encontrada no Arquivo 3")
    
    # Padronização TOTAL das chaves
    df_financeiro["Cod Fornecedor"] = df_financeiro["Cod Fornecedor"].astype(str).str.strip().str.zfill(8)
    df_financeiro["Loja"] = df_financeiro["Loja"].astype(str).str.strip().str.zfill(4)
    
    if "Codigo" in df_arquivo3.columns:
        df_arquivo3["Codigo"] = df_arquivo3["Codigo"].astype(str).str.strip().str.zfill(8)
    
    if "Loja" in df_arquivo3.columns:
        df_arquivo3["Loja"] = df_arquivo3["Loja"].astype(str).str.strip().str.zfill(4)
    
    # Validar se o JOIN está funcionando (INNER JOIN para teste)
    st.write("**Teste de JOIN (primeiras 5 correspondências):**")
    teste_join = df_financeiro.merge(
        df_arquivo3,
        how="inner",
        left_on=["Cod Fornecedor", "Loja"],
        right_on=["Codigo", "Loja"]
    )
    
    if len(teste_join) > 0:
        st.write(f"✅ Encontradas {len(teste_join)} correspondências")
        st.write(teste_join[["Cod Fornecedor", "Loja", "Codigo"]].head(5))
        
        # Realizar LEFT JOIN com a coluna correta
        if coluna_contabil:
            # Verificar se as colunas existem no dataframe auxiliar
            colunas_merge = ["Codigo", "Loja", coluna_contabil]
            colunas_existentes_merge = [col for col in colunas_merge if col in df_arquivo3.columns]
            
            if len(colunas_existentes_merge) == 3:
                df_financeiro = df_financeiro.merge(
                    df_arquivo3[colunas_existentes_merge],
                    how="left",
                    left_on=["Cod Fornecedor", "Loja"],
                    right_on=["Codigo", "Loja"]
                )
                st.write(f"✅ JOIN realizado com sucesso usando coluna '{coluna_contabil}'")
            else:
                st.error(f"Colunas necessárias não encontradas no Arquivo 3. Encontradas: {list(df_arquivo3.columns)}")
        else:
            st.error("Não foi possível identificar a coluna de conta contábil")
    else:
        st.warning("❌ Nenhuma correspondência encontrada entre os arquivos. Verifique os dados:")
        st.write("**Exemplos do Financeiro:**")
        st.write(df_financeiro[["Cod Fornecedor", "Loja"]].head(10))
        st.write("**Exemplos do Arquivo 3:**")
        if "Codigo" in df_arquivo3.columns and "Loja" in df_arquivo3.columns:
            st.write(df_arquivo3[["Codigo", "Loja"]].head(10))
    
    st.divider()
    
    # Ajustar exibição da aba "Saldo Financeiro"
    colunas_exibir = [
        coluna_contabil if coluna_contabil else "C Contabil",
        "Codigo-Nome do Fornecedor",
        "Cod Fornecedor",
        "Loja",
        "Valor Original"
    ]
    
    colunas_existentes = [col for col in colunas_exibir if col in df_financeiro.columns]
    if colunas_existentes:
        df_financeiro = df_financeiro[colunas_existentes]
    
    # Mostrar colunas após merge
    st.write("**Colunas após o merge:**")
    st.write(list(df_financeiro.columns))

# Exibir abas
if df_contabil is not None or df_financeiro is not None or df_arquivo3 is not None:
    tab1, tab2, tab3 = st.tabs(["Saldo Contabil", "Saldo Financeiro", "Arquivo 3"])
    
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
else:
    st.info("Envie os arquivos Excel na sidebar para visualizar os dados")