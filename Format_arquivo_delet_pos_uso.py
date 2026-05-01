import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta

st.set_page_config(page_title="Sistema Contábil ERP", layout="wide")

# -------------------------
# Inicialização do Estado (PRESERVANDO DADOS EXISTENTES)
# -------------------------
def init_session_state():
    if "lancamentos" not in st.session_state:
        st.session_state.lancamentos = []
    
    if "contas" not in st.session_state:
        st.session_state.contas = ["Caixa", "Banco", "Receita", "Despesa"]
    
    # Estrutura avançada de contas (compatível com antiga)
    if "contas_estruturadas" not in st.session_state:
        st.session_state.contas_estruturadas = {}
        
        # Converter contas antigas para novo formato
        for idx, conta in enumerate(st.session_state.contas, start=1):
            tipo = "Ativo"
            conta_lower = conta.lower()
            if "receita" in conta_lower or "venda" in conta_lower:
                tipo = "Receita"
                codigo = f"3.{idx:02d}"
            elif "despesa" in conta_lower or "custo" in conta_lower:
                tipo = "Despesa"
                codigo = f"4.{idx:02d}"
            elif "passivo" in conta_lower or "fornecedor" in conta_lower:
                tipo = "Passivo"
                codigo = f"2.{idx:02d}"
            else:
                tipo = "Ativo"
                codigo = f"1.{idx:02d}"
            
            st.session_state.contas_estruturadas[codigo] = {
                "codigo": codigo,
                "descricao": conta,
                "tipo": tipo,
                "natureza": "Analítica",
                "conta_superior": None,
                "nome_original": conta,
                "nivel": 1,
                "filhas": []
            }
    
    if "proximo_codigo_aux" not in st.session_state:
        st.session_state.proximo_codigo_aux = len(st.session_state.contas_estruturadas) + 1

init_session_state()

# -------------------------
# Funções Auxiliares de Hierarquia
# -------------------------
def validar_codigo_por_tipo(codigo, tipo):
    """Valida se o código começa com o dígito correto baseado no tipo"""
    if not codigo:
        return False, "Código não pode ser vazio!"
    
    primeiro_digito = str(codigo).split('.')[0]
    
    regras = {
        "Ativo": "1",
        "Passivo": "2",
        "Receita": "3",
        "Despesa": "4"
    }
    
    if tipo in regras:
        if primeiro_digito != regras[tipo]:
            return False, f"Conta do tipo {tipo} deve começar com o dígito {regras[tipo]}! Exemplo: {regras[tipo]}.XX.XX"
    
    return True, "OK"

def validar_hierarquia_codigo(codigo, conta_superior):
    """Valida a hierarquia do código"""
    if not conta_superior:
        return True, "OK"
    
    # Verificar se o código filho começa com o código pai
    if not str(codigo).startswith(str(conta_superior)):
        return False, f"O código {codigo} deve começar com o código da conta superior {conta_superior}"
    
    # Verificar níveis
    niveis_pai = len(str(conta_superior).split('.'))
    niveis_filho = len(str(codigo).split('.'))
    
    if niveis_filho != niveis_pai + 1:
        return False, f"O nível hierárquico deve ser {niveis_pai + 1} (pai tem {niveis_pai} níveis)"
    
    return True, "OK"

def verificar_loop_hierarquia(codigo, conta_superior_codigo, contas_dict):
    """Verifica se a hierarquia criaria um loop"""
    if not conta_superior_codigo:
        return True, "OK"
    
    # Verificar se conta superior não é ela mesma
    if codigo == conta_superior_codigo:
        return False, "Uma conta não pode ser superior a si mesma!"
    
    # Verificar se a conta superior não é filha da conta atual
    current = conta_superior_codigo
    visited = set()
    
    while current and current not in visited:
        if current == codigo:
            return False, "Loop hierárquico detectado! Esta conta seria ancestral de si mesma."
        visited.add(current)
        current = contas_dict.get(current, {}).get("conta_superior")
    
    return True, "OK"

def atualizar_hierarquia_filhas():
    """Atualiza a lista de contas filhas para todas as contas"""
    for conta in st.session_state.contas_estruturadas.values():
        conta["filhas"] = []
    
    for codigo, conta in st.session_state.contas_estruturadas.items():
        if conta["conta_superior"] and conta["conta_superior"] in st.session_state.contas_estruturadas:
            st.session_state.contas_estruturadas[conta["conta_superior"]]["filhas"].append(codigo)

