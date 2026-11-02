"""Posts extras do pacote do Instagram (6 formatos, além dos 3 de `instagram.py`). Mesmas regras: tudo da base, sem nome de pessoa,
sem ranking entre faculdades, nada publicado. Cada função devolve (legenda, fontes) ou (None, []) quando não há conteúdo seguro."""
import json
import re
import statistics
from collections import Counter
from datetime import date, timedelta

import gerar_site as g
import instagram as ig

LINK = ig.LINK


def _salvar(img, destino):
    img.save(destino, "PNG", optimize=True)


def _linhas(d, y, itens, tam=34, passo=70, x=72):
    """Linhas de texto simples (rótulo, valor) em cartões claros."""
    for rotulo, valor in itens:
        ig._cartao(d, x, y, ig.LARGURA - 2 * x, 100, [(rotulo, tam, "Bold", "#0A4338")], valor)
        y += 116
    return y


def post_prazos(editais, facs, hoje, destino):
    h = date.fromisoformat(hoje)
    limite = (h + timedelta(days=14)).isoformat()
    lista = [e for e in ig.abertos(editais, facs, hoje) if e["inscricao_fim"] <= limite][:6]
    if not lista:
        return None, []
    img, d, y = ig._base("Prazos dos próximos 14 dias", "Não perca o prazo")
    for e in lista:
        f = facs[e["faculdade_id"]]
        ig._cartao(d, 72, y, ig.LARGURA - 144, 104, [(f["sigla"], 34, "Bold", "#0A4338"), (f"{f['cidade']}/{f['uf']}", 24, "Regular", "#565B57")],
                   f"até {g.fmt(e['inscricao_fim'])[:5]}")
        y += 120
    _salvar(img, destino)
    legenda = ("Prazos que encerram nas próximas duas semanas, em ordem de data. Confira sempre no edital oficial: o prazo pode ser "
               f"prorrogado ou retificado.\n\nDescubra em quais você pode se inscrever: {LINK} (link na bio)\n")
    return legenda, [f"- {facs[e['faculdade_id']]['sigla']}: `{e['id']}` ({e['url_edital']})" for e in lista]


def post_taxas(editais, facs, hoje, destino):
    ab = [e for e in ig.abertos(editais, facs, hoje) if e.get("taxa_inscricao") is not None
          and "taxa_inscricao" not in (e.get("conferir_campos") or {})]
    if len(ab) < 5:
        return None, []
    t = sorted(e["taxa_inscricao"] for e in ab)
    img, d, y = ig._base("Quanto custa se inscrever?", "Taxa de inscrição")
    itens = [("Menor taxa", f"R$ {t[0]:.0f}"), ("Mediana", f"R$ {statistics.median(t):.0f}"), ("Maior taxa", f"R$ {t[-1]:.0f}")]
    y = _linhas(d, y + 10, itens)
    d.text((72, y + 10), f"Nos {len(ab)} editais abertos com taxa conferida. Cada taxa é por inscrição.", font=g._fonte(26), fill=ig.VERDE_CLARO)
    _salvar(img, destino)
    legenda = ("A taxa de inscrição varia muito de uma faculdade para outra, e em alguns editais é cobrada por campus. "
               f"Veja a taxa de cada edital antes de decidir onde se inscrever: {LINK} (link na bio)\nConfira sempre no edital oficial.\n")
    return legenda, [f"- {len(ab)} editais abertos com taxa conferida (data/editais.json); menor R$ {t[0]:.2f}, maior R$ {t[-1]:.2f}"]


def post_documentos(editais, facs, hoje, destino):
    ab = [e for e in ig.abertos(editais, facs, hoje) if e.get("documentos")]
    if len(ab) < 8:
        return None, []
    chaves = [("Histórico escolar", r"hist[oó]rico"), ("Declaração de vínculo com a faculdade", r"v[ií]nculo"),
              ("Programas das disciplinas (ementas)", r"programa|ementa|plano de ensino"), ("Documento de identidade e CPF", r"\bRG\b|identidade|\bCPF\b"),
              ("Declaração do Enade", r"enade")]
    cont = []
    for nome, rx in chaves:
        n = sum(1 for e in ab if any(re.search(rx, doc, re.I) for doc in e["documentos"]))
        if n:
            cont.append((nome, n))
    cont.sort(key=lambda kv: -kv[1])
    img, d, y = ig._base("O que separar antes de se inscrever", "Documentos mais pedidos")
    for nome, n in cont[:5]:
        ig._cartao(d, 72, y, ig.LARGURA - 144, 100, [(nome, 32, "Bold", "#0A4338")], f"{n} de {len(ab)}")
        y += 116
    d.text((72, y + 6), "Editais abertos que listam o documento. Cada edital tem a sua lista.", font=g._fonte(26), fill=ig.VERDE_CLARO)
    _salvar(img, destino)
    legenda = (f"Documentos citados nas listas de {len(ab)} editais abertos. A lista exata é a do edital da faculdade onde você vai se inscrever.\n\n"
               f"Veja os documentos de cada edital: {LINK} (link na bio)\nConfira sempre no edital oficial.\n")
    return legenda, [f"- contagem sobre {len(ab)} editais abertos com lista de documentos transcrita (campo `documentos`, com página em `evidencias`)"]


