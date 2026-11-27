# -*- coding: utf-8 -*-
"""
app.py — Facilitador Fiscal (versão Streamlit)
==============================================
Interface Streamlit sobre o motor (gerador_cenarios.py), que não é alterado aqui.

    python -m streamlit run app.py

Fluxo em 5 passos (na ordem da tela):
  1. Importar XMLs de saída
  2. Regime dos clientes (planilha com CNPJ, inscrição e regime)
  3. Empresa e opções
  4. Gerar cenários
  5. Conferir resultados (abas)
"""
import csv
from collections import Counter
import json
import io
import os
import re
import unicodedata
import zipfile

import pandas as pd
import streamlit as st

import gerador_cenarios as g

AQUI = os.path.dirname(os.path.abspath(__file__))
ARQ_REGIME = os.path.join(AQUI, "regime_clientes.csv")

# mesmos conjuntos de palavras que o servidor web usa para interpretar o regime
_SIMPLES = {"S", "SIM", "1", "X", "TRUE", "VERDADEIRO", "SIMPLES", "SIMPLES NACIONAL", "OPTANTE", "ME", "EPP", "MEI",
            "OPTANTE PELO SIMPLES", "SN"}
_NORMAL = {"N", "NAO", "NÃO", "2", "0", "FALSE", "FALSO", "NORMAL", "REGIME NORMAL", "LUCRO REAL", "LUCRO PRESUMIDO",
           "NAO OPTANTE", "NÃO OPTANTE", "RN"}

st.set_page_config(page_title="Gerador de Regras Fiscais", layout="wide", initial_sidebar_state="collapsed")

def _css():
    """Paleta do PsIntegra: painel escuro à esquerda (passos), conteúdo claro à direita.
    Laranja = atenção/confirmação, verde = concluído, azul = destaque, vermelho = ação crítica."""
    return """
<style>
.stApp { background:#f4f6f8; color:#263238; }
.block-container { max-width:100% !important; padding:3.2rem 1rem 1.5rem 1rem !important; }
h1, h2, h3 { color:#1f2a33 !important; }
[data-testid="column"]:first-child { background:#1f2328; border-radius:12px; padding:7px 6px; max-width:360px; }
[data-testid="column"]:first-child * { color:#e8ecf0; }
[data-testid="column"]:first-child .sub, [data-testid="column"]:first-child small { color:#aab4be !important; }
[data-testid="column"]:first-child [data-testid="stExpander"] { background:#2a2f36; border-color:#3a414b; }
[data-testid="column"]:first-child [data-testid="stFileUploaderDropzone"] { background:#2a2f36; border-color:#3a414b; }
.passo { display:flex; align-items:center; gap:6px; padding:6px 7px; border:1px solid #3a414b;
         border-radius:8px; margin:4px 0; background:#2a2f36; }
.passo .bolinha { min-width:32px; height:32px; border-radius:50%; background:#2e7d32; color:#ffffff;
                  display:flex; align-items:center; justify-content:center; font-weight:700; }
.passo.pendente .bolinha { background:#6b7580; color:#ffffff; }
.passo .titulo { font-weight:600; font-size:.98rem; color:#e8ecf0; }
.passo .sub { font-size:.8rem; color:#aab4be; }
.passo .direita { margin-left:auto; font-size:.8rem; color:#ffb74d; text-align:right; font-weight:600; }
.passo.pendente .direita { color:#aab4be; }
[data-testid="stMetric"] { background:#ffffff; border:1px solid #dfe4ea; border-radius:10px; padding:12px 14px; }
[data-testid="stMetricValue"] { color:#1565c0 !important; }
.stButton > button { border-radius:6px; }
.stButton > button[kind="primary"] { background:#d32f2f; border:none; color:#ffffff; }
.stButton > button[kind="primary"]:hover { background:#b71c1c; }
.st-key-btn_desconsiderar button { background:#f57c00 !important; border:none !important; color:#ffffff !important; font-weight:600; }
.st-key-btn_desconsiderar button:hover { background:#e65100 !important; }
.stTabs [aria-selected="true"] { color:#1565c0 !important; }
</style>
"""
st.markdown(_css(), unsafe_allow_html=True)


# ── utilidades ────────────────────────────────────────────────────────────────
def _sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _so_digitos(s):
    return re.sub(r"\D", "", str(s or ""))


def _regime_norm(valor):
    """Converte o texto da planilha em SIMPLES, NORMAL ou None (não reconhecido)."""
    u = _sem_acento(str(valor or "").strip().upper())
    if not u:
        return None
    if u in {_sem_acento(x) for x in _SIMPLES} or u.startswith("SIMPLES") or u.startswith("OPTANTE"):
        return "SIMPLES"
    if u in {_sem_acento(x) for x in _NORMAL}:
        return "NORMAL"
    return None


def _ler_regime_texto(texto):
    """Lê o regime (CNPJ;REGIME;IE) de um texto CSV. Devolve (dados, ies)."""
    dados, ies = {}, {}
    for linha in csv.reader(io.StringIO(texto), delimiter=";"):
        if len(linha) >= 2 and linha[0].isdigit():
            dados[linha[0]] = linha[1]
            if len(linha) >= 3 and linha[2].strip():
                ies[linha[0]] = linha[2]
    return dados, ies


def _texto_regime(dados, ies):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["CNPJ", "REGIME", "IE"])
    for cnpj in sorted(dados):
        w.writerow([cnpj, dados[cnpj], ies.get(cnpj, "")])
    return buf.getvalue()


def _ler_planilha(arquivo):
    """Lê XLSX ou CSV e devolve DataFrame de texto. Procura as colunas CNPJ, IE e REGIME."""
    nome = arquivo.name.lower()
    conteudo = arquivo.getvalue()
    if nome.endswith(".xlsx") or nome.endswith(".xls"):
        df = pd.read_excel(io.BytesIO(conteudo), dtype=str)
    else:
        for sep in (";", ",", "\t"):
            try:
                df = pd.read_csv(io.BytesIO(conteudo), dtype=str, sep=sep, encoding="utf-8-sig")
                if df.shape[1] >= 2:
                    break
            except Exception:
                continue
    df.columns = [_sem_acento(str(c)).strip().upper() for c in df.columns]
    return df


def _achar_coluna(df, opcoes):
    for c in df.columns:
        if any(o in c for o in opcoes):
            return c
    return None


# Colunas do cadastro de clientes (SA1) exigidas quando há perfis próprios de ST/DIFAL ST
CAMPOS_SA1 = {"GRPTRIB": ["GRPTRIB", "GRUPO TRIB", "GRUPO DE TRIB", "GRUPO TRIBUT"],
              "CONTRIB": ["CONTRIB", "A1_CONTRIB"],
              "PESSOA": ["PESSOA", "A1_PESSOA", "TIPO PESSOA"],
              "SIMPNAC": ["SIMPNAC", "A1_SIMPNAC"],
              "EST": ["EST", "A1_EST", "UF"],
              "SUFRAMA": ["SUFRAMA", "A1_SUFRAMA"]}


def _coluna_sa1(df, nomes):
    """Coluna cujo cabeçalho é exatamente um dos nomes (evita pegar 'CONTRIBUINTE' por 'CONTRIB' por engano)."""
    for c in df.columns:
        if _sem_acento(str(c)).strip().upper() in nomes:
            return c
    return None


def _importar_regime(arquivo, progresso=None):
    """Atualiza o dicionário do motor e grava regime_clientes.csv e cadastro_sa1.csv.
    Devolve (aceitos, recusados, colunas_sa1_faltando)."""
    df = _ler_planilha(arquivo)
    col_cnpj = _achar_coluna(df, ["CNPJ", "CPF"])
    col_reg = _achar_coluna(df, ["REGIME", "SIMPLES", "SIMPNAC", "OPTANTE", "CRT"])
    col_ie = _achar_coluna(df, ["INSCRI", "IE"])
    if not col_cnpj or not col_reg:
        raise ValueError("Não encontrei as colunas CNPJ e REGIME. Use cabeçalhos como 'CNPJ', 'INSCRIÇÃO' e 'REGIME'.")
    cols_sa1 = {k: _coluna_sa1(df, [_sem_acento(n).upper() for n in nomes]) for k, nomes in CAMPOS_SA1.items()}
    faltam = [k for k, c in cols_sa1.items() if c is None]
    dados, ies = dict(st.session_state.get("regime", {})), dict(st.session_state.get("regime_ie", {}))
    sa1 = dict(st.session_state.get("sa1", {}))
    aceitos, recusados = 0, []
    total = len(df) or 1
    for k, (_, linha) in enumerate(df.iterrows(), 1):
        if progresso is not None and (k % 50 == 0 or k == total):
            _barra(progresso, (k / total, f"Lendo planilha: {k:,} de {total:,} linhas ({k / total:.0%})".replace(",", ".")))
        cnpj = _so_digitos(linha[col_cnpj])
        if not cnpj:
            continue
        reg = _regime_norm(linha[col_reg])
        if reg is None:
            recusados.append(f"{cnpj}: regime '{linha[col_reg]}' não reconhecido")
            continue
        dados[cnpj] = reg
        if col_ie and pd.notna(linha[col_ie]):
            ies[cnpj] = str(linha[col_ie]).strip()
        sa1[cnpj] = {campo: (str(linha[c]).strip() if c is not None and pd.notna(linha[c]) else "")
                     for campo, c in cols_sa1.items()}
        aceitos += 1
    st.session_state["regime"], st.session_state["regime_ie"], st.session_state["sa1"] = dados, ies, sa1
    _aplicar_dados_sessao()
    return aceitos, recusados, faltam


