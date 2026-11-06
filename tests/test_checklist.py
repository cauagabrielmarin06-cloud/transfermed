"""Checklist de documentos por edital: só vai ao ar fechado (página em todo item, prazo em toda etapa, nenhum "conferir")."""
import json
import sys
import unittest
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))
import gerar_site  # noqa: E402

ED = json.loads((PASTA / "data" / "editais.json").read_text(encoding="utf-8"))
COM = [e for e in ED if e.get("checklist")]


def base(**kw):
    return {"id": "e1", "checklist": {"conferido_em": "2026-11-06", "etapas": [
        {"titulo": "Inscrição", "prazo": "até 01/12/2026", "itens": [{"texto": "Histórico", "pagina": "p. 4 (item 2.3.3)", "obs": "Com assinatura"}]}],
        "aviso": "Leve os originais."}, **kw}


class ChecklistsPublicados(unittest.TestCase):
    def test_existe_ao_menos_um_e_todos_estao_fechados(self):
        self.assertGreaterEqual(len(COM), 2)
        for e in COM:
            self.assertEqual(gerar_site.problemas_do_checklist(e), [], e["id"])

    def test_edital_com_checklist_e_publicavel_e_a_pagina_traz_pagina_e_data(self):
        for e in COM:
            self.assertTrue(gerar_site.publicavel(e))
            html = (PASTA / "docs" / "edital" / f"{gerar_site.slug_edital(e)}" / "index.html").read_text(encoding="utf-8")
            self.assertIn("Checklist de documentos e prazos", html)
            self.assertIn(f"Conferido nos PDFs do edital em {gerar_site.fmt(e['checklist']['conferido_em'])}", html)
            self.assertIn("Prazo:", html)
            self.assertNotIn("conferir)", html.split("Checklist de documentos e prazos")[1].split("</section>")[0].lower())

    def test_o_que_nao_fechou_continua_em_rascunho_fora_do_ar(self):
        uva = next(e for e in ED if e["id"] == "1e0e3121b570")
        self.assertNotIn("checklist", uva)  # título de eleitor com asterisco sem explicação no edital
        html = (PASTA / "docs" / "edital" / gerar_site.slug_edital(uva) / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("Checklist de documentos e prazos", html)


class RegrasDoValidador(unittest.TestCase):
    def test_checklist_completo_passa_e_e_renderizado(self):
        self.assertEqual(gerar_site.problemas_do_checklist(base()), [])
        html = gerar_site.bloco_checklist(base())
        self.assertIn("(p. 4 (item 2.3.3))", html)
        self.assertIn("Conferido nos PDFs do edital em 06/11/2026", html)

    def test_item_sem_pagina_trava(self):
        e = base()
        e["checklist"]["etapas"][0]["itens"][0]["pagina"] = ""
        self.assertTrue(gerar_site.problemas_do_checklist(e))
        self.assertEqual(gerar_site.bloco_checklist(e), "")

    def test_item_com_conferir_trava(self):
        e = base()
        e["checklist"]["etapas"][0]["itens"][0]["obs"] = "Conferir a data de entrega"
        self.assertTrue(any("a conferir" in p for p in gerar_site.problemas_do_checklist(e)))
        self.assertEqual(gerar_site.bloco_checklist(e), "")

    def test_sem_data_de_conferencia_ou_sem_prazo_trava(self):
        e = base()
        e["checklist"]["conferido_em"] = None
        self.assertEqual(gerar_site.bloco_checklist(e), "")
        e = base()
        e["checklist"]["etapas"][0]["prazo"] = ""
        self.assertTrue(gerar_site.problemas_do_checklist(e))

    def test_sem_checklist_nada_aparece(self):
        self.assertEqual(gerar_site.bloco_checklist({"id": "x"}), "")


if __name__ == "__main__":
    unittest.main()
