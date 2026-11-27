# Modelo GF — Tabelas do Configurador de Tributos (FISA170)

Fonte: dicionário SX3 (`U_CMNCOL_PR.SX3010`) da base TESTE da GF, consultado em modo somente leitura em 2026-11-27.
Cada tabela física é `<ALIAS>010` (empresa 01). Toda tabela tem `<ALIAS>_FILIAL` (8 caracteres), e a chave lógica
é o código da tabela. Campos `_MSEXP` e `_HREXP` são de controle de exportação e não entram na geração.

Este arquivo é o **modelo de referência**: o motor deve usar os mesmos códigos, campos e formatos.
Alterar configuração de regra exige pergunta ao usuário (ver `INSTRUCOES_IA.md`).

Legenda dos campos: `→XXX` indica consulta (F3) à tabela `XXX`. Campos sem `→` são livres.

---

## 1. Perfis (F20 a F26)

### F20 — Perfis Tributários (cabeçalho do perfil)
`F20_CODIGO` Cód. Perfil (6) · `F20_DESC` Descrição · `F20_TIPO` Tipo Perfil (2) · `F20_NATOPE` Nat. Oper. →CJH · `F20_STATUS`

Tipos de perfil observados no banco (`F20_TIPO`):
| Tipo | Uso | Exemplos |
|---|---|---|
| 01 | Origem/Destino (F2B_PEROD) | `000001` Operações Internas · `000004` Entradas Interestaduais |
| 02 | Participante (F2B_PERFPA) | `CJCN01` PJ contrib. normal · `CJCS01` PJ contrib. Simples · `CFCS01` PF contrib. · `CFNN01` PF não contrib. · `CGERAL` Cliente geral · `FGERAL` Fornecedor geral |
| 03 | Operação (F2B_PERFOP) | `POS005` Venda interestadual consumo sem ST · `POT001` Transferências entre filiais · `POIB01` Bonificação · `POIP01` Perda de estoque |
| 04 | Produto (F2B_PERFPR) | `ICMI01` ICMS importado origem 1 · `ICMI02` origem 2 · `ICMC01` CAMEX origem 6/7 · `PROD01` Geral produtos |

Padrão de nome do perfil de participante: `C` + `J`/`F` + `C`/`N` + `S`/`N` + `01`. Descrição no padrão
`CLIENTE | PJ | CONTRIB. | NORMAL | EXC. ...` quando o perfil pai tem exceção.

### F21 — Perfil Tributário Orig./Dest.
`F21_CODIGO` · `F21_UFORI` UF Origem →12 · `F21_UFDEST` UF Destino →12 · `F21_TIPOPF` Tipo Perfil

### F22 — Perfil Trib. de Participante
`F22_CODIGO` · `F22_TPPART` Tipo · `F22_CLIFOR` Participante · `F22_LOJA` · `F22_RAZSOC` Razão Social · `F22_TIPOPF` · `F22_STATUS`
(Liga o perfil de participante a um cliente ou fornecedor específico.)

### F23 — Perfil Tributário de Operação
`F23_CODIGO` · `F23_CFOP` CFOP →13 · `F23_DCFOP` Descr. CFOP · `F23_TIPOPF`

### F24 — Perfil Tributário de Produto
`F24_CODIGO` · `F24_CDPROD` Cód. Produto →SB1 · `F24_DSPROD` · `F24_TIPOPF` · `F24_CODNCM` NCM · `F24_STATUS`

### F25 — Perfil Produto x Origem
`F25_CODIGO` · `F25_ORIGEM` Origem Prod. →S0 · `F25_DSORIG` · `F25_TIPOPF`

### F26 — Perfil Tipo de Operação (tipo de operação)
`F26_CODIGO` · `F26_TPOPER` Tp. Operação →DJ · `F26_DESCRI` · `F26_TIPOPF`
Exemplos do padrão do escritório: REVENDA = V1, CONSUMO = V3, INSUMO = V5 (ver `padroes_configurador.md`).

---

## 2. Bases e alíquotas (F27 e F28)

