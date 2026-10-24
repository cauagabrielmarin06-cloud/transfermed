"""Testes das regras do robô. Rodar com: python -m unittest discover tests"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import radar  # noqa: E402


class ReconheceEdital(unittest.TestCase):
    def test_externa_e_interna(self):
        self.assertTrue(radar.parece_edital("Edital 034/2026 Medicina Transferência Externa https://x/edital.pdf"))
        self.assertTrue(radar.parece_edital("Processo Seletivo de Transferência Interna - Medicina"))

    def test_ignora_resultados(self):
        for rotulo in ("medicina-fernandopolis-preliminar-transferencia", "Resultado final transferência medicina",
                       "gabarito transferência medicina", "Convocação para matrícula transferência medicina"):
            self.assertFalse(radar.parece_edital(rotulo), rotulo)

    def test_ignora_outros_cursos(self):
        self.assertFalse(radar.parece_edital("Edital Transferência Curso de Enfermagem"))
        self.assertFalse(radar.parece_edital("Transferência Medicina Veterinária 2026"))

    def test_ignora_edital_geral_de_varios_cursos(self):
        self.assertFalse(radar.parece_edital("https://unifor.br/edital-49_2026-transf-grad-demais-cursos-2027 medicina"))
        self.assertFalse(radar.parece_edital("edital-ub-050_2025-cursos-presenciais-e-a-distancia transferencia medicina"))

    def test_aditivo_e_rerratificacao_sao_retificacao(self):
        self.assertTrue(radar.eh_retificacao("2°-Aditivo-do-edital-transferencia-externa-Medicina"))
        self.assertTrue(radar.eh_retificacao("RERRATIFICACAO-DO-EDITAL-DE-TRANSFERENCIA-MEDICINA"))

    def test_pagina_de_transferencia_aceita_link_edital(self):
        self.assertTrue(radar.parece_edital("Acesse o Edital https://uniube.br/baixarEdital.php?concurso=1044", True))
        self.assertFalse(radar.parece_edital("Acesse o Edital", False))


class Modalidade(unittest.TestCase):
    def test_palpites(self):
        self.assertEqual(radar.modalidade_provavel("", "TRANSFERÊNCIA INTERNA DE ALUNOS DA UNIVERSIDADE"), "interna")
        self.assertEqual(radar.modalidade_provavel("26071_edital_te_estrangeiras_prova.pdf", ""), "exterior")
        self.assertEqual(radar.modalidade_provavel("", "Transferência externa para Medicina"), "externa")

    def test_nome_do_link_vence_texto(self):
        rotulo = "Edital-1-Processo-Seletivo-Transferencia-externa-Medicina-UNEX-2025.1"
        self.assertEqual(radar.modalidade_provavel(rotulo, "vagas para alunos da instituição"), "externa")


class Retificacao(unittest.TestCase):
    def test_so_marca_edital_citado(self):
        e = {"numero_edital": "UB 034/2026", "semestre_ingresso": "2027.1"}
        self.assertTrue(radar.cita_edital("Retifica o Edital UB Nº 034/2026", e))
        self.assertTrue(radar.cita_edital("aditivo ao processo de 2027-1", e))
        self.assertFalse(radar.cita_edital("Retifica o edital 038/2025 para 2025.2", e))

    def test_janela_de_dois_anos(self):
        self.assertTrue(radar.antigo_demais({"semestre_ingresso": "2024.2"}, "2026-10-24"))
        self.assertFalse(radar.antigo_demais({"semestre_ingresso": "2025.1"}, "2026-10-24"))
        self.assertTrue(radar.antigo_demais({"inscricao_fim": "2024-06-30"}, "2026-10-24"))


class Datas(unittest.TestCase):
    HOJE = "2026-10-24"

    def test_fim_antes_do_inicio(self):
        p = radar.problemas_de_data({"inscricao_inicio": "2026-08-04", "inscricao_fim": "2026-06-18"}, self.HOJE)
        self.assertTrue(any("antes de começar" in x for x in p))

    def test_ano_errado(self):
        p = radar.problemas_de_data({"inscricao_inicio": "2016-10-01", "inscricao_fim": "2026-10-29"}, self.HOJE)
        self.assertTrue(any("ano improvável" in x for x in p))

    def test_semestre_nao_combina(self):
        p = radar.problemas_de_data({"semestre_ingresso": "2029.1", "inscricao_fim": "2026-10-29"}, self.HOJE)
        self.assertTrue(p)

    def test_datas_normais(self):
        e = {"inscricao_inicio": "2026-10-01", "inscricao_fim": "2026-10-29", "data_prova": "2026-10-31",
             "semestre_ingresso": "2027.1"}
        self.assertEqual(radar.problemas_de_data(e, self.HOJE), [])


class Situacao(unittest.TestCase):
    def test_situacoes(self):
        hoje = "2026-10-24"
        self.assertEqual(radar.situacao({"inscricao_inicio": "2026-10-01", "inscricao_fim": "2026-10-29"}, hoje), "aberto")
        self.assertEqual(radar.situacao({"inscricao_inicio": "2026-11-01", "inscricao_fim": "2026-11-29"}, hoje), "em breve")
        self.assertEqual(radar.situacao({"inscricao_fim": "2026-07-06"}, hoje), "encerrado")
        self.assertEqual(radar.situacao({"fluxo_continuo": True}, hoje), "fluxo contínuo")


class ExtracaoPorRegras(unittest.TestCase):
    def test_guarda_pagina_da_evidencia(self):
        paginas = ["Edital de transferência para o 1º semestre de 2027",
                   "Período de inscrição: 01/10/2026 a 29/10/2026. Taxa de inscrição: R$ 350,00",
                   "Aberto a estudantes de instituições brasileiras ou estrangeiras. Prova objetiva."]
        d = radar.extrair_por_regras(paginas)
        self.assertEqual(d["semestre_ingresso"], "2027.1")
        self.assertEqual((d["inscricao_inicio"], d["inscricao_fim"]), ("2026-10-01", "2026-10-29"))
        self.assertEqual(d["taxa_inscricao"], 350.0)
        self.assertTrue(d["aceita_curso_exterior"])
        self.assertEqual(d["evidencias"]["taxa_inscricao"], 2)
        self.assertEqual(d["evidencias"]["aceita_curso_exterior"], 3)


if __name__ == "__main__":
    unittest.main()
