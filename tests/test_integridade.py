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
        self.assertEqual(len(list((docs / "edital").glob("*/index.html"))), len(ED))
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
