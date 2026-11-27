# -*- coding: utf-8 -*-
"""
gerador_cenarios.py — Gerador de cenários do Configurador de Tributos (Protheus FISA170)
=========================================================================================
Importe os XMLs de NF-e de SAÍDA, escolha o CNPJ e o programa mostra na hora:
  - os cenários fiscais encontrados (CFOP, finalidade, UF, participante, produto);
  - as regras F2B que precisam existir, com TODOS os campos (código, descrição, base,
    alíquota, perfis, escrituração) e o XML de exemplo de cada uma;
  - os cadastros de que as regras dependem: perfis de produto, participante,
    origem/destino e operação, tipos de operação, bases (F27), alíquotas (F28),
    alíquotas por NCM/UF e escrituração (CJ2);
  - a validação: cada item x tributo deve acionar exatamente uma regra.

Os PADRÕES (códigos, prefixos, perfis, naturezas de CFOP, opções) ficam no arquivo
padroes_configurador.md, ao lado deste programa. Edite o .md e clique em "Recarregar
padrões": nada precisa ser mudado no código. Se o .md não existir, é criado com o padrão.

Uso:  python gerador_cenarios.py
Só usa a biblioteca padrão do Python 3.8+ (tkinter).
O núcleo (ler_xml_bytes -> analisar -> montar_matriz) não depende da tela: é o que vai para o site.
"""
import os, sys, csv, re, zipfile, threading, queue, time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime

# ═════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO — ajuste aqui os códigos ao padrão do seu ambiente
# ═════════════════════════════════════════════════════════════════════════════
# chave interna: (F2B_TRIB, nome na descrição, prefixo da regra de saída, início, dígitos, família do produto)
# Código da regra: 3 letras do imposto + 3 dígitos. Saída de 500 a 999; entrada de 000 a 499.
TRIBUTOS = {
    "ICMS":   ("ICMS",   "ICMS",       "ICM", 500, 3, "ORIG"),
    "ICMSST": ("ICMSST", "ICMS ST",    "IST", 500, 3, "ORIG"),
    "DIFAL":  ("DIFAL",  "DIFAL",      "DIF", 500, 3, "ORIG"),
    "FECP":   ("FECPIC", "FECP",       "FCP", 500, 3, "ORIG"),
    "FECPST": ("FECPST", "FECP ST",    "FST", 500, 3, "ORIG"),
    "FECPDF": ("FCPCMP", "FECP DIFAL", "FCD", 500, 3, "ORIG"),   # código F2B usado na GF (F2B010): FCPCMP
    "IPI":    ("IPI",    "IPI",        "IPI", 500, 3, "IPI"),
    "PIS":    ("PIS",    "PIS",        "PIS", 500, 3, "PC"),
    "COF":    ("COF",    "COFINS",     "COF", 500, 3, "PC"),
    "IBSEST": ("IBSEST", "IBS UF",     "IBE", 500, 3, "IBS"),
    "IBSMUN": ("IBSMUN", "IBS MUN",    "IBM", 500, 3, "IBS"),
    "CBSFED": ("CBSFED", "CBS",        "CBS", 500, 3, "IBS"),
}
FIM_FAIXA_SAIDA = 999
CODIGOS_RESERVADOS = set()     # códigos que já existem no ambiente: o programa nunca os sugere

# Tipo de operação: casa com a finalidade (de-para) e pode ser definido por cliente.
TIPOS_OPERACAO = {"REVENDA": ("V1", "Venda para revenda"), "CONSUMO": ("V3", "Venda para uso e consumo"),
                  "INSUMO": ("V5", "Revenda para insumo")}
FINALIDADE_CLIENTE = {}        # CNPJ/CPF do cliente -> finalidade (ex.: INSUMO -> tipo V5)
OBS_CLIENTE = {}               # observação livre por cliente
# Regime tributário do cliente (não vem no XML): CNPJ -> "SIMPLES" | "NORMAL", carregado de planilha.
REGIME_CLIENTE = {}
# Campos do cadastro de clientes (SA1) vindos da planilha: CNPJ -> {"GRPTRIB", "CONTRIB", "PESSOA", "SIMPNAC", "EST", "SUFRAMA"}
CADASTRO_SA1 = {}
# Correções de XML informadas pelo usuário: o motor analisa como se o XML viesse corrigido.
# Cada uma: {"id", "cnpj", "itens": [[chave, nItem], ...] ou [], "filtro": {campo: valor}, "alteracoes": {campo: valor}}
CORRECOES = []
CAMPOS_CORRIGIVEIS = ("cfop", "cst", "cbenef", "orig", "cst_ipi", "cst_pis", "cst_cof", "cst_ibs", "cclass",
                      "base_icms")          # e base_<TRIBUTO> (ex.: base_IPI, base_IBSEST) para a base de cada tributo
FAMILIA_IBS = ("IBSEST", "IBSMUN", "CBSFED")
# Equivalência de CFOP: o 1º dígito (5 interna, 6 interestadual, 7 exterior) é convertido pelo sistema conforme a UF,
# então 5949, 6949 e 7949 são a mesma operação. Alguns CFOPs também são conversões automáticas de outro:
# x108 (venda a não contribuinte em outra UF) = x102; x107 = x101.
USAR_EQUIVALENCIA_CFOP = True
EQUIV_CFOP = {"108": ("102", "Venda interestadual a não contribuinte: conversão automática do 5102/6102"),
              "107": ("101", "Venda de produção a não contribuinte: conversão automática do 5101/6101")}
# CFOPs que não existem ou não cabem na operação: são erro do XML e aparecem em Validações.
CFOP_INVALIDOS = {"5107": "Não existe x107 interno: venda interna a não contribuinte usa 5101/5401",
                  "5108": "Não existe x108 interno: venda interna a não contribuinte usa 5102/5403/5405"}


def cfop_base(cfop):
    """CFOP equivalente para comparar e agrupar: 'x' + 3 últimos dígitos, com as conversões automáticas."""
    if not USAR_EQUIVALENCIA_CFOP or len(cfop) != 4:
        return cfop
    fim = cfop[1:]
    return "x" + EQUIV_CFOP.get(fim, (fim, ""))[0]
# Segregações: o usuário confirmou que itens que pareciam divergentes são cenários legítimos e diferentes.
# Cada uma força o tributo a separar regras pelo critério: cfop | classe | origem | participante | uf
SEGREGACOES = []               # [{"tributo": "IBSEST", "dim": "cfop", "obs": "..."}]
DIM_SEGREGACAO = {"cfop": ("CFOP", 2), "classe": ("classe do produto", 0), "origem": ("origem", 0),
                  "participante": ("participante", 1), "uf": ("UF de destino", 3)}


def _familia(t):
    if t in FAMILIA_IBS:
        return FAMILIA_IBS
    if t in ("PIS", "COF"):
        return ("PIS", "COF")
    return (t,)


# Exceções: regra própria para itens de clientes, produtos ou NCMs específicos (quando nenhuma dimensão os separa).
# [{"id": "E1", "tributo": "CBSFED", "campo": "dest"|"cprod"|"ncm", "valores": [...], "obs": "..."}]
EXCECOES = []
CAMPOS_EXCECAO = {"dest": ("cliente", 1), "cprod": ("produto", 0), "ncm": ("NCM", 0)}
# alíquota corrigível por tributo: (campo da alíquota, campo do valor)
CAMPO_ALIQ = {"ICMS": ("picms", "vicms"), "ICMSST": ("picmsst", "vicmsst"), "DIFAL": ("pdifdest", "vdif"),
              "FECP": ("pfcp", "vfcp"), "FECPST": ("pfcpst", "vfcpst"), "FECPDF": ("pfcpdif", "vfcpdif"),
              "IPI": ("pipi", "vipi"), "PIS": ("ppis", "vpis"), "COF": ("pcof", "vcof"),
              "IBSEST": ("pibsuf", "vibsuf"), "IBSMUN": ("pibsmun", "vibsmun"), "CBSFED": ("pcbs", "vcbs")}


# Conhecimento com alcance "só esta empresa" (aprovado na tela, normalmente a partir de proposta da IA).
# Fica fora do .md (conhecimento_empresa.json) e o motor soma ao padrão geral quando analisa o emitente.
# {cnpj: {"regras_negocio": [{tributo, quando, entao, observacao}], "agrupamentos": [{tributo, criterio, decisao}],
#         "segregacoes": [{tributo, dim, obs}], "excecoes": [{id, tributo, campo, valores, obs}], "notas": [{texto}]}}
CONHECIMENTO_EMPRESA = {}


def _emp():
    return CONHECIMENTO_EMPRESA.get(_IDX_GRUPOS.get("cnpj") or "", {}) if CONHECIMENTO_EMPRESA else {}


def todas_excecoes():
    return EXCECOES + list(_emp().get("excecoes", []))


def excecao_de(t, d, it):
    for x in todas_excecoes():
        if x.get("tributo") in _familia(t) and x.get("campo") in CAMPOS_EXCECAO:
            v = d.get("dest", "") if x["campo"] == "dest" else it.get(x["campo"], "")
            if v in x.get("valores", []):
                return x
    return None


def dims_excecao(t):
    return {CAMPOS_EXCECAO[x["campo"]][1] for x in todas_excecoes()
            if x.get("tributo") in _familia(t) and x.get("campo") in CAMPOS_EXCECAO}


def segregacoes_de(t):
    """Critérios que o tributo deve separar obrigatoriamente (vale para a família: IBS/CBS, PIS/COFINS)."""
    return {x["dim"] for x in SEGREGACOES + list(_emp().get("segregacoes", []))
            if x.get("tributo") in _familia(t) and x.get("dim") in DIM_SEGREGACAO}


# ── Grupos derivados ─────────────────────────────────────────────────────────
# Grupo de clientes ou de produtos informado NA MÃO pelo usuário, filho de um perfil que já existe
# (ex.: "TRANSPORTADORA", filho de PJ | CONTRIB | NORMAL; "TRADE", filho de ORIGEM 2). No Protheus o grupo vira
# um grupo de tributação próprio, então o perfil pai deixa de enxergar esses clientes/produtos: em todo tributo
# que separa regras por participante (ou por produto) a regra do pai é DUPLICADA para o grupo (regra filha).
# Por tributo, a ação diz o que muda para o grupo:
#   duplicar  = mesmo tratamento do pai, mas em regra filha (a regra é duplicada onde o tributo usa perfil
#               específico; onde usa perfil geral, nada muda)
#   incluir   = mesmo tratamento do pai: o grupo de tributação entra no perfil do pai, sem regra nova
#   diferente = tratamento próprio, conforme o XML (o tributo passa a separar o grupo em regra própria)
#   ausente   = o tributo não existe para o grupo (ex.: transportadora sem ICMS ST) — com alcance opcional
# [{"id": "G1", "tipo": "participante"|"produto", "nome": "TRANSPORTADORA", "codigo": "CJCNTR", "descricao": "",
#   "valores": ["..."], "tributos": {"ICMSST": {"acao": "ausente", "alcance": {"abrangencia": "INTERNA"}}},
#   "obs": "", "cnpj": "emitente"}]
GRUPOS_DERIVADOS = []
ACOES_GRUPO = {"duplicar": "Mesmo tratamento do pai, em regra filha (duplica a regra)",
               "incluir": "Mesmo tratamento do pai, incluindo o grupo no perfil do pai (sem regra nova)",
               "diferente": "Tratamento próprio (conforme o XML)", "ausente": "Tributo não existe para o grupo"}
_IDX_GRUPOS = {"cnpj": None, "part": {}, "prod": {}, "id": {}}


def indexar_grupos(cnpj=None):
    """Monta os índices CNPJ/produto -> grupo para o emitente analisado (grupos sem emitente valem para todos)."""
    part, prod, ids = {}, {}, {}
    for gr in GRUPOS_DERIVADOS:
        if gr.get("cnpj") and cnpj and gr["cnpj"] != cnpj:
            continue
        ids[gr["id"]] = gr
        alvo = part if gr.get("tipo") == "participante" else prod
        for v in gr.get("valores", []):
            alvo.setdefault(str(v).strip(), gr)
    _IDX_GRUPOS.update(cnpj=cnpj, part=part, prod=prod, id=ids)


def grupo_por_id(gid):
    return _IDX_GRUPOS["id"].get(gid) or next((g_ for g_ in GRUPOS_DERIVADOS if g_["id"] == gid), None)


def grupo_cliente(d):
    return _IDX_GRUPOS["part"].get(d.get("dest", "")) if _IDX_GRUPOS["part"] else None


def grupo_produto(it):
    return _IDX_GRUPOS["prod"].get(it.get("cprod", "")) if _IDX_GRUPOS["prod"] else None


def acao_grupo(gr, t):
    """-> duplicar | incluir | diferente | ausente (sem escolha: duplica na família do ICMS, inclui nas demais)."""
    for x in _familia(t):
        a = (gr.get("tributos") or {}).get(x)
        if a and a.get("acao"):
            return "duplicar" if a["acao"] == "igual" else a["acao"]
    return "duplicar" if TRIBUTOS.get(t, ("",) * 6)[5] == "ORIG" else "incluir"


def alcance_grupo(gr, t):
    for x in _familia(t):
        a = (gr.get("tributos") or {}).get(x)
        if a:
            return a.get("alcance") or {}
    return {}


def _id_derivado(x):
    """'PJ Contribuinte · NORMAL »G1' -> 'G1'; 'N§I2§G2' -> 'G2'; senão ''."""
    if " »" in x:
        return x.split(" »", 1)[1]
    p = x.split("§")
    return p[2] if len(p) > 2 else ""


def _sem_derivado(x):
    if " »" in x:
        return x.split(" »", 1)[0]
    p = x.split("§")
    return "§".join(p[:2]) if len(p) > 2 else x


# ── Agrupamentos: perguntar antes de juntar ─────────────────────────────────
# O motor NÃO junta sozinho tipos de participante, regimes, origens e finalidades diferentes nos tributos da
# família do ICMS: gera o esqueleto separado (operação | origem | participante | regime | finalidade) e pergunta
# se pode juntar quando o tratamento é igual. A decisão fica no .md (## Agrupamentos): juntar | separar.
# Sem decisão = perguntar (gera separado e mostra a pergunta). Nos demais tributos o padrão é juntar.
CRITERIOS_AGRUP = {"tipo": ("tipo de participante (PJ/PF, contribuinte/não contribuinte)", 1),
                   "regime": ("regime do cliente (Simples/Normal)", 1),
                   "origem": ("origem do produto", 0),
                   "finalidade": ("finalidade (consumo/revenda)", 2),
                   "abrangencia": ("abrangência (interna/interestadual)", 3)}
AGRUPAMENTOS = {}        # (tributo | "*", critério) -> "juntar" | "separar"


def decisao_agrup(t, c):
    """-> 'juntar' | 'separar' | 'perguntar' (a decisão da empresa vale antes da geral)."""
    emp = {(x.get("tributo"), x.get("criterio")): x.get("decisao") for x in _emp().get("agrupamentos", [])}
    for k in [(x, c) for x in _familia(t)] + [("*", c)]:
        if k in emp:
            return emp[k]
    for k in [(x, c) for x in _familia(t)] + [("*", c)]:
        if k in AGRUPAMENTOS:
            return AGRUPAMENTOS[k]
    return "perguntar" if TRIBUTOS.get(t, ("",) * 6)[5] == "ORIG" else "juntar"


def criterio_aplicavel(t, c):
    dm = DIMENSOES.get(t, DIM_PADRAO)
    sg = segregacoes_de(t)
    if c in ("tipo", "regime"):
        return bool(dm["participante"] or "participante" in sg)
    if c == "origem":
        return bool(dm["origem"] or "origem" in sg)
    if c == "abrangencia":
        return dm["uf"] is True or "uf" in sg
    return bool(dm["finalidade"])


def criterios_separados(t):
    return {c for c in CRITERIOS_AGRUP if criterio_aplicavel(t, c) and decisao_agrup(t, c) != "juntar"}


def _chave_split(dim, x, crit, uf_emit=""):
    """Parte de um valor da dimensão que obriga regra própria (derivado sempre; demais conforme os critérios)."""
    if x in ("*", "*§*") or x.startswith("EXC:"):
        return x
    if dim == 1:
        base, der = (x.split(" »", 1) + [""])[:2]
        suf = base.endswith(" SUFRAMA")
        b2 = base.replace(" SUFRAMA", "")
        tipo, reg = (b2.split(" · ") + [""])[:2]
        return ("T:" + tipo + ("|Z" if suf else "") if "tipo" in crit else "",
                "R:" + reg if "regime" in crit else "", "D:" + der)
    if dim == 0:
        p = x.split("§")
        return ("O:" + (p[1] if len(p) > 1 else "") if "origem" in crit else "", "D:" + (p[2] if len(p) > 2 else ""))
    if dim == 2:
        fin = x.split("|")[1] if "|" in x else ""
        return "F:" + fin if "finalidade" in crit else ""
    if dim == 3 and "abrangencia" in crit:
        return "A:" + ("INTERNA" if x == uf_emit else "EXTERIOR" if x == "EX" else "INTERESTADUAL")
    return ""


def _separar_caixas(cx, crit, uf_emit=""):
    """Parte cada regra pelos critérios que não podem ser juntados e pelos grupos derivados.
    -> [(trat, b)], meta [{pai, chaves}] (pai = índice da regra antes de separar)."""
    from itertools import product as _prod
    novo, meta = [], []
    for i, (trat, b) in enumerate(cx):
        partes = []
        for dim in (0, 1, 2, 3):
            grupos = defaultdict(set)
            for x in b[dim]:
                grupos[_chave_split(dim, x, crit, uf_emit)].add(x)
            partes.append(sorted(grupos.items(), key=lambda kv: str(kv[0])))
        for combo in _prod(*partes):
            novo.append((trat, [frozenset(sx) for _, sx in combo]))
            meta.append({"pai": i, "chaves": tuple(k for k, _ in combo)})
    return novo, meta
ORDEM_TRIB = list(TRIBUTOS)
RAPUR_PADRAO = "000001"          # F2B_RAPUR como no modelo de importação
ALIQ_NCM = ("INCN01", "ÍNDICE DE CÁLCULO | NCM")
ALIQ_ZERO = ("ALQZER", "ALÍQUOTA ZERO")
INICIO_PERFIL_OPERACAO = 101     # POS101, POS102... (evita colidir com os POS existentes)

# Perfis de produto por origem (família ORIG), no padrão ICMN01/ICMI01/ICMI02/ICMC01
ORIGEM_GRUPO = {"0": "N", "3": "N", "4": "N", "5": "N", "8": "N", "1": "I1", "2": "I2", "6": "C", "7": "C"}
PERFIL_ORIGEM = {"N": ("ICMN01", "ICMS NACIONAL - ORIGEM 0/3/4/5/8", "ORIGEM 0/3/4/5/8"),
                 "I1": ("ICMI01", "ICMS IMPORTADO - ORIGEM 1", "ORIGEM 1"),
                 "I2": ("ICMI02", "ICMS IMPORTADO - ORIGEM 2", "ORIGEM 2"),
                 "C": ("ICMC01", "ICMS CAMEX - ORIGEM 6/7", "ORIGEM 6/7")}
PERFIL_PRODUTO_GERAL = ("PROD01", "GERAL | PRODUTOS")

# Perfis de participante: tipo do destinatário -> (código, descrição curta, critério sugerido)
# O REGIME (Simples/Normal) do cliente NÃO vem no XML: os códigos usam "G" (geral, ambos os regimes).
PERFIL_PARTICIPANTE = {
    "PJ Contribuinte":                 ("CJCG01", "PJ | CONTRIB",          "A1_PESSOA=J; A1_CONTRIB=1"),
    "PJ Isento":                       ("CJIG01", "PJ | ISENTO",           "A1_PESSOA=J; IE=ISENTO"),
    "PJ Não contribuinte":             ("CJNG01", "PJ | NÃO CONTRIB",      "A1_PESSOA=J; A1_CONTRIB=2"),
    "PJ Não contribuinte COM IE":      ("CJNE01", "PJ | NÃO CONTRIB C/ IE", "A1_PESSOA=J; A1_CONTRIB=2; com IE (conferir cadastro)"),
    "PF Não contribuinte":             ("CFNN01", "PF | NÃO CONTRIB",      "A1_PESSOA=F; A1_CONTRIB=2"),
    "PF Contribuinte (produtor rural)": ("CFCS01", "PF | CONTRIB",          "A1_PESSOA=F; A1_CONTRIB=1"),
    "PF Isento":                       ("CFIG01", "PF | ISENTO",           "A1_PESSOA=F; IE=ISENTO"),
    "Exterior":                        ("CEXG01", "EXTERIOR",              "A1_EST=EX"),
    "Consumidor":                      ("CCFG01", "CONSUMIDOR NÃO IDENTIF.", "sem destinatário (NFC-e)"),
}
PERFIL_PARTICIPANTE_GERAL = ("CGERAL", "CLIENTE | GERAL")

# Perfis de origem/destino (padrão do seu ambiente)
OD_INTERNA = ("000001", "OPERAÇÕES INTERNAS")
OD_INTERESTADUAL = ("000003", "SAÍDAS INTERESTADUAIS")
OD_TODAS = ("000002", "TODAS AS UFS")

# Operações: 3 últimos dígitos do CFOP -> (natureza, grupo, finalidade).
# Finalidade "indFinal" = vem da nota (1 = CONSUMO, 0 = REVENDA); qualquer outro texto é fixo.
OPERACAO = {}
for _c, _n, _g, _f in [
        ("101 102 103 104 105 106 107 108", "VENDA", "VENDAS", "indFinal"),
        ("109 110", "VENDA ZFM/ALC", "VENDAS", "indFinal"),
        ("111 112 113 114 115 116 117", "VENDA ENTREGA FUTURA", "VENDAS", "indFinal"),
        ("118 119 120", "VENDA À ORDEM", "VENDAS", "indFinal"),
        ("122 123", "VENDA P/ INDUSTRIALIZAÇÃO", "VENDAS", "indFinal"),
        ("401 403", "VENDA ST", "VENDAS", "indFinal"),
        ("405", "VENDA SUBSTITUÍDO", "VENDAS", "indFinal"),
        ("922", "SIMPLES FATURAMENTO", "VENDAS", "indFinal"),
        ("151 152 153 155 156", "TRANSFERÊNCIA", "TRANSFERÊNCIAS", "TRANSFERÊNCIA"),
        ("408 409", "TRANSFERÊNCIA ST", "TRANSFERÊNCIAS", "TRANSFERÊNCIA"),
        ("552", "TRANSFERÊNCIA ATIVO", "TRANSFERÊNCIAS", "TRANSFERÊNCIA"),
        ("557", "TRANSFERÊNCIA USO/CONSUMO", "TRANSFERÊNCIAS", "TRANSFERÊNCIA"),
        ("201 202 208 209 210", "DEVOLUÇÃO DE COMPRA", "DEVOLUÇÕES", "DEVOLUÇÃO"),
        ("410 411 412 413", "DEVOLUÇÃO DE COMPRA ST", "DEVOLUÇÕES", "DEVOLUÇÃO"),
        ("553", "DEVOLUÇÃO ATIVO", "DEVOLUÇÕES", "DEVOLUÇÃO"),
        ("556", "DEVOLUÇÃO USO/CONSUMO", "DEVOLUÇÕES", "DEVOLUÇÃO"),
        ("910", "BONIFICAÇÃO", "BONIFICAÇÕES", "indFinal"),
        ("911", "AMOSTRA GRÁTIS", "BONIFICAÇÕES", "indFinal"),
        ("551", "VENDA ATIVO", "ATIVO", "ATIVO"),
        ("501 502", "REMESSA EXPORTAÇÃO", "REMESSAS", "REMESSA"),
        ("901 902", "REMESSA INDUSTRIALIZAÇÃO", "REMESSAS", "REMESSA"),
        ("904", "REMESSA VENDA FORA DO ESTAB.", "REMESSAS", "REMESSA"),
        ("905 906 907", "DEPÓSITO", "REMESSAS", "REMESSA"),
        ("908 909", "COMODATO", "REMESSAS", "REMESSA"),
        ("912 913", "DEMONSTRAÇÃO", "REMESSAS", "REMESSA"),
        ("914", "REMESSA EXPOSIÇÃO/FEIRA", "REMESSAS", "REMESSA"),
        ("915 916", "CONSERTO", "REMESSAS", "REMESSA"),
        ("917 918 919", "CONSIGNAÇÃO", "REMESSAS", "REMESSA"),
        ("920 921", "VASILHAME", "REMESSAS", "REMESSA"),
        ("923 924", "REMESSA CONTA E ORDEM", "REMESSAS", "REMESSA"),
        ("925", "RETORNO CONSIGNAÇÃO", "REMESSAS", "REMESSA"),
        ("934", "REMESSA ARMAZÉM GERAL", "REMESSAS", "REMESSA"),
        ("927", "PERDA DE ESTOQUE", "OUTRAS", "OUTRAS"),
        ("929", "CUPOM FISCAL", "VENDAS", "indFinal"),
        ("949", "OUTRAS SAÍDAS", "OUTRAS", "OUTRAS")]:
    for _x in _c.split():
        OPERACAO[_x] = (_n, _g, _f)
