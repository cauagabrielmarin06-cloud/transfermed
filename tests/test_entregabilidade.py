"""Entregabilidade dos e-mails automáticos (entregabilidade.py, 10/11/2026): contrato de cada modelo, descadastro em um clique com sonda,
multipart + Reply-To no envio, leitura do rastreio do Brevo, nota do mail-tester e o botão "Não chegou? Reenviar"."""
import sys
import unittest
from pathlib import Path
from unittest import mock

PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))
import alertas  # noqa: E402
import entregabilidade as en  # noqa: E402
import funcoes  # noqa: E402
import nutricao  # noqa: E402
from tests.test_nutricao import FAC, assinante, ed  # noqa: E402

SITE = en.SITE
HOJE = "2026-11-18"


def contexto():
    return nutricao.Contexto([ed(id="e1"), ed(id="e2", inscricao_fim="2026-11-30")], {"x": FAC}, SITE, HOJE)


def itens():
    return [(ed(id="e1"), FAC), (ed(id="e2", inscricao_fim="2026-11-30"), FAC), (ed(id="e3", inscricao_fim="2026-12-20"), FAC)]


def modelos():
    """Um e-mail de cada família que o robô envia: confirmação (3 etapas), lembrete com valor, alerta e lembretes de prazo."""
    a, c = assinante(status="pendente", token="11111111-1111-4111-8111-111111111111"), contexto()
    saida = {f"confirmação etapa {n}": nutricao.confirmacao(a, SITE, 7, n) for n in (0, 1, 2)}
    for etapa in (None, 1, 2):
        saida[f"lembrete com valor ({etapa})"] = nutricao.lembrete_valor(a, c, itens(), 7, etapa)
    saida["alerta"] = nutricao.alerta(assinante(token=a["token"]), c, itens())
    saida["alerta de 1 edital"] = nutricao.alerta(assinante(token=a["token"]), c, itens()[:1])
    for tipo, falta in ((7, 5), (2, 1), (2, 0)):
        assunto, previa, corpo = nutricao.lembrete(assinante(token=a["token"]), c, tipo, falta, ed(documentos=["Histórico escolar"]), FAC)
        saida[f"lembrete de prazo {tipo}d"] = nutricao.finalizar(assinante(token=a["token"]), SITE, assunto, previa, corpo)
    return saida


class ContratoDoModelo(unittest.TestCase):
    def test_todo_modelo_cumpre_o_contrato(self):
        for nome, (assunto, html, texto) in modelos().items():
            with self.subTest(nome):
                self.assertEqual(en.checar_email(assunto, html, texto), [])

    def test_multipart_primeira_linha_e_rodape(self):
        for nome, (assunto, html, texto) in modelos().items():
            with self.subTest(nome):
                self.assertTrue(texto.startswith("Você pediu um alerta no Transfermed."))
                self.assertIn("Você pediu um alerta no Transfermed.", html)
                self.assertIn("Você recebe este e-mail porque", texto)
                self.assertIn("Para sair, use este link", texto)
                self.assertNotRegex(texto, r"</?(?:p|a|div|span|table|tr|td|strong|br|h[1-6]|li|ul)[ >/]", "a versão em texto não leva HTML")

    def test_no_maximo_2_links_todos_diretos_no_site(self):
        for nome, (_, html, texto) in modelos().items():
            with self.subTest(nome):
                links = en._urls(texto) | en._urls(html)
                self.assertLessEqual(len(links), 2, links)
                self.assertTrue(all(u.startswith(SITE + "/") for u in links), links)
                self.assertNotIn("<img", html)

    def test_o_checador_pega_cada_defeito(self):
        assunto, html, texto = nutricao.confirmacao(assinante(status="pendente"), SITE, 7, 0)
        casos = {
            "sem texto": (assunto, html, ""),
            "primeira linha": (assunto, html, "Oi!\n" + texto),
            "imagem": (assunto, html.replace("<h1", '<img src="https://www.transfermed.com.br/x.png"><h1', 1), texto),
            "pixel": (assunto, html.replace("<h1", '<img width="1" height="1" src="https://t.exemplo/p.gif"><h1', 1), texto),
            "3 links": (assunto, html.replace("<h1", f'<a href="{SITE}/a/">a</a><a href="{SITE}/b/">b</a><h1', 1), texto),
            "link de terceiro": (assunto, html.replace("<h1", '<a href="https://exemplo.com/x">x</a><h1', 1), texto),
            "redirecionador": (assunto, html.replace("<h1", '<a href="https://sendibt3.com/tr/cl/x">x</a><h1', 1), texto),
            "palavra de venda": (assunto, html, texto + " Grátis: aproveite"),
            "assunto gritado": ("CONFIRME SEU ALERTA AGORA!!", html, texto),
            "html pesado": (assunto, html + "<!--" + "x" * 41000 + "-->", texto),
            "rodapé sem saída": (assunto, html, texto.split("\n--\n")[0]),
        }
        for nome, args in casos.items():
            with self.subTest(nome):
                self.assertTrue(en.checar_email(*args), f"o checador deixou passar: {nome}")


