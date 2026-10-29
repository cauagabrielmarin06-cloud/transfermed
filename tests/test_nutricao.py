"""Testes dos e-mails novos (nutricao.py), da simulação sem ALERTAS_ATIVOS e da isca em PDF."""
import json
import re
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import alertas  # noqa: E402
import gerar_site  # noqa: E402
import isca  # noqa: E402
import nutricao  # noqa: E402

PASTA = Path(__file__).resolve().parent.parent
F = {f["id"]: f for f in json.loads((PASTA / "data" / "faculdades.json").read_text(encoding="utf-8"))}
E = json.loads((PASTA / "data" / "editais.json").read_text(encoding="utf-8"))
CONS = gerar_site.CONSENTIMENTO
FAC = {"id": "x", "nome": "Faculdade X", "sigla": "FX", "cidade": "C", "uf": "SP", "tipo": "particular", "lat": 0, "lon": 0}


def ed(**kw):
    base = {"id": "e1", "faculdade_id": "x", "fonte_dados": "manual", "modalidade": "externa", "url_edital": "https://x/e.pdf",
            "inscricao_inicio": "2026-11-01", "inscricao_fim": "2026-11-20", "conferido_em": "2026-10-26"}
    return {**base, **kw}


def assinante(**kw):
    base = {"id": "a1", "email": "a@exemplo.com", "token": "t", "status": "ativo", "criado_em": "2026-10-29T12:00:00+00:00",
            "confirmado_em": "2026-10-29T12:00:00+00:00", "consentimento_texto": CONS,
            "perfil": {"curso": "medicina", "origem": "brasil", "semestre": 5}}
    return {**base, **kw}


class Sequencia(unittest.TestCase):
    def test_consentimento_fala_das_dicas_e_do_resumo(self):
        self.assertIn(nutricao.MARCA_CONSENTIMENTO, CONS)
        self.assertIn("resumo semanal", CONS)

    def test_passos_no_dia_certo_e_so_uma_vez(self):
        a = assinante()
        self.assertEqual(nutricao.passo_devido(a, "2026-10-29", set()), 0)
        self.assertEqual(nutricao.passo_devido(a, "2026-10-31", {"seq:0"}), 2)
        self.assertIsNone(nutricao.passo_devido(a, "2026-10-31", {"seq:0", "seq:2"}))
        self.assertEqual(nutricao.passo_devido(a, "2026-11-12", {"seq:0", "seq:2", "seq:5", "seq:9"}), 14)

    def test_passo_atrasado_e_pulado(self):
        # boas-vindas nunca chega semanas depois (ex.: quem confirmou antes da ativação)
        self.assertIsNone(nutricao.passo_devido(assinante(confirmado_em="2026-09-01T00:00:00+00:00"), "2026-10-29", set()))

    def test_sem_o_consentimento_novo_nao_recebe_dicas(self):
        antigo = assinante(consentimento_texto="Quero receber por e-mail alertas de editais. Sei que posso cancelar.")
        self.assertIsNone(nutricao.passo_devido(antigo, "2026-10-29", set()))
        self.assertIsNone(nutricao.passo_devido(assinante(confirmado_em=None), "2026-10-29", set()))

    def test_versao_exterior_nos_dias_2_e_9(self):
        c = nutricao.Contexto(E, F, "https://s", "2026-10-29")
        ext = assinante(perfil={"curso": "medicina", "origem": "exterior"})
        self.assertNotEqual(nutricao.dia2(ext, c)[0], nutricao.dia2(assinante(), c)[0])
        self.assertIn("exterior", nutricao.dia9(ext, c)[0])
        self.assertIn("apostila", nutricao.dia9(ext, c)[2].lower())

    def test_exemplos_sempre_com_pagina_e_link(self):
        c = nutricao.Contexto(E, F, "https://s", "2026-10-29")
        for x in c.exemplos(r"enade|historico"):
            self.assertRegex(x, r'href="https://s/edital/[^"]+/"')

    def test_nenhum_email_fala_em_consultoria(self):
        c = nutricao.Contexto(E, F, "https://s", "2026-10-29")
        for passo in nutricao.PASSOS.values():
            for p in ({"curso": "medicina"}, {"curso": "medicina", "origem": "exterior"}, {}):
                self.assertNotIn("consultoria", passo(assinante(perfil=p), c)[2].lower())