def _ler_sa1_texto(texto):
    dados = {}
    leitor = csv.reader(io.StringIO(texto), delimiter=";")
    cab = next(leitor, [])
    for linha in leitor:
        if linha and linha[0].isdigit():
            dados[linha[0]] = dict(zip(cab[1:], linha[1:]))
    return dados


def _texto_sa1(sa1):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["CNPJ"] + list(CAMPOS_SA1))
    for cnpj in sorted(sa1):
        w.writerow([cnpj] + [sa1[cnpj].get(k, "") for k in CAMPOS_SA1])
    return buf.getvalue()


def _aplicar_dados_sessao():
    """Coloca no motor só os cadastros desta sessão (cada usuário tem os seus)."""
    g.REGIME_CLIENTE.clear()
    g.REGIME_CLIENTE.update(st.session_state.get("regime", {}))
    g.CADASTRO_SA1.clear()
    g.CADASTRO_SA1.update(st.session_state.get("sa1", {}))
    g.CORRECOES.clear()
    g.CORRECOES.extend(st.session_state.get("correcoes", []))


@st.cache_resource(show_spinner=False)
def _inicializar_motor():
    """Carrega só os padrões GF (uma vez por servidor). Cadastros de cliente ficam na sessão."""
    _, avisos = g.carregar_padroes()
    return avisos


def _init_state():
    padroes = {
        "docs": {}, "canc": set(), "fonte": {}, "emit": [],
        "an": None, "mt": None, "cen": [], "cnpj": None,
        "stats": {"nfe": 0, "repetidas": 0, "cancelamentos": 0, "ignorados": 0, "erros": 0},
        "gerado_em": None,
    }
    for k, v in padroes.items():
        st.session_state.setdefault(k, v)


def _registrar(dados, fonte):
    tp, val = g.ler_xml_bytes(dados)
    stats = st.session_state["stats"]
    if tp == "nfe" and val.get("chave"):
        stats["repetidas" if val["chave"] in st.session_state["docs"] else "nfe"] += 1
        st.session_state["docs"][val["chave"]] = val
        st.session_state["fonte"][val["chave"]] = fonte
    elif tp == "canc":
        st.session_state["canc"].add(val)
        stats["cancelamentos"] += 1
    else:
        stats["ignorados"] += 1


def _barra(progresso, texto):
    """Mostra o percentual concluído na barra e no texto."""
    progresso.progress(min(max(texto[0], 0.0), 1.0), text=texto[1])


def _importar_uploads(arquivos, progresso=None):
    # total de XMLs (ZIP conta cada XML dentro dele)
    entradas = []
    for arq in arquivos:
        if arq.name.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(arq.getvalue())) as z:
                entradas += [(arq, n) for n in z.namelist() if n.lower().endswith(".xml")]
        else:
            entradas.append((arq, None))
    total = len(entradas) or 1
    feitos, lidos_n = 0, 0
    zips = {}
    for arq, nome_xml in entradas:
        try:
            if nome_xml is None:
                _registrar(arq.getvalue(), (arq.name, None))
            else:
                if arq.name not in zips:
                    zips[arq.name] = zipfile.ZipFile(io.BytesIO(arq.getvalue()))
                _registrar(zips[arq.name].read(nome_xml), (nome_xml, arq.name))
        except Exception:
            st.session_state["stats"]["erros"] += 1
        feitos += 1
        lidos_n += 1
        if progresso is not None and (feitos % 50 == 0 or feitos == total):
            _barra(progresso, (feitos / total, f"Lendo XMLs: {feitos:,} de {total:,} ({feitos / total:.0%})"
                               .replace(",", ".")))
    for z in zips.values():
        z.close()
    st.session_state["emit"] = g.emitentes(st.session_state["docs"], st.session_state["canc"])
    return lidos_n


def _importar_pasta(caminho, progresso=None):
    lista = list(g._listar(caminho))
    total = len(lista) or 1
    zf, zn = None, None
    try:
        for k, (nm, z) in enumerate(lista, 1):
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
                _registrar(dados, (nm, z))
            except Exception:
                st.session_state["stats"]["erros"] += 1
            if progresso is not None and (k % 200 == 0 or k == total):
                _barra(progresso, (k / total, f"Lendo arquivos: {k:,} de {total:,} ({k / total:.0%})"
                                   .replace(",", ".")))
    finally:
        if zf:
            zf.close()
    st.session_state["emit"] = g.emitentes(st.session_state["docs"], st.session_state["canc"])
    return len(lista)


def _ler_desconsiderados():
    return list(st.session_state.get("desconsiderados", []))


def _cnpjs_desconsiderados():
    # só vale para quem continua SEM regime: quem já tem regime nunca fica de fora
    return {r["cnpj"] for r in _ler_desconsiderados() if r["cnpj"] not in g.REGIME_CLIENTE}


def _clientes_pj():
    """Destinatários PJ dos XMLs importados (CNPJ -> nome), para cobrar o regime."""
    clientes = {}
    for d in st.session_state["docs"].values():
        if str(d.get("tipo", "")).startswith("PJ") and d.get("dest"):
            clientes.setdefault(d["dest"], d.get("dest_nome", ""))
    return clientes


def _gerar(cnpj, agrupar, separar, ufs=None, dp=None):
    """Gera os cenários mostrando o andamento: análise por tributo, montagem das regras e cenários."""
    barra = st.progress(0.0, text="Analisando cenários: 0%")
    tributos_total = max(len(g.ORDEM_TRIB), 1)
    estado = {"tributos": 0}

    def avisar(msg):
        # o motor avisa cada tributo que agrupa; a análise ocupa 0% a 80% da barra
        if msg.startswith("Agrupando regras"):
            estado["tributos"] += 1
            p = min(estado["tributos"] / tributos_total, 1.0) * 0.8
            barra.progress(p, text=f"Analisando cenários: {p / 0.8:.0%} ({msg[len('Agrupando regras de '):-1]})")

    desc = _cnpjs_desconsiderados()
    docs_ok = {k: d for k, d in st.session_state["docs"].items() if d.get("dest") not in desc}
    if ufs:
        docs_ok = {k: d for k, d in docs_ok.items() if d.get("uf_dest") in ufs}
    cfops_ok = st.session_state.get("cfops_sel")
    agregar = st.session_state.get("cfops_agregar") or set()
    todos = {it.get("cfop") for d in docs_ok.values() for it in d.get("itens", [])}
    if cfops_ok is not None:
        novos = {}
        for k, d in docs_ok.items():
            itens_ok = [it for it in d.get("itens", []) if it.get("cfop") in cfops_ok]
            if itens_ok:
                novos[k] = dict(d, itens=itens_ok)
        docs_ok = novos
        g.CFOPS_AGREGAR.clear(); g.CFOPS_AGREGAR.update(agregar & set(cfops_ok))
        g.CFOPS_SEPARAR.clear(); g.CFOPS_SEPARAR.update(set(cfops_ok) - agregar)
    else:
        g.CFOPS_AGREGAR.clear(); g.CFOPS_SEPARAR.clear()
    cli = st.session_state.get("dp_cli_df")
    if cli is not None:
        g.FINALIDADE_CLIENTE.clear()
        for _, linha in cli.iterrows():
            doc = "".join(ch for ch in str(linha["CNPJ"]) if ch.isdigit())
            if doc and str(linha["Finalidade"]).strip():
                g.FINALIDADE_CLIENTE[doc] = str(linha["Finalidade"]).strip().upper()
    if dp is not None:
        insumo = g.TIPOS_OPERACAO.get("INSUMO", ("V5", "Revenda para insumo"))   # específico por cliente
        g.TIPOS_OPERACAO.clear()
        for _, linha in dp.iterrows():
            fin_k = str(linha["Finalidade"]).strip().upper()
            if fin_k and str(linha["Tipo de operação"]).strip():
                g.TIPOS_OPERACAO[fin_k] = (str(linha["Tipo de operação"]).strip(), str(linha.get("Descrição", "")).strip())
        g.TIPOS_OPERACAO.setdefault("INSUMO", insumo)
    an = g.analisar(docs_ok, st.session_state["canc"], cnpj, agrupar, avisar, separar, None)
    barra.progress(0.85, text="Montando regras e cadastros: 85%")
    mt = g.montar_matriz(an)
    barra.progress(0.95, text="Organizando cenários: 95%")
    cen = g.montar_cenarios(an, mt)
    barra.progress(1.0, text="Concluído: 100%")
    st.session_state.update(an=an, mt=mt, cen=cen, cnpj=cnpj,
                            gerado_em=pd.Timestamp.now().strftime("%d/%m/%Y %H:%M"))


def _tabela_dict(d):
    if not d:
        return pd.DataFrame()
    df = pd.DataFrame.from_dict(d, orient="index")
    df.index.name = "Código"
    return df


