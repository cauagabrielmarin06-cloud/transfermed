"""
Isca do alerta: PDF "Checklist de documentos para transferência de Medicina".

Só entra o que foi transcrito à mão do edital (campo "documentos" de editais conferidos), com a página de onde saiu.
Nada é deduzido: os grupos abaixo só juntam itens que o próprio edital escreveu, por palavras do texto, e cada item
aparece com a faculdade, o edital e a página. O gerador do site chama `gerar()` a cada atualização.
"""
import re
import unicodedata
from datetime import datetime, timezone

ARQUIVO = "checklist-documentos-transferencia-medicina.pdf"
ARQUIVO_EXTERIOR = "checklist-documentos-transferencia-medicina-exterior.pdf"  # só editais que aceitam quem vem de fora
FORA = ("portador_diploma",)  # outro público (diplomados): lista própria, não entra no checklist de quem cursa Medicina

# (título, explicação curta, palavras do texto que colocam o item no grupo)
GRUPOS = [
    ("Histórico escolar", "O documento que mais aparece. Repare no que cada edital exige junto: carga horária, notas, "
     "assinatura, data de emissão.", r"historico"),
    ("Programas das disciplinas (planos de ensino, ementas)", "É com eles que a faculdade decide o aproveitamento das "
     "matérias. Costumam demorar para sair: peça cedo.", r"programa|plano[s]? de ensino|ementa|projetos de ensino"),
    ("Comprovante de matrícula ou de vínculo", "Mostra que você ainda está cursando. Vários editais dizem de qual "
     "semestre ele tem que ser.", r"(?<!na )matricula|vinculo|trancamento"),
    ("Carga horária cursada", "Alguns editais pedem a carga horária em documento separado do histórico.",
     r"carga horaria"),
    ("ENADE / Enamed", "Situação regular no exame nacional, às vezes dentro do próprio histórico.", r"enade|enamed"),
    ("Autorização ou reconhecimento do curso de origem", "Ato do MEC que autoriza ou reconhece o seu curso.",
     r"autorizacao|reconhecimento"),
    ("Documentos pessoais", "Identidade, CPF e, em alguns editais, certidão e comprovante de residência.",
     r"\brg\b|cpf|identidade|certidao|residencia|cnh|\brne\b"),
    ("Ensino médio", "Certificado de conclusão, às vezes só na matrícula.", r"ensino medio"),
    ("Quem estuda no exterior", "Documentos estrangeiros precisam de legalização e tradução. Veja o que cada edital "
     "aceita: apostila de Haia ou visto consular.", r"apostila|consular|traducao juramentada|exterior|estrangeir"),
]
OUTROS = ("Outros pedidos que apareceram", "Itens que só um ou outro edital pede.")


def norm(s):
    return unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()


def do_exterior(E):
    """Editais que aceitam quem estuda Medicina no exterior (exclusivos ou abertos aos dois públicos)."""
    return [x for x in E if x.get("modalidade") == "exterior" or x.get("aceita_curso_exterior") is True]


def editais_com_lista(E, F):
    """Editais conferidos com documentos transcritos, sem repetir o mesmo PDF (o IDOMED publica um edital para 3
    câmpus): um item por PDF e modalidade, com as faculdades que ele cobre."""
    vistos = {}
    for ed in E:
        if not ed.get("documentos") or ed.get("modalidade") in FORA or ed.get("fluxo_continuo") or ed["faculdade_id"] not in F:
            continue
        chave = (ed["url_edital"], ed.get("modalidade"))
        if chave in vistos:
            vistos[chave]["siglas"].append(F[ed["faculdade_id"]]["sigla"])
            continue
        pag = (ed.get("evidencias") or {}).get("documentos")
        vistos[chave] = {"ed": ed, "siglas": [F[ed["faculdade_id"]]["sigla"]],
                         "pagina": f"p. {pag}" if isinstance(pag, int) else (pag or "")}
    return list(vistos.values())


def montar(E, F):
    """Grupos com os itens transcritos e a fonte de cada um. Devolve (grupos, total de editais, data mais recente)."""
    base = editais_com_lista(E, F)
    grupos = [{"titulo": t, "explica": x, "itens": [], "editais": set()} for t, x, _ in GRUPOS]
    outros = {"titulo": OUTROS[0], "explica": OUTROS[1], "itens": [], "editais": set()}
    for i, b in enumerate(base):
        ed = b["ed"]
        siglas = " / ".join(dict.fromkeys(b["siglas"]))
        fonte = ", ".join(x for x in (siglas, ed.get("numero_edital"), f"ingresso {ed['semestre_ingresso']}" if ed.get("semestre_ingresso") else "",
                                      b["pagina"]) if x)
        for doc in ed["documentos"]:
            # o grupo é o da palavra que aparece primeiro: "Ato de autorização, se não constar no histórico" é ato,
            # "Histórico ... com situação no ENADE" é histórico
            achados = [(m.start(), k) for k, (_, _, rx) in enumerate(GRUPOS) for m in [re.search(rx, norm(doc))] if m]
            g = grupos[min(achados)[1]] if achados else outros
            g["itens"].append((doc, fonte))
            g["editais"].add(i)
    usados = [g for g in grupos if g["itens"]] + ([outros] if outros["itens"] else [])
    datas = [b["ed"].get("conferido_em") or b["ed"].get("atualizado_em") for b in base]
    return usados, len(base), max(d for d in datas if d) if datas else None


