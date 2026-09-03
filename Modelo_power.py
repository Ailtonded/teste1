import pandas as pd
import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson
from pathlib import Path
from datetime import datetime

# ==============================================================================
# CONFIGURAÇÕES
# ==============================================================================

ARQUIVO_DADOS = 'jogos.csv'  # Nome do arquivo de entrada
PASTA_SAIDA = Path('output') # Pasta onde os resultados serão salvos

# ==============================================================================
# MÓDULO 1: DADOS
# ==============================================================================

def carregar_dados(caminho_arquivo: str) -> pd.DataFrame:
    """
    Carrega e trata o arquivo CSV histórico.
    Espera colunas: Temporada, Mandante, Gols Casa, Gols Visitante, Visitante, 
    Resultado, Odd Casa, Odd Empate, Odd Visitante, Data, Rodada.
    """
    caminho = Path(caminho_arquivo)
    
    if not caminho.exists():
        print(f"AVISO: Arquivo '{caminho_arquivo}' não encontrado.")
        print("Gerando dados fictícios para demonstração do sistema...")
        df = criar_dados_dummy()
        # Salva o dummy para referência
        df.to_csv(caminho_arquivo, index=False, sep=';', decimal=',')
        print(f"Arquivo dummy criado: {caminho_arquivo}")
    else:
        # Leitura considerando separador ';' e decimal ',' (padrão BR)
        df = pd.read_csv(caminho, sep=';', decimal=',')
        
    # Padronização de nomes de colunas
    df.columns = df.columns.str.strip().str.replace(' ', '_')
    
    # Conversão de datas
    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
    
    # Limpeza básica
    df = df.dropna(subset=['Data', 'Mandante', 'Visitante', 'Gols_Casa', 'Gols_Visitante'])
    
    # Garantir tipos numéricos para gols
    df['Gols_Casa'] = pd.to_numeric(df['Gols_Casa'], errors='coerce').fillna(0).astype(int)
    df['Gols_Visitante'] = pd.to_numeric(df['Gols_Visitante'], errors='coerce').fillna(0).astype(int)
    
    # Ordenação cronológica essencial para o loop temporal
    df = df.sort_values('Data').reset_index(drop=True)
    
    return df

def preparar_estruturas(df: pd.DataFrame) -> tuple:
    """
    Cria lista de times e mapa de índices para o vetor de otimização.
    """
    times = sorted(list(set(df['Mandante'].unique()) | set(df['Visitante'].unique())))
    time_to_idx = {time: i for i, time in enumerate(times)}
    return times, time_to_idx

def criar_dados_dummy() -> pd.DataFrame:
    """
    Gera um dataset fictício para testes se o arquivo real não existir.
    """
    datas = pd.to_datetime([
        '2025-06-10', '2025-06-10', 
        '2025-06-13', 
        '2025-06-14', '2025-06-14', 
        '2025-06-15'
    ])
    
    data = {
        'Temporada': [2025]*6,
        'Mandante': ['Flamengo', 'Palmeiras', 'Bodo/Glimt', 'Flamengo', 'Palmeiras', 'Bodo/Glimt'],
        'Gols Casa': [2, 1, 3, 1, 2, 0],
        'Gols Visitante': [0, 1, 1, 1, 0, 2],
        'Visitante': ['Vasco', 'Santos', 'Fredrikstad', 'Palmeiras', 'Flamengo', 'Vasco'],
        'Resultado': ['H', 'D', 'H', 'D', 'H', 'A'],
        'Odd Casa': [1.50, 1.80, 1.40, 2.10, 2.20, 1.90],
        'Odd Empate': [4.00, 3.50, 4.50, 3.20, 3.10, 3.50],
        'Odd Visitante': [6.00, 4.50, 8.00, 3.50, 3.30, 4.00],
        'Data': datas,
        'Rodada': [1, 1, 2, 3, 3, 4]
    }
    return pd.DataFrame(data)

# ==============================================================================
# MÓDULO 2: MODELO MATEMÁTICO
# ==============================================================================

def calcular_media_liga(df: pd.DataFrame) -> float:
    """Calcula a média de gols por time na liga."""
    if df.empty: return 0.0
    total_gols = df['Gols_Casa'].sum() + df['Gols_Visitante'].sum()
    total_jogos = len(df)
    return total_gols / (total_jogos * 2)

