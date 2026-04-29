import streamlit as st
import pandas as pd

st.set_page_config(page_title="Excel Viewer", layout="wide")

with st.sidebar:
    st.header("Upload")
    arquivo = st.file_uploader("Arquivo Excel", type=["xlsx", "xls"])

st.title("Visualizador de Excel")

if arquivo:
    excel = pd.ExcelFile(arquivo)
    
    # Procurar aba "Plano de contas"
    aba_selecionada = None
    for sheet in excel.sheet_names:
        if "Plano" in sheet or sheet == "Plano de contas":
            aba_selecionada = sheet
            break
    
    if aba_selecionada is None:
        aba_selecionada = excel.sheet_names[0]
        st.warning(f"Aba 'Plano de contas' não encontrada. Usando: {aba_selecionada}")
    else:
        st.success(f"Aba selecionada: {aba_selecionada}")
    
    # Ler todos os dados sem cabeçalho
    df_raw = pd.read_excel(arquivo, sheet_name=aba_selecionada, header=None, dtype=str)
    
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
        
        # ========== AUDITORIA ==========
        st.subheader("📊 Auditoria do Tratamento da Coluna Conta")
        
        if "Conta" in df.columns:
            # Antes do tratamento
            st.write("**1. ANTES de qualquer tratamento (primeiras 20 linhas):**")
            st.write(df["Conta"].astype(str).head(20).tolist())
            
            # Remover pontos
            df["Conta_sem_pontos"] = df["Conta"].astype(str).str.replace(".", "")
            st.write("**2. DEPOIS de remover os pontos (primeiras 20 linhas):**")
            st.write(df["Conta_sem_pontos"].head(20).tolist())
            
            # Pegar 10 primeiros caracteres
            df["Conta_10_caracteres"] = df["Conta_sem_pontos"].str[:10]
            st.write("**3. DEPOIS do corte de 10 caracteres (primeiras 20 linhas):**")
            st.write(df["Conta_10_caracteres"].head(20).tolist())
            
            # Totais
            st.write(f"**Total de registros antes do filtro:** {len(df)}")
            
            # Aplicar tratamento na coluna original
            df["Conta"] = df["Conta_10_caracteres"]
            
            # Aplicar filtro
            df_filtrado = df[df["Conta"].astype(str).str.startswith("2103001001")]
            st.write(f"**Total de registros após o filtro:** {len(df_filtrado)}")
            
            st.divider()
            
            # Usar o DataFrame filtrado
            df = df_filtrado
            
            # Remover colunas auxiliares
            df = df.drop(columns=["Conta_sem_pontos", "Conta_10_caracteres"], errors='ignore')
        else:
            st.error("Coluna 'Conta' não encontrada na planilha")
        
        # Manter apenas as colunas desejadas
        colunas_desejadas = ["Conta", "Descricao", "Saldo atual"]
        colunas_existentes = [col for col in colunas_desejadas if col in df.columns]
        
        if colunas_existentes:
            df = df[colunas_existentes]
        
    else:
        # Se não encontrou, exibir normalmente
        st.warning("Cabeçalho 'Conta' e 'Descricao' não encontrado. Exibindo dados crus.")
        df = pd.read_excel(arquivo, sheet_name=aba_selecionada)
    
    # Exibir dados
    if "Conta" in df.columns:
        df["Conta"] = df["Conta"].astype(str)
    
    st.subheader("📋 Dados Finais")
    st.dataframe(df, use_container_width=True)
    
else:
    st.info("Envie um arquivo Excel na sidebar")