### F27 — Regra de Base de Cálculo
`F27_CODIGO` Cód. Regra (6) · `F27_DESC` Descrição · `F27_VALORI` Valor Origem (2, ex.: `01`, `11`) ·
`F27_DESCON` Desconto (1, `1` = soma) · `F27_FRETE` · `F27_SEGURO` · `F27_DESPE` · `F27_ICMDES` ICMS Deson. ·
`F27_ICMRET` ICMS Retido · `F27_REDBAS` % Redução (N 6,3) · `F27_TPRED` Tipo Redução · `F27_UM` →SAH · `F27_ID`

Bases observadas (`F27_CODIGO`):
- `ICMI01` ICMS | BASE INTEGRAL · redução 0 · composição: mercadoria + frete + seguro + despesas − desconto.
- `ICMC01` ICMS | COMPLEMENTAR · redução 0.
- `ICMI02` ICMS | BASE INTEGRAL | DIFERIMENTO 29,41% · **duas linhas**: 29,41 (valor 01) e 70,59 (valor 01).
  Uma base pode ter várias linhas com percentuais diferentes.
- `REG02` Regra de base do ICMS com redução de 8,5% (convênio 06/2006) · redução 8,5.

### F28 — Regra de Alíquota
`F28_CODIGO` Cód. Regra (6) · `F28_DESC` · `F28_VALORI` Valor Origem (2) · `F28_TPALIQ` Tp. Alíquota (1) ·
`F28_ALIQ` Alíquota (N 6,2) · `F28_URF` →F29 · `F28_UFRPER` Perc. URF · `F28_REDALI` Red. Aliq. % (N 7,3) ·
`F28_REDADC` Red. Adic. % (N 7,3) · `F28_ID`

Alíquotas observadas:
- `ICM120` ICMS | ALÍQUOTA 12% · `F28_ALIQ` 12 (tipo `04`) ou `06` conforme o caso.
- `ICM170` ICMS | ALÍQUOTA 17%.
- `ALQZER` ALÍQUOTA ZERO · `F28_ALIQ` 0.
- `INCN01` ÍNDICE DE CÁLCULO | NCM · alíquota vem da tabela por NCM (CIT/CIU).
- `LQR000` ALÍQ 0% C% REDUÇÃO DE 100% · `F28_REDALI` 100 (exemplo de redução de alíquota da GF).
  **Redução de alíquota ainda não está implementada no motor** (decisão do usuário).

Tipo de alíquota `F28_TPALIQ` e valor origem `F28_VALORI` seguem o mesmo padrão observado nas linhas da GF
(`04`, `06`, `01`). Confirmar antes de gerar um código novo.

---

## 3. Regra tributária (F2B)