class Lembretes(unittest.TestCase):
    def ctx(self, hoje, **kw):
        return nutricao.Contexto([ed(**kw)], {"x": FAC}, "https://s", hoje)

    def a(self):
        return assinante(perfil={"seguir": {"lembretes": ["e1"]}})

    def test_7_e_2_dias(self):
        self.assertEqual([t for t, *_ in nutricao.lembretes_devidos(self.a(), self.ctx("2026-11-13"), set())], [7])
        self.assertEqual(nutricao.lembretes_devidos(self.a(), self.ctx("2026-11-13"), {"lembrete7:e1"}), [])
        self.assertEqual([t for t, *_ in nutricao.lembretes_devidos(self.a(), self.ctx("2026-11-18"), {"lembrete7:e1"})], [2])
        self.assertEqual(nutricao.lembretes_devidos(self.a(), self.ctx("2026-11-21"), set()), [], "depois do prazo, nada")
        self.assertEqual(nutricao.lembretes_devidos(self.a(), self.ctx("2026-11-05"), set()), [], "longe do prazo, nada")

    def test_data_a_conferir_nao_gera_lembrete(self):
        self.assertEqual(nutricao.lembretes_devidos(self.a(), self.ctx("2026-11-18", status="conferir"), set()), [])

    def test_so_quem_pediu(self):
        self.assertEqual(nutricao.lembretes_devidos(assinante(), self.ctx("2026-11-18"), set()), [])


class Resumo(unittest.TestCase):
    SEG = datetime(2026, 11, 2, 11, 30, tzinfo=timezone.utc)  # segunda, 8h30 em Brasília

    def test_so_segunda_depois_das_8(self):
        c = nutricao.Contexto([], {}, "https://s", "2026-11-02")
        self.assertTrue(nutricao.resumo_devido(None, c, self.SEG, set()))
        self.assertFalse(nutricao.resumo_devido(None, c, self.SEG.replace(hour=10), set()))
        self.assertFalse(nutricao.resumo_devido(None, c, self.SEG, {"resumo:2026-11-02"}))

    def test_so_com_novidade_depois_da_inscricao(self):
        c = nutricao.Contexto([ed()], {"x": FAC}, "https://s", "2026-11-02")
        antigo = assinante(confirmado_em="2026-10-01T00:00:00+00:00")
        self.assertIsNotNone(nutricao.resumo_semanal(antigo, c, [(ed(), FAC)]))
        self.assertIsNone(nutricao.resumo_semanal(assinante(), c, [(ed(), FAC)]), "conferido antes da inscrição")
        self.assertIsNone(nutricao.resumo_semanal(antigo, c, [(ed(conferido_em="2026-10-01"), FAC)]), "nada novo na semana")