def _regras_df(mt):
    colunas = ["F2B_REGRA", "F2B_DESC", "F2B_TRIB", "F2B_RBASE", "F2B_RALIQ", "F2B_PEROD",
               "F2B_PERFPA", "F2B_PERFOP", "F2B_PERFPR", "F2B_CODESC", "cBenef", "Itens", "CFOPs", "UFs",
               "PAI", "GRUPO_DERIVADO", "_status"]
    linhas = [{c: r.get(c, "") for c in colunas} for r in mt["regras"]]
    return pd.DataFrame(linhas, columns=colunas).rename(columns={"_status": "Status"})


DIMS_CEN = {"CFOP / operação": 0, "Finalidade": 1, "UF destino": 2, "Participante": 3,
            "Origem / grupo do produto": 4, "Classe IPI": 5, "Classe PIS/COFINS": 6, "Classe IBS": 7,
            "Classe ICMS": 8}
DIMENSOES_SEPARAR = {
    "Origem/destino (UF)": "origem_destino",
    "Participante (cliente)": "participante",
    "Produto": "produto",
    "Perfil de operação (CFOP)": "operacao",
    "Tipo de operação (finalidade)": "tipo_operacao",
}


TRIB_NOME = {"ICMS": "ICMS", "ICMSST": "ICMS ST", "DIFAL": "DIFAL", "FECP": "FECP", "FECPST": "FECP ST",
             "FECPDF": "FCP DIFAL", "FCPCMP": "FCP da compra", "IPI": "IPI", "PIS": "PIS", "COF": "COFINS",
             "IBSEST": "IBS estadual", "IBSMUN": "IBS municipal", "CBSFED": "CBS federal"}
CST_TXT = {("ICMS", "00"): "tributada integralmente", ("ICMS", "10"): "tributada com ST",
           ("ICMS", "20"): "com redução de base", ("ICMS", "30"): "isenta com ST", ("ICMS", "40"): "isenta",
           ("ICMS", "41"): "não tributada", ("ICMS", "50"): "com suspensão", ("ICMS", "51"): "com diferimento",
           ("ICMS", "60"): "ST já cobrado antes", ("ICMS", "70"): "redução com ST", ("ICMS", "90"): "outras",
           ("IBS", "000"): "tributação integral", ("IPI", "50"): "saída tributada", ("IPI", "99"): "outras saídas",
           ("PIS", "01"): "operação tributável", ("COF", "01"): "operação tributável"}
INCIDE_TXT = {"1": "tem imposto neste item", "3": "sem imposto neste item"}
STOT_TXT = {"1": "entra no total da nota", "3": "sai do total da nota"}
MODO_TXT = {"F": "alíquota fixa", "NCM": "alíquota pela tabela de NCM", "ITEM": "alíquota por item"}
TOKENS_BASE = [("O:VAL_MERCADORIA", "mercadoria"), ("O:FRETE", "frete"), ("O:SEGURO", "seguro"),
               ("O:DESPESAS", "despesas"), ("O:DESCONTO", "desconto"), ("O:VAL_II", "II"), ("O:VAL_PS2", "PIS"),
               ("O:VAL_CF2", "COFINS"), ("O:VAL_ICM_TRIBUTADO", "ICMS"), ("O:VAL_DIFAL", "DIFAL"),
               ("O:VAL_FECPDIF", "FCP DIFAL"), ("O:VAL_FCPDIF", "FCP DIFAL"), ("O:VAL_FECP", "FECP")]
SEM_VALOR = ("*", "•", "")


def _traduz_formula(f):
    for k, v in sorted(TOKENS_BASE, key=lambda kv: -len(kv[0])):
        f = f.replace(k, v)
    return f.replace("O:", "")


def _txt_escrituracao(esc, tributo):
    """Escrituração em frases: CST, incidência, total da nota, diferimento e classe tributária."""
    cab, cst, incide, stot, dif, cls = (list(esc) + [""] * 6)[:6]
    familia = "IBS" if tributo.startswith(("IBS", "CBS")) else tributo
    partes = []
    if cst:
        nome = CST_TXT.get((familia, cst))
        partes.append(f"CST {cst}" + (f" ({nome})" if nome else ""))
    if incide:
        partes.append(INCIDE_TXT.get(str(incide), f"incidência código {incide}"))
    if stot:
        partes.append(STOT_TXT.get(str(stot), f"total código {stot}"))
    if dif:
        partes.append(f"diferimento de {dif}%")
    if cls:
        partes.append(f"classe tributária {cls}")
    return " · ".join(partes) or "—"


def _txt_base(base):
    cod, desc, form = (list(base) + ["", "", ""])[:3]
    if cod == "BASZER":
        return "base zero"
    f = _traduz_formula(form) if form else ""
    return f"{desc} · base = {f}" if f else (desc or "—")


def _txt_aliquota(al):
    try:
        return f"{float(al[0]) if al else 0.0:.2f}%".replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def _txt_produto(prod):
    s = str(prod)
    if ":" not in s:
        return s
    trib, _, resto = s.partition("|")
    nome, _, cst = trib.partition(":")
    texto = TRIB_NOME.get(nome, nome)
    if cst.startswith("CST"):
        texto += f" · CST {cst[3:]}"
    formula = next((x for x in resto.split("|") if x.startswith("O:")), "")
    if formula:
        texto += f" · base = {_traduz_formula(formula)}"
    if "§" in s:
        marca = s.rsplit("§", 1)[1]
        texto += " · qualquer origem" if marca in ("*", "") else f" · código {marca}"
    return texto


def _txt_cliente(part):
    return "qualquer cliente" if str(part) in SEM_VALOR else str(part)


def _txt_operacao(op):
    s = str(op)
    if s in SEM_VALOR:
        return "qualquer operação"
    codigo, _, fin = s.partition("|")
    return f"operação {codigo}" + (f" ({fin.lower()})" if fin else "")


def _txt_uf(uf):
    return "qualquer UF" if str(uf) in SEM_VALOR else str(uf)


def _descreve_coords(c):
    """(produto, participante, operação, UF) -> textos para o usuário."""
    prod, part, op, uf = c
    return {"Produto": _txt_produto(prod), "Cliente": _txt_cliente(part), "Operação": _txt_operacao(op),
            "UF de destino": _txt_uf(uf)}


def _descreve_trat(trat, tributo=""):
    """Tratamento que o XML trouxe, em frases: escrituração, base, tipo e valor da alíquota, cBenef."""
    esc, base, modo, al, cbenef = trat[0], trat[1], trat[2], trat[3], trat[4]
    return {"Escrituração": _txt_escrituracao(esc, tributo), "Base de cálculo": _txt_base(base),
            "Tipo de alíquota": MODO_TXT.get(str(modo), str(modo)), "Alíquota no XML": _txt_aliquota(al),
            "Benefício fiscal (cBenef)": str(cbenef) if cbenef else "nenhum"}


def _ler_decisoes():
    return list(st.session_state.get("decisoes", []))


def _limpa_celula(v):
    """Valores para a planilha: texto para listas/dicts, vazio para nulos."""
    if v is None or (isinstance(v, float) and v != v):
        return ""
    if isinstance(v, (list, tuple, set, frozenset, dict)):
        return str(v)
    return v


def _xlsx_completo(mt, cen):
    """Exporta tudo que a tela mostra em um XLSX com várias abas."""
    abas = {}
    pend = mt.get("pendencias", []) or []
    abas["Visão geral"] = pd.DataFrame(
        [("Notas analisadas", mt.get("notas", 0)), ("Itens", mt.get("itens", 0)),
         ("Regras F2B a cadastrar", len(mt["regras"])), ("Cenários pendentes", len(pend))],
        columns=["Indicador", "Valor"])
    abas["Regras F2B"] = _regras_df(mt).apply(lambda c: c.map(_limpa_celula))
    cenarios = []
    for c in cen or []:
        linha = {d: str(c["k"][i]) for d, i in DIMS_CEN.items()}
        linha.update({"Itens": c["itens"], "Notas": len(c["notas"]), "Nota exemplo": c["exemplo"]})
        for t in sorted(c["regras"]):
            linha[f"Regra {t}"] = " / ".join(sorted(c["regras"][t]))
        cenarios.append(linha)
    abas["Cenários"] = pd.DataFrame(cenarios).apply(lambda c: c.map(_limpa_celula)) if cenarios else pd.DataFrame()
    for nome, chave in [("Perfis de produto", "perf_prod"), ("Perfis de participante", "perf_part"),
                        ("Perfis de origem-destino", "perf_od"), ("Perfis de operação", "perf_op"),
                        ("Bases (F27)", "bases"), ("Alíquotas (F28)", "aliqs"),
                        ("Escriturações (CJ2)", "escs"), ("Tipos de operação", "tipos_op")]:
        df = _tabela_dict(mt.get(chave, {}))
        if not df.empty:
            # o índice vira coluna; se já existe coluna "Código" nos valores, o índice recebe outro nome
            df.index.name = "Chave" if "Código" in df.columns else "Código"
            abas[nome] = df.reset_index().apply(lambda c: c.map(_limpa_celula))
    abas["Validações"] = pd.DataFrame(list((mt.get("validacao") or {}).items()), columns=["Situação", "Itens"])
    if pend:
        abas["Pendências"] = pd.DataFrame(pend).apply(lambda c: c.map(_limpa_celula))
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for nome, df in abas.items():
            df.to_excel(w, sheet_name=nome[:31], index=False)
    return buf.getvalue()


