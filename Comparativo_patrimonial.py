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

# Processar terceiro arquivo (Cadastro de Fornecedor)
df_fornecedor = None
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
        df_fornecedor = df_raw3.iloc[linha_header3 + 1:].copy()
        df_fornecedor.columns = cabecalho3
        
        # Remover espaços dos nomes das colunas
        df_fornecedor.columns = df_fornecedor.columns.str.strip()
    else:
        # Se não encontrou "Codigo", exibir dados crus
        df_fornecedor = pd.read_excel(arquivo3, sheet_name=0, dtype=str)
        # Remover espaços dos nomes das colunas
        df_fornecedor.columns = df_fornecedor.columns.str.strip()

# Realizar LEFT JOIN entre Saldo Financeiro e Cadastro de Fornecedor
if df_financeiro is not None and df_fornecedor is not None:
    # Garantir tipos como string e limpar espaços
    df_financeiro["Cod Fornecedor"] = df_financeiro["Cod Fornecedor"].astype(str).str.strip()
    df_financeiro["Loja"] = df_financeiro["Loja"].astype(str).str.strip()
    
    df_fornecedor["Codigo"] = df_fornecedor["Codigo"].astype(str).str.strip()
    df_fornecedor["Loja"] = df_fornecedor["Loja"].astype(str).str.strip()
    
    # Verificar se a coluna "C Contabil" existe no df_fornecedor
    if "C Contabil" in df_fornecedor.columns:
        # LEFT JOIN com as colunas corretas
        df_financeiro = df_financeiro.merge(
            df_fornecedor[["Codigo", "Loja", "C Contabil"]],
            how="left",
            left_on=["Cod Fornecedor", "Loja"],
            right_on=["Codigo", "Loja"]
        )
        
        # Remover coluna duplicada do merge
        df_financeiro = df_financeiro.drop(columns=["Codigo"], errors="ignore")
    else:
        st.warning("⚠️ Coluna 'C Contabil' não encontrada no Cadastro de Fornecedor")
    
    # Garantir as colunas finais na ordem correta
    colunas_final = [
        "Codigo-Nome do Fornecedor",
        "Cod Fornecedor",
        "Loja",
        "Valor Original",
        "C Contabil"
    ]
    
    colunas_existentes = [col for col in colunas_final if col in df_financeiro.columns]
    if colunas_existentes:
        df_financeiro = df_financeiro[colunas_existentes]

