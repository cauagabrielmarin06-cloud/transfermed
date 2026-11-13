"""B2 (12/11/2026): o bloco único "Não perca o prazo" da ficha do edital (e-mail + agenda), o .ics de evento único e o
consentimento (nunca pré-marcado, texto completo atrás de "O que vou receber")."""
import json
import re
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gerar_site  # noqa: E402

FAC = {"id": "fac-x", "nome": "Faculdade X", "sigla": "FACX", "cidade": "Cidade", "uf": "SP", "tipo": "particular", "site": "https://fac.br"}


def edital(**kw):
    base = {"id": "abc123def456", "faculdade_id": "fac-x", "modalidade": "externa", "semestre_ingresso": "2027.1", "fonte_dados": "manual",
            "url_edital": "https://fac.br/edital.pdf", "inscricao_inicio": "2026-11-01", "inscricao_fim": "2026-12-03",
            "vagas": [{"semestre": "2º período", "vagas": 2}], "documentos": ["Histórico"], "evidencias": {"inscricao_fim": 4},
            "aceita_curso_exterior": False, "conferido_em": "2026-11-10"}
    base.update(kw)
    return base


def pagina(ed, hoje):
    return gerar_site.pagina_edital(ed, FAC, hoje, "og/inicio.png")


class ModoDoBloco(unittest.TestCase):
    def test_modos(self):
        self.assertEqual(gerar_site.modo_lembrete(edital(), "2026-11-12"), "completo")
        self.assertEqual(gerar_site.modo_lembrete(edital(), "2026-12-01"), "agenda", "a 2 dias: o lembrete por e-mail já não cabe")
        self.assertEqual(gerar_site.modo_lembrete(edital(), "2026-12-03"), "agenda", "no último dia")
        self.assertEqual(gerar_site.modo_lembrete(edital(), "2026-12-04"), "", "encerrado")
        self.assertEqual(gerar_site.modo_lembrete(edital(inscricao_fim=None), "2026-11-12"), "email", "sem prazo conferido")
        self.assertEqual(gerar_site.modo_lembrete(edital(status="conferir", conferir_campos={"inscricao_fim": "x"}), "2026-11-12"), "email", "prazo em conferir")
        self.assertEqual(gerar_site.modo_lembrete(edital(fluxo_continuo=True), "2026-11-12"), "", "fluxo contínuo")


