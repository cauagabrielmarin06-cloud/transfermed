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
(V) nenhuma faculdade dos `fatos` aparece no post do dia anterior nem do dia seguinte (docs/social), exceto na lista de editais abertos da segunda;
(g) o gancho (a chamada principal, `gancho`) é específico, não "leia com atenção": pode ser sem número (12/11/2026), desde que seja uma pergunta ou um fato
    concreto e traga um ponto de apoio medível: número, valor ou data; a sigla de uma faculdade dos `fatos`; ou um termo do edital (prova, nota, vaga, taxa, prazo...).

Itens do privado/PADRAO_DE_QUALIDADE.md (seção 3) que dá para medir (10/11/2026); a data de publicação é `data` do post (às 12h) ou `hoje`:
(P2) nenhum prazo citado vence antes de 48 h após a publicação;
(P3) gancho de até 8 palavras;
(P6) leitura no celular, medida nos pixels de cada imagem (instagram_visual.py): texto principal >= 36 px, apoio e rodapé >= 26 px
     em 1080 px, nenhuma área vazia maior que 1/3 da tela;
(P8) rodapé de fonte (edital, p. N) em cada tela que traz dado (data, valor em R$ ou vagas); o texto de cada tela vem de `telas`
     (post.json) ou dos slides do robô;
