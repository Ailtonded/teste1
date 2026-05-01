import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from dateutil.relativedelta import relativedelta

st.set_page_config(page_title="Mini ERP Contábil", layout="wide")

# -------------------------
# Inicialização do Estado
# -------------------------
def init_session_state():
    if "lancamentos" not in st.session_state:
        st.session_state.lancamentos = []
    
    if "contas" not in st.session_state:
        st.session_state.contas = ["Caixa", "Banco", "Receita", "Despesa"]
    
    if "expanded_nodes" not in st.session_state:
        st.session_state.expanded_nodes = set(["1", "2", "3", "4"])
    
    if "contas_hierarquicas" not in st.session_state:
        st.session_state.contas_hierarquicas = {}
        
        estrutura_base = {
            "1": {"codigo": "1", "descricao": "ATIVO", "tipo": "Ativo", "natureza": "Sintética", "pai": None, "nivel": 1},
            "11": {"codigo": "11", "descricao": "Disponibilidade", "tipo": "Ativo", "natureza": "Sintética", "pai": "1", "nivel": 2},
            "111": {"codigo": "111", "descricao": "Caixa", "tipo": "Ativo", "natureza": "Analítica", "pai": "11", "nivel": 3},
            "112": {"codigo": "112", "descricao": "Banco", "tipo": "Ativo", "natureza": "Analítica", "pai": "11", "nivel": 3},
            "2": {"codigo": "2", "descricao": "PASSIVO", "tipo": "Passivo", "natureza": "Sintética", "pai": None, "nivel": 1},
            "3": {"codigo": "3", "descricao": "RECEITAS", "tipo": "Receita", "natureza": "Sintética", "pai": None, "nivel": 1},
            "30": {"codigo": "30", "descricao": "Receitas Operacionais", "tipo": "Receita", "natureza": "Sintética", "pai": "3", "nivel": 2},
            "301": {"codigo": "301", "descricao": "Vendas", "tipo": "Receita", "natureza": "Analítica", "pai": "30", "nivel": 3},
            "4": {"codigo": "4", "descricao": "DESPESAS", "tipo": "Despesa", "natureza": "Sintética", "pai": None, "nivel": 1},
            "40": {"codigo": "40", "descricao": "Despesas Operacionais", "tipo": "Despesa", "natureza": "Sintética", "pai": "4", "nivel": 2},
            "401": {"codigo": "401", "descricao": "Aluguel", "tipo": "Despesa", "natureza": "Analítica", "pai": "40", "nivel": 3},
        }
        
        for codigo, dados in estrutura_base.items():
            st.session_state.contas_hierarquicas[codigo] = dados
        
        for conta in st.session_state.contas:
            if conta not in [c["descricao"] for c in estrutura_base.values()]:
                codigo = f"999{len(st.session_state.contas_hierarquicas)}"
                tipo = "Ativo"
                if "receita" in conta.lower():
                    tipo = "Receita"
                elif "despesa" in conta.lower():
                    tipo = "Despesa"
                elif "passivo" in conta.lower():
                    tipo = "Passivo"
                
                st.session_state.contas_hierarquicas[codigo] = {
                    "codigo": codigo,
                    "descricao": conta,
                    "tipo": tipo,
                    "natureza": "Analítica",
                    "pai": None,
                    "nivel": 1
                }

init_session_state()

# -------------------------
# Funções de Hierarquia
# -------------------------
def auto_calcular_nivel(codigo):
    if '.' in codigo:
        return len(codigo.split('.'))
    else:
        return len(codigo)

def auto_identificar_pai(codigo):
    if '.' in codigo:
        partes = codigo.split('.')
        if len(partes) > 1:
            return '.'.join(partes[:-1])
    else:
        if len(codigo) > 1:
            return codigo[:-1]
    return None

def montar_hierarquia(contas_dict, expanded_nodes):
    """Retorna lista de contas com indentacao e respeito aos nos expandidos"""
    def ordenar_recursivo(pai=None, nivel=0):
        resultado = []
        contas_filhas = [c for c in contas_dict.values() if c.get("pai") == pai]
        contas_filhas.sort(key=lambda x: x["codigo"])
        
        for conta in contas_filhas:
            resultado.append(conta)
            if conta["codigo"] in expanded_nodes:
                resultado.extend(ordenar_recursivo(conta["codigo"], nivel + 1))
        
        return resultado
    
    raizes = [c for c in contas_dict.values() if c.get("pai") is None]
    raizes.sort(key=lambda x: x["codigo"])
    
    resultado = []
    for raiz in raizes:
        resultado.append(raiz)
        if raiz["codigo"] in expanded_nodes:
            resultado.extend(ordenar_recursivo(raiz["codigo"], 1))
    
    return resultado

