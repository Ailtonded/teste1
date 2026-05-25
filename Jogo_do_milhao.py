import streamlit as st
import random
import base64
import time

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DA PÁGINA
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Show do Milhão - Protheus",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ═══════════════════════════════════════════════════════════════════════════════
# LISTA DE PERGUNTAS (Fornecida pelo usuário)
# ═══════════════════════════════════════════════════════════════════════════════
PERGUNTAS_ORIGINAIS = [
  {
    "pergunta": "Qual é a principal função da tabela SX3 no Protheus?",
    "alternativas": {
      "A": "Armazenar pedidos de venda",
      "B": "Definir os campos das tabelas do sistema",
      "C": "Registrar movimentações financeiras",
      "D": "Cadastrar usuários",
      "E": "Controlar backups"
    },
    "resposta_correta": "B"
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
    "resposta_correta": "B"
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
    "resposta_correta": "C"
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
    "resposta_correta": "C"
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
    "resposta_correta": "A"
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
    "resposta_correta": "C"
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
    "resposta_correta": "B"
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
    "resposta_correta": "A"
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
    "resposta_correta": "A"
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
    "resposta_correta": "A"
  },
  {
    "pergunta": "Qual tabela armazena títulos a pagar?",
    "alternativas": {
      "A": "SE1",
      "B": "SE2",
      "C": "SD2",
      "D": "SB2",
      "E": "SC6"
    },
    "resposta_correta": "B"
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
    "resposta_correta": "A"
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
    "resposta_correta": "A"
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
    "resposta_correta": "A"
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
    "resposta_correta": "A"
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
    "resposta_correta": "A"
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
    "resposta_correta": "C"
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
    "resposta_correta": "A"
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
    "resposta_correta": "E"
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
    "resposta_correta": "A"
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
    "resposta_correta": "C"
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
    "resposta_correta": "B"
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
    "resposta_correta": "A"
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
    "resposta_correta": "C"
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
    "resposta_correta": "D"
  },
  {
    "pergunta": "Qual banco de dados é amplamente usado com Protheus?",
    "alternativas": {
      "A": "Oracle",
      "B": "SQL Server",
      "C": "PostgreSQL",
      "D": "DBAccess",
      "E": "Todas as anteriores"
    },
    "resposta_correta": "E"
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
    "resposta_correta": "B"
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
    "resposta_correta": "A"
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
    "resposta_correta": "B"
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
    "resposta_correta": "C"
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
    "resposta_correta": "A"
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
    "resposta_correta": "C"
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
    "resposta_correta": "A"
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
    "resposta_correta": "A"
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
    "resposta_correta": "A"
  },
  {
    "pergunta": "Qual tabela normalmente armazena natureza financeira?",
    "alternativas": {
      "A": "SED",
      "B": "SB1",
      "C": "SC5",
      "D": "SA1",
      "E": "SX5"
    },
    "resposta_correta": "A"
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
    "resposta_correta": "B"
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
    "resposta_correta": "A"
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
    "resposta_correta": "B"
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
    "resposta_correta": "A"
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
    "resposta_correta": "C"
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
    "resposta_correta": "A"
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
    "resposta_correta": "A"
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
    "resposta_correta": "B"
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
    "resposta_correta": "A"
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
    "resposta_correta": "A"
  }
]

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES DE JOGO
# ═══════════════════════════════════════════════════════════════════════════════
# Função para gerar valores de prêmio crescentes
def gerar_premios(total_perguntas, valor_maximo=1000000):
    premios = []
    incremento = valor_maximo / total_perguntas
    for i in range(total_perguntas):
        valor = int((i + 1) * incremento)
        # Arredondar para números mais "apresentáveis"
        if valor >= 1000000:
            valor = 1000000
        elif valor >= 100000:
            valor = round(valor / 10000) * 10000
        elif valor >= 1000:
            valor = round(valor / 1000) * 1000
        premios.append(valor)
    return premios

VALORES_PREMIO = gerar_premios(len(PERGUNTAS_ORIGINAIS))

