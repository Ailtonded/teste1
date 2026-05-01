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
    
    if "grid_lancamentos" not in st.session_state:
        st.session_state.grid_lancamentos = [
            {"conta": "", "tipo": "Débito", "valor": 0.0, "historico": ""}
        ]

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
# Funções do Grid de Lançamentos
# -------------------------
def adicionar_linha_grid():
    """Adiciona nova linha vazia ao grid"""
    st.session_state.grid_lancamentos.append(
        {"conta": "", "tipo": "Débito", "valor": 0.0, "historico": ""}
    )

def remover_linha_grid(index):
    """Remove uma linha do grid"""
    if len(st.session_state.grid_lancamentos) > 1:
        st.session_state.grid_lancamentos.pop(index)
    else:
        st.warning("Mantenha pelo menos uma linha!")

def validar_grid_e_salvar(data, grid_lancamentos):
    """Valida o grid e salva os lançamentos"""
    
    # Calcular totais
    total_debito = 0
    total_credito = 0
    
    for linha in grid_lancamentos:
        valor = linha["valor"] if linha["valor"] else 0
        if linha["tipo"] == "Débito":
            total_debito += valor
        else:
            total_credito += valor
    
    # Verificar se totais são iguais
    if abs(total_debito - total_credito) > 0.01:
        return False, f"Totais não conferem! Débito: R$ {total_debito:,.2f} | Crédito: R$ {total_credito:,.2f} | Diferença: R$ {abs(total_debito - total_credito):,.2f}"
    
    # Verificar se há alguma linha com valor
    if total_debito == 0 and total_credito == 0:
        return False, "Nenhum valor informado!"
    
    # Verificar contas analíticas
    contas_analiticas = [c["descricao"] for c in st.session_state.contas_hierarquicas.values() 
                        if c["natureza"] == "Analítica"]
    
    for i, linha in enumerate(grid_lancamentos):
        if linha["valor"] > 0:  # Só valida linhas com valor
            if not linha["conta"]:
                return False, f"Linha {i+1}: Conta é obrigatória!"
            
            if linha["conta"] not in contas_analiticas:
                return False, f"Linha {i+1}: Conta '{linha['conta']}' não é analítica ou não existe!"
            
            if linha["valor"] <= 0:
                return False, f"Linha {i+1}: Valor deve ser maior que zero!"
    
    # Converter grid para lançamentos no formato atual
    linhas_debito = [l for l in grid_lancamentos if l["tipo"] == "Débito" and l["valor"] > 0]
    linhas_credito = [l for l in grid_lancamentos if l["tipo"] == "Crédito" and l["valor"] > 0]
    
    novos_lancamentos = []
    
    # Se há apenas um débito e um crédito, cria um lançamento de partida dobrada
    if len(linhas_debito) == 1 and len(linhas_credito) == 1:
        novo_lanc = {
            "data": data.strftime("%Y-%m-%d"),
            "tipo": "Partida Dobrada",
            "conta_debito": linhas_debito[0]["conta"],
            "conta_credito": linhas_credito[0]["conta"],
            "valor": linhas_debito[0]["valor"],
            "historico": linhas_debito[0]["historico"] or linhas_credito[0]["historico"] or "Lançamento via grid",
            "data_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        novos_lancamentos.append(novo_lanc)
    else:
        # Múltiplas linhas: criar lançamentos individuais com contrapartida temporária
        contrapartida = "Contrapartida Temporária"
        
        # Verificar se conta de contrapartida existe e é analítica
        contas_analiticas = [c["descricao"] for c in st.session_state.contas_hierarquicas.values() 
                            if c["natureza"] == "Analítica"]
        
        if contrapartida not in contas_analiticas:
            # Criar conta de contrapartida se não existir
            novo_codigo = "9999"
            if novo_codigo not in st.session_state.contas_hierarquicas:
                st.session_state.contas_hierarquicas[novo_codigo] = {
                    "codigo": novo_codigo,
                    "descricao": contrapartida,
                    "tipo": "Ativo",
                    "natureza": "Analítica",
                    "pai": None,
                    "nivel": 1
                }
                st.session_state.contas.append(contrapartida)
        
        historico_combined = " | ".join([l["historico"] for l in grid_lancamentos if l["historico"]]) or "Lançamento múltiplo via grid"
        
        for linha in linhas_debito:
            novo_lanc = {
                "data": data.strftime("%Y-%m-%d"),
                "tipo": "Partida Dobrada",
                "conta_debito": linha["conta"],
                "conta_credito": contrapartida,
                "valor": linha["valor"],
                "historico": linha["historico"] or historico_combined,
                "data_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            novos_lancamentos.append(novo_lanc)
        
        for linha in linhas_credito:
            novo_lanc = {
                "data": data.strftime("%Y-%m-%d"),
                "tipo": "Partida Dobrada",
                "conta_debito": contrapartida,
                "conta_credito": linha["conta"],
                "valor": linha["valor"],
                "historico": linha["historico"] or historico_combined,
                "data_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            novos_lancamentos.append(novo_lanc)
    
    st.session_state.lancamentos.extend(novos_lancamentos)
    return True, f"{len(novos_lancamentos)} lançamento(s) registrado(s) com sucesso! Totais: Débito R$ {total_debito:,.2f} = Crédito R$ {total_credito:,.2f}"

def limpar_grid():
    """Limpa o grid mantendo uma linha padrão"""
    st.session_state.grid_lancamentos = [
        {"conta": "", "tipo": "Débito", "valor": 0.0, "historico": ""}
    ]

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
    
    else:
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
    if not lancamentos or not historico:
        return None
    
    palavras = historico.lower().split()
    contas_usadas = {}
    
    for lanc in lancamentos:
        if lanc["historico"]:
            for palavra in palavras:
                if palavra in lanc["historico"].lower():
                    if lanc.get("conta_debito"):
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
            st.session_state.contas_hierarquicas = dados.get("contas_hierarquicas", dados.get("contas_estruturadas", {}))
            st.session_state.lancamentos = dados.get("lancamentos", [])
            st.session_state.contas = dados.get("contas_simples", [])
            
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
            
            # Display hierarchical accounts
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
# TAB 2: GRID CONTÁBIL MULTI-LINHAS
# -------------------------
with tab2:
    st.subheader("➕ Lançamentos - Grid Contábil Multi-Linhas")
    
    contas_analiticas = [c["descricao"] for c in st.session_state.contas_hierarquicas.values() if c["natureza"] == "Analítica"]
    
    if not contas_analiticas:
        st.warning("⚠️ Nenhuma conta analítica cadastrada!")
    else:
        with st.form("form_grid_lancamentos"):
            st.markdown("### 📋 Grid de Lançamentos")
            
            data = st.date_input("Data do Lançamento", datetime.today())
            
            # Exibir grid editável
            col1, col2, col3, col4, col5 = st.columns([3, 1.5, 2, 3, 0.5])
            with col1:
                st.markdown("**Conta**")
            with col2:
                st.markdown("**Tipo**")
            with col3:
                st.markdown("**Valor (R$)**")
            with col4:
                st.markdown("**Histórico**")
            with col5:
                st.markdown("**Ações**")
            
            # Lista para armazenar linhas para remover
            linhas_para_remover = []
            
            for i, linha in enumerate(st.session_state.grid_lancamentos):
                cols = st.columns([3, 1.5, 2, 3, 0.5])
                
                with cols[0]:
                    conta = st.selectbox(
                        "Conta",
                        [""] + contas_analiticas,
                        index=([""] + contas_analiticas).index(linha["conta"]) if linha["conta"] in contas_analiticas else 0,
                        key=f"conta_{i}",
                        label_visibility="collapsed"
                    )
                
                with cols[1]:
                    tipo = st.selectbox(
                        "Tipo",
                        ["Débito", "Crédito"],
                        index=0 if linha["tipo"] == "Débito" else 1,
                        key=f"tipo_{i}",
                        label_visibility="collapsed"
                    )
                
                with cols[2]:
                    valor = st.number_input(
                        "Valor",
                        min_value=0.0,
                        step=0.01,
                        format="%.2f",
                        value=float(linha["valor"]),
                        key=f"valor_{i}",
                        label_visibility="collapsed"
                    )
                
                with cols[3]:
                    historico = st.text_input(
                        "Histórico",
                        value=linha["historico"],
                        key=f"historico_{i}",
                        label_visibility="collapsed",
                        placeholder="Descrição opcional"
                    )
                
                with cols[4]:
                    if st.button("❌", key=f"remove_{i}"):
                        linhas_para_remover.append(i)
                
                # Atualizar valores
                st.session_state.grid_lancamentos[i]["conta"] = conta
                st.session_state.grid_lancamentos[i]["tipo"] = tipo
                st.session_state.grid_lancamentos[i]["valor"] = valor
                st.session_state.grid_lancamentos[i]["historico"] = historico
            
            # Remover linhas marcadas
            for idx in sorted(linhas_para_remover, reverse=True):
                if len(st.session_state.grid_lancamentos) > 1:
                    st.session_state.grid_lancamentos.pop(idx)
            
            # Botões de ação
            col_add, col_clear = st.columns(2)
            with col_add:
                if st.button("➕ Adicionar Linha", use_container_width=True):
                    adicionar_linha_grid()
                    st.rerun()
            
            with col_clear:
                if st.button("🗑️ Limpar Tudo", type="secondary", use_container_width=True):
                    limpar_grid()
                    st.rerun()
            
            st.markdown("---")
            
            # Calcular totais
            total_debito = sum(l["valor"] for l in st.session_state.grid_lancamentos if l["tipo"] == "Débito")
            total_credito = sum(l["valor"] for l in st.session_state.grid_lancamentos if l["tipo"] == "Crédito")
            
            # Exibir totais com cores
            col_tot1, col_tot2, col_tot3 = st.columns([2, 2, 3])
            
            with col_tot1:
                debito_color = "green" if total_debito > 0 else "gray"
                st.markdown(f"### 💰 **Total Débito:** <span style='color:{debito_color}'>R$ {total_debito:,.2f}</span>", unsafe_allow_html=True)
            
            with col_tot2:
                credito_color = "red" if total_credito > 0 else "gray"
                st.markdown(f"### 💸 **Total Crédito:** <span style='color:{credito_color}'>R$ {total_credito:,.2f}</span>", unsafe_allow_html=True)
            
            with col_tot3:
                diferenca = total_debito - total_credito
                if abs(diferenca) < 0.01:
                    st.markdown("### ✅ **Status:** <span style='color:green'>EQUILIBRADO (D = C)</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"### ⚠️ **Diferença:** <span style='color:red'>R$ {abs(diferenca):,.2f}</span>", unsafe_allow_html=True)
                    st.markdown("### ❌ **Status:** <span style='color:red'>DESEQUILIBRADO</span>", unsafe_allow_html=True)
            
            st.markdown("---")
            
            submitted = st.form_submit_button("✅ Registrar Lançamentos", use_container_width=True, type="primary")
            
            if submitted:
                if abs(total_debito - total_credito) > 0.01:
                    st.error(f"❌ Total de Débitos (R$ {total_debito:,.2f}) e Créditos (R$ {total_credito:,.2f}) não conferem! Diferença: R$ {abs(total_debito - total_credito):,.2f}")
                elif total_debito == 0 and total_credito == 0:
                    st.error("❌ Nenhum valor informado! Adicione pelo menos uma linha com valor maior que zero.")
                else:
                    ok, msg = validar_grid_e_salvar(data, st.session_state.grid_lancamentos)
                    if ok:
                        st.success(msg)
                        st.balloons()
                        limpar_grid()
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

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
            conta_filtro = st.selectbox("Conta", contas_filtro, key="filtro_conta_list")
        
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
                    if st.button("🗑️", key=f"del_{idx}_{datetime.now().timestamp()}"):
                        excluir_lancamento(idx)
                        st.rerun()
                st.divider()
    else:
        st.info("Nenhum lançamento registrado")

# -------------------------
# TAB 4: DEMONSTRATIVO DE SALDOS (BALANÇO)
# -------------------------
with tab4:
    st.subheader("📊 Balanço Patrimonial - Demonstrativo de Saldos")
    
    st.info("O Balanço Patrimonial mostra a posição financeira da empresa em uma data específica, incluindo Ativos, Passivos e Patrimônio Líquido.")
    
    hoje = datetime.now()
    data_ini_default = datetime(hoje.year, hoje.month, 1)
    data_fim_default = datetime(hoje.year, hoje.month + 1, 1) - timedelta(days=1) if hoje.month < 12 else datetime(hoje.year, 12, 31)
    
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        data_inicio = st.date_input("Data Inicial (Saldo Anterior)", data_ini_default, key="balanco_ini")
    with col_p2:
        data_fim = st.date_input("Data Final (Período)", data_fim_default, key="balanco_fim")
    
    if st.button("📊 Gerar Balanço Patrimonial", use_container_width=True):
        with st.spinner("Calculando saldos..."):
            resultado = calcular_demonstrativo_saldos(data_inicio, data_fim)
            
            if resultado:
                # Separar Ativos, Passivos e outras contas
                ativos = [item for item in resultado if item["tipo"] == "Ativo"]
                passivos = [item for item in resultado if item["tipo"] == "Passivo"]
                outras = [item for item in resultado if item["tipo"] not in ["Ativo", "Passivo"]]
                
                # Calcular totais
                total_ativo = sum(item["saldo_final"] for item in ativos)
                total_passivo = sum(item["saldo_final"] for item in passivos)
                
                # Exibir resumo
                col_a1, col_a2, col_a3 = st.columns(3)
                with col_a1:
                    st.metric("🏦 Total do Ativo", f"R$ {total_ativo:,.2f}")
                with col_a2:
                    st.metric("💳 Total do Passivo", f"R$ {total_passivo:,.2f}")
                with col_a3:
                    patrimonio = total_ativo - total_passivo
                    st.metric("📊 Patrimônio Líquido", f"R$ {patrimonio:,.2f}", 
                             delta_color="normal" if patrimonio >= 0 else "inverse")
                
                st.markdown("---")
                
                # Mostrar Ativos
                st.subheader("🏦 ATIVO")
                dados_ativos = []
                for item in ativos:
                    indent = "  " * (item["nivel"] - 1)
                    saldo_final_str = f"R$ {item['saldo_final']:,.2f}"
                    dados_ativos.append({
                        "Código": item["codigo"],
                        "Conta": f"{indent}{item['descricao']}",
                        "Saldo Anterior": f"R$ {item['saldo_anterior']:,.2f}",
                        "Débitos": f"R$ {item['debitos']:,.2f}",
                        "Créditos": f"R$ {item['creditos']:,.2f}",
                        "Saldo Final": saldo_final_str
                    })
                
                if dados_ativos:
                    st.dataframe(pd.DataFrame(dados_ativos), use_container_width=True, hide_index=True)
                else:
                    st.info("Nenhuma conta de Ativo cadastrada")
                
                st.markdown("---")
                
                # Mostrar Passivos
                st.subheader("💳 PASSIVO")
                dados_passivos = []
                for item in passivos:
                    indent = "  " * (item["nivel"] - 1)
                    saldo_final_str = f"R$ {item['saldo_final']:,.2f}"
                    dados_passivos.append({
                        "Código": item["codigo"],
                        "Conta": f"{indent}{item['descricao']}",
                        "Saldo Anterior": f"R$ {item['saldo_anterior']:,.2f}",
                        "Débitos": f"R$ {item['debitos']:,.2f}",
                        "Créditos": f"R$ {item['creditos']:,.2f}",
                        "Saldo Final": saldo_final_str
                    })
                
                if dados_passivos:
                    st.dataframe(pd.DataFrame(dados_passivos), use_container_width=True, hide_index=True)
                else:
                    st.info("Nenhuma conta de Passivo cadastrada")
                
                st.markdown("---")
                st.subheader("📈 Verificação Contábil")
                
                total_debitos = sum(r["debitos"] for r in resultado)
                total_creditos = sum(r["creditos"] for r in resultado)
                diff = total_debitos - total_creditos
                
                col_t1, col_t2, col_t3 = st.columns(3)
                with col_t1:
                    st.metric("Total Débitos no Período", f"R$ {total_debitos:,.2f}")
                with col_t2:
                    st.metric("Total Créditos no Período", f"R$ {total_creditos:,.2f}")
                with col_t3:
                    st.metric("Diferença", f"R$ {diff:,.2f}", delta_color="inverse" if abs(diff) > 0.01 else "off")
                
                if abs(diff) < 0.01:
                    st.success("✅ Sistema em equilíbrio contábil! Débitos = Créditos")
                else:
                    st.warning("⚠️ Diferença detectada! Verifique os lançamentos.")
            else:
                st.info("Nenhum dado no período")

# -------------------------
# TAB 5: DRE AUTOMÁTICA
# -------------------------
with tab5:
    st.subheader("📈 DRE - Demonstrativo de Resultado do Exercício")
    
    st.info("A DRE (Demonstração do Resultado do Exercício) mostra o desempenho financeiro da empresa em um período, calculando Receitas, Despesas e o Resultado Líquido.")
    
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        dre_data_ini = st.date_input("Data Inicial", datetime(datetime.now().year, datetime.now().month, 1), key="dre_ini")
    with col_p2:
        dre_data_fim = st.date_input("Data Final", datetime.now(), key="dre_fim")
    
    if st.button("📊 Calcular DRE", use_container_width=True):
        with st.spinner("Calculando DRE..."):
            df_detalhe, receitas, despesas = calcular_dre(dre_data_ini, dre_data_fim)
            resultado = receitas - despesas
            
            st.markdown("### 📊 Resultado do Período")
            st.caption(f"Período: {dre_data_ini.strftime('%d/%m/%Y')} a {dre_data_fim.strftime('%d/%m/%Y')}")
            
            col_r1, col_r2, col_r3 = st.columns(3)
            with col_r1:
                st.metric("💰 Receitas Totais", f"R$ {receitas:,.2f}", delta=f"R$ {receitas:,.2f}")
            with col_r2:
                st.metric("📉 Despesas Totais", f"R$ {despesas:,.2f}", delta=f"-R$ {despesas:,.2f}")
            with col_r3:
                cor = "normal" if resultado >= 0 else "inverse"
                delta_texto = f"R$ {abs(resultado):,.2f}"
                st.metric("📈 Resultado Líquido", f"R$ {resultado:,.2f}", 
                         delta=delta_texto, delta_color=cor)
            
            st.markdown("---")
            st.subheader("Detalhamento por Conta Analítica")
            
            if not df_detalhe.empty:
                # Separar receitas e despesas
                df_receitas = df_detalhe[df_detalhe["Tipo"] == "Receita"].sort_values("Valor", ascending=False)
                df_despesas = df_detalhe[df_detalhe["Tipo"] == "Despesa"].sort_values("Valor", ascending=False)
                
                col_rec, col_desp = st.columns(2)
                with col_rec:
                    st.markdown("#### 🟢 Receitas")
                    if not df_receitas.empty:
                        st.dataframe(df_receitas, use_container_width=True, hide_index=True)
                    else:
                        st.info("Nenhuma receita no período")
                
                with col_desp:
                    st.markdown("#### 🔴 Despesas")
                    if not df_despesas.empty:
                        st.dataframe(df_despesas, use_container_width=True, hide_index=True)
                    else:
                        st.info("Nenhuma despesa no período")
            else:
                st.info("Nenhum movimento no período")
            
            if receitas > 0 or despesas > 0:
                st.markdown("---")
                st.subheader("📊 Gráfico Comparativo")
                
                fig = go.Figure(data=[
                    go.Bar(name="Receitas", x=["Valores"], y=[receitas], marker_color="green", text=[f"R$ {receitas:,.2f}"], textposition='auto'),
                    go.Bar(name="Despesas", x=["Valores"], y=[despesas], marker_color="red", text=[f"R$ {despesas:,.2f}"], textposition='auto')
                ])
                fig.update_layout(title="Receitas vs Despesas", barmode='group', yaxis_title="Valor (R$)")
                st.plotly_chart(fig, use_container_width=True)
                
                # Gráfico de pizza
                if resultado != 0:
                    fig_pie = go.Figure(data=[go.Pie(
                        labels=['Receitas', 'Despesas', 'Resultado Líquido'],
                        values=[max(0, receitas), max(0, despesas), abs(resultado)],
                        marker_colors=['green', 'red', 'blue'],
                        hole=.3
                    )])
                    fig_pie.update_layout(title="Composição dos Resultados")
                    st.plotly_chart(fig_pie, use_container_width=True)

# -------------------------
# TAB 6: FLUXO DE CAIXA
# -------------------------
with tab6:
    st.subheader("💰 Fluxo de Caixa")
    
    st.info("O Fluxo de Caixa demonstra todas as entradas e saídas de recursos financeiros no período, permitindo analisar a liquidez da empresa.")
    
    hoje = datetime.now()
    # Calcular último dia do mês
    if hoje.month < 12:
        ultimo_dia = datetime(hoje.year, hoje.month + 1, 1) - timedelta(days=1)
    else:
        ultimo_dia = datetime(hoje.year, 12, 31)
    
    fluxo_data_ini = st.date_input("Data Inicial", datetime(hoje.year, hoje.month, 1), key="fluxo_ini")
    fluxo_data_fim = st.date_input("Data Final", ultimo_dia, key="fluxo_fim")
    
    if st.button("📊 Calcular Fluxo de Caixa", use_container_width=True):
        with st.spinner("Calculando fluxo de caixa..."):
            df_fluxo = calcular_fluxo_caixa(fluxo_data_ini, fluxo_data_fim)
            
            if not df_fluxo.empty:
                st.markdown("### 📊 Resumo do Período")
                
                total_entradas = df_fluxo["Entradas"].sum()
                total_saidas = df_fluxo["Saídas"].sum()
                saldo_inicial = df_fluxo["Saldo Acumulado"].iloc[0] - df_fluxo["Saldo Dia"].iloc[0] if len(df_fluxo) > 0 else 0
                saldo_final = df_fluxo["Saldo Acumulado"].iloc[-1] if not df_fluxo.empty else 0
                
                col_f1, col_f2, col_f3, col_f4 = st.columns(4)
                with col_f1:
                    st.metric("💰 Total Entradas", f"R$ {total_entradas:,.2f}")
                with col_f2:
                    st.metric("💸 Total Saídas", f"R$ {total_saidas:,.2f}")
                with col_f3:
                    st.metric("📈 Saldo Inicial", f"R$ {saldo_inicial:,.2f}")
                with col_f4:
                    st.metric("📊 Saldo Final", f"R$ {saldo_final:,.2f}", 
                             delta=f"R$ {saldo_final - saldo_inicial:,.2f}",
                             delta_color="normal" if saldo_final >= saldo_inicial else "inverse")
                
                st.markdown("---")
                st.subheader("📈 Evolução Diária do Saldo")
                
                fig = px.line(df_fluxo, x="Data", y="Saldo Acumulado", 
                             title="Evolução do Saldo Acumulado no Período",
                             markers=True)
                fig.update_layout(xaxis_title="Data", yaxis_title="Saldo (R$)")
                fig.add_hline(y=0, line_dash="dash", line_color="red")
                st.plotly_chart(fig, use_container_width=True)
                
                st.subheader("📊 Entradas vs Saídas por Dia")
                
                fig2 = go.Figure()
                fig2.add_trace(go.Bar(name="Entradas", x=df_fluxo["Data"], y=df_fluxo["Entradas"], marker_color="green"))
                fig2.add_trace(go.Bar(name="Saídas", x=df_fluxo["Data"], y=df_fluxo["Saídas"], marker_color="red"))
                fig2.update_layout(title="Entradas e Saídas Diárias", barmode='group', 
                                  xaxis_title="Data", yaxis_title="Valor (R$)")
                st.plotly_chart(fig2, use_container_width=True)
                
                st.subheader("📋 Fluxo Detalhado")
                df_fluxo_display = df_fluxo.copy()
                for col in ["Entradas", "Saídas", "Saldo Dia", "Saldo Acumulado"]:
                    df_fluxo_display[col] = df_fluxo_display[col].apply(lambda x: f"R$ {x:,.2f}")
                df_fluxo_display["Data"] = df_fluxo_display["Data"].dt.strftime("%d/%m/%Y")
                st.dataframe(df_fluxo_display, use_container_width=True, hide_index=True)
                
                st.markdown("---")
                st.subheader("📊 Comparativo Mensal")
                
                df_mensal = calcular_comparativo_mensal()
                if not df_mensal.empty:
                    # Filtrar apenas meses dentro do período
                    df_mensal_filtrado = df_mensal[
                        (df_mensal["Mês"] >= fluxo_data_ini.strftime("%Y-%m")) & 
                        (df_mensal["Mês"] <= fluxo_data_fim.strftime("%Y-%m"))
                    ]
                    
                    if not df_mensal_filtrado.empty:
                        fig3 = go.Figure()
                        fig3.add_trace(go.Bar(name="Receitas", x=df_mensal_filtrado["Mês"], y=df_mensal_filtrado["Receitas"], 
                                             marker_color="green", text=df_mensal_filtrado["Receitas"].apply(lambda x: f"R$ {x:,.0f}"), 
                                             textposition='auto'))
                        fig3.add_trace(go.Bar(name="Despesas", x=df_mensal_filtrado["Mês"], y=df_mensal_filtrado["Despesas"], 
                                             marker_color="red", text=df_mensal_filtrado["Despesas"].apply(lambda x: f"R$ {x:,.0f}"), 
                                             textposition='auto'))
                        fig3.add_trace(go.Scatter(name="Resultado", x=df_mensal_filtrado["Mês"], y=df_mensal_filtrado["Resultado"], 
                                                mode="lines+markers", line=dict(color="blue", width=3), 
                                                marker=dict(size=10)))
                        fig3.update_layout(title="Evolução Mensal - Receitas, Despesas e Resultado", 
                                          barmode='group', xaxis_title="Mês", yaxis_title="Valor (R$)")
                        st.plotly_chart(fig3, use_container_width=True)
                        
                        # Tabela mensal formatada
                        df_mensal_display = df_mensal_filtrado.copy()
                        for col in ["Receitas", "Despesas", "Resultado"]:
                            df_mensal_display[col] = df_mensal_display[col].apply(lambda x: f"R$ {x:,.2f}")
                        st.dataframe(df_mensal_display, use_container_width=True, hide_index=True)
                    else:
                        st.info("Nenhum dado mensal disponível no período selecionado")
            else:
                st.info("Nenhum movimento financeiro no período selecionado")

# -------------------------
# Rodapé
# -------------------------
st.markdown("---")
st.caption(f"🏢 Mini ERP Contábil v5.1 - Grid Multi-Linhas | © 2024 | {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")