"""Checagem que TRAVA o post do Instagram antes de ele ir para docs/social (09/11/2026).

Por quê: o post de 10/11 saiu com "Leia antes de pagar a taxa" a partir de um edital que não cita taxa e ainda estava em "conferir".
A regra do projeto é que dado de edital só vai ao ar conferido no PDF, com a página, e que o texto não afirma mais do que os dados sustentam.

Entrada: um dicionário com as mesmas chaves do `post.json` gravado pelo gerador:
  usados   lista de ids dos editais que aparecem no post
  fatos    [{"faculdade": sigla, "edital": id, "campo": "...", "pagina": "..."}]  um por edital usado
  textos   texto de cada imagem, na ordem em que é lido (inclui os números dos painéis)
  legenda  a legenda
Devolve a lista de problemas. Lista vazia = pode ir ao ar. Qualquer problema = o post não é gravado.

(a) edital usado sem status "ok", com "conferir" ou lido só pelo robô;
(b) quantidade ou "todos/nenhum/único" que os dados não sustentam;
(c) fato sem faculdade ou sem página;
(d) "chance", ranking ou promessa;
(e) aspas ou "O edital diz/afirma/exige..." sem o texto literal do PDF (o post só pode citar entre aspas um trecho que venha em `literais`:
    [{"edital", "trecho", "pagina"}], copiado do PDF; os dados do projeto guardam resumos, não o texto literal, então o gerador nunca cita);
(f) uma página única por fato (nada de "págs. 4, 5, 6, 8 e 9" nem "uma destas páginas");
(g) o gancho (a chamada principal, `gancho`) traz o fato concreto (número, valor ou data), não "leia com atenção".
"""
import re
from datetime import date

import gerar_site as g

DEMONSTRATIVO = r"(?:estes|estas|esses|essas|destes|destas|desses|dessas)"
SUBSTANTIVOS = {"editais": "edital", "faculdades": "faculdade", "cursos": "curso"}
ABSOLUTOS = re.compile(r"\b(todos|todas|nenhum|nenhuma|único|única|únicos|únicas|unico|unica)\b", re.I)
PROIBIDOS = [
    (re.compile(r"\bchances?\b", re.I), "fala em chance"),
    (re.compile(r"\branking\b|\bposi[cç][aã]o\b|\bmelhores?\b|\bpiores?\b|\bmais f[aá]cil\b|\bmais dif[ií]cil\b|\btop\s*\d+\b|\b\d+[ºo°]\s*lugar\b", re.I), "compara ou ordena faculdades (ranking)"),
    (re.compile(r"\bgarant\w*|\bpromess\w*|\bpromet\w*|\bcertez[ao]\b|\baprova[cç][aã]o\b|\baprovad[oa]s?\b|\bsem risco\b", re.I), "faz promessa ou garantia"),
]
ASPAS = re.compile(r"[“”\"«»]")
ATRIBUICAO = re.compile(r"\bo\s+edital\s+(diz|afirma|exige|determina|estabelece|prev[eê]|informa|garante)\b", re.I)
VARIAS_PAGINAS = re.compile(r"\bp[áa]gs?\.|\buma\s+(?:destas|dessas)\s+p[áa]ginas|\bp[áa]ginas?\s+\d+\s*(?:,|e)\s*\d", re.I)
GANCHO_VAGO = re.compile(r"\bleia\b|\bcom aten[cç][aã]o\b|\bdetalhes?\b|\bdescubra\b|\bconfira\b|\bfique (de )?olho\b|\barmadilha\b", re.I)


def pagina_unica(pag):
    """True se `pag` é uma só página ('3', 'Anexo 1, p. 1'); False para '4, 5, 6, 8 e 9', '2 e 3' ou vazio."""
    return len(re.findall(r"\d+", re.sub(r"anexo\s*\d+", "", str(pag or ""), flags=re.I))) == 1