def funcao_objetivo(params: np.ndarray, df: pd.DataFrame, time_to_idx: dict, media_liga: float) -> float:
    """
    Função objetivo: Soma dos Quadrados dos Erros (SSE).
    Minimiza a diferença entre gols reais e gols esperados (Lambda).
    """
    n_times = len(time_to_idx)
    ataques = params[:n_times]
    defesas = params[n_times:]
    
    sse = 0.0
    
    # Vetorização para performance (evita loop lento em Python puro para grandes bases)
    # Porém, para clareza lógica e manutenção solicitada, mantemos o loop explícito:
    for _, row in df.iterrows():
        idx_casa = time_to_idx[row['Mandante']]
        idx_fora = time_to_idx[row['Visitante']]
        
        # Lambdas
        # LambdaCasa = Media + AtkCasa - DefFora
        lambda_casa = media_liga + ataques[idx_casa] - defesas[idx_fora]
        # LambdaFora = Media + AtkFora - DefCasa
        lambda_fora = media_liga + ataques[idx_fora] - defesas[idx_casa]
        
        # Proteção contra lambdas negativos
        lambda_casa = max(lambda_casa, 0.01)
        lambda_fora = max(lambda_fora, 0.01)
        
        # Erros
        sse += (row['Gols_Casa'] - lambda_casa) ** 2
        sse += (row['Gols_Visitante'] - lambda_fora) ** 2
        
    return sse

def otimizar_parametros(df: pd.DataFrame, time_to_idx: dict) -> dict:
    """
    Executa o Solver (scipy.optimize.minimize) para encontrar Ataque e Defesa.
    Aplica restrições de soma zero.
    """
    n_times = len(time_to_idx)
    media_liga = calcular_media_liga(df)
    
    # Chute inicial: zeros (média da liga)
    initial_guess = np.zeros(n_times * 2)
    
    # Restrições: Soma(Ataque) = 0 e Soma(Defesa) = 0
    # Passamos duas restrições de igualdade separadas para precisão
    constraints = [
        {'type': 'eq', 'fun': lambda p: np.sum(p[:n_times])},      # Soma Ataques = 0
        {'type': 'eq', 'fun': lambda p: np.sum(p[n_times:])}       # Soma Defesas = 0
    ]
    
    result = minimize(
        funcao_objetivo,
        initial_guess,
        args=(df, time_to_idx, media_liga),
        method='SLSQP',
        constraints=constraints,
        options={'maxiter': 1000, 'ftol': 1e-7}
    )
    
    # Montar dicionário de ratings
    params = result.x
    ratings = {}
    
    for time, idx in time_to_idx.items():
        atk = params[idx]
        defe = params[n_times + idx]
        ratings[time] = {
            'Ataque': atk,
            'Defesa': defe,
            'PowerRank': atk - defe # Fórmula principal
        }
        
    return ratings, media_liga

# ==============================================================================
# MÓDULO 3: PREVISÕES
# ==============================================================================

def calcular_probabilidades_poisson(lambda_casa: float, lambda_fora: float) -> dict:
    """
    Calcula probabilidades de resultado baseado em distribuição de Poisson.
    """
    # Matriz de probabilidades (0 a 6 gols é suficiente para precisão)
    max_gols = 6
    probs = np.zeros((max_gols + 1, max_gols + 1))
    
    for i in range(max_gols + 1):
        for j in range(max_gols + 1):
            probs[i, j] = poisson.pmf(i, lambda_casa) * poisson.pmf(j, lambda_fora)
            
    prob_h = np.sum(np.triu(probs, k=1)) # Casa marca mais que visitante
    prob_a = np.sum(np.tril(probs, k=-1)) # Visitante marca mais
    prob_d = np.sum(np.diag(probs))       # Diagonal = empate
    
    prob_over25 = 1.0 - (probs[0,0] + probs[0,1] + probs[1,0] + probs[1,1])
    
    return {
        'Prob_H': prob_h,
        'Prob_D': prob_d,
        'Prob_A': prob_a,
        'Prob_Over25': prob_over25
    }

def processar_previsoes(jogos_dia: pd.DataFrame, ratings: dict, media_liga: float) -> pd.DataFrame:
    """
    Gera previsões para um conjunto de jogos usando ratings estáticos.
    """
    results = []
    
    for _, row in jogos_dia.iterrows():
        m = row['Mandante']
        v = row['Visitante']
        
        # Se o time não tem rating (novo time), assume neutro (0)
        r_m = ratings.get(m, {'Ataque': 0, 'Defesa': 0, 'PowerRank': 0})
        r_v = ratings.get(v, {'Ataque': 0, 'Defesa': 0, 'PowerRank': 0})
        
        atk_m, def_m, pr_m = r_m['Ataque'], r_m['Defesa'], r_m['PowerRank']
        atk_v, def_v, pr_v = r_v['Ataque'], r_v['Defesa'], r_v['PowerRank']
        
        # Cálculo dos Lambdas
        lambda_casa = max(media_liga + atk_m - def_v, 0.01)
        lambda_fora = max(media_liga + atk_v - def_m, 0.01)
        
        # Probabilidades
        probs = calcular_probabilidades_poisson(lambda_casa, lambda_fora)
        
        registro = row.to_dict()
        registro.update({
            'Ataque_Casa': atk_m, 'Defesa_Casa': def_m, 'PowerRank_Casa': pr_m,
            'Ataque_Fora': atk_v, 'Defesa_Fora': def_v, 'PowerRank_Fora': pr_v,
            'Lambda_Casa': lambda_casa, 'Lambda_Fora': lambda_fora,
            'Prob_H': probs['Prob_H'], 'Prob_D': probs['Prob_D'], 'Prob_A': probs['Prob_A'],
            'Media_Liga': media_liga
        })
        results.append(registro)
        
    return pd.DataFrame(results)

