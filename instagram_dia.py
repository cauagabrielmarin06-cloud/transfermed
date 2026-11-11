"""Instagram diário (09/11/2026): monta, da base, o post do DIA SEGUINTE. Roda toda madrugada no GitHub Actions (instagram_dia.yml).

Identidade (logo v2): fundo azul-escuro #0B1E2C, verde-água #2CC8BA, logo no canto, anéis de radar, nenhuma área vazia (o corpo do
post estica os cartões e termina num painel de número que absorve a sobra). JPEG 1080x1350, até 8 MB cada.

Saída:
  docs/social/AAAA-MM-DD/01.jpg, 02.jpg...   imagens, com link https público (o Pages serve; é o que o Instagram precisa para publicar)
  docs/social/AAAA-MM-DD/post.json           tipo, endereços das imagens e texto alternativo
  docs/social/AAAA-MM-DD/legenda.txt e fontes.txt   no Actions (o privado/ não vai para o Git)
  privado/instagram/AAAA-MM-DD/legenda.txt e fontes.txt   quando a pasta privado/ existe (no computador do dono)
  `python instagram_dia.py --sincronizar` copia as legendas e fontes dos próximos dias do docs/social para o privado/ (depois do git pull).

Calendário (o dia da publicação decide o formato; sem dado seguro, cai para o próximo da lista de reserva):
  segunda  editais abertos da semana (carrossel)       terça    armadilha do edital (regra real, com a página)
  quarta   prazos que fecham em 14 dias                quinta   taxas de inscrição (mínima, mediana, máxima)
  sexta    quem aceita estudo no exterior              sábado   documentos mais pedidos
  domingo  editais abertos por estado
  (quinta a domingo: decisão do Claude em 09/11/2026, porque o pedido do dono veio cortado depois de "quarta"; fácil de mudar em CALENDARIO)

Regras de conteúdo (as mesmas do instagram.py): só dado de edital conferido e com prazo firme; nenhuma pessoa citada; nenhum ranking entre
faculdades (listas em ordem de prazo); nada inventado: sem dado seguro, o post do dia cai na reserva ou não sai (SEM_POST.txt).
Nada é publicado no Instagram por este script: ele só gera os arquivos.

uso: python instagram_dia.py [--data AAAA-MM-DD] [--manter 14] [--sincronizar]
"""
import argparse
import json
import re
import statistics
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import gerar_site as g
import instagram as ig
import instagram_checagem as ck

PASTA = Path(__file__).resolve().parent
SOCIAL = PASTA / "docs" / "social"
PRIVADO = PASTA / "privado" / "instagram"
SITE = "https://www.transfermed.com.br"
LINK = "transfermed.com.br/diagnostico/?origem=instagram"
LOGO = PASTA / "docs" / "assets" / "marca" / "logo-512-v3.png"
LARGURA, ALTURA = 1080, 1350
AZUL, AZUL_2, AZUL_3 = "#0B1E2C", "#10293A", "#17384D"
VERDE_AGUA, BRANCO, CINZA = "#2CC8BA", "#FFFFFF", "#9FB6C3"
LIMITE_BYTES = 8 * 1024 * 1024
BRASILIA = timezone(timedelta(hours=-3))
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
HASHTAGS = "#transferenciamedicina #medicina #transferenciaexterna #estudantedemedicina"


def rgb(hexa, a=255):
    h = hexa.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


# ---------------------------------------------------------------- desenho

class _Registro:
    """Envolve o ImageDraw e guarda cada texto desenhado, na ordem em que é lido: é o que a checagem examina (instagram_checagem.py)."""

    def __init__(self, d, textos):
        self._d, self._textos = d, textos

    def text(self, xy, texto, *a, **k):
        self._textos.append(str(texto))
        return self._d.text(xy, texto, *a, **k)

    def __getattr__(self, nome):
        return getattr(self._d, nome)


class Lona:
    """Uma imagem do post (criada por instagram_cartoes.desenhar) com os textos desenhados nela."""

    def texto(self):
        return "\n".join(self.textos)   # uma linha por texto: "p. 19" + nome da faculdade não vira "19 faculdades" na checagem (b)

    def salvar(self, destino):
        """JPEG 1080x1350 de até 8 MB: baixa a qualidade só se passar do limite (na prática fica em poucas centenas de KB)."""
        rgb_img = self.Image.new("RGB", self.img.size, rgb(AZUL)[:3])
        rgb_img.paste(self.img, mask=self.img.split()[3])
        for q in (90, 82, 74, 66, 58):
            rgb_img.save(destino, "JPEG", quality=q, optimize=True, progressive=True)
            if Path(destino).stat().st_size <= LIMITE_BYTES:
                return
        raise RuntimeError(f"{destino}: não coube em 8 MB nem com qualidade 58")


# ---------------------------------------------------------------- dados (só o que está conferido, com prazo firme)

def _dados():
    return ig._dados()


def abertos(editais, facs, hoje, *campos):
    """Editais abertos usáveis em post: os de ig.abertos que também passam em ck.edital_confirmado (status "ok", conferido à mão, sem
    campo em "conferir"), têm a página do prazo e de cada campo que o post usa e fecham daqui a 2 dias ou mais (item P2 do padrão: nenhum
    prazo citado vence antes de 48 h após a publicação; o edital que fecha antes disso fica de fora, não derruba o post). Os demais ficam só no site."""
    minimo = (date.fromisoformat(hoje) + timedelta(days=2)).isoformat()
    return [e for e in ig.abertos(editais, facs, hoje)
            if e["inscricao_fim"] >= minimo and not ck.edital_confirmado(e, ("inscricao_fim",) + campos)
            and all(ck.pagina_unica(ck.com_pagina(e, c)) for c in ("inscricao_fim",) + campos)]


