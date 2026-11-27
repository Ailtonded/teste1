# Padrões do Gerador de Cenários — Configurador de Tributos

Este arquivo é a base de conhecimento do programa. Edite as tabelas e clique em **Recarregar padrões**.
Não renomeie os títulos `##` nem a primeira coluna das tabelas. Para usar `|` dentro de uma célula, escreva `\|`.

## Instruções

### Objetivo
Gerar um CENÁRIO BASE (esqueleto de regras e cadastros: perfis, bases, alíquotas, escriturações) que atenda a
TODOS os cenários dos XMLs, sem duplicidade: cada item × tributo aciona exatamente uma regra. Cada tributo tem
suas próprias regras e escriturações; nunca se misturam tributos.
Na família do ICMS (ICMS, ST, DIFAL, FECP) o esqueleto segue a estrutura do escritório e NÃO é juntado sem
perguntar: TRIBUTO | OPERAÇÃO + ABRANGÊNCIA | ORIGEM | PARTICIPANTE (PJ/PF, contribuinte, regime) | FINALIDADE.
Quando regras separadas têm o mesmo tratamento, o programa pergunta em **Agrupamentos** se pode juntar.
Nos demais tributos (IPI, PIS/COFINS, IBS/CBS) vale o mínimo de regras.

### Como o programa decide
1. Cada CFOP pertence a um grupo de operação (VENDAS, TRANSFERÊNCIAS, REMESSAS...) com uma finalidade.
   Só nas VENDAS e BONIFICAÇÕES a finalidade vem da nota (indFinal: CONSUMO ou REVENDA).
2. Para cada tributo, a tabela **Dimensões por tributo** diz por quais critérios ele PODE separar regras.
   Dimensão proibida vira perfil geral (PROD01, CGERAL, 000002). Entre as permitidas, o programa usa
   só as que o XML realmente exige.
3. Alíquota que varia por NCM/origem/UF vai para o índice de cálculo (tabela por NCM); alíquota constante
   vira alíquota fixa. Isso evita uma regra por alíquota.
4. As **Regras de negócio** prevalecem sobre o XML. Quando o XML diverge, a divergência é mostrada.
5. Cenários em que o XML se contradiz e o padrão não explica aparecem em Conflitos: são o sinal de que
   falta uma dimensão ou uma regra de negócio.

### Conhecimento por tributo
- **ICMS**: estadual e cheio de particularidades. Pode variar por UF, finalidade, participante, origem
  e CFOP (ex.: venda interna para comercialização a 4% e para uso e consumo com outra alíquota).
- **Operação por CFOP**: o programa separa por CFOP só onde o tratamento muda (ex.: 6409 × 6152) e junta
  os CFOPs de mesmo tratamento em uma regra. Grupos diferentes (venda, transferência...) nunca se misturam.
- **PIS/COFINS**: valem para todas as UFs e todos os participantes; incidem nas vendas. Só o perfil de
  produto muda o tratamento: alíquota básica, monofásico ou alíquota zero.
- **IPI**: todas as UFs e participantes; CFOPs de venda. Depende do produto E da origem: importação
  direta (origem 1) e importação por trade (origem 2) tributam quando há alíquota; origem 2 comprada no
  mercado interno de fornecedor comum sai sem IPI. Para vendas à ZFM/ALC, permita Participante no IPI.
- **DIFAL**: só na venda interestadual a não contribuinte (ex.: CFOP 6108); para os demais, só o ICMS.
- **FECP**: segue a lógica do DIFAL, mas só para algumas UFs de destino (ex.: SE, RJ).
- **ICMS ST**: depende do produto (CEST/NCM), da UF de destino (protocolos) e da operação.
- **DIFAL, ICMS ST, FECP ST e FECP do DIFAL**: uma regra fiscal para CADA combinação UF origem → UF destino
  (ex.: SC→BA, SC→SP e SC→RJ = 3 regras). Na tabela de dimensões isso é UF destino = `cada`.
- **cBenef (código de benefício/ajuste)**: algumas UFs exigem o código quando o ICMS não é destacado
  ou é reduzido. Cada regra de ICMS aceita UM único cBenef: itens com cBenef diferentes obrigam regras
  diferentes. O programa separa automaticamente e confere se o XML trouxe o código.
- **CFOP**: o 1º dígito (5 interna, 6 interestadual, 7 exterior) é convertido pelo sistema conforme a UF; 5949
  e 6949 são a mesma operação. 6108 é a venda (x102) a não contribuinte de outra UF, conversão automática;
  não existe 5108 (interna vai com 5102, 5403...). Ver **Equivalência de CFOP** e **CFOPs inválidos**.
