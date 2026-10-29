"""
E-mails novos do alerta: boas-vindas com o checklist, sequência de dicas (dias 2, 5, 9 e 14), lembretes de prazo
(7 e 2 dias antes) e resumo semanal. Quem envia é o `alertas.py`; enquanto a variável ALERTAS_ATIVOS não existir,
tudo isto roda em simulação (gera os e-mails, não envia e não registra nada no banco).

Regra dos dados: todo número e exemplo vem dos editais conferidos (`data/editais.json`), com a página do PDF.
Nada de "costuma": se não há exemplo transcrito, a dica não entra.
"""
import re
import unicodedata
from datetime import date, timedelta
from html import escape

import gerar_site
import isca
from gerar_site import MODALIDADES, fmt, publicavel, slug_edital

# só recebe a sequência de dicas e o resumo quem aceitou o texto de consentimento que fala deles
MARCA_CONSENTIMENTO = "dicas sobre transferência"
SEQUENCIA = (0, 2, 5, 9, 14)   # dias depois da confirmação
JANELA_DIAS = 3                # se o robô atrasar, ainda envia até 3 dias depois; mais que isso, pula
ASSINATURA = '<p>Um abraço,<br>Cauã, do Transfermed</p>'
VERDE = "#17694F"


def norm(s):
    return unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()


def p(texto):
    return f"<p>{texto}</p>"


def link(url, texto):
    return f'<a href="{escape(url)}" style="color:{VERDE}">{escape(texto)}</a>'


def botao(url, texto):
    return (f'<p><a href="{escape(url)}" style="display:inline-block;background:#0F5C4D;color:#FFFFFF;text-decoration:none;'
            f'padding:12px 20px;border-radius:10px;font-weight:bold">{escape(texto)}</a></p>')


def lista(itens):
    return "<ul>" + "".join(f"<li style=\"margin:0 0 8px\">{i}</li>" for i in itens) + "</ul>"


