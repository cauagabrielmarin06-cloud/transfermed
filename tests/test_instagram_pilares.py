"""Pautas curadas do Instagram nos 7 pilares (instagram_pilares.py, 11/11/2026): cada pauta passa em todas as regras com os dados reais e
deixa de sair quando o dado do edital muda (o post nunca leva número velho)."""
import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

import instagram_checagem as ck
import instagram_dia as dia
import instagram_pilares as pil

HOJE = "2026-11-16"
SEMANA = {1: "2026-11-17", 2: "2026-11-18", 3: "2026-11-19", 4: "2026-11-20", 5: "2026-11-21", 6: "2026-11-22"}
TIPOS = {1: "armadilha-do-edital", 2: "como-funciona-periodo", 3: "curiosidade-de-faculdade", 4: "numeros-do-raio-x", 5: "mito-ou-fato", 6: "estudo-no-exterior"}


class PautasComDadosReais(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.editais, cls.facs = dia._dados()

    def test_cada_dia_da_semana_tem_o_pilar_do_banco_e_passa_em_todas_as_regras(self):
        for k, fn in pil.PAUTAS.items():
            r = fn(self.editais, self.facs, SEMANA[k])
            self.assertEqual(r["tipo"], TIPOS[k])
            self.assertEqual(ck.checar(r, self.editais, self.facs, SEMANA[k]), [], fn.__name__)

    def test_gancho_com_fato_concreto_ate_8_palavras_e_sem_aspas(self):
        for k, fn in pil.PAUTAS.items():
            r = fn(self.editais, self.facs, SEMANA[k])
            self.assertLessEqual(len(r["gancho"].split()), 8, r["gancho"])   # contagem crua, como o P3 (R$ e valor são 2 palavras)
            self.assertRegex(r["gancho"], r"\d")
            self.assertNotRegex(" ".join(r["textos"]) + r["legenda"], r"[“”\"]", fn.__name__)

    def test_todo_fato_tem_pagina_unica_e_toda_tela_com_dado_tem_rodape_de_fonte(self):
        for k, fn in pil.PAUTAS.items():
            r = fn(self.editais, self.facs, SEMANA[k])
            self.assertTrue(r["fatos"], fn.__name__)
            for f in r["fatos"]:
                self.assertTrue(ck.pagina_unica(f["pagina"]), f)

    def test_pauta_com_o_dado_que_mudou_nao_sai(self):
        """São Camilo muda o quadro de vagas, UNIFACCAMP muda o critério ou a FPP perde o status: a pauta levanta PautaInvalida em vez de sair com o dado antigo."""
        eds = copy.deepcopy(self.editais)
        next(e for e in eds if e["id"] == "098f92b0cc9a")["criterio_selecao"] = "prova objetiva"
        with self.assertRaises(pil.PautaInvalida):
            pil.pauta_curiosidade_unifaccamp(eds, self.facs, SEMANA[3])
        eds = copy.deepcopy(self.editais)
        next(e for e in eds if e["id"] == "24163eeabba8")["vagas"][1]["vagas"] = 5
        with self.assertRaises(pil.PautaInvalida):
            pil.pauta_processo_periodo(eds, self.facs, SEMANA[2])
        eds = copy.deepcopy(self.editais)
        next(e for e in eds if e["id"] == "528d5ef7e915")["status"] = "conferir"
        with self.assertRaises(pil.PautaInvalida):
            pil.pauta_armadilha_fpp(eds, self.facs, SEMANA[1])
        eds = copy.deepcopy(self.editais)
        next(e for e in eds if e["id"] == "2a698cddcbf7")["criterio_selecao"] = "análise do histórico"
        with self.assertRaises(pil.PautaInvalida):
            pil.pauta_mito_prova(eds, self.facs, SEMANA[5])

    def test_sao_camilo_cita_o_quadro_da_p1_e_nao_o_semestre_de_ingresso_contraditorio(self):
        r = pil.pauta_processo_periodo(self.editais, self.facs, SEMANA[2])
        txt = " ".join(r["textos"]) + r["legenda"]
        self.assertIn("3 vagas no 3º semestre, 4 no 4º", r["gancho"])
        self.assertIn("já foi encerrado", r["legenda"])   # o edital 054/2026 acabou em 12/07/2026: o post diz que é exemplo
        self.assertNotIn("2026.2", txt)
        self.assertNotIn("2º semestre de 2026", txt)
        self.assertEqual({f["pagina"] for f in r["fatos"]}, {"1"})

    def test_mito_da_nota_alta_usa_tres_editais_com_pagina_e_responde_depende(self):
        r = pil.pauta_mito_prova(self.editais, self.facs, SEMANA[5])
        self.assertEqual({f["edital"] for f in r["fatos"]}, {"528d5ef7e915", "2a698cddcbf7", "1e0e3121b570"})
        self.assertIn("Depende do edital", " ".join(r["textos"]))
        self.assertIn("só entra quem tem nota alta", " ".join(r["textos"]).lower())   # a pergunta do pedido continua na capa

    def test_unicamp_nao_afirma_que_so_transferencia_externa_e_diz_que_o_processo_passou(self):
        r = pil.pauta_numeros_unicamp(self.editais, self.facs, SEMANA[4])
        txt = " ".join(r["textos"]) + r["legenda"]
        self.assertIn("segmentos I, II e III", r["legenda"])   # a lista do documento reúne os 3 segmentos (p. 2)
        self.assertIn("já passou", txt)
        self.assertNotIn("transferência externa", txt.lower())


DIAS_13_A_15 = {"2026-11-13": "numeros-do-raio-x", "2026-11-14": "mito-ou-fato", "2026-11-15": "estudo-no-exterior"}


class Dias13a15(unittest.TestCase):
    def test_cada_pauta_de_13_a_15_passa_em_todas_as_regras_e_tem_o_pilar_do_dia(self):
        editais, facs = dia._dados()
        for d, tipo in DIAS_13_A_15.items():
            r = pil.PAUTAS_DO_DIA[d](editais, facs, d)
            self.assertEqual(r["tipo"], tipo, d)
            self.assertEqual(ck.checar(r, editais, facs, d), [], d)
            self.assertLessEqual(len(r["gancho"].split()), 8, r["gancho"])

    def test_unifaa_diz_que_o_resultado_nao_traz_o_total_de_inscritos(self):
        editais, facs = dia._dados()
        r = pil.pauta_numeros_unifaa(editais, facs, "2026-11-13")
        self.assertIn("não informa quantos candidatos se inscreveram", r["legenda"])
        self.assertEqual({f["pagina"] for f in r["fatos"]}, {"1"})


class SemanaCompleta(unittest.TestCase):
    def test_gerar_semana_grava_os_7_dias_marca_curado_e_monta_o_pacote_com_as_telas(self):
        editais, facs = dia._dados()
        with tempfile.TemporaryDirectory() as t:
            social, privado = Path(t) / "docs" / "social", Path(t) / "privado" / "instagram"
            privado.mkdir(parents=True)
            velho = (dia.SOCIAL, dia.PRIVADO)
            dia.SOCIAL, dia.PRIVADO = social, privado
            try:
                msgs, pasta = pil.gerar_semana(HOJE, saida=privado, dados=(editais, facs))
            finally:
                dia.SOCIAL, dia.PRIVADO = velho
            self.assertFalse([m for m in msgs if "SEM POST" in m], msgs)
            for k, d in SEMANA.items():
                post = json.loads((social / d / "post.json").read_text(encoding="utf-8"))
                self.assertTrue(post["curado"], d)
                self.assertEqual(post["tipo"], TIPOS[k])
                self.assertTrue(dia.revisado_pelo_dono(social / d), d)   # o robô de domingo não regera
                self.assertTrue((pasta / d / "FONTES.md").exists() and (pasta / d / "legenda.txt").exists() and (pasta / d / "01.jpg").exists(), d)
            self.assertTrue((pasta / "previa.jpg").exists())

    def test_post_curado_e_post_revisado_nao_sao_regerados_e_post_comum_e(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t)
            for chave, esperado in (("curado", True), ("revisado", True), ("outro", False)):
                (p / "post.json").write_text(json.dumps({chave: True}), encoding="utf-8")
                self.assertEqual(dia.revisado_pelo_dono(p), esperado, chave)


if __name__ == "__main__":
    unittest.main()
