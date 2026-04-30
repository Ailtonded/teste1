import streamlit as st
import pandas as pd
from io import BytesIO
import re

st.set_page_config(page_title="Excel Viewer", layout="wide")

with st.sidebar:
    st.header("Upload")
    arquivo1 = st.file_uploader("Arquivo Excel - Plano de Contas", type=["xlsx", "xls"])
    arquivo2 = st.file_uploader("Arquivo Excel - Posicao dos Titulos", type=["xlsx", "xls"])
    arquivo3 = st.file_uploader("Cadastro de Fornecedor", type=["xlsx", "xls"])
    arquivo4 = st.file_uploader("Relação de Contas de Fornecedor", type=["xlsx", "xls"])

st.title("Visualizador de Excel")

# ========== FUNÇÃO OTIMIZADA PARA CONVERSÃO DE VALORES ==========
def converter_para_float(valor):
    """Converte valores monetários dos formatos brasileiro/americano para float"""
    if pd.isna(valor) or valor == "" or str(valor).strip() == "":
        return 0.0
    
    valor_str = str(valor).strip()
    
    # Se já é número, retorna diretamente
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return float(valor)
    
    try:
        # Remove espaços
        valor_str = valor_str.replace(" ", "")
        
        # Detecta formato baseado na presença de vírgula
        if "," in valor_str:
            # Formato brasileiro: remove pontos e troca vírgula por ponto
            valor_str = valor_str.replace(".", "").replace(",", ".")
        # Formato americano: mantém como está
        
        return float(valor_str)
    except:
        return 0.0

# ========== FUNÇÃO PARA PADRONIZAR CONTAS ==========
def padronizar_conta(conta):
    """Remove pontos, espaços e padroniza conta para junção"""
    if pd.isna(conta):
        return ""
    return str(conta).strip().replace(".", "")

# ========== PROCESSAR PLANO DE CONTAS ==========
df_contabil = None
df_contabil_original = None

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
    
    # Ler dados crus
    df_raw = pd.read_excel(arquivo1, sheet_name=aba_selecionada, header=None, dtype=str)
    
    # Procurar linha de cabeçalho
    linha_header = None
    for i in range(len(df_raw)):
        col_a = str(df_raw.iloc[i, 0]) if pd.notna(df_raw.iloc[i, 0]) else ""
        col_b = str(df_raw.iloc[i, 1]) if pd.notna(df_raw.iloc[i, 1]) else ""
        
        if "Conta" in col_a and "Descricao" in col_b:
            linha_header = i
            break
    
    if linha_header is not None:
        cabecalho = df_raw.iloc[linha_header]
        df = df_raw.iloc[linha_header + 1:].copy()
        df.columns = cabecalho
        
        # Selecionar colunas necessárias
        colunas_desejadas = ["Conta", "Descricao", "Saldo atual"]
        colunas_existentes = [col for col in colunas_desejadas if col in df.columns]
        
        if colunas_existentes:
            df = df[colunas_existentes]
            df_contabil_original = df.copy()
            
            # Padronizar conta
            df["Conta"] = df["Conta"].apply(padronizar_conta)
            
            # Converter saldo usando função otimizada
            df["Saldo atual"] = df["Saldo atual"].apply(converter_para_float)
            
            df_contabil = df
    else:
        df_contabil_original = pd.read_excel(arquivo1, sheet_name=aba_selecionada)
        df_contabil = df_contabil_original.copy()
        if "Conta" in df_contabil.columns:
            df_contabil["Conta"] = df_contabil["Conta"].apply(padronizar_conta)
        if "Saldo atual" in df_contabil.columns:
            df_contabil["Saldo atual"] = df_contabil["Saldo atual"].apply(converter_para_float)

# ========== APLICAR FILTRO POR RELAÇÃO DE CONTAS ==========
if arquivo4 and df_contabil is not None:
    try:
        df_relacao = pd.read_excel(arquivo4, dtype=str)
        contas_permitidas = df_relacao.iloc[:, 0].apply(padronizar_conta).tolist()
        df_contabil = df_contabil[df_contabil["Conta"].isin(contas_permitidas)]
        st.sidebar.success(f"✅ Filtrado: {len(df_contabil)} contas de fornecedor")
    except Exception as e:
        st.sidebar.error(f"Erro ao ler relação de contas: {e}")