def gerar(E, F, destino, fonte_ttf, site_url, subtitulo="para transferência de Medicina"):
    """Grava o PDF e devolve o número de editais usados. O arquivo só muda quando os dados mudam (datas fixas)."""
    from fpdf import FPDF

    grupos, total, data = montar(E, F)
    data_br = "/".join(reversed(data.split("-"))) if data else ""
    verde, tinta, cinza, linha = (15, 92, 77), (26, 31, 28), (86, 91, 87), (228, 224, 216)

    pdf = FPDF(format="A4")
    pdf.set_creation_date(datetime.fromisoformat(data or "2026-01-01").replace(tzinfo=timezone.utc))
    pdf.set_title(f"Checklist de documentos {subtitulo}")
    pdf.set_author("Transfermed")
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(True, 20)
    pdf.add_font("Inter", "", str(fonte_ttf), variations={"wght": 400})
    pdf.add_font("Inter", "B", str(fonte_ttf), variations={"wght": 700})

    def rodape():
        pdf.set_y(-14)
        pdf.set_font("Inter", "", 8)
        pdf.set_text_color(*cinza)
        pdf.cell(0, 5, f"transfermed.com.br · Quem decide a vaga e o aproveitamento é sempre a faculdade · página {pdf.page_no()}",
                 align="C")

    pdf.footer = rodape
    pdf.add_page()
    pdf.set_fill_color(*verde)
    pdf.rect(0, 0, 210, 40, "F")
    pdf.set_xy(18, 11)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Inter", "B", 20)
    pdf.cell(0, 9, "Checklist de documentos", new_x="LMARGIN", new_y="NEXT", align="L")
    pdf.set_font("Inter", "", 12)
    pdf.cell(0, 7, subtitulo, new_x="LMARGIN", new_y="NEXT", align="L")
    pdf.set_y(48)
    pdf.set_text_color(*tinta)
    pdf.set_font("Inter", "B", 11)
    pdf.multi_cell(0, 6, f"Baseado em {total} editais conferidos no PDF oficial (o mais recente em {data_br}).",
                   new_x="LMARGIN", new_y="NEXT", align="L")
    pdf.set_font("Inter", "", 10)
    pdf.set_text_color(*cinza)
    pdf.multi_cell(0, 5.2, "Cada item abaixo foi copiado do edital, com a faculdade e a página de onde saiu. Os grupos só juntam "
                   "pedidos parecidos para você se organizar: cada edital tem a sua lista, então confira sempre o edital "
                   "vigente antes de enviar.", new_x="LMARGIN", new_y="NEXT", align="L")
    for g in grupos:
        pdf.ln(5)
        if pdf.get_y() > 250:
            pdf.add_page()
        pdf.set_draw_color(*linha)
        pdf.line(18, pdf.get_y(), 192, pdf.get_y())
        pdf.ln(3)
        pdf.set_text_color(*verde)
        pdf.set_font("Inter", "B", 13)
        pdf.multi_cell(0, 7, g["titulo"], new_x="LMARGIN", new_y="NEXT", align="L")
        pdf.set_text_color(*cinza)
        pdf.set_font("Inter", "", 9.5)
        n = len(g["editais"])
        pdf.multi_cell(0, 5, f"Pedido em {n} de {total} editais. {g['explica']}", new_x="LMARGIN", new_y="NEXT", align="L")
        pdf.ln(1)
        for doc, fonte in dict.fromkeys(g["itens"]):
            if pdf.get_y() > 268:
                pdf.add_page()
            pdf.set_draw_color(*verde)
            pdf.rect(19, pdf.get_y() + 0.9, 3.4, 3.4)  # caixinha para marcar à mão
            pdf.set_x(25)
            pdf.set_text_color(*tinta)
            pdf.set_font("Inter", "", 10)
            pdf.multi_cell(0, 5, doc, new_x="LMARGIN", new_y="NEXT", align="L")
            pdf.set_x(25)
            pdf.set_text_color(*cinza)
            pdf.set_font("Inter", "", 8.5)
            pdf.multi_cell(0, 4.4, fonte, new_x="LMARGIN", new_y="NEXT", align="L")
            pdf.ln(0.8)
    pdf.ln(6)
    pdf.set_text_color(*tinta)
    pdf.set_font("Inter", "B", 11)
    pdf.multi_cell(0, 6, "Receba um aviso quando abrir edital para o seu perfil", new_x="LMARGIN", new_y="NEXT", align="L")
    pdf.set_font("Inter", "", 10)
    pdf.set_text_color(*verde)
    pdf.cell(0, 6, f"{site_url.replace('https://', '')}/diagnostico/", link=f"{site_url}/diagnostico/?origem=checklist")
    pdf.output(str(destino))
    return total
