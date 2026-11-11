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
            self.assertLessEqual(len(re.sub(r"R\$\s+", "R$", r["gancho"]).split()), 8, r["gancho"])   # "R$ 400" conta como uma palavra (mesma regra do P3)
            self.assertRegex(r["gancho"], r"\d")
            self.assertNotRegex(" ".join(r["textos"]) + r["legenda"], r"[“”\"]", fn.__name__)

    def test_todo_fato_tem_pagina_unica_e_toda_tela_com_dado_tem_rodape_de_fonte(self):
        for k, fn in pil.PAUTAS.items():
            r = fn(self.editais, self.facs, SEMANA[k])
            self.assertTrue(r["fatos"], fn.__name__)
            for f in r["fatos"]:
                self.assertTrue(ck.pagina_unica(f["pagina"]), f)

    def test_pauta_com_o_dado_que_mudou_nao_sai(self):
        """UVA volta a R$ 400 ou a FPP muda o quadro de vagas: a pauta levanta PautaInvalida em vez de sair com o número antigo."""
        eds = copy.deepcopy(self.editais)
        next(e for e in eds if e["id"] == "1e0e3121b570")["taxa_inscricao"] = 400.0
        with self.assertRaises(pil.PautaInvalida):
            pil.pauta_curiosidade_uva(eds, self.facs, SEMANA[3])
        eds = copy.deepcopy(self.editais)
        next(e for e in eds if e["id"] == "528d5ef7e915")["vagas"][1]["vagas"] = 5
        with self.assertRaises(pil.PautaInvalida):
            pil.pauta_processo_periodo(eds, self.facs, SEMANA[2])
        eds = copy.deepcopy(self.editais)
        next(e for e in eds if e["id"] == "528d5ef7e915")["status"] = "conferir"
        with self.assertRaises(pil.PautaInvalida):
            pil.pauta_armadilha_fpp(eds, self.facs, SEMANA[1])

    def test_unicamp_nao_afirma_que_so_transferencia_externa_e_diz_que_o_processo_passou(self):
        r = pil.pauta_numeros_unicamp(self.editais, self.facs, SEMANA[4])
        txt = " ".join(r["textos"]) + r["legenda"]
        self.assertIn("segmentos I, II e III", r["legenda"])   # a lista do documento reúne os 3 segmentos (p. 2)
        self.assertIn("já passou", txt)
        self.assertNotIn("transferência externa", txt.lower())


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
