"""Nota automática (nota_entrega.py), a trava dos envios (entregabilidade.liberado) e as linhas do relatório semanal."""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))
import alertas  # noqa: E402
import entregabilidade as en  # noqa: E402
import nota_entrega  # noqa: E402

ENV = {"MAILTESTER_USUARIO": "dono", "BREVO_API_KEY": "k", "REMETENTE_EMAIL": "alertas@exemplo.org", "REPLY_TO_EMAIL": "resp@exemplo.org"}


def rodar(env, http=None, args=("--enviar",)):
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(en, "REGISTRO", Path(tmp) / "nota.json"), \
            mock.patch.object(alertas.requests, "post") as post, redirect_stdout(io.StringIO()) as saida:
        post.return_value = mock.Mock(raise_for_status=lambda: None)
        codigo = nota_entrega.main(list(args), env=env, http=http, dormir=mock.Mock())
        reg = json.loads((Path(tmp) / "nota.json").read_text(encoding="utf-8")) if (Path(tmp) / "nota.json").exists() else None
        return codigo, reg, post.call_args_list, saida.getvalue()


def mailtester(nota):
    h = mock.Mock()
    h.get.return_value = mock.Mock(status_code=200, json=lambda: {"mark": nota})
    return h


class NotaAutomatica(unittest.TestCase):
    def test_nota_alta_passa_envia_3_copias_com_os_cabecalhos_reais(self):
        codigo, reg, envios, _ = rodar(ENV, mailtester(10))
        self.assertEqual((codigo, reg["estado"], reg["nota"]), (0, "ok", 10.0))
        self.assertEqual(len(envios), 3)
        for c in envios:
            corpo = c.kwargs["json"]
            self.assertRegex(corpo["to"][0]["email"], r"^dono-[0-9a-f]{10}@mail-tester\.com$")
            self.assertTrue(corpo["textContent"].startswith("Você pediu um alerta no Transfermed."))
            self.assertEqual(corpo["replyTo"], {"email": "resp@exemplo.org"})
            self.assertIn("List-Unsubscribe", corpo["headers"])

    def test_nota_abaixo_de_9_trava(self):
        codigo, reg, _, saida = rodar(ENV, mailtester(8.4))
        self.assertEqual((codigo, reg["estado"], reg["nota"]), (1, "reprovado", 8.4))
        self.assertIn("publicação travada", saida)

    def test_vale_a_pior_nota_dos_modelos(self):
        h = mock.Mock()
        h.get.side_effect = [mock.Mock(status_code=200, json=lambda n=n: {"mark": n}) for n in (10, 8.8, 9.5)]
        codigo, reg, _, _ = rodar(ENV, h)
        self.assertEqual((codigo, reg["nota"]), (1, 8.8))

    def test_sem_conta_do_mail_tester_nao_mede_e_nao_inventa(self):
        codigo, reg, envios, _ = rodar({k: v for k, v in ENV.items() if k != "MAILTESTER_USUARIO"})
        self.assertEqual((codigo, reg["estado"], reg["nota"], envios), (0, "nao_medido", None, []))
        self.assertIn("MAILTESTER_USUARIO", reg["detalhe"])

    def test_mail_tester_fora_do_ar_nao_trava(self):
        h = mock.Mock()
        h.get.side_effect = OSError("fora do ar")
        codigo, reg, _, _ = rodar(ENV, h)
        self.assertEqual((codigo, reg["estado"]), (0, "nao_medido"))
        self.assertIsNone(reg["nota"])

    def test_registro_publico_nao_tem_email_nem_segredo(self):
        _, reg, _, _ = rodar(ENV, mailtester(10))
        texto = json.dumps(reg)
        for proibido in ("@", "dono", "alertas@", "resp@", "k"):
            if proibido in ("dono", "k"):
                continue  # palavras curtas demais para procurar em texto solto
            self.assertNotIn(proibido, texto)
        self.assertNotIn("mail-tester.com", texto)

    def test_so_contrato_sem_enviar(self):
        codigo, reg, envios, _ = rodar(ENV, args=())
        self.assertEqual((codigo, reg["estado"], envios), (0, "nao_medido", []))

    def test_modelo_fora_do_contrato_trava_antes_de_enviar(self):
        original = nota_entrega.modelos_de_teste

        def quebrado(site):
            modelos, token = original(site)
            nome, (assunto, html, texto) = modelos[0]
            return [(nome, (assunto, html + '<img src="https://www.transfermed.com.br/x.png">', texto))], token
        with mock.patch.object(nota_entrega, "modelos_de_teste", quebrado):
            codigo, reg, envios, saida = rodar(ENV, mailtester(10))
        self.assertEqual(codigo, 1)
        self.assertEqual(envios, [])
        self.assertIn("descumpre o contrato", saida)