# ========== PROCESSAR POSIÇÃO DOS TÍTULOS ==========
df_financeiro = None

if arquivo2:
    excel2 = pd.ExcelFile(arquivo2)
    
    # Procurar aba
    aba_financeiro = None
    for sheet in excel2.sheet_names:
        if "Posicao" in sheet or "Titulos" in sheet:
            aba_financeiro = sheet
            break
    
    if aba_financeiro is None:
        aba_financeiro = excel2.sheet_names[0]
    
    df_financeiro = pd.read_excel(arquivo2, sheet_name=aba_financeiro, dtype=str)
    
    # ========== FILTRO: REMOVER LINHAS ONDE Tp = "PA" ==========
    if "Tp" in df_financeiro.columns:
        antes = len(df_financeiro)
        df_financeiro = df_financeiro[df_financeiro["Tp"].astype(str).str.upper() != "PA"]
        depois = len(df_financeiro)
        st.sidebar.info(f"✅ Removidas {antes - depois} linhas com Tp=PA - Restam {depois} registros")
    
    # Tratar coluna Codigo-Nome do Fornecedor
    if "Codigo-Nome do Fornecedor" in df_financeiro.columns:
        split_df = df_financeiro["Codigo-Nome do Fornecedor"].astype(str).str.split("-", expand=True)
        df_financeiro.insert(0, "Cod Fornecedor", split_df[0])
        df_financeiro.insert(1, "Loja", split_df[1])
    
    # Converter Valor Original
    if "Valor Original" in df_financeiro.columns:
        df_financeiro["Valor Original"] = df_financeiro["Valor Original"].apply(converter_para_float)

# ========== PROCESSAR CADASTRO DE FORNECEDOR ==========
df_fornecedor = None

if arquivo3:
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
        cabecalho3 = df_raw3.iloc[linha_header3]
        df_fornecedor = df_raw3.iloc[linha_header3 + 1:].copy()
        df_fornecedor.columns = cabecalho3
        df_fornecedor.columns = df_fornecedor.columns.str.strip()
    else:
        df_fornecedor = pd.read_excel(arquivo3, sheet_name=0, dtype=str)
        df_fornecedor.columns = df_fornecedor.columns.str.strip()

# ========== JOIN FINANCEIRO COM CADASTRO ==========
if df_financeiro is not None and df_fornecedor is not None:
    # Padronizar colunas para join
    if "Cod Fornecedor" in df_financeiro.columns:
        df_financeiro["Cod Fornecedor"] = df_financeiro["Cod Fornecedor"].astype(str).str.strip()
    
    if "Loja" in df_financeiro.columns:
        df_financeiro["Loja"] = df_financeiro["Loja"].astype(str).str.strip()
    
    if "Codigo" in df_fornecedor.columns:
        df_fornecedor["Codigo"] = df_fornecedor["Codigo"].astype(str).str.strip()
    
    if "Loja" in df_fornecedor.columns:
        df_fornecedor["Loja"] = df_fornecedor["Loja"].astype(str).str.strip()
    
    if "C Contabil" in df_fornecedor.columns:
        df_financeiro = df_financeiro.merge(
            df_fornecedor[["Codigo", "Loja", "C Contabil"]],
            how="left",
            left_on=["Cod Fornecedor", "Loja"],
            right_on=["Codigo", "Loja"]
        )
        df_financeiro = df_financeiro.drop(columns=["Codigo"], errors="ignore")
        
        # Padronizar C Contabil
        df_financeiro["C Contabil"] = df_financeiro["C Contabil"].apply(padronizar_conta)
    else:
        st.warning("⚠️ Coluna 'C Contabil' não encontrada no Cadastro de Fornecedor")

