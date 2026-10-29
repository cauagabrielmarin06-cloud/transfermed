"""
Todos os e-mails do alerta, montados num lugar só: confirmação, alerta de editais, boas-vindas com o checklist,
dicas (dias 2, 5, 9 e 14), lembretes de prazo (7 e 2 dias antes) e resumo semanal. Quem envia e decide quando é o
`alertas.py`; enquanto a variável ALERTAS_ATIVOS não existir, só a confirmação e o alerta de editais saem de verdade.

Regras:
- Todo número vem dos editais conferidos (`data/editais.json`), calculado na hora do envio.
- Documento citado é paráfrase do que a base guarda (resumo do edital), sem aspas, com o link da página do PDF.
- Todo e-mail termina com o perfil do alerta, "Quem decide a vaga é sempre a faculdade." e o link de cancelar.
"""
import re
import unicodedata
from datetime import date, timedelta
from html import escape

import gerar_site
import isca
from gerar_site import MODALIDADES, dinheiro, fmt, publicavel, slug_edital, vagas_texto

# só recebe a sequência de dicas e o resumo quem aceitou o texto de consentimento que fala deles
MARCA_CONSENTIMENTO = "dicas sobre transferência"
SEQUENCIA = (0, 2, 5, 9, 14)   # dias depois da confirmação
JANELA_DIAS = 3                # se o robô atrasar (ou o dia já teve e-mail), ainda envia até 3 dias depois
LEMBRETE_LONGE, LEMBRETE_PERTO = 7, 2  # dias antes do fim das inscrições
DIAS_URGENTE = 7               # "Encerram nos próximos 7 dias"
MAX_BOAS_VINDAS = 5            # editais no e-mail de boas-vindas
ASSINATURA = "<p>Um abraço,<br>Cauã</p>"
VERDE = "#17694F"
ESTILO = "font-family:Arial,Helvetica,sans-serif;color:#1A1F1C;line-height:1.5"


def norm(s):
    return unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()


def plural(n, um, varios):
    return f"{n} {um if n == 1 else varios}"


def p(texto):
    return f"<p>{texto}</p>"


def h2(texto):
    return f'<h2 style="font-size:16px;margin:22px 0 8px">{escape(texto)}</h2>'


def link(url, texto):
    return f'<a href="{escape(url)}" style="color:{VERDE}">{escape(texto)}</a>'


def botao(url, texto):
    return (f'<p><a href="{escape(url)}" style="display:inline-block;background:#0F5C4D;color:#FFFFFF;text-decoration:none;'
            f'padding:12px 20px;border-radius:10px;font-weight:bold">{escape(texto)}</a></p>')


def lista(itens):
    return "<ul>" + "".join(f"<li style=\"margin:0 0 8px\">{i}</li>" for i in itens) + "</ul>"