def _modalidade(e):
    return {"portador_diploma": "Portador de diploma", "externa": "Transferência externa", "interna": "Transferência interna",
            "exterior": "Para quem estuda no exterior"}.get(e.get("modalidade"), "Edital")


def _pag_curta(e, campo):
    """'p. 2' para página numérica; 'Anexo 1, p. 1' já vem completo do dado."""
    pag = ck.com_pagina(e, campo)
    return f"p. {pag}" if re.fullmatch(r"\d+", pag) else ck.rotulo_pagina(pag) if re.fullmatch(r"[\d,\se]+", pag) else pag


def _pares(facs, grupo, *campos, rotulos=()):
    """[(sigla, 'p. 2')]; com mais de um campo e páginas diferentes, cada fato com a sua: 'regra p. 2, prazo p. 1' (uma página por fato)."""
    out = []
    for e in grupo:
        pags = [_pag_curta(e, c) for c in campos]
        txt = pags[0] if len(set(pags)) == 1 else ", ".join(f"{r} {p}" for r, p in zip(rotulos, pags))
        out.append((facs[e["faculdade_id"]]["sigla"], txt))
    return list(dict.fromkeys(out))


def _fonte_edital(e, f, extra="", campo="inscricao_fim"):
    return f"- {f['sigla']} ({f['cidade']}/{f['uf']}): `{e['id']}`{extra}, página {ck.com_pagina(e, campo)} ({e['url_edital']})"


def _reais(v):
    return f"R$ {v:.0f}" if float(v).is_integer() else "R$ " + f"{v:.2f}".replace(".", ",")


# ---------------------------------------------------------------- telas do modelo (capa, cartões, chamada; ver instagram_cartoes.py)

BOTAO_ALERTA = "Ative o alerta grátis · link na bio"
CTA_LEGENDA = "O alerta grátis do Transfermed avisa antes de cada prazo: link na bio."


def _capa(kicker, titulo, apoio, fonte="", cor="agua"):
    t = {"tipo": "capa", "cor": cor, "kicker": kicker, "titulo": titulo, "apoio": apoio, "botao": "Arraste e veja →"}
    if fonte:
        t["fonte"] = fonte
    return t


def _fonte_capa(pares, prefixo="Fontes: edital de cada faculdade"):
    return f"{prefixo} ({'; '.join(f'{s} {p}' for s, p in pares)})"


def _chamada(titulo, apoio):
    return {"tipo": "chamada", "titulo": titulo, "apoio": apoio, "botao": BOTAO_ALERTA, "rodape": "Confira sempre o edital oficial."}


def _cartao_edital(e, f, prazo=None, extra="", fonte=None):
    """Cartão de uma faculdade: nome, cidade, modalidade, prazo e a página do edital (um dado, uma página)."""
    return {"nome": f["nome"], "detalhe": f"{f['cidade']} ({f['uf']}) · {_modalidade(e)}{extra}",
            "prazo": prazo or f"Inscrições até {g.fmt(e['inscricao_fim'])}", "fonte": fonte or f"edital, {_pag_curta(e, 'inscricao_fim')}"}