def exibir_plano_hierarquico(contas_dict, nivel=0, codigo_pai=None):
    """Retorna lista de contas com indentação"""
    resultado = []
    
    contas_filtradas = []
    for codigo, conta in contas_dict.items():
        if conta["conta_superior"] == codigo_pai:
            contas_filtradas.append((codigo, conta))
    
    contas_filtradas.sort(key=lambda x: x[0])
    
    for codigo, conta in contas_filtradas:
        indentacao = "&nbsp;&nbsp;&nbsp;" * nivel
        resultado.append({
            "Código": codigo,
            "Descrição": f"{indentacao}{conta['descricao']}",
            "Tipo": conta["tipo"],
            "Natureza": conta["natureza"],
            "Conta Superior": conta["conta_superior"] or "-",
            "Nível": conta["nivel"]
        })
        
        resultado.extend(exibir_plano_hierarquico(contas_dict, nivel + 1, codigo))
    
    return resultado

# -------------------------
# Funções de Plano de Contas (EVOLUÍDAS)
# -------------------------
def adicionar_conta_estruturada(codigo, descricao, tipo, natureza, conta_superior):
    # Verificar campos obrigatórios
    if not codigo or not descricao:
        return False, "Código e descrição são obrigatórios!"
    
    # Verificar código duplicado
    if codigo in st.session_state.contas_estruturadas:
        return False, "Código já existe!"
    
    # Validar código por tipo
    valido, mensagem = validar_codigo_por_tipo(codigo, tipo)
    if not valido:
        return False, mensagem
    
    # Validar hierarquia
    if conta_superior:
        valido, mensagem = validar_hierarquia_codigo(codigo, conta_superior)
        if not valido:
            return False, mensagem
        
        # Verificar loop hierárquico
        valido, mensagem = verificar_loop_hierarquia(codigo, conta_superior, st.session_state.contas_estruturadas)
        if not valido:
            return False, mensagem
    
    # Calcular nível
    if conta_superior and conta_superior in st.session_state.contas_estruturadas:
        nivel = st.session_state.contas_estruturadas[conta_superior]["nivel"] + 1
    else:
        nivel = 1
    
    # Adicionar conta
    st.session_state.contas_estruturadas[codigo] = {
        "codigo": codigo,
        "descricao": descricao,
        "tipo": tipo,
        "natureza": natureza,
        "conta_superior": conta_superior,
        "nome_original": descricao,
        "nivel": nivel,
        "filhas": []
    }
    
    # Manter compatibilidade com lista antiga de contas
    if descricao not in st.session_state.contas:
        st.session_state.contas.append(descricao)
    
    # Atualizar hierarquia
    atualizar_hierarquia_filhas()
    
    return True, "Conta adicionada com sucesso!"

def remover_conta_estruturada(codigo):
    if codigo not in st.session_state.contas_estruturadas:
        return False, "Conta não encontrada!"
    
    conta = st.session_state.contas_estruturadas[codigo]
    
    # Verificar se tem lançamentos
    tem_lancamento = False
    for lanc in st.session_state.lancamentos:
        if lanc["debito"] == conta["descricao"] or lanc["credito"] == conta["descricao"]:
            tem_lancamento = True
            break
    
    if tem_lancamento:
        return False, "Não é possível excluir conta com lançamentos!"
    
    # Verificar se tem contas filhas
    if conta["filhas"]:
        return False, f"Não é possível excluir conta que possui {len(conta['filhas'])} conta(s) filha(s)!"
    
    # Remover conta
    descricao_conta = conta["descricao"]
    del st.session_state.contas_estruturadas[codigo]
    
    # Remover da lista simples
    if descricao_conta in st.session_state.contas:
        st.session_state.contas.remove(descricao_conta)
    
    # Atualizar hierarquia
    atualizar_hierarquia_filhas()
    
    return True, "Conta removida com sucesso!"

def get_contas_analiticas():
    """Retorna apenas contas analíticas para lançamentos"""
    return [conta["descricao"] for conta in st.session_state.contas_estruturadas.values() 
            if conta["natureza"] == "Analítica"]

