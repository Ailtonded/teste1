import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="SPED Fiscal Completo", layout="wide")

# CSS para reduzir a fonte do grid em 25%
st.markdown("""
<style>
    .stDataFrame {
        font-size: 75% !important;
    }
    .dataframe {
        font-size: 75% !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 Leitor SPED Fiscal (C100 + C170 + C190 + C197)")

# =========================
# FUNÇÕES AUXILIARES
# =========================
def to_float(valor):
    try:
        if valor is None:
            return 0.0
        valor = str(valor).replace(",", ".").strip()
        # Remove caracteres não numéricos exceto ponto
        valor = ''.join(c for c in valor if c.isdigit() or c == '.')
        return float(valor) if valor else 0.0
    except:
        return 0.0

def get_part(parts, index):
    return parts[index] if len(parts) > index else ""

def get_origem_produto(cst_icms):
    """Extrai o primeiro dígito do CST_ICMS para identificar a origem do produto"""
    try:
        if cst_icms and len(str(cst_icms)) > 0:
            primeiro_digito = str(cst_icms)[0]
            origem_map = {
                "0": "0 - Nacional",
                "1": "1 - Estrangeira - Importação direta",
                "2": "2 - Estrangeira - Adquirida no mercado interno",
                "3": "3 - Nacional - Conteúdo de importação > 40%",
                "4": "4 - Nacional - Produção conforme processo produtivo básico",
                "5": "5 - Nacional - Conteúdo de importação < 40%",
                "6": "6 - Estrangeira - Importação direta sem similar nacional",
                "7": "7 - Estrangeira - Adquirida no mercado interno sem similar nacional",
                "8": "8 - Nacional - Conteúdo de importação > 70%"
            }
            return origem_map.get(primeiro_digito, f"{primeiro_digito} - Origem desconhecida")
        return "Sem origem"
    except:
        return "Erro"

def get_class_fis(cst_icms):
    """Extrai as posições 2 e 3 do CST_ICMS (dois últimos dígitos) e retorna com descrição"""
    try:
        if cst_icms and len(str(cst_icms)) >= 3:
            cst_str = str(cst_icms)
            class_fis_num = cst_str[1:3]  # Pega posições 2 e 3
            
            class_fis_map = {
                "00": "00 - Tributada integralmente",
                "10": "10 - Tributada e com cobrança do ICMS por substituição tributária",
                "20": "20 - Com redução de base de cálculo",
                "30": "30 - Isenta ou não tributada e com cobrança do ICMS por substituição tributária",
                "40": "40 - Isenta",
                "41": "41 - Não tributada",
                "50": "50 - Suspensão",
                "51": "51 - Diferimento",
                "60": "60 - ICMS cobrado anteriormente por substituição tributária",
                "70": "70 - Com redução de base de cálculo e cobrança do ICMS por substituição tributária",
                "90": "90 - Outras"
            }
            
            return class_fis_map.get(class_fis_num, f"{class_fis_num} - Classificação não mapeada")
        elif cst_icms and len(str(cst_icms)) == 2:
            class_fis_num = str(cst_icms)
            class_fis_map = {
                "00": "00 - Tributada integralmente",
                "10": "10 - Tributada e com cobrança do ICMS por substituição tributária",
                "20": "20 - Com redução de base de cálculo",
                "30": "30 - Isenta ou não tributada e com cobrança do ICMS por substituição tributária",
                "40": "40 - Isenta",
                "41": "41 - Não tributada",
                "50": "50 - Suspensão",
                "51": "51 - Diferimento",
                "60": "60 - ICMS cobrado anteriormente por substituição tributária",
                "70": "70 - Com redução de base de cálculo e cobrança do ICMS por substituição tributária",
                "90": "90 - Outras"
            }
            return class_fis_map.get(class_fis_num, f"{class_fis_num} - Classificação não mapeada")
        return ""
    except:
        return ""

def carregar_tabela_cfop(arquivo_cfop):
    """Carrega a tabela de CFOP do arquivo Excel"""
    try:
        if arquivo_cfop is not None:
            df_cfop = pd.read_excel(arquivo_cfop)
            
            coluna_cfop = None
            coluna_descricao = None
            
            for col in df_cfop.columns:
                col_lower = col.lower()
                if 'cfop' in col_lower or 'código' in col_lower:
                    coluna_cfop = col
                if 'descri' in col_lower or 'descrição' in col_lower:
                    coluna_descricao = col
            
            if coluna_cfop and coluna_descricao:
                df_cfop = df_cfop.rename(columns={coluna_cfop: "CFOP", coluna_descricao: "DESCRICAO"})
                df_cfop["CFOP"] = df_cfop["CFOP"].astype(str).str.strip()
                dict_cfop = dict(zip(df_cfop["CFOP"], df_cfop["DESCRICAO"]))
                return dict_cfop
            else:
                st.error("❌ O arquivo Excel deve conter colunas com 'CFOP'/'Código' e 'Descrição'")
                return None
        else:
            return {}
    except Exception as e:
        st.error(f"❌ Erro ao carregar arquivo de CFOP: {str(e)}")
        return None

def get_descricao_cfop(cfop, dict_cfop):
    """Retorna apenas a descrição do CFOP sem o número"""
    try:
        if not dict_cfop:
            return ""
        
        cfop_str = str(cfop).strip()
        descricao = dict_cfop.get(cfop_str, "")
        
        if descricao:
            return descricao
        else:
            return "CFOP não encontrado"
    except:
        return ""

def parse_bloco_0000(lines):
    """Extrai informações do bloco 0000"""
    info = {
        "DATA_INICIAL": "",
        "DATA_FINAL": "",
        "NOME_EMPRESA": "",
        "CNPJ": "",
        "UF": "",
        "IE": ""
    }
    
    for line in lines:
        parts = line.strip().split("|")
        if len(parts) < 2:
            continue
        
        reg = parts[1]
        
        if reg == "0000":
            info["DATA_INICIAL"] = get_part(parts, 4)
            info["DATA_FINAL"] = get_part(parts, 5)
            info["NOME_EMPRESA"] = get_part(parts, 6)
            info["CNPJ"] = get_part(parts, 7)
            info["UF"] = get_part(parts, 9)
            info["IE"] = get_part(parts, 10)
            break
            
    return info

def formatar_data_brasil(data_str):
    """Converte data do formato DDMMAAAA para DD/MM/AAAA"""
    try:
        if not data_str:
            return ""
        
        data_str = str(data_str).strip()
        
        if len(data_str) == 8 and data_str.isdigit():
            dia = data_str[0:2]
            mes = data_str[2:4]
            ano = data_str[4:8]
            return f"{dia}/{mes}/{ano}"
        else:
            return data_str
    except:
        return data_str

def parse_sped(lines, dict_cfop):
    """
    Parser completo para SPED Fiscal.
    Retorna dois DataFrames:
    1. df_c100_c190 (Resumo por nota/CST/CFOP)
    2. df_c170 (Detalhamento de itens)
    """
    
    # Listas para armazenar os dados
    dados_c100_c190 = []
    dados_c170 = []
    
    # Variáveis de controle
    nota_atual = None
    primeiro_item_c197 = None

    # Mapeamento de colunas do C170 para garantir ordem e existência
    cols_c170_order = [
        "NUM_ITEM", "COD_ITEM", "DESCR_COMPL", "QTD", "UNID", "VL_ITEM", "VL_DESC", 
        "IND_MOV", "CST_ICMS", "CFOP", "COD_NAT", "VL_BC_ICMS", "ALIQ_ICMS", "VL_ICMS", 
        "VL_BC_ICMS_ST", "ALIQ_ST", "VL_ICMS_ST", "IND_APUR", "CST_IPI", "COD_ENQ", 
        "VL_BC_IPI", "ALIQ_IPI", "VL_IPI", "CST_PIS", "VL_BC_PIS", "ALIQ_PIS_PERC", 
        "QUANT_BC_PIS", "ALIQ_PIS_REAIS", "VL_PIS", "CST_COFINS", "VL_BC_COFINS", 
        "ALIQ_COFINS_PERC", "QUANT_BC_COFINS", "ALIQ_COFINS_REAIS", "VL_COFINS", 
        "COD_CTA", "VL_ABAT_NT"
    ]

    for line in lines:
        parts = line.strip().split("|")

        if len(parts) < 2:
            continue

        reg = parts[1]

        # -----------------------------------
        # REGISTRO C100 (Cabeçalho da Nota)
        # -----------------------------------
        if reg == "C100":
            # Estrutura base para C100/C190
            nota_atual = {
                "NUM_DOC": get_part(parts, 8),
                "SER": get_part(parts, 7),
                "DT_DOC": get_part(parts, 10),
                "VL_DOC": to_float(get_part(parts, 12)),
                "CHAVE_NFE": get_part(parts, 9),
                # Campos para C170 (serão herdados)
                "_header_info": {
                    "NUM_DOC": get_part(parts, 8),
                    "SER": get_part(parts, 7),
                    "DT_DOC": get_part(parts, 10),
                    "CHAVE_NFE": get_part(parts, 9),
                }
            }
            primeiro_item_c197 = None  # Reseta o controle do C197

        # -----------------------------------
        # REGISTRO C170 (Itens da Nota)
        # -----------------------------------
        elif reg == "C170" and nota_atual is not None:
            # Extrair todos os campos do C170
            # Layout: |REG|NUM_ITEM|COD_ITEM|DESCR_COMPL|QTD|UNID|VL_ITEM|...
            
            item_data = {
                "NUM_ITEM": get_part(parts, 2),
                "COD_ITEM": get_part(parts, 3),
                "DESCR_COMPL": get_part(parts, 4),
                "QTD": to_float(get_part(parts, 5)),
                "UNID": get_part(parts, 6),
                "VL_ITEM": to_float(get_part(parts, 7)),
                "VL_DESC": to_float(get_part(parts, 8)),
                "IND_MOV": get_part(parts, 9),
                "CST_ICMS": get_part(parts, 10),
                "CFOP": get_part(parts, 11),
                "COD_NAT": get_part(parts, 12),
                "VL_BC_ICMS": to_float(get_part(parts, 13)),
                "ALIQ_ICMS": to_float(get_part(parts, 14)),
                "VL_ICMS": to_float(get_part(parts, 15)),
                "VL_BC_ICMS_ST": to_float(get_part(parts, 16)),
                "ALIQ_ST": to_float(get_part(parts, 17)),
                "VL_ICMS_ST": to_float(get_part(parts, 18)),
                "IND_APUR": get_part(parts, 19),
                "CST_IPI": get_part(parts, 20),
                "COD_ENQ": get_part(parts, 21),
                "VL_BC_IPI": to_float(get_part(parts, 22)),
                "ALIQ_IPI": to_float(get_part(parts, 23)),
                "VL_IPI": to_float(get_part(parts, 24)),
                "CST_PIS": get_part(parts, 25),
                "VL_BC_PIS": to_float(get_part(parts, 26)),
                "ALIQ_PIS_PERC": to_float(get_part(parts, 27)),
                "QUANT_BC_PIS": to_float(get_part(parts, 28)),
                "ALIQ_PIS_REAIS": to_float(get_part(parts, 29)),
                "VL_PIS": to_float(get_part(parts, 30)),
                "CST_COFINS": get_part(parts, 31),
                "VL_BC_COFINS": to_float(get_part(parts, 32)),
                "ALIQ_COFINS_PERC": to_float(get_part(parts, 33)),
                "QUANT_BC_COFINS": to_float(get_part(parts, 34)),
                "ALIQ_COFINS_REAIS": to_float(get_part(parts, 35)),
                "VL_COFINS": to_float(get_part(parts, 36)),
                "COD_CTA": get_part(parts, 37),
                "VL_ABAT_NT": to_float(get_part(parts, 38)),
            }
            
            # Adicionar informações do cabeçalho (C100) ao item
            item_data.update(nota_atual["_header_info"])
            
            # Adicionar descrição do CFOP e classificações
            cfop_item = item_data["CFOP"]
            cst_item = item_data["CST_ICMS"]
            
            item_data["DESC_CFOP"] = get_descricao_cfop(cfop_item, dict_cfop)
            item_data["ORIGEM_PRODUTO"] = get_origem_produto(cst_item)
            item_data["CLASS_FIS"] = get_class_fis(cst_item)
            
            dados_c170.append(item_data)

        # -----------------------------------
        # REGISTRO C197 (Observações do Lançamento Fiscal)
        # -----------------------------------
        elif reg == "C197" and nota_atual is not None and primeiro_item_c197 is None:
            # Mantendo lógica original para capturar o primeiro C197 para o C190
            # parts[4] é COD_ITEM no layout padrão, ou parts[2] dependendo da versão.
            # Mantendo parts[4] conforme correção anterior.
            cod_item = get_part(parts, 4) 
            primeiro_item_c197 = cod_item

        # -----------------------------------
        # REGISTRO C190 (Totais por CST/CFOP)
        # -----------------------------------
        elif reg == "C190" and nota_atual is not None:
            cst_icms_original = get_part(parts, 2)
            cfop_numero = get_part(parts, 3)
            
            linha_completa = {
                "NUM_DOC": nota_atual["NUM_DOC"],
                "SER": nota_atual["SER"],
                "DT_DOC": nota_atual["DT_DOC"],
                "VL_DOC": nota_atual["VL_DOC"],
                "CHAVE_NFE": nota_atual["CHAVE_NFE"],
                
                "CST_ICMS": cst_icms_original,
                "CFOP": cfop_numero,
                "DESC_CFOP": get_descricao_cfop(cfop_numero, dict_cfop),
                "ALIQ_ICMS": to_float(get_part(parts, 4)),
                "VL_OPR": to_float(get_part(parts, 5)),
                "VL_BC_ICMS": to_float(get_part(parts, 6)),
                "VL_ICMS": to_float(get_part(parts, 7)),
                "VL_BC_ICMS_ST": to_float(get_part(parts, 8)),
                "VL_ICMS_ST": to_float(get_part(parts, 9)),
                "VL_RED_BC": to_float(get_part(parts, 10)),
                "VL_IPI": to_float(get_part(parts, 11)),
                "COD_OBS": get_part(parts, 12),
                "ORIGEM_PRODUTO": get_origem_produto(cst_icms_original),
                "CLASS_FIS": get_class_fis(cst_icms_original),
                "COD_ITEM": primeiro_item_c197 if primeiro_item_c197 else "",
            }
            dados_c100_c190.append(linha_completa)
            # Não reseta nota_atual aqui para permitir múltiplos C190 para mesma nota
            # A nota_atual será sobrescrita apenas no próximo C100

    # Criar DataFrames
    df_c190 = pd.DataFrame(dados_c100_c190)
    df_c170 = pd.DataFrame(dados_c170)

    # Formatação de datas
    if not df_c190.empty:
        df_c190["DT_DOC"] = pd.to_datetime(df_c190["DT_DOC"], format="%d%m%Y", errors="coerce")
        df_c190["DT_DOC"] = df_c190["DT_DOC"].dt.strftime("%d/%m/%Y")

    if not df_c170.empty:
        df_c170["DT_DOC"] = pd.to_datetime(df_c170["DT_DOC"], format="%d%m%Y", errors="coerce")
        df_c170["DT_DOC"] = df_c170["DT_DOC"].dt.strftime("%d/%m/%Y")
        
        # Reordenar colunas do C170 para lógica: Identificação -> Produto -> Valores
        cols_front = ["NUM_DOC", "SER", "DT_DOC", "CHAVE_NFE", "NUM_ITEM", "COD_ITEM", "DESCR_COMPL", "QTD", "UNID"]
        cols_middle = ["CFOP", "DESC_CFOP", "CST_ICMS", "ORIGEM_PRODUTO", "CLASS_FIS"]
        
        # Todas as outras colunas que não estão nas listas acima
        other_cols = [c for c in df_c170.columns if c not in cols_front and c not in cols_middle]
        
        # Ordem final
        final_order = cols_front + cols_middle + other_cols
        # Filtrar apenas colunas que existem de fato
        final_order = [c for c in final_order if c in df_c170.columns]
        
        df_c170 = df_c170[final_order]

    return df_c190, df_c170


def processar_arquivo(uploaded_file, dict_cfop):
    """Processa um único arquivo SPED retornando ambos os DataFrames"""
    content = uploaded_file.read().decode("latin-1")
    lines = content.splitlines()
    
    info_empresa = parse_bloco_0000(lines)
    df_c190, df_c170 = parse_sped(lines, dict_cfop)
    
    return info_empresa, df_c190, df_c170, uploaded_file.name


def to_excel_multi(df_c190, df_c170):
    """Converte DataFrames para Excel com múltiplas abas"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not df_c190.empty:
            df_c190.to_excel(writer, index=False, sheet_name='Resumo C100-C190')
        if not df_c170.empty:
            df_c170.to_excel(writer, index=False, sheet_name='Itens C170')
    return output.getvalue()


# =========================
# INTERFACE
# =========================
with st.sidebar:
    st.header("⚙️ Configurações")
    
    st.subheader("📚 Tabela de CFOP")
    arquivo_cfop = st.file_uploader(
        "Carregar tabela CFOP (Excel)", 
        type=["xlsx", "xls"],
        help="Arquivo Excel com colunas: CFOP/Código e Descrição"
    )
    
    dict_cfop = {}
    if arquivo_cfop:
        dict_cfop = carregar_tabela_cfop(arquivo_cfop)
        if dict_cfop is not None:
            st.success(f"✅ Tabela CFOP carregada com {len(dict_cfop)} registros")
        else:
            st.error("❌ Erro ao carregar tabela CFOP")
    else:
        st.info("ℹ️ Opcional: Carregue uma tabela CFOP")
    
    st.divider()
    
    st.subheader("📁 Arquivos SPED")
    uploaded_files = st.file_uploader(
        "Envie os arquivos SPED (.txt)", 
        type=["txt"], 
        accept_multiple_files=True
    )

# =========================
# CONTEÚDO PRINCIPAL
# =========================
if uploaded_files:
    todos_c190 = []
    todos_c170 = []
    
    with st.spinner(f"Processando {len(uploaded_files)} arquivo(s)..."):
        for arquivo in uploaded_files:
            info_empresa, df_c190, df_c170, nome_arquivo = processar_arquivo(arquivo, dict_cfop)
            
            # Processar Resumo C100/C190
            if not df_c190.empty:
                df_c190["EMPRESA"] = info_empresa["NOME_EMPRESA"]
                df_c190["CNPJ"] = info_empresa["CNPJ"]
                df_c190["PERIODO_INICIAL"] = formatar_data_brasil(info_empresa["DATA_INICIAL"])
                df_c190["PERIODO_FINAL"] = formatar_data_brasil(info_empresa["DATA_FINAL"])
                df_c190["UF"] = info_empresa["UF"]
                df_c190["IE"] = info_empresa["IE"]
                df_c190["ARQUIVO_ORIGEM"] = nome_arquivo
                todos_c190.append(df_c190)
            
            # Processar Itens C170
            if not df_c170.empty:
                df_c170["EMPRESA"] = info_empresa["NOME_EMPRESA"]
                df_c170["CNPJ"] = info_empresa["CNPJ"]
                df_c170["ARQUIVO_ORIGEM"] = nome_arquivo
                todos_c170.append(df_c170)
    
    # Concatenar resultados
    df_final_c190 = pd.concat(todos_c190, ignore_index=True) if todos_c190 else pd.DataFrame()
    df_final_c170 = pd.concat(todos_c170, ignore_index=True) if todos_c170 else pd.DataFrame()
    
    if not df_final_c190.empty or not df_final_c170.empty:
        
        tab1, tab2 = st.tabs(["📄 Resumo Notas (C100/C190)", "📦 Itens da Nota (C170)"])
        
        # =========================
        # ABA 1: C100/C190 (Mantendo lógica original)
        # =========================
        with tab1:
            if not df_final_c190.empty:
                st.subheader("Resumo Fiscal por CST/CFOP")
                
                colunas_ordenadas_c190 = [
                    "EMPRESA", "CNPJ", "UF", "IE", "PERIODO_INICIAL", "PERIODO_FINAL",
                    "NUM_DOC", "SER", "DT_DOC", "CHAVE_NFE", "VL_DOC",
                    "CST_ICMS", "ORIGEM_PRODUTO", "CLASS_FIS",
                    "CFOP", "DESC_CFOP",
                    "ALIQ_ICMS", "VL_OPR", "VL_BC_ICMS", "VL_ICMS",
                    "VL_BC_ICMS_ST", "VL_ICMS_ST", "VL_RED_BC", "VL_IPI", "COD_OBS",
                    "COD_ITEM", 
                    "ARQUIVO_ORIGEM"
                ]
                
                colunas_existentes = [col for col in colunas_ordenadas_c190 if col in df_final_c190.columns]
                df_view_c190 = df_final_c190[colunas_existentes]
                
                st.dataframe(df_view_c190, use_container_width=True, height=600)
                st.info(f"Total de {len(df_view_c190)} registros resumidos.")
            else:
                st.warning("Nenhum registro C100/C190 encontrado.")

        # =========================
        # ABA 2: C170 (Nova funcionalidade)
        # =========================
        with tab2:
            if not df_final_c170.empty:
                st.subheader("Detalhamento dos Itens (C170)")
                
                # O DataFrame já vem ordenado da função de parser
                st.dataframe(df_final_c170, use_container_width=True, height=600)
                st.info(f"Total de {len(df_final_c170)} itens extraídos.")
            else:
                st.warning("Nenhum registro C170 encontrado.")
        
        # =========================
        # DOWNLOADS
        # =========================
        st.divider()
        st.subheader("📥 Download dos dados")
        
        col1, col2 = st.columns(2)
        
        # Botão Excel (Agora contém duas abas)
        with col1:
            excel_data = to_excel_multi(df_final_c190, df_final_c170)
            st.download_button(
                "📊 Baixar Excel (Completo)",
                excel_data,
                "sped_completo_c170_c190.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        
        # Botão CSV C170 (Novo)
        with col2:
            if not df_final_c170.empty:
                csv_c170 = df_final_c170.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "📄 Baixar CSV Itens (C170)",
                    csv_c170,
                    "itens_c170.csv",
                    "text/csv",
                    use_container_width=True
                )
            else:
                st.download_button(
                    "📄 Baixar CSV Resumo (C190)",
                    df_final_c190.to_csv(index=False).encode("utf-8"),
                    "resumo_c190.csv",
                    "text/csv",
                    use_container_width=True,
                    disabled=True
                )
        
    else:
        st.warning("⚠️ Nenhum registro encontrado nos arquivos enviados!")
else:
    st.info("👆 Selecione um ou mais arquivos SPED na barra lateral")