# ========== NOVA ABA: COMPARATIVO (MELHORADO) ==========
df_comp = None
if df_contabil is not None and df_financeiro is not None:
    # Função segura para converter para float
    def converter_para_float(valor):
        try:
            if pd.isna(valor) or valor == "" or valor == "nan":
                return 0.0
            valor_str = str(valor).strip()
            
            # Verificar se é formato brasileiro (contém vírgula)
            if "," in valor_str:
                # Formato brasileiro: remover pontos de milhar e substituir vírgula por ponto
                valor_str = valor_str.replace(".", "").replace(",", ".")
            else:
                # Formato americano: apenas remover caracteres não numéricos exceto ponto
                valor_str = valor_str.replace(" ", "")
            
            return float(valor_str)
        except:
            return 0.0
    
    # ========== PASSO 1: Preparar Saldo Contábil ==========
    df_comp_contabil = df_contabil.copy()
    df_comp_contabil["Conta"] = df_comp_contabil["Conta"].astype(str).str.strip()
    df_comp_contabil["Saldo atual"] = df_comp_contabil["Saldo atual"].apply(converter_para_float)
    
    df_contabil_group = df_comp_contabil.groupby("Conta", as_index=False)["Saldo atual"].sum()
    df_contabil_group.rename(columns={"Saldo atual": "Saldo Contábil"}, inplace=True)
    
    # ========== PASSO 2: Preparar Saldo Financeiro ==========
    df_comp_financeiro = df_financeiro.copy()
    
    # Verificar se a coluna "C Contabil" existe
    if "C Contabil" in df_comp_financeiro.columns:
        df_comp_financeiro["C Contabil"] = df_comp_financeiro["C Contabil"].astype(str).str.strip()
        df_comp_financeiro["Valor Original"] = df_comp_financeiro["Valor Original"].apply(converter_para_float)
        
        df_fin_group = df_comp_financeiro.groupby("C Contabil", as_index=False)["Valor Original"].sum()
        df_fin_group.rename(columns={"Valor Original": "Saldo Financeiro"}, inplace=True)
    else:
        st.warning("⚠️ Coluna 'C Contabil' não encontrada no Saldo Financeiro")
        df_fin_group = pd.DataFrame(columns=["C Contabil", "Saldo Financeiro"])
    
    # ========== PASSO 3: Preparar Razão Social do Cadastro de Fornecedor ==========
    df_razao = None
    if df_fornecedor is not None and "Razao Social" in df_fornecedor.columns and "C Contabil" in df_fornecedor.columns:
        df_temp = df_fornecedor.copy()
        df_temp["C Contabil"] = df_temp["C Contabil"].astype(str).str.strip()
        df_temp["Razao Social"] = df_temp["Razao Social"].astype(str).str.strip()
        
        # Agrupar e concatenar valores únicos da Razão Social
        df_razao = df_temp.groupby("C Contabil")["Razao Social"].apply(
            lambda x: ", ".join(x.unique())
        ).reset_index()
        df_razao.rename(columns={"C Contabil": "Conta"}, inplace=True)
    
    # ========== PASSO 4: Criar base única de contas ==========
    contas_unicas = pd.concat([
        df_contabil_group[["Conta"]],
        df_fin_group[["C Contabil"]].rename(columns={"C Contabil": "Conta"}) if len(df_fin_group) > 0 else pd.DataFrame(columns=["Conta"])
    ], ignore_index=True)
    
    if len(contas_unicas) > 0:
        contas_unicas = contas_unicas.drop_duplicates(subset=["Conta"]).copy()
        contas_unicas["Conta"] = contas_unicas["Conta"].astype(str).str.strip()
        contas_unicas = contas_unicas.sort_values(by="Conta").reset_index(drop=True)
        
        # ========== PASSO 5: LEFT JOIN com Saldo Contábil ==========
        df_comp = contas_unicas.copy()
        
        df_comp = df_comp.merge(
            df_contabil_group,
            how="left",
            left_on="Conta",
            right_on="Conta"
        )
        
        # ========== PASSO 6: LEFT JOIN com Saldo Financeiro ==========
        if len(df_fin_group) > 0:
            df_comp = df_comp.merge(
                df_fin_group,
                how="left",
                left_on="Conta",
                right_on="C Contabil"
            )
            df_comp = df_comp.drop(columns=["C Contabil"], errors="ignore")
        else:
            df_comp["Saldo Financeiro"] = 0
        
        # ========== PASSO 7: LEFT JOIN com Razão Social ==========
        if df_razao is not None:
            df_comp = df_comp.merge(
                df_razao,
                how="left",
                left_on="Conta",
                right_on="Conta"
            )
        
        # ========== PASSO 7.1: Filtrar apenas contas que existem em contas_unicas ==========
        df_comp = df_comp[df_comp["Conta"].isin(contas_unicas["Conta"])]
        
        # ========== PASSO 8: Tratar valores nulos ==========
        df_comp["Saldo Contábil"] = df_comp["Saldo Contábil"].fillna(0)
        df_comp["Saldo Financeiro"] = df_comp["Saldo Financeiro"].fillna(0)
        
        if "Razao Social" in df_comp.columns:
            df_comp["Razao Social"] = df_comp["Razao Social"].fillna("")
        
        # ========== PASSO 9: Calcular diferença ==========
        df_comp["Diferença"] = df_comp["Saldo Contábil"] - df_comp["Saldo Financeiro"]
        
        # ========== PASSO 9.1: Calcular coluna Tp ==========
        def definir_tp(row):
            tem_contabil = row["Saldo Contábil"] != 0
            tem_financeiro = row["Saldo Financeiro"] != 0
            
            if tem_contabil and tem_financeiro:
                return "3-Ambos"
            elif tem_financeiro and not tem_contabil:
                return "1-Saldo Financeiro"
            elif tem_contabil and not tem_financeiro:
                return "2-Saldo Contábil"
            else:
                return ""
        
        df_comp["Tp"] = df_comp.apply(definir_tp, axis=1)
        
        # ========== PASSO 10: Ordenar pela maior diferença ==========
        df_comp = df_comp.sort_values(by="Diferença", ascending=False).reset_index(drop=True)
        
        # ========== PASSO 11: Selecionar colunas finais ==========
        colunas_finais = ["Conta", "Razao Social", "Tp", "Saldo Contábil", "Saldo Financeiro", "Diferença"]
        colunas_existentes = [col for col in colunas_finais if col in df_comp.columns]
        df_comp = df_comp[colunas_existentes]