class BlocoNaFicha(unittest.TestCase):
    def test_completo_tem_as_duas_opcoes_e_o_texto_novo(self):
        html = pagina(edital(), "2026-11-12")
        self.assertEqual(html.count('id="lembrete"'), 1)
        for esperado in ("Não perca o prazo da FACX", "21</b><span>dias para o fim das inscrições", "Hoje · 12/11", "Fecha · 03/12",
                         "Como você quer ser lembrado?", "Por e-mail", "Recomendado", "Na agenda do celular",
                         "7 dias e 2 dias antes, com a lista de documentos deste edital.", "Me lembre do prazo",
                         "Grátis · sem spam · ", "na hora", "Adicionar à minha agenda", "qui, 03/12/2026 · alarmes 7 e 2 dias antes",
                         "Vai prestar mais de uma etapa?", "Seguir todos os prazos da FACX na agenda", 'href="lembrete.ics" download'):
            self.assertIn(esperado, html)
        self.assertLess(html.index("t-quando"), html.index('id="lembrete"'), "o bloco fica na parte Quando")
        self.assertLess(html.index('id="lembrete"'), html.index("t-preciso"))

    def test_substitui_o_que_havia(self):
        html = pagina(edital(), "2026-11-12")
        for velho in ("Salvar o último dia no Google Agenda", "Assinar os prazos da", "Como assinar no Google", "Me lembre 7 e 2 dias antes do prazo",
                      'class="agenda"', "agenda-ajuda"):
            self.assertNotIn(velho, html)

    def test_formulario_unico_e_ids_unicos(self):
        for modo_hoje, ed in (("2026-11-12", edital()), ("2026-11-12", edital(inscricao_fim=None)), ("2026-12-02", edital()), ("2026-12-05", edital())):
            html = pagina(ed, modo_hoje)
            ids = re.findall(r'\sid="([^"]+)"', html)
            self.assertEqual(sorted({i for i in ids if ids.count(i) > 1}), [], f"id repetido em {modo_hoje} {ed.get('inscricao_fim')}")
            for ident in ("form-alerta", "email-alerta", "consentimento", "alerta-msg", "alerta-passo2", "alerta"):
                self.assertEqual(html.count(f'id="{ident}"'), 1, f"{ident} em {modo_hoje} {ed.get('inscricao_fim')}")

    def test_consentimento_nunca_pre_marcado_e_texto_completo(self):
        html = pagina(edital(), "2026-11-12")
        caixa = re.search(r'<input type="checkbox" id="consentimento"[^>]*>', html).group(0)
        self.assertNotIn("checked", caixa)
        self.assertIn("Quero receber os lembretes e alertas de editais por e-mail. Cancelo em um clique.", html)
        detalhe = re.search(r'<details class="consent-ver">.*?</details>', html, re.S).group(0)
        self.assertIn("O que vou receber", detalhe)
        self.assertIn(gerar_site.e(gerar_site.CONSENTIMENTO), detalhe, "texto de consentimento completo, sem cortes")
        self.assertNotIn(" open", detalhe.split(">")[0])

    def test_formulario_leva_o_pedido_do_lembrete(self):
        html = pagina(edital(), "2026-11-12")
        form = re.search(r'<form id="form-alerta"[^>]*>', html).group(0)
        self.assertIn('data-contexto="edital_lembrete"', form)
        self.assertIn('data-lembrete="abc123def456"', form)
        self.assertIn('data-seguir-faculdade="fac-x"', form)

    def test_sem_prazo_conferido_so_o_email(self):
        html = pagina(edital(inscricao_fim=None), "2026-11-12")
        self.assertIn("Avisamos quando ela for confirmada", html)
        self.assertNotIn("Na agenda do celular", html)
        self.assertNotIn("dias para o fim", html)
        self.assertNotIn("Recomendado", html)
        self.assertIn('data-contexto="edital_seguir"', html)
        self.assertNotIn("data-lembrete=", html)

    def test_perto_do_fim_so_a_agenda_e_a_chamada_do_proximo_edital(self):
        html = pagina(edital(), "2026-12-01")
        self.assertIn("Na agenda do celular", html)
        self.assertNotIn("Por e-mail", html)
        self.assertIn("2</b><span>dias para o fim", html)
        self.assertIn("Avise-me quando a FACX abrir o próximo edital", html, "o formulário do fim da página continua")
        self.assertIn("alarme", html)

    def test_encerrado_so_a_chamada_do_fim_da_pagina(self):
        html = pagina(edital(), "2026-12-05")
        self.assertNotIn('id="lembrete"', html)
        self.assertIn("Avise-me quando a FACX abrir o próximo edital", html)

    def test_contador_so_aparece_uma_vez(self):
        html = pagina(edital(), "2026-11-12")
        self.assertEqual(html.count('class="contador'), 1)
        em_breve = pagina(edital(inscricao_inicio="2026-11-20"), "2026-11-12")
        self.assertEqual(em_breve.count('class="contador'), 2, "em breve: a da abertura na linha do tempo e a do fim no bloco")


class BarraDoPrazo(unittest.TestCase):
    """B3: barra fixa do celular, só na ficha aberta com prazo conferido."""

    def test_texto_e_vagas(self):
        html = pagina(edital(), "2026-11-12")
        barra = re.search(r'<div class="barra-prazo".*?</div>', html, re.S).group(0)
        self.assertIn("FACX", barra)
        self.assertIn("fecha em 21 dias", barra)
        self.assertIn("03/12 · 2 vagas", barra)
        self.assertIn('href="#lembrete"', barra)
        self.assertIn("Me lembre", barra)
        self.assertIn(" hidden", barra.split(">")[0], "nasce escondida: só o app.js mostra depois do scroll")
        self.assertIn('data-barra-prazo="1"', html, "o body ganha o padding")
        self.assertNotIn("pop", barra.lower())

    def test_hoje_e_um_dia(self):
        self.assertIn("fecha hoje", pagina(edital(), "2026-12-03"))
        self.assertIn("fecha em 1 dia<", pagina(edital(), "2026-12-02"))

    def test_vagas_em_conferir_ou_sem_numero_nao_entram(self):
        sem = pagina(edital(vagas=[]), "2026-11-12")
        self.assertNotIn("vagas</span>", re.search(r'<div class="barra-prazo".*?</div>', sem, re.S).group(0))
        self.assertIn("03/12<", re.search(r'<div class="barra-prazo".*?</div>', sem, re.S).group(0))
        conferir = pagina(edital(status="conferir", conferir_campos={"vagas": "contradição"}), "2026-11-12")
        self.assertNotIn("2 vagas", re.search(r'<div class="barra-prazo".*?</div>', conferir, re.S).group(0))

    def test_sem_prazo_conferido_encerrado_e_fluxo_ficam_sem_barra(self):
        for ed, hoje in ((edital(inscricao_fim=None), "2026-11-12"), (edital(), "2026-12-05"), (edital(fluxo_continuo=True), "2026-11-12"),
                         (edital(status="conferir", conferir_campos={"inscricao_fim": "x"}), "2026-11-12")):
            html = pagina(ed, hoje)
            self.assertNotIn('id="barra-prazo"', html)
            self.assertNotIn("data-barra-prazo", html)