NATUREZA = {k: v[0] for k, v in OPERACAO.items()}

# Modelo de decisão: por quais dimensões cada tributo PODE separar regras.
# O programa usa, dentre as permitidas, o MÍNIMO que o XML exigir. Proibida = perfil geral.
#   classe = classe do produto (CST do tributo nas vendas; para ICMS: com/sem ST)
#   operacao = "cfop" (perfil por CFOP) ou "grupo" (perfil por grupo: VENDAS, TRANSFERÊNCIAS...)
DIM_CAMPOS = ("classe", "origem", "participante", "uf", "operacao", "finalidade")
DIMENSOES = {
    "ICMS":   dict(classe=False, origem=True,  participante=True,  uf=True,  operacao="cfop",  finalidade=True),
    "ICMSST": dict(classe=False, origem=True,  participante=True,  uf="cada",operacao="cfop",  finalidade=True),
    "DIFAL":  dict(classe=False, origem=True,  participante=True,  uf="cada",operacao="cfop",  finalidade=True),
    "FECP":   dict(classe=False, origem=False, participante=True,  uf=True,  operacao="cfop",  finalidade=True),
    "FECPST": dict(classe=False, origem=False, participante=True,  uf="cada",operacao="cfop",  finalidade=True),
    "FECPDF": dict(classe=False, origem=False, participante=True,  uf="cada",operacao="cfop",  finalidade=True),
    "IPI":    dict(classe=True,  origem=True,  participante=False, uf=False, operacao="cfop", finalidade=False),
    "PIS":    dict(classe=True,  origem=False, participante=False, uf=False, operacao="cfop", finalidade=False),
    "COF":    dict(classe=True,  origem=False, participante=False, uf=False, operacao="cfop", finalidade=False),
    "IBSEST": dict(classe=True,  origem=False, participante=False, uf=False, operacao="cfop", finalidade=False),
    "IBSMUN": dict(classe=True,  origem=False, participante=False, uf=False, operacao="cfop", finalidade=False),
    "CBSFED": dict(classe=True,  origem=False, participante=False, uf=False, operacao="cfop", finalidade=False),
}

# Regras de negócio: (tributo, condições, ação, observação). O padrão prevalece sobre o XML.
# Condições: campo=valor (vírgula = OU, * no fim = começa com), unidas por " e ". Campos:
#   cfop natureza grupo finalidade uf abrangencia participante contribuinte pessoa origem ncm cest cst suframa
# Ações: base=CÓDIGO | ausente | aliquota=ncm
REGRAS_NEGOCIO = [
    ("ICMS", "grupo=VENDAS e finalidade=CONSUMO", "base=ICMP01", "No uso e consumo o IPI compõe a base do ICMS"),
    ("ICMS", "grupo=VENDAS e finalidade=REVENDA", "base=ICMI01", "Na comercialização o IPI não compõe a base do ICMS"),
    ("DIFAL", "contribuinte=SIM", "ausente", "DIFAL de saída só na venda a não contribuinte"),
    ("DIFAL", "abrangencia=INTERNA", "ausente", "DIFAL só em operação interestadual"),
    ("FECPDF", "contribuinte=SIM", "ausente", "FECP do DIFAL segue o DIFAL"),
]

# UFs (do EMITENTE) que exigem o código de benefício (cBenef) quando o ICMS não é destacado ou é reduzido.
# Cada regra de ICMS aceita UM único cBenef: códigos diferentes obrigam regras diferentes.
UFS_CBENEF = {"SC", "DF", "SP", "ES", "PR", "RS", "RJ", "GO"}
CST_EXIGE_CBENEF = {"20", "30", "40", "41", "50", "51", "70", "90"}

# Perfil de origem/destino para tributos com uma regra por combinação de UF (DIFAL, ST, FECP ST)
# Perfil de origem/destino por UF de destino, do padrão GF (tabela F21 do banco TESTE, perfis SIBSnn).
# Cada UF tem um código dedicado. ES, RJ, RS e SP não têm código único no banco, então ficam de fora
# e o motor gera OD{UF}01 para eles (aviso ao usuário: precisa confirmar o código GF).
GF_OD_POR_UF = {"AC": "SIBS22", "AL": "SIBSD5", "AM": "SIBS26", "AP": "SIBS07", "BA": "SIBS08", "CE": "SIBS09",
                "DF": "SIBS10", "GO": "SIBS12", "MA": "SIBS13", "MG": "SIBS14", "MS": "SIBS15", "MT": "SIBS16",
                "PA": "SIBS17", "PB": "SIBS18", "PE": "SIBS19", "PI": "SIBS20", "PR": "SIBS21", "RN": "SIBS23",
                "RO": "SIBS28", "RR": "SIBS24", "SC": "SIBS25", "SE": "SIBSD6", "TO": "SIBS27",
                # códigos NOVOS, aprovados pelo usuário (não existiam na GF)
                "ES": "SIBS34", "RJ": "SIBS35", "RS": "SIBS36", "SP": "SIBS37"}
OD_POR_UF = {uf: (cod, f"SAÍDAS INTERESTADUAIS → {uf}") for uf, cod in GF_OD_POR_UF.items()}   # UF -> (código, descrição)

# Escrituração (CJ2) — ação na nota (STOTNF) por tributo: (com valor, sem valor)
STOTNF_TXT = {"1": "Sem ação", "2": "Subtrai só do total da nota", "3": "Subtrai do total da nota e da duplicata",
              "4": "Subtrai só da duplicata", "5": "Soma só no total da nota", "6": "Soma no total da nota e da duplicata",
              "7": "Soma só na duplicata", "8": "Gross up na duplicata", "9": "Soma no total e não nas despesas"}
INCIDE_TXT = {"1": "Tributado", "2": "Isento", "3": "Outros", "4": "Tributado e Isento", "5": "Tributado e Outros",
              "6": "Isento e Outros", "7": "Tributado, Isento e Outros", "8": "Integração"}
STOTNF = {"ICMS": ("1", "1"), "ICMSST": ("6", "1"), "DIFAL": ("1", "1"), "FECP": ("1", "1"), "FECPST": ("6", "1"),
          "FECPDF": ("1", "1"), "IPI": ("6", "1"), "PIS": ("1", "1"), "COF": ("1", "1"),
          "IBSEST": ("1", "1"), "IBSMUN": ("1", "1"), "CBSFED": ("1", "1")}
STOTNF_DESONERADO = "3"   # ICMS desonerado com indDeduzDeson=1 subtrai do total
# Escrituração — INCIDE por tributo e CST. "valor" = 1 se houver imposto, senão 3. "*" = qualquer CST.
INCIDE = {
    ("ICMS", "00"): "1", ("ICMS", "10"): "1", ("ICMS", "20"): "4", ("ICMS", "70"): "4",
    ("ICMS", "30"): "2", ("ICMS", "40"): "2", ("ICMS", "41"): "3", ("ICMS", "50"): "3",
    ("ICMS", "51"): "3", ("ICMS", "60"): "3", ("ICMS", "90"): "valor",
    ("ICMS", "101"): "1", ("ICMS", "102"): "3", ("ICMS", "103"): "2", ("ICMS", "201"): "1", ("ICMS", "202"): "3",
    ("ICMS", "203"): "2", ("ICMS", "300"): "2", ("ICMS", "400"): "2", ("ICMS", "500"): "3", ("ICMS", "900"): "valor",
    ("IPI", "50"): "1", ("IPI", "51"): "2", ("IPI", "52"): "2", ("IPI", "53"): "3", ("IPI", "54"): "3",
    ("IPI", "55"): "3", ("IPI", "99"): "valor",
    ("PIS", "01"): "1", ("PIS", "02"): "1", ("PIS", "03"): "1", ("PIS", "05"): "1", ("PIS", "06"): "2",
    ("PIS", "07"): "2", ("PIS", "*"): "valor",
    ("COF", "01"): "1", ("COF", "02"): "1", ("COF", "03"): "1", ("COF", "05"): "1", ("COF", "06"): "2",
    ("COF", "07"): "2", ("COF", "*"): "valor",
    ("ICMSST", "*"): "1", ("DIFAL", "*"): "1", ("FECP", "*"): "1", ("FECPST", "*"): "1", ("FECPDF", "*"): "1",
    ("IBSEST", "*"): "valor", ("IBSMUN", "*"): "valor", ("CBSFED", "*"): "valor"}


def _incide(t, cst, valor):
    v = INCIDE.get((t, cst)) or INCIDE.get((t, "*")) or "valor"
    return ("1" if valor > 0 else "3") if v == "valor" else v


def _stot(t, valor):
    com, sem = STOTNF.get(t, ("1", "1"))
    return com if valor > 0 else sem


CST_ST = {"10", "30", "70", "201", "202", "203"}
AUTORIZADA = {"100", "150", ""}


# ═════════════════════════════════════════════════════════════════════════════
# LEITURA DO XML
# ═════════════════════════════════════════════════════════════════════════════
def _sem_ns(root):
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def _t(el, cam):
    if el is None:
        return ""
    x = el.find(cam)
    return (x.text or "").strip() if x is not None else ""


def _n(el, cam):
    try:
        return float(_t(el, cam) or 0)
    except ValueError:
        return 0.0


def _filho(el):
    if el is None:
        return None
    for c in el:
        return c
    return None


def tipo_destinatario(dest):
    if dest is None:
        return "Consumidor", "", "", False
    uf, ind, ie = _t(dest, "enderDest/UF"), _t(dest, "indIEDest"), _t(dest, "IE")
    suf = bool(_t(dest, "ISUF"))
    if dest.find("CNPJ") is not None:
        t = {"1": "PJ Contribuinte", "2": "PJ Isento"}.get(ind, "PJ Não contribuinte")
        if ind == "9" and ie:
            t = "PJ Não contribuinte COM IE"
        return t, _t(dest, "CNPJ"), uf, suf
    if dest.find("CPF") is not None:
        t = {"1": "PF Contribuinte (produtor rural)", "2": "PF Isento"}.get(ind, "PF Não contribuinte")
        return t, _t(dest, "CPF"), uf, suf
    if dest.find("idEstrangeiro") is not None:
        return "Exterior", _t(dest, "idEstrangeiro"), "EX", False
    return "Consumidor", "", uf, suf


def ler_xml_bytes(dados):
    """bytes -> ("nfe", doc) | ("canc", chave) | (None, None). Pura: serve para site/servidor."""
    try:
        root = _sem_ns(ET.fromstring(dados))
    except ET.ParseError:
        return None, None
    ev = root if root.tag == "infEvento" else root.find(".//infEvento")
    if ev is not None:
        return ("canc", _t(ev, "chNFe")) if _t(ev, "tpEvento") == "110111" else (None, None)
    inf = root.find(".//infNFe")
    if inf is None:
        return None, None
    ide, emit, dest = inf.find("ide"), inf.find("emit"), inf.find("dest")
    tipo, doc_dest, uf_dest, suframa = tipo_destinatario(dest)
    uf_emit = _t(emit, "enderEmit/UF")
    itens = []
    for det in inf.findall("det"):
        p, imp = det.find("prod"), det.find("imposto")
        g = (lambda nm: imp.find(nm) if imp is not None else None)
        icms, dif, ipi, ibs = _filho(g("ICMS")), g("ICMSUFDest"), g("IPI"), g("IBSCBS")
        ipi_g = None if ipi is None else (ipi.find("IPITrib") if ipi.find("IPITrib") is not None else ipi.find("IPINT"))
        pis, cof = _filho(g("PIS")), _filho(g("COFINS"))
        gi = ibs.find("gIBSCBS") if ibs is not None else None
        it = {
            "cprod": _t(p, "cProd"), "xprod": _t(p, "xProd"), "ncm": _t(p, "NCM"), "cest": _t(p, "CEST"),
            "cbenef": _t(p, "cBenef"), "cfop": _t(p, "CFOP"), "vprod": _n(p, "vProd"), "vfrete": _n(p, "vFrete"), "vseg": _n(p, "vSeg"),
            "voutro": _n(p, "vOutro"), "vdesc": _n(p, "vDesc"),
            "orig": _t(icms, "orig"), "cst": _t(icms, "CST") or _t(icms, "CSOSN"),
            "predbc": _n(icms, "pRedBC"), "vbc": _n(icms, "vBC"), "picms": _n(icms, "pICMS"), "vicms": _n(icms, "vICMS"),
            "vdeson": _n(icms, "vICMSDeson"), "motdes": _t(icms, "motDesICMS"), "deduzdes": _t(icms, "indDeduzDeson"),
            "pdif": _n(icms, "pDif"), "vbcfcp": _n(icms, "vBCFCP"), "pfcp": _n(icms, "pFCP"), "vfcp": _n(icms, "vFCP"),
            "vbcst": _n(icms, "vBCST"), "pmvast": _n(icms, "pMVAST"), "predbcst": _n(icms, "pRedBCST"),
            "picmsst": _n(icms, "pICMSST"), "vicmsst": _n(icms, "vICMSST"),
            "vbcfcpst": _n(icms, "vBCFCPST"), "pfcpst": _n(icms, "pFCPST"), "vfcpst": _n(icms, "vFCPST"),
            "tem_dif": dif is not None, "vbcdif": _n(dif, "vBCUFDest"), "pdifdest": _n(dif, "pICMSUFDest"),
            "pinter": _n(dif, "pICMSInter"), "vdif": _n(dif, "vICMSUFDest"),
            "vbcfcpdif": _n(dif, "vBCFCPUFDest"), "pfcpdif": _n(dif, "pFCPUFDest"), "vfcpdif": _n(dif, "vFCPUFDest"),
            "tem_ipi": ipi_g is not None, "cst_ipi": _t(ipi_g, "CST"), "vbcipi": _n(ipi_g, "vBC"),
            "pipi": _n(ipi_g, "pIPI"), "vipi": _n(ipi_g, "vIPI"),
            "cst_pis": _t(pis, "CST"), "vbcpis": _n(pis, "vBC"), "ppis": _n(pis, "pPIS"), "vpis": _n(pis, "vPIS"),
            "cst_cof": _t(cof, "CST"), "vbccof": _n(cof, "vBC"), "pcof": _n(cof, "pCOFINS"), "vcof": _n(cof, "vCOFINS"),
            "tem_ibs": ibs is not None, "cst_ibs": _t(ibs, "CST"), "cclass": _t(ibs, "cClassTrib"),
            "vbcibs": _n(gi, "vBC"), "pibsuf": _n(gi, "gIBSUF/pIBSUF"), "vibsuf": _n(gi, "gIBSUF/vIBSUF"),
            "pibsmun": _n(gi, "gIBSMun/pIBSMun"), "vibsmun": _n(gi, "gIBSMun/vIBSMun"),
            "pcbs": _n(gi, "gCBS/pCBS"), "vcbs": _n(gi, "gCBS/vCBS"),
        }
        itens.append(it)
    dh = _t(ide, "dhEmi") or _t(ide, "dEmi")
    return "nfe", {
        "chave": (inf.get("Id") or "")[3:], "num": _t(ide, "nNF"), "tpnf": _t(ide, "tpNF"),
        "fin": _t(ide, "finNFe"), "indfinal": _t(ide, "indFinal"), "cstat": _t(root, ".//protNFe/infProt/cStat"),
        "dt": dh[0:4] + dh[5:7] + dh[8:10] if len(dh) >= 10 else "",
        "emit": _t(emit, "CNPJ") or _t(emit, "CPF"), "emit_nome": _t(emit, "xNome"), "uf_emit": uf_emit,
        "tipo": tipo, "dest": doc_dest, "dest_nome": _t(dest, "xNome"), "uf_dest": uf_dest or uf_emit,
        "suframa": suframa, "itens": itens}


def _listar(caminho):
    if os.path.isfile(caminho) and caminho.lower().endswith(".zip"):
        zips, soltos = [caminho], []
    elif os.path.isfile(caminho):
        zips, soltos = [], [caminho]
    else:
        zips, soltos = [], []
        for raiz, _, arqs in os.walk(caminho):
            for a in arqs:
                (zips if a.lower().endswith(".zip") else soltos if a.lower().endswith(".xml") else []).append(
                    os.path.join(raiz, a))
    for p in sorted(soltos):
        yield p, None
    for z in sorted(zips):
        try:
            with zipfile.ZipFile(z) as zf:
                for nm in zf.namelist():
                    if nm.lower().endswith(".xml"):
                        yield nm, z
        except (zipfile.BadZipFile, OSError):
            pass


def ler_pasta(caminho, avisar=print):
    docs, canc = {}, set()
    lista, zf, zn, t0 = list(_listar(caminho)), None, None, time.time()
    try:
        for i, (nm, z) in enumerate(lista, 1):
            try:
                if z:
                    if z != zn:
                        if zf:
                            zf.close()
                        zf, zn = zipfile.ZipFile(z), z
                    dados = zf.read(nm)
                else:
                    with open(nm, "rb") as f:
                        dados = f.read()
            except Exception:
                continue
            tp, val = ler_xml_bytes(dados)
            if tp == "nfe" and val["chave"]:
                docs[val["chave"]] = val
            elif tp == "canc":
                canc.add(val)
            if i % 1000 == 0 or i == len(lista):
                avisar(f"Lendo XMLs: {i:,}/{len(lista):,} ({i / max(time.time() - t0, .01):,.0f}/s)".replace(",", "."))
    finally:
        if zf:
            zf.close()
    return docs, canc


def emitentes(docs, canc):
    c, nomes = Counter(), {}
    for d in docs.values():
        if _valida(d, canc):
            c[d["emit"]] += 1
            nomes[d["emit"]] = d["emit_nome"]
    return [(k, nomes[k], q) for k, q in c.most_common()]


def _valida(d, canc):
    return d["tpnf"] == "1" and d["chave"] not in canc and d["cstat"] in AUTORIZADA and d["fin"] in ("1", "")


# ═════════════════════════════════════════════════════════════════════════════
# TRATAMENTO DE CADA TRIBUTO NO ITEM (escrituração, base, alíquota)
# ═════════════════════════════════════════════════════════════════════════════
def _ok(a, b):
    return abs(a - b) <= max(0.05, abs(b) * 0.001)


def _fmt(v):
    return f"{v:.4f}".rstrip("0").rstrip(".").replace(".", ",")


def _base_merc(it):
    return it["vprod"] + it["vfrete"] + it["vseg"] + it["voutro"] - it["vdesc"]


# Composições de base: (código F27, descrição, fórmula do Configurador, função)
BASES = {
    "ICMS": [("ICMI01", "ICMS | BASE INTEGRAL", "O:VAL_MERCADORIA + O:FRETE + O:SEGURO + O:DESPESAS - O:DESCONTO",
              lambda it: _base_merc(it)),
             ("ICMP01", "ICMS | BASE INTEGRAL + IPI", "O:VAL_MERCADORIA + O:FRETE + O:SEGURO + O:DESPESAS - O:DESCONTO + IPI",
              lambda it: _base_merc(it) + it["vipi"])],
    "IPI": [("BCIPI1", "IPI | MERCADORIA + FRETE + SEGURO + DESPESAS - DESCONTO",
             "O:VAL_MERCADORIA + O:FRETE + O:SEGURO + O:DESPESAS - O:DESCONTO", _base_merc),
            ("BCIPI2", "IPI | MERCADORIA - DESCONTO", "O:VAL_MERCADORIA - O:DESCONTO",
             lambda it: it["vprod"] - it["vdesc"]),
            ("BCIPI3", "IPI | MERCADORIA", "O:VAL_MERCADORIA", lambda it: it["vprod"])],
    "PC": [("PC001", "PIS/COFINS | COM EXCLUSÃO DO ICMS",
            "O:VAL_MERCADORIA + O:FRETE + O:SEGURO + O:DESPESAS - O:DESCONTO - O:VAL_ICM_TRIBUTADO",
            lambda it: _base_merc(it) - it["vicms"]),
           ("PC002", "PIS/COFINS | SEM EXCLUSÃO DO ICMS", "O:VAL_MERCADORIA + O:FRETE + O:SEGURO + O:DESPESAS - O:DESCONTO",
            _base_merc)],
    "IBS": [("IBC001", "IBS/CBS | DEDUZ ICMS, PIS, COFINS, FECP E DIFAL",
             "O:VAL_MERCADORIA + O:FRETE + O:SEGURO + O:DESPESAS + O:VAL_II - O:DESCONTO - O:VAL_PS2 - O:VAL_CF2 "
             "- O:VAL_ICM_TRIBUTADO - O:VAL_DIFAL - O:VAL_FECP - O:VAL_FCPDIF",
             lambda it: _base_merc(it) - it["vpis"] - it["vcof"] - it["vicms"] - it["vdif"] - it["vfcp"] - it["vfcpdif"]),
            ("IBC002", "IBS/CBS | IBC001 E DEDUZ IPI", "IBC001 - O:VAL_IPI_TRIBUTADO",
             lambda it: _base_merc(it) - it["vpis"] - it["vcof"] - it["vicms"] - it["vdif"] - it["vfcp"]
             - it["vfcpdif"] - it["vipi"]),
            ("IBC003", "IBS/CBS | VALOR DA OPERAÇÃO", "O:VAL_MERCADORIA + O:FRETE + O:SEGURO + O:DESPESAS - O:DESCONTO",
             _base_merc),
            ("IBC004", "IBS/CBS | VALOR DA OPERAÇÃO + IPI", "... + IPI", lambda it: _base_merc(it) + it["vipi"])],
}
BASE_ZERO = ("BASZER", "BASE ZERO", "")
# Cada regra de base aceita UM percentual de redução: uma base por composição × percentual.
PREFIXO_REDUCAO = {"ICMI01": "ICR", "ICMP01": "ICP", "BCIPI1": "IPR", "BCIPI2": "IPS", "BCIPI3": "IPT",
                   "PC001": "PCR", "PC002": "PCS", "IBC001": "IBR", "IBC002": "IBS", "IBC003": "IBT", "IBC004": "IBU"}
BASE_INDEF = ("?BASE?", "BASE NÃO IDENTIFICADA PELOS VALORES DO XML", "")


def _achar_base(fam, it, vbc, red=0.0):
    if vbc <= 0:
        return BASE_ZERO
    for cod, desc, form, fn in BASES[fam]:
        cheia = fn(it)
        if _ok(vbc, cheia):
            return (cod, desc, form)
        if red and _ok(vbc, cheia * (1 - red / 100)):
            pref = PREFIXO_REDUCAO.get(cod, cod[:2] + "R")
            return (f"{pref}{int(round(red * 10)):03d}"[:6], f"{desc} | REDUÇÃO {_fmt(red)}%",
                    f"({form}) × (1 - {_fmt(red)}%)")
    return BASE_INDEF


