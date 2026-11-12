"""Pautas curadas do Instagram nos 7 pilares do banco de pautas (11/11/2026).

Calendário (o dia da semana decide o pilar; segunda continua sendo o carrossel de editais abertos que o robô monta da base):
  segunda  editais abertos (instagram_dia.post_abertos)   terça    armadilha do edital        quarta   como funciona o processo
  quinta   curiosidade de faculdade                       sexta    números do Raio-X          sábado   mito ou fato
  domingo  quem estuda no exterior

Cada pauta é um fato lido no PDF, com a página, e conferido AGORA contra a base: se o dado do edital mudar (taxa, vagas, status), a pauta
levanta PautaInvalida e o dia fica sem post em vez de sair com número velho. Nada vai ao Instagram daqui: os arquivos vão para docs/social
(com "curado": true, que o robô semanal respeita como o "revisado": true do dono) e para o pacote de revisão em privado/instagram/semana-AAAA-MM-DD/.

uso: python instagram_pilares.py --semana 2026-11-16 [--saida privado/instagram]
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import instagram_checagem as ck
import instagram_dia as dia

BOTAO = dia.BOTAO_ALERTA
RODAPE = "Confira sempre o edital oficial."


class PautaInvalida(Exception):
    """A base já não sustenta o fato da pauta: o dia fica sem post."""


def _edital(editais, id_):
    e = next((x for x in editais if x["id"] == id_), None)
    if e is None:
        raise PautaInvalida(f"edital {id_} não existe na base")
    return e


def _exige(cond, msg):
    if not cond:
        raise PautaInvalida(msg)


def _vagas(e):
    return [(v["semestre"], v["vagas"]) for v in e.get("vagas") or []]


def _cartao(nome, detalhe, destaque, fonte):
    return {"nome": nome, "detalhe": detalhe, "prazo": destaque, "fonte": fonte}


def _capa(kicker, titulo, apoio, fonte="", botao="Arraste e veja →", cor="agua"):
    t = {"tipo": "capa", "cor": cor, "kicker": kicker, "titulo": titulo, "apoio": apoio, "botao": botao}
    if fonte:
        t["fonte"] = fonte
    return t


def _fatos(facs, itens):
    """itens: [(edital, sigla, campo, página única)] -> `fatos` do post.json (uma página por fato)."""
    return [{"faculdade": s, "edital": e["id"], "campo": c, "pagina": p} for e, s, c, p in itens]


def _montar(tipo, telas, corpo, siglas, lista, fontes, itens, facs, gancho):
    r = dia._resultado(tipo, telas, dia._legenda(corpo, siglas, lista), fontes, [(e, c) for e, _, c, _ in itens], facs, gancho)
    r["fatos"] = _fatos(facs, itens)
    return r


# ---------------------------------------------------------------- terça: armadilha (BANCO #6)

def pauta_armadilha_fpp(editais, facs, hoje):
    e = _edital(editais, "528d5ef7e915")
    _exige(e["status"] == "ok" and e["inscricao_fim"] == "2026-12-01" and e["situacao"] == "aberto", "FPP: o edital mudou (status, prazo ou situação)")
    gancho = "FPP exige o período na declaração, até 01/12"
    tela = {"tipo": "armadilha", "kicker": "Armadilha do edital", "titulo": gancho,
            "cartao": {"linha": "FPP · Curitiba (PR) · Medicina 2027.1", "destaque": "A declaração da faculdade de origem precisa indicar o período em curso.",
                       "destaque2": "Pré-inscrição até 01/12, às 16h.",
                       "apoio": "Sem o período expresso, a FPP analisa se a declaração vale.",
                       "fonte": "edital, p. 4, item 2.3.2 · prazo p. 2, item 1.9, a"},
            "botao": BOTAO, "rodape": RODAPE}
    corpo = ("Na FPP (Curitiba/PR), a pré-inscrição para a transferência de Medicina 2027.1 pede uma declaração da faculdade de origem com o vínculo ativo "
             "e o período em curso indicado de forma clara (edital 025/2026, p. 4, item 2.3.2). Sem a indicação expressa do período, a validade da declaração "
             "é analisada pela FPP (p. 4, item 2.5). A pré-inscrição vai até as 16h de 01/12/2026 (p. 2, item 1.9, a).\n\n"
             "Peça a declaração com antecedência e leia o edital inteiro antes de se inscrever.")
    fontes = ["- FPP (Curitiba/PR): `528d5ef7e915`, edital 025/2026 (https://fpp.edu.br/wp-content/uploads/2026/10/EDITAL-DE-TRANSFERENCIA-DE-MEDICINA-1-SEMESTRE-DE-2027_MED.pdf)",
              "  - declaração com vínculo e período em curso: p. 4, item 2.3.2 (validade analisada pela FPP se faltar o período: p. 4, item 2.5)",
              "  - pré-inscrição até as 16h00 de 01/12/2026: p. 2, item 1.9, a (confere com o item 2.1, p. 3)"]
    return _montar("armadilha-do-edital", [tela], corpo, ["FPP"], [], fontes,
                   [(e, "FPP", "documentos", "4"), (e, "FPP", "inscricao_fim", "2")], facs, gancho) | {"pauta": "BANCO #6"}


# ---------------------------------------------------------------- quarta: como funciona (BANCO #10, com o quadro de vagas da São Camilo)

def pauta_processo_periodo(editais, facs, hoje):
    """Edital 054/2026 da São Camilo (já encerrado): o quadro de vagas por semestre, p. 1, itens 2.1 a 2.3 (lido no PDF em 12/11/2026).
    Só os campos vagas e quadro entram no post: o semestre de ingresso do edital é contraditório (título x item 1.3) e não é citado."""
    e = _edital(editais, "24163eeabba8")
    _exige(_vagas(e) == [("3º", 3), ("4º", 4)] and e["situacao"] == "encerrado" and "vagas" not in (e.get("conferir_campos") or {}), "São Camilo 054/2026: o quadro de vagas ou a situação mudou")
    sigla = facs[e["faculdade_id"]]["sigla"]
    gancho = "3 vagas no 3º semestre, 4 no 4º"
    telas = [
        _capa("Como funciona o processo", gancho, "No edital 054/2026 da São Camilo (São Paulo/SP), as vagas vêm listadas por semestre. Esse edital já foi encerrado e serve de exemplo.",
              "Fonte: São Camilo, edital 054/2026, p. 1, item 2.1"),
        {"tipo": "cartoes", "cor": "agua", "kicker": "Quadro de vagas do edital 054/2026", "cartoes": [
            _cartao("3º semestre", "Vagas remanescentes de Medicina", "3 vagas", "edital, p. 1, item 2.1"),
            _cartao("4º semestre", "Vagas remanescentes de Medicina", "4 vagas", "edital, p. 1, item 2.1"),
            _cartao("Total do edital", "Vagas remanescentes no curso de Medicina", "7 vagas", "edital, p. 1, item 2.1")]},
        {"tipo": "cartoes", "cor": "agua", "kicker": "Outras regras do mesmo item das vagas", "cartoes": [
            _cartao("O número pode crescer", "Podem ser acrescidas vagas se surgirem desistências até a publicação dos resultados da Terceira Fase", "Item 2.2", "edital, p. 1"),
            _cartao("Alunos do Prouni", "Não há vagas de transferência para alunos provenientes do Prouni", "Item 2.3", "edital, p. 1")]},
        dia._chamada("Em que semestre você está?", "Cada edital abre vagas por semestre ou período. O alerta grátis avisa quando um edital abrir, e o diagnóstico mostra quais combinam com o seu."),
    ]
    corpo = ("Na transferência, as vagas são listadas por semestre. No edital 054/2026 da São Camilo (São Paulo/SP) eram 7 vagas remanescentes: 3 no 3º semestre e 4 no 4º (p. 1, item 2.1). "
             "O número podia crescer se surgissem desistências até a publicação dos resultados da Terceira Fase (p. 1, item 2.2). Esse edital já foi encerrado: serve de exemplo de como o quadro aparece.\n\n"
             "Salve este post para a época da inscrição e envie para quem estuda com você.")
    fontes = [f"- São Camilo (São Paulo/SP): `{e['id']}`, edital 054/2026 ({e['url_edital']})",
              "  - quadro de vagas: 3º semestre 03, 4º semestre 04, total 07 vagas remanescentes: p. 1, item 2.1",
              "  - vagas podem ser acrescidas por desistências até os resultados da Terceira Fase: p. 1, item 2.2; sem vagas para alunos do Prouni: p. 1, item 2.3",
              "  - edital encerrado: inscrições de 02/07/2026 a 12/07/2026, p. 2, item 3.2 (o semestre de ingresso do edital é contraditório e não é citado no post)"]
    return _montar("como-funciona-periodo", telas, corpo, [sigla], [], fontes, [(e, sigla, "vagas", "1")], facs, gancho) | {"pauta": "BANCO #10 (São Camilo)"}


# ---------------------------------------------------------------- quinta: curiosidade (BANCO #3, UNIFACCAMP)

def pauta_curiosidade_unifaccamp(editais, facs, hoje):
    e = _edital(editais, "098f92b0cc9a")
    _exige(e["status"] == "ok" and e["situacao"] == "aberto" and e["inscricao_fim"] == "2027-03-12" and "ordem de envio" in e["criterio_selecao"]
           and not (e.get("conferir_campos") or {}), "UNIFACCAMP: o critério, o prazo ou o status mudou")
    sigla = facs[e["faculdade_id"]]["sigla"]
    gancho = "UNIFACCAMP: vaga por ordem de envio até 12/03/2027"
    telas = [
        _capa("Curiosidade do edital", gancho, "No edital 2027.1 de transferência externa em Medicina, o critério para preencher as vagas é a ordem de envio da documentação.",
              "Fonte: UNIFACCAMP, edital 2027.1, p. 2, item 2.3"),
        {"tipo": "cartoes", "cor": "agua", "kicker": "O que o edital da UNIFACCAMP diz", "cartoes": [
            _cartao("Critério das vagas", "A ordem de envio da documentação para análise", "Ordem de envio", "edital, p. 2, item 2.3"),
            _cartao("Documentos anexados na inscrição", "Declaração de matrícula, histórico escolar e programas das disciplinas", "3 documentos", "edital, p. 2, itens 2.1 e 2.2"),
            _cartao("Período das solicitações", "Campo Limpo Paulista (SP), transferência externa 2027.1", "28/09/2026 a 12/03/2027", "edital, p. 1, item 1.3")]},
        dia._chamada("Vai se inscrever em mais de um edital?", "Cada edital tem critério, prazo e documentos próprios. O alerta grátis avisa antes de cada prazo."),
    ]
    corpo = ("Na UNIFACCAMP (Campo Limpo Paulista/SP), o critério para preencher as vagas da transferência externa 2027.1 é a ordem de envio da documentação para análise (edital, p. 2, item 2.3). "
             "Os documentos são anexados na própria inscrição: declaração de matrícula, histórico escolar e programas das disciplinas (p. 2, itens 2.1 e 2.2). "
             "As solicitações vão de 28/09/2026 a 12/03/2027 (p. 1, item 1.3).\n\n"
             "Se pretende se inscrever, deixe os documentos prontos antes de abrir o formulário.")
    fontes = [f"- UNIFACCAMP (Campo Limpo Paulista/SP): `{e['id']}`, edital 2027.1 ({e['url_edital']})",
              "  - critério: ordem de envio da documentação para análise: p. 2, item 2.3",
              "  - documentos (declaração de matrícula, histórico, programas das disciplinas), anexados na inscrição: p. 2, itens 2.1 e 2.2",
              "  - período das solicitações, 28/09/2026 a 12/03/2027: p. 1, item 1.3"]
    return _montar("curiosidade-de-faculdade", telas, corpo, [sigla], [], fontes,
                   [(e, sigla, "criterio_selecao", "2"), (e, sigla, "documentos", "2"), (e, sigla, "inscricao_fim", "1")], facs, gancho) | {"pauta": "BANCO #3 (UNIFACCAMP)"}


# ---------------------------------------------------------------- sexta: números (BANCO #1)

def pauta_numeros_unicamp(editais, facs, hoje):
    e = _edital(editais, "d0e8257830c7")
    _exige(e["faculdade_id"] == "unicamp" and e["situacao"] == "encerrado", "UNICAMP: o edital mudou")
    gancho = "246 candidatos para 2 vagas em Medicina"
    fonte = "Comvest, Vagas Remanescentes 2027, p. 1"
    telas = [
        _capa("Números do Raio-X", gancho, "Unicamp, vagas remanescentes 2027, Medicina (Integral): 123 candidatos para cada vaga. O processo já passou.", f"Fonte: {fonte}"),
        {"tipo": "cartoes", "cor": "agua", "kicker": "O que o documento da Comvest mostra", "cartoes": [
            _cartao("Candidatos", "Medicina (Integral), vagas remanescentes 2027", "246", fonte),
            _cartao("Vagas", "Medicina (Integral), vagas remanescentes 2027", "2", fonte),
            _cartao("Relação candidatos por vaga", "Medicina (Integral), vagas remanescentes 2027", "123", fonte)]},
        {"tipo": "cartoes", "cor": "agua", "kicker": "Quem entra nessa lista", "cartoes": [
            _cartao("Alunos da Unicamp em outro curso", "Remanescentes 2027, Segmento I", "Segmento I", "Comvest, p. 2"),
            _cartao("Alunos de outras faculdades, do Brasil ou do exterior", "Remanescentes 2027, Segmento II", "Segmento II", "Comvest, p. 2"),
            _cartao("Portadores de diploma de outro curso", "Remanescentes 2027, Segmento III", "Segmento III", "Comvest, p. 2")]},
        dia._chamada("Quer ver os números da sua faculdade?", "O Raio-X mostra vagas e classificados quando a faculdade publica. O alerta grátis avisa quando abrir um edital."),
    ]
    corpo = ("Na Unicamp, a relação de vagas remanescentes 2027 para Medicina (Integral) traz 246 candidatos para 2 vagas, ou 123 candidatos por vaga (documento da Comvest, p. 1). "
             "A lista reúne alunos da Unicamp em outro curso, alunos de outras faculdades (do Brasil ou do exterior) e portadores de diploma (segmentos I, II e III, p. 2). "
             "O processo de 2027 já passou: o número mostra como a procura pode ser alta.\n\n"
             "Envie para quem estuda com você.")
    fontes = ["- UNICAMP (Campinas/SP): `d0e8257830c7`, Raio-X (data/resultados.json), conferido de novo no PDF em 11/11/2026",
              "  - Medicina (Integral): 246 candidatos, 2 vagas, relação 123: p. 1 de https://www.comvest.unicamp.br/wp-content/uploads/2026/09/VR27-RelacaoCVatualizado.pdf",
              "  - segmentos I, II e III (quem entra na lista): p. 2 do mesmo documento",
              "  - o campo vagas do edital segue em conferir (semestre da vaga); este post usa só o documento da Comvest"]
    return _montar("numeros-do-raio-x", telas, corpo, ["UNICAMP"], [], fontes,
                   [(e, "UNICAMP", "raio_x_vagas", "1"), (e, "UNICAMP", "raio_x_segmentos", "2")], facs, gancho) | {"pauta": "BANCO #1"}


# ---------------------------------------------------------------- sábado: mito ou fato (BANCO #11, "Só entra quem tem nota alta?")

def pauta_mito_prova(editais, facs, hoje):
    """Três editais abertos, três jeitos de selecionar: FPP (nota de corte, p. 9), UniUBE (pontos por fase, p. 4) e UVA (documentação, p. 4); lidos nos PDFs."""
    fpp, uni, uva = _edital(editais, "528d5ef7e915"), _edital(editais, "2a698cddcbf7"), _edital(editais, "1e0e3121b570")
    _exige(all(x["status"] == "ok" and x["situacao"] == "aberto" for x in (fpp, uni, uva)) and "nota de corte 5,0" in fpp["criterio_selecao"]
           and "prova escrita (60 pts)" in uni["criterio_selecao"] and "entrevista (30 pts)" in uni["criterio_selecao"]
           and "deferimento" in uva["criterio_selecao"], "FPP/UniUBE/UVA: o critério de seleção mudou")
    gancho = "Nota alta decide nestes 3 editais?"
    telas = [
        _capa("Mito ou fato: só entra quem tem nota alta?", gancho, "Três editais abertos, três jeitos de selecionar. Arraste para ver o que cada um prevê e qual é a resposta.", cor="ambar"),
        {"tipo": "cartoes", "cor": "ambar", "kicker": "O que dizem três editais abertos", "cartoes": [
            _cartao("FPP · Curitiba (PR)", "A classificação segue as notas, em ordem decrescente, e há nota de corte", "Nota de corte 5,0", "edital, p. 9, item 6.3"),
            _cartao("Uniube · Uberaba (MG)", "Dos 100 pontos, a prova escrita vale 60 e a entrevista, 30", "60 + 30 pontos", "edital, p. 4"),
            _cartao("UVA · Rio de Janeiro (RJ)", "O resultado é imediato ao deferimento da documentação", "Documentação", "edital, p. 4, item 7.1")]},
        _capa("Resposta: mito", "Depende do edital", "Na FPP e na Uniube a nota pesa. No edital da UVA, o resultado sai com o deferimento da documentação, e a ordem de entrega define a prioridade na matrícula.",
              "Fonte: FPP, p. 9; Uniube, p. 4; UVA, p. 4", botao=BOTAO, cor="agua"),
    ]
    corpo = ("Mito: o critério muda de edital para edital. Na FPP (Curitiba/PR), a classificação segue as notas em ordem decrescente, com nota de corte 5,0 (p. 9, item 6.3). "
             "Na Uniube (Uberaba/MG), dos 100 pontos a prova escrita vale 60 e a entrevista, 30 (p. 4). "
             "Já no edital da UVA (Rio de Janeiro/RJ), o resultado é imediato ao deferimento da documentação (p. 4, item 7.1), e a ordem de entrega dos documentos define a prioridade na matrícula (p. 4, item 8.2).\n\n"
             "Leia o critério do edital da faculdade onde você vai se inscrever.")
    fontes = ["- FPP (Curitiba/PR): `528d5ef7e915`, classificação pelas notas em ordem decrescente, nota de corte 5,0: p. 9, item 6.3",
              "- Uniube (Uberaba/MG): `2a698cddcbf7`, 100 pontos em três fases; 2ª fase, prova escrita, 60 pontos; 3ª fase, entrevista, 30 pontos: p. 4 (a análise do histórico, 10 pontos, está na p. 3)",
              "- UVA (Rio de Janeiro/RJ): `1e0e3121b570`, resultado imediato ao deferimento da documentação: p. 4, item 7.1; prioridade na matrícula pela inscrição e entrega dos documentos: p. 4, item 8.2"]
    return _montar("mito-ou-fato", telas, corpo, [facs[x["faculdade_id"]]["sigla"] for x in (fpp, uni, uva)], [], fontes,
                   [(fpp, "FPP", "criterio_selecao", "9"), (uni, "Uniube", "criterio_selecao", "4"), (uva, "UVA", "criterio_selecao", "4")], facs, gancho) | {"pauta": "BANCO #11 (conferida em 12/11)"}


# ---------------------------------------------------------------- domingo: exterior (BANCO #13 + #12)

def pauta_exterior_unoeste(editais, facs, hoje):
    jau, gua, fpp = _edital(editais, "0bfe52b7ab9f"), _edital(editais, "ebbabac553c6"), _edital(editais, "528d5ef7e915")
    _exige(jau["aceita_curso_exterior"] is True and gua["aceita_curso_exterior"] is True and fpp["aceita_curso_exterior"] is False
           and jau["inscricao_fim"] == "2026-12-07" and jau["status"] == gua["status"] == "ok", "UNOESTE/FPP: a regra do exterior ou o prazo mudou")
    gancho = "UNOESTE aceita curso do exterior, até 07/12"
    telas = [
        _capa("Quem estuda no exterior", gancho, "Mas os documentos do exterior precisam de visto consular e tradução juramentada.", "Fonte: UNOESTE, Portaria 24/2026, p. 4, item 6.9, e"),
        {"tipo": "cartoes", "cor": "agua", "kicker": "O que a UNOESTE pede de quem estuda fora", "cartoes": [
            _cartao("Carimbo ou visto do consulado", "Documentos expedidos por instituições estrangeiras", "Item 6.9, e", "edital, p. 4"),
            _cartao("Tradução juramentada para o português", "Do mesmo documento, para estudos de Medicina no exterior", "Item 6.9, e", "edital, p. 4"),
            _cartao("Envio do histórico e dos documentos", "Por e-mail ou na ficha de inscrição, Jaú e Guarujá", "Até 07/12/2026", "edital, p. 4, item 6.8")]},
        {"tipo": "cartoes", "cor": "agua", "kicker": "Nem todo edital aceita", "cartoes": [
            _cartao("UNOESTE · Jaú e Guarujá (SP)", "Aceita quem estuda Medicina no exterior, com os documentos acima", "Aceita", "edital, p. 4, item 6.9, e"),
            _cartao("FPP · Curitiba (PR)", "Não aceita pré-inscrição de quem cursou, no todo ou em parte, em instituição estrangeira", "Não aceita", "edital, p. 5, item 2.10")]},
        dia._chamada("Seu curso no exterior é aceito?", "Cada edital tem a sua regra. O alerta grátis avisa quando abrir, e o diagnóstico mostra quais combinam com o seu caso."),
    ]
    corpo = ("A UNOESTE (Jaú e Guarujá, SP) aceita quem estuda Medicina no exterior na transferência 2027.1: os documentos de instituições estrangeiras precisam do carimbo ou visto "
             "do consulado e da tradução juramentada para o português (Portaria 24/2026, p. 4, item 6.9, e). Histórico e documentos podem ser enviados até 07/12/2026 (p. 4, item 6.8).\n\n"
             "Nem todo edital aceita: o da FPP (Curitiba/PR) não aceita pré-inscrição de quem cursou, no todo ou em parte, em instituição estrangeira (p. 5, item 2.10).")
    fontes = ["- UNOESTE (Jaú/SP) `0bfe52b7ab9f` e (Guarujá/SP) `ebbabac553c6`, Portaria 24/2026 (https://www.unoeste.br/content/documentos/transferencia/Edital-Medicina-2027-1.pdf)",
              "  - documentos do exterior com carimbo ou visto do consulado e tradução juramentada: p. 4, item 6.9, e",
              "  - envio do histórico e dos documentos até 07/12/2026: p. 4, item 6.8",
              "- FPP (Curitiba/PR): `528d5ef7e915`, não aceita quem cursou em IES estrangeira: p. 5, item 2.10"]
    return _montar("estudo-no-exterior", telas, corpo, ["UNOESTE", "FPP"], [], fontes,
                   [(jau, "UNOESTE", "aceita_curso_exterior", "4"), (gua, "UNOESTE", "aceita_curso_exterior", "4"), (fpp, "FPP", "aceita_curso_exterior", "5")], facs, gancho) | {"pauta": "BANCO #13 e #12"}


# ---------------------------------------------------------------- 13 a 15/11 (sexta, sábado e domingo): mesmas pautas, outros dados

def pauta_numeros_unifaa(editais, facs, hoje):
    """Sexta 13/11. UNIFAA Valença, edital 065/2026 (encerrado): 10 vagas de transferência externa (edital, p. 1, item 1.2) e 2 classificados na lista do
    resultado oficial (p. 1). Os dois lidos nos PDFs em 12/11/2026. O documento não traz o número de inscritos, e o post diz isso."""
    e = _edital(editais, "9f1d5ec46f7b")
    _exige(e["situacao"] == "encerrado" and e["status"] == "ok" and _vagas(e) == [("total", 10)] and not (e.get("conferir_campos") or {}), "UNIFAA 065/2026: o edital mudou")
    sigla = facs[e["faculdade_id"]]["sigla"]
    gancho = "UNIFAA: 10 vagas, 2 classificados"
    telas = [
        _capa("Números do Raio-X", gancho, "Transferência externa de Medicina na UNIFAA (Valença/RJ), edital 065/2026: o resultado oficial listou 2 classificados para 10 vagas. O processo já terminou.",
              "Fonte: UNIFAA, edital 065/2026, p. 1, item 1.2; resultado oficial, p. 1"),
        {"tipo": "cartoes", "cor": "agua", "kicker": "Transferência externa, edital 065/2026", "cartoes": [
            _cartao("Vagas ofertadas", "Transferência externa, do 2º ao 6º período", "10 vagas", "edital, p. 1, item 1.2"),
            _cartao("Classificados", "Lista do resultado oficial da transferência externa", "2", "resultado oficial, p. 1")]},
        {"tipo": "cartoes", "cor": "agua", "kicker": "O que o resultado não mostra", "cartoes": [
            _cartao("Quantos se inscreveram", "A lista oficial traz só os classificados, sem o total de candidatos", "Sem esse número", "resultado oficial, p. 1")]},
        dia._chamada("Quer ver os números da sua faculdade?", "O Raio-X mostra vagas e classificados quando a faculdade publica. O alerta grátis avisa quando abrir um edital."),
    ]
    corpo = ("Na UNIFAA (Valença/RJ), a transferência externa de Medicina do edital 065/2026 ofereceu 10 vagas (p. 1, item 1.2), e o resultado oficial listou 2 classificados (p. 1 do resultado). "
             "O documento não informa quantos candidatos se inscreveram. O processo já terminou: o número mostra o que a faculdade divulgou.\n\n"
             "Envie para quem estuda com você.")
    fontes = [f"- UNIFAA (Valença/RJ): `{e['id']}`, Raio-X (data/resultados.json), conferido de novo nos PDFs em 12/11/2026",
              f"  - 10 vagas de transferência externa (2º ao 6º período): p. 1, item 1.2 de {e['url_edital']}",
              "  - 2 classificados/aprovados na lista do resultado oficial: p. 1 de https://www.unifaa.edu.br/pdfs/2026/11/resultado-final-medicina-transferencia-externa-edital-n065.pdf",
              "  - o resultado não traz o total de inscritos (lista só classificados)"]
    return _montar("numeros-do-raio-x", telas, corpo, [sigla], [], fontes,
                   [(e, sigla, "vagas", "1"), (e, sigla, "raio_x_aprovados", "1")], facs, gancho) | {"pauta": "Raio-X UNIFAA (conferido 12/11)"}


def pauta_mito_prova_60(editais, facs, hoje):
    """Sábado 14/11: "Prova de 60 questões em toda faculdade?" (FPP p. 2, item 1.9, b; UVA p. 4, itens 7.1 e 8.2; lidos nos PDFs em 11 e 12/11/2026)."""
    fpp, uva = _edital(editais, "528d5ef7e915"), _edital(editais, "1e0e3121b570")
    _exige(fpp["status"] == "ok" and uva["status"] == "ok" and "60 questões" in fpp["criterio_selecao"] and "deferimento" in uva["criterio_selecao"], "FPP/UVA: critério de seleção mudou")
    gancho = "Prova de 60 questões em toda faculdade?"
    telas = [
        _capa("Mito ou fato?", gancho, "Dois editais abertos, dois jeitos de selecionar os candidatos. Arraste para ver o que cada um prevê e qual é a resposta.", cor="ambar"),
        {"tipo": "cartoes", "cor": "ambar", "kicker": "O que dizem dois editais abertos", "cartoes": [
            _cartao("FPP · Curitiba (PR)", "Etapa classificatória: prova objetiva presencial", "60 questões", "edital, p. 2, item 1.9, b"),
            _cartao("UVA · Rio de Janeiro (RJ)", "Resultado imediato ao deferimento da documentação; o edital não prevê prova", "Sem prova", "edital, p. 4, item 7.1")]},
        _capa("Resposta: mito", "Depende do edital", "A FPP aplica prova objetiva. O edital da UVA decide pela análise da documentação, e a ordem de entrega define a prioridade na matrícula.",
              "Fonte: FPP, p. 2, item 1.9, b; UVA, p. 4, item 8.2", botao=BOTAO, cor="agua"),
    ]
    corpo = ("Mito: nem toda transferência em Medicina tem prova. O edital da FPP (Curitiba/PR) prevê prova objetiva classificatória, de 60 questões (p. 2, item 1.9, b). "
             "Já o edital da UVA (Rio de Janeiro/RJ) não prevê prova: o resultado é imediato ao deferimento da documentação (p. 4, item 7.1), e a ordem de entrega dos documentos "
             "define a prioridade na matrícula (p. 4, item 8.2).\n\n"
             "O critério muda de edital para edital: leia o da faculdade onde você vai se inscrever.")
    fontes = ["- FPP (Curitiba/PR): `528d5ef7e915`, prova objetiva de 60 questões, classificatória: p. 2, item 1.9, b",
              "- UVA (Rio de Janeiro/RJ): `1e0e3121b570`, resultado imediato ao deferimento da documentação (item 7.1) e prioridade pela ordem de entrega (item 8.2): p. 4;",
              "  o PDF retificado de 09/11/2026 só cita \"prova\" no sentido de prova do ENEM (p. 4, itens 6.2 e 6.6), nenhuma prova do processo seletivo"]
    return _montar("mito-ou-fato", telas, corpo, ["FPP", "UVA"], [], fontes,
                   [(fpp, "FPP", "criterio_selecao", "2"), (uva, "UVA", "criterio_selecao", "4")], facs, gancho) | {"pauta": "BANCO #11 (conferida em 11/11)"}


def pauta_exterior_nem_todo(editais, facs, hoje):
    """Domingo 15/11 (BANCO #12): dois editais abertos que não aceitam curso feito no exterior (FPP p. 5, item 2.10; UNIFACCAMP p. 1, item 1.2; lidos nos PDFs)."""
    fpp, fac = _edital(editais, "528d5ef7e915"), _edital(editais, "098f92b0cc9a")
    _exige(fpp["aceita_curso_exterior"] is False and fac["aceita_curso_exterior"] is False and fpp["status"] == fac["status"] == "ok"
           and fpp["situacao"] == fac["situacao"] == "aberto", "FPP/UNIFACCAMP: a regra do exterior mudou")
    s1, s2 = facs[fpp["faculdade_id"]]["sigla"], facs[fac["faculdade_id"]]["sigla"]
    gancho = "Estes 2 editais não aceitam curso do exterior"
    telas = [
        _capa("Quem estuda no exterior", gancho, "Cada edital tem a sua regra para quem cursou fora do Brasil. Veja o que dizem dois editais abertos.", "Fonte: FPP, p. 5, item 2.10; UNIFACCAMP, p. 1, item 1.2"),
        {"tipo": "cartoes", "cor": "agua", "kicker": "Dois editais abertos, a mesma regra", "cartoes": [
            _cartao("FPP · Curitiba (PR)", "Não aceita pré-inscrição de quem cursou, no todo ou em parte, em instituição estrangeira", "Não aceita", "edital, p. 5, item 2.10"),
            _cartao("UNIFACCAMP · Campo Limpo Paulista (SP)", "Só aceita transferência de curso de Medicina feito no território nacional", "Não aceita", "edital, p. 1, item 1.2")]},
        dia._chamada("Seu curso no exterior é aceito?", "Cada edital tem a sua regra. O alerta grátis avisa quando abrir, e o diagnóstico mostra quais combinam com o seu caso."),
    ]
    corpo = ("Se você estuda Medicina no exterior, confira a regra de cada edital. O da FPP (Curitiba/PR) não aceita pré-inscrição de quem cursou, no todo ou em parte, em instituição estrangeira (p. 5, item 2.10). "
             "O da UNIFACCAMP (Campo Limpo Paulista/SP) só aceita transferência de curso de Medicina realizado no território nacional (p. 1, item 1.2).\n\n"
             "Outros editais têm regras diferentes: leia a do edital da faculdade onde você quer se inscrever.")
    fontes = ["- FPP (Curitiba/PR): `528d5ef7e915`, não aceita pré-inscrição de quem cursou, no todo ou em parte, em IES estrangeira: p. 5, item 2.10",
              "- UNIFACCAMP (Campo Limpo Paulista/SP): `098f92b0cc9a`, só transferência de curso de Medicina realizado no território nacional; sem transferência do exterior nem aproveitamento de disciplinas do exterior: p. 1, item 1.2"]
    return _montar("estudo-no-exterior", telas, corpo, [s1, s2], [], fontes,
                   [(fpp, s1, "aceita_curso_exterior", "5"), (fac, s2, "aceita_curso_exterior", "1")], facs, gancho) | {"pauta": "BANCO #12"}


# data -> pauta, para os dias fora da semana de segunda a domingo montada acima (13 a 15/11, pedido de 12/11/2026)
PAUTAS_DO_DIA = {"2026-11-13": pauta_numeros_unifaa, "2026-11-14": pauta_mito_prova_60, "2026-11-15": pauta_exterior_nem_todo}


PAUTAS = {1: pauta_armadilha_fpp, 2: pauta_processo_periodo, 3: pauta_curiosidade_unifaccamp, 4: pauta_numeros_unicamp, 5: pauta_mito_prova, 6: pauta_exterior_unoeste}


def revisar(r, editais, facs, dia_):
    """Problemas que impedem a pauta de sair: as regras (a) a (g) e os itens do padrão (a imagem é medida nos pixels)."""
    return ck.checar(r, editais, facs, dia_)


def _gravar_pauta(fn, d, editais, facs, base):
    """Roda a pauta, passa pela checagem e grava em docs/social/d (curado: true). Devolve a mensagem do dia."""
    try:
        r = fn(editais, facs, d)
        nota = r.pop("pauta", "")
        problemas = revisar(r, editais, facs, d)
    except PautaInvalida as exc:
        r, nota, problemas = None, "", [f"pauta inválida: {exc}"]
    if problemas:
        pasta = dia.SOCIAL / d
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "SEM_POST.txt").write_text(f"Sem post para {d}: {fn.__name__} reprovou: {' | '.join(problemas)}. Nada foi inventado.\n", encoding="utf-8")
        return f"{d}: SEM POST ({fn.__name__}): {' | '.join(problemas)}"
    dia.gravar(r, f"Pauta curada ({nota}); passou em ck.checar com os dados de {base}", d, privado=dia.PRIVADO / d if dia.PRIVADO.parent.exists() else None)
    manifesto = dia.SOCIAL / d / "post.json"
    post = json.loads(manifesto.read_text(encoding="utf-8"))
    post["curado"] = True
    manifesto.write_text(json.dumps(post, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return f"{d}: {r['tipo']} ({len(r['slides'])} telas) · {nota}"


def gerar_semana(segunda, saida=None, dados=None):
    """Segunda: o robô (post_abertos). Terça a domingo: as pautas curadas acima. Grava em docs/social/AAAA-MM-DD (curado: true) e monta o pacote de
    revisão (previa.jpg + FONTES.md e legenda de cada dia). Devolve (mensagens, pasta do pacote)."""
    editais, facs = dados or dia._dados()
    dias = dia.semana_de(segunda)
    msgs = []
    sit, msg = dia.gerar_dia(dias[0], (editais, facs))
    msgs.append(f"{dias[0]}: {msg}")
    for k, fn in PAUTAS.items():
        msgs.append(_gravar_pauta(PAUTAS_DO_DIA.get(dias[k], fn), dias[k], editais, facs, segunda))
    return msgs, dia.pacote_da_semana(segunda, saida=saida)


def gerar_dias(inicio, saida=None, dados=None):
    """Grava as pautas de PAUTAS_DO_DIA (13 a 15/11) e monta o pacote de 7 dias a partir de `inicio` (a prévia rotula o dia da semana de cada data)."""
    editais, facs = dados or dia._dados()
    msgs = [_gravar_pauta(fn, d, editais, facs, inicio) for d, fn in sorted(PAUTAS_DO_DIA.items())]
    return msgs, dia.pacote_da_semana(inicio, saida=saida)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--semana", metavar="SEGUNDA", help="segunda-feira da semana, AAAA-MM-DD")
    ap.add_argument("--dias-de", metavar="DATA", help="grava as pautas de PAUTAS_DO_DIA (13 a 15/11) e monta o pacote de 7 dias a partir desta data")
    ap.add_argument("--saida", default=None, help="pasta do pacote de revisão (padrão privado/instagram)")
    args = ap.parse_args(argv)
    if args.dias_de:
        msgs, pasta = gerar_dias(args.dias_de, args.saida)
        print("\n".join(msgs))
        print(f"Pacote de {args.dias_de}: {pasta}")
        return 0
    if not args.semana:
        ap.error("informe --semana SEGUNDA ou --dias-de DATA")
    if date.fromisoformat(args.semana).weekday() != 0:
        ap.error("--semana precisa ser uma segunda-feira")
    msgs, pasta = gerar_semana(args.semana, args.saida)
    print("\n".join(msgs))
    print(f"Pacote da semana de {args.semana}: {pasta}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