# ========== CONSTRUIR COMPARATIVO OTIMIZADO ==========
df_comp = None

if df_contabil is not None and df_financeiro is not None:
    
    # ========== PASSO 1: Agrupar Saldo Contábil ==========
    df_contabil_group = df_contabil.groupby("Conta", as_index=False)["Saldo atual"].sum()
    df_contabil_group.rename(columns={"Saldo atual": "Saldo Contábil"}, inplace=True)
    
    # ========== PASSO 2: Agrupar Saldo Financeiro ==========
    if "C Contabil" in df_financeiro.columns and "Valor Original" in df_financeiro.columns:
        df_financeiro_group = df_financeiro.groupby("C Contabil", as_index=False)["Valor Original"].sum()
        df_financeiro_group.rename(columns={"C Contabil": "Conta", "Valor Original": "Saldo Financeiro"}, inplace=True)
    else:
        df_financeiro_group = pd.DataFrame(columns=["Conta", "Saldo Financeiro"])
        st.warning("⚠️ Dados financeiros incompletos para conciliação")
    
    # ========== PASSO 3: Criar base única de contas ==========
    contas_unicas = pd.concat([
        df_contabil_group["Conta"],
        df_financeiro_group["Conta"]
    ], ignore_index=True).drop_duplicates().reset_index(drop=True)
    
    contas_unicas = pd.DataFrame({"Conta": contas_unicas})
    
    # ========== PASSO 4: LEFT JOINS ==========
    df_comp = contas_unicas.merge(df_contabil_group, on="Conta", how="left")
    df_comp = df_comp.merge(df_financeiro_group, on="Conta", how="left")
    
    # ========== PASSO 5: Tratar nulos ==========
    df_comp["Saldo Contábil"] = df_comp["Saldo Contábil"].fillna(0)
    df_comp["Saldo Financeiro"] = df_comp["Saldo Financeiro"].fillna(0)
    
    # ========== PASSO 6: Adicionar Razão Social ==========
    if df_fornecedor is not None and "Razao Social" in df_fornecedor.columns and "C Contabil" in df_fornecedor.columns:
        df_razao = df_fornecedor.copy()
        df_razao["C Contabil"] = df_razao["C Contabil"].apply(padronizar_conta)
        df_razao["Razao Social"] = df_razao["Razao Social"].astype(str).str.strip()
        
        df_razao_group = df_razao.groupby("C Contabil")["Razao Social"].apply(
            lambda x: ", ".join(x.unique())
        ).reset_index()
        df_razao_group.rename(columns={"C Contabil": "Conta"}, inplace=True)
        
        df_comp = df_comp.merge(df_razao_group, on="Conta", how="left")
        df_comp["Razao Social"] = df_comp["Razao Social"].fillna("")
    
    # ========== PASSO 7: Calcular Diferença ==========
    df_comp["Diferença"] = df_comp["Saldo Contábil"] - df_comp["Saldo Financeiro"]
    
    # ========== PASSO 8: Calcular Tp (versão vetorizada) ==========
    cond_ambos = (df_comp["Saldo Contábil"] != 0) & (df_comp["Saldo Financeiro"] != 0)
    cond_apenas_contabil = (df_comp["Saldo Contábil"] != 0) & (df_comp["Saldo Financeiro"] == 0)
    cond_apenas_financeiro = (df_comp["Saldo Financeiro"] != 0) & (df_comp["Saldo Contábil"] == 0)
    
    df_comp["Tp"] = "0-Sem Saldo"
    df_comp.loc[cond_ambos, "Tp"] = "3-Ambos"
    df_comp.loc[cond_apenas_contabil, "Tp"] = "2-Saldo Contábil"
    df_comp.loc[cond_apenas_financeiro, "Tp"] = "1-Saldo Financeiro"
    
    # ========== PASSO 9: Aplicar regra para NÃO trazer apenas financeiro ==========
    df_comp = df_comp[df_comp["Tp"] != "1-Saldo Financeiro"]
    
    # ========== PASSO 10: Ordenar ==========
    df_comp = df_comp.sort_values(by="Diferença", ascending=False).reset_index(drop=True)
    
    # ========== PASSO 11: Selecionar colunas finais ==========
    colunas_finais = ["Conta", "Razao Social", "Tp", "Saldo Contábil", "Saldo Financeiro", "Diferença"]
    colunas_existentes = [col for col in colunas_finais if col in df_comp.columns]
    df_comp = df_comp[colunas_existentes]

