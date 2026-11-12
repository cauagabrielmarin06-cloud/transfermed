"""Prazo de inscrição não pode ser a data de outra etapa; PDF de outra cidade não vale para a ficha (caso Corumbá, 12/11/2026).
O robô leu 27/11 (publicação dos locais de prova) como fim da inscrição (o certo era 23/11) e achou o edital de Corumbá
na ficha de Maringá. Os testes valem também para o estado "sem problema": campo ausente nunca derruba."""
import json
import sys
import unittest
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))
import gerar_site  # noqa: E402
import radar  # noqa: E402

EDITAIS = json.loads((PASTA / "data" / "editais.json").read_text(encoding="utf-8"))
ABERTOS = [e for e in EDITAIS if e.get("situacao") == "aberto"]
ETAPAS_DEPOIS = ("data_prova", "data_resultado", "data_matricula")


def prazo_fora_de_ordem(e):
    """Etapas que não vêm depois do fim da inscrição (a data de etapa lida como fim da inscrição cai aqui)."""
    fim = e.get("inscricao_fim")
    return [c for c in ETAPAS_DEPOIS if fim and e.get(c) and not fim < e[c]]


class PrazoNaoEOutraEtapa(unittest.TestCase):
    def test_inscricao_termina_antes_de_prova_resultado_e_matricula(self):
        for e in ABERTOS:
            self.assertEqual(prazo_fora_de_ordem(e), [], f"{e['id']}: inscricao_fim {e.get('inscricao_fim')} não é anterior à etapa")

    def test_edital_lido_so_por_regras_nunca_afirma_prazo(self):
        for e in ABERTOS:
            if e.get("fonte_dados") != "manual":
                self.assertTrue(gerar_site.fora_dos_emails(e), f"{e['id']}: prazo lido só por regras entrou nos e-mails e no site como certo")

    def test_edital_aberto_conferido_cita_a_pagina_do_prazo(self):
        for e in ABERTOS:
            if e.get("status") == "ok":
                self.assertTrue((e.get("evidencias") or {}).get("inscricao_fim"), f"{e['id']}: prazo sem página citada")

    def test_pega_o_caso_corumba_e_deixa_passar_o_correto(self):
        errado = {"inscricao_fim": "2026-11-28", "data_prova": "2026-11-28", "data_resultado": "2026-12-04"}  # data da etapa no lugar do fim
        certo = {"inscricao_fim": "2026-11-23", "data_prova": "2026-11-28", "data_resultado": "2026-12-04"}
        self.assertEqual(prazo_fora_de_ordem(errado), ["data_prova"])
        self.assertEqual(prazo_fora_de_ordem(certo), [])
        self.assertEqual(prazo_fora_de_ordem({}), [], "campos ausentes não derrubam")


class PdfDeOutraCidade(unittest.TestCase):
    FACS = {
        "unicesumar-corumba": {"id": "unicesumar-corumba", "cidade": "Corumbá"},
        "unicesumar-maringa": {"id": "unicesumar-maringa", "cidade": "Maringá"},
        "fpp-curitiba": {"id": "fpp-curitiba", "cidade": "Curitiba"},
    }

    def test_pdf_de_corumba_achado_na_ficha_de_maringa(self):
        texto = radar.normalizar("Faculdade Unicesumar de Corumbá/MS. Prova em Campo Grande ou Corumbá.")
        self.assertEqual(radar.cidade_diverge(self.FACS["unicesumar-maringa"], texto, self.FACS), ["corumba"])

    def test_pdf_que_cita_a_propria_cidade_passa(self):
        texto = radar.normalizar("Unicesumar Maringá e também Corumbá")
        self.assertEqual(radar.cidade_diverge(self.FACS["unicesumar-maringa"], texto, self.FACS), [])

    def test_sem_irmas_ou_sem_cidade_nao_acusa(self):
        self.assertEqual(radar.cidade_diverge(self.FACS["fpp-curitiba"], "texto qualquer", self.FACS), [])
        self.assertEqual(radar.cidade_diverge({"id": "x-y"}, "texto", self.FACS), [])
        self.assertEqual(radar.cidade_diverge(self.FACS["unicesumar-maringa"], "corumba", None), [])

    def test_dados_de_hoje_cidade_do_edital_e_a_da_ficha(self):
        """Contra a base real: a cidade guardada no edital é a da ficha (o PDF em si só é lido pelo robô, que usa cidade_diverge)."""
        faculdades = {f["id"]: f for f in json.loads((PASTA / "data" / "faculdades.json").read_text(encoding="utf-8"))}
        for e in ABERTOS:
            cidade = e.get("cidade_uf")
            fac = faculdades.get(e.get("faculdade_id"), {})
            if cidade and fac.get("cidade"):
                self.assertTrue(cidade.startswith(fac["cidade"]), f"{e['id']}: cidade do edital {cidade} x ficha {fac['cidade']}")


if __name__ == "__main__":
    unittest.main()