def _alertas_ipi_icms(an):
    """Regra para confirmar: IPI entra na base do ICMS só na finalidade CONSUMO; fora dela, não tem IPI."""
    from collections import Counter
    cont, exemplo = Counter(), {}
    for d, it, tr in an.get("linhas", []):
        if "ICMS" not in tr:
            continue
        base_cod = str(tr["ICMS"][1][0])
        tem_ipi = base_cod.startswith(("ICMP", "ICP"))
        fin = g._fin(d, it)
        if fin == "CONSUMO" and not tem_ipi:
            problema = "consumo sem IPI na base"
        elif fin != "CONSUMO" and tem_ipi:
            problema = "IPI na base fora do consumo"
        else:
            continue
        chave = (problema, fin, base_cod, it["cfop"])
        cont[chave] += 1
        exemplo.setdefault(chave, d["chave"])
    return [{"Situação": k[0], "Finalidade": k[1], "Base do ICMS": k[2], "CFOP": k[3], "Itens": v,
             "Nota exemplo": exemplo[k]} for k, v in cont.most_common()]


def _pendencias_ipi(an):
    """Casos de ICMS fora da regra do IPI, no mesmo formato das pendências de cenário."""
    grupos = {}
    for d, it, tr in an.get("linhas", []):
        if "ICMS" not in tr:
            continue
        esc, base, al, cb = tr["ICMS"]
        base_cod = str(base[0])
        tem_ipi = base_cod.startswith(("ICMP", "ICP"))
        fin = g._fin(d, it)
        if fin == "CONSUMO" and not tem_ipi:
            problema = "consumo sem IPI na base"
        elif fin != "CONSUMO" and tem_ipi:
            problema = "IPI na base fora do consumo"
        else:
            continue
        chave = (problema, fin, base_cod, it["cfop"])
        if chave not in grupos:
            grupos[chave] = {"tributo": "ICMS", "tipo": "regra_ipi", "regra": "", "qtd": 0,
                             "exemplo": d["chave"], "coords": ("—", "—", f"{it['cfop']}|{fin}", "—"),
                             "trat": (esc, base, "F", al, cb, ""), "problema": problema}
        grupos[chave]["qtd"] += 1
    return list(grupos.values())


def _tela_regra_ipi():
    an = st.session_state.get("an")
    if not an:
        return
    alertas = _alertas_ipi_icms(an)
    st.markdown("### Confirmação da regra do IPI no ICMS")
    st.caption("Regra: o IPI entra na base do ICMS só quando a finalidade é CONSUMO. Fora do consumo, a base não tem IPI. "
               "Abaixo, os itens que não seguem essa regra. Nada muda nas regras até você confirmar.")
    if not alertas:
        st.success("Todos os itens de ICMS seguem a regra do IPI.")
        return
    st.checkbox("Confirmo a regra do IPI na base do ICMS (IPI só para consumo)", key="conf_regra_ipi")


def _tela_pendencias(mt):
    pend = list(mt.get("pendencias", []) or []) + _pendencias_ipi(st.session_state.get("an") or {})
    if not pend:
        st.success("Nenhum cenário pendente: todos os itens do XML acionam exatamente uma regra.")
        return
    st.info(f"{len(pend)} cenário(s) do XML sem regra certa. Responda para cada um se o XML está certo "
            "ou se é um cenário novo. Nada muda nas regras até você aprovar.")

    linhas = []
    for i, p in enumerate(pend):
        rot = {"Tributo": p["tributo"], "Situação": ("sem regra" if p["tipo"] == "sem_regra"
                                                     else ("regra do IPI não segue a regra" if p["tipo"] == "regra_ipi" else f"regra {p['regra']} não bate")),
               "Itens": p["qtd"], "Nota exemplo": p["exemplo"]}
        rot.update(_descreve_coords(p["coords"]))
        linhas.append({"#": i, **rot})
    ev = st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True, height=420,
                      on_select="rerun", selection_mode="single-row", key="tab_pendencias")
    # clicar numa linha seleciona esse cenário para análise
    marcados = ev.selection.rows if ev and getattr(ev, "selection", None) else []
    if marcados and st.session_state.get("pend_sel") != marcados[0]:
        st.session_state["pend_sel"] = marcados[0]

    escolha = st.selectbox("Cenário a analisar (ou clique numa linha da tabela)", options=list(range(len(pend))),
                           key="pend_sel",
                           format_func=lambda i: f"#{i} · {pend[i]['tributo']} · "
                                                 f"{'sem regra' if pend[i]['tipo'] == 'sem_regra' else ('regra do IPI' if pend[i]['tipo'] == 'regra_ipi' else 'regra não bate')} · "
                                                 f"{pend[i]['qtd']} item(ns)")
    p = pend[escolha]
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Como o XML veio**")
        st.table(pd.DataFrame(list(_descreve_trat(p["trat"], p["tributo"]).items()), columns=["O que a nota traz", "Valor"]))
    with c2:
        st.markdown("**Perfis do cenário**")
        st.table(pd.DataFrame(list(_descreve_coords(p["coords"]).items()), columns=["Regra procura", "Valor"]))

    st.markdown("### 1. O XML está correto?")
    xml_certo = st.radio("Responda", ["Não, o XML está errado (erro de emissão)",
                                      "Sim, o XML está certo: é um cenário novo"], key=f"certo_{escolha}")

    if xml_certo.startswith("Não"):
        ops = _opcoes_correcao(p)
        if not ops:
            st.info("Ainda não dá para corrigir este imposto pela tela. Corrija no XML e importe de novo.")
        else:
            st.caption("Preencha só o que estiver errado na nota. Na base, use o código do padrão (ex.: ICMI01, ICMP01).")
            tabela = pd.DataFrame([{"Campo": rot, "Na nota": op["mostra"], "Valor correto": ""}
                                   for rot, op in ops.items()])
            editada = st.data_editor(tabela, hide_index=True, use_container_width=True,
                                     key=f"corr_grid_{escolha}", disabled=["Campo", "Na nota"])
            obs = st.text_input("Observação (opcional)", key=f"obs_{escolha}")
            pendentes = []
            for _, linha in editada.iterrows():
                novo = str(linha["Valor correto"]).strip()
                if not novo:
                    continue
                op = ops[linha["Campo"]]
                cod = op["lista"].get(novo, novo) if op["tipo"] == "lista" else novo
                pendentes.append((linha["Campo"], op, cod))
            if pendentes:
                st.markdown("Serão aplicadas: " + "; ".join(f"{c}: {op['mostra']} → {cod}" for c, op, cod in pendentes)
                            + ". Só vale para a sua sessão.")
            if st.button("Aplicar correções marcadas", key=f"aplica_{escolha}", disabled=not pendentes):
                lista = st.session_state.setdefault("correcoes", [])
                for campo, op, cod in pendentes:
                    lista.append({"id": f"C{len(lista) + 1}", "cnpj": "", "itens": [], "filtro": op["filtro"],
                                  "alteracoes": {op["chave"]: cod}, "tributo": p["tributo"], "campo": campo})
                    _registrar_decisao(p, "xml_corrigido", {"campo": op["chave"], "de": op["mostra"], "para": cod}, obs)
                _aplicar_dados_sessao()
                st.success(f"{len(pendentes)} correção(ões) aplicada(s).")
            if st.session_state.get("args_gerar") and st.session_state.get("correcoes"):
                if st.button("Gerar cenários com as correções", key=f"gerar_pos_{escolha}", type="primary"):
                    a = st.session_state["args_gerar"]
                    _gerar(a["cnpj"], a["agrupar"], a["separar"], ufs=a["ufs"], dp=a["dp"])
                    st.rerun()
    else:
        st.markdown("### 2. Quais perfis separam este cenário?")
        escolhidos = st.multiselect("Dimensões que diferenciam o cenário", list(DIMENSOES_SEPARAR.keys()),
                                    key=f"dim_{escolha}")
        st.markdown("### 3. O que fazer")
        acao = st.radio("Ação", ["Criar regra nova", "Derivar de regra existente (regra pai)", "Ignorar por enquanto"],
                        key=f"acao_{escolha}")
        pai = ""
        if acao.startswith("Derivar"):
            pai = st.text_input("Código da regra pai (ex.: ICM519)", key=f"pai_{escolha}")
        obs = st.text_input("Observação (opcional)", key=f"obs2_{escolha}")
        if st.button("Registrar decisão", type="primary", key=f"reg_nova_{escolha}",
                     disabled=(acao.startswith("Derivar") and not pai)):
            _registrar_decisao(p, "cenario_novo",
                               {"dimensoes": [DIMENSOES_SEPARAR[d] for d in escolhidos], "acao": acao, "pai": pai},
                               obs)
            st.success("Decisão registrada. Ela entra no padrão só depois da sua aprovação, abaixo.")

        # Aprovação: o motor só separa por cliente (dest) ou produto/NCM, pelas exceções do padrão.
        dims = [DIMENSOES_SEPARAR[d] for d in escolhidos]
        st.markdown("### 4. Aprovar e gravar no padrão")
        if not acao.startswith("Criar"):
            st.caption("Aprovação automática só para 'Criar regra nova'.")
        elif "participante" in dims:
            st.caption("Vira exceção por cliente: o CNPJ de destino da nota de exemplo.")
            if st.button("Aprovar: exceção por cliente", key=f"aprv_part_{escolha}"):
                _aprovar_excecao(p, "dest", _cnpj_exemplo(p["exemplo"]), obs, escolha)
        elif "produto" in dims:
            cprod = st.text_input("Código do produto (cprod) para a exceção", key=f"cprod_{escolha}")
            if st.button("Aprovar: exceção por produto", key=f"aprv_prod_{escolha}", disabled=not cprod):
                _aprovar_excecao(p, "cprod", cprod.strip(), obs, escolha)
        else:
            st.warning("Esta dimensão (UF, operação ou tipo de operação) ainda não tem suporte no motor. "
                       "A decisão fica registrada e não entra no padrão automaticamente.")

    with st.expander(f"Correções desta sessão ({len(st.session_state.get('correcoes', []))})"):
        if st.session_state.get("correcoes"):
            st.dataframe(pd.DataFrame([{"Campo": c["campo"], "Imposto": c["tributo"],
                                        "Na nota": str(list(c["filtro"].values())[0]),
                                        "Analisar como": str(list(c["alteracoes"].values())[0])}
                                       for c in st.session_state["correcoes"]]),
                         use_container_width=True, hide_index=True)
            if st.button("Apagar todas as correções", key="apagar_correcoes"):
                st.session_state["correcoes"] = []
                _aplicar_dados_sessao()
                st.rerun()
        else:
            st.caption("Nenhuma correção aplicada.")
    with st.expander("Decisões já registradas"):
        decisoes = _ler_decisoes()
        if decisoes:
            st.dataframe(pd.DataFrame(decisoes), use_container_width=True, hide_index=True, height=420)
        else:
            st.caption("Nenhuma decisão registrada.")


