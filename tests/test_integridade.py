"""Integridade da base e do envio: contagens que já geraram dúvida e o rastreio anônimo do Brevo."""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))
import alertas  # noqa: E402

FAC = json.loads((PASTA / "data" / "faculdades.json").read_text(encoding="utf-8"))
ED = json.loads((PASTA / "data" / "editais.json").read_text(encoding="utf-8"))


class ContagemFaculdadesEEditais(unittest.TestCase):
    """O número de faculdades e o de editais são grandezas diferentes (uma faculdade pode ter vários editais ou
    nenhum). Em 01/11/2026 os dois deram 206 por coincidência; este teste prova que não há dado emprestado."""

    def test_todo_edital_aponta_para_uma_faculdade_que_existe(self):
        ids = {f["id"] for f in FAC}
        soltos = sorted({e["faculdade_id"] for e in ED} - ids)
        self.assertEqual(soltos, [])

    def test_ids_nao_se_repetem(self):
        for nome, itens in (("faculdades", FAC), ("editais", ED)):
            ids = [x["id"] for x in itens]
            self.assertEqual(len(ids), len(set(ids)), f"id repetido em {nome}")

    def test_cada_edital_tem_sua_pagina_e_cada_faculdade_a_dela(self):
        docs = PASTA / "docs"
        # só edital publicável (conferido à mão) ganha página; o que o robô achou e ainda não foi conferido fica de fora
        import gerar_site
        publicaveis = [e for e in ED if gerar_site.publicavel(e)]
        self.assertEqual(len(list((docs / "edital").glob("*/index.html"))), len(publicaveis))
        self.assertEqual(len(list((docs / "faculdade").glob("*/index.html"))), len(FAC))


class RastreioAnonimoNoBrevo(unittest.TestCase):
    """O Brevo não deixa desligar a reescrita de links por e-mail (só o rastreio anônimo). O código pede o
    anonimato de cada destinatário (contactPixelTrackingConsent=false); sem o recurso na conta, o campo é ignorado."""

    def test_destinatario_vai_com_rastreio_anonimo(self):
        envio = alertas.EnvioBrevo("chave", "de@exemplo.org", "Transfermed")
        resp = mock.Mock(status_code=201)
        resp.raise_for_status.return_value = None
        with mock.patch.object(alertas.requests, "post", return_value=resp) as post:
            envio.enviar("aluno@exemplo.org", "Assunto", "<p>oi</p>", "oi", "token123")
        corpo = post.call_args.kwargs["json"]
        self.assertEqual(corpo["to"], [{"email": "aluno@exemplo.org", "contactPixelTrackingConsent": False}])


if __name__ == "__main__":
    unittest.main()


class LogoDaMarca(unittest.TestCase):
    """Logo v2 aprovada em 06/11/2026: ícones com versão no nome (cache) e logo decorativa (alt vazio: o nome está escrito ao lado) no cabeçalho."""

    def test_arquivos_da_marca_existem_e_a_home_os_usa(self):
        from PIL import Image
        docs = PASTA / "docs"
        for nome, tam in (("logo-32-v3.png", 32), ("logo-180-v3.png", 180), ("logo-192-v3.png", 192), ("logo-512-v3.png", 512)):
            self.assertEqual(Image.open(docs / "assets" / "marca" / nome).size, (tam, tam))
        self.assertTrue((docs / "assets" / "marca" / "favicon-v3.ico").exists())
        html = (docs / "index.html").read_text(encoding="utf-8")
        for esperado in ("./assets/marca/favicon-v3.ico", "./assets/marca/favicon-v3.svg", 'rel="apple-touch-icon" href="./assets/marca/logo-180-v3.png"',
                         'og:image" content="https://www.transfermed.com.br/assets/marca/logo-512-v3.png"',
                         '<img src="./assets/marca/transfermed-logo-v3.svg" alt="" width="36" height="36">'):
            self.assertIn(esperado, html)
        self.assertNotIn("assets/icone-192.png", html.split("</head>")[0])

    def test_manifest_usa_os_icones_da_logo_v2_com_versao_e_nada_mais_mudou(self):
        m = json.loads((PASTA / "docs" / "manifest.webmanifest").read_text(encoding="utf-8"))
        self.assertEqual([(i["src"], i["sizes"], i.get("purpose")) for i in m["icons"]],
                         [("assets/marca/logo-192-v3.png", "192x192", None), ("assets/marca/logo-512-v3.png", "512x512", "any maskable")])
        self.assertEqual((m["display"], m["start_url"], m["scope"]), ("standalone", "./", "./"))
        html = (PASTA / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertIn('<img src="./assets/marca/transfermed-logo-v3.svg" alt="" width="28" height="28">', html)