# ========== FUNÇÃO PARA SANITIZAR NOMES DE ABAS DO EXCEL ==========
def sanitizar_nome_aba(nome):
    # Remover emojis e caracteres especiais
    nome = re.sub(r'[^\w\s\u00C0-\u00FF-]', '', nome)
    # Remover espaços extras
    nome = nome.strip()
    # Limitar a 31 caracteres
    return nome[:31]

# ========== FUNÇÃO PARA EXPORTAR EXCEL ==========
def exportar_para_excel():
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Aba 1: Comparativo
        if df_comp is not None and len(df_comp) > 0:
            df_comp.to_excel(writer, sheet_name=sanitizar_nome_aba("Comparativo Contabil vs Financeiro"), index=False)
        
        # Aba 2: Saldo Contábil
        if df_contabil is not None:
            df_contabil.to_excel(writer, sheet_name=sanitizar_nome_aba("Saldo Contabil"), index=False)
        
        # Aba 3: Saldo Financeiro
        if df_financeiro is not None:
            # Garantir que a coluna "C Contabil" exista
            df_financeiro_export = df_financeiro.copy()
            if "C Contabil" not in df_financeiro_export.columns:
                df_financeiro_export["C Contabil"] = ""
            df_financeiro_export.to_excel(writer, sheet_name=sanitizar_nome_aba("Saldo Financeiro"), index=False)
        
        # Aba 4: Cadastro de Fornecedor
        if df_fornecedor is not None:
            df_fornecedor.to_excel(writer, sheet_name=sanitizar_nome_aba("Cadastro de Fornecedor"), index=False)
    
    output.seek(0)
    return output

