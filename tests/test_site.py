"""Testes do gerador do site. Rodar com: python -m unittest discover tests"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gerar_site  # noqa: E402


class Publicacao(unittest.TestCase):
    def test_so_publica_conferido_a_mao(self):
        self.assertTrue(gerar_site.publicavel({"fonte_dados": "manual"}))
        self.assertFalse(gerar_site.publicavel({"fonte_dados": "regras"}))
        self.assertFalse(gerar_site.publicavel({"fonte_dados": "ia"}))


class NovosDetectados(unittest.TestCase):
    HOJE = "2026-10-24"

    def test_novo_do_robo_aparece_sem_dados(self):
        self.assertTrue(gerar_site.novo_detectado({"fonte_dados": "regras", "detectado_em": "2026-10-20"}, self.HOJE))

    def test_nao_mostra_conferido_antigo_ou_encerrado(self):
        self.assertFalse(gerar_site.novo_detectado({"fonte_dados": "manual", "detectado_em": "2026-10-20"}, self.HOJE))
        self.assertFalse(gerar_site.novo_detectado({"fonte_dados": "regras"}, self.HOJE))  # carga inicial, sem data
        self.assertFalse(gerar_site.novo_detectado({"fonte_dados": "regras", "detectado_em": "2026-06-01"}, self.HOJE))
        self.assertFalse(gerar_site.novo_detectado({"fonte_dados": "regras", "detectado_em": "2026-10-20",
                                                    "inscricao_fim": "2026-10-01"}, self.HOJE))

    def test_robo_ativo_exige_pagina_sem_pendencia(self):
        self.assertTrue(gerar_site.com_robo({"paginas_editais": ["https://x"]}))
        self.assertFalse(gerar_site.com_robo({"paginas_editais": ["https://x"], "pendente": "achar a página certa"}))
        self.assertFalse(gerar_site.com_robo({"paginas_editais": []}))


class Situacao(unittest.TestCase):
    HOJE = "2026-10-24"

    def test_urgencia_real(self):
        self.assertEqual(gerar_site.texto_situacao({"inscricao_fim": "2026-10-25"}, self.HOJE)[0], "alerta")
        self.assertEqual(gerar_site.texto_situacao({"inscricao_fim": "2026-10-29"}, self.HOJE),
                         ("aviso", "Inscrições encerram em 5 dias"))
        self.assertEqual(gerar_site.texto_situacao({"inscricao_fim": "2026-12-03"}, self.HOJE)[0], "ok")
        self.assertEqual(gerar_site.texto_situacao({"inscricao_fim": "2026-07-06"}, self.HOJE)[0], "")


class Calendario(unittest.TestCase):
    def test_linhas_no_maximo_75_bytes(self):
        linha = "DESCRIPTION:Confira sempre o edital oficial: https://exemplo.com.br/" + "a" * 120
        for parte in gerar_site.dobrar(linha).split("\r\n"):
            self.assertLessEqual(len(parte.encode("utf-8")), 75)

    def test_ics_tem_prazos(self):
        ed = {"id": "x1", "url_edital": "https://exemplo/edital.pdf", "inscricao_inicio": "2026-10-01",
              "inscricao_fim": "2026-10-29", "data_prova": "2026-10-31"}
        ics = gerar_site.ics_estatico(ed, {"sigla": "UB"})
        self.assertIn("DTSTART;VALUE=DATE:20261029", ics)
        self.assertIn("TRIGGER:-P3D", ics)
        self.assertEqual(ics.count("BEGIN:VEVENT"), 3)


class Mapa(unittest.TestCase):
    def test_projecao_bate_com_o_javascript(self):
        # Fernandópolis: x = (lon + 74) * 10 ; y = (6 - lat) * 10
        x, y = gerar_site.proj(-20.2836, -50.2463)
        self.assertAlmostEqual(x, 237.537, places=2)
        self.assertAlmostEqual(y, 262.836, places=2)


if __name__ == "__main__":
    unittest.main()


class Exterior(unittest.TestCase):
    def test_sugestoes_do_exterior_sem_repetir_e_com_pais(self):
        lista = json.loads((Path(__file__).resolve().parent.parent / "data" / "faculdades_exterior.json").read_text(encoding="utf-8"))["faculdades"]
        nomes = [x["nome"] for x in lista]
        self.assertEqual(len(nomes), len(set(nomes)))
        self.assertTrue(all(x["pais"] in {"Paraguai", "Bolívia", "Argentina", "Uruguai"} for x in lista))