def tratamentos(d, it):
    """{tributo: (esc, base, aliq_valores, cbenef)} dos tributos presentes no item.
    esc = (CSTCAB, CST, INCIDE, STOTNF, PERDIF, cClassTrib/obs); base = (cód, desc, fórmula);
    aliq_valores = números que a regra precisa produzir; cbenef = código de ajuste (só ICMS)."""
    r = {}
    cst = it["cst"]
    cab = "000002" if len(cst) == 3 else "000001"
    if cst:
        stot = STOTNF_DESONERADO if it["vdeson"] > 0 and it["deduzdes"] == "1" else _stot("ICMS", it["vicms"])
        base = BASE_ZERO if it["vicms"] <= 0 and it["vbc"] <= 0 else _achar_base("ICMS", it, it["vbc"], it["predbc"])
        r["ICMS"] = ((cab, cst, _incide("ICMS", cst, it["vicms"]), stot, _fmt(it["pdif"]) if it["pdif"] else "",
                      ""),
                     base, (it["picms"],) if it["vicms"] > 0 else (0.0,), it.get("cbenef", ""))
    if it["vicmsst"] > 0 or it["vbcst"] > 0:
        cheia = (_base_merc(it) + it["vipi"]) * (1 + it["pmvast"] / 100)
        red = it["predbcst"]
        if _ok(it["vbcst"], cheia * (1 - red / 100)):
            b = ("ISTB01", "ICMS ST | (MERCADORIA + IPI) × MVA" + (f" | RED. {_fmt(red)}%" if red else ""),
                 "(O:VAL_MERCADORIA + O:FRETE + O:SEGURO + O:DESPESAS - O:DESCONTO + IPI) × (1 + MVA)")
        elif _ok(it["vbcst"], _base_merc(it) * (1 + it["pmvast"] / 100) * (1 - red / 100)):
            b = ("ISTB02", "ICMS ST | MERCADORIA × MVA (SEM IPI)", "(O:VAL_MERCADORIA + ... - O:DESCONTO) × (1 + MVA)")
        else:
            b = ("ISTB99", "ICMS ST | PAUTA OU BASE NÃO IDENTIFICADA", "")
        r["ICMSST"] = (("000001", cst, _incide("ICMSST", cst, it["vicmsst"]), _stot("ICMSST", it["vicmsst"]), "", ""),
                       b, (it["picmsst"], it["pmvast"]), "")
    if it["tem_dif"] and (it["vdif"] > 0 or it["vbcdif"] > 0):
        if _ok(it["vbcdif"], it["vbc"]):
            b = ("DIFS01", "DIFAL | BASE SIMPLES", "BASE DO ICMS")
        elif it["vbcdif"] > it["vbc"]:
            b = ("DIFD01", "DIFAL | BASE DUPLA", "(BASE - ICMS ORIGEM) / (1 - ALÍQ. DESTINO)")
        else:
            b = ("DIFX01", "DIFAL | BASE NÃO IDENTIFICADA", "")
        r["DIFAL"] = (("000001", cst, _incide("DIFAL", cst, it["vdif"]), _stot("DIFAL", it["vdif"]), "", ""),
                      b, (it["pdifdest"], it["pinter"]), "")
        if it["vfcpdif"] > 0:
            r["FECPDF"] = (("000001", cst, _incide("FECPDF", cst, it["vfcpdif"]), _stot("FECPDF", it["vfcpdif"]), "", ""),
                           b, (it["pfcpdif"],), "")
    if it["vfcp"] > 0:
        r["FECP"] = (("000001", cst, _incide("FECP", cst, it["vfcp"]), _stot("FECP", it["vfcp"]), "", ""),
                     ("FCPB01", "FECP | MESMA BASE DO ICMS", "BASE DO ICMS"), (it["pfcp"],), "")
    if it["vfcpst"] > 0:
        r["FECPST"] = (("000001", cst, _incide("FECPST", cst, it["vfcpst"]), _stot("FECPST", it["vfcpst"]), "", ""),
                       ("FSTB01", "FECP ST | MESMA BASE DO ICMS ST", "BASE DO ICMS ST"), (it["pfcpst"],), "")
    if it["tem_ipi"]:
        c = it["cst_ipi"]
        base = _achar_base("IPI", it, it["vbcipi"]) if it["vipi"] > 0 else ("BCZR00", "IPI | BASE ZERO", "")
        r["IPI"] = (("000003", c, _incide("IPI", c, it["vipi"]), _stot("IPI", it["vipi"]), "", ""), base,
                    (it["pipi"],) if it["vipi"] > 0 else (0.0,), "")
    for t, cc, vb, pp, vv, cab_ in (("PIS", "cst_pis", "vbcpis", "ppis", "vpis", "000005"),
                                    ("COF", "cst_cof", "vbccof", "pcof", "vcof", "000006")):
        if it[cc]:
            base = _achar_base("PC", it, it[vb]) if it[vv] > 0 else BASE_ZERO
            r[t] = ((cab_, it[cc], _incide(t, it[cc], it[vv]), _stot(t, it[vv]), "", ""), base,
                    (it[pp],) if it[vv] > 0 else (0.0,), "")
    if it["tem_ibs"] and it["cst_ibs"]:
        base = _achar_base("IBS", it, it["vbcibs"])
        for t, p_, v in (("IBSEST", "pibsuf", "vibsuf"), ("IBSMUN", "pibsmun", "vibsmun"), ("CBSFED", "pcbs", "vcbs")):
            r[t] = (("", it["cst_ibs"], _incide(t, it["cst_ibs"], it[v]), _stot(t, it[v]), "", it["cclass"]), base,
                    (it[p_],), "")
    return r


# ═════════════════════════════════════════════════════════════════════════════
# ANÁLISE: cenários -> regras com o mínimo de sobreposição
# ═════════════════════════════════════════════════════════════════════════════
def operacao(cfop, d):
    """-> (natureza, grupo, finalidade) do CFOP, com a finalidade da nota quando for 'indFinal'."""
    nat, grupo, fin = OPERACAO.get(cfop[1:], (f"CFOP {cfop}", "OUTRAS", "OUTRAS"))
    if fin.lower() == "indfinal":
        fin = FINALIDADE_CLIENTE.get(d.get("dest", "")) or ("CONSUMO" if d["indfinal"] == "1" else "REVENDA")
    return nat, grupo, fin


def tipo_operacao(fin):
    """-> (código, descrição) do tipo de operação para a finalidade, pelo de-para dos padrões."""
    return TIPOS_OPERACAO.get(fin, ("", ""))


def _rotulo_tipo(fin):
    if not fin:
        return "— | TODAS AS FINALIDADES"
    cod, desc = tipo_operacao(fin)
    return f"{cod} | {fin} | {desc}" if cod else f"— | {fin} | sem tipo de operação no de-para"


def _fin(d, it=None):
    return operacao(it["cfop"], d)[2] if it else ("CONSUMO" if d["indfinal"] == "1" else "REVENDA")


def _classe_produto(fam, it, modas):
    if fam == "ORIG":
        return ORIGEM_GRUPO.get(it["orig"], "N")
    return modas[fam].get(it["cprod"], "")


DIM_PADRAO = dict(classe=True, origem=True, participante=True, uf=True, operacao="cfop", finalidade=True)


def participante_de(d):
    """Participante do cenário: tipo do destinatário (XML) + regime (planilha) + SUFRAMA."""
    reg = REGIME_CLIENTE.get(d.get("dest", ""), "") if d["tipo"].startswith("PJ") else ""
    return d["tipo"] + (f" · {reg}" if reg else "") + (" SUFRAMA" if d["suframa"] else "")


def combo_icms(it):
    """CST + alíquota + composição da base do ICMS (inclui a redução). Usado como classe nos impostos ORIG."""
    try:
        base = _achar_base("ICMS", it, it["vbc"], it["predbc"])
        form = base[2] or "-"
    except Exception:
        form = "-"
    # a alíquota não separa regra: ela vem da tabela por NCM/CEST/UF/origem (quando essa opção está ligada)
    return f"CST{it.get('cst', '')}|{form}"


def combo_imposto(t, it):
    """CST + alíquota + composição da base de CADA imposto (IPI, PIS, COFINS, IBSEST, IBSMUN, CBSFED)."""
    try:
        if t == "IPI":
            cst, aliq, base = it.get("cst_ipi", ""), it.get("pipi", 0), _achar_base("IPI", it, it.get("vbcipi", 0))
        elif t in ("PIS", "COF"):
            sufixo = "pis" if t == "PIS" else "cof"
            cst = it.get(f"cst_{sufixo}", "")
            aliq = it.get("ppis" if t == "PIS" else "pcof", 0)
            base = _achar_base("PC", it, it.get("vbcpis" if t == "PIS" else "vbccof", 0))
        else:  # IBSEST, IBSMUN, CBSFED
            cst = it.get("cst_ibs", "")
            aliq = it.get(CAMPO_ALIQ[t][0], 0)
            base = _achar_base("IBS", it, it.get("vbcibs", 0))
        form = base[2] or "-"
    except Exception:
        cst, aliq, form = "", 0, "-"
    extra = f"|CCT{it.get('cclass', '')}" if t in ("IBSEST", "IBSMUN", "CBSFED") else ""
    # alíquota fora da classe: vem da tabela por NCM/CEST/UF/origem
    return f"{t}:CST{cst}|{form}{extra}"


def _classe_fam(fam, it, modas, t=None):
    """IPI, PIS/COFINS e IBS: classe = CST + alíquota + base do próprio imposto. ICMS e demais: como antes."""
    if fam in ("IPI", "PC", "IBS"):
        return combo_imposto(t, it)
    return modas[fam].get(it["cprod"], "")


def _part_gf(conjunto):
    """Participante no padrão GF: PJ/PF | CONT./NÃO CONT. | SIMPLES/NORMAL. Conjunto com vários -> só o que for comum."""
    toks = sorted({x.split(" »")[0].split(" SUFRAMA")[0] for x in conjunto if x and x != "*"})
    if len(toks) != 1:
        return []
    base, _, reg = toks[0].partition(" · ")
    if base.startswith("Consumidor") or base.startswith("Exterior"):
        return [base.upper()]
    pessoa = "PJ" if base.startswith("PJ") else "PF" if base.startswith("PF") else base.split()[0].upper()
    if "Não contribuinte" in base:
        contrib = "NÃO CONT."
    elif "Isento" in base:
        contrib = "ISENTO"
    else:
        contrib = "CONT."
    reg = reg.strip().upper().replace("SIMPLES NACIONAL", "SIMPLES")
    return [pessoa, contrib] + ([reg] if reg else [])


def celula(t, d, it, modas, forcar_part=False):
    """Coordenadas do item para o tributo t: (produto, participante, operação, UF).
    Dimensão proibida no modelo de decisão vira '*' (= perfil geral)."""
    dm = DIMENSOES.get(t, DIM_PADRAO)
    sg = segregacoes_de(t)
    fam = TRIBUTOS[t][5]
    nat, grupo, fin = operacao(it["cfop"], d)
    classe = _classe_fam(fam, it, modas, t) if (dm["classe"] or "classe" in sg) else "*"
    orig = ORIGEM_GRUPO.get(it["orig"], "N") if (dm["origem"] or "origem" in sg) else "*"
    part = participante_de(d) if (dm["participante"] or forcar_part or "participante" in sg) else "*"
    op = (cfop_base(it["cfop"]) if (dm["operacao"] == "cfop" or "cfop" in sg) else grupo) + \
        (f"|{fin}" if dm["finalidade"] else "")
    uf = d["uf_dest"] if (dm["uf"] or "uf" in sg) else "*"
    prod = f"{classe}§{orig}"
    if fam == "ORIG":
        # ICMS, ST, DIFAL e FECP: além da origem, a combinação CST + alíquota + composição da base
        # (com a redução, quando houver) separa os itens com tratamento diferente.
        prod = f"{prod}§{combo_icms(it)}"
    # grupo derivado: separa onde o tributo já usa perfil específico, ou onde o grupo tem tratamento próprio
    gc = grupo_cliente(d)
    if gc:
        a = acao_grupo(gc, t)
        if a in ("diferente", "ausente") or (a == "duplicar" and part != "*"):
            part = (participante_de(d) if part == "*" else part) + f" »{gc['id']}"
    gp = grupo_produto(it)
    if gp:
        a = acao_grupo(gp, t)
        if a in ("diferente", "ausente") or (a == "duplicar" and prod != "*§*"):
            prod = f"{prod}§{gp['id']}"
    ex = excecao_de(t, d, it) if (EXCECOES or _emp().get("excecoes")) else None
    if ex:
        if ex["campo"] == "dest":
            part = f"EXC:{ex['id']}"
        else:
            prod = f"EXC:{ex['id']}"
    return (prod, part, op, uf)


def _norm(x):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", str(x).upper()) if unicodedata.category(c) != "Mn").strip()


def contexto(d, it):
    nat, grupo, fin = operacao(it["cfop"], d)
    tipo = d["tipo"]
    if "Isento" in tipo:
        contrib = "ISENTO"
    elif "Não contribuinte" in tipo or tipo in ("Consumidor", "Exterior"):
        contrib = "NAO"
    else:
        contrib = "SIM"
    abr = "INTERNA" if d["uf_dest"] == d["uf_emit"] else ("EXTERIOR" if d["uf_dest"] == "EX" else "INTERESTADUAL")
    return {k: _norm(v) for k, v in {
        "CFOP": it["cfop"], "CFOP_BASE": cfop_base(it["cfop"]), "NATUREZA": nat, "GRUPO": grupo, "FINALIDADE": fin, "UF": d["uf_dest"],
        "UF_EMIT": d["uf_emit"], "ABRANGENCIA": abr, "PARTICIPANTE": tipo, "CONTRIBUINTE": contrib,
        "REGIME": REGIME_CLIENTE.get(d.get("dest", ""), "NAO INFORMADO"),
        "PESSOA": "PF" if tipo.startswith("PF") else ("PJ" if tipo.startswith("PJ") else tipo),
        "ORIGEM": it["orig"], "NCM": it["ncm"], "CEST": it["cest"], "CST": it["cst"],
        "SUFRAMA": "SIM" if d["suframa"] else "NAO",
        "GRUPOCLIENTE": (grupo_cliente(d) or {}).get("nome", ""),
        "GRUPOPRODUTO": (grupo_produto(it) or {}).get("nome", "")}.items()}


def _compilar_condicoes(txt):
    conds = []
    if not txt.strip() or _norm(txt) in ("SEMPRE", "*", "-"):
        return conds
    for parte in re.split(r"\s+e\s+|;", txt, flags=re.I):
        m = re.match(r"^\s*([A-Za-zÀ-ú_]+)\s*(!=|=)\s*(.+?)\s*$", parte)
        if not m:
            raise ValueError(f"condição inválida: '{parte}'")
        conds.append((_norm(m.group(1)), m.group(2), [_norm(v) for v in m.group(3).split(",") if v.strip()]))
    return conds


def _bate(conds, ctx):
    for campo, op, vals in conds:
        v = ctx.get(campo, "")
        ok = any(v.startswith(x[:-1]) if x.endswith("*") else v == x for x in vals)
        if ok != (op == "="):
            return False
    return True


def _chave_trib(nome):
    n = _norm(nome)
    for k, v in TRIBUTOS.items():
        if n in (_norm(k), _norm(v[0]), _norm(v[1])):
            return k
    return None


def _mesma_familia_base(atual, regra):
    """A regra de base só substitui bases da mesma família 'integral' (com/sem IPI) ou não identificadas;
    bases com redução, pauta ou fórmulas específicas são preservadas."""
    integrais = {"ICMI01", "ICMP01", "?BASE?", "BCIPI1", "BCIPI2", "BCIPI3", "PC001", "PC002",
                 "IBC001", "IBC002", "IBC003", "IBC004", "ISTB01", "ISTB02", "DIFS01", "DIFD01"}
    return atual in integrais or atual == regra


def _base_catalogo(cod):
    for lista in BASES.values():
        for c, desc, form, _ in lista:
            if c == cod:
                return (c, desc, form)
    known = {"ICMI01": ("ICMI01", "ICMS | BASE INTEGRAL", "O:VAL_MERCADORIA + O:FRETE + O:SEGURO + O:DESPESAS - O:DESCONTO"),
             BASE_ZERO[0]: BASE_ZERO, "BCZR00": ("BCZR00", "IPI | BASE ZERO", "")}
    return known.get(cod, (cod, "BASE DEFINIDA NO PADRÃO", "conforme padrões"))


def _intersecta(a, b):
    return all(a[i] & b[i] for i in range(4))


def _dependencia(cel, universos, obrig=()):
    """Descobre de quais dimensões (0 produto, 1 participante, 2 operação, 3 UF) o tratamento depende.
    Usa o menor conjunto que explica os itens quase tão bem quanto as 4 dimensões juntas."""
    from itertools import combinations
    tot = sum(sum(c.values()) for c in cel.values()) or 1

    def proj(S):
        pr = defaultdict(Counter)
        for c, cnt in cel.items():
            pr[tuple(c[i] for i in S)].update(cnt)
        return sum(max(v.values()) for v in pr.values()) / tot, pr
    base, _ = proj((0, 1, 2, 3))
    for tam in range(5):
        cands = [(proj(S)[0], S) for S in combinations(range(4), tam) if set(obrig) <= set(S)]
        cands = [x for x in cands if x[0] >= base - 0.002]
        if cands:
            acc, S = max(cands)
            pr = proj(S)[1]
            caixas = []
            for k, cnt in pr.items():
                b = [universos[i] for i in range(4)]
                for pos, i in enumerate(S):
                    b[i] = frozenset([k[pos]])
                caixas.append((cnt.most_common(1)[0][0], b, cnt))
            return S, caixas


def _mesclar(caixas, agressivo=True, fixos=frozenset()):
    """caixas: [(tratamento|None, [4 frozensets])] disjuntas. Junta em regras sem sobreposição.
    None = tributo ausente: não vira regra, mas impede que uma regra o cubra."""

    def uma_dimensao(cx):
        mudou = True
        while mudou:
            mudou = False
            for d in (3, 2, 1, 0):          # UF, operação, participante, produto
                if d in fixos:
                    continue
                grupos = {}
                for t, b in cx:
                    grupos.setdefault((t,) + tuple(b[i] for i in range(4) if i != d), []).append(b)
                if len(grupos) < len(cx):
                    mudou = True
                    novo = []
                    for k, bs in grupos.items():
                        b = list(bs[0])
                        b[d] = frozenset().union(*[x[d] for x in bs])
                        novo.append((k[0], b))
                    cx = novo
        return cx

    caixas = uma_dimensao([(t, list(b)) for t, b in caixas])
    if agressivo:
        for _ in range(50):
            juntou = False
            por_trat = defaultdict(list)
            for i, (t, b) in enumerate(caixas):
                if t is not None:
                    por_trat[t].append(i)
            for t, idx in por_trat.items():
                pares = sorted(((sum(caixas[i][1][k] == caixas[j][1][k] for k in range(4)), i, j)
                                for a, i in enumerate(idx) for j in idx[a + 1:]), reverse=True)
                for _, i, j in pares:
                    if any(caixas[i][1][k] != caixas[j][1][k] for k in fixos):
                        continue
                    u = [caixas[i][1][k] | caixas[j][1][k] for k in range(4)]
                    if not any(_intersecta(u, b) for m, (_, b) in enumerate(caixas) if m not in (i, j)):
                        caixas = [c for m, c in enumerate(caixas) if m not in (i, j)] + [(t, u)]
                        juntou = True
                        break
                if juntou:
                    break
            if not juntou:
                break
            caixas = uma_dimensao(caixas)
    return caixas


def _expandir(caixas, universos, uf_emit, fixos=frozenset()):
    """Amplia UF e produto de cada regra para o universo quando isso não invade outra caixa:
    a regra passa a valer também para UFs/produtos ainda não vendidos (ex.: 000003 todas interestaduais)."""
    for i in range(len(caixas)):
        t, b = caixas[i]
        if t is None:
            continue
        for d, alvo in ((3, universos[3] - {uf_emit} if uf_emit not in b[3] else universos[3]), (0, universos[0])):
            if d in fixos or b[d] >= alvo:
                continue
            nb = list(b)
            nb[d] = frozenset(alvo)
            if not any(_intersecta(nb, x) for m, (_, x) in enumerate(caixas) if m != i):
                caixas[i] = (t, nb)
                b = nb
    return caixas


# ── correções de XML ──────────────────────────────────────────────────────────
_ZERA_ICMS = {"40", "41", "50", "60", "102", "103", "300", "400", "500"}
_ZERA_PC = {"04", "05", "06", "07", "08", "09", "49", "70", "71", "72", "73", "74", "75", "98", "99"}
_ZERA_IPI = {"51", "52", "53", "54", "55"}


def valor_campo(d, it, campo):
    if campo.startswith("base_"):                      # código da base que o motor usa para este imposto
        t_ = "ICMS" if campo == "base_icms" else campo[5:].upper()
        tr_ = tratamentos(d, it).get(t_)
        return tr_[1][0] if tr_ else ""
    return {"uf": d["uf_dest"], "tipo": d["tipo"], "dest": d.get("dest", ""), "cfop": it["cfop"],
            "cfop_base": cfop_base(it["cfop"]),
            "cst": it["cst"], "cst_ipi": it["cst_ipi"], "cst_pis": it["cst_pis"], "cst_cof": it["cst_cof"],
            "cst_ibs": it.get("cst_ibs", ""), "cclass": it.get("cclass", ""),
            "orig": it["orig"], "ncm": it["ncm"], "cprod": it["cprod"], "cbenef": it.get("cbenef", ""),
            "indfinal": d["indfinal"],
            "grupo_cliente": (grupo_cliente(d) or {}).get("nome", ""),
            "grupo_produto": (grupo_produto(it) or {}).get("nome", ""),
            "abrangencia": ("INTERNA" if d["uf_dest"] == d["uf_emit"] else "EXTERIOR" if d["uf_dest"] == "EX"
                            else "INTERESTADUAL"),
            "grupo": operacao(it["cfop"], d)[1], "finalidade": operacao(it["cfop"], d)[2]}.get(campo, it.get(campo, ""))


def _corrigir_doc(d, corr, stats):
    """Cópia da nota com os itens corrigidos (a nota original não é alterada)."""
    novos, mudou = [], False
    for n, it in enumerate(d["itens"], 1):
        for c in corr:
            if c.get("itens"):
                bate = [d["chave"], n] in c["itens"] or (d["chave"], n) in c["itens"]
            else:
                bate = bool(c.get("filtro")) and all(str(valor_campo(d, it, k)) == str(v) for k, v in c["filtro"].items())
            if not bate:
                continue
            it = dict(it)
            for k, v in c.get("alteracoes", {}).items():
                if k.startswith("base_"):
                    t_ = "ICMS" if k == "base_icms" else k[5:].upper()
                    bs = dict(it.get("_bases", {}))
                    for x in (FAMILIA_IBS if t_ in FAMILIA_IBS else (t_,)):   # IBS e CBS têm a mesma base
                        bs[x] = v
                    it["_bases"] = bs
                elif k.startswith("aliq_"):
                    t_ = k[5:].upper()
                    for x in (t_,):
                        if x in CAMPO_ALIQ:
                            pa, va = CAMPO_ALIQ[x]
                            try:
                                novo = float(str(v).replace("%", "").replace(",", "."))
                            except ValueError:
                                continue
                            it[pa] = novo
                            if novo == 0:
                                it[va] = 0.0
                elif k in it:
                    it[k] = "" if v == "-" else v          # "-" = remover o valor (ex.: cBenef indevido)
            if "cst" in c.get("alteracoes", {}) and it["cst"] in _ZERA_ICMS:
                it.update(vicms=0.0, vbc=0.0, picms=0.0)
            for cc, vb, pp, vv in (("cst_pis", "vbcpis", "ppis", "vpis"), ("cst_cof", "vbccof", "pcof", "vcof")):
                if cc in c.get("alteracoes", {}) and it[cc] in _ZERA_PC:
                    it.update({vb: 0.0, pp: 0.0, vv: 0.0})
            if "cst_ipi" in c.get("alteracoes", {}) and it["cst_ipi"] in _ZERA_IPI:
                it.update(vbcipi=0.0, pipi=0.0, vipi=0.0)
            it["_corrigido"] = it.get("_corrigido", []) + [c["id"]]
            stats[c["id"]] = stats.get(c["id"], 0) + 1
            mudou = True
        novos.append(it)
    return dict(d, itens=novos) if mudou else d


def tratamento_item(an, t, d, it, tr):
    """Mesma chave de tratamento usada nas células (para comparar item × regra)."""
    if t not in tr:
        return None
    esc, base, al, cb = tr[t]
    modo = an["modo_aliq"].get((t, esc, base), ("F", al))
    if modo[0] == "ITEM":
        modo = ("F", al)
    grupo = operacao(it["cfop"], d)[1] if OPCOES.get("SEPARAR_GRUPOS", True) else ""
    return (esc, base, modo[0], modo[1], cb, grupo)


def itens_por_tratamento(an, t, caixa):
    """Itens das células dentro da caixa (regra ou conflito), agrupados pelo tratamento que o XML trouxe."""
    grupos = defaultdict(list)
    for d, it, tr in an["linhas"]:
        c = celula(t, d, it, an["modas"], an["separar"] and TRIBUTOS[t][5] == "ORIG")
        if all(c[i] in caixa[i] for i in range(4)):
            n = next((k for k, x in enumerate(d["itens"], 1) if x is it), 0)
            grupos[tratamento_item(an, t, d, it, tr)].append((d, it, n, tr))
    return grupos


