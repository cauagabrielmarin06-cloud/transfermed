"""Guardião (T6.2): site no ar, prazos vencidos ainda abertos, PDFs, e-mail (DNS), quarentena e linha semanal.
Nada acessa a rede: o cliente HTTP é falso."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import requests

PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))
import gerar_site  # noqa: E402
import guardiao  # noqa: E402


class Resp:
    def __init__(self, codigo=200, texto="", headers=None):
        self.status_code, self.text, self.headers = codigo, texto, headers or {}

    def json(self):
        return json.loads(self.text)

    def close(self):
        pass


class Http:
    """Respostas por URL (prefixo exato); URL ausente = erro de rede."""
    def __init__(self, mapa):
        self.mapa, self.chamadas = mapa, []

    def get(self, url, **kw):
        self.chamadas.append(url)
        r = self.mapa.get(url)
        if r is None:
            raise requests.ConnectionError("sem rede")
        return r


SITE = "https://www.transfermed.com.br"
SW = "const CACHE = 'tm-202611060000';"


def site_ok(extra=None):
    m = {SITE + "/": Resp(), "http://www.transfermed.com.br/": Resp(301, headers={"location": SITE + "/"}), SITE + "/sw.js": Resp(texto=SW)}
    m.update(extra or {})
    return Http(m)


class SiteNoAr(unittest.TestCase):
    def rodar(self, http, **kw):
        return guardiao.checar_site(http, sw_local="tm-202611060000", espera=(0,), dormir=lambda s: None, certificado=kw.get("cert", lambda h: 60))

    def test_tudo_certo_nao_gera_achado(self):
        self.assertEqual(self.rodar(site_ok()), [])

    def test_site_fora_do_ar_gera_achado(self):
        a = self.rodar(Http({}))
        self.assertEqual([x["chave"] for x in a], ["guardiao:home"])

    def test_certificado_perto_de_vencer(self):
        a = self.rodar(site_ok(), cert=lambda h: 5)
        self.assertEqual([x["chave"] for x in a], ["guardiao:certificado"])

    def test_http_sem_redirecionar_para_https(self):
        a = self.rodar(site_ok({"http://www.transfermed.com.br/": Resp(200)}))
        self.assertEqual([x["chave"] for x in a], ["guardiao:http-sem-redirecionar"])

    def test_deploy_defasado_e_detectado(self):
        a = self.rodar(site_ok({SITE + "/sw.js": Resp(texto="const CACHE = 'tm-antigo';")}))
        self.assertEqual([x["chave"] for x in a], ["guardiao:deploy-defasado"])

    def test_sitemap_com_pagina_quebrada(self):
        xml = "<urlset><loc>%s/a/</loc><loc>%s/b/</loc></urlset>" % (SITE, SITE)
        a, n = guardiao.checar_sitemap(Http({SITE + "/sitemap.xml": Resp(texto=xml), SITE + "/a/": Resp(), SITE + "/b/": Resp(404)}))
        self.assertEqual((n, [x["chave"] for x in a]), (2, ["guardiao:sitemap-paginas"]))
        self.assertIn("/b/", a[0]["corpo"])


class PrazosNoAr(unittest.TestCase):
    DADOS = 'window.TM={"editais":[{"id":"a","slug":"velho","fid":"x","fim":"2026-10-01","quem":"..."},{"id":"b","slug":"novo","fid":"x","fim":"2026-12-01"}]}'

    def test_prazo_vencido_ainda_aberto_gera_achado(self):
        http = Http({SITE + "/dados.js": Resp(texto=self.DADOS), SITE + "/edital/velho/": Resp(texto="Inscrições abertas até 01/10/2026")})
        a, n = guardiao.checar_prazos_no_ar(http, "2026-11-06")
        self.assertEqual((n, [x["chave"] for x in a], a[0]["etiqueta"]), (2, ["guardiao:prazo-vencido-aberto"], "prazo"))

    def test_prazo_vencido_mostrado_como_encerrado_passa(self):
        http = Http({SITE + "/dados.js": Resp(texto=self.DADOS), SITE + "/edital/velho/": Resp(texto="Encerrado em 01/10/2026")})
        self.assertEqual(guardiao.checar_prazos_no_ar(http, "2026-11-06")[0], [])


class PdfsAbertos(unittest.TestCase):
    def ed(self, **kw):
        d = {"id": "e1", "fonte_dados": "manual", "inscricao_inicio": "2026-10-01", "inscricao_fim": "2026-12-01", "url_edital": "https://x.br/a.pdf"}
        return {**d, **kw}

    def test_pdf_que_nao_abre_em_edital_aberto(self):
        a = guardiao.checar_pdfs_abertos([self.ed()], "2026-11-06", Http({"https://x.br/a.pdf": Resp(404)}))
        self.assertEqual([x["chave"] for x in a], ["guardiao:pdfs"])

    def test_edital_encerrado_nao_e_conferido(self):
        http = Http({})
        self.assertEqual(guardiao.checar_pdfs_abertos([self.ed(inscricao_fim="2026-10-05")], "2026-11-06", http), [])
        self.assertEqual(http.chamadas, [])

    def test_pdf_que_abre_passa(self):
        self.assertEqual(guardiao.checar_pdfs_abertos([self.ed()], "2026-11-06", Http({"https://x.br/a.pdf": Resp(200)})), [])


class EmailPorDns(unittest.TestCase):
    def consulta(self, spf="v=spf1 include:spf.brevo.com ~all", dmarc="v=DMARC1; p=none", dkim=True, mx=True):
        def f(http, nome, tipo="TXT"):
            if nome == "transfermed.com.br" and tipo == "TXT":
                return [spf] if spf else []
            if nome.startswith("_dmarc."):
                return [dmarc] if dmarc else []
            if "_domainkey" in nome:
                return ["brevo1.domainkey.brevo.com"] if dkim and nome.startswith("brevo1") else []
            return ["10 mx.x"] if mx else []
        return f

    def test_configuracao_correta(self):
        a, pol, indisp = guardiao.checar_email(None, consulta=self.consulta())
        self.assertEqual((a, pol, indisp), ([], "none", None))

    def test_dmarc_ausente_e_spf_sem_brevo(self):
        a, _, _ = guardiao.checar_email(None, consulta=self.consulta(spf="v=spf1 -all", dmarc=None))
        self.assertIn("DMARC ausente", a[0]["corpo"])
        self.assertIn("SPF não autoriza o Brevo", a[0]["corpo"])

    def test_dns_fora_do_ar_nao_vira_alarme_falso(self):
        def quebra(*a, **k):
            raise requests.ConnectionError("x")
        self.assertEqual(guardiao.checar_email(None, consulta=quebra)[0], [])

    def test_nunca_envia_nada(self):
        import inspect
        fonte = inspect.getsource(guardiao)
        for proibido in ("api.brevo.com", "smtp", "sendinblue.com/v3", ".post("):
            self.assertNotIn(proibido, fonte)


class Quarentena(unittest.TestCase):
    def ed(self, **kw):
        d = {"id": "e1", "faculdade_id": "f", "fonte_dados": "manual", "status": "ok", "inscricao_inicio": "2026-10-01",
             "inscricao_fim": "2026-12-01", "url_edital": "https://x.br/a.pdf", "conferido_em": "2026-10-20"}
        return {**d, **kw}

    def test_pdf_trocado_depois_da_conferencia_entra_na_quarentena(self):
        q = guardiao.calcular_quarentena([self.ed()], {"https://x.br/a.pdf": "2026-11-05"}, {}, "2026-11-06")
        self.assertEqual(q["e1"]["desde"], "2026-11-05")

    def test_pdf_trocado_antes_da_conferencia_nao_entra(self):
        self.assertEqual(guardiao.calcular_quarentena([self.ed()], {"https://x.br/a.pdf": "2026-10-10"}, {}, "2026-11-06"), {})

    def test_reconferido_sai_sozinho(self):
        anterior = {"e1": {"desde": "2026-11-05", "motivo": "pdf_trocado", "url": "u"}}
        self.assertEqual(guardiao.calcular_quarentena([self.ed(conferido_em="2026-11-06")], {}, anterior, "2026-11-06"), {})
        self.assertIn("e1", guardiao.calcular_quarentena([self.ed()], {}, anterior, "2026-11-06"))

    def test_edital_em_quarentena_vira_conferir_no_prazo_e_sai_dos_emails(self):
        with tempfile.TemporaryDirectory() as t:
            arq = Path(t) / "q.json"
            arq.write_text(json.dumps({"editais": {"e1": {"desde": "2026-11-05", "motivo": "pdf_trocado", "url": "u"}}}), encoding="utf-8")
            ed = gerar_site.aplicar_quarentena([self.ed()], arq)[0]
            self.assertEqual(ed["status"], "conferir")
            self.assertIn("inscricao_fim", gerar_site.campos_conferir(ed))
            self.assertTrue(gerar_site.fora_dos_emails(ed))
            reconferido = gerar_site.aplicar_quarentena([self.ed(conferido_em="2026-11-06")], arq)[0]
            self.assertEqual(reconferido["status"], "ok")

    def test_sem_arquivo_nada_muda(self):
        ed = gerar_site.aplicar_quarentena([self.ed()], Path("nao-existe.json"))[0]
        self.assertEqual(ed["status"], "ok")

    def test_edital_do_robo_nunca_e_publicado(self):
        robo = self.ed(fonte_dados="robo", detectado_em="2026-11-01")
        self.assertFalse(gerar_site.publicavel(robo))
        self.assertEqual(guardiao.esperando_conferencia([robo, self.ed()], "2026-11-06"), 1)


class ResumoSemanal(unittest.TestCase):
    def test_linha_sem_falhas(self):
        r = {"historico": [{"dia": f"2026-11-0{d}", "falhas": 0, "chaves": []} for d in range(2, 8)], "quarentena": 0, "aguardando_conferencia": 6, "dmarc": "none"}
        linha = guardiao.linha_semanal(r, "2026-11-08")
        self.assertIn("6 de 7 dias vigiados, nenhuma falha", linha)
        self.assertIn("DMARC p=none", linha)

    def test_linha_com_falha_e_sem_execucao(self):
        r = {"historico": [{"dia": "2026-11-05", "falhas": 1, "chaves": ["guardiao:pdfs"]}]}
        self.assertIn("guardiao:pdfs", guardiao.linha_semanal(r, "2026-11-08"))
        self.assertIn("nenhuma execução", guardiao.linha_semanal({"historico": [{"dia": "2026-10-01", "falhas": 0, "chaves": []}]}, "2026-11-08"))
        self.assertIn("ainda sem execução", guardiao.linha_semanal({}, "2026-11-08"))

    def test_falha_simulada_abre_uma_issue_so(self):
        import issues
        a = guardiao.achado("pdfs", "x", "corpo")
        acoes = issues.planejar([a, a], [], "guardiao")
        self.assertEqual([x[0] for x in acoes], ["criar"])


if __name__ == "__main__":
    unittest.main()