def _telas_de_cartoes(cartoes, kicker_primeira, kicker_demais, cor="agua", maximo_telas=8):
    """Reparte os cartões em telas de 2 ou 3 (2 quando há nome ou detalhe longo, para o texto caber), equilibradas. Devolve (telas, quantos coube)."""
    longo = any(len(c["nome"]) > 34 or len(c["detalhe"]) > 62 for c in cartoes)
    por_tela = 2 if longo else 3
    cartoes = cartoes[:maximo_telas * por_tela]
    n_telas = -(-len(cartoes) // por_tela)
    base, resto = divmod(len(cartoes), n_telas)
    telas, i = [], 0
    for k in range(n_telas):
        tam = base + (1 if k < resto else 0)
        telas.append({"tipo": "cartoes", "cor": cor, "kicker": kicker_primeira if k == 0 else kicker_demais, "cartoes": cartoes[i:i + tam]})
        i += tam
    return telas, len(cartoes)


def _resultado(tipo, telas, legenda, fontes, usados=(), facs=None, gancho=""):
    """telas: lista no formato de instagram_cartoes.py (é o que vira imagem e o que a checagem lê). usados: [(edital, campo)], os editais que
    aparecem no post e o campo mostrado; vira `fatos` (faculdade + página) e entra no post.json."""
    import instagram_cartoes as cart
    lonas = cart.desenhar(telas)
    fatos = [{"faculdade": facs[e["faculdade_id"]]["sigla"], "edital": e["id"], "campo": campo, "pagina": ck.com_pagina(e, campo)} for e, campo in usados]
    alts = [". ".join(x.rstrip(".") for x in cart.textos_da_tela(t)) + "." for t in telas]   # ". " entre os textos: "p. 19" + nome da faculdade não vira "19 faculdades"
    return {"tipo": tipo, "slides": lonas, "telas": telas, "legenda": legenda, "fontes": fontes, "alt": alts,
            "usados": list(dict.fromkeys(e["id"] for e, _ in usados)), "fatos": fatos, "textos": [sl.texto() for sl in lonas], "gancho": gancho}


def _tag(sigla):
    import unicodedata
    return "#" + re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", sigla).encode("ascii", "ignore").decode().lower())


def _legenda(corpo, siglas=(), lista=()):
    """Modelo dos posts revisados: 1ª linha = o fato; lista com datas; um único chamado (alerta grátis, link na bio); 'Confira sempre o edital
    oficial'; até 7 hashtags (as 4 do tema + as siglas das faculdades citadas)."""
    tags = HASHTAGS.split() + [t for t in dict.fromkeys(_tag(s) for s in siglas) if len(t) > 2 and t not in HASHTAGS.split()]
    bloco = ("\n".join(f"• {x}" for x in lista) + "\n\n") if lista else ""
    return f"{corpo}\n\n{bloco}{CTA_LEGENDA}\n\nConfira sempre o edital oficial.\n\n{' '.join(tags[:7])}\n"


def _linhas_prazo(grupo, facs):
    """Uma linha por edital, com a modalidade (a mesma faculdade abre transferência externa e portador de diploma: sem ela as linhas parecem repetidas)."""
    curta = {"externa": "externa", "portador_diploma": "diploma", "interna": "interna", "exterior": "exterior"}
    return [f"{facs[e['faculdade_id']]['sigla']} ({facs[e['faculdade_id']]['cidade']}/{facs[e['faculdade_id']]['uf']}), {curta.get(e.get('modalidade'), 'edital')}: até {g.fmt(e['inscricao_fim'])}" for e in grupo]


# ---------------------------------------------------------------- os formatos

def post_abertos(editais, facs, hoje):
    """Segunda: carrossel com a capa (quantos editais estão abertos), cartões de 2 ou 3 faculdades por tela em ordem de prazo e a chamada. Até 10 telas."""
    lista = abertos(editais, facs, hoje)
    if not lista:
        return None
    cartoes = [_cartao_edital(e, facs[e["faculdade_id"]]) for e in lista]
    miolo, n = _telas_de_cartoes(cartoes, "Fecha primeiro", "Depois, em ordem de prazo", maximo_telas=8)
    mostrados = lista[:n]   # o gancho e a capa contam só os que o carrossel mostra; o resto fica no site (legenda)
    por_uf = Counter(facs[e["faculdade_id"]]["uf"] for e in mostrados)
    top = " · ".join(f"{uf}: {k}" for uf, k in sorted(por_uf.items(), key=lambda kv: (g.ordem_uf(kv[0]), kv[0])))
    gancho = f"Estes {n} editais de Medicina têm inscrição aberta"
    telas = [_capa("Radar da semana", gancho, f"Dados conferidos no edital oficial, em ordem de prazo. Por estado: {top}.")] + miolo + \
            [_chamada("Em qual deles você pode se inscrever?", "O alerta grátis avisa antes de cada prazo, e o diagnóstico mostra quais combinam com o seu período.")]
    extra = f" Mais {len(lista) - n} no site." if n < len(lista) else ""
    corpo = (f"{gancho}, com dados conferidos no edital, em ordem de prazo (arraste).{extra} Há outros editais abertos no site, ainda em conferência. "
             "O prazo é o que está no edital: confira o documento oficial antes de se inscrever.")
    return _resultado("editais-abertos-da-semana", telas, _legenda(corpo, [facs[e["faculdade_id"]]["sigla"] for e in mostrados], _linhas_prazo(mostrados, facs)),
                      [_fonte_edital(e, facs[e["faculdade_id"]], f", prazo {e['inscricao_fim']}") for e in mostrados], [(e, "inscricao_fim") for e in mostrados], facs, gancho)


def _taxa_e_prazo(editais, facs, hoje):
    """Editais abertos usáveis com taxa (maior que zero) e prazo na MESMA página única do PDF. Nada de resumo de regra entre aspas: os
    dados do projeto guardam resumos, não o texto literal do edital, então o post só afirma o que o dado sustenta (valor e data)."""
    return [e for e in abertos(editais, facs, hoje, "taxa_inscricao")
            if (e.get("taxa_inscricao") or 0) > 0 and ck.com_pagina(e, "taxa_inscricao") == ck.com_pagina(e, "inscricao_fim")]


def post_armadilha(editais, facs, hoje):
    """Terça: o dado concreto de um edital 'ok' (taxa e prazo, com a página única). O edital do dia muda a cada semana; se o escolhido
    não passar na checagem, tenta o próximo."""
    achados = _taxa_e_prazo(editais, facs, hoje)
    semana = date.fromisoformat(hoje).isocalendar()[1]
    for k in range(len(achados)):
        r = _armadilha_de(achados[(semana + k) % len(achados)], facs)
        if not ck.checar(r, editais, facs, hoje):
            return r
    return None


def _armadilha_de(e, facs):
    f = facs[e["faculdade_id"]]
    pag = ck.com_pagina(e, "inscricao_fim")
    taxa, fim = _reais(e["taxa_inscricao"]), g.fmt(e["inscricao_fim"])[:5]
    gancho = f"{f['sigla']}: taxa de {taxa}, inscrição até {fim}"
    tela = {"tipo": "armadilha", "kicker": "Dado do edital", "titulo": gancho,
            "cartao": {"linha": f"{f['sigla']} · {f['cidade']} ({f['uf']}) · {_modalidade(e)}", "destaque": f"Taxa de inscrição: {taxa}",
                       "destaque2": f"Último dia: {fim}", "apoio": "Confira o edital completo antes de pagar.", "fonte": f"edital, {_pag_curta(e, 'inscricao_fim')}"},
            "botao": BOTAO_ALERTA, "rodape": "Confira sempre o edital oficial."}
    corpo = (f"Na {f['sigla']} ({f['cidade']}/{f['uf']}), a inscrição na transferência de Medicina custa {taxa} e vai até {fim} (edital, página {pag}). "
             "Veja no PDF oficial se há outra regra de pagamento ou de documento que mude o seu caso: leia o edital completo antes de se inscrever.")
    return _resultado("armadilha-do-edital", [tela], _legenda(corpo, [f["sigla"]]),
                      [f"- {f['sigla']} ({f['cidade']}/{f['uf']}): `{e['id']}`, taxa {taxa} e prazo {e['inscricao_fim']}, página {pag} ({e['url_edital']})"],
                      [(e, "taxa_inscricao"), (e, "inscricao_fim")], facs, gancho)


def post_prazos(editais, facs, hoje):
    h = date.fromisoformat(hoje)
    limite = (h + timedelta(days=14)).isoformat()
    lista = [e for e in abertos(editais, facs, hoje) if e["inscricao_fim"] <= limite]
    if not lista:
        return None
    cartoes = [_cartao_edital(e, facs[e["faculdade_id"]]) for e in lista]
    miolo, n = _telas_de_cartoes(cartoes, "Fecha primeiro", "E logo depois", cor="ambar", maximo_telas=3)
    lista = lista[:n]
    gancho = f"Estes {n} editais fecham a inscrição até {g.fmt(lista[-1]['inscricao_fim'])[:5]}"
    telas = [_capa("Os prazos mais próximos", gancho, "Transferência em Medicina, com o prazo conferido no edital oficial.",
                   _fonte_capa(_pares(facs, lista, "inscricao_fim")), cor="ambar")] + miolo + \
            [_chamada("Seu documento está pronto antes do prazo?", "Cada edital pede documentos e prazos diferentes. O alerta grátis avisa antes de cada prazo, e o diagnóstico mostra quais combinam com o seu período.")]
    corpo = (f"{gancho}, de editais conferidos, em ordem de data. Há outros editais no site, ainda em conferência. "
             "O prazo pode ser prorrogado ou retificado: confira no edital oficial.")
    return _resultado("prazos-14-dias", telas, _legenda(corpo, [facs[e["faculdade_id"]]["sigla"] for e in lista], _linhas_prazo(lista, facs)),
                      [_fonte_edital(e, facs[e["faculdade_id"]], f", prazo {e['inscricao_fim']}") for e in lista], [(e, "inscricao_fim") for e in lista], facs, gancho)


def post_taxas(editais, facs, hoje):
    ab = [e for e in abertos(editais, facs, hoje, "taxa_inscricao") if e.get("taxa_inscricao") is not None]
    if len(ab) < 5:
        return None
    t = sorted(e["taxa_inscricao"] for e in ab)
    menor, maior = min(ab, key=lambda e: (e["taxa_inscricao"], e["id"])), max(ab, key=lambda e: (e["taxa_inscricao"], e["id"]))
    gancho = f"Taxas de {_reais(t[0])} a {_reais(t[-1])} nestes {len(ab)} editais" if t[0] else f"Taxas de até {_reais(t[-1])} nestes {len(ab)} editais"
    cartoes = [{"nome": "Menor taxa", "detalhe": f"entre estes {len(ab)} editais abertos com taxa conferida" if t[0] else "há edital aberto sem taxa de inscrição",
                "prazo": _reais(t[0]) if t[0] else "sem taxa", "fonte": f"edital, {_pag_curta(menor, 'taxa_inscricao')}"},
               {"nome": "Taxa mediana", "detalhe": "a metade cobra menos que isto", "prazo": _reais(statistics.median(t)), "fonte": "mediana dos editais abertos"},
               {"nome": "Maior taxa", "detalhe": "cada taxa é por inscrição", "prazo": _reais(t[-1]), "fonte": f"edital, {_pag_curta(maior, 'taxa_inscricao')}"}]
    telas = [_capa("Taxa de inscrição", gancho, "Menor, mediana e maior taxa entre os editais abertos com taxa conferida.",
                   _fonte_capa(_pares(facs, [menor, maior], "taxa_inscricao"), "Fonte: edital da menor e da maior taxa")),
             {"tipo": "cartoes", "cor": "agua", "kicker": "Taxa por inscrição", "cartoes": cartoes},
             _chamada("Compare as taxas antes de se inscrever", "Cada edital cobra um valor e pede documentos diferentes. O alerta grátis avisa quando um edital abrir.")]
    corpo = (f"{gancho}. A taxa de inscrição varia muito de uma faculdade para outra, e em alguns editais é cobrada por campus. "
             "Veja a taxa de cada edital antes de decidir onde se inscrever.")
    return _resultado("taxas", telas, _legenda(corpo, [facs[menor["faculdade_id"]]["sigla"], facs[maior["faculdade_id"]]["sigla"]]),
                      [f"- {len(ab)} editais abertos com taxa conferida (data/editais.json): menor R$ {t[0]:.2f}, mediana R$ {statistics.median(t):.2f}, maior R$ {t[-1]:.2f}"]
                      + [_fonte_edital(e, facs[e["faculdade_id"]], f", taxa R$ {e['taxa_inscricao']:.2f}", "taxa_inscricao") for e in ab],
                      [(e, "taxa_inscricao") for e in ab], facs, gancho)


def post_exterior(editais, facs, hoje):
    todos = abertos(editais, facs, hoje, "aceita_curso_exterior")
    lista = [e for e in todos if e.get("aceita_curso_exterior") is True]
    if not lista:
        return None
    nao = sum(1 for e in todos if e.get("aceita_curso_exterior") is False)
    cartoes = []
    for e in lista:
        regra, prazo = _pag_curta(e, "aceita_curso_exterior"), _pag_curta(e, "inscricao_fim")
        cartoes.append(_cartao_edital(e, facs[e["faculdade_id"]], extra=" · aceita curso do exterior",
                                      fonte=f"edital, {regra}" if regra == prazo else f"edital, regra {regra}, prazo {prazo}"))
    miolo, n = _telas_de_cartoes(cartoes, "Aceitam, em ordem de prazo", "E também aceitam", maximo_telas=8)
    lista = lista[:n]
    gancho = f"Estes {len(lista)} editais abertos aceitam quem estudou fora"
    telas = [_capa("Estuda Medicina fora do Brasil?", gancho, f"Entre os editais conferidos, {nao} dizem expressamente que não aceitam." if nao else "Dados conferidos no edital oficial, em ordem de prazo.")] + miolo + \
            [_chamada("Seu curso no exterior é aceito?", "Cada edital tem a sua regra. O alerta grátis avisa quando abrir, e o diagnóstico mostra quais combinam com o seu caso.")]
    corpo = (f"{gancho}, em ordem de prazo. Nem todo edital aceita quem cursou parte da faculdade no exterior: "
             f"entre os conferidos, {nao} dizem expressamente que não aceitam. Confira a regra no edital da faculdade onde vai se inscrever.")
    return _resultado("estudo-no-exterior", telas, _legenda(corpo, [facs[e["faculdade_id"]]["sigla"] for e in lista], _linhas_prazo(lista, facs)),
                      [_fonte_edital(e, facs[e["faculdade_id"]], ", aceita curso do exterior", "aceita_curso_exterior") for e in lista],
                      [(e, "aceita_curso_exterior") for e in lista], facs, gancho)


def post_documentos(editais, facs, hoje):
    ab = [e for e in abertos(editais, facs, hoje, "documentos") if e.get("documentos")]
    if len(ab) < 8:
        return None
    chaves = [("Histórico escolar", r"hist[oó]rico"), ("Declaração de vínculo com a faculdade", r"v[ií]nculo"),
              ("Programas das disciplinas (ementas)", r"programa|ementa|plano de ensino"), ("Documento de identidade e CPF", r"\bRG\b|identidade|\bCPF\b"),
              ("Declaração do Enade", r"enade")]
    cont = [(nome, sum(1 for e in ab if any(re.search(rx, doc, re.I) for doc in e["documentos"]))) for nome, rx in chaves]
    cont = sorted([c for c in cont if c[1]], key=lambda kv: -kv[1])[:4]
    if not cont:
        return None
    gancho = f"{cont[0][0]}: pedido em {cont[0][1]} de {len(ab)} abertos"
    cartoes = [{"nome": nome, "detalhe": f"citado na lista de {n} destes {len(ab)} editais abertos", "prazo": f"{n} de {len(ab)}",
                "fonte": "listas de documentos de cada edital"} for nome, n in cont]
    miolo, _ = _telas_de_cartoes(cartoes, "Mais pedidos", "Também pedidos", maximo_telas=2)
    telas = [_capa("Documentos mais pedidos", gancho, "Contagem sobre as listas de documentos transcritas dos editais abertos e conferidos.")] + miolo + \
            [_chamada("Seus documentos estão em dia?", "A lista exata é a do edital de cada faculdade. O alerta grátis avisa antes de cada prazo.")]
    corpo = (f"{gancho}. Entre estes {len(ab)} editais abertos e conferidos, estes são os documentos mais citados nas listas. "
             "A lista exata é a do edital da faculdade onde você vai se inscrever.")
    return _resultado("documentos", telas, _legenda(corpo),
                      [f"- contagem sobre {len(ab)} editais abertos com lista de documentos transcrita (campo `documentos`, página em `evidencias`)"]
                      + [_fonte_edital(e, facs[e["faculdade_id"]], "", "documentos") for e in ab],
                      [(e, "documentos") for e in ab], facs, gancho)


def post_estados(editais, facs, hoje):
    ab = abertos(editais, facs, hoje)
    c = Counter(facs[e["faculdade_id"]]["uf"] for e in ab)
    if not c:
        return None
    ordem = sorted(c.items(), key=lambda kv: (g.ordem_uf(kv[0]), kv[0]))
    fac_uf = {uf: len({e["faculdade_id"] for e in ab if facs[e["faculdade_id"]]["uf"] == uf}) for uf in c}
    gancho = f"Estes {len(ab)} editais abertos estão em {len(c)} {'estado' if len(c) == 1 else 'estados'}"
    cartoes = [{"nome": g.NOMES_UF.get(uf, uf), "detalhe": f"faculdades com edital aberto e conferido: {fac_uf[uf]}",
                "prazo": f"Conferidos: {k}", "fonte": "contagem dos editais abertos conferidos"} for uf, k in ordem]
    miolo, n = _telas_de_cartoes(cartoes, "Onde estão", "E também em", maximo_telas=4)
    ordem = ordem[:n]
    telas = [_capa("Onde estão os editais", gancho, "Transferência em Medicina com dados conferidos no PDF oficial, por estado.")] + miolo + \
            [_chamada("Tem edital aberto no seu estado?", "O diagnóstico grátis mostra quais combinam com o seu período, e o alerta avisa quando abrir outro.")]
    corpo = f"{gancho}, com dados conferidos no PDF oficial. Há outros no site, ainda em conferência."
    return _resultado("editais-por-estado", telas, _legenda(corpo),
                      [f"- {k} editais abertos em {uf} (contagem de data/editais.json em {g.fmt(hoje)}):" for uf, k in ordem]
                      + [_fonte_edital(e, facs[e["faculdade_id"]]) for e in ab], [(e, "inscricao_fim") for e in ab], facs, gancho)


CALENDARIO = {0: post_abertos, 1: post_armadilha, 2: post_prazos, 3: post_taxas, 4: post_exterior, 5: post_documentos, 6: post_estados}
RESERVA = [post_estados, post_prazos]  # quando o formato do dia não tem dado seguro


def escolher(editais, facs, hoje, padrao=True):
    """(resultado, nota). O formato do dia; se não houver dado seguro, ou se a checagem (instagram_checagem.py) reprovar, o primeiro da reserva
    que passar. Nada é inventado e nada reprovado é gravado."""
    dia = date.fromisoformat(hoje).weekday()
    principal = CALENDARIO[dia]
    motivos = []
    for formato in [principal] + [x for x in RESERVA if x is not principal]:
        r = formato(editais, facs, hoje)
        if not r:
            motivos.append(f"{formato.__name__}: sem dado seguro")
            continue
        problemas = ck.checar(r, editais, facs, hoje, padrao=padrao)
        if problemas:
            motivos.append(f"{formato.__name__} reprovado na checagem: " + " | ".join(problemas))
            continue
        return r, ("" if formato is principal else f"o formato de {DIAS[dia]} ({principal.__name__}) não passou ({motivos[0]}); usou a reserva {formato.__name__}")
    return None, f"nenhum formato passou para {DIAS[dia]}: " + " || ".join(motivos)


# ---------------------------------------------------------------- saída

def gravar(resultado, nota, hoje, destino=None, privado=None, agora=None):
    destino = Path(destino or SOCIAL / hoje)
    destino.mkdir(parents=True, exist_ok=True)
    for velho in list(destino.glob("*.jpg")) + [destino / "SEM_POST.txt"]:
        velho.unlink(missing_ok=True)
    urls, nomes = [], []
    for i, lona in enumerate(resultado["slides"], 1):
        nome = f"{i:02d}.jpg"
        lona.salvar(destino / nome)
        nomes.append(nome)
        urls.append(f"{SITE}/social/{hoje}/{nome}")
    dia = DIAS[date.fromisoformat(hoje).weekday()]
    manifesto = {"data": hoje, "dia_da_semana": dia, "tipo": resultado["tipo"], "imagens": urls, "texto_alternativo": resultado["alt"],
                 "carrossel": len(urls) > 1, "usados": resultado["usados"], "fatos": resultado["fatos"], "textos": resultado["textos"], "telas": resultado["telas"], "gancho": resultado.get("gancho", ""), "nota": nota, "gerado_em": (agora or datetime.now(BRASILIA)).isoformat(timespec="seconds")}
    (destino / "post.json").write_text(json.dumps(manifesto, ensure_ascii=False, indent=1), encoding="utf-8")
    legenda = resultado["legenda"] + "\nImagens (https): " + " ".join(urls) + "\n"
    fontes = (f"# Fontes do post de {dia}, {g.fmt(hoje)} ({resultado['tipo']})\n"
              "Confira cada dado no edital oficial antes de publicar. Se algum estiver diferente, não poste e avise.\n\n"
              + "\n".join(resultado["fontes"]) + "\n")
    for pasta in [destino] + ([Path(privado)] if privado else []):
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "legenda.txt").write_text(legenda, encoding="utf-8")
        (pasta / "fontes.txt").write_text(fontes, encoding="utf-8")
    return manifesto