def analisar(docs, canc, cnpj, agressivo=True, avisar=print, separar_participante=False, aliq_ncm=None):
    """Núcleo: devolve um dicionário com regras e cadastros sugeridos (sem depender de tela)."""
    validos = [d for d in docs.values() if _valida(d, canc) and d["emit"] == cnpj]
    indexar_grupos(cnpj)
    corr_stats = {}
    corr = [c for c in CORRECOES if c.get("cnpj", "") in ("", cnpj)]
    if corr:
        validos = [_corrigir_doc(d, corr, corr_stats) for d in validos]
    if not validos:
        raise ValueError("Nenhuma NF-e de saída válida para esse emitente.")
    uf_emit = Counter(d["uf_emit"] for d in validos).most_common(1)[0][0]

    # 1) classe de cada produto, medida nas VENDAS (outras operações ficam com o perfil de operação)
    cont = {f: defaultdict(Counter) for f in ("ORIG", "IPI", "PC", "IBS")}
    cont_v = {f: defaultdict(Counter) for f in ("ORIG", "IPI", "PC", "IBS")}
    prod_info, grupo_cfops, grupo_fins = {}, defaultdict(set), defaultdict(set)
    base_cfops, cfop_inv = defaultdict(set), defaultdict(lambda: [0, ""])
    for d in validos:
        for it in d["itens"]:
            _, grupo, fin_ = operacao(it["cfop"], d)
            grupo_cfops[grupo].add(it["cfop"])
            base_cfops[cfop_base(it["cfop"])].add(it["cfop"])
            if it["cfop"] in CFOP_INVALIDOS:
                cfop_inv[it["cfop"]][0] += 1
                cfop_inv[it["cfop"]][1] = cfop_inv[it["cfop"]][1] or d["chave"]
            grupo_fins[grupo].add(fin_)
            vals = {"ORIG": "COM ST" if it["cst"] in CST_ST or it["cst"] in ("60", "500") else "SEM ST",
                    "IPI": f"CST {it['cst_ipi']}" if it["tem_ipi"] else "SEM IPI",
                    "PC": f"CST {it['cst_pis']}",
                    "IBS": f"CLASS {it['cclass']}" if it["tem_ibs"] else "SEM IBS/CBS"}
            for f, v in vals.items():
                cont[f][it["cprod"]][v] += 1
                if grupo == "VENDAS":
                    cont_v[f][it["cprod"]][v] += 1
            prod_info.setdefault(it["cprod"], (it["xprod"], it["ncm"], it["orig"], it["cest"]))
    modas = {f: {p: (cont_v[f].get(p) or c).most_common(1)[0][0] for p, c in m.items()} for f, m in cont.items()}

    # 2) tratamento de cada item/tributo + regras de negócio do padrão (prevalecem sobre o XML)
    regras_cmp = []
    rn_emp = [(x.get("tributo", ""), x.get("quando", ""), x.get("entao", ""),
               (x.get("observacao", "") + " (só esta empresa)").strip()) for x in _emp().get("regras_negocio", [])]
    for i, (trib, cond, acao, obs) in enumerate(list(REGRAS_NEGOCIO) + rn_emp):
        k = _chave_trib(trib)
        try:
            regras_cmp.append((k, _compilar_condicoes(cond), acao.strip(), {"regra": (trib, cond, acao, obs),
                               "aplicou": 0, "divergiu": 0, "exemplo": "", "erro": "" if k else "tributo desconhecido"}))
        except ValueError as e:
            regras_cmp.append((None, [], acao, {"regra": (trib, cond, acao, obs), "aplicou": 0, "divergiu": 0,
                                                "exemplo": "", "erro": str(e)}))
    # grupos derivados com tributo ausente: viram regras de negócio "ausente" (com o alcance escolhido)
    for gr in _IDX_GRUPOS["id"].values():
        campo = "GRUPOCLIENTE" if gr.get("tipo") == "participante" else "GRUPOPRODUTO"
        for t_, cfg in (gr.get("tributos") or {}).items():
            if cfg.get("acao") != "ausente" or t_ not in TRIBUTOS:
                continue
            conds = [(campo, "=", [_norm(gr["nome"])])]
            txt = [f"grupo {gr['nome']}"]
            for k_, v_ in (cfg.get("alcance") or {}).items():
                if v_:
                    conds.append((_norm(k_), "=", [_norm(x) for x in str(v_).split(",") if x.strip()]))
                    txt.append(f"{k_}={v_}")
            regras_cmp.append((t_, conds, "ausente", {"regra": (TRIBUTOS[t_][1], " e ".join(txt), "ausente",
                               f"Grupo derivado {gr['nome']}: {TRIBUTOS[t_][1]} não existe para o grupo"),
                               "aplicou": 0, "divergiu": 0, "exemplo": "", "erro": ""}))
    forcar_ncm = set()
    linhas = []
    chk = {"regra": ("ICMS", f"UF emitente em {'/'.join(sorted(UFS_CBENEF))} e CST {'/'.join(sorted(CST_EXIGE_CBENEF))}",
                     "cBenef obrigatório", "Checagem automática: itens sem cBenef no XML (cada regra de ICMS aceita "
                     "um único cBenef)"), "aplicou": 0, "divergiu": 0, "exemplo": "", "erro": ""}
    for d in validos:
        for it in d["itens"]:
            tr = tratamentos(d, it)
            for t_, cod_ in it.get("_bases", {}).items():  # correção de base informada pelo usuário
                if t_ in tr:
                    e_, b_, a_, c_ = tr[t_]
                    tr[t_] = (e_, _base_catalogo(cod_), a_, c_)
            ctx = None
            for k, conds, acao, st in regras_cmp:
                if not k:
                    continue
                al = acao.lower()
                if al != "ausente" and k not in tr:
                    continue
                if ctx is None:
                    ctx = contexto(d, it)
                if not _bate(conds, ctx):
                    continue
                if al == "ausente":
                    st["aplicou"] += 1
                    if k in tr:
                        st["divergiu"] += 1
                        st["exemplo"] = st["exemplo"] or d["chave"]
                        del tr[k]
                elif al.startswith("base="):
                    cod = acao.split("=", 1)[1].strip().upper()
                    esc, base, aliq, cb = tr[k]
                    if base[0] in ("BASZER", "BCZR00") or not _mesma_familia_base(base[0], cod):
                        continue      # sem base no item, ou base de outra natureza (ex.: com redução): não se aplica
                    st["aplicou"] += 1
                    if base[0] != cod:
                        st["divergiu"] += 1
                        st["exemplo"] = st["exemplo"] or d["chave"]
                        tr[k] = (esc, _base_catalogo(cod), aliq, cb)
                elif al.startswith("aliquota=") and al.endswith("ncm"):
                    st["aplicou"] += 1
                    forcar_ncm.add((k, tr[k][0], tr[k][1]))
            if "ICMS" in tr and d["uf_emit"] in UFS_CBENEF and it["cst"] in CST_EXIGE_CBENEF:
                chk["aplicou"] += 1
                if not tr["ICMS"][3]:
                    chk["divergiu"] += 1
                    chk["exemplo"] = chk["exemplo"] or d["chave"]
            linhas.append((d, it, tr))

    # 3) alíquota fixa ou pela NCM: por (tributo, escrituração, base)
    grupo_aliq = defaultdict(Counter)
    for d, it, tr in linhas:
        for t, (esc, base, al, cb) in tr.items():
            grupo_aliq[(t, esc, base)][al] += 1
    # Tributo com "regra de NCM": alíquota que varia vai para a tabela por NCM/UF/origem (menos regras).
    # Tributo sem regra de NCM: alíquota fixa na regra; alíquotas diferentes viram regras diferentes.
    usa_ncm = set(OPCOES["ALIQ_NCM"] if aliq_ncm is None else aliq_ncm)
    modo_aliq = {}
    for k, c in grupo_aliq.items():
        if len(c) == 1 and k not in forcar_ncm:
            modo_aliq[k] = ("F", next(iter(c)))
        elif k[0] in usa_ncm or k in forcar_ncm:
            modo_aliq[k] = ("NCM", None)
        else:
            modo_aliq[k] = ("ITEM", None)            # fixa, resolvida item a item

    # 4) células por tributo (só nas dimensões permitidas pelo modelo de decisão)
    cel = {t: defaultdict(Counter) for t in ORDEM_TRIB}
    exemplo, prod_keys = {}, {t: defaultdict(set) for t in ORDEM_TRIB}
    tabela_ncm = {t: defaultdict(Counter) for t in ORDEM_TRIB}
    for d, it, tr in linhas:
        for t in ORDEM_TRIB:
            c = celula(t, d, it, modas, separar_participante and TRIBUTOS[t][5] == "ORIG")
            prod_keys[t][c[0]].add(it["cprod"])
            if t in tr:
                esc, base, al, cb = tr[t]
                modo = modo_aliq[(t, esc, base)]
                if modo[0] == "ITEM":
                    modo = ("F", al)
                grupo = operacao(it["cfop"], d)[1] if OPCOES.get("SEPARAR_GRUPOS", True) else ""
                trat = (esc, base, modo[0], modo[1], cb, grupo)
                if modo[0] == "NCM":
                    tabela_ncm[t][(it["ncm"], it["orig"], uf_emit, d["uf_dest"], it["cest"])][al] += 1
            else:
                trat = None
            cel[t][c][trat] += 1
            exemplo.setdefault((t, c, trat), d["chave"])

    # 5) por tributo: dimensões que importam, tratamento majoritário e agrupamento em regras
    regras_trib, conflitos, dims, univ = {}, [], {}, {}
    meta, criterios = {}, {}
    for t in ORDEM_TRIB:
        if not any(trat for c in cel[t].values() for trat in c):
            continue
        avisar(f"Agrupando regras de {TRIBUTOS[t][1]}…")
        u = [frozenset(c[i] for c in cel[t]) for i in range(4)]
        univ[t] = u
        por_uf = DIMENSOES.get(t, DIM_PADRAO)["uf"] == "cada"
        obrig = tuple(sorted(({1} if separar_participante and TRIBUTOS[t][5] == "ORIG" else set())
                             | ({3} if por_uf else set())
                             | {DIM_SEGREGACAO[x][1] for x in segregacoes_de(t)}
                             | dims_excecao(t)))
        fixos = {3} if por_uf else set()
        S, iniciais = _dependencia(cel[t], u, obrig)
        dims[t] = S
        for trat, b, cnt in iniciais:
            if len(cnt) > 1:
                conflitos.append((t, b, cnt))
        cx = _mesclar([(x[0], x[1]) for x in iniciais], agressivo, fixos)
        cx = _expandir(cx, [set(x) for x in u], uf_emit, fixos)
        if agressivo:
            cx = _mesclar(cx, True, fixos)
        # esqueleto: separa o que não pode ser juntado sem perguntar e os grupos derivados
        crit = criterios_separados(t)
        cx = [c for c in cx if c[0] is not None]
        cx, meta[t] = _separar_caixas(cx, crit, uf_emit)
        if not OPCOES.get("ESQUELETO_COMPLETO", True):
            # só as regras com itens nos XMLs (combinações nunca vistas ficam sem regra)
            manter = [k for k, (trat_, b_) in enumerate(cx)
                      if any(trat_ in cnt_ and all(c_[i] in b_[i] for i in range(4)) for c_, cnt_ in cel[t].items())]
            cx, meta[t] = [cx[k] for k in manter], [meta[t][k] for k in manter]
        criterios[t] = sorted(crit)
        regras_trib[t] = (cx, cel[t])

    return {"cnpj": cnpj, "nome": validos[0]["emit_nome"], "uf_emit": uf_emit, "notas": len(validos),
            "itens": len(linhas), "linhas": linhas, "regras_trib": regras_trib, "conflitos": conflitos, "dims": dims,
            "univ": univ, "grupo_cfops": grupo_cfops, "base_cfops": base_cfops,
            "cfop_invalidos": [{"cfop": c, "motivo": CFOP_INVALIDOS[c], "itens": v[0], "exemplo": v[1]}
                               for c, v in cfop_inv.items()], "grupo_fins": grupo_fins, "prod_keys": prod_keys, "separar": separar_participante,
            "tabela_ncm": tabela_ncm, "modo_aliq": modo_aliq, "prod_info": prod_info, "modas": modas,
            "exemplo": exemplo, "regras_negocio": [x[3] for x in regras_cmp] + [chk], "validos": validos,
            "aliq_ncm": sorted(usa_ncm), "correcoes_stats": corr_stats, "meta_caixas": meta,
            "criterios_separados": criterios}


# ═════════════════════════════════════════════════════════════════════════════
# CADASTROS: perfis, bases, alíquotas, escrituração e as regras F2B
# ═════════════════════════════════════════════════════════════════════════════
def _uf_set_txt(s):
    return "/".join(sorted(s))


def _aliq_codigo(t, al):
    v = al[0] if al else 0.0
    if not v:
        return ALIQ_ZERO
    p = TRIBUTOS[t][2][:3]
    if abs(v * 10 - round(v * 10)) < 1e-6 and v < 100:
        return (f"{p}{int(round(v * 10)):03d}", f"{TRIBUTOS[t][1]} | ALÍQUOTA {_fmt(v)}%")
    return (f"{p[:2]}{int(round(v * 100)):04d}", f"{TRIBUTOS[t][1]} | ALÍQUOTA {_fmt(v)}%")


class _Codigos:
    """Atribui códigos a conjuntos (perfis) e conteúdos (bases, escriturações) sem repetir."""
    def __init__(self):
        self.mapa, self.usados = {}, set()

    def pegar(self, chave, sugerido, gerar):
        if chave in self.mapa:
            return self.mapa[chave]
        cod = sugerido
        n = 1
        while cod in self.usados:
            cod = gerar(n)
            n += 1
        self.usados.add(cod)
        self.mapa[chave] = cod
        return cod


def _cfops_reais(an, elementos):
    """CFOPs reais de um conjunto da dimensão de operação (CFOP, CFOP equivalente 'x949' ou grupo)."""
    reais = set()
    for x in elementos:
        el = x.split("|")[0]
        if el.startswith("x") and el[1:].isdigit():
            reais |= an["base_cfops"].get(el, {el})
        elif el.isdigit():
            reais.add(el)
        else:
            reais |= an["grupo_cfops"].get(el, set())
    return reais


BASE_DIFAL_GF = {"DIFD01": "BC DUPLA", "DIFS01": "BC SIMPLES"}


def _desc_difal_gf(bcod, part_txt, ufs):
    """DIFAL no padrão GF: DIFAL | BASE | PJ/PF | CONTRIBUINTE/NÃO CONTRIBUINTE | UF XX (até 100 caracteres)."""
    base = BASE_DIFAL_GF.get(bcod, "")
    pessoa = [x for x in part_txt if x in ("PJ", "PF")]
    contrib = ["NÃO CONTRIBUINTE" if x == "NÃO CONT." else "CONTRIBUINTE"
               for x in part_txt if x in ("CONT.", "NÃO CONT.", "ISENTO")]
    uf = [f"UF {next(iter(ufs))}"] if len(ufs) == 1 and "*" not in ufs else []
    return " | ".join(["DIFAL"] + ([base] if base else []) + pessoa + contrib + uf)[:100]


def _desc_icms_gf(nat, abr, fin, origem_txt, part_txt, ufs=(), cbenef=""):
    """ICMS no padrão GF de venda: ICMS | VENDA INTERNA | ORIGEM 2 | PJ | CONTRIB | NORMAL | CONSUMO [| UF XX] [| CBENEF x].
    Se passar de 100 caracteres, tira primeiro o regime (a UF e o cBenef não podem sair)."""
    op = "VENDA" if ("VENDA" in nat.upper() or "FATURAMENTO" in nat.upper()) else (nat.split(" / ")[-1] if nat else "")
    pessoa = [x for x in part_txt if x in ("PJ", "PF")]
    contrib = [{"CONT.": "CONTRIB", "NÃO CONT.": "NÃO CONTRIB", "ISENTO": "ISENTO"}[x]
               for x in part_txt if x in ("CONT.", "NÃO CONT.", "ISENTO")]
    regime = [x for x in part_txt if x in ("NORMAL", "SIMPLES")]
    uf = [f"UF {next(iter(ufs))}"] if len(ufs) == 1 and "*" not in ufs else []
    cb = [f"CBENEF {cbenef}"] if cbenef else []
    base = (["ICMS", " ".join(x for x in (op, abr) if x)] + ([origem_txt] if origem_txt else [])
            + pessoa + contrib)
    fim = ([fin] if fin else []) + uf + cb
    desc = " | ".join(base + regime + fim)
    if len(desc) > 100:
        desc = " | ".join(base + fim)
    return desc[:100]


def assinatura_regra(r):
    """Identidade da regra entre gerações (para manter o código): tributo + descrição + tratamento."""
    esc, base, modo, al, cb, grupo = r["_trat"]
    return "|".join(str(x) for x in (r["_t"], r["F2B_DESC"], esc[1], esc[2], esc[3], base[0], modo, al, cb, grupo))


def _vincular_pais(an, t, lista):
    """Regra filha (grupo derivado) -> regra pai: a regra do perfil pai que cobre a mesma operação/UF/produto."""
    for r in lista:
        b = r["_b"]
        ders_pa = {_id_derivado(x) for x in b[1]} - {""}
        ders_pr = {_id_derivado(x) for x in b[0]} - {""}
        if not ders_pa and not ders_pr:
            continue
        gid = next(iter(ders_pa or ders_pr))
        gr = grupo_por_id(gid) or {"nome": gid}
        r["GRUPO_DERIVADO"] = gr["nome"]
        dim = 1 if ders_pa else 0
        alvo = {_sem_derivado(x) for x in b[dim]}
        melhor, nota = None, -1
        for p in lista:
            if p is r or any(_id_derivado(x) == gid for x in p["_b"][dim]):
                continue
            pb = p["_b"]
            if not (alvo & set(pb[dim]) or (pb[dim] == an["univ"][t][dim] and alvo)):
                continue
            outro = 0 if dim == 1 else 1
            if not (pb[2] & b[2] and pb[3] & b[3]):
                continue
            outros_b = {_sem_derivado(x) for x in b[outro]}
            if not (outros_b & {_sem_derivado(x) for x in pb[outro]}):
                continue
            pts = len(pb[2] & b[2]) * 4 + len(pb[3] & b[3]) + (3 if p["_trat"] == r["_trat"] else 0) \
                + (5 if alvo <= set(pb[dim]) else 0) + (8 if pb[outro] == b[outro] else 0)
            if pts > nota:
                melhor, nota = p, pts
        r["PAI"] = melhor["F2B_REGRA"] if melhor else ""
        r["_mesmo_trat_pai"] = bool(melhor and melhor["_trat"] == r["_trat"])


def perguntas_agrupamento(an, regras):
    """Para cada tributo e critério ainda sem decisão: quais regras separadas teriam o mesmo tratamento e
    poderiam ser juntadas (são irmãs: vieram da mesma regra mínima e só diferem nesse critério)."""
    por_t = defaultdict(list)
    for r in regras:
        por_t[r["_t"]].append(r)
    saida = []
    for t, lista in por_t.items():
        meta = an.get("meta_caixas", {}).get(t) or []
        crit_t = an.get("criterios_separados", {}).get(t, [])
        pos = {"tipo": (1, 0), "regime": (1, 1), "origem": (0, 0), "finalidade": (2, None), "abrangencia": (3, None)}
        for c in crit_t:
            grupos = defaultdict(list)
            for r in lista:
                m = meta[r["_i"]] if r.get("_i") is not None and r["_i"] < len(meta) else None
                if not m:
                    continue
                ch = list(m["chaves"])
                d_, j_ = pos[c]
                if j_ is None:
                    ch[d_] = ""
                else:
                    k_ = list(ch[d_]) if isinstance(ch[d_], tuple) else [ch[d_]]
                    if j_ < len(k_):
                        k_[j_] = ""
                    ch[d_] = tuple(k_)
                grupos[(m["pai"], str(ch))].append(r)
            juntaveis = [g_ for g_ in grupos.values() if len(g_) > 1]
            if juntaveis:
                saida.append({"tributo": t, "criterio": c, "decisao": decisao_agrup(t, c),
                              "grupos": [[x["F2B_REGRA"] for x in g_] for g_ in juntaveis],
                              "regras_antes": sum(len(g_) for g_ in juntaveis), "regras_depois": len(juntaveis)})
    return saida


