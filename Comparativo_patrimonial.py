import streamlit as st
import pandas as pd

def main():
    st.set_page_config(page_title="Leitor de Excel", layout="wide")
    
    st.title("📊 Leitor de Arquivos Excel")
    st.write("Faça upload de um arquivo Excel para visualizar suas colunas e linhas")
    
    # Upload do arquivo
    arquivo = st.file_uploader("Escolha um arquivo Excel", type=["xlsx", "xls"])
    
    if arquivo is not None:
        try:
            # Ler o arquivo Excel
            df = pd.read_excel(arquivo)
            
            # Exibir informações básicas
            st.subheader("📋 Informações do Arquivo")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total de Linhas", df.shape[0])
            
            with col2:
                st.metric("Total de Colunas", df.shape[1])
            
            with col3:
                st.metric("Total de Células", df.shape[0] * df.shape[1])
            
            # Exibir colunas
            st.subheader("📑 Colunas da Planilha")
            
            colunas_df = pd.DataFrame({
                "Nº": range(1, len(df.columns) + 1),
                "Nome da Coluna": df.columns,
                "Tipo de Dado": df.dtypes.values
            })
            
            st.dataframe(colunas_df, use_container_width=True)
            
            # Opção para visualizar os dados
            st.subheader("🔍 Visualização dos Dados")
            
            linhas_para_mostrar = st.slider(
                "Quantas linhas deseja visualizar?",
                min_value=1,
                max_value=min(100, df.shape[0]),
                value=min(10, df.shape[0])
            )
            
            # Exibir as primeiras linhas
            st.write(f"Mostrando as primeiras **{linhas_para_mostrar}** linhas:")
            st.dataframe(df.head(linhas_para_mostrar), use_container_width=True)
            
            # Opção para ver estatísticas
            if st.checkbox("Mostrar estatísticas básicas"):
                st.subheader("📊 Estatísticas Básicas")
                st.dataframe(df.describe(), use_container_width=True)
            
            # Opção para ver valores nulos
            if st.checkbox("Mostrar valores nulos por coluna"):
                st.subheader("❓ Valores Nulos")
                nulos = pd.DataFrame({
                    "Coluna": df.columns,
                    "Valores Nulos": df.isnull().sum(),
                    "Percentual (%)": (df.isnull().sum() / len(df) * 100).round(2)
                })
                st.dataframe(nulos, use_container_width=True)
                
        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {str(e)}")
    
    else:
        st.info("👈 Faça upload de um arquivo Excel para começar")

if __name__ == "__main__":
    main()