# ==============================================================================
# MÓDULO 4: SNAPSHOTS E EXECUÇÃO PRINCIPAL
# ==============================================================================

def main():
    print("=== MOTOR DE POWER RANK FUTEBOL ===")
    
    # 1. Carregar Base Completa
    df_base = carregar_dados(ARQUIVO_DADOS)
    
    # Mapear todos os times únicos da base (para manter índice fixo)
    todos_times, time_to_idx = preparar_estruturas(df_base)
    print(f"Times identificados: {len(todos_times)}")
    print(f"Total de jogos na base: {len(df_base)}")
    
    # Preparar pastas
    PASTA_SAIDA.mkdir(exist_ok=True)
    
    # Variáveis de estado
    df_historico = pd.DataFrame(columns=df_base.columns) # Dados passados (D-1)
    ratings_atuais = {}      # Parâmetros vigentes
    media_liga_atual = 0.0   # Média vigente
    
    # Acumuladores de saída
    lista_snapshots = []
    lista_previsoes = []
    
    # 2. Loop Temporal (Por Data)
    datas_unicas = np.sort(df_base['Data'].unique())
    
    print("\nIniciando processamento temporal...")
    
    for data_alvo in datas_unicas:
        # A. Filtrar jogos do dia
        jogos_hoje = df_base[df_base['Data'] == data_alvo].copy()
        
        # B. Gerar Previsões (usando dados até ontem)
        if not ratings_atuais:
            # Primeiro dia: sem histórico, não há previsão
            pass
        else:
            prevs = processar_previsoes(jogos_hoje, ratings_atuais, media_liga_atual)
            lista_previsoes.append(prevs)
        
        # C. Atualizar Histórico (incorporar jogos de hoje)
        df_historico = pd.concat([df_historico, jogos_hoje], ignore_index=True)
        
        # D. Recalcular Modelo (Otimização)
        # Nota: A otimização pode demorar alguns segundos dependendo do tamanho do histórico
        ratings_atuais, media_liga_atual = otimizar_parametros(df_historico, time_to_idx)
        
        # E. Salvar Snapshot
        data_str = data_alvo.strftime('%Y-%m-%d')
        n_jogos = len(df_historico)
        temporada = jogos_hoje['Temporada'].iloc[0] # Pega a temporada do jogo atual
        
        for time, params in ratings_atuais.items():
            lista_snapshots.append({
                'DataSnapshot': data_str,
                'Time': time,
                'Ataque': params['Ataque'],
                'Defesa': params['Defesa'],
                'PowerRank': params['PowerRank'],
                'Temporada': temporada,
                'N_Jogos_Utilizados': n_jogos
            })
            
        print(f"Processado: {data_str} | Jogos Acumulados: {n_jogos} | Média Liga: {media_liga_atual:.3f}")

    # 3. Finalização e Exportação
    print("\nExportando arquivos...")
    
    # Snapshots
    df_snap = pd.DataFrame(lista_snapshots)
    df_snap.to_csv(PASTA_SAIDA / 'snapshots.csv', index=False, sep=';', decimal=',')
    
    # Previsões
    if lista_previsoes:
        df_prev = pd.concat(lista_previsoes, ignore_index=True)
        # Ordenar colunas para melhor visualização
        cols_ordenadas = [
            'Data', 'Mandante', 'Visitante', 'Gols_Casa', 'Gols_Visitante', 'Resultado',
            'PowerRank_Casa', 'PowerRank_Fora', 'Lambda_Casa', 'Lambda_Fora',
            'Prob_H', 'Prob_D', 'Prob_A', 'Odd_Casa', 'Odd_Empate', 'Odd_Visitante'
        ]
        # Filtrar apenas colunas que existem
        cols_existentes = [c for c in cols_ordenadas if c in df_prev.columns]
        df_prev[cols_existentes].to_csv(PASTA_SAIDA / 'previsoes.csv', index=False, sep=';', decimal=',')
    
    # Ranking Atual
    ranking_final = df_snap[df_snap['DataSnapshot'] == df_snap['DataSnapshot'].max()].copy()
    ranking_final = ranking_final.sort_values('PowerRank', ascending=False)
    ranking_final.to_csv(PASTA_SAIDA / 'ranking_atual.csv', index=False, sep=';', decimal=',')
    
    print(f"Processo concluído. Arquivos salvos em '{PASTA_SAIDA}'.")

if __name__ == "__main__":
    main()