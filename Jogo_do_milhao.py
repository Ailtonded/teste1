import streamlit as st
import random
import time
from datetime import datetime

# Configuração da página
st.set_page_config(
    page_title="Show do Milhão - Protheus",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==================== DADOS DAS PERGUNTAS COM NÍVEIS ====================
PERGUNTAS = [
    # Nível 1 - Fácil (Perguntas 1-10)
    {
        "pergunta": "Qual é a principal função da tabela SX3 no Protheus?",
        "alternativas": {
            "A": "Armazenar pedidos de venda",
            "B": "Definir os campos das tabelas do sistema",
            "C": "Registrar movimentações financeiras",
            "D": "Cadastrar usuários",
            "E": "Controlar backups"
        },
        "resposta_correta": "B",
        "nivel": 1
    },
    {
        "pergunta": "Qual tabela é utilizada para cadastro de clientes?",
        "alternativas": {
            "A": "SB1",
            "B": "SA1",
            "C": "SC5",
            "D": "SE1",
            "E": "SD2"
        },
        "resposta_correta": "B",
        "nivel": 1
    },
    {
        "pergunta": "Qual tabela armazena produtos no Protheus?",
        "alternativas": {
            "A": "SA2",
            "B": "SC6",
            "C": "SB1",
            "D": "SE2",
            "E": "SF2"
        },
        "resposta_correta": "C",
        "nivel": 1
    },
    {
        "pergunta": "A tabela SC5 representa:",
        "alternativas": {
            "A": "Itens do pedido",
            "B": "Cadastro de fornecedores",
            "C": "Cabeçalho do pedido de venda",
            "D": "Notas fiscais",
            "E": "Produtos"
        },
        "resposta_correta": "C",
        "nivel": 1
    },
    {
        "pergunta": "Qual tabela contém os itens do pedido de venda?",
        "alternativas": {
            "A": "SC6",
            "B": "SC5",
            "C": "SB1",
            "D": "SD1",
            "E": "SE1"
        },
        "resposta_correta": "A",
        "nivel": 1
    },
    {
        "pergunta": "O campo D_E_L_E_T_ indica:",
        "alternativas": {
            "A": "Chave estrangeira",
            "B": "Controle financeiro",
            "C": "Exclusão lógica",
            "D": "Backup automático",
            "E": "Erro de índice"
        },
        "resposta_correta": "C",
        "nivel": 1
    },
    {
        "pergunta": "A tabela SX2 serve para:",
        "alternativas": {
            "A": "Cadastrar usuários",
            "B": "Definir tabelas do sistema",
            "C": "Armazenar pedidos",
            "D": "Controlar estoque",
            "E": "Gerenciar relatórios"
        },
        "resposta_correta": "B",
        "nivel": 1
    },
    {
        "pergunta": "Qual tabela é usada para fornecedores?",
        "alternativas": {
            "A": "SA2",
            "B": "SA1",
            "C": "SB1",
            "D": "SC5",
            "E": "SE2"
        },
        "resposta_correta": "A",
        "nivel": 1
    },
    {
        "pergunta": "A SX5 é utilizada para:",
        "alternativas": {
            "A": "Parâmetros e tabelas genéricas",
            "B": "Notas fiscais",
            "C": "Pedidos",
            "D": "Clientes",
            "E": "Logs"
        },
        "resposta_correta": "A",
        "nivel": 1
    },
    {
        "pergunta": "Qual tabela normalmente armazena títulos a receber?",
        "alternativas": {
            "A": "SE1",
            "B": "SE2",
            "C": "SF1",
            "D": "SC5",
            "E": "SB1"
        },
        "resposta_correta": "A",
        "nivel": 1
    },
    # Nível 2 - Médio (Perguntas 11-25)
    {
        "pergunta": "Qual tabela armazena títulos a pagar?",
        "alternativas": {
            "A": "SE1",
            "B": "SE2",
            "C": "SD2",
            "D": "SB2",
            "E": "SC6"
        },
        "resposta_correta": "B",
        "nivel": 2
    },
    {
        "pergunta": "A tabela SB2 normalmente controla:",
        "alternativas": {
            "A": "Saldo em estoque",
            "B": "Clientes",
            "C": "Financeiro",
            "D": "Usuários",
            "E": "Compras"
        },
        "resposta_correta": "A",
        "nivel": 2
    },
    {
        "pergunta": "Qual tabela representa notas fiscais de saída?",
        "alternativas": {
            "A": "SF2",
            "B": "SF1",
            "C": "SC5",
            "D": "SD1",
            "E": "SE2"
        },
        "resposta_correta": "A",
        "nivel": 2
    },
    {
        "pergunta": "A tabela SF1 representa:",
        "alternativas": {
            "A": "Notas fiscais de entrada",
            "B": "Pedidos",
            "C": "Produtos",
            "D": "Clientes",
            "E": "Estoque"
        },
        "resposta_correta": "A",
        "nivel": 2
    },
    {
        "pergunta": "Qual tabela contém itens da nota fiscal de saída?",
        "alternativas": {
            "A": "SD2",
            "B": "SC6",
            "C": "SB1",
            "D": "SE1",
            "E": "SA1"
        },
        "resposta_correta": "A",
        "nivel": 2
    },
    {
        "pergunta": "A tabela SD1 armazena:",
        "alternativas": {
            "A": "Itens de nota fiscal de entrada",
            "B": "Produtos",
            "C": "Pedidos",
            "D": "Clientes",
            "E": "Contas a pagar"
        },
        "resposta_correta": "A",
        "nivel": 2
    },
    {
        "pergunta": "No Protheus, índices são normalmente definidos em:",
        "alternativas": {
            "A": "SX2",
            "B": "SX3",
            "C": "SIX",
            "D": "SB1",
            "E": "SC5"
        },
        "resposta_correta": "C",
        "nivel": 2
    },
    {
        "pergunta": "Qual tabela armazena campos das tabelas?",
        "alternativas": {
            "A": "SX3",
            "B": "SX2",
            "C": "SX5",
            "D": "SC5",
            "E": "SB1"
        },
        "resposta_correta": "A",
        "nivel": 2
    },
    {
        "pergunta": "A filial padrão de um registro normalmente fica em qual campo?",
        "alternativas": {
            "A": "FILIAL",
            "B": "D_E_L_E_T_",
            "C": "R_E_C_N_O_",
            "D": "CODFIL",
            "E": "XFILIAL"
        },
        "resposta_correta": "E",
        "nivel": 2
    },
    {
        "pergunta": "O campo R_E_C_N_O_ representa:",
        "alternativas": {
            "A": "Número sequencial interno do registro",
            "B": "Código da filial",
            "C": "Usuário logado",
            "D": "Data de exclusão",
            "E": "Tipo de índice"
        },
        "resposta_correta": "A",
        "nivel": 2
    },
    {
        "pergunta": "Qual linguagem é usada para customizações no Protheus?",
        "alternativas": {
            "A": "Java",
            "B": "Python",
            "C": "ADVPL",
            "D": "C#",
            "E": "PHP"
        },
        "resposta_correta": "C",
        "nivel": 2
    },
    {
        "pergunta": "O configurador do Protheus é conhecido como:",
        "alternativas": {
            "A": "SIGAFAT",
            "B": "SIGACFG",
            "C": "SIGAEST",
            "D": "SIGAFIN",
            "E": "SIGACOM"
        },
        "resposta_correta": "B",
        "nivel": 2
    },
    {
        "pergunta": "Qual módulo é relacionado ao faturamento?",
        "alternativas": {
            "A": "SIGAFAT",
            "B": "SIGAEST",
            "C": "SIGAFIN",
            "D": "SIGACFG",
            "E": "SIGAQRY"
        },
        "resposta_correta": "A",
        "nivel": 2
    },
    {
        "pergunta": "SIGAEST é o módulo de:",
        "alternativas": {
            "A": "Financeiro",
            "B": "Compras",
            "C": "Estoque",
            "D": "RH",
            "E": "Fiscal"
        },
        "resposta_correta": "C",
        "nivel": 2
    },
    {
        "pergunta": "Qual tabela geralmente guarda usuários?",
        "alternativas": {
            "A": "SX5",
            "B": "SC5",
            "C": "SB1",
            "D": "SYS_USR",
            "E": "SE2"
        },
        "resposta_correta": "D",
        "nivel": 2
    },
    # Nível 3 - Difícil (Perguntas 26-35)
    {
        "pergunta": "Qual banco de dados é amplamente usado com Protheus?",
        "alternativas": {
            "A": "Oracle",
            "B": "SQL Server",
            "C": "PostgreSQL",
            "D": "DBAccess",
            "E": "Todas as anteriores"
        },
        "resposta_correta": "E",
        "nivel": 3
    },
    {
        "pergunta": "DBAccess é responsável por:",
        "alternativas": {
            "A": "Gerar relatórios",
            "B": "Conectar o Protheus ao banco de dados",
            "C": "Cadastrar usuários",
            "D": "Gerenciar permissões",
            "E": "Executar backups"
        },
        "resposta_correta": "B",
        "nivel": 3
    },
    {
        "pergunta": "Qual tabela está relacionada ao cadastro de TES?",
        "alternativas": {
            "A": "SF4",
            "B": "SB1",
            "C": "SA1",
            "D": "SE2",
            "E": "SC5"
        },
        "resposta_correta": "A",
        "nivel": 3
    },
    {
        "pergunta": "TES significa:",
        "alternativas": {
            "A": "Tabela Especial de Sistema",
            "B": "Tipo de Entrada e Saída",
            "C": "Transação Eletrônica Simples",
            "D": "Teste Estrutural de Sistema",
            "E": "Tabela de Estoque"
        },
        "resposta_correta": "B",
        "nivel": 3
    },
    {
        "pergunta": "A tabela CT1 pertence normalmente ao módulo:",
        "alternativas": {
            "A": "Estoque",
            "B": "Compras",
            "C": "Contabilidade",
            "D": "RH",
            "E": "Fiscal"
        },
        "resposta_correta": "C",
        "nivel": 3
    },
    {
        "pergunta": "Qual tabela normalmente armazena centros de custo?",
        "alternativas": {
            "A": "CTT",
            "B": "SB1",
            "C": "SC5",
            "D": "SE1",
            "E": "SA2"
        },
        "resposta_correta": "A",
        "nivel": 3
    },
    {
        "pergunta": "O relacionamento entre SC5 e SC6 ocorre por:",
        "alternativas": {
            "A": "Produto",
            "B": "TES",
            "C": "Número do pedido",
            "D": "Cliente",
            "E": "Filial"
        },
        "resposta_correta": "C",
        "nivel": 3
    },
    {
        "pergunta": "Qual tabela armazena saldo por produto e filial?",
        "alternativas": {
            "A": "SB2",
            "B": "SB1",
            "C": "SC6",
            "D": "SD2",
            "E": "SF4"
        },
        "resposta_correta": "A",
        "nivel": 3
    },
    {
        "pergunta": "Qual tabela geralmente contém transportadoras?",
        "alternativas": {
            "A": "SA4",
            "B": "SA1",
            "C": "SB1",
            "D": "SC5",
            "E": "SE2"
        },
        "resposta_correta": "A",
        "nivel": 3
    },
    {
        "pergunta": "A tabela SA3 representa:",
        "alternativas": {
            "A": "Vendedores",
            "B": "Produtos",
            "C": "Pedidos",
            "D": "Notas fiscais",
            "E": "Estoque"
        },
        "resposta_correta": "A",
        "nivel": 3
    },
    # Nível 4 - Especialista (Perguntas 36-47)
    {
        "pergunta": "Qual tabela normalmente armazena natureza financeira?",
        "alternativas": {
            "A": "SED",
            "B": "SB1",
            "C": "SC5",
            "D": "SA1",
            "E": "SX5"
        },
        "resposta_correta": "A",
        "nivel": 4
    },
    {
        "pergunta": "O módulo SIGAFIN refere-se a:",
        "alternativas": {
            "A": "Faturamento",
            "B": "Financeiro",
            "C": "Estoque",
            "D": "Fiscal",
            "E": "Compras"
        },
        "resposta_correta": "B",
        "nivel": 4
    },
    {
        "pergunta": "Qual tabela armazena condições de pagamento?",
        "alternativas": {
            "A": "SE4",
            "B": "SE1",
            "C": "SA2",
            "D": "SB2",
            "E": "SC6"
        },
        "resposta_correta": "A",
        "nivel": 4
    },
    {
        "pergunta": "A exclusão física remove:",
        "alternativas": {
            "A": "Apenas o índice",
            "B": "O registro definitivamente do banco",
            "C": "Somente a filial",
            "D": "Apenas os relacionamentos",
            "E": "O usuário"
        },
        "resposta_correta": "B",
        "nivel": 4
    },
    {
        "pergunta": "Qual tabela está ligada ao cadastro de moedas?",
        "alternativas": {
            "A": "SM2",
            "B": "SA1",
            "C": "SC5",
            "D": "SB1",
            "E": "SE2"
        },
        "resposta_correta": "A",
        "nivel": 4
    },
    {
        "pergunta": "A principal finalidade do dicionário de dados é:",
        "alternativas": {
            "A": "Executar backups",
            "B": "Controlar permissões",
            "C": "Definir estrutura e regras das tabelas",
            "D": "Gerar notas fiscais",
            "E": "Controlar usuários"
        },
        "resposta_correta": "C",
        "nivel": 4
    },
    {
        "pergunta": "Qual tabela normalmente contém grupos de produtos?",
        "alternativas": {
            "A": "SBM",
            "B": "SA1",
            "C": "SC5",
            "D": "SE1",
            "E": "CT1"
        },
        "resposta_correta": "A",
        "nivel": 4
    },
    {
        "pergunta": "Qual tabela guarda informações de armazéns?",
        "alternativas": {
            "A": "NNR",
            "B": "SB1",
            "C": "SA2",
            "D": "SC6",
            "E": "SF2"
        },
        "resposta_correta": "A",
        "nivel": 4
    },
    {
        "pergunta": "No Protheus, customizações são geralmente compiladas em:",
        "alternativas": {
            "A": "DLL",
            "B": "RPO",
            "C": "APK",
            "D": "EXE",
            "E": "JSON"
        },
        "resposta_correta": "B",
        "nivel": 4
    },
    {
        "pergunta": "Qual tabela normalmente armazena pedidos de compra?",
        "alternativas": {
            "A": "SC7",
            "B": "SC5",
            "C": "SB1",
            "D": "SF1",
            "E": "SE2"
        },
        "resposta_correta": "A",
        "nivel": 4
    },
    {
        "pergunta": "Qual tabela contém itens do pedido de compra?",
        "alternativas": {
            "A": "SC8",
            "B": "SC7",
            "C": "SD1",
            "D": "SB2",
            "E": "SE4"
        },
        "resposta_correta": "A",
        "nivel": 4
    },
    {
        "pergunta": "O que significa a sigla RPO no contexto do Protheus?",
        "alternativas": {
            "A": "Relatório de Processamento Online",
            "B": "Resource Program Object",
            "C": "Rápido Processamento Organizado",
            "D": "Registro de Programas Offline",
            "E": "Rotina de Processamento Otimizado"
        },
        "resposta_correta": "B",
        "nivel": 4
    }
]

# Configuração dos prêmios
PREMIO_VALORES = [1000, 2000, 3000, 5000, 10000, 20000, 40000, 80000, 150000, 300000, 
                  500000, 750000, 1000000, 1500000, 2000000, 3000000, 5000000, 7500000, 10000000, 20000000]

TOTAL_PERGUNTAS = len(PERGUNTAS)

# CSS customizado
st.markdown("""
<style>
    /* Estilo principal */
    .stApp {
        background: linear-gradient(135deg, #0a0e1a 0%, #0a1a3a 50%, #0a0e1a 100%);
    }
    
    /* Título principal */
    .main-title {
        text-align: center;
        background: linear-gradient(135deg, #FFD700, #FFA500, #FFD700);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3.5em;
        font-weight: bold;
        text-shadow: 2px 2px 10px rgba(0,0,0,0.5);
        margin-bottom: 10px;
        animation: glow 2s ease-in-out infinite alternate;
    }
    
    @keyframes glow {
        from { filter: drop-shadow(0 0 5px #FFD700); }
        to { filter: drop-shadow(0 0 20px #FFA500); }
    }
    
    .sub-title {
        text-align: center;
        color: #FFD700;
        font-size: 1.2em;
        margin-bottom: 30px;
        letter-spacing: 3px;
    }
    
    /* Cartão de perguntas */
    .question-card {
        background: linear-gradient(135deg, rgba(26, 31, 58, 0.95), rgba(15, 20, 40, 0.95));
        border: 2px solid #FFD700;
        border-radius: 20px;
        padding: 30px;
        margin: 20px 0;
        box-shadow: 0 10px 40px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,215,0,0.2);
        backdrop-filter: blur(5px);
        animation: slideIn 0.5s ease-out;
    }
    
    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateY(30px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .question-text {
        color: #FFD700;
        font-size: 1.6em;
        text-align: center;
        font-weight: bold;
        margin-bottom: 30px;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
    }
    
    .question-number {
        text-align: center;
        color: #FFA500;
        font-size: 1em;
        margin-bottom: 15px;
        font-weight: bold;
    }
    
    /* Botões das alternativas */
    .stButton > button {
        width: 100%;
        background: linear-gradient(135deg, #2a2f4a, #1a1f3a);
        border: 2px solid #FFD700;
        border-radius: 15px;
        padding: 15px 20px;
        margin: 8px 0;
        color: #FFD700;
        font-weight: bold;
        font-size: 1.1em;
        transition: all 0.3s ease;
        cursor: pointer;
        text-align: left;
    }
    
    .stButton > button:hover {
        transform: scale(1.02);
        background: linear-gradient(135deg, #3a3f5a, #2a2f4a);
        border-color: #FFA500;
        box-shadow: 0 5px 20px rgba(255,215,0,0.3);
        color: #FFA500;
    }
    
    /* Botões de ajuda */
    .help-button > button {
        background: linear-gradient(135deg, #FFD700, #FFA500);
        color: #1a1f3a;
        font-weight: bold;
        border: none;
        border-radius: 10px;
        padding: 10px;
        margin: 5px;
        font-size: 0.9em;
    }
    
    .help-button > button:hover {
        transform: scale(1.05);
        box-shadow: 0 5px 15px rgba(255,215,0,0.4);
    }
    
    /* Cartas de ajuda */
    .card-container {
        display: flex;
        gap: 15px;
        justify-content: center;
        margin: 20px 0;
    }
    
    .help-card {
        background: linear-gradient(135deg, #2a2f4a, #1a1f3a);
        border: 2px solid #FFD700;
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        cursor: pointer;
        transition: all 0.3s ease;
        flex: 1;
        margin: 0 5px;
    }
    
    .help-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 25px rgba(255,215,0,0.3);
        border-color: #FFA500;
    }
    
    .help-card-icon {
        font-size: 2em;
        margin-bottom: 10px;
    }
    
    .help-card-title {
        color: #FFD700;
        font-weight: bold;
        font-size: 1.1em;
    }
    
    .help-card-desc {
        color: #FFF;
        font-size: 0.9em;
        margin-top: 5px;
    }
    
    /* Painel de prêmios */
    .prize-panel {
        background: linear-gradient(135deg, #1a1f3a, #0f1428);
        border: 2px solid #FFD700;
        border-radius: 15px;
        padding: 20px;
        margin: 20px 0;
        text-align: center;
    }
    
    .prize-value {
        font-size: 2.5em;
        color: #FFD700;
        font-weight: bold;
        text-shadow: 0 0 10px rgba(255,215,0,0.5);
    }
    
    .prize-label {
        color: #FFA500;
        font-size: 1em;
        letter-spacing: 2px;
    }
    
    /* Painel de ranking */
    .ranking-panel {
        background: linear-gradient(135deg, rgba(26, 31, 58, 0.9), rgba(15, 20, 40, 0.9));
        border: 1px solid #FFD700;
        border-radius: 15px;
        padding: 20px;
        margin: 20px 0;
        backdrop-filter: blur(5px);
    }
    
    .ranking-title {
        color: #FFD700;
        font-size: 1.5em;
        text-align: center;
        border-bottom: 2px solid #FFD700;
        padding-bottom: 10px;
        margin-bottom: 15px;
    }
    
    .ranking-item {
        color: #FFF;
        padding: 8px;
        margin: 5px 0;
        border-left: 3px solid #FFD700;
        background: rgba(255,215,0,0.1);
    }
    
    /* Barra de progresso personalizada */
    .stProgress > div > div {
        background: linear-gradient(90deg, #FFD700, #FFA500);
    }
    
    /* Mensagens de resultado */
    .result-success {
        background: linear-gradient(135deg, #00AA00, #008800);
        color: white;
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        font-size: 1.5em;
        animation: pulse 0.5s ease;
    }
    
    .result-failure {
        background: linear-gradient(135deg, #AA0000, #880000);
        color: white;
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        font-size: 1.5em;
        animation: shake 0.5s ease;
    }
    
    @keyframes pulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.05); }
    }
    
    @keyframes shake {
        0%, 100% { transform: translateX(0); }
        25% { transform: translateX(-10px); }
        75% { transform: translateX(10px); }
    }
    
    /* Botões de controle */
    .control-button > button {
        background: linear-gradient(135deg, #FFD700, #FFA500);
        color: #1a1f3a;
        font-weight: bold;
        font-size: 1.1em;
        padding: 10px 20px;
        border-radius: 25px;
        border: none;
        transition: all 0.3s ease;
        margin: 5px;
    }
    
    .control-button > button:hover {
        transform: scale(1.05);
        box-shadow: 0 5px 20px rgba(255,215,0,0.5);
    }
    
    /* Input do jogador */
    .player-input {
        text-align: center;
        margin: 20px 0;
    }
    
    .player-input label {
        color: #FFD700;
        font-size: 1.2em;
    }
    
    /* Info adicional */
    .info-text {
        color: #FFA500;
        text-align: center;
        font-size: 0.9em;
        margin-top: 20px;
    }
    
    /* Nível de dificuldade */
    .difficulty {
        display: inline-block;
        padding: 5px 10px;
        border-radius: 20px;
        font-size: 0.8em;
        font-weight: bold;
        margin-bottom: 10px;
        text-align: center;
    }
    
    .difficulty-1 { background: #00AA00; color: white; }
    .difficulty-2 { background: #FFA500; color: white; }
    .difficulty-3 { background: #FF6600; color: white; }
    .difficulty-4 { background: #FF0000; color: white; }
    
    /* Divider */
    hr {
        border-color: #FFD700;
        margin: 20px 0;
    }
</style>
""", unsafe_allow_html=True)

# ==================== FUNÇÕES AUXILIARES ====================

def format_premium(value):
    """Formata o valor do prêmio"""
    if value >= 1000000:
        return f"R$ {value/1000000:.1f} Milhão"
    return f"R$ {value:,.0f}".replace(",", ".")

def init_session_state():
    """Inicializa o estado da sessão"""
    if 'game_active' not in st.session_state:
        st.session_state.game_active = False
    if 'game_started' not in st.session_state:
        st.session_state.game_started = False
    if 'current_question' not in st.session_state:
        st.session_state.current_question = 0
    if 'current_prize' not in st.session_state:
        st.session_state.current_prize = 0
    if 'player_name' not in st.session_state:
        st.session_state.player_name = ""
    if 'ranking' not in st.session_state:
        st.session_state.ranking = []
    if 'answer_locked' not in st.session_state:
        st.session_state.answer_locked = False
    if 'game_over' not in st.session_state:
        st.session_state.game_over = False
    if 'winner' not in st.session_state:
        st.session_state.winner = False
    if 'skip_count' not in st.session_state:
        st.session_state.skip_count = 2  # 2 pulos por jogo
    if 'cards_used' not in st.session_state:
        st.session_state.cards_used = False
    if 'eliminated_options' not in st.session_state:
        st.session_state.eliminated_options = []
    if 'current_help' not in st.session_state:
        st.session_state.current_help = None
    if 'question_answered' not in st.session_state:
        st.session_state.question_answered = False

def add_to_ranking(name, prize):
    """Adiciona jogador ao ranking"""
    st.session_state.ranking.append({
        'name': name,
        'prize': prize,
        'date': datetime.now().strftime("%d/%m/%Y %H:%M")
    })
    # Ordena ranking por prêmio
    st.session_state.ranking.sort(key=lambda x: x['prize'], reverse=True)
    # Mantém apenas os top 10
    st.session_state.ranking = st.session_state.ranking[:10]

def reset_game():
    """Reinicia o jogo"""
    st.session_state.game_active = True
    st.session_state.game_started = True
    st.session_state.current_question = 0
    st.session_state.current_prize = 0
    st.session_state.answer_locked = False
    st.session_state.game_over = False
    st.session_state.winner = False
    st.session_state.skip_count = 2
    st.session_state.cards_used = False
    st.session_state.eliminated_options = []
    st.session_state.current_help = None
    st.session_state.question_answered = False

def skip_question():
    """Pula a pergunta atual"""
    if st.session_state.skip_count > 0 and not st.session_state.answer_locked:
        st.session_state.skip_count -= 1
        st.session_state.current_question += 1
        st.session_state.eliminated_options = []
        st.session_state.current_help = None
        st.success(f"✅ Pergunta pulada! Restam {st.session_state.skip_count} pulo(s)")
        time.sleep(1)
        st.rerun()

def use_help_card(card_type):
    """Usa carta de ajuda"""
    if st.session_state.cards_used or st.session_state.answer_locked:
        return
    
    st.session_state.cards_used = True
    current_q = PERGUNTAS[st.session_state.current_question]
    correct_answer = current_q['resposta_correta']
    
    # Obtém todas as alternativas
    all_options = list(current_q['alternativas'].keys())
    wrong_options = [opt for opt in all_options if opt != correct_answer]
    
    if card_type == 1:  # Elimina 1 alternativa errada
        eliminar = random.sample(wrong_options, min(1, len(wrong_options)))
        st.session_state.eliminated_options = eliminar
        st.info(f"🎴 Carta usada! Alternativa {', '.join(eliminar)} foi eliminada!")
        
    elif card_type == 2:  # Elimina 2 alternativas erradas
        eliminar = random.sample(wrong_options, min(2, len(wrong_options)))
        st.session_state.eliminated_options = eliminar
        st.info(f"🎴 Carta usada! Alternativas {', '.join(eliminar)} foram eliminadas!")
        
    elif card_type == 3:  # Elimina 3 alternativas erradas
        eliminar = random.sample(wrong_options, min(3, len(wrong_options)))
        st.session_state.eliminated_options = eliminar
        st.info(f"🎴 Carta usada! Alternativas {', '.join(eliminar)} foram eliminadas!")
    
    st.session_state.current_help = card_type
    time.sleep(1.5)
    st.rerun()

def give_up():
    """Desiste do jogo"""
    st.session_state.game_active = False
    st.session_state.game_over = True
    add_to_ranking(st.session_state.player_name, st.session_state.current_prize)
    st.warning(f"🏳️ Você desistiu! Levou {format_premium(st.session_state.current_prize)} para casa!")
    time.sleep(2)
    st.rerun()

def check_answer(selected_option):
    """Verifica se a resposta está correta"""
    if st.session_state.answer_locked or st.session_state.game_over or st.session_state.winner:
        return
    
    st.session_state.answer_locked = True
    
    current_q = PERGUNTAS[st.session_state.current_question]
    is_correct = (selected_option == current_q['resposta_correta'])
    
    if is_correct:
        # Resposta correta
        st.balloons()
        st.session_state.current_prize = PREMIO_VALORES[st.session_state.current_question]
        
        if st.session_state.current_question + 1 >= TOTAL_PERGUNTAS:
            # Vitória!
            st.session_state.winner = True
            st.session_state.game_active = False
            add_to_ranking(st.session_state.player_name, st.session_state.current_prize)
            st.success(f"🎉 PARABÉNS! Você ganhou {format_premium(st.session_state.current_prize)}! 🎉")
            time.sleep(2)
            st.rerun()
        else:
            # Avança para próxima pergunta
            st.session_state.current_question += 1
            st.session_state.answer_locked = False
            st.session_state.eliminated_options = []
            st.session_state.cards_used = False
            st.session_state.current_help = None
            st.rerun()
    else:
        # Resposta errada
        st.error(f"❌ RESPOSTA ERRADA! Você perdeu tudo! ❌")
        time.sleep(2)
        st.session_state.game_over = True
        st.session_state.game_active = False
        add_to_ranking(st.session_state.player_name, 0)
        st.rerun()

# ==================== INTERFACE PRINCIPAL ====================

init_session_state()

# Layout em colunas
col_left, col_center, col_right = st.columns([1, 2, 1])

with col_center:
    # Título
    st.markdown('<div class="main-title">💰 SHOW DO MILHÃO 💰</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">ESPECIAL PROTHEUS - 47 PERGUNTAS</div>', unsafe_allow_html=True)
    
    # Tela inicial
    if not st.session_state.game_started:
        st.markdown('<div class="player-input">', unsafe_allow_html=True)
        player_name = st.text_input("Digite seu nome:", max_chars=30)
        st.markdown('</div>', unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🎮 COMEÇAR JOGO 🎮", key="start", use_container_width=True):
                if player_name:
                    st.session_state.player_name = player_name
                    reset_game()
                    st.rerun()
                else:
                    st.warning("Por favor, digite seu nome!")
    
    # Jogo em andamento
    elif st.session_state.game_active and not st.session_state.game_over and not st.session_state.winner:
        current_q = PERGUNTAS[st.session_state.current_question]
        
        # Informações da pergunta
        nivel_text = {1: "FÁCIL", 2: "MÉDIO", 3: "DIFÍCIL", 4: "ESPECIALISTA"}
        nivel_class = f"difficulty difficulty-{current_q['nivel']}"
        
        st.markdown(f'<div class="question-number">Pergunta {st.session_state.current_question + 1} de {TOTAL_PERGUNTAS}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="{nivel_class}" style="text-align: center;">NÍVEL: {nivel_text[current_q["nivel"]]}</div>', unsafe_allow_html=True)
        
        # Barra de progresso
        progress = (st.session_state.current_question) / TOTAL_PERGUNTAS
        st.progress(progress)
        
        # Cartão da pergunta
        st.markdown('<div class="question-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="question-text">{current_q["pergunta"]}</div>', unsafe_allow_html=True)
        
        # Botões das alternativas (com opções eliminadas ocultas)
        for letra, texto in current_q["alternativas"].items():
            if letra not in st.session_state.eliminated_options:
                if st.button(f"{letra}. {texto}", key=f"q_{st.session_state.current_question}_{letra}", use_container_width=True):
                    check_answer(letra)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Botões de ajuda
        st.markdown('<div style="display: flex; gap: 10px; justify-content: center; margin: 20px 0;">', unsafe_allow_html=True)
        
        col_help1, col_help2, col_help3, col_help4 = st.columns(4)
        
        with col_help1:
            if st.button(f"⏭️ PULAR ({st.session_state.skip_count}/2)", key="skip", use_container_width=True, disabled=st.session_state.skip_count == 0 or st.session_state.answer_locked):
                skip_question()
        
        with col_help2:
            if st.button("🎴 CARTA -1", key="card1", use_container_width=True, disabled=st.session_state.cards_used or st.session_state.answer_locked):
                use_help_card(1)
        
        with col_help3:
            if st.button("🎴 CARTA -2", key="card2", use_container_width=True, disabled=st.session_state.cards_used or st.session_state.answer_locked):
                use_help_card(2)
        
        with col_help4:
            if st.button("🎴 CARTA -3", key="card3", use_container_width=True, disabled=st.session_state.cards_used or st.session_state.answer_locked):
                use_help_card(3)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Botão desistir
        col_desist1, col_desist2, col_desist3 = st.columns([1, 2, 1])
        with col_desist2:
            if st.button("🏳️ DESISTIR E LEVAR O PRÊMIO 🏳️", key="giveup", use_container_width=True):
                give_up()
        
        # Painel do prêmio atual
        st.markdown('<div class="prize-panel">', unsafe_allow_html=True)
        st.markdown('<div class="prize-label">PRÊMIO ATUAL</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="prize-value">{format_premium(st.session_state.current_prize)}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Dica
        if st.session_state.skip_count > 0:
            st.markdown(f'<div class="info-text">⭐ Você tem {st.session_state.skip_count} pulo(s) disponível(is)! Use com sabedoria! ⭐</div>', unsafe_allow_html=True)
        if not st.session_state.cards_used:
            st.markdown('<div class="info-text">🎴 Você pode usar UMA carta de ajuda por pergunta! 🎴</div>', unsafe_allow_html=True)
    
    # Tela de vitória
    elif st.session_state.winner:
        st.markdown('<div class="result-success">', unsafe_allow_html=True)
        st.markdown(f"🎉🏆 **MILHONÁRIO!** 🏆🎉")
        st.markdown(f"**{st.session_state.player_name}** você ganhou **{format_premium(st.session_state.current_prize)}**!")
        st.markdown(f"🎊 PARABÉNS! Você respondeu todas as {TOTAL_PERGUNTAS} perguntas! 🎊")
        st.markdown('</div>', unsafe_allow_html=True)
        
        if st.button("🔄 JOGAR NOVAMENTE 🔄", key="play_again_win", use_container_width=True):
            st.session_state.game_started = False
            st.session_state.game_active = False
            st.session_state.game_over = False
            st.session_state.winner = False
            st.session_state.current_question = 0
            st.session_state.current_prize = 0
            st.session_state.answer_locked = False
            st.session_state.skip_count = 2
            st.session_state.cards_used = False
            st.session_state.eliminated_options = []
            st.rerun()
    
    # Tela de derrota
    elif st.session_state.game_over:
        st.markdown('<div class="result-failure">', unsafe_allow_html=True)
        if st.session_state.current_prize > 0:
            st.markdown(f"💔 **GAME OVER!** 💔")
            st.markdown(f"**{st.session_state.player_name}** você errou na pergunta {st.session_state.current_question + 1}!")
            st.markdown(f"Você perdeu **{format_premium(st.session_state.current_prize)}**")
        else:
            st.markdown(f"💔 **GAME OVER!** 💔")
            st.markdown(f"**{st.session_state.player_name}** você errou na primeira pergunta!")
            st.markdown(f"Infelizmente você não ganhou nada!")
        st.markdown('</div>', unsafe_allow_html=True)
        
        if st.button("🔄 TENTAR NOVAMENTE 🔄", key="play_again_loss", use_container_width=True):
            st.session_state.game_started = False
            st.session_state.game_active = False
            st.session_state.game_over = False
            st.session_state.winner = False
            st.session_state.current_question = 0
            st.session_state.current_prize = 0
            st.session_state.answer_locked = False
            st.session_state.skip_count = 2
            st.session_state.cards_used = False
            st.session_state.eliminated_options = []
            st.rerun()

# Ranking lateral
with col_right:
    if st.session_state.ranking:
        st.markdown('<div class="ranking-panel">', unsafe_allow_html=True)
        st.markdown('<div class="ranking-title">🏆 RANKING 🏆</div>', unsafe_allow_html=True)
        
        for i, player in enumerate(st.session_state.ranking[:5]):
            st.markdown(f"""
            <div class="ranking-item">
                <b>{i+1}º</b> {player['name']} - <span style="color:#FFD700">{format_premium(player['prize'])}</span><br>
                <small style="color:#888">{player['date']}</small>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Painel de premiação completa
    st.markdown('<div class="prize-panel">', unsafe_allow_html=True)
    st.markdown('<div class="prize-label">🏅 TABELA DE PRÊMIOS 🏅</div>', unsafe_allow_html=True)
    
    for i in range(min(TOTAL_PERGUNTAS, 15)):
        prize = PREMIO_VALORES[i]
        nivel = PERGUNTAS[i]['nivel']
        nivel_icon = {1: "🌟", 2: "⭐⭐", 3: "⭐⭐⭐", 4: "💎"}
        
        if i == st.session_state.current_question and st.session_state.game_active:
            st.markdown(f'<div style="color:#FFD700; font-weight:bold;">▶ {nivel_icon[nivel]} Pergunta {i+1}: {format_premium(prize)}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="color:#FFF;">{nivel_icon[nivel]} Pergunta {i+1}: {format_premium(prize)}</div>', unsafe_allow_html=True)
    
    if TOTAL_PERGUNTAS > 15:
        st.markdown(f'<div style="color:#888; text-align:center;">... e mais {TOTAL_PERGUNTAS - 15} perguntas</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# Informações do jogador (lado esquerdo)
with col_left:
    if st.session_state.game_started and st.session_state.player_name:
        st.markdown('<div class="ranking-panel">', unsafe_allow_html=True)
        st.markdown('<div class="ranking-title">👤 JOGADOR</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="color:#FFD700; font-size:1.2em; text-align:center;">{st.session_state.player_name}</div>', unsafe_allow_html=True)
        
        if st.session_state.skip_count > 0:
            st.markdown(f'<div style="color:#FFA500; text-align:center; margin-top:10px;">⏭️ Pulos restantes: {st.session_state.skip_count}</div>', unsafe_allow_html=True)
        
        if st.session_state.cards_used:
            st.markdown(f'<div style="color:#FF6600; text-align:center; margin-top:5px;">🎴 Carta de ajuda usada nesta pergunta</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Estatísticas
        st.markdown('<div class="ranking-panel">', unsafe_allow_html=True)
        st.markdown('<div class="ranking-title">📊 ESTATÍSTICAS</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="color:#FFF; text-align:center;">✅ Progresso: {st.session_state.current_question}/{TOTAL_PERGUNTAS}</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="color:#FFD700; text-align:center; margin-top:10px;">💰 Prêmio: {format_premium(st.session_state.current_prize)}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

# Rodapé
st.markdown("---")
st.markdown('<div style="text-align: center; color: #FFA500;">🎬 Show do Milhão - Edição Especial Protheus 🎬</div>', unsafe_allow_html=True)
st.markdown('<div style="text-align: center; color: #888; font-size: 0.8em;">✅ 2 pulos por jogo | 🎴 1 carta de ajuda por pergunta (elimina 1-3 alternativas erradas) | 🏳️ Desistência com prêmio atual</div>', unsafe_allow_html=True)