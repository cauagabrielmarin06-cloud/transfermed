"""Guia Exterior → Brasil 2027 (plano de receita, 19/11/2026): o botão "Comprar", o preço e as chamadas só existem com link de compra real.

Os testes usam um relógio e dados de teste fixos (nada de edital real com prazo) e isolam o ambiente: a máquina do dono pode ter
privado/receita/link_compra.txt e a variável LINK_COMPRA_GUIA, e isso não pode mudar o resultado.
"""
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gerar_site  # noqa: E402
import guia  # noqa: E402
import nutricao  # noqa: E402

PASTA = Path(__file__).resolve().parent.parent
HOJE = "2026-11-19"
LINK = "https://pay.exemplo.com.br/checkout/guia-exterior"
FAC = {"id": "fx", "nome": "Faculdade X", "sigla": "FX", "cidade": "Cidade", "uf": "SP", "tipo": "particular", "lat": -23.5, "lon": -46.6}
ED = {"id": "e1", "faculdade_id": "fx", "fonte_dados": "manual", "modalidade": "externa", "aceita_curso_exterior": True, "status": "ok",
      "url_edital": "https://x.br/edital.pdf", "inscricao_inicio": "2026-11-01", "inscricao_fim": "2026-12-20", "conferido_em": "2026-11-10",
      "semestre_ingresso": "2027.1"}


class Ambiente:
    """Sem link nenhum (variável e arquivo) ou com os que o teste escolher."""

    def __init__(self, link=None, preco=None, arquivo_link=None):
        self.link, self.preco, self.arquivo_link = link, preco, arquivo_link

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        arq = base / "link_compra.txt"
        if self.arquivo_link is not None:
            arq.write_text(self.arquivo_link, encoding="utf-8")
        env = {k: v for k, v in {"LINK_COMPRA_GUIA": self.link, "GUIA_PRECO": self.preco}.items() if v}
        self.mocks = [mock.patch.dict("os.environ", env, clear=False), mock.patch.object(guia, "ARQUIVO_LINK", arq),
                      mock.patch.object(guia, "ARQUIVO_PRECO", base / "preco.txt")]
        for m in self.mocks:
            m.start()
        if not self.link:
            import os
            os.environ.pop("LINK_COMPRA_GUIA", None)
        if not self.preco:
            import os
            os.environ.pop("GUIA_PRECO", None)
        return self

    def __exit__(self, *a):
        for m in reversed(self.mocks):
            m.stop()
        self.tmp.cleanup()


def pagina_guia():
    return gerar_site.pagina_guia_exterior({"fx": FAC}, [ED], HOJE)


def pagina_exterior():
    return gerar_site.pagina_exterior({"fx": FAC}, [ED], HOJE)


class LinkDeCompra(unittest.TestCase):
    def test_so_aceita_link_https_de_verdade(self):
        for ruim in ("", "   ", "http://pay.exemplo.com.br/x", "pay.exemplo.com.br/x", "https://localhost/x", "https://u:s@pay.exemplo.com.br/x",
                     "https://pay.exemplo.com.br/x y", 'https://pay.exemplo.com.br/"x', "javascript:alert(1)", "https://" + "a" * 300 + ".com"):
            self.assertEqual(guia.link_valido(ruim), "", ruim)
        self.assertEqual(guia.link_valido(f"  {LINK}  "), LINK)

    def test_variavel_vale_mais_que_o_arquivo_e_o_arquivo_aceita_bom_e_linha_vazia(self):
        with Ambiente(link=LINK, arquivo_link="https://outro.exemplo.com.br/y\n"):
            self.assertEqual(guia.link_compra(), LINK)
        with Ambiente(arquivo_link="﻿\n\n  https://outro.exemplo.com.br/y  \nsegunda linha ignorada\n"):
            self.assertEqual(guia.link_compra(), "https://outro.exemplo.com.br/y")
        with Ambiente(link="isto não é link", arquivo_link=LINK + "\n"):
            self.assertEqual(guia.link_compra(), LINK, "variável inválida cai para o arquivo")
        with Ambiente():
            self.assertEqual(guia.link_compra(), "")
            self.assertFalse(guia.ativo())
            self.assertIn("pré-lançamento", guia.estado())
        with Ambiente(link=LINK):
            self.assertIn("ATIVO", guia.estado())

    def test_preco_so_no_formato_certo(self):
        for bom in ("R$ 47", "R$47", "R$ 47,00", "R$ 1234,50"):
            with Ambiente(preco=bom):
                self.assertEqual(guia.preco(), bom)
        for ruim in ("47", "R$ quarenta", "R$ 47,5", "de R$ 97 por R$ 47", "<b>R$ 47</b>"):
            with Ambiente(preco=ruim):
                self.assertEqual(guia.preco(), "", ruim)