def get_contas_sinteticas():
    """Retorna apenas contas sintéticas"""
    return [conta["descricao"] for conta in st.session_state.contas_estruturadas.values() 
            if conta["natureza"] == "Sintética"]

# -------------------------
# Funções de Lançamento (PRESERVADAS E EVOLUÍDAS)
# -------------------------
def adicionar_lancamento(data, debito, credito, historico, valor):
    # Validações
    if debito == credito:
        return False, "Débito e Crédito não podem ser iguais!"
    
    if valor <= 0:
        return False, "Valor deve ser maior que zero!"
    
    # Verificar se as contas são analíticas
    contas_analiticas = get_contas_analiticas()
    
    if debito not in contas_analiticas:
        return False, f"A conta débito '{debito}' é sintética e não pode receber lançamentos!"
    
    if credito not in contas_analiticas:
        return False, f"A conta crédito '{credito}' é sintética e não pode receber lançamentos!"
    
    # Adicionar lançamento
    st.session_state.lancamentos.append({
        "data": data.strftime("%Y-%m-%d"),
        "debito": debito,
        "credito": credito,
        "historico": historico,
        "valor": valor,
        "data_hora_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    return True, "Lançamento registrado com sucesso!"

def excluir_lancamento(index):
    if 0 <= index < len(st.session_state.lancamentos):
        st.session_state.lancamentos.pop(index)
        return True
    return False

# -------------------------
# Funções de Filtro
# -------------------------
def filtrar_por_periodo(df, data_inicio, data_fim):
    if data_inicio:
        df = df[pd.to_datetime(df["data"]) >= pd.to_datetime(data_inicio)]
    if data_fim:
        df = df[pd.to_datetime(df["data"]) <= pd.to_datetime(data_fim)]
    return df

def filtrar_por_conta(df, conta):
    if conta and conta != "Todas":
        df = df[(df["debito"] == conta) | (df["credito"] == conta)]
    return df

# -------------------------
# Funções do Demonstrativo de Saldos (EVOLUÍDAS COM HIERARQUIA)
# -------------------------
def calcular_saldo_conta(conta_codigo, df_periodo, df_anterior):
    """Calcula saldo de uma conta individual"""
    conta = st.session_state.contas_estruturadas[conta_codigo]
    
    # Saldo anterior
    debitos_anterior = df_anterior[df_anterior["debito"] == conta["descricao"]]["valor"].sum()
    creditos_anterior = df_anterior[df_anterior["credito"] == conta["descricao"]]["valor"].sum()
    saldo_anterior = debitos_anterior - creditos_anterior
    
    # Movimento do período
    debitos_periodo = df_periodo[df_periodo["debito"] == conta["descricao"]]["valor"].sum()
    creditos_periodo = df_periodo[df_periodo["credito"] == conta["descricao"]]["valor"].sum()
    
    # Saldo final
    saldo_final = saldo_anterior + debitos_periodo - creditos_periodo
    
    return {
        "codigo": conta_codigo,
        "descricao": conta["descricao"],
        "tipo": conta["tipo"],
        "natureza": conta["natureza"],
        "saldo_anterior": saldo_anterior,
        "debitos_periodo": debitos_periodo,
        "creditos_periodo": creditos_periodo,
        "saldo_final": saldo_final,
        "filhas": conta["filhas"]
    }

def calcular_saldo_hierarquico(conta_codigo, df_periodo, df_anterior):
    """Calcula saldo considerando hierarquia (contas sintéticas somam filhas)"""
    conta = st.session_state.contas_estruturadas[conta_codigo]
    
    if conta["natureza"] == "Sintética" and conta["filhas"]:
        # Soma os saldos das contas filhas
        resultado = {
            "codigo": conta_codigo,
            "descricao": conta["descricao"],
            "tipo": conta["tipo"],
            "natureza": conta["natureza"],
            "saldo_anterior": 0,
            "debitos_periodo": 0,
            "creditos_periodo": 0,
            "saldo_final": 0,
            "filhas": conta["filhas"]
        }
        
        for filha_codigo in conta["filhas"]:
            saldo_filha = calcular_saldo_hierarquico(filha_codigo, df_periodo, df_anterior)
            resultado["saldo_anterior"] += saldo_filha["saldo_anterior"]
            resultado["debitos_periodo"] += saldo_filha["debitos_periodo"]
            resultado["creditos_periodo"] += saldo_filha["creditos_periodo"]
            resultado["saldo_final"] += saldo_filha["saldo_final"]
        
        return resultado
    else:
        return calcular_saldo_conta(conta_codigo, df_periodo, df_anterior)

def calcular_demonstrativo_periodo(data_inicio, data_fim):
    """Calcula demonstrativo completo com hierarquia"""
    df_lancamentos = pd.DataFrame(st.session_state.lancamentos)
    if df_lancamentos.empty:
        return []
    
    df_lancamentos["data"] = pd.to_datetime(df_lancamentos["data"])
    
    # Filtrar períodos
    df_anterior = df_lancamentos[df_lancamentos["data"] < pd.to_datetime(data_inicio)]
    df_periodo = df_lancamentos[(df_lancamentos["data"] >= pd.to_datetime(data_inicio)) & 
                                (df_lancamentos["data"] <= pd.to_datetime(data_fim))]
    
    resultado = []
    
    # Calcular apenas contas raiz
    for codigo, conta in st.session_state.contas_estruturadas.items():
        if conta["conta_superior"] is None:
            saldo = calcular_saldo_hierarquico(codigo, df_periodo, df_anterior)
            resultado.append(saldo)
    
    return resultado

# -------------------------
# Funções de Backup (MANTIDAS E EVOLUÍDAS)
# -------------------------
def exportar_dados():
    dados_export = {
        "versao": "3.0",
        "exportado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "contas_simples": st.session_state.contas,
        "contas_estruturadas": st.session_state.contas_estruturadas,
        "lancamentos": st.session_state.lancamentos
    }
    return json.dumps(dados_export, indent=2, ensure_ascii=False)

def importar_dados(arquivo_json):
    try:
        dados = json.load(arquivo_json)
        
        # Compatibilidade com versões anteriores
        if "versao" not in dados:
            # Versão 1.0 (mais antiga)
            st.session_state.contas = dados.get("contas", [])
            st.session_state.lancamentos = dados.get("lancamentos", [])
            
            # Converter para novo formato
            st.session_state.contas_estruturadas = {}
            for idx, conta in enumerate(st.session_state.contas, start=1):
                tipo = "Ativo"
                conta_lower = conta.lower()
                if "receita" in conta_lower:
                    tipo = "Receita"
                    codigo = f"3.{idx:02d}"
                elif "despesa" in conta_lower:
                    tipo = "Despesa"
                    codigo = f"4.{idx:02d}"
                elif "passivo" in conta_lower:
                    tipo = "Passivo"
                    codigo = f"2.{idx:02d}"
                else:
                    tipo = "Ativo"
                    codigo = f"1.{idx:02d}"
                
                st.session_state.contas_estruturadas[codigo] = {
                    "codigo": codigo,
                    "descricao": conta,
                    "tipo": tipo,
                    "natureza": "Analítica",
                    "conta_superior": None,
                    "nome_original": conta,
                    "nivel": 1,
                    "filhas": []
                }
        elif dados["versao"] == "2.0":
            # Versão 2.0
            st.session_state.contas = dados.get("contas_simples", [])
            st.session_state.contas_estruturadas = dados.get("contas_avancadas", {})
            st.session_state.lancamentos = dados.get("lancamentos", [])
            
            # Converter para nova estrutura
            for codigo, conta in st.session_state.contas_estruturadas.items():
                if "natureza" not in conta:
                    conta["natureza"] = "Analítica"
                if "nivel" not in conta:
                    conta["nivel"] = 1
                if "filhas" not in conta:
                    conta["filhas"] = []
        else:
            # Versão 3.0 (atual)
            st.session_state.contas = dados.get("contas_simples", [])
            st.session_state.contas_estruturadas = dados.get("contas_estruturadas", {})
            st.session_state.lancamentos = dados.get("lancamentos", [])
        
        # Atualizar hierarquia
        atualizar_hierarquia_filhas()
        
        return True, "Dados importados com sucesso!"
    except Exception as e:
        return False, f"Erro ao importar: {str(e)}"

# -------------------------
# Interface Principal
# -------------------------
st.title("🏢 Sistema Contábil ERP - Hierárquico")
st.markdown("---")

# Sidebar - Backup
with st.sidebar:
    st.header("💾 Backup e Recuperação")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📤 Exportar", use_container_width=True):
            json_data = exportar_dados()
            st.download_button(
                label="⬇️ Download JSON",
                data=json_data,
                file_name=f"erp_contabil_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )
    
    with col2:
        arquivo = st.file_uploader("📂 Importar", type="json", key="backup_import")
        if arquivo:
            sucesso, mensagem = importar_dados(arquivo)
            if sucesso:
                st.success(mensagem)
                st.rerun()
            else:
                st.error(mensagem)
    
    st.markdown("---")
    st.metric("Total Lançamentos", len(st.session_state.lancamentos))
    st.metric("Total Contas", len(st.session_state.contas_estruturadas))
    
    contas_analiticas = len(get_contas_analiticas())
    contas_sinteticas = len(get_contas_sinteticas())
    st.metric("Contas Analíticas", contas_analiticas)
    st.metric("Contas Sintéticas", contas_sinteticas)

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📘 Plano de Contas", "➕ Novo Lançamento", "📋 Listagem de Lançamentos", "📊 Demonstrativo de Saldos"])

# -------------------------
# TAB 1: PLANO DE CONTAS (HIERÁRQUICO)
# -------------------------
with tab1:
    st.subheader("📘 Plano de Contas Hierárquico")
    
    col_form, col_lista = st.columns([1, 2])
    
    with col_form:
        with st.expander("➕ Nova Conta", expanded=True):
            with st.form("form_nova_conta"):
                codigo = st.text_input("Código", placeholder="Ex: 1.01.01 ou 3.01", 
                                      help="Formato: número com pontos (ex: 1.01, 2.01.001)")
                
                descricao = st.text_input("Descrição", placeholder="Ex: Caixa, Fornecedores, Receita de Vendas...")
                
                col_tipo = st.columns(2)
                with col_tipo[0]:
                    tipo = st.selectbox("Tipo", ["Ativo", "Passivo", "Receita", "Despesa"],
                                       help="Define o primeiro dígito do código")
                with col_tipo[1]:
                    natureza = st.selectbox("Natureza", ["Analítica", "Sintética"],
                                           help="Analítica: recebe lançamentos | Sintética: apenas agrupamento")
                
                # Lista de contas superiores (apenas contas existentes)
                contas_superiores_lista = [None] + [c["codigo"] for c in st.session_state.contas_estruturadas.values()]
                conta_superior = st.selectbox("Conta Superior (Opcional)", contas_superiores_lista,
                                             format_func=lambda x: x if x else "Nenhuma (Raiz)",
                                             help="Define hierarquia: conta pai desta conta")
                
                st.caption("🔢 Regras:")
                st.caption("- Ativo: código começa com 1 | Passivo: começa com 2")
                st.caption("- Receita: começa com 3 | Despesa: começa com 4")
                st.caption("- Conta sintética NÃO pode receber lançamentos")
                
                submitted = st.form_submit_button("✅ Adicionar Conta", use_container_width=True)
                
                if submitted:
                    if not codigo or not descricao:
                        st.error("Código e descrição são obrigatórios!")
                    else:
                        sucesso, mensagem = adicionar_conta_estruturada(codigo, descricao, tipo, natureza, conta_superior)
                        if sucesso:
                            st.success(mensagem)
                            st.rerun()
                        else:
                            st.error(mensagem)
    
    with col_lista:
        st.subheader("📋 Plano de Contas (Visualização Hierárquica)")
        
        if st.session_state.contas_estruturadas:
            # Exibir plano hierárquico
            plano_hierarquico = exibir_plano_hierarquico(st.session_state.contas_estruturadas)
            df_plano = pd.DataFrame(plano_hierarquico)
            
            st.dataframe(df_plano, use_container_width=True, hide_index=True)
            
            # Remover conta
            st.markdown("---")
            st.subheader("🗑️ Remover Conta")
            
            contas_para_remover = [f"{c['codigo']} - {c['descricao']}" for c in st.session_state.contas_estruturadas.values()]
            conta_selecionada = st.selectbox("Selecione a conta para remover", contas_para_remover)
            
            if st.button("Remover Conta", type="secondary", use_container_width=True):
                codigo_conta = conta_selecionada.split(" - ")[0]
                sucesso, mensagem = remover_conta_estruturada(codigo_conta)
                if sucesso:
                    st.success(mensagem)
                    st.rerun()
                else:
                    st.error(mensagem)
        else:
            st.info("Nenhuma conta cadastrada. Use o formulário ao lado para adicionar.")

# -------------------------
# TAB 2: NOVO LANÇAMENTO (APENAS CONTAS ANALÍTICAS)
# -------------------------
with tab2:
    st.subheader("➕ Novo Lançamento")
    
    contas_analiticas = get_contas_analiticas()
    
    if not contas_analiticas:
        st.warning("⚠️ Não existem contas analíticas cadastradas! Contas analíticas são necessárias para lançamentos.")
        st.info("Cadastre contas com natureza 'Analítica' na aba 'Plano de Contas' para realizar lançamentos.")
    else:
        with st.form("form_lancamento", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                data = st.date_input("Data do Lançamento", datetime.today())
                debito = st.selectbox("Conta Débito (Analítica)", contas_analiticas)
                historico = st.text_input("Histórico", placeholder="Descrição do lançamento...")
            
            with col2:
                valor = st.number_input("Valor (R$)", min_value=0.01, step=0.01, format="%.2f")
                credito = st.selectbox("Conta Crédito (Analítica)", contas_analiticas)
            
            submitted = st.form_submit_button("✅ Registrar Lançamento", use_container_width=True)
            
            if submitted:
                sucesso, mensagem = adicionar_lancamento(data, debito, credito, historico, valor)
                if sucesso:
                    st.success(mensagem)
                    st.balloons()
                    st.rerun()
                else:
                    st.error(mensagem)

# -------------------------
# TAB 3: LISTAGEM DE LANÇAMENTOS (MANTIDA)
# -------------------------
with tab3:
    st.subheader("📋 Listagem de Lançamentos")
    
    if st.session_state.lancamentos:
        df_lancamentos = pd.DataFrame(st.session_state.lancamentos)
        df_lancamentos["data"] = pd.to_datetime(df_lancamentos["data"])
        
        # Filtros
        st.markdown("### 🔍 Filtros")
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            data_inicio_filtro = st.date_input("Data Inicial", value=None, key="filtro_inicio")
        
        with col_f2:
            data_fim_filtro = st.date_input("Data Final", value=None, key="filtro_fim")
        
        with col_f3:
            contas_filtro = ["Todas"] + st.session_state.contas
            conta_filtro = st.selectbox("Conta", contas_filtro, key="filtro_conta")
        
        df_filtrado = filtrar_por_periodo(df_lancamentos, data_inicio_filtro, data_fim_filtro)
        df_filtrado = filtrar_por_conta(df_filtrado, conta_filtro)
        df_filtrado = df_filtrado.sort_values("data", ascending=False)
        
        total_filtrado = df_filtrado["valor"].sum()
        st.metric("💰 Total dos Lançamentos Filtrados", f"R$ {total_filtrado:,.2f}")
        
        st.markdown("### 📊 Lançamentos")
        
        if not df_filtrado.empty:
            for idx, row in df_filtrado.iterrows():
                with st.container():
                    cols = st.columns([1.2, 2, 2, 2.5, 1.5, 0.5])
                    
                    with cols[0]:
                        st.write(row["data"].strftime("%d/%m/%Y"))
                    with cols[1]:
                        st.write(row["debito"])
                    with cols[2]:
                        st.write(row["credito"])
                    with cols[3]:
                        historico_texto = row["historico"] if len(row["historico"]) <= 40 else row["historico"][:40] + "..."
                        st.write(historico_texto)
                    with cols[4]:
                        st.write(f"R$ {row['valor']:,.2f}")
                    with cols[5]:
                        if st.button("🗑️", key=f"del_{idx}_{row['data']}_{row['valor']}"):
                            indice_original = st.session_state.lancamentos.index(
                                next(l for l in st.session_state.lancamentos 
                                     if l["data"] == row["data"].strftime("%Y-%m-%d") 
                                     and l["debito"] == row["debito"]
                                     and l["credito"] == row["credito"]
                                     and l["valor"] == row["valor"])
                            )
                            if excluir_lancamento(indice_original):
                                st.success("Lançamento excluído!")
                                st.rerun()
                    
                    st.divider()
        else:
            st.info("Nenhum lançamento encontrado com os filtros selecionados.")
    else:
        st.info("📭 Nenhum lançamento registrado ainda. Use a aba 'Novo Lançamento' para começar!")

# -------------------------
# TAB 4: DEMONSTRATIVO DE SALDOS (COM HIERARQUIA)
# -------------------------
with tab4:
    st.subheader("📊 Demonstrativo de Saldos com Hierarquia")
    
    if st.session_state.lancamentos:
        hoje = datetime.now()
        primeiro_dia_mes = datetime(hoje.year, hoje.month, 1)
        ultimo_dia_mes = datetime(hoje.year, hoje.month + 1, 1) - timedelta(days=1) if hoje.month < 12 else datetime(hoje.year, 12, 31)
        
        col_p1, col_p2 = st.columns(2)
        
        with col_p1:
            data_inicio_demo = st.date_input("Data Inicial", primeiro_dia_mes, key="demo_inicio")
        
        with col_p2:
            data_fim_demo = st.date_input("Data Final", ultimo_dia_mes, key="demo_fim")
        
        if st.button("📊 Calcular Demonstrativo", use_container_width=True):
            with st.spinner("Calculando saldos com hierarquia..."):
                resultado = calcular_demonstrativo_periodo(data_inicio_demo, data_fim_demo)
                
                if resultado:
                    # Preparar dados para exibição
                    dados_tabela = []
                    
                    def adicionar_linha(saldo, nivel=0):
                        indentacao = "&nbsp;&nbsp;&nbsp;" * nivel
                        
                        dados_tabela.append({
                            "Conta": f"{indentacao}{saldo['descricao']} ({saldo['codigo']})",
                            "Tipo": saldo["tipo"],
                            "Natureza": saldo["natureza"],
                            "Saldo Anterior": saldo["saldo_anterior"],
                            "Débitos": saldo["debitos_periodo"],
                            "Créditos": saldo["creditos_periodo"],
                            "Saldo Final": saldo["saldo_final"]
                        })
                        
                        for filha_codigo in saldo["filhas"]:
                            # Encontrar saldo da filha no resultado
                            saldo_filha = next((s for s in resultado if s["codigo"] == filha_codigo), None)
                            if saldo_filha:
                                adicionar_linha(saldo_filha, nivel + 1)
                    
                    for saldo in resultado:
                        adicionar_linha(saldo)
                    
                    df_demo = pd.DataFrame(dados_tabela)
                    
                    # Formatar valores
                    for col in ["Saldo Anterior", "Débitos", "Créditos", "Saldo Final"]:
                        df_demo[col] = df_demo[col].apply(lambda x: f"R$ {x:,.2f}" if x >= 0 else f"R$ ({abs(x):,.2f})")
                    
                    st.dataframe(df_demo, use_container_width=True, hide_index=True)
                    
                    # Totais gerais
                    st.markdown("---")
                    st.subheader("📈 Totais do Período")
                    
                    total_debitos = sum(s["debitos_periodo"] for s in resultado)
                    total_creditos = sum(s["creditos_periodo"] for s in resultado)
                    diferenca = total_debitos - total_creditos
                    
                    col_t1, col_t2, col_t3 = st.columns(3)
                    
                    with col_t1:
                        st.metric("Total Débitos no Período", f"R$ {total_debitos:,.2f}")
                    
                    with col_t2:
                        st.metric("Total Créditos no Período", f"R$ {total_creditos:,.2f}")
                    
                    with col_t3:
                        cor_delta = "inverse" if diferenca < 0 else "normal"
                        st.metric("Diferença (D - C)", f"R$ {diferenca:,.2f}", delta_color=cor_delta)
                    
                    if abs(diferenca) > 0.01:
                        st.warning("⚠️ Diferença detectada! Verifique os lançamentos.")
                    else:
                        st.success("✅ Sistema em equilíbrio contábil!")
                else:
                    st.info("Nenhum movimento encontrado no período selecionado.")
    else:
        st.info("📭 Nenhum lançamento registrado. Cadastre lançamentos para visualizar o demonstrativo.")

# -------------------------
# Rodapé
# -------------------------
st.markdown("---")
st.caption(f"🏢 Sistema Contábil ERP v3.0 (Hierárquico) | Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")