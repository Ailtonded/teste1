# app.py
import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import hashlib
from datetime import datetime
import re

# Configuração da página
st.set_page_config(
    page_title="Sistema de Auditoria SPED Fiscal", 
    page_icon="📊", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado para interface profissional
st.markdown("""
<style>
    /* Estilo geral */
    .main {
        background-color: #f5f7f9;
    }
    
    /* Cards de métricas */
    .metric-card {
        background-color: white;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #1f77b4;
        margin-bottom: 10px;
    }
    
    .metric-title {
        font-size: 14px;
        color: #666;
        margin-bottom: 5px;
    }
    
    .metric-value {
        font-size: 28px;
        font-weight: bold;
        color: #1f77b4;
    }
    
    .metric-subtitle {
        font-size: 12px;
        color: #999;
        margin-top: 5px;
    }
    
    /* Tabela estilizada */
    .stDataFrame {
        font-size: 13px !important;
        font-family: 'Consolas', monospace !important;
    }
    
    .dataframe {
        font-size: 13px !important;
    }
    
    /* Cabeçalhos */
    h1, h2, h3 {
        color: #2c3e50;
        font-weight: 600;
    }
    
    /* Sidebar */
    .css-1d391kg {
        background-color: #2c3e50;
    }
    
    /* Botões */
    .stButton button {
        background-color: #1f77b4;
        color: white;
        border-radius: 5px;
        border: none;
        padding: 8px 16px;
        transition: all 0.3s;
    }
    
    .stButton button:hover {
        background-color: #135f8a;
        transform: translateY(-2px);
    }
    
    /* Alertas */
    .stAlert {
        border-radius: 8px;
        border-left: 4px solid;
    }
    
    /* Abas */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 4px;
        padding: 8px 16px;
        background-color: #f0f2f6;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #1f77b4;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# CLASSES PRINCIPAIS
# ============================================================================

class SPEDParser:
    """Parser principal para arquivos SPED Fiscal"""
    
    def __init__(self, dict_cfop=None):
        self.dict_cfop = dict_cfop or {}
        self.registros = {
            '0000': self.parse_registro_0000,
            'C100': self.parse_registro_C100,
            'C170': self.parse_registro_C170,
            '0200': self.parse_registro_0200,
            '0150': self.parse_registro_0150,
        }
        
    def to_float(self, valor):
        """Converte string para float tratando vírgula e ponto"""
        try:
            if valor is None or str(valor).strip() == '':
                return 0.0
            valor = str(valor).replace(',', '.').strip()
            valor = re.sub(r'[^\d.-]', '', valor)
            return float(valor) if valor else 0.0
        except:
            return 0.0
    
    def to_int(self, valor):
        """Converte string para inteiro"""
        try:
            if valor is None or str(valor).strip() == '':
                return 0
            return int(float(str(valor).replace(',', '.')))
        except:
            return 0
    
    def get_origem_produto(self, cst_icms):
        """Extrai origem do produto do CST_ICMS"""
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
        try:
            cst_str = str(cst_icms).strip()
            if cst_str and len(cst_str) > 0:
                return origem_map.get(cst_str[0], f"{cst_str[0]} - Origem desconhecida")
            return "Sem origem"
        except:
            return "Erro"
    
    def get_class_fis(self, cst_icms):
        """Extrai classificação fiscal do CST_ICMS"""
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
        try:
            cst_str = str(cst_icms).strip()
            if len(cst_str) >= 3:
                class_fis_num = cst_str[1:3]
                return class_fis_map.get(class_fis_num, f"{class_fis_num} - Classificação não mapeada")
            elif len(cst_str) == 2:
                return class_fis_map.get(cst_str, f"{cst_str} - Classificação não mapeada")
            return ""
        except:
            return ""
    
    def get_descricao_cfop(self, cfop):
        """Retorna descrição do CFOP"""
        try:
            if not self.dict_cfop:
                return ""
            cfop_str = str(cfop).strip()
            return self.dict_cfop.get(cfop_str, "CFOP não encontrado")
        except:
            return ""
    
    def formatar_data(self, data_str):
        """Formata data do SPED para DD/MM/AAAA"""
        try:
            if not data_str or str(data_str).strip() == '':
                return ""
            data_str = str(data_str).strip()
            if len(data_str) == 8 and data_str.isdigit():
                return f"{data_str[0:2]}/{data_str[2:4]}/{data_str[4:8]}"
            return data_str
        except:
            return data_str
    
    def parse_registro_0000(self, parts):
        """Parse do registro 0000 - Dados da empresa"""
        if len(parts) < 11:
            return {}
        return {
            "DATA_INICIAL": self.formatar_data(self.get_part(parts, 4)),
            "DATA_FINAL": self.formatar_data(self.get_part(parts, 5)),
            "NOME_EMPRESA": self.get_part(parts, 6),
            "CNPJ": self.get_part(parts, 7),
            "UF": self.get_part(parts, 9),
            "IE": self.get_part(parts, 10),
            "MUNICIPIO": self.get_part(parts, 8)
        }
    
    def parse_registro_C100(self, parts):
        """Parse do registro C100 - Cabeçalho da nota fiscal"""
        if len(parts) < 13:
            return {}
        return {
            "NUM_DOC": self.get_part(parts, 8),
            "SER": self.get_part(parts, 7),
            "DT_DOC": self.formatar_data(self.get_part(parts, 10)),
            "VL_DOC": self.to_float(self.get_part(parts, 12)),
            "CHAVE_NFE": self.get_part(parts, 9),
            "IND_OPER": self.get_part(parts, 2),
            "IND_EMIT": self.get_part(parts, 3),
            "COD_PART": self.get_part(parts, 4),
            "COD_MOD": self.get_part(parts, 5),
            "CFOP_C100": self.get_part(parts, 11)
        }
    
    def parse_registro_C170(self, parts):
        """Parse do registro C170 - Itens da nota fiscal"""
        if len(parts) < 18:
            return {}
        return {
            "NUM_ITEM": self.to_int(self.get_part(parts, 2)),
            "COD_ITEM": self.get_part(parts, 3),
            "DESCR_COMPL": self.get_part(parts, 4),
            "QTD": self.to_float(self.get_part(parts, 5)),
            "UNID": self.get_part(parts, 6),
            "VL_ITEM": self.to_float(self.get_part(parts, 7)),
            "VL_DESC": self.to_float(self.get_part(parts, 8)),
            "CST_ICMS": self.get_part(parts, 12),
            "CFOP": self.get_part(parts, 13),
            "ALIQ_ICMS": self.to_float(self.get_part(parts, 15)),
            "VL_BC_ICMS": self.to_float(self.get_part(parts, 16)),
            "VL_ICMS": self.to_float(self.get_part(parts, 17)),
            "VL_IPI": self.to_float(self.get_part(parts, 25)) if len(parts) > 25 else 0.0
        }
    
    def parse_registro_0200(self, parts):
        """Parse do registro 0200 - Tabela de produtos"""
        if len(parts) < 9:
            return {}
        return {
            "COD_ITEM": self.get_part(parts, 2),
            "DESCR_ITEM": self.get_part(parts, 3),
            "COD_BARRAS": self.get_part(parts, 4),
            "UNID_INV": self.get_part(parts, 5),
            "NCM": self.get_part(parts, 7)
        }
    
    def parse_registro_0150(self, parts):
        """Parse do registro 0150 - Tabela de participantes"""
        if len(parts) < 9:
            return {}
        return {
            "COD_PART": self.get_part(parts, 2),
            "NOME_PART": self.get_part(parts, 3),
            "COD_PAIS": self.get_part(parts, 4),
            "CNPJ_CPF": self.get_part(parts, 5),
            "IE": self.get_part(parts, 8)
        }
    
    def get_part(self, parts, index):
        """Retorna parte do registro ou string vazia"""
        return parts[index].strip() if len(parts) > index else ""
    
    def parse_arquivo(self, lines):
        """Parse completo do arquivo SPED"""
        dados_empresa = {}
        notas_fiscais = {}
        itens_notas = []
        produtos = {}
        participantes = {}
        
        nota_atual = None
        
        for line_num, line in enumerate(lines):
            try:
                if not line.strip():
                    continue
                    
                parts = line.strip().split('|')
                if len(parts) < 2:
                    continue
                
                reg = parts[1]
                
                if reg == '0000':
                    dados_empresa = self.parse_registro_0000(parts)
                
                elif reg == '0200':
                    produto = self.parse_registro_0200(parts)
                    if produto:
                        produtos[produto['COD_ITEM']] = produto
                
                elif reg == '0150':
                    participante = self.parse_registro_0150(parts)
                    if participante:
                        participantes[participante['COD_PART']] = participante
                
                elif reg == 'C100':
                    nota_atual = self.parse_registro_C100(parts)
                    if nota_atual:
                        notas_fiscais[nota_atual.get('NUM_DOC', line_num)] = nota_atual
                
                elif reg == 'C170' and nota_atual:
                    item = self.parse_registro_C170(parts)
                    if item:
                        # Vincula com o cabeçalho da nota
                        item_completo = {**nota_atual, **item}
                        
                        # Adiciona campos auxiliares
                        item_completo['ORIGEM_PRODUTO'] = self.get_origem_produto(item.get('CST_ICMS', ''))
                        item_completo['CLASS_FIS'] = self.get_class_fis(item.get('CST_ICMS', ''))
                        item_completo['DESC_CFOP'] = self.get_descricao_cfop(item.get('CFOP', ''))
                        
                        # Adiciona dados da empresa
                        item_completo['EMPRESA'] = dados_empresa.get('NOME_EMPRESA', '')
                        item_completo['CNPJ'] = dados_empresa.get('CNPJ', '')
                        item_completo['UF_EMITENTE'] = dados_empresa.get('UF', '')
                        item_completo['IE_EMITENTE'] = dados_empresa.get('IE', '')
                        item_completo['PERIODO_INICIAL'] = dados_empresa.get('DATA_INICIAL', '')
                        item_completo['PERIODO_FINAL'] = dados_empresa.get('DATA_FINAL', '')
                        
                        itens_notas.append(item_completo)
            
            except Exception as e:
                st.warning(f"Erro na linha {line_num + 1}: {str(e)}")
                continue
        
        return pd.DataFrame(itens_notas), dados_empresa, produtos, participantes


class SPEDAnalytics:
    """Classe para análises e métricas do SPED"""
    
    @staticmethod
    def calcular_resumo_tributario(df):
        """Calcula resumo tributário"""
        if df.empty:
            return {}
        
        resumo = {
            'total_notas': df['NUM_DOC'].nunique(),
            'total_itens': len(df),
            'valor_total': df['VL_DOC'].sum(),
            'valor_itens': df['VL_ITEM'].sum(),
            'total_icms': df['VL_ICMS'].sum(),
            'total_ipi': df['VL_IPI'].sum(),
            'total_desc': df['VL_DESC'].sum(),
            'media_icms': df['VL_ICMS'].mean(),
            'total_bc_icms': df['VL_BC_ICMS'].sum(),
            'ticket_medio': df['VL_DOC'].mean()
        }
        
        # Resumo por CST
        resumo_cst = df.groupby('CST_ICMS').agg({
            'VL_ITEM': 'sum',
            'VL_ICMS': 'sum',
            'NUM_ITEM': 'count'
        }).to_dict()
        
        resumo['resumo_cst'] = resumo_cst
        
        # Resumo por CFOP
        resumo_cfop = df.groupby('CFOP').agg({
            'VL_ITEM': 'sum',
            'VL_ICMS': 'sum'
        }).to_dict()
        
        resumo['resumo_cfop'] = resumo_cfop
        
        return resumo
    
    @staticmethod
    def gerar_graficos(df):
        """Gera gráficos para dashboard"""
        if df.empty:
            return None
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Valor por Mês', 'Top 10 Produtos', 
                           'Distribuição ICMS', 'Participação CFOP'),
            specs=[[{"type": "scatter"}, {"type": "bar"}],
                   [{"type": "pie"}, {"type": "pie"}]]
        )
        
        # Gráfico 1: Valor por mês
        if 'DT_DOC' in df.columns:
            df_temp = df.copy()
            df_temp['MES'] = pd.to_datetime(df_temp['DT_DOC'], format='%d/%m/%Y', errors='coerce')
            if not df_temp['MES'].isna().all():
                df_mes = df_temp.groupby(df_temp['MES'].dt.to_period('M'))['VL_DOC'].sum().reset_index()
                df_mes['MES'] = df_mes['MES'].astype(str)
                fig.add_trace(
                    go.Scatter(x=df_mes['MES'], y=df_mes['VL_DOC'], mode='lines+markers', name='Valor'),
                    row=1, col=1
                )
        
        # Gráfico 2: Top 10 produtos
        top_produtos = df.groupby('COD_ITEM')['VL_ITEM'].sum().nlargest(10).reset_index()
        fig.add_trace(
            go.Bar(x=top_produtos['COD_ITEM'], y=top_produtos['VL_ITEM'], name='Produtos'),
            row=1, col=2
        )
        
        # Gráfico 3: Distribuição ICMS
        icms_sum = df['VL_ICMS'].sum()
        if icms_sum > 0:
            fig.add_trace(
                go.Pie(labels=['Com ICMS', 'Sem ICMS'], 
                       values=[icms_sum, df['VL_ITEM'].sum() - icms_sum],
                       name='ICMS'),
                row=2, col=1
            )
        
        # Gráfico 4: Participação CFOP
        top_cfop = df.groupby('CFOP')['VL_ITEM'].sum().nlargest(5).reset_index()
        fig.add_trace(
            go.Pie(labels=top_cfop['CFOP'], values=top_cfop['VL_ITEM'], name='CFOP'),
            row=2, col=2
        )
        
        fig.update_layout(height=800, showlegend=True, title_text="Dashboard Fiscal")
        fig.update_xaxes(title_text="Período", row=1, col=1)
        fig.update_yaxes(title_text="Valor (R$)", row=1, col=1)
        fig.update_xaxes(title_text="Produtos", row=1, col=2)
        fig.update_yaxes(title_text="Valor (R$)", row=1, col=2)
        
        return fig


# ============================================================================
# FUNÇÕES DE EXPORTAÇÃO
# ============================================================================

def to_excel_formatado(df):
    """Exporta DataFrame para Excel com formatação profissional"""
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Escreve dados
        df.to_excel(writer, index=False, sheet_name='Itens NF')
        
        # Ajusta largura das colunas
        worksheet = writer.sheets['Itens NF']
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
        
        # Congela cabeçalho
        worksheet.freeze_panes = 'A2'
        
        # Adiciona filtros
        worksheet.auto_filter.ref = worksheet.dimensions
        
        # Formata números
        from openpyxl.styles import numbers
        for row in worksheet.iter_rows(min_row=2, max_row=worksheet.max_row):
            for cell in row:
                if isinstance(cell.value, (int, float)):
                    cell.number_format = numbers.FORMAT_NUMBER_COMMA_SEPARATED1
    
    return output.getvalue()


# ============================================================================
# INTERFACE STREAMLIT
# ============================================================================

def main():
    """Função principal do sistema"""
    
    # Título principal
    st.title("📊 Sistema de Auditoria SPED Fiscal")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/000000/invoice.png", width=80)
        st.markdown("## ⚙️ Configurações")
        
        # Upload tabela CFOP
        st.markdown("### 📚 Tabela de CFOP")
        arquivo_cfop = st.file_uploader(
            "Carregar tabela CFOP (Excel)", 
            type=["xlsx", "xls"],
            help="Arquivo Excel com colunas: CFOP/Código e Descrição"
        )
        
        dict_cfop = {}
        if arquivo_cfop:
            try:
                df_cfop = pd.read_excel(arquivo_cfop)
                col_cfop = None
                col_desc = None
                
                for col in df_cfop.columns:
                    if 'cfop' in col.lower() or 'código' in col.lower():
                        col_cfop = col
                    if 'descri' in col.lower() or 'descrição' in col.lower():
                        col_desc = col
                
                if col_cfop and col_desc:
                    dict_cfop = dict(zip(df_cfop[col_cfop].astype(str), df_cfop[col_desc]))
                    st.success(f"✅ {len(dict_cfop)} registros carregados")
                else:
                    st.error("❌ Colunas não encontradas")
            except Exception as e:
                st.error(f"Erro: {str(e)}")
        
        st.markdown("---")
        
        # Upload arquivos SPED
        st.markdown("### 📁 Arquivos SPED")
        uploaded_files = st.file_uploader(
            "Envie os arquivos SPED (.txt)", 
            type=["txt"], 
            accept_multiple_files=True,
            help="Selecione um ou mais arquivos no formato SPED Fiscal"
        )
        
        st.markdown("---")
        
        # Informações do sistema
        st.markdown("### ℹ️ Informações")
        st.info("""
        **Registros lidos:**
        - C100 (Cabeçalho NF)
        - C170 (Itens NF)
        - 0200 (Produtos)
        - 0150 (Participantes)
        
        **Em desenvolvimento:**
        - C190 (ICMS)
        - E110 (Apuração)
        - H010 (Inventário)
        """)
    
    # Conteúdo principal
    if uploaded_files:
        todos_dados = []
        todas_empresas = {}
        todos_produtos = {}
        todos_participantes = {}
        
        with st.spinner(f"🔄 Processando {len(uploaded_files)} arquivo(s)..."):
            for arquivo in uploaded_files:
                try:
                    # Lê arquivo
                    content = arquivo.read().decode('latin-1')
                    lines = content.splitlines()
                    
                    # Processa com parser
                    parser = SPEDParser(dict_cfop)
                    df_itens, dados_empresa, produtos, participantes = parser.parse_arquivo(lines)
                    
                    if not df_itens.empty:
                        df_itens['ARQUIVO_ORIGEM'] = arquivo.name
                        todos_dados.append(df_itens)
                        
                        if dados_empresa:
                            todas_empresas[dados_empresa.get('CNPJ', '')] = dados_empresa
                        
                        todos_produtos.update(produtos)
                        todos_participantes.update(participantes)
                        
                        st.success(f"✅ {arquivo.name}: {len(df_itens)} itens processados")
                    else:
                        st.warning(f"⚠️ {arquivo.name}: Nenhum item encontrado")
                
                except Exception as e:
                    st.error(f"❌ Erro no arquivo {arquivo.name}: {str(e)}")
        
        if todos_dados:
            df_final = pd.concat(todos_dados, ignore_index=True)
            
            # Métricas no topo
            st.markdown("## 📈 Painel de Métricas")
            
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-title">Total de Itens</div>
                    <div class="metric-value">{:,.0f}</div>
                    <div class="metric-subtitle">Itens processados</div>
                </div>
                """.format(len(df_final)), unsafe_allow_html=True)
            
            with col2:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-title">Valor Total</div>
                    <div class="metric-value">R$ {:,.2f}</div>
                    <div class="metric-subtitle">Soma dos itens</div>
                </div>
                """.format(df_final['VL_ITEM'].sum()), unsafe_allow_html=True)
            
            with col3:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-title">Total ICMS</div>
                    <div class="metric-value">R$ {:,.2f}</div>
                    <div class="metric-subtitle">ICMS destacado</div>
                </div>
                """.format(df_final['VL_ICMS'].sum()), unsafe_allow_html=True)
            
            with col4:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-title">Notas Fiscais</div>
                    <div class="metric-value">{:,.0f}</div>
                    <div class="metric-subtitle">Documentos únicos</div>
                </div>
                """.format(df_final['NUM_DOC'].nunique()), unsafe_allow_html=True)
            
            with col5:
                ticket_medio = df_final['VL_DOC'].mean() if not df_final['VL_DOC'].isna().all() else 0
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-title">Ticket Médio</div>
                    <div class="metric-value">R$ {:,.2f}</div>
                    <div class="metric-subtitle">Por nota fiscal</div>
                </div>
                """.format(ticket_medio), unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Abas para diferentes visualizações
            tab1, tab2, tab3, tab4 = st.tabs(["📋 Dados", "🔍 Filtros", "📊 Dashboard", "📥 Exportação"])
            
            with tab1:
                st.markdown("## 📋 Itens das Notas Fiscais")
                
                # Colunas para exibição
                colunas_exibicao = [
                    'EMPRESA', 'CNPJ', 'NUM_DOC', 'SER', 'DT_DOC', 'NUM_ITEM',
                    'COD_ITEM', 'DESCR_COMPL', 'QTD', 'UNID', 'VL_ITEM', 'VL_DESC',
                    'CST_ICMS', 'ORIGEM_PRODUTO', 'CLASS_FIS', 'CFOP', 'DESC_CFOP',
                    'ALIQ_ICMS', 'VL_BC_ICMS', 'VL_ICMS', 'VL_IPI', 'CHAVE_NFE'
                ]
                
                colunas_existentes = [col for col in colunas_exibicao if col in df_final.columns]
                df_exibicao = df_final[colunas_existentes]
                
                # Dataframe interativo
                st.dataframe(
                    df_exibicao,
                    use_container_width=True,
                    height=500,
                    column_config={
                        "VL_ITEM": st.column_config.NumberColumn("Valor Item", format="R$ %.2f"),
                        "VL_DESC": st.column_config.NumberColumn("Desconto", format="R$ %.2f"),
                        "VL_ICMS": st.column_config.NumberColumn("ICMS", format="R$ %.2f"),
                        "VL_IPI": st.column_config.NumberColumn("IPI", format="R$ %.2f"),
                        "ALIQ_ICMS": st.column_config.NumberColumn("Alíquota ICMS", format="%.2f%%"),
                    }
                )
            
            with tab2:
                st.markdown("## 🔍 Filtros Avançados")
                
                col_filtro1, col_filtro2, col_filtro3 = st.columns(3)
                
                with col_filtro1:
                    # Filtro por empresa
                    empresas = ['Todas'] + sorted(df_final['EMPRESA'].unique().tolist())
                    filtro_empresa = st.selectbox("🏢 Empresa", empresas)
                    
                    # Filtro por CNPJ
                    cnps = ['Todos'] + sorted(df_final['CNPJ'].unique().tolist())
                    filtro_cnpj = st.selectbox("📄 CNPJ", cnps)
                
                with col_filtro2:
                    # Filtro por CFOP
                    cfops = ['Todos'] + sorted(df_final['CFOP'].unique().tolist())
                    filtro_cfop = st.selectbox("📑 CFOP", cfops)
                    
                    # Filtro por CST
                    csts = ['Todos'] + sorted(df_final['CST_ICMS'].unique().tolist())
                    filtro_cst = st.selectbox("🔖 CST ICMS", csts)
                
                with col_filtro3:
                    # Filtro por produto
                    produtos_lista = ['Todos'] + sorted(df_final['COD_ITEM'].unique().tolist())
                    filtro_produto = st.selectbox("📦 Produto", produtos_lista)
                    
                    # Busca por NF
                    busca_nf = st.text_input("🔎 Buscar Nota Fiscal", placeholder="Digite o número da NF")
                
                # Aplicar filtros
                df_filtrado = df_final.copy()
                
                if filtro_empresa != 'Todas':
                    df_filtrado = df_filtrado[df_filtrado['EMPRESA'] == filtro_empresa]
                if filtro_cnpj != 'Todos':
                    df_filtrado = df_filtrado[df_filtrado['CNPJ'] == filtro_cnpj]
                if filtro_cfop != 'Todos':
                    df_filtrado = df_filtrado[df_filtrado['CFOP'] == filtro_cfop]
                if filtro_cst != 'Todos':
                    df_filtrado = df_filtrado[df_filtrado['CST_ICMS'] == filtro_cst]
                if filtro_produto != 'Todos':
                    df_filtrado = df_filtrado[df_filtrado['COD_ITEM'] == filtro_produto]
                if busca_nf:
                    df_filtrado = df_filtrado[df_filtrado['NUM_DOC'].astype(str).str.contains(busca_nf, case=False)]
                
                st.markdown(f"**Resultados:** {len(df_filtrado)} itens encontrados")
                st.dataframe(df_filtrado[colunas_existentes], use_container_width=True, height=400)
            
            with tab3:
                st.markdown("## 📊 Dashboard Analítico")
                
                # Resumo tributário
                analytics = SPEDAnalytics()
                resumo = analytics.calcular_resumo_tributario(df_final)
                
                if resumo:
                    col_r1, col_r2, col_r3 = st.columns(3)
                    
                    with col_r1:
                        st.markdown("### 💰 Valores")
                        st.metric("Valor Total dos Itens", f"R$ {resumo['valor_itens']:,.2f}")
                        st.metric("Total ICMS", f"R$ {resumo['total_icms']:,.2f}")
                        st.metric("Total IPI", f"R$ {resumo['total_ipi']:,.2f}")
                    
                    with col_r2:
                        st.markdown("### 📊 Estatísticas")
                        st.metric("Média ICMS por Item", f"R$ {resumo['media_icms']:,.2f}")
                        st.metric("Total de Descontos", f"R$ {resumo['total_desc']:,.2f}")
                        st.metric("Base de Cálculo ICMS", f"R$ {resumo['total_bc_icms']:,.2f}")
                    
                    with col_r3:
                        st.markdown("### 📈 Indicadores")
                        st.metric("Ticket Médio", f"R$ {resumo['ticket_medio']:,.2f}")
                        st.metric("Itens por NF", f"{resumo['total_itens'] / max(resumo['total_notas'], 1):.1f}")
                        st.metric("Efetividade ICMS", f"{(resumo['total_icms'] / max(resumo['valor_itens'], 1) * 100):.1f}%")
                
                # Gráficos
                st.markdown("### 📈 Visualizações Gráficas")
                fig = analytics.gerar_graficos(df_final)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                
                # Tabela de CFOP
                st.markdown("### 📑 Resumo por CFOP")
                if 'CFOP' in df_final.columns and 'DESC_CFOP' in df_final.columns:
                    resumo_cfop = df_final.groupby(['CFOP', 'DESC_CFOP']).agg({
                        'VL_ITEM': 'sum',
                        'VL_ICMS': 'sum',
                        'NUM_ITEM': 'count'
                    }).reset_index()
                    resumo_cfop.columns = ['CFOP', 'Descrição', 'Valor Total', 'ICMS Total', 'Quantidade']
                    resumo_cfop = resumo_cfop.sort_values('Valor Total', ascending=False)
                    st.dataframe(resumo_cfop, use_container_width=True)
            
            with tab4:
                st.markdown("## 📥 Exportação de Dados")
                
                st.info("💡 Os arquivos exportados incluem formatação profissional, filtros automáticos e cabeçalho congelado.")
                
                col_export1, col_export2 = st.columns(2)
                
                with col_export1:
                    # Exportação CSV
                    csv_data = df_final[colunas_existentes].to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label="📄 Exportar como CSV",
                        data=csv_data,
                        file_name=f"sped_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                
                with col_export2:
                    # Exportação Excel
                    excel_data = to_excel_formatado(df_final[colunas_existentes])
                    st.download_button(
                        label="📊 Exportar como Excel",
                        data=excel_data,
                        file_name=f"sped_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                
                st.markdown("---")
                st.markdown("### 📋 Relatórios Específicos")
                
                if st.button("📈 Gerar Relatório Resumido"):
                    relatorio = df_final.groupby(['EMPRESA', 'CFOP']).agg({
                        'VL_ITEM': 'sum',
                        'VL_ICMS': 'sum',
                        'NUM_DOC': 'nunique'
                    }).reset_index()
                    st.dataframe(relatorio, use_container_width=True)
        else:
            st.warning("⚠️ Nenhum dado foi processado. Verifique os arquivos enviados.")
    
    else:
        # Estado inicial
        st.info("👈 **Como usar:**")
        st.markdown("""
        1. **Carregue a tabela CFOP** (opcional) para descrições completas
        2. **Envie um ou mais arquivos SPED** no formato .txt
        3. **Explore os dados** com filtros e dashboard
        4. **Exporte** os resultados em CSV ou Excel
        
        **Registros suportados atualmente:**
        - ✅ C100 (Cabeçalho da Nota Fiscal)
        - ✅ C170 (Itens da Nota Fiscal)
        - ✅ 0200 (Cadastro de Produtos)
        - ✅ 0150 (Cadastro de Participantes)
        
        **Em breve:**
        - 🔄 C190 (Detalhamento ICMS)
        - 🔄 E110 (Apuração do ICMS)
        - 🔄 H010 (Inventário)
        """)
        
        