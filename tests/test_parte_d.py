"""13/11/2026 · Parte D (Meu plano, comparar, o que mudou, app). O que o gerador entrega; a lógica do navegador é testada em qa/meu_plano.mjs."""
import json
import re
import sys
import unittest
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))
import gerar_site  # noqa: E402

HOJE = "2026-11-13"
FAC = {"id": "uva-rio", "nome": "Universidade Veiga de Almeida", "sigla": "UVA", "cidade": "Rio de Janeiro", "uf": "RJ"}


def edital(**kw):
    base = {"id": "e1", "faculdade_id": "uva-rio", "fonte_dados": "manual", "status": "ok", "url_edital": "https://x.edu/e.pdf", "conferido_em": "2026-11-10",
            "inscricao_fim": "2026-12-01", "taxa_inscricao": 250.0, "evidencias": {"taxa_inscricao": "2 (item 3.1, f; edital retificado em 09/11/2026)", "data_prova": 5},
            "versoes": [{"em": "2026-11-10", "motivo": "retificação de 09/11 lida por inteiro", "retificado_em": "2026-11-09", "mudou": {"taxa_inscricao": [400.0, 250.0]}}]}
    base.update(kw)
    return base


class PaginaEItem(unittest.TestCase):
    def test_pagina_e_item_do_texto_de_evidencia(self):
        e = edital()
        self.assertEqual(gerar_site.pagina_e_item(e, "taxa_inscricao"), "p. 2, item 3.1, f")
        self.assertEqual(gerar_site.pagina_e_item(e, "data_prova"), "p. 5")

    def test_sem_numero_claro_nao_chuta(self):
        e = edital(evidencias={"inscricao_fim": "Anexo 1, p. 1"})
        self.assertEqual(gerar_site.pagina_e_item(e, "inscricao_fim"), "")
        self.assertEqual(gerar_site.pagina_e_item(e, "vagas"), "")


class CartaoDeRetificacao(unittest.TestCase):
    def test_com_antes_e_depois_guardados(self):
        r = gerar_site.retificacao_do_edital(edital())
        self.assertEqual(r["em"], "2026-11-09")
        self.assertEqual(r["mudancas"], [{"rotulo": "Taxa", "antes": "R$ 400", "depois": "R$ 250", "pagina": "p. 2, item 3.1, f"}])
        html = gerar_site.cartao_retificacao(edital(), FAC)
        self.assertIn("Retificado em 09/11", html)
        self.assertIn("<s>R$ 400</s>", html)
        self.assertIn("<b>R$ 250</b>", html)
        self.assertIn("p. 2, item 3.1, f", html)

    def test_sem_data_da_retificacao_nao_ha_cartao(self):
        """A data em que o robô leu não é a data da retificação: sem `retificado_em` o cartão não existe (nada de chute)."""
        v = [{"em": "2026-11-10", "motivo": "reconferência", "mudou": {"taxa_inscricao": [400.0, 250.0]}}]
        self.assertIsNone(gerar_site.retificacao_do_edital(edital(versoes=v)))
        self.assertEqual(gerar_site.cartao_retificacao(edital(versoes=v), FAC), "")
        self.assertIsNone(gerar_site.retificacao_do_edital(edital(versoes=None)))

    def test_sem_o_valor_anterior_cai_em_leia_a_versao_nova(self):
        v = [{"em": "2026-11-10", "retificado_em": "2026-11-09", "mudou": {"taxa_inscricao": [None, 250.0]}}]
        e = edital(versoes=v, retificacoes=["https://x.edu/ret.pdf"])
        r = gerar_site.retificacao_do_edital(e)
        self.assertEqual(r["mudancas"], [])
        html = gerar_site.cartao_retificacao(e, FAC)
        self.assertIn("Retificado em 09/11", html)
        self.assertIn("Leia a versão nova", html)
        self.assertIn('href="https://x.edu/ret.pdf"', html)
        self.assertNotIn("<s>", html)

    def test_campo_em_conferir_nao_aparece_como_antes_e_depois(self):
        e = edital(status="conferir", conferir_campos={"taxa_inscricao": "o edital se contradiz"})
        self.assertEqual(gerar_site.retificacao_do_edital(e)["mudancas"], [])
        e = edital(status="conferir", conferir_campos={"edital": "ponto a conferir"})
        self.assertEqual(gerar_site.retificacao_do_edital(e)["mudancas"], [])

    def test_datas_mostram_dia_e_mes(self):
        v = [{"em": "2026-11-10", "retificado_em": "2026-11-09", "mudou": {"data_prova": ["2026-12-05", "2026-12-12"]}}]
        r = gerar_site.retificacao_do_edital(edital(versoes=v))
        self.assertEqual((r["mudancas"][0]["antes"], r["mudancas"][0]["depois"]), ("05/12/2026", "12/12/2026"))

    def test_valor_de_outro_tipo_nao_quebra_o_site(self):
        v = [{"em": "2026-11-10", "retificado_em": "2026-11-09", "mudou": {"taxa_inscricao": ["abc", 250.0]}}]
        r = gerar_site.retificacao_do_edital(edital(versoes=v))
        self.assertEqual(r["mudancas"], [])

    def test_alimenta_o_painel_o_robo_hoje(self):
        e = edital(retificacoes=["http://x.edu/ret.pdf"])
        detalhes = gerar_site.detalhes_das_retificacoes([e])
        self.assertEqual(detalhes, {"http://x.edu/ret.pdf": "Taxa R$ 400 → R$ 250"})
        exec_ = {"executado_em_utc": "2026-11-13T12:00:00Z", "retificacoes": ["UVA: http://x.edu/ret.pdf"], "novos": [], "atualizados": []}
        linhas, mudou, _ = gerar_site.eventos_do_robo({"uva-rio": FAC}, HOJE, exec_, {}, detalhes)
        self.assertTrue(mudou)
        self.assertIn("Taxa R$ 400 → R$ 250", linhas[0][1])
        sem, _, _ = gerar_site.eventos_do_robo({"uva-rio": FAC}, HOJE, exec_, {})
        self.assertNotIn("R$ 400", sem[0][1])


