"""Testes do histórico e da previsão de abertura. Rodar com: python -m unittest discover tests"""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import historico  # noqa: E402


def ed(fid, sem, inicio, **extra):
    return {"faculdade_id": fid, "semestre_ingresso": sem, "inscricao_inicio": inicio, "fonte_dados": "manual", **extra}


class Previsao(unittest.TestCase):
    HOJE = date(2026, 10, 28)

    def test_tres_ciclos_proximos_dao_confianca_alta(self):
        E = [ed("x", "2025.1", "2024-08-05"), ed("x", "2026.1", "2025-08-12"), ed("x", "2027.1", "2026-08-01")]
        p = historico.prever(E, self.HOJE)["x"][0]
        self.assertEqual(p["confianca"], "alta")
        self.assertEqual(p["ingresso"], "2028.1")
        self.assertTrue("2027-07-15" <= p["janela_inicio"] <= p["janela_fim"] <= "2027-08-31")

    def test_um_ciclo_so_e_baixa(self):
        p = historico.prever([ed("x", "2027.2", "2027-04-01")], self.HOJE)["x"][0]
        self.assertEqual(p["confianca"], "baixa")

    def test_varias_chamadas_no_mesmo_ciclo_valem_a_primeira(self):
        E = [ed("x", "2026.1", "2025-08-01"), ed("x", "2026.1", "2025-12-01"), ed("x", "2027.1", "2026-08-03")]
        self.assertEqual(historico.prever(E, self.HOJE)["x"][0]["confianca"], "média")

    def test_ignora_o_que_nao_foi_conferido(self):
        E = [ed("x", "2027.1", "2026-08-01", fonte_dados="regras")]
        self.assertEqual(historico.prever(E, self.HOJE), {})


class Auditoria(unittest.TestCase):
    def test_analise_de_historico_nao_exige_data_de_prova(self):
        base = {"inscricao_inicio": "a", "inscricao_fim": "b", "vagas": [1], "taxa_inscricao": 1, "quem_pode": "x",
                "documentos": ["d"], "evidencias": {"x": 1}}
        self.assertEqual(historico.faltando({**base, "criterio_selecao": "análise curricular"}), [])
        self.assertIn("data da prova/análise", historico.faltando({**base, "criterio_selecao": "prova objetiva"}))

    def test_chave_igual_a_do_radar(self):
        import radar
        for u in ["https://www.X.br/Edital.pdf ", "http://x.br/edital.pdf%20"]:
            self.assertEqual(historico.chave_url(u), radar.chave_url(u))


if __name__ == "__main__":
    unittest.main()
