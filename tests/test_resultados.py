"""Resultados agregados: nenhum dado pessoal pode entrar (nome, CPF, e-mail), nem por observação nem por endereço."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import resultados  # noqa: E402

BOM = {"edital_id": "ub-fernandopolis-externa-2026-1-abc123", "faculdade_id": "ub-fernandopolis", "status": "publicado",
       "numeros": {"vagas_ofertadas": {"valor": 30, "pagina": "2", "grandeza": "vagas_do_edital", "fonte_url": "https://exemplo.edu.br/edital.pdf"},
                   "inscritos": {"valor": 80, "pagina": "3", "grandeza": "candidatos_inscritos", "fonte_url": "https://exemplo.edu.br/resultado-final.pdf"},
                   "aprovados": {"valor": 25, "pagina": "4", "grandeza": "classificados_dentro_das_vagas", "fonte_url": "https://exemplo.edu.br/resultado-final.pdf"}},
       "fonte_url": "https://exemplo.edu.br/resultado-final.pdf", "ressalva": "chamadas_multiplas", "conferido_em": "2026-11-02"}
NAO = {"edital_id": "x1", "faculdade_id": "f1", "status": "nao_publicado", "numeros": {}, "motivo": "ainda_nao_divulgado",
       "fonte_url": "https://exemplo.edu.br/", "ressalva": "", "conferido_em": "2026-11-02"}


class SemDadoPessoal(unittest.TestCase):
    def test_registro_bom_passa(self):
        self.assertEqual(resultados.validar(BOM), [])
        self.assertEqual(resultados.validar(NAO), [])

    def test_todo_numero_exige_fonte_url_e_pagina_proprias(self):
        """Auditoria de 07/11/2026: cada número aponta para o documento e a página onde está; sem isso o registro não grava."""
        for campo in ("fonte_url", "pagina"):
            r = copy.deepcopy(BOM)
            del r["numeros"]["inscritos"][campo]
            self.assertTrue(resultados.validar(r), f"sem {campo}")
        for ruim in ("", "exemplo.edu.br/a.pdf", "ftp://x.br/a.pdf", "https://x.br/lista-123.456.789-09.pdf", "https://x.br/a@b.com", None, 7):
            r = copy.deepcopy(BOM)
            r["numeros"]["aprovados"]["fonte_url"] = ruim
            self.assertTrue(resultados.validar(r), repr(ruim))
        r = copy.deepcopy(BOM)
        r["numeros"]["aprovados"]["pagina"] = ""
        self.assertTrue(resultados.validar(r))

    def test_toda_a_base_publicada_tem_fonte_e_pagina_em_cada_numero(self):
        """Trava a publicação: nenhum número de data/resultados.json sem fonte_url e página próprias."""
        regs = resultados.carregar()
        self.assertGreaterEqual(len(regs), 25)
        for r in regs:
            for nome, v in r["numeros"].items():
                self.assertTrue(v.get("fonte_url", "").startswith("http"), (r["edital_id"], nome, "sem fonte_url"))
                self.assertTrue(v.get("pagina"), (r["edital_id"], nome, "sem pagina"))
        self.assertEqual(resultados.validar_todos(regs), {})

    def test_pagina_aceita_numero_site_ou_intervalo_e_nada_mais(self):
        for ok in ("3", "1-2", "site"):
            r = copy.deepcopy(BOM)
            r["numeros"]["inscritos"]["pagina"] = ok
            self.assertEqual(resultados.validar(r), [], ok)
        for ruim in ("1 e 2", "1-", "a-b", "1-2-3", "", "p. 2"):
            r = copy.deepcopy(BOM)
            r["numeros"]["inscritos"]["pagina"] = ruim
            self.assertTrue(resultados.validar(r), ruim)

    def test_inscritos_que_a_auditoria_nao_confirmou_nao_voltam(self):
        """Auditoria de 07/11/2026: UMC 2026.1 e 2025.1 (o 10 eram inscrições deferidas, outro PDF), FMJ (o 29 não está no PDF citado, que lista 4
        classificados) e UFU (o 490 não aparece mais na página citada). Só voltam com fonte e página que os confirmem."""
        por_id = {r["edital_id"]: r for r in resultados.carregar()}
        for eid in ("591452ea5828", "6f938c018d30", "a14e7a8bc5f7", "fae938ceab41"):
            self.assertNotIn("inscritos", por_id.get(eid, {"numeros": {}})["numeros"], eid)  # UFU saiu inteira (vagas sem apoio no edital)

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
        r["numeros"]["aprovados"] = {"valor": "Maria da Silva", "pagina": "2", "grandeza": "a_revisar", "fonte_url": "https://x.br/a.pdf"}
        self.assertTrue(resultados.validar(r))
        r = copy.deepcopy(BOM)
        r["numeros"]["aprovados"]["pagina"] = "Maria da Silva"
        self.assertTrue(resultados.validar(r))
        r = copy.deepcopy(BOM)
        r["numeros"]["nomes"] = {"valor": 1, "pagina": "1", "grandeza": "a_revisar", "fonte_url": "https://x.br/a.pdf"}
        self.assertTrue(resultados.validar(r))

    def test_cpf_ou_email_no_endereco_ou_nos_ids_falha(self):
        self.assertTrue(resultados.validar(dict(BOM, fonte_url="https://x.br/lista-123.456.789-09.pdf")))
        self.assertTrue(resultados.validar(dict(BOM, fonte_url="https://x.br/a@b.com")))
        self.assertTrue(resultados.validar(dict(BOM, edital_id="maria da silva")))
        self.assertTrue(resultados.validar(dict(BOM, faculdade_id="123.456.789-09")))

    def test_nao_publicado_nao_tem_numeros_e_publicado_tem(self):
        self.assertTrue(resultados.validar(dict(NAO, numeros=BOM["numeros"])))
        self.assertTrue(resultados.validar(dict(BOM, numeros={})))

    def test_grandeza_e_obrigatoria_e_so_codigo(self):
        r = copy.deepcopy(BOM)
        del r["numeros"]["aprovados"]["grandeza"]
        self.assertTrue(resultados.validar(r))
        r["numeros"]["aprovados"]["grandeza"] = "Maria da Silva"
        self.assertTrue(resultados.validar(r))
        r["numeros"]["aprovados"]["grandeza"] = "candidatos_inscritos"  # código de outro número
        self.assertTrue(resultados.validar(r))

    def test_nao_publicado_exige_motivo_em_codigo(self):
        self.assertTrue(resultados.validar(dict(NAO, motivo="a faculdade não publicou")))
        sem = dict(NAO)
        del sem["motivo"]
        self.assertTrue(resultados.validar(sem))

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
