import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path
import os
from typing import List, Dict, Any
import glob

st.set_page_config(
    layout="wide",
    page_title="Leitor XML NF-e",
    page_icon="📄"
)

# =========================
# FUNÇÕES AUXILIARES
# =========================

def get_text(parent, tag: str) -> str:
    """Extrai texto de um elemento XML com segurança"""
    if parent is None:
        return ""
    el = parent.find(f".//{tag}")
    return el.text if el is not None else ""


def remove_namespace(element):
    """Remove namespace de todos os elementos do XML"""
    for elem in element.iter():
        if "}" in elem.tag:
            elem.tag = elem.tag.split("}", 1)[1]


def parse_icms(icms_parent):
    """
    Parse genérico de ICMS - detecta automaticamente o tipo e extrai campos
    Retorna dicionário com todos os campos encontrados
    """
    icms_data = {}
    
    if icms_parent is None:
        return icms_data
    
    # Encontra a tag ICMS
    icms_tag = icms_parent.find(".//ICMS")
    if icms_tag is None:
        return icms_data
    
    # Lista de possíveis tipos de ICMS
    icms_types = ['ICMS00', 'ICMS10', 'ICMS20', 'ICMS30', 'ICMS40', 
                  'ICMS41', 'ICMS50', 'ICMS51', 'ICMS60', 'ICMS70', 'ICMS90']
    
    # Detecta qual tipo está presente
    icms_type = None
    icms_element = None
    
    for icms_type_name in icms_types:
        found = icms_tag.find(icms_type_name)
        if found is not None:
            icms_type = icms_type_name
            icms_element = found
            break
    
    if icms_element is None:
        return icms_data
    
    # Registra o tipo encontrado
    icms_data['ICMS_tipo'] = icms_type
    
    # Mapeamento de campos comuns a todos os tipos
    common_fields = {
        'orig': 'ICMS_orig',
        'CST': 'ICMS_CST',
        'CSOSN': 'ICMS_CSOSN',
        'modBC': 'ICMS_modBC',
        'vBC': 'ICMS_vBC',
        'pICMS': 'ICMS_pICMS',
        'vICMS': 'ICMS_vICMS',
        'pRedBC': 'ICMS_pRedBC',
        'vBCST': 'ICMS_vBCST',
        'pST': 'ICMS_pST',
        'vICMSST': 'ICMS_vICMSST',
        'pFCP': 'ICMS_pFCP',
        'vFCP': 'ICMS_vFCP',
        'pFCPST': 'ICMS_pFCPST',
        'vFCPST': 'ICMS_vFCPST',
        'vFCPSTRet': 'ICMS_vFCPSTRet',
        'pST': 'ICMS_pST',
        'vICMSDeson': 'ICMS_vICMSDeson',
        'motDesICMS': 'ICMS_motDesICMS',
        'vICMSOp': 'ICMS_vICMSOp',
        'pDif': 'ICMS_pDif',
        'vICMSDif': 'ICMS_vICMSDif',
        'vBCFCP': 'ICMS_vBCFCP',
        'vBCST': 'ICMS_vBCST',
        'vBCSTRet': 'ICMS_vBCSTRet',
        'vICMSSTRet': 'ICMS_vICMSSTRet',
        'vICMSSubstituto': 'ICMS_vICMSSubstituto',
        'vICMSST': 'ICMS_vICMSST',
        'pCredSN': 'ICMS_pCredSN',
        'vCredICMSSN': 'ICMS_vCredICMSSN'
    }
    
    # Extrai campos comuns
    for xml_field, df_field in common_fields.items():
        value = get_text(icms_element, xml_field)
        if value:  # Só adiciona se tiver valor
            icms_data[df_field] = value
    
    # Campos específicos para ICMS60 (ST retido)
    if icms_type == 'ICMS60':
        st_ret_fields = {
            'vBCSTRet': 'ICMS_vBCSTRet',
            'vICMSSTRet': 'ICMS_vICMSSTRet',
            'vICMSSubstituto': 'ICMS_vICMSSubstituto',
            'pST': 'ICMS_pST'
        }
        for xml_field, df_field in st_ret_fields.items():
            value = get_text(icms_element, xml_field)
            if value:
                icms_data[df_field] = value
    
    # Campos específicos para ICMS10, ICMS70, ICMS90 (ST)
    if icms_type in ['ICMS10', 'ICMS70', 'ICMS90']:
        st_fields = {
            'vBCST': 'ICMS_vBCST',
            'vICMSST': 'ICMS_vICMSST',
            'pST': 'ICMS_pST',
            'vBCSTRet': 'ICMS_vBCSTRet',
            'vICMSSTRet': 'ICMS_vICMSSTRet'
        }
        for xml_field, df_field in st_fields.items():
            value = get_text(icms_element, xml_field)
            if value:
                icms_data[df_field] = value
    
    # Campos específicos para ICMS51
    if icms_type == 'ICMS51':
        specific_fields = {
            'pRedBC': 'ICMS_pRedBC',
            'vBC': 'ICMS_vBC',
            'pICMS': 'ICMS_pICMS',
            'vICMS': 'ICMS_vICMS',
            'vBCSTRet': 'ICMS_vBCSTRet',
            'vICMSSTRet': 'ICMS_vICMSSTRet'
        }
        for xml_field, df_field in specific_fields.items():
            value = get_text(icms_element, xml_field)
            if value:
                icms_data[df_field] = value
    
    # Campos para ICMS00 (normal)
    if icms_type == 'ICMS00':
        normal_fields = {
            'modBC': 'ICMS_modBC',
            'vBC': 'ICMS_vBC',
            'pICMS': 'ICMS_pICMS',
            'vICMS': 'ICMS_vICMS'
        }
        for xml_field, df_field in normal_fields.items():
            value = get_text(icms_element, xml_field)
            if value:
                icms_data[df_field] = value
    
    # Campos para ICMS20 (com redução de base)
    if icms_type == 'ICMS20':
        reducao_fields = {
            'pRedBC': 'ICMS_pRedBC',
            'vBC': 'ICMS_vBC',
            'pICMS': 'ICMS_pICMS',
            'vICMS': 'ICMS_vICMS'
        }
        for xml_field, df_field in reducao_fields.items():
            value = get_text(icms_element, xml_field)
            if value:
                icms_data[df_field] = value
    
    return icms_data


