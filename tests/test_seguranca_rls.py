"""Segurança do banco (09/11/2026): a chave pública do site não pode ler nenhuma tabela. O guardião abre issue `workflow` se ler."""
import sys
import unittest
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))
import guardiao  # noqa: E402
import seguranca_rls  # noqa: E402

CRED = lambda: ("https://x.supabase.co", "chave-publica")  # noqa: E731


class Resp:
    def __init__(self, status, corpo, cr=None):
        self.status_code, self._c, self.headers = status, corpo, ({"Content-Range": cr} if cr else {})
        self.ok = status < 400

    def json(self):
        return self._c


class Sessao:
    def __init__(self, por_tabela):
        self.por = por_tabela

    def get(self, url, **kw):
        return self.por[url.rsplit("/", 1)[-1]]


TABS = seguranca_rls.TABELAS


class Teste(unittest.TestCase):
    def res(self, **mudar):
        base = {t: Resp(401, {"message": "permission denied"}) for t in TABS}
        base.update(mudar)
        return seguranca_rls.testar("https://x", "k", sessao=Sessao(base))

    def test_negado_ou_vazio_e_seguro(self):
        r = self.res(eventos=Resp(200, [], "*/0"))
        self.assertEqual(seguranca_rls.veredito(r), ("ok", []))

    def test_uma_linha_legivel_e_vazamento(self):
        r = self.res(assinantes=Resp(200, [{"id": 1}], "0-0/12"))
        self.assertEqual(seguranca_rls.veredito(r), ("vazou", ["assinantes"]))

    def test_contagem_sem_corpo_tambem_conta(self):
        r = self.res(mensagens=Resp(200, [], "*/3"))
        self.assertEqual(seguranca_rls.veredito(r)[0], "vazou")

    def test_rede_fora_nao_e_seguro(self):
        class Fora:
            def get(self, *a, **k):
                raise seguranca_rls.requests.ConnectionError()
        self.assertEqual(seguranca_rls.veredito(seguranca_rls.testar("https://x", "k", sessao=Fora()))[0], "nao_testado")


class Guardiao(unittest.TestCase):
    def test_ok_sem_achado(self):
        achados, ext = guardiao.checar_rls(testar=lambda u, k: {t: {"http": 401, "linhas": 0} for t in TABS}, credenciais=CRED)
        self.assertEqual((achados, ext["rls_anon"]), ([], "ok"))

    def test_vazamento_abre_issue_workflow_que_nao_fecha_sozinha_e_sem_dado(self):
        res = {t: {"http": 401, "linhas": 0} for t in TABS}
        res["assinantes"] = {"http": 200, "linhas": 12}
        achados, ext = guardiao.checar_rls(testar=lambda u, k: res, credenciais=CRED)
        self.assertEqual((len(achados), achados[0]["etiqueta"], achados[0]["auto_fecha"], ext["rls_anon"]), (1, "workflow", False, "VAZOU"))
        self.assertNotIn("@", achados[0]["corpo"])

    def test_sem_credencial_vira_issue(self):
        achados, ext = guardiao.checar_rls(credenciais=lambda: ("", ""))
        self.assertEqual((len(achados), ext["rls_anon"]), (1, "nao_testado"))


if __name__ == "__main__":
    unittest.main()