def edital_confirmado(e):
    """None se o edital pode ser usado em post; senão o motivo."""
    if e.get("status") != "ok":
        return f"status {e.get('status')!r} (precisa ser 'ok')"
    if e.get("fonte_dados") != "manual":
        return "lido só automaticamente (fonte_dados != manual)"
    if e.get("conferir_campos"):
        return "tem campo em 'conferir': " + ", ".join(sorted(e["conferir_campos"]))
    if re.search(r"conferir|lido automaticamente", str(e.get("observacao") or ""), re.I):
        return "a observação do edital pede conferência"
    return None


def pagina_txt(ev):
    """A página como o dado registra, sem os itens entre parênteses: 5 -> '5'; '2 (itens 1.8), 2 e 3 (item 3.2)' -> '2 e 3'. '' se não houver."""
    if ev is None or ev is False or ev == "":
        return ""
    if isinstance(ev, int):
        return str(ev)
    limpo = re.sub(r"\s*\([^)]*\)", "", str(ev)).strip(" ,;")
    if not re.search(r"\d", limpo):
        return ""
    if re.fullmatch(r"[\d,\se]+", limpo):
        nums = sorted({int(n) for n in re.findall(r"\d+", limpo)})
        return nums and (str(nums[0]) if len(nums) == 1 else ", ".join(map(str, nums[:-1])) + f" e {nums[-1]}") or ""
    return limpo


def com_pagina(e, campo):
    return pagina_txt((e.get("evidencias") or {}).get(campo))


def rotulo_pagina(pag):
    return ("págs. " if re.search(r"\d\D+\d", pag) else "p. ") + pag


def _universo(editais, facs, hoje):
    """O que os dados dizem de verdade: TODOS os editais abertos hoje (de qualquer status) e as faculdades deles."""
    ab = [e for e in editais if e.get("faculdade_id") in facs and g.situacao(e, hoje) == "aberto"]
    return {"editais": len(ab), "faculdades": len({e["faculdade_id"] for e in ab}), "cursos": len({e["faculdade_id"] for e in ab})}


