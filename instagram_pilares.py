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


# ---------------------------------------------------------------- quarta: como funciona (BANCO #10, com o quadro aberto da FPP)

def pauta_processo_periodo(editais, facs, hoje):
    e = _edital(editais, "528d5ef7e915")
    _exige(_vagas(e) == [("2º", 6), ("3º", 3), ("4º", 6)] and e["status"] == "ok", "FPP: o quadro de vagas mudou")
    gancho = "Na FPP, o 3º período tem 3 vagas"
    telas = [
        _capa("Como funciona o processo", gancho, "A vaga é por período, não por faculdade: cada quadro de vagas mostra quantas há em cada período e em qual período você precisa estar.",
              "Fonte: FPP, edital 025/2026, p. 2 e p. 3"),
        {"tipo": "cartoes", "cor": "agua", "kicker": "Quadro de vagas da FPP, 2027.1", "cartoes": [
            _cartao("2º período", "Curitiba (PR) · transferência dependente de vaga", "6 vagas", "edital, p. 2, item 1.8"),
            _cartao("3º período", "Curitiba (PR) · transferência dependente de vaga", "3 vagas", "edital, p. 2, item 1.8"),
            _cartao("4º período", "Curitiba (PR) · transferência dependente de vaga", "6 vagas", "edital, p. 2, item 1.8")]},
        {"tipo": "cartoes", "cor": "agua", "kicker": "Em que período você precisa estar", "cartoes": [
            _cartao("Para a vaga do 2º período", "Estar cursando o equivalente ao 1º período do 1º ano", "Cursando o 1º", "edital, p. 3, item 2.2, a"),
            _cartao("Para a vaga do 3º período", "Estar cursando o equivalente ao 2º período do 1º ano", "Cursando o 2º", "edital, p. 3, item 2.2, b"),
            _cartao("Para a vaga do 4º período", "Estar cursando o equivalente ao 3º período do 2º ano", "Cursando o 3º", "edital, p. 3, item 2.2, c")]},
        dia._chamada("Em que período você está?", "Cada edital abre vagas por período. O alerta grátis avisa antes de cada prazo, e o diagnóstico mostra quais combinam com o seu período."),
    ]
    corpo = ("Na transferência, a vaga é por período. No edital 025/2026 da FPP (Curitiba/PR, Medicina 2027.1) são 6 vagas no 2º período, 3 no 3º e 6 no 4º (p. 2, item 1.8). "
             "Para concorrer, você precisa estar cursando o período imediatamente anterior ao da vaga (p. 3, item 2.2).\n\n"
             "Salve este post para a época da inscrição e envie para quem estuda com você.")
    fontes = ["- FPP (Curitiba/PR): `528d5ef7e915`, edital 025/2026 (https://fpp.edu.br/wp-content/uploads/2026/10/EDITAL-DE-TRANSFERENCIA-DE-MEDICINA-1-SEMESTRE-DE-2027_MED.pdf)",
              "  - quadro de vagas: 2º período 06, 3º período 03, 4º período 06: p. 2, item 1.8",
              "  - requisito de período (cursando o equivalente ao período anterior): p. 3, item 2.2, a, b e c"]
    return _montar("como-funciona-periodo", telas, corpo, ["FPP"], [], fontes,
                   [(e, "FPP", "vagas", "2"), (e, "FPP", "quem_pode", "3")], facs, gancho) | {"pauta": "BANCO #10"}


# ---------------------------------------------------------------- quinta: curiosidade (BANCO #2)

def pauta_curiosidade_uva(editais, facs, hoje):
    e = _edital(editais, "1e0e3121b570")
    _exige(e["taxa_inscricao"] == 250.0 and e["status"] == "ok" and "taxa_inscricao" not in (e.get("conferir_campos") or {}), "UVA: a taxa ou o status mudou")
    gancho = "UVA baixou a taxa de R$ 400 para R$ 250"
    telas = [
        _capa("Curiosidade do edital", gancho, "O edital retificado em 09/11/2026 da transferência externa 2027.1 da UVA (Rio de Janeiro) traz a taxa de inscrição menor.",
              "Fonte: UVA, edital 2027.1, p. 2, item 3.1, f", cor="agua"),
        {"tipo": "cartoes", "cor": "agua", "kicker": "O mesmo item, em duas versões", "cartoes": [
            _cartao("Edital original", "Taxa de inscrição, item 3.1, f", "R$ 400", "edital original, p. 2"),
            _cartao("Edital retificado em 09/11/2026", "Taxa de inscrição, item 3.1, f", "R$ 250", "edital retificado, p. 2")]},
        dia._chamada("Vai se inscrever em mais de um edital?", "Cada edital tem taxa, prazo e documentos próprios. O alerta grátis avisa antes de cada prazo."),
    ]
    corpo = ("A UVA (Rio de Janeiro/RJ) baixou a taxa de inscrição da transferência externa 2027.1 de R$ 400 para R$ 250. Os dois valores estão no item 3.1, f, "
             "na página 2: R$ 400 no edital original e R$ 250 no edital retificado em 09/11/2026.\n\n"
             "Quem já tinha pagado antes da retificação deve tirar a dúvida direto com a faculdade.")
    fontes = ["- UVA (Rio de Janeiro/RJ): `1e0e3121b570`, taxa de inscrição, item 3.1, f, página 2 das duas versões",
              "  - R$ 400,00 no edital original (https://selecao.econrio.com.br/modulo/arquivos/26148/inscricao/edital/26148_-_uva_-_edital_pd_e_te__27.1.pdf)",
              "  - R$ 250,00 no edital retificado em 09/11/2026 (https://selecao.econrio.com.br/modulo/arquivos/26148/inscricao/edital/26148_-_uva_-_edital_pd_e_te__27.1_-_retificado_09112026.pdf)"]
    return _montar("curiosidade-de-faculdade", telas, corpo, ["UVA"], [], fontes, [(e, "UVA", "taxa_inscricao", "2")], facs, gancho) | {"pauta": "BANCO #2"}


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


