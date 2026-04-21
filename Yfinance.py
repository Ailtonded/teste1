"""
Sistema de Importação e Exportação de Plano de Contas para TOTVS Protheus
Versão: 3.5.0 - Formato Oficial Protheus - Produção
"""

import streamlit as st
import pandas as pd
from io import BytesIO
import json
import re
from typing import Tuple, Optional, Dict, Any, List
from datetime import datetime

# Configuração da página
st.set_page_config(
    page_title="Sistema Protheus - Plano de Contas",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== CONSTANTES ====================

COLUNAS_OBRIGATORIAS = ['CT1_CONTA', 'CT1_DESC01']

# LAYOUT COMPLETO DO PROTHEUS (TODAS AS 79 COLUNAS - ORDEM EXATA)
LAYOUT_FINAL_COMPLETO: List[str] = [
    'CT1_FILIAL', 'CT1_CONTA', 'CT1_DESC01', 'CT1_DESC02', 'CT1_DESC03',
    'CT1_DESC04', 'CT1_DESC05', 'CT1_CLASSE', 'CT1_NORMAL', 'CT1_RES',
    'CT1_BLOQ', 'CT1_DTBLIN', 'CT1_DTBLFI', 'CT1_DC', 'CT1_NCUSTO',
    'CT1_CC', 'CT1_CVD01', 'CT1_CVD02', 'CT1_CVD03', 'CT1_CVD04',
    'CT1_CVD05', 'CT1_CVC01', 'CT1_CVC02', 'CT1_CVC03', 'CT1_CVC04',
    'CT1_CVC05', 'CT1_CTASUP', 'CT1_HP', 'CT1_ACITEM', 'CT1_ACCUST',
    'CT1_ACCLVL', 'CT1_DTEXIS', 'CT1_CTAVM', 'CT1_CTARED', 'CT1_DTEXSF',
    'CT1_MOEDVM', 'CT1_CTALP', 'CT1_CTAPON', 'CT1_BOOK', 'CT1_GRUPO',
    'CT1_AGLSLD', 'CT1_RGNV1', 'CT1_RGNV2', 'CT1_RGNV3', 'CT1_CCOBRG',
    'CT1_ITOBRG', 'CT1_CLOBRG', 'CT1_CTLALU', 'CT1_TRNSEF', 'CT1_TPLALU',
    'CT1_AGLUT', 'CT1_LALHIR', 'CT1_LALUR', 'CT1_RATEIO', 'CT1_ESTOUR',
    'CT1_CODIMP', 'CT1_AJ_INF', 'CT1_DIOPS', 'CT1_NATCTA', 'CT1_ACATIV',
    'CT1_ATOBRG', 'CT1_ACET05', 'CT1_05OBRG', 'CT1_INDNAT', 'CT1_SPEDST',
    'CT1_NTSPED', 'CT1_ACAT01', 'CT1_AT01OB', 'CT1_ACAT02', 'CT1_AT02OB',
    'CT1_ACAT03', 'CT1_AT03OB', 'CT1_ACAT04', 'CT1_AT04OB', 'CT1_TPO01',
    'CT1_TPO02', 'CT1_TPO03', 'CT1_TPO04', 'CT1_INTP', 'CT1_PVARC', 'CT1_CTAORC'
]

# LARGURAS DE CADA CAMPO (conforme dicionário CT1 do Protheus)
LARGURAS_CAMPOS: Dict[str, int] = {
    'CT1_FILIAL': 2, 'CT1_CONTA': 20, 'CT1_DESC01': 40, 'CT1_DESC02': 40,
    'CT1_DESC03': 40, 'CT1_DESC04': 40, 'CT1_DESC05': 40, 'CT1_CLASSE': 1,
    'CT1_NORMAL': 1, 'CT1_RES': 10, 'CT1_BLOQ': 1, 'CT1_DTBLIN': 8,
    'CT1_DTBLFI': 8, 'CT1_DC': 1, 'CT1_NCUSTO': 14, 'CT1_CC': 9,
    'CT1_CVD01': 1, 'CT1_CVD02': 1, 'CT1_CVD03': 1, 'CT1_CVD04': 1,
    'CT1_CVD05': 1, 'CT1_CVC01': 1, 'CT1_CVC02': 1, 'CT1_CVC03': 1,
    'CT1_CVC04': 1, 'CT1_CVC05': 1, 'CT1_CTASUP': 20, 'CT1_HP': 3,
    'CT1_ACITEM': 1, 'CT1_ACCUST': 1, 'CT1_ACCLVL': 1, 'CT1_DTEXIS': 8,
    'CT1_CTAVM': 20, 'CT1_CTARED': 20, 'CT1_DTEXSF': 8, 'CT1_MOEDVM': 2,
    'CT1_CTALP': 20, 'CT1_CTAPON': 20, 'CT1_BOOK': 20, 'CT1_GRUPO': 20,
    'CT1_AGLSLD': 2, 'CT1_RGNV1': 20, 'CT1_RGNV2': 20, 'CT1_RGNV3': 20,
    'CT1_CCOBRG': 1, 'CT1_ITOBRG': 1, 'CT1_CLOBRG': 1, 'CT1_CTLALU': 20,
    'CT1_TRNSEF': 1, 'CT1_TPLALU': 1, 'CT1_AGLUT': 2, 'CT1_LALHIR': 1,
    'CT1_LALUR': 1, 'CT1_RATEIO': 1, 'CT1_ESTOUR': 1, 'CT1_CODIMP': 20,
    'CT1_AJ_INF': 1, 'CT1_DIOPS': 1, 'CT1_NATCTA': 2, 'CT1_ACATIV': 1,
    'CT1_ATOBRG': 1, 'CT1_ACET05': 1, 'CT1_05OBRG': 1, 'CT1_INDNAT': 1,
    'CT1_SPEDST': 2, 'CT1_NTSPED': 1, 'CT1_ACAT01': 1, 'CT1_AT01OB': 1,
    'CT1_ACAT02': 1, 'CT1_AT02OB': 1, 'CT1_ACAT03': 1, 'CT1_AT03OB': 1,
    'CT1_ACAT04': 1, 'CT1_AT04OB': 1, 'CT1_TPO01': 2, 'CT1_TPO02': 2,
    'CT1_TPO03': 2, 'CT1_TPO04': 2, 'CT1_INTP': 1, 'CT1_PVARC': 2, 'CT1_CTAORC': 1
}

# Opções de validação
OPCOES_CLASSE = {
    '1': 'Sintética (Totalizadora)',
    '2': 'Analítica (Recebe Valores)'
}

OPCOES_NORMAL = {
    '1': 'Devedora',
    '2': 'Credora'
}

OPCOES_BLOQ = {
    '1': 'Sim (Bloqueada)',
    '2': 'Não (Ativa)'
}

# ==================== FUNÇÕES PRINCIPAIS ====================

def formatar_valor_protheus(valor: Any, largura: int, campo: str = '') -> str:
    """
    Formata um valor para o padrão Protheus:
    - String com largura fixa (espaços à direita)
    - Trata datas no formato YYYYMMDD
    - Remove caracteres inválidos
    - Valores nulos viram espaços
    
    Args:
        valor: Valor a ser formatado
        largura: Tamanho máximo do campo
        campo: Nome do campo (para tratamento específico)
        
    Returns:
        String formatada com padding de espaços
    """
    # Trata nulos
    if pd.isna(valor) or valor is None:
        return ' ' * largura
    
    # Converte para string
    valor_str = str(valor).strip()
    
    # Trata campos vazios
    if valor_str == '' or valor_str == 'nan' or valor_str == 'None':
        return ' ' * largura
    
    # Tratamento especial para datas (YYYYMMDD)
    if 'DT' in campo or 'DATA' in campo:
        # Tenta converter datas no formato DD/MM/YYYY para YYYYMMDD
        if '/' in valor_str:
            try:
                partes = valor_str.split('/')
                if len(partes) == 3:
                    valor_str = f"{partes[2]}{partes[1]}{partes[0]}"
            except:
                pass
        
        # Remove caracteres não numéricos
        valor_str = re.sub(r'[^0-9]', '', valor_str)
        
        # Garante 8 dígitos para data
        if len(valor_str) == 8:
            return valor_str.ljust(largura)
        elif len(valor_str) == 6:
            valor_str = '19' + valor_str
            return valor_str.ljust(largura)
        else:
            return ' ' * largura
    
    # Tratamento para campos numéricos
    if any(num in campo for num in ['VALOR', 'SALDO', 'NCUSTO']):
        # Remove caracteres não numéricos exceto ponto e vírgula
        valor_str = re.sub(r'[^0-9.,-]', '', valor_str)
        # Troca vírgula por ponto
        valor_str = valor_str.replace(',', '.')
    
    # Remove caracteres especiais inválidos
    valor_str = re.sub(r'[^\w\s\.\-\/]', '', valor_str)
    
    # Trunca se necessário
    if len(valor_str) > largura:
        valor_str = valor_str[:largura]
    
    # Preenche com espaços à direita
    return valor_str.ljust(largura)


def gerar_csv_protheus(df: pd.DataFrame) -> str:
    """
    Gera CSV no formato EXATO que o Protheus espera para importação da tabela CT1.
    
    Formato correto:
    - Linha 0: 0;CT1;CVD
    - Linha 1: 1;CT1_FILIAL;CT1_CONTA;CT1_DESC01;... (apenas nomes, SEM tamanhos)
    - Linhas dados: 1;valor1;valor2;... (com padding de espaços)
    - Linha final: 2;CVD_FILIAL;CVD_CONTA;...
    
    Args:
        df: DataFrame com os dados transformados
        
    Returns:
        String CSV formatada para o Protheus
    """
    output_lines = []
    
    # Linha 0 - Tipo de arquivo e tabela
    output_lines.append("0;CT1;CVD")
    
    # Linha 1 - Cabeçalho com nomes dos campos APENAS (SEM tamanhos)
    header_campos = "1;" + ";".join(LAYOUT_FINAL_COMPLETO)
    output_lines.append(header_campos)
    
    # Linhas de dados - cada campo com padding de espaços (largura fixa)
    for idx, row in df.iterrows():
        linha_dados = ["1"]
        for col in LAYOUT_FINAL_COMPLETO:
            valor = row[col] if col in row else ''
            largura = LARGURAS_CAMPOS.get(col, 20)
            valor_formatado = formatar_valor_protheus(valor, largura, col)
            linha_dados.append(valor_formatado)
        output_lines.append(";".join(linha_dados))
    
    # Linha final - Marcador de fim do arquivo
    output_lines.append("2;CVD_FILIAL;CVD_CONTA;CVD_ENTREF;CVD_CODPLA;CVD_VERSAO;CVD_CTAREF;CVD_CUSTO;CVD_CLASSE;CVD_TPUTIL;CVD_NATCTA;CVD_CTASUP")
    
    return "\n".join(output_lines)


def validar_conta(conta: str) -> Tuple[bool, str]:
    """Valida o código da conta contábil"""
    if pd.isna(conta) or not str(conta).strip():
        return False, "Código da conta vazio"
    
    conta_limpa = str(conta).strip()
    
    # Aceita números, pontos e vírgulas
    if not all(c.isdigit() or c in ['.', ','] for c in conta_limpa):
        return False, f"Código '{conta_limpa}' contém caracteres inválidos"
    
    # Converte vírgula para ponto
    conta_limpa = conta_limpa.replace(',', '.')
    
    return True, conta_limpa


def validar_descricao(descricao: str) -> Tuple[bool, str]:
    """Valida a descrição da conta"""
    if pd.isna(descricao) or not str(descricao).strip():
        return False, "Descrição da conta vazia"
    return True, str(descricao).strip()


def carregar_arquivo(uploaded_file) -> Optional[pd.DataFrame]:
    """Carrega arquivo Excel e realiza tratamento inicial"""
    try:
        df = pd.read_excel(uploaded_file, dtype=str)
        df.columns = df.columns.str.strip()
        df = df.map(lambda x: x.strip() if isinstance(x, str) else x)
        return df
    except Exception as e:
        st.error(f"❌ Erro ao carregar arquivo: {str(e)}")
        return None


def transformar_para_protheus(df: pd.DataFrame, config: Dict[str, Any]) -> Tuple[pd.DataFrame, List[str]]:
    """Transforma DataFrame para o layout COMPLETO do Protheus"""
    # Criar DataFrame com TODAS as colunas do layout
    df_protheus = pd.DataFrame(columns=LAYOUT_FINAL_COMPLETO)
    erros = []
    
    # Valores padrão para campos obrigatórios do Protheus
    valores_padrao = {
        'CT1_RES': '',
        'CT1_DC': '7',
        'CT1_HP': '   ',
        'CT1_ACITEM': '1',
        'CT1_ACCUST': '1',
        'CT1_ACCLVL': '1',
        'CT1_DTEXIS': '19800101',
        'CT1_ACATIV': '1',
        'CT1_ATOBRG': '1',
        'CT1_ACET05': '1',
        'CT1_05OBRG': '1',
        'CT1_INDNAT': '1',
        'CT1_SPEDST': '01',
        'CT1_NTSPED': '1',
        'CT1_INTP': '1',
        'CT1_PVARC': '01'
    }
    
    # Para cada linha do arquivo original
    for idx, row in df.iterrows():
        linha_num = idx + 2
        nova_linha = {}
        
        # Inicializar todos os campos como vazio
        for col in LAYOUT_FINAL_COMPLETO:
            nova_linha[col] = ''
        
        # ========== MAPEAR CAMPOS DO EXCEL PARA O PROTHEUS ==========
        
        # CT1_CONTA (código da conta)
        if 'CT1_CONTA' in row:
            conta = row['CT1_CONTA']
            valido, resultado = validar_conta(conta)
            if not valido:
                erros.append(f"Linha {linha_num}: {resultado}")
                nova_linha['CT1_CONTA'] = ''
            else:
                nova_linha['CT1_CONTA'] = resultado
        
        # CT1_DESC01 (descrição)
        if 'CT1_DESC01' in row:
            descricao = row['CT1_DESC01']
            valido, resultado = validar_descricao(descricao)
            if not valido:
                erros.append(f"Linha {linha_num}: {resultado}")
                nova_linha['CT1_DESC01'] = ''
            else:
                nova_linha['CT1_DESC01'] = resultado
        
        # CT1_FILIAL
        if 'CT1_FILIAL' in row and row['CT1_FILIAL']:
            nova_linha['CT1_FILIAL'] = str(row['CT1_FILIAL']).strip()[:2]
        elif config.get('filial_padrao'):
            nova_linha['CT1_FILIAL'] = config['filial_padrao']
        
        # CT1_CLASSE
        if 'CT1_CLASSE' in row and row['CT1_CLASSE']:
            classe = str(row['CT1_CLASSE']).strip()
            if classe in OPCOES_CLASSE:
                nova_linha['CT1_CLASSE'] = classe
        if not nova_linha['CT1_CLASSE'] and config.get('aplicar_regras_auto', True):
            # Determina automaticamente: níveis 0-1 = Sintética, 2+ = Analítica
            niveis = nova_linha['CT1_CONTA'].count('.')
            nova_linha['CT1_CLASSE'] = '1' if niveis <= 1 else '2'
        elif not nova_linha['CT1_CLASSE'] and config.get('classe_padrao'):
            nova_linha['CT1_CLASSE'] = config['classe_padrao']
        
        # CT1_NORMAL
        if 'CT1_NORMAL' in row and row['CT1_NORMAL']:
            normal = str(row['CT1_NORMAL']).strip()
            if normal in OPCOES_NORMAL:
                nova_linha['CT1_NORMAL'] = normal
        if not nova_linha['CT1_NORMAL']:
            nova_linha['CT1_NORMAL'] = config.get('normal_padrao', '1')
        
        # CT1_BLOQ
        if 'CT1_BLOQ' in row and row['CT1_BLOQ']:
            bloq = str(row['CT1_BLOQ']).strip()
            if bloq in OPCOES_BLOQ:
                nova_linha['CT1_BLOQ'] = bloq
        if not nova_linha['CT1_BLOQ']:
            nova_linha['CT1_BLOQ'] = config.get('bloq_padrao', '2')
        
        # CT1_CTASUP (conta superior)
        if 'CT1_CTASUP' in row and row['CT1_CTASUP']:
            nova_linha['CT1_CTASUP'] = str(row['CT1_CTASUP']).strip()
        
        # Aplicar valores padrão
        for campo, valor in valores_padrao.items():
            if not nova_linha.get(campo):
                nova_linha[campo] = valor
        
        # Adicionar linha ao DataFrame
        df_protheus.loc[len(df_protheus)] = nova_linha
    
    return df_protheus, erros


def main():
    """Função principal do aplicativo"""
    st.title("📊 Sistema de Plano de Contas - TOTVS Protheus")
    st.markdown("---")
    
    # Configurações iniciais
    config = {
        'filial_padrao': '',
        'aplicar_regras_auto': True,
        'classe_padrao': '',
        'normal_padrao': '1',
        'bloq_padrao': '2'
    }
    
    # Sidebar - Configurações
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        config['filial_padrao'] = st.text_input(
            "Filial Padrão",
            max_chars=2,
            placeholder="Ex: 01"
        )
        
        st.markdown("---")
        
        config['aplicar_regras_auto'] = st.checkbox(
            "Determinar classe automaticamente",
            value=True
        )
        
        if not config['aplicar_regras_auto']:
            config['classe_padrao'] = st.selectbox(
                "Classe Padrão",
                options=['', '1', '2'],
                format_func=lambda x: 'Não preencher' if x == '' else f"{x} - {OPCOES_CLASSE[x]}"
            )
        
        st.markdown("---")
        
        config['normal_padrao'] = st.selectbox(
            "Natureza Padrão",
            options=['1', '2'],
            format_func=lambda x: f"{x} - {OPCOES_NORMAL[x]}"
        )
        
        st.markdown("---")
        
        config['bloq_padrao'] = st.selectbox(
            "Bloqueio Padrão",
            options=['1', '2'],
            format_func=lambda x: f"{x} - {OPCOES_BLOQ[x]}"
        )
    
    # Upload do arquivo
    uploaded_file = st.file_uploader(
        "📂 Selecione o arquivo Excel (.xlsx)",
        type=['xlsx'],
        help="Colunas: CT1_CONTA (código) e CT1_DESC01 (descrição)"
    )
    
    if uploaded_file is not None:
        with st.spinner("Carregando arquivo..."):
            df_original = carregar_arquivo(uploaded_file)
        
        if df_original is not None:
            # Verificar colunas obrigatórias
            colunas_faltando = set(COLUNAS_OBRIGATORIAS) - set(df_original.columns)
            if colunas_faltando:
                st.error(f"❌ Colunas obrigatórias faltando: {', '.join(colunas_faltando)}")
                st.stop()
            
            st.success("✅ Arquivo carregado com sucesso!")
            
            with st.spinner("Transformando dados..."):
                df_transformado, erros = transformar_para_protheus(df_original, config)
            
            if erros:
                st.warning(f"⚠️ {len(erros)} aviso(s) encontrado(s):")
                for erro in erros[:10]:  # Mostra apenas os 10 primeiros
                    st.warning(erro)
            
            # Preview dos dados
            st.subheader("📋 Preview dos Dados Transformados")
            colunas_preview = ['CT1_CONTA', 'CT1_DESC01', 'CT1_CLASSE', 'CT1_NORMAL']
            st.dataframe(df_transformado[colunas_preview].head(10), use_container_width=True)
            
            st.info(f"Total de registros: {len(df_transformado)} | Colunas no CSV: {len(LAYOUT_FINAL_COMPLETO)}")
            
            # Botão de exportação
            if st.button("📥 Gerar CSV para Protheus", type="primary", use_container_width=True):
                try:
                    csv_data = gerar_csv_protheus(df_transformado)
                    
                    # Criar arquivo para download
                    b = BytesIO()
                    b.write(csv_data.encode('latin1'))
                    b.seek(0)
                    
                    st.download_button(
                        label="✅ Baixar CSV",
                        data=b,
                        file_name=f"plano_contas_protheus_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                    
                    st.success("✅ CSV gerado com sucesso! Pronto para importação no Protheus.")
                    
                    # Preview do CSV gerado
                    with st.expander("🔍 Ver preview do CSV gerado (primeiras linhas)"):
                        linhas = csv_data.split('\n')[:5]
                        st.code('\n'.join(linhas), language="text")
                        
                except Exception as e:
                    st.error(f"❌ Erro ao gerar CSV: {str(e)}")
    
    else:
        st.info("👈 Configure as opções e faça upload de um arquivo Excel para começar")
        
        with st.expander("📋 Exemplo de arquivo válido"):
            st.markdown("""
            **Colunas necessárias no Excel:**
            - `CT1_CONTA` - Código da conta (ex: 1, 1.01, 1.01.001)
            - `CT1_DESC01` - Descrição da conta (ex: Ativo, Caixa, Bancos)
            
            **Colunas opcionais:**
            - `CT1_CLASSE` - 1=Sintética, 2=Analítica
            - `CT1_NORMAL` - 1=Devedora, 2=Credora
            - `CT1_CTASUP` - Conta superior
            - `CT1_BLOQ` - 1=Bloqueada, 2=Ativa
            - `CT1_FILIAL` - Código da filial
            """)
            
            df_exemplo = pd.DataFrame({
                'CT1_CONTA': ['1', '1.01', '1.01.001', '1.01.002'],
                'CT1_DESC01': ['Ativo', 'Ativo Circulante', 'Caixa', 'Bancos'],
                'CT1_CLASSE': ['1', '1', '2', '2'],
                'CT1_NORMAL': ['1', '1', '1', '1']
            })
            st.dataframe(df_exemplo, use_container_width=True)


if __name__ == "__main__":
    main()