def montar_matriz(an, anteriores=None):
    """anteriores = {assinatura da regra: código} da geração anterior: a regra que continua igual mantém o
    código e as novas recebem o próximo código livre da sequência (ICM5xx)."""
    uf_emit = an["uf_emit"]
    ufs_todas = {d["uf_dest"] for d in an["validos"]}
    ufs_inter = ufs_todas - {uf_emit}
    perf_prod, perf_part, perf_od, perf_op = {}, {}, {}, {}
    cods = _Codigos()
    cods.usados |= set(CODIGOS_RESERVADOS)
    alertas_codigos = []
    bases, aliqs, escs, tipos_op = {}, {}, {}, {}
    regras = []
    ordem_orig = list(PERFIL_ORIGEM)

    def _orig_txt(gs):
        return "ORIGEM " + "/".join(PERFIL_ORIGEM[g][2][7:] for g in ordem_orig if g in gs)

    def _sufixo(gr):
        suf = re.sub(r"[^A-Z0-9]", "", _norm(gr.get("sufixo") or gr.get("nome", "")))[:2]
        return (suf or "DV").ljust(2, "X")

    def _nome_prod(fam, s):
        """-> (código sugerido, descrição, texto curto, código fixo do padrão?) de um conjunto sem derivados."""
        classes = sorted({x.split("§")[0] for x in s})
        origens = {x.split("§")[1] for x in s}
        nomef = {"ORIG": "ICMS", "IPI": "IPI", "PC": "PIS/COF", "IBS": "IBS/CBS"}[fam]
        so_origem = classes == ["*"]
        so_classe = origens == {"*"}
        if so_origem and len(origens) == 1 and next(iter(origens)) in PERFIL_ORIGEM:
            cod0, desc, curto = PERFIL_ORIGEM[next(iter(origens))]
            return cod0, desc, curto, True
        if so_origem:
            curto = _orig_txt(origens)
            return "ICMX01", f"{nomef} | {curto}", curto, False
        if so_classe:
            curto = f"{nomef} " + " + ".join(classes)
            desc = f"{nomef} | " + " + ".join(classes) + " NAS VENDAS"
            csts = [c.split()[-1] for c in classes]
            if len(classes) == 1 and fam in ("IPI", "PC") and csts[0].isdigit():
                sug = ("IPIS" if fam == "IPI" else "PCST") + csts[0][-2:]
            else:
                sug = {"ORIG": "ICMS01", "IPI": "IPIX01", "PC": "PCSX01", "IBS": "IBPR01"}[fam]
            return sug, desc, curto, False
        combos = sorted(s)
        if len(origens) == 1 or len(classes) == 1:
            curto = f"{nomef} {' + '.join(classes)} | {_orig_txt(origens)}"
        else:
            curto = f"{nomef} " + " + ".join(f"{x.split('§')[0]} {_orig_txt({x.split('§')[1]})}" for x in combos)
        return {"ORIG": "ICMX01", "IPI": "IPIX01", "PC": "PCSX01", "IBS": "IBPR01"}[fam], curto, curto, False

    def _excluidos(t, dim, s):
        """Grupos derivados que saíram deste perfil (para a descrição: 'EXC. TRANSPORTADORA')."""
        bases = {_sem_derivado(x) for x in s}
        nomes = set()
        for y in an["univ"][t][dim]:
            gid = _id_derivado(y)
            if gid and _sem_derivado(y) in bases and not _id_derivado(_sem_derivado(y)):
                nomes.add((grupo_por_id(gid) or {"nome": gid})["nome"])
        return sorted(nomes)

    def perfil_produto(t, s):
        fam = TRIBUTOS[t][5]
        if s == an["univ"][t][0] or all(x == "*§*" for x in s):
            cod, desc = PERFIL_PRODUTO_GERAL
            perf_prod.setdefault(cod, {"Código": cod, "Descrição": desc, "Família": "GERAL", "Classes": "todos",
                                       "_s": None, "_t": t, "Produtos": len(an["prod_info"])})
            return cod, desc, "GERAL"
        prods = set()
        for k in s:
            prods |= an["prod_keys"][t].get(k, set())
        excs = [x for x in s if x.startswith("EXC:")]
        if excs and len(excs) == len(s):
            info = [next((e for e in todas_excecoes() if e["id"] == x[4:]), {}) for x in excs]
            txt = "; ".join(f"{CAMPOS_EXCECAO.get(e.get('campo'), ('', 0))[0]} {', '.join(e.get('valores', [])[:3])}"
                            for e in info)
            cod = cods.pegar(("PR", "EXC", s), "PEXC01", lambda n: f"PEXC{n + 1:02d}")
            perf_prod[cod] = {"Código": cod, "Descrição": f"PRODUTO | EXCEÇÃO | {txt}"[:120], "Família": "EXCEÇÃO",
                              "Classes": txt, "_s": s, "_t": t, "Produtos": len(prods)}
            return cod, perf_prod[cod]["Descrição"], f"EXCEÇÃO {txt}"
        s = frozenset(x for x in s if not x.startswith("EXC:")) or s
        nomef = {"ORIG": "ICMS", "IPI": "IPI", "PC": "PIS/COF", "IBS": "IBS/CBS"}[fam]
        ders = {_id_derivado(x) for x in s}
        classes_txt = " + ".join(sorted(_sem_derivado(x).replace("§", " | ").replace("*", "todas") for x in s))
        if len(ders) == 1 and "" not in ders:
            gid = next(iter(ders))
            gr = grupo_por_id(gid) or {"nome": gid, "valores": []}
            base_s = frozenset(_sem_derivado(x) for x in s)
            if all(x == "*§*" for x in base_s):
                pcod, pdesc, pcurto = PERFIL_PRODUTO_GERAL[0], PERFIL_PRODUTO_GERAL[1], "PRODUTOS"
            else:
                pcod, pdesc, pcurto, _ = _nome_prod(fam, base_s)
            suf = _sufixo(gr)
            sug = (gr.get("codigo") if fam == "ORIG" else "") or f"{pcod[:4]}{suf}"
            cod = cods.pegar(("PR", fam, s), sug, lambda n: f"{sug[:4]}{suf[0]}{n}")
            curto = f"{pcurto} - {gr['nome']}"
            perf_prod[cod] = {"Código": cod, "Descrição": f"{pdesc} - {gr['nome']}"[:120], "Família": nomef,
                              "Classes": classes_txt, "_s": s, "_t": t, "Produtos": len(prods),
                              "Grupo derivado": gr["nome"], "Perfil pai": pcod,
                              "Critério sugerido": f"grupo de tributação {gr['nome']} ({len(gr.get('valores', []))} produto(s))"}
            return cod, perf_prod[cod]["Descrição"], curto
        s_base = frozenset(_sem_derivado(x) for x in s)
        sug, desc, curto, fixo = _nome_prod(fam, s_base)
        if len(ders) > 1:          # derivado misturado com o pai (critério juntado): descreve os grupos
            nomes = sorted((grupo_por_id(g_) or {"nome": g_})["nome"] for g_ in ders if g_)
            curto += " + " + "/".join(nomes)
            desc += " + " + "/".join(nomes)
            fixo = False
        exc = _excluidos(t, 0, s) if not any(ders) else []
        if exc:
            desc += " | EXC. " + "/".join(exc)
        if fixo:
            cod = sug
        else:
            cod = cods.pegar(("PR", fam, s), sug, lambda n: f"{sug[:4]}{n + 1:02d}")
        perf_prod[cod] = {"Código": cod, "Descrição": desc, "Família": nomef, "Classes": classes_txt,
                          "_s": s, "_t": t, "Produtos": len(prods)}
        return cod, desc, curto

    def perfil_participante(t, s):
        if s == {"*"} or s == an["univ"][t][1]:
            cod, desc = PERFIL_PARTICIPANTE_GERAL
            perf_part[cod] = {"Código": cod, "Descrição": desc, "Tipos": "todos",
                              "Critério sugerido": "todos os clientes", "_s": None}
            return cod, "GERAL"
        excs = [x for x in s if x.startswith("EXC:")]
        if excs and len(excs) == len(s):
            info = [next((e for e in todas_excecoes() if e["id"] == x[4:]), {}) for x in excs]
            docs_ = [v for e in info for v in e.get("valores", [])]
            cod = cods.pegar(("PA", "EXC", s), "CEXC01", lambda n: f"CEXC{n + 1:02d}")
            perf_part[cod] = {"Código": cod, "Descrição": f"CLIENTE | EXCEÇÃO | {', '.join(docs_[:3])}"[:120],
                              "Tipos": "exceção", "Critério sugerido": f"A1_CGC em ({', '.join(docs_)})", "_s": s}
            return cod, f"EXCEÇÃO {', '.join(docs_[:2])}"
        if excs:
            s = frozenset(x for x in s if not x.startswith("EXC:")) or s
            if s == {"*"}:
                cod, desc = PERFIL_PARTICIPANTE_GERAL
                perf_part[cod] = {"Código": cod, "Descrição": desc, "Tipos": "todos",
                                  "Critério sugerido": "todos os clientes", "_s": None}
                return cod, "GERAL"
        # todos os clientes menos um grupo derivado: perfil geral com exceção
        resto = {x for x in an["univ"][t][1] if x not in s}
        if resto and all(_id_derivado(x) for x in resto) and not any(_id_derivado(x) for x in s):
            nomes = sorted({(grupo_por_id(_id_derivado(x)) or {"nome": _id_derivado(x)})["nome"] for x in resto})
            cod = cods.pegar(("PA", s), "CGEX01", lambda n: f"CGEX{n + 1:02d}")
            perf_part[cod] = {"Código": cod, "Descrição": f"CLIENTE | GERAL | EXC. {'/'.join(nomes)}"[:120],
                              "Tipos": " + ".join(sorted(s)), "_s": frozenset(s),
                              "Critério sugerido": f"todos os clientes, exceto os grupos de tributação {', '.join(nomes)}"}
            return cod, f"GERAL EXC. {'/'.join(nomes)}"

        # regime irrelevante: se o conjunto cobre todas as variantes de regime de um tipo, usa o tipo geral
        def _tipo_sem_regime(x):
            if " »" in x:
                return x                      # grupo derivado nunca se confunde com o tipo pai
            return x.replace(" SUFRAMA", "").split(" · ")[0] + (" SUFRAMA" if x.endswith(" SUFRAMA") else "")
        variantes = defaultdict(set)
        for x in an["univ"][t][1]:
            variantes[_tipo_sem_regime(x)].add(x)
        s_orig, s_norm = s, set()
        for k in {_tipo_sem_regime(x) for x in s}:
            membros = {x for x in s if _tipo_sem_regime(x) == k}
            s_norm |= {k} if len(variantes[k]) > 1 and membros >= variantes[k] else membros
        s = frozenset(s_norm)
        partes, exc_tot = [], set()
        for x in sorted(s):
            der = _id_derivado(x)
            xb = _sem_derivado(x)
            suf = xb.endswith(" SUFRAMA")
            base = xb.replace(" SUFRAMA", "")
            reg = base.split(" · ")[1] if " · " in base else ""
            base = base.split(" · ")[0]
            cod0, curto, crit = PERFIL_PARTICIPANTE.get(base, ("CXXG01", base.upper(), ""))
            if reg:
                cod0 = cod0[:3] + ("S" if reg == "SIMPLES" else "N") + cod0[4:]
                curto += f" | {reg}"
                crit += f"; A1_SIMPNAC={'1' if reg == 'SIMPLES' else '2'}"
            if suf:
                cod0 = cod0[:3] + "Z" + cod0[4:]
                curto += " | SUFRAMA"
            if der:
                gr = grupo_por_id(der) or {"nome": der, "valores": []}
                cod0 = cod0[:4] + _sufixo(gr)
                curto += f" | {gr['nome']}"
                crit += f"; grupo de tributação {gr['nome']} ({len(gr.get('valores', []))} cliente(s) informados)"
            else:
                for y in an["univ"][t][1]:
                    if _id_derivado(y) and _sem_derivado(y) == xb:
                        exc_tot.add((grupo_por_id(_id_derivado(y)) or {"nome": _id_derivado(y)})["nome"])
            partes.append((cod0, curto, crit))
        if len(s) == 1:
            sug, curto = partes[0][0], partes[0][1]
        else:
            sug, curto = "CMIX01", " / ".join(p[1] for p in partes)
        ders = {_id_derivado(x) for x in s} - {""}
        gr1 = grupo_por_id(next(iter(ders))) if len(s) == 1 and ders else None
        if gr1 and gr1.get("codigo") and sum(1 for g_ in an["univ"][t][1] if _id_derivado(g_) == gr1["id"]) == 1:
            sug = gr1["codigo"]
        cod = cods.pegar(("PA", s), sug, lambda n: f"{sug[:4]}{n + 1:02d}" if not ders else f"{sug[:5]}{n}")
        desc = "CLIENTE | " + curto + (f" | EXC. {'/'.join(sorted(exc_tot))}" if exc_tot else "")
        perf_part[cod] = {"Código": cod, "Descrição": desc[:120], "Tipos": " + ".join(sorted(s)),
                          "Critério sugerido": " | ".join(sorted({p[2] for p in partes}))
                          + (f" | exceto os grupos de tributação {', '.join(sorted(exc_tot))}" if exc_tot else ""),
                          "_s": frozenset(s_orig) | frozenset(x for x in an["univ"][t][1] if _tipo_sem_regime(x) in s)}
        if gr1:
            perf_part[cod]["Grupo derivado"] = gr1["nome"]
        return cod, curto

    def perfil_od(t, s):
        if DIMENSOES.get(t, DIM_PADRAO)["uf"] == "cada" and len(s) == 1 and s != {uf_emit} and s != {"*"}:
            uf = next(iter(s))
            cod, desc = OD_POR_UF.get(uf, (f"OD{uf}01", f"SAÍDAS | {uf_emit} → {uf}"))
            perf_od[cod] = {"Código": cod, "Descrição": desc, "UF origem": uf_emit, "UFs destino": uf, "_s": s}
            return cod, "INTERESTADUAL"
        if s == {"*"}:
            cod, desc = OD_TODAS
            ufs = "todas"
        elif s == {uf_emit}:
            cod, desc = OD_INTERNA
            ufs = uf_emit
        elif uf_emit not in s and s >= ufs_inter:
            cod, desc = OD_INTERESTADUAL
            ufs = "todas exceto " + uf_emit
        elif s >= ufs_todas:
            cod, desc = OD_TODAS
            ufs = "todas"
        else:
            sug = f"OD{sorted(s)[0]}01" if len(s) == 1 else "ODX001"
            cod = cods.pegar(("OD", s), sug, lambda n: f"{sug[:4]}{n + 1:02d}")
            desc = f"SAÍDAS | {uf_emit} → {_uf_set_txt(s)}"
            ufs = _uf_set_txt(s)
        perf_od[cod] = {"Código": cod, "Descrição": desc, "UF origem": uf_emit, "UFs destino": ufs, "_s": s}
        abr = ("" if cod == OD_TODAS[0] else "INTERNA" if s == {uf_emit} else
               "INTERESTADUAL" if uf_emit not in s else "INTERNA/INTERESTADUAL")
        return cod, abr

    def perfil_operacao(t, s):
        cfops, nomes, fins, tps = set(), [], set(), []
        for x in sorted(s):
            el, fin = (x.split("|") + [""])[:2]
            if fin:
                fins.add(fin)
            if el.isdigit() or (el.startswith("x") and el[1:].isdigit()):
                reais = an["base_cfops"].get(el, {el}) if el.startswith("x") else {el}
                cfops |= reais
                el = sorted(reais)[0]
                nome = NATUREZA.get(el[1:], f"CFOP {el}")
                tipos_op.setdefault(_rotulo_tipo(fin), set()).update(reais)
            else:
                cfops |= an["grupo_cfops"].get(el, set())
                nome = el
                for f_ in ([fin] if fin else sorted(an["grupo_fins"].get(el, ()))):
                    tipos_op.setdefault(_rotulo_tipo(f_), set()).update(an["grupo_cfops"].get(el, set()))
                    tps.append(_rotulo_tipo(f_))
                nomes.append(nome)
                continue
            nomes.append(nome)
            tps.append(_rotulo_tipo(fin))
        nomes = sorted(set(nomes))
        if s == an["univ"][t][2] and len(nomes) > 1:
            nomes = ["TODAS AS OPERAÇÕES"]
        abr = sorted({{"5": "INTERNA", "6": "INTERESTADUAL", "7": "EXTERIOR"}.get(c[0], "") for c in cfops})
        fins_txt = "/".join(f for f in sorted(fins) if not any(f in n for n in nomes))
        desc = " | ".join(x for x in (" / ".join(nomes), "/".join(abr), fins_txt) if x)
        cod = cods.pegar(("OP", s), f"POS{INICIO_PERFIL_OPERACAO}", lambda n: f"POS{INICIO_PERFIL_OPERACAO + n}")
        perf_op[cod] = {"Código": cod, "Descrição": desc, "CFOPs": ", ".join(sorted(cfops)),
                        "Tipos de operação": " ; ".join(sorted(set(tps))), "_s": s}
        nat_txt = f"{' / '.join(nomes[:2])} +{len(nomes) - 2} OPERAÇÕES" if len(nomes) > 3 else " / ".join(nomes)
        return cod, nat_txt, "/".join(sorted(fins))

    for t in ORDEM_TRIB:
        if t not in an["regras_trib"]:
            continue
        trib, nome, pref, ini, dig, fam = TRIBUTOS[t]
        caixas, cel = an["regras_trib"][t]
        lista = []
        for i_cx, (trat, b) in enumerate(caixas):
            esc, base, modo, al, cbenef, grupo_reg = trat
            pr_cod, pr_desc, pr_curto = perfil_produto(t, b[0])
            pa_cod, pa_curto = perfil_participante(t, b[1])
            op_cod, nat, fin = perfil_operacao(t, b[2])
            od_cod, abr = perfil_od(t, b[3])
            # base
            b0 = base[0]
            bcod = cods.pegar(("BASE", base), b0, lambda n: f"{b0[:5]}{chr(64 + n)}" if len(b0) >= 6
                              else f"{b0}{chr(64 + n)}")
            # campos no layout do F27 da GF: % Redução (F27_REDBAS) e Valor Origem (F27_VALORI, 01 = normal)
            m_red = re.search(r"REDUÇÃO ([\d.,]+)%", base[1])
            bases.setdefault(bcod, {
                "Código": bcod, "Descrição": base[1], "Fórmula sugerida": base[2],
                "% Redução": m_red.group(1).replace(",", ".") if m_red else "0",
                "Valor origem": "01"})
            # alíquota
            acod, adesc = ALIQ_NCM if modo == "NCM" else _aliq_codigo(t, al)
            if modo != "NCM" and acod != ALIQ_ZERO[0]:
                a0 = acod
                acod = cods.pegar(("ALIQ", t, al), a0, lambda n: f"{a0[:5]}{chr(64 + n)}")
            extra = ""
            if modo != "NCM" and t == "ICMSST":
                extra = f" | MVA {_fmt(al[1])}%"
            aliqs.setdefault(acod, {"Código": acod, "Descrição": adesc + extra,
                                    "Tipo": "Busca da tabela por NCM/UF" if modo == "NCM" else "Fixa",
                                    "Valor": "" if modo == "NCM" else _fmt(al[0])})
            # escrituração
            cab, cst, inc, stot, perdif, cls = esc
            sug = {"ICMS": "ICMS", "ICMSST": "ICST", "DIFAL": "DIF0", "FECP": "FCP0", "FECPST": "FCS0",
                   "FECPDF": "FCD0", "IPI": "IPI0", "PIS": "PIS0", "COF": "COF0",
                   "IBSEST": "IBE", "IBSMUN": "IBM", "CBSFED": "CBS"}[t]
            sug = (sug + cst)[:6] if len(sug + cst) <= 6 else (sug[:3] + cst)[:6]
            ecod = cods.pegar(("ESC", t, esc), sug, lambda n: f"{sug[:5]}{chr(64 + n)}")
            escs[ecod] = {"Código": ecod, "Tributo": trib, "CJ2_CSTCAB": cab, "CJ2_CST": cst,
                          "CJ2_INCIDE": inc, "CJ2_STOTNF": stot, "CJ2_PERDIF": perdif,
                          "Incidência": INCIDE_TXT.get(inc, ""), "Ação na nota": STOTNF_TXT.get(stot, ""),
                          "CJ2_CSTCCT (cClassTrib)": cls if t in ("IBSEST", "IBSMUN", "CBSFED") else "",
                          "CJ2_CCT": cls[-3:] if cls and t in ("IBSEST", "IBSMUN", "CBSFED") else "",
                          "Observação": cls if t not in ("IBSEST", "IBSMUN", "CBSFED") else ""}
            # descrição da regra no padrão TRIBUTO | OPERAÇÃO + ABRANGÊNCIA | PRODUTO | PARTICIPANTE | FINALIDADE
            # padrão GF: TRIBUTO | OPERAÇÃO | ORIGEM n | PJ/PF | CONT./NÃO CONT. | SIMPLES/NORMAL | FINALIDADE
            origens_r = {x.split("§")[1] for x in b[0] if x.count("§") >= 1 and x.split("§")[1] not in ("*", "")}
            origem_txt = _orig_txt(origens_r) if origens_r else ""
            part_txt = _part_gf(b[1])
            partes = [nome, f"{nat} {abr}".strip(), origem_txt] + part_txt +                      ([fin] if fin and fin not in nat else []) +                      ([f"UF {_uf_set_txt(b[3])}"] if
                      DIMENSOES.get(t, DIM_PADRAO)["uf"] == "cada" and b[3] != {"*"} else []) +                      ([f"CBENEF {cbenef}"] if cbenef else [])
            # sem repetir o nome do tributo nem o mesmo trecho em sequência
            limpas = []
            for p in partes:
                p = (p or "").strip()
                if p and p.upper() != nome.upper() and (not limpas or p != limpas[-1]):
                    limpas.append(p)
            desc = " | ".join([nome] + limpas)
            if t == "ICMSST" and fin == "CONSUMO":          # ST de consumo final = DIFAL ST (mesmo F2B_TRIB ICMSST)
                desc = desc.replace("ICMS ST |", "DIFAL ST |", 1)
            desc_gerencial = desc
            if t == "DIFAL":
                desc = _desc_difal_gf(bcod, part_txt, b[3])
            elif t == "ICMS":
                desc = _desc_icms_gf(nat, abr, fin, origem_txt, part_txt, b[3], cbenef)
            lista.append({"_ord": (nat, abr, pr_curto, pa_curto, fin), "_t": t, "_b": b, "_trat": trat, "_i": i_cx,
                          "F2B_DESC": desc[:120], "DESC_GERENCIAL": desc_gerencial, "F2B_TRIB": trib, "F2B_RBASE": bcod, "F2B_RALIQ": acod,
                          "F2B_PEROD": od_cod, "F2B_PERFPA": pa_cod, "F2B_PERFOP": op_cod, "F2B_PERFPR": pr_cod,
                          "F2B_CODESC": ecod, "cBenef": cbenef, "Itens": 0, "Exemplo (chave)": "",
                          "CFOPs": ", ".join(sorted(_cfops_reais(an, b[2]))), "UFs": _uf_set_txt(b[3])})
        lista.sort(key=lambda r: r["_ord"])
        # códigos: a regra que já existia mantém o código; as novas pegam o próximo código livre (sequencial)
        usados_t = set(CODIGOS_RESERVADOS)
        if anteriores:
            # código que já foi usado por outra regra não é reaproveitado (pode já estar no Protheus)
            usados_ant = {c_ for c_ in anteriores.values() if c_.startswith(pref)}
            for r in lista:
                c_ = anteriores.get(assinatura_regra(r))
                if c_ and c_ not in usados_t and c_.startswith(pref):
                    r["F2B_REGRA"] = c_
                    usados_t.add(c_)
            usados_t |= usados_ant
        n = ini
        for r in lista:
            if r.get("F2B_REGRA"):
                continue
            while f"{pref}{n:0{dig}d}" in usados_t:
                n += 1
            r["F2B_REGRA"] = f"{pref}{n:0{dig}d}"
            usados_t.add(r["F2B_REGRA"])
            if n > FIM_FAIXA_SAIDA:
                alertas_codigos.append(f"{r['F2B_REGRA']}: passou do fim da faixa de saída ({pref}{FIM_FAIXA_SAIDA})")
            n += 1
        lista.sort(key=lambda r: r["F2B_REGRA"])
        _vincular_pais(an, t, lista)
        regras += lista

    # tabela de alíquotas por NCM/UF: a menor chave que determina a alíquota
    linhas_ncm = []
    nomes = ("ncm", "orig", "ufo", "ufd", "cest")
    chaves = [("ufd",), ("orig", "ufd"), ("ncm",), ("ncm", "ufd"), ("ncm", "orig", "ufd"), nomes]
    for t, tab in an["tabela_ncm"].items():
        if not tab:
            continue
        maj = {k: c.most_common(1)[0][0] for k, c in tab.items()}
        usar = nomes
        for ch in chaves:
            idx = [nomes.index(x) for x in ch]
            m = {}
            if all(m.setdefault(tuple(k[i] for i in idx), v) == v for k, v in maj.items()):
                usar = ch
                break
        idx = [nomes.index(x) for x in usar]
        agg = defaultdict(lambda: [None, 0])
        for k, c in tab.items():
            kk = tuple(k[i] if nomes[i] in usar else "*" for i in range(5))
            agg[kk][0] = maj[k] if agg[kk][0] is None else agg[kk][0]
            agg[kk][1] += sum(c.values())
        for kk, (v, q) in sorted(agg.items()):
            linhas_ncm.append({"Tributo": TRIBUTOS[t][0], "Chave usada": " + ".join(usar).replace("ufd", "UF destino")
                               .replace("ncm", "NCM").replace("orig", "origem").replace("ufo", "UF origem")
                               .replace("cest", "CEST"),
                               "NCM": kk[0], "Origem": kk[1], "UF origem": kk[2], "UF destino": kk[3], "CEST": kk[4],
                               "Alíquota %": _fmt(v[0]),
                               "MVA % / Alíq. interestadual %": _fmt(v[1]) if len(v) > 1 else "", "Itens": q})

    # validação: cada item/tributo deve acionar exatamente uma regra
    por_t = defaultdict(list)
    for r in regras:
        por_t[r["_t"]].append(r)
    val = Counter()
    cel_regra = defaultdict(dict)
    pendencias = []   # cenários do XML sem regra (ou com tratamento diferente): o usuário decide
    for t, (cx, cel) in an["regras_trib"].items():
        for c, cnt in cel.items():
            hits = [r for r in por_t[t] if c[0] in r["_b"][0] and c[1] in r["_b"][1]
                    and c[2] in r["_b"][2] and c[3] in r["_b"][3]]
            cel_regra[t][c] = hits[0]["F2B_REGRA"] if len(hits) == 1 else ("DUPLICADA" if hits else "")
            for trat, q in cnt.items():
                if trat is None:
                    val["sem_tributo_ok" if not hits else "aciona_indevido"] += q
                elif len(hits) == 1 and hits[0]["_trat"] == trat:
                    val["ok"] += q
                    hits[0]["Itens"] += q
                    if not hits[0]["Exemplo (chave)"]:
                        hits[0]["Exemplo (chave)"] = an["exemplo"].get((t, c, trat), "")
                elif len(hits) > 1:
                    val["duplicada"] += q
                elif not hits:
                    val["sem_regra"] += q
                    pendencias.append({"tributo": t, "coords": c, "trat": trat, "tipo": "sem_regra", "qtd": q,
                                       "regra": "", "exemplo": an["exemplo"].get((t, c, trat), "")})
                else:
                    val["tratamento_diferente"] += q
                    pendencias.append({"tributo": t, "coords": c, "trat": trat, "tipo": "tratamento_diferente",
                                       "qtd": q, "regra": hits[0]["F2B_REGRA"],
                                       "exemplo": an["exemplo"].get((t, c, trat), "")})
    return {"regras": regras, "perf_prod": perf_prod, "perf_part": perf_part, "perf_od": perf_od,
            "pendencias": pendencias,
            "perf_op": perf_op, "tipos_op": tipos_op, "bases": bases, "aliqs": aliqs, "escs": escs,
            "linhas_ncm": linhas_ncm, "validacao": val, "cel_regra": cel_regra, "alertas_codigos": alertas_codigos,
            "assinaturas": {assinatura_regra(r): r["F2B_REGRA"] for r in regras},
            "agrupamentos": perguntas_agrupamento(an, regras)}



# ═════════════════════════════════════════════════════════════════════════════
# PADRÕES EM MARKDOWN (padroes_configurador.md)
# ═════════════════════════════════════════════════════════════════════════════
ARQ_PADROES = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0] if sys.argv[0] else __file__)),
                           "padroes_configurador.md")
FAMILIA = {"ICMS": "ORIG", "ICMSST": "ORIG", "DIFAL": "ORIG", "FECP": "ORIG", "FECPST": "ORIG", "FECPDF": "ORIG",
           "IPI": "IPI", "PIS": "PC", "COF": "PC", "IBSEST": "IBS", "IBSMUN": "IBS", "CBSFED": "IBS"}
OPCOES = {"AGRUPAR_MAXIMO": True, "SEPARAR_PARTICIPANTE": False, "SEPARAR_GRUPOS": True, "ESQUELETO_COMPLETO": True,
          "ALIQ_NCM": ["ICMS", "ICMSST", "DIFAL", "FECP", "FECPST", "FECPDF", "IPI", "PIS", "COF",
                       "IBSEST", "IBSMUN", "CBSFED"]}
_SIM = {"sim", "s", "yes", "true", "1", "x"}


def _md(v):
    return str(v).replace("|", "\\|")