# ---------------------------------------------------------------- sábado: mito ou fato (BANCO #11)

def pauta_mito_prova(editais, facs, hoje):
    fpp, uva = _edital(editais, "528d5ef7e915"), _edital(editais, "1e0e3121b570")
    _exige(fpp["status"] == "ok" and uva["status"] == "ok" and "análise da documentação" in uva["criterio_selecao"], "FPP/UVA: critério de seleção mudou")
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
    fontes = ["- FPP (Curitiba/PR): `528d5ef7e915`, prova objetiva de 60 questões, classificatória, 07/12/2026: p. 2, item 1.9, b",
              "- UVA (Rio de Janeiro/RJ): `1e0e3121b570`, resultado imediato ao deferimento da documentação (item 7.1) e prioridade pela ordem de entrega (item 8.2): p. 4;",
              "  o PDF retificado de 09/11/2026 só cita \"prova\" no sentido de prova do ENEM (p. 4, itens 6.2 e 6.6), nenhuma prova do processo seletivo"]
    return _montar("mito-ou-fato", telas, corpo, ["FPP", "UVA"], [], fontes,
                   [(fpp, "FPP", "criterio_selecao", "2"), (uva, "UVA", "criterio_selecao", "4")], facs, gancho) | {"pauta": "BANCO #11 (conferida em 11/11)"}


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


PAUTAS = {1: pauta_armadilha_fpp, 2: pauta_processo_periodo, 3: pauta_curiosidade_uva, 4: pauta_numeros_unicamp, 5: pauta_mito_prova, 6: pauta_exterior_unoeste}


def revisar(r, editais, facs, dia_):
    """Problemas que impedem a pauta de sair: as regras (a) a (g) e os itens do padrão (a imagem é medida nos pixels)."""
    return ck.checar(r, editais, facs, dia_)


def gerar_semana(segunda, saida=None, dados=None):
    """Segunda: o robô (post_abertos). Terça a domingo: as pautas curadas acima. Grava em docs/social/AAAA-MM-DD (curado: true) e monta o pacote de
    revisão (previa.jpg + FONTES.md e legenda de cada dia). Devolve (mensagens, pasta do pacote)."""
    editais, facs = dados or dia._dados()
    dias = dia.semana_de(segunda)
    msgs = []
    sit, msg = dia.gerar_dia(dias[0], (editais, facs))
    msgs.append(f"{dias[0]}: {msg}")
    for k, fn in PAUTAS.items():
        d = dias[k]
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
            msgs.append(f"{d}: SEM POST ({fn.__name__}): {' | '.join(problemas)}")
            continue
        dia.gravar(r, f"Pauta curada ({nota}); passou em ck.checar com os dados de {segunda}", d, privado=dia.PRIVADO / d if dia.PRIVADO.parent.exists() else None)
        manifesto = dia.SOCIAL / d / "post.json"
        post = json.loads(manifesto.read_text(encoding="utf-8"))
        post["curado"] = True
        manifesto.write_text(json.dumps(post, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        msgs.append(f"{d}: {r['tipo']} ({len(r['slides'])} telas) · {nota}")
    return msgs, dia.pacote_da_semana(segunda, saida=saida)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--semana", required=True, metavar="SEGUNDA", help="segunda-feira da semana, AAAA-MM-DD")
    ap.add_argument("--saida", default=None, help="pasta do pacote de revisão (padrão privado/instagram)")
    args = ap.parse_args(argv)
    if date.fromisoformat(args.semana).weekday() != 0:
        ap.error("--semana precisa ser uma segunda-feira")
    msgs, pasta = gerar_semana(args.semana, args.saida)
    print("\n".join(msgs))
    print(f"Pacote da semana de {args.semana}: {pasta}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
