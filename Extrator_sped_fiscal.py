import streamlit as st
import pandas as pd

st.set_page_config(page_title="SPED Fiscal", layout="wide")

st.title("📊 Leitor SPED Fiscal (C100 + C190)")

uploaded_file = st.file_uploader("Envie o arquivo SPED (.txt)", type=["txt"])


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
            # Mapeamento conforme tabela de origem do SPED
            origem_map = {
                "0": "Nacional",
                "1": "Estrangeira - Importação direta",
                "2": "Estrangeira - Adquirida no mercado interno",
                "3": "Nacional - Conteúdo de importação > 40%",
                "4": "Nacional - Produção conforme processo produtivo básico",
                "5": "Nacional - Conteúdo de importação < 40%",
                "6": "Estrangeira - Importação direta sem similar nacional",
                "7": "Estrangeira - Adquirida no mercado interno sem similar nacional",
                "8": "Nacional - Conteúdo de importação > 70%"
            }
            return origem_map.get(primeiro_digito, f"Origem {primeiro_digito}")
        return "Não informado"
    except:
        return "Erro"


def get_class_fis(cst_icms):
    """Extrai os dois últimos dígitos do CST_ICMS (posições 2 e 3) para CLASS_FIS"""
    try:
        if cst_icms and len(str(cst_icms)) >= 2:
            # Se CST_ICMS tem 3 dígitos (ex: 00, 10, 20, 90, etc)
            if len(str(cst_icms)) >= 2:
                return str(cst_icms)[:2]  # Pega os dois primeiros dígitos (posição 1 e 2)
        return ""
    except:
        return ""


def parse_bloco_0000(lines):
    """Extrai informações do bloco 0000 (ABERTURA DO ARQUIVO DIGITAL)"""
    info = {
        "DATA_INICIAL": "",
        "DATA_FINAL": "",
        "NOME_EMPRESA": "",
        "CNPJ": "",
        "UF": "",
        "IE": ""  # Inscrição Estadual
    }
    
    for line in lines:
        parts = line.strip().split("|")
        if len(parts) < 2:
            continue
        
        reg = parts[1]
        
        if reg == "0000":
            # Posições do registro 0000:
            # |0000|...|DATA_INICIAL|DATA_FINAL|NOME_EMPRESA|...|CNPJ|...|UF|...|IE|
            info["DATA_INICIAL"] = get_part(parts, 4)   # Posição 4 - Data inicial
            info["DATA_FINAL"] = get_part(parts, 5)     # Posição 5 - Data final
            info["NOME_EMPRESA"] = get_part(parts, 6)   # Posição 6 - Nome empresarial
            info["CNPJ"] = get_part(parts, 9)           # Posição 9 - CNPJ
            info["UF"] = get_part(parts, 12)            # Posição 12 - UF
            info["IE"] = get_part(parts, 13)            # Posição 13 - Inscrição Estadual
            break
            
    return info


def formatar_data_brasil(data_str):
    """Converte data do formato AAAAMMDD ou DDMMAAAA para DD/MM/AAAA"""
    try:
        if not data_str:
            return ""
        
        # Se a data já tem 8 dígitos no formato DDMMAAAA
        if len(data_str) == 8 and data_str.isdigit():
            return f"{data_str[0:2]}/{data_str[2:4]}/{data_str[4:8]}"
        
        # Se a data está no formato AAAAMMDD
        elif len(data_str) == 8:
            return f"{data_str[6:8]}/{data_str[4:6]}/{data_str[0:4]}"
        else:
            return data_str
    except:
        return data_str