_CONHECIMENTO_EXTRA = '- **Padrão da descrição da regra** (como no ambiente do escritório):\n  `ICMS | VENDA INTERNA ST | ORIGEM 2 - TRADE | PJ | CONTRIB | NORMAL | REVENDA`;\n  grupo derivado entra depois do regime: `ICMS | VENDA INTERNA | ORIGEM 1 | PJ | CONTRIB | NORMAL | TRANSP. | CONSUMO`.\n- **Códigos de perfil de participante**: C + J/F (pessoa) + C/N (contribuinte) + S/N (Simples/Normal) + 01\n  (CJCN01 PJ contrib. normal, CJCS01 PJ contrib. Simples, CJNN01 PJ não contrib. normal, CJNS01 PJ não contrib.\n  Simples, CFNN01 PF não contrib., CFCS01 PF contrib.). Grupo derivado troca o final pelo sufixo do grupo:\n  CJCNTR / CJCSTR (transportadora), CJCNIN / CJCNI1 (indústria). Perfis especiais: CJSZFM (Zona Franca),\n  CJSALC (Área de Livre Comércio), CLIORP (órgão público), CGERAL (todos).\n- **Perfil pai com exceção**: quando um grupo derivado sai do perfil, a descrição do pai ganha "EXC.":\n  `CLIENTE | PJ | CONTRIB. | NORMAL | EXC. INDÚSTRIA E TRANSP. SC/MG/RS/MS`. O critério do pai precisa excluir\n  o grupo de tributação do filho, senão os perfis se sobrepõem.\n- **Grupos derivados (informados na mão)**: o XML nem sempre mostra a diferença. Ex.: PJ contribuinte do regime\n  normal que é TRANSPORTADORA com benefício não tem ICMS ST — o ICMS é igual, mas o ST não existe para ele.\n  O cliente informa os CNPJs, eles ganham grupo de tributação próprio e, como os perfis não podem se sobrepor,\n  TODA regra de ICMS do perfil pai é duplicada para o grupo (regra filha), mesmo com o mesmo cálculo; no ST\n  o grupo fica sem regra. O mesmo vale para produtos e para qualquer tributo (ICMS, ST, DIFAL, IPI, PIS/COFINS).\n  Pergunte sempre o alcance: só operação interna? interestadual? vendas, bonificação, transferência?\n- **Origem 2 (estrangeira adquirida no mercado interno)**: o mesmo NCM/CEST pode ter dois tratamentos.\n  Comprado de TRADE (importação por conta e ordem/encomenda): a empresa é equiparada a industrial, credita e\n  destaca IPI na saída. Comprado de fornecedor nacional comum: sem IPI na saída. Separe em dois grupos de\n  tributação: `ICMS IMPORTADO | ORIGEM 2 - TRADE` (ICMI02) e `ICMS IMPORTADO | ORIGEM 2 - MERC. NAC.` (ICMI05).\n  A lista de produtos vem do cliente — não dá para descobrir só pelo XML de saída.\n- **Perfis próprios do ICMS ST**: o ST pode agrupar participantes de outro jeito que o ICMS (ex.: CJCNT0\n  "ICMSST | PJ | CONTRIB | NORMAL | REVENDEDOR", CJCNT1 "ICMSST | PJ | CONTRIB | SIMPLES", CJCNT2\n  "DISTRIBUIDORAS"); ST por produto costuma usar perfil por NCM (ex.: ICSA01 "ICMS ST | NCM 4011/4012/4013").\n- **DIFAL ST / consumidor final contribuinte**: perfis como CJCF01/CJCF02 "DIFAL ST | PJ | CONTRIB | ... | CONS.\n  FINAL | EXC. INDÚSTRIA E TRANSP." com uma regra por UF de destino.\n- **ZFM / ALC**: vendas para Zona Franca e Área de Livre Comércio têm regras próprias (CJSZFM, CJSALC), com\n  base deduzindo PIS/COFINS e CST 40 na origem nacional; importados seguem tributados.\n- **Códigos estáveis**: a regra que continua igual mantém o código entre gerações; regra nova recebe o próximo\n  código livre (código já usado não é reaproveitado). Pai/filha é só informação gerencial (CSV gerencial).'
_SECOES_EXTRA = '## Grupos derivados\n\nInformativo (o motor usa grupos_derivados.json, que tem os CNPJs/produtos de cada empresa). Grupos que já\napareceram em projetos e o que costuma mudar — use como checklist ao implantar uma empresa nova:\n\n| Grupo | Tipo | Deriva de | Sufixo/código | O que muda |\n|---|---|---|---|---|\n| TRANSPORTADORA | Clientes | PJ \\| CONTRIB \\| NORMAL ou SIMPLES | TR (CJCNTR, CJCSTR) | Sem ICMS ST (benefício); ICMS igual ao pai, em regra filha; ver UFs (SC/MG/RS/MS/ES) |\n| INDÚSTRIA | Clientes | PJ \\| CONTRIB \\| NORMAL ou SIMPLES | IN (CJCNIN, CJCNI1) | Compra para insumo (tipo de operação V5): sem ST na venda; ICMS em regra filha |\n| DISTRIBUIDORA / REVENDEDOR | Clientes | PJ \\| CONTRIB | perfis do ST (CJCNT0/T1/T2) | Só o ICMS ST muda (MVA/regime do destinatário) |\n| ÓRGÃO PÚBLICO | Clientes | PJ \\| NÃO CONTRIB | CLIORP | Isenções/retenções específicas |\n| TRADE | Produtos | ORIGEM 2 | ICMI02 | IPI destacado na saída (equiparado a industrial) |\n| MERC. NAC. | Produtos | ORIGEM 2 | ICMI05 | Sem IPI na saída; ICMS igual ao pai, em regra filha |\n\n## Assistente IA\n\nOrientação para o assistente (DeepSeek) que lê este arquivo:\n- Responda como consultor do Configurador de Tributos (FISA170). Não invente códigos: use os da análise.\n- Toda sugestão deve dizer o impacto nos outros tributos e em quais perfis o grupo de tributação entra/sai.\n- Para cenário que o XML não explica, sugira Correções (emissão errada), Grupos derivados (lista do cliente),\n  Agrupamentos (juntar/separar) ou uma linha em Regras de negócio, nesta ordem de preferência.\n- Antes de recomendar, pergunte o alcance quando fizer diferença (interna × interestadual, operação, finalidade).'


def md_padrao():
    """Texto do .md com os padrões atuais (usado para criar o arquivo na primeira vez)."""
    sim = lambda b: "sim" if b else "não"
    L = ["# Padrões do Gerador de Cenários — Configurador de Tributos", "",
         "Este arquivo é a base de conhecimento do programa. Edite as tabelas e clique em **Recarregar padrões**.",
         "Não renomeie os títulos `##` nem a primeira coluna das tabelas. Para usar `|` dentro de uma célula, "
         "escreva `\\|`.", "",
         "## Instruções", "",
         "### Objetivo",
         "Gerar um CENÁRIO BASE (regras e cadastros: perfis, bases, alíquotas, escriturações) que atenda a TODOS",
         "os cenários dos XMLs, sem duplicidade: cada item × tributo aciona exatamente uma regra. Na família do ICMS",
         "o esqueleto fica separado (operação | origem | participante | regime | finalidade) e o programa PERGUNTA",
         "em Agrupamentos antes de juntar; nos demais tributos vale o mínimo de regras.",
         "Cada tributo tem suas próprias regras e escriturações; nunca se misturam tributos.", "",
         "### Como o programa decide",
         "1. Cada CFOP pertence a um grupo de operação (VENDAS, TRANSFERÊNCIAS, REMESSAS...) com uma finalidade.",
         "   Só nas VENDAS e BONIFICAÇÕES a finalidade vem da nota (indFinal: CONSUMO ou REVENDA).",
         "2. Para cada tributo, a tabela **Dimensões por tributo** diz por quais critérios ele PODE separar regras.",
         "   Dimensão proibida vira perfil geral (PROD01, CGERAL, 000002). Entre as permitidas, o programa usa",
         "   só as que o XML realmente exige.",
         "3. Alíquota que varia por NCM/origem/UF vai para o índice de cálculo (tabela por NCM); alíquota constante",
         "   vira alíquota fixa. Isso evita uma regra por alíquota.",
         "4. As **Regras de negócio** prevalecem sobre o XML. Quando o XML diverge, a divergência é mostrada.",
         "5. Cenários em que o XML se contradiz e o padrão não explica aparecem em Conflitos: são o sinal de que",
         "   falta uma dimensão ou uma regra de negócio.", "",
         "### Conhecimento por tributo",
         "- **ICMS**: estadual e cheio de particularidades. Pode variar por UF, finalidade, participante, origem",
         "  e CFOP (ex.: venda interna para comercialização a 4% e para uso e consumo com outra alíquota).",
         "- **Operação por CFOP**: o programa separa por CFOP só onde o tratamento muda (ex.: 6409 × 6152) e junta",
         "  os CFOPs de mesmo tratamento em uma regra. Grupos diferentes (venda, transferência...) nunca se misturam.",
         "- **PIS/COFINS**: valem para todas as UFs e todos os participantes; incidem nas vendas. Só o perfil de",
         "  produto muda o tratamento: alíquota básica, monofásico ou alíquota zero.",
         "- **IPI**: todas as UFs e participantes; CFOPs de venda. Depende do produto E da origem: importação",
         "  direta (origem 1) e importação por trade (origem 2) tributam quando há alíquota; origem 2 comprada no",
         "  mercado interno de fornecedor comum sai sem IPI. Para vendas à ZFM/ALC, permita Participante no IPI.",
         "- **DIFAL**: só na venda interestadual a não contribuinte (ex.: CFOP 6108); para os demais, só o ICMS.",
         "- **FECP**: segue a lógica do DIFAL, mas só para algumas UFs de destino (ex.: SE, RJ).",
         "- **ICMS ST**: depende do produto (CEST/NCM), da UF de destino (protocolos) e da operação.",
         "- **DIFAL, ICMS ST, FECP ST e FECP do DIFAL**: uma regra fiscal para CADA combinação UF origem → UF destino",
         "  (ex.: SC→BA, SC→SP e SC→RJ = 3 regras). Na tabela de dimensões isso é UF destino = `cada`.",
         "- **cBenef (código de benefício/ajuste)**: algumas UFs exigem o código quando o ICMS não é destacado",
         "  ou é reduzido. Cada regra de ICMS aceita UM único cBenef: itens com cBenef diferentes obrigam regras",
         "  diferentes. O programa separa automaticamente e confere se o XML trouxe o código.",
         "- **CFOP**: o 1º dígito (5 interna, 6 interestadual, 7 exterior) é convertido pelo sistema conforme a UF; 5949",
         "  e 6949 são a mesma operação. 6108 é a venda (x102) a não contribuinte de outra UF, conversão automática;",
         "  não existe 5108 (interna vai com 5102, 5403...). Ver **Equivalência de CFOP** e **CFOPs inválidos**.",
         "- **Regras de base (F27)**: cada base aceita UM percentual de redução e uma composição. Base comum",
         "  (mercadoria + frete + seguro + despesas - desconto) e base com IPI são bases diferentes; cada percentual",
         "  de redução (ex.: 15%, 20%, 80%) é uma base própria para cada composição.",
         "- **Alíquota por NCM**: com regra de NCM, a alíquota sai da tabela por NCM, origem, UF origem, UF destino",
         "  e CEST, e não é preciso segregar regras por UF/origem (ex.: ICMS origem 0 a 12% para S/SE exceto ES e 7%",
         "  para N/NE/CO e ES; origem 1 a 4%). Sem regra de NCM, a alíquota é fixa e cada alíquota vira uma regra.",
         "  Defina em Opções: USAR_REGRAS_NCM e ALIQUOTA_POR_NCM.",
         "- **Escrituração (CJ2)**: uma por tributo e por CST (na CJ2 escolhe-se o CST do imposto e depois o CST).",
         "  Define se o imposto vai como Tributado (sai na nota), Isento ou Outros (sai",
         "  zerado) e a ação na nota. ICMS, PIS e COFINS não têm ação (já estão no preço); IPI, ICMS ST e FECP ST",
         "  somam no total da nota; DIFAL e FECP são tributados sem ação na nota. Cada tributo tem a sua",
         "  escrituração, e tributado × zerado nunca compartilham a mesma escrituração.", "",
         "- **Código da regra**: 3 letras do imposto + 3 dígitos; saída de 500 a 999, entrada de 000 a 499",
         "  (ex.: ICM500, PIS500, IPI501). Códigos já usados no ambiente vão em **Códigos reservados**.",
         "- **Perfil de operação** = CFOPs + tipos de operação. O tipo de operação casa com a finalidade",
         "  (de-para em **Tipos de operação**, ex.: REVENDA = V1, CONSUMO = V3, INSUMO = V5). Clientes com",
         "  finalidade própria (ex.: revenda para insumo) vão em **Finalidade por cliente** e o motor considera.",
         "- **Grupos de operação nunca dividem a mesma regra**: vendas, transferências, bonificações, remessas e",
         "  devoluções têm regras próprias (ex.: operações com ICMS zero têm cBenef diferentes em SC, SP...).",
         *_CONHECIMENTO_EXTRA.splitlines(), "",
         "### Como acrescentar conhecimento",
         "- Uma nova exceção de um tributo → acrescente uma linha em **Regras de negócio**.",
         "- Um tributo que passou a variar por um critério → mude para `sim` em **Dimensões por tributo**.",
         "- Um CFOP novo ou com finalidade errada → ajuste **Grupos de operação**.", "",
         "## Tributos", "",
         "| Chave | F2B_TRIB | Nome na descrição | Prefixo da regra | Início | Dígitos |",
         "|---|---|---|---|---|---|"]
    for k, (trib, nome, pref, ini, dig, _) in TRIBUTOS.items():
        L.append(f"| {k} | {trib} | {nome} | {pref} | {ini} | {dig} |")
    L += ["", "## Dimensões por tributo", "",
          "Por quais critérios cada tributo PODE separar regras (`sim`/`não`). Operação: `cfop` ou `grupo`.",
          "UF destino `cada` = uma regra para cada combinação de UF (nunca agrupa UFs).", "",
          "| Tributo | Classe do produto | Origem | Participante | UF destino | Operação | Finalidade |",
          "|---|---|---|---|---|---|---|"]
    for k, dm in DIMENSOES.items():
        L.append(f"| {k} | {sim(dm['classe'])} | {sim(dm['origem'])} | {sim(dm['participante'])} | "
                 f"{'cada' if dm['uf'] == 'cada' else sim(dm['uf'])} "
                 f"| {dm['operacao']} | {sim(dm['finalidade'])} |")
    L += ["", "## Regras de negócio", "",
          "Condições: `campo=valor` (vírgula = OU; `*` no fim = começa com; `!=` = diferente), unidas por ` e `.",
          "Campos: cfop, natureza, grupo, finalidade, uf, abrangencia (INTERNA/INTERESTADUAL/EXTERIOR), "
          "participante, contribuinte (SIM/NAO/ISENTO), pessoa (PF/PJ), origem, ncm, cest, cst, suframa (SIM/NAO).",
          "Ações: `base=CÓDIGO` · `ausente` (o tributo não deve existir) · `aliquota=ncm` (força o índice por NCM).", "",
          "| Tributo | Quando | Então | Observação |", "|---|---|---|---|"]
    for t, c, a, o in REGRAS_NEGOCIO:
        L.append(f"| {t} | {_md(c)} | {_md(a)} | {_md(o)} |")
    L += ["", "## Código de benefício (cBenef)", "",
          "UFs do EMITENTE que exigem cBenef e CSTs de ICMS em que ele é exigido. Cada regra de ICMS aceita um único "
          "cBenef.", "", "| Item | Valor |", "|---|---|",
          f"| UFS_EXIGEM | {', '.join(sorted(UFS_CBENEF))} |",
          f"| CST_EXIGEM | {', '.join(sorted(CST_EXIGE_CBENEF))} |"]
    L += ["", "## Escrituração — ação na nota", "",
          "STOTNF: 1 Sem ação · 2 Subtrai só do total · 3 Subtrai do total e da duplicata · 5 Soma só no total · "
          "6 Soma no total e na duplicata.", "",
          "| Tributo | Com imposto | Sem imposto | Observação |", "|---|---|---|---|"]
    obs_stot = {"ICMS": "já está no preço (desonerado que deduz usa 3)", "ICMSST": "soma na nota",
                "FECPST": "soma na nota", "IPI": "soma na nota", "DIFAL": "tributado, sem ação na nota",
                "FECP": "tributado, sem ação na nota", "FECPDF": "tributado, sem ação na nota",
                "PIS": "já está no preço", "COF": "já está no preço"}
    for k, (com, sem) in STOTNF.items():
        L.append(f"| {k} | {com} | {sem} | {obs_stot.get(k, '')} |")
    L += ["", "## Escrituração — incidência por CST", "",
          "INCIDE: 1 Tributado · 2 Isento · 3 Outros · 4 Tributado e Isento · 5 Tributado e Outros. "
          "`valor` = 1 se houver imposto, senão 3. CST `*` = qualquer outro.", "",
          "| Tributo | CSTs | INCIDE |", "|---|---|---|"]
    agr = defaultdict(list)
    for (t, c), v in INCIDE.items():
        agr[(t, v)].append(c)
    for (t, v), cs in agr.items():
        L.append(f"| {t} | {', '.join(cs)} | {v} |")
    L += ["", "## Perfis de origem/destino por UF", "",
          "Usados nos tributos com uma regra por UF (DIFAL, ICMS ST, FECP ST). Ajuste os códigos ao seu ambiente.", "",
          "| UF destino | Código | Descrição |", "|---|---|---|"]
    for uf in "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO".split():
        cod, desc = OD_POR_UF.get(uf, (f"OD{uf}01", f"SAÍDAS | INTERESTADUAL | {uf}"))
        L.append(f"| {uf} | {cod} | {_md(desc)} |")
    L += ["", "## Tipos de operação", "",
          "De-para da finalidade para o tipo de operação usado nos perfis de operação.", "",
          "| Finalidade | Tipo de operação | Descrição |", "|---|---|---|"]
    for f, (c, d) in TIPOS_OPERACAO.items():
        L.append(f"| {f} | {c} | {_md(d)} |")
    L += ["", "## Finalidade por cliente", "",
          "Clientes cuja finalidade não segue o indFinal da nota (ex.: revenda para insumo = INSUMO → V5).", "",
          "| CNPJ/CPF | Finalidade | Observação |", "|---|---|---|"]
    for doc, f in FINALIDADE_CLIENTE.items():
        L.append(f"| {doc} | {f} | {_md(OBS_CLIENTE.get(doc, ''))} |")
    L += ["", "## Códigos reservados", "",
          "Códigos que já existem no ambiente (regras, perfis, bases...). Separe por vírgula ou espaço; aceita "
          "faixas como ICM500-ICM560.", "", "| Códigos |", "|---|",
          f"| {', '.join(sorted(CODIGOS_RESERVADOS))} |"]
    L += ["", "## Equivalência de CFOP", "",
          "O 1º dígito do CFOP (5 interna, 6 interestadual, 7 exterior) é convertido pelo sistema conforme a UF:",
          "5949, 6949 e 7949 são a mesma operação e não são divergência. Alguns CFOPs também são conversões",
          "automáticas de outro (ex.: 6108 = venda a não contribuinte de outra UF, convertida do 5102/6102).",
          "Não existe operação interna com 5108: a venda interna vai com o CFOP normal (5102, 5403...).", "",
          f"| Opção | Valor |", "|---|---|", f"| USAR_EQUIVALENCIA_CFOP | {sim(USAR_EQUIVALENCIA_CFOP)} |", "",
          "| CFOP (3 últimos dígitos) | Equivale a | Observação |", "|---|---|---|"]
    for k, (v, o) in EQUIV_CFOP.items():
        L.append(f"| {k} | {v} | {_md(o)} |")
    L += ["", "## CFOPs inválidos", "", "CFOPs que não existem ou não cabem na operação: aparecem em Validações como erro do XML.", "",
          "| CFOP | Motivo |", "|---|---|"]
    for k, v in CFOP_INVALIDOS.items():
        L.append(f"| {k} | {_md(v)} |")
    L += ["", "## Exceções", "",
          "Regra própria para clientes, produtos ou NCMs específicos, quando nenhuma dimensão separa os itens.",
          "Campo: dest (cliente), cprod (produto) ou ncm. Valores separados por vírgula.", "",
          "| Tributo | Campo | Valores | Observação | Id |", "|---|---|---|---|---|"]
    for x in EXCECOES:
        L.append(f"| {x['tributo']} | {x['campo']} | {', '.join(x.get('valores', []))} | {_md(x.get('obs', ''))} | {x['id']} |")
    L += ["", "## Segregações", "",
          "Cenários que pareciam divergentes mas são legítimos: o tributo passa a separar regras pelo critério.",
          "Critérios: cfop, classe, origem, participante, uf. Vale para a família (IBS/CBS juntos; PIS/COFINS juntos).", "",
          "| Tributo | Separar por | Observação |", "|---|---|---|"]
    for x in SEGREGACOES:
        L.append(f"| {x['tributo']} | {x['dim']} | {_md(x.get('obs', ''))} |")
    L += ["", "## Agrupamentos", "",
          "Na família do ICMS o programa gera o esqueleto separado (operação | abrangência | origem | participante |",
          "regime | finalidade) e PERGUNTA antes de juntar regras de mesmo tratamento. A resposta fica aqui.",
          "Critérios: tipo, regime, origem, finalidade, abrangencia. Decisão: juntar ou separar. Tributo `*` = todos.", "",
          "| Tributo | Critério | Decisão | Observação |", "|---|---|---|---|"]
    for (t_, c_), d_ in AGRUPAMENTOS.items():
        L.append(f"| {t_} | {c_} | {d_} |  |")
    L += ["", *_SECOES_EXTRA.splitlines()]
    L += ["", "## Grupos de operação", "",
          "Finalidade `indFinal` = vem da nota (CONSUMO/REVENDA). Qualquer outro texto é a finalidade fixa.", "",
          "| CFOPs (3 últimos dígitos) | Natureza | Grupo | Finalidade |", "|---|---|---|---|"]
    por_nat = defaultdict(list)
    for c, v in OPERACAO.items():
        por_nat[v].append(c)
    for (n, g, f), cs in por_nat.items():
        L.append(f"| {' '.join(sorted(cs))} | {n} | {g} | {f} |")
    L += ["", "## Perfis de produto por origem", "",
          "| Grupo | Origens | Código | Descrição |", "|---|---|---|---|"]
    for g, (cod, desc, curto) in PERFIL_ORIGEM.items():
        origens = ",".join(o for o, gg in ORIGEM_GRUPO.items() if gg == g)
        L.append(f"| {g} | {origens} | {cod} | {_md(desc)} |")
    L += ["", "## Perfis de participante", "",
          "| Tipo no XML | Código | Descrição curta | Critério sugerido |", "|---|---|---|---|"]
    for k, (cod, curto, crit) in PERFIL_PARTICIPANTE.items():
        L.append(f"| {k} | {cod} | {_md(curto)} | {_md(crit)} |")
    L += ["", "## Códigos gerais", "", "| Item | Código | Descrição |", "|---|---|---|",
          f"| PRODUTO_GERAL | {PERFIL_PRODUTO_GERAL[0]} | {_md(PERFIL_PRODUTO_GERAL[1])} |",
          f"| PARTICIPANTE_GERAL | {PERFIL_PARTICIPANTE_GERAL[0]} | {_md(PERFIL_PARTICIPANTE_GERAL[1])} |",
          f"| OD_INTERNA | {OD_INTERNA[0]} | {_md(OD_INTERNA[1])} |",
          f"| OD_INTERESTADUAL | {OD_INTERESTADUAL[0]} | {_md(OD_INTERESTADUAL[1])} |",
          f"| OD_TODAS | {OD_TODAS[0]} | {_md(OD_TODAS[1])} |",
          f"| ALIQ_NCM | {ALIQ_NCM[0]} | {_md(ALIQ_NCM[1])} |",
          f"| ALIQ_ZERO | {ALIQ_ZERO[0]} | {_md(ALIQ_ZERO[1])} |",
          "", "## Opções", "", "| Opção | Valor |", "|---|---|",
          f"| RAPUR | {RAPUR_PADRAO} |", f"| INICIO_PERFIL_OPERACAO | {INICIO_PERFIL_OPERACAO} |",
          f"| AGRUPAR_MAXIMO | {sim(OPCOES['AGRUPAR_MAXIMO'])} |",
          f"| SEPARAR_PARTICIPANTE | {sim(OPCOES['SEPARAR_PARTICIPANTE'])} |",
          f"| SEPARAR_REGRAS_POR_GRUPO | {sim(OPCOES['SEPARAR_GRUPOS'])} |",
          f"| ESQUELETO_COMPLETO | {sim(OPCOES['ESQUELETO_COMPLETO'])} |",
          f"| USAR_REGRAS_NCM | {sim(bool(OPCOES['ALIQ_NCM']))} |",
          f"| ALIQUOTA_POR_NCM | {', '.join(OPCOES['ALIQ_NCM'])} |"]
    return "\n".join(L) + "\n"