def texto_puro(html):
    """Versão em texto simples: tira as tags; cada link vira "texto <endereço>"."""
    t = re.sub(r'<a href="([^"]+)"[^>]*>(.*?)</a>', "\\2 \x01\\1\x02", html, flags=re.S)  # marcas: "<url>" não é tag
    t = re.sub(r"<h2[^>]*>(.*?)</h2>", r"\n\1\n", t, flags=re.S)
    t = re.sub(r"<li[^>]*>", "- ", t)
    t = re.sub(r"</div>", "\n\n", t)  # um edital por bloco
    t = re.sub(r"</p>|</li>|<br>", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = t.replace("\x01", "<").replace("\x02", ">").replace("&amp;", "&").replace("&quot;", '"').replace("&#x27;", "'").replace("&lt;", "<").replace("&gt;", ">")
    t = re.sub(r"[ \t]+\n", "\n", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


# ---------------------------------------------------------------- perfil

def seguidas(p):
    return ((p or {}).get("seguir") or {}).get("faculdades") or []


def resumo_perfil(p):
    p = p or {}
    n = len(seguidas(p))
    if not p.get("curso"):
        return plural(n, "faculdade que você segue", "faculdades que você segue") if n else "editais de transferência de Medicina"
    partes = ["Medicina" if p.get("curso") == "medicina" else "outro curso da saúde",
              "no exterior" if p.get("origem") == "exterior" else "no Brasil"]
    if p.get("semestre"):
        partes.append(f"{p['semestre']}º semestre")
    if p.get("cidade"):
        partes.append(f"até {p['raio']} km de {p['cidade']}" if p.get("raio") else f"distâncias a partir de {p['cidade']}")
    if p.get("tipo") in ("publica", "particular"):
        partes.append("só faculdades públicas" if p["tipo"] == "publica" else "só faculdades particulares")
    texto = ", ".join(partes)
    return texto + (f" e {plural(n, 'faculdade que você segue', 'faculdades que você segue')}" if n else "")


def exterior(perfil):
    return (perfil or {}).get("origem") == "exterior"


# ---------------------------------------------------------------- moldura (igual para todos os e-mails)

def moldura(titulo, corpo_html, a, site):
    descad = f"{site}/alerta/descadastrar/?t={a['token']}"
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(titulo)}</title></head><body style="margin:0;background:#F7F5F1;padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#FFFFFF;border-radius:14px;{ESTILO}">
<tr><td style="background:#0F5C4D;border-radius:14px 14px 0 0;padding:18px 24px;color:#FFFFFF;font-size:18px;font-weight:bold">Transfermed
<div style="font-size:13px;font-weight:normal;color:#CFE8DF">Seu radar de transferência de Medicina</div></td></tr>
<tr><td style="padding:24px"><h1 style="font-size:20px;margin:0 0 12px">{escape(titulo)}</h1>{corpo_html}</td></tr>
<tr><td style="padding:16px 24px 24px;font-size:12px;color:#565B57;border-top:1px solid #E4E0D8">
Você recebe este e-mail porque ativou alertas para: {escape(resumo_perfil(a.get('perfil')))}.<br>
Quem decide a vaga é sempre a faculdade.<br>
<a href="{descad}" style="color:#565B57">Cancelar os alertas e apagar meus dados</a> · <a href="{site}/privacidade/" style="color:#565B57">Privacidade</a>
</td></tr></table></td></tr></table></body></html>"""


def finalizar(a, site, assunto, titulo, corpo):
    """(assunto, html, texto) com o mesmo rodapé nas duas versões."""
    texto = (texto_puro(corpo) + "\n\n--\n"
             f"Você recebe este e-mail porque ativou alertas para: {resumo_perfil(a.get('perfil'))}.\n"
             "Quem decide a vaga é sempre a faculdade.\n"
             f"Cancelar os alertas e apagar meus dados: {site}/alerta/descadastrar/?t={a['token']}")
    return assunto, moldura(titulo, corpo, a, site), texto


# ---------------------------------------------------------------- dados que os e-mails citam

class Contexto:
    """Números e exemplos calculados na hora do envio, a partir dos editais conferidos."""

    def __init__(self, editais, faculdades, site_url, hoje):
        self.F = faculdades
        self.E = [x for x in editais if publicavel(x) and x["faculdade_id"] in faculdades]
        self.site = site_url
        self.hoje = hoje
        reais = [x for x in self.E if not x.get("fluxo_continuo")]
        self.total = len(reais)
        self.com_prova = sum(1 for x in reais if "prova" in norm(x.get("criterio_selecao")))
        self.aceitam_exterior = sum(1 for x in reais if x.get("aceita_curso_exterior") is True or x.get("modalidade") == "exterior")
        self.nao_aceitam_exterior = sum(1 for x in reais if x.get("aceita_curso_exterior") is False)
        self.excluem_transferidos = sum(1 for x in reais if x.get("exclui_quem_ja_transferiu") is True)
        self.com_retificacao = sum(1 for x in reais if x.get("retificacoes"))
        janelas = sorted((date.fromisoformat(x["inscricao_fim"]) - date.fromisoformat(x["inscricao_inicio"])).days + 1
                         for x in reais if x.get("inscricao_inicio") and x.get("inscricao_fim"))
        self.com_janela = len(janelas)
        self.janela_mediana = janelas[len(janelas) // 2] if janelas else None
        self.janela_curta = sum(1 for d in janelas if d < 7)
        self.isca_url = f"{site_url}/{isca.ARQUIVO}"
        self.isca_total = len(isca.editais_com_lista(self.E, faculdades))

    def pagina(self, ed):
        return f"{self.site}/edital/{slug_edital(ed)}/"

    def exemplos(self, rx, n=3, sem_exterior=False):
        """Até n pedidos transcritos que batem com a expressão, um por faculdade, em paráfrase (a base guarda o resumo
        do edital, não o texto literal) e com o link da página do PDF."""
        achados, vistos = [], set()
        for b in isca.editais_com_lista(self.E, self.F):
            ed = b["ed"]
            sigla = " / ".join(dict.fromkeys(b["siglas"]))
            if sem_exterior and ed.get("modalidade") == "exterior":
                continue
            for doc in ed["documentos"]:
                if re.search(rx, norm(doc)) and sigla not in vistos:
                    vistos.add(sigla)
                    achados.append(f"{escape(sigla)} pede {escape(minuscula(doc))} ({link(self.pagina(ed), b['pagina'] or 'ver edital')})")
                    break
            if len(achados) >= n:
                break
        return achados


def minuscula(texto):
    """"Histórico escolar..." vira "histórico escolar..."; siglas no começo ("RG e CPF") ficam como estão."""
    primeira = texto.split(" ", 1)[0]
    return texto if primeira.isupper() else texto[:1].lower() + texto[1:]


# ---------------------------------------------------------------- editais no corpo do e-mail

def dias_para_fim(ed, hoje):
    return (date.fromisoformat(ed["inscricao_fim"]) - date.fromisoformat(hoje)).days if ed.get("inscricao_fim") else None


def separar(itens, hoje):
    """[(ed, fac)] em (encerram nos próximos 7 dias, abertos, abrem em breve), cada grupo pela data de fim."""
    urgentes, abertos, breve = [], [], []
    for ed, fac in sorted(itens, key=lambda t: t[0].get("inscricao_fim") or "9999"):
        sit, d = gerar_site.situacao(ed, hoje), dias_para_fim(ed, hoje)
        if sit == "em breve":
            breve.append((ed, fac))
        elif d is not None and 0 <= d <= DIAS_URGENTE:
            urgentes.append((ed, fac))
        else:
            abertos.append((ed, fac))
    return urgentes, abertos, breve


def cartao(ed, fac, perfil, c):
    cls, prazo = gerar_site.texto_situacao(ed, c.hoje)
    cor = {"alerta": "#B42318", "aviso": "#7A4D00"}.get(cls, VERDE)
    nome_mod = MODALIDADES.get(ed.get("modalidade"), MODALIDADES["externa"])[0]
    taxa = "" if ed.get("taxa_inscricao") is None else (" · inscrição gratuita" if ed["taxa_inscricao"] == 0 else f" · taxa {dinheiro(ed['taxa_inscricao'])}")
    semestre = ("" if (perfil or {}).get("semestre") else
                '<br><span style="font-size:14px;color:#7A4D00">Confira se o seu semestre se encaixa nas vagas.</span>')
    # conferência por campo: o aviso do campo duvidoso vai junto (prazo duvidoso nem chega aqui: fica fora dos e-mails)
    semestre += "".join(f'<br><span style="font-size:14px;color:#7A4D00"><strong>Atenção:</strong> {escape(a)}</span>'
                        for a in gerar_site.campos_conferir(ed).values())
    return (f'<div style="border:1px solid #E4E0D8;border-radius:12px;padding:12px 14px;margin:0 0 10px">'
            f"<strong>{escape(fac['sigla'])} ({escape(fac['cidade'])}/{escape(fac['uf'])})</strong><br>"
            f'<span style="font-size:14px;color:#565B57">{escape(nome_mod)}{" · ingresso " + escape(ed["semestre_ingresso"]) if ed.get("semestre_ingresso") else ""}</span><br>'
            f'<span style="font-weight:bold;color:{cor}">{escape(prazo)}</span><span style="font-size:14px">{escape(taxa)} · {escape(vagas_texto(ed))}</span>'
            f"{semestre}<br>{link(c.pagina(ed), 'Ver resumo e documentos')} · {link(ed['url_edital'], 'Edital oficial')}</div>")


def blocos(itens, perfil, c):
    urgentes, abertos, breve = separar(itens, c.hoje)
    html = ""
    for titulo, grupo in ((f"Encerram nos próximos {DIAS_URGENTE} dias", urgentes), ("Abertos", abertos), ("Abrem em breve", breve)):
        if grupo:
            html += h2(titulo) + "".join(cartao(ed, fac, perfil, c) for ed, fac in grupo)
    return html


CONFIRA_DATA = p("Antes de se inscrever, confira sempre as datas no edital oficial: se houver retificação, vale o que a "
                 "faculdade publicar.")


# ---------------------------------------------------------------- confirmação e alerta

def confirmacao(a, site, dias_para_confirmar):
    url = f"{site}/alerta/confirmar/?t={a['token']}"
    corpo = (p("Oi! Aqui é o Cauã, do Transfermed. Para começar a receber os avisos de transferência de Medicina para o seu "
               "perfil, confirme seu e-mail:")
             + botao(url, "Confirmar meus alertas")
             + p("Depois disso, você recebe o checklist de documentos e passa a ser avisado quando abrir um edital conferido "
                 "que combine com você.")
             + p(f"Se não foi você que se cadastrou, é só ignorar: o cadastro é apagado sozinho em {dias_para_confirmar} dias.")
             + ASSINATURA)
    return finalizar(a, site, "Falta um clique para ativar seus alertas", "Falta um clique", corpo)


def assunto_alerta(itens, hoje):
    """Gerado dos dados: "2 editais encerram hoje · 12 abertos para o seu perfil"."""
    if len(itens) == 1:
        ed, fac = itens[0]
        return f"{fac['sigla']} ({fac['cidade']}): {gerar_site.texto_situacao(ed, hoje)[1].lower()}"
    urgentes, abertos, breve = separar(itens, hoje)
    hoje_n = sum(1 for ed, _ in urgentes if dias_para_fim(ed, hoje) == 0)
    partes = []
    if hoje_n:
        partes.append(plural(hoje_n, "edital encerra hoje", "editais encerram hoje"))
    elif urgentes:
        partes.append(plural(len(urgentes), f"edital encerra em até {DIAS_URGENTE} dias", f"editais encerram em até {DIAS_URGENTE} dias"))
    n_abertos = len(urgentes) + len(abertos)
    if n_abertos:
        partes.append(plural(n_abertos, "aberto para o seu perfil", "abertos para o seu perfil"))
    if breve:
        partes.append(plural(len(breve), "abre em breve", "abrem em breve"))
    return " · ".join(partes)


def alerta(a, c, itens):
    """O alerta de editais (o que já existia), no formato novo. itens: [(ed, fac)]."""
    perfil = a.get("perfil") or {}
    corpo = (p(f"Oi! Aqui é o Cauã. {'Encontrei um edital conferido' if len(itens) == 1 else f'Encontrei {len(itens)} editais conferidos'} "
               "que combina" + ("" if len(itens) == 1 else "m") + " com o seu perfil.")
             + blocos(itens, perfil, c) + CONFIRA_DATA
             + p(link(c.site + "/diagnostico/", "Ver tudo no meu diagnóstico"))
             + ASSINATURA)
    return finalizar(a, c.site, assunto_alerta(itens, c.hoje), "Editais para o seu perfil", corpo)


# ---------------------------------------------------------------- sequência

def boas_vindas(a, c, itens=()):
    """Único e-mail depois da confirmação: o checklist e os editais mais urgentes do perfil (no máximo 5)."""
    perfil = a.get("perfil") or {}
    n_dicas, dias_total = len(SEQUENCIA) - 1, SEQUENCIA[-1]
    urgentes = sorted(itens, key=lambda t: t[0].get("inscricao_fim") or "9999")[:MAX_BOAS_VINDAS]
    corpo = (p("Oi! Aqui é o Cauã, do Transfermed. Seu alerta está ativo.")
             + p(f"Aqui está o checklist de documentos para transferência de Medicina, montado com as listas de "
                 f"{c.isca_total} editais conferidos no PDF oficial, com a página de onde saiu cada item.")
             + botao(c.isca_url, "Baixar o checklist (PDF)"))
    if urgentes:
        titulo = (f"Os {len(urgentes)} mais urgentes para o seu perfil" if len(itens) > len(urgentes)
                  else f"Os {len(urgentes)} editais abertos para o seu perfil" if len(urgentes) > 1 else "O edital aberto para o seu perfil")
        corpo += (h2(titulo)
                  + "".join(cartao(ed, fac, perfil, c) for ed, fac in urgentes)
                  + (p(link(c.site + "/diagnostico/", f"Ver todos os {len(itens)} editais para o seu perfil")) if len(itens) > len(urgentes) else "")
                  + CONFIRA_DATA)
    elif perfil.get("curso"):
        corpo += p("Hoje não há edital conferido aberto para o seu perfil. Aviso assim que abrir.")
    corpo += (p("O que vai chegar no seu e-mail daqui para a frente (no máximo um por dia):")
              + lista(["um aviso quando abrir edital conferido para o seu perfil (ou de uma faculdade que você segue);",
                       f"lembretes {LEMBRETE_LONGE} e {LEMBRETE_PERTO} dias antes do fim das inscrições, nos editais em que você pedir;",
                       f"nos próximos {dias_total} dias, {n_dicas} e-mails curtos com o que eu queria ter sabido quando transferi;",
                       "às segundas, um resumo da semana, só quando tiver novidade ou prazo encerrando."]))
    if not perfil.get("curso"):
        corpo += p(f"Você ainda não preencheu o seu perfil, então por enquanto só aviso das faculdades que você segue. "
                   f"{link(c.site + '/diagnostico/', 'Faça o diagnóstico')} para receber todos os editais que servem para você.")
    corpo += p("Se algum e-mail não fizer sentido para você, é só cancelar pelo link no rodapé: apaga tudo na hora.") + ASSINATURA
    assunto = (f"Seu alerta está ativo: checklist e {plural(len(itens), 'edital aberto', 'editais abertos')} para você" if itens
               else "Seu alerta está ativo: checklist de documentos para transferência")
    return assunto, "Seu alerta está ativo", corpo


def dia2(a, c, itens=()):
    if exterior(a.get("perfil")):
        corpo = (p(f"Talvez você já tenha ouvido que voltar do exterior é impossível. Não é: dos {c.total} editais que conferi, "
                   f"{c.aceitam_exterior} aceitaram quem vem de faculdade estrangeira. Mas o caminho tem três partes que quem "
                   "estuda no Brasil não tem:")
                 + lista(["<strong>Achar o edital que aceita o exterior.</strong> Alguns são exclusivos para quem vem de fora; "
                          f"outros não aceitam ({c.nao_aceitam_exterior} dos {c.total} conferidos).",
                          "<strong>Legalizar os documentos.</strong> Histórico, programas e declarações saem no país onde você "
                          "estuda e precisam de apostila (ou visto consular, conforme o edital) e tradução juramentada no Brasil.",
                          f"<strong>Passar na seleção.</strong> Em {c.com_prova} dos {c.total} editais tem prova; nos outros, a "
                          "análise é do histórico."])
                 + p("Apostila no país de origem e tradução juramentada aqui levam tempo e custam. Por isso vale separar os "
                     "documentos antes de o edital abrir.")
                 + p(link(c.site + "/exterior/", "Veja as faculdades que aceitaram quem estuda no exterior"))
                 + ASSINATURA)
        return "Transferência do exterior: as 3 partes do caminho", "Como funciona a transferência do exterior", corpo
    corpo = (p("Transferência externa é quando você sai da sua faculdade de Medicina e entra em outra, aproveitando o que já "
               "cursou. Não existe uma regra única: cada faculdade publica o próprio edital, com vagas, datas e critérios.")
             + p("Na prática, o edital passa por estas etapas:")
             + lista([f"<strong>Inscrição</strong>, quase sempre com taxa. Em metade dos {c.com_janela} editais conferidos com as "
                      f"duas datas, as inscrições ficaram abertas por {c.janela_mediana} dias ou menos; em {c.janela_curta}, por "
                      "menos de uma semana.",
                      f"<strong>Seleção:</strong> em {c.com_prova} dos {c.total} editais que conferi tem prova; nos outros, "
                      "contam a análise do histórico e dos programas.",
                      "<strong>Resultado e matrícula</strong>, com datas próprias no edital: anote essas também.",
                      "<strong>Aproveitamento:</strong> a faculdade compara as suas disciplinas com as dela e decide em que "
                      "semestre você entra."])
             + p("Prova se estuda. Prazo perdido e documento errado não têm conserto: é para isso que servem os alertas e o "
                 "checklist.")
             + p(f"{link(c.site + '/diagnostico/', 'Refaça o diagnóstico')} quando mudar de semestre: os editais mudam com ele.")
             + ASSINATURA)
    return "Como funciona uma transferência de Medicina", "Como funciona uma transferência", corpo


def historia():
    """Os parágrafos da história do dono, tirados do texto da /sobre/ (sem a parte da consultoria)."""
    pars = re.findall(r"<p>(.*?)</p>", gerar_site.SOBRE_TEXTO.split("<h2>")[0], flags=re.S)
    return [x for x in pars if x.startswith(("Hoje estou", "Comecei", "O que mais me marcou"))]


def dia5(a, c, itens=()):
    corpo = (p("Queria te contar por que o Transfermed existe.")
             + "".join(p(x) for x in historia())
             + p("O Transfermed é o que eu queria ter tido: os editais num lugar só, conferidos no PDF oficial, com a página de "
                 "onde saiu cada dado. Nenhuma faculdade paga para aparecer.")
             + p(f"Se você está vivendo esse momento agora, eu sei como é. Se quiser me contar a sua situação ou achou algum erro, "
                 f"{link(c.site + '/contato/', 'me escreva')}: eu leio todas as mensagens.")
             + ASSINATURA)
    return "Por que eu fiz o Transfermed", "Por que o Transfermed existe", corpo


def dia9(a, c, itens=()):
    ext = exterior(a.get("perfil"))
    dicas = []
    recentes = c.exemplos(r"emitido|ultimos 12 meses|a partir do|atualizad|recente", sem_exterior=not ext)
    if recentes:
        dicas.append("<strong>Mandar documento velho.</strong> Vários editais dizem de quando o documento tem que ser: "
                     + "; ".join(recentes) + ".")
    assinatura = c.exemplos(r"assinad|carimbad|certificacao digital|validacao", sem_exterior=not ext)
    if assinatura:
        dicas.append("<strong>Programas e histórico sem assinatura ou carimbo.</strong> " + "; ".join(assinatura) + ".")
    vinculo = c.exemplos(r"(vinculo|matricula).*(20\d\d|semestre)", sem_exterior=not ext)
    if vinculo:
        dicas.append("<strong>Declaração de vínculo do semestre errado.</strong> " + "; ".join(vinculo) + ".")
    enade = c.exemplos(r"enade|enamed", sem_exterior=not ext)
    if enade:
        dicas.append("<strong>Esquecer o ENADE.</strong> " + "; ".join(enade) + ".")
    if ext:
        legal = c.exemplos(r"apostila|consular|traducao juramentada")
        if legal:
            dicas.insert(0, "<strong>Legalizar do jeito errado.</strong> Cada edital diz o que aceita: " + "; ".join(legal) + ".")
        if c.nao_aceitam_exterior:
            dicas.append(f"<strong>Pagar inscrição num edital que não aceita o exterior.</strong> {c.nao_aceitam_exterior} dos "
                         f"{c.total} editais conferidos não aceitam. O diagnóstico já tira esses da sua lista.")
    elif c.excluem_transferidos:
        dicas.append(f"<strong>Não ler as restrições.</strong> {plural(c.excluem_transferidos, 'dos editais conferidos não aceita', 'dos editais conferidos não aceitam')} "
                     "quem já foi transferido uma vez; outros só têm vaga em alguns semestres. O diagnóstico confere isso para você.")
    if c.com_retificacao:
        dicas.append(f"<strong>Não acompanhar as retificações.</strong> {plural(c.com_retificacao, 'dos editais conferidos já teve', 'dos editais conferidos já tiveram')} "
                     "retificação depois de publicado. Quando isso acontece, o edital aparece com aviso no site.")
    corpo = (p("Alguns erros tiram gente da transferência e são fáceis de evitar. Separei os que aparecem nas exigências "
               "dos editais que conferi (cada página leva ao resumo do edital):")
             + lista(dicas)
             + p(f"O {link(c.isca_url, 'checklist em PDF')} tem a lista completa, por tipo de documento.")
             + ASSINATURA)
    assunto = "Erros que dá para evitar na transferência do exterior" if ext else "Erros que dá para evitar na transferência"
    return assunto, "Erros que dá para evitar", corpo


def dia14(a, c, itens=()):
    corpo = (p(f"Faz {SEQUENCIA[-1]} dias que você ativou o alerta. Este é o último e-mail de dicas; depois disso, só chegam "
               "os avisos, os lembretes que você pedir e o resumo de segunda quando houver novidade ou prazo encerrando.")
             + p("Para tirar o máximo do Transfermed:")
             + lista([f"<strong>{link(c.site + '/diagnostico/', 'Diagnóstico')}:</strong> refaça quando mudar de semestre ou de cidade.",
                      "<strong>Minha lista:</strong> salve os editais que interessam (a estrela em cada edital) e veja todos num lugar.",
                      "<strong>Agenda:</strong> em cada edital, \"Adicionar à agenda\" coloca as datas no seu calendário.",
                      "<strong>Seguir uma faculdade:</strong> na página dela, \"Avise-me quando abrir\" manda e-mail no próximo edital.",
                      "<strong>Checklist do edital:</strong> marque os documentos que já separou; fica salvo no seu navegador."])
             + p("E se você conhece alguém que também quer transferir, mande o link. É grátis para todo mundo:")
             + botao(f"{c.site}/?origem=indicacao", "transfermed.com.br")
             + ASSINATURA)
    return "Como tirar o máximo do Transfermed (e indicar a um colega)", "Como tirar o máximo do Transfermed", corpo


PASSOS = {0: boas_vindas, 2: dia2, 5: dia5, 9: dia9, 14: dia14}


def passo_devido(a, hoje, ja):
    """O passo da sequência que vence hoje, ou None. Só para quem aceitou o consentimento novo e confirmou o e-mail;
    um passo atrasado mais de JANELA_DIAS é pulado (nunca chega "boas-vindas" semanas depois)."""
    if MARCA_CONSENTIMENTO not in (a.get("consentimento_texto") or "") or not a.get("confirmado_em"):
        return None
    dias = (date.fromisoformat(hoje) - date.fromisoformat(a["confirmado_em"][:10])).days
    for d in SEQUENCIA:
        if f"seq:{d}" not in ja and d <= dias < d + JANELA_DIAS:
            return d
    return None


# ---------------------------------------------------------------- lembretes e resumo

def lembretes_devidos(a, c, ja):
    """[(tipo, dias que faltam, edital, faculdade)] dos editais que a pessoa pediu para lembrar, o mais urgente primeiro.
    Longe: entre 3 e 7 dias do fim; perto: entre 0 e 2. Prazo final a conferir não gera lembrete (a data pode estar errada)."""
    pedidos = ((a.get("perfil") or {}).get("seguir") or {}).get("lembretes") or []
    saida = []
    for ed in c.E:
        if ed["id"] not in pedidos or gerar_site.fora_dos_emails(ed) or not ed.get("inscricao_fim") or ed.get("fluxo_continuo"):
            continue
        falta = dias_para_fim(ed, c.hoje)
        if 0 <= falta <= LEMBRETE_PERTO and f"lembrete{LEMBRETE_PERTO}:{ed['id']}" not in ja:
            saida.append((LEMBRETE_PERTO, falta, ed, c.F[ed["faculdade_id"]]))
        elif LEMBRETE_PERTO < falta <= LEMBRETE_LONGE and f"lembrete{LEMBRETE_LONGE}:{ed['id']}" not in ja:
            saida.append((LEMBRETE_LONGE, falta, ed, c.F[ed["faculdade_id"]]))
    return sorted(saida, key=lambda t: t[1])


def pagina_do_pdf(ed, campo):
    pag = (ed.get("evidencias") or {}).get(campo)
    return f" (edital, p. {pag})" if isinstance(pag, int) else ""


def lembrete(a, c, tipo, falta, ed, fac):
    nome_mod = MODALIDADES.get(ed.get("modalidade"), MODALIDADES["externa"])[0]
    quando = "hoje" if falta == 0 else ("amanhã" if falta == 1 else f"em {falta} dias")
    docs = ed.get("documentos") or []
    perto = tipo == LEMBRETE_PERTO
    checklist = c.pagina(ed) + ("#checklist" if docs else "")
    corpo = (p(f"Oi! Aqui é o Cauã. As inscrições de <strong>{escape(nome_mod.lower())} da {escape(fac['sigla'])}</strong> "
               f"({escape(fac['cidade'])}/{escape(fac['uf'])}) encerram <strong>{quando}</strong>, em "
               f"{fmt(ed['inscricao_fim'])}{pagina_do_pdf(ed, 'inscricao_fim')}.")
             + (p("Documentos que este edital pede:") + lista([escape(d) for d in docs]) if docs and not perto else "")
             + (p(f"{link(checklist, 'Abra o checklist deste edital')} e marque o que já separou."
                  if docs else f"{link(checklist, 'Veja o resumo deste edital')} antes de enviar.")
                + p("Confira também o horário limite no edital: muitas inscrições fecham num horário específico do último dia.")
                if perto else "")
             + botao(c.pagina(ed), "Ver o resumo e o edital")
             + p(f"Você pediu este lembrete no site. Confira sempre a data no {link(ed['url_edital'], 'edital oficial')}: "
                 "se houver retificação, vale o que a faculdade publicar.")
             + ASSINATURA)
    assunto = (f"Últimos dias: as inscrições da {fac['sigla']} encerram {quando}" if perto
               else f"Faltam {falta} dias para o fim das inscrições da {fac['sigla']}")
    return assunto, f"Prazo da {fac['sigla']} encerra {quando}", corpo


def resumo_devido(a, c, agora_utc, ja):
    """Segunda-feira a partir das 8h de Brasília (11h UTC), uma vez por semana."""
    return agora_utc.weekday() == 0 and agora_utc.hour >= 11 and f"resumo:{c.hoje}" not in ja


def resumo_semanal(a, c, compativeis):
    """compativeis: [(edital, faculdade)] vivos e compatíveis com o perfil ou com as faculdades seguidas.
    Grupos, sem repetir edital: novos esta semana (conferidos nos últimos 7 dias e depois da inscrição),
    encerram nos próximos 7 dias, continuam abertos e abrem em breve. Sem novos nem prazo encerrando, não há resumo."""
    hoje = date.fromisoformat(c.hoje)
    desde = max((hoje - timedelta(days=7)).isoformat(), (a.get("confirmado_em") or "")[:10])
    novos = [(ed, f) for ed, f in compativeis if (ed.get("conferido_em") or "") >= desde]
    ids = {ed["id"] for ed, _ in novos}
    resto = [(ed, f) for ed, f in compativeis if ed["id"] not in ids]
    urgentes, continuam, breve = separar(resto, c.hoje)
    if not novos and not urgentes:
        return None
    perfil = a.get("perfil") or {}
    corpo = p("Oi! Aqui é o Cauã. O resumo da semana para o seu perfil:")
    for titulo, grupo in (("Novos esta semana", novos), (f"Encerram nos próximos {DIAS_URGENTE} dias", urgentes),
                          ("Continuam abertos", continuam), ("Abrem em breve", breve)):
        if grupo:
            corpo += h2(titulo) + "".join(cartao(ed, fac, perfil, c) for ed, fac in sorted(grupo, key=lambda t: t[0].get("inscricao_fim") or "9999"))
    corpo += CONFIRA_DATA + p(link(c.site + "/diagnostico/", "Ver tudo no meu diagnóstico")) + ASSINATURA
    partes = []
    if novos:
        partes.append(plural(len(novos), "edital novo", "editais novos"))
    if urgentes:
        partes.append(plural(len(urgentes), f"encerra nos próximos {DIAS_URGENTE} dias", f"encerram nos próximos {DIAS_URGENTE} dias"))
    if continuam:
        partes.append(plural(len(continuam), "continua aberto", "continuam abertos"))
    if breve:
        partes.append(plural(len(breve), "abre em breve", "abrem em breve"))
    return "Resumo da semana: " + " · ".join(partes), "Resumo da semana", corpo