def podar(manter_dias, hoje, base=None):
    """Apaga as pastas de datas antigas (o repositório não pode crescer sem limite). Devolve os nomes apagados."""
    import shutil
    base = Path(base or SOCIAL)
    corte = (date.fromisoformat(hoje) - timedelta(days=manter_dias)).isoformat()
    apagadas = []
    for p in sorted(base.glob("????-??-??")):
        if p.is_dir() and p.name < corte:
            shutil.rmtree(p)
            apagadas.append(p.name)
    return apagadas


def sincronizar(hoje, base=None, privado=None):
    """Copia legenda e fontes das datas de hoje em diante do docs/social para o privado/instagram (no computador do dono)."""
    base, privado = Path(base or SOCIAL), Path(privado or PRIVADO)
    copiadas = []
    for p in sorted(base.glob("????-??-??")):
        if p.name >= hoje:
            for nome in ("legenda.txt", "fontes.txt"):
                if (p / nome).exists():
                    (privado / p.name).mkdir(parents=True, exist_ok=True)
                    (privado / p.name / nome).write_text((p / nome).read_text(encoding="utf-8"), encoding="utf-8")
            copiadas.append(p.name)
    return copiadas


def revisado_pelo_dono(pasta):
    """Post que o dono revisou à mão (post.json com "revisado": true) ou pauta curada do banco (instagram_pilares.py, "curado": true): o robô nunca o regera nem o sobrescreve."""
    try:
        post = json.loads((Path(pasta) / "post.json").read_text(encoding="utf-8"))
        return post.get("revisado") is True or post.get("curado") is True   # "curado": pauta do banco montada por instagram_pilares.py
    except (OSError, ValueError):
        return False


