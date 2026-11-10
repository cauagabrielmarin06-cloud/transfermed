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
HASHTAGS = "#transferenciamedicina #medicina #estudantedemedicina"


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
    """Um slide: fundo com anéis de radar, cabeçalho com o logo, título, corpo que preenche a altura e rodapé com o link."""

    TOPO_TITULO = 215
    RODAPE = 190

    def __init__(self, kicker, titulo, tam_titulo=62):
        from PIL import Image, ImageDraw
        self.Image = Image
        self.img = Image.new("RGBA", (LARGURA, ALTURA), rgb(AZUL))
        self._radar()
        self.textos = []
        self.d = _Registro(ImageDraw.Draw(self.img, "RGBA"), self.textos)
        self._cabecalho()
        self.d.text((64, self.TOPO_TITULO), kicker.upper(), font=g._fonte(26, "SemiBold"), fill=rgb(VERDE_AGUA))
        y = self.TOPO_TITULO + 48
        fonte = g._fonte(tam_titulo, "Bold")
        for linha in g._quebrar(self.d, titulo, fonte, LARGURA - 128)[:3]:
            self.d.text((64, y), linha, font=fonte, fill=rgb(BRANCO))
            y += tam_titulo + 12
        self.topo = y + 22
        self.base = ALTURA - self.RODAPE
        self._rodape()

    def texto(self):
        return " ".join(self.textos)

    def _radar(self):
        from PIL import ImageDraw
        cam = self.Image.new("RGBA", (LARGURA, ALTURA), (0, 0, 0, 0))
        d = ImageDraw.Draw(cam)
        for cx, cy, raios, alfa in ((LARGURA - 40, 120, (160, 300, 440, 580, 720, 860), 46), (80, ALTURA - 60, (200, 360, 520, 680), 26)):
            for i, r in enumerate(raios):
                d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=rgb(VERDE_AGUA, max(10, alfa - i * 5)), width=3)
        # varredura e pontos do radar
        d.line((LARGURA - 40, 120, LARGURA - 40 - 520, 120 + 360), fill=rgb(VERDE_AGUA, 40), width=3)
        for x, y, r in ((780, 250, 9), (900, 430, 7), (640, 120, 6), (960, 300, 6), (210, 1180, 8), (400, 1290, 6)):
            d.ellipse((x - r, y - r, x + r, y + r), fill=rgb(VERDE_AGUA, 170))
        self.img = self.Image.alpha_composite(self.img, cam)

    def _cabecalho(self):
        d = self.d
        if LOGO.exists():
            logo = self.Image.open(LOGO).convert("RGBA").resize((124, 124), self.Image.LANCZOS)
            d.ellipse((60, 52, 188, 180), outline=rgb(VERDE_AGUA, 150), width=3)
            self.img.alpha_composite(logo, (62, 54))
        d.text((214, 74), "Transfermed", font=g._fonte(44, "Bold"), fill=rgb(BRANCO))
        d.text((214, 130), "Radar de transferência de Medicina", font=g._fonte(26), fill=rgb(VERDE_AGUA))

    def _rodape(self):
        d = self.d
        y0 = ALTURA - self.RODAPE + 20
        d.line((64, y0, LARGURA - 64, y0), fill=rgb(VERDE_AGUA, 90), width=2)
        d.text((64, y0 + 24), "Descubra em 1 minuto onde você pode se inscrever", font=g._fonte(30), fill=rgb(BRANCO))
        d.text((64, y0 + 70), LINK, font=g._fonte(34, "Bold"), fill=rgb(VERDE_AGUA))
        d.text((64, y0 + 124), "Confira sempre o edital oficial. Os prazos podem mudar.", font=g._fonte(28), fill=rgb(CINZA))

    def capacidade(self, minimo=118, painel_min=190, gap=18):
        return max(1, (self.base - self.topo - painel_min) // (minimo + gap))

    def cartoes(self, itens, painel_fn, minimo=118, painel_min=190):
        """itens: [(titulo, subtitulo, selo)]. Os cartões ocupam a altura toda; a sobra vai para o painel de número, de modo que não
        fica área vazia. painel_fn(n) -> (numero, rotulo) recebe quantos cartões couberam. Devolve esse n."""
        gap, maximo = 18, 250
        area = self.base - self.topo
        n = min(len(itens), self.capacidade(minimo, painel_min, gap))
        h = min(maximo, (area - painel_min - gap * n) // n)
        y = self.topo
        for titulo, sub, selo in itens[:n]:
            self._cartao(y, h, titulo, sub, selo)
            y += h + gap
        self._painel(y, self.base - y, *painel_fn(n))
        return n

    def _cartao(self, y, h, titulo, sub, selo):
        d, x, w = self.d, 64, LARGURA - 128
        d.rounded_rectangle((x, y, x + w, y + h), radius=26, fill=rgb(AZUL_2), outline=rgb(VERDE_AGUA, 70), width=2)
        d.rounded_rectangle((x, y + 18, x + 10, y + h - 18), radius=5, fill=rgb(VERDE_AGUA))
        tam_t, tam_s = max(34, min(56, int(h * 0.34))), max(24, min(32, int(h * 0.19)))
        larg_selo = 0
        if selo:
            fs = g._fonte(max(26, min(34, int(h * 0.2))), "Bold")
            larg_selo = int(d.textlength(selo, font=fs)) + 44
            hs = int(fs.size * 1.9)
            d.rounded_rectangle((x + w - larg_selo - 24, y + (h - hs) // 2, x + w - 24, y + (h + hs) // 2), radius=hs // 2, fill=rgb(VERDE_AGUA))
            d.text((x + w - larg_selo - 24 + 22, y + (h - fs.size) // 2 - 3), selo, font=fs, fill=rgb(AZUL))
        largura_texto = w - 56 - larg_selo - (36 if selo else 0)
        ft = g._fonte(tam_t, "Bold")
        while d.textlength(titulo, font=ft) > largura_texto and ft.size > 26:
            ft = g._fonte(ft.size - 2, "Bold")
        fs2 = g._fonte(tam_s)
        sub_linhas = g._quebrar(d, sub, fs2, largura_texto)[:2] if sub else []
        alto_texto = ft.size + (len(sub_linhas) * (tam_s + 6) + 8 if sub_linhas else 0)
        ty = y + (h - alto_texto) // 2 - 4
        d.text((x + 36, ty), titulo, font=ft, fill=rgb(BRANCO))
        ty += ft.size + 12
        for linha in sub_linhas:
            d.text((x + 36, ty), linha, font=fs2, fill=rgb(CINZA))
            ty += tam_s + 6

    def _painel(self, y, h, numero, rotulo, estes="Estes"):
        d, x, w = self.d, 64, LARGURA - 128
        d.rounded_rectangle((x, y, x + w, y + h), radius=26, fill=rgb(VERDE_AGUA))
        if estes:  # o número é só dos editais conferidos, nunca o total: a palavra vem antes do número
            d.text((x + 36, y + 12), estes.upper(), font=g._fonte(24, "Bold"), fill=rgb(AZUL))
        fn = g._fonte(min(150, max(80, int(h * 0.62))), "Bold")
        while d.textlength(str(numero), font=fn) > w * 0.46 and fn.size > 50:
            fn = g._fonte(fn.size - 4, "Bold")
        larg_n = int(d.textlength(str(numero), font=fn))
        d.text((x + 36, y + (h - fn.size) // 2 - 10 + (14 if estes else 0)), str(numero), font=fn, fill=rgb(AZUL))
        fr = g._fonte(30, "SemiBold")
        zona = w - 36 - larg_n - 36 - 36
        linhas = g._quebrar(d, rotulo, fr, zona)[:4]
        ty = y + (h - len(linhas) * 40) // 2
        for linha in linhas:
            d.text((x + 36 + larg_n + 36, ty), linha, font=fr, fill=rgb(AZUL))
            ty += 40

    def texto_grande(self, linhas, fonte_tam, entrada="", saida="", rodape_painel=None):
        """Um cartão único que ocupa o corpo todo: chamada no alto, texto no meio e faixa com a fonte embaixo (armadilha do edital)."""
        d, x, w = self.d, 64, LARGURA - 128
        y0, y1 = self.topo, self.base
        d.rounded_rectangle((x, y0, x + w, y1), radius=26, fill=rgb(AZUL_2), outline=rgb(VERDE_AGUA, 70), width=2)
        d.rounded_rectangle((x, y0 + 22, x + 10, y1 - 22), radius=5, fill=rgb(VERDE_AGUA))
        f = g._fonte(fonte_tam, "SemiBold")
        passo = int(fonte_tam * 1.28)
        faixa = 130 if rodape_painel else 0
        topo_txt, base_txt = y0 + 40, y1 - faixa - 20
        if entrada:
            d.text((x + 48, topo_txt), entrada.upper(), font=g._fonte(30, "SemiBold"), fill=rgb(VERDE_AGUA))
            topo_txt += 56
        if saida:
            fs = g._fonte(28)
            d.text((x + 48, base_txt - 36), saida, font=fs, fill=rgb(CINZA))
            base_txt -= 56
        ty = topo_txt + (base_txt - topo_txt - len(linhas) * passo) // 2
        for linha in linhas:
            d.text((x + 48, ty), linha, font=f, fill=rgb(BRANCO))
            ty += passo
        if rodape_painel:
            d.rounded_rectangle((x + 24, y1 - faixa, x + w - 24, y1 - 24), radius=22, fill=rgb(VERDE_AGUA))
            fr = g._fonte(34, "Bold")
            d.text((x + 56, y1 - faixa + (faixa - 24 - fr.size) // 2 - 2), rodape_painel, font=fr, fill=rgb(AZUL))

    def painel_total(self, numero, rotulo, extras=(), estes="Estes"):
        """Capa do carrossel: o número grande ocupa o corpo, com uma lista curta embaixo."""
        d, x, w = self.d, 64, LARGURA - 128
        y0, y1 = self.topo, self.base
        d.rounded_rectangle((x, y0, x + w, y1), radius=26, fill=rgb(VERDE_AGUA))
        fn = g._fonte(380, "Bold")
        fr, fe = g._fonte(40, "Bold"), g._fonte(30, "SemiBold")
        caixa = d.textbbox((0, 0), str(numero), font=fn)  # (x0, y0, x1, y1) do desenho real do número
        linhas_r = g._quebrar(d, rotulo, fr, w - 80)[:2]
        alto_estes = 56 if estes else 0
        total = alto_estes + (caixa[3] - caixa[1]) + 36 + 52 * len(linhas_r) + 14 + 42 * len(extras)
        ty = y0 + (y1 - y0 - total) // 2  # o conjunto fica no centro do painel: sem faixa vazia em cima ou embaixo
        if estes:
            d.text(((LARGURA - d.textlength(estes.upper(), font=fr)) // 2, ty), estes.upper(), font=fr, fill=rgb(AZUL))
            ty += alto_estes
        d.text(((LARGURA - (caixa[2] - caixa[0])) // 2 - caixa[0], ty - caixa[1]), str(numero), font=fn, fill=rgb(AZUL))
        ty += (caixa[3] - caixa[1]) + 36
        for linha in linhas_r:
            d.text(((LARGURA - d.textlength(linha, font=fr)) // 2, ty), linha, font=fr, fill=rgb(AZUL))
            ty += 52
        ty += 14
        for linha in extras:
            d.text(((LARGURA - d.textlength(linha, font=fe)) // 2, ty), linha, font=fe, fill=rgb(AZUL))
            ty += 42

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
    campo em "conferir") e têm a página do prazo e de cada campo que o post usa. Os demais ficam só no site."""
    return [e for e in ig.abertos(editais, facs, hoje)
            if not ck.edital_confirmado(e, ("inscricao_fim",) + campos) and all(ck.pagina_unica(ck.com_pagina(e, c)) for c in ("inscricao_fim",) + campos)]


def _onde(pag):
    return f"página {pag}" if re.fullmatch(r"\d+", pag) else f"uma destas páginas: {pag}"


def _vagas(e):
    if {"vagas", "edital"} & set(g.campos_conferir(e)):
        return None
    return g.total_vagas(e) or None


def _vagas_txt(v):
    return f"{v} vaga" if v == 1 else f"{v} vagas"


def _modalidade(e):
    return {"portador_diploma": "Portador de diploma", "externa": "Transferência externa", "interna": "Transferência interna",
            "exterior": "Para quem estuda no exterior"}.get(e.get("modalidade"), "Edital")


def _sub(e, f):
    v = _vagas(e)
    return f"{f['cidade']}/{f['uf']} · {_modalidade(e)}" + (f" · {_vagas_txt(v)}" if v else "")


def _selo(e):
    return f"até {g.fmt(e['inscricao_fim'])[:5]}"


def _fonte_edital(e, f, extra="", campo="inscricao_fim"):
    return f"- {f['sigla']} ({f['cidade']}/{f['uf']}): `{e['id']}`{extra}, página {ck.com_pagina(e, campo)} ({e['url_edital']})"


def _resultado(tipo, slides, legenda, fontes, alts, usados=(), facs=None, gancho=""):
    """usados: [(edital, campo)], os editais que aparecem no post e o campo mostrado; vira `fatos` (faculdade + página) e entra no post.json."""
    fatos = [{"faculdade": facs[e["faculdade_id"]]["sigla"], "edital": e["id"], "campo": campo, "pagina": ck.com_pagina(e, campo)} for e, campo in usados]
    return {"tipo": tipo, "slides": slides, "legenda": legenda, "fontes": fontes, "alt": alts, "usados": list(dict.fromkeys(e["id"] for e, _ in usados)),
            "fatos": fatos, "textos": [sl.texto() for sl in slides], "gancho": gancho}


def _legenda(corpo, cta):
    return f"{corpo}\n\n{cta}: {LINK} (link na bio)\nConfira sempre o edital oficial.\n\n{HASHTAGS}\n"


# ---------------------------------------------------------------- os formatos

def post_abertos(editais, facs, hoje):
    """Segunda: carrossel com a capa (quantos editais estão abertos) e 4 editais por slide, em ordem de prazo. Até 10 slides."""
    lista = abertos(editais, facs, hoje)
    if not lista:
        return None
    h = date.fromisoformat(hoje)
    por_uf = Counter(facs[e["faculdade_id"]]["uf"] for e in lista)
    top = [f"{uf}: {n}" for uf, n in sorted(por_uf.items(), key=lambda kv: (g.ordem_uf(kv[0]), kv[0]))][:6]
    gancho = f"Estes {len(lista)} editais de Medicina têm inscrição aberta"
    capa = Lona("Semana de " + g.fmt(hoje)[:5], gancho)
    capa.painel_total(len(lista), "editais de Medicina com inscrição aberta e dados conferidos no edital, em ordem de prazo", ["Por estado: " + " · ".join(top), "Arraste para ver →"])
    slides, alts, fontes = [capa], [f"Estes {len(lista)} editais de transferência de Medicina abertos e conferidos na semana de {g.fmt(hoje)[:5]}"], []
    usados = []
    i = 0
    while i < len(lista) and len(slides) < 10:
        sl = Lona(f"Editais abertos · {len(slides)}", "Inscrição aberta")
        resto = lista[i:]
        itens = [(facs[e["faculdade_id"]]["sigla"], _sub(e, facs[e["faculdade_id"]]), _selo(e)) for e in resto]
        n = sl.cartoes(itens, lambda k, i=i: (len(lista), "editais abertos e conferidos" + (f" · faltam {len(lista) - i - k} nos próximos slides" if len(lista) - i - k > 0 else " · este é o último")),
                       minimo=128, painel_min=150)
        grupo = resto[:n]
        slides.append(sl)
        alts.append("; ".join(f"{facs[e['faculdade_id']]['sigla']} até {g.fmt(e['inscricao_fim'])[:5]}" for e in grupo))
        fontes += [_fonte_edital(e, facs[e["faculdade_id"]], f", prazo {e['inscricao_fim']}") for e in grupo]
        usados += [(e, "inscricao_fim") for e in grupo]
        i += n
    extra = f" Mais {len(lista) - i} no site." if i < len(lista) else ""
    corpo = (f"Estes {len(lista)} editais de transferência de Medicina têm inscrição aberta e dados conferidos no edital, em ordem de prazo (arraste).{extra} "
             "Há outros editais abertos no site, ainda em conferência. O prazo é o que está no edital: confira o documento oficial antes de se inscrever.")
    return _resultado("editais-abertos-da-semana", slides, _legenda(corpo, "Veja em quais você pode se inscrever"), fontes, alts, usados, facs, gancho)


def _taxa_e_prazo(editais, facs, hoje):
    """Editais abertos usáveis com taxa (maior que zero) e prazo na MESMA página única do PDF. Nada de resumo de regra entre aspas: os
    dados do projeto guardam resumos, não o texto literal do edital, então o post só afirma o que o dado sustenta (valor e data)."""
    return [e for e in abertos(editais, facs, hoje, "taxa_inscricao")
            if (e.get("taxa_inscricao") or 0) > 0 and ck.com_pagina(e, "taxa_inscricao") == ck.com_pagina(e, "inscricao_fim")]


def _reais(v):
    return f"R$ {v:.0f}" if float(v).is_integer() else "R$ " + f"{v:.2f}".replace(".", ",")


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
    s = Lona("Dado do edital", gancho, 66)
    s.texto_grande([f"Taxa de inscrição: {taxa}", f"Último dia: {fim}"], 76, entrada="Conferido no edital", saida="Confira o edital completo antes de pagar.",
                   rodape_painel=f"{f['sigla']} · edital, {ck.rotulo_pagina(pag)}")
    corpo = (f"Na {f['sigla']} ({f['cidade']}/{f['uf']}), a inscrição na transferência de Medicina custa {taxa} e vai até {fim} (edital, página {pag}). "
             "Veja no PDF oficial se há outra regra de pagamento ou de documento que mude o seu caso: leia o edital completo antes de se inscrever.")
    return _resultado("armadilha-do-edital", [s], _legenda(corpo, "Veja os requisitos de cada edital aberto"),
                      [f"- {f['sigla']} ({f['cidade']}/{f['uf']}): `{e['id']}`, taxa {taxa} e prazo {e['inscricao_fim']}, página {pag} ({e['url_edital']})"],
                      [f"{f['sigla']}: taxa de inscrição de {taxa}, inscrição até {fim}"], [(e, "taxa_inscricao"), (e, "inscricao_fim")], facs, gancho)


def post_prazos(editais, facs, hoje):
    h = date.fromisoformat(hoje)
    limite = (h + timedelta(days=14)).isoformat()
    lista = [e for e in abertos(editais, facs, hoje) if e["inscricao_fim"] <= limite]
    if not lista:
        return None
    gancho = f"Estes {len(lista)} editais fecham em até 14 dias"
    s = Lona("Prazos dos próximos 14 dias", gancho)

    def quando(e):
        dias = (date.fromisoformat(e["inscricao_fim"]) - h).days
        return "encerra hoje" if dias == 0 else "encerra amanhã" if dias == 1 else f"encerra em {dias} dias"

    def sub_prazo(e, f):
        v = _vagas(e)
        return f"{quando(e)} · {f['cidade']}/{f['uf']}" + (f" · {_vagas_txt(v)}" if v else "")

    itens = [(facs[e["faculdade_id"]]["sigla"], sub_prazo(e, facs[e["faculdade_id"]]), _selo(e)) for e in lista]
    n = s.cartoes(itens, lambda k: (len(lista), "editais com prazo nas próximas duas semanas" + (f" · mais {len(lista) - k} no site" if len(lista) > k else "")),
                  minimo=112)
    lista = lista[:n]
    corpo = ("Estes são os prazos de inscrição, de editais conferidos, que encerram nas próximas duas semanas, em ordem de data. Há outros editais no site, "
             "ainda em conferência. O prazo pode ser prorrogado ou retificado: confira no edital oficial.")
    return _resultado("prazos-14-dias", [s], _legenda(corpo, "Receba o aviso antes que feche"),
                      [_fonte_edital(e, facs[e["faculdade_id"]], f", prazo {e['inscricao_fim']}") for e in lista],
                      ["; ".join(f"{facs[e['faculdade_id']]['sigla']} até {g.fmt(e['inscricao_fim'])[:5]}" for e in lista)],
                      [(e, "inscricao_fim") for e in lista], facs, gancho)


def post_taxas(editais, facs, hoje):
    ab = [e for e in abertos(editais, facs, hoje, "taxa_inscricao") if e.get("taxa_inscricao") is not None]
    if len(ab) < 5:
        return None
    t = sorted(e["taxa_inscricao"] for e in ab)
    gancho = f"Taxas de {_reais(t[0])} a {_reais(t[-1])} nestes {len(ab)} editais" if t[0] else f"Taxas de até {_reais(t[-1])} nestes {len(ab)} editais"
    s = Lona("Taxa de inscrição", gancho)
    s.cartoes([("Menor taxa", f"entre estes {len(ab)} editais abertos com taxa conferida" if t[0] else "há edital aberto sem taxa de inscrição", f"R$ {t[0]:.0f}" if t[0] else "sem taxa"),
               ("Taxa mediana", "a metade cobra menos que isto", f"R$ {statistics.median(t):.0f}"),
               ("Maior taxa", "cada taxa é por inscrição", f"R$ {t[-1]:.0f}")],
              lambda k: (len(ab), "editais abertos com a taxa conferida no edital"))
    corpo = ("A taxa de inscrição varia muito de uma faculdade para outra, e em alguns editais é cobrada por campus. "
             "Veja a taxa de cada edital antes de decidir onde se inscrever.")
    return _resultado("taxas", [s], _legenda(corpo, "Compare os editais"),
                      [f"- {len(ab)} editais abertos com taxa conferida (data/editais.json): menor R$ {t[0]:.2f}, mediana R$ {statistics.median(t):.2f}, maior R$ {t[-1]:.2f}"]
                      + [_fonte_edital(e, facs[e["faculdade_id"]], f", taxa R$ {e['taxa_inscricao']:.2f}", "taxa_inscricao") for e in ab],
                      [f"Taxas de inscrição dos editais abertos conferidos: de R$ {t[0]:.0f} a R$ {t[-1]:.0f}"], [(e, "taxa_inscricao") for e in ab], facs, gancho)


def post_exterior(editais, facs, hoje):
    todos = abertos(editais, facs, hoje, "aceita_curso_exterior")
    lista = [e for e in todos if e.get("aceita_curso_exterior") is True]
    if not lista:
        return None
    nao = sum(1 for e in todos if e.get("aceita_curso_exterior") is False)
    gancho = f"Estes {len(lista)} editais abertos aceitam quem estudou fora"
    s = Lona("Estuda Medicina fora do Brasil?", gancho)
    itens = [(facs[e["faculdade_id"]]["sigla"], _sub(e, facs[e["faculdade_id"]]), _selo(e)) for e in lista]
    n = s.cartoes(itens, lambda k: (len(lista), "editais abertos e conferidos dizem que aceitam" + (f" · mais {len(lista) - k} no site" if len(lista) > k else "")
                                    + f" · entre os conferidos, {nao} dizem que NÃO aceitam"))
    lista = lista[:n]
    corpo = ("Nem todo edital aceita quem cursou parte da faculdade no exterior. "
             f"Estes {len(lista)} editais abertos e conferidos dizem que aceitam, em ordem de prazo. "
             f"Entre os conferidos, {nao} dizem expressamente que não aceitam.")
    return _resultado("estudo-no-exterior", [s], _legenda(corpo, "Veja o que cada edital exige"),
                      [_fonte_edital(e, facs[e["faculdade_id"]], ", aceita curso do exterior", "aceita_curso_exterior") for e in lista],
                      ["; ".join(facs[e["faculdade_id"]]["sigla"] for e in lista)], [(e, "aceita_curso_exterior") for e in lista], facs, gancho)


def post_documentos(editais, facs, hoje):
    ab = [e for e in abertos(editais, facs, hoje, "documentos") if e.get("documentos")]
    if len(ab) < 8:
        return None
    chaves = [("Histórico escolar", r"hist[oó]rico"), ("Declaração de vínculo com a faculdade", r"v[ií]nculo"),
              ("Programas das disciplinas (ementas)", r"programa|ementa|plano de ensino"), ("Documento de identidade e CPF", r"\bRG\b|identidade|\bCPF\b"),
              ("Declaração do Enade", r"enade")]
    cont = [(nome, sum(1 for e in ab if any(re.search(rx, doc, re.I) for doc in e["documentos"]))) for nome, rx in chaves]
    cont = sorted([c for c in cont if c[1]], key=lambda kv: -kv[1])
    if not cont:
        return None
    gancho = f"{cont[0][0]}: pedido em {cont[0][1]} de {len(ab)} abertos"
    s = Lona("Documentos mais pedidos", gancho)
    s.cartoes([(nome, f"citado na lista de {n} destes {len(ab)} editais abertos", f"{n} de {len(ab)}") for nome, n in cont[:4]],
              lambda k: (len(ab), "editais abertos com lista de documentos transcrita. Cada edital tem a sua lista"))
    corpo = (f"Entre estes {len(ab)} editais abertos e conferidos, estes são os documentos mais citados nas listas. "
             "A lista exata é a do edital da faculdade onde você vai se inscrever.")
    return _resultado("documentos", [s], _legenda(corpo, "Veja os documentos de cada edital"),
                      [f"- contagem sobre {len(ab)} editais abertos com lista de documentos transcrita (campo `documentos`, página em `evidencias`)"]
                      + [_fonte_edital(e, facs[e["faculdade_id"]], "", "documentos") for e in ab],
                      ["; ".join(f"{nome}: {n} de {len(ab)}" for nome, n in cont[:4])], [(e, "documentos") for e in ab], facs, gancho)


def post_estados(editais, facs, hoje):
    ab = abertos(editais, facs, hoje)
    c = Counter(facs[e["faculdade_id"]]["uf"] for e in ab)
    if not c:
        return None
    gancho = f"Estes {len(ab)} editais abertos estão em {len(c)} {'estado' if len(c) == 1 else 'estados'}"
    s = Lona("Onde estão os editais", gancho)
    ordem = sorted(c.items(), key=lambda kv: (g.ordem_uf(kv[0]), kv[0]))
    fac_uf = {uf: len({e["faculdade_id"] for e in ab if facs[e["faculdade_id"]]["uf"] == uf}) for uf in c}
    n = s.cartoes([(g.NOMES_UF.get(uf, uf), f"faculdades com edital aberto e conferido: {fac_uf[uf]}",
                    f"{k} {'conferido' if k == 1 else 'conferidos'}") for uf, k in ordem],
                  lambda k: (len(ab), f"editais abertos e conferidos, em {len(c)} {'estado' if len(c) == 1 else 'estados'}" + (f" · mais {len(ordem) - k} no site" if len(ordem) > k else "")),
                  minimo=100, painel_min=170)
    ordem = ordem[:n]
    corpo = ("Estes são os editais de transferência de Medicina abertos hoje com dados conferidos no PDF oficial, por estado. "
             "Há outros no site, ainda em conferência.")
    return _resultado("editais-por-estado", [s], _legenda(corpo, "Veja o seu estado"),
                      [f"- {k} editais abertos em {uf} (contagem de data/editais.json em {g.fmt(hoje)}):" for uf, k in ordem]
                      + [_fonte_edital(e, facs[e["faculdade_id"]]) for e in ab],
                      ["; ".join(f"{uf}: {k}" for uf, k in ordem)], [(e, "inscricao_fim") for e in ab], facs, gancho)


def post_abrem_em_breve(editais, facs, hoje):
    """FORA da reserva desde 09/11/2026: a tendência vem do histórico das faculdades e não tem a página de cada fato, o que a checagem exige."""
    h = date.fromisoformat(hoje)
    prox = h.month % 12 + 1
    com_aberto = {e["faculdade_id"] for e in ig.abertos(editais, facs, hoje)}
    breve = [f for f in facs.values() if f["id"] not in com_aberto and f["uf"] in g.PRIORITARIOS and prox in (f.get("meses") or [])]
    if len(breve) < 3:
        return None
    breve = sorted({f["sigla"]: f for f in breve}.values(), key=lambda f: f["sigla"])
    s = Lona("Pelo histórico", f"Costumam abrir em {g.MESES[prox - 1]}")
    n = s.cartoes([(f["sigla"], f"{f['cidade']}/{f['uf']}", "histórico") for f in breve],
                  lambda k: (len(breve), "faculdades abriram em " + g.MESES[prox - 1] + " nos editais anteriores. Não é data de abertura"))
    breve = breve[:n]
    corpo = (f"Faculdades que, pelo histórico dos editais anteriores, costumam abrir transferência em {g.MESES[prox - 1]}. "
             "É uma tendência, não uma promessa: cada faculdade decide a cada semestre.")
    return _resultado("costumam-abrir", [s], _legenda(corpo, "Receba o aviso quando abrir"),
                      [f"- {f['sigla']} ({f['id']}): meses no histórico {f.get('meses')}" for f in breve], ["; ".join(f["sigla"] for f in breve)])


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
                 "carrossel": len(urls) > 1, "usados": resultado["usados"], "fatos": resultado["fatos"], "textos": resultado["textos"], "telas": [{"tipo": "robo", "textos": list(sl.textos)} for sl in resultado["slides"]], "gancho": resultado.get("gancho", ""), "nota": nota, "gerado_em": (agora or datetime.now(BRASILIA)).isoformat(timespec="seconds")}
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
    """Post que o dono revisou à mão (post.json com "revisado": true): o robô nunca o regera nem o sobrescreve."""
    try:
        return json.loads((Path(pasta) / "post.json").read_text(encoding="utf-8")).get("revisado") is True
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


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", default=None, help="dia da publicação, AAAA-MM-DD (padrão: amanhã, em Brasília)")
    ap.add_argument("--manter", type=int, default=14, help="quantos dias de pastas antigas ficam em docs/social")
    ap.add_argument("--sincronizar", action="store_true", help="copia legendas e fontes de docs/social para privado/instagram e sai")
    args = ap.parse_args(argv)
    hoje = args.data or amanha_em_brasilia()
    if args.sincronizar:
        print("Sincronizado em privado/instagram:", ", ".join(sincronizar(hoje)) or "nada")
        return 0
    pasta = SOCIAL / hoje
    if aplicar_revisado(hoje):
        print(f"Post de {hoje}: usada a pasta privado/instagram/{hoje}-revisado (tem prioridade sobre o robô)")
        return 0
    if revisado_pelo_dono(pasta):
        print(f"Post de {hoje} revisado pelo dono (post.json com revisado=true): mantido, nada foi regerado")
        return 0
    editais, facs = _dados()
    resultado, nota = escolher(editais, facs, hoje)
    if not resultado:
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "SEM_POST.txt").write_text(f"Sem post para {hoje}: {nota}. Nada foi inventado.\n", encoding="utf-8")
        print("Sem post:", nota)
        return 0
    privado = PRIVADO / hoje if PRIVADO.parent.exists() else None
    m = gravar(resultado, nota, hoje, privado=privado)
    apagadas = podar(args.manter, hoje)
    print(f"Post de {m['dia_da_semana']} ({m['tipo']}): {len(m['imagens'])} imagem(ns) em docs/social/{hoje}"
          + (f" · {nota}" if nota else "") + (f" · pastas antigas apagadas: {len(apagadas)}" if apagadas else ""))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
