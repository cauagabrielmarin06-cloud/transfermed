"""Ficha da faculdade: bloco "Quando costuma abrir" (10/11/2026, especialização item 1).

Regras: só aparece com 2 ou mais editais anteriores (encerrados) conferidos à mão e com a data de início das inscrições confirmada no PDF
(com a página); não faz previsão; liga cada data ao edital antigo. Menos de 2: nada aparece."""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gerar_site as g  # noqa: E402
from tests.test_site import data_do_site  # noqa: E402

HOJE = "2026-11-10"


def ed(i, ini, fim, sem, **mais):
    base = {"id": f"{i:012x}", "faculdade_id": "fac-x", "modalidade": "externa", "semestre_ingresso": sem, "fonte_dados": "manual", "status": "ok",
            "inscricao_inicio": ini, "inscricao_fim": fim, "url_edital": f"https://x.br/{i}.pdf", "evidencias": {"inscricao_inicio": 2}}
    base.update(mais)
    return base


ANTIGOS = [ed(1, "2025-02-10", "2025-02-28", "2025.1"), ed(2, "2025-08-11", "2025-08-29", "2025.2"), ed(3, "2026-02-09", "2026-02-27", "2026.1")]


class Regras(unittest.TestCase):
    def html(self, eds):
        return g.bloco_aberturas(eds, HOJE, "../../")

    def test_com_dois_ou_mais_mostra_cada_data_com_link_e_pagina(self):
        h = self.html(ANTIGOS)
        self.assertIn("Quando costuma abrir", h)
        for x in ANTIGOS:
            self.assertIn(f'href="../../edital/{g.slug_edital(x)}/"', h)
            self.assertIn(g.fmt(x["inscricao_inicio"]), h)
        self.assertEqual(h.count("<li>"), 3)
        self.assertIn('<span class="pag">p. 2</span>', h)
        # do mais novo para o mais antigo
        self.assertLess(h.index("09/02/2026"), h.index("11/08/2025"))
        self.assertLess(h.index("11/08/2025"), h.index("10/02/2025"))

    def test_com_menos_de_dois_nao_mostra_nada(self):
        self.assertEqual(self.html([]), "")
        self.assertEqual(self.html(ANTIGOS[:1]), "")

    def test_nao_faz_previsao(self):
        h = self.html(ANTIGOS)
        self.assertIn("Sem previsão", h)
        for proibido in ("deve abrir", "vai abrir", "próximo edital abre em", "abrirá", "provável", "previsto para"):
            self.assertNotIn(proibido, h.lower())
        self.assertFalse(re.search(r"\b2027\b", h))   # nenhuma data futura inventada

    def test_edital_ainda_aberto_ou_futuro_nao_conta(self):
        aberto = ed(9, "2026-11-01", "2026-12-01", "2027.1")
        futuro = ed(10, "2026-12-10", "2026-12-20", "2027.1")
        self.assertEqual(self.html(ANTIGOS[:1] + [aberto, futuro]), "")
        self.assertEqual(len(g.aberturas_anteriores(ANTIGOS + [aberto, futuro], HOJE)), 3)

    def test_so_conta_o_que_foi_conferido_a_mao(self):
        robo = ed(9, "2025-03-01", "2025-03-20", "2025.1", fonte_dados="regras")
        self.assertEqual(self.html(ANTIGOS[:1] + [robo]), "")

    def test_data_em_conferir_ou_sem_pagina_ou_edital_em_duvida_nao_conta(self):
        em_conferir = ed(9, "2025-03-01", "2025-03-20", "2025.1", conferir_campos={"inscricao_inicio": "o edital e o aditivo divergem"})
        sem_pagina = ed(10, "2025-04-01", "2025-04-20", "2025.1", evidencias={})
        em_duvida = ed(11, "2025-05-01", "2025-05-20", "2025.1", conferir_campos={"edital": "retificação publicada"})
        sem_data = ed(12, None, "2025-05-20", "2025.1")
        for ruim in (em_conferir, sem_pagina, em_duvida, sem_data):
            self.assertEqual(self.html(ANTIGOS[:1] + [ruim]), "", ruim["id"])
        # dúvida em OUTRO campo não atrapalha a data de início
        outro = ed(13, "2025-06-01", "2025-06-20", "2025.2", conferir_campos={"vagas": "tabela confusa"})
        self.assertNotEqual(self.html(ANTIGOS[:1] + [outro]), "")

    def test_edital_sem_data_de_fim_encerrado_pela_situacao_tambem_conta(self):
        antigo = ed(14, "2025-03-01", None, "2025.1", situacao="encerrado")
        self.assertEqual(len(g.aberturas_anteriores([antigo], HOJE)), 1)

    def test_pagina_com_aspas_e_html_e_escapada(self):
        x = ed(15, "2025-03-01", "2025-03-20", "2025.1", evidencias={"inscricao_inicio": "2 <b>(item 3)</b>"})
        h = self.html([x, ANTIGOS[0]])
        self.assertNotIn("<b>", h)


