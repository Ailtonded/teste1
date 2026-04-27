import streamlit as st
import pandas as pd

st.set_page_config(page_title="SPED Fiscal", layout="wide")

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
            # Mapeamento conforme tabela de origem do SPED com o número no início
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
    """Extrai os dois primeiros dígitos do CST_ICMS para CLASS_FIS"""
    try:
        if cst_icms and len(str(cst_icms)) >= 2:
            return str(cst_icms)[:2]
        return ""
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
            # POSIÇÕES CORRETAS DO REGISTRO 0000:
            # parts[0] = vazio
            # parts[1] = "0000"
            # parts[2] = COD_VER
            # parts[3] = COD_FIN
            # parts[4] = DT_INI (DATA INICIAL)
            # parts[5] = DT_FIN (DATA FINAL)
            # parts[6] = NOME (NOME EMPRESARIAL)
            # parts[7] = CNPJ
            # parts[8] = CPF
            # parts[9] = UF
            # parts[10] = IE (INSCRIÇÃO ESTADUAL)
            
            info["DATA_INICIAL"] = get_part(parts, 4)   # Posição 4 = DT_INI
            info["DATA_FINAL"] = get_part(parts, 5)     # Posição 5 = DT_FIN  
            info["NOME_EMPRESA"] = get_part(parts, 6)   # Posição 6 = NOME
            info["CNPJ"] = get_part(parts, 7)           # Posição 7 = CNPJ
            info["UF"] = get_part(parts, 9)             # Posição 9 = UF
            info["IE"] = get_part(parts, 10)            # Posição 10 = IE
            break
            
    return info


def formatar_data_brasil(data_str):
    """Converte data do formato AAAAMMDD para DD/MM/AAAA"""
    try:
        if not data_str:
            return ""
        data_str = str(data_str).strip()
        if len(data_str) == 8 and data_str.isdigit():
            # Formato AAAAMMDD
            return f"{data_str[6:8]}/{data_str[4:6]}/{data_str[0:4]}"
        elif len(data_str) == 8:
            # Formato DDMMAAAA
            return f"{data_str[0:2]}/{data_str[2:4]}/{data_str[4:8]}"
        else:
            return data_str
    except:
        return data_str


def parse_sped(lines):
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
            
            linha_completa = nota_atual.copy()
            linha_completa.update({
                "CST_ICMS": cst_icms_original,
                "CFOP": get_part(parts, 3),
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


def processar_arquivo(uploaded_file):
    """Processa um único arquivo SPED e retorna as informações"""
    content = uploaded_file.read().decode("latin-1")
    lines = content.splitlines()
    
    info_empresa = parse_bloco_0000(lines)
    df_completo = parse_sped(lines)
    
    return info_empresa, df_completo, uploaded_file.name


# =========================
# INTERFACE PARA MÚLTIPLOS ARQUIVOS
# =========================
uploaded_files = st.file_uploader(
    "Envie os arquivos SPED (.txt)", 
    type=["txt"], 
    accept_multiple_files=True
)

if uploaded_files:
    todos_os_dados = []
    
    with st.spinner(f"Processando {len(uploaded_files)} arquivo(s)..."):
        for arquivo in uploaded_files:
            info_empresa, df_completo, nome_arquivo = processar_arquivo(arquivo)
            
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
        
        # Ordenar colunas para exibição (informações da empresa primeiro)
        colunas_ordenadas = [
            "EMPRESA", "CNPJ", "UF", "IE", "PERIODO_INICIAL", "PERIODO_FINAL",
            "NUM_DOC", "SER", "DT_DOC", "CHAVE_NFE", "VL_DOC",
            "CST_ICMS", "ORIGEM_PRODUTO", "CLASS_FIS", "CFOP", "ALIQ_ICMS", 
            "VL_OPR", "VL_BC_ICMS", "VL_ICMS", "VL_BC_ICMS_ST", "VL_ICMS_ST", 
            "VL_RED_BC", "VL_IPI", "COD_OBS", "ARQUIVO_ORIGEM"
        ]
        
        # Garantir que todas as colunas existam
        colunas_existentes = [col for col in colunas_ordenadas if col in df_final.columns]
        df_exibicao = df_final[colunas_existentes]
        
        st.dataframe(df_exibicao, use_container_width=True, height=500)
        
        # Mostrar resumo de quantos arquivos foram processados
        st.success(f"✅ {len(uploaded_files)} arquivo(s) processado(s) com sucesso! Total de {len(df_final)} registros de notas fiscais.")
        
    else:
        st.warning("⚠️ Nenhum registro C100/C190 encontrado nos arquivos!")
else:
    st.info("👆 Selecione um ou mais arquivos SPED para começar")