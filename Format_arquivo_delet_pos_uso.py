import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta

st.set_page_config(page_title="Mini ERP Contábil", layout="wide")

# -------------------------
# Inicialização do Estado (PRESERVANDO DADOS EXISTENTES)
# -------------------------
def init_session_state():
    if "lancamentos" not in st.session_state:
        st.session_state.lancamentos = []
    
    if "contas" not in st.session_state:
        st.session_state.contas = ["Caixa", "Banco", "Receita", "Despesa"]
    
    if "contas_hierarquicas" not in st.session_state:
        st.session_state.contas_hierarquicas = {}
        
        # Converter contas antigas para novo formato hierárquico
        mapeamento = {
            "Caixa": {"codigo": "111", "tipo": "Ativo", "descricao": "Caixa", "pai": "11"},
            "Banco": {"codigo": "112", "tipo": "Ativo", "descricao": "Banco", "pai": "11"},
            "Receita": {"codigo": "301", "tipo": "Receita", "descricao": "Receita", "pai": "30"},
            "Despesa": {"codigo": "401", "tipo": "Despesa", "descricao": "Despesa", "pai": "40"}
        }
        
        # Criar estrutura base
        estrutura_base = {
            "1": {"codigo": "1", "descricao": "ATIVO", "tipo": "Ativo", "natureza": "Sintética", "pai": None, "nivel": 1},
            "11": {"codigo": "11", "descricao": "Disponibilidade", "tipo": "Ativo", "natureza": "Sintética", "pai": "1", "nivel": 2},
            "2": {"codigo": "2", "descricao": "PASSIVO", "tipo": "Passivo", "natureza": "Sintética", "pai": None, "nivel": 1},
            "3": {"codigo": "3", "descricao": "RECEITAS", "tipo": "Receita", "natureza": "Sintética", "pai": None, "nivel": 1},
            "30": {"codigo": "30", "descricao": "Receitas Operacionais", "tipo": "Receita", "natureza": "Sintética", "pai": "3", "nivel": 2},
            "4": {"codigo": "4", "descricao": "DESPESAS", "tipo": "Despesa", "natureza": "Sintética", "pai": None, "nivel": 1},
            "40": {"codigo": "40", "descricao": "Despesas Operacionais", "tipo": "Despesa", "natureza": "Sintética", "pai": "4", "nivel": 2},
        }
        
        for codigo, dados in estrutura_base.items():
            st.session_state.contas_hierarquicas[codigo] = dados
        
        for conta in st.session_state.contas:
            if conta in mapeamento:
                info = mapeamento[conta]
                st.session_state.contas_hierarquicas[info["codigo"]] = {
                    "codigo": info["codigo"],
                    "descricao": info["descricao"],
                    "tipo": info["tipo"],
                    "natureza": "Analítica",
                    "pai": info["pai"],
                    "nivel": 3 if info["codigo"].startswith("1") else 3
                }
        
        # Atualizar lista simples de contas
        st.session_state.contas = [c["descricao"] for c in st.session_state.contas_hierarquicas.values()]

init_session_state()

# -------------------------
# Funções de Hierarquia
# -------------------------
def auto_calcular_nivel(codigo):
    """Calcula o nível baseado no código (quantidade de caracteres ou pontos)"""
    if '.' in codigo:
        return len(codigo.split('.'))
    else:
        return len(codigo)

def auto_identificar_pai(codigo):
    """Identifica automaticamente a conta pai baseada no código"""
    if '.' in codigo:
        partes = codigo.split('.')
        if len(partes) > 1:
            pai = '.'.join(partes[:-1])
            return pai
    else:
        if len(codigo) > 1:
            return codigo[:-1] if len(codigo) > 1 else None
    return None

def validar_codigo_hierarquico(codigo, tipo, contas_dict):
    """Valida código hierárquico e regras de tipo"""
    if not codigo:
        return False, "Código é obrigatório!"
    
    if codigo in contas_dict:
        return False, "Código já existe!"
    
    # Validar primeiro dígito baseado no tipo
    primeiro_digito = codigo[0]
    regras = {
        "Ativo": "1",
        "Passivo": "2",
        "Receita": "3",
        "Despesa": "4"
    }
    
    if tipo in regras and primeiro_digito != regras[tipo]:
        return False, f"Conta do tipo {tipo} deve começar com o dígito {regras[tipo]}! Códigos {tipo}: {regras[tipo]}, {regras[tipo]}., {regras[tipo]}.0, etc."
    
    # Validar existência da conta pai
    pai = auto_identificar_pai(codigo)
    if pai and pai not in contas_dict:
        return False, f"Conta pai '{pai}' não existe! Crie a conta hierárquica superior primeiro."
    
    return True, "OK"