### F2B — Regra Tributária (cabeçalho da regra fiscal)
Campos principais (ordem do SX3):
| Campo | Título | Tam. | Lookup | Observação |
|---|---|---|---|---|
| `F2B_REGRA` | Código Regra | 6 | | 3 letras + 3 dígitos |
| `F2B_DESC` | Descrição | 100 | | Padrão `TRIBUTO \| OPERAÇÃO \| ORIGEM \| PJ/PF \| CONTRIB \| NORMAL \| FINALIDADE` |
| `F2B_TRIB` | Tributo | 6 | →F2E | Ex.: ICMS, ICMSST, DIFAL, FCPCMP, IPI, PIS, COF, IBSEST, IBSMUN, CBSFED |
| `F2B_VIGINI` / `F2B_VIGFIM` | Vigência | 8 | | |
| `F2B_RBASE` | Base Cálculo | 6 | →F27 | Código F27 (ICMI01, ICMC01, ICMI02...) |
| `F2B_RALIQ` | Alíquota | 6 | →F28 | Código F28 (ICM120, ALQZER, INCN01...) |
| `F2B_PEROD` | Perf. Ori/Des | 6 | →F20OD | Perfil tipo 01 |
| `F2B_PERFPA` | Perf. Part. | 6 | →F20PAR | Perfil tipo 02 |
| `F2B_PERFOP` | Perf. Oper. | 6 | →F20OPE | Perfil tipo 03 |
| `F2B_PERFPR` | Perf. Prod. | 6 | →F20PRD | Perfil tipo 04 |
| `F2B_RFIN` | Financeira | 6 | →FKK | Regra financeira |
| `F2B_RAPUR` | Regra Apur. | 6 | →F2G | Regra de apuração |
| `F2B_RBASES` | Bas. Second. | 6 | →F27 | Base secundária |
| `F2B_TRBMAJ` | Trib. Maj. | 6 | →F2B2 | Tributo de majoração |
| `F2B_DEDDEP` / `F2B_DEDPRO` | Dedução dep. / progressiva | 6 | →CIV / →CIQ | IRRF |
| `F2B_CODESC` | Cód. Escrit. | 6 | →CJ2REG | Escrituração CJ2 (ex.: ICMS00, ICMS10, ICMS41, ICMS90) |
| `F2B_MAXMIN` | Maior Menor | 1 | | `1` maior, `2` menor |
| `F2B_RGGUIA` | Reg. Ger. Guia | 6 | →CJ4 | Regra de guia |
| `F2B_VLRMIN` / `F2B_VLRMAX` | Vlr. Mín./Máx. | 14,2 | | |
| `F2B_OPRMIN` / `F2B_OPRMAX` | Operador | 30 | →CINOPR | |
| `F2B_ORIGEM` | Origem Regra | 1 | | `1` padrão |
| `F2B_RDBASE` | % Base Aux | 3 | | |
| `F2B_RCUSTO` | Custo | 6 | →D4H | |
| `F2B_STATUS` | Status | 1 | | `1` ativo, `2` inativo |
| `F2B_TPREGR` | Tipo Regra | 30 | | |
| `F2B_TBCONF` | Trib Generic | 6 | →F2B3 | |
| `F2B_CONREG` | Consulta Reg | 30 | →CINLIM | |
| `F2B_ACMAX` / `F2B_ACMIN` | Ação máx./mín. | 1 | | `1`, `2`, `3` |
| `F2B_MSGCOD` | Cód. Grupo mensagem | 6 | →CK7 | |
| `F2B_RND` | Config Arred | 1 | | |

Regras com status `2` (ativo na amostra) e código `DESATIVADO` / `INATIVO` no início da descrição existem no banco:
não reutilizar esses códigos (o motor já trata código usado como não reaproveitável).

Quantidade por tributo no banco TESTE: ICMS 4.817 · DIFAL 4.730 · ICMSST 2.451 · IPI 680 · PIS 382 · COF 323 ·
CBSFED 246 · IBSEST 223 · FCPST 213 · IBSMUN 171 · FCPCMP 135 · FECPIC 28 · demais tributos com poucas regras.

---

## 4. Escrituração e cadastros (CJ0 a CJ9, CJA, CJL)

Tabelas de movimento (CJ3, F2D, F2A, F2F, F2H a F2N) foram **excluídas** do modelo, por pedido do usuário.
Elas são geradas pelo Protheus na apuração e não são configuradas.

### CJ0 — CST Cabeçalho
`CJ0_CODIGO` Código · `CJ0_DESCR` · `CJ0_IDTRIB` Id. Tributo →F2C · `CJ0_DESCTR` · `CJ0_VIGINI` / `CJ0_VIGFIM`

### CJ1 — CST Item
`CJ1_CST` CST (3) · `CJ1_ID_CAB` · `CJ1_ID` · `CJ1_DESCR` · `CJ1_CODCAB` Cód. Cabeçalho

### CJ2 — Regra Escrituração (código de escrituração da F2B)
| Campo | Título | Observação |
|---|---|---|
| `CJ2_CODIGO` | Código Regra (6) | Código usado em `F2B_CODESC`, ex.: `ICMS00`, `ICMS10`, `ICMS41`, `ICMS90`, `ICM170` |
| `CJ2_DESCR` | Descrição | |
| `CJ2_INCIDE` | Incidência | Tributado, isento ou outros |
| `CJ2_STOTNF` | Soma Total | Soma no total da nota (`1`) |
| `CJ2_PERDIF` | Perc. Difer. | % diferimento |
| `CJ2_CSTCAB` | Tab. CST → CJ0 | Tabela de CST |
| `CJ2_CST` | CST → CJ1 | Classificação fiscal |
| `CJ2_CSTDEV` | CST Devol. → CJ1 | CST na devolução |
| `CJ2_CSTCCT` | Class Trib → CKB | Classificação tributária IBS/CBS |
| `CJ2_CCT` | CCT IBS/CBS | 3 caracteres |
| `CJ2_CCTVIG` | Data inicial CCT | |
| `CJ2_NLIVRO` | Número do livro | |
| `CJ2_MSGCOD` | Cód. grupo mensagem → CK7 | |
| `CJ2_INDOP` | Indic. Operação → CI1 | |
| `CJ2_INCRBS` / `CJ2_INCDEV` / `CJ2_INCINT` | Incidências (redução, devolução, integração) | |
| `CJ2_DSTONF` | Soma Tot Dev | |
| `CJ2_IREDBS` | Incid. Red. | |