class DescadastroUmClique(unittest.TestCase):
    URL = "https://abc.supabase.co"

    def http(self, codigo=None, erro=None):
        h = mock.Mock()
        if erro:
            h.post.side_effect = erro
        else:
            h.post.return_value = mock.Mock(status_code=codigo)
        return h

    def test_esta_ligado_por_padrao_no_codigo(self):
        self.assertIn("DESCADASTRO_UM_CLIQUE", funcoes.LIGADAS_POR_PADRAO)
        with mock.patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("DESCADASTRO_UM_CLIQUE", None)
            self.assertTrue(funcoes.ligada("DESCADASTRO_UM_CLIQUE"))
            url, _ = en.um_clique_url(self.URL, http=self.http(400))
            self.assertEqual(url, self.URL + "/functions/v1/descadastrar")

    def test_so_o_zero_desliga(self):
        url, motivo = en.um_clique_url(self.URL, http=self.http(400), ambiente={"DESCADASTRO_UM_CLIQUE": "0"})
        self.assertIsNone(url)
        self.assertIn("desligado", motivo)
        for valor in ("", "1", "   1"):
            self.assertIsNotNone(en.um_clique_url(self.URL, http=self.http(400), ambiente={"DESCADASTRO_UM_CLIQUE": valor})[0], repr(valor))

    def test_sonda_sem_funcao_no_ar_cai_no_link_da_pagina(self):
        for codigo, trecho in ((404, "não implantada"), (401, "JWT"), (403, "JWT"), (500, "HTTP 500")):
            with self.subTest(codigo):
                url, motivo = en.um_clique_url(self.URL, http=self.http(codigo))
                self.assertIsNone(url)
                self.assertIn(trecho, motivo)

    def test_rede_fora_do_ar_nao_derruba_o_envio(self):
        url, motivo = en.um_clique_url(self.URL, http=self.http(erro=OSError("sem rede")))
        self.assertIsNone(url)
        self.assertIn("sonda sem resposta", motivo)

    def test_a_sonda_nao_apaga_ninguem(self):
        h = self.http(400)
        en.um_clique_url(self.URL, http=h)
        args, kw = h.post.call_args
        self.assertIn("sonda-sem-token", args[0])  # token que não é UUID: a função recusa antes de chamar o banco

    def test_cabecalhos_do_envio_com_e_sem_a_funcao(self):
        tok = "11111111-1111-4111-8111-111111111111"
        com = alertas.cabecalhos_descadastro(tok, self.URL + "/functions/v1/descadastrar")
        self.assertEqual(com["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")
        self.assertIn(f"?t={tok}>", com["List-Unsubscribe"])
        sem = alertas.cabecalhos_descadastro(tok, None)
        self.assertNotIn("List-Unsubscribe-Post", sem)
        self.assertIn("/alerta/descadastrar/?t=", sem["List-Unsubscribe"])


class EnvioBrevo(unittest.TestCase):
    def enviar(self, **kw):
        with mock.patch.object(alertas.requests, "post") as post:
            post.return_value = mock.Mock(raise_for_status=lambda: None)
            e = alertas.EnvioBrevo("chave", "alertas@exemplo.org", "Nome", **kw)
            e.enviar("pessoa@exemplo.org", "Assunto", "<p>oi</p>", "oi", "11111111-1111-4111-8111-111111111111")
            return post.call_args.kwargs["json"]

    def test_multipart_com_texto_e_html(self):
        corpo = self.enviar()
        self.assertEqual((corpo["htmlContent"], corpo["textContent"]), ("<p>oi</p>", "oi"))

    def test_reply_to_padrao_vem_da_variavel(self):
        self.assertEqual(self.enviar(responder_para="resposta@exemplo.org")["replyTo"], {"email": "resposta@exemplo.org"})
        self.assertNotIn("replyTo", self.enviar())

    def test_cabecalhos_de_descadastro_vao_no_envio(self):
        corpo = self.enviar(um_clique="https://abc.supabase.co/functions/v1/descadastrar")
        self.assertEqual(corpo["headers"]["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")

    def test_nenhum_campo_de_rastreio_no_envio(self):
        texto = str(self.enviar(um_clique="https://x/f")).lower()
        for proibido in ("pixel_tracking", "trackopens", "trackclicks", "tracking_pixel"):
            self.assertNotIn(proibido, texto.replace("contactpixeltrackingconsent", ""))

    def test_remetentes_usam_o_reply_to_do_ambiente(self):
        for arq in ("alertas.py", "lembrete_valor.py"):
            self.assertIn("REPLY_TO_EMAIL", (PASTA / arq).read_text(encoding="utf-8"), arq)


class RastreioBrevo(unittest.TestCase):
    def test_le_aberturas_e_cliques(self):
        h = mock.Mock()
        h.get.return_value = mock.Mock(status_code=200, json=lambda: {"opens": 4, "clicks": 2, "requests": 30})
        self.assertEqual(en.rastreio_brevo("k", http=h), {"aberturas": 4, "cliques": 2, "enviados": 30})

    def test_falha_vira_none(self):
        h = mock.Mock()
        h.get.return_value = mock.Mock(status_code=401)
        self.assertIsNone(en.rastreio_brevo("k", http=h))
        h.get.side_effect = OSError("x")
        self.assertIsNone(en.rastreio_brevo("k", http=h))


class NotaMailTester(unittest.TestCase):
    def test_ler_nota(self):
        self.assertEqual(en.ler_nota({"mark": 9.5}), 9.5)
        self.assertEqual(en.ler_nota({"spamAssassin": {"mark": -0.5}, "signature": {"mark": 0}, "body": {"mark": -0.3}}), 9.2)
        for ruim in (None, {}, {"status": False, "title": "erro"}, "x"):
            self.assertIsNone(en.ler_nota(ruim))

    def test_so_nota_medida_e_baixa_trava(self):
        self.assertEqual(en.decidir(10)[0], "ok")
        self.assertEqual(en.decidir(9.0)[0], "ok")
        self.assertEqual(en.decidir(8.9)[0], "reprovado")
        self.assertEqual(en.decidir(None)[0], "nao_medido")

    def test_espera_a_mensagem_chegar(self):
        respostas = [mock.Mock(status_code=200, json=lambda: {"status": False}), mock.Mock(status_code=404), mock.Mock(status_code=200, json=lambda: {"mark": 10})]
        h = mock.Mock()
        h.get.side_effect = respostas
        espera = mock.Mock()
        nota, det = en.consultar_nota("usuario", "abc", http=h, tentativas=5, dormir=espera)
        self.assertEqual((nota, det), (10.0, "ok"))
        self.assertEqual(espera.call_count, 2)
        self.assertIn("usuario-abc", h.get.call_args.args[0])

    def test_sem_resposta_devolve_nao_medido(self):
        h = mock.Mock()
        h.get.side_effect = OSError("fora do ar")
        nota, det = en.consultar_nota("u", "s", http=h, tentativas=3, dormir=mock.Mock())
        self.assertIsNone(nota)
        self.assertIn("não devolveu a nota", det)


class BotaoReenviar(unittest.TestCase):
    JS = (PASTA / "docs" / "assets" / "app.js").read_text(encoding="utf-8")

    def test_botao_e_dica_de_spam_e_promocoes(self):
        self.assertIn("Não chegou? Reenviar", self.JS)
        self.assertIn("Spam", self.JS)
        self.assertIn("Promoções", self.JS)

    def test_reenvio_usa_o_inscrever_e_respeita_10_minutos(self):
        trecho = self.JS[self.JS.index("const ligarReenvio"):]
        trecho = trecho[:trecho.index("setTimeout(ligarReenvio")]
        self.assertIn("rpc('inscrever'", trecho)
        self.assertIn("600000", trecho)  # 10 minutos, igual à regra do inscrever no banco
        self.assertIn("tm_reenvio", trecho)

    def test_regra_de_10_minutos_continua_no_banco(self):
        sql = (PASTA / "supabase" / "schema.sql").read_text(encoding="utf-8")
        self.assertIn("confirmacao_enviada_em < now() - interval '10 minutes'", sql)


if __name__ == "__main__":
    unittest.main()