class DadosDoPlano(unittest.TestCase):
    def test_encerrado_nao_pesa_no_dados_js(self):
        self.assertEqual(gerar_site.dados_do_plano(edital(inscricao_fim="2026-11-01"), HOJE), {})

    def test_aberto_leva_conferir_pagina_e_cartao(self):
        d = gerar_site.dados_do_plano(edital(status="conferir", conferir_campos={"data_prova": "aviso"}, criterio_selecao="prova"), HOJE)
        self.assertEqual(d["conf"], ["data_prova"])
        self.assertEqual(d["pg"]["taxa"], "p. 2, item 3.1, f")
        self.assertEqual(d["crit"], "prova")
        self.assertEqual(d["ret"]["em"], "2026-11-09")
        self.assertEqual(d["ret"]["m"][0][:3], ["Taxa", "R$ 400", "R$ 250"])

    def test_edital_sem_aviso_tem_conf_vazio_e_sem_retificacao(self):
        d = gerar_site.dados_do_plano(edital(versoes=None), HOJE)
        self.assertEqual(d["conf"], [])
        self.assertIsNone(d["ret"])

    def test_dados_js_publicado_tem_os_campos_da_parte_d(self):
        js = (gerar_site.DOCS / "dados.js").read_text(encoding="utf-8")
        m = re.match(r"window\.TM=(\{.*?\});\nwindow\.CAPITAIS", js, re.S)
        eds = json.loads(m.group(1))["editais"]
        abertos = [x for x in eds if x.get("fim", "") >= HOJE]
        self.assertTrue(abertos)
        self.assertTrue(any(x.get("pg") for x in abertos), "página de cada dado para o Meu plano e o comparador")
        self.assertTrue(any(x.get("conf") for x in abertos), "campos em conferir precisam chegar ao navegador (nunca viram data no plano)")


class AppInstalavel(unittest.TestCase):
    def test_manifest_abre_no_meu_plano_e_so_tem_icone_v3(self):
        m = json.loads((gerar_site.DOCS / "manifest.webmanifest").read_text(encoding="utf-8"))
        self.assertEqual(m["start_url"], "./minha-lista/?origem=app")
        self.assertEqual(m["display"], "standalone")
        self.assertTrue(m["theme_color"])
        for i in m["icons"]:
            self.assertRegex(i["src"], r"assets/marca/logo-(maskable-)?(192|512)-v3\.png$")
        mask = {i["sizes"] for i in m["icons"] if i["purpose"] == "maskable"}
        self.assertEqual(mask, {"192x192", "512x512"})
        for i in m["icons"]:
            self.assertTrue((gerar_site.DOCS / i["src"]).exists(), i["src"])

    def test_service_worker_revalida_os_dados_na_rede(self):
        sw = (gerar_site.DOCS / "sw.js").read_text(encoding="utf-8")
        self.assertIn("['dados.js', 'editais.json', 'faculdades.json']", sw)
        self.assertIn("cache: 'no-cache'", sw)

    def test_visita_do_app_nao_vira_canal_de_origem(self):
        js = (gerar_site.DOCS / "assets" / "app.js").read_text(encoding="utf-8")
        self.assertIn("['brasil', 'exterior', 'app'].includes(q.get('origem'))", js)


class PaginaMeuPlano(unittest.TestCase):
    def test_pagina_continua_privada_e_na_mesma_url(self):
        html = (gerar_site.DOCS / "minha-lista" / "index.html").read_text(encoding="utf-8")
        self.assertIn('name="robots" content="noindex"', html)
        self.assertIn("<h1>Meu plano</h1>", html)
        self.assertIn('id="minha-lista"', html)

    def test_ficha_do_uva_mostra_o_cartao_com_antes_e_depois(self):
        pasta = gerar_site.DOCS / "edital"
        achou = [p for p in pasta.glob("uva-rio-externa-2027-1-*/index.html") if "cartao-ret" in p.read_text(encoding="utf-8")]
        self.assertTrue(achou, "o edital da UVA retificado em 09/11 precisa do cartão")
        html = achou[0].read_text(encoding="utf-8")
        self.assertIn("Retificado em 09/11", html)
        self.assertIn("<s>R$ 400</s>", html)
        self.assertIn("<b>R$ 250</b>", html)


if __name__ == "__main__":
    unittest.main()