# ========== FUNÇÃO PARA SANITIZAR NOMES DE ABAS ==========
def sanitizar_nome_aba(nome):
    nome = re.sub(r'[^\w\s\u00C0-\u00FF-]', '', nome)
    nome = nome.strip()
    return nome[:31]

# ========== EXPORTAÇÃO PARA EXCEL ==========
def exportar_para_excel():
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        if df_comp is not None and len(df_comp) > 0:
            df_comp.to_excel(writer, sheet_name=sanitizar_nome_aba("Comparativo"), index=False)
        
        if df_contabil is not None:
            df_contabil.to_excel(writer, sheet_name=sanitizar_nome_aba("Saldo Contabil"), index=False)
        
        if df_financeiro is not None:
            df_financeiro_export = df_financeiro.copy()
            if "C Contabil" not in df_financeiro_export.columns:
                df_financeiro_export["C Contabil"] = ""
            df_financeiro_export.to_excel(writer, sheet_name=sanitizar_nome_aba("Saldo Financeiro"), index=False)
        
        if df_fornecedor is not None:
            df_fornecedor.to_excel(writer, sheet_name=sanitizar_nome_aba("Cadastro"), index=False)
    
    output.seek(0)
    return output

# ========== INTERFACE STREAMLIT ==========
if df_contabil is not None or df_financeiro is not None or df_fornecedor is not None:
    
    with st.sidebar:
        st.divider()
        if st.button("📥 Exportar para Excel", type="primary", use_container_width=True):
            with st.spinner("Gerando arquivo..."):
                excel_data = exportar_para_excel()
                st.download_button(
                    label="✅ Baixar arquivo",
                    data=excel_data,
                    file_name="relatorio_conciliacao.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
    
    tab1, tab2, tab3, tab4 = st.tabs(["Saldo Contabil", "Saldo Financeiro", "Cadastro", "Comparativo"])
    
    with tab1:
        if df_contabil is not None:
            st.subheader("📋 Saldo Contábil")
            st.dataframe(df_contabil, use_container_width=True)
            if arquivo4:
                st.caption(f"✅ Filtrado pela relação - Total: {len(df_contabil)} contas")
        else:
            st.info("Nenhum arquivo carregado")
    
    with tab2:
        if df_financeiro is not None:
            st.subheader("📋 Saldo Financeiro")
            
            # Mostrar versão agrupada por C Contabil
            if "C Contabil" in df_financeiro.columns and "Valor Original" in df_financeiro.columns:
                df_financeiro_agrupado = df_financeiro.groupby("C Contabil", as_index=False)["Valor Original"].sum()
                df_financeiro_agrupado["Valor Original"] = df_financeiro_agrupado["Valor Original"].apply(lambda x: f"R$ {x:,.2f}")
                st.dataframe(df_financeiro_agrupado, use_container_width=True)
                st.caption(f"📊 Total de registros agrupados: {len(df_financeiro_agrupado)}")
            else:
                st.dataframe(df_financeiro, use_container_width=True)
        else:
            st.info("Nenhum arquivo carregado")
    
    with tab3:
        if df_fornecedor is not None:
            st.subheader("📋 Cadastro de Fornecedor")
            st.dataframe(df_fornecedor, use_container_width=True)
        else:
            st.info("Nenhum arquivo carregado")
    
    with tab4:
        if df_comp is not None and len(df_comp) > 0:
            st.subheader("📊 Comparativo Contábil vs Financeiro")
            
            df_comp_filtrado = df_comp.copy()
            colunas_texto = ["Conta", "Razao Social", "Tp"]
            colunas_numericas = ["Saldo Contábil", "Saldo Financeiro", "Diferença"]
            
            with st.expander("🔍 Filtros", expanded=True):
                col1, col2, col3 = st.columns(3)
                filtros_texto = {}
                
                for idx, col in enumerate(colunas_texto):
                    if col in df_comp.columns:
                        with [col1, col2, col3][idx % 3]:
                            st.markdown(f"**{col}**")
                            tipo_filtro = st.selectbox("Tipo", ["Contém", "Igual a"], key=f"tipo_{col}", label_visibility="collapsed")
                            valor_filtro = st.text_input("Valor", key=f"valor_{col}", placeholder=f"Filtrar {col}...", label_visibility="collapsed")
                            if valor_filtro:
                                filtros_texto[col] = {"tipo": tipo_filtro, "valor": valor_filtro}
                
                st.markdown("---")
                st.markdown("**Filtros Numéricos**")
                col_n1, col_n2, col_n3 = st.columns(3)
                
                for idx, col in enumerate(colunas_numericas):
                    if col in df_comp.columns:
                        with [col_n1, col_n2, col_n3][idx % 3]:
                            st.markdown(f"**{col}**")
                            min_val = st.number_input("Mínimo", key=f"min_{col}", value=None, placeholder="Mínimo", label_visibility="collapsed")
                            max_val = st.number_input("Máximo", key=f"max_{col}", value=None, placeholder="Máximo", label_visibility="collapsed")
                            if min_val is not None or max_val is not None:
                                if col not in filtros_texto:
                                    filtros_texto[col] = {}
                                if min_val is not None:
                                    filtros_texto[col]["min"] = min_val
                                if max_val is not None:
                                    filtros_texto[col]["max"] = max_val
            
            # Aplicar filtros
            for col, config in filtros_texto.items():
                if col in colunas_texto and "tipo" in config and config["valor"]:
                    valor = config["valor"]
                    if config["tipo"] == "Contém":
                        df_comp_filtrado = df_comp_filtrado[df_comp_filtrado[col].astype(str).str.contains(valor, case=False, na=False)]
                    else:
                        df_comp_filtrado = df_comp_filtrado[df_comp_filtrado[col].astype(str).str.lower() == valor.lower()]
                elif col in colunas_numericas:
                    if "min" in config:
                        df_comp_filtrado = df_comp_filtrado[df_comp_filtrado[col] >= config["min"]]
                    if "max" in config:
                        df_comp_filtrado = df_comp_filtrado[df_comp_filtrado[col] <= config["max"]]
            
            st.caption(f"📊 Mostrando {len(df_comp_filtrado)} de {len(df_comp)} registros")
            
            df_comp_display = df_comp_filtrado.copy()
            for col in colunas_numericas:
                if col in df_comp_display.columns:
                    df_comp_display[col] = df_comp_display[col].apply(lambda x: f"R$ {x:,.2f}")
            
            st.dataframe(df_comp_display, use_container_width=True)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Contábil", f"R$ {df_comp_filtrado['Saldo Contábil'].sum():,.2f}")
            with col2:
                st.metric("Total Financeiro", f"R$ {df_comp_filtrado['Saldo Financeiro'].sum():,.2f}")
            with col3:
                st.metric("Diferença Total", f"R$ {df_comp_filtrado['Diferença'].sum():,.2f}")
            
            with st.expander("📈 Estatísticas"):
                st.write(f"**Total de Contas:** {len(df_comp_filtrado)}")
                st.write(f"**Contas com diferença:** {len(df_comp_filtrado[df_comp_filtrado['Diferença'] != 0])}")
                if len(df_comp_filtrado) > 0:
                    st.write(f"**Maior diferença positiva:** R$ {df_comp_filtrado['Diferença'].max():,.2f}")
                    st.write(f"**Maior diferença negativa:** R$ {df_comp_filtrado['Diferença'].min():,.2f}")
        else:
            st.info("Carregue os arquivos para visualizar o comparativo")
else:
    st.info("Envie os arquivos Excel na sidebar")