- **Regras de base (F27)**: cada base aceita UM percentual de redução e uma composição. Base comum
  (mercadoria + frete + seguro + despesas - desconto) e base com IPI são bases diferentes; cada percentual
  de redução (ex.: 15%, 20%, 80%) é uma base própria para cada composição.
- **Alíquota por NCM**: com regra de NCM, a alíquota sai da tabela por NCM, origem, UF origem, UF destino
  e CEST, e não é preciso segregar regras por UF/origem (ex.: ICMS origem 0 a 12% para S/SE exceto ES e 7%
  para N/NE/CO e ES; origem 1 a 4%). Sem regra de NCM, a alíquota é fixa e cada alíquota vira uma regra.
  Defina em Opções: USAR_REGRAS_NCM e ALIQUOTA_POR_NCM.
- **Escrituração (CJ2)**: uma por tributo e por CST (na CJ2 escolhe-se o CST do imposto e depois o CST).
  Define se o imposto vai como Tributado (sai na nota), Isento ou Outros (sai
  zerado) e a ação na nota. ICMS, PIS e COFINS não têm ação (já estão no preço); IPI, ICMS ST e FECP ST
  somam no total da nota; DIFAL e FECP são tributados sem ação na nota. Cada tributo tem a sua
  escrituração, e tributado × zerado nunca compartilham a mesma escrituração.

- **Código da regra**: 3 letras do imposto + 3 dígitos; saída de 500 a 999, entrada de 000 a 499
  (ex.: ICM500, PIS500, IPI501). Códigos já usados no ambiente vão em **Códigos reservados**.
- **Perfil de operação** = CFOPs + tipos de operação. O tipo de operação casa com a finalidade
  (de-para em **Tipos de operação**, ex.: REVENDA = V1, CONSUMO = V3, INSUMO = V5). Clientes com
  finalidade própria (ex.: revenda para insumo) vão em **Finalidade por cliente** e o motor considera.
- **Grupos de operação nunca dividem a mesma regra**: vendas, transferências, bonificações, remessas e
  devoluções têm regras próprias (ex.: operações com ICMS zero têm cBenef diferentes em SC, SP...).

- **Padrão da descrição da regra** (como no ambiente do escritório):
  `ICMS | VENDA INTERNA ST | ORIGEM 2 - TRADE | PJ | CONTRIB | NORMAL | REVENDA`;
  grupo derivado entra depois do regime: `ICMS | VENDA INTERNA | ORIGEM 1 | PJ | CONTRIB | NORMAL | TRANSP. | CONSUMO`.
- **Códigos de perfil de participante**: C + J/F (pessoa) + C/N (contribuinte) + S/N (Simples/Normal) + 01
  (CJCN01 PJ contrib. normal, CJCS01 PJ contrib. Simples, CJNN01 PJ não contrib. normal, CJNS01 PJ não contrib.
  Simples, CFNN01 PF não contrib., CFCS01 PF contrib.). Grupo derivado troca o final pelo sufixo do grupo:
  CJCNTR / CJCSTR (transportadora), CJCNIN / CJCNI1 (indústria). Perfis especiais: CJSZFM (Zona Franca),
  CJSALC (Área de Livre Comércio), CLIORP (órgão público), CGERAL (todos).
- **Perfil pai com exceção**: quando um grupo derivado sai do perfil, a descrição do pai ganha "EXC.":
  `CLIENTE | PJ | CONTRIB. | NORMAL | EXC. INDÚSTRIA E TRANSP. SC/MG/RS/MS`. O critério do pai precisa excluir
  o grupo de tributação do filho, senão os perfis se sobrepõem.
- **Grupos derivados (informados na mão)**: o XML nem sempre mostra a diferença. Ex.: PJ contribuinte do regime
  normal que é TRANSPORTADORA com benefício não tem ICMS ST — o ICMS é igual, mas o ST não existe para ele.
  O cliente informa os CNPJs, eles ganham grupo de tributação próprio e, como os perfis não podem se sobrepor,
  TODA regra de ICMS do perfil pai é duplicada para o grupo (regra filha), mesmo com o mesmo cálculo; no ST
  o grupo fica sem regra. O mesmo vale para produtos e para qualquer tributo (ICMS, ST, DIFAL, IPI, PIS/COFINS).
  Pergunte sempre o alcance: só operação interna? interestadual? vendas, bonificação, transferência?
- **Origem 2 (estrangeira adquirida no mercado interno)**: o mesmo NCM/CEST pode ter dois tratamentos.
  Comprado de TRADE (importação por conta e ordem/encomenda): a empresa é equiparada a industrial, credita e
  destaca IPI na saída. Comprado de fornecedor nacional comum: sem IPI na saída. Separe em dois grupos de
  tributação: `ICMS IMPORTADO | ORIGEM 2 - TRADE` (ICMI02) e `ICMS IMPORTADO | ORIGEM 2 - MERC. NAC.` (ICMI05).
  A lista de produtos vem do cliente — não dá para descobrir só pelo XML de saída.