class TravaDosEnvios(unittest.TestCase):
    H = "abc123"

    def test_so_trava_com_nota_medida_baixa_dos_modelos_atuais(self):
        self.assertTrue(en.liberado(None, self.H)[0])
        self.assertTrue(en.liberado({"hash": "outro", "estado": "reprovado", "nota": 5}, self.H)[0], "nota de modelo antigo não trava o novo")
        self.assertTrue(en.liberado({"hash": self.H, "estado": "nao_medido", "nota": None}, self.H)[0])
        self.assertTrue(en.liberado({"hash": self.H, "estado": "ok", "nota": 9.5}, self.H)[0])
        livre, motivo = en.liberado({"hash": self.H, "estado": "reprovado", "nota": 8.1, "gerado_em": "2026-11-10T10:00:00"}, self.H)
        self.assertFalse(livre)
        self.assertIn("8.1/10", motivo)

    def test_chave_do_dono_libera(self):
        reg = {"hash": self.H, "estado": "reprovado", "nota": 7}
        self.assertTrue(en.liberado(reg, self.H, {"NOTA_ENTREGA_MINIMA": "0"})[0])
        self.assertFalse(en.liberado(reg, self.H, {"NOTA_ENTREGA_MINIMA": ""})[0], "variável vazia = padrão 9")
        self.assertFalse(en.liberado(reg, self.H, {"NOTA_ENTREGA_MINIMA": "lixo"})[0])

    def test_hash_muda_quando_o_modelo_muda_e_ignora_fim_de_linha(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "nutricao.py").write_bytes(b"a\nb\n")
            h1 = en.hash_modelos(tmp)
            (Path(tmp) / "nutricao.py").write_bytes(b"a\r\nb\r\n")
            self.assertEqual(en.hash_modelos(tmp), h1)
            (Path(tmp) / "nutricao.py").write_bytes(b"a\nc\n")
            self.assertNotEqual(en.hash_modelos(tmp), h1)

    def test_o_envio_real_para_quando_reprovado_e_mostra_o_motivo(self):
        reg = {"hash": en.hash_modelos(), "estado": "reprovado", "nota": 7.0, "gerado_em": "2026-11-10T10:00:00"}
        env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_KEY": "s", "BREVO_API_KEY": "k", "REMETENTE_EMAIL": "a@b.c"}
        for modulo in ("alertas",):
            with mock.patch.dict("os.environ", env), mock.patch.object(en, "ler_registro", return_value=reg), \
                    mock.patch.object(alertas, "BancoSupabase") as banco, redirect_stdout(io.StringIO()) as saida, \
                    mock.patch.object(sys, "argv", ["alertas.py"]):
                self.assertEqual(alertas.main(), 1)
            self.assertIn("trava de entregabilidade", saida.getvalue())
            banco.assert_not_called()  # nada foi lido nem enviado


class LinhasDoRelatorio(unittest.TestCase):
    def test_com_nota_e_sem_rastreio(self):
        linhas = en.linhas_relatorio({"aberturas": 0, "cliques": 0}, {"hash": "h", "nota": 9.7, "gerado_em": "2026-11-10T10:00:00"}, "h")
        self.assertIn("9.7/10", linhas[0])
        self.assertIn("sem rastreamento", linhas[1])

    def test_nota_de_modelo_anterior_e_avisada(self):
        linhas = en.linhas_relatorio(None, {"hash": "velho", "nota": 9.7, "gerado_em": "2026-11-01T10:00:00"}, "novo")
        self.assertIn("modelo anterior", linhas[0])
        self.assertIn("não medido", linhas[1])

    def test_sem_nota_diz_por_que(self):
        linhas = en.linhas_relatorio({"aberturas": 3, "cliques": 1}, {"hash": "h", "nota": None, "detalhe": "falta a conta do mail-tester"}, "h")
        self.assertIn("nota não medida (falta a conta do mail-tester)", linhas[0])
        self.assertIn("ainda está ligado", linhas[1])
        self.assertIn("nenhuma medição", en.linhas_relatorio(None, {}, "h")[0])

    def test_entra_nos_numeros_do_dia(self):
        import relatorio
        with mock.patch.object(en, "ler_registro", return_value={"hash": "h", "nota": 9.0, "gerado_em": "2026-11-10T10:00:00"}):
            n = relatorio.numeros_do_dia([], [], __import__("datetime").date(2026, 11, 10), {"enviados": 5, "entregues": 5, "aberturas": 0, "cliques": 0})
            texto = "\n".join(relatorio.texto_numeros_do_dia(n))
        self.assertIn("Entregabilidade (nota do mail-tester", texto)
        self.assertIn("Rastreamento do Brevo em 7 dias", texto)


class Workflows(unittest.TestCase):
    def test_workflow_da_nota_roda_a_cada_mudanca_de_modelo(self):
        y = (PASTA / ".github" / "workflows" / "entregabilidade.yml").read_text(encoding="utf-8")
        self.assertIn('"nutricao.py"', y)
        self.assertIn("MAILTESTER_USUARIO: ${{ secrets.MAILTESTER_USUARIO }}", y)
        self.assertIn("python nota_entrega.py --enviar", y)

    def test_workflows_de_envio_levam_reply_to_e_a_trava(self):
        for arq in ("alertas.yml", "lembrete_valor.yml"):
            y = (PASTA / ".github" / "workflows" / arq).read_text(encoding="utf-8")
            self.assertIn("REPLY_TO_EMAIL: ${{ vars.REPLY_TO_EMAIL }}", y, arq)
            self.assertIn("NOTA_ENTREGA_MINIMA", y, arq)


if __name__ == "__main__":
    unittest.main()