def texto_puro(html):
    """Versão em texto do e-mail (para quem lê sem HTML): tira as tags e mantém os links."""
    t = re.sub(r'<a href="([^"]+)"[^>]*>(.*?)</a>', r"\2 (\1)", html)
    t = re.sub(r"<li[^>]*>", "- ", t)
    t = re.sub(r"</(p|li|ul|h2)>|<br>", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\n{3,}", "\n\n", t.replace("&amp;", "&")).strip()


class Contexto:
    """Dados que os e-mails citam, calculados uma vez por rodada a partir dos editais conferidos."""

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

    def exemplos(self, rx, n=3, sem_exterior=False):
        """Até n itens de documentos transcritos que batem com a expressão, cada um com a faculdade e a página
        (uma vez por faculdade; sem_exterior deixa de fora os editais só para quem vem de fora)."""
        achados, vistos = [], set()
        for b in isca.editais_com_lista(self.E, self.F):
            ed = b["ed"]
            sigla = " / ".join(dict.fromkeys(b["siglas"]))
            if sem_exterior and ed.get("modalidade") == "exterior":
                continue
            for doc in ed["documentos"]:
                if re.search(rx, norm(doc)) and sigla not in vistos:
                    vistos.add(sigla)
                    url = f"{self.site}/edital/{slug_edital(ed)}/"
                    achados.append(f"{escape(sigla)}: “{escape(doc)}” ({link(url, b['pagina'] or 'ver edital')})")
                    break
            if len(achados) >= n:
                break
        return achados


def exterior(perfil):
    return (perfil or {}).get("origem") == "exterior"


# ---------------------------------------------------------------- sequência

def boas_vindas(a, c):
    perfil = a.get("perfil") or {}
    sem_perfil = not perfil.get("curso")
    corpo = (p("Oi! Aqui é o Cauã, do Transfermed. Seu alerta está ativo.")
             + p(f"Como prometido, aqui está o checklist de documentos para transferência de Medicina. Ele foi montado com "
                 f"as listas de {c.isca_total} editais conferidos no PDF oficial, com a página de onde saiu cada item.")
             + botao(c.isca_url, "Baixar o checklist (PDF)")
             + p("O que vai chegar no seu e-mail daqui para a frente:")
             + lista(["um aviso quando abrir edital conferido para o seu perfil (ou de uma faculdade que você segue);",
                      "lembretes 7 e 2 dias antes do fim das inscrições, nos editais em que você pedir;",
                      "nas próximas duas semanas, 4 e-mails curtos com o que eu queria ter sabido quando transferi;",
                      "às segundas, um resumo da semana, só quando tiver novidade para você."])
             + (p(f"Você ainda não preencheu o seu perfil, então por enquanto só aviso das faculdades que você segue. "
                  f"{link(c.site + '/diagnostico/', 'Faça o diagnóstico (1 minuto)')} para receber todos os editais que servem para você.")
                if sem_perfil else "")
             + p("Se algum e-mail não fizer sentido para você, é só cancelar pelo link no rodapé: apaga tudo na hora.")
             + ASSINATURA)
    return "Seu checklist de documentos para transferência", "Seu alerta está ativo", corpo


def dia2(a, c):
    if exterior(a.get("perfil")):
        corpo = (p("Talvez você já tenha ouvido que voltar do exterior é impossível. Não é: dos "
                   f"{c.total} editais que conferi, {c.aceitam_exterior} aceitaram quem vem de faculdade estrangeira. "
                   "Mas o caminho tem três partes que quem estuda no Brasil não tem:")
                 + lista(["<strong>Achar o edital que aceita o exterior.</strong> Alguns são exclusivos para quem vem de fora; "
                          f"outros não aceitam ({c.nao_aceitam_exterior} dos {c.total} conferidos).",
                          "<strong>Legalizar os documentos.</strong> Histórico, programas e declarações saem no país onde você "
                          "estuda e precisam de apostila (ou visto consular, conforme o edital) e tradução juramentada no Brasil.",
                          "<strong>Passar na seleção.</strong> "
                          f"Em {c.com_prova} dos {c.total} editais tem prova; nos outros, a análise é do histórico."])
                 + p("Apostila no país de origem e tradução juramentada aqui levam tempo e custam. Por isso vale separar os "
                     "documentos antes de o edital abrir.")
                 + p(f"{link(c.site + '/exterior/', 'Veja as faculdades que aceitaram quem estuda no exterior')}.")
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


def dia5(a, c):
    corpo = (p("Hoje eu queria contar por que o Transfermed existe.")
             + p("Comecei a faculdade no Paraguai. No meu primeiro ano de curso, perdi meu pai. Foi o período mais difícil da "
                 "minha vida, e mesmo assim eu decidi seguir em frente. Continuei estudando e consegui transferir meu curso para "
                 "o Brasil. Hoje estou no 7º período de Medicina na Universidade Brasil, em Fernandópolis (SP).")
             + p("O que mais me marcou na transferência foi a sensação de estar perdido: editais espalhados em sites diferentes, "
                 "prazos curtos, regras confusas e pouca gente para explicar.")
             + p("O Transfermed é o que eu queria ter tido: os editais num lugar só, conferidos no PDF oficial, com a página de "
                 "onde saiu cada dado. Nenhuma faculdade paga para aparecer.")
             + p(f"Se você está vivendo esse momento agora, eu sei como é. Se quiser me contar a sua situação ou achou algum erro, "
                 f"{link(c.site + '/contato/', 'me escreva')}: eu leio todas as mensagens.")
             + ASSINATURA)
    return "Por que eu fiz o Transfermed", "Por que o Transfermed existe", corpo


def dia9(a, c):
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
        dicas.append(f"<strong>Não ler as restrições.</strong> {c.excluem_transferidos} dos editais conferidos não aceitam quem "
                     "já foi transferido uma vez; outros só têm vaga em alguns semestres. O diagnóstico confere isso para você.")
    if c.com_retificacao:
        dicas.append(f"<strong>Não acompanhar as retificações.</strong> {c.com_retificacao} dos editais conferidos já tiveram "
                     "retificação depois de publicados. Quando isso acontece, o edital aparece com aviso no site.")
    corpo = (p("Alguns erros tiram gente da transferência e são fáceis de evitar. Separei os que aparecem nas exigências "
               "dos editais que conferi (o link leva à página do edital):")
             + lista(dicas)
             + p(f"O {link(c.isca_url, 'checklist em PDF')} tem a lista completa, por tipo de documento.")
             + ASSINATURA)
    assunto = "Erros que dá para evitar na transferência do exterior" if ext else "Erros que dá para evitar na transferência"
    return assunto, "Erros que dá para evitar", corpo


def dia14(a, c):
    corpo = (p("Faz duas semanas que você ativou o alerta. Este é o último e-mail de dicas; depois disso, só chegam os avisos, "
               "os lembretes que você pedir e o resumo de segunda quando houver novidade.")
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
    """[(dias, edital, faculdade)] dos editais que a pessoa pediu para lembrar. 7 dias: entre 3 e 7 dias do fim;
    2 dias: entre 0 e 2. Edital "conferir" não gera lembrete (a data pode estar errada)."""
    pedidos = ((a.get("perfil") or {}).get("seguir") or {}).get("lembretes") or []
    saida = []
    for ed in c.E:
        if ed["id"] not in pedidos or ed.get("status") == "conferir" or not ed.get("inscricao_fim") or ed.get("fluxo_continuo"):
            continue
        falta = (date.fromisoformat(ed["inscricao_fim"]) - date.fromisoformat(c.hoje)).days
        if 0 <= falta <= 2 and f"lembrete2:{ed['id']}" not in ja:
            saida.append((2, falta, ed, c.F[ed["faculdade_id"]]))
        elif 2 < falta <= 7 and f"lembrete7:{ed['id']}" not in ja:
            saida.append((7, falta, ed, c.F[ed["faculdade_id"]]))
    return saida


def pagina_do_pdf(ed, campo):
    pag = (ed.get("evidencias") or {}).get(campo)
    return f" (edital, p. {pag})" if isinstance(pag, int) else ""


def lembrete(a, c, tipo, falta, ed, fac):
    nome_mod = MODALIDADES.get(ed.get("modalidade"), MODALIDADES["externa"])[0]
    quando = "hoje" if falta == 0 else ("amanhã" if falta == 1 else f"em {falta} dias")
    pagina = f"{c.site}/edital/{slug_edital(ed)}/"
    docs = ed.get("documentos") or []
    corpo = (p(f"As inscrições de <strong>{escape(nome_mod.lower())} da {escape(fac['sigla'])}</strong> ({escape(fac['cidade'])}/{escape(fac['uf'])}) "
               f"encerram <strong>{quando}</strong>, em {fmt(ed['inscricao_fim'])}{pagina_do_pdf(ed, 'inscricao_fim')}.")
             + (p("Documentos que este edital pede:") + lista([escape(d) for d in docs]) if docs and tipo == 7 else "")
             + botao(pagina, "Ver o resumo e o edital")
             + p(f"Você pediu este lembrete no site. Confira sempre a data no {link(ed['url_edital'], 'edital oficial')}: "
                 "se houver retificação, vale o que a faculdade publicar.")
             + ASSINATURA)
    assunto = (f"Últimos dias: as inscrições da {fac['sigla']} encerram {quando}" if tipo == 2
               else f"Faltam {falta} dias para o fim das inscrições da {fac['sigla']}")
    return assunto, f"Prazo da {fac['sigla']} encerra {quando}", corpo


def resumo_devido(a, c, agora_utc, ja):
    """Segunda-feira a partir das 8h de Brasília (11h UTC), uma vez por semana."""
    return agora_utc.weekday() == 0 and agora_utc.hour >= 11 and f"resumo:{c.hoje}" not in ja


def resumo_semanal(a, c, compativeis):
    """compativeis: [(edital, faculdade)] vivos e compatíveis com o perfil ou com as faculdades seguidas.
    Só há resumo se algum foi conferido nos últimos 7 dias e depois da inscrição da pessoa (novidade de verdade);
    os que encerram na semana entram junto, sem repetir edital."""
    hoje = date.fromisoformat(c.hoje)
    desde = max((hoje - timedelta(days=7)).isoformat(), (a.get("confirmado_em") or "")[:10])
    novos = [(ed, f) for ed, f in compativeis if (ed.get("conferido_em") or "") >= desde]
    if not novos:
        return None
    ids = {ed["id"] for ed, _ in novos}
    prazos = [(ed, f) for ed, f in compativeis if ed["id"] not in ids and ed.get("inscricao_fim")
              and 0 <= (date.fromisoformat(ed["inscricao_fim"]) - hoje).days <= 7]

    def item(ed, f):
        _, txt = gerar_site.texto_situacao(ed, c.hoje)
        return f"{link(c.site + '/edital/' + slug_edital(ed) + '/', f['sigla'] + ' (' + f['cidade'] + '/' + f['uf'] + ')')}: {escape(txt.lower())}"

    corpo = (p("O resumo da semana para o seu perfil:")
             + f"<h2 style=\"font-size:16px;margin:16px 0 4px\">Novos ou atualizados</h2>" + lista([item(*x) for x in novos])
             + (f"<h2 style=\"font-size:16px;margin:16px 0 4px\">Encerram nos próximos 7 dias</h2>" + lista([item(*x) for x in prazos]) if prazos else "")
             + p(f"{link(c.site + '/diagnostico/', 'Ver o meu diagnóstico completo')}")
             + ASSINATURA)
    n = len(novos)
    return (f"Resumo da semana: {n} {'edital novo' if n == 1 else 'editais novos'} para você", "Resumo da semana", corpo)