class NoSiteGerado(unittest.TestCase):
    """O que está em docs/faculdade/*/index.html bate com a base: bloco só nas fichas com 2+ aberturas anteriores confirmadas."""

    @classmethod
    def setUpClass(cls):
        import json
        cls.hoje = data_do_site()
        cls.faculdades = json.loads((g.PASTA / "data" / "faculdades.json").read_text(encoding="utf-8"))
        cls.editais = json.loads((g.PASTA / "data" / "editais.json").read_text(encoding="utf-8"))
        if isinstance(cls.faculdades, dict):
            cls.faculdades = cls.faculdades.get("faculdades", list(cls.faculdades.values()))
        if isinstance(cls.editais, dict):
            cls.editais = cls.editais.get("editais", list(cls.editais.values()))

    def pagina(self, fid):
        return (g.DOCS / "faculdade" / fid / "index.html").read_text(encoding="utf-8")

    def test_bloco_so_nas_fichas_com_duas_aberturas_e_com_um_link_por_edital_antigo(self):
        com = sem = 0
        for f in self.faculdades:
            antigos = g.aberturas_anteriores([x for x in self.editais if x["faculdade_id"] == f["id"]], self.hoje)
            html = self.pagina(f["id"])
            if len(antigos) >= 2:
                com += 1
                self.assertIn('<h2 id="quando-abre">Quando costuma abrir</h2>', html, f["id"])
                for x in antigos:
                    self.assertIn(f'href="../../edital/{g.slug_edital(x)}/"', html, (f["id"], x["id"]))
                    self.assertIn(g.fmt(x["inscricao_inicio"]), html)
            else:
                sem += 1
                self.assertNotIn("quando-abre", html, f["id"])
        self.assertGreater(com + sem, 0)

    def test_etiqueta_costuma_abrir_so_onde_ha_o_bloco_com_os_links(self):
        """A etiqueta "Costuma abrir em <mês>" segue a mesma regra do bloco: 2 ou mais editais anteriores confirmados, cada um com link na ficha."""
        for f in self.faculdades:
            html = self.pagina(f["id"])
            tem_etiqueta = "Costuma abrir em" in html or "costuma abrir em" in html.replace("quando costuma abrir", "")
            if tem_etiqueta:
                self.assertIn('id="quando-abre"', html, f["id"])
        # regra no gerador: mês manual (meses_costuma_abrir) sem 2 editais confirmados não vira etiqueta
        import json
        dados = (g.DOCS / "dados.js").read_text(encoding="utf-8")
        for f in self.faculdades:
            if f.get("meses_costuma_abrir") and len(g.aberturas_anteriores([x for x in self.editais if x["faculdade_id"] == f["id"]], self.hoje)) < 2:
                self.assertNotIn("costuma abrir em", self.pagina(f["id"]).replace("Quando costuma abrir", "").replace("quando costuma abrir", ""), f["id"])
        self.assertTrue(dados)

    def test_todo_link_do_bloco_aponta_para_uma_ficha_de_edital_que_existe(self):
        for f in self.faculdades:
            html = self.pagina(f["id"])
            m = re.search(r'<ul class="aberturas">(.*?)</ul>', html, re.S)
            if not m:
                continue
            for slug in re.findall(r'href="\.\./\.\./edital/([^/"]+)/"', m.group(1)):
                self.assertTrue((g.DOCS / "edital" / slug / "index.html").exists(), (f["id"], slug))


if __name__ == "__main__":
    unittest.main()
