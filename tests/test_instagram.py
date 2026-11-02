"""Pacote do Instagram: sai só da base, sem nome de pessoa, com a chamada para o diagnóstico e as fontes para conferir."""
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import instagram  # noqa: E402

HOJE = "2026-11-02"


class Pacote(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        instagram.SAIDA = cls.tmp
        cls.pasta, cls.feitos = instagram.gerar(HOJE)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_tres_posts_1080x1350(self):
        from PIL import Image
        self.assertGreaterEqual(len(self.feitos), 8)  # 9 formatos; só sai o que tem dado suficiente na base
        for png in self.feitos:
            self.assertEqual(Image.open(png).size, (1080, 1350))

    def test_legenda_leva_ao_diagnostico_com_origem_e_manda_conferir(self):
        for txt in self.pasta.glob("*.legenda.txt"):
            t = txt.read_text(encoding="utf-8")
            self.assertIn("transfermed.com.br/diagnostico/?origem=instagram", t)
            self.assertRegex(t.lower(), r"edital oficial|no edital")

    def test_cada_post_lista_a_fonte_para_o_dono_conferir(self):
        leia = (self.pasta / "LEIA-ME.md").read_text(encoding="utf-8")
        self.assertIn("Nada foi publicado", leia)
        self.assertEqual(len(re.findall(r"https://", leia)) >= 3, True)

    def test_so_edital_conferido_aberto_e_com_prazo_firme_entra(self):
        editais, facs = instagram._dados()
        for e in instagram.abertos(editais, facs, HOJE):
            self.assertEqual(e["fonte_dados"], "manual")
            self.assertGreaterEqual(e["inscricao_fim"], HOJE)
            self.assertNotIn("inscricao_fim", e.get("conferir_campos") or {})

    def test_ordem_e_por_prazo_nao_por_ranking(self):
        editais, facs = instagram._dados()
        fins = [e["inscricao_fim"] for e in instagram.abertos(editais, facs, HOJE)]
        self.assertEqual(fins, sorted(fins))

    def test_a_restricao_do_post_tem_pagina_registrada(self):
        editais, facs = instagram._dados()
        achado = instagram._restricao(editais, facs, HOJE)
        self.assertIsNotNone(achado)
        e, texto, pag = achado
        self.assertTrue(pag)
        self.assertIn(texto, e["outras_restricoes"])

    def test_nada_de_dado_pessoal_nas_legendas(self):
        for txt in list(self.pasta.glob("*.txt")) + [self.pasta / "LEIA-ME.md"]:
            t = txt.read_text(encoding="utf-8")
            self.assertNotRegex(t, r"\d{3}\.\d{3}\.\d{3}-\d{2}")
            self.assertNotRegex(t, r"[^\s@]+@[^\s@]+\.[a-z]{2,}")


if __name__ == "__main__":
    unittest.main()