# ========== EXIBIÇÃO DAS ABAS NO STREAMLIT ==========
if df_contabil is not None or df_financeiro is not None or df_fornecedor is not None:
    # Botão de exportação na sidebar
    with st.sidebar:
        st.divider()
        if st.button("📥 Exportar para Excel", type="primary", use_container_width=True):
            with st.spinner("Gerando arquivo Excel..."):
                excel_data = exportar_para_excel()
                st.download_button(
                    label="✅ Clique aqui para baixar o arquivo",
                    data=excel_data,
                    file_name="relatorio_concilicacao.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
    
    # Tabs de visualização
    tab1, tab2, tab3, tab4 = st.tabs(["Saldo Contabil", "Saldo Financeiro", "Cadastro de Fornecedor", "Comparativo"])
    
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
        if df_fornecedor is not None:
            st.subheader("📋 Cadastro de Fornecedor")
            st.dataframe(df_fornecedor, use_container_width=True)
        else:
            st.info("Nenhum arquivo de cadastro de fornecedor carregado")
    
    with tab4:
        if df_comp is not None and len(df_comp) > 0:
            st.subheader("📊 Comparativo Contábil vs Financeiro")
            
            # ========== FILTROS INTERATIVOS ==========
            df_comp_filtrado = df_comp.copy()
            
            # Identificar colunas de texto e numéricas
            colunas_texto = ["Conta", "Razao Social", "Tp"]
            colunas_numericas = ["Saldo Contábil", "Saldo Financeiro", "Diferença"]
            
            # Filtros para colunas de texto
            with st.expander("🔍 Filtros", expanded=True):
                col1, col2, col3 = st.columns(3)
                
                filtros_texto = {}
                for idx, col in enumerate(colunas_texto):
                    if col in df_comp.columns:
                        with [col1, col2, col3][idx % 3]:
                            st.markdown(f"**{col}**")
                            tipo_filtro = st.selectbox(
                                "Tipo",
                                ["Contém", "Igual a"],
                                key=f"tipo_{col}",
                                label_visibility="collapsed"
                            )
                            valor_filtro = st.text_input(
                                "Valor",
                                key=f"valor_{col}",
                                placeholder=f"Filtrar {col}...",
                                label_visibility="collapsed"
                            )
                            if valor_filtro:
                                filtros_texto[col] = {"tipo": tipo_filtro, "valor": valor_filtro}
                
                # Filtros para colunas numéricas
                st.markdown("---")
                st.markdown("**Filtros Numéricos (deixe em branco para ignorar)**")
                
                col_n1, col_n2, col_n3 = st.columns(3)
                
                for idx, col in enumerate(colunas_numericas):
                    if col in df_comp.columns:
                        with [col_n1, col_n2, col_n3][idx % 3]:
                            st.markdown(f"**{col}**")
                            min_val = st.number_input(
                                f"Mínimo",
                                key=f"min_{col}",
                                value=None,
                                placeholder="Mínimo",
                                label_visibility="collapsed"
                            )
                            max_val = st.number_input(
                                f"Máximo",
                                key=f"max_{col}",
                                value=None,
                                placeholder="Máximo",
                                label_visibility="collapsed"
                            )
                            if min_val is not None or max_val is not None:
                                if col not in filtros_texto:
                                    filtros_texto[col] = {}
                                if min_val is not None:
                                    filtros_texto[col]["min"] = min_val
                                if max_val is not None:
                                    filtros_texto[col]["max"] = max_val
            
            # Aplicar filtros de texto
            for col, config in filtros_texto.items():
                if col in colunas_texto and "tipo" in config:
                    valor = config["valor"]
                    if valor:
                        if config["tipo"] == "Contém":
                            df_comp_filtrado = df_comp_filtrado[df_comp_filtrado[col].astype(str).str.contains(valor, case=False, na=False)]
                        elif config["tipo"] == "Igual a":
                            df_comp_filtrado = df_comp_filtrado[df_comp_filtrado[col].astype(str).str.lower() == valor.lower()]
            
            # Aplicar filtros numéricos
            for col, config in filtros_texto.items():
                if col in colunas_numericas:
                    if "min" in config:
                        df_comp_filtrado = df_comp_filtrado[df_comp_filtrado[col] >= config["min"]]
                    if "max" in config:
                        df_comp_filtrado = df_comp_filtrado[df_comp_filtrado[col] <= config["max"]]
            
            # Exibir número de registros após filtro
            st.caption(f"📊 Mostrando {len(df_comp_filtrado)} de {len(df_comp)} registros")
            
            # Formatar valores monetários para exibição
            df_comp_display = df_comp_filtrado.copy()
            for col in ["Saldo Contábil", "Saldo Financeiro", "Diferença"]:
                if col in df_comp_display.columns:
                    df_comp_display[col] = df_comp_display[col].apply(lambda x: f"R$ {x:,.2f}")
            
            st.dataframe(df_comp_display, use_container_width=True)
            
            # Exibir resumo com base no filtrado
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Contábil", f"R$ {df_comp_filtrado['Saldo Contábil'].sum():,.2f}")
            with col2:
                st.metric("Total Financeiro", f"R$ {df_comp_filtrado['Saldo Financeiro'].sum():,.2f}")
            with col3:
                st.metric("Diferença Total", f"R$ {df_comp_filtrado['Diferença'].sum():,.2f}")
            
            # Estatísticas adicionais
            with st.expander("📈 Estatísticas do Comparativo"):
                st.write(f"**Total de Contas:** {len(df_comp_filtrado)}")
                st.write(f"**Contas com diferença:** {len(df_comp_filtrado[df_comp_filtrado['Diferença'] != 0])}")
                st.write(f"**Maior diferença positiva:** R$ {df_comp_filtrado['Diferença'].max():,.2f}")
                st.write(f"**Maior diferença negativa:** R$ {df_comp_filtrado['Diferença'].min():,.2f}")
        else:
            st.info("Carregue os arquivos de Saldo Contábil e Financeiro para visualizar o comparativo")
else:
    st.info("Envie os arquivos Excel na sidebar para visualizar os dados")