class Simulacao(unittest.TestCase):
    def banco(self, assinantes):
        d = Path(tempfile.mkdtemp())
        (d / "b.json").write_text(json.dumps({"assinantes": assinantes, "notificacoes": []}), encoding="utf-8")
        return alertas.BancoSimulado(d / "b.json")

    def test_sem_alertas_ativos_monta_mas_nao_envia_nem_registra(self):
        banco = self.banco([assinante()])
        envio, teste = alertas.EnvioSimulado(tempfile.mkdtemp()), alertas.EnvioContador()
        r = alertas.rodar(banco, envio, [], F, hoje="2026-10-29", agora=datetime(2026, 10, 29, 12, tzinfo=timezone.utc),
                          novos_ativos=False, envio_teste=teste)
        self.assertEqual(r["simulados"]["boas_vindas"], 1)
        self.assertEqual(len(teste.enviados), 1)
        self.assertEqual(envio.enviados, [])
        self.assertEqual(banco.avisados("a1"), set())

    def test_com_alertas_ativos_envia_uma_vez(self):
        banco = self.banco([assinante()])
        envio = alertas.EnvioSimulado(tempfile.mkdtemp())
        agora = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)
        for _ in range(2):
            alertas.rodar(banco, envio, [], F, hoje="2026-10-29", agora=agora, novos_ativos=True)
        self.assertEqual(len(envio.enviados), 1)
        self.assertEqual(banco.avisados("a1"), {"seq:0"})

    def test_perfil_so_seguindo_faculdade_nao_recebe_alerta_geral(self):
        x = ed(inscricao_inicio="2026-10-01")
        p = {"seguir": {"faculdades": [], "lembretes": []}}
        self.assertEqual(alertas.novidades(p, [x], {"x": FAC}, set(), "2026-10-29"), [])
        p["seguir"]["faculdades"] = ["x"]
        self.assertEqual(len(alertas.novidades_seguidas(p, [x], {"x": FAC}, set(), "2026-10-29")), 1)

    def test_inscrever_soma_pedidos_e_nao_apaga_o_perfil(self):
        banco = self.banco([])
        banco.inscrever("a@exemplo.com", {"curso": "medicina", "semestre": 3, "seguir": {"faculdades": ["x"], "lembretes": []}}, CONS)
        banco.inscrever("a@exemplo.com", {"seguir": {"faculdades": ["y"], "lembretes": ["e1"]}}, CONS)
        p = banco.assinantes()[0]["perfil"]
        self.assertEqual(p["semestre"], 3)
        self.assertEqual(p["seguir"], {"faculdades": ["x", "y"], "lembretes": ["e1"]})


class Isca(unittest.TestCase):
    def test_so_itens_transcritos_com_fonte(self):
        publicaveis = [x for x in E if gerar_site.publicavel(x)]
        grupos, total, _ = isca.montar(publicaveis, F)
        transcritos = {d for x in publicaveis if x.get("documentos") for d in x["documentos"]}
        self.assertGreater(total, 0)
        for g in grupos:
            for doc, fonte in g["itens"]:
                self.assertIn(doc, transcritos)
                self.assertTrue(fonte)

    def test_pdf_publicado_e_citado_nas_chamadas(self):
        self.assertTrue((gerar_site.DOCS / isca.ARQUIVO).exists())
        html = (gerar_site.DOCS / "exterior" / "index.html").read_text(encoding="utf-8")
        self.assertIn(isca.ARQUIVO, html)
        self.assertIn("Grátis. Sem spam. Cancele em um clique.", html)

    def test_lembrete_so_com_prazo_que_ainda_da_tempo(self):
        hoje = "2026-10-29"
        for x in (x for x in E if gerar_site.publicavel(x)):
            html = (gerar_site.DOCS / "edital" / gerar_site.slug_edital(x) / "index.html").read_text(encoding="utf-8")
            self.assertEqual(html.count('id="form-alerta"'), 1)
            if "data-lembrete" in html:
                self.assertFalse(gerar_site.fora_dos_emails(x), "prazo final a conferir não tem lembrete")
                self.assertFalse(x.get("fluxo_continuo"))
                self.assertGreaterEqual(x["inscricao_fim"], hoje)