def validar_codigo(codigo, tipo, contas_dict):
    if not codigo:
        return False, "Código é obrigatório!"
    if codigo in contas_dict:
        return False, "Código já existe!"
    
    primeiro_digito = codigo[0]
    regras = {"Ativo": "1", "Passivo": "2", "Receita": "3", "Despesa": "4"}
    
    if tipo in regras and primeiro_digito != regras[tipo]:
        return False, f"Conta {tipo} deve começar com {regras[tipo]}!"
    
    pai = auto_identificar_pai(codigo)
    if pai and pai not in contas_dict:
        return False, f"Conta pai '{pai}' não existe!"
    
    return True, "OK"

def pode_excluir_conta(codigo, contas_dict, lancamentos):
    if codigo not in contas_dict:
        return False, "Conta não encontrada!"
    
    tem_filhos = any(c.get("pai") == codigo for c in contas_dict.values())
    if tem_filhos:
        return False, "Conta possui contas filhas!"
    
    conta = contas_dict[codigo]
    tem_lancamento = any(lanc["conta_debito"] == conta["descricao"] or 
                        (lanc.get("conta_credito") == conta["descricao"]) 
                        for lanc in lancamentos)
    
    if tem_lancamento:
        return False, "Conta possui lançamentos!"
    
    return True, "OK"