- **Perfis próprios do ICMS ST**: o ST pode agrupar participantes de outro jeito que o ICMS (ex.: CJCNT0
  "ICMSST | PJ | CONTRIB | NORMAL | REVENDEDOR", CJCNT1 "ICMSST | PJ | CONTRIB | SIMPLES", CJCNT2
  "DISTRIBUIDORAS"); ST por produto costuma usar perfil por NCM (ex.: ICSA01 "ICMS ST | NCM 4011/4012/4013").
- **DIFAL ST / consumidor final contribuinte**: perfis como CJCF01/CJCF02 "DIFAL ST | PJ | CONTRIB | ... | CONS.
  FINAL | EXC. INDÚSTRIA E TRANSP." com uma regra por UF de destino.
- **ZFM / ALC**: vendas para Zona Franca e Área de Livre Comércio têm regras próprias (CJSZFM, CJSALC), com
  base deduzindo PIS/COFINS e CST 40 na origem nacional; importados seguem tributados.
- **Códigos estáveis**: a regra que continua igual mantém o código entre gerações; regra nova recebe o próximo
  código livre (código já usado não é reaproveitado). Pai/filha é só informação gerencial (CSV gerencial).

### Como acrescentar conhecimento
- Uma nova exceção de um tributo → acrescente uma linha em **Regras de negócio**.
- Um tributo que passou a variar por um critério → mude para `sim` em **Dimensões por tributo**.
- Um CFOP novo ou com finalidade errada → ajuste **Grupos de operação**.
- Clientes ou produtos que o cliente diz terem outro tratamento → tela **Grupos derivados** (assistente).
- Juntar ou manter separadas regras de mesmo tratamento → tela **Agrupamentos** (fica em ## Agrupamentos).

## Conhecimento aprendido

Decisões confirmadas pelo usuário durante as análises (artefatos de conhecimento para outras empresas).
Informativo: o que o motor aplica está em Segregações e Regras de negócio.

| Data | Tributo | Situação observada | Decisão | Origem |
|---|---|---|---|---|
| 15/11/2026 | Regra ICM500 | CFOP 5910/6910 com CST ICMS 40 e cBenef SC810165 | Tratar como: CST ICMS 00, Base ICMI01, cBenef (remover), Alíquota 17 | [CNPJ] |
| 15/11/2026 | Regra ICM509 | CFOP 5949/6949 com CST ICMS 41 e cBenef SC999999 | Tratar como: CST ICMS 90 | [CNPJ] |
| 15/11/2026 | Regra ICM509 | CFOP 5949/6949 com CST ICMS 90 | Tratar como: cBenef SC999999 | [CNPJ] |
| 15/11/2026 | Regra ICM563 | CFOP 5403/6403 com CST ICMS 70 e cBenef SC820044 | Tratar como: CST ICMS 10, Base ICMI01, cBenef (remover) | [CNPJ] |
| 15/11/2026 | Regra ICM543 | CFOP 5102/6102 com CST ICMS 20 e cBenef SC820044 | Tratar como: CST ICMS 00, Base ICMI01, cBenef (remover) | [CNPJ] |
| 15/11/2026 | Regra ICM518 | CFOP 5152/6152 com CST ICMS 41 e cBenef SC800006 | Tratar como: CST ICMS 51 | [CNPJ] |
| 15/11/2026 | Regra ICM518 | CFOP 5152/6152 com CST ICMS 51 e cBenef SC830073 | Tratar como: cBenef SC800006 | [CNPJ] |
| 15/11/2026 | Regra ICM520 | CFOP 5552/6552 com cBenef SC800006 | Tratar como: cBenef SC999999 | [CNPJ] |
| 15/11/2026 | Regra ICM530 | CFOP 5119/6119 com CST ICMS 00 | Tratar como: CST ICMS 10 | [CNPJ] |
| 15/11/2026 | Regra ICM524 | CFOP 5102/6102 com CST ICMS 00 | Tratar como: CST ICMS 51, cBenef SC830018 | [CNPJ] |
| 21/11/2026 | Regra COF504 | CFOP 5152/6152 com CST COFINS 08 | Tratar como: CST COFINS 49 | [CNPJ] |
| 21/11/2026 | Geral | FECPIC, FECPDF e FECPST são tributos distintos no F2B e não se sobrepõem | FECPIC = FECP próprio da operação interna RJ->RJ. FECPDF = FECP do DIFAL na venda interestadual a não contribuinte (CFOP 6108). FECPST = FECP carona do ICMS ST, só em vendas com ST destinadas a RJ, SE e AL. São três tributos F2B separados; regra de um não substitui a do outro. | [CNPJ] · IA |
| 21/11/2026 | Geral | FECPST acompanha o ST e varia por UF de destino | FECPST só existe onde há ICMS ST e o destino é RJ, SE ou AL. Uma regra por UF de destino (dimensão UF = cada), base e alíquota do FECPST, escrituração que soma na nota (STOTNF=6). | [CNPJ] · IA |
| 21/11/2026 | Geral | tabela oficial de CST de PIS/COFINS, para consulta nas análises | CST PIS/COFINS: 01 tributável básica; 02 tributável diferenciada; 03 tributável por unidade; 04 monofásica revenda alíquota zero; 05 tributável por ST; 06 alíquota zero; 07 isenta; 08 sem incidência; 09 suspensão; 49 outras saídas; 50-56 direito a crédito (entrada); 60-67 crédito presumido (entrada); 70-75 aquisição (entrada); 98 outras entradas; 99 outras. CSTs 50-56, 60-67 e 70-75 são de ENTRADA e não devem aparecer em NF-e de saída. | [CNPJ] · IA |
| 21/11/2026 | Regra COF500 | CFOP 5910/6910 com CST COFINS 07 | Tratar como: CST COFINS 49 | [CNPJ] |

## Tributos

| Chave | F2B_TRIB | Nome na descrição | Prefixo da regra | Início | Dígitos |
|---|---|---|---|---|---|
| ICMS | ICMS | ICMS | ICM | 500 | 3 |
| ICMSST | ICMSST | ICMS ST | IST | 500 | 3 |
| DIFAL | DIFAL | DIFAL | DIF | 500 | 3 |
| FECP | FECPIC | FECP | FCP | 500 | 3 |
| FECPST | FECPST | FECP ST | FST | 500 | 3 |
| FECPDF | FCPCMP | FECP DIFAL | FCD | 500 | 3 |
| IPI | IPI | IPI | IPI | 500 | 3 |
| PIS | PIS | PIS | PIS | 500 | 3 |
| COF | COF | COFINS | COF | 500 | 3 |
| IBSEST | IBSEST | IBS UF | IBE | 500 | 3 |
| IBSMUN | IBSMUN | IBS MUN | IBM | 500 | 3 |
| CBSFED | CBSFED | CBS | CBS | 500 | 3 |

## Dimensões por tributo

Por quais critérios cada tributo PODE separar regras (`sim`/`não`). Operação: `cfop` ou `grupo`.
UF destino `cada` = uma regra para cada combinação de UF (nunca agrupa UFs).

| Tributo | Classe do produto | Origem | Participante | UF destino | Operação | Finalidade |
|---|---|---|---|---|---|---|
| ICMS | não | sim | sim | sim | cfop | sim |
| ICMSST | não | sim | sim | cada | cfop | sim |
| DIFAL | não | sim | sim | cada | cfop | sim |
| FECP | não | não | sim | sim | cfop | sim |
| FECPST | não | não | sim | cada | cfop | sim |
| FECPDF | não | não | sim | cada | cfop | sim |
| IPI | sim | sim | não | não | cfop | não |
| PIS | sim | não | não | não | cfop | não |
| COF | sim | não | não | não | cfop | não |
| IBSEST | sim | não | não | não | cfop | não |
| IBSMUN | sim | não | não | não | cfop | não |
| CBSFED | sim | não | não | não | cfop | não |

## Regras de negócio

Condições: `campo=valor` (vírgula = OU; `*` no fim = começa com; `!=` = diferente), unidas por ` e `.
Campos: cfop, natureza, grupo, finalidade, uf, abrangencia (INTERNA/INTERESTADUAL/EXTERIOR), participante, contribuinte (SIM/NAO/ISENTO), pessoa (PF/PJ), regime (SIMPLES/NORMAL), origem, ncm, cest, cst, suframa (SIM/NAO), grupocliente e grupoproduto (nome do grupo derivado, ex.: `grupocliente=TRANSPORTADORA`).
Ações: `base=CÓDIGO` · `ausente` (o tributo não deve existir) · `aliquota=ncm` (força o índice por NCM).

| Tributo | Quando | Então | Observação |
|---|---|---|---|
| ICMS | grupo=VENDAS e finalidade=CONSUMO | base=ICMP01 | No uso e consumo o IPI compõe a base do ICMS |
| ICMS | grupo=VENDAS e finalidade=REVENDA | base=ICMI01 | Na comercialização o IPI não compõe a base do ICMS |
| DIFAL | contribuinte=SIM | ausente | DIFAL de saída só na venda a não contribuinte |
| DIFAL | abrangencia=INTERNA | ausente | DIFAL só em operação interestadual |
| FECPDF | contribuinte=SIM | ausente | FECP do DIFAL segue o DIFAL |

## Código de benefício (cBenef)

UFs do EMITENTE que exigem cBenef e CSTs de ICMS em que ele é exigido. Cada regra de ICMS aceita um único cBenef.

| Item | Valor |
|---|---|
| UFS_EXIGEM | DF, ES, GO, PR, RJ, RS, SC, SP |
| CST_EXIGEM | 20, 30, 40, 41, 50, 51, 70, 90 |

## Escrituração — ação na nota

STOTNF: 1 Sem ação · 2 Subtrai só do total · 3 Subtrai do total e da duplicata · 5 Soma só no total · 6 Soma no total e na duplicata.

| Tributo | Com imposto | Sem imposto | Observação |
|---|---|---|---|
| ICMS | 1 | 1 | já está no preço (desonerado que deduz usa 3) |
| ICMSST | 6 | 1 | soma na nota |
| DIFAL | 1 | 1 | tributado, sem ação na nota |
| FECP | 1 | 1 | tributado, sem ação na nota |
| FECPST | 6 | 1 | soma na nota |
| FECPDF | 1 | 1 | tributado, sem ação na nota |
| IPI | 6 | 1 | soma na nota |
| PIS | 1 | 1 | já está no preço |
| COF | 1 | 1 | já está no preço |
| IBSEST | 1 | 1 |  |
| IBSMUN | 1 | 1 |  |
| CBSFED | 1 | 1 |  |

## Escrituração — incidência por CST

INCIDE: 1 Tributado · 2 Isento · 3 Outros · 4 Tributado e Isento · 5 Tributado e Outros. `valor` = 1 se houver imposto, senão 3. CST `*` = qualquer outro.

| Tributo | CSTs | INCIDE |
|---|---|---|
| ICMS | 00, 10, 101, 201 | 1 |
| ICMS | 20, 70 | 4 |
| ICMS | 30, 40, 103, 203, 300, 400 | 2 |
| ICMS | 41, 50, 51, 60, 102, 202, 500 | 3 |
| ICMS | 90, 900 | valor |
| IPI | 50 | 1 |
| IPI | 51, 52 | 2 |
| IPI | 53, 54, 55 | 3 |
| IPI | 99 | valor |
| PIS | 01, 02, 03, 05 | 1 |
| PIS | 06, 07 | 2 |
| PIS | * | valor |
| COF | 01, 02, 03, 05 | 1 |
| COF | 06, 07 | 2 |
| COF | * | valor |
| ICMSST | * | 1 |
| DIFAL | * | 1 |
| FECP | * | 1 |
| FECPST | * | 1 |
| FECPDF | * | 1 |
| IBSEST | * | valor |
| IBSMUN | * | valor |
| CBSFED | * | valor |

## Perfis de origem/destino por UF

Usados nos tributos com uma regra por UF (DIFAL, ICMS ST, FECP ST). Códigos do padrão GF (perfis SIBSnn, tabela F21). ES (SIBS34), RJ (SIBS35), RS (SIBS36) e SP (SIBS37) são códigos novos, criados com aprovação.

| UF destino | Código | Descrição |
|---|---|---|
| AC | SIBS22 | SAÍDAS INTERESTADUAIS \| AC || INTERESTADUAL \| AC |
| AL | SIBSD5 | SAÍDAS INTERESTADUAIS \| AL || INTERESTADUAL \| AL |
| AM | SIBS26 | SAÍDAS INTERESTADUAIS \| AM || INTERESTADUAL \| AM |
| AP | SIBS07 | SAÍDAS INTERESTADUAIS \| AP || INTERESTADUAL \| AP |
| BA | SIBS08 | SAÍDAS INTERESTADUAIS \| BA || INTERESTADUAL \| BA |
| CE | SIBS09 | SAÍDAS INTERESTADUAIS \| CE || INTERESTADUAL \| CE |
| DF | SIBS10 | SAÍDAS INTERESTADUAIS \| DF || INTERESTADUAL \| DF |
| ES | SIBS34 | SAÍDAS INTERESTADUAIS \| ES || INTERESTADUAL \| ES (sem código único na GF: confirmar) || INTERESTADUAL \| ES |
| GO | SIBS12 | SAÍDAS INTERESTADUAIS \| GO || INTERESTADUAL \| GO |
| MA | SIBS13 | SAÍDAS INTERESTADUAIS \| MA || INTERESTADUAL \| MA |
| MG | SIBS14 | SAÍDAS INTERESTADUAIS \| MG || INTERESTADUAL \| MG |
| MS | SIBS15 | SAÍDAS INTERESTADUAIS \| MS || INTERESTADUAL \| MS |
| MT | SIBS16 | SAÍDAS INTERESTADUAIS \| MT || INTERESTADUAL \| MT |
| PA | SIBS17 | SAÍDAS INTERESTADUAIS \| PA || INTERESTADUAL \| PA |
| PB | SIBS18 | SAÍDAS INTERESTADUAIS \| PB || INTERESTADUAL \| PB |
| PE | SIBS19 | SAÍDAS INTERESTADUAIS \| PE || INTERESTADUAL \| PE |
| PI | SIBS20 | SAÍDAS INTERESTADUAIS \| PI || INTERESTADUAL \| PI |
| PR | SIBS21 | SAÍDAS INTERESTADUAIS \| PR || INTERESTADUAL \| PR |
| RJ | SIBS35 | SAÍDAS INTERESTADUAIS \| RJ || INTERESTADUAL \| RJ (sem código único na GF: confirmar) || INTERESTADUAL \| RJ |
| RN | SIBS23 | SAÍDAS INTERESTADUAIS \| RN || INTERESTADUAL \| RN |
| RO | SIBS28 | SAÍDAS INTERESTADUAIS \| RO || INTERESTADUAL \| RO |
| RR | SIBS24 | SAÍDAS INTERESTADUAIS \| RR || INTERESTADUAL \| RR |
| RS | SIBS36 | SAÍDAS INTERESTADUAIS \| RS || INTERESTADUAL \| RS (sem código único na GF: confirmar) || INTERESTADUAL \| RS |
| SC | SIBS25 | SAÍDAS INTERESTADUAIS \| SC || INTERESTADUAL \| SC |
| SE | SIBSD6 | SAÍDAS INTERESTADUAIS \| SE || INTERESTADUAL \| SE |
| SP | SIBS37 | SAÍDAS INTERESTADUAIS \| SP || INTERESTADUAL \| SP (sem código único na GF: confirmar) || INTERESTADUAL \| SP |
| TO | SIBS27 | SAÍDAS INTERESTADUAIS \| TO || INTERESTADUAL \| TO |

## Tipos de operação

De-para da finalidade para o tipo de operação usado nos perfis de operação.

| Finalidade | Tipo de operação | Descrição |
|---|---|---|
| REVENDA | V1 | Venda para revenda |
| CONSUMO | V3 | Venda para uso e consumo |
| INSUMO | V5 | Revenda para insumo |
| TRANSFERÊNCIAS | T1 | TRANSFERÊNCIAS |

## Finalidade por cliente

Clientes cuja finalidade não segue o indFinal da nota (ex.: revenda para insumo = INSUMO → V5).

| CNPJ/CPF | Finalidade | Observação |
|---|---|---|

## Códigos reservados

Códigos que já existem no ambiente (regras, perfis, bases...). Separe por vírgula ou espaço; aceita faixas como ICM500-ICM560.

| Códigos |
|---|
|  |

## Equivalência de CFOP

O 1º dígito do CFOP (5 interna, 6 interestadual, 7 exterior) é convertido pelo sistema conforme a UF:
5949, 6949 e 7949 são a mesma operação e não são divergência. Alguns CFOPs também são conversões
automáticas de outro (ex.: 6108 = venda a não contribuinte de outra UF, convertida do 5102/6102).
Não existe operação interna com 5108: a venda interna vai com o CFOP normal (5102, 5403...).

| Opção | Valor |
|---|---|
| USAR_EQUIVALENCIA_CFOP | sim |

| CFOP (3 últimos dígitos) | Equivale a | Observação |
|---|---|---|
| 108 | 102 | Venda interestadual a não contribuinte: conversão automática do 5102/6102 |
| 107 | 101 | Venda de produção a não contribuinte: conversão automática do 5101/6101 |

## CFOPs inválidos

CFOPs que não existem ou não cabem na operação: aparecem em Validações como erro do XML.

| CFOP | Motivo |
|---|---|
| 5107 | Não existe x107 interno: venda interna a não contribuinte usa 5101/5401 |
| 5108 | Não existe x108 interno: venda interna a não contribuinte usa 5102/5403/5405 |

## Exceções

Regra própria para clientes, produtos ou NCMs específicos, quando nenhuma dimensão separa os itens.
Campo: dest (cliente), cprod (produto) ou ncm. Valores separados por vírgula.

| Tributo | Campo | Valores | Observação | Id |
|---|---|---|---|---|

## Segregações

Cenários que pareciam divergentes mas são legítimos: o tributo passa a separar regras pelo critério.
Critérios: cfop, classe, origem, participante, uf. Vale para a família (IBS/CBS juntos; PIS/COFINS juntos).

| Tributo | Separar por | Observação |
|---|---|---|

## Agrupamentos

Na família do ICMS o programa gera o esqueleto separado (operação | abrangência | origem | participante |
regime | finalidade) e PERGUNTA antes de juntar regras de mesmo tratamento. A resposta fica aqui.
Critérios: tipo, regime, origem, finalidade, abrangencia. Decisão: juntar ou separar. Tributo `*` = todos.

| Tributo | Critério | Decisão | Observação |
|---|---|---|---|

## Grupos derivados

Informativo (o motor usa grupos_derivados.json, que tem os CNPJs/produtos de cada empresa). Grupos que já
apareceram em projetos e o que costuma mudar — use como checklist ao implantar uma empresa nova:

| Grupo | Tipo | Deriva de | Sufixo/código | O que muda |
|---|---|---|---|---|
| TRANSPORTADORA | Clientes | PJ \| CONTRIB \| NORMAL ou SIMPLES | TR (CJCNTR, CJCSTR) | Sem ICMS ST (benefício); ICMS igual ao pai, em regra filha; ver UFs (SC/MG/RS/MS/ES) |
| INDÚSTRIA | Clientes | PJ \| CONTRIB \| NORMAL ou SIMPLES | IN (CJCNIN, CJCNI1) | Compra para insumo (tipo de operação V5): sem ST na venda; ICMS em regra filha |
| DISTRIBUIDORA / REVENDEDOR | Clientes | PJ \| CONTRIB | perfis do ST (CJCNT0/T1/T2) | Só o ICMS ST muda (MVA/regime do destinatário) |
| ÓRGÃO PÚBLICO | Clientes | PJ \| NÃO CONTRIB | CLIORP | Isenções/retenções específicas |
| TRADE | Produtos | ORIGEM 2 | ICMI02 | IPI destacado na saída (equiparado a industrial) |
| MERC. NAC. | Produtos | ORIGEM 2 | ICMI05 | Sem IPI na saída; ICMS igual ao pai, em regra filha |

## Assistente IA

Orientação para o assistente (DeepSeek) que lê este arquivo:
- Responda como consultor do Configurador de Tributos (FISA170). Não invente códigos: use os da análise.
- Toda sugestão deve dizer o impacto nos outros tributos e em quais perfis o grupo de tributação entra/sai.
- Para cenário que o XML não explica, sugira Correções (emissão errada), Grupos derivados (lista do cliente),
  Agrupamentos (juntar/separar) ou uma linha em Regras de negócio, nesta ordem de preferência.
- Antes de recomendar, pergunte o alcance quando fizer diferença (interna × interestadual, operação, finalidade).

## Grupos de operação

Finalidade `indFinal` = vem da nota (CONSUMO/REVENDA). Qualquer outro texto é a finalidade fixa.

| CFOPs (3 últimos dígitos) | Natureza | Grupo | Finalidade |
|---|---|---|---|
| 101 102 103 104 105 106 107 108 | VENDA | VENDAS | indFinal |
| 109 110 | VENDA ZFM/ALC | VENDAS | indFinal |
| 111 112 113 114 115 116 117 | VENDA ENTREGA FUTURA | VENDAS | indFinal |
| 118 119 120 | VENDA À ORDEM | VENDAS | indFinal |
| 122 123 | VENDA P/ INDUSTRIALIZAÇÃO | VENDAS | indFinal |
| 401 403 | VENDA ST | VENDAS | indFinal |
| 405 | VENDA SUBSTITUÍDO | VENDAS | indFinal |
| 922 | SIMPLES FATURAMENTO | VENDAS | indFinal |
| 151 152 153 155 156 | TRANSFERÊNCIA | TRANSFERÊNCIAS | TRANSFERÊNCIA |
| 408 409 | TRANSFERÊNCIA ST | TRANSFERÊNCIAS | TRANSFERÊNCIA |
| 552 | TRANSFERÊNCIA ATIVO | TRANSFERÊNCIAS | TRANSFERÊNCIA |
| 557 | TRANSFERÊNCIA USO/CONSUMO | TRANSFERÊNCIAS | TRANSFERÊNCIA |
| 201 202 208 209 210 | DEVOLUÇÃO DE COMPRA | DEVOLUÇÕES | DEVOLUÇÃO |
| 410 411 412 413 | DEVOLUÇÃO DE COMPRA ST | DEVOLUÇÕES | DEVOLUÇÃO |
| 553 | DEVOLUÇÃO ATIVO | DEVOLUÇÕES | DEVOLUÇÃO |
| 556 | DEVOLUÇÃO USO/CONSUMO | DEVOLUÇÕES | DEVOLUÇÃO |
| 910 | BONIFICAÇÃO | BONIFICAÇÕES | indFinal |
| 911 | AMOSTRA GRÁTIS | BONIFICAÇÕES | indFinal |
| 551 | VENDA ATIVO | ATIVO | ATIVO |
| 501 502 | REMESSA EXPORTAÇÃO | REMESSAS | REMESSA |
| 901 902 | REMESSA INDUSTRIALIZAÇÃO | REMESSAS | REMESSA |
| 904 | REMESSA VENDA FORA DO ESTAB. | REMESSAS | REMESSA |
| 905 906 907 | DEPÓSITO | REMESSAS | REMESSA |
| 908 909 | COMODATO | REMESSAS | REMESSA |
| 912 913 | DEMONSTRAÇÃO | REMESSAS | REMESSA |
| 914 | REMESSA EXPOSIÇÃO/FEIRA | REMESSAS | REMESSA |
| 915 916 | CONSERTO | REMESSAS | REMESSA |
| 917 918 919 | CONSIGNAÇÃO | REMESSAS | REMESSA |
| 920 921 | VASILHAME | REMESSAS | REMESSA |
| 923 924 | REMESSA CONTA E ORDEM | REMESSAS | REMESSA |
| 925 | RETORNO CONSIGNAÇÃO | REMESSAS | REMESSA |
| 934 | REMESSA ARMAZÉM GERAL | REMESSAS | REMESSA |
| 927 | PERDA DE ESTOQUE | OUTRAS | OUTRAS |
| 929 | CUPOM FISCAL | VENDAS | indFinal |
| 949 | OUTRAS SAÍDAS | OUTRAS | OUTRAS |

## Perfis de produto por origem

| Grupo | Origens | Código | Descrição |
|---|---|---|---|
| N | 0,3,4,5,8 | ICMN01 | ICMS NACIONAL - ORIGEM 0/3/4/5/8 |
| I1 | 1 | ICMI01 | ICMS IMPORTADO - ORIGEM 1 |
| I2 | 2 | ICMI02 | ICMS IMPORTADO - ORIGEM 2 |
| C | 6,7 | ICMC01 | ICMS CAMEX - ORIGEM 6/7 |

## Perfis de participante

| Tipo no XML | Código | Descrição curta | Critério sugerido |
|---|---|---|---|
| PJ Contribuinte | CJCG01 | PJ \| CONTRIB | A1_PESSOA=J; A1_CONTRIB=1 |
| PJ Isento | CJIG01 | PJ \| ISENTO | A1_PESSOA=J; IE=ISENTO |
| PJ Não contribuinte | CJNG01 | PJ \| NÃO CONTRIB | A1_PESSOA=J; A1_CONTRIB=2 |
| PJ Não contribuinte COM IE | CJNE01 | PJ \| NÃO CONTRIB C/ IE | A1_PESSOA=J; A1_CONTRIB=2; com IE (conferir cadastro) |
| PF Não contribuinte | CFNN01 | PF \| NÃO CONTRIB | A1_PESSOA=F; A1_CONTRIB=2 |
| PF Contribuinte (produtor rural) | CFCS01 | PF \| CONTRIB | A1_PESSOA=F; A1_CONTRIB=1 |
| PF Isento | CFIG01 | PF \| ISENTO | A1_PESSOA=F; IE=ISENTO |
| Exterior | CEXG01 | EXTERIOR | A1_EST=EX |
| Consumidor | CCFG01 | CONSUMIDOR NÃO IDENTIF. | sem destinatário (NFC-e) |

## Códigos gerais

| Item | Código | Descrição |
|---|---|---|
| PRODUTO_GERAL | PROD01 | GERAL \| PRODUTOS |
| PARTICIPANTE_GERAL | CGERAL | CLIENTE \| GERAL |
| OD_INTERNA | 000001 | OPERAÇÕES INTERNAS |
| OD_INTERESTADUAL | 000003 | SAÍDAS INTERESTADUAIS |
| OD_TODAS | 000002 | TODAS AS UFS |
| ALIQ_NCM | INCN01 | ÍNDICE DE CÁLCULO \| NCM |
| ALIQ_ZERO | ALQZER | ALÍQUOTA ZERO |

## Opções

Escolhas de geração. As telas do programa gravam aqui as decisões do usuário.

| Opção | Valor |
|---|---|
| RAPUR | 000001 |
| INICIO_PERFIL_OPERACAO | 101 |
| AGRUPAR_MAXIMO | não |
| SEPARAR_PARTICIPANTE | sim |
| SEPARAR_REGRAS_POR_GRUPO | sim |
| ESQUELETO_COMPLETO | sim |
| USAR_REGRAS_NCM | sim |
| ALIQUOTA_POR_NCM | ICMS, ICMSST, DIFAL, FECP, FECPST, FECPDF, IPI, PIS, COF |

