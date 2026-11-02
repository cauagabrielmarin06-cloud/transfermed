"""Resultados agregados: nenhum dado pessoal pode entrar (nome, CPF, e-mail), nem por observação nem por endereço."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import resultados  # noqa: E402

BOM = {"edital_id": "ub-fernandopolis-externa-2026-1-abc123", "faculdade_id": "ub-fernandopolis", "status": "publicado",
       "numeros": {"vagas_ofertadas": {"valor": 30, "pagina": "2"}, "inscritos": {"valor": 80, "pagina": "3"},
                   "aprovados": {"valor": 25, "pagina": "4"}},
       "fonte_url": "https://exemplo.edu.br/resultado-final.pdf", "ressalva": "chamadas_multiplas", "conferido_em": "2026-11-02"}
NAO = {"edital_id": "x1", "faculdade_id": "f1", "status": "nao_publicado", "numeros": {},
       "fonte_url": "https://exemplo.edu.br/", "ressalva": "", "conferido_em": "2026-11-02"}


class SemDadoPessoal(unittest.TestCase):
    def test_registro_bom_passa(self):
        self.assertEqual(resultados.validar(BOM), [])
        self.assertEqual(resultados.validar(NAO), [])

    def test_nome_em_chave_nova_falha(self):
        for chave in ("nome", "aprovados_nomes", "candidatos", "lista", "observacao", "cpf", "email"):
            self.assertTrue(resultados.validar(dict(BOM, **{chave: "Maria da Silva"})), chave)

    def test_nome_em_ressalva_falha(self):
        self.assertTrue(resultados.validar(dict(BOM, ressalva="aprovada: Maria da Silva")))

    def test_nome_dentro_de_numeros_falha(self):
        r = copy.deepcopy(BOM)
        r["numeros"]["aprovados"]["nome"] = "Maria"
        self.assertTrue(resultados.validar(r))
        r = copy.deepcopy(BOM)
        r["numeros"]["aprovados"] = {"valor": "Maria da Silva", "pagina": "2"}
        self.assertTrue(resultados.validar(r))
        r = copy.deepcopy(BOM)
        r["numeros"]["aprovados"]["pagina"] = "Maria da Silva"
        self.assertTrue(resultados.validar(r))
        r = copy.deepcopy(BOM)
        r["numeros"]["nomes"] = {"valor": 1, "pagina": "1"}
        self.assertTrue(resultados.validar(r))

    def test_cpf_ou_email_no_endereco_ou_nos_ids_falha(self):
        self.assertTrue(resultados.validar(dict(BOM, fonte_url="https://x.br/lista-123.456.789-09.pdf")))
        self.assertTrue(resultados.validar(dict(BOM, fonte_url="https://x.br/a@b.com")))
        self.assertTrue(resultados.validar(dict(BOM, edital_id="maria da silva")))
        self.assertTrue(resultados.validar(dict(BOM, faculdade_id="123.456.789-09")))

    def test_nao_publicado_nao_tem_numeros_e_publicado_tem(self):
        self.assertTrue(resultados.validar(dict(NAO, numeros=BOM["numeros"])))
        self.assertTrue(resultados.validar(dict(BOM, numeros={})))

    def test_aprovados_nao_passam_de_inscritos_e_edital_nao_repete(self):
        r = copy.deepcopy(BOM)
        r["numeros"]["aprovados"]["valor"] = 99
        self.assertTrue(resultados.validar(r))
        self.assertIn(1, resultados.validar_todos([BOM, BOM]))

    def test_o_que_esta_gravado_no_repositorio_e_valido(self):
        self.assertEqual(resultados.validar_todos(resultados.carregar()), {})

    def test_gravar_recusa_registro_com_dado_pessoal(self):
        with self.assertRaises(ValueError):
            resultados.gravar([dict(BOM, nome="Maria")])


if __name__ == "__main__":
    unittest.main()