def checar(post, editais, facs, hoje):
    problemas = []
    por_id = {e["id"]: e for e in editais}
    usados = list(post.get("usados") or [])
    if not usados:
        problemas.append("(a) o post não declara nenhum edital usado")
    for i in usados:  # (a)
        e = por_id.get(i)
        if e is None:
            problemas.append(f"(a) edital {i} não existe nos dados")
            continue
        motivo = edital_confirmado(e)
        if motivo:
            problemas.append(f"(a) edital {i} ({e.get('faculdade_id')}): {motivo}")
    fatos = post.get("fatos") or []  # (c)
    for i in usados:
        mine = [f for f in fatos if f.get("edital") == i]
        if not mine:
            problemas.append(f"(c) edital {i}: nenhum fato registrado com faculdade e página")
        for f in mine:
            if not f.get("faculdade") or f["faculdade"] not in {x.get("sigla") for x in facs.values()}:
                problemas.append(f"(c) edital {i}: fato sem faculdade conhecida")
            if not re.search(r"\d", str(f.get("pagina") or "")):
                problemas.append(f"(c) edital {i} ({f.get('campo')}): fato sem página")
    textos = [t for t in (post.get("textos") or []) if t] + [post.get("legenda") or ""] + list(post.get("alts") or [])
    todo = "\n".join(textos)
    univ = _universo(editais, facs, hoje)  # (b)
    for m in re.finditer(r"(?<![\d/,.])(\d+)\s+(editais|faculdades|cursos)\b", todo, re.I):
        n, subst = int(m.group(1)), m.group(2).lower()
        antes = todo[max(0, m.start() - 14):m.start()]
        if re.search(DEMONSTRATIVO + r"\s*(?:\w+\s+){0,2}$", antes, re.I) or n == univ[subst]:
            continue
        problemas.append(f"(b) “{m.group(0)}” afirma uma quantidade que os dados não sustentam ({univ[subst]} {subst} abertos no total); use “Estes {n} {subst}”")
    for m in ABSOLUTOS.finditer(todo):
        problemas.append(f"(b) “{m.group(0)}” é uma afirmação absoluta que os dados não sustentam")
    if re.search(r"\btaxa\b", todo, re.I):  # a taxa só pode ser citada se todo edital usado tem a taxa conferida
        sem = [i for i in usados if i in por_id and (por_id[i].get("taxa_inscricao") is None or "taxa_inscricao" in (por_id[i].get("conferir_campos") or {}))]
        if sem and post.get("tipo") != "taxas":
            problemas.append("(b) o texto fala em taxa, mas o(s) edital(is) " + ", ".join(sem) + " não tem(têm) taxa conferida")
    for rx, porque in PROIBIDOS:  # (d)
        for m in rx.finditer(todo):
            problemas.append(f"(d) “{m.group(0)}”: {porque}")
    literais = [x for x in (post.get("literais") or []) if x.get("trecho") and pagina_unica(x.get("pagina"))]  # (e)
    sem_citacao = todo
    for x in literais:
        for abre, fecha in (("“", "”"), ('"', '"'), ("«", "»"), ("", "")):  # a citação inteira, com as aspas, só se o trecho é literal
            sem_citacao = sem_citacao.replace(abre + x["trecho"] + fecha, " ")
    if ASPAS.search(sem_citacao):
        problemas.append("(e) o texto usa aspas sem o trecho literal do PDF (resumo entre aspas parece citação do edital)")
    for m in ATRIBUICAO.finditer(sem_citacao):
        problemas.append(f"(e) “{m.group(0)}” sem o texto literal do PDF")
    for f in fatos:  # (f)
        if f.get("pagina") and not pagina_unica(f["pagina"]):
            problemas.append(f"(f) edital {f.get('edital')} ({f.get('campo')}): o fato cita mais de uma página ({f['pagina']}); precisa de uma página única")
    for m in VARIAS_PAGINAS.finditer(todo):
        problemas.append(f"(f) “{m.group(0)}”: o texto cita várias páginas; precisa de uma página única por fato")
    gancho = (post.get("gancho") or "").strip()  # (g)
    if not gancho:
        problemas.append("(g) o post não registra o gancho (chamada principal)")
    else:
        if not re.search(r"\d", gancho):
            problemas.append(f"(g) o gancho “{gancho}” não traz o fato concreto (número, valor ou data)")
        if GANCHO_VAGO.search(gancho):
            problemas.append(f"(g) o gancho “{gancho}” é genérico (“leia com atenção”, “detalhes”...): diga o fato")
    if not gancho and re.search(r"leia o edital com aten[cç][aã]o", todo, re.I):
        problemas.append("(g) o texto usa o gancho genérico “Leia o edital com atenção”")
    return problemas


def post_de_pasta(pasta):
    """Reconstrói o dicionário a partir do que foi gravado numa pasta docs/social/AAAA-MM-DD (post.json, legenda.txt, fontes.txt).
    Posts antigos, sem `usados`/`fatos`, são lidos do fontes.txt (ids entre crases e 'página N'), o suficiente para reprová-los."""
    import json
    from pathlib import Path
    pasta = Path(pasta)
    post = json.loads((pasta / "post.json").read_text(encoding="utf-8"))
    post["legenda"] = (pasta / "legenda.txt").read_text(encoding="utf-8")
    fontes = (pasta / "fontes.txt").read_text(encoding="utf-8") if (pasta / "fontes.txt").exists() else ""
    if "usados" not in post:
        post["usados"] = re.findall(r"`([0-9a-f]{12})`", fontes)
        post["fatos"] = []
        for linha in fontes.splitlines():
            m = re.match(r"- ([^:]+): `([0-9a-f]{12})`(.*)", linha)
            if m:
                pg = re.search(r"p[áa]gina\s+(\d[^(]*)", m.group(3))
                post["fatos"].append({"faculdade": m.group(1), "edital": m.group(2), "campo": "?", "pagina": pg.group(1).strip() if pg else ""})
    post.setdefault("textos", [])
    post.setdefault("gancho", "")
    return post