def montar_hierarquia(contas_dict):
    """Retorna lista de contas ordenada hierarquicamente"""
    def ordenar_recursivo(pai=None, nivel=0):
        resultado = []
        contas_filhas = [c for c in contas_dict.values() if c.get("pai") == pai]
        contas_filhas.sort(key=lambda x: x["codigo"])
        
        for conta in contas_filhas:
            resultado.append(conta)
            resultado.extend(ordenar_recursivo(conta["codigo"], nivel + 1))
        
        return resultado
    
    return ordenar_recursivo()

def pode_excluir_conta(codigo, contas_dict, lancamentos):
    """Verifica se conta pode ser excluída"""
    if codigo not in contas_dict:
        return False, "Conta não encontrada!"
    
    conta = contas_dict[codigo]
    
    # Verificar se tem contas filhas
    tem_filhos = any(c.get("pai") == codigo for c in contas_dict.values())
    if tem_filhos:
        return False, "Não é possível excluir conta que possui contas filhas!"
    
    # Verificar se tem lançamentos
    tem_lancamento = False
    for lanc in lancamentos:
        if lanc["conta_debito"] == conta["descricao"] or lanc["conta_credito"] == conta["descricao"]:
            tem_lancamento = True
            break
    
    if tem_lancamento:
        return False, "Não é possível excluir conta que possui lançamentos!"
    
    return True, "OK"