FAMILIA_BASE_APP = {"ICMS": "ICMS", "IPI": "IPI", "PIS": "PC", "COF": "PC",
                    "IBSEST": "IBS", "IBSMUN": "IBS", "CBSFED": "IBS"}


def _opcoes_correcao(p):
    """O que o usuário pode corrigir neste imposto: rótulo -> dados da correção."""
    t = p["tributo"]
    esc, base, al, cbenef = p["trat"][0], p["trat"][1], p["trat"][3], p["trat"][4]
    ops = {}
    chave_cst = {"ICMS": "cst", "IPI": "cst_ipi", "PIS": "cst_pis", "COF": "cst_cof"}.get(t)
    if t in g.FAMILIA_IBS:
        chave_cst = "cst_ibs"
    if chave_cst:
        atual = str(esc[1]) if len(esc) > 1 else ""
        ops["Situação tributária (CST)"] = {"tipo": "texto", "chave": chave_cst, "filtro": {chave_cst: atual},
                                            "mostra": atual or "(vazio)", "exemplo": "ex.: 50"}
    if t == "ICMS":
        ops["Benefício fiscal (cBenef)"] = {"tipo": "texto", "chave": "cbenef", "filtro": {"cbenef": str(cbenef or "")},
                                            "mostra": str(cbenef or "(nenhum)"), "exemplo": "código do benefício"}
    if t in g.FAMILIA_IBS:
        cc = str(esc[5]) if len(esc) > 5 else ""
        ops["Classe tributária"] = {"tipo": "texto", "chave": "cclass", "filtro": {"cclass": cc},
                                    "mostra": cc or "(vazio)", "exemplo": "ex.: 000001"}
    if t in g.CAMPO_ALIQ:
        try:
            atual_al = float(al[0]) if al else 0.0
        except (TypeError, ValueError):
            atual_al = 0.0
        ops["Alíquota"] = {"tipo": "texto", "chave": "aliq_" + t, "filtro": {g.CAMPO_ALIQ[t][0]: str(atual_al)},
                           "mostra": f"{atual_al:.2f}%".replace(".", ","), "exemplo": "ex.: 18"}
    fam = FAMILIA_BASE_APP.get(t)
    lista = {f"{cod} · {desc}": cod for cod, desc, _f, _fn in g.BASES.get(fam, [])} if fam else {}
    if lista:
        chave_base = "base_icms" if t == "ICMS" else "base_" + t
        atual_base = str(base[0]) if base else ""
        ops["Base de cálculo"] = {"tipo": "lista", "chave": chave_base, "filtro": {chave_base: atual_base},
                                  "mostra": str(base[1]) if len(base) > 1 else atual_base, "lista": lista}
    return ops


def _registrar_decisao(p, tipo, extra, obs):
    decisoes = _ler_decisoes()
    registro = {"tributo": p["tributo"], "tipo_pendencia": p["tipo"], "coords": list(p["coords"]),
                "trat": [str(x) for x in p["trat"]], "decisao": tipo, "obs": obs,
                "quando": pd.Timestamp.now().strftime("%d/%m/%Y %H:%M")}
    registro.update(extra)
    decisoes.append(registro)
    st.session_state["decisoes"] = decisoes


def _cnpj_exemplo(chave):
    doc = st.session_state["docs"].get(chave, {})
    return doc.get("dest", "")


def _aprovar_excecao(p, campo, valor, obs, idx):
    """Grava a exceção no padroes_configurador.md (com cópia de segurança) e recarrega o padrão."""
    if not valor:
        st.error("Não encontrei o valor da exceção (CNPJ/código). Informe manualmente.")
        return
    caminho = g.ARQ_PADROES
    raw = open(caminho, "rb").read().decode("utf-8")
    fim = "\r\n" if "\r\n" in raw else "\n"
    linhas = raw.split(fim)
    ini = next((i for i, l in enumerate(linhas) if l.strip() == "## Exceções"), None)
    if ini is None:
        st.error("Não achei a seção '## Exceções' no padrão.")
        return
    cab = next((i for i in range(ini, len(linhas)) if linhas[i].startswith("|---")), None)
    if cab is None:
        st.error("Tabela de exceções não encontrada.")
        return
    fim_tab = cab + 1
    while fim_tab < len(linhas) and linhas[fim_tab].startswith("|"):
        fim_tab += 1
    n = sum(1 for l in linhas[cab + 1:fim_tab] if l.startswith("|")) + 1
    id_exc = f"E{n:02d}"
    linha = f"| {p['tributo']} | {campo} | {valor} | {obs or 'aprovado a partir de pendência'} | {id_exc} |"
    pasta = os.path.join(AQUI, "padroes_backup")
    os.makedirs(pasta, exist_ok=True)
    with open(os.path.join(pasta, f"padroes_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.md"), "wb") as f:
        f.write(raw.encode("utf-8"))
    linhas.insert(fim_tab, linha)
    with open(caminho, "wb") as f:
        f.write(fim.join(linhas).encode("utf-8"))
    g.carregar_padroes()
    _registrar_decisao(p, "aprovada_excecao", {"excecao": id_exc, "campo": campo, "valor": valor}, obs)
    st.success(f"Exceção {id_exc} gravada no padrão ({campo} = {valor}). Gere os cenários de novo para aplicar.")


CHAVES_SESSAO = ["perf_st", "campos_st", "ufs_filtro", "conf_emp", "conf_dp", "conf_cfop", "dims_cen",
                 "filtros_st", "sa1_faltam"]


def _config_sessao():
    cfg = {k: st.session_state[k] for k in CHAVES_SESSAO if k in st.session_state}
    cfg.update({k: st.session_state[k] for k in list(st.session_state.keys()) if str(k).startswith("v_")})
    return cfg


def _zip_sessao():
    """ZIP compacto: notas já lidas, configuração da tela e os cadastros de clientes (regime, SA1, decisões)."""
    sessao = {"versao": 1, "salvo_em": pd.Timestamp.now().strftime("%d/%m/%Y %H:%M"),
              "docs": st.session_state["docs"], "canc": sorted(st.session_state["canc"]),
              "fonte": st.session_state["fonte"], "stats": st.session_state["stats"],
              "lidos": [list(x) for x in st.session_state.get("lidos", set())],
              "config": _config_sessao(), "correcoes": st.session_state.get("correcoes", [])}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr("sessao.json", json.dumps(sessao, ensure_ascii=False, default=str))
        z.writestr("regime_clientes.csv", _texto_regime(st.session_state.get("regime", {}), st.session_state.get("regime_ie", {})))
        z.writestr("cadastro_sa1.csv", _texto_sa1(st.session_state.get("sa1", {})))
        z.writestr("clientes_desconsiderados.json", json.dumps(_ler_desconsiderados(), ensure_ascii=False, indent=2))
        z.writestr("decisoes_pendencias.json", json.dumps(_ler_decisoes(), ensure_ascii=False, indent=2))
    return buf.getvalue()


