# -*- coding: utf-8 -*-
"""
servidor.py — Facilitador Fiscal (versão web)
=============================================
Backend da interface web. NÃO reimplementa nenhuma regra: importa o motor existente
(gerador_cenarios.py) e expõe seus resultados em uma API JSON para a interface em web/index.html.

    python servidor.py            -> abre http://127.0.0.1:8765 no navegador
    python servidor.py 9000       -> usa outra porta

Só usa a biblioteca padrão do Python 3.9+. A versão desktop (python gerador_cenarios.py) continua funcionando.
"""
import os, sys, json, time, zipfile, threading, tempfile, webbrowser, csv, io, re, copy, hashlib
import urllib.request, urllib.error
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
if not sys.argv[0] or os.path.dirname(os.path.abspath(sys.argv[0])) != AQUI:
    sys.argv[0] = os.path.join(AQUI, "servidor.py")      # padroes_configurador.md fica ao lado do programa
import gerador_cenarios as g                              # o motor (leitura, análise, regras, cadastros)

WEB = os.path.join(AQUI, "web")
DADOS = os.path.join(tempfile.gettempdir(), "facilitador_fiscal")   # fora do OneDrive/Área de Trabalho
os.makedirs(os.path.join(DADOS, "uploads"), exist_ok=True)

TRAVA = threading.RLock()
LIMITE_REVISAR_PCT = 1.0   # regra vira "Revisar" quando 1% ou mais dos itens do seu cenário divergem no XML
EST = {"docs": {}, "canc": set(), "fonte": {}, "emit": [], "an": None, "mt": None, "cen": [],
       "cnpj": None, "opcoes": {"agrupar": True, "separar": False, "aliq_ncm": None}, "stats": Counter(),
       "status": {"tarefa": None, "msg": "", "prog": 0.0, "erro": ""}, "avisos_padroes": [], "gerado_em": None}


def _status(**kw):
    with TRAVA:
        EST["status"].update(kw)


# ── importação: guarda a origem de cada XML para mostrar o exemplo depois ─────
def _registrar(dados, fonte):
    tp, val = g.ler_xml_bytes(dados)
    with TRAVA:
        if tp == "nfe" and val.get("chave"):
            EST["stats"]["repetidas" if val["chave"] in EST["docs"] else "nfe"] += 1
            EST["docs"][val["chave"]] = val
            EST["fonte"][val["chave"]] = fonte
        elif tp == "canc":
            EST["canc"].add(val)
            EST["stats"]["cancelamentos"] += 1
        else:
            EST["stats"]["ignorados"] += 1


def _importar_caminhos(caminhos):
    lista = []
    for c in caminhos:
        lista += list(g._listar(c))
    total = len(lista) or 1
    zf, zn = None, None
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
                _registrar(dados, (nm, z))
            except Exception:
                with TRAVA:
                    EST["stats"]["erros"] += 1
            if i % 500 == 0 or i == total:
                _status(msg=f"Lendo XMLs: {i:,} de {total:,}".replace(",", "."), prog=i / total)
    finally:
        if zf:
            zf.close()
    _atualizar_emitentes()


def _atualizar_emitentes():
    with TRAVA:
        EST["emit"] = g.emitentes(EST["docs"], EST["canc"])


def _em_segundo_plano(nome, func):
    with TRAVA:
        if EST["status"]["tarefa"]:
            raise RuntimeError(f"Aguarde: {EST['status']['tarefa']} em andamento.")
        EST["status"].update(tarefa=nome, msg="", prog=0.0, erro="")

    def rodar():
        try:
            func()
            _status(tarefa=None, msg="Concluído.", prog=1.0)
        except Exception as e:
            _status(tarefa=None, erro=str(e), msg="")
    threading.Thread(target=rodar, daemon=True).start()


def _gerar(cnpj, agrupar, separar, aliq_ncm=None):
    _status(msg="Analisando cenários…", prog=0.1)
    an = g.analisar(EST["docs"], EST["canc"], cnpj, agrupar, lambda s: _status(msg=s), separar, aliq_ncm)
    _status(msg="Montando regras e cadastros…", prog=0.7)
    mt = g.montar_matriz(an, _codigos_anteriores(cnpj))
    _salvar_codigos(cnpj, mt["assinaturas"])
    _status(msg="Organizando cenários…", prog=0.9)
    cen = g.montar_cenarios(an, mt)
    _marcar_status_regras(an, mt)
    mapa = _mapa_itens(an, mt)
    with TRAVA:
        EST.update(an=an, mt=mt, cen=cen, cnpj=cnpj, mapa_itens=mapa,
                   opcoes={"agrupar": agrupar, "separar": separar, "aliq_ncm": an["aliq_ncm"]},
                   gerado_em=time.strftime("%d/%m/%Y %H:%M"))


# ── códigos das regras: a regra que continua igual mantém o código entre gerações ──
ARQ_CODIGOS = os.path.join(AQUI, "codigos_regras.json")