def aplicar_revisado(hoje, privado=None, social=None):
    """Se existir privado/instagram/AAAA-MM-DD-revisado/, ele tem prioridade sobre o post do robô: copia as imagens e a legenda
    para docs/social/AAAA-MM-DD e grava post.json com "revisado": true (a tabela do FONTES.md vira os fatos). Devolve True se aplicou."""
    origem = (privado or PRIVADO) / f"{hoje}-revisado"
    destino = (social or SOCIAL) / hoje
    imagens = sorted(origem.glob("[0-9][0-9].jpg")) if origem.is_dir() else []
    if not imagens:
        return False
    anterior = {}
    try:   # as telas e o gancho que o post já tinha (itens 3, 6 e 8 do padrão) sobrevivem a uma nova cópia da pasta revisada
        anterior = json.loads((destino / "post.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    if destino.exists():
        for velho in destino.iterdir():
            if velho.is_file():
                velho.unlink()
    destino.mkdir(parents=True, exist_ok=True)
    for im in imagens:
        (destino / im.name).write_bytes(im.read_bytes())
    legenda = origem / "legenda.txt"
    if legenda.exists():
        (destino / "legenda.txt").write_text(legenda.read_text(encoding="utf-8"), encoding="utf-8")
    fontes = origem / "FONTES.md"
    fatos, usados = [], []
    texto_fontes = fontes.read_text(encoding="utf-8") if fontes.exists() else ""
    if texto_fontes:
        (destino / "fontes.txt").write_text(texto_fontes, encoding="utf-8")
    for linha in texto_fontes.splitlines():
        c = [x.strip() for x in linha.strip().strip("|").split("|")]
        m = re.fullmatch(r"[0-9a-f]{12}", c[1]) if len(c) >= 4 else None
        pg = re.search(r"p\. (\d+)", c[3]) if m else None
        if m and pg:
            fatos.append({"faculdade": c[0], "edital": c[1], "campo": "inscricao_fim", "pagina": pg.group(1)})
            usados.append(c[1])
    dt = date.fromisoformat(hoje)
    dias = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
    gancho = ""
    for linha in (destino / "legenda.txt").read_text(encoding="utf-8").splitlines() if legenda.exists() else []:
        if linha.strip():
            gancho = linha.strip().rstrip(":")
            break
    post = {"data": hoje, "dia_da_semana": dias[dt.weekday()], "tipo": "revisado-pelo-dono",
            "imagens": [f"{SITE}/social/{hoje}/{im.name}" for im in imagens],
            "texto_alternativo": [], "carrossel": len(imagens) > 1, "usados": usados, "fatos": fatos, "textos": [],
            "gancho": gancho, "nota": f"Post revisado pelo dono em privado/instagram/{hoje}-revisado; tem prioridade sobre o robô.",
            "gerado_em": datetime.now(timezone(timedelta(hours=-3))).isoformat(timespec="seconds"), "revisado": True}
    for chave in ("telas", "gancho"):
        if anterior.get(chave):
            post[chave] = anterior[chave]
    (destino / "post.json").write_text(json.dumps(post, ensure_ascii=False, indent=1) + chr(10), encoding="utf-8")
    return True


def amanha_em_brasilia():
    return ((datetime.now(timezone.utc) - timedelta(hours=3)).date() + timedelta(days=1)).isoformat()


def gerar_dia(hoje, dados=None):
    """Gera (ou preserva) o post de `hoje` em docs/social/AAAA-MM-DD. Devolve (situacao, mensagem): situacao = revisado | mantido | sem-post | gerado."""
    pasta = SOCIAL / hoje
    if aplicar_revisado(hoje):
        return "revisado", f"Post de {hoje}: usada a pasta privado/instagram/{hoje}-revisado (tem prioridade sobre o robô)"
    if revisado_pelo_dono(pasta):
        return "mantido", f"Post de {hoje} revisado pelo dono (post.json com revisado=true): mantido, nada foi regerado"
    editais, facs = dados or _dados()
    resultado, nota = escolher(editais, facs, hoje)
    if not resultado:
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "SEM_POST.txt").write_text(f"Sem post para {hoje}: {nota}. Nada foi inventado.\n", encoding="utf-8")
        return "sem-post", f"Sem post: {nota}"
    privado = PRIVADO / hoje if PRIVADO.parent.exists() else None
    m = gravar(resultado, nota, hoje, privado=privado)
    return "gerado", f"Post de {m['dia_da_semana']} ({m['tipo']}): {len(m['imagens'])} imagem(ns) em docs/social/{hoje}" + (f" · {nota}" if nota else "")


# ---------------------------------------------------------------- pacote semanal (domingo à noite)

def proxima_segunda(hoje):
    """Segunda-feira seguinte a `hoje` (AAAA-MM-DD); se `hoje` já é segunda, a própria."""
    d = date.fromisoformat(hoje)
    return (d + timedelta(days=(7 - d.weekday()) % 7)).isoformat()


def semana_de(segunda):
    d = date.fromisoformat(segunda)
    return [(d + timedelta(days=i)).isoformat() for i in range(7)]


def previa_da_semana(segunda, base=None, destino=None):
    """Imagem única (previa.jpg) com a 1ª tela de cada um dos 7 dias, em ordem, com o dia, o formato e o número de telas. Lê de docs/social."""
    from PIL import Image, ImageDraw
    base = Path(base or SOCIAL)
    larg, alt, topo, margem = 300, 375, 64, 24
    cols = 4
    folha = Image.new("RGB", (margem + cols * (larg + margem), margem + 2 * (alt + topo + margem)), rgb(AZUL)[:3])
    d = ImageDraw.Draw(folha)
    for i, dia_ in enumerate(semana_de(segunda)):
        x, y = margem + (i % cols) * (larg + margem), margem + (i // cols) * (alt + topo + margem)
        pasta = base / dia_
        imagens = sorted(pasta.glob("[0-9][0-9].jpg"))
        try:
            tipo = json.loads((pasta / "post.json").read_text(encoding="utf-8")).get("tipo", "")
        except (OSError, ValueError):
            tipo = ""
        d.text((x, y), f"{DIAS[i]} {g.fmt(dia_)[:5]}", font=g._fonte(26, "Bold"), fill=rgb(BRANCO))
        rotulo = (tipo or "sem post") + (f" · {len(imagens)} telas" if len(imagens) > 1 else "")
        tam = 20
        while tam > 12 and d.textlength(rotulo, font=g._fonte(tam)) > larg:   # o rótulo não pode invadir a coluna ao lado
            tam -= 1
        d.text((x, y + 32), rotulo, font=g._fonte(tam), fill=rgb(VERDE_AGUA))
        if imagens:
            with Image.open(imagens[0]) as im:
                folha.paste(im.convert("RGB").resize((larg, alt)), (x, y + topo))
        else:
            d.rectangle((x, y + topo, x + larg, y + topo + alt), outline=rgb(CINZA)[:3], width=2)
    destino = Path(destino) if destino else PRIVADO / f"semana-{segunda}" / "previa.jpg"
    destino.parent.mkdir(parents=True, exist_ok=True)
    folha.save(destino, "JPEG", quality=88)
    return destino


def pacote_da_semana(segunda, base=None, saida=None):
    """Monta, em saida/semana-AAAA-MM-DD/ (padrão privado/instagram), a previa.jpg e, por dia, o FONTES.md (fontes e página de cada fato) e a legenda.
    Lê o que já está em docs/social. Devolve a pasta."""
    base = Path(base or SOCIAL)
    pasta = Path(saida or PRIVADO) / f"semana-{segunda}"
    for dia_ in semana_de(segunda):
        origem = base / dia_
        if not origem.is_dir():
            continue
        (pasta / dia_).mkdir(parents=True, exist_ok=True)
        fontes = origem / "fontes.txt"
        (pasta / dia_ / "FONTES.md").write_text(fontes.read_text(encoding="utf-8") if fontes.exists() else f"# Fontes do post de {dia_}\n\nSem fontes registradas (post sem dado ou sem fontes.txt).\n", encoding="utf-8")
        if (origem / "legenda.txt").exists():
            (pasta / dia_ / "legenda.txt").write_text((origem / "legenda.txt").read_text(encoding="utf-8"), encoding="utf-8")
        for im in sorted(origem.glob("[0-9][0-9].jpg")):   # as telas de cada dia, para revisar sem abrir o docs/social
            (pasta / dia_ / im.name).write_bytes(im.read_bytes())
    previa_da_semana(segunda, base, pasta / "previa.jpg")
    return pasta


def gerar_semana(segunda, dados=None, manter=14, saida=None):
    """Gera os 7 posts da semana que começa em `segunda` (os revisados pelo dono ficam como estão) e monta o pacote. Devolve (mensagens, pasta)."""
    dados = dados or _dados()
    msgs = []
    for dia_ in semana_de(segunda):
        _, msg = gerar_dia(dia_, dados)
        msgs.append(f"{dia_}: {msg}")
    podar(manter, segunda)
    return msgs, pacote_da_semana(segunda, saida=saida)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", default=None, help="dia da publicação, AAAA-MM-DD (padrão: amanhã, em Brasília)")
    ap.add_argument("--manter", type=int, default=14, help="quantos dias de pastas antigas ficam em docs/social")
    ap.add_argument("--sincronizar", action="store_true", help="copia legendas e fontes de docs/social para privado/instagram, monta o pacote da próxima semana e sai")
    ap.add_argument("--semana", nargs="?", const="", default=None, metavar="SEGUNDA",
                    help="gera os 7 posts da semana que começa na segunda AAAA-MM-DD (vazio = a próxima segunda, em Brasília) e o pacote com a prévia")
    ap.add_argument("--saida", default=None, help="pasta do pacote semanal (padrão privado/instagram); no GitHub Actions é publicada como artefato")
    args = ap.parse_args(argv)
    hoje = args.data or amanha_em_brasilia()
    if args.semana is not None:
        segunda = args.semana or proxima_segunda(datetime.now(BRASILIA).date().isoformat())
        msgs, pasta = gerar_semana(segunda, manter=args.manter, saida=args.saida)
        print("\n".join(msgs))
        print(f"Pacote da semana de {segunda}: {pasta}")
        return 0
    if args.sincronizar:
        print("Sincronizado em privado/instagram:", ", ".join(sincronizar(hoje)) or "nada")
        segunda = proxima_segunda(datetime.now(BRASILIA).date().isoformat())
        print("Pacote da semana:", pacote_da_semana(segunda, saida=args.saida))
        return 0
    situacao, msg = gerar_dia(hoje)
    apagadas = podar(args.manter, hoje) if situacao == "gerado" else []
    print(msg + (f" · pastas antigas apagadas: {len(apagadas)}" if apagadas else ""))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
