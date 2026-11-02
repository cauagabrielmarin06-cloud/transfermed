"""Boletim para grupos: só dado conferido, sem ranking, com o link de origem de grupo e o aviso de conferir o edital."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import boletim  # noqa: E402
import instagram  # noqa: E402

HOJE = "2026-11-02"


class Boletim(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.editais, cls.facs = instagram._dados()
        cls.texto = boletim.montar(cls.editais, cls.facs, HOJE)

    def test_leva_o_link_de_grupo_e_manda_conferir(self):
        self.assertIn("transfermed.com.br/diagnostico/?origem=grupo", self.texto)
        self.assertIn("Confira sempre o edital oficial", self.texto)

    def test_numero_de_abertos_vem_da_base(self):
        n = len(instagram.abertos(self.editais, self.facs, HOJE))
        self.assertIn(f"Hoje há {n} editais abertos", self.texto)

    def test_ordem_por_prazo_sem_ranking(self):
        import re
        datas = re.findall(r"até (\d\d/\d\d)", self.texto.split("Encerram nos próximos 7 dias:")[1].split("\n\n")[0])
        chave = [d[3:] + d[:2] for d in datas]
        self.assertEqual(chave, sorted(chave))

    def test_so_o_que_esta_na_base_nada_de_dado_pessoal(self):
        import re
        self.assertNotRegex(self.texto, r"[^\s@]+@[^\s@]+\.[a-z]{2,}")
        self.assertNotRegex(self.texto, r"\d{3}\.\d{3}\.\d{3}-\d{2}")
        for sigla in re.findall(r"• ([^ (]+)", self.texto):
            self.assertTrue(any(f["sigla"] == sigla for f in self.facs.values()), sigla)

    def test_cabe_no_whatsapp(self):
        self.assertLess(len(self.texto), 1800)


if __name__ == "__main__":
    unittest.main()
