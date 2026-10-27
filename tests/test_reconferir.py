"""Testes da reconferência por sorteio (qa/reconferir.py)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "qa"))
import reconferir  # noqa: E402


class Datas(unittest.TestCase):
    def test_formatos_de_data_dos_editais(self):
        self.assertTrue(reconferir.data_na_pagina("2026-09-24", "Inscrições 24/09 à 18/11/2026"))  # Unime: ano só no fim
        self.assertTrue(reconferir.data_na_pagina("2026-11-18", "Inscrições 24/09 à 18/11/2026"))
        self.assertTrue(reconferir.data_na_pagina("2026-03-23", "no período de 23 de Março de 2026 a 22 de Junho"))
        self.assertTrue(reconferir.data_na_pagina("2026-10-26", "de 26/10/26 a 29/10/26"))
        self.assertFalse(reconferir.data_na_pagina("2026-09-25", "Inscrições 24/09 à 18/11/2026"))

    def test_vagas_e_taxa(self):
        e = {"evidencias": {"vagas": 1, "taxa_inscricao": 1}, "vagas": [{"semestre": "2º", "vagas": 5}], "taxa_inscricao": 250.0}
        self.assertEqual([r[3] for r in reconferir.conferir(e, {1: "05 (cinco) vagas. Taxa de R$ 250,00"})], ["confere", "confere"])
        self.assertEqual([r[3] for r in reconferir.conferir(e, {1: "15 vagas. Taxa de R$ 300,00"})], ["não achei", "não achei"])