# =========================
# PARSER SPED (C100 + C190 NA MESMA LINHA)
# =========================
def parse_sped(lines):
    dados_completos = []
    nota_atual = None

    for line in lines:
        parts = line.strip().split("|")

        if len(parts) < 2:
            continue

        reg = parts[1]

        # =========================
        # C100 - NOTA
        # =========================
        if reg == "C100":
            nota_atual = {
                "NUM_DOC": get_part(parts, 8),
                "SER": get_part(parts, 7),
                "DT_DOC": get_part(parts, 10),
                "VL_DOC": to_float(get_part(parts, 12)),
                "CHAVE_NFE": get_part(parts, 9),
                # Inicializa campos do C190
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

        # =========================
        # C190 - ICMS (vincula à nota atual)
        # =========================
        elif reg == "C190" and nota_atual is not None:
            # Extrai o CST_ICMS original
            cst_icms_original = get_part(parts, 2)
            
            # Cria uma linha combinando C100 + C190
            linha_completa = nota_atual.copy()
            linha_completa.update({
                "CST_ICMS": cst_icms_original,                    # CST/ICMS original preservado
                "CFOP": get_part(parts, 3),                       # CFOP
                "ALIQ_ICMS": to_float(get_part(parts, 9)),        # Alíquota do ICMS (%)
                "VL_OPR": to_float(get_part(parts, 4)),           # Valor da operação
                "VL_BC_ICMS": to_float(get_part(parts, 6)),       # Base de cálculo do ICMS
                "VL_ICMS": to_float(get_part(parts, 7)),          # Valor do ICMS
                "VL_BC_ICMS_ST": to_float(get_part(parts, 10)),   # Base ICMS ST
                "VL_ICMS_ST": to_float(get_part(parts, 11)),      # Valor ICMS ST
                "VL_RED_BC": to_float(get_part(parts, 12)),       # Valor não tributado base do ICMS
                "VL_IPI": to_float(get_part(parts, 13)),          # Valor do IPI
                "COD_OBS": get_part(parts, 14),                   # Código observação lançamento
                # NOVOS CAMPOS
                "ORIGEM_PRODUTO": get_origem_produto(cst_icms_original),  # Origem do produto (1º dígito)
                "CLASS_FIS": get_class_fis(cst_icms_original),            # Classificação Fiscal (posições 2 e 3)
            })
            dados_completos.append(linha_completa)
            nota_atual = None  # Reseta após vincular

    df = pd.DataFrame(dados_completos)

    # =========================
    # TRATAR DATAS
    # =========================
    if not df.empty:
        # Converte para datetime e depois formata como data brasileira
        df["DT_DOC"] = pd.to_datetime(
            df["DT_DOC"], format="%d%m%Y", errors="coerce"
        )
        # Formata como data brasileira (dd/mm/aaaa)
        df["DT_DOC"] = df["DT_DOC"].dt.strftime("%d/%m/%Y")

    return df


# =========================
# EXECUÇÃO
# =========================
if uploaded_file:

    content = uploaded_file.read().decode("latin-1")
    lines = content.splitlines()
    
    # Extrai informações do bloco 0000
    info_empresa = parse_bloco_0000(lines)
    
    # Parse dos dados C100/C190
    df_completo = parse_sped(lines)

    if df_completo.empty:
        st.warning("⚠️ Nenhum registro C100/C190 encontrado no arquivo!")
    else:
        # =========================
        # INFORMAÇÕES DO BLOCO 0000 (NO INÍCIO)
        # =========================
        st.subheader("🏢 INFORMAÇÕES DA EMPRESA (BLOCO 0000)")
        
        # Formatar datas do bloco 0000
        data_inicial_formatada = formatar_data_brasil(info_empresa["DATA_INICIAL"])
        data_final_formatada = formatar_data_brasil(info_empresa["DATA_FINAL"])
        
        # Criar 3 colunas para exibir as informações
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**📅 Período de Apuração**")
            st.write(f"📆 Data Inicial: **{data_inicial_formatada}**")
            st.write(f"📆 Data Final: **{data_final_formatada}**")
        
        with col2:
            st.markdown("**🏢 Dados da Empresa**")
            st.write(f"📛 Nome: **{info_empresa['NOME_EMPRESA']}**")
            st.write(f"🔢 CNPJ: **{info_empresa['CNPJ']}**")
        
        with col3:
            st.markdown("**📍 Localização**")
            st.write(f"🗺️ UF: **{info_empresa['UF']}**")
            st.write(f"📄 Inscrição Estadual: **{info_empresa['IE']}**")
        
        st.divider()
        
        # =========================
        # MOSTRAR DADOS COMPLETOS
        # =========================
        st.subheader("📄 Notas Fiscais + ICMS (C100 e C190 na mesma linha)")
        
        # Selecionar e ordernar as colunas para exibição
        colunas_ordenadas = [
            "NUM_DOC", "SER", "DT_DOC", "CHAVE_NFE", "VL_DOC",
            "CST_ICMS", "ORIGEM_PRODUTO", "CLASS_FIS", "CFOP", "ALIQ_ICMS", 
            "VL_OPR", "VL_BC_ICMS", "VL_ICMS", "VL_BC_ICMS_ST", "VL_ICMS_ST", 
            "VL_RED_BC", "VL_IPI", "COD_OBS"
        ]
        
        df_exibicao = df_completo[colunas_ordenadas]
        st.dataframe(df_exibicao, use_container_width=True)

        # =========================
        # MÉTRICAS DETALHADAS
        # =========================
        st.subheader("📊 Métricas Gerais")
        
        # Converter colunas numéricas para float antes de somar
        colunas_numericas = ["VL_ICMS", "VL_ICMS_ST", "VL_IPI", "VL_RED_BC", "VL_OPR", "VL_BC_ICMS", "VL_DOC"]
        for col in colunas_numericas:
            if col in df_completo.columns:
                df_completo[col] = pd.to_numeric(df_completo[col], errors="coerce").fillna(0)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total ICMS", f"R$ {df_completo['VL_ICMS'].sum():,.2f}")
        with col2:
            st.metric("Total ICMS ST", f"R$ {df_completo['VL_ICMS_ST'].sum():,.2f}")
        with col3:
            st.metric("Total IPI", f"R$ {df_completo['VL_IPI'].sum():,.2f}")
        with col4:
            st.metric("Total não tributado", f"R$ {df_completo['VL_RED_BC'].sum():,.2f}")

        # =========================
        # VALIDAÇÃO
        # =========================
        st.subheader("🧠 Validação (C100 vs C190)")
        
        # Agrupa por documento para comparar valores
        validacao = df_completo.groupby(["NUM_DOC", "SER"]).agg({
            "VL_DOC": "first",
            "VL_OPR": "sum"
        }).reset_index()
        
        validacao["VL_DOC"] = pd.to_numeric(validacao["VL_DOC"], errors="coerce").fillna(0)
        validacao["VL_OPR"] = pd.to_numeric(validacao["VL_OPR"], errors="coerce").fillna(0)
        validacao["DIFERENCA"] = validacao["VL_DOC"] - validacao["VL_OPR"]
        validacao["STATUS"] = validacao["DIFERENCA"].apply(
            lambda x: "✅ OK" if abs(x) <= 1 else "⚠️ Divergência"
        )
        
        st.dataframe(validacao, use_container_width=True)
        
        total_notas = df_completo["VL_DOC"].sum()
        total_icms_opr = df_completo["VL_OPR"].sum()

        col1, col2 = st.columns(2)
        col1.metric("Total Notas (C100)", f"R$ {total_notas:,.2f}")
        col2.metric("Total C190 (VL_OPR)", f"R$ {total_icms_opr:,.2f}")

        if abs(total_notas - total_icms_opr) > 1:
            st.error("⚠️ Diferença entre C100 e C190!")
        else:
            st.success("✅ Valores batem!")

        # =========================
        # DOWNLOAD - INCLUINDO INFORMAÇÕES DO BLOCO 0000
        # =========================
        st.subheader("📥 Downloads")
        
        # Criar DataFrame com informações da empresa para download
        df_info_empresa = pd.DataFrame([{
            "DATA_INICIAL": formatar_data_brasil(info_empresa["DATA_INICIAL"]),
            "DATA_FINAL": formatar_data_brasil(info_empresa["DATA_FINAL"]),
            "NOME_EMPRESA": info_empresa["NOME_EMPRESA"],
            "CNPJ": info_empresa["CNPJ"],
            "UF": info_empresa["UF"],
            "IE": info_empresa["IE"]
        }])
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.download_button(
                "📥 Baixar Dados Completos CSV",
                df_completo[colunas_ordenadas].to_csv(index=False).encode("utf-8"),
                "sped_c100_c190_completo.csv",
                "text/csv"
            )
        
        with col2:
            # Resumo por CFOP e CLASS_FIS
            resumo = df_completo.groupby(["CFOP", "CLASS_FIS", "ORIGEM_PRODUTO"]).agg({
                "VL_OPR": "sum",
                "VL_BC_ICMS": "sum",
                "VL_ICMS": "sum",
                "VL_BC_ICMS_ST": "sum",
                "VL_ICMS_ST": "sum",
                "VL_RED_BC": "sum",
                "VL_IPI": "sum"
            }).reset_index()
            
            st.download_button(
                "📥 Baixar Resumo CSV",
                resumo.to_csv(index=False).encode("utf-8"),
                "resumo_sped.csv",
                "text/csv"
            )
        
        with col3:
            st.download_button(
                "📥 Baixar Informações da Empresa CSV",
                df_info_empresa.to_csv(index=False).encode("utf-8"),
                "info_empresa_sped.csv",
                "text/csv"
            )