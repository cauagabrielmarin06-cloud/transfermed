"""Envio B0: texto puro (sem pixel nem HTML), a partir de contato@transfermed.com.br, sem imprimir destinatário nem conteúdo."""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import envio_b0  # noqa: E402

P = {"para": "relacionamento@exemplo.edu.br", "assunto": "Perfil oficial grátis", "corpo": "Prezada equipe,\n\nTexto."}


class Resp:
    def __init__(self, status=201, corpo=None, texto=""):
        self.status_code, self._c, self.text = status, corpo or {"messageId": "<abc@smtp>"}, texto

    def json(self):
        return self._c


class EnvioB0(unittest.TestCase):
    def test_so_texto_sem_html_sem_pixel_e_do_remetente_certo(self):
        c = envio_b0.montar(P)
        self.assertNotIn("htmlContent", c)
        self.assertIn("textContent", c)
        self.assertEqual(c["sender"]["email"], "contato@transfermed.com.br")
        self.assertEqual(c["replyTo"]["email"], "contato@transfermed.com.br")
        self.assertFalse(c["to"][0]["contactPixelTrackingConsent"])
        self.assertNotIn("headers", c)

    def test_payload_incompleto_ou_destinatario_ruim_falha(self):
        for ruim in ({**P, "para": ""}, {**P, "para": "sem-arroba"}, {**P, "assunto": " "}, {k: v for k, v in P.items() if k != "corpo"}):
            with self.assertRaises(ValueError):
                envio_b0.montar(ruim)

    def test_main_nao_imprime_endereco_nem_texto(self):
        import io, json, contextlib, os
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"B0_PAYLOAD": json.dumps(P), "BREVO_API_KEY": "k"}), \
                mock.patch.object(envio_b0.requests, "post", return_value=Resp()), contextlib.redirect_stdout(out):
            self.assertEqual(envio_b0.main(), 0)
        self.assertNotIn("exemplo.edu.br", out.getvalue())
        self.assertNotIn("Prezada", out.getvalue())

    def test_erro_do_brevo_sai_sem_o_endereco(self):
        msg, status, erro = envio_b0.enviar(P, "k", post=lambda *a, **k: Resp(400, texto="sender invalid para relacionamento@exemplo.edu.br"))
        self.assertIsNone(msg)
        self.assertEqual(status, 400)
        self.assertNotIn("relacionamento@exemplo.edu.br", erro)


if __name__ == "__main__":
    unittest.main()