Regra do banco: uma escrituração por tributo e por CST. Tributado × zerado nunca compartilham a mesma escrituração.

### CJ4 — Regra para Guia de Recolhimento
`CJ4_CODIGO` · `CJ4_DESCR` · `CJ4_MODO` Gera Guia · `CJ4_ORIDES` · `CJ4_IMPEXP` · `CJ4_IE` · `CJ4_VTELA` · `CJ4_CNPJ` · `CJ4_IEGUIA` · `CJ4_UF` · `CJ4_CFVENC` Vencimento · `CJ4_QTDDIA` · `CJ4_DTFIXA` Dia Fixo · `CJ4_INFCOM` → CCE · `CJ4_MAJSEP` · `CJ4_MESFIX`

### CJ5 — Regra de Código de Receita
`CJ5_CODIGO` Cód. Tributo →F2E · `CJ5_DESCR`

### CJ6 — Código de Receita por Estado
`CJ6_CODIGO` · `CJ6_ESTADO` UF →12 · `CJ6_CODREC` Cód. Receita (15) · `CJ6_DETALH` Det. Receita · `CJ6_REF` · `CJ6_ID` · `CJ6_COBREC` → 86

### CJ7 — Código de Receita (mod. documento)
`CJ7_CODIGO` · `CJ7_ESPECI` Espécie →42 · `CJ7_DESCR`

### CJ8 — Cadastro de Mensagem
`CJ8_CODREF` Código Regra · `CJ8_DESC` · `CJ8_TPREGR` Tipo Regra · `CJ8_TRIFIL` Tri. Filtro · `CJ8_REGRA` Ref Tributo · `CJ8_MENSG` Mensagem (memo) · `CJ8_CONSUL` · `CJ8_TBCONF` → F2B2

### CJ9 — Cabeçalho Regra de Ajuste de Lançamento
`CJ9_CODREG` · `CJ9_DESCR` · `CJ9_VIGINI` / `CJ9_VIGFIM`

### CJA — Itens da Regra de Ajuste de Lançamento
`CJA_CODREG` Cod. Cabec · `CJA_REGCAL` Reg. Cálculo →F2B3 · `CJA_CODTAB` Tab. Lanç. · `CJA_CODLAN` Cód. Lanç. · `CJA_VIGINI` / `CJA_VIGFIM` · `CJA_NFBASE` · `CJA_NFALIQ` · `CJA_VALOR` →CIN2 · `CJA_VLOUTR` →CIN2 · `CJA_OPER` · `CJA_CODMSG` →CJ8 · `CJA_GUIA` →CJ42 · `CJA_TITULO` →FKK2

### CJL — Controle de Mensagens Decodificadas
`CJL_INDICE` · `CJL_CODMSG` · `CJL_MENSG` (memo)

---

## 5. Cadastros auxiliares do tributo

### F2C — Tributos De/Para
`F2C_CODIGO` Tributo · `F2C_DESC`

### F2E — Cadastro de Tributo
`F2E_TRIB` Tributo · `F2E_DESC` · `F2E_ESFERA` Esfera · `F2E_ESPECI` Espécie · `F2E_IDTRIB` →F2C · `F2E_DIDTRB`
(Tabela de tributos aceitos em `F2B_TRIB`.)

### F29 — Unidade de Referência Fiscal
`F29_CODIGO` Cód. Unidade · `F29_DESC`

### F2G — Regra de Apuração
`F2G_CODIGO` · `F2G_DESCRI` · `F2G_SAIDA` · `F2G_ENTRAD` · `F2G_DEVOL`

