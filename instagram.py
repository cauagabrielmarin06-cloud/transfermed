"""Pacote semanal do Instagram (ROADMAP 9g, bastidores): gera, da base, 3 posts de 1080x1350 em privado/instagram/AAAA-MM-DD/.

Regras: nenhum dado inventado (tudo vem de data/editais.json e data/resultados.json, só editais conferidos); nenhum nome
de pessoa; nenhum ranking entre faculdades (listas em ordem de prazo, sem destaque); nada é publicado: o dono revisa e
publica. Cada post vem com legenda, chamada para o diagnóstico com `?origem=instagram` e uma lista das fontes
(edital e página) para o dono conferir antes de postar.

  segunda: editais abertos (por prazo)      quarta: "leia antes de pagar a taxa" (uma restrição real, com página)
  sexta: quem aceita estudo no exterior (ou Raio-X da concorrência, quando houver número com a grandeza certa)
uso: python instagram.py [--hoje AAAA-MM-DD]
"""
import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

import gerar_site as g

PASTA = Path(__file__).resolve().parent
SAIDA = PASTA / "privado" / "instagram"
LINK = "transfermed.com.br/diagnostico/?origem=instagram"
LARGURA, ALTURA = 1080, 1350
VERDE, VERDE_CLARO, AMBAR, BRANCO = "#0F5C4D", "#CFE8DF", "#E8A33D", "#FFFFFF"


def _dados():
    editais = json.loads((PASTA / "data" / "editais.json").read_text(encoding="utf-8"))
    facs = {f["id"]: f for f in json.loads((PASTA / "data" / "faculdades.json").read_text(encoding="utf-8"))}
    return editais, facs


def abertos(editais, facs, hoje):
    """Editais conferidos, abertos hoje, com prazo final firme (sem 'conferir' no prazo), por ordem de prazo."""
    saida = []
    for e in editais:
        if not g.publicavel(e) or g.situacao(e, hoje) != "aberto" or not e.get("inscricao_fim"):
            continue
        if "inscricao_fim" in (e.get("conferir_campos") or {}) or e["faculdade_id"] not in facs:
            continue
        saida.append(e)
    return sorted(saida, key=lambda e: (e["inscricao_fim"], e["faculdade_id"]))