def parse_xml_content(xml_content: str) -> List[Dict[str, Any]]:
    """
    Parse conteúdo XML e extrai dados da NF-e
    Suporta ambos formatos: com/sem nfeProc
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        st.error(f"Erro ao parsear XML: {e}")
        return []

    # Remove namespace
    remove_namespace(root)

    # Localiza infNFe (pode estar em diferentes níveis)
    infNFe = root.find(".//infNFe")
    if infNFe is None:
        return []

    # Dados do emitente
    emit = infNFe.find("emit")
    dest = infNFe.find("dest")
    ide = infNFe.find("ide")

    # Lista de itens
    dets = infNFe.findall("det")

    linhas = []

    for det in dets:
        prod = det.find("prod")
        
        # Busca impostos IBSCBS (pode estar em diferentes locais)
        ibscbs = det.find(".//IBSCBS")
        
        # Busca por tags alternativas se IBSCBS não for encontrado
        if ibscbs is None:
            ibscbs = det.find(".//imposto/IBSCBS")
        
        # Parse ICMS
        imposto = det.find("imposto")
        icms_data = parse_icms(imposto) if imposto is not None else {}
        
        linha = {
            # Dados do emitente
            "Emitente_xFant": get_text(emit, "xFant"),
            "Emitente_CNPJ": get_text(emit, "CNPJ"),
            "Emitente_UF": get_text(emit, "UF"),
            "Emitente_IE": get_text(emit, "IE"),
            
            # Dados do destinatário
            "Destinatario_Nome": get_text(dest, "xNome"),
            "Destinatario_CNPJ": get_text(dest, "CNPJ"),
            "Destinatario_CPF": get_text(dest, "CPF"),
            "Destinatario_UF": get_text(dest, "UF"),
            "Destinatario_indIEDest": get_text(dest, "indIEDest"),
            
            # Dados da nota
            "Modelo": get_text(ide, "mod"),
            "Numero_NF": get_text(ide, "nNF"),
            "Serie": get_text(ide, "serie"),
            "Data_Emissao": get_text(ide, "dhEmi"),
            "Data_Saida": get_text(ide, "dhSaiEnt"),
            "Natureza_Operacao": get_text(ide, "natOp"),
            
            # Dados do item
            "Item_Numero": det.attrib.get("nItem", ""),
            "Item_Codigo_EAN": get_text(prod, "cEAN"),
            "Item_Codigo": get_text(prod, "cProd"),
            "Item_Descricao": get_text(prod, "xProd"),
            "Item_NCM": get_text(prod, "NCM"),
            "Item_CFOP": get_text(prod, "CFOP"),
            "Item_CEST": get_text(prod, "CEST"),
            "Item_Beneficio": get_text(prod, "cBenef"),
            
            # Quantidades e valores
            "Item_Quantidade": get_text(prod, "qCom"),
            "Item_Valor_Unitario": get_text(prod, "vUnCom"),
            "Item_Valor_Total": get_text(prod, "vProd"),
            
            # Unidades
            "Item_Unidade_Comercial": get_text(prod, "uCom"),
            "Item_Unidade_Tributacao": get_text(prod, "uTrib"),
            "Item_Quantidade_Tributacao": get_text(prod, "qTrib"),
            "Item_Valor_Unitario_Tributacao": get_text(prod, "vUnTrib"),
            
            # Impostos IBS/CBS
            "IBS_CST": get_text(ibscbs, "CST"),
            "IBS_Classificacao_Trib": get_text(ibscbs, "cClassTrib"),
            "IBS_Base_Calculo": get_text(ibscbs, "vBC"),
            "IBS_Valor_IBS": get_text(ibscbs, "vIBS"),
            "IBS_Percentual_CBS": get_text(ibscbs, "pCBS"),
            "IBS_Valor_CBS": get_text(ibscbs, "vCBS"),
            "IBS_Dev_Trib_CBS": get_text(ibscbs, "vDevTrib"),
            "IBS_Percentual_IBSUF": get_text(ibscbs, "pIBSUF"),
            "IBS_Valor_IBSUF": get_text(ibscbs, "vIBSUF"),
            "IBS_Dev_Trib_IBSUF": get_text(ibscbs, "vDevTrib_IBSUF"),
            "IBS_Percentual_IBSMun": get_text(ibscbs, "pIBSMun"),
            "IBS_Valor_IBSMun": get_text(ibscbs, "vIBSMun"),
            
            # Dados ICMS (adicionados dinamicamente)
            **icms_data  # Desempacota todos os campos ICMS extraídos
        }
        
        linhas.append(linha)
    
    return linhas


def processar_arquivos_xml(arquivos: List) -> List[Dict[str, Any]]:
    """Processa múltiplos arquivos XML"""
    todos_dados = []
    
    for arquivo in arquivos:
        try:
            # Se for objeto de upload
            if hasattr(arquivo, 'read'):
                content = arquivo.read()
                # Tenta decode com diferentes encodings
                try:
                    xml_str = content.decode('utf-8')
                except UnicodeDecodeError:
                    xml_str = content.decode('latin-1')
                
                dados = parse_xml_content(xml_str)
                todos_dados.extend(dados)
                
        except Exception as e:
            st.warning(f"Erro ao processar arquivo {getattr(arquivo, 'name', 'desconhecido')}: {e}")
            continue
    
    return todos_dados


def processar_pasta_xml(pasta_path: str) -> List[Dict[str, Any]]:
    """Processa todos XMLs de uma pasta"""
    todos_dados = []
    
    # Busca todos arquivos .xml na pasta
    xml_files = glob.glob(os.path.join(pasta_path, "*.xml"))
    xml_files.extend(glob.glob(os.path.join(pasta_path, "*.XML")))
    
    for xml_file in xml_files:
        try:
            with open(xml_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            dados = parse_xml_content(content)
            todos_dados.extend(dados)
            
        except UnicodeDecodeError:
            # Tenta com latin-1
            with open(xml_file, 'r', encoding='latin-1') as f:
                content = f.read()
            dados = parse_xml_content(content)
            todos_dados.extend(dados)
        except Exception as e:
            st.warning(f"Erro no arquivo {os.path.basename(xml_file)}: {e}")
            continue
    
    return todos_dados


# =========================
# CSS PERSONALIZADO
# =========================
st.markdown("""
<style>
    /* Estilo da barra lateral direita */
    section[data-testid="stSidebar"] {
        position: fixed;
        right: 0;
        left: auto;
        width: 280px !important;
        background-color: #f8f9fa;
        border-left: 1px solid #e0e0e0;
        padding: 20px 15px;
        box-shadow: -2px 0 5px rgba(0,0,0,0.05);
    }
    
    /* Ajuste do conteúdo principal */
    section[data-testid="stSidebar"] + div {
        margin-right: 280px !important;
    }
    
    /* Cards de métricas */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 12px;
        color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* Tabela com scroll */
    .stDataFrame {
        max-height: 600px;
        overflow-y: auto;
    }
    
    /* Título principal */
    .main-title {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 12px;
        color: white;
        margin-bottom: 30px;
    }
    
    /* Botões estilizados */
    .stButton > button {
        width: 100%;
        border-radius: 8px;
        transition: all 0.3s;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
</style>
""", unsafe_allow_html=True)


# =========================
# INTERFACE PRINCIPAL
# =========================

# Título
st.markdown("""
<div class="main-title">
    <h1 style="margin:0; color:white;">📄 Leitor XML NF-e</h1>
    <p style="margin:5px 0 0 0; opacity:0.9;">Extração inteligente de dados de Notas Fiscais Eletrônicas</p>
</div>
""", unsafe_allow_html=True)


# =========================
# BARRA LATERAL DIREITA
# =========================
with st.sidebar:
    st.markdown("### 📥 Entrada de Dados")
    st.markdown("---")
    
    # Opção 1: Upload de múltiplos arquivos
    st.markdown("**Upload de XMLs**")
    uploaded_files = st.file_uploader(
        "Selecione um ou mais arquivos XML",
        type=["xml"],
        accept_multiple_files=True,
        key="uploader",
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    # Opção 2: Colar XML
    st.markdown("**Colar XML**")
    xml_text = st.text_area(
        "Cole o conteúdo do XML aqui",
        height=150,
        placeholder="<nfeProc>...</nfeProc>",
        label_visibility="collapsed"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📋 Processar", use_container_width=True):
            if xml_text:
                dados = parse_xml_content(xml_text)
                st.session_state['dados'] = dados
                st.success(f"✅ {len(dados)} itens processados")
            else:
                st.warning("Cole um XML primeiro")
    
    with col2:
        if st.button("🗑️ Limpar", use_container_width=True):
            if 'dados' in st.session_state:
                st.session_state['dados'] = []
            st.rerun()
    
    st.markdown("---")
    
    # Opção 3: Selecionar pasta
    st.markdown("**Pasta Local**")
    pasta_path = st.text_input(
        "Caminho da pasta com XMLs",
        placeholder="C:/caminho/para/pasta",
        label_visibility="collapsed"
    )
    
    if st.button("📁 Carregar Pasta", use_container_width=True):
        if pasta_path and os.path.exists(pasta_path):
            with st.spinner("Processando XMLs da pasta..."):
                dados = processar_pasta_xml(pasta_path)
                st.session_state['dados'] = dados
                st.success(f"✅ {len(dados)} itens processados")
        else:
            st.error("Pasta não encontrada")
    
    st.markdown("---")
    
    # Botão de exportação
    st.markdown("### 💾 Exportar")
    
    if st.button("📊 Baixar Excel", use_container_width=True, type="primary"):
        if 'dados' in st.session_state and st.session_state['dados']:
            df = pd.DataFrame(st.session_state['dados'])
            output = BytesIO()
            
            # Configuração do Excel com formatação
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='NF-e_Itens')
                
                # Ajusta largura das colunas
                worksheet = writer.sheets['NF-e_Itens']
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            st.download_button(
                label="💾 Fazer Download",
                data=output.getvalue(),
                file_name="nfe_exportado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.warning("Nenhum dado para exportar")
    
    # Informações
    st.markdown("---")
    st.markdown("""
    <div style="font-size:12px; color:#666; text-align:center;">
        <p>✅ Suporta múltiplos XMLs<br>
        ✅ Extrai emitente, destinatário e itens<br>
        ✅ Campos de impostos IBS/CBS<br>
        ✅ <strong>Suporte completo ICMS</strong><br>
        ✅ Robusto contra XMLs incompletos</p>
    </div>
    """, unsafe_allow_html=True)


# =========================
# ÁREA PRINCIPAL
# =========================

# Processar uploads se houver
if uploaded_files:
    with st.spinner("Processando arquivos..."):
        dados = processar_arquivos_xml(uploaded_files)
        st.session_state['dados'] = dados

# Exibir dados
if 'dados' in st.session_state and st.session_state['dados']:
    df = pd.DataFrame(st.session_state['dados'])
    
    # Converter colunas numéricas para cálculos
    numeric_cols = ['Item_Quantidade', 'Item_Valor_Total', 'IBS_Valor_IBS', 'IBS_Valor_CBS',
                    'ICMS_vBC', 'ICMS_vICMS', 'ICMS_vBCSTRet', 'ICMS_vICMSSTRet']
    
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Métricas
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📄 Notas Fiscais", df['Numero_NF'].nunique() if 'Numero_NF' in df else 0)
    
    with col2:
        st.metric("📦 Total de Itens", len(df))
    
    with col3:
        valor_total = df['Item_Valor_Total'].sum() if 'Item_Valor_Total' in df else 0
        st.metric("💰 Valor Total", f"R$ {valor_total:,.2f}")
    
    with col4:
        valor_icms = df['ICMS_vICMS'].sum() if 'ICMS_vICMS' in df else 0
        st.metric("💸 ICMS Total", f"R$ {valor_icms:,.2f}")
    
    st.markdown("---")
    
    # Tabela de dados
    st.subheader("📊 Detalhamento dos Itens")
    
    # Configuração da tabela com scroll
    st.dataframe(
        df,
        use_container_width=True,
        height=500,
        column_config={
            "Item_Descricao": st.column_config.TextColumn("Descrição", width="medium"),
            "Item_Valor_Total": st.column_config.NumberColumn("Valor Total", format="R$ %.2f"),
            "Item_Quantidade": st.column_config.NumberColumn("Quantidade", format="%.3f"),
            "ICMS_vICMS": st.column_config.NumberColumn("ICMS", format="R$ %.2f"),
            "ICMS_tipo": st.column_config.TextColumn("Tipo ICMS", width="small"),
        }
    )
    
    # Botão para limpar dados
    if st.button("🗑️ Limpar todos os dados", type="secondary"):
        st.session_state['dados'] = []
        st.rerun()

else:
    # Mensagem inicial
    st.info("""
    ### 👋 Bem-vindo ao Leitor XML NF-e
    
    **Como usar:**
    
    1. **Upload de XMLs** - Selecione um ou mais arquivos no menu lateral direito
    2. **Colar XML** - Cole o conteúdo diretamente na caixa de texto
    3. **Pasta Local** - Informe o caminho de uma pasta com vários XMLs
    
    Após carregar, os dados aparecerão automaticamente nesta área principal.
    
    **Dados extraídos:**
    - ✅ Emitente (nome fantasia, CNPJ, UF, IE)
    - ✅ Destinatário (nome, CNPJ/CPF, UF)
    - ✅ Nota fiscal (número, série, data, natureza)
    - ✅ Itens (código, descrição, NCM, CFOP, quantidade, valores)
    - ✅ Impostos IBS/CBS (alíquotas, bases, valores)
    - ✅ **ICMS (todos os tipos: ICMS00, ICMS10, ICMS20, ICMS30, ICMS40, ICMS41, ICMS50, ICMS51, ICMS60, ICMS70, ICMS90)**
    
    **Exportação:** Use o botão "Baixar Excel" no menu lateral.
    """)