def _restaurar_zip(arquivo):
    """Lê o ZIP salvo e volta com as notas, a configuração e os cadastros de clientes."""
    with zipfile.ZipFile(io.BytesIO(arquivo.getvalue())) as z:
        sessao = json.loads(z.read("sessao.json").decode("utf-8"))
        nomes = z.namelist()
        regime, ies = _ler_regime_texto(z.read("regime_clientes.csv").decode("utf-8-sig")) if "regime_clientes.csv" in nomes else ({}, {})
        sa1 = _ler_sa1_texto(z.read("cadastro_sa1.csv").decode("utf-8-sig")) if "cadastro_sa1.csv" in nomes else {}
        desc = json.loads(z.read("clientes_desconsiderados.json").decode("utf-8")) if "clientes_desconsiderados.json" in nomes else []
        decs = json.loads(z.read("decisoes_pendencias.json").decode("utf-8")) if "decisoes_pendencias.json" in nomes else []
    st.session_state["regime"], st.session_state["regime_ie"], st.session_state["sa1"] = regime, ies, sa1
    st.session_state["desconsiderados"], st.session_state["decisoes"] = desc, decs
    st.session_state["correcoes"] = sessao.get("correcoes", [])
    _aplicar_dados_sessao()
    canc = set(sessao["canc"])
    st.session_state["docs"] = sessao["docs"]
    st.session_state["canc"] = canc
    st.session_state["fonte"] = sessao["fonte"]
    st.session_state["stats"] = sessao["stats"]
    st.session_state["lidos"] = {tuple(x) for x in sessao["lidos"]}
    st.session_state["emit"] = g.emitentes(st.session_state["docs"], canc)
    st.session_state["mt"], st.session_state["cen"] = None, []   # resultados antigos saem; gere de novo
    for k, v in sessao.get("config", {}).items():
        st.session_state[k] = v


def _passo(numero, titulo, sub, direita, feito=True):
    classe = "passo" if feito else "passo pendente"
    st.markdown(
        f"""<div class="{classe}"><div class="bolinha">{numero}</div>
        <div><div class="titulo">{titulo}</div><div class="sub">{sub}</div></div>
        <div class="direita">{direita}</div></div>""",
        unsafe_allow_html=True,
    )


# ── início ────────────────────────────────────────────────────────────────────
_init_state()
_aplicar_dados_sessao()
avisos_padroes = _inicializar_motor()
for aviso in avisos_padroes:
    st.warning(aviso)

st.title("Gerador de Regras Fiscais")
st.caption("Das notas fiscais às regras tributárias, com agilidade e precisão.")

stats = st.session_state["stats"]
clientes_pj = _clientes_pj()
_desc = _cnpjs_desconsiderados()
clientes_pj = {c: n for c, n in clientes_pj.items() if c not in _desc}
sem_regime = {c: n for c, n in clientes_pj.items() if c not in g.REGIME_CLIENTE}
tem_xml = stats["nfe"] > 0