class Revisao2(unittest.TestCase):
    """Itens da 2ª revisão do dono (29/10/2026)."""
    AGORA = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)

    def banco(self, assinantes):
        d = Path(tempfile.mkdtemp())
        (d / "b.json").write_text(json.dumps({"assinantes": assinantes, "notificacoes": []}), encoding="utf-8")
        return alertas.BancoSimulado(d / "b.json")

    def test_1_exterior_sem_semestre_recebe_edital_so_do_exterior_com_aviso(self):
        x = ed(modalidade="exterior", inscricao_inicio="2026-10-01", vagas=[{"semestre": "3º", "vagas": 2}])
        p = {"curso": "medicina", "origem": "exterior"}
        itens = alertas.novidades(p, [x], {"x": FAC}, set(), "2026-10-29")
        self.assertEqual(len(itens), 1, "semestre não informado não exclui o edital")
        _, html, texto = alertas.email_alerta(assinante(perfil=p), itens, "2026-10-29")
        self.assertIn("Confira se o seu semestre se encaixa", html)
        self.assertIn("Confira se o seu semestre se encaixa", texto)
        com_sem = alertas.email_alerta(assinante(perfil={**p, "semestre": 3}), itens, "2026-10-29")[1]
        self.assertNotIn("Confira se o seu semestre se encaixa", com_sem)

    def test_2_dia_da_inscricao_confirmacao_e_um_so_email(self):
        x = ed(inscricao_inicio="2026-10-01", inscricao_fim="2026-10-31")
        pend = assinante(status="pendente", confirmado_em=None,
                         perfil={"curso": "medicina", "seguir": {"lembretes": ["e1"], "faculdades": ["x"]}})
        banco = self.banco([pend])
        envio = alertas.EnvioSimulado(tempfile.mkdtemp())
        alertas.rodar(banco, envio, [x], {"x": FAC}, hoje="2026-10-29", agora=self.AGORA, novos_ativos=True)
        banco.confirmar("t", agora=self.AGORA)
        for _ in range(3):  # o robô roda várias vezes no dia
            alertas.rodar(banco, envio, [x], {"x": FAC}, hoje="2026-10-29", agora=self.AGORA, novos_ativos=True)
        assuntos = [s for _, s in envio.enviados]
        self.assertEqual(len(assuntos), 2, assuntos)
        self.assertEqual(assuntos[0], "Falta um clique para ativar seus alertas")
        # vencem lembrete de 2 dias, boas-vindas e alerta: só o mais importante sai hoje
        self.assertTrue(assuntos[1].startswith("Últimos dias"), assuntos)
        amanha = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)
        alertas.rodar(banco, envio, [x], {"x": FAC}, hoje="2026-10-30", agora=amanha, novos_ativos=True)
        self.assertEqual(len(envio.enviados), 3)
        self.assertTrue(envio.enviados[-1][1].startswith("Seu alerta está ativo"), "boas-vindas no dia seguinte")

    def test_2_boas_vindas_leva_os_editais_no_lugar_do_alerta(self):
        eds = [ed(id=f"e{i}", inscricao_inicio="2026-10-01", inscricao_fim=f"2026-12-{10 + i}") for i in range(7)]
        banco = self.banco([assinante()])
        envio = alertas.EnvioSimulado(tempfile.mkdtemp())
        alertas.rodar(banco, envio, eds, {"x": FAC}, hoje="2026-10-29", agora=self.AGORA, novos_ativos=True)
        self.assertEqual(len(envio.enviados), 1)
        html = next(Path(envio.pasta).glob("*.html")).read_text(encoding="utf-8")
        self.assertEqual(html.count("Ver resumo e documentos"), nutricao.MAX_BOAS_VINDAS)
        self.assertIn("Ver todos os 7 editais para o seu perfil", html)
        self.assertEqual(banco.avisados("a1"), {"seq:0"} | {f"e{i}" for i in range(7)}, "não sai alerta depois")

    def test_3_todo_email_tem_o_mesmo_rodape(self):
        c = nutricao.Contexto(E, F, "https://s", "2026-11-13")
        a = assinante(perfil={"curso": "medicina", "origem": "brasil", "semestre": 5, "seguir": {"lembretes": ["e1"]}})
        x = (ed(), FAC)
        emails = [nutricao.confirmacao(a, "https://s", 7), nutricao.alerta(a, c, [x])]
        emails += [nutricao.finalizar(a, "https://s", *f(a, c)) for f in nutricao.PASSOS.values()]
        emails.append(nutricao.finalizar(a, "https://s", *nutricao.lembrete(a, c, 2, 1, *x)))
        antigo = assinante(perfil=a["perfil"], confirmado_em="2026-10-01")
        emails.append(nutricao.finalizar(antigo, "https://s", *nutricao.resumo_semanal(antigo, c, [x])))
        for assunto, html, texto in emails:
            for v in (html, texto):
                self.assertIn("Você recebe este e-mail porque ativou alertas para: Medicina, no Brasil, 5º semestre", v, assunto)
                self.assertIn("Quem decide a vaga é sempre a faculdade.", v, assunto)
                self.assertIn("https://s/alerta/descadastrar/?t=t", v, assunto)
            self.assertIn("Cauã", texto)

    def test_4_documento_sem_aspas_e_em_parafrase(self):
        c = nutricao.Contexto(E, F, "https://s", "2026-10-29")
        for perfil in ({"curso": "medicina"}, {"curso": "medicina", "origem": "exterior"}):
            corpo = nutricao.dia9(assinante(perfil=perfil), c)[2]
            for aspa in ("“", "”", "&quot;"):
                self.assertNotIn(aspa, corpo)
            self.assertRegex(corpo, r"[A-Z]{2,} pede [a-zà-ú]")

    def test_5_numeros_saem_dos_dados_na_hora(self):
        base = [ed(id=f"e{i}", url_edital=f"https://x/{i}.pdf", criterio_selecao="prova objetiva" if i < 2 else "análise do histórico",
                   aceita_curso_exterior=(i == 0)) for i in range(3)]
        ext = assinante(perfil={"curso": "medicina", "origem": "exterior"})
        corpo = nutricao.dia2(ext, nutricao.Contexto(base, {"x": FAC}, "https://s", "2026-10-29"))[2]
        self.assertIn("dos 3 editais que conferi, 1 aceitaram", corpo)
        self.assertIn("Em 2 dos 3 editais tem prova", corpo)
        corpo2 = nutricao.dia2(ext, nutricao.Contexto(base[:2], {"x": FAC}, "https://s", "2026-10-29"))[2]
        self.assertIn("Em 2 dos 2 editais tem prova", corpo2)
        self.assertTrue(nutricao.historia()[0].startswith("Hoje estou "), "a história vem do texto da /sobre/")

    def test_6_resumo_assunto_conforme_o_conteudo(self):
        antigo = assinante(confirmado_em="2026-10-01T00:00:00+00:00")
        c = nutricao.Contexto([], {"x": FAC}, "https://s", "2026-11-02")
        velho = {"conferido_em": "2026-10-01"}
        itens = [(ed(id="n", inscricao_inicio="2026-10-01", inscricao_fim="2026-12-01"), FAC),
                 (ed(id="u", inscricao_inicio="2026-10-01", inscricao_fim="2026-11-05", **velho), FAC),
                 (ed(id="a", inscricao_inicio="2026-10-01", inscricao_fim="2026-12-20", **velho), FAC)]
        assunto, _, corpo = nutricao.resumo_semanal(antigo, c, itens)
        self.assertEqual(assunto, "Resumo da semana: 1 edital novo · 1 encerra nos próximos 7 dias · 1 continua aberto")
        for t in ("Novos esta semana", "Encerram nos próximos 7 dias", "Continuam abertos"):
            self.assertEqual(corpo.count(t), 1)
        self.assertNotIn("novo", nutricao.resumo_semanal(antigo, c, itens[1:])[0])
        self.assertIsNone(nutricao.resumo_semanal(antigo, c, itens[2:]), "sem novos nem prazo, sem resumo")

    def test_7_confirmacao_com_o_texto_do_dono(self):
        assunto, _, texto = nutricao.confirmacao(assinante(), "https://s", 7)
        self.assertEqual(assunto, "Falta um clique para ativar seus alertas")
        self.assertIn("Oi! Aqui é o Cauã, do Transfermed. Para começar a receber os avisos de transferência de Medicina "
                      "para o seu perfil, confirme seu e-mail:", texto)
        self.assertIn("Confirmar meus alertas <https://s/alerta/confirmar/?t=t>", texto)
        self.assertIn("o cadastro é apagado sozinho em 7 dias.", texto)
        self.assertIn("Um abraço,\nCauã", texto)

    def test_8_alerta_agrupado_e_assunto_dos_dados(self):
        c = nutricao.Contexto([], {"x": FAC}, "https://s", "2026-10-29")
        itens = [(ed(id="h1", inscricao_inicio="2026-10-01", inscricao_fim="2026-10-29"), FAC),
                 (ed(id="h2", inscricao_inicio="2026-10-01", inscricao_fim="2026-10-29"), FAC),
                 (ed(id="a1", inscricao_inicio="2026-10-01", inscricao_fim="2026-12-29"), FAC)]
        assunto, html, texto = nutricao.alerta(assinante(), c, itens)
        self.assertEqual(assunto, "2 editais encerram hoje · 3 abertos para o seu perfil")
        self.assertLess(html.index("Encerram nos próximos 7 dias"), html.index(">Abertos<"))
        self.assertIn("FX (C/SP)", html)
        self.assertIn("confira sempre as datas no edital oficial", texto)
        self.assertTrue(texto.startswith("Oi! Aqui é o Cauã."))
        self.assertEqual(nutricao.alerta(assinante(), c, itens[2:])[0], "FX (C): inscrições abertas até 29/12/2026")

    def test_9_lembrete_de_2_dias_com_checklist_e_horario(self):
        c = nutricao.Contexto([], {"x": FAC}, "https://s", "2026-11-18")
        x = ed(documentos=["Histórico escolar"])
        corpo = nutricao.lembrete(assinante(), c, 2, 2, x, FAC)[2]
        self.assertIn("#checklist", corpo)
        self.assertIn("Confira também o horário limite no edital: muitas inscrições fecham num horário específico do "
                      "último dia.", corpo)
        self.assertNotIn("horário limite", nutricao.lembrete(assinante(), c, 7, 7, x, FAC)[2])

    def test_10_links_de_pagina_e_texto_limpo(self):
        c = nutricao.Contexto(E, F, "https://s", "2026-10-29")
        a = assinante()
        _, html, texto = nutricao.finalizar(a, "https://s", *nutricao.dia9(a, c))
        corpo = html.split("<h1", 1)[1]
        self.assertRegex(corpo, r'<a href="https://s/edital/[^"]+/"[^>]*>p\. \d+</a>')
        sem_tags = re.sub(r"<[^>]+>", " ", corpo)
        self.assertNotIn("http", sem_tags, "nenhum endereço solto no HTML")
        self.assertNotIn("<a ", texto)
        self.assertNotIn("((", texto)
        self.assertIn('or "Cauã, do Transfermed"', Path(alertas.__file__).read_text(encoding="utf-8"), "remetente padrão")