# ═══════════════════════════════════════════════════════════════════════════════
# CSS CUSTOMIZADO - VISUAL DO GAME SHOW
# ═══════════════════════════════════════════════════════════════════════════════
def load_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;600;700&family=Roboto:wght@400;500;700&display=swap');
        
        /* Fundo principal */
        .stApp {
            background: linear-gradient(135deg, #0a1628 0%, #1a2a4a 30%, #0d1f3c 60%, #051025 100%);
            background-attachment: fixed;
        }
        
        /* Esconder menu padrão */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* Container centralizado */
        .main .block-container {
            padding: 2rem 3rem;
        }
        
        /* Título Principal */
        .title-main {
            font-family: 'Oswald', sans-serif;
            font-size: 4rem;
            font-weight: 700;
            text-align: center;
            background: linear-gradient(180deg, #FFD700 0%, #FFA500 50%, #FF8C00 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 5px;
            letter-spacing: 4px;
            animation: glow 2s ease-in-out infinite alternate;
        }
        
        .subtitle {
            font-family: 'Roboto', sans-serif;
            font-size: 1.2rem;
            color: #87CEEB;
            text-align: center;
            margin-bottom: 30px;
            letter-spacing: 2px;
        }
        
        /* Card do jogo */
        .game-card {
            background: linear-gradient(145deg, rgba(20, 40, 80, 0.9), rgba(10, 25, 50, 0.95));
            border: 3px solid #FFD700;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 0 50px rgba(255, 215, 0, 0.2);
            margin-bottom: 20px;
        }
        
        /* Painel de prêmio */
        .prize-panel {
            background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
            border: 3px solid #FFD700;
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            margin-bottom: 30px;
            box-shadow: 0 0 25px rgba(255, 215, 0, 0.3);
        }
        
        .prize-label {
            font-family: 'Roboto', sans-serif;
            font-size: 0.9rem;
            color: #87CEEB;
            text-transform: uppercase;
            letter-spacing: 3px;
        }
        
        .prize-value {
            font-family: 'Oswald', sans-serif;
            font-size: 4rem;
            font-weight: 700;
            color: #FFD700;
            text-shadow: 0 0 20px rgba(255, 215, 0, 0.5);
        }
        
        /* Pergunta */
        .question-container {
            background: linear-gradient(180deg, rgba(30, 60, 114, 0.8), rgba(20, 40, 80, 0.9));
            border: 2px solid #4169E1;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 25px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
        }
        
        .question-number {
            font-family: 'Oswald', sans-serif;
            font-size: 1rem;
            color: #FFD700;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-bottom: 10px;
        }
        
        .question-text {
            font-family: 'Roboto', sans-serif;
            font-size: 1.4rem;
            color: #FFFFFF;
            line-height: 1.6;
            text-align: center;
        }
        
        /* Alternativas - Grid */
        .alternatives-container {
            display: grid;
            grid-template-columns: 1fr;
            gap: 12px;
            margin-top: 25px;
        }
        
        /* Botões Streamlit customizados */
        .stButton button {
            width: 100%;
            background: linear-gradient(180deg, #1e3a5f 0%, #0d2137 100%);
            border: 2px solid #4169E1;
            border-radius: 12px;
            padding: 16px 25px;
            font-family: 'Roboto', sans-serif;
            font-size: 1.1rem;
            color: #FFFFFF;
            transition: all 0.3s ease;
            text-align: left;
        }
        
        .stButton button:hover {
            background: linear-gradient(180deg, #2a4a6f 0%, #1a3a57 100%);
            border-color: #FFD700;
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(255, 215, 0, 0.3);
            color: #FFD700;
        }
        
        .stButton button:focus {
            background: linear-gradient(180deg, #2a4a6f 0%, #1a3a57 100%);
            border-color: #FFD700;
            color: #FFD700;
        }
        
        /* Botão principal (Começar/Reiniciar) */
        .main-button button {
            background: linear-gradient(180deg, #FFD700 0%, #FFA500 50%, #FF8C00 100%) !important;
            color: #000000 !important;
            font-family: 'Oswald', sans-serif !important;
            font-weight: 700;
            font-size: 1.5rem !important;
            text-align: center !important;
            border: none !important;
            padding: 20px 50px !important;
            border-radius: 15px !important;
            letter-spacing: 2px;
            box-shadow: 0 5px 25px rgba(255, 215, 0, 0.4);
        }
        
        .main-button button:hover {
            transform: translateY(-3px) scale(1.02) !important;
            box-shadow: 0 8px 35px rgba(255, 215, 0, 0.6) !important;
        }
        
        /* Input de texto */
        .stTextInput input {
            background: rgba(30, 60, 114, 0.8);
            border: 2px solid #4169E1;
            border-radius: 10px;
            color: #FFFFFF;
            font-family: 'Roboto', sans-serif;
            font-size: 1.2rem;
            padding: 15px;
            text-align: center;
        }
        
        .stTextInput input:focus {
            border-color: #FFD700;
            box-shadow: 0 0 15px rgba(255, 215, 0, 0.3);
        }
        
        .stTextInput label {
            color: #87CEEB !important;
            font-family: 'Roboto', sans-serif;
            font-size: 1.1rem;
            text-align: center;
            display: block;
        }
        
        /* Resultados */
        .result-win {
            font-family: 'Oswald', sans-serif;
            font-size: 3.5rem;
            font-weight: 700;
            color: #00FF00;
            text-shadow: 0 0 30px rgba(0, 255, 0, 0.5);
            text-align: center;
        }
        
        .result-lose {
            font-family: 'Oswald', sans-serif;
            font-size: 3.5rem;
            font-weight: 700;
            color: #FF4444;
            text-shadow: 0 0 30px rgba(255, 68, 68, 0.5);
            text-align: center;
        }
        
        /* Ranking */
        .ranking-container {
            background: linear-gradient(145deg, rgba(20, 40, 80, 0.95), rgba(10, 25, 50, 0.98));
            border: 2px solid #FFD700;
            border-radius: 15px;
            padding: 20px;
        }
        
        .ranking-title {
            font-family: 'Oswald', sans-serif;
            font-size: 1.5rem;
            color: #FFD700;
            text-align: center;
            margin-bottom: 15px;
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        
        .ranking-item {
            display: flex;
            justify-content: space-between;
            padding: 10px;
            margin: 5px 0;
            background: rgba(65, 105, 225, 0.2);
            border-radius: 8px;
            border-left: 4px solid #FFD700;
            font-family: 'Roboto', sans-serif;
            color: #FFFFFF;
        }
        
        /* Barra de progresso */
        .stProgress > div > div > div > div {
            background: linear-gradient(90deg, #4169E1, #FFD700);
        }
        
        /* Linha divisória */
        .divider {
            height: 2px;
            background: linear-gradient(90deg, transparent, #FFD700, transparent);
            margin: 25px 0;
        }
        
        /* Animação de pulso */
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.05); }
            100% { transform: scale(1); }
        }
        
        .pulse-animation {
            animation: pulse 2s infinite;
        }
        
        /* Badge de status */
        .status-badge {
            display: inline-block;
            background: rgba(65, 105, 225, 0.3);
            border: 1px solid #4169E1;
            border-radius: 20px;
            padding: 8px 20px;
            font-family: 'Roboto', sans-serif;
            color: #87CEEB;
            font-size: 0.9rem;
        }
    </style>
    """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# GERENCIAMENTO DE ESTADO (SESSION STATE)
# ═══════════════════════════════════════════════════════════════════════════════
def init_state():
    if 'game_state' not in st.session_state:
        st.session_state.game_state = 'start'  # start, playing, game_over, victory
    if 'current_question' not in st.session_state:
        st.session_state.current_question = 0
    if 'player_name' not in st.session_state:
        st.session_state.player_name = ""
    if 'ranking' not in st.session_state:
        st.session_state.ranking = []
    if 'questions' not in st.session_state:
        # Embaralha as perguntas para cada novo jogo
        st.session_state.questions = random.sample(PERGUNTAS_ORIGINAIS, len(PERGUNTAS_ORIGINAIS))
    if 'correct_answers' not in st.session_state:
        st.session_state.correct_answers = 0

# ═══════════════════════════════════════════════════════════════════════════════
# FUNÇÕES AUXILIARES
# ═══════════════════════════════════════════════════════════════════════════════
def format_currency(value):
    """Formata valor para moeda brasileira"""
    return f"R$ {value:,.0f}".replace(",", ".")

def add_to_ranking(name, score, questions_answered):
    """Adiciona jogador ao ranking"""
    st.session_state.ranking.append({
        'name': name,
        'score': score,
        'questions': questions_answered,
        'timestamp': time.strftime("%d/%m %H:%M")
    })
    # Ordena por pontuação
    st.session_state.ranking.sort(key=lambda x: x['score'], reverse=True)
    # Mantém apenas top 10
    st.session_state.ranking = st.session_state.ranking[:10]

def reset_game():
    """Reinicia o jogo"""
    st.session_state.game_state = 'start'
    st.session_state.current_question = 0
    st.session_state.correct_answers = 0
    st.session_state.questions = random.sample(PERGUNTAS_ORIGINAIS, len(PERGUNTAS_ORIGINAIS))

# ═══════════════════════════════════════════════════════════════════════════════
# TELAS DO JOGO
# ═══════════════════════════════════════════════════════════════════════════════

def show_start_screen():
    """Tela inicial do jogo"""
    col1, col2, col3 = st.columns([1, 3, 1])
    
    with col2:
        st.markdown('<div class="game-card">', unsafe_allow_html=True)
        
        st.markdown('<h1 class="title-main">SHOW DO MILHÃO</h1>', unsafe_allow_html=True)
        st.markdown('<p class="subtitle">Conhecimento Protheus - ADVPL</p>', unsafe_allow_html=True)
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        # Input do nome
        name = st.text_input("Digite seu nome para começar:", placeholder="Seu nome aqui...")
        
        st.markdown('<div style="height: 20px;"></div>', unsafe_allow_html=True)
        
        # Botão começar
        if st.button("🎮 COMEÇAR JOGO", key="start_btn"):
            if name.strip():
                st.session_state.player_name = name.strip().upper()
                st.session_state.game_state = 'playing'
                st.rerun()
            else:
                st.warning("⚠️ Por favor, digite seu nome!")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Instruções
        st.markdown("""
        <div style="text-align: center; color: #87CEEB; font-family: 'Roboto', sans-serif; margin-top: 20px;">
            <p>📌 Responda corretamente para acumular o prêmio</p>
            <p>💰 Cada acerto aumenta seu prêmio</p>
            <p>❌ Uma resposta errada encerra o jogo</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Mostrar ranking se existir
        if st.session_state.ranking:
            st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
            show_ranking()

def show_game_screen():
    """Tela principal do jogo"""
    # Layout em colunas
    col_left, col_center, col_right = st.columns([1, 3, 1])
    
    # === Coluna Esquerda - Ranking ===
    with col_left:
        if st.session_state.ranking:
            st.markdown('<div class="ranking-container">', unsafe_allow_html=True)
            st.markdown('<p class="ranking-title">🏆 RANKING</p>', unsafe_allow_html=True)
            
            for i, player in enumerate(st.session_state.ranking[:5]):
                medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}º"
                st.markdown(f"""
                <div class="ranking-item">
                    <span>{medal} {player['name']}</span>
                    <span>{format_currency(player['score'])}</span>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    # === Coluna Central - Jogo ===
    with col_center:
        # Informações do jogador
        st.markdown(f"""
        <div style="text-align: center; margin-bottom: 10px;">
            <span class="status-badge">👤 {st.session_state.player_name}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Painel de prêmio atual
        current_idx = st.session_state.current_question
        current_prize = VALORES_PREMIO[current_idx] if current_idx < len(VALORES_PREMIO) else VALORES_PREMIO[-1]
        
        st.markdown(f"""
        <div class="prize-panel">
            <p class="prize-label">Prêmio Atual</p>
            <p class="prize-value">{format_currency(current_prize)}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Card da pergunta
        st.markdown('<div class="game-card">', unsafe_allow_html=True)
        
        # Número da pergunta e barra de progresso
        total_questions = len(st.session_state.questions)
        progress = (current_idx + 1) / total_questions
        
        st.markdown(f"""
        <p class="question-number">Pergunta {current_idx + 1} de {total_questions}</p>
        """, unsafe_allow_html=True)
        
        st.progress(progress)
        
        # Pergunta atual
        question_data = st.session_state.questions[current_idx]
        
        st.markdown(f"""
        <div class="question-container">
            <p class="question-text">{question_data['pergunta']}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Alternativas
        st.markdown('<div class="alternatives-container">', unsafe_allow_html=True)
        
        # Criar colunas para as alternativas (2 por linha)
        alt_keys = list(question_data['alternativas'].keys())
        
        for i in range(0, len(alt_keys), 2):
            cols = st.columns(2)
            for j in range(2):
                if i + j < len(alt_keys):
                    key = alt_keys[i + j]
                    text = question_data['alternativas'][key]
                    
                    with cols[j]:
                        # Botão da alternativa
                        if st.button(f" {key}: {text}", key=f"alt_{current_idx}_{key}"):
                            check_answer(key, question_data['resposta_correta'])
        
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Estatísticas
        st.markdown(f"""
        <div style="text-align: center; margin-top: 15px; color: #87CEEB; font-family: 'Roboto', sans-serif;">
            ✅ Acertos: {st.session_state.correct_answers} | 🎯 Progresso: {int(progress * 100)}%
        </div>
        """, unsafe_allow_html=True)
    
    # === Coluna Direita - Escada de Prêmios ===
    with col_right:
        st.markdown('<div class="ranking-container">', unsafe_allow_html=True)
        st.markdown('<p class="ranking-title">💰 PRÊMIOS</p>', unsafe_allow_html=True)
        
        # Mostrar próximos prêmios
        for i in range(min(5, len(VALORES_PREMIO) - current_idx)):
            idx = current_idx + i
            is_current = i == 0
            prize_val = VALORES_PREMIO[idx]
            
            style = "color: #FFD700; font-weight: bold; background: rgba(255, 215, 0, 0.2);" if is_current else "color: #87CEEB;"
            marker = "▶ " if is_current else "   "
            
            st.markdown(f"""
            <div style="padding: 8px; margin: 5px 0; border-radius: 5px; {style}">
                {marker}P{idx + 1}: {format_currency(prize_val)}
            </div>
            """, unsafe_allow_html=True)
        
        # Prêmio final
        if current_idx + 5 < len(VALORES_PREMIO):
            st.markdown(f"""
            <div style="padding: 8px; margin: 5px 0; border-radius: 5px; color: #FFD700; text-align: center;">
                ...<br>
                🏆 FINAL: R$ 1.000.000
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)

def check_answer(selected, correct):
    """Verifica a resposta e atualiza o estado"""
    if selected == correct:
        st.session_state.correct_answers += 1
        st.session_state.current_question += 1
        
        # Verifica se venceu
        if st.session_state.current_question >= len(st.session_state.questions):
            st.session_state.game_state = 'victory'
            add_to_ranking(
                st.session_state.player_name,
                1000000,  # Prêmio máximo
                st.session_state.current_question
            )
    else:
        # Errou - game over
        st.session_state.game_state = 'game_over'
        # Adiciona ao ranking com o prêmio da pergunta anterior
        prize = VALORES_PREMIO[st.session_state.current_question - 1] if st.session_state.current_question > 0 else 0
        add_to_ranking(
            st.session_state.player_name,
            prize,
            st.session_state.correct_answers
        )
    
    st.rerun()

def show_game_over_screen():
    """Tela de derrota"""
    col1, col2, col3 = st.columns([1, 3, 1])
    
    with col2:
        st.markdown('<div class="game-card" style="text-align: center;">', unsafe_allow_html=True)
        
        st.markdown('<h1 class="result-lose">FIM DE JOGO!</h1>', unsafe_allow_html=True)
        
        prize = VALORES_PREMIO[st.session_state.current_question - 1] if st.session_state.current_question > 0 else 0
        
        st.markdown(f"""
        <div style="margin: 30px 0;">
            <p style="color: #87CEEB; font-family: 'Roboto', sans-serif; font-size: 1.2rem;">
                😔 Infelizmente você errou, {st.session_state.player_name}!
            </p>
            <p style="color: #FFFFFF; font-family: 'Oswald', sans-serif; font-size: 1.5rem; margin-top: 20px;">
                Você conquistou:
            </p>
            <p style="color: #FFD700; font-family: 'Oswald', sans-serif; font-size: 3rem; font-weight: 700;">
                {format_currency(prize)}
            </p>
            <p style="color: #87CEEB; font-family: 'Roboto', sans-serif; margin-top: 10px;">
                📊 {st.session_state.correct_answers} respostas corretas
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        # Mostrar resposta correta
        question = st.session_state.questions[st.session_state.current_question]
        correct_key = question['resposta_correta']
        correct_text = question['alternativas'][correct_key]
        
        st.markdown(f"""
        <div style="background: rgba(0, 255, 0, 0.1); border: 1px solid #00FF00; border-radius: 10px; padding: 15px; margin: 20px 0;">
            <p style="color: #00FF00; font-family: 'Roboto', sans-serif; margin: 0;">
                ✅ Resposta correta: <strong>{correct_key}) {correct_text}</strong>
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        # Botão reiniciar
        if st.button("🔄 JOGAR NOVAMENTE", key="restart_lose"):
            reset_game()
            st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Ranking
        st.markdown('<div style="height: 20px;"></div>', unsafe_allow_html=True)
        show_ranking()

def show_victory_screen():
    """Tela de vitória"""
    col1, col2, col3 = st.columns([1, 3, 1])
    
    with col2:
        st.markdown('<div class="game-card" style="text-align: center;">', unsafe_allow_html=True)
        
        st.markdown('<h1 class="result-win">PARABÉNS!</h1>', unsafe_allow_html=True)
        st.markdown('<h2 style="color: #FFD700; font-family: Oswald;">VOCÊ É O CAMPEÃO!</h2>', unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style="margin: 30px 0;">
            <p style="color: #FFFFFF; font-family: 'Roboto', sans-serif; font-size: 1.3rem;">
                🎉 Incrível, {st.session_state.player_name}!
            </p>
            <p style="color: #87CEEB; font-family: 'Roboto', sans-serif; margin-top: 20px;">
                Você venceu o
            </p>
            <p style="color: #FFD700; font-family: 'Oswald', sans-serif; font-size: 4rem; font-weight: 700; animation: pulse 1s infinite;">
                SHOW DO MILHÃO!
            </p>
            <p style="color: #FFD700; font-family: 'Oswald', sans-serif; font-size: 3rem; font-weight: 700;">
                💰 {format_currency(1000000)} 💰
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        # Botão reiniciar
        if st.button("🔄 JOGAR NOVAMENTE", key="restart_win"):
            reset_game()
            st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Ranking
        st.markdown('<div style="height: 20px;"></div>', unsafe_allow_html=True)
        show_ranking()

def show_ranking():
    """Exibe o ranking dos melhores"""
    st.markdown('<div class="ranking-container">', unsafe_allow_html=True)
    st.markdown('<p class="ranking-title">🏆 TOP 10 JOGADORES</p>', unsafe_allow_html=True)
    
    if st.session_state.ranking:
        for i, player in enumerate(st.session_state.ranking):
            medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}º"
            
            st.markdown(f"""
            <div class="ranking-item">
                <span>{medal} {player['name']}</span>
                <span>{format_currency(player['score'])}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown('<p style="text-align: center; color: #87CEEB;">Nenhum jogador ainda.</p>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# FUNÇÃO PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    load_css()
    init_state()
    
    # Roteamento de telas
    if st.session_state.game_state == 'start':
        show_start_screen()
    elif st.session_state.game_state == 'playing':
        show_game_screen()
    elif st.session_state.game_state == 'game_over':
        show_game_over_screen()
    elif st.session_state.game_state == 'victory':
        show_victory_screen()

if __name__ == "__main__":
    main()