---

## 6. Cadastros de fórmula, NCM, ISS e perfis de filtro

### CIN — Cadastro de Fórmulas
`CIN_CODIGO` Cód. Cabec. · `CIN_DESCR` · `CIN_TREGRA` Tipo Regra · `CIN_REGRA` Regra · `CIN_FORMUL` Fórmula (memo) ·
`CIN_FNPI` Fórmula NPI · `CIN_CONSUL` Consulta →CIN · `CIN_VAL` Valor Manual · `CIN_TRIB` Tributo →F2B2 · `CIN_ORITRB`

### CIO — Código de Serviço Municipal do perfil de operações
`CIO_CODIGO` · `CIO_CODISS` Cód. Serv. ISS (9) →60 · `CIO_DESCR` · `CIO_TIPOPF`

### CIQ / CIR — Tabela progressiva (IRRF)
CIQ: `CIQ_CODIGO` · `CIQ_DESCR` · `CIQ_DEDSIR` Ded. Simp. IR
CIR: `CIR_ITEM` · `CIR_VALINI` · `CIR_VALFIM` · `CIR_ALIQ` · `CIR_VALDED` · `CIR_IDCAB`

### CIS / CIT / CIU — Regras por NCM
- CIS (cabeçalho NCM): `CIS_CODNCM` NCM →SYD1 · `CIS_DESCR`
- CIT (tributo × NCM): `CIT_TRIB` →F2E · `CIT_IDNCM` · `CIT_TIPO` · `CIT_NCM` · `CIT_ALIQ` · `CIT_CODISS`
- CIU (regra adicional por NCM): `CIU_UFORI` · `CIU_UFDEST` · `CIU_VIGINI` / `CIU_VIGFIM` · `CIU_ORIGEM` →S0 ·
  `CIU_MARGEM` MVA · `CIU_VLPAUT` Vlr. Pauta · `CIU_UM` · `CIU_MAJORA` · `CIU_TIPO` · `CIU_ITEM` · `CIU_NCM` ·
  `CIU_TRIB` · `CIU_CEST` CEST →F0G · `CIU_ALIQTR` Alíquota · `CIU_EX_NCM` Ex-Tarifário

### CIV — Regra por Dependentes (IRRF)
`CIV_CODDEP` · `CIV_DESCR` · `CIV_VALDEP` · `CIV_TPDATA`

### CIX / CIY — ISS
- CIX (cabeçalho do serviço): `CIX_CODISS` Cód. Serv. →60 · `CIX_DESCR`
- CIY (alíquota por município): `CIY_UF` →12 · `CIY_CODMUN` Município →CC2CIY · `CIY_DESMUN` · `CIY_ALIQ` · `CIY_TRIB`

### CKJ / CKK — Filtros de perfis
- CKJ (filtro do perfil): `CKJ_CODIGO` Cód. Perfil · `CKJ_TIPOPF` · `CKJ_TIPO`
- CKK (valores do filtro): `CKK_IDFILT` · `CKK_CHAVE` · `CKK_VALOR`

---

## 7. Como o motor deve usar este modelo

1. **Códigos**: F2B, F27, F28, F20, CJ2 e F26 usam exatamente os códigos da GF listados acima. Código novo só com
   aprovação do usuário.
2. **Formatos**: 3 letras + 3 dígitos para regra (`ICM519`); 6 caracteres para código de perfil, base e alíquota;
   `CJ2_CODIGO` no padrão CST da GF (`ICMS00`, `ICMS10`...).
3. **Vínculos**: `F2B_RBASE` → F27, `F2B_RALIQ` → F28, `F2B_PEROD/PERFPA/PERFOP/PERFPR` → F20 por tipo, e
   `F2B_CODESC` → CJ2. Nenhum vínculo pode apontar para código inexistente.
4. **Alterações**: qualquer mudança de configuração de regra (campo do F2B, base, alíquota, perfil, escrituração,
   código, vigência) deve ser perguntada ao usuário antes.
5. **Fora do escopo atual**: redução de alíquota (`F28_REDALI`, `LQR000`) e cálculo por NCM detalhado (CIS/CIT/CIU).