def _ler_codigos():
    try:
        with open(ARQ_CODIGOS, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _codigos_anteriores(cnpj):
    return _ler_codigos().get(cnpj or "", {})


def _salvar_codigos(cnpj, assinaturas):
    tudo = _ler_codigos()
    atual = tudo.get(cnpj, {})
    atual.update(assinaturas)
    tudo[cnpj] = atual
    try:
        with open(ARQ_CODIGOS, "w", encoding="utf-8") as f:
            json.dump(tudo, f, ensure_ascii=False)
    except OSError:
        pass


def api_renumerar(_):
    """Esquece os códigos guardados do emitente: a próxima geração numera tudo de novo (ICM500, ICM501…)."""
    tudo = _ler_codigos()
    tudo.pop(EST["cnpj"] or "", None)
    with open(ARQ_CODIGOS, "w", encoding="utf-8") as f:
        json.dump(tudo, f, ensure_ascii=False)
    return {"regerando": _regenerar()}


def _mapa_itens(an, mt):
    """Regra que cada item aciona em cada tributo (na ordem de an['linhas']) — base do 'antes → depois'."""
    mapa = []
    for d, it, tr in an["linhas"]:
        m = {}
        for t in g.ORDEM_TRIB:
            if t in mt["cel_regra"]:
                cl = g.celula(t, d, it, an["modas"], an["separar"] and g.TRIBUTOS[t][5] == "ORIG")
                m[t] = mt["cel_regra"][t].get(cl, "") if t in tr else ""
        mapa.append(m)
    return mapa


def _br(n, casas=None):
    txt = f"{n:,.{casas}f}" if casas is not None else f"{n:,}"
    return txt.replace(",", "§").replace(".", ",").replace("§", ".")


def _marcar_status_regras(an, mt):
    """Revisar = base não identificada, ou 1% ou mais dos itens que a regra aciona vieram com outro
    tratamento no XML (contagem feita só nas células cobertas pela própria regra)."""
    for r in mt["regras"]:
        motivos = []
        relevante = False
        if r["F2B_RBASE"] in ("?BASE?", "ISTB99", "DIFX01"):
            motivos.append("Base não identificada pelos valores do XML")
            relevante = True
        cel = an["regras_trib"][r["_t"]][1]
        n = 0
        for c, cnt in cel.items():
            if all(c[i] in r["_b"][i] for i in range(4)):
                n += sum(q for tr, q in cnt.items() if tr != r["_trat"])
        if n:
            pct = n / max(r["Itens"] + n, 1) * 100
            motivos.append(f"{_br(n)} item(ns) que esta regra acionaria vieram com outro tratamento no XML "
                           f"({_br(pct, 1)}%)")
            relevante = relevante or pct >= LIMITE_REVISAR_PCT
        r["_status"] = "Revisar" if relevante else "Identificado"
        if not relevante and not r["Itens"]:
            r["_status"] = "Prevista"
            motivos.append("Nenhum item nos XMLs: regra do esqueleto, prevista para quando o cenário acontecer")
        if r.get("GRUPO_DERIVADO"):
            motivos.append(f"Regra filha do grupo derivado {r['GRUPO_DERIVADO']}"
                           + (f", derivada da {r['PAI']}" if r.get("PAI") else " (sem regra pai equivalente)"))
        r["_motivos"] = motivos


# ── conversões para JSON ──────────────────────────────────────────────────────
def _regra_json(r):
    j = {c: r.get(c, "") for c in ("F2B_REGRA", "F2B_DESC", "F2B_TRIB", "F2B_RBASE", "F2B_RALIQ", "F2B_PEROD",
                                   "F2B_PERFPA", "F2B_PERFOP", "F2B_PERFPR", "F2B_CODESC", "cBenef", "Itens",
                                   "Exemplo (chave)", "CFOPs", "UFs", "PAI", "GRUPO_DERIVADO")}
    j.update(status=r.get("_status", ""), motivos=r.get("_motivos", []))
    mt = EST["mt"]
    if mt:
        e = mt["escs"].get(r["F2B_CODESC"], {})
        a = mt["aliqs"].get(r["F2B_RALIQ"], {})
        j.update(
            tributo_nome=g.TRIBUTOS.get(r.get("_t"), ("", r["F2B_TRIB"]))[1],
            d_base=mt["bases"].get(r["F2B_RBASE"], {}).get("Descrição", ""),
            d_aliq=a.get("Descrição", "") + (f" · {a['Valor']}%" if a.get("Valor") else ""),
            d_od=mt["perf_od"].get(r["F2B_PEROD"], {}).get("Descrição", ""),
            d_part=mt["perf_part"].get(r["F2B_PERFPA"], {}).get("Descrição", ""),
            d_op=mt["perf_op"].get(r["F2B_PERFOP"], {}).get("Descrição", ""),
            d_prod=mt["perf_prod"].get(r["F2B_PERFPR"], {}).get("Descrição", ""),
            esc_trib=e.get("Tributo", ""), esc_cst=e.get("CJ2_CST", ""),
            esc_incide=f"{e.get('CJ2_INCIDE', '')} · {e.get('Incidência', '')}",
            esc_acao=f"{e.get('CJ2_STOTNF', '')} · {e.get('Ação na nota', '')}")
    return j


def _limpo(d):
    return {k: v for k, v in d.items() if not k.startswith("_")}


def _exige_gerado():
    if not EST["mt"]:
        raise LookupError("Nenhuma análise gerada. Importe os XMLs e gere os cenários.")


def api_status(_):
    with TRAVA:
        st = dict(EST["status"])
        return {"status": st, "docs": len(EST["docs"]), "stats": dict(EST["stats"]),
                "emitentes": [{"cnpj": c, "nome": n, "notas": q} for c, n, q in EST["emit"]],
                "cnpj": EST["cnpj"], "gerado": bool(EST["mt"]), "gerado_em": EST["gerado_em"],
                "opcoes": EST["opcoes"], "nome": EST["an"]["nome"] if EST["an"] else "",
                "tributos": [{"chave": k, "trib": v[0], "nome": v[1]} for k, v in g.TRIBUTOS.items()],
                "aliq_ncm_padrao": list(g.OPCOES["ALIQ_NCM"]),
                "padroes_opcoes": {"agrupar": g.OPCOES["AGRUPAR_MAXIMO"], "separar": g.OPCOES["SEPARAR_PARTICIPANTE"],
                                   "esqueleto": g.OPCOES.get("ESQUELETO_COMPLETO", True)},
                "padroes": g.ARQ_PADROES,
                "agrupamentos_pendentes": sum(1 for q in (EST["mt"] or {}).get("agrupamentos", [])
                                              if q["decisao"] == "perguntar"),
                "grupos": len(g.GRUPOS_DERIVADOS), "llm": bool(_llm_cfg().get("api_key"))}


def api_visao(_):
    _exige_gerado()
    an, mt = EST["an"], EST["mt"]
    v = mt["validacao"]
    tot = sum(v.values()) or 1
    divergencias = [st for st in an["regras_negocio"] if st["divergiu"]]
    revisar = [r for r in mt["regras"] if r.get("_status") == "Revisar"]
    nomes = ["produto", "participante", "operação", "UF"]
    por = Counter(r["F2B_TRIB"] for r in mt["regras"])
    return {
        "emitente": {"cnpj": an["cnpj"], "nome": an["nome"], "uf": an["uf_emit"]},
        "kpis": {"xmls": an["notas"], "itens": an["itens"], "docs_total": len(EST["docs"]),
                 "cenarios": len(EST["cen"]), "regras": len(mt["regras"]),
                 "regras_por_tributo": dict(por), "revisar": len(an["conflitos"]) + len(divergencias),
                 "revisar_conflitos": len(an["conflitos"]), "revisar_divergencias": len(divergencias),
                 "regras_revisar": len(revisar),
                 "correto_pct": round((v["ok"] + v["sem_tributo_ok"]) / tot * 100, 2),
                 "duplicidades": v["duplicada"]},
        "aliq_ncm": [g.TRIBUTOS[k][0] for k in an["aliq_ncm"] if k in g.TRIBUTOS],
        "dependencias": [{"tributo": g.TRIBUTOS[t][0], "nome": g.TRIBUTOS[t][1],
                          "depende": [nomes[i] for i in S], "regras": por.get(g.TRIBUTOS[t][0], 0),
                          "uf_cada": g.DIMENSOES.get(t, g.DIM_PADRAO)["uf"] == "cada"}
                         for t, S in an["dims"].items()],
        "principais": [_regra_json(r) for r in sorted(mt["regras"], key=lambda r: -r["Itens"])[:12]],
        "cadastros": {"perfis_produto": len(mt["perf_prod"]), "perfis_participante": len(mt["perf_part"]),
                      "origem_destino": len(mt["perf_od"]), "perfis_operacao": len(mt["perf_op"]),
                      "tipos_operacao": len(mt["tipos_op"]), "bases": len(mt["bases"]), "aliquotas": len(mt["aliqs"]),
                      "aliquotas_ncm": len(mt["linhas_ncm"]), "escrituracao": len(mt["escs"])},
        "resumo_texto": g.resumo_texto(an, mt),
    }


def api_regras(_):
    _exige_gerado()
    return {"regras": [_regra_json(r) for r in EST["mt"]["regras"]],
            "tributos": [g.TRIBUTOS[t][0] for t in g.ORDEM_TRIB if t in EST["an"]["regras_trib"]]}


def _xml_exemplo(r):
    """Trecho do XML real que originou a regra: cabeçalho da nota e o item que aciona a regra."""
    ch = r.get("Exemplo (chave)")
    fonte = EST["fonte"].get(ch)
    if not fonte:
        return ""
    nm, z = fonte
    try:
        if z:
            with zipfile.ZipFile(z) as zf:
                dados = zf.read(nm)
        else:
            with open(nm, "rb") as f:
                dados = f.read()
        root = g._sem_ns(ET.fromstring(dados))
    except Exception:
        return ""
    inf = root.find(".//infNFe")
    if inf is None:
        return ""
    d = EST["docs"][ch]
    an, mt = EST["an"], EST["mt"]
    t = r["_t"]
    det_ok, n_item = None, None
    for i, (det, it) in enumerate(zip(inf.findall("det"), d["itens"])):
        cl = g.celula(t, d, it, an["modas"], an["separar"] and g.TRIBUTOS[t][5] == "ORIG")
        if mt["cel_regra"].get(t, {}).get(cl) == r["F2B_REGRA"]:
            det_ok, n_item = det, i + 1
            break
    novo = ET.Element("infNFe", {"Id": inf.get("Id", "")})
    for tag, filhos in (("ide", ("nNF", "dhEmi", "tpNF", "idDest", "finNFe", "indFinal")),
                        ("emit", ("CNPJ", "xNome", "enderEmit/UF", "CRT")),
                        ("dest", ("CNPJ", "CPF", "xNome", "enderDest/UF", "indIEDest", "IE", "ISUF"))):
        el = inf.find(tag)
        if el is None:
            continue
        sub = ET.SubElement(novo, tag)
        for f in filhos:
            x = el.find(f)
            if x is not None:
                if "/" in f:
                    pai = ET.SubElement(sub, f.split("/")[0])
                    ET.SubElement(pai, x.tag).text = x.text
                else:
                    ET.SubElement(sub, x.tag).text = x.text
    if det_ok is not None:
        novo.append(det_ok)
    try:
        ET.indent(novo, space="  ")
    except AttributeError:
        pass
    txt = ET.tostring(novo, encoding="unicode")
    return (f"<!-- NF {d['num']} · item {n_item or '?'} · trecho do XML real que aciona {r['F2B_REGRA']} -->\n"
            + txt)


def api_regra(q):
    _exige_gerado()
    cod = (q.get("cod") or [""])[0]
    mt = EST["mt"]
    r = next((x for x in mt["regras"] if x["F2B_REGRA"] == cod), None)
    if not r:
        raise LookupError(f"Regra {cod} não encontrada.")
    pr, pa = mt["perf_prod"].get(r["F2B_PERFPR"], {}), mt["perf_part"].get(r["F2B_PERFPA"], {})
    od, op = mt["perf_od"].get(r["F2B_PEROD"], {}), mt["perf_op"].get(r["F2B_PERFOP"], {})
    b, a, e = mt["bases"].get(r["F2B_RBASE"], {}), mt["aliqs"].get(r["F2B_RALIQ"], {}), mt["escs"].get(r["F2B_CODESC"], {})
    ncm = [l for l in mt["linhas_ncm"] if l["Tributo"] == r["F2B_TRIB"]] if r["F2B_RALIQ"] == g.ALIQ_NCM[0] else []
    campos = [[c, r.get(c, g.RAPUR_PADRAO if c == "F2B_RAPUR" else "")] for c in g.COLS_F2B]
    return {"regra": _regra_json(r), "campos": campos, "linha_csv": g.linha_csv_f2b(r),
            "cadastros": {"base": _limpo(b), "aliquota": _limpo(a), "escrituracao": _limpo(e),
                          "produto": _limpo(pr), "participante": _limpo(pa), "origem_destino": _limpo(od),
                          "operacao": _limpo(op)},
            "aliquotas_ncm": ncm[:300], "aliquotas_ncm_total": len(ncm), "xml": _xml_exemplo(r)}


def api_cenarios(_):
    _exige_gerado()
    tribs = [t for t in g.ORDEM_TRIB if t in EST["an"]["regras_trib"]]
    return {"tributos": [{"chave": t, "trib": g.TRIBUTOS[t][0], "nome": g.TRIBUTOS[t][1]} for t in tribs],
            "cenarios": [{"cfop": c["k"][0], "finalidade": c["k"][1], "uf": c["k"][2], "participante": c["k"][3],
                          "origem": c["k"][4], "classe_ipi": c["k"][5], "classe_pc": c["k"][6], "classe_ibs": c["k"][7],
                          "itens": c["itens"], "notas": len(c["notas"]), "exemplo": c["exemplo"],
                          "regras": {g.TRIBUTOS[t][0]: c["regras"].get(t, "") for t in tribs}} for c in EST["cen"]]}


def api_cadastros(_):
    _exige_gerado()
    an, mt = EST["an"], EST["mt"]
    qtd_prod = Counter(it["cprod"] for d in an["validos"] for it in d["itens"])
    perfis_do_prod = defaultdict(set)
    for cod, x in mt["perf_prod"].items():
        if x.get("_s"):
            for k in x["_s"]:
                for pr in an["prod_keys"][x["_t"]].get(k, ()):
                    perfis_do_prod[pr].add(cod)
    clientes = defaultdict(lambda: ["", "", "", 0])
    for d in an["validos"]:
        c = clientes[d["dest"] or "(consumidor)"]
        c[0], c[1], c[2] = d["dest_nome"], d["uf_dest"], d["tipo"] + (" SUFRAMA" if d["suframa"] else "")
        c[3] += 1
    part_qtd = Counter(v[2] for v in clientes.values())

    def tab(cols, linhas):
        return {"colunas": cols, "linhas": linhas}
    return {
        "perfis_produto": tab(["Código", "Descrição", "Família", "Classes", "Produtos"],
                              [[p["Código"], p["Descrição"], p["Família"], p["Classes"], p["Produtos"]]
                               for p in mt["perf_prod"].values()]),
        "perfis_participante": tab(["Código", "Descrição", "Tipos", "Critério sugerido", "Clientes"],
                                   [[p["Código"], p["Descrição"], p["Tipos"], p["Critério sugerido"],
                                     sum(q for k, q in part_qtd.items() if p.get("_s") is None or k in p["_s"])]
                                    for p in mt["perf_part"].values()]),
        "origem_destino": tab(["Código", "Descrição", "UF origem", "UFs destino"],
                              [[p["Código"], p["Descrição"], p["UF origem"], p["UFs destino"]]
                               for p in mt["perf_od"].values()]),
        "perfis_operacao": tab(["Código", "Descrição", "CFOPs", "Tipos de operação"],
                               [[p["Código"], p["Descrição"], p["CFOPs"], p["Tipos de operação"]]
                                for p in mt["perf_op"].values()]),
        "tipos_operacao": tab(["Tipo de operação", "CFOPs"],
                              [[k, ", ".join(sorted(v))] for k, v in sorted(mt["tipos_op"].items())]),
        "bases": tab(["Código", "Descrição", "Fórmula sugerida"],
                     [[b["Código"], b["Descrição"], b["Fórmula sugerida"]] for b in mt["bases"].values()]),
        "aliquotas": tab(["Código", "Descrição", "Tipo", "Valor"],
                         [[a["Código"], a["Descrição"], a["Tipo"], a["Valor"]] for a in mt["aliqs"].values()]),
        "aliquotas_ncm": tab(["Tributo", "Chave usada", "NCM", "Origem", "UF origem", "UF destino", "CEST",
                              "Alíquota %", "MVA % / Alíq. inter %", "Itens"],
                             [[l["Tributo"], l["Chave usada"], l["NCM"], l["Origem"], l["UF origem"], l["UF destino"],
                               l["CEST"], l["Alíquota %"], l["MVA % / Alíq. interestadual %"], l["Itens"]]
                              for l in mt["linhas_ncm"]]),
        "escrituracao": tab(["Código", "Tributo", "CSTCAB", "CST", "INCIDE", "Incidência", "STOTNF", "Ação na nota",
                             "PERDIF", "cClassTrib", "CJ2_CCT", "Observação"],
                            [[e["Código"], e["Tributo"], e["CJ2_CSTCAB"], e["CJ2_CST"], e["CJ2_INCIDE"],
                              e.get("Incidência", ""), e["CJ2_STOTNF"], e.get("Ação na nota", ""), e["CJ2_PERDIF"],
                              e["CJ2_CSTCCT (cClassTrib)"], e["CJ2_CCT"], e["Observação"]] for e in mt["escs"].values()]),
        "produtos": tab(["Produto", "Descrição", "NCM", "Origem", "CEST", "Itens", "Perfis de produto", "Classe IPI",
                         "Classe PIS/COF"],
                        [[p, i[0], i[1], i[2], i[3], qtd_prod[p], ", ".join(sorted(perfis_do_prod.get(p, ()))),
                          an["modas"]["IPI"].get(p, ""), an["modas"]["PC"].get(p, "")]
                         for p, i in sorted(an["prod_info"].items(), key=lambda x: -qtd_prod[x[0]])]),
        "clientes": tab(["CNPJ/CPF", "Nome", "UF", "Tipo no XML", "Notas"],
                        [[k, v[0], v[1], v[2], v[3]] for k, v in sorted(clientes.items(), key=lambda x: -x[1][3])]),
    }


def api_validacoes(_):
    _exige_gerado()
    an, mt = EST["an"], EST["mt"]
    v = mt["validacao"]
    tot = sum(v.values()) or 1
    conf = []
    for ci, (t, b, cnt) in enumerate(an["conflitos"]):
        u = an["univ"][t]
        dims = [("todos" if b[i] == frozenset(u[i]) or b[i] in (frozenset({"*"}), frozenset({"*§*"}))
                 else ", ".join(sorted(x.replace("§", " | ") for x in b[i]))[:160]) for i in range(4)]
        menor = cnt.most_common()[-1][0]
        ex = next((an["exemplo"][(t, c, menor)] for c in an["regras_trib"][t][1]
                   if all(c[i] in b[i] for i in range(4)) and (t, c, menor) in an["exemplo"]), "")
        trat = [{"tratamento": "Tributo ausente" if tr is None else
                 f"CST {tr[0][1]} · base {tr[1][0]} · " + ("alíquota por NCM" if tr[2] == "NCM" else f"{g._fmt(tr[3][0])}%")
                 + (f" · cBenef {tr[4]}" if len(tr) > 4 and tr[4] else ""), "itens": q} for tr, q in cnt.most_common()]
        conf.append({"idx": ci, "tributo": g.TRIBUTOS[t][0], "produto": dims[0], "participante": dims[1], "operacao": dims[2],
                     "uf": dims[3], "tratamentos": trat, "itens": sum(cnt.values()), "exemplo": ex})
    conf.sort(key=lambda x: -x["itens"])
    return {"resumo": {"correto_pct": round((v["ok"] + v["sem_tributo_ok"]) / tot * 100, 2), "ok": v["ok"],
                       "sem_tributo_ok": v["sem_tributo_ok"], "duplicidades": v["duplicada"],
                       "conflitos_itens": v["tratamento_diferente"] + v["sem_regra"] + v["aciona_indevido"],
                       "conflitos_cenarios": len(an["conflitos"]), "total": tot},
            "regras_negocio": [{"tributo": st["regra"][0], "quando": st["regra"][1], "entao": st["regra"][2],
                                "observacao": st["regra"][3], "aplicou": st["aplicou"], "divergiu": st["divergiu"],
                                "exemplo": st["exemplo"], "erro": st["erro"]} for st in an["regras_negocio"]],
            "conflitos": conf, "alertas_codigos": mt.get("alertas_codigos", []),
            "cfop_invalidos": an.get("cfop_invalidos", []),
            "regras_revisar": [_regra_json(r) for r in mt["regras"] if r.get("_status") == "Revisar"]}


# ── dicionário de códigos (dicas ao passar o mouse) ──────────────────────────
_OPERANDOS = [("O:VAL_MERCADORIA", "valor da mercadoria"), ("O:FRETE", "frete"), ("O:SEGURO", "seguro"),
              ("O:DESPESAS", "despesas acessórias"), ("O:DESCONTO", "desconto"), ("O:VAL_II", "II"),
              ("O:VAL_PS2", "PIS"), ("O:VAL_CF2", "COFINS"), ("O:VAL_ICM_TRIBUTADO", "ICMS"),
              ("O:VAL_DIFAL", "DIFAL"), ("O:VAL_FECP", "FECP"), ("O:VAL_FCPDIF", "FECP do DIFAL"),
              ("O:VAL_IPI_TRIBUTADO", "IPI")]


def _humanizar(form, bases):
    if not form:
        return ""
    txt = form
    for cod, b in bases.items():                     # fórmula que referencia outra base
        if cod in txt and b.get("Fórmula sugerida") and cod != form:
            txt = txt.replace(cod, "(" + b["Fórmula sugerida"] + ")")
    for op, nome in _OPERANDOS:
        txt = txt.replace(op, nome)
    return txt.replace(" - ", " − ").replace("×", "×")


def api_dicionario(_):
    _exige_gerado()
    mt = EST["mt"]
    d = {}

    def por(cod, texto):
        if cod:
            d[cod] = (d[cod] + "\n\n" + texto) if cod in d and texto not in d[cod] else texto
    for b in mt["bases"].values():
        comp = _humanizar(b.get("Fórmula sugerida", ""), mt["bases"])
        por(b["Código"], f"Base de cálculo (F27)\n{b['Descrição']}" + (f"\nCompõe: {comp}" if comp else ""))
    for a in mt["aliqs"].values():
        por(a["Código"], f"Alíquota (F28)\n{a['Descrição']}\n{a['Tipo']}" + (f": {a['Valor']}%" if a.get("Valor") else
                         " — a alíquota vem da tabela por NCM, origem e UF"))
    for e in mt["escs"].values():
        por(e["Código"], f"Escrituração (CJ2) · {e['Tributo']} · CST {e['CJ2_CST']}\nINCIDE {e['CJ2_INCIDE']}: "
                         f"{e.get('Incidência', '')}\nSTOTNF {e['CJ2_STOTNF']}: {e.get('Ação na nota', '')}"
                         + (f"\nDiferimento: {e['CJ2_PERDIF']}%" if e.get("CJ2_PERDIF") else "")
                         + (f"\ncClassTrib: {e['CJ2_CSTCCT (cClassTrib)']}" if e.get("CJ2_CSTCCT (cClassTrib)") else ""))
    for p_ in mt["perf_prod"].values():
        por(p_["Código"], f"Perfil de produto\n{p_['Descrição']}\nClasses: {p_['Classes']}\n{_br(p_['Produtos'])} produto(s)")
    for p_ in mt["perf_part"].values():
        por(p_["Código"], f"Perfil de participante\n{p_['Descrição']}\nCritério: {p_['Critério sugerido']}")
    for p_ in mt["perf_od"].values():
        por(p_["Código"], f"Perfil de origem/destino\n{p_['Descrição']}\nUF origem {p_['UF origem']} → {p_['UFs destino']}")
    for p_ in mt["perf_op"].values():
        por(p_["Código"], f"Perfil de operação\n{p_['Descrição']}\nCFOPs: {p_['CFOPs']}\nTipos: {p_['Tipos de operação']}")
    for f, (c, desc) in g.TIPOS_OPERACAO.items():
        por(c, f"Tipo de operação\n{c} — {desc}\nFinalidade: {f}")
    for r in mt["regras"]:
        por(r["F2B_REGRA"], f"Regra fiscal (F2B) · {r['F2B_TRIB']}\n{r['F2B_DESC']}\n{_br(r['Itens'])} item(ns) nos XMLs")
    por(g.ALIQ_ZERO[0], "Alíquota zero: o imposto não é calculado")
    por("BASZER", "Base zero: o imposto não tem base (não destacado)")
    return d


# ── tipos de operação: de-para e finalidade por cliente ──────────────────────
def _bloco_tipos():
    L = ["## Tipos de operação", "", "De-para da finalidade para o tipo de operação usado nos perfis de operação.", "",
         "| Finalidade | Tipo de operação | Descrição |", "|---|---|---|"]
    L += [f"| {f} | {c} | {g._md(d)} |" for f, (c, d) in g.TIPOS_OPERACAO.items()]
    return "\n".join(L) + "\n"


def _bloco_clientes():
    L = ["## Finalidade por cliente", "",
         "Clientes cuja finalidade não segue o indFinal da nota (ex.: revenda para insumo = INSUMO → V5).", "",
         "| CNPJ/CPF | Finalidade | Observação |", "|---|---|---|"]
    L += [f"| {doc} | {f} | {g._md(g.OBS_CLIENTE.get(doc, ''))} |" for doc, f in g.FINALIDADE_CLIENTE.items()]
    return "\n".join(L) + "\n"


def _substituir_secao(texto, titulo, bloco, antes_de="## Grupos de operação"):
    m = re.search(r"^## " + re.escape(titulo) + r"\s*$.*?(?=^## |\Z)", texto, flags=re.M | re.S)
    if m:
        return texto[:m.start()] + bloco + "\n" + texto[m.end():]
    i = texto.find(antes_de)
    return (texto[:i] + bloco + "\n" + texto[i:]) if i >= 0 else texto + "\n" + bloco


def api_tipos(_):
    an = EST["an"]
    fins = Counter()
    nomes = {}
    if an:
        for d in an["validos"]:
            nomes[d["dest"]] = (d["dest_nome"], d["uf_dest"], d["tipo"])
            for it in d["itens"]:
                _, grupo, fin = g.operacao(it["cfop"], d)
                fins[(grupo, fin)] += 1
    clientes_xml = {}
    if an:
        cont = Counter(d["dest"] for d in an["validos"] if d["dest"])
        clientes_xml = [{"doc": k, "nome": nomes[k][0], "uf": nomes[k][1], "tipo": nomes[k][2], "notas": q}
                        for k, q in cont.most_common(5000)]
    return {"depara": [{"finalidade": f, "codigo": c, "descricao": d} for f, (c, d) in g.TIPOS_OPERACAO.items()],
            "clientes": [{"doc": doc, "finalidade": f, "obs": g.OBS_CLIENTE.get(doc, ""),
                          "nome": nomes.get(doc, ("", "", ""))[0]} for doc, f in g.FINALIDADE_CLIENTE.items()],
            "encontradas": [{"grupo": gr, "finalidade": f, "itens": q,
                             "tipo": g.TIPOS_OPERACAO.get(f, ("", ""))[0]} for (gr, f), q in fins.most_common()],
            "clientes_xml": clientes_xml}


def api_salvar_tipos(corpo):
    dep = [x for x in corpo.get("depara", []) if (x.get("finalidade") or "").strip()]
    cli = [x for x in corpo.get("clientes", []) if re.sub(r"\D", "", x.get("doc") or "")]
    g.TIPOS_OPERACAO.clear()
    for x in dep:
        g.TIPOS_OPERACAO[x["finalidade"].strip().upper()] = ((x.get("codigo") or "").strip().upper(),
                                                            (x.get("descricao") or "").strip())
    g.FINALIDADE_CLIENTE.clear()
    g.OBS_CLIENTE.clear()
    for x in cli:
        doc = re.sub(r"\D", "", x["doc"])
        g.FINALIDADE_CLIENTE[doc] = (x.get("finalidade") or "").strip().upper()
        g.OBS_CLIENTE[doc] = (x.get("obs") or "").strip()
    with open(g.ARQ_PADROES, encoding="utf-8") as f:
        texto = f.read()
    texto = _substituir_secao(texto, "Tipos de operação", _bloco_tipos())
    texto = _substituir_secao(texto, "Finalidade por cliente", _bloco_clientes())
    return api_salvar_padroes({"texto": texto})


# ── regime dos clientes (Simples Nacional) ─────────────────────────────────────
ARQ_REGIME = os.path.join(AQUI, "regime_clientes.csv")
ARQ_CORRECOES = os.path.join(AQUI, "correcoes.json")
_SIMPLES = {"S", "SIM", "1", "X", "TRUE", "VERDADEIRO", "SIMPLES", "SIMPLES NACIONAL", "OPTANTE", "ME", "EPP", "MEI",
            "OPTANTE PELO SIMPLES", "SN"}
_NORMAL = {"N", "NAO", "NÃO", "2", "0", "FALSE", "FALSO", "NORMAL", "REGIME NORMAL", "LUCRO REAL", "LUCRO PRESUMIDO",
           "NAO OPTANTE", "NÃO OPTANTE", "RN"}


def _carregar_regime():
    g.REGIME_CLIENTE.clear()
    if os.path.isfile(ARQ_REGIME):
        with open(ARQ_REGIME, encoding="utf-8-sig") as f:
            for l in csv.reader(f, delimiter=";"):
                if len(l) >= 2 and l[0].isdigit():
                    g.REGIME_CLIENTE[l[0]] = l[1]


def _salvar_regime():
    with open(ARQ_REGIME, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["CNPJ", "REGIME"])
        for k, v in sorted(g.REGIME_CLIENTE.items()):
            w.writerow([k, v])


def _ler_xlsx(dados):
    """Leitor mínimo de XLSX (primeira planilha), sem bibliotecas externas."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        comp = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
                comp.append("".join(t.text or "" for t in si.iter("{%s}t" % ns["m"])))
        folhas = sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml"))
        if not folhas:
            return []
        linhas = []
        for row in ET.fromstring(z.read(folhas[0])).iter("{%s}row" % ns["m"]):
            vals = {}
            for c in row.findall("m:c", ns):
                ref = re.match(r"([A-Z]+)", c.get("r", "A")).group(1)
                col = 0
                for ch in ref:
                    col = col * 26 + ord(ch) - 64
                v = c.find("m:v", ns)
                if c.get("t") == "s" and v is not None:
                    txt = comp[int(v.text)]
                elif c.get("t") == "inlineStr":
                    txt = "".join(t.text or "" for t in c.iter("{%s}t" % ns["m"]))
                else:
                    txt = v.text if v is not None else ""
                    if txt and re.fullmatch(r"\d+\.0+", txt):
                        txt = txt.split(".")[0]
                    elif txt and re.fullmatch(r"\d+(\.\d+)?E\+\d+", txt, re.I):
                        txt = str(int(float(txt)))
                vals[col - 1] = txt
            if vals:
                linhas.append([vals.get(i, "") for i in range(max(vals) + 1)])
        return linhas


def _ler_planilha(nome, dados):
    if nome.lower().endswith((".xlsx", ".xlsm")):
        return _ler_xlsx(dados)
    txt = dados.decode("utf-8-sig", errors="replace")
    if txt.count("\ufffd") > 3:
        txt = dados.decode("latin-1")
    amostra = txt[:4000]
    sep = max((";", ",", "\t", "|"), key=amostra.count)
    return [l for l in csv.reader(io.StringIO(txt), delimiter=sep)]


def _interpretar_regime(linhas):
    """Descobre a coluna do CNPJ e a do regime (pelo cabeçalho ou pelo conteúdo)."""
    if not linhas:
        raise ValueError("A planilha está vazia.")
    cab = [g._norm(x) for x in linhas[0]]
    i_doc = next((i for i, h in enumerate(cab) if any(k in h for k in ("CNPJ", "CGC", "CPF", "DOCUMENTO", "A1_CGC"))), None)
    i_reg = next((i for i, h in enumerate(cab) if any(k in h for k in ("SIMPLES", "REGIME", "OPTANTE", "SIMPNAC", "CRT"))), None)
    corpo = linhas[1:] if i_doc is not None or i_reg is not None else linhas
    if i_doc is None:
        conta = Counter(i for l in corpo[:200] for i, v in enumerate(l) if len(re.sub(r"\D", "", v)) in (11, 14))
        i_doc = conta.most_common(1)[0][0] if conta else None
    if i_reg is None:
        conta = Counter(i for l in corpo[:200] for i, v in enumerate(l) if g._norm(v) in _SIMPLES | _NORMAL and i != i_doc)
        i_reg = conta.most_common(1)[0][0] if conta else None
    if i_doc is None or i_reg is None:
        raise ValueError("Não encontrei as colunas de CNPJ e de regime. Use um cabeçalho como 'CNPJ' e 'SIMPLES' (S/N).")
    res, ign = {}, []
    for l in corpo:
        if len(l) <= max(i_doc, i_reg):
            continue
        doc = re.sub(r"\D", "", l[i_doc])
        v = g._norm(l[i_reg])
        if len(doc) in (12, 13):
            doc = doc.zfill(14)
        if len(doc) == 10:
            doc = doc.zfill(11)
        if not doc:
            continue
        if v in _SIMPLES or v.startswith("SIMPLES") or v.startswith("OPTANTE"):
            res[doc] = "SIMPLES"
        elif v in _NORMAL or v.startswith(("NAO", "NORMAL", "LUCRO")):
            res[doc] = "NORMAL"
        else:
            ign.append(f"{l[i_doc]} = '{l[i_reg]}'")
    return res, {"coluna_cnpj": (linhas[0][i_doc] if corpo is not linhas else f"coluna {i_doc + 1}"),
                 "coluna_regime": (linhas[0][i_reg] if corpo is not linhas else f"coluna {i_reg + 1}"),
                 "ignoradas": ign[:20], "total_ignoradas": len(ign)}


def _regenerar():
    if EST["cnpj"] and not EST["status"]["tarefa"]:
        o = EST["opcoes"]
        _em_segundo_plano("gerando cenários", lambda: _gerar(EST["cnpj"], o["agrupar"], o["separar"], o.get("aliq_ncm")))
        return True
    return False


def api_regime(_):
    clientes = Counter()
    nomes = {}
    if EST["an"]:
        for d in EST["an"]["validos"]:
            if d["dest"] and d["tipo"].startswith("PJ"):
                clientes[d["dest"]] += 1
                nomes[d["dest"]] = (d["dest_nome"], d["uf_dest"], d["tipo"])
    reg = g.REGIME_CLIENTE
    com = [k for k in clientes if k in reg]
    sem = [k for k, _ in clientes.most_common() if k not in reg]
    lista = sorted(reg.items(), key=lambda kv: -clientes.get(kv[0], 0))
    return {"total": len(reg), "simples": sum(1 for v in reg.values() if v == "SIMPLES"),
            "normal": sum(1 for v in reg.values() if v == "NORMAL"),
            "clientes_xml": len(clientes), "cobertos": len(com),
            "notas_cobertas": sum(clientes[k] for k in com), "notas_pj": sum(clientes.values()),
            "lista": [[k, v, nomes.get(k, ("", "", ""))[0], nomes.get(k, ("", "", ""))[1], clientes.get(k, 0)]
                      for k, v in lista[:3000]],
            "sem_regime": [[k, nomes[k][0], nomes[k][1], nomes[k][2], clientes[k]] for k in sem[:300]],
            "arquivo": ARQ_REGIME}


def _receber_regime(corpo, nome, modo):
    novos, info = _interpretar_regime(_ler_planilha(nome, corpo))
    if modo == "substituir":
        g.REGIME_CLIENTE.clear()
    g.REGIME_CLIENTE.update(novos)
    _salvar_regime()
    info.update(lidos=len(novos), total=len(g.REGIME_CLIENTE), regerando=_regenerar())
    return info


def api_limpar_regime(_):
    g.REGIME_CLIENTE.clear()
    if os.path.isfile(ARQ_REGIME):
        os.remove(ARQ_REGIME)
    return {"regerando": _regenerar()}


# ── correções de XML ────────────────────────────────────────────────────────────
def _carregar_correcoes():
    g.CORRECOES.clear()
    if os.path.isfile(ARQ_CORRECOES):
        with open(ARQ_CORRECOES, encoding="utf-8") as f:
            g.CORRECOES.extend(json.load(f))


def _salvar_correcoes():
    with open(ARQ_CORRECOES, "w", encoding="utf-8") as f:
        json.dump(g.CORRECOES, f, ensure_ascii=False, indent=1)


def _linha_item(an, chave, n):
    for d, it, tr in an["linhas"]:
        if d["chave"] == chave and n <= len(d["itens"]) and d["itens"][n - 1] is it:
            return d, it, tr
    return None


def _retrato_item(chave, n):
    """Cenário e regras que um item aciona na análise atual (para o 'antes → depois')."""
    an, mt = EST["an"], EST["mt"]
    x = _linha_item(an, chave, n) if an else None
    if not x:
        return None
    d, it, tr = x
    regras = {}
    for t in g.ORDEM_TRIB:
        if t in tr and t in mt["cel_regra"]:
            cl = g.celula(t, d, it, an["modas"], an["separar"] and g.TRIBUTOS[t][5] == "ORIG")
            regras[g.TRIBUTOS[t][0]] = mt["cel_regra"][t].get(cl, "")
    b = tr.get("ICMS", (None, ("", "", ""), None, ""))[1][0] if "ICMS" in tr else ""
    return {"cfop": it["cfop"], "cst": it["cst"], "base_icms": b, "cst_ipi": it["cst_ipi"], "cst_pis": it["cst_pis"],
            "cst_cof": it["cst_cof"], "cbenef": it.get("cbenef", ""), "orig": it["orig"],
            "cst_ibs": it.get("cst_ibs", ""), "cclass": it.get("cclass", ""),
            "bases": {g.TRIBUTOS[t][0]: tr[t][1][0] for t in tr},
            "natureza": g.operacao(it["cfop"], d)[0], "finalidade": g.operacao(it["cfop"], d)[2], "regras": regras}


def _desc_trat(tr):
    if tr is None:
        return "Tributo ausente no XML"
    esc, base, modo, al, cb, grupo = tr
    return (f"CST {esc[1]} · base {base[0]} · " + ("alíquota por NCM" if modo == "NCM" else f"{g._fmt(al[0])}%")
            + (f" · cBenef {cb}" if cb else "") + (f" · {grupo}" if grupo else ""))


# campos que cada tributo mostra e permite corrigir na tela de divergências: (chave da correção, rótulo)
def _campos_tributo(t):
    base = ("base_ICMS" if t == "ICMS" else f"base_{t}", "Base")
    if t == "ICMS":
        return [("cfop", "CFOP"), ("cst", "CST ICMS"), base, ("cbenef", "cBenef"), ("orig", "Origem")]
    if t == "IPI":
        return [("cfop", "CFOP"), ("cst_ipi", "CST IPI"), base]
    if t == "PIS":
        return [("cfop", "CFOP"), ("cst_pis", "CST PIS"), base]
    if t == "COF":
        return [("cfop", "CFOP"), ("cst_cof", "CST COFINS"), base]
    if t in g.FAMILIA_IBS:
        return [("cfop", "CFOP"), ("cst_ibs", "CST IBS/CBS"), ("cclass", "cClassTrib"), base]
    return [("cfop", "CFOP"), ("cst", "CST ICMS"), base, ("orig", "Origem")]   # ST, DIFAL, FECP


def _valor_item(t, campo, d, it, tr):
    if campo.startswith("base_"):
        return tr[t][1][0] if t in tr else ""
    if campo.startswith("aliq_"):
        return g._fmt(tr[t][2][0]) if t in tr else ""
    return str(g.valor_campo(d, it, campo))


def _cmp(campo, v):
    """Valor usado para comparar com a regra: o CFOP compara pelo equivalente (5949 = 6949; 6108 = x102)."""
    return g.cfop_base(v) if campo == "cfop" else v


CAMPOS_CENARIO = {"cfop", "orig"}     # diferença de cenário (regra faltando), não erro de tratamento


def api_divergencias(q):
    _exige_gerado()
    an, mt = EST["an"], EST["mt"]
    cod = (q.get("regra") or [""])[0]
    idx = (q.get("conflito") or [""])[0]
    if cod:
        r = next((x for x in mt["regras"] if x["F2B_REGRA"] == cod), None)
        if not r:
            raise LookupError(f"Regra {cod} não encontrada.")
        t, caixa, ref = r["_t"], r["_b"], r["_trat"]
        titulo = f"{cod} · {r['F2B_DESC']}"
    else:
        t, caixa, cnt = an["conflitos"][int(idx)]
        ref = cnt.most_common(1)[0][0]
        titulo = f"Conflito de {g.TRIBUTOS[t][1]}"
    campos = _campos_tributo(t) + [(f"aliq_{t}", "Alíquota %")]
    grupos = g.itens_por_tratamento(an, t, caixa)

    def mais_comum(itens, campo):
        c = Counter(_valor_item(t, campo, d, it, tr) for d, it, n, tr in itens)
        v, qv = c.most_common(1)[0]
        return v, qv == len(itens)

    saida = []
    for tr_g, itens in sorted(grupos.items(), key=lambda kv: (kv[0] != ref, -len(kv[1]))):
        amostra = []
        for d, it, n, tr in itens[:80]:
            al = tr[t][2][0] if t in tr else None
            amostra.append({"chave": d["chave"], "nf": d["num"], "n": n, "cprod": it["cprod"], "xprod": it["xprod"][:60],
                            "ncm": it["ncm"], "uf": d["uf_dest"], "tipo": d["tipo"], "dest": d["dest"],
                            "dest_nome": d["dest_nome"][:40], "corrigido": bool(it.get("_corrigido")),
                            "aliq": "" if al is None else g._fmt(al) + "%",
                            "vals": {c: _valor_item(t, c, d, it, tr) for c, _ in campos},
                            "cmp": {c: _cmp(c, _valor_item(t, c, d, it, tr)) for c, _ in campos}})
        valores = {c: mais_comum(itens, c)[0] for c, _ in campos}
        valores_cmp = {c: Counter(_cmp(c, _valor_item(t, c, d, it, tr)) for d, it, n, tr in itens).most_common(1)[0][0]
                       for c, _ in campos}
        fam = g.TRIBUTOS[t][5]
        def valor_seg(dim, d, it):
            if dim == "cfop":
                return g.cfop_base(it["cfop"])
            if dim == "classe":
                return an["modas"][fam].get(it["cprod"], "") if fam != "ORIG" else \
                    an["modas"]["ORIG"].get(it["cprod"], "")
            if dim == "origem":
                return g.ORIGEM_GRUPO.get(it["orig"], "N")
            if dim == "participante":
                return g.participante_de(d)
            return d["uf_dest"]
        seg_vals = {}
        for dim in g.DIM_SEGREGACAO:
            c = Counter(valor_seg(dim, d, it) for d, it, n, tr in itens)
            seg_vals[dim] = set(c)
        for campo in g.CAMPOS_EXCECAO:
            seg_vals["exc_" + campo] = {(d["dest"] if campo == "dest" else it.get(campo, "")) for d, it, n, tr in itens}
        comuns = {}
        for campo in ("cfop", "cfop_base", "cst", "cst_ipi", "cst_pis", "cst_cof", "cst_ibs", "cclass", "cbenef", "orig", "uf",
                      "tipo", "ncm", "cprod", "dest"):
            c = Counter(str(g.valor_campo(d, it, campo)) for d, it, n, tr in itens)
            v, qv = c.most_common(1)[0]
            comuns[campo] = {"valor": v, "todos": qv == len(itens)}
        saida.append({"_seg": seg_vals, "valores_cmp": valores_cmp, "tratamento": _desc_trat(tr_g),
                      "referencia": tr_g == ref, "itens": len(itens),
                      "valores": valores, "amostra": amostra, "comuns": comuns,
                      "aliq": (g._fmt(tr_g[3][0]) + "%") if tr_g and tr_g[2] == "F" else ("por NCM" if tr_g else ""),
                      "itens_ids": [[d["chave"], n] for d, it, n, tr in itens]})
    # critério que separa o grupo divergente do grupo da regra (valores sem interseção) e ainda não é segregado
    ja = g.segregacoes_de(t)
    ref_g = next((x for x in saida if x["referencia"]), None)
    for x in saida:
        x["segregar"], x["excecao"] = [], []
        if ref_g and x is not ref_g:
            for campo, (rotulo, _) in g.CAMPOS_EXCECAO.items():
                a, b = x["_seg"]["exc_" + campo], ref_g["_seg"]["exc_" + campo]
                if a and not (a & b) and len(a) <= 60 and "" not in a:
                    x["excecao"].append({"campo": campo, "rotulo": rotulo, "valores": sorted(a)})
            for dim, (rotulo, _) in g.DIM_SEGREGACAO.items():
                a, b = x["_seg"][dim], ref_g["_seg"][dim]
                if dim not in ja and a and b and not (a & b):
                    x["segregar"].append({"dim": dim, "rotulo": rotulo, "valores": sorted(a)[:4], "ref": sorted(b)[:4]})
    for x in saida:
        x.pop("_seg", None)
    bases = sorted({b["Código"] for b in mt["bases"].values()} | {c for l in g.BASES.values() for c, *_ in l})
    descr_bases = {b["Código"]: b["Descrição"] for b in mt["bases"].values()}
    return {"titulo": titulo, "tributo": g.TRIBUTOS[t][0], "tributo_nome": g.TRIBUTOS[t][1], "chave_tributo": t,
            "campos": [{"campo": c, "rotulo": r_, "tipo": "cenario" if c in CAMPOS_CENARIO else "tratamento"}
                       for c, r_ in campos], "grupos": saida, "bases": bases,
            "descr_bases": descr_bases}


def api_correcoes(_):
    an = EST["an"]
    st = an["correcoes_stats"] if an else {}
    lista = []
    for c in g.CORRECOES:
        ex = c.get("exemplo")
        depois = _retrato_item(*ex) if ex and an else None
        lista.append(dict(c, aplicados=st.get(c["id"], 0), depois=depois))
    seg = [{"i": i, "tributo": x["tributo"], "tributo_nome": g.TRIBUTOS.get(x["tributo"], ("", x["tributo"]))[1],
            "familia": [g.TRIBUTOS[f][1] for f in g._familia(x["tributo"]) if f in g.TRIBUTOS],
            "dim": x["dim"], "rotulo": g.DIM_SEGREGACAO[x["dim"]][0], "obs": x.get("obs", "")}
           for i, x in enumerate(g.SEGREGACOES)]
    exc = [{"id": x["id"], "tributo": x["tributo"], "tributo_nome": g.TRIBUTOS.get(x["tributo"], ("", x["tributo"]))[1],
            "familia": [g.TRIBUTOS[f][1] for f in g._familia(x["tributo"]) if f in g.TRIBUTOS],
            "campo": x["campo"], "rotulo": g.CAMPOS_EXCECAO[x["campo"]][0], "valores": x["valores"], "obs": x.get("obs", "")}
           for x in g.EXCECOES]
    return {"correcoes": lista, "segregacoes": seg, "excecoes": exc, "arquivo": ARQ_CORRECOES}


def api_nova_correcao(corpo):
    if corpo.get("lote"):                         # várias decisões de uma vez: um único reprocessamento
        ids = [_criar_correcao(c) for c in corpo["lote"]]
        _salvar_correcoes()
        _conhecimento_decisoes([c for c in corpo["lote"] if (c.get("filtro") or {}).get("cfop_base")])
        return {"ids": ids, "regerando": _regenerar()}
    cid = _criar_correcao(corpo)
    _salvar_correcoes()
    return {"id": cid, "regerando": _regenerar()}


def _conhecimento_decisoes(decisoes):
    """Decisão que vale para todo um CFOP é conhecimento reaproveitável: registra no .md."""
    if not decisoes:
        return
    nomes = {"cst": "CST ICMS", "cbenef": "cBenef", "cst_ipi": "CST IPI", "cst_pis": "CST PIS", "cst_cof": "CST COFINS",
             "cst_ibs": "CST IBS/CBS", "cclass": "cClassTrib", "orig": "Origem", "cfop": "CFOP"}
    with open(g.ARQ_PADROES, encoding="utf-8") as f:
        texto = f.read()
    for c in decisoes:
        f_ = c["filtro"]
        cb = f_.get("cfop_base", "")
        cfops = f"{'5' + cb[1:]}/{'6' + cb[1:]}" if cb.startswith("x") else cb
        quando = " e ".join(f"{nomes.get(k, k)} {v}" for k, v in f_.items() if k != "cfop_base")
        vira = ", ".join(f"{nomes.get(k) or ('Base' if k.startswith('base_') else 'Alíquota' if k.startswith('aliq_') else k)} "
                         f"{'(remover)' if v == '-' else v}" for k, v in c["alteracoes"].items())
        linha = (f"| {time.strftime('%d/%m/%Y')} | {g._md(c.get('origem', ''))} | "
                 f"{g._md(f'CFOP {cfops} com {quando}')} | {g._md(f'Tratar como: {vira}')} | {g._md(str(EST['cnpj'] or ''))} |")
        texto = _registrar_conhecimento(texto, linha)
    with open(g.ARQ_PADROES, "w", encoding="utf-8") as f:
        f.write(texto)
    _, EST["avisos_padroes"] = g.carregar_padroes()


def _criar_correcao(corpo):
    alt = {k: str(v).strip() for k, v in (corpo.get("alteracoes") or {}).items()
           if (k in g.CAMPOS_CORRIGIVEIS or k.startswith(("base_", "aliq_"))) and str(v).strip()}
    if not alt:
        raise ValueError("Informe pelo menos um campo corrigido.")
    itens = corpo.get("itens") or []
    filtro = {k: str(v) for k, v in (corpo.get("filtro") or {}).items() if str(v) != ""}
    if not itens and not filtro:
        raise ValueError("Escolha os itens ou as características que a correção deve alcançar.")
    ex = corpo.get("exemplo") or (itens[0] if itens else None)
    c = {"id": f"c{int(time.time() * 1000)}", "cnpj": EST["cnpj"] or "", "itens": [] if filtro else itens,
         "filtro": filtro, "alteracoes": alt, "obs": (corpo.get("obs") or "").strip(),
         "origem": corpo.get("origem") or "", "exemplo": ex, "antes": _retrato_item(*ex) if ex else None,
         "criada_em": time.strftime("%d/%m/%Y %H:%M"), "qtd_prevista": int(corpo.get("qtd") or 0)}
    c["id"] += f"{len(g.CORRECOES)}"
    g.CORRECOES.append(c)
    return c["id"]


def api_remover_correcao(corpo):
    antes = len(g.CORRECOES)
    g.CORRECOES[:] = [c for c in g.CORRECOES if c["id"] != corpo.get("id")]
    if len(g.CORRECOES) == antes:
        raise LookupError("Correção não encontrada.")
    _salvar_correcoes()
    return {"regerando": _regenerar()}


# ── segregações: "está correto, separe em outra regra" ─────────────────────────
def _bloco_segregacoes():
    L = ["## Segregações", "",
         "Cenários que pareciam divergentes mas são legítimos: o tributo passa a separar regras pelo critério.",
         "Critérios: cfop, classe, origem, participante, uf. Vale para a família (IBS/CBS juntos; PIS/COFINS juntos).", "",
         "| Tributo | Separar por | Observação |", "|---|---|---|"]
    L += [f"| {x['tributo']} | {x['dim']} | {g._md(x.get('obs', ''))} |" for x in g.SEGREGACOES]
    return "\n".join(L) + "\n"


def _registrar_conhecimento(texto, linha):
    """Acrescenta uma linha à tabela '## Conhecimento aprendido' (cria a seção se não existir)."""
    m = re.search(r"^## Conhecimento aprendido\s*$.*?(?=^## |\Z)", texto, flags=re.M | re.S)
    if m:
        sec = m.group(0).rstrip("\n") + "\n" + linha + "\n"
        return texto[:m.start()] + sec + "\n" + texto[m.end():]
    bloco = ("## Conhecimento aprendido\n\n"
             "Decisões confirmadas pelo usuário durante as análises (artefatos de conhecimento para outras empresas).\n"
             "Informativo: o que o motor aplica está em Segregações e Regras de negócio.\n\n"
             "| Data | Tributo | Situação observada | Decisão | Origem |\n|---|---|---|---|---|\n" + linha + "\n\n")
    i = texto.find("## Tributos")
    return (texto[:i] + bloco + texto[i:]) if i >= 0 else texto + "\n" + bloco


def _gravar_segregacoes(linha_conhecimento=None):
    with open(g.ARQ_PADROES, encoding="utf-8") as f:
        texto = f.read()
    texto = _substituir_secao(texto, "Segregações", _bloco_segregacoes())
    if linha_conhecimento:
        texto = _registrar_conhecimento(texto, linha_conhecimento)
    return api_salvar_padroes({"texto": texto})


def api_nova_segregacao(corpo):
    t = corpo.get("tributo")
    if t not in g.TRIBUTOS:
        t = g._chave_trib(t or "")
    dim = (corpo.get("dim") or "").lower()
    if not t or dim not in g.DIM_SEGREGACAO:
        raise ValueError("Tributo ou critério inválido.")
    if dim in g.segregacoes_de(t):
        raise ValueError("Esse tributo já separa regras por esse critério.")
    g.SEGREGACOES.append({"tributo": t, "dim": dim, "obs": (corpo.get("obs") or "").strip()})
    k = corpo.get("conhecimento") or {}
    linha = None
    if k:
        fam = ", ".join(g.TRIBUTOS[f][1] for f in g._familia(t) if f in g.TRIBUTOS)
        rot = g.DIM_SEGREGACAO[dim][0]
        situacao = (f"{rot} {', '.join(k.get('valores', []))} ({k.get('grupo', '')}) e "
                    f"{rot} {', '.join(k.get('ref', []))} ({k.get('referencia', '')}) caíam na mesma regra")
        decisao = f"Cenários legítimos e diferentes: separar regras por {rot}"
        origem = f"{EST['cnpj'] or ''} · {k.get('origem', '')} · {_br(int(k.get('itens') or 0))} itens"
        linha = (f"| {time.strftime('%d/%m/%Y')} | {g._md(fam)} | {g._md(situacao)} | {g._md(decisao)} | "
                 f"{g._md(origem)} |")
    return _gravar_segregacoes(linha)


def api_remover_segregacao(corpo):
    i = int(corpo.get("i", -1))
    if not 0 <= i < len(g.SEGREGACOES):
        raise LookupError("Segregação não encontrada.")
    g.SEGREGACOES.pop(i)
    return _gravar_segregacoes()


# ── exceções: regra própria para clientes, produtos ou NCMs ─────────────────────
def _bloco_excecoes():
    L = ["## Exceções", "", "Regra própria para clientes, produtos ou NCMs específicos, quando nenhuma dimensão separa os itens.",
         "Campo: dest (cliente), cprod (produto) ou ncm. Valores separados por vírgula.", "",
         "| Tributo | Campo | Valores | Observação | Id |", "|---|---|---|---|---|"]
    L += [f"| {x['tributo']} | {x['campo']} | {', '.join(x['valores'])} | {g._md(x.get('obs', ''))} | {x['id']} |"
          for x in g.EXCECOES]
    return "\n".join(L) + "\n"


def _gravar_excecoes(linha_conhecimento=None):
    with open(g.ARQ_PADROES, encoding="utf-8") as f:
        texto = f.read()
    texto = _substituir_secao(texto, "Exceções", _bloco_excecoes(), antes_de="## Segregações")
    if linha_conhecimento:
        texto = _registrar_conhecimento(texto, linha_conhecimento)
    return api_salvar_padroes({"texto": texto})


def api_nova_excecao(corpo):
    t = corpo.get("tributo")
    if t not in g.TRIBUTOS:
        t = g._chave_trib(t or "")
    campo = corpo.get("campo")
    vals = [str(v).strip() for v in corpo.get("valores") or [] if str(v).strip()]
    if not t or campo not in g.CAMPOS_EXCECAO or not vals:
        raise ValueError("Tributo, campo ou valores inválidos.")
    usados = {x["id"] for x in g.EXCECOES}
    n = 1
    while f"E{n}" in usados:
        n += 1
    g.EXCECOES.append({"id": f"E{n}", "tributo": t, "campo": campo, "valores": vals, "obs": (corpo.get("obs") or "").strip()})
    k = corpo.get("conhecimento") or {}
    linha = None
    if k:
        fam = ", ".join(g.TRIBUTOS[f][1] for f in g._familia(t) if f in g.TRIBUTOS)
        rot = g.CAMPOS_EXCECAO[campo][0]
        situacao = f"{rot} {', '.join(vals[:5])} com {k.get('grupo', '')} × regra {k.get('referencia', '')}"
        origem = f"{EST['cnpj'] or ''} · {k.get('origem', '')}"
        linha = (f"| {time.strftime('%d/%m/%Y')} | {g._md(fam)} | {g._md(situacao)} | "
                 f"{g._md('Exceção: regra própria para o ' + rot)} | {g._md(origem)} |")
    return _gravar_excecoes(linha)


def api_remover_excecao(corpo):
    antes = len(g.EXCECOES)
    g.EXCECOES[:] = [x for x in g.EXCECOES if x["id"] != corpo.get("id")]
    if len(g.EXCECOES) == antes:
        raise LookupError("Exceção não encontrada.")
    return _gravar_excecoes()


# ── simulação: aplica uma decisão só em memória e compara com a análise atual ─────
_ESTADO_MOTOR = ("GRUPOS_DERIVADOS", "AGRUPAMENTOS", "CORRECOES", "SEGREGACOES", "EXCECOES", "REGRAS_NEGOCIO",
                 "CONHECIMENTO_EMPRESA")


def _foto_motor():
    return {k: copy.deepcopy(getattr(g, k)) for k in _ESTADO_MOTOR}


def _restaurar_motor(foto):
    for k, v in foto.items():
        obj = getattr(g, k)
        if isinstance(obj, list):
            obj[:] = v
        else:
            obj.clear()
            obj.update(v)


def _resumo_regra(r, mt):
    return {"cod": r["F2B_REGRA"], "trib": r["F2B_TRIB"], "desc": r["F2B_DESC"], "itens": r["Itens"],
            "pai": r.get("PAI", ""), "grupo": r.get("GRUPO_DERIVADO", ""), "status": r.get("_status", ""),
            "part": r["F2B_PERFPA"], "prod": r["F2B_PERFPR"],
            "d_part": mt["perf_part"].get(r["F2B_PERFPA"], {}).get("Descrição", ""),
            "d_prod": mt["perf_prod"].get(r["F2B_PERFPR"], {}).get("Descrição", "")}


_CAMPOS_CMP = (("F2B_DESC", "Descrição"), ("F2B_RBASE", "Base"), ("F2B_RALIQ", "Alíquota"), ("F2B_PEROD", "Orig/dest"),
               ("F2B_PERFPA", "Participante"), ("F2B_PERFOP", "Operação"), ("F2B_PERFPR", "Produto"),
               ("F2B_CODESC", "Escrituração"), ("cBenef", "cBenef"))
_CADS_CMP = (("perf_part", "Perfil de participante"), ("perf_prod", "Perfil de produto"), ("perf_od", "Origem/destino"),
             ("perf_op", "Perfil de operação"), ("bases", "Base (F27)"), ("aliqs", "Alíquota (F28)"),
             ("escs", "Escrituração (CJ2)"))


def _comparar(an0, mt0, mapa0, an1, mt1, mapa1):
    A = {r["F2B_REGRA"]: r for r in mt0["regras"]}
    B = {r["F2B_REGRA"]: r for r in mt1["regras"]}
    por_t = {}

    def bloco(trib):
        return por_t.setdefault(trib, {"tributo": trib, "antes": 0, "depois": 0, "novas": [], "removidas": [],
                                       "alteradas": [], "movimentos": []})
    for c, r in A.items():
        bloco(r["F2B_TRIB"])["antes"] += 1
        if c not in B:
            bloco(r["F2B_TRIB"])["removidas"].append(_resumo_regra(r, mt0))
    for c, r in B.items():
        b = bloco(r["F2B_TRIB"])
        b["depois"] += 1
        if c not in A:
            b["novas"].append(_resumo_regra(r, mt1))
        else:
            dif = [{"campo": rot, "antes": A[c].get(k, ""), "depois": r.get(k, "")} for k, rot in _CAMPOS_CMP
                   if str(A[c].get(k, "")) != str(r.get(k, ""))]
            if dif or A[c]["Itens"] != r["Itens"]:
                x = _resumo_regra(r, mt1)
                x.update(mudancas=dif, itens_antes=A[c]["Itens"])
                b["alteradas"].append(x)
    # itens que trocam de regra
    if mapa0 and mapa1 and len(mapa0) == len(mapa1):
        mov = defaultdict(Counter)
        for m0, m1 in zip(mapa0, mapa1):
            for t in set(m0) | set(m1):
                a, b_ = m0.get(t, ""), m1.get(t, "")
                if a != b_:
                    mov[g.TRIBUTOS[t][0]][(a or "sem regra", b_ or "sem regra")] += 1
        for trib, cnt in mov.items():
            bloco(trib)["movimentos"] = [{"de": a, "para": b_, "itens": q} for (a, b_), q in cnt.most_common(30)]
    cads = []
    for k, rot in _CADS_CMP:
        novos = sorted(set(mt1[k]) - set(mt0[k]))
        rem = sorted(set(mt0[k]) - set(mt1[k]))
        alt = sorted(c for c in set(mt0[k]) & set(mt1[k])
                     if mt0[k][c].get("Descrição") != mt1[k][c].get("Descrição"))
        if novos or rem or alt:
            cads.append({"cadastro": rot,
                         "novos": [{"cod": c, "desc": mt1[k][c].get("Descrição", ""),
                                    "criterio": mt1[k][c].get("Critério sugerido", "")} for c in novos],
                         "removidos": [{"cod": c, "desc": mt0[k][c].get("Descrição", "")} for c in rem],
                         "alterados": [{"cod": c, "antes": mt0[k][c].get("Descrição", ""),
                                        "depois": mt1[k][c].get("Descrição", "")} for c in alt]})

    def pct(mt):
        v = mt["validacao"]
        return round((v["ok"] + v["sem_tributo_ok"]) / (sum(v.values()) or 1) * 100, 2)
    tribs = [x for x in por_t.values() if x["novas"] or x["removidas"] or x["alteradas"] or x["movimentos"]]
    ordem = {g.TRIBUTOS[t][0]: i for i, t in enumerate(g.ORDEM_TRIB)}
    tribs.sort(key=lambda x: ordem.get(x["tributo"], 99))
    return {"tributos": tribs, "cadastros": cads,
            "resumo": {"regras_antes": len(A), "regras_depois": len(B),
                       "novas": sum(len(x["novas"]) for x in tribs), "removidas": sum(len(x["removidas"]) for x in tribs),
                       "alteradas": sum(len(x["alteradas"]) for x in tribs),
                       "correto_antes": pct(mt0), "correto_depois": pct(mt1),
                       "conflitos_antes": len(an0["conflitos"]), "conflitos_depois": len(an1["conflitos"]),
                       "duplicidades_depois": mt1["validacao"]["duplicada"]}}


def _simular(mudar):
    """Roda o motor com a mudança aplicada só em memória e devolve o antes → depois de todas as regras."""
    _exige_gerado()
    with TRAVA:
        if EST["status"]["tarefa"]:
            raise RuntimeError(f"Aguarde: {EST['status']['tarefa']} em andamento.")
        EST["status"]["tarefa"] = "simulando impacto"
    foto = _foto_motor()
    try:
        mudar()
        o = EST["opcoes"]
        an = g.analisar(EST["docs"], EST["canc"], EST["cnpj"], o["agrupar"], lambda s: None, o["separar"],
                        o.get("aliq_ncm"))
        mt = g.montar_matriz(an, _codigos_anteriores(EST["cnpj"]))
        _marcar_status_regras(an, mt)
        mapa = _mapa_itens(an, mt)
    finally:
        _restaurar_motor(foto)
        g.indexar_grupos(EST["cnpj"])
        with TRAVA:
            EST["status"]["tarefa"] = None
    res = _comparar(EST["an"], EST["mt"], EST.get("mapa_itens"), an, mt, mapa)
    EST["ultima_simulacao"] = res
    return res


# ── grupos derivados (clientes ou produtos informados na mão) ──────────────────
ARQ_GRUPOS = os.path.join(AQUI, "grupos_derivados.json")


def _carregar_grupos():
    g.GRUPOS_DERIVADOS.clear()
    if os.path.isfile(ARQ_GRUPOS):
        with open(ARQ_GRUPOS, encoding="utf-8") as f:
            g.GRUPOS_DERIVADOS.extend(json.load(f))
    g.indexar_grupos(EST["cnpj"])


def _salvar_grupos():
    with open(ARQ_GRUPOS, "w", encoding="utf-8") as f:
        json.dump(g.GRUPOS_DERIVADOS, f, ensure_ascii=False, indent=1)


def _ler_valores(tipo, valores):
    if isinstance(valores, str):
        valores = re.split(r"[\s,;|]+", valores)
    saida = []
    for v in valores or []:
        v = str(v).strip()
        if not v:
            continue
        if tipo == "participante":
            v = re.sub(r"\D", "", v)
            if len(v) in (12, 13):
                v = v.zfill(14)
            elif len(v) == 10:
                v = v.zfill(11)
            if not v:
                continue
        if v not in saida:
            saida.append(v)
    return saida


def _desc_trat_curto(tr):
    if tr is None:
        return "ausente"
    esc, base, modo, al, cb, grupo = tr
    return (f"CST {esc[1]} · base {base[0]} · " + ("alíq. NCM" if modo == "NCM" else f"{g._fmt(al[0])}%")
            + (f" · cBenef {cb}" if cb else ""))


def _abr(d):
    return "INTERNA" if d["uf_dest"] == d["uf_emit"] else ("EXTERIOR" if d["uf_dest"] == "EX" else "INTERESTADUAL")


def api_grupos(_):
    an = EST["an"]
    qtd = Counter()
    if an:
        for d, it, tr in an["linhas"]:
            gc, gp = g.grupo_cliente(d), g.grupo_produto(it)
            if gc:
                qtd[gc["id"]] += 1
            if gp:
                qtd[gp["id"]] += 1
    regras = Counter()
    if EST["mt"]:
        for r in EST["mt"]["regras"]:
            if r.get("GRUPO_DERIVADO"):
                regras[r["GRUPO_DERIVADO"]] += 1
    lista = []
    for gr in g.GRUPOS_DERIVADOS:
        x = dict(gr)
        x.update(itens=qtd.get(gr["id"], 0), regras=regras.get(gr["nome"], 0),
                 acoes={t: g.acao_grupo(gr, t) for t in g.ORDEM_TRIB})
        lista.append(x)
    return {"grupos": lista, "acoes": g.ACOES_GRUPO, "arquivo": ARQ_GRUPOS,
            "tributos": [{"chave": t, "trib": v[0], "nome": v[1]} for t, v in g.TRIBUTOS.items()]}


def _novo_grupo(corpo):
    tipo = "produto" if corpo.get("tipo") == "produto" else "participante"
    nome = re.sub(r"\s+", " ", str(corpo.get("nome") or "")).strip().upper()
    if not nome:
        raise ValueError("Dê um nome ao grupo (ex.: TRANSPORTADORA, TRADE).")
    valores = _ler_valores(tipo, corpo.get("valores"))
    if not valores:
        raise ValueError("Informe os CNPJs/CPFs ou os códigos de produto do grupo.")
    gid = corpo.get("id") or ""
    if not gid:
        usados = {x["id"] for x in g.GRUPOS_DERIVADOS}
        n = 1
        while f"G{n}" in usados:
            n += 1
        gid = f"G{n}"
    if any(x["nome"] == nome and x["id"] != gid for x in g.GRUPOS_DERIVADOS):
        raise ValueError(f"Já existe um grupo chamado {nome}.")
    outros = {v: x["nome"] for x in g.GRUPOS_DERIVADOS if x["id"] != gid and x.get("tipo") == tipo
              for v in x.get("valores", [])}
    repetidos = [v for v in valores if v in outros]
    if repetidos:
        raise ValueError(f"{len(repetidos)} valor(es) já estão em outro grupo (ex.: {repetidos[0]} em "
                         f"{outros[repetidos[0]]}). Cada cliente/produto pode estar em um só grupo.")
    tribs = {}
    for t, cfg in (corpo.get("tributos") or {}).items():
        if t in g.TRIBUTOS and (cfg or {}).get("acao") in g.ACOES_GRUPO:
            alc = {k: str(v).strip().upper() for k, v in (cfg.get("alcance") or {}).items()
                   if k in ("abrangencia", "grupo", "finalidade") and str(v).strip()}
            tribs[t] = {"acao": cfg["acao"], "alcance": alc}
    return {"id": gid, "tipo": tipo, "nome": nome,
            "sufixo": re.sub(r"[^A-Z0-9]", "", g._norm(corpo.get("sufixo") or nome))[:2],
            "codigo": re.sub(r"[^A-Z0-9]", "", g._norm(corpo.get("codigo") or ""))[:6],
            "valores": valores, "tributos": tribs, "obs": str(corpo.get("obs") or "").strip(),
            "cnpj": EST["cnpj"] or "", "criado_em": time.strftime("%d/%m/%Y %H:%M")}


def api_grupo_analisar(corpo):
    """Passo 2 do assistente: quem são os clientes/produtos, de qual perfil eles derivam e, por tributo,
    quais regras os atendem hoje, qual tratamento o XML trouxe e o que o programa sugere fazer."""
    _exige_gerado()
    an, mt, mapa = EST["an"], EST["mt"], EST.get("mapa_itens") or []
    tipo = "produto" if corpo.get("tipo") == "produto" else "participante"
    valores = _ler_valores(tipo, corpo.get("valores"))
    if not valores:
        raise ValueError("Informe os CNPJs/CPFs ou os códigos de produto do grupo.")
    alvo = set(valores)
    regras = {r["F2B_REGRA"]: r for r in mt["regras"]}
    achados, pais, nomes = Counter(), Counter(), {}
    por_t = defaultdict(lambda: {"regras": Counter(), "trat_grupo": Counter(), "g_tem": set(), "g_falta": set(),
                                 "itens": 0})

    def chave_cmp(d, it):      # o que comparar entre grupo e pai: mesmo produto (ou cliente) e mesma abrangência
        return ((it["cprod"] if tipo == "participante" else g.participante_de(d)), _abr(d))
    for idx, (d, it, tr) in enumerate(an["linhas"]):
        chave = d.get("dest", "") if tipo == "participante" else it["cprod"]
        if chave not in alvo:
            continue
        achados[chave] += 1
        if tipo == "participante":
            pais[g.participante_de(d)] += 1
            nomes[chave] = f"{d['dest_nome']} · {d['uf_dest']} · {g.participante_de(d)}"
        else:
            grp = g.ORIGEM_GRUPO.get(it["orig"], "N")
            pais[g.PERFIL_ORIGEM.get(grp, ("", f"ORIGEM {it['orig']}", ""))[1]] += 1
            nomes[chave] = f"{it['xprod'][:50]} · NCM {it['ncm']} · origem {it['orig']}"
        m = mapa[idx] if idx < len(mapa) else {}
        for t in g.ORDEM_TRIB:
            if t not in an["regras_trib"]:
                continue
            b = por_t[t]
            b["itens"] += 1
            trat = g.tratamento_item(an, t, d, it, tr)
            b["trat_grupo"][_desc_trat_curto(trat)] += 1
            if m.get(t):
                b["regras"][m[t]] += 1
            (b["g_tem"] if t in tr else b["g_falta"]).add(chave_cmp(d, it))
    # o pai: os demais clientes do mesmo tipo/regime (ou produtos da mesma origem), fora do grupo
    pai_tem = defaultdict(set)
    for d, it, tr in an["linhas"]:
        chave = d.get("dest", "") if tipo == "participante" else it["cprod"]
        if chave in alvo:
            continue
        comparavel = (g.participante_de(d) in pais) if tipo == "participante" else \
            (g.PERFIL_ORIGEM.get(g.ORIGEM_GRUPO.get(it["orig"], "N"), ("", "", ""))[1] in pais)
        if comparavel:
            for t in tr:
                pai_tem[t].add(chave_cmp(d, it))
    nao = [v for v in valores if v not in achados]
    tribs = []
    for t in g.ORDEM_TRIB:
        if t not in por_t:
            continue
        b = por_t[t]
        dm = g.DIMENSOES.get(t, g.DIM_PADRAO)
        usa = bool(dm["participante"] or "participante" in g.segregacoes_de(t)) if tipo == "participante" \
            else bool(dm["classe"] or dm["origem"] or {"classe", "origem"} & g.segregacoes_de(t))
        regs = [{"cod": c, "desc": regras[c]["F2B_DESC"] if c in regras else "", "itens": q,
                 "tratamento": _desc_trat_curto(regras[c]["_trat"]) if c in regras else "",
                 "perfil": regras[c]["F2B_PERFPA" if tipo == "participante" else "F2B_PERFPR"] if c in regras else ""}
                for c, q in b["regras"].most_common()]
        trat_regras = {x["tratamento"] for x in regs}
        trat_g = set(b["trat_grupo"])
        # o pai tem o tributo e o grupo não, no mesmo produto/cliente e abrangência -> ausente
        falta = b["g_falta"] & pai_tem[t]
        tem = b["g_tem"] & pai_tem[t]
        alcance = {}
        quem = "clientes do mesmo perfil" if tipo == "participante" else "produtos da mesma origem"
        if falta and not tem:
            abr_f = sorted({k[1] for k in falta})
            abr_pai = sorted({k[1] for k in pai_tem[t]})
            sug = "ausente"
            motivo = (f"Os demais {quem} têm {g.TRIBUTOS[t][1]} nas mesmas operações e o grupo não teve em "
                      f"nenhum item: o tributo não deve existir para o grupo")
            if abr_f != abr_pai:
                alcance = {"abrangencia": ",".join(abr_f)}
                motivo += f" (só nas operações {', '.join(abr_f).lower()})"
            motivo += "."
        elif falta and tem:
            sug, motivo = "diferente", (f"O XML se contradiz: parte dos itens do grupo teve {g.TRIBUTOS[t][1]} e "
                                        f"parte não, onde os demais {quem} têm. Confira as notas antes de decidir "
                                        f"(pode ser emissão errada — use Correções).")
        elif trat_g - {"ausente"} and trat_regras and not (trat_g - {"ausente"}) <= trat_regras:
            sug, motivo = "diferente", "O XML do grupo traz um tratamento diferente do da regra que o atende hoje."
        elif trat_g == {"ausente"}:
            sug, motivo = "incluir", f"{g.TRIBUTOS[t][1]} não aparece para o grupo nem para os demais."
        elif usa and g.TRIBUTOS[t][5] == "ORIG":
            sug, motivo = "duplicar", ("Mesmo tratamento do pai. Como o tributo separa regras por "
                                       + ("participante" if tipo == "participante" else "produto")
                                       + ", a regra do pai é duplicada para o grupo (os perfis não podem se sobrepor).")
        elif usa:
            sug, motivo = "incluir", ("Mesmo tratamento do pai: basta incluir o grupo de tributação no perfil "
                                      "usado hoje (sem regra nova). Escolha 'duplicar' se preferir regra filha.")
        else:
            sug, motivo = "incluir", ("Mesmo tratamento e o tributo usa perfil geral "
                                      + ("de participante" if tipo == "participante" else "de produto")
                                      + ": nada muda.")
        tribs.append({"chave": t, "trib": g.TRIBUTOS[t][0], "nome": g.TRIBUTOS[t][1], "usa_perfil": usa,
                      "itens": b["itens"], "regras": regs[:12], "regras_total": len(regs),
                      "trat_grupo": [{"tratamento": k, "itens": q} for k, q in b["trat_grupo"].most_common(6)],
                      "sugestao": sug, "alcance": alcance, "motivo": motivo})
    nome = re.sub(r"\s+", " ", str(corpo.get("nome") or "")).strip().upper()
    suf = re.sub(r"[^A-Z0-9]", "", g._norm(corpo.get("sufixo") or nome))[:2] or "DV"
    sugestoes = {}
    for pai in pais:
        if tipo == "participante":
            base = pai.split(" · ")[0].replace(" SUFRAMA", "")
            cod = g.PERFIL_PARTICIPANTE.get(base, ("CXXG01",))[0]
            if " · " in pai:
                cod = cod[:3] + ("S" if pai.split(" · ")[1].startswith("SIMPLES") else "N") + cod[4:]
            sugestoes[pai] = cod[:4] + suf
        else:
            cod = next((v[0] for v in g.PERFIL_ORIGEM.values() if v[1] == pai), "ICMX01")
            usados = set(mt["perf_prod"]) | set(g.CODIGOS_RESERVADOS)
            n = int(cod[4:]) + 1 if cod[4:].isdigit() else 1
            while f"{cod[:4]}{n:02d}" in usados:
                n += 1
            sugestoes[pai] = f"{cod[:4]}{n:02d}"
    return {"tipo": tipo, "valores": valores, "encontrados": len(achados), "nao_encontrados": nao[:200],
            "total_nao_encontrados": len(nao), "itens": sum(achados.values()),
            "amostra": [{"valor": k, "desc": nomes.get(k, ""), "itens": q} for k, q in achados.most_common(60)],
            "pais": [{"pai": k, "itens": q, "codigo_sugerido": sugestoes.get(k, "")} for k, q in pais.most_common()],
            "sufixo": suf, "tributos": tribs, "acoes": g.ACOES_GRUPO}


def api_grupo_simular(corpo):
    gr = _novo_grupo(corpo)

    def mudar():
        g.GRUPOS_DERIVADOS[:] = [x for x in g.GRUPOS_DERIVADOS if x["id"] != gr["id"]] + [gr]
    res = _simular(mudar)
    res["grupo"] = gr
    return res


def api_grupo_salvar(corpo):
    gr = _novo_grupo(corpo)
    novo = not any(x["id"] == gr["id"] for x in g.GRUPOS_DERIVADOS)
    g.GRUPOS_DERIVADOS[:] = [x for x in g.GRUPOS_DERIVADOS if x["id"] != gr["id"]] + [gr]
    _salvar_grupos()
    g.indexar_grupos(EST["cnpj"])
    pais = corpo.get("pais") or []
    acoes = "; ".join(f"{g.TRIBUTOS[t][1]}: {cfg['acao']}" + (
        " (" + ", ".join(f"{k} {v}" for k, v in cfg["alcance"].items()) + ")" if cfg.get("alcance") else "")
        for t, cfg in gr["tributos"].items() if cfg["acao"] != g.acao_grupo({"tributos": {}}, t))
    linha = (f"| {time.strftime('%d/%m/%Y')} | Grupo derivado | "
             f"{g._md(('Clientes' if gr['tipo'] == 'participante' else 'Produtos') + ' ' + gr['nome'] + (' filhos de ' + ', '.join(pais[:3]) if pais else '') + (' — ' + gr['obs'] if gr['obs'] else ''))} | "
             f"{g._md('Grupo de tributação próprio' + ('. ' + acoes if acoes else '; mesmo tratamento do pai em todos os tributos'))} | "
             f"{g._md(str(EST['cnpj'] or ''))} |")
    if novo:
        with open(g.ARQ_PADROES, encoding="utf-8") as f:
            texto = f.read()
        with open(g.ARQ_PADROES, "w", encoding="utf-8") as f:
            f.write(_registrar_conhecimento(texto, linha))
        _, EST["avisos_padroes"] = g.carregar_padroes()
    return {"id": gr["id"], "regerando": _regenerar()}


def api_grupo_remover(corpo):
    antes = len(g.GRUPOS_DERIVADOS)
    g.GRUPOS_DERIVADOS[:] = [x for x in g.GRUPOS_DERIVADOS if x["id"] != corpo.get("id")]
    if len(g.GRUPOS_DERIVADOS) == antes:
        raise LookupError("Grupo não encontrado.")
    _salvar_grupos()
    g.indexar_grupos(EST["cnpj"])
    return {"regerando": _regenerar()}


def api_grupo_simular_remocao(corpo):
    gid = corpo.get("id")
    return _simular(lambda: g.GRUPOS_DERIVADOS.__setitem__(slice(None), [x for x in g.GRUPOS_DERIVADOS
                                                                         if x["id"] != gid]))


# ── agrupamentos: perguntar antes de juntar ─────────────────────────────────────
def _bloco_agrupamentos():
    L = ["## Agrupamentos", "",
         "Na família do ICMS o programa gera o esqueleto separado (operação | abrangência | origem | participante |",
         "regime | finalidade) e PERGUNTA antes de juntar regras de mesmo tratamento. A resposta fica aqui.",
         "Critérios: tipo, regime, origem, finalidade, abrangencia. Decisão: juntar ou separar. Tributo `*` = todos.", "",
         "| Tributo | Critério | Decisão | Observação |", "|---|---|---|---|"]
    obs = EST.setdefault("obs_agrup", {})
    L += [f"| {t} | {c} | {d} | {g._md(obs.get(f'{t}|{c}', ''))} |" for (t, c), d in g.AGRUPAMENTOS.items()]
    return "\n".join(L) + "\n"


def api_agrupamentos(_):
    _exige_gerado()
    mt = EST["mt"]
    regras = {r["F2B_REGRA"]: r for r in mt["regras"]}
    pend = []
    for q in mt.get("agrupamentos", []):
        t, c = q["tributo"], q["criterio"]
        pend.append({"tributo": t, "trib": g.TRIBUTOS[t][0], "nome": g.TRIBUTOS[t][1], "criterio": c,
                     "rotulo": g.CRITERIOS_AGRUP[c][0], "decisao": q["decisao"],
                     "regras_antes": q["regras_antes"], "regras_depois": q["regras_depois"],
                     "grupos": [[{"cod": x, "desc": regras[x]["F2B_DESC"], "itens": regras[x]["Itens"],
                                  "status": regras[x].get("_status", "")} for x in grp] for grp in q["grupos"][:60]],
                     "total_grupos": len(q["grupos"])})
    dec = [{"tributo": t, "nome": "Todos os tributos" if t == "*" else g.TRIBUTOS.get(t, ("", t))[1], "criterio": c,
            "rotulo": g.CRITERIOS_AGRUP.get(c, (c,))[0], "decisao": d} for (t, c), d in g.AGRUPAMENTOS.items()]
    return {"pendentes": [p for p in pend if p["decisao"] == "perguntar"],
            "separados": [p for p in pend if p["decisao"] == "separar"], "decisoes": dec,
            "criterios": {k: v[0] for k, v in g.CRITERIOS_AGRUP.items()}}


def _alvos_agrup(corpo):
    t = corpo.get("tributo")
    c = corpo.get("criterio")
    if c not in g.CRITERIOS_AGRUP or not (t == "*" or t in g.TRIBUTOS):
        raise ValueError("Tributo ou critério inválido.")
    d = corpo.get("decisao")
    if d not in ("juntar", "separar"):
        raise ValueError("Decisão inválida (juntar ou separar).")
    return t, c, d


def api_agrup_simular(corpo):
    t, c, d = _alvos_agrup(corpo)
    return _simular(lambda: g.AGRUPAMENTOS.__setitem__((t, c), d))


def _gravar_agrupamentos(linha=None):
    with open(g.ARQ_PADROES, encoding="utf-8") as f:
        texto = f.read()
    texto = _substituir_secao(texto, "Agrupamentos", _bloco_agrupamentos(), antes_de="## Grupos de operação")
    if linha:
        texto = _registrar_conhecimento(texto, linha)
    return api_salvar_padroes({"texto": texto})


def api_agrup_salvar(corpo):
    t, c, d = _alvos_agrup(corpo)
    g.AGRUPAMENTOS[(t, c)] = d
    if corpo.get("obs"):
        EST.setdefault("obs_agrup", {})[f"{t}|{c}"] = str(corpo["obs"])
    nome = "Todos os tributos" if t == "*" else g.TRIBUTOS[t][1]
    linha = (f"| {time.strftime('%d/%m/%Y')} | {g._md(nome)} | "
             f"{g._md('Regras de mesmo tratamento que só diferem por ' + g.CRITERIOS_AGRUP[c][0])} | "
             f"{g._md(('Juntar em uma regra' if d == 'juntar' else 'Manter separadas (esqueleto completo)') + (' — ' + corpo['obs'] if corpo.get('obs') else ''))} | "
             f"{g._md(str(EST['cnpj'] or ''))} |")
    return _gravar_agrupamentos(linha)


def api_agrup_remover(corpo):
    t, c = corpo.get("tributo"), corpo.get("criterio")
    if (t, c) not in g.AGRUPAMENTOS:
        raise LookupError("Decisão não encontrada.")
    del g.AGRUPAMENTOS[(t, c)]
    return _gravar_agrupamentos()


# ── assistente com LLM (DeepSeek, API compatível com OpenAI) ─────────────────────
ARQ_LLM = os.path.join(AQUI, "llm_config.json")
LLM_PADRAO = {"url": "https://api.deepseek.com", "modelo": "deepseek-chat", "mascarar": True, "api_key": ""}


def _llm_cfg():
    cfg = dict(LLM_PADRAO)
    try:
        with open(ARQ_LLM, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    if not cfg.get("api_key"):
        cfg["api_key"] = os.environ.get("DEEPSEEK_API_KEY", "")
    return cfg


def api_llm_config(_):
    c = _llm_cfg()
    k = c.get("api_key", "")
    return {"configurado": bool(k), "chave": (k[:3] + "…" + k[-4:]) if len(k) > 8 else ("definida" if k else ""),
            "url": c["url"], "modelo": c["modelo"], "mascarar": bool(c.get("mascarar", True)), "arquivo": ARQ_LLM}


def api_llm_salvar(corpo):
    c = _llm_cfg()
    for k in ("url", "modelo"):
        if str(corpo.get(k) or "").strip():
            c[k] = str(corpo[k]).strip().rstrip("/")
    if "mascarar" in corpo:
        c["mascarar"] = bool(corpo["mascarar"])
    if str(corpo.get("api_key") or "").strip():
        c["api_key"] = str(corpo["api_key"]).strip()
    if corpo.get("limpar_chave"):
        c["api_key"] = ""
    with open(ARQ_LLM, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=1)
    return api_llm_config(None)


class _Mascara:
    """Troca CNPJ/CPF por apelidos (CLIENTE_1…) antes de enviar e desfaz na resposta (LGPD)."""
    _RE = re.compile(r"(?<!\d)(\d{14}|\d{11}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{3}\.\d{3}\.\d{3}-\d{2})(?!\d)")

    def __init__(self, ativo, preservar=()):
        self.ativo, self.ida, self.volta = ativo, {}, {}
        self.preservar = set(preservar)

    def __call__(self, txt):
        if not self.ativo or not txt:
            return txt

        def troca(m):
            v = re.sub(r"\D", "", m.group(1))
            if v in self.preservar:
                return m.group(1)
            if v not in self.ida:
                ap = f"{'CNPJ' if len(v) == 14 else 'CPF'}_{len(self.ida) + 1}"
                self.ida[v], self.volta[ap] = ap, v
            return self.ida[v]
        return self._RE.sub(troca, txt)

    def desfazer(self, txt):
        for ap in sorted(self.volta, key=len, reverse=True):
            txt = txt.replace(ap, self.volta[ap])
        return txt


def _contexto_llm(extra=""):
    partes = []
    an, mt = EST["an"], EST["mt"]
    if an and mt:
        partes.append("## Análise atual\n" + g.resumo_texto(an, mt))
        linhas = [f"{r['F2B_REGRA']} | {r['F2B_DESC']} | base {r['F2B_RBASE']} | alíq {r['F2B_RALIQ']} | "
                  f"part {r['F2B_PERFPA']} | prod {r['F2B_PERFPR']} | op {r['F2B_PERFOP']} | esc {r['F2B_CODESC']} | "
                  f"{r['Itens']} itens | {r.get('_status', '')}" + (f" | filha de {r['PAI']} ({r['GRUPO_DERIVADO']})"
                                                                    if r.get("GRUPO_DERIVADO") else "")
                  for r in mt["regras"][:500]]
        partes.append("## Regras sugeridas (código | descrição | cadastros | itens | status)\n" + "\n".join(linhas))
        pend = mt.get("agrupamentos", [])
        if pend:
            partes.append("## Perguntas de agrupamento pendentes\n" + "\n".join(
                f"{g.TRIBUTOS[q['tributo']][1]} · {q['criterio']}: {q['regras_antes']} regras → {q['regras_depois']}"
                for q in pend))
        if g.GRUPOS_DERIVADOS:
            partes.append("## Grupos derivados\n" + "\n".join(
                f"{x['nome']} ({x['tipo']}, {len(x['valores'])} valores): " +
                ", ".join(f"{t} {c['acao']}" for t, c in x.get("tributos", {}).items()) for x in g.GRUPOS_DERIVADOS))
        emp = g.CONHECIMENTO_EMPRESA.get(EST["cnpj"] or "", {})
        if emp:
            partes.append("## Conhecimento só desta empresa (já aplicado pelo motor)\n" + json.dumps(emp, ensure_ascii=False)[:8000])
        conf = an["conflitos"][:30]
        if conf:
            partes.append("## Conflitos do XML (tributo: tratamentos)\n" + "\n".join(
                f"{g.TRIBUTOS[t][1]}: " + "; ".join(f"{_desc_trat_curto(tr)} ({q})" for tr, q in cnt.most_common(4))
                for t, b, cnt in conf))
    if extra:
        partes.append("## Contexto enviado pela tela\n" + str(extra)[:30000])
    return "\n\n".join(partes)


_SISTEMA_LLM = """Você é o assistente fiscal do Facilitador Fiscal, programa que transforma XMLs de NF-e de saída em
regras do Configurador de Tributos do Protheus (FISA170: regras F2B, perfis F20, bases F27, alíquotas F28,
escrituração CJ2). Responda em português do Brasil, de forma objetiva, como um consultor tributário sênior que
conhece o Protheus.

Como trabalhar:
- A base de conhecimento (padroes_configurador.md) e a análise atual vêm abaixo. Use-as como fonte; não invente
  códigos de regra, perfis ou números que não estejam no contexto. Se faltar informação, diga o que falta.
- Quem gera e altera regras é o motor do programa, pelas telas. Você explica, analisa impacto e recomenda a ação
  na tela certa: Correções (XML emitido errado), Grupos derivados (clientes/produtos informados na mão que viram
  grupo de tributação próprio, com regra filha duplicada do pai), Agrupamentos (juntar ou manter separadas regras
  de mesmo tratamento), Segregações/Exceções e Padrões (regras de negócio).
- Sempre que sugerir uma mudança, diga o impacto nos OUTROS tributos (ICMS, ST, DIFAL, FECP, IPI, PIS/COFINS,
  IBS/CBS): perfis de participante e de produto não podem se sobrepor, então separar um grupo num tributo costuma
  exigir regra filha nos demais tributos que usam perfil específico.
- Pergunte o alcance quando fizer diferença: só operação interna? interestadual? vendas, bonificação,
  transferência? consumo ou revenda?
- Lembre que CNPJ/CPF podem vir mascarados (CNPJ_1, CPF_2): use os apelidos como estão.

Propor conhecimento para a base:
Quando o usuário explicar uma situação que deve valer nas próximas análises, PROPONHA a mudança (nunca diga que
gravou: quem grava é o usuário, depois de ver o impacto). Explique em 2–4 linhas e depois escreva cada proposta
num bloco próprio, exatamente assim:
```proposta
{"tabela": "regras_negocio", "alcance": "empresa", "motivo": "por que isso é verdade",
 "linha": {"tributo": "ICMSST", "quando": "grupocliente=TRANSPORTADORA e abrangencia=INTERNA", "entao": "ausente",
           "observacao": "texto curto"}}
```
Tabelas e campos aceitos:
- regras_negocio: tributo (ICMS, ICMSST, DIFAL, FECP, FECPST, FECPDF, IPI, PIS, COF, IBSEST, IBSMUN, CBSFED),
  quando (condições campo=valor unidas por " e "; vírgula = OU; `*` no fim = começa com; `!=` = diferente; campos:
  cfop, cfop_base, natureza, grupo, finalidade, uf, uf_emit, abrangencia, participante, contribuinte, regime, pessoa,
  origem, ncm, cest, cst, suframa, grupocliente, grupoproduto), entao (ausente | base=CÓDIGO | aliquota=ncm).
- agrupamentos: tributo (ou *), criterio (tipo, regime, origem, finalidade, abrangencia), decisao (juntar | separar).
- segregacoes: tributo, dim (cfop, classe, origem, participante, uf).
- excecoes: tributo, campo (dest, cprod, ncm), valores (lista).
- conhecimento: texto (só para consulta; o motor não aplica).
alcance: "empresa" (só este cliente: use sempre que depender de clientes, produtos, grupos ou benefício do cliente)
ou "geral" (vale para todas as empresas: só para regra de legislação/prática que se repete). Na dúvida, "empresa".
Não proponha códigos de regra/perfil nem mudanças em Tributos, Escrituração ou Grupos de operação.
Se faltar informação para a condição (ex.: alcance interna/interestadual), pergunte antes de propor.
- Você não é advogado tributarista; quando a dúvida for de legislação, indique o que conferir."""


def api_llm_chat(corpo):
    cfg = _llm_cfg()
    if not cfg.get("api_key"):
        raise ValueError("Configure a chave da API do DeepSeek (ícone de engrenagem no assistente).")
    msgs = [m for m in (corpo.get("mensagens") or []) if m.get("role") in ("user", "assistant") and m.get("content")]
    if not msgs:
        raise ValueError("Escreva uma pergunta.")
    masc = _Mascara(cfg.get("mascarar", True))
    try:
        with open(g.ARQ_PADROES, encoding="utf-8") as f:
            md = f.read()
    except OSError:
        md = ""
    sistema = (_SISTEMA_LLM + "\n\n# Base de conhecimento (padroes_configurador.md)\n" + md[:60000]
               + "\n\n# Situação atual\n" + _contexto_llm(corpo.get("contexto", "") if corpo.get("incluir_analise", True)
                                                     else ""))
    payload = {"model": cfg["modelo"], "temperature": 0.2, "stream": False,
               "messages": [{"role": "system", "content": masc(sistema)}] +
                           [{"role": m["role"], "content": masc(str(m["content"])[:20000])} for m in msgs[-16:]]}
    req = urllib.request.Request(cfg["url"].rstrip("/") + "/chat/completions",
                                 data=json.dumps(payload).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['api_key']}"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            res = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        corpo_e = e.read().decode("utf-8", "replace")[:400]
        msg = {401: "chave da API inválida", 402: "sem saldo na conta da API", 429: "limite de uso atingido"}.get(
            e.code, f"erro {e.code}")
        raise RuntimeError(f"DeepSeek recusou a chamada ({msg}): {corpo_e}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise RuntimeError(f"Não consegui falar com {cfg['url']}: {e}")
    try:
        txt = res["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("Resposta inesperada da API: " + json.dumps(res)[:300])
    return {"resposta": masc.desfazer(txt), "mascarados": len(masc.ida), "modelo": res.get("model", cfg["modelo"]),
            "uso": res.get("usage", {})}


# ── conhecimento proposto (pela IA ou à mão) → validar → impacto → aprovar → desfazer ─────
ARQ_CONH_EMPRESA = os.path.join(AQUI, "conhecimento_empresa.json")
ARQ_HISTORICO = os.path.join(AQUI, "conhecimento_historico.json")
PASTA_BACKUP = os.path.join(AQUI, "padroes_backup")
TABELAS_PROPOSTA = {"regras_negocio": "Regras de negócio", "agrupamentos": "Agrupamentos", "segregacoes": "Segregações",
                    "excecoes": "Exceções", "conhecimento": "Conhecimento (texto para consulta)"}
CAMPOS_CONTEXTO = {"CFOP", "CFOP_BASE", "NATUREZA", "GRUPO", "FINALIDADE", "UF", "UF_EMIT", "ABRANGENCIA", "PARTICIPANTE",
                   "CONTRIBUINTE", "REGIME", "PESSOA", "ORIGEM", "NCM", "CEST", "CST", "SUFRAMA", "GRUPOCLIENTE",
                   "GRUPOPRODUTO"}


def _carregar_conh_empresa():
    g.CONHECIMENTO_EMPRESA.clear()
    try:
        with open(ARQ_CONH_EMPRESA, encoding="utf-8") as f:
            g.CONHECIMENTO_EMPRESA.update(json.load(f))
    except (OSError, ValueError):
        pass


def _salvar_conh_empresa():
    with open(ARQ_CONH_EMPRESA, "w", encoding="utf-8") as f:
        json.dump(g.CONHECIMENTO_EMPRESA, f, ensure_ascii=False, indent=1)


def _ler_historico():
    try:
        with open(ARQ_HISTORICO, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def _salvar_historico(h):
    with open(ARQ_HISTORICO, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=1)


def _backup_md():
    """Cópia do padroes_configurador.md antes de cada mudança aprovada (guarda as 40 mais recentes)."""
    os.makedirs(PASTA_BACKUP, exist_ok=True)
    nome = os.path.join(PASTA_BACKUP, time.strftime("padroes_%Y%m%d_%H%M%S.md"))
    try:
        with open(g.ARQ_PADROES, encoding="utf-8") as f, open(nome, "w", encoding="utf-8") as o:
            o.write(f.read())
    except OSError:
        return ""
    antigos = sorted(x for x in os.listdir(PASTA_BACKUP) if x.startswith("padroes_"))
    for x in antigos[:-40]:
        try:
            os.remove(os.path.join(PASTA_BACKUP, x))
        except OSError:
            pass
    return nome


def _linha_md_proposta(p):
    l = p["linha"]
    if p["tabela"] == "regras_negocio":
        return f"| {l['tributo']} | {g._md(l['quando'])} | {g._md(l['entao'])} | {g._md(l.get('observacao', ''))} |"
    if p["tabela"] == "agrupamentos":
        return f"| {l['tributo']} | {l['criterio']} | {l['decisao']} | {g._md(l.get('observacao', ''))} |"
    if p["tabela"] == "segregacoes":
        return f"| {l['tributo']} | {l['dim']} | {g._md(l.get('observacao', ''))} |"
    if p["tabela"] == "excecoes":
        return f"| {l['tributo']} | {l['campo']} | {', '.join(l['valores'])} | {g._md(l.get('observacao', ''))} | {l.get('id', '')} |"
    return f"| {l.get('tributo') or '—'} | {g._md(l['texto'])} |"


def _validar_proposta(p):
    """Normaliza a proposta e confere se o motor entende: -> (proposta, erros, avisos)."""
    erros, avisos = [], []
    if not isinstance(p, dict):
        return {}, ["Proposta inválida."], []
    tab = str(p.get("tabela") or "").strip().lower().replace(" ", "_").replace("ç", "c").replace("õ", "o").replace("ã", "a")
    tab = {"regras_de_negocio": "regras_negocio", "regra_de_negocio": "regras_negocio", "regras": "regras_negocio",
           "excecao": "excecoes", "segregacao": "segregacoes", "agrupamento": "agrupamentos",
           "conhecimento_aprendido": "conhecimento"}.get(tab, tab)
    if tab not in TABELAS_PROPOSTA:
        return {}, [f"Tabela '{p.get('tabela')}' não pode ser alterada por proposta (use: {', '.join(TABELAS_PROPOSTA)})."], []
    l = {str(k).lower(): v for k, v in (p.get("linha") or {}).items()}
    alcance = "geral" if str(p.get("alcance") or "").lower().startswith("geral") else "empresa"
    out = {"tabela": tab, "alcance": alcance, "motivo": str(p.get("motivo") or "").strip()[:600], "linha": {},
           "origem": "IA" if p.get("origem", "IA") == "IA" else "manual"}
    trib = str(l.get("tributo") or "").strip()
    t = "*" if trib in ("*", "todos", "TODOS") and tab == "agrupamentos" else (g._chave_trib(trib) if trib else None)
    obs = str(l.get("observacao") or l.get("obs") or out["motivo"])[:200]
    if tab == "regras_negocio":
        if not t:
            erros.append(f"Tributo '{trib}' não existe (use {', '.join(g.TRIBUTOS)}).")
        quando = str(l.get("quando") or "").strip()
        entao = str(l.get("entao") or l.get("então") or "").strip()
        try:
            conds = g._compilar_condicoes(quando)
            if not conds:
                erros.append("A condição está vazia: a regra valeria para todos os itens.")
            for campo, op, vals in conds:
                if campo not in CAMPOS_CONTEXTO:
                    erros.append(f"Campo '{campo.lower()}' não existe nas condições "
                                 f"(use {', '.join(sorted(c.lower() for c in CAMPOS_CONTEXTO))}).")
        except ValueError as e:
            erros.append(str(e))
        el = entao.lower()
        if el == "ausente" or (el.startswith("aliquota=") and el.endswith("ncm")):
            entao = el
        elif el.startswith("base="):
            cod = entao.split("=", 1)[1].strip().upper()
            conhecidas = {c for lst in g.BASES.values() for c, *_ in lst} | {g.BASE_ZERO[0], "BCZR00"} | \
                set((EST["mt"] or {}).get("bases", {}))
            if cod not in conhecidas:
                avisos.append(f"A base {cod} não está no catálogo do programa nem nas bases geradas: confira o código.")
            entao = f"base={cod}"
        else:
            erros.append("Ação inválida: use ausente, base=CÓDIGO ou aliquota=ncm.")
        if t and any(g._chave_trib(r[0]) == t and g._norm(r[1]) == g._norm(quando) and r[2].lower() == entao.lower()
                     for r in g.REGRAS_NEGOCIO):
            erros.append("Essa regra de negócio já existe no padrão.")
        out["linha"] = {"tributo": t or trib, "quando": quando, "entao": entao, "observacao": obs}
        if alcance == "geral" and re.search(r"grupo(cliente|produto)", quando, re.I):
            avisos.append("A condição usa um grupo derivado desta empresa: no padrão geral ela só vale onde existir "
                          "grupo com o mesmo nome. Considere 'só esta empresa'.")
    elif tab == "agrupamentos":
        c = g._norm(str(l.get("criterio") or "")).lower().split(" ")[0] if l.get("criterio") else ""
        c = {"participante": "tipo"}.get(c, c)
        d = str(l.get("decisao") or "").lower()
        d = "juntar" if d.startswith("junt") else "separar" if d.startswith("separ") else d
        if not t:
            erros.append(f"Tributo '{trib}' não existe.")
        if c not in g.CRITERIOS_AGRUP:
            erros.append(f"Critério '{l.get('criterio')}' inválido (use {', '.join(g.CRITERIOS_AGRUP)}).")
        if d not in ("juntar", "separar"):
            erros.append("Decisão inválida (juntar ou separar).")
        out["linha"] = {"tributo": t or trib, "criterio": c, "decisao": d, "observacao": obs}
    elif tab == "segregacoes":
        dim = str(l.get("dim") or l.get("separar_por") or "").lower().strip()
        if not t:
            erros.append(f"Tributo '{trib}' não existe.")
        if dim not in g.DIM_SEGREGACAO:
            erros.append(f"Critério '{dim}' inválido (use {', '.join(g.DIM_SEGREGACAO)}).")
        elif t and dim in g.segregacoes_de(t):
            erros.append("Esse tributo já separa regras por esse critério.")
        out["linha"] = {"tributo": t or trib, "dim": dim, "observacao": obs}
    elif tab == "excecoes":
        campo = str(l.get("campo") or "").lower().strip()
        vals = l.get("valores") or []
        vals = [str(v).strip() for v in (re.split(r"[,; ]+", vals) if isinstance(vals, str) else vals) if str(v).strip()]
        if not t:
            erros.append(f"Tributo '{trib}' não existe.")
        if campo not in g.CAMPOS_EXCECAO:
            erros.append(f"Campo '{campo}' inválido (use dest, cprod ou ncm).")
        if not vals:
            erros.append("Informe os valores da exceção.")
        if alcance == "geral" and campo in ("dest", "cprod"):
            avisos.append("Clientes e produtos são desta empresa: no padrão geral a exceção não fará sentido para outras.")
        out["linha"] = {"tributo": t or trib, "campo": campo, "valores": vals, "observacao": obs}
    else:
        texto = str(l.get("texto") or out["motivo"]).strip()
        if not texto:
            erros.append("O texto do conhecimento está vazio.")
        out["linha"] = {"tributo": (g.TRIBUTOS[t][1] if t and t in g.TRIBUTOS else trib), "texto": texto[:800]}
        avisos.append("Texto livre não muda o cálculo: fica como conhecimento para consulta (inclusive da IA). "
                      "Para o motor aplicar, a proposta precisa ser uma regra de negócio, agrupamento, segregação ou exceção.")
    out["linha_md"] = _linha_md_proposta(out) if not erros else ""
    return out, erros, avisos


def _aplicar_em_memoria(p):
    """Aplica a proposta nas estruturas do motor (para simular ou depois de gravar)."""
    l, emp = p["linha"], g.CONHECIMENTO_EMPRESA.setdefault(EST["cnpj"] or "", {})
    if p["tabela"] == "regras_negocio":
        if p["alcance"] == "geral":
            g.REGRAS_NEGOCIO.append((l["tributo"], l["quando"], l["entao"], l["observacao"]))
        else:
            emp.setdefault("regras_negocio", []).append(dict(l))
    elif p["tabela"] == "agrupamentos":
        if p["alcance"] == "geral":
            g.AGRUPAMENTOS[(l["tributo"], l["criterio"])] = l["decisao"]
        else:
            lst = [x for x in emp.get("agrupamentos", []) if (x["tributo"], x["criterio"]) != (l["tributo"], l["criterio"])]
            emp["agrupamentos"] = lst + [dict(l)]
    elif p["tabela"] == "segregacoes":
        alvo = g.SEGREGACOES if p["alcance"] == "geral" else emp.setdefault("segregacoes", [])
        alvo.append({"tributo": l["tributo"], "dim": l["dim"], "obs": l["observacao"]})
    elif p["tabela"] == "excecoes":
        if p["alcance"] == "geral":
            usados = {x["id"] for x in g.EXCECOES}
            n = 1
            while f"E{n}" in usados:
                n += 1
            l["id"] = l.get("id") or f"E{n}"
            g.EXCECOES.append({"id": l["id"], "tributo": l["tributo"], "campo": l["campo"], "valores": l["valores"],
                               "obs": l["observacao"]})
        else:
            lst = emp.setdefault("excecoes", [])
            usados = {x["id"] for x in lst}
            n = 1
            while f"EE{n}" in usados:
                n += 1
            l["id"] = l.get("id") or f"EE{n}"
            lst.append({"id": l["id"], "tributo": l["tributo"], "campo": l["campo"], "valores": l["valores"],
                        "obs": l["observacao"]})
    elif p["alcance"] == "empresa":
        emp.setdefault("notas", []).append({"texto": l["texto"], "tributo": l.get("tributo", "")})


def _itens_afetados(p):
    """Em quais itens dos XMLs a regra proposta se aplica (amostra para conferir contra a nota)."""
    an = EST["an"]
    if not an or p["tabela"] != "regras_negocio":
        return None
    l = p["linha"]
    conds = g._compilar_condicoes(l["quando"])
    t = l["tributo"]
    tot, muda, ex = 0, 0, []
    for d, it, tr in an["linhas"]:
        if not g._bate(conds, g.contexto(d, it)):
            continue
        tot += 1
        e = l["entao"]
        diverge = (t in tr) if e == "ausente" else (t in tr and e.startswith("base=") and tr[t][1][0] != e[5:])
        muda += bool(diverge)
        if len(ex) < 8 and (diverge or len(ex) < 3):
            n = next((k for k, x in enumerate(d["itens"], 1) if x is it), 0)
            ex.append({"nf": d["num"], "item": n, "chave": d["chave"], "cliente": d["dest_nome"][:40], "uf": d["uf_dest"],
                       "produto": f"{it['cprod']} {it['xprod'][:40]}", "cfop": it["cfop"],
                       "hoje": _desc_trat_curto(g.tratamento_item(an, t, d, it, tr)) if t in g.TRIBUTOS else "",
                       "muda": bool(diverge)})
    ex.sort(key=lambda x: not x["muda"])
    return {"itens": tot, "mudam": muda, "exemplos": ex}


def api_proposta_validar(corpo):
    p, erros, avisos = _validar_proposta(corpo.get("proposta") or corpo)
    return {"proposta": p, "erros": erros, "avisos": avisos, "tabela_nome": TABELAS_PROPOSTA.get(p.get("tabela"), ""),
            "afetados": _itens_afetados(p) if not erros and EST["an"] else None}


def api_proposta_simular(corpo):
    p, erros, avisos = _validar_proposta(corpo.get("proposta") or corpo)
    if erros:
        raise ValueError("Proposta inválida: " + " ".join(erros))
    res = _simular(lambda: _aplicar_em_memoria(copy.deepcopy(p)))
    res.update(proposta=p, avisos=avisos, afetados=_itens_afetados(p))
    return res


def _md_inserir_linha(texto, titulo, linha):
    """Acrescenta uma linha no fim da tabela da seção '## titulo'."""
    m = re.search(r"^## " + re.escape(titulo) + r"\s*$.*?(?=^## |\Z)", texto, flags=re.M | re.S)
    if not m:
        raise LookupError(f"Seção '## {titulo}' não encontrada no padroes_configurador.md.")
    sec = m.group(0)
    linhas = sec.rstrip("\n").split("\n")
    ult = max((i for i, x in enumerate(linhas) if x.strip().startswith("|")), default=None)
    if ult is None:
        raise LookupError(f"A seção '## {titulo}' não tem tabela.")
    linhas.insert(ult + 1, linha)
    return texto[:m.start()] + "\n".join(linhas) + "\n\n" + texto[m.end():].lstrip("\n")


def _md_remover_linha(texto, titulo, linha):
    m = re.search(r"^## " + re.escape(titulo) + r"\s*$.*?(?=^## |\Z)", texto, flags=re.M | re.S)
    if not m:
        return texto, False
    sec = m.group(0).split("\n")
    alvo = linha.strip()
    for i, x in enumerate(sec):
        if x.strip() == alvo:
            del sec[i]
            return texto[:m.start()] + "\n".join(sec) + texto[m.end():], True
    return texto, False


def api_proposta_aplicar(corpo):
    p, erros, avisos = _validar_proposta(corpo.get("proposta") or corpo)
    if erros:
        raise ValueError("Proposta inválida: " + " ".join(erros))
    with TRAVA:
        if EST["status"]["tarefa"]:
            raise RuntimeError(f"Aguarde: {EST['status']['tarefa']} em andamento.")
    reg = {"id": f"K{int(time.time() * 1000)}", "data": time.strftime("%d/%m/%Y %H:%M"), "cnpj": EST["cnpj"] or "",
           "origem": p["origem"], "alcance": p["alcance"], "tabela": p["tabela"], "linha": p["linha"],
           "linha_md": "", "motivo": p["motivo"], "ativo": True, "backup": ""}
    if p["alcance"] == "empresa":
        _aplicar_em_memoria(p)
        _salvar_conh_empresa()
    else:
        reg["backup"] = _backup_md()
        with open(g.ARQ_PADROES, encoding="utf-8") as f:
            texto = f.read()
        if p["tabela"] in ("agrupamentos", "segregacoes", "excecoes"):
            _aplicar_em_memoria(p)          # as funções abaixo reescrevem a seção a partir da memória
        p["linha_md"] = _linha_md_proposta(p)
        reg["linha_md"] = p["linha_md"]
        if p["tabela"] == "regras_negocio":
            texto = _md_inserir_linha(texto, "Regras de negócio", p["linha_md"])
        elif p["tabela"] == "agrupamentos":
            EST.setdefault("obs_agrup", {})[f"{p['linha']['tributo']}|{p['linha']['criterio']}"] = p["linha"]["observacao"]
            texto = _substituir_secao(texto, "Agrupamentos", _bloco_agrupamentos(), antes_de="## Grupos de operação")
        elif p["tabela"] == "segregacoes":
            texto = _substituir_secao(texto, "Segregações", _bloco_segregacoes())
        elif p["tabela"] == "excecoes":
            texto = _substituir_secao(texto, "Exceções", _bloco_excecoes(), antes_de="## Segregações")
        tl = p["linha"].get("tributo") or "Geral"
        tnome = g.TRIBUTOS[tl][1] if tl in g.TRIBUTOS else ("Todos os tributos" if tl == "*" else tl)
        situacao = p["motivo"] or (p["linha"].get("texto") if p["tabela"] == "conhecimento" else "")
        decisao = (p["linha"]["texto"] if p["tabela"] == "conhecimento"
                   else f"{TABELAS_PROPOSTA[p['tabela']]}: {p['linha_md'].strip('| ').replace(' | ', ' · ')}")
        texto = _registrar_conhecimento(texto, f"| {time.strftime('%d/%m/%Y')} | {g._md(tnome)} | {g._md(situacao)} | "
                                               f"{g._md(decisao)} | {g._md((EST['cnpj'] or '') + ' · ' + p['origem'])} |")
        with open(g.ARQ_PADROES, "w", encoding="utf-8") as f:
            f.write(texto)
        _, EST["avisos_padroes"] = g.carregar_padroes()
    h = _ler_historico()
    h.append(reg)
    _salvar_historico(h)
    return {"id": reg["id"], "avisos": avisos + EST.get("avisos_padroes", []), "regerando": _regenerar()}


def api_conhecimento(_):
    h = _ler_historico()
    backups = sorted((x for x in os.listdir(PASTA_BACKUP) if x.startswith("padroes_")), reverse=True) \
        if os.path.isdir(PASTA_BACKUP) else []
    emp = g.CONHECIMENTO_EMPRESA.get(EST["cnpj"] or "", {})
    return {"historico": list(reversed(h))[:300], "backups": backups[:40], "pasta_backup": PASTA_BACKUP,
            "tabelas": TABELAS_PROPOSTA, "empresa": {k: len(v) for k, v in emp.items()}, "cnpj": EST["cnpj"]}


def api_conhecimento_desfazer(corpo):
    h = _ler_historico()
    reg = next((x for x in h if x["id"] == corpo.get("id")), None)
    if not reg or not reg.get("ativo"):
        raise LookupError("Conhecimento não encontrado ou já desfeito.")
    l = reg["linha"]
    if reg["alcance"] == "empresa":
        emp = g.CONHECIMENTO_EMPRESA.get(reg["cnpj"], {})
        chave = {"regras_negocio": "regras_negocio", "agrupamentos": "agrupamentos", "segregacoes": "segregacoes",
                 "excecoes": "excecoes", "conhecimento": "notas"}[reg["tabela"]]
        lst = emp.get(chave, [])
        for i, x in enumerate(lst):
            if (reg["tabela"] == "excecoes" and x.get("id") == l.get("id")) or \
               (reg["tabela"] == "conhecimento" and x.get("texto") == l.get("texto")) or \
               (reg["tabela"] == "segregacoes" and (x.get("tributo"), x.get("dim")) == (l["tributo"], l["dim"])) or \
               (reg["tabela"] in ("regras_negocio", "agrupamentos") and all(x.get(k) == l.get(k) for k in l if k != "observacao")):
                del lst[i]
                break
        _salvar_conh_empresa()
    else:
        _backup_md()
        with open(g.ARQ_PADROES, encoding="utf-8") as f:
            texto = f.read()
        if reg["tabela"] == "regras_negocio":
            texto, ok = _md_remover_linha(texto, "Regras de negócio", reg["linha_md"])
            if not ok:
                raise LookupError("A linha não está mais em Regras de negócio (foi editada à mão?). Ajuste na tela Padrões.")
        elif reg["tabela"] == "agrupamentos":
            g.AGRUPAMENTOS.pop((l["tributo"], l["criterio"]), None)
            texto = _substituir_secao(texto, "Agrupamentos", _bloco_agrupamentos(), antes_de="## Grupos de operação")
        elif reg["tabela"] == "segregacoes":
            g.SEGREGACOES[:] = [x for x in g.SEGREGACOES if (x["tributo"], x["dim"]) != (l["tributo"], l["dim"])]
            texto = _substituir_secao(texto, "Segregações", _bloco_segregacoes())
        elif reg["tabela"] == "excecoes":
            g.EXCECOES[:] = [x for x in g.EXCECOES if x["id"] != l.get("id")]
            texto = _substituir_secao(texto, "Exceções", _bloco_excecoes(), antes_de="## Segregações")
        texto = _registrar_conhecimento(texto, f"| {time.strftime('%d/%m/%Y')} | Desfeito | "
                                               f"{g._md(reg['data'] + ' · ' + TABELAS_PROPOSTA[reg['tabela']])} | "
                                               f"{g._md('Desfeito: ' + ((reg.get('linha_md') or '').strip('| ').replace(' | ', ' · ') or str(l)))} | {g._md(EST['cnpj'] or '')} |")
        with open(g.ARQ_PADROES, "w", encoding="utf-8") as f:
            f.write(texto)
        _, EST["avisos_padroes"] = g.carregar_padroes()
    reg["ativo"] = False
    reg["desfeito_em"] = time.strftime("%d/%m/%Y %H:%M")
    _salvar_historico(h)
    return {"regerando": _regenerar()}


def api_backup_restaurar(corpo):
    nome = os.path.basename(str(corpo.get("arquivo") or ""))
    cam = os.path.join(PASTA_BACKUP, nome)
    if not nome.startswith("padroes_") or not os.path.isfile(cam):
        raise LookupError("Cópia não encontrada.")
    _backup_md()
    with open(cam, encoding="utf-8") as f:
        texto = f.read()
    return api_salvar_padroes({"texto": texto})


def api_exportar_gerencial(_):
    """CSV de conferência: colunas do F2B + regra pai, grupo derivado, status e itens (não é o layout de importação)."""
    _exige_gerado()
    cols = g.COLS_F2B + ["PAI", "GRUPO_DERIVADO", "STATUS", "ITENS", "CFOPS", "UFS"]
    buf = io.StringIO()
    buf.write(";".join(cols) + "\r\n")
    for r in EST["mt"]["regras"]:
        extra = [r.get("PAI", ""), r.get("GRUPO_DERIVADO", ""), r.get("_status", ""), str(r["Itens"]),
                 r.get("CFOPs", ""), r.get("UFs", "")]
        buf.write(g.linha_csv_f2b(r) + ";" + ";".join(str(x).replace(";", ",") for x in extra) + "\r\n")
    return buf.getvalue()


# ── opções de geração (gravadas no .md: o arquivo de padrões aprende com o uso) ─────
def _bloco_opcoes():
    sim = lambda b: "sim" if b else "não"
    o = g.OPCOES
    L = ["## Opções", "", "Escolhas de geração. As telas do programa gravam aqui as decisões do usuário.", "",
         "| Opção | Valor |", "|---|---|",
         f"| RAPUR | {g.RAPUR_PADRAO} |", f"| INICIO_PERFIL_OPERACAO | {g.INICIO_PERFIL_OPERACAO} |",
         f"| AGRUPAR_MAXIMO | {sim(o['AGRUPAR_MAXIMO'])} |", f"| SEPARAR_PARTICIPANTE | {sim(o['SEPARAR_PARTICIPANTE'])} |",
         f"| SEPARAR_REGRAS_POR_GRUPO | {sim(o.get('SEPARAR_GRUPOS', True))} |",
         f"| ESQUELETO_COMPLETO | {sim(o.get('ESQUELETO_COMPLETO', True))} |",
         f"| USAR_REGRAS_NCM | {sim(bool(o['ALIQ_NCM']))} |", f"| ALIQUOTA_POR_NCM | {', '.join(o['ALIQ_NCM'])} |"]
    return "\n".join(L) + "\n"


def api_opcoes(corpo):
    """Grava no .md as opções escolhidas na tela (alíquota por NCM, agrupamento, participante)."""
    if "aliq_ncm" in corpo:
        g.OPCOES["ALIQ_NCM"] = [k for k in corpo.get("aliq_ncm") or [] if k in g.TRIBUTOS]
    if "agrupar" in corpo:
        g.OPCOES["AGRUPAR_MAXIMO"] = bool(corpo["agrupar"])
    if "separar" in corpo:
        g.OPCOES["SEPARAR_PARTICIPANTE"] = bool(corpo["separar"])
    if "esqueleto" in corpo:
        g.OPCOES["ESQUELETO_COMPLETO"] = bool(corpo["esqueleto"])
    if corpo.get("salvar", True):
        with open(g.ARQ_PADROES, encoding="utf-8") as f:
            texto = f.read()
        texto = _substituir_secao(texto, "Opções", _bloco_opcoes(), antes_de="## Grupos de operação")
        with open(g.ARQ_PADROES, "w", encoding="utf-8") as f:
            f.write(texto)
        _, EST["avisos_padroes"] = g.carregar_padroes()
    return {"aliq_ncm": g.OPCOES["ALIQ_NCM"], "agrupar": g.OPCOES["AGRUPAR_MAXIMO"],
            "separar": g.OPCOES["SEPARAR_PARTICIPANTE"], "esqueleto": g.OPCOES["ESQUELETO_COMPLETO"],
            "salvo": bool(corpo.get("salvar", True))}


def api_padroes(_):
    with open(g.ARQ_PADROES, encoding="utf-8") as f:
        return {"arquivo": g.ARQ_PADROES, "texto": f.read(), "avisos": EST["avisos_padroes"]}


def api_salvar_padroes(corpo):
    texto = corpo.get("texto")
    if texto is not None:
        with open(g.ARQ_PADROES, "w", encoding="utf-8") as f:
            f.write(texto)
    _, avisos = g.carregar_padroes()
    EST["avisos_padroes"] = avisos
    regerou = False
    if EST["cnpj"] and not EST["status"]["tarefa"]:
        o = EST["opcoes"]
        _em_segundo_plano("gerando cenários", lambda: _gerar(EST["cnpj"], o["agrupar"], o["separar"], o.get("aliq_ncm")))
        regerou = True
    return {"avisos": avisos, "regerando": regerou}


def api_importar_caminho(corpo):
    cam = (corpo.get("caminho") or "").strip().strip('"')
    if not cam or not os.path.exists(cam):
        raise LookupError(f"Caminho não encontrado: {cam or '(vazio)'}")
    _em_segundo_plano("importando XMLs", lambda: _importar_caminhos([cam]))
    return {"ok": True}


def api_gerar(corpo):
    cnpj = corpo.get("cnpj") or (EST["emit"][0][0] if EST["emit"] else None)
    if not cnpj:
        raise LookupError("Nenhum CNPJ emitente com NF-e de saída autorizada. Importe os XMLs primeiro.")
    agr, sep = bool(corpo.get("agrupar", True)), bool(corpo.get("separar", False))
    ncm = corpo.get("aliq_ncm")
    ncm = [k for k in ncm if k in g.TRIBUTOS] if isinstance(ncm, list) else None
    _em_segundo_plano("gerando cenários", lambda: _gerar(cnpj, agr, sep, ncm))
    return {"ok": True}


def api_limpar(_):
    with TRAVA:
        if EST["status"]["tarefa"]:
            raise RuntimeError("Aguarde a tarefa em andamento.")
        EST.update(docs={}, canc=set(), fonte={}, emit=[], an=None, mt=None, cen=[], cnpj=None, stats=Counter(),
                   gerado_em=None)
        EST["status"].update(msg="", prog=0.0, erro="")
    return {"ok": True}


def _receber_upload(corpo):
    """Lote de arquivos: [4 bytes tam. nome][nome UTF-8][8 bytes tamanho][conteúdo] ... (big-endian)."""
    pasta = os.path.join(DADOS, "uploads", time.strftime("%Y%m%d_%H%M%S_") + str(int(time.time() * 1000) % 1000))
    os.makedirs(pasta, exist_ok=True)
    i, n, zips = 0, 0, []
    while i < len(corpo):
        tn = int.from_bytes(corpo[i:i + 4], "big"); i += 4
        nome = corpo[i:i + tn].decode("utf-8", "replace"); i += tn
        tam = int.from_bytes(corpo[i:i + 8], "big"); i += 8
        dados = corpo[i:i + tam]; i += tam
        seguro = re.sub(r"[^\w.\-]+", "_", os.path.basename(nome)) or f"arquivo_{n}"
        destino = os.path.join(pasta, f"{n:06d}_{seguro}")
        with open(destino, "wb") as f:
            f.write(dados)
        n += 1
        if seguro.lower().endswith(".zip"):
            zips.append(destino)
        elif seguro.lower().endswith(".xml"):
            try:
                _registrar(dados, (destino, None))
            except Exception:
                with TRAVA:
                    EST["stats"]["erros"] += 1
    if zips:
        _em_segundo_plano("importando ZIP", lambda: _importar_caminhos(zips))
    else:
        _atualizar_emitentes()
    return {"recebidos": n, "zips": len(zips), "docs": len(EST["docs"])}


def api_exportar(_):
    _exige_gerado()
    buf = io.StringIO()
    buf.write(";".join(g.COLS_F2B) + "\r\n")
    for r in EST["mt"]["regras"]:
        buf.write(g.linha_csv_f2b(r) + "\r\n")
    return buf.getvalue()


def _achar_index():
    """A interface pode estar em web/index.html (padrão) ou solta ao lado do servidor.py."""
    for c in (os.path.join(WEB, "index.html"), os.path.join(AQUI, "index.html")):
        if os.path.isfile(c):
            return c
    return None


_PAGINA_SEM_INDEX = f"""<!doctype html><meta charset="utf-8"><title>Facilitador Fiscal</title>
<body style="font-family:Segoe UI,Arial,sans-serif;max-width:720px;margin:60px auto;color:#13263A;line-height:1.6">
<h1 style="color:#0D2847">Interface não encontrada</h1>
<p>O servidor está funcionando, mas não achou o arquivo <b>index.html</b> da interface.</p>
<p>Coloque o <b>index.html</b> em um destes lugares e recarregue esta página (F5):</p>
<ul><li><code>{os.path.join(WEB, "index.html")}</code> (recomendado)</li>
<li><code>{os.path.join(AQUI, "index.html")}</code></li></ul>
<p>Estrutura esperada:</p>
<pre style="background:#F2F5F9;padding:14px;border-radius:8px">{os.path.basename(AQUI)}\\
├── servidor.py
├── gerador_cenarios.py
├── padroes_configurador.md
└── web\\
    └── index.html</pre></body>"""


ROTAS_GET = {"/api/status": api_status, "/api/visao": api_visao, "/api/regras": api_regras,
             "/api/regra": api_regra, "/api/cenarios": api_cenarios, "/api/cadastros": api_cadastros,
             "/api/validacoes": api_validacoes, "/api/padroes": api_padroes, "/api/dicionario": api_dicionario,
             "/api/tipos-operacao": api_tipos, "/api/regime": api_regime, "/api/divergencias": api_divergencias,
             "/api/correcoes": api_correcoes, "/api/grupos": api_grupos, "/api/agrupamentos": api_agrupamentos,
             "/api/llm/config": api_llm_config, "/api/conhecimento": api_conhecimento}
ROTAS_POST = {"/api/importar-caminho": api_importar_caminho, "/api/gerar": api_gerar, "/api/limpar": api_limpar,
              "/api/padroes": api_salvar_padroes, "/api/tipos-operacao": api_salvar_tipos,
              "/api/regime/limpar": api_limpar_regime, "/api/correcoes": api_nova_correcao,
              "/api/correcoes/remover": api_remover_correcao, "/api/segregacoes": api_nova_segregacao,
              "/api/segregacoes/remover": api_remover_segregacao, "/api/excecoes": api_nova_excecao,
              "/api/excecoes/remover": api_remover_excecao, "/api/opcoes": api_opcoes,
              "/api/grupos/analisar": api_grupo_analisar, "/api/grupos/simular": api_grupo_simular,
              "/api/grupos": api_grupo_salvar, "/api/grupos/remover": api_grupo_remover,
              "/api/grupos/simular-remocao": api_grupo_simular_remocao,
              "/api/agrupamentos/simular": api_agrup_simular, "/api/agrupamentos": api_agrup_salvar,
              "/api/agrupamentos/remover": api_agrup_remover, "/api/codigos/renumerar": api_renumerar,
              "/api/llm/config": api_llm_salvar, "/api/llm/chat": api_llm_chat,
              "/api/proposta/validar": api_proposta_validar, "/api/proposta/simular": api_proposta_simular,
              "/api/proposta/aplicar": api_proposta_aplicar, "/api/conhecimento/desfazer": api_conhecimento_desfazer,
              "/api/padroes/restaurar": api_backup_restaurar}


class Manipulador(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _resp(self, cod, corpo, tipo="application/json; charset=utf-8", extra=None):
        dados = corpo if isinstance(corpo, bytes) else (
            corpo.encode("utf-8") if isinstance(corpo, str) else json.dumps(corpo, ensure_ascii=False).encode("utf-8"))
        self.send_response(cod)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(dados)

    def _erro(self, e):
        cod = (404 if isinstance(e, LookupError) else 409 if isinstance(e, RuntimeError)
               else 400 if isinstance(e, ValueError) else 500)
        self._resp(cod, {"erro": str(e)})

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            arq = _achar_index()
            if not arq:
                return self._resp(500, _PAGINA_SEM_INDEX.encode("utf-8"), "text/html; charset=utf-8")
            with open(arq, "rb") as f:
                return self._resp(200, f.read(), "text/html; charset=utf-8")
        if u.path == "/api/exportar-gerencial":
            try:
                txt = api_exportar_gerencial(None)
                return self._resp(200, ("\ufeff" + txt).encode("utf-8"), "text/csv; charset=utf-8",
                                  {"Content-Disposition": f'attachment; filename="REGRAS_GERENCIAL_{EST["cnpj"]}.csv"'})
            except Exception as e:
                return self._erro(e)
        if u.path == "/api/exportar-f2b":
            try:
                txt = api_exportar(None)
                return self._resp(200, ("\ufeff" + txt).encode("utf-8"), "text/csv; charset=utf-8",
                                  {"Content-Disposition": f'attachment; filename="F2B_{EST["cnpj"]}.csv"'})
            except Exception as e:
                return self._erro(e)
        f = ROTAS_GET.get(u.path)
        if not f:
            return self._resp(404, {"erro": "Rota não encontrada"})
        try:
            self._resp(200, f(parse_qs(u.query)))
        except Exception as e:
            self._erro(e)

    def do_POST(self):
        u = urlparse(self.path)
        tam = int(self.headers.get("Content-Length") or 0)
        corpo = self.rfile.read(tam) if tam else b""
        try:
            if u.path == "/api/upload":
                return self._resp(200, _receber_upload(corpo))
            if u.path == "/api/regime/upload":
                from urllib.parse import unquote
                q = parse_qs(u.query)
                return self._resp(200, _receber_regime(corpo, unquote(self.headers.get("X-Nome") or "planilha.csv"),
                                                       (q.get("modo") or ["acrescentar"])[0]))
            f = ROTAS_POST.get(u.path)
            if not f:
                return self._resp(404, {"erro": "Rota não encontrada"})
            self._resp(200, f(json.loads(corpo or b"{}")))
        except Exception as e:
            self._erro(e)


def main():
    porta = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8765
    _, avisos = g.carregar_padroes()
    EST["avisos_padroes"] = avisos
    _carregar_regime()
    _carregar_correcoes()
    _carregar_grupos()
    _carregar_conh_empresa()
    srv = ThreadingHTTPServer(("127.0.0.1", porta), Manipulador)
    url = f"http://127.0.0.1:{porta}"
    print(f"Facilitador Fiscal rodando em {url}  (Ctrl+C para encerrar)")
    if not _achar_index():
        print(f"ATENÇÃO: index.html não encontrado. Coloque-o em {os.path.join(WEB, 'index.html')}")
    for nome in ("gerador_cenarios.py", "padroes_configurador.md"):
        if not os.path.isfile(os.path.join(AQUI, nome)):
            print(f"ATENÇÃO: {nome} não encontrado em {AQUI}")
    if "--sem-navegador" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
