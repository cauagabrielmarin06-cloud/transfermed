"""Testes dos e-mails novos (nutricao.py), da simulação sem ALERTAS_ATIVOS e da isca em PDF."""
import json
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
        self.assertEqual(r["novos"]["sequencia"], 1)
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
                self.assertNotEqual(x.get("status"), "conferir")
                self.assertFalse(x.get("fluxo_continuo"))
                self.assertGreaterEqual(x["inscricao_fim"], hoje)