def post_estados(editais, facs, hoje, destino):
    ab = ig.abertos(editais, facs, hoje)
    c = Counter(facs[e["faculdade_id"]]["uf"] for e in ab)
    if not c:
        return None, []
    img, d, y = ig._base("Editais abertos por estado", "Onde estão os editais")
    y = _linhas(d, y + 10, [(g.NOMES_UF.get(uf, uf), f"{n} {'edital' if n == 1 else 'editais'}") for uf, n in sorted(c.items(), key=lambda kv: (g.ordem_uf(kv[0]), kv[0]))][:7])
    _salvar(img, destino)
    legenda = (f"Editais de transferência de Medicina abertos hoje, por estado, com dados conferidos no PDF oficial.\n\nVeja o seu estado: {LINK} (link na bio)\n"
               "Confira sempre no edital oficial.\n")
    return legenda, [f"- {n} editais abertos em {uf} (contagem de data/editais.json em {g.fmt(hoje)})" for uf, n in sorted(c.items())]


def post_abrem_em_breve(editais, facs, hoje, destino):
    h = date.fromisoformat(hoje)
    prox = h.month % 12 + 1
    com_aberto = {e["faculdade_id"] for e in ig.abertos(editais, facs, hoje)}
    breve = [f for f in facs.values() if f["id"] not in com_aberto and f["uf"] in g.PRIORITARIOS and prox in (f.get("meses") or [])]
    if len(breve) < 3:
        return None, []
    breve = sorted({f["sigla"]: f for f in breve}.values(), key=lambda f: f["sigla"])[:8]
    img, d, y = ig._base(f"Costumam abrir em {g.MESES[prox - 1]}", "Pelo histórico")
    for f in breve[:6]:
        ig._cartao(d, 72, y, ig.LARGURA - 144, 90, [(f"{f['sigla']} · {f['cidade']}/{f['uf']}", 32, "Bold", "#0A4338")])
        y += 106
    d.text((72, y + 6), "Pelos editais anteriores. Não é data de abertura.", font=g._fonte(26), fill=ig.VERDE_CLARO)
    _salvar(img, destino)
    legenda = (f"Faculdades que, pelo histórico dos editais anteriores, costumam abrir transferência em {g.MESES[prox - 1]}. "
               f"É uma tendência, não uma promessa: cada faculdade decide a cada semestre.\n\nReceba o aviso quando abrir: {LINK} (link na bio)\n")
    return legenda, [f"- {f['sigla']} ({f['id']}): meses no histórico {f.get('meses')}" for f in breve]


def post_chance_real(editais, facs, hoje, destino):
    """Só resultado publicado pela faculdade com a grandeza certa (vagas do edital × classificados dentro das vagas), com a página."""
    try:
        res = json.loads((ig.PASTA / "data" / "resultados.json").read_text(encoding="utf-8"))
    except OSError:
        return None, []
    por_id = {e["id"]: e for e in editais}
    boas = []
    for r in res:
        n = r["numeros"]
        if n.get("vagas_ofertadas", {}).get("grandeza") == "vagas_do_edital" and n.get("aprovados", {}).get("grandeza") == "classificados_dentro_das_vagas" \
                and r["edital_id"] in por_id:
            boas.append((r, por_id[r["edital_id"]]))
    if len(boas) < 2:
        return None, []
    boas.sort(key=lambda t: (t[1].get("inscricao_fim") or ""), reverse=True)
    img, d, y = ig._base("Vagas preenchidas na última seleção", "Resultado divulgado")
    fontes = []
    for r, e in boas[:5]:
        f = facs[e["faculdade_id"]]
        n = r["numeros"]
        ig._cartao(d, 72, y, ig.LARGURA - 144, 118, [(f"{f['sigla']} · {e.get('semestre_ingresso')}", 32, "Bold", "#0A4338"),
                   (f"{n['vagas_ofertadas']['valor']} vagas · {n['aprovados']['valor']} classificados dentro das vagas", 24, "Regular", "#565B57")])
        y += 134
        fontes.append(f"- {f['sigla']} {e.get('semestre_ingresso')}: `{e['id']}`, vagas p. {n['vagas_ofertadas']['pagina']}, classificados p. {n['aprovados']['pagina']} ({r['fonte_url']})")
    d.text((72, y + 6), "Estas faculdades não divulgam quantos se inscreveram: sem isso, não dá para calcular a concorrência.", font=g._fonte(26), fill=ig.VERDE_CLARO)
    _salvar(img, destino)
    legenda = ("Quantas vagas havia e quantos candidatos foram classificados dentro delas nas últimas seleções que a própria faculdade divulgou. "
               "Só números agregados, nunca nomes. Estas faculdades não divulgam o total de inscritos, então o número não mostra a concorrência. "
               "Muitas nem publicam o resultado.\n\n"
               f"Veja o que cada edital exige: {LINK} (link na bio)\nConfira sempre no edital oficial e na fonte indicada.\n")
    return legenda, fontes


EXTRAS = [("terca-prazos-14-dias", post_prazos), ("quinta-taxas", post_taxas), ("sabado-documentos", post_documentos),
          ("domingo-editais-por-estado", post_estados), ("segunda2-costumam-abrir", post_abrem_em_breve), ("quarta2-chance-real", post_chance_real)]
