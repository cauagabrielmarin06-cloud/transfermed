"""Auditoria de precisão: a comparação aceita formas equivalentes e pega divergência de verdade."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import auditoria  # noqa: E402

N = auditoria.normalizar


class Normalizacao(unittest.TestCase):
    def test_formas_equivalentes(self):
        self.assertEqual(N("taxa_inscricao", 150), N("taxa_inscricao", "150.00"))
        self.assertEqual(N("taxa_inscricao", 150.0), N("taxa_inscricao", "R$ 150,00"))
        self.assertEqual(N("numero_edital", "Edital nº 034/2026, de 04/09/2026"), N("numero_edital", "34/2026"))
        self.assertEqual(N("vagas_total", 10), N("vagas_total", "10"))
        self.assertEqual(N("inscricao_fim", "2026-11-23"), N("inscricao_fim", " 2026-11-23 "))
        self.assertEqual(N("aceita_curso_exterior", None), N("aceita_curso_exterior", "nao_consta"))

    def test_divergencias_reais_aparecem(self):
        self.assertNotEqual(N("taxa_inscricao", 150), N("taxa_inscricao", 190))
        self.assertNotEqual(N("inscricao_fim", "2026-11-23"), N("inscricao_fim", "2026-11-22"))
        self.assertNotEqual(N("numero_edital", "034/2026"), N("numero_edital", "035/2026"))


class Fluxo(unittest.TestCase):
    def test_comparar_conta_acertos_e_lista_divergencias(self):
        import json
        import tempfile
        raiz = Path(tempfile.mkdtemp())
        auditoria.RAIZ_AUDITORIA = raiz
        (raiz / "2099-01").mkdir()
        (raiz / "2099-01" / "gabarito.json").write_text(json.dumps({"e1": {"inscricao_fim": "2099-02-01", "taxa_inscricao": 100.0, "data_prova": None}}))
        (raiz / "2099-01" / "respostas_cego.json").write_text(json.dumps({"e1": {"inscricao_fim": "2099-02-01", "taxa_inscricao": "120", "data_prova": "sem_prova"}}))
        r = auditoria.comparar("2099-01")
        self.assertEqual((r["campos_comparados"], r["acertos"], r["taxa_acerto_pct"]), (3, 2, 66.7))
        self.assertEqual(r["divergencias"][0]["campo"], "taxa_inscricao")


if __name__ == "__main__":
    unittest.main()