(P9) legenda com "Confira sempre o edital oficial" e até 7 hashtags.
"""
import json
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path

import gerar_site as g

DEMONSTRATIVO = r"(?:estes|estas|esses|essas|destes|destas|desses|dessas|nestes|nestas|nesses|nessas)"
SUBSTANTIVOS = {"editais": "edital", "faculdades": "faculdade", "cursos": "curso"}
ABSOLUTOS = re.compile(r"\b(todos|todas|nenhum|nenhuma|único|única|únicos|únicas|unico|unica)\b", re.I)
PROIBIDOS = [
    (re.compile(r"\bchances?\b", re.I), "fala em chance"),
    (re.compile(r"\branking\b|\bposi[cç][aã]o\b|\bmelhores?\b|\bpiores?\b|\bmais f[aá]cil\b|\bmais dif[ií]cil\b|\btop\s*\d+\b|\b\d+[ºo°]\s*lugar\b", re.I), "compara ou ordena faculdades (ranking)"),
    (re.compile(r"\b(?:menor|maior)\s+(?:taxa|valor|nota|prazo|vagas?|n[uú]mero|concorr\w*)\b|\bmais\s+(?:barat|car[oa]|concorrid|dispon)\w*|\b(?:cobra|cobram)\s+(?:mais|menos)\b", re.I),
     "compara faculdades entre si (menor, maior, mais, menos): é ranking"),
    (re.compile(r"\bgarant\w*|\bpromess\w*|\bpromet\w*|\bcertez[ao]\b|\baprova[cç][aã]o\b|\baprovad[oa]s?\b|\bsem risco\b", re.I), "faz promessa ou garantia"),
]
ASPAS = re.compile(r"[“”\"«»]")
ATRIBUICAO = re.compile(r"\bo\s+edital\s+(diz|afirma|exige|determina|estabelece|prev[eê]|informa|garante)\b", re.I)
VARIAS_PAGINAS = re.compile(r"\bp[áa]gs?\.|\buma\s+(?:destas|dessas)\s+p[áa]ginas|\bp[áa]ginas?\s+\d+\s*(?:,|e)\s*\d", re.I)
GANCHO_TERMO = re.compile(r"\b(prova|provas|nota|notas|vaga|vagas|taxa|taxas|prazo|prazos|edital|editais|inscri[cç][aã]o|per[ií]odo|semestre|hist[oó]rico|documentos?|exterior|resultado|matr[ií]cula)\b", re.I)
GANCHO_VAGO = re.compile(r"\bleia\b|\bcom aten[cç][aã]o\b|\bdetalhes?\b|\bdescubra\b|\bconfira\b|\bfique (de )?olho\b|\barmadilha\b", re.I)


def pagina_unica(pag):
    """True se `pag` é uma só página ('3', 'Anexo 1, p. 1'); False para '4, 5, 6, 8 e 9', '2 e 3' ou vazio."""
    return len(re.findall(r"\d+", re.sub(r"anexo\s*\d+", "", str(pag or ""), flags=re.I))) == 1


def edital_confirmado(e, campos=None):
    """None se o edital pode ser usado em post; senão o motivo.
    Sem `campos` (post antigo, que não registra o campo usado): exige o edital inteiro limpo (status 'ok', nada em conferir).
    Com `campos` (os campos que o post usa, ex.: inscricao_fim): vale por campo. Reprova se algum campo usado está em
    conferir_campos (ou se o edital inteiro está marcado, "edital"), ou se o status é 'conferir' sem conferir_campos detalhado.
    Dúvida em outro campo (resultado, vagas...) não impede um post que só usa o prazo."""
    if e.get("fonte_dados") != "manual":
        return "lido só automaticamente (fonte_dados != manual)"
    conf = e.get("conferir_campos") or {}
    if e.get("prazo_contraditorio") and (campos is None or "inscricao_fim" in campos):
        return "campo usado no post em 'conferir': inscricao_fim (o edital traz duas datas; o prazo seguro vale só na ficha e no alerta, com o aviso)"
    if campos is None:
        if e.get("status") != "ok":
            return f"status {e.get('status')!r} (precisa ser 'ok')"
        if conf:
            return "tem campo em 'conferir': " + ", ".join(sorted(conf))
    else:
        if e.get("status") not in ("ok", "conferir"):
            return f"status {e.get('status')!r} (precisa ser 'ok' ou 'conferir' com campos detalhados)"
        if e.get("status") == "conferir" and not conf:
            return "status 'conferir' sem conferir_campos detalhado"
        ruins = sorted(c for c in set(campos) if c in conf)
        if ruins or "edital" in conf:
            return "campo usado no post em 'conferir': " + ", ".join(ruins or ["edital"])
        if e.get("status") == "conferir":
            return None
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


def _faculdade_conhecida(nome, edital, facs):
    """Aceita a sigla, o nome ou o id da faculdade, e o formato do FONTES.md ('USCS São Caetano', 'Unime externa'): sigla da faculdade do edital + complemento."""
    nome = str(nome or "").strip().casefold()
    if not nome:
        return False
    for fid, x in facs.items():
        if nome in {str(x.get("sigla") or "").casefold(), str(x.get("nome") or "").casefold(), str(fid).casefold()} - {""}:
            return True
    fac = facs.get((edital or {}).get("faculdade_id"))
    sigla = str((fac or {}).get("sigla") or "").casefold()
    return bool(sigla) and (nome == sigla or nome.startswith(sigla + " "))


SOCIAL = Path(__file__).resolve().parent / "docs" / "social"
# a segunda-feira (carrossel com todos os editais abertos) lista faculdades de propósito: a regra dos dias seguidos vale para os posts de um tema
POSTS_DE_LISTA = {"editais-abertos-da-semana"}


def faculdades_do_post(post):
    return {(f.get("faculdade") or "").strip().lower() for f in post.get("fatos") or [] if f.get("faculdade")}


def repete_faculdade_vizinha(post, hoje, pasta=None):
    """(V) mesma faculdade em dias seguidos reprova (decisão de 12/11/2026): compara os `fatos` do post com os do dia anterior e do dia seguinte
    gravados em `docs/social/AAAA-MM-DD/post.json`. Post de lista (editais abertos da semana) fica fora. Dia sem post não conta."""
    if post.get("tipo") in POSTS_DE_LISTA:
        return []
    mias, problemas = faculdades_do_post(post), []
    for delta in (-1, 1):
        d = (date.fromisoformat(str(hoje)) + timedelta(days=delta)).isoformat()
        try:
            viz = json.loads(((pasta or SOCIAL) / d / "post.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if viz.get("tipo") in POSTS_DE_LISTA:
            continue
        for sigla in sorted(mias & faculdades_do_post(viz)):
            problemas.append(f"(V) a faculdade {sigla.upper()} também está no post de {d}: não repetir faculdade em dias seguidos")
    return problemas


def checar(post, editais, facs, hoje, padrao=True, pasta_social=None):
    """Regras (a) a (g) e, com `padrao=True` (o normal), os itens 2, 3, 6, 8 e 9 do padrão de qualidade. `padrao=False` só nos testes que
    examinam o conteúdo que o gerador monta, sem o desenho das imagens."""
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
        campos = [f.get("campo") for f in post.get("fatos") or [] if f.get("edital") == i]
        campos = None if (not campos or "?" in campos or not all(campos)) else campos
        motivo = edital_confirmado(e, campos)
        if motivo:
            problemas.append(f"(a) edital {i} ({e.get('faculdade_id')}): {motivo}")
    fatos = post.get("fatos") or []  # (c)
    for i in usados:
        mine = [f for f in fatos if f.get("edital") == i]
        if not mine:
            problemas.append(f"(c) edital {i}: nenhum fato registrado com faculdade e página")
        for f in mine:
            if not _faculdade_conhecida(f.get("faculdade"), por_id.get(i), facs):
                problemas.append(f"(c) edital {i}: fato sem faculdade conhecida")
            if not re.search(r"\d", str(f.get("pagina") or "")):
                problemas.append(f"(c) edital {i} ({f.get('campo')}): fato sem página")
    textos = [t for t in (post.get("textos") or []) if t] + [post.get("legenda") or ""] + list(post.get("alts") or [])
    todo = "\n".join(textos)
    univ = _universo(editais, facs, hoje)  # (b)
    for m in re.finditer(r"(?<![\d/,.])(\d+)[ \t]+(editais|faculdades|cursos)\b", todo, re.I):   # mesma linha: "p. 19" + "Faculdades..." de outro texto não é "19 faculdades"
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
        ancora = re.search(r"\d", gancho) or GANCHO_TERMO.search(gancho) or any(
            re.search(r"\b" + re.escape(f["faculdade"]) + r"\b", gancho, re.I) for f in fatos if f.get("faculdade"))
        if not ancora:
            problemas.append(f"(g) o gancho “{gancho}” não é específico: traga um número, valor, data, a faculdade ou um termo do edital (prova, nota, vaga, taxa, prazo...)")
        if GANCHO_VAGO.search(gancho):
            problemas.append(f"(g) o gancho “{gancho}” é genérico (“leia com atenção”, “detalhes”...): diga o fato")
    if not gancho and re.search(r"leia o edital com aten[cç][aã]o", todo, re.I):
        problemas.append("(g) o texto usa o gancho genérico “Leia o edital com atenção”")
    return problemas + repete_faculdade_vizinha(post, hoje, pasta_social) + (checar_padrao(post, hoje) if padrao else [])


MESES = {"janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
         "outubro": 10, "novembro": 11, "dezembro": 12}
DATA_NUMERICA = re.compile(r"(?<![\d/.])(\d{1,2})º?/(\d{1,2})(?:/(\d{4}|\d{2}))?(?![\d/])")
DATA_POR_EXTENSO = re.compile(r"(?<![\d/])(\d{1,2})º?\s+de\s+(" + "|".join(MESES) + r")(?:\s+de\s+(\d{4}))?\b", re.I)
PRAZO = re.compile(r"(?:\baté|\bfecha\w*|\bencerr\w*|\bvenc\w*|\bprazo|\btermin\w*|\búltimo dia|\blimite|\d\s+a)\s+(?:(?:o|no)\s+)?(?:dia\s+)?(?:de\s+)?$", re.I)
PASSADO = re.compile(r"\b(desde|abriu\s+em|abriram\s+em|saiu\s+em|publicad[oa]s?\s+em|divulgad[oa]s?\s+em)\s+(?:o\s+dia\s+|dia\s+)?$", re.I)
CONTADOR = re.compile(r"\d{1,2}/\d{1,2}")
DADO_NA_TELA = re.compile(r"(?<![\d/])\d{1,2}º?/\d{1,2}(?:/\d{2,4})?(?![\d/])|R\$\s*\d|\b\d+\s+vagas?\b", re.I)
FONTE_NA_TELA = re.compile(r"\bp\.\s*\d|\bp[áa]gs?\.\s*\d|\bp[áa]gina\s+\d", re.I)
HORAS_ANTES = 48
HORA_DA_PUBLICACAO = 12


def _data_publicacao(post, hoje):
    try:
        return date.fromisoformat(str(post.get("data") or hoje))
    except ValueError:
        return date.fromisoformat(str(hoje))


def datas_citadas(texto, pub):
    """[(texto da data, date)] de cada data citada como PRAZO (dd/mm, dd/mm/aaaa, 'dd de mês' depois de até, fecha, encerra, vence, prazo, último dia,
    limite ou 'N a'), exceto as ditas no passado ('desde 03/11'). Data de calendário ('semana de 09/11') não é prazo."""
    texto = re.sub(r"https?://\S+", " ", texto or "")
    achadas = []
    for rx in (DATA_NUMERICA, DATA_POR_EXTENSO):
        for m in rx.finditer(texto):
            antes = texto[max(0, m.start() - 40):m.start()]
            if PASSADO.search(antes) or not PRAZO.search(antes):   # só conta data que é prazo ("até 16/11", "fecha em 20/11", "02 a 07/12")
                continue
            if rx is DATA_NUMERICA:
                dia, mes, ano = int(m.group(1)), int(m.group(2)), m.group(3)
            else:
                dia, mes, ano = int(m.group(1)), MESES[m.group(2).lower()], m.group(3)
            if not (1 <= mes <= 12 and 1 <= dia <= 31):
                continue
            ano = (2000 + int(ano) if len(ano) == 2 else int(ano)) if ano else pub.year
            try:
                d = date(ano, mes, dia)
            except ValueError:
                continue
            if not m.group(3) and (pub - d).days > 180:   # sem ano e muito para trás: é o próximo ano (cita-se em dezembro um prazo de janeiro)
                d = date(d.year + 1, mes, dia)
            achadas.append((m.group(0), d))
    return achadas


def _textos_da_tela(t):
    import instagram_cartoes as cart
    return cart.textos_da_tela(t) if isinstance(t, dict) else [str(t)]


def _textos_dos_slides(post):
    return [list(getattr(s, "textos", []) or []) for s in (post.get("slides") or [])]


def _telas_com_textos(post):
    """None se o post não declara as telas; senão a lista de listas de texto, uma por tela."""
    if post.get("telas") is not None:
        return [_textos_da_tela(t) for t in post["telas"]]
    if post.get("slides") is not None:
        return _textos_dos_slides(post)
    return None


def _elementos_de_texto(post):
    """Cada pedaço de texto do post, separado (o contador de telas '2/5' é um pedaço só e não é data)."""
    pedacos = [t for t in (post.get("textos") or []) if t] + list(post.get("alts") or []) + [post.get("legenda") or "", post.get("gancho") or ""]
    for textos in _telas_com_textos(post) or []:
        pedacos += textos
    return [p for p in pedacos if p and not CONTADOR.fullmatch(p.strip())]


def checar_padrao(post, hoje):
    """Itens 2, 3, 6, 8 e 9 do padrão de qualidade (seção 3 de privado/PADRAO_DE_QUALIDADE.md). Lista de problemas, cada um com o item."""
    problemas = []
    pub = _data_publicacao(post, hoje)
    limite = datetime.combine(pub, time(HORA_DA_PUBLICACAO)) + timedelta(hours=HORAS_ANTES)
    vistos = set()
    for pedaco in _elementos_de_texto(post):  # (P2)
        for txt, d in datas_citadas(pedaco, pub):
            if datetime.combine(d, time(23, 59)) < limite and (txt, d) not in vistos:
                vistos.add((txt, d))
                problemas.append(f"(P2) a data “{txt}” ({d.strftime('%d/%m/%Y')}) vence menos de 48 h depois da publicação ({pub.strftime('%d/%m/%Y')} às 12h)")
    gancho = (post.get("gancho") or "").strip()  # (P3)
    palavras = len(gancho.split())   # contagem crua: "R$ 100" são 2 palavras (12/11/2026: um gancho de 9 palavras passou por contar R$ e valor como uma só)
    if gancho and palavras > 8:
        problemas.append(f"(P3) o gancho tem {palavras} palavras (máximo 8): “{gancho}”")
    imagens = None  # (P6)
    if post.get("_imagens") is not None:
        imagens = [str(x) for x in post["_imagens"]]
        if not imagens:
            problemas.append("(P6) a pasta do post não tem imagens para medir")
    if imagens or post.get("slides"):
        import tempfile

        import instagram_visual as vis
        with tempfile.TemporaryDirectory() as tmp:
            caminhos = list(imagens or [])
            if not imagens:
                for i, lona in enumerate(post.get("slides") or [], 1):
                    alvo = Path(tmp) / f"{i:02d}.jpg"
                    lona.salvar(alvo)
                    caminhos.append(str(alvo))
            for caminho in caminhos:
                problemas += ["(P6) " + x for x in vis.problemas(caminho)]
    telas = _telas_com_textos(post)  # (P8)
    if telas is not None:
        if not telas:
            problemas.append("(P8) o post não declara o texto de cada tela (telas)")
        for i, textos in enumerate(telas, 1):
            texto = " ".join(t for t in textos if not CONTADOR.fullmatch(t.strip()))
            if DADO_NA_TELA.search(texto) and not FONTE_NA_TELA.search(texto):
                problemas.append(f"(P8) a tela {i} traz dado (data, valor ou vagas) sem rodapé de fonte (“edital, p. N”)")
    legenda = post.get("legenda") or ""  # (P9)
    if "confira sempre o edital oficial" not in legenda.lower():
        problemas.append("(P9) a legenda não traz “Confira sempre o edital oficial”")
    tags = re.findall(r"(?<!\w)#\w+", re.sub(r"https?://\S+", " ", legenda))
    if len(tags) > 7:
        problemas.append(f"(P9) a legenda tem {len(tags)} hashtags (máximo 7)")
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
    post["_imagens"] = sorted(str(p) for p in pasta.glob("[0-9][0-9].jpg"))
    if post.get("telas") is None:
        post["telas"] = []   # a pasta existe: um post sem `telas` não declara o texto de cada tela (P8)
    return post
