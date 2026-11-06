"""Avisos visíveis na ficha do edital: PDF alterado depois da conferência e PDF fora do ar no site da faculdade."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))
import gerar_site  # noqa: E402

FAC = {"id": "f", "sigla": "FAC", "site": "https://fac.br", "paginas_editais": ["https://fac.br/transferencia"]}
URL = "https://fac.br/edital.pdf"


def ed(**kw):
    return {"id": "e1", "faculdade_id": "f", "fonte_dados": "manual", "status": "ok", "url_edital": URL, "conferido_em": "2026-10-20", **kw}


class EditalAlterado(unittest.TestCase):
    def quarentena(self, desde="2026-11-05"):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        arq = Path(t.name) / "q.json"
        arq.write_text(json.dumps({"editais": {"e1": {"desde": desde, "motivo": "pdf_trocado", "url": URL}}}), encoding="utf-8")
        return arq

    def test_aviso_com_o_texto_e_a_data(self):
        e1 = gerar_site.aplicar_quarentena([ed()], self.quarentena())[0]
        with mock.patch.dict(gerar_site.PDFS_FORA, {}, clear=True):
            html = gerar_site.avisos_do_pdf(e1, FAC)
        self.assertIn("O edital foi alterado em 05/11/2026. Confira o PDF antes de enviar documentos.", html)
        self.assertIn('class="aviso-caixa"', html)

    def test_edital_continua_publicado_e_na_lista(self):
        e1 = gerar_site.aplicar_quarentena([ed()], self.quarentena())[0]
        self.assertTrue(gerar_site.publicavel(e1))

    def test_sem_alteracao_nao_ha_aviso(self):
        with mock.patch.dict(gerar_site.PDFS_FORA, {}, clear=True):
            self.assertEqual(gerar_site.avisos_do_pdf(ed(), FAC), "")

    def test_reconferido_depois_da_alteracao_tira_o_aviso(self):
        e1 = gerar_site.aplicar_quarentena([ed(conferido_em="2026-11-06")], self.quarentena())[0]
        self.assertNotIn("alterado_em", e1)


class PdfForaDoAr(unittest.TestCase):
    def retratos(self, **x):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        arq = Path(t.name) / "r.json"
        arq.write_text(json.dumps({"pdfs": {"fac.br/edital.pdf": x}}), encoding="utf-8")
        return arq

    def test_uma_falha_isolada_nao_avisa(self):
        self.assertEqual(gerar_site.pdfs_fora_do_ar(self.retratos(falhas_seguidas=1, verificado_em="2026-11-05")), {})

    def test_duas_falhas_avisam_com_a_data_da_primeira(self):
        self.assertEqual(gerar_site.pdfs_fora_do_ar(self.retratos(falhas_seguidas=2, verificado_em="2026-11-06", falha_desde="2026-11-05")),
                         {"fac.br/edital.pdf": "2026-11-05"})

    def test_sem_falha_desde_a_data_e_calculada(self):
        self.assertEqual(gerar_site.pdfs_fora_do_ar(self.retratos(falhas_seguidas=3, verificado_em="2026-11-06")),
                         {"fac.br/edital.pdf": "2026-11-04"})

    def test_aviso_na_ficha_com_link_da_pagina_de_transferencia(self):
        with mock.patch.dict(gerar_site.PDFS_FORA, {"fac.br/edital.pdf": "2026-11-05"}, clear=True):
            html = gerar_site.avisos_do_pdf(ed(), FAC)
        self.assertIn("O PDF do edital está fora do ar no site da faculdade desde 05/11/2026.", html)
        self.assertIn('href="https://fac.br/transferencia"', html)

    def test_url_com_www_e_maiuscula_casa_com_a_chave(self):
        with mock.patch.dict(gerar_site.PDFS_FORA, {"fac.br/edital.pdf": "2026-11-05"}, clear=True):
            self.assertIn("fora do ar", gerar_site.avisos_do_pdf(ed(url_edital="https://www.FAC.br/edital.pdf "), FAC))

    def test_pagina_gerada_do_edital_mostra_o_aviso(self):
        e1 = ed(modalidade="externa", semestre_ingresso="2027.1", inscricao_inicio="2026-10-01", inscricao_fim="2026-12-01", vagas=[{"semestre": "2º período", "vagas": 2}],
                documentos=["Histórico"], evidencias={"inscricao_fim": 1}, aceita_curso_exterior=False)
        fac = {**FAC, "nome": "Faculdade X", "cidade": "Cidade", "uf": "SP", "tipo": "particular"}
        with mock.patch.dict(gerar_site.PDFS_FORA, {"fac.br/edital.pdf": "2026-11-05"}, clear=True):
            pagina = gerar_site.pagina_edital(e1, fac, "2026-11-06", "og/inicio.png")
        self.assertIn("fora do ar no site da faculdade desde 05/11/2026", pagina)


class MonitorGuardaDesdeQuando(unittest.TestCase):
    def test_primeira_falha_registra_o_dia_e_a_volta_apaga(self):
        import monitor
        e1 = ed(inscricao_inicio="2026-10-01", inscricao_fim="2026-12-01")
        retratos = {}
        with mock.patch("radar.baixar_pdf", side_effect=RuntimeError("404")):
            monitor.retratar_pdfs([e1], {"f": FAC}, retratos, [], "2026-11-05")
            monitor.retratar_pdfs([e1], {"f": FAC}, retratos, [], "2026-11-06")
        x = retratos["pdfs"]["fac.br/edital.pdf"]
        self.assertEqual((x["falhas_seguidas"], x["falha_desde"]), (2, "2026-11-05"))
        with mock.patch("radar.baixar_pdf", return_value=b"%PDF conteudo"):
            monitor.retratar_pdfs([e1], {"f": FAC}, retratos, [], "2026-11-07")
        self.assertNotIn("falha_desde", retratos["pdfs"]["fac.br/edital.pdf"])
        self.assertEqual(retratos["pdfs"]["fac.br/edital.pdf"]["falhas_seguidas"], 0)


if __name__ == "__main__":
    unittest.main()
