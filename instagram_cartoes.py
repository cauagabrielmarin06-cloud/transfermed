"""Renderiza as telas de um post do Instagram a partir da lista `telas` do post.json (10/11/2026).

Serve aos posts revisados (privado/instagram/AAAA-MM-DD-revisado) e a qualquer post que declare `telas`: o texto da imagem e o texto que a
checagem examina (instagram_checagem.py) são o mesmo, e o desenho respeita o item 6 do privado/PADRAO_DE_QUALIDADE.md
(texto principal ≥ 36 px, apoio e rodapé de fonte ≥ 26 px em 1080 px, nenhuma área vazia maior que 1/3 da tela).

Tipos de tela:
  capa      kicker, titulo, apoio, fonte (rodapé de fonte, se a capa traz dado), botao
  cartoes   kicker, cor ("ambar" | "agua"), cartoes: [{nome, detalhe, prazo, fonte}]   (os cartões esticam para ocupar a altura)
  armadilha kicker, titulo, cartao: {linha, destaque, destaque2, apoio, fonte}, botao, rodape
  chamada   titulo, apoio, botao, rodape

uso: python instagram_cartoes.py docs/social/AAAA-MM-DD        (relê post.json e regrava 01.jpg, 02.jpg...)
"""
import json
import sys
from pathlib import Path

import gerar_site as g
import instagram_dia as dia

LARGURA, ALTURA = dia.LARGURA, dia.ALTURA
MARGEM = 72
AMBAR = "#F4B942"
CARTAO = "#12293E"
FUNDO_FIM = 1190  # o último cartão termina aqui; abaixo fica a margem
RODAPE_Y = 1250


def _aneis(lona):
    """Fundo só com os anéis do radar (sem pontos nem varredura: um ponto sobre o texto atrapalha a leitura)."""
    from PIL import ImageDraw
    cam = lona.Image.new("RGBA", (LARGURA, ALTURA), (0, 0, 0, 0))
    d = ImageDraw.Draw(cam)
    for cx, cy, raios, alfa in ((LARGURA - 40, 120, (160, 300, 440, 580, 720, 860), 46), (80, ALTURA - 60, (200, 360, 520, 680), 26)):
        for i, r in enumerate(raios):
            d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=dia.rgb(dia.VERDE_AGUA, max(10, alfa - i * 5)), width=3)
    lona.img = lona.Image.alpha_composite(lona.img, cam)


def _nova():
    from PIL import ImageDraw
    lona = dia.Lona.__new__(dia.Lona)
    from PIL import Image
    lona.Image = Image
    lona.img = Image.new("RGBA", (LARGURA, ALTURA), dia.rgb(dia.AZUL))
    _aneis(lona)
    lona.textos = []
    lona.d = dia._Registro(ImageDraw.Draw(lona.img, "RGBA"), lona.textos)
    return lona


def _cabecalho(lona, n, total):
    d = lona.d
    logo = lona.Image.open(dia.LOGO).convert("RGBA").resize((94, 94), lona.Image.LANCZOS)
    d._d.ellipse((70, 63, 168, 161), outline=dia.rgb(dia.BRANCO), width=3)
    lona.img.alpha_composite(logo, (72, 65))
    d._d.text((187, 82), "Transfermed", font=g._fonte(40, "Bold"), fill=dia.rgb(dia.BRANCO))
    d._d.text((187, 125), "Seu radar de transferência de Medicina", font=g._fonte(26), fill=dia.rgb(dia.CINZA))
    if total > 1:
        f = g._fonte(28, "SemiBold")
        txt = f"{n}/{total}"
        d._d.text((LARGURA - MARGEM - d.textlength(txt, font=f), 85), txt, font=f, fill=dia.rgb(dia.CINZA))


def _linhas(lona, x, y, texto, fonte, cor, largura, passo):
    """Desenha o texto quebrado em linhas e devolve o y seguinte."""
    for linha in g._quebrar(lona.d, texto, fonte, largura):
        lona.d.text((x, y), linha, font=fonte, fill=dia.rgb(cor))
        y += passo
    return y


