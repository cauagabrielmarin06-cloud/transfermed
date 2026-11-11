"""Mutirão do "conferir" (11/11/2026): campos fechados com a página lida no PDF e avisos neutros nas contradições do próprio edital.

Os dois grupos são dados lidos à mão do PDF: se alguém reabrir um campo fechado, ou trocar o aviso por um resumo sem o texto literal e a página,
estes testes avisam. (Rodados contra o data/editais.json de antes da mudança, os de "fechado" e os de "aviso literal" falham.)
"""
import json
import re
import unittest
from pathlib import Path

DADOS = Path(__file__).resolve().parent.parent / "data" / "editais.json"
E = {e["id"]: e for e in json.loads(DADOS.read_text(encoding="utf-8"))}

USCS = ("41a0eb874829", "d208383ef911", "99a8bef34f35")
# edital -> campos em contradição (tipo B do padrão: aviso neutro, com o trecho literal entre aspas e a página; o campo segue em "conferir")
AVISOS_B = {
    "3d14f3174108": ("resultado",), "bea65dcbf046": ("resultado",),                                   # Unime
    "c396ff22dfa7": ("vagas",), "df64cb906f3f": ("vagas",),                                          # UNOESTE
    "97d825526f95": ("inscricao_fim", "numero_edital"), "4f356b303f31": ("inscricao_inicio",),       # UNIG
    "39c910ec7b14": ("taxa_inscricao", "numero_edital"), "d035a73eafa5": ("taxa_inscricao", "numero_edital"),   # UNIP
    "b12c262ed876": ("taxa_inscricao", "numero_edital"), "1a2ac4350e80": ("taxa_inscricao", "numero_edital"),
    "cdd254117886": ("resultado",),                                                                  # Integrado (a taxa é ausência: ver AUSENCIAS)
    "08c5a253018c": ("documentos",),                                                                 # UVA (portador de diploma)
}


# o edital não traz o dado: não há trecho literal a citar, o aviso diz isso e que a conferência de todas as páginas foi feita
AUSENCIAS = {"cdd254117886": "taxa_inscricao"}


class CamposFechados(unittest.TestCase):
    def test_uscs_resultado_fechado_com_as_duas_paginas_do_anexo_i(self):
        for i in USCS:
            e = E[i]
            self.assertEqual(e["status"], "ok", i)
            self.assertNotIn("conferir_campos", e, i)
            txt = e["resultado_texto"]
            self.assertIn("21/12/2026", txt)
            self.assertIn("Anexo I, p. 13", txt)
            self.assertIn("04/01/2027", txt)
            self.assertIn("Anexo I, p. 14", txt)
            self.assertIn("13 e 14", e["evidencias"]["data_resultado"])

    def test_unicesumar_maringa_vagas_fechadas_e_numero_do_edital_segue_em_conferir(self):
        e = E["1ddd4445afdc"]
        self.assertEqual([(v["semestre"], v["vagas"]) for v in e["vagas"]], [("2ª série", 30), ("3ª série", 10), ("4ª série", 10)])
        self.assertNotIn("vagas", e["conferir_campos"])
        self.assertIn("numero_edital", e["conferir_campos"])   # a retificação citada não está no PDF: não se fecha sem ler

    def test_unoeste_guaruja_aponta_a_pagina_do_proprio_quadro_de_vagas(self):
        self.assertEqual(E["df64cb906f3f"]["evidencias"]["vagas"], 2)   # o quadro do Campus de Guarujá está na p. 2 (o de Jaú, na p. 1)
        self.assertEqual(E["c396ff22dfa7"]["evidencias"]["vagas"], 1)


class AvisosNeutros(unittest.TestCase):
    def test_todo_aviso_tipo_b_cita_trecho_literal_entre_aspas_e_pagina_e_nao_escolhe_lado(self):
        for i, campos in AVISOS_B.items():
            conf = E[i].get("conferir_campos") or {}
            for campo in campos:
                aviso = conf.get(campo)
                self.assertTrue(aviso, f"{i}: {campo} saiu de conferir sem a faculdade confirmar")
                self.assertRegex(aviso, r"“[^”]+”|\"[^\"]{6,}\"", f"{i} {campo}: sem trecho literal entre aspas")
                self.assertRegex(aviso, r"\bp\. \d", f"{i} {campo}: sem página")
                self.assertRegex(aviso, r"Confirme com a (faculdade|secretaria)", f"{i} {campo}")
                self.assertNotIn("Mostramos", aviso, f"{i} {campo}: o aviso não pode dizer que a ficha escolheu um dos lados")
                self.assertNotIn("Parece", aviso, f"{i} {campo}: nada de dedução")

    def test_ausencia_de_dado_diz_que_o_edital_nao_traz_e_manda_confirmar(self):
        for i, campo in AUSENCIAS.items():
            aviso = E[i]["conferir_campos"][campo]
            self.assertIn("não traz", aviso)
            self.assertIn("Confirme com a faculdade", aviso)

    def test_unime_traz_as_duas_datas_com_a_pagina_de_cada_uma(self):
        aviso = E["3d14f3174108"]["conferir_campos"]["resultado"]
        self.assertTrue(aviso.startswith("O edital traz duas datas para o resultado: 26/11/2026 (p. 2"), aviso)
        self.assertIn("25/11/2026 (p. 7", aviso)
        self.assertEqual(aviso, E["bea65dcbf046"]["conferir_campos"]["resultado"])

    def test_avisos_b_continuam_em_conferir_e_com_status_conferir(self):
        for i in AVISOS_B:
            self.assertEqual(E[i]["status"], "conferir", i)


if __name__ == "__main__":
    unittest.main()