def _secoes_md(texto):
    sec, atual = {}, None
    for linha in texto.splitlines():
        if linha.startswith("## "):
            atual = linha[3:].strip().lower()
            sec[atual] = {"tab": [], "txt": []}
            continue
        if atual is None:
            continue
        l = linha.strip()
        if l.startswith("|"):
            miolo = l[1:-1] if l.endswith("|") and not l.endswith("\\|") else l[1:]
            cels = [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", miolo)]
            if cels and all(set(c) <= set("-: ") for c in cels):
                continue
            sec[atual]["tab"].append(cels)
        else:
            sec[atual]["txt"].append(linha)
    return sec


def _tabela(sec, inicio):
    for k, v in sec.items():
        if k.startswith(inicio):
            return v["tab"][1:]
    return []


def carregar_padroes(caminho=None):
    """Lê o .md e aplica os padrões. -> (texto do arquivo, [avisos])"""
    global TRIBUTOS, ORDEM_TRIB, RAPUR_PADRAO, INICIO_PERFIL_OPERACAO, PERFIL_PRODUTO_GERAL, USAR_EQUIVALENCIA_CFOP
    global PERFIL_PARTICIPANTE_GERAL, OD_INTERNA, OD_INTERESTADUAL, OD_TODAS, ALIQ_NCM, ALIQ_ZERO
    caminho = caminho or ARQ_PADROES
    avisos = []
    if not os.path.exists(caminho):
        try:
            with open(caminho, "w", encoding="utf-8") as f:
                f.write(md_padrao())
            avisos.append(f"Arquivo de padrões criado: {caminho}")
        except OSError as e:
            avisos.append(f"Não consegui criar {caminho}: {e}. Usando o padrão interno.")
            return md_padrao(), avisos
    with open(caminho, encoding="utf-8") as f:
        texto = f.read()
    sec = _secoes_md(texto)

    trib = {}
    for l in _tabela(sec, "tributos"):
        if len(l) >= 6 and l[0] in FAMILIA:
            try:
                trib[l[0]] = (l[1], l[2], l[3], int(l[4]), int(l[5]), FAMILIA[l[0]])
            except ValueError:
                avisos.append(f"Tributos: linha inválida {l}")
        elif l and l[0]:
            avisos.append(f"Tributos: chave desconhecida '{l[0]}' (use {', '.join(FAMILIA)})")
    if trib:
        TRIBUTOS = trib
        ORDEM_TRIB = list(trib)

    po = _tabela(sec, "perfis de produto")
    if po:
        PERFIL_ORIGEM.clear()
        ORIGEM_GRUPO.clear()
        for l in po:
            if len(l) >= 4:
                origens = [o.strip() for o in re.split(r"[,/ ]+", l[1]) if o.strip()]
                for o in origens:
                    ORIGEM_GRUPO[o] = l[0]
                PERFIL_ORIGEM[l[0]] = (l[2], l[3], "ORIGEM " + "/".join(origens))

    pp = _tabela(sec, "perfis de participante")
    if pp:
        PERFIL_PARTICIPANTE.clear()
        for l in pp:
            if len(l) >= 3:
                PERFIL_PARTICIPANTE[l[0]] = (l[1], l[2], l[3] if len(l) > 3 else "")

    for l in _tabela(sec, "códigos gerais") or _tabela(sec, "codigos gerais"):
        if len(l) < 3:
            continue
        v = (l[1], l[2])
        if l[0] == "PRODUTO_GERAL":
            PERFIL_PRODUTO_GERAL = v
        elif l[0] == "PARTICIPANTE_GERAL":
            PERFIL_PARTICIPANTE_GERAL = v
        elif l[0] == "OD_INTERNA":
            OD_INTERNA = v
        elif l[0] == "OD_INTERESTADUAL":
            OD_INTERESTADUAL = v
        elif l[0] == "OD_TODAS":
            OD_TODAS = v
        elif l[0] == "ALIQ_NCM":
            ALIQ_NCM = v
        elif l[0] == "ALIQ_ZERO":
            ALIQ_ZERO = v

    usar_ncm = True
    for l in _tabela(sec, "opções") or _tabela(sec, "opcoes"):
        if len(l) < 2:
            continue
        if l[0] == "RAPUR":
            RAPUR_PADRAO = l[1]
        elif l[0] == "INICIO_PERFIL_OPERACAO" and l[1].isdigit():
            INICIO_PERFIL_OPERACAO = int(l[1])
        elif l[0] == "ALIQUOTA_POR_NCM":
            OPCOES["ALIQ_NCM"] = [k for k in (_chave_trib(x) for x in re.split(r"[,/ ]+", l[1]) if x.strip()) if k]
        elif l[0] == "SEPARAR_REGRAS_POR_GRUPO":
            OPCOES["SEPARAR_GRUPOS"] = l[1].strip().lower() in _SIM
        elif l[0] == "USAR_REGRAS_NCM":
            usar_ncm = l[1].strip().lower() in _SIM
        elif l[0] in OPCOES:
            OPCOES[l[0]] = l[1].strip().lower() in _SIM

    if not usar_ncm:
        OPCOES["ALIQ_NCM"] = []

    ops = _tabela(sec, "grupos de operação") or _tabela(sec, "grupos de operacao") or _tabela(sec, "natureza")
    if ops:
        OPERACAO.clear()
        for l in ops:
            if len(l) >= 2:
                nat = l[1]
                grupo = l[2] if len(l) > 2 and l[2] else ("VENDAS" if nat.upper().startswith("VENDA") else nat)
                fin = l[3] if len(l) > 3 and l[3] else ("indFinal" if grupo == "VENDAS" else nat)
                for c in re.findall(r"\d{3,4}", l[0]):
                    OPERACAO[c[-3:]] = (nat, grupo, fin)
        NATUREZA.clear()
        NATUREZA.update({k: v[0] for k, v in OPERACAO.items()})

    for l in _tabela(sec, "dimensões") or _tabela(sec, "dimensoes"):
        k = _chave_trib(l[0]) if l else None
        if not k or len(l) < 7:
            if l and l[0]:
                avisos.append(f"Dimensões: linha ignorada {l[:2]}")
            continue
        DIMENSOES[k] = dict(classe=l[1].lower() in _SIM, origem=l[2].lower() in _SIM,
                            participante=l[3].lower() in _SIM,
                            uf="cada" if _norm(l[4]).startswith(("CADA", "POR UF", "UMA")) else l[4].lower() in _SIM,
                            operacao="grupo" if l[5].lower().startswith("g") else "cfop",
                            finalidade=l[6].lower() in _SIM)

    for l in _tabela(sec, "código de benefício") or _tabela(sec, "codigo de beneficio"):
        if len(l) >= 2 and l[0] == "UFS_EXIGEM":
            UFS_CBENEF.clear()
            UFS_CBENEF.update(x.strip().upper() for x in re.split(r"[,/ ]+", l[1]) if x.strip())
        elif len(l) >= 2 and l[0] == "CST_EXIGEM":
            CST_EXIGE_CBENEF.clear()
            CST_EXIGE_CBENEF.update(x.strip() for x in re.split(r"[,/ ]+", l[1]) if x.strip())

    for l in _tabela(sec, "escrituração — ação") or _tabela(sec, "escrituração - ação"):
        k = _chave_trib(l[0]) if l else None
        if k and len(l) >= 3:
            STOTNF[k] = (l[1].strip() or "1", l[2].strip() or "1")
    inc = _tabela(sec, "escrituração — incidência") or _tabela(sec, "escrituração - incidência")
    if inc:
        INCIDE.clear()
        for l in inc:
            k = _chave_trib(l[0]) if l else None
            if k and len(l) >= 3:
                for c in re.split(r"[,/ ]+", l[1]):
                    if c.strip():
                        INCIDE[(k, c.strip())] = l[2].strip().lower() if l[2].strip().lower() == "valor" else l[2].strip()

    odu = _tabela(sec, "perfis de origem/destino por uf")
    if odu:
        OD_POR_UF.clear()
        for l in odu:
            if len(l) >= 2 and l[0]:
                OD_POR_UF[l[0].upper()] = (l[1], l[2] if len(l) > 2 else f"SAÍDAS | {l[0].upper()}")

    tpo = _tabela(sec, "tipos de operação") or _tabela(sec, "tipos de operacao")
    if tpo or any(k.startswith("tipos de opera") for k in sec):
        TIPOS_OPERACAO.clear()
        for l in tpo:
            if len(l) >= 2 and l[0]:
                TIPOS_OPERACAO[l[0].strip().upper()] = (l[1].strip(), l[2].strip() if len(l) > 2 else "")
    fcl = _tabela(sec, "finalidade por cliente")
    if fcl or any(k.startswith("finalidade por cliente") for k in sec):
        FINALIDADE_CLIENTE.clear()
        OBS_CLIENTE.clear()
        for l in fcl:
            doc = re.sub(r"\D", "", l[0]) if l else ""
            if doc and len(l) >= 2 and l[1].strip():
                FINALIDADE_CLIENTE[doc] = l[1].strip().upper()
                OBS_CLIENTE[doc] = l[2].strip() if len(l) > 2 else ""
                if l[1].strip().upper() not in TIPOS_OPERACAO:
                    avisos.append(f"Finalidade por cliente: '{l[1].strip()}' não está no de-para de tipos de operação")
    res = _tabela(sec, "códigos reservados") or _tabela(sec, "codigos reservados")
    if res or any(k.startswith(("códigos reservados", "codigos reservados")) for k in sec):
        CODIGOS_RESERVADOS.clear()
        for l in res:
            for tok in re.split(r"[,; ]+", " ".join(l)):
                tok = tok.strip().upper()
                m = re.match(r"^([A-Z]+)(\d+)-([A-Z]+)?(\d+)$", tok)
                if m:
                    pref, a, b = m.group(1), int(m.group(2)), int(m.group(4))
                    CODIGOS_RESERVADOS.update(f"{pref}{n:0{len(m.group(2))}d}" for n in range(a, b + 1))
                elif tok:
                    CODIGOS_RESERVADOS.add(tok)

    eq = _tabela(sec, "equivalência de cfop") or _tabela(sec, "equivalencia de cfop")
    if eq or any(k.startswith(("equivalência de cfop", "equivalencia de cfop")) for k in sec):
        EQUIV_CFOP.clear()
        for l in eq:
            if l and l[0] == "USAR_EQUIVALENCIA_CFOP" and len(l) > 1:
                USAR_EQUIVALENCIA_CFOP = l[1].strip().lower() in _SIM
            elif len(l) >= 2 and re.fullmatch(r"\d{3}", l[0]) and re.fullmatch(r"\d{3}", l[1]):
                EQUIV_CFOP[l[0]] = (l[1], l[2] if len(l) > 2 else "")
    inv = _tabela(sec, "cfops inválidos") or _tabela(sec, "cfops invalidos")
    if inv or any(k.startswith(("cfops inválidos", "cfops invalidos")) for k in sec):
        CFOP_INVALIDOS.clear()
        for l in inv:
            if l and re.fullmatch(r"\d{4}", l[0]):
                CFOP_INVALIDOS[l[0]] = l[1] if len(l) > 1 else ""

    exs = _tabela(sec, "exceções") or _tabela(sec, "excecoes")
    if exs or any(k.startswith(("exceções", "excecoes")) for k in sec):
        EXCECOES.clear()
        for n_, l in enumerate(exs, 1):
            k = _chave_trib(l[0]) if l else None
            campo = l[1].strip().lower() if len(l) > 1 else ""
            vals = [v.strip() for v in re.split(r"[,; ]+", l[2]) if v.strip()] if len(l) > 2 else []
            if k and campo in CAMPOS_EXCECAO and vals:
                EXCECOES.append({"tributo": k, "campo": campo, "valores": vals, "obs": l[3].strip() if len(l) > 3 else "",
                                 "id": (l[4].strip() if len(l) > 4 and l[4].strip() else f"E{n_}")})
            elif l and l[0]:
                avisos.append(f"Exceções: linha ignorada {l[:3]} (campos: dest, cprod, ncm)")

    sgs = _tabela(sec, "segregações") or _tabela(sec, "segregacoes")
    if sgs or any(k.startswith(("segregações", "segregacoes")) for k in sec):
        SEGREGACOES.clear()
        for l in sgs:
            k = _chave_trib(l[0]) if l else None
            dim = l[1].strip().lower() if len(l) > 1 else ""
            if k and dim in DIM_SEGREGACAO:
                SEGREGACOES.append({"tributo": k, "dim": dim, "obs": l[2].strip() if len(l) > 2 else ""})
            elif l and l[0]:
                avisos.append(f"Segregações: linha ignorada {l[:2]} (critérios: {', '.join(DIM_SEGREGACAO)})")

    agr = _tabela(sec, "agrupamentos")
    if agr or any(k.startswith("agrupamentos") for k in sec):
        AGRUPAMENTOS.clear()
        for l in agr:
            if len(l) < 3 or not l[0]:
                continue
            t_ = "*" if _norm(l[0]) in ("*", "TODOS", "TODOS OS TRIBUTOS") else _chave_trib(l[0])
            c_ = _norm(l[1]).lower().split()[0] if l[1].strip() else ""
            c_ = {"abrangência": "abrangencia", "participante": "tipo"}.get(c_, c_)
            d_ = _norm(l[2]).lower()
            d_ = "juntar" if d_.startswith("junt") else "separar" if d_.startswith("separ") else ""
            if t_ and c_ in CRITERIOS_AGRUP and d_:
                AGRUPAMENTOS[(t_, c_)] = d_
            else:
                avisos.append(f"Agrupamentos: linha ignorada {l[:3]} (critérios: {', '.join(CRITERIOS_AGRUP)}; "
                              f"decisão: juntar ou separar)")

    rn = _tabela(sec, "regras de negócio") or _tabela(sec, "regras de negocio")
    if rn or any(k.startswith("regras de neg") for k in sec):
        REGRAS_NEGOCIO.clear()
        for l in rn:
            if len(l) >= 3 and l[0]:
                if not _chave_trib(l[0]):
                    avisos.append(f"Regras de negócio: tributo desconhecido '{l[0]}'")
                try:
                    _compilar_condicoes(l[1])
                except ValueError as e:
                    avisos.append(f"Regras de negócio: {e}")
                REGRAS_NEGOCIO.append((l[0], l[1], l[2], l[3] if len(l) > 3 else ""))
    return texto, avisos


# ═════════════════════════════════════════════════════════════════════════════
# CENÁRIOS E RESUMO
# ═════════════════════════════════════════════════════════════════════════════
def montar_cenarios(an, mt):
    """Cenário = CFOP + finalidade + UF destino + participante + origem + classes de IPI/PIS/IBS.
    -> lista de dicts com a regra que cada tributo aciona."""
    cen = {}
    for d, it, tr in an["linhas"]:
        part = participante_de(d)
        gc, gp = grupo_cliente(d), grupo_produto(it)
        if gc:
            part += f" | {gc['nome']}"
        fin = _fin(d, it)
        cls = {f: _classe_produto(f, it, an["modas"]) for f in ("IPI", "PC", "IBS")}
        cls["ICMS"] = combo_icms(it)   # classe do ICMS: CST + alíquota + composição da base
        k = (it["cfop"], fin, d["uf_dest"], part, it["orig"] + (f" | {gp['nome']}" if gp else ""), cls["IPI"], cls["PC"],
             cls["IBS"], cls["ICMS"])
        c = cen.get(k)
        if c is None:
            regras = {}
            for t in ORDEM_TRIB:
                if t in tr and t in mt["cel_regra"]:
                    cl = celula(t, d, it, an["modas"], an["separar"] and TRIBUTOS[t][5] == "ORIG")
                    regras[t] = mt["cel_regra"][t].get(cl, "")
                else:
                    regras[t] = ""
            c = cen[k] = {"k": k, "itens": 0, "notas": set(), "exemplo": d["chave"], "regras": regras}
        c["itens"] += 1
        c["notas"].add(d["chave"])
    return sorted(cen.values(), key=lambda c: -c["itens"])


def resumo_texto(an, mt):
    v = mt["validacao"]
    tot = sum(v.values()) or 1
    por = Counter(r["F2B_TRIB"] for r in mt["regras"])
    dep = []
    for t, S in an["dims"].items():
        nomes = ["produto", "participante", "operação", "UF"]
        dep.append(f"  {TRIBUTOS[t][1]:<11} depende de: {', '.join(nomes[i] for i in S) or 'nada (uma regra)'}"
                   f"  →  {por.get(TRIBUTOS[t][0], 0)} regra(s)")
    f = lambda x: f"{x:,}".replace(",", ".")
    return "\n".join([
        f"Emitente: {an['cnpj']} · {an['nome']} · UF {an['uf_emit']}",
        f"Notas de saída analisadas: {f(an['notas'])} · itens: {f(an['itens'])}", "",
        f"REGRAS F2B A CADASTRAR: {len(mt['regras'])}",
        "  " + " · ".join(f"{k}: {q}" for k, q in por.items()), "",
        "CADASTROS NECESSÁRIOS (antes das regras):",
        f"  Perfis de produto ........ {len(mt['perf_prod'])}",
        f"  Perfis de participante ... {len(mt['perf_part'])}",
        f"  Perfis de origem/destino . {len(mt['perf_od'])}",
        f"  Perfis de operação ....... {len(mt['perf_op'])}   (tipos de operação: {len(mt['tipos_op'])})",
        f"  Regras de base (F27) ..... {len(mt['bases'])}",
        f"  Regras de alíquota (F28) . {len(mt['aliqs'])}   (+{f(len(mt['linhas_ncm']))} linhas por NCM/UF)",
        f"  Escriturações (CJ2) ...... {len(mt['escs'])}", "",
        "DE QUE CADA TRIBUTO DEPENDE:", *dep, "",
        "VALIDAÇÃO (cada item x tributo deve acionar exatamente 1 regra):",
        f"  Resultado correto ........ {(v['ok'] + v['sem_tributo_ok']) / tot * 100:.2f}%",
        f"  Duplicidades ............. {f(v['duplicada'])}",
        f"  Conflitos no próprio XML . {f(v['tratamento_diferente'] + v['sem_regra'] + v['aciona_indevido'])} "
        f"item×tributo em {len(an['conflitos'])} cenário(s) — veja a aba Conflitos", "",
        "REGRAS DE NEGÓCIO DO PADRÃO (prevalecem sobre o XML):",
        *[f"  {st['regra'][0]:<7} {st['regra'][1]:<45} → {st['regra'][2]:<12} "
          f"{st['aplicou']:>7} itens · {st['divergiu']} divergência(s)" + (f" · ERRO: {st['erro']}" if st['erro'] else "")
          for st in an["regras_negocio"]], "",
        "ORDEM DE CADASTRO NO CONFIGURADOR:",
        "  1) Perfis (produto, participante, origem/destino, operação) e tipos de operação",
        "  2) Regras de base, de alíquota e alíquotas por NCM",
        "  3) Regras de escrituração",
        "  4) Regras fiscais (F2B)",
    ])


UFS_BR = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI",
          "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"]
COLS_F21 = ["F21_CODIGO", "F21_UFORI", "F21_UFDEST", "F21_TIPOPF"]


def linhas_f21(mt):
    """Tabela F21 (Perfil Orig./Dest.) da GF: uma linha por par UF origem x UF destino de cada perfil OD.
    Perfil de todas as UFs ('*') lista todos os destinos."""
    linhas = []
    for cod, p in mt["perf_od"].items():
        s = p.get("_s", set())
        destinos = UFS_BR if s == {"*"} else sorted(s)
        origem = p.get("UF origem", "")
        for uf in destinos:
            if uf != origem or s == {origem}:
                linhas.append({"F21_CODIGO": cod, "F21_UFORI": origem, "F21_UFDEST": uf, "F21_TIPOPF": "01"})
    return linhas


def linha_csv_f2b(r):
    return ";".join(str(r.get(c, RAPUR_PADRAO if c == "F2B_RAPUR" else "")) for c in COLS_F2B)


COLS_F2B = ["F2B_REGRA", "F2B_DESC", "F2B_TRIB", "F2B_RBASE", "F2B_RALIQ", "F2B_PEROD", "F2B_PERFPA", "F2B_PERFOP",
            "F2B_PERFPR", "F2B_RFIN", "F2B_RAPUR", "F2B_RND", "F2B_ALTERA", "F2B_CODESC", "F2B_RGGUIA", "F2B_VLRMIN",
            "F2B_VLRMAX", "F2B_RDBASE", "F2B_STATUS", "F2B_ACMAX", "F2B_ACMIN", "VALOR_PERCENTUAL", "PERFOR_DESTAQUE"]


def detalhe_regra(r, mt):
    """Texto com todos os campos da regra e o conteúdo de cada cadastro que ela usa."""
    pr, pa = mt["perf_prod"].get(r["F2B_PERFPR"], {}), mt["perf_part"].get(r["F2B_PERFPA"], {})
    od, op = mt["perf_od"].get(r["F2B_PEROD"], {}), mt["perf_op"].get(r["F2B_PERFOP"], {})
    b, a, e = mt["bases"].get(r["F2B_RBASE"], {}), mt["aliqs"].get(r["F2B_RALIQ"], {}), mt["escs"].get(r["F2B_CODESC"], {})
    L = [f"REGRA {r['F2B_REGRA']}  —  {r['F2B_DESC']}", "=" * 90, "", "CAMPOS DA REGRA (F2B):"]
    for c in COLS_F2B:
        v = r.get(c, RAPUR_PADRAO if c == "F2B_RAPUR" else "")
        if v != "" or c in ("F2B_RFIN", "F2B_RGGUIA"):
            L.append(f"  {c:<12} {v}")
    L += ["", "O QUE CADA CÓDIGO PRECISA TER:",
          f"  Base {r['F2B_RBASE']}: {b.get('Descrição', '')}",
          f"      fórmula: {b.get('Fórmula sugerida', '') or '—'}",
          f"  Alíquota {r['F2B_RALIQ']}: {a.get('Descrição', '')} ({a.get('Tipo', '')}"
          f"{': ' + a['Valor'] + '%' if a.get('Valor') else ''})",
          f"  Código de ajuste (cBenef): {r.get('cBenef') or '— (nenhum)'}   ← uma regra de ICMS aceita um único cBenef",
          f"  Escrituração {r['F2B_CODESC']}: CSTCAB {e.get('CJ2_CSTCAB', '')} · CST {e.get('CJ2_CST', '')} · "
          f"INCIDE {e.get('CJ2_INCIDE', '')} ({e.get('Incidência', '')}) · "
          f"STOTNF {e.get('CJ2_STOTNF', '')} ({e.get('Ação na nota', '')})"
          + (f" · PERDIF {e['CJ2_PERDIF']}" if e.get("CJ2_PERDIF") else "")
          + (f" · cClassTrib {e['CJ2_CSTCCT (cClassTrib)']} (CJ2_CCT {e['CJ2_CCT']})" if e.get("CJ2_CSTCCT (cClassTrib)") else "")
          + (f" · {e['Observação']}" if e.get("Observação") else ""),
          f"  Perfil de produto {r['F2B_PERFPR']}: {pr.get('Descrição', '')}",
          f"  Perfil de participante {r['F2B_PERFPA']}: {pa.get('Descrição', '')} — {pa.get('Critério sugerido', '')}",
          f"  Perfil origem/destino {r['F2B_PEROD']}: {od.get('Descrição', '')} — UFs: {od.get('UFs destino', '')}",
          f"  Perfil de operação {r['F2B_PERFOP']}: {op.get('Descrição', '')}",
          f"      CFOPs: {op.get('CFOPs', '')}", f"      tipos de operação: {op.get('Tipos de operação', '')}", "",
          f"ITENS DOS XMLs QUE ACIONAM ESTA REGRA: {r['Itens']:,}".replace(",", "."),
          f"XML de exemplo (chave): {r['Exemplo (chave)']}", "",
          "LINHA PARA IMPORTAÇÃO (layout F2B):", "  " + linha_csv_f2b(r)]
    if r["F2B_RALIQ"] == ALIQ_NCM[0]:
        linhas = [l for l in mt["linhas_ncm"] if l["Tributo"] == r["F2B_TRIB"]]
        L += ["", f"ALÍQUOTAS POR NCM/UF USADAS POR {r['F2B_TRIB']} ({len(linhas)} linhas; primeiras 15):"]
        for l in linhas[:15]:
            L.append(f"  NCM {l['NCM']:<9} orig {l['Origem']:<2} {l['UF origem']}→{l['UF destino']:<3} "
                     f"CEST {l['CEST'] or '*':<8} alíq {l['Alíquota %']:>6}%"
                     + (f"  MVA/inter {l['MVA % / Alíq. interestadual %']}%" if l["MVA % / Alíq. interestadual %"] else ""))
    return "\n".join(L)


