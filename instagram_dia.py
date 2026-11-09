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

class Lona:
    """Um slide: fundo com anéis de radar, cabeçalho com o logo, título, corpo que preenche a altura e rodapé com o link."""

    TOPO_TITULO = 215
    RODAPE = 190

    def __init__(self, kicker, titulo, tam_titulo=62):
        from PIL import Image, ImageDraw
        self.Image = Image
        self.img = Image.new("RGBA", (LARGURA, ALTURA), rgb(AZUL))
        self._radar()
        self.d = ImageDraw.Draw(self.img, "RGBA")
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
        d.text((64, y0 + 124), "Confira sempre o edital oficial. Os prazos podem mudar.", font=g._fonte(24), fill=rgb(CINZA))

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

    def _painel(self, y, h, numero, rotulo):
        d, x, w = self.d, 64, LARGURA - 128
        d.rounded_rectangle((x, y, x + w, y + h), radius=26, fill=rgb(VERDE_AGUA))
        fn = g._fonte(min(150, max(80, int(h * 0.62))), "Bold")
        while d.textlength(str(numero), font=fn) > w * 0.46 and fn.size > 50:
            fn = g._fonte(fn.size - 4, "Bold")
        larg_n = int(d.textlength(str(numero), font=fn))
        d.text((x + 36, y + (h - fn.size) // 2 - 10), str(numero), font=fn, fill=rgb(AZUL))
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

    def painel_total(self, numero, rotulo, extras=()):
        """Capa do carrossel: o número grande ocupa o corpo, com uma lista curta embaixo."""
        d, x, w = self.d, 64, LARGURA - 128
        y0, y1 = self.topo, self.base
        d.rounded_rectangle((x, y0, x + w, y1), radius=26, fill=rgb(VERDE_AGUA))
        fn = g._fonte(380, "Bold")
        fr, fe = g._fonte(40, "Bold"), g._fonte(30, "SemiBold")
        caixa = d.textbbox((0, 0), str(numero), font=fn)  # (x0, y0, x1, y1) do desenho real do número
        linhas_r = g._quebrar(d, rotulo, fr, w - 80)[:2]
        total = (caixa[3] - caixa[1]) + 36 + 52 * len(linhas_r) + 14 + 42 * len(extras)
        ty = y0 + (y1 - y0 - total) // 2  # o conjunto fica no centro do painel: sem faixa vazia em cima ou embaixo
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


def _fonte_edital(e, f, extra=""):
    return f"- {f['sigla']}: `{e['id']}`{extra} ({e['url_edital']})"


def _resultado(tipo, slides, legenda, fontes, alts):
    return {"tipo": tipo, "slides": slides, "legenda": legenda, "fontes": fontes, "alt": alts}


def _legenda(corpo, cta):
    return f"{corpo}\n\n{cta}: {LINK} (link na bio)\nConfira sempre o edital oficial.\n\n{HASHTAGS}\n"


# ---------------------------------------------------------------- os formatos

def post_abertos(editais, facs, hoje):
    """Segunda: carrossel com a capa (quantos editais estão abertos) e 4 editais por slide, em ordem de prazo. Até 10 slides."""
    lista = ig.abertos(editais, facs, hoje)
    if not lista:
        return None
    h = date.fromisoformat(hoje)
    por_uf = Counter(facs[e["faculdade_id"]]["uf"] for e in lista)
    top = [f"{uf}: {n}" for uf, n in sorted(por_uf.items(), key=lambda kv: (g.ordem_uf(kv[0]), kv[0]))][:6]
    capa = Lona("Semana de " + g.fmt(hoje)[:5], "Editais de transferência abertos esta semana")
    capa.painel_total(len(lista), "editais de Medicina com inscrição aberta, em ordem de prazo", ["Por estado: " + " · ".join(top), "Arraste para ver →"])
    slides, alts, fontes = [capa], [f"{len(lista)} editais de transferência de Medicina abertos na semana de {g.fmt(hoje)[:5]}"], []
    i = 0
    while i < len(lista) and len(slides) < 10:
        sl = Lona(f"Editais abertos · {len(slides)}", "Inscrição aberta")
        resto = lista[i:]
        itens = [(facs[e["faculdade_id"]]["sigla"], _sub(e, facs[e["faculdade_id"]]), _selo(e)) for e in resto]
        n = sl.cartoes(itens, lambda k, i=i: (len(lista), "editais abertos no radar" + (f" · faltam {len(lista) - i - k} nos próximos slides" if len(lista) - i - k > 0 else " · este é o último")),
                       minimo=128, painel_min=150)
        grupo = resto[:n]
        slides.append(sl)
        alts.append("; ".join(f"{facs[e['faculdade_id']]['sigla']} até {g.fmt(e['inscricao_fim'])[:5]}" for e in grupo))
        fontes += [_fonte_edital(e, facs[e["faculdade_id"]], f", prazo {e['inscricao_fim']}") for e in grupo]
        i += n
    extra = f" Mais {len(lista) - i} no site." if i < len(lista) else ""
    corpo = (f"{len(lista)} editais de transferência de Medicina com inscrição aberta nesta semana, em ordem de prazo (arraste).{extra} "
             "O prazo é o que está no edital: confira sempre o documento oficial antes de se inscrever.")
    return _resultado("editais-abertos-da-semana", slides, _legenda(corpo, "Veja em quais você pode se inscrever"), fontes, alts)


def _restricoes(editais, facs, hoje):
    """Regras reais de edital aberto, com a página do PDF registrada em `evidencias`."""
    saida = []
    for e in ig.abertos(editais, facs, hoje):
        pag = (e.get("evidencias") or {}).get("outras_restricoes")
        for r in e.get("outras_restricoes") or []:
            if pag and 25 <= len(r) <= 170 and "R$" not in r and "bolsa" not in r.lower():
                saida.append((e, re.sub(r"\s*\([^)]*\)", "", r).strip().rstrip(";."), pag))
    return saida


def post_armadilha(editais, facs, hoje):
    achados = _restricoes(editais, facs, hoje)
    if not achados:
        return None
    semana = date.fromisoformat(hoje).isocalendar()[1]
    e, texto, pag = achados[semana % len(achados)]  # muda toda semana, sem guardar estado
    f = facs[e["faculdade_id"]]
    s = Lona("Armadilha do edital", "Leia antes de pagar a taxa", 66)
    citacao = f"“{texto}”"
    tam, linhas = 96, []
    largura = LARGURA - 128 - 96
    while tam >= 36:  # a maior letra em que o texto cabe, para o cartão nunca ficar vazio
        linhas = g._quebrar(s.d, citacao, g._fonte(tam, "SemiBold"), largura)
        if len(linhas) * int(tam * 1.28) <= (s.base - s.topo) - 330:
            break
        tam -= 4
    s.texto_grande(linhas, tam, entrada="O edital diz:", saida="Confira o texto completo na página indicada do edital.",
                   rodape_painel=f"{f['sigla']} · {f['cidade']}/{f['uf']} · edital, p. {str(pag).split()[0]}")
    corpo = (f"Esta regra está escrita no edital da {f['sigla']} ({f['cidade']}/{f['uf']}), na página {str(pag).split()[0]}, e pode deixar você de fora. "
             "Detalhes pequenos do edital mudam tudo: leia antes de pagar a taxa.")
    return _resultado("armadilha-do-edital", [s], _legenda(corpo, "Veja os requisitos de cada edital aberto"),
                      [f"- {f['sigla']}: `{e['id']}`, página {pag}, regra: \"{texto}\" ({e['url_edital']})"],
                      [f"Regra do edital da {f['sigla']}: {texto}"])


def post_prazos(editais, facs, hoje):
    h = date.fromisoformat(hoje)
    limite = (h + timedelta(days=14)).isoformat()
    lista = [e for e in ig.abertos(editais, facs, hoje) if e["inscricao_fim"] <= limite]
    if not lista:
        return None
    s = Lona("Prazos dos próximos 14 dias", "Estes prazos fecham logo")

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
    corpo = ("Prazos de inscrição que encerram nas próximas duas semanas, em ordem de data. O prazo pode ser prorrogado ou retificado: "
             "confira no edital oficial.")
    return _resultado("prazos-14-dias", [s], _legenda(corpo, "Receba o aviso antes que feche"),
                      [_fonte_edital(e, facs[e["faculdade_id"]], f", prazo {e['inscricao_fim']}") for e in lista],
                      ["; ".join(f"{facs[e['faculdade_id']]['sigla']} até {g.fmt(e['inscricao_fim'])[:5]}" for e in lista)])


def post_taxas(editais, facs, hoje):
    ab = [e for e in ig.abertos(editais, facs, hoje) if e.get("taxa_inscricao") is not None and "taxa_inscricao" not in (e.get("conferir_campos") or {})]
    if len(ab) < 5:
        return None
    t = sorted(e["taxa_inscricao"] for e in ab)
    s = Lona("Taxa de inscrição", "Quanto custa se inscrever?")
    s.cartoes([("Menor taxa", f"entre os {len(ab)} editais abertos com taxa conferida" if t[0] else "há edital aberto sem taxa de inscrição", f"R$ {t[0]:.0f}" if t[0] else "sem taxa"),
               ("Taxa mediana", "a metade cobra menos que isto", f"R$ {statistics.median(t):.0f}"),
               ("Maior taxa", "cada taxa é por inscrição", f"R$ {t[-1]:.0f}")],
              lambda k: (len(ab), "editais abertos com a taxa conferida no edital"))
    corpo = ("A taxa de inscrição varia muito de uma faculdade para outra, e em alguns editais é cobrada por campus. "
             "Veja a taxa de cada edital antes de decidir onde se inscrever.")
    return _resultado("taxas", [s], _legenda(corpo, "Compare os editais"),
                      [f"- {len(ab)} editais abertos com taxa conferida (data/editais.json): menor R$ {t[0]:.2f}, mediana R$ {statistics.median(t):.2f}, maior R$ {t[-1]:.2f}"]
                      + [_fonte_edital(e, facs[e["faculdade_id"]], f", taxa R$ {e['taxa_inscricao']:.2f}") for e in ab],
                      [f"Taxas de inscrição dos editais abertos: de R$ {t[0]:.0f} a R$ {t[-1]:.0f}"])


def post_exterior(editais, facs, hoje):
    todos = ig.abertos(editais, facs, hoje)
    lista = [e for e in todos if e.get("aceita_curso_exterior") is True]
    if not lista:
        return None
    nao = sum(1 for e in todos if e.get("aceita_curso_exterior") is False)
    s = Lona("Estuda Medicina fora do Brasil?", "Editais que aceitam quem estudou fora")
    itens = [(facs[e["faculdade_id"]]["sigla"], _sub(e, facs[e["faculdade_id"]]), _selo(e)) for e in lista]
    n = s.cartoes(itens, lambda k: (len(lista), "editais abertos dizem que aceitam" + (f" · mais {len(lista) - k} no site" if len(lista) > k else "")
                                    + f" · outros {nao} dizem que NÃO aceitam"))
    lista = lista[:n]
    corpo = ("Nem todo edital aceita quem cursou parte da faculdade no exterior. Estes dizem que aceitam, em ordem de prazo. "
             f"Outros {nao} editais abertos dizem expressamente que não aceitam.")
    return _resultado("estudo-no-exterior", [s], _legenda(corpo, "Veja o que cada edital exige"),
                      [_fonte_edital(e, facs[e["faculdade_id"]], ", aceita curso do exterior") for e in lista],
                      ["; ".join(facs[e["faculdade_id"]]["sigla"] for e in lista)])


def post_documentos(editais, facs, hoje):
    ab = [e for e in ig.abertos(editais, facs, hoje) if e.get("documentos")]
    if len(ab) < 8:
        return None
    chaves = [("Histórico escolar", r"hist[oó]rico"), ("Declaração de vínculo com a faculdade", r"v[ií]nculo"),
              ("Programas das disciplinas (ementas)", r"programa|ementa|plano de ensino"), ("Documento de identidade e CPF", r"\bRG\b|identidade|\bCPF\b"),
              ("Declaração do Enade", r"enade")]
    cont = [(nome, sum(1 for e in ab if any(re.search(rx, doc, re.I) for doc in e["documentos"]))) for nome, rx in chaves]
    cont = sorted([c for c in cont if c[1]], key=lambda kv: -kv[1])
    if not cont:
        return None
    s = Lona("Documentos mais pedidos", "O que separar antes de se inscrever")
    s.cartoes([(nome, f"citado na lista de {n} dos {len(ab)} editais abertos", f"{n} de {len(ab)}") for nome, n in cont[:4]],
              lambda k: (len(ab), "editais abertos com lista de documentos transcrita. Cada edital tem a sua lista"))
    corpo = f"Documentos citados nas listas de {len(ab)} editais abertos. A lista exata é a do edital da faculdade onde você vai se inscrever."
    return _resultado("documentos", [s], _legenda(corpo, "Veja os documentos de cada edital"),
                      [f"- contagem sobre {len(ab)} editais abertos com lista de documentos transcrita (campo `documentos`, página em `evidencias`)"]
                      + [_fonte_edital(e, facs[e["faculdade_id"]]) for e in ab],
                      ["; ".join(f"{nome}: {n} de {len(ab)}" for nome, n in cont[:4])])


def post_estados(editais, facs, hoje):
    ab = ig.abertos(editais, facs, hoje)
    c = Counter(facs[e["faculdade_id"]]["uf"] for e in ab)
    if not c:
        return None
    s = Lona("Onde estão os editais", "Editais abertos por estado")
    ordem = sorted(c.items(), key=lambda kv: (g.ordem_uf(kv[0]), kv[0]))
    fac_uf = {uf: len({e["faculdade_id"] for e in ab if facs[e["faculdade_id"]]["uf"] == uf}) for uf in c}
    n = s.cartoes([(g.NOMES_UF.get(uf, uf), f"{fac_uf[uf]} {'faculdade' if fac_uf[uf] == 1 else 'faculdades'} com edital aberto",
                    f"{k} {'edital' if k == 1 else 'editais'}") for uf, k in ordem],
                  lambda k: (len(ab), f"editais abertos em {len(c)} {'estado' if len(c) == 1 else 'estados'}" + (f" · mais {len(ordem) - k} no site" if len(ordem) > k else "")),
                  minimo=100, painel_min=170)
    ordem = ordem[:n]
    corpo = "Editais de transferência de Medicina abertos hoje, por estado, com dados conferidos no PDF oficial."
    return _resultado("editais-por-estado", [s], _legenda(corpo, "Veja o seu estado"),
                      [f"- {k} editais abertos em {uf} (contagem de data/editais.json em {g.fmt(hoje)}):" for uf, k in ordem]
                      + [_fonte_edital(e, facs[e["faculdade_id"]]) for e in ab],
                      ["; ".join(f"{uf}: {k}" for uf, k in ordem)])


def post_abrem_em_breve(editais, facs, hoje):
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
RESERVA = [post_estados, post_prazos, post_abrem_em_breve]  # quando o formato do dia não tem dado seguro


def escolher(editais, facs, hoje):
    """(resultado, nota). O formato do dia; se não houver dado seguro, o primeiro da reserva que tiver. Nada é inventado."""
    dia = date.fromisoformat(hoje).weekday()
    principal = CALENDARIO[dia]
    r = principal(editais, facs, hoje)
    if r:
        return r, ""
    for reserva in RESERVA:
        if reserva is principal:
            continue
        r = reserva(editais, facs, hoje)
        if r:
            return r, f"o formato de {DIAS[dia]} ({principal.__name__}) não tinha dado seguro; usou a reserva {reserva.__name__}"
    return None, f"nenhum formato tinha dado seguro para {DIAS[dia]}"


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
                 "carrossel": len(urls) > 1, "nota": nota, "gerado_em": (agora or datetime.now(BRASILIA)).isoformat(timespec="seconds")}
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
    editais, facs = _dados()
    resultado, nota = escolher(editais, facs, hoje)
    pasta = SOCIAL / hoje
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