def _base(titulo, sobretitulo, rodape="Confira sempre o edital oficial."):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (LARGURA, ALTURA), VERDE)
    d = ImageDraw.Draw(img, "RGBA")
    for i, raio in enumerate((760, 600, 440, 280)):
        d.ellipse((LARGURA - raio, -raio // 3, LARGURA + raio, raio * 5 // 3 - raio // 3 * 2), outline=(227, 242, 236, 22 + i * 8), width=3)
    g._logo(d, 100, 100, 40)
    d.text((160, 72), "Transfermed", font=g._fonte(36, "Bold"), fill=BRANCO)
    d.text((160, 116), "Seu radar de transferência de Medicina", font=g._fonte(24), fill=VERDE_CLARO)
    d.text((72, 200), sobretitulo.upper(), font=g._fonte(26, "SemiBold"), fill=AMBAR)
    y = 245
    fonte = g._fonte(64, "Bold")
    for linha in g._quebrar(d, titulo, fonte, LARGURA - 144)[:3]:
        d.text((72, y), linha, font=fonte, fill=BRANCO)
        y += 76
    d.text((72, ALTURA - 120), rodape, font=g._fonte(26), fill=VERDE_CLARO)
    d.text((72, ALTURA - 76), LINK, font=g._fonte(30, "SemiBold"), fill=BRANCO)
    return img, d, y + 24


def _cartao(d, x, y, w, h, linhas, destaque=None):
    d.rounded_rectangle((x, y, x + w, y + h), radius=24, fill=(255, 255, 255, 235))
    ty = y + 18
    for texto, tam, peso, cor in linhas:
        d.text((x + 28, ty), texto, font=g._fonte(tam, peso), fill=cor)
        ty += tam + 8
    if destaque:
        fonte = g._fonte(30, "Bold")
        larg = d.textlength(destaque, font=fonte) + 40
        d.rounded_rectangle((x + w - larg - 20, y + 20, x + w - 20, y + 72), radius=26, fill=AMBAR)
        d.text((x + w - larg, y + 28), destaque, font=fonte, fill="#2B1A00")


def post_abertos(editais, facs, hoje, destino):
    lista = abertos(editais, facs, hoje)[:6]
    img, d, y = _base("Editais abertos agora", f"Semana de {g.fmt(hoje)[:5]}")
    for e in lista:
        f = facs[e["faculdade_id"]]
        total = g.total_vagas(e) if not {"vagas", "edital"} & set(g.campos_conferir(e)) else None
        mod = {"portador_diploma": "Portador de diploma", "externa": "Transferência externa"}.get(e.get("modalidade"), "Edital")
        sub = f"{f['cidade']}/{f['uf']} · {mod}"
        _cartao(d, 72, y, LARGURA - 144, 118, [(f["sigla"], 36, "Bold", "#0A4338"), (sub + (f" · {total} vagas" if total else ""), 24, "Regular", "#565B57")],
                f"até {g.fmt(e['inscricao_fim'])[:5]}")
        y += 134
    d.text((72, y + 6), f"São {len(abertos(editais, facs, hoje))} editais abertos no radar. Lista completa no site.", font=g._fonte(26), fill=VERDE_CLARO)
    img.save(destino, "PNG", optimize=True)
    fontes = [f"- {facs[e['faculdade_id']]['sigla']}: `{e['id']}` ({e['url_edital']})" for e in lista]
    legenda = ("Estes editais de transferência de Medicina estão com inscrição aberta agora, em ordem de prazo.\n\n"
               "O prazo é o que está no edital: confira sempre o documento oficial antes de se inscrever.\n"
               f"Descubra em 1 minuto em quais você pode se inscrever: {LINK} (link na bio)\n")
    return legenda, fontes


def _restricao(editais, facs, hoje):
    """Uma restrição real de edital aberto, com a página do PDF registrada em `evidencias`."""
    for e in abertos(editais, facs, hoje):
        pag = (e.get("evidencias") or {}).get("outras_restricoes")
        for r in e.get("outras_restricoes") or []:
            if pag and 25 <= len(r) <= 150 and "R$" not in r and "bolsa" not in r.lower():
                return e, r, pag
    return None


def post_armadilha(editais, facs, hoje, destino):
    achado = _restricao(editais, facs, hoje)
    if not achado:
        return None, []
    e, texto, pag = achado
    f = facs[e["faculdade_id"]]
    img, d, y = _base("Leia antes de pagar a taxa", "Armadilha do edital")
    fonte = g._fonte(44, "SemiBold")
    linhas = g._quebrar(d, re.sub(r"\s*\([^)]*\)", "", texto).strip().rstrip(";."), fonte, LARGURA - 200)[:7]
    altura = 140 + 58 * len(linhas) + 50
    _cartao(d, 72, y + 10, LARGURA - 144, altura, [(f"{f['sigla']} · {f['cidade']}/{f['uf']}", 34, "Bold", "#0A4338")])
    ty = y + 90
    for linha in linhas:
        d.text((100, ty), linha, font=fonte, fill="#1F2421")
        ty += 58
    d.text((100, ty + 14), f"Está no edital (p. {str(pag).split()[0]}).", font=g._fonte(28), fill="#565B57")
    img.save(destino, "PNG", optimize=True)
    legenda = ("Detalhes pequenos no edital mudam tudo. Este está escrito no edital oficial, na página indicada na imagem.\n\n"
               f"Veja os requisitos de cada edital aberto: {LINK} (link na bio)\n")
    return legenda, [f"- {f['sigla']}: `{e['id']}`, página {pag}, restrição: \"{texto}\" ({e['url_edital']})"]


def post_exterior(editais, facs, hoje, destino):
    lista = [e for e in abertos(editais, facs, hoje) if e.get("aceita_curso_exterior") is True][:6]
    total_ab = len(abertos(editais, facs, hoje))
    img, d, y = _base("Estuda Medicina fora do Brasil?", "Editais que aceitam")
    for e in lista:
        f = facs[e["faculdade_id"]]
        _cartao(d, 72, y, LARGURA - 144, 104, [(f["sigla"], 34, "Bold", "#0A4338"), (f"{f['cidade']}/{f['uf']}", 24, "Regular", "#565B57")],
                f"até {g.fmt(e['inscricao_fim'])[:5]}")
        y += 120
    sem = sum(1 for e in abertos(editais, facs, hoje) if e.get("aceita_curso_exterior") is False)
    d.text((72, y + 6), f"Dos {total_ab} abertos, {sem} dizem no edital que NÃO aceitam quem estudou fora.", font=g._fonte(26), fill=VERDE_CLARO)
    img.save(destino, "PNG", optimize=True)
    legenda = ("Nem todo edital aceita quem cursou parte da faculdade no exterior. Estes dizem que aceitam, em ordem de prazo. Confira sempre no edital oficial.\n\n"
               f"Veja a lista completa e o que cada edital exige: {LINK} (link na bio)\n")
    return legenda, [f"- {facs[e['faculdade_id']]['sigla']}: `{e['id']}` ({e['url_edital']})" for e in lista]


def gerar(hoje):
    editais, facs = _dados()
    pasta = SAIDA / hoje
    pasta.mkdir(parents=True, exist_ok=True)
    import instagram_mais
    partes = [("segunda-editais-abertos", post_abertos), ("quarta-armadilha-do-edital", post_armadilha),
              ("sexta-estudo-no-exterior", post_exterior), *instagram_mais.EXTRAS]
    leia = [f"# Pacote do Instagram (rascunho): semana de {g.fmt(hoje)}\n",
            "Gerado da base (`instagram.py`). **Nada foi publicado.** Revise as imagens e as fontes antes de postar; "
            "se algum dado estiver diferente do edital, não poste e avise.\n"]
    feitos = []
    for nome, funcao in partes:
        png = pasta / f"{nome}.png"
        legenda, fontes = funcao(editais, facs, hoje, png)
        if legenda is None:
            leia.append(f"## {nome}\nSem conteúdo seguro esta semana (faltam dados suficientes na base para este formato: nada é inventado).\n")
            continue
        (pasta / f"{nome}.legenda.txt").write_text(legenda, encoding="utf-8")
        leia += [f"## {nome}", f"Imagem: `{png.name}` · Legenda: `{nome}.legenda.txt`", "Fontes:", *fontes, ""]
        feitos.append(png)
    (pasta / "LEIA-ME.md").write_text("\n".join(leia), encoding="utf-8")
    return pasta, feitos


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--hoje", default=date.today().isoformat())
    a = ap.parse_args()
    pasta, feitos = gerar(a.hoje)
    print(f"{len(feitos)} posts em {pasta}")
