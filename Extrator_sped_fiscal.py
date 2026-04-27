import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="SPED Fiscal", layout="wide")

# CSS para reduzir a fonte do grid em 25%
st.markdown("""
<style>
    .stDataFrame {
        font-size: 75% !important;
    }
    .dataframe {
        font-size: 75% !important;
    }
    .stDataFrame div[data-testid="stHorizontalBlock"] {
        font-size: 75% !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 Leitor SPED Fiscal (C100 + C190)")

# =========================
# FUNÇÕES AUXILIARES
# =========================
def to_float(valor):
    try:
        if valor is None:
            return 0.0
        valor = str(valor).replace(",", ".").strip()
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
    """Extrai os dois primeiros dígitos do CST_ICMS e retorna com descrição"""
    try:
        if cst_icms and len(str(cst_icms)) >= 2:
            class_fis_num = str(cst_icms)[:2]
            
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
            
            # Verifica se as colunas necessárias existem
            coluna_cfop = None
            coluna_descricao = None
            
            for col in df_cfop.columns:
                col_lower = col.lower()
                if 'cfop' in col_lower or 'código' in col_lower:
                    coluna_cfop = col
                if 'descri' in col_lower or 'descrição' in col_lower:
                    coluna_descricao = col
            
            if coluna_cfop and coluna_descricao:
                # Renomeia as colunas para padronizar
                df_cfop = df_cfop.rename(columns={coluna_cfop: "CFOP", coluna_descricao: "DESCRICAO"})
                # Converte CFOP para string e remove espaços
                df_cfop["CFOP"] = df_cfop["CFOP"].astype(str).str.strip()
                # Cria um dicionário para busca rápida
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
    """Extrai informações do bloco 0000 - POSIÇÕES CORRETAS DO SPED"""
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
    except Exception as e:
        return data_str


def parse_sped(lines, dict_cfop):
    """Parser para C100 + C190 na mesma linha"""
    dados_completos = []
    nota_atual = None

    for line in lines:
        parts = line.strip().split("|")

        if len(parts) < 2:
            continue

        reg = parts[1]

        if reg == "C100":
            nota_atual = {
                "NUM_DOC": get_part(parts, 8),
                "SER": get_part(parts, 7),
                "DT_DOC": get_part(parts, 10),
                "VL_DOC": to_float(get_part(parts, 12)),
                "CHAVE_NFE": get_part(parts, 9),
                "CST_ICMS": "",
                "CFOP": "",
                "DESC_CFOP": "",
                "ALIQ_ICMS": 0.0,
                "VL_OPR": 0.0,
                "VL_BC_ICMS": 0.0,
                "VL_ICMS": 0.0,
                "VL_BC_ICMS_ST": 0.0,
                "VL_ICMS_ST": 0.0,
                "VL_RED_BC": 0.0,
                "VL_IPI": 0.0,
                "COD_OBS": "",
            }

        elif reg == "C190" and nota_atual is not None:
            cst_icms_original = get_part(parts, 2)
            cfop_numero = get_part(parts, 3)
            
            linha_completa = nota_atual.copy()
            linha_completa.update({
                "CST_ICMS": cst_icms_original,
                "CFOP": cfop_numero,
                "DESC_CFOP": get_descricao_cfop(cfop_numero, dict_cfop),
                "ALIQ_ICMS": to_float(get_part(parts, 9)),
                "VL_OPR": to_float(get_part(parts, 4)),
                "VL_BC_ICMS": to_float(get_part(parts, 6)),
                "VL_ICMS": to_float(get_part(parts, 7)),
                "VL_BC_ICMS_ST": to_float(get_part(parts, 10)),
                "VL_ICMS_ST": to_float(get_part(parts, 11)),
                "VL_RED_BC": to_float(get_part(parts, 12)),
                "VL_IPI": to_float(get_part(parts, 13)),
                "COD_OBS": get_part(parts, 14),
                "ORIGEM_PRODUTO": get_origem_produto(cst_icms_original),
                "CLASS_FIS": get_class_fis(cst_icms_original),
            })
            dados_completos.append(linha_completa)
            nota_atual = None

    df = pd.DataFrame(dados_completos)

    if not df.empty:
        df["DT_DOC"] = pd.to_datetime(
            df["DT_DOC"], format="%d%m%Y", errors="coerce"
        )
        df["DT_DOC"] = df["DT_DOC"].dt.strftime("%d/%m/%Y")

    return df


def processar_arquivo(uploaded_file, dict_cfop):
    """Processa um único arquivo SPED e retorna as informações"""
    content = uploaded_file.read().decode("latin-1")
    lines = content.splitlines()
    
    info_empresa = parse_bloco_0000(lines)
    df_completo = parse_sped(lines, dict_cfop)
    
    return info_empresa, df_completo, uploaded_file.name


def to_excel(df):
    """Converte DataFrame para Excel em memória"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Dados SPED')
    processed_data = output.getvalue()
    return processed_data


# =========================
# INTERFACE PARA MÚLTIPLOS ARQUIVOS
# =========================
# Criar layout com sidebar e conteúdo principal
with st.sidebar:
    st.header("⚙️ Configurações")
    
    # Upload da tabela de CFOP
    st.subheader("📚 Tabela de CFOP")
    arquivo_cfop = st.file_uploader(
    "Carregar tabela CFOP (Excel)", 
    type=["xlsx", "xls"],
    help="Arquivo Excel com colunas: CFOP/Código e Descrição"
    )
    
    # Carregar dicionário de CFOP
    dict_cfop = {}
    if arquivo_cfop:
        dict_cfop = carregar_tabela_cfop(arquivo_cfop)
        if dict_cfop is not None:
            st.success(f"✅ Tabela CFOP carregada com {len(dict_cfop)} registros")
        else:
            st.error("❌ Erro ao carregar tabela CFOP")
    else:
        st.info("ℹ️ Opcional: Carregue uma tabela CFOP para ver descrições")
    
    st.divider()
    
    # Upload dos arquivos SPED
    st.subheader("📁 Arquivos SPED")
    uploaded_files = st.file_uploader(
        "Envie os arquivos SPED (.txt)", 
        type=["txt"], 
        accept_multiple_files=True,
        help="Selecione um ou mais arquivos SPED no formato TXT"
    )
    
    # Botões de download na lateral (aparecem apenas se tiver dados)
    if 'df_exibicao' in locals() and df_exibicao is not None and len(df_exibicao) > 0:
        st.divider()
        st.subheader("📥 Download dos dados")
        
        # Download em CSV
        csv_data = df_exibicao.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📄 Baixar como CSV",
            csv_data,
            "dados_sped_completos.csv",
            "text/csv",
            use_container_width=True
        )
        
        # Download em Excel
        excel_data = to_excel(df_exibicao)
        st.download_button(
            "📊 Baixar como Excel",
            excel_data,
            "dados_sped_completos.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

# =========================
# CONTEÚDO PRINCIPAL
# =========================
if uploaded_files:
    todos_os_dados = []
    
    with st.spinner(f"Processando {len(uploaded_files)} arquivo(s)..."):
        for arquivo in uploaded_files:
            info_empresa, df_completo, nome_arquivo = processar_arquivo(arquivo, dict_cfop)
            
            if not df_completo.empty:
                # Adiciona informações da empresa em CADA LINHA
                df_completo["EMPRESA"] = info_empresa["NOME_EMPRESA"]
                df_completo["CNPJ"] = info_empresa["CNPJ"]
                df_completo["PERIODO_INICIAL"] = formatar_data_brasil(info_empresa["DATA_INICIAL"])
                df_completo["PERIODO_FINAL"] = formatar_data_brasil(info_empresa["DATA_FINAL"])
                df_completo["UF"] = info_empresa["UF"]
                df_completo["IE"] = info_empresa["IE"]
                df_completo["ARQUIVO_ORIGEM"] = nome_arquivo
                
                todos_os_dados.append(df_completo)
    
    if todos_os_dados:
        # Concatena todos os DataFrames
        df_final = pd.concat(todos_os_dados, ignore_index=True)
        
        # =========================
        # GRID ÚNICO COM TUDO (EMPRESA + NOTAS)
        # =========================
        st.subheader("📄 Notas Fiscais + ICMS + Dados da Empresa")
        
        # Ordenar colunas para exibição
        colunas_ordenadas = [
            "EMPRESA", "CNPJ", "UF", "IE", "PERIODO_INICIAL", "PERIODO_FINAL",
            "NUM_DOC", "SER", "DT_DOC", "CHAVE_NFE", "VL_DOC",
            "CST_ICMS", "ORIGEM_PRODUTO", "CLASS_FIS", "CFOP", "DESC_CFOP", "ALIQ_ICMS", 
            "VL_OPR", "VL_BC_ICMS", "VL_ICMS", "VL_BC_ICMS_ST", "VL_ICMS_ST", 
            "VL_RED_BC", "VL_IPI", "COD_OBS", "ARQUIVO_ORIGEM"
        ]
        
        # Garantir que todas as colunas existam
        colunas_existentes = [col for col in colunas_ordenadas if col in df_final.columns]
        df_exibicao = df_final[colunas_existentes]
        
        # Exibir o grid com altura maior e fonte reduzida
        st.dataframe(df_exibicao, use_container_width=True, height=600)
        
        # Mostrar resumo
        st.success(f"✅ {len(uploaded_files)} arquivo(s) processado(s) com sucesso! Total de {len(df_final)} registros de notas fiscais.")
        
    else:
        st.warning("⚠️ Nenhum registro C100/C190 encontrado nos arquivos!")
else:
    st.info("👆 Selecione um ou mais arquivos SPED na barra lateral para começar")