# -------------------------
# Funções de Lançamentos (EVOLUÍDAS)
# -------------------------
def adicionar_lancamento(data, tipo_lancamento, conta_debito, conta_credito, valor, historico):
    """Adiciona lançamento contábil com suporte a diferentes tipos"""
    
    if valor <= 0:
        return False, "Valor deve ser maior que zero!"
    
    # Obter contas analíticas
    contas_analiticas = [c["descricao"] for c in st.session_state.contas_hierarquicas.values() 
                        if c["natureza"] == "Analítica"]
    
    if tipo_lancamento == "Débito Simples":
        if conta_debito not in contas_analiticas:
            return False, f"Conta '{conta_debito}' não é analítica ou não existe!"
        
        st.session_state.lancamentos.append({
            "data": data.strftime("%Y-%m-%d"),
            "tipo": "Débito",
            "conta_debito": conta_debito,
            "conta_credito": None,
            "valor": valor,
            "historico": historico,
            "data_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        return True, "Lançamento de débito registrado!"
    
    elif tipo_lancamento == "Crédito Simples":
        if conta_credito not in contas_analiticas:
            return False, f"Conta '{conta_credito}' não é analítica ou não existe!"
        
        st.session_state.lancamentos.append({
            "data": data.strftime("%Y-%m-%d"),
            "tipo": "Crédito",
            "conta_debito": None,
            "conta_credito": conta_credito,
            "valor": valor,
            "historico": historico,
            "data_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        return True, "Lançamento de crédito registrado!"
    
    else:  # Partida Dobrada
        if conta_debito == conta_credito:
            return False, "Conta débito e crédito não podem ser iguais!"
        
        if conta_debito not in contas_analiticas:
            return False, f"Conta débito '{conta_debito}' não é analítica ou não existe!"
        
        if conta_credito not in contas_analiticas:
            return False, f"Conta crédito '{conta_credito}' não é analítica ou não existe!"
        
        st.session_state.lancamentos.append({
            "data": data.strftime("%Y-%m-%d"),
            "tipo": "Partida Dobrada",
            "conta_debito": conta_debito,
            "conta_credito": conta_credito,
            "valor": valor,
            "historico": historico,
            "data_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        return True, "Lançamento de partida dobrada registrado!"

def excluir_lancamento(index):
    if 0 <= index < len(st.session_state.lancamentos):
        st.session_state.lancamentos.pop(index)
        return True
    return False

# -------------------------
# Funções de Cálculo de Saldos
# -------------------------
def calcular_saldo_analitica(conta_descricao, df_anterior, df_periodo):
    """Calcula saldo para conta analítica"""
    deb_anterior = df_anterior[df_anterior["conta_debito"] == conta_descricao]["valor"].sum()
    cred_anterior = df_anterior[df_anterior["conta_credito"] == conta_descricao]["valor"].sum()
    saldo_anterior = deb_anterior - cred_anterior
    
    deb_periodo = df_periodo[df_periodo["conta_debito"] == conta_descricao]["valor"].sum()
    cred_periodo = df_periodo[df_periodo["conta_credito"] == conta_descricao]["valor"].sum()
    
    saldo_final = saldo_anterior + deb_periodo - cred_periodo
    
    return {
        "saldo_anterior": saldo_anterior,
        "debitos": deb_periodo,
        "creditos": cred_periodo,
        "saldo_final": saldo_final
    }

def calcular_saldo_sintetica(conta_codigo, contas_dict, df_anterior, df_periodo):
    """Calcula saldo para conta sintética (soma das filhas)"""
    contas_filhas = [c for c in contas_dict.values() if c.get("pai") == conta_codigo]
    
    resultado = {
        "saldo_anterior": 0,
        "debitos": 0,
        "creditos": 0,
        "saldo_final": 0
    }
    
    for filha in contas_filhas:
        if filha["natureza"] == "Analítica":
            saldo = calcular_saldo_analitica(filha["descricao"], df_anterior, df_periodo)
        else:
            saldo = calcular_saldo_sintetica(filha["codigo"], contas_dict, df_anterior, df_periodo)
        
        resultado["saldo_anterior"] += saldo["saldo_anterior"]
        resultado["debitos"] += saldo["debitos"]
        resultado["creditos"] += saldo["creditos"]
        resultado["saldo_final"] += saldo["saldo_final"]
    
    return resultado

def calcular_demonstrativo(data_inicio, data_fim):
    """Calcula demonstrativo completo respeitando hierarquia"""
    if not st.session_state.lancamentos:
        return []
    
    df_lancamentos = pd.DataFrame(st.session_state.lancamentos)
    df_lancamentos["data"] = pd.to_datetime(df_lancamentos["data"])
    
    # Filtrar períodos
    df_anterior = df_lancamentos[df_lancamentos["data"] < pd.to_datetime(data_inicio)]
    df_periodo = df_lancamentos[(df_lancamentos["data"] >= pd.to_datetime(data_inicio)) & 
                                (df_lancamentos["data"] <= pd.to_datetime(data_fim))]
    
    # Montar hierarquia
    hierarquia = montar_hierarquia(st.session_state.contas_hierarquicas)
    
    resultado = []
    for conta in hierarquia:
        if conta["natureza"] == "Analítica":
            saldo = calcular_saldo_analitica(conta["descricao"], df_anterior, df_periodo)
        else:
            saldo = calcular_saldo_sintetica(conta["codigo"], st.session_state.contas_hierarquicas, df_anterior, df_periodo)
        
        resultado.append({
            "codigo": conta["codigo"],
            "descricao": conta["descricao"],
            "tipo": conta["tipo"],
            "natureza": conta["natureza"],
            "nivel": conta["nivel"],
            "pai": conta.get("pai"),
            "saldo_anterior": saldo["saldo_anterior"],
            "debitos": saldo["debitos"],
            "creditos": saldo["creditos"],
            "saldo_final": saldo["saldo_final"]
        })
    
    return resultado

# -------------------------
# Funções de Backup (COMPATÍVEIS)
# -------------------------
def exportar_dados():
    return json.dumps({
        "versao": "4.0",
        "exportado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "contas_hierarquicas": st.session_state.contas_hierarquicas,
        "lancamentos": st.session_state.lancamentos,
        "contas_simples": st.session_state.contas
    }, indent=2, ensure_ascii=False)

def importar_dados(arquivo_json):
    try:
        dados = json.load(arquivo_json)
        
        if "versao" not in dados or dados["versao"] == "1.0":
            # Versão antiga - converter
            st.session_state.contas = dados.get("contas", [])
            st.session_state.lancamentos = dados.get("lancamentos", [])
            
            # Converter lançamentos antigos
            novos_lancamentos = []
            for lanc in st.session_state.lancamentos:
                novo_lanc = {
                    "data": lanc["data"],
                    "historico": lanc["historico"],
                    "valor": lanc["valor"],
                    "data_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                if "debito" in lanc and "credito" in lanc:
                    novo_lanc["tipo"] = "Partida Dobrada"
                    novo_lanc["conta_debito"] = lanc["debito"]
                    novo_lanc["conta_credito"] = lanc["credito"]
                elif "debito" in lanc:
                    novo_lanc["tipo"] = "Débito"
                    novo_lanc["conta_debito"] = lanc["debito"]
                    novo_lanc["conta_credito"] = None
                else:
                    novo_lanc["tipo"] = "Crédito"
                    novo_lanc["conta_debito"] = None
                    novo_lanc["conta_credito"] = lanc["credito"]
                
                novos_lancamentos.append(novo_lanc)
            
            st.session_state.lancamentos = novos_lancamentos
            
        elif dados["versao"] in ["2.0", "3.0"]:
            # Versões intermediárias
            st.session_state.contas_hierarquicas = dados.get("contas_hierarquicas", dados.get("contas_estruturadas", {}))
            st.session_state.lancamentos = dados.get("lancamentos", [])
            st.session_state.contas = [c["descricao"] for c in st.session_state.contas_hierarquicas.values()]
        else:
            # Versão 4.0 (atual)
            st.session_state.contas_hierarquicas = dados.get("contas_hierarquicas", {})
            st.session_state.lancamentos = dados.get("lancamentos", [])
            st.session_state.contas = dados.get("contas_simples", [])
        
        return True, "Dados importados com sucesso!"
    except Exception as e:
        return False, f"Erro ao importar: {str(e)}"

# -------------------------
# Interface Principal
# -------------------------
st.title("🏢 Mini ERP Contábil")
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("💾 Backup")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📤 Exportar", use_container_width=True):
            json_data = exportar_dados()
            st.download_button("⬇️ JSON", json_data, f"erp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", use_container_width=True)
    
    with col2:
        arquivo = st.file_uploader("📂 Importar", type="json", key="backup_import")
        if arquivo:
            ok, msg = importar_dados(arquivo)
            st.success(msg) if ok else st.error(msg)
            if ok:
                st.rerun()
    
    st.markdown("---")
    st.metric("Lançamentos", len(st.session_state.lancamentos))
    st.metric("Contas", len(st.session_state.contas_hierarquicas))

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📘 Plano de Contas", "➕ Lançamentos", "📋 Listagem", "📊 Balanço Patrimonial"])

# -------------------------
# TAB 1: PLANO DE CONTAS HIERÁRQUICO
# -------------------------
with tab1:
    st.subheader("📘 Plano de Contas Hierárquico")
    
    col_form, col_lista = st.columns([1, 2])
    
    with col_form:
        with st.expander("➕ Nova Conta", expanded=True):
            with st.form("form_conta"):
                codigo = st.text_input("Código", placeholder="Ex: 111, 112, 1.01, 3.02.001",
                                      help="Use números. Ex: 1 (Ativo), 11 (Disponibilidade), 111 (Caixa)")
                descricao = st.text_input("Descrição", placeholder="Ex: Caixa, Banco, Fornecedores")
                
                col_tipo = st.columns(2)
                with col_tipo[0]:
                    tipo = st.selectbox("Tipo", ["Ativo", "Passivo", "Receita", "Despesa"])
                with col_tipo[1]:
                    natureza = st.selectbox("Natureza", ["Analítica", "Sintética"],
                                           help="Analítica: lançamentos | Sintética: apenas agrupamento")
                
                submitted = st.form_submit_button("Adicionar Conta", use_container_width=True)
                
                if submitted:
                    valido, msg = validar_codigo_hierarquico(codigo, tipo, st.session_state.contas_hierarquicas)
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
            hierarquia = montar_hierarquia(st.session_state.contas_hierarquicas)
            
            dados_tabela = []
            for conta in hierarquia:
                indent = "  " * (conta["nivel"] - 1)
                dados_tabela.append({
                    "Código": conta["codigo"],
                    "Descrição": f"{indent}{conta['descricao']}",
                    "Tipo": conta["tipo"],
                    "Natureza": conta["natureza"],
                    "Nível": conta["nivel"]
                })
            
            st.dataframe(pd.DataFrame(dados_tabela), use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.subheader("🗑️ Remover Conta")
            
            contas_opcoes = [f"{c['codigo']} - {c['descricao']}" for c in hierarquia]
            conta_remover = st.selectbox("Selecione", contas_opcoes)
            
            if st.button("Remover", type="secondary", use_container_width=True):
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
        else:
            st.info("Nenhuma conta cadastrada")

# -------------------------
# TAB 2: LANÇAMENTOS (EVOLUÍDO)
# -------------------------
with tab2:
    st.subheader("➕ Novo Lançamento")
    
    contas_analiticas = [c["descricao"] for c in st.session_state.contas_hierarquicas.values() 
                        if c["natureza"] == "Analítica"]
    
    if not contas_analiticas:
        st.warning("⚠️ Nenhuma conta analítica cadastrada! Cadastre contas com natureza 'Analítica' primeiro.")
    else:
        with st.form("form_lancamento", clear_on_submit=True):
            data = st.date_input("Data", datetime.today())
            tipo_lanc = st.selectbox("Tipo de Lançamento", ["Partida Dobrada", "Débito Simples", "Crédito Simples"])
            
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
            historico = st.text_input("Histórico", placeholder="Descrição...")
            
            submitted = st.form_submit_button("Registrar", use_container_width=True)
            
            if submitted:
                ok, msg = adicionar_lancamento(data, tipo_lanc, conta_debito, conta_credito, valor, historico)
                if ok:
                    st.success(msg)
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
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            data_ini = st.date_input("Data Inicial", value=None, key="list_ini")
        with col_f2:
            data_fim = st.date_input("Data Final", value=None, key="list_fim")
        
        if data_ini:
            df = df[df["data"] >= pd.to_datetime(data_ini)]
        if data_fim:
            df = df[df["data"] <= pd.to_datetime(data_fim)]
        
        df = df.sort_values("data", ascending=False)
        
        st.metric("Total", f"R$ {df['valor'].sum():,.2f}")
        
        for idx, row in df.iterrows():
            with st.container():
                cols = st.columns([1, 2, 2, 2, 1.5, 0.5])
                
                with cols[0]:
                    st.write(row["data"].strftime("%d/%m/%Y"))
                with cols[1]:
                    st.write(row["tipo"])
                with cols[2]:
                    if row["conta_debito"]:
                        codigo = next((c["codigo"] for c in st.session_state.contas_hierarquicas.values() 
                                     if c["descricao"] == row["conta_debito"]), "")
                        st.write(f"{codigo} - {row['conta_debito']}" if codigo else row["conta_debito"])
                with cols[3]:
                    if row["conta_credito"]:
                        codigo = next((c["codigo"] for c in st.session_state.contas_hierarquicas.values() 
                                     if c["descricao"] == row["conta_credito"]), "")
                        st.write(f"{codigo} - {row['conta_credito']}" if codigo else row["conta_credito"])
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
# TAB 4: BALANÇO PATRIMONIAL
# -------------------------
with tab4:
    st.subheader("📊 Balanço Patrimonial e Demonstrativo de Saldos")
    
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
            resultado = calcular_demonstrativo(data_inicio, data_fim)
            
            if resultado:
                dados_tabela = []
                for item in resultado:
                    indent = "  " * (item["nivel"] - 1)
                    dados_tabela.append({
                        "Código": item["codigo"],
                        "Conta": f"{indent}{item['descricao']}",
                        "Tipo": item["tipo"],
                        "Saldo Anterior": item["saldo_anterior"],
                        "Débitos": item["debitos"],
                        "Créditos": item["creditos"],
                        "Saldo Final": item["saldo_final"]
                    })
                
                df_balanco = pd.DataFrame(dados_tabela)
                
                for col in ["Saldo Anterior", "Débitos", "Créditos", "Saldo Final"]:
                    df_balanco[col] = df_balanco[col].apply(lambda x: f"R$ {x:,.2f}" if x >= 0 else f"<span style='color:red'>R$ {abs(x):,.2f}</span>")
                
                st.dataframe(df_balanco, use_container_width=True, hide_index=True)
                
                # Totais
                st.markdown("---")
                st.subheader("📈 Totais Gerais")
                
                totais = {
                    "Débitos": sum(r["debitos"] for r in resultado),
                    "Créditos": sum(r["creditos"] for r in resultado)
                }
                
                col_t1, col_t2, col_t3 = st.columns(3)
                with col_t1:
                    st.metric("Total Débitos", f"R$ {totais['Débitos']:,.2f}")
                with col_t2:
                    st.metric("Total Créditos", f"R$ {totais['Créditos']:,.2f}")
                with col_t3:
                    diff = totais["Débitos"] - totais["Créditos"]
                    st.metric("Diferença", f"R$ {diff:,.2f}", delta_color="inverse" if diff != 0 else "off")
                
                if abs(diff) < 0.01:
                    st.success("✅ Sistema em equilíbrio contábil!")
                else:
                    st.warning("⚠️ Diferença detectada! Verifique os lançamentos.")
            else:
                st.info("Nenhum dado no período selecionado")

# -------------------------
# Rodapé
# -------------------------
st.markdown("---")
st.caption(f"🏢 Mini ERP Contábil v4.0 | {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")