# -------------------------
# Funções de Lançamentos
# -------------------------
def gerar_lancamentos_recorrentes(data_base, tipo_lanc, conta_debito, conta_credito, valor, historico, quantidade, periodicidade):
    lancamentos = []
    
    for i in range(quantidade):
        if i == 0:
            data_lanc = data_base
        else:
            if periodicidade == "Diário":
                data_lanc = data_base + timedelta(days=i)
            elif periodicidade == "Semanal":
                data_lanc = data_base + timedelta(weeks=i)
            elif periodicidade == "Mensal":
                data_lanc = data_base + relativedelta(months=i)
            else:
                data_lanc = data_base
        
        lancamentos.append({
            "data": data_lanc.strftime("%Y-%m-%d"),
            "tipo": tipo_lanc,
            "conta_debito": conta_debito if tipo_lanc in ["Partida Dobrada", "Débito Simples"] else None,
            "conta_credito": conta_credito if tipo_lanc in ["Partida Dobrada", "Crédito Simples"] else None,
            "valor": valor,
            "historico": f"{historico} ({'Original' if i==0 else f'Repetição {i}'})",
            "data_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    
    return lancamentos

def adicionar_lancamento(data, tipo_lanc, conta_debito, conta_credito, valor, historico, recorrente, qtd_recorrencia, periodicidade):
    if valor <= 0:
        return False, "Valor deve ser maior que zero!"
    
    contas_analiticas = [c["descricao"] for c in st.session_state.contas_hierarquicas.values() if c["natureza"] == "Analítica"]
    
    if tipo_lanc == "Partida Dobrada":
        if conta_debito == conta_credito:
            return False, "Contas débito e crédito não podem ser iguais!"
        if conta_debito not in contas_analiticas:
            return False, f"Conta '{conta_debito}' não é analítica!"
        if conta_credito not in contas_analiticas:
            return False, f"Conta '{conta_credito}' não é analítica!"
        
        lancamentos = [{
            "data": data.strftime("%Y-%m-%d"),
            "tipo": tipo_lanc,
            "conta_debito": conta_debito,
            "conta_credito": conta_credito,
            "valor": valor,
            "historico": historico,
            "data_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }]
        
        if recorrente and qtd_recorrencia > 1:
            lancamentos.extend(gerar_lancamentos_recorrentes(data, tipo_lanc, conta_debito, conta_credito, valor, historico, qtd_recorrencia, periodicidade)[1:])
        
        st.session_state.lancamentos.extend(lancamentos)
        return True, f"{len(lancamentos)} lançamento(s) registrado(s)!"
    
    elif tipo_lanc == "Débito Simples":
        if conta_debito not in contas_analiticas:
            return False, f"Conta '{conta_debito}' não é analítica!"
        
        lancamentos = [{
            "data": data.strftime("%Y-%m-%d"),
            "tipo": tipo_lanc,
            "conta_debito": conta_debito,
            "conta_credito": None,
            "valor": valor,
            "historico": historico,
            "data_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }]
        
        if recorrente and qtd_recorrencia > 1:
            lancamentos.extend(gerar_lancamentos_recorrentes(data, tipo_lanc, conta_debito, None, valor, historico, qtd_recorrencia, periodicidade)[1:])
        
        st.session_state.lancamentos.extend(lancamentos)
        return True, f"{len(lancamentos)} lançamento(s) registrado(s)!"
    
    else:  # Crédito Simples
        if conta_credito not in contas_analiticas:
            return False, f"Conta '{conta_credito}' não é analítica!"
        
        lancamentos = [{
            "data": data.strftime("%Y-%m-%d"),
            "tipo": tipo_lanc,
            "conta_debito": None,
            "conta_credito": conta_credito,
            "valor": valor,
            "historico": historico,
            "data_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }]
        
        if recorrente and qtd_recorrencia > 1:
            lancamentos.extend(gerar_lancamentos_recorrentes(data, tipo_lanc, None, conta_credito, valor, historico, qtd_recorrencia, periodicidade)[1:])
        
        st.session_state.lancamentos.extend(lancamentos)
        return True, f"{len(lancamentos)} lançamento(s) registrado(s)!"

def excluir_lancamento(index):
    if 0 <= index < len(st.session_state.lancamentos):
        st.session_state.lancamentos.pop(index)
        return True
    return False

def sugerir_conta(historico, lancamentos):
    """Sugere conta baseada no histórico anterior"""
    if not lancamentos or not historico:
        return None
    
    # Buscar histórico similar
    palavras = historico.lower().split()
    contas_usadas = {}
    
    for lanc in lancamentos:
        if lanc["historico"]:
            for palavra in palavras:
                if palavra in lanc["historico"].lower():
                    if lanc["conta_debito"]:
                        contas_usadas[lanc["conta_debito"]] = contas_usadas.get(lanc["conta_debito"], 0) + 1
                    if lanc.get("conta_credito"):
                        contas_usadas[lanc.get("conta_credito")] = contas_usadas.get(lanc.get("conta_credito"), 0) + 1
    
    if contas_usadas:
        return max(contas_usadas, key=contas_usadas.get)
    return None

# -------------------------
# Funções de Cálculo
# -------------------------
def calcular_saldo_conta(conta_descricao, df_anterior, df_periodo):
    deb_anterior = df_anterior[df_anterior["conta_debito"] == conta_descricao]["valor"].sum()
    cred_anterior = df_anterior[df_anterior["conta_credito"] == conta_descricao]["valor"].sum()
    saldo_anterior = deb_anterior - cred_anterior
    
    deb_periodo = df_periodo[df_periodo["conta_debito"] == conta_descricao]["valor"].sum()
    cred_periodo = df_periodo[df_periodo["conta_credito"] == conta_descricao]["valor"].sum()
    
    saldo_final = saldo_anterior + deb_periodo - cred_periodo
    
    return {"saldo_anterior": saldo_anterior, "debitos": deb_periodo, "creditos": cred_periodo, "saldo_final": saldo_final}

def calcular_saldo_sintetico(conta_codigo, contas_dict, df_anterior, df_periodo):
    contas_filhas = [c for c in contas_dict.values() if c.get("pai") == conta_codigo]
    
    resultado = {"saldo_anterior": 0, "debitos": 0, "creditos": 0, "saldo_final": 0}
    
    for filha in contas_filhas:
        if filha["natureza"] == "Analítica":
            saldo = calcular_saldo_conta(filha["descricao"], df_anterior, df_periodo)
        else:
            saldo = calcular_saldo_sintetico(filha["codigo"], contas_dict, df_anterior, df_periodo)
        
        for key in resultado:
            resultado[key] += saldo[key]
    
    return resultado

def calcular_dre(data_inicio, data_fim):
    """Calcula DRE (Demonstrativo de Resultado do Exercício)"""
    if not st.session_state.lancamentos:
        return pd.DataFrame(), 0, 0
    
    df = pd.DataFrame(st.session_state.lancamentos)
    df["data"] = pd.to_datetime(df["data"])
    
    df_periodo = df[(df["data"] >= pd.to_datetime(data_inicio)) & (df["data"] <= pd.to_datetime(data_fim))]
    
    receitas = 0
    despesas = 0
    contas_detalhe = []
    
    contas_receita = [c for c in st.session_state.contas_hierarquicas.values() 
                      if c["tipo"] == "Receita" and c["natureza"] == "Analítica"]
    
    contas_despesa = [c for c in st.session_state.contas_hierarquicas.values() 
                      if c["tipo"] == "Despesa" and c["natureza"] == "Analítica"]
    
    for conta in contas_receita:
        credito = df_periodo[df_periodo["conta_credito"] == conta["descricao"]]["valor"].sum()
        debito = df_periodo[df_periodo["conta_debito"] == conta["descricao"]]["valor"].sum()
        saldo = credito - debito
        receitas += saldo
        if saldo != 0:
            contas_detalhe.append({"Conta": f"{conta['codigo']} - {conta['descricao']}", "Tipo": "Receita", "Valor": saldo})
    
    for conta in contas_despesa:
        debito = df_periodo[df_periodo["conta_debito"] == conta["descricao"]]["valor"].sum()
        credito = df_periodo[df_periodo["conta_credito"] == conta["descricao"]]["valor"].sum()
        saldo = debito - credito
        despesas += saldo
        if saldo != 0:
            contas_detalhe.append({"Conta": f"{conta['codigo']} - {conta['descricao']}", "Tipo": "Despesa", "Valor": saldo})
    
    df_detalhe = pd.DataFrame(contas_detalhe)
    return df_detalhe, receitas, despesas

def calcular_fluxo_caixa(data_inicio, data_fim):
    """Calcula fluxo de caixa diário"""
    if not st.session_state.lancamentos:
        return pd.DataFrame()
    
    df = pd.DataFrame(st.session_state.lancamentos)
    df["data"] = pd.to_datetime(df["data"])
    
    contas_caixa = ["Caixa", "Banco", "Disponibilidade"]
    contas_receita = [c["descricao"] for c in st.session_state.contas_hierarquicas.values() 
                      if c["tipo"] == "Receita" and c["natureza"] == "Analítica"]
    contas_despesa = [c["descricao"] for c in st.session_state.contas_hierarquicas.values() 
                      if c["tipo"] == "Despesa" and c["natureza"] == "Analítica"]
    
    df_periodo = df[(df["data"] >= pd.to_datetime(data_inicio)) & (df["data"] <= pd.to_datetime(data_fim))]
    
    datas = pd.date_range(start=data_inicio, end=data_fim, freq='D')
    fluxo = []
    
    saldo_acumulado = 0
    
    for data in datas:
        entradas = 0
        saidas = 0
        
        lanc_dia = df_periodo[df_periodo["data"] == data]
        
        for _, lanc in lanc_dia.iterrows():
            if lanc["tipo"] == "Partida Dobrada":
                if lanc["conta_credito"] in contas_receita:
                    entradas += lanc["valor"]
                if lanc["conta_debito"] in contas_despesa:
                    saidas += lanc["valor"]
            elif lanc["tipo"] == "Débito Simples":
                if lanc["conta_debito"] in contas_despesa:
                    saidas += lanc["valor"]
            else:
                if lanc["conta_credito"] in contas_receita:
                    entradas += lanc["valor"]
        
        saldo_dia = entradas - saidas
        saldo_acumulado += saldo_dia
        
        fluxo.append({
            "Data": data,
            "Entradas": entradas,
            "Saídas": saidas,
            "Saldo Dia": saldo_dia,
            "Saldo Acumulado": saldo_acumulado
        })
    
    return pd.DataFrame(fluxo)

def calcular_comparativo_mensal():
    """Calcula comparativo mensal de receitas e despesas"""
    if not st.session_state.lancamentos:
        return pd.DataFrame()
    
    df = pd.DataFrame(st.session_state.lancamentos)
    df["data"] = pd.to_datetime(df["data"])
    df["mes_ano"] = df["data"].dt.strftime("%Y-%m")
    
    contas_receita = [c["descricao"] for c in st.session_state.contas_hierarquicas.values() 
                      if c["tipo"] == "Receita" and c["natureza"] == "Analítica"]
    contas_despesa = [c["descricao"] for c in st.session_state.contas_hierarquicas.values() 
                      if c["tipo"] == "Despesa" and c["natureza"] == "Analítica"]
    
    resultado = []
    
    for mes in df["mes_ano"].unique():
        df_mes = df[df["mes_ano"] == mes]
        
        receitas = 0
        for conta in contas_receita:
            receitas += df_mes[df_mes["conta_credito"] == conta]["valor"].sum()
            receitas -= df_mes[df_mes["conta_debito"] == conta]["valor"].sum()
        
        despesas = 0
        for conta in contas_despesa:
            despesas += df_mes[df_mes["conta_debito"] == conta]["valor"].sum()
            despesas -= df_mes[df_mes["conta_credito"] == conta]["valor"].sum()
        
        resultado.append({
            "Mês": mes,
            "Receitas": receitas,
            "Despesas": despesas,
            "Resultado": receitas - despesas
        })
    
    return pd.DataFrame(resultado).sort_values("Mês")

def calcular_demonstrativo_saldos(data_inicio, data_fim):
    """Calcula demonstrativo completo com hierarquia"""
    if not st.session_state.lancamentos:
        return []
    
    df = pd.DataFrame(st.session_state.lancamentos)
    df["data"] = pd.to_datetime(df["data"])
    
    df_anterior = df[df["data"] < pd.to_datetime(data_inicio)]
    df_periodo = df[(df["data"] >= pd.to_datetime(data_inicio)) & (df["data"] <= pd.to_datetime(data_fim))]
    
    hierarquia = montar_hierarquia(st.session_state.contas_hierarquicas, set())
    
    resultado = []
    for conta in hierarquia:
        if conta["natureza"] == "Analítica":
            saldo = calcular_saldo_conta(conta["descricao"], df_anterior, df_periodo)
        else:
            saldo = calcular_saldo_sintetico(conta["codigo"], st.session_state.contas_hierarquicas, df_anterior, df_periodo)
        
        resultado.append({
            "codigo": conta["codigo"],
            "descricao": conta["descricao"],
            "tipo": conta["tipo"],
            "natureza": conta["natureza"],
            "nivel": conta["nivel"],
            "saldo_anterior": saldo["saldo_anterior"],
            "debitos": saldo["debitos"],
            "creditos": saldo["creditos"],
            "saldo_final": saldo["saldo_final"]
        })
    
    return resultado

# -------------------------
# Funções de Backup
# -------------------------
def exportar_dados():
    return json.dumps({
        "versao": "5.0",
        "exportado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "contas_hierarquicas": st.session_state.contas_hierarquicas,
        "lancamentos": st.session_state.lancamentos,
        "contas_simples": st.session_state.contas
    }, indent=2, ensure_ascii=False)

def importar_dados(arquivo_json):
    try:
        dados = json.load(arquivo_json)
        
        if "versao" not in dados or dados["versao"] in ["1.0", "2.0", "3.0", "4.0"]:
            # Compatibilidade com versões anteriores
            st.session_state.contas_hierarquicas = dados.get("contas_hierarquicas", dados.get("contas_estruturadas", {}))
            st.session_state.lancamentos = dados.get("lancamentos", [])
            st.session_state.contas = dados.get("contas_simples", [])
            
            # Garantir estrutura mínima
            if not st.session_state.contas:
                st.session_state.contas = [c["descricao"] for c in st.session_state.contas_hierarquicas.values()]
        else:
            st.session_state.contas_hierarquicas = dados.get("contas_hierarquicas", {})
            st.session_state.lancamentos = dados.get("lancamentos", [])
            st.session_state.contas = dados.get("contas_simples", [])
        
        return True, "Dados importados com sucesso!"
    except Exception as e:
        return False, f"Erro ao importar: {str(e)}"

# -------------------------
# Interface Principal
# -------------------------
st.title("🏢 Mini ERP Contábil Completo")
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("💾 Backup")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📤 Exportar", use_container_width=True):
            json_data = exportar_dados()
            st.download_button("⬇️ JSON", json_data, f"erp_{datetime.now().strftime('%Y%m%d')}.json", use_container_width=True)
    
    with col2:
        arquivo = st.file_uploader("📂 Importar", type="json", key="backup_import")
        if arquivo:
            ok, msg = importar_dados(arquivo)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
    
    st.markdown("---")
    st.metric("📊 Lançamentos", len(st.session_state.lancamentos))
    st.metric("📘 Contas", len(st.session_state.contas_hierarquicas))

# Tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📘 Plano de Contas", "➕ Lançamentos", "📋 Listagem", 
    "📊 Balanço", "📈 DRE", "💰 Fluxo de Caixa"
])

# -------------------------
# TAB 1: PLANO DE CONTAS HIERÁRQUICO INTERATIVO
# -------------------------
with tab1:
    st.subheader("📘 Plano de Contas - Visualização Hierárquica")
    
    col_form, col_lista = st.columns([1, 2])
    
    with col_form:
        with st.expander("➕ Nova Conta", expanded=True):
            with st.form("form_conta"):
                codigo = st.text_input("Código", placeholder="Ex: 111, 112, 1.01")
                descricao = st.text_input("Descrição")
                
                col_tipo = st.columns(2)
                with col_tipo[0]:
                    tipo = st.selectbox("Tipo", ["Ativo", "Passivo", "Receita", "Despesa"])
                with col_tipo[1]:
                    natureza = st.selectbox("Natureza", ["Analítica", "Sintética"])
                
                submitted = st.form_submit_button("Adicionar Conta", use_container_width=True)
                
                if submitted:
                    valido, msg = validar_codigo(codigo, tipo, st.session_state.contas_hierarquicas)
                    if valido:
                        pai_auto = auto_identificar_pai(codigo)
                        nivel_auto = auto_calcular_nivel(codigo)
                        
                        st.session_state.contas_hierarquicas[codigo] = {
                            "codigo": codigo,
                            "descricao": descricao,
                            "tipo": tipo,
                            "natureza": natureza,
                            "pai": pai_auto,
                            "nivel": nivel_auto
                        }
                        
                        if descricao not in st.session_state.contas:
                            st.session_state.contas.append(descricao)
                        
                        st.success(f"Conta {codigo} - {descricao} adicionada!")
                        st.rerun()
                    else:
                        st.error(msg)
    
    with col_lista:
        if st.session_state.contas_hierarquicas:
            # Botões de expandir/recolher
            col_exp, col_col = st.columns(2)
            with col_exp:
                if st.button("📂 Expandir Tudo", use_container_width=True):
                    st.session_state.expanded_nodes = set(st.session_state.contas_hierarquicas.keys())
                    st.rerun()
            with col_col:
                if st.button("📁 Recolher Tudo", use_container_width=True):
                    st.session_state.expanded_nodes = set()
                    st.rerun()
            
            st.markdown("---")
            
            hierarquia = montar_hierarquia(st.session_state.contas_hierarquicas, st.session_state.expanded_nodes)
            
            dados_tabela = []
            for conta in hierarquia:
                indent = "  " * (conta["nivel"] - 1)
                prefixo = "📂 " if conta["natureza"] == "Sintética" else "📄 "
                
                col1, col2, col3, col4 = st.columns([1, 3, 1.5, 1])
                
                with col1:
                    st.write(conta["codigo"])
                with col2:
                    if st.button(f"{prefixo}{indent}{conta['descricao']}", key=f"btn_{conta['codigo']}", use_container_width=True):
                        if conta["codigo"] in st.session_state.expanded_nodes:
                            st.session_state.expanded_nodes.discard(conta["codigo"])
                        else:
                            st.session_state.expanded_nodes.add(conta["codigo"])
                        st.rerun()
                with col3:
                    st.write(conta["tipo"])
                with col4:
                    st.write(conta["natureza"])
            
            st.markdown("---")
            st.subheader("🗑️ Remover Conta")
            
            contas_opcoes = [f"{c['codigo']} - {c['descricao']}" for c in hierarquia]
            conta_remover = st.selectbox("Selecione", contas_opcoes)
            
            if st.button("Remover Conta", type="secondary", use_container_width=True):
                codigo = conta_remover.split(" - ")[0]
                pode, msg = pode_excluir_conta(codigo, st.session_state.contas_hierarquicas, st.session_state.lancamentos)
                if pode:
                    desc = st.session_state.contas_hierarquicas[codigo]["descricao"]
                    del st.session_state.contas_hierarquicas[codigo]
                    if desc in st.session_state.contas:
                        st.session_state.contas.remove(desc)
                    st.success("Conta removida!")
                    st.rerun()
                else:
                    st.error(msg)

# -------------------------
# TAB 2: LANÇAMENTOS COM RECORRÊNCIA E SUGESTÃO
# -------------------------
with tab2:
    st.subheader("➕ Novo Lançamento")
    
    contas_analiticas = [c["descricao"] for c in st.session_state.contas_hierarquicas.values() if c["natureza"] == "Analítica"]
    
    if not contas_analiticas:
        st.warning("⚠️ Nenhuma conta analítica cadastrada!")
    else:
        with st.form("form_lancamento", clear_on_submit=True):
            data = st.date_input("Data", datetime.today())
            tipo_lanc = st.selectbox("Tipo de Lançamento", ["Partida Dobrada", "Débito Simples", "Crédito Simples"])
            
            historico = st.text_input("Histórico", placeholder="Descrição...")
            
            # Sugestão automática
            if historico and len(historico) > 3:
                sugestao = sugerir_conta(historico, st.session_state.lancamentos)
                if sugestao:
                    st.info(f"💡 Sugestão: {sugestao}")
            
            if tipo_lanc == "Partida Dobrada":
                col1, col2 = st.columns(2)
                with col1:
                    conta_debito = st.selectbox("Conta Débito", contas_analiticas)
                with col2:
                    conta_credito = st.selectbox("Conta Crédito", contas_analiticas)
            elif tipo_lanc == "Débito Simples":
                conta_debito = st.selectbox("Conta Débito", contas_analiticas)
                conta_credito = None
            else:
                conta_debito = None
                conta_credito = st.selectbox("Conta Crédito", contas_analiticas)
            
            valor = st.number_input("Valor (R$)", min_value=0.01, step=0.01, format="%.2f")
            
            st.markdown("---")
            st.subheader("🔄 Recorrência")
            
            recorrente = st.checkbox("Lançamento Recorrente")
            qtd_recorrencia = 1
            periodicidade = "Mensal"
            
            if recorrente:
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    qtd_recorrencia = st.number_input("Quantidade", min_value=2, max_value=365, value=3)
                with col_r2:
                    periodicidade = st.selectbox("Periodicidade", ["Diário", "Semanal", "Mensal"])
            
            submitted = st.form_submit_button("Registrar Lançamento", use_container_width=True)
            
            if submitted:
                ok, msg = adicionar_lancamento(data, tipo_lanc, conta_debito, conta_credito, valor, historico, recorrente, qtd_recorrencia, periodicidade)
                if ok:
                    st.success(msg)
                    st.balloons()
                    st.rerun()
                else:
                    st.error(msg)

# -------------------------
# TAB 3: LISTAGEM DE LANÇAMENTOS
# -------------------------
with tab3:
    st.subheader("📋 Listagem de Lançamentos")
    
    if st.session_state.lancamentos:
        df = pd.DataFrame(st.session_state.lancamentos)
        df["data"] = pd.to_datetime(df["data"])
        
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            data_ini = st.date_input("Data Inicial", value=None, key="list_ini")
        with col_f2:
            data_fim = st.date_input("Data Final", value=None, key="list_fim")
        with col_f3:
            contas_filtro = ["Todas"] + st.session_state.contas
            conta_filtro = st.selectbox("Conta", contas_filtro)
        
        if data_ini:
            df = df[df["data"] >= pd.to_datetime(data_ini)]
        if data_fim:
            df = df[df["data"] <= pd.to_datetime(data_fim)]
        
        if conta_filtro != "Todas":
            df = df[(df["conta_debito"] == conta_filtro) | (df["conta_credito"] == conta_filtro)]
        
        df = df.sort_values("data", ascending=False)
        
        st.metric("💰 Total", f"R$ {df['valor'].sum():,.2f}")
        
        for idx, row in df.iterrows():
            with st.container():
                cols = st.columns([1, 1.5, 2, 2, 1.5, 0.5])
                
                with cols[0]:
                    st.write(row["data"].strftime("%d/%m/%Y"))
                with cols[1]:
                    st.write(row["tipo"])
                with cols[2]:
                    if row["conta_debito"]:
                        codigo = next((c["codigo"] for c in st.session_state.contas_hierarquicas.values() 
                                     if c["descricao"] == row["conta_debito"]), "")
                        st.write(f"{codigo} - {row['conta_debito']}" if codigo else row["conta_debito"])
                    else:
                        st.write("-")
                with cols[3]:
                    if row["conta_credito"]:
                        codigo = next((c["codigo"] for c in st.session_state.contas_hierarquicas.values() 
                                     if c["descricao"] == row["conta_credito"]), "")
                        st.write(f"{codigo} - {row['conta_credito']}" if codigo else row["conta_credito"])
                    else:
                        st.write("-")
                with cols[4]:
                    st.write(f"R$ {row['valor']:,.2f}")
                with cols[5]:
                    if st.button("🗑️", key=f"del_{idx}"):
                        excluir_lancamento(idx)
                        st.rerun()
                st.divider()
    else:
        st.info("Nenhum lançamento registrado")

# -------------------------
# TAB 4: DEMONSTRATIVO DE SALDOS
# -------------------------
with tab4:
    st.subheader("📊 Balanço Patrimonial")
    
    hoje = datetime.now()
    data_ini_default = datetime(hoje.year, hoje.month, 1)
    data_fim_default = datetime(hoje.year, hoje.month + 1, 1) - timedelta(days=1) if hoje.month < 12 else datetime(hoje.year, 12, 31)
    
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        data_inicio = st.date_input("Data Inicial", data_ini_default, key="balanco_ini")
    with col_p2:
        data_fim = st.date_input("Data Final", data_fim_default, key="balanco_fim")
    
    if st.button("📊 Gerar Balanço", use_container_width=True):
        with st.spinner("Calculando..."):
            resultado = calcular_demonstrativo_saldos(data_inicio, data_fim)
            
            if resultado:
                dados_tabela = []
                for item in resultado:
                    indent = "  " * (item["nivel"] - 1)
                    
                    saldo_anterior = item["saldo_anterior"]
                    saldo_final = item["saldo_final"]
                    
                    saldo_anterior_str = f"R$ {saldo_anterior:,.2f}"
                    saldo_final_str = f"<span style='color:red'>R$ {abs(saldo_final):,.2f}</span>" if saldo_final < 0 else f"R$ {saldo_final:,.2f}"
                    
                    dados_tabela.append({
                        "Código": item["codigo"],
                        "Conta": f"{indent}{item['descricao']}",
                        "Tipo": item["tipo"],
                        "Saldo Anterior": saldo_anterior_str,
                        "Débitos": f"R$ {item['debitos']:,.2f}",
                        "Créditos": f"R$ {item['creditos']:,.2f}",
                        "Saldo Final": saldo_final_str
                    })
                
                df_balanco = pd.DataFrame(dados_tabela)
                st.dataframe(df_balanco, use_container_width=True, hide_index=True)
                
                # Totais
                st.markdown("---")
                st.subheader("📈 Totais Gerais")
                
                total_debitos = sum(r["debitos"] for r in resultado)
                total_creditos = sum(r["creditos"] for r in resultado)
                diff = total_debitos - total_creditos
                
                col_t1, col_t2, col_t3 = st.columns(3)
                with col_t1:
                    st.metric("Total Débitos", f"R$ {total_debitos:,.2f}")
                with col_t2:
                    st.metric("Total Créditos", f"R$ {total_creditos:,.2f}")
                with col_t3:
                    st.metric("Diferença", f"R$ {diff:,.2f}", delta_color="inverse" if diff != 0 else "off")
                
                if abs(diff) < 0.01:
                    st.success("✅ Sistema em equilíbrio contábil!")
                else:
                    st.warning("⚠️ Diferença detectada!")
            else:
                st.info("Nenhum dado no período")

# -------------------------
# TAB 5: DRE AUTOMÁTICA
# -------------------------
with tab5:
    st.subheader("📈 DRE - Demonstrativo de Resultado")
    
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        dre_data_ini = st.date_input("Data Inicial", datetime(datetime.now().year, datetime.now().month, 1), key="dre_ini")
    with col_p2:
        dre_data_fim = st.date_input("Data Final", datetime.now(), key="dre_fim")
    
    if st.button("📊 Calcular DRE", use_container_width=True):
        with st.spinner("Calculando..."):
            df_detalhe, receitas, despesas = calcular_dre(dre_data_ini, dre_data_fim)
            resultado = receitas - despesas
            
            st.markdown("### 📊 Resultado do Período")
            
            col_r1, col_r2, col_r3 = st.columns(3)
            with col_r1:
                st.metric("💰 Receitas Totais", f"R$ {receitas:,.2f}")
            with col_r2:
                st.metric("📉 Despesas Totais", f"R$ {despesas:,.2f}")
            with col_r3:
                cor = "normal" if resultado >= 0 else "inverse"
                st.metric("📈 Resultado Líquido", f"R$ {resultado:,.2f}", delta_color=cor)
            
            st.markdown("---")
            st.subheader("Detalhamento por Conta")
            
            if not df_detalhe.empty:
                st.dataframe(df_detalhe, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum movimento no período")
            
            # Gráfico comparativo
            if receitas > 0 or despesas > 0:
                fig = go.Figure(data=[
                    go.Bar(name="Receitas", x=["Valores"], y=[receitas], marker_color="green"),
                    go.Bar(name="Despesas", x=["Valores"], y=[despesas], marker_color="red")
                ])
                fig.update_layout(title="Receitas vs Despesas", barmode='group')
                st.plotly_chart(fig, use_container_width=True)

# -------------------------
# TAB 6: FLUXO DE CAIXA
# -------------------------
with tab6:
    st.subheader("💰 Fluxo de Caixa")
    
    hoje = datetime.now()
    fluxo_data_ini = st.date_input("Data Inicial", datetime(hoje.year, hoje.month, 1), key="fluxo_ini")
    fluxo_data_fim = st.date_input("Data Final", datetime(hoje.year, hoje.month + 1, 1) - timedelta(days=1) if hoje.month < 12 else datetime(hoje.year, 12, 31), key="fluxo_fim")
    
    if st.button("📊 Calcular Fluxo", use_container_width=True):
        with st.spinner("Calculando fluxo de caixa..."):
            df_fluxo = calcular_fluxo_caixa(fluxo_data_ini, fluxo_data_fim)
            
            if not df_fluxo.empty:
                st.markdown("### 📊 Resumo do Período")
                
                total_entradas = df_fluxo["Entradas"].sum()
                total_saidas = df_fluxo["Saídas"].sum()
                saldo_final = df_fluxo["Saldo Acumulado"].iloc[-1] if not df_fluxo.empty else 0
                
                col_f1, col_f2, col_f3 = st.columns(3)
                with col_f1:
                    st.metric("💰 Total Entradas", f"R$ {total_entradas:,.2f}")
                with col_f2:
                    st.metric("💸 Total Saídas", f"R$ {total_saidas:,.2f}")
                with col_f3:
                    st.metric("📊 Saldo Final", f"R$ {saldo_final:,.2f}", delta_color="normal" if saldo_final >= 0 else "inverse")
                
                st.markdown("---")
                st.subheader("📈 Evolução do Saldo")
                
                fig = px.line(df_fluxo, x="Data", y="Saldo Acumulado", title="Saldo Acumulado Diário")
                fig.update_layout(xaxis_title="Data", yaxis_title="Saldo (R$)")
                st.plotly_chart(fig, use_container_width=True)
                
                st.subheader("📋 Fluxo Detalhado")
                df_fluxo_display = df_fluxo.copy()
                for col in ["Entradas", "Saídas", "Saldo Dia", "Saldo Acumulado"]:
                    df_fluxo_display[col] = df_fluxo_display[col].apply(lambda x: f"R$ {x:,.2f}")
                df_fluxo_display["Data"] = df_fluxo_display["Data"].dt.strftime("%d/%m/%Y")
                st.dataframe(df_fluxo_display, use_container_width=True, hide_index=True)
                
                # Gráfico comparativo mensal
                st.markdown("---")
                st.subheader("📊 Comparativo Mensal")
                
                df_mensal = calcular_comparativo_mensal()
                if not df_mensal.empty:
                    fig2 = go.Figure()
                    fig2.add_trace(go.Bar(name="Receitas", x=df_mensal["Mês"], y=df_mensal["Receitas"], marker_color="green"))
                    fig2.add_trace(go.Bar(name="Despesas", x=df_mensal["Mês"], y=df_mensal["Despesas"], marker_color="red"))
                    fig2.add_trace(go.Scatter(name="Resultado", x=df_mensal["Mês"], y=df_mensal["Resultado"], mode="lines+markers", line=dict(color="blue", width=2)))
                    fig2.update_layout(title="Evolução Mensal", barmode='group')
                    st.plotly_chart(fig2, use_container_width=True)
                    
                    st.dataframe(df_mensal, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum movimento no período")

# -------------------------
# Rodapé
# -------------------------
st.markdown("---")
st.caption(f"🏢 Mini ERP Contábil v5.0 | {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")