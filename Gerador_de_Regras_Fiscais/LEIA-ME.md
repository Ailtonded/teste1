# Facilitador Fiscal — versão web

Transforma XMLs de NF-e de saída em regras F2B e cadastros-base para o Configurador de Tributos (FISA170).

## Como usar
1. Tenha o Python 3.9 ou mais novo instalado (não precisa instalar bibliotecas).
2. Na pasta do programa, rode: `python servidor.py`
3. O navegador abre em http://127.0.0.1:8765. Importe os XMLs, escolha o CNPJ e clique em **Gerar cenários**.

Para pastas com dezenas de milhares de XMLs, use "Pasta grande no computador?" na tela Importar XML:
a leitura é feita direto no disco, sem envio pelo navegador.

## Arquivos
| Arquivo | Função |
|---|---|
| `servidor.py` | Backend: API JSON que usa o motor sem alterar nenhuma regra |
| `web/index.html` | Interface web |
| `gerador_cenarios.py` | Motor: leitura dos XMLs, modelo de decisão, regras, cadastros e validação. Também roda sozinho com a tela desktop: `python gerador_cenarios.py` |
| `padroes_configurador.md` | Base de conhecimento (códigos, dimensões, regras de negócio, cBenef, escrituração). Editável na tela **Padrões** |

## Telas
- **Visão geral**: indicadores, principais regras, dependências por tributo e cadastros necessários.
- **Importar XML**: arquivos, pastas, ZIP ou caminho local; CNPJ emitente; opções (regras de NCM por tributo, agrupamento, participante).
- **Cenários fiscais**: cada combinação de CFOP, finalidade, UF, participante e produto, e a regra que aciona em cada tributo.
- **Regras F2B**: todas as regras com filtro por tributo, cópia no layout F2B e exportação CSV. A visão
  **Detalhada** mostra a descrição de cada código e, na escrituração, o imposto, o CST, a incidência e a ação na nota. O detalhe mostra os campos, os cadastros vinculados e o trecho do XML real.
- **Cadastros-base**: perfis (F20), tipos de operação, bases (F27), alíquotas (F28), alíquotas por NCM/UF, escrituração (CJ2), produtos e clientes.
- **Validações**: resultado correto, duplicidades, conflitos do XML, regras do padrão × XML e regras para revisar.
- **Correções**: quando o XML foi emitido errado (CFOP, CST, base, cBenef, origem), clique em **Revisar** ou em
  **Corrigir**, informe o valor correto e escolha o alcance (só aqueles itens ou todos com as mesmas características).
  O programa reprocessa como se o XML viesse corrigido e mostra o cenário antes → depois. Use `-` para remover
  um valor (ex.: cBenef indevido). Os XMLs originais não são alterados; as correções ficam em `correcoes.json`.
- **Regime dos clientes**: envie uma planilha (XLSX ou CSV) com CNPJ e regime (S/N, Sim/Não, 1/2 do A1_SIMPNAC,
  Simples/Normal). O motor passa a gerar perfis como CJCS01 (Simples) e CJCN01 (Normal). A lista fica em
  `regime_clientes.csv`. A tela oferece um modelo com os clientes dos XMLs que ainda estão sem regime.
- **Tipos de operação**: de-para da finalidade para o tipo de operação (ex.: REVENDA = V1, CONSUMO = V3,
  INSUMO = V5) e finalidade por CNPJ de cliente, considerada pelo motor no cálculo.
- **Grupos derivados**: assistente em 3 passos para clientes ou produtos que o cliente informa na mão
  (ex.: transportadoras sem ICMS ST; produtos origem 2 de trade com IPI). (1) cole os CNPJs/códigos;
  (2) o programa mostra de qual perfil eles derivam, quais regras os atendem hoje em cada tributo e sugere a ação:
  *duplicar* (regra filha), *incluir no perfil do pai*, *tratamento próprio* ou *tributo ausente*, com alcance
  (interna/interestadual, operação, finalidade); (3) mostra o impacto em TODAS as regras e cadastros antes de gravar.
  As listas ficam em `grupos_derivados.json`; a decisão vira conhecimento no .md.
- **Agrupamentos**: na família do ICMS o esqueleto sai separado (operação | abrangência | origem | participante |
  regime | finalidade). Quando regras separadas têm o mesmo tratamento, a tela pergunta se pode juntar, mostra as
  regras e o impacto de juntar. A resposta fica em `## Agrupamentos` do .md.
- **Assistente (IA)**: botão no canto inferior direito. Usa a API do DeepSeek, lê o padroes_configurador.md e a
  análise atual e ajuda a analisar regras, conflitos e o impacto de um grupo. Quem gera regras continua sendo o
  motor. CNPJ/CPF são mascarados antes do envio (CNPJ_1, CPF_2…) e voltam ao normal na resposta. A chave fica em
  `llm_config.json` (ou na variável de ambiente `DEEPSEEK_API_KEY`) — não compartilhe esse arquivo.
- **Propostas de conhecimento (IA)**: explique uma situação no Assistente e peça para ele propor. Cada proposta vira
  um cartão com a linha exata (regra de negócio, agrupamento, segregação, exceção ou texto de consulta). O programa
  confere se o motor entende a linha (campo ou ação inválida bloqueia), mostra em quais itens dos XMLs ela se
  aplica e o impacto em todas as regras. Você escolhe o alcance — **só esta empresa** (`conhecimento_empresa.json`)
  ou **padrão geral** (padroes_configurador.md, vale para as próximas empresas) — e aprova. A próxima geração já
  aplica. Tudo fica no histórico em **Padrões › Conhecimento aprovado**, com **Desfazer** e cópias de segurança do
  .md (`padroes_backup/`, as 40 mais recentes).
- **Padrões**: edição do padroes_configurador.md com aplicação imediata.

Passe o mouse sobre qualquer código (base, alíquota, perfil, escrituração, regra) para ver o que ele é e o que compõe.
A tela se adapta à largura da janela: o menu vira ícones e as tabelas que não cabem viram cartões.

## O arquivo de padrões aprende com o uso
Toda decisão tomada nas telas fica gravada no `padroes_configurador.md` e vale para as próximas análises
(inclusive de outras empresas que usarem o mesmo arquivo):

| Decisão na tela | Onde fica no .md |
|---|---|
| Impostos com alíquota pela NCM (janela ao gerar), agrupar, separar por participante | Opções |
| De-para de finalidade → tipo de operação e finalidade por cliente | Tipos de operação · Finalidade por cliente |
| "Está correto: criar regra separada por CFOP/produto/UF..." | Segregações + Conhecimento aprendido |
| "Criar regra só para este cliente/produto/NCM" | Exceções + Conhecimento aprendido |
| Edição livre (regras de negócio, dimensões, CFOPs, cBenef, escrituração...) | tela Padrões |

| "Juntar" / "Manter separadas" em Agrupamentos | Agrupamentos + Conhecimento aprendido |
| Grupo derivado confirmado | Conhecimento aprendido (a lista de CNPJs/produtos fica no .json) |
| Proposta da IA aprovada como "padrão geral" | Tabela correspondente + Conhecimento aprendido (origem IA) |

Ficam fora do .md, por serem dados de cada empresa: as correções de XML (`correcoes.json`), o regime dos
clientes (`regime_clientes.csv`), os grupos derivados (`grupos_derivados.json`), os códigos já atribuídos às
regras (`codigos_regras.json`), o conhecimento aprovado só para a empresa (`conhecimento_empresa.json`), o histórico
de aprovações (`conhecimento_historico.json`) e a configuração da IA (`llm_config.json`).

## Códigos sugeridos
Regras: 3 letras do imposto + 3 dígitos; saída de 500 a 999 (ex.: ICM500, PIS500), entrada de 000 a 499.
Códigos que já existem no seu ambiente podem ser informados em **Códigos reservados** (padroes_configurador.md,
aceita faixas como ICM500-ICM560): o programa nunca os sugere. Regras de grupos de operação diferentes
(vendas, transferências, bonificações, remessas, devoluções) nunca são misturadas.

**Códigos estáveis**: a regra que continua igual mantém o código entre gerações e a regra nova recebe o próximo
código livre (um código que já foi usado não é reaproveitado). Para começar do zero, use **Renumerar** em Regras F2B.
A regra filha de um grupo derivado tem código próprio da sequência; o vínculo com a regra pai aparece nas colunas
**Pai** e **Grupo** e no **CSV gerencial** (o CSV do F2B continua no layout de importação).

Regra marcada como **Prevista**: combinação do esqueleto ainda sem nota nos XMLs (desligue em "Esqueleto completo").

Regra marcada como **Revisar**: base não identificada, ou 1% ou mais dos itens que ela aciona vieram com outro
tratamento no XML (ajuste `LIMITE_REVISAR_PCT` em servidor.py).

Os arquivos enviados pelo navegador ficam na pasta temporária do sistema (`facilitador_fiscal/uploads`).
