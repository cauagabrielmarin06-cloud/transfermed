"""Contrato dos dados (T6.3): os JSON publicados mantêm o formato descrito em docs/DADOS.md.
Os testes de "quebra" provam que o contrato pega o defeito (campo renomeado, tipo trocado), rodando contra cópias alteradas."""
import copy
import json
import sys
import unittest
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))
import contrato  # noqa: E402

CONTRATO = json.loads(contrato.ARQUIVO.read_text(encoding="utf-8"))


class DadosDeHojeRespeitamOContrato(unittest.TestCase):
    def test_cada_arquivo_publicado_e_compativel(self):
        for nome in CONTRATO["arquivos"]:
            dados = contrato.carregar(nome)
            if dados is None:
                self.assertIn(nome, contrato.OPCIONAIS, f"{nome}.json sumiu")
                continue
            self.assertEqual(contrato.conferir(CONTRATO, nome, dados), [], f"o formato de {nome}.json quebrou o contrato")

    def test_retratos_sem_nenhum_pdf_falhando_continua_compativel(self):
        # falha_desde e ultimo_erro só existem enquanto um PDF não abre: quando todos voltam, o contrato não pode travar a publicação
        dados = contrato.carregar("retratos")
        sem_falha = copy.deepcopy(dados)
        for v in sem_falha["pdfs"].values():
            for campo in ("falha_desde", "ultimo_erro"):
                v.pop(campo, None)
        self.assertEqual(contrato.conferir(CONTRATO, "retratos", sem_falha), [])

    def test_quarentena_do_monitor_nao_precisa_estar_no_contrato(self):
        self.assertIn("quarentena", contrato.OPCIONAIS)

    def test_todos_os_arquivos_de_dados_estao_no_contrato_ou_foram_excluidos_de_proposito(self):
        # fora do contrato de propósito: estado interno dos robôs, resumos e a geometria estática do mapa
        fora = {"processados", "relatorio_qualidade", "ultima_execucao", "guardiao", "mapa_brasil"}
        existentes = {p.stem for p in (PASTA / "data").glob("*.json")}
        self.assertEqual(sorted(existentes - set(CONTRATO["arquivos"]) - fora - contrato.OPCIONAIS), [],
                         "arquivo novo em data/: acrescente em contrato.ARQUIVOS (e rode python contrato.py --gravar) ou justifique aqui")

    def test_documento_publico_traz_exatamente_o_contrato(self):
        texto = contrato.DOC.read_text(encoding="utf-8")
        bloco = texto.split(contrato.INI, 1)[1].split(contrato.FIM, 1)[0].strip()
        self.assertEqual(bloco, contrato.tabela_do_contrato(CONTRATO).strip(), "docs/DADOS.md fora de sincronia: python contrato.py --gravar")

    def test_documento_nao_traz_estrategia_nem_dado_pessoal(self):
        texto = contrato.DOC.read_text(encoding="utf-8").lower()
        for proibido in ("receita", "meta h", "preço", "@gmail", "cpf:", "estratégia"):
            self.assertNotIn(proibido, texto)


class ContratoPegaOsDefeitos(unittest.TestCase):
    def setUp(self):
        self.ed = copy.deepcopy(contrato.carregar("editais"))

    def quebras(self, dados, nome="editais"):
        return contrato.conferir(CONTRATO, nome, dados)

    def test_dados_intactos_passam(self):
        self.assertEqual(self.quebras(self.ed), [])

    def test_campo_renomeado_quebra(self):
        for e in self.ed:
            if "inscricao_fim" in e:
                e["inscricao_final"] = e.pop("inscricao_fim")
        self.assertTrue(any("inscricao_fim" in q for q in self.quebras(self.ed)))

    def test_campo_obrigatorio_removido_de_um_registro_quebra(self):
        manual = next(e for e in self.ed if e.get("fonte_dados") == "manual")
        del manual["url_edital"]
        self.assertTrue(any("url_edital" in q for q in self.quebras(self.ed)))

    def test_tipo_trocado_quebra(self):
        manual = next(e for e in self.ed if e.get("fonte_dados") == "manual" and e.get("vagas"))
        manual["vagas"] = "3 vagas"
        self.assertTrue(any("vagas" in q and "tipo" in q for q in self.quebras(self.ed)))

    def test_campo_novo_e_opcional_nao_quebra(self):
        self.ed[0]["campo_novo_do_futuro"] = {"qualquer": 1}
        self.assertEqual(self.quebras(self.ed), [])

    def test_nao_informado_e_inteiro_virando_decimal_nao_quebram(self):
        manual = next(e for e in self.ed if e.get("fonte_dados") == "manual" and isinstance(e.get("taxa_inscricao"), (int, float)))
        manual["taxa_inscricao"] = float(manual["taxa_inscricao"]) + 0.5
        manual2 = next(e for e in self.ed if e.get("fonte_dados") == "manual" and e is not manual and e.get("inscricao_fim"))
        manual2["inscricao_fim"] = None
        self.assertEqual([q for q in self.quebras(self.ed) if "taxa" in q or "tipo" in q], [])

    def test_edital_do_robo_com_menos_campos_nao_trava_a_publicacao(self):
        self.ed.append({"id": "novo", "faculdade_id": "x", "fonte_dados": "robo", "url_edital": "https://x.br/a.pdf"})
        self.assertEqual(self.quebras(self.ed), [])

    def test_forma_errada_quebra(self):
        self.assertTrue(self.quebras({"editais": []}))

    def test_resultados_com_grandeza_trocada_de_tipo_quebra(self):
        res = copy.deepcopy(contrato.carregar("resultados"))
        primeiro = next(iter(res[0]["numeros"].values()))
        primeiro["valor"] = "muitos"
        self.assertTrue(any("valor" in q for q in self.quebras(res, "resultados")))


if __name__ == "__main__":
    unittest.main()