def _botao(lona, texto, y, cheio=False):
    d, f = lona.d, g._fonte(38, "Bold")
    larg = LARGURA - 2 * MARGEM if cheio else int(d.textlength(texto, font=f)) + 146
    d.rounded_rectangle((MARGEM, y, MARGEM + larg, y + 80 if not cheio else y + 100), radius=50, fill=dia.rgb(dia.VERDE_AGUA))
    alt = 80 if not cheio else 100
    d.text((MARGEM + (larg - d.textlength(texto, font=f)) // 2, y + (alt - 38) // 2 - 4), texto, font=f, fill=dia.rgb(dia.AZUL))


def _capa(lona, t):
    d = lona.d
    cor = AMBAR if t.get("cor") == "ambar" else dia.VERDE_AGUA
    d.text((MARGEM, 300), t["kicker"].upper(), font=g._fonte(30, "Bold"), fill=dia.rgb(cor))
    y = _linhas(lona, MARGEM, 360, t["titulo"], g._fonte(88, "Bold"), dia.BRANCO, LARGURA - 2 * MARGEM, 104)
    y = _linhas(lona, MARGEM, y + 14, t["apoio"], g._fonte(38), dia.CINZA, LARGURA - 2 * MARGEM, 50)
    if t.get("fonte"):
        _linhas(lona, MARGEM, 1010, t["fonte"], g._fonte(28), dia.CINZA, LARGURA - 2 * MARGEM, 38)
    _botao(lona, t["botao"], 1150)


def _cartoes(lona, t):
    d = lona.d
    cor = AMBAR if t.get("cor") == "ambar" else dia.VERDE_AGUA
    d.text((MARGEM, 250), t["kicker"].upper(), font=g._fonte(30, "Bold"), fill=dia.rgb(cor))
    cs = t["cartoes"]
    topo, folga = 310, 30
    alto = (FUNDO_FIM - topo - folga * (len(cs) - 1)) // len(cs)
    esc = 1.3 if alto > 600 else 1.0
    for i, c in enumerate(cs):
        y0 = topo + i * (alto + folga)
        y1 = y0 + alto
        d.rounded_rectangle((MARGEM, y0, LARGURA - MARGEM, y1), radius=28, fill=dia.rgb(CARTAO))
        d.rounded_rectangle((MARGEM, y0, MARGEM + 13, y1), radius=6, fill=dia.rgb(dia.VERDE_AGUA))
        x, larg = MARGEM + 46, LARGURA - 2 * MARGEM - 92
        y = _linhas(lona, x, y0 + 32, c["nome"], g._fonte(int(42 * esc), "Bold"), dia.BRANCO, larg, int(50 * esc))
        y = _linhas(lona, x, y + 6, c["detalhe"], g._fonte(int(30 * esc)), dia.CINZA, larg, int(40 * esc))
        fp, ff = g._fonte(int(46 * esc), "Bold"), g._fonte(28)
        base = y1 - 30
        if d.textlength(c["prazo"], font=fp) + 36 + d.textlength(c["fonte"], font=ff) <= larg:   # prazo e fonte na mesma linha
            d.text((x, base - int(56 * esc)), c["prazo"], font=fp, fill=dia.rgb(dia.VERDE_AGUA))
            d.text((x + larg - d.textlength(c["fonte"], font=ff), base - 32), c["fonte"], font=ff, fill=dia.rgb(dia.CINZA))
        else:                                                                                      # empilhados
            d.text((x, base - 30), c["fonte"], font=ff, fill=dia.rgb(dia.CINZA))
            d.text((x, base - 30 - 12 - int(56 * esc)), c["prazo"], font=fp, fill=dia.rgb(dia.VERDE_AGUA))


def _armadilha(lona, t):
    d = lona.d
    d.text((MARGEM, 250), t["kicker"].upper(), font=g._fonte(30, "Bold"), fill=dia.rgb(AMBAR))
    y = _linhas(lona, MARGEM, 305, t["titulo"], g._fonte(76, "Bold"), dia.BRANCO, LARGURA - 2 * MARGEM, 92)
    c = t["cartao"]
    y0, y1 = y + 36, 1075
    d.rounded_rectangle((MARGEM, y0, LARGURA - MARGEM, y1), radius=28, fill=dia.rgb(CARTAO))
    d.rounded_rectangle((MARGEM, y0, MARGEM + 13, y1), radius=6, fill=dia.rgb(dia.VERDE_AGUA))
    x, larg = MARGEM + 46, LARGURA - 2 * MARGEM - 92
    yy = y0 + 34
    yy = _linhas(lona, x, yy, c["linha"], g._fonte(30, "SemiBold"), dia.CINZA, larg, 40) + 14
    yy = _linhas(lona, x, yy, c["destaque"], g._fonte(42, "Bold"), dia.BRANCO, larg, 54)
    yy = _linhas(lona, x, yy + 6, c["destaque2"], g._fonte(42, "Bold"), dia.VERDE_AGUA, larg, 54)
    _linhas(lona, x, yy + 18, c["apoio"], g._fonte(34), dia.CINZA, larg, 46)
    d.text((x, y1 - 34 - 30), c["fonte"], font=g._fonte(28), fill=dia.rgb(dia.CINZA))
    _botao(lona, t["botao"], 1100 if y1 + 20 <= 1100 else y1 + 20, cheio=True)
    _rodape(lona, t["rodape"], 1235)


def _rodape(lona, rodape, y):
    d = lona.d
    f, fb = g._fonte(28), g._fonte(30, "Bold")
    d.text((MARGEM, y), rodape, font=f, fill=dia.rgb(dia.CINZA))
    link = "transfermed.com.br"
    d.text((LARGURA - MARGEM - d.textlength(link, font=fb), y - 1), link, font=fb, fill=dia.rgb(dia.BRANCO))


def _chamada(lona, t):
    y = _linhas(lona, MARGEM, 340, t["titulo"], g._fonte(80, "Bold"), dia.BRANCO, LARGURA - 2 * MARGEM, 96)
    _linhas(lona, MARGEM, y + 24, t["apoio"], g._fonte(40), dia.CINZA, LARGURA - 2 * MARGEM, 52)
    _botao(lona, t["botao"], 1010, cheio=True)
    d = lona.d
    d.text((MARGEM, 1170), t["rodape"], font=g._fonte(30), fill=dia.rgb(dia.CINZA))
    d.text((MARGEM, 1216), "transfermed.com.br", font=g._fonte(32, "Bold"), fill=dia.rgb(dia.BRANCO))


TIPOS = {"capa": _capa, "cartoes": _cartoes, "armadilha": _armadilha, "chamada": _chamada}


def textos_da_tela(t):
    """Todo o texto de uma tela, na ordem em que é lido (o que a checagem examina). Tela do robô já traz a lista pronta em `textos`."""
    if "textos" in t:
        return [x for x in t["textos"] if x]
    partes = [t.get(k) for k in ("kicker", "titulo", "apoio", "fonte", "botao", "rodape")]
    for c in t.get("cartoes") or []:
        partes += [c.get(k) for k in ("nome", "detalhe", "prazo", "fonte")]
    c = t.get("cartao") or {}
    partes += [c.get(k) for k in ("linha", "destaque", "destaque2", "apoio", "fonte")]
    return [p for p in partes if p]


def desenhar(telas):
    """Uma Lona (imagem + textos desenhados) por tela."""
    lonas = []
    for n, t in enumerate(telas, 1):
        lona = _nova()
        _cabecalho(lona, n, len(telas))
        TIPOS[t["tipo"]](lona, t)
        lonas.append(lona)
    return lonas


def renderizar(telas, pasta):
    pasta = Path(pasta)
    for n, lona in enumerate(desenhar(telas), 1):
        lona.salvar(pasta / f"{n:02d}.jpg")


if __name__ == "__main__":
    pasta = Path(sys.argv[1])
    post = json.loads((pasta / "post.json").read_text(encoding="utf-8"))
    renderizar(post["telas"], pasta)
    print(f"{len(post['telas'])} imagens em {pasta}")