col_passos, col_res = st.columns([13, 87], gap="medium")
with col_passos:
    with st.expander("Salvar ou carregar sessão"):
        st.download_button("Salvar dados da sessão (ZIP)", data=_zip_sessao(),
                           file_name="sessao_gerador_regras.zip", mime="application/zip")
        arq_sessao = st.file_uploader("Carregar sessão salva (ZIP)", type=["zip"], key="upload_sessao")
        if arq_sessao is not None and st.button("Carregar esta sessão", key="btn_carregar_sessao"):
            try:
                _restaurar_zip(arq_sessao)
                st.toast("Sessão carregada.")
                st.rerun()
            except Exception as e:
                st.error(f"Não consegui carregar este ZIP: {e}")
    # Passo 1 — Importar
    _passo(1, "Importar XMLs de saída", "XML ou ZIP de NF-e emitidas pela empresa",
           f"{stats['nfe']} notas lidas", feito=tem_xml)
    with st.expander("Abrir importação" + ("⁠" if tem_xml else ""), expanded=not tem_xml):
        col_a, col_b = st.columns([2, 1])
        with col_a:
            arquivos = st.file_uploader("Arquivos XML ou ZIP", type=["xml", "zip"], accept_multiple_files=True)
        # leitura automática: lê só os arquivos ainda não lidos nesta sessão
        lidos = st.session_state.setdefault("lidos", set())
        novos = [a for a in (arquivos or []) if (a.name, a.size) not in lidos]
        if novos:
            barra = st.progress(0.0, text="Lendo XMLs: 0%")
            n = _importar_uploads(novos, barra)
            lidos.update((a.name, a.size) for a in novos)
            st.toast(f"{n} arquivo(s) lidos.")
            st.rerun()
        with col_b:
            caminho = st.text_input("Ou pasta grande no computador", placeholder=r"C:\XMLs\saidas",
                                    help="Lê direto do disco. Indicado para milhares de notas.")
            if st.button("Ler caminho", disabled=not caminho):
                barra = st.progress(0.0, text="Lendo arquivos: 0%")
                n = _importar_pasta(caminho, barra)
                st.success(f"{n} arquivo(s) encontrados.")
                st.rerun()

    # Passo 2 — Regime
    if not tem_xml:
        _passo(2, "Regime dos clientes", "Simples ou Normal, por CNPJ. Não vem no XML.", "aguarda o passo 1", feito=False)
    else:
        total_pj = len(clientes_pj)
        ok_pj = total_pj - len(sem_regime)
        if total_pj == 0:
            dir_txt, feito = "sem clientes PJ", True
        elif sem_regime:
            dir_txt, feito = f"{ok_pj} de {total_pj} PJ com regime", False
        else:
            dir_txt, feito = f"{total_pj} de {total_pj} PJ com regime", True
        _passo(2, "Regime dos clientes", "Envie a planilha com CNPJ, inscrição estadual e regime (Simples ou Normal)",
               dir_txt + (f" · {len(_cnpjs_desconsiderados())} desconsiderado(s)"
                          if _cnpjs_desconsiderados() else ""), feito=feito)
        with st.expander("Enviar planilha de regime" + ("" if sem_regime else "⁠"), expanded=bool(sem_regime)):
            st.markdown(
                "A planilha precisa ter as colunas **CNPJ**, **INSCRIÇÃO** (IE) e **REGIME**. "
                "Valores aceitos para o regime: **Simples** ou **Normal**; também **S/N**, **Sim/Não**, **1/2**.")
            arq_regime = st.file_uploader("Planilha de regime (XLSX ou CSV)", type=["xlsx", "xls", "csv"],
                                          key="upload_regime")
            # importação automática ao escolher a planilha (sem botão)
            if arq_regime is not None:
                chave = (arq_regime.name, arq_regime.size)
                if st.session_state.get("regime_lido") != chave:
                    try:
                        barra = st.progress(0.0, text="Lendo planilha: 0%")
                        aceitos, recusados, faltam_sa1 = _importar_regime(arq_regime, barra)
                        st.session_state["regime_lido"] = chave
                        st.session_state["sa1_faltam"] = faltam_sa1
                        st.toast(f"{aceitos} cliente(s) gravados em regime_clientes.csv e cadastro_sa1.csv.")
                        for r in recusados[:20]:
                            st.warning(r)
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

            if _ler_desconsiderados():
                st.info(f"{len(_ler_desconsiderados())} cliente(s) estão desconsiderados por sua confirmação.")
                if st.button("Voltar a considerar esses clientes", key="btn_reverter_desc"):
                    st.session_state["desconsiderados"] = []
                    st.rerun()
            if sem_regime:
                st.warning(f"{len(sem_regime)} cliente(s) estão no XML, mas NÃO vieram na planilha de regime. "
                           "Você pode enviar uma nova planilha com eles. Se não for enviar, eles só saem dos cenários "
                           "se você confirmar abaixo.")
                st.markdown("**Clientes PJ sem regime** — inclua estes CNPJs na planilha:")
                faltam = pd.DataFrame(
                    [{"CNPJ": c, "Nome": n, "INSCRIÇÃO": "", "REGIME": ""} for c, n in sorted(sem_regime.items())])
                st.dataframe(faltam, use_container_width=True, hide_index=True, height=420)
                buf = io.BytesIO()
                faltam.to_excel(buf, index=False, sheet_name="Regime")
                st.download_button("Baixar modelo com os clientes sem regime (XLSX)",
                               data=buf.getvalue(),
                               file_name="modelo_regime_clientes.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                if st.button("Confirmo que esses clientes não existem na base e serão desconsiderados dos cenários",
                             key="btn_desconsiderar"):  # ação só acontece com o clique do usuário
                    novos_d = _ler_desconsiderados()
                    hoje = pd.Timestamp.now().strftime("%d/%m/%Y %H:%M")
                    ja = {r["cnpj"] for r in novos_d}
                    for c, nome in sem_regime.items():
                        # só clientes SEM regime entram na lista de desconsiderados
                        if c not in g.REGIME_CLIENTE and c not in ja:
                            novos_d.append({"cnpj": c, "nome": nome, "quando": hoje})
                    st.session_state["desconsiderados"] = novos_d
                    st.toast(f"{len(sem_regime)} cliente(s) desconsiderados dos cenários.")
                    st.rerun()


    # Passo 3 — Empresa e opções
    emit = st.session_state["emit"]
    if not emit:
        _passo(3, "Empresa e opções", "Escolha o CNPJ emitente", "aguarda o passo 1", feito=False)
        cnpj_sel = None
    else:
        opcoes = {f"{cnpj} · {nome} ({q} notas)": cnpj for cnpj, nome, q in emit}
        _passo(3, "Empresa e opções", "CNPJ emitente e opções de agrupamento",
                   "" if not sem_regime else f"{len(sem_regime)} cliente(s) sem regime",
                   feito=(not sem_regime) and bool(st.session_state.get("conf_emp")))
        with st.expander("Empresa e opções (detalhes)" + ("⁠" if ((not sem_regime) and bool(st.session_state.get("conf_emp"))) else ""),
                         expanded=not ((not sem_regime) and bool(st.session_state.get("conf_emp")))):
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                cnpj_sel = opcoes[st.selectbox("CNPJ emitente", list(opcoes.keys()))]
            with col2:
                agrupar = st.checkbox("Agrupar CFOPs de mesmo tratamento", value=True)
            with col3:
                separar = st.checkbox("Separar por participante", value=True)
            st.markdown("**Campos que compõem o cenário** (escolha antes de gerar)")
            st.multiselect("Campos", list(DIMS_CEN.keys()), default=list(DIMS_CEN.keys()), key="dims_cen",
                           label_visibility="collapsed")
            st.caption("Define como os cenários são agrupados na aba Cenários. Não altera as regras geradas.")
            st.checkbox("Confirmo a empresa, os campos e as opções acima", key="conf_emp")

    _passo(4, "Tipo de operação (de-para)", "Finalidade → tipo de operação, e filtros de UF",
           "confirme para liberar", feito=bool(st.session_state.get("conf_dp")))
    with st.expander("Detalhes do de-para e filtros" + ("⁠" if st.session_state.get("conf_dp") else ""),
                     expanded=not bool(st.session_state.get("conf_dp"))):
        st.markdown("**De-para: finalidade → tipo de operação** (edite se precisar)")
        # IndFinal vem do XML: 1 = consumidor final (independe de ser contribuinte), 0 = demais casos
        linhas_dp = [
            {"IndFinal (XML)": "1", "Finalidade": "CONSUMO",
             "Tipo de operação": g.TIPOS_OPERACAO.get("CONSUMO", ("V3", ""))[0],
             "Descrição": g.TIPOS_OPERACAO.get("CONSUMO", ("", "Venda para uso e consumo"))[1]},
            {"IndFinal (XML)": "0", "Finalidade": "REVENDA",
             "Tipo de operação": g.TIPOS_OPERACAO.get("REVENDA", ("V1", ""))[0],
             "Descrição": g.TIPOS_OPERACAO.get("REVENDA", ("", "Venda para revenda"))[1]},
        ]
        dp_df = st.data_editor(
            pd.DataFrame(linhas_dp, columns=["IndFinal (XML)", "Finalidade", "Tipo de operação", "Descrição"]),
            num_rows="dynamic", use_container_width=True, hide_index=True, key="dp_tipos")
        st.session_state["dp_df"] = dp_df
        st.markdown("**Clientes com finalidade específica** (ex.: INSUMO → V5). Só entra quem você informar aqui.")
        dp_cli = st.data_editor(
            pd.DataFrame([{"CNPJ": "", "Finalidade": "INSUMO"}], columns=["CNPJ", "Finalidade"]),
            num_rows="dynamic", use_container_width=True, hide_index=True, key="dp_clientes",
            column_config={"Finalidade": st.column_config.SelectboxColumn(options=["INSUMO", "REVENDA", "CONSUMO"])})
        st.session_state["dp_cli_df"] = dp_cli
        st.markdown("**Perfis de participante para ST e DIFAL ST**")
        st.caption("A GF usa perfis próprios de cliente para o ST (ex.: CJCF01, CJCF02, CJCNT0, CJCNT1) e para o DIFAL. "
                   "Quer criar perfis próprios para ST e DIFAL ST, ou usar os perfis gerais?")
        perf_st = st.radio("Perfis de participante ST/DIFAL ST",
                           ["Ainda não decidi", "Sim, criar perfis próprios para ST e DIFAL ST",
                            "Não, usar os perfis gerais de participante"],
                           index=0, key="perf_st")
        st.session_state["filtros_st"] = {}
        if perf_st.startswith("Sim"):
            with st.expander("Filtros dos perfis de ST e DIFAL ST (campos do cadastro de clientes)", expanded=True):
                campos = {
                    "Grupo de clientes (A1_GRPTRIB)": None,
                    "Contribuinte (A1_CONTRIB)": ["Contribuinte", "Não contribuinte", "Isento"],
                    "Pessoa (A1_PESSOA)": ["PJ", "PF"],
                    "Regime (A1_SIMPNAC)": ["SIMPLES", "NORMAL"],
                    "UF destino (A1_EST)": sorted({d.get("uf_dest") for d in st.session_state["docs"].values()
                                                  if d.get("uf_dest")}),
                    "SUFRAMA (A1_SUFRAMA)": ["Sim", "Não"],
                }
                escolhidos_campos = st.multiselect("Campos que definem o perfil de ST", list(campos.keys()),
                                                   key="campos_st")
                filtros = {}
                for c in escolhidos_campos:
                    if campos[c] is None:
                        txt = st.text_input(f"Valores de {c} (separados por vírgula)", key=f"v_{c}")
                        vals = [v.strip() for v in txt.split(",") if v.strip()]
                    else:
                        vals = st.multiselect(f"Valores de {c}", campos[c], key=f"v_{c}")
                    if vals:
                        filtros[c] = vals
                st.session_state["filtros_st"] = filtros
                if escolhidos_campos and not filtros:
                    st.warning("Informe ao menos um valor para cada campo escolhido.")
                st.caption("Grupo de clientes não vem na nota: informe os códigos do cadastro (ex.: TRANSP, IND).")
        faltam_sa1 = st.session_state.get("sa1_faltam", list(CAMPOS_SA1)) if g.CADASTRO_SA1 else list(CAMPOS_SA1)
        campos_usados = {c.split("(")[-1].rstrip(")").replace("A1_", "") for c in st.session_state.get("filtros_st", {})}
        faltam_uso = [f for f in faltam_sa1 if f in campos_usados]
        if perf_st.startswith("Sim") and st.session_state.get("filtros_st") and faltam_uso:
            st.error("A planilha de regime não traz as colunas do cadastro de clientes necessárias para estes filtros: "
                     + ", ".join(faltam_uso) + ". Envie a exportação do SA1 com essas colunas.")
        st.session_state["perf_st_ok"] = (perf_st.startswith("Não")) or (
            perf_st.startswith("Sim") and bool(st.session_state.get("filtros_st")) and not faltam_uso)
        ufs_todas = sorted({d.get("uf_dest") for d in st.session_state["docs"].values() if d.get("uf_dest")})
        st.multiselect("Filtro: UF de destino a considerar (vazio = todas)", ufs_todas, key="ufs_filtro")
        st.checkbox("Confirmo o de-para e os filtros acima", key="conf_dp")
    # Passo 4 — Gerar
    pode_gerar = cnpj_sel is not None
    # sem planilha de clientes enviada, o programa não segue (quando há clientes PJ nas notas)
    tem_pj = len(clientes_pj) > 0 or any(str(d.get("tipo", "")).startswith("PJ")
                                         for d in st.session_state["docs"].values())
    if pode_gerar and tem_pj and not g.REGIME_CLIENTE:
        st.error("Envie primeiro a planilha de clientes com o regime (Simples ou Normal). "
                 "Sem ela, o programa não gera os cenários.")
        pode_gerar = False
    elif pode_gerar and sem_regime:
        st.warning(f"{len(sem_regime)} cliente(s) PJ sem regime. Regras de PJ podem sair erradas. "
                   "Recomendo enviar a planilha antes de gerar.")
        confirmar = st.checkbox("Gerar mesmo assim (as regras de PJ ficarão pendentes de regime)")
        pode_gerar = confirmar
    # ── CFOPs para análise: venda agregada; demais CFOPs só entram se o usuário incluir ──
    contagem = Counter()
    for d in st.session_state["docs"].values():
        for it in d.get("itens", []):
            contagem[it.get("cfop", "")] += 1
    linhas_cf = []
    for cf, qtd in sorted(contagem.items(), key=lambda kv: -kv[1]):
        op = g.OPERACAO.get(cf[1:], ("", "OUTRAS", ""))
        linhas_cf.append({"Incluir": True, "Agregar com vendas": op[1] == "VENDAS", "CFOP": cf, "Grupo": op[1],
                          "Natureza": op[0], "Itens": qtd})
    venda_n = sum(1 for x in linhas_cf if x["Grupo"] == "VENDAS")
    venda_itens = sum(x["Itens"] for x in linhas_cf if x["Grupo"] == "VENDAS")
    outros_n = len(linhas_cf) - venda_n
    _passo(5, "CFOPs para análise", "Venda agregada entra por padrão; os demais precisam de análise",
           f"{venda_n} CFOP de venda ({venda_itens:,} itens) · {outros_n} outros".replace(",", "."),
           feito=bool(st.session_state.get("conf_cfop")))
    with st.expander("Detalhes dos CFOPs" + ("⁠" if st.session_state.get("conf_cfop") else ""),
                     expanded=not bool(st.session_state.get("conf_cfop"))):
        if linhas_cf:
            st.markdown("**Incluir**: marcados por padrão (todos os CFOPs das notas). Desmarque para deixar um CFOP de fora. "
                        "**Agregar com vendas**: marcado só para o grupo VENDAS. Desmarcado, o CFOP gera cenários próprios.")
            cf_df = st.data_editor(pd.DataFrame(linhas_cf), hide_index=True, use_container_width=True,
                                   key="cfops_tab", height=300,
                                   column_config={"Incluir": st.column_config.CheckboxColumn(),
                                                  "Agregar com vendas": st.column_config.CheckboxColumn(),
                                                  "Itens": st.column_config.NumberColumn(format="%d")},
                                   disabled=["CFOP", "Grupo", "Natureza", "Itens"])
            incluidos = cf_df.loc[cf_df["Incluir"] == True, "CFOP"].tolist()  # noqa: E712
            agregados = cf_df.loc[(cf_df["Incluir"] == True) & (cf_df["Agregar com vendas"] == True), "CFOP"].tolist()  # noqa: E712
            st.session_state["cfops_sel"] = set(incluidos)
            st.session_state["cfops_agregar"] = set(agregados)
            st.checkbox("Confirmo os CFOPs incluídos", key="conf_cfop")
        else:
            st.info("Nenhuma nota importada.")

    _passo(6, "Gerar cenários", "Analisa as notas e monta regras, bases, alíquotas e escrituração",
           f"última geração: {st.session_state['gerado_em']}" if st.session_state["gerado_em"] else "",
           feito=st.session_state["mt"] is not None)
    conf_ok = bool(st.session_state.get("conf_dp")) and bool(st.session_state.get("conf_cfop")) and bool(st.session_state.get("perf_st_ok"))
    conf_ok = conf_ok and bool(st.session_state.get("conf_emp"))
    if pode_gerar and not conf_ok:
        st.info("Confirme o de-para, os CFOPs e a escolha dos perfis de ST antes de gerar.")
        pode_gerar = False
    if cnpj_sel is not None:
        st.session_state["args_gerar"] = {"cnpj": cnpj_sel, "agrupar": agrupar, "separar": separar,
                                          "ufs": st.session_state.get("ufs_filtro") or None,
                                          "dp": st.session_state.get("dp_df")}
    if st.button("Gerar cenários", type="primary", disabled=not pode_gerar):
        _gerar(cnpj_sel, agrupar, separar, ufs=st.session_state.get("ufs_filtro") or None,
               dp=st.session_state.get("dp_df"))
        st.toast("Cenários gerados.")
        st.rerun()


