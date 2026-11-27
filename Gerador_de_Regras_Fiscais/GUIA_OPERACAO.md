# Guia de operação — Facilitador Fiscal (Streamlit)

Este guia mostra, passo a passo, como gerar os cenários e as regras F2B a partir de XMLs de NF-e de saída.
As imagens são do programa em execução, com XMLs de **exemplo fictício** (CNPJ [CNPJ de exemplo]).

## 0. Antes de começar

- Python 3.9 ou mais novo, com Streamlit e pandas instalados (`pip install streamlit pandas`).
- Abra um terminal na pasta do programa e rode:

```powershell
python -m streamlit run app.py
```

- O navegador abre em `http://localhost:8501`.

![Tela inicial](guia_imagens/01_tela_inicial.png)

## 1. Importar os XMLs

Na barra lateral, em **1. XMLs de saída**, você tem duas formas:

- **Arquivos pequenos**: arraste XML ou ZIP para a área de upload e clique em **Importar arquivos enviados**.
- **Pasta grande**: abra **Pasta grande no computador?**, informe o caminho da pasta ou do ZIP e clique em **Ler caminho**.
  Essa opção lê direto do disco e é a mais indicada para milhares de notas.

Confira o resultado na aba **Importar**: NF-e lidas, repetidas, cancelamentos, ignoradas e erros.

![XML lido](guia_imagens/02_xml_lido.png)

## 2. Escolher a empresa e as opções

Em **2. Empresa e opções**:

- **CNPJ emitente**: escolha o CNPJ da empresa cujas saídas você está analisando.
- **Agrupar CFOPs de mesmo tratamento**: junta CFOPs que têm o mesmo tratamento tributário. Recomendado.
- **Separar por participante**: cria regras separadas por cliente. Use só se a empresa exigir.

## 3. Gerar os cenários

Clique em **Gerar cenários**. Quando terminar, aparece a mensagem "Cenários gerados" e a data da última geração.

![Cenários gerados](guia_imagens/03_cenarios_gerados.png)

## 4. Conferir as abas

| Aba | O que mostra | O que verificar |
|---|---|---|
| Importar | Contadores e emitentes | Número de notas bate com o esperado |
| Visão geral | Resumo e validação | Não deve haver itens sem regra |
| Regras F2B | Todas as regras, com filtro por tributo | Status, base, alíquota, perfis e escrituração |
| Cenários | Combinação de CFOP, finalidade, UF, participante e produto | Cada cenário aciona uma regra por tributo |
| Cadastros | Bases (F27), alíquotas (F28), escrituração (CJ2) e tipos de operação | Códigos seguem o padrão GF |
| Validações | Resultado da validação e conflitos do XML | Conflitos devem ser resolvidos antes de usar |
| Padrões | Edição do `padroes_configurador.md` | Só alterar com aprovação |

![Visão geral](guia_imagens/05_aba_visao_geral.png)
![Regras F2B](guia_imagens/06_aba_regras_f2b.png)
![Cenários](guia_imagens/07_aba_cenarios.png)
![Cadastros](guia_imagens/08_aba_cadastros.png)
![Validações](guia_imagens/09_aba_validacoes.png)
![Padrões](guia_imagens/10_aba_padroes.png)

## 5. Exportar a regra para o Protheus

Na aba **Regras F2B**, clique em **Baixar CSV F2B (layout de importação)**. O arquivo segue o layout de importação
do F2B no Protheus.

## 6. Status e o que fazer

- **Revisar**: a base não foi identificada, ou 1% ou mais dos itens vieram com outro tratamento no XML. Confira se
  é erro do XML (então vira correção) ou do padrão.
- **Prevista**: combinação do esqueleto ainda sem nota nos XMLs. É uma previsão, não um erro.
- **Conflito do XML**: o XML se contradiz e o padrão não explica. Pergunte antes de decidir.

## 7. Limitações atuais

- O **regime do cliente** (Simples ou Normal) não vem no XML. Sem ele, as regras de PJ contribuinte podem sair
  erradas. A aba de regime ainda não está no Streamlit.
- A **redução de alíquota** (ex.: `LQR000`) ainda não é gerada.
- As regras ainda não foram validadas com notas reais da GF.