class ConferenciaPorCampo(unittest.TestCase):
    """Só o campo com problema fica "conferir"; prazo final duvidoso tira o edital dos e-mails."""
    HOJE = "2026-10-29"
    IDOMED = "O calendário do edital traz a data 29/02/2027, que não existe. Confirme essa etapa com a faculdade."

    def conf(self, campos, **kw):
        return ed(status="conferir", conferir_campos=campos, inscricao_inicio="2026-10-01", **kw)

    def test_regra(self):
        self.assertFalse(gerar_site.fora_dos_emails(ed()))
        self.assertFalse(gerar_site.fora_dos_emails(self.conf({"resultado": "x"})))
        self.assertFalse(gerar_site.fora_dos_emails(self.conf({"vagas": "x"})))
        self.assertTrue(gerar_site.fora_dos_emails(self.conf({"inscricao_fim": "x"})))
        self.assertTrue(gerar_site.fora_dos_emails(self.conf({"edital": "x"})))
        self.assertTrue(gerar_site.fora_dos_emails(ed(status="conferir")), "sem campos, vale o edital inteiro")

    def test_campo_duvidoso_vai_no_email_com_o_aviso(self):
        x = self.conf({"resultado": self.IDOMED}, modalidade="exterior")
        p = {"curso": "medicina", "origem": "exterior"}
        itens = alertas.novidades(p, [x], {"x": FAC}, set(), self.HOJE)
        self.assertEqual(len(itens), 1)
        self.assertIn(self.IDOMED, alertas.email_alerta(assinante(perfil=p), itens, self.HOJE)[2])

    def test_prazo_duvidoso_fica_fora_de_alerta_e_lembrete(self):
        x = self.conf({"inscricao_fim": "datas diferentes"}, inscricao_fim="2026-10-31")
        self.assertEqual(alertas.novidades({"curso": "medicina"}, [x], {"x": FAC}, set(), self.HOJE), [])
        self.assertEqual(alertas.novidades_seguidas({"seguir": {"faculdades": ["x"]}}, [x], {"x": FAC}, set(), self.HOJE), [])
        c = nutricao.Contexto([x], {"x": FAC}, "https://s", self.HOJE)
        self.assertEqual(nutricao.lembretes_devidos(assinante(perfil={"seguir": {"lembretes": ["e1"]}}), c, set()), [])
        c2 = nutricao.Contexto([self.conf({"resultado": "x"}, inscricao_fim="2026-10-31")], {"x": FAC}, "https://s", self.HOJE)
        self.assertEqual(len(nutricao.lembretes_devidos(assinante(perfil={"seguir": {"lembretes": ["e1"]}}), c2, set())), 1)

    def test_todo_edital_publicado_conferir_diz_o_campo(self):
        for x in E:
            if gerar_site.publicavel(x) and x.get("status") == "conferir":
                self.assertTrue(x.get("conferir_campos"), f"{x['id']} ({x['faculdade_id']}) sem campo marcado")
                for campo, aviso in x["conferir_campos"].items():
                    self.assertTrue(aviso.strip(), x["id"])

    def test_ficha_do_idomed_mostra_o_aviso_ao_lado_da_etapa(self):
        x = next(y for y in E if y["id"] == "3efda2bccfd0")
        html = (gerar_site.DOCS / "edital" / gerar_site.slug_edital(x) / "index.html").read_text(encoding="utf-8")
        linha = html[html.index("<dt>Resultado e matrícula</dt>"):]
        linha = linha[:linha.index("</div>")]
        self.assertIn("29/02/2027, que não existe. Confirme essa etapa com a faculdade.", linha)
        self.assertIn("Anexo 1, p. 1", linha)
        self.assertNotIn("2027 não é bissexto", html, "a observação interna não vira aviso no topo")
        self.assertIn("data-lembrete", html, "prazo de inscrição conferido: o lembrete continua valendo")

    def test_ficha_com_prazo_duvidoso_nao_oferece_lembrete(self):
        x = next(y for y in E if y["id"] == "e7925576d6b8")  # Pitágoras: 30/10 no edital x 18/11 na página
        html = (gerar_site.DOCS / "edital" / gerar_site.slug_edital(x) / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("data-lembrete", html)
        inscr = html[html.index("<dt>Inscrições</dt>"):]
        self.assertIn("18/11/2026", inscr[:inscr.index("</div>")])

    def test_robo_marca_o_edital_inteiro_quando_ja_tinha_campo(self):
        import radar
        x = self.conf({"resultado": "x"})
        radar.marcar_conferir(x, "Retificação publicada em 2026-10-30: confira as mudanças.")
        self.assertIn("edital", x["conferir_campos"])
        self.assertTrue(gerar_site.fora_dos_emails(x))