with col_res:
    # Passo 5 — Conferir
    mt = st.session_state["mt"]
    an = st.session_state["an"]
    _passo(7, "Conferir resultados", "Regras F2B, cenários, cadastros e validações",
           "", feito=mt is not None)
    if mt is None:
        st.info("Gere os cenários no passo 4 para ver os resultados.")
    else:
        pend_n = len(mt.get("pendencias", []) or [])
        if pend_n:
            st.warning(f"{pend_n} cenário(s) do XML sem regra certa (faltando ou com tratamento diferente). "
                       "Veja a aba **Pendências** para decidir cada um.")
        else:
            st.success("Todos os cenários do XML têm regra.")
        abas = st.tabs(["Visão geral", "Regras F2B", "Cenários", "Cadastros", "Validações", "Pendências", "Padrões"])
        (aba_vis, aba_reg, aba_cen, aba_cad, aba_val, aba_pen, aba_pad) = abas
        st.download_button("Exportar tudo em Excel (XLSX)", data=_xlsx_completo(mt, st.session_state.get("cen")),
                           file_name="facilitador_fiscal_resultados.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        with aba_pen:
            _tela_pendencias(mt)
            _tela_regra_ipi()

        with aba_vis:
            v = mt["validacao"]
            total_v = sum(v.values()) or 1
            correto = v.get("ok", 0) / total_v
            notas = len(an.get("validos", [])) if an else 0
            itens = sum(v.values())
            pend_n = len(mt.get("pendencias", []) or [])
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Notas analisadas", f"{notas:,}".replace(",", "."))
            c2.metric("Itens", f"{itens:,}".replace(",", "."))
            c3.metric("Regras F2B a cadastrar", f"{len(mt['regras']):,}".replace(",", "."))
            c4.metric("Resultado correto", f"{correto:.1%}")

            st.markdown("#### Regras por imposto")
            por_trib = Counter(r["F2B_TRIB"] for r in mt["regras"])
            df_trib = pd.DataFrame(sorted(por_trib.items(), key=lambda kv: -kv[1]), columns=["Imposto", "Regras"])
            st.bar_chart(df_trib, x="Imposto", y="Regras", color="#1565c0", height=260)

            g1, g2 = st.columns(2)
            with g1:
                st.markdown("#### Cadastros necessários")
                cad = pd.DataFrame([
                    ("Perfis de produto", len(mt["perf_prod"])),
                    ("Perfis de participante", len(mt["perf_part"])),
                    ("Perfis de origem/destino", len(mt["perf_od"])),
                    ("Perfis de operação", len(mt["perf_op"])),
                    ("Bases (F27)", len(mt["bases"])),
                    ("Alíquotas (F28)", len(mt["aliqs"])),
                    ("Escriturações (CJ2)", len(mt["escs"])),
                    ("Tipos de operação", len(mt["tipos_op"])),
                ], columns=["Cadastro", "Quantidade"])
                st.dataframe(cad, use_container_width=True, hide_index=True)
            with g2:
                st.markdown("#### Validação (1 item = 1 regra por imposto)")
                val = pd.DataFrame([(k, int(x)) for k, x in v.items()], columns=["Situação", "Itens"])
                st.bar_chart(val, x="Situação", y="Itens", color="#2e7d32", height=260)
                if pend_n:
                    st.warning(f"{pend_n} cenário(s) sem regra certa. Veja a aba Pendências.")
                else:
                    st.success("Nenhum cenário pendente.")

        with aba_reg:
            df = _regras_df(mt)
            tributos = sorted(df["F2B_TRIB"].dropna().unique())
            filtro = st.multiselect("Filtrar por imposto (escolha quais quer ver; sem escolha = todos)",
                                    tributos, default=[], key="filtro_tributo_regras")
            escolhidos = filtro or tributos
            visivel = df[df["F2B_TRIB"].isin(escolhidos)]
            st.caption(f"{len(visivel)} regra(s)")
            st.dataframe(visivel, use_container_width=True, hide_index=True, height=420)
            csv_txt = "\n".join(g.linha_csv_f2b(r) for r in mt["regras"] if r.get("F2B_TRIB") in escolhidos)
            st.download_button("Baixar CSV F2B (layout de importação)", data=csv_txt.encode("cp1252", "replace"),
                               file_name="regras_f2b.csv", mime="text/csv")

        with aba_cen:
            escolhidas = st.session_state.get("dims_cen") or list(DIMS_CEN.keys())
            if not escolhidas:
                st.info("Selecione ao menos um item.")
            else:
                idx = [DIMS_CEN[d] for d in escolhidas]
                agregado = {}
                for c in st.session_state["cen"]:
                    chave = tuple(c["k"][i] for i in idx)
                    a = agregado.setdefault(chave, {"itens": 0, "notas": set(), "exemplo": c["exemplo"],
                                                    "regras": {}})
                    a["itens"] += c["itens"]
                    a["notas"] |= c["notas"]
                    for t, r in c["regras"].items():
                        if r:
                            a["regras"].setdefault(t, set()).add(r)
                linhas = []
                for chave, a in sorted(agregado.items(), key=lambda kv: -kv[1]["itens"]):
                    linha = {d: str(v) for d, v in zip(escolhidas, chave)}
                    linha.update({"Itens": a["itens"], "Notas": len(a["notas"]), "Nota exemplo": a["exemplo"]})
                    for t in sorted(a["regras"]):
                        linha[f"Regra {t}"] = " / ".join(sorted(a["regras"][t]))
                    linhas.append(linha)
                st.caption(f"{len(linhas)} cenário(s) com os itens escolhidos.")
                st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True, height=420)

        with aba_cad:
            sec = st.radio("Cadastro", ["Bases (F27)", "Alíquotas (F28)", "Escrituração (CJ2)", "Tipos de operação",
                                        "Perfil Orig./Dest. (F21)"], horizontal=True)
            if sec == "Perfil Orig./Dest. (F21)":
                df21 = pd.DataFrame(g.linhas_f21(mt), columns=g.COLS_F21)
                st.caption(f"{len(df21)} linha(s): um par UF origem × UF destino por linha, por perfil.")
                st.dataframe(df21, use_container_width=True, hide_index=True, height=420)
                st.download_button("Baixar F21 (CSV)", data=df21.to_csv(sep=";", index=False).encode("utf-8-sig"),
                                   file_name="f21_perfil_orig_dest.csv", mime="text/csv")
            else:
                mapa = {"Bases (F27)": "bases", "Alíquotas (F28)": "aliqs", "Escrituração (CJ2)": "escs",
                        "Tipos de operação": "tipos_op"}
                st.dataframe(_tabela_dict(mt.get(mapa[sec], {})), use_container_width=True, hide_index=True, height=420)

        with aba_val:
            st.json(mt["validacao"])
            if an and an.get("conflitos"):
                st.subheader("Conflitos do XML")
                st.write(an["conflitos"])

        with aba_pad:
            st.caption("Edite o padroes_configurador.md e salve. O motor relê o arquivo ao recarregar.")
            caminho_md = g.ARQ_PADROES
            texto_atual = open(caminho_md, encoding="utf-8").read() if os.path.exists(caminho_md) else ""
            novo = st.text_area("Conteúdo do padrão", value=texto_atual, height=500)
            if st.button("Salvar e recarregar padrões", type="primary"):
                with open(caminho_md, "w", encoding="utf-8") as f:
                    f.write(novo)
                _, avisos = g.carregar_padroes()
                st.success("Padrões salvos e recarregados. Gere os cenários de novo para aplicar.")
                for a in avisos:
                    st.info(a)