class ArquivoIcs(unittest.TestCase):
    def ics(self, ed, hoje):
        import icalendar
        return icalendar.Calendar.from_ical(gerar_site.ics_lembrete(ed, FAC, hoje))

    def test_evento_unico_com_alarmes_e_link(self):
        cal = self.ics(edital(), "2026-11-12")
        eventos = [c for c in cal.walk() if c.name == "VEVENT"]
        self.assertEqual(len(eventos), 1)
        ev = eventos[0]
        self.assertEqual(ev["DTSTART"].dt, date(2026, 12, 3))
        self.assertEqual(ev["DTEND"].dt, date(2026, 12, 4))
        self.assertEqual(str(ev["SUMMARY"]), "FACX Cidade · último dia de inscrição")
        self.assertIn("https://fac.br/edital.pdf", str(ev["DESCRIPTION"]))
        self.assertIn("/edital/", str(ev["URL"]))
        gatilhos = [a["TRIGGER"].dt for a in ev.subcomponents if a.name == "VALARM"]
        # 7 e 2 dias antes, às 9h (o dia começa à meia-noite: 6 dias e 15 h, 1 dia e 15 h)
        self.assertEqual(gatilhos, [-timedelta(days=6, hours=15), -timedelta(days=1, hours=15)])

    def test_alarme_que_ja_passou_nao_entra(self):
        self.assertEqual([n for n, _ in gerar_site.alarmes_lembrete(edital(), "2026-11-12")], [7, 2])
        self.assertEqual([n for n, _ in gerar_site.alarmes_lembrete(edital(), "2026-11-30")], [2])
        self.assertEqual(gerar_site.alarmes_lembrete(edital(), "2026-12-01"), [])
        cal = self.ics(edital(), "2026-11-30")
        ev = [c for c in cal.walk() if c.name == "VEVENT"][0]
        self.assertEqual(len([a for a in ev.subcomponents if a.name == "VALARM"]), 1)

    def test_prazo_contraditorio_usa_a_data_mais_cedo(self):
        ed = edital(inscricao_fim="2026-11-27", prazo_contraditorio={"datas": [{"data": "2026-12-03", "pagina": 2}, {"data": "2026-11-27", "pagina": 5}]})
        self.assertEqual(gerar_site.prazo_seguro(ed), "2026-11-27")
        ev = [c for c in self.ics(ed, "2026-11-12").walk() if c.name == "VEVENT"][0]
        self.assertEqual(ev["DTSTART"].dt, date(2026, 11, 27))


class SiteGerado(unittest.TestCase):
    """O que está em docs/: cada ficha com o bloco completo ou de agenda tem o seu lembrete.ics, e nenhuma tem dois formulários."""

    def test_toda_ficha_com_agenda_tem_o_ics_e_um_formulario_so(self):
        docs = gerar_site.DOCS
        for pasta in sorted((docs / "edital").iterdir()):
            html = (pasta / "index.html").read_text(encoding="utf-8")
            self.assertLessEqual(html.count('id="form-alerta"'), 1, pasta.name)
            if "Na agenda do celular" in html:
                self.assertTrue((pasta / "lembrete.ics").exists(), pasta.name)
                self.assertIn('href="lembrete.ics" download', html)


if __name__ == "__main__":
    unittest.main()
