import streamlit as st
import pandas as pd

def main():
    st.set_page_config(page_title="Leitor de Excel", layout="wide")
    
    st.title("📊 Leitor de Arquivos Excel")
    st.write("Faça upload de um arquivo Excel para visualizar seus dados")
    
    # Upload do arquivo
    arquivo = st.file_uploader("Escolha um arquivo Excel", type=["xlsx", "xls"])
    
    if arquivo is not None:
        try:
            # Ler todas as abas do Excel
            arquivo_excel = pd.ExcelFile(arquivo)
            abas = arquivo_excel.sheet_names
            
            # Perguntar qual aba visualizar
            aba_selecionada = st.selectbox(
                "Selecione a aba que deseja visualizar:",
                options=abas
            )
            
            if aba_selecionada:
                # Ler a aba selecionada
                df = pd.read_excel(arquivo, sheet_name=aba_selecionada)
                
                # Exibir informações
                st.success(f"Exibindo aba: **{aba_selecionada}**")
                
                # Exibir total de linhas e colunas
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total de Linhas", df.shape[0])
                with col2:
                    st.metric("Total de Colunas", df.shape[1])
                
                # Exibir os dados (10 colunas e 10 linhas)
                st.subheader("📋 Dados da Planilha")
                st.write("Mostrando as primeiras 10 linhas e 10 colunas:")
                
                # Pegar apenas as 10 primeiras linhas e 10 primeiras colunas
                linhas_10 = df.head(10)
                colunas_10 = linhas_10.iloc[:, :10]
                
                # Exibir a tabela
                st.dataframe(colunas_10, use_container_width=True)
                
                # Informação adicional
                if df.shape[0] > 10 or df.shape[1] > 10:
                    st.info(f"⚠️ A planilha tem {df.shape[0]} linhas e {df.shape[1]} colunas. Exibindo apenas as primeiras 10 linhas e 10 colunas.")
                
        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {str(e)}")
    
    else:
        st.info("👈 Faça upload de um arquivo Excel para começar")

if __name__ == "__main__":
    main()