class PreLancamento(unittest.TestCase):
    """Sem link: nada de botão, preço ou chamada, e a página fica fora do Google."""

    def setUp(self):
        self.amb = Ambiente(preco="R$ 47")  # mesmo com preço no ambiente, sem link não pode aparecer valor nenhum
        self.amb.__enter__()
        self.addCleanup(self.amb.__exit__)

    def test_pagina_existe_sem_botao_sem_preco_e_com_noindex(self):
        html = pagina_guia()
        self.assertIn('<meta name="robots" content="noindex">', html)
        self.assertIn("ainda não está à venda", html)
        self.assertNotIn("Comprar", html)
        self.assertNotIn("guia_comprar", html)
        self.assertNotIn("R$", html, "nenhum valor: preço de mentira é o que este teste proíbe")
        self.assertNotIn("Reembolso", html)

    def test_nenhuma_chamada_aponta_para_a_pagina(self):
        self.assertEqual(gerar_site.chamada_guia("../", "exterior"), "")
        self.assertEqual(gerar_site.chamada_guia_radar(), "")
        self.assertNotIn("guia-exterior", pagina_exterior())

    def test_sem_link_o_e_mail_de_confirmacao_nao_cita_o_guia(self):
        a = {"token": "t", "perfil": {"origem": "exterior", "curso": "medicina"}}
        html = nutricao.confirmacao(a, "https://www.transfermed.com.br", 7)[1]
        self.assertNotIn("guia-exterior", html)

    def test_a_pagina_ainda_oferece_o_alerta_gratis_sem_caixa_pre_marcada(self):
        html = pagina_guia()
        self.assertIn('id="form-alerta"', html)
        caixa = re.search(r'<input type="checkbox" id="consentimento"[^>]*>', html).group(0)
        self.assertNotIn("checked", caixa, "consentimento nunca pré-marcado")


class ComLink(unittest.TestCase):
    def test_botao_comprar_aponta_para_a_plataforma_e_mede_o_clique(self):
        with Ambiente(link=LINK):
            html = pagina_guia()
        self.assertIn(f'href="{LINK}" target="_blank" rel="noopener" data-medir="guia_comprar">Comprar o guia', html)
        self.assertNotIn('<meta name="robots" content="noindex">', html)
        self.assertNotIn("ainda não está à venda", html)
        self.assertIn("Reembolso em até 7 dias", html)
        self.assertIn("Isto garante vaga?", html)
        self.assertNotRegex(html, r"R\$", "sem preço informado, a página não cita valor")

    def test_preco_aparece_so_quando_informado(self):
        with Ambiente(link=LINK, preco="R$ 47"):
            self.assertIn("Comprar o guia · R$ 47", pagina_guia())

    def test_url_com_caractere_perigoso_nao_vira_botao(self):
        with Ambiente(link='https://pay.exemplo.com.br/x"><script>alert(1)</script>'):
            html = pagina_guia()
        self.assertNotIn("<script>alert", html)
        self.assertNotIn("Comprar", html)

    def test_chamadas_na_exterior_e_no_radar(self):
        with Ambiente(link=LINK):
            ext = pagina_exterior()
            radar = gerar_site.chamada_guia_radar()
        self.assertIn('href="../guia-exterior/" data-medir="guia_chamada"', ext)
        self.assertIn('id="guia-radar" hidden', radar, "a chamada do radar nasce escondida: o app.js a mostra com o chip do exterior")
        self.assertIn('href="guia-exterior/"', radar)

    def test_e_mail_de_confirmacao_so_para_quem_estuda_fora_e_so_no_primeiro(self):
        site = "https://www.transfermed.com.br"
        fora = {"token": "t", "perfil": {"origem": "exterior", "curso": "medicina"}}
        brasil = {"token": "t", "perfil": {"origem": "brasil", "curso": "medicina"}}
        with Ambiente(link=LINK):
            assunto, html, texto = nutricao.confirmacao(fora, site, 7, etapa=0)
            self.assertIn(f"{site}/guia-exterior/?origem=email", html)
            self.assertIn(f"{site}/guia-exterior/?origem=email", texto, "o endereço também vai na versão em texto")
            self.assertIn("pago, opcional", texto)
            self.assertIn("Confirmar meus alertas", html, "o botão de confirmar continua o foco do e-mail")
            for etapa in (1, 2):
                self.assertNotIn("guia-exterior", nutricao.confirmacao(fora, site, 7, etapa=etapa)[1], f"lembrete {etapa}")
            self.assertNotIn("guia-exterior", nutricao.confirmacao(brasil, site, 7, etapa=0)[1])
            self.assertNotIn("guia-exterior", nutricao.confirmacao({"token": "t"}, site, 7, etapa=0)[1], "sem perfil")


class OsRobosRecebemAVariavel(unittest.TestCase):
    """Os robôs rodam sem a pasta privado/: sem a variável, o próximo site gerado por eles tiraria o botão do ar (mesmo tipo de falha de
    06/11/2026 com o Raio-X). Todo workflow que gera o site ou monta e-mail do alerta passa LINK_COMPRA_GUIA."""

    def test_workflows_que_geram_o_site_ou_o_email_do_alerta(self):
        for wf in sorted((PASTA / ".github" / "workflows").glob("*.yml")):
            texto = wf.read_text(encoding="utf-8")
            if re.search(r"python (-m \w+ )?(gerar_site|radar|monitor|alertas|nutricao)\.py|python (gerar_site|radar|monitor|alertas)\b", texto):
                self.assertIn("LINK_COMPRA_GUIA: ${{ vars.LINK_COMPRA_GUIA }}", texto, wf.name)
                self.assertIn("GUIA_PRECO: ${{ vars.GUIA_PRECO }}", texto, wf.name)


class SiteGerado(unittest.TestCase):
    """O que está em docs/ deve ser coerente com o estado do guia na hora em que foi gerado (nenhuma ponta solta)."""

    def test_pagina_gerada_existe_e_e_coerente(self):
        html = (gerar_site.DOCS / "guia-exterior" / "index.html").read_text(encoding="utf-8")
        ativa = "Comprar o guia" in html
        self.assertEqual(ativa, "noindex" not in html, "pré-lançamento = noindex; à venda = indexável")
        sitemap = (gerar_site.DOCS / "sitemap.xml").read_text(encoding="utf-8")
        self.assertEqual(ativa, "/guia-exterior/" in sitemap, "no sitemap só com o guia à venda")
        exterior = (gerar_site.DOCS / "exterior" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(ativa, 'href="../guia-exterior/"' in exterior, "a chamada na /exterior/ acompanha o estado do guia")
        inicio = (gerar_site.DOCS / "index.html").read_text(encoding="utf-8")
        self.assertEqual(ativa, 'id="guia-radar"' in inicio, "a chamada do radar acompanha o estado do guia")


if __name__ == "__main__":
    unittest.main()