# ═════════════════════════════════════════════════════════════════════════════
# TELA
# ═════════════════════════════════════════════════════════════════════════════
def tela():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    root = tk.Tk()
    root.title("Gerador de Cenários — Configurador de Tributos")
    root.geometry("1280x780")
    try:
        root.state("zoomed")
    except tk.TclError:
        pass
    q = queue.Queue()
    est = {"docs": {}, "canc": set(), "emit": [], "an": None, "mt": None, "cen": [], "regras": {}}

    # ── barra superior ──────────────────────────────────────────────────────
    topo = ttk.Frame(root, padding=(10, 8))
    topo.pack(fill="x")
    ttk.Button(topo, text="Importar pasta…", command=lambda: importar("pasta")).pack(side="left")
    ttk.Button(topo, text="Importar ZIP…", command=lambda: importar("zip")).pack(side="left", padx=4)
    ttk.Button(topo, text="Importar XMLs…", command=lambda: importar("xml")).pack(side="left")
    ttk.Label(topo, text="   CNPJ:").pack(side="left")
    cb = ttk.Combobox(topo, state="readonly", width=60)
    cb.pack(side="left", padx=4)
    cb.bind("<<ComboboxSelected>>", lambda e: gerar())
    v_agr = tk.BooleanVar(value=OPCOES["AGRUPAR_MAXIMO"])
    v_sep = tk.BooleanVar(value=OPCOES["SEPARAR_PARTICIPANTE"])
    ttk.Checkbutton(topo, text="Agrupar ao máximo", variable=v_agr, command=lambda: gerar()).pack(side="left", padx=6)
    ttk.Checkbutton(topo, text="Separar por participante", variable=v_sep, command=lambda: gerar()).pack(side="left")
    ttk.Button(topo, text="Limpar", command=lambda: limpar()).pack(side="right")

    v_st = tk.StringVar(value="Importe os XMLs de saída (pasta, ZIP ou arquivos).")
    barra = ttk.Label(root, textvariable=v_st, padding=(10, 2))
    barra.pack(fill="x", side="bottom")

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=8, pady=4)

    # ── utilitário: tabela ordenável ────────────────────────────────────────
    def nova_tabela(pai, colunas, larguras=None, ao_selecionar=None, altura=None):
        f = ttk.Frame(pai)
        tv = ttk.Treeview(f, columns=colunas, show="headings", height=altura or 20)
        for i, c in enumerate(colunas):
            tv.heading(c, text=c, command=lambda c=c: ordenar(tv, c, False))
            tv.column(c, width=(larguras[i] if larguras else 120), stretch=True, anchor="w")
        sy = ttk.Scrollbar(f, orient="vertical", command=tv.yview)
        sx = ttk.Scrollbar(f, orient="horizontal", command=tv.xview)
        tv.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        tv.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")
        f.rowconfigure(0, weight=1)
        f.columnconfigure(0, weight=1)
        if ao_selecionar:
            tv.bind("<<TreeviewSelect>>", lambda e: ao_selecionar(tv))
        return f, tv

    def ordenar(tv, col, rev):
        def chave(v):
            try:
                return (0, float(str(v).replace(".", "").replace(",", ".")))
            except ValueError:
                return (1, str(v))
        itens = sorted(((tv.set(k, col), k) for k in tv.get_children("")), key=lambda x: chave(x[0]), reverse=rev)
        for i, (_, k) in enumerate(itens):
            tv.move(k, "", i)
        tv.heading(col, command=lambda: ordenar(tv, col, not rev))

    def preencher(tv, linhas):
        tv.delete(*tv.get_children())
        for l in linhas:
            tv.insert("", "end", values=l)

    def caixa_texto(pai, altura=12):
        f = ttk.Frame(pai)
        t = tk.Text(f, wrap="none", font=("Consolas", 10), height=altura)
        sy = ttk.Scrollbar(f, orient="vertical", command=t.yview)
        sx = ttk.Scrollbar(f, orient="horizontal", command=t.xview)
        t.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        t.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")
        f.rowconfigure(0, weight=1)
        f.columnconfigure(0, weight=1)
        return f, t

    def escrever(t, s):
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.insert("end", s)
        t.configure(state="disabled")

    # ── aba Resumo ──────────────────────────────────────────────────────────
    ab_res = ttk.Frame(nb)
    nb.add(ab_res, text="Resumo")
    f, txt_res = caixa_texto(ab_res)
    f.pack(fill="both", expand=True)

    # ── aba Regras ──────────────────────────────────────────────────────────
    ab_reg = ttk.Frame(nb)
    nb.add(ab_reg, text="Regras F2B")
    filtro = ttk.Frame(ab_reg, padding=4)
    filtro.pack(fill="x")
    ttk.Label(filtro, text="Tributo:").pack(side="left")
    cb_trib = ttk.Combobox(filtro, state="readonly", width=12, values=["Todos"])
    cb_trib.current(0)
    cb_trib.pack(side="left", padx=4)
    ttk.Label(filtro, text="Buscar:").pack(side="left", padx=(10, 0))
    v_busca = tk.StringVar()
    ttk.Entry(filtro, textvariable=v_busca, width=40).pack(side="left", padx=4)
    ttk.Button(filtro, text="Copiar regra selecionada", command=lambda: copiar(False)).pack(side="right")
    ttk.Button(filtro, text="Copiar todas (layout F2B)", command=lambda: copiar(True)).pack(side="right", padx=4)
    ttk.Button(filtro, text="Exportar CSV…", command=lambda: exportar()).pack(side="right")
    cb_trib.bind("<<ComboboxSelected>>", lambda e: mostrar_regras())
    v_busca.trace_add("write", lambda *a: mostrar_regras())
    pan = ttk.PanedWindow(ab_reg, orient="vertical")
    pan.pack(fill="both", expand=True)
    cols_reg = ("Regra", "Tributo", "Descrição", "Base", "Alíquota", "Orig/Dest", "Participante", "Operação",
                "Produto", "Escrituração", "cBenef", "Itens")
    f, tv_reg = nova_tabela(pan, cols_reg, (70, 70, 460, 70, 70, 70, 80, 70, 70, 80, 80, 70),
                            lambda tv: selecionar_regra(tv), 14)
    pan.add(f, weight=3)
    f, txt_reg = caixa_texto(pan, 14)
    pan.add(f, weight=2)

    # ── aba Cenários ────────────────────────────────────────────────────────
    ab_cen = ttk.Frame(nb)
    nb.add(ab_cen, text="Cenários")
    pan2 = ttk.PanedWindow(ab_cen, orient="vertical")
    pan2.pack(fill="both", expand=True)
    cols_cen = ["CFOP", "Finalidade", "UF dest.", "Participante", "Origem", "Classe IPI", "Classe PIS/COF",
                "Classe IBS/CBS", "Itens", "Notas"]
    f, tv_cen = nova_tabela(pan2, cols_cen + ["Regras"], None, lambda tv: selecionar_cenario(tv), 16)
    pan2.add(f, weight=3)
    f, txt_cen = caixa_texto(pan2, 10)
    pan2.add(f, weight=2)

    # ── aba Cadastros ───────────────────────────────────────────────────────
    ab_cad = ttk.Frame(nb)
    nb.add(ab_cad, text="Cadastros necessários")
    nb_cad = ttk.Notebook(ab_cad)
    nb_cad.pack(fill="both", expand=True)
    tabs_cad = {}
    for nome, cols in [("Perfis de produto", ("Código", "Descrição", "Família", "Classes", "Produtos")),
                       ("Perfis de participante", ("Código", "Descrição", "Tipos", "Critério sugerido", "Clientes")),
                       ("Origem/destino", ("Código", "Descrição", "UF origem", "UFs destino")),
                       ("Perfis de operação", ("Código", "Descrição", "CFOPs", "Tipos de operação")),
                       ("Tipos de operação", ("Tipo de operação", "CFOPs")),
                       ("Bases (F27)", ("Código", "Descrição", "Fórmula sugerida", "% Redução", "Valor origem")),
                       ("Alíquotas (F28)", ("Código", "Descrição", "Tipo", "Valor")),
                       ("Alíquotas por NCM/UF", ("Tributo", "Chave usada", "NCM", "Origem", "UF origem", "UF destino",
                                                 "CEST", "Alíquota %", "MVA % / Alíq. inter %", "Itens")),
                       ("Escrituração (CJ2)", ("Código", "Tributo", "CSTCAB", "CST", "INCIDE", "Incidência", "STOTNF",
                                               "Ação na nota", "PERDIF", "cClassTrib", "CJ2_CCT", "Observação")),
                       ("Produtos", ("Produto", "Descrição", "NCM", "Origem", "CEST", "Itens", "Perfis de produto",
                                     "Classe IPI", "Classe PIS/COF")),
                       ("Clientes", ("CNPJ/CPF", "Nome", "UF", "Tipo no XML", "Notas"))]:
        fr = ttk.Frame(nb_cad)
        nb_cad.add(fr, text=nome)
        f, tv = nova_tabela(fr, cols)
        f.pack(fill="both", expand=True)
        tabs_cad[nome] = tv

    # ── aba Conflitos ───────────────────────────────────────────────────────
    ab_conf = ttk.Frame(nb)
    nb.add(ab_conf, text="Conflitos")
    ttk.Label(ab_conf, padding=6, text="Cenários em que o próprio XML traz tratamentos diferentes. A regra segue o "
              "majoritário; confira o minoritário pela chave de exemplo (pode ser erro do sistema anterior "
              "ou um critério que o XML não mostra).").pack(anchor="w")
    f, tv_conf = nova_tabela(ab_conf, ("Tributo", "Produto", "Participante", "CFOP | finalidade", "UF destino",
                                       "Tratamentos (itens)", "Exemplo do minoritário"),
                             (70, 120, 160, 200, 120, 520, 330))
    f.pack(fill="both", expand=True)

    # ── aba Padrão × XML ────────────────────────────────────────────────────
    ab_px = ttk.Frame(nb)
    nb.add(ab_px, text="Padrão × XML")
    ttk.Label(ab_px, padding=6, text="Regras de negócio do padrões_configurador.md aplicadas aos XMLs. "
              "O padrão prevalece; 'Divergências' são itens em que o XML fazia diferente.").pack(anchor="w")
    f, tv_px = nova_tabela(ab_px, ("Tributo", "Quando", "Então", "Observação", "Itens aplicados", "Divergências",
                                   "Exemplo de divergência", "Erro"), (70, 300, 110, 330, 100, 90, 330, 160))
    f.pack(fill="both", expand=True)

    # ── aba Padrões ─────────────────────────────────────────────────────────
    ab_pad = ttk.Frame(nb)
    nb.add(ab_pad, text="Padrões (.md)")
    bar = ttk.Frame(ab_pad, padding=4)
    bar.pack(fill="x")
    v_arq = tk.StringVar(value=ARQ_PADROES)
    ttk.Label(bar, textvariable=v_arq).pack(side="left")
    ttk.Button(bar, text="Recarregar padrões", command=lambda: recarregar()).pack(side="right")
    ttk.Button(bar, text="Abrir no editor", command=lambda: abrir_md()).pack(side="right", padx=4)
    f, txt_pad = caixa_texto(ab_pad)
    f.pack(fill="both", expand=True)

    # ── tarefas em segundo plano ────────────────────────────────────────────
    def rodar(func, fim):
        def w():
            try:
                q.put(("fim", fim, func()))
            except Exception as e:
                q.put(("erro", None, e))
        threading.Thread(target=w, daemon=True).start()

    def bomba():
        try:
            while True:
                tp, f_, v = q.get_nowait()
                if tp == "aviso":
                    v_st.set(v)
                elif tp == "erro":
                    v_st.set("Erro: " + str(v))
                    messagebox.showerror("Erro", str(v))
                else:
                    f_(v)
        except queue.Empty:
            pass
        root.after(100, bomba)

    avisar = lambda s: q.put(("aviso", None, s))

    def importar(tipo):
        if tipo == "pasta":
            p = filedialog.askdirectory()
            caminhos = [p] if p else []
        elif tipo == "zip":
            caminhos = list(filedialog.askopenfilenames(filetypes=[("ZIP", "*.zip")]))
        else:
            caminhos = list(filedialog.askopenfilenames(filetypes=[("XML", "*.xml")]))
        if not caminhos:
            return

        def trab():
            docs, canc = {}, set()
            for c in caminhos:
                d, k = ler_pasta(c, avisar)
                docs.update(d)
                canc |= k
            return docs, canc

        def fim(r):
            est["docs"].update(r[0])
            est["canc"] |= r[1]
            est["emit"] = emitentes(est["docs"], est["canc"])
            cb["values"] = [f"{c} · {n} · {x:,} notas".replace(",", ".") for c, n, x in est["emit"]]
            v_st.set(f"{len(est['docs']):,} NF-e na memória · {len(est['emit'])} CNPJ(s) emitente(s)".replace(",", "."))
            if est["emit"]:
                cb.current(0)
                gerar()
            else:
                messagebox.showinfo("Gerador", "Nenhuma NF-e de saída autorizada encontrada.")
        rodar(trab, fim)

    def gerar():
        if not est["emit"] or cb.current() < 0:
            return
        cnpj, agr, sep = est["emit"][cb.current()][0], v_agr.get(), v_sep.get()
        v_st.set("Gerando cenários…")

        def trab():
            an = analisar(est["docs"], est["canc"], cnpj, agr, avisar, sep)
            avisar("Montando regras e cadastros…")
            mt = montar_matriz(an)
            return an, mt, montar_cenarios(an, mt)

        def fim(r):
            est["an"], est["mt"], est["cen"] = r
            mostrar_tudo()
            v_st.set(f"Pronto: {len(est['mt']['regras'])} regras para {cnpj}. "
                     "Clique numa regra ou cenário para ver os detalhes.")
        rodar(trab, fim)

    def mostrar_tudo():
        an, mt = est["an"], est["mt"]
        escrever(txt_res, resumo_texto(an, mt))
        est["regras"] = {r["F2B_REGRA"]: r for r in mt["regras"]}
        cb_trib["values"] = ["Todos"] + sorted({r["F2B_TRIB"] for r in mt["regras"]},
                                               key=lambda x: [TRIBUTOS[k][0] for k in ORDEM_TRIB].index(x)
                                               if x in [TRIBUTOS[k][0] for k in ORDEM_TRIB] else 99)
        cb_trib.current(0)
        mostrar_regras()
        escrever(txt_reg, "Selecione uma regra para ver todos os campos e o que cada cadastro precisa ter.")
        # cenários
        tribs = [t for t in ORDEM_TRIB if t in an["regras_trib"]]
        tv_cen["columns"] = cols_cen + [TRIBUTOS[t][0] for t in tribs]
        for c in tv_cen["columns"]:
            tv_cen.heading(c, text=c, command=lambda c=c: ordenar(tv_cen, c, False))
            tv_cen.column(c, width={"Participante": 190, "Finalidade": 80, "Classe IBS/CBS": 110,
                                   "Classe PIS/COF": 95, "Classe IPI": 80}.get(c, 62), anchor="w", stretch=False)
        preencher(tv_cen, [list(c["k"][:5]) + [c["k"][5], c["k"][6], c["k"][7], c["itens"], len(c["notas"])]
                           + [c["regras"][t] or "—" for t in tribs] for c in est["cen"]])
        escrever(txt_cen, f"{len(est['cen'])} cenários. Selecione um para ver as regras que ele aciona em cada tributo.")
        # cadastros
        clientes = defaultdict(lambda: ["", "", "", 0])
        for d in an["validos"]:
            c = clientes[d["dest"] or "(consumidor)"]
            c[0], c[1], c[2] = d["dest_nome"], d["uf_dest"], d["tipo"] + (" SUFRAMA" if d["suframa"] else "")
            c[3] += 1
        qtd_prod = Counter(it["cprod"] for d in an["validos"] for it in d["itens"])
        perfis_do_prod = defaultdict(set)
        for cod, x in mt["perf_prod"].items():
            if x["_s"] is None:
                continue
            for k in x["_s"]:
                for pr in an["prod_keys"][x["_t"]].get(k, ()):
                    perfis_do_prod[pr].add(cod)
        preencher(tabs_cad["Perfis de produto"],
                  [[p["Código"], p["Descrição"], p["Família"], p["Classes"], p["Produtos"]]
                   for p in mt["perf_prod"].values()])
        part_qtd = Counter(v[2] for v in clientes.values())
        preencher(tabs_cad["Perfis de participante"],
                  [[p["Código"], p["Descrição"], p["Tipos"], p["Critério sugerido"],
                    sum(q for k, q in part_qtd.items() if p["_s"] is None or k in p["_s"])]
                   for p in mt["perf_part"].values()])
        preencher(tabs_cad["Origem/destino"], [[p["Código"], p["Descrição"], p["UF origem"], p["UFs destino"]]
                                               for p in mt["perf_od"].values()])
        preencher(tabs_cad["Perfis de operação"], [[p["Código"], p["Descrição"], p["CFOPs"], p["Tipos de operação"]]
                                                   for p in mt["perf_op"].values()])
        preencher(tabs_cad["Tipos de operação"], [[k, ", ".join(sorted(v))] for k, v in sorted(mt["tipos_op"].items())])
        preencher(tabs_cad["Bases (F27)"], [[b["Código"], b["Descrição"], b["Fórmula sugerida"], b["% Redução"], b["Valor origem"]]
                                            for b in mt["bases"].values()])
        preencher(tabs_cad["Alíquotas (F28)"], [[a["Código"], a["Descrição"], a["Tipo"], a["Valor"]]
                                                for a in mt["aliqs"].values()])
        preencher(tabs_cad["Alíquotas por NCM/UF"],
                  [[l["Tributo"], l["Chave usada"], l["NCM"], l["Origem"], l["UF origem"], l["UF destino"], l["CEST"],
                    l["Alíquota %"], l["MVA % / Alíq. interestadual %"], l["Itens"]] for l in mt["linhas_ncm"]])
        preencher(tabs_cad["Escrituração (CJ2)"],
                  [[e["Código"], e["Tributo"], e["CJ2_CSTCAB"], e["CJ2_CST"], e["CJ2_INCIDE"], e["Incidência"],
                    e["CJ2_STOTNF"], e["Ação na nota"], e["CJ2_PERDIF"], e["CJ2_CSTCCT (cClassTrib)"], e["CJ2_CCT"],
                    e["Observação"]]
                   for e in mt["escs"].values()])
        preencher(tabs_cad["Produtos"],
                  [[p, i[0], i[1], i[2], i[3], qtd_prod[p], ", ".join(sorted(perfis_do_prod.get(p, ()))),
                    an["modas"]["IPI"].get(p, ""), an["modas"]["PC"].get(p, "")]
                   for p, i in sorted(an["prod_info"].items(), key=lambda x: -qtd_prod[x[0]])])
        preencher(tabs_cad["Clientes"], [[k, v[0], v[1], v[2], v[3]]
                                         for k, v in sorted(clientes.items(), key=lambda x: -x[1][3])])
        # conflitos
        lin = []
        for t, b, cnt in an["conflitos"]:
            u = an["univ"][t]
            dims = [("todos" if b[i] == frozenset(u[i]) or b[i] == frozenset({"*"}) or b[i] == frozenset({"*§*"})
                     else ", ".join(sorted(x.replace("§", " | ") for x in b[i]))[:120]) for i in range(4)]
            menor = cnt.most_common()[-1][0]
            ex = next((an["exemplo"][(t, c, menor)] for c in an["regras_trib"][t][1]
                       if all(c[i] in b[i] for i in range(4)) and (t, c, menor) in an["exemplo"]), "")
            trat = " // ".join(
                f"{'AUSENTE' if tr is None else 'CST ' + tr[0][1] + ' ' + tr[1][0] + ' ' + ('NCM' if tr[2] == 'NCM' else _fmt(tr[3][0]) + '%')}: {qq}"
                for tr, qq in cnt.most_common())
            lin.append([TRIBUTOS[t][0]] + dims + [trat, ex])
        preencher(tv_conf, lin)
        preencher(tv_px, [[*st["regra"], st["aplicou"], st["divergiu"], st["exemplo"], st["erro"]]
                          for st in an["regras_negocio"]])

    def mostrar_regras():
        mt = est["mt"]
        if not mt:
            return
        trib, busca = cb_trib.get(), v_busca.get().strip().lower()
        linhas = []
        for r in mt["regras"]:
            if trib not in ("", "Todos") and r["F2B_TRIB"] != trib:
                continue
            vals = [r["F2B_REGRA"], r["F2B_TRIB"], r["F2B_DESC"], r["F2B_RBASE"], r["F2B_RALIQ"], r["F2B_PEROD"],
                    r["F2B_PERFPA"], r["F2B_PERFOP"], r["F2B_PERFPR"], r["F2B_CODESC"], r["cBenef"], r["Itens"]]
            if busca and busca not in " ".join(map(str, vals)).lower() + r["CFOPs"].lower():
                continue
            linhas.append(vals)
        preencher(tv_reg, linhas)

    def selecionar_regra(tv):
        sel = tv.selection()
        if sel:
            r = est["regras"].get(tv.set(sel[0], "Regra"))
            if r:
                escrever(txt_reg, detalhe_regra(r, est["mt"]))

    def selecionar_cenario(tv):
        sel = tv.selection()
        if not sel:
            return
        idx = tv.index(sel[0])
        vals = tv.item(sel[0], "values")
        c = next((x for x in est["cen"] if list(map(str, x["k"][:3])) == list(vals[:3])
                  and x["k"][3] == vals[3] and x["k"][4] == vals[4] and x["k"][5] == vals[5]
                  and x["k"][6] == vals[6] and x["k"][7] == vals[7]), None)
        if not c:
            return
        L = [f"CENÁRIO: CFOP {c['k'][0]} · {c['k'][1]} · UF {c['k'][2]} · {c['k'][3]} · origem {c['k'][4]} · "
             f"{c['k'][5]} · {c['k'][6]} · {c['k'][7]}",
             f"{c['itens']} itens em {len(c['notas'])} notas · exemplo: {c['exemplo']}", "", "REGRAS ACIONADAS:"]
        for t in ORDEM_TRIB:
            cod = c["regras"].get(t)
            if cod:
                r = est["regras"].get(cod, {})
                L.append(f"  {TRIBUTOS[t][1]:<11} {cod:<7} {r.get('F2B_DESC', '')}")
                L.append(f"  {'':<11} base {r.get('F2B_RBASE', '')} · alíq {r.get('F2B_RALIQ', '')} · "
                         f"escrit. {r.get('F2B_CODESC', '')} · perfis {r.get('F2B_PERFPR', '')}/"
                         f"{r.get('F2B_PERFPA', '')}/{r.get('F2B_PEROD', '')}/{r.get('F2B_PERFOP', '')}")
        escrever(txt_cen, "\n".join(L))

    def copiar(todas):
        mt = est["mt"]
        if not mt:
            return
        if todas:
            txt = ";".join(COLS_F2B) + "\n" + "\n".join(linha_csv_f2b(r) for r in mt["regras"])
        else:
            sel = tv_reg.selection()
            if not sel:
                return
            txt = linha_csv_f2b(est["regras"][tv_reg.set(sel[0], "Regra")])
        root.clipboard_clear()
        root.clipboard_append(txt)
        v_st.set("Copiado para a área de transferência.")

    def exportar():
        mt = est["mt"]
        if not mt:
            return
        p = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=f"F2B_{est['an']['cnpj']}.csv",
                                         filetypes=[("CSV", "*.csv")])
        if not p:
            return
        try:
            with open(p, "w", newline="", encoding="utf-8-sig") as f:
                f.write(";".join(COLS_F2B) + "\r\n")
                for r in mt["regras"]:
                    f.write(linha_csv_f2b(r) + "\r\n")
            v_st.set(f"Exportado: {p}")
        except OSError as e:
            messagebox.showerror("Exportar", f"Não consegui gravar ({e}). Escolha uma pasta fora do OneDrive/Área de Trabalho.")

    def limpar():
        est.update(docs={}, canc=set(), emit=[], an=None, mt=None, cen=[], regras={})
        cb["values"] = []
        cb.set("")
        for tv in [tv_reg, tv_cen, tv_conf, tv_px] + list(tabs_cad.values()):
            tv.delete(*tv.get_children())
        for t in (txt_res, txt_reg, txt_cen):
            escrever(t, "")
        v_st.set("Memória limpa. Importe os XMLs.")

    def recarregar():
        texto, avisos = carregar_padroes()
        escrever(txt_pad, texto)
        v_agr.set(OPCOES["AGRUPAR_MAXIMO"])
        v_sep.set(OPCOES["SEPARAR_PARTICIPANTE"])
        v_st.set("Padrões recarregados." + (" " + " | ".join(avisos) if avisos else ""))
        if est["emit"]:
            gerar()

    def abrir_md():
        try:
            os.startfile(ARQ_PADROES)
        except AttributeError:
            import subprocess
            subprocess.Popen(["xdg-open" if sys.platform.startswith("linux") else "open", ARQ_PADROES])
        except OSError as e:
            messagebox.showerror("Padrões", str(e))

    texto, avisos = carregar_padroes()
    escrever(txt_pad, texto)
    v_agr.set(OPCOES["AGRUPAR_MAXIMO"])
    v_sep.set(OPCOES["SEPARAR_PARTICIPANTE"])
    if avisos:
        v_st.set(" | ".join(avisos))
    escrever(txt_res, "1) Importe os XMLs de SAÍDA (pasta, ZIP ou arquivos).\n"
                      "2) Escolha o CNPJ emitente.\n"
                      "3) O programa gera na hora os cenários, as regras F2B e os cadastros necessários.\n\n"
                      "Os padrões de códigos ficam no arquivo padroes_configurador.md (aba 'Padrões').")
    bomba()
    root.mainloop()


if __name__ == "__main__":
    tela()
