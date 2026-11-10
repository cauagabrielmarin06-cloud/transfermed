"""Lembrete único com valor (09/11/2026): "N editais abertos combinam com o seu perfil" para quem não confirmou e já passou das janelas de 24 h e 72 h."""
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))
sys.path.insert(0, str(PASTA / "tests"))
import alertas  # noqa: E402
import lembrete_valor as lv  # noqa: E402
import nutricao  # noqa: E402
from test_alertas import ED, FAC, HOJE, PERFIL, Envio, assinante, banco  # noqa: E402

AGORA = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
H = timedelta(hours=1)


def antigo(ident, horas=100, status="pendente", ultima_h=10, perfil=PERFIL, **extra):
    """Pendente de antes do funil novo: criado há `horas`, última confirmação há `ultima_h` horas (o robô antigo reenviava todo dia)."""
    return assinante(ident, status, (AGORA - horas * H).isoformat(), perfil=perfil,
                     confirmacao_enviada_em=(AGORA - ultima_h * H).isoformat(), **extra)


class Elegibilidade(unittest.TestCase):
    def test_pendente_entre_72h_e_7_dias(self):
        self.assertTrue(lv.elegivel(antigo("a", 100), AGORA, set()))
        self.assertTrue(lv.elegivel(antigo("a", 24 * 7 - 1), AGORA, set()))

    def test_quem_ainda_esta_na_fila_normal_ou_ja_passou_dos_7_dias_fica_de_fora(self):
        self.assertFalse(lv.elegivel(antigo("a", 30, ultima_h=2), AGORA, set()), "antes de 72 h: segue os lembretes normais")
        self.assertFalse(lv.elegivel(antigo("a", 24 * 7 + 1), AGORA, set()), "depois de 7 dias o cadastro é apagado")
        # passou de 72 h mas o robô ainda vai mandar o último lembrete normal (última confirmação anterior às 72 h): não somar outro
        self.assertFalse(lv.elegivel(antigo("a", 80, ultima_h=20), AGORA, set()))

    def test_nunca_para_quem_ja_confirmou_nem_para_quem_ja_recebeu(self):
        self.assertFalse(lv.elegivel(antigo("a", 100, status="ativo"), AGORA, set()))
        self.assertFalse(lv.elegivel(antigo("a", 100), AGORA, {lv.CHAVE}))


class Envio_(unittest.TestCase):
    def cenario(self):
        return banco([antigo("p1", 100), antigo("p2", 120), antigo("novo", 30, ultima_h=2), antigo("ativo", 100, status="ativo"),
                      antigo("velho", 24 * 7 + 1)])

    def rodar(self, b, envio, **kw):
        return lv.rodar(b, envio, ED, FAC, agora=AGORA, hoje=HOJE, **kw)

    def test_so_um_envio_por_pessoa_para_sempre(self):
        b, envio = self.cenario(), Envio()
        r1 = self.rodar(b, envio, enviar=True)
        self.assertEqual((r1["enviados"], r1["sem_edital"]), (2, 0))
        self.assertEqual(sorted(x["para"] for x in envio.enviados), ["p1@exemplo.com", "p2@exemplo.com"])
        r2 = self.rodar(b, envio, enviar=True)
        self.assertEqual(r2["enviados"], 0)
        self.assertEqual(len(envio.enviados), 2, "uma segunda rodada nunca reenvia")
        self.assertIn(lv.CHAVE, b.avisados("p1"))

    def test_quem_ja_confirmou_ou_ainda_esta_na_fila_nao_recebe(self):
        b, envio = self.cenario(), Envio()
        self.rodar(b, envio, enviar=True)
        self.assertFalse({"ativo@exemplo.com", "novo@exemplo.com", "velho@exemplo.com"} & {x["para"] for x in envio.enviados})

    def test_ensaio_nao_envia_nem_registra(self):
        b, envio = self.cenario(), Envio()
        r = self.rodar(b, envio, enviar=False)
        self.assertEqual((r["receberiam"], r["enviados"], r["ensaio"]), (2, 0, True))
        self.assertEqual(envio.enviados, [])
        self.assertEqual(b.d["notificacoes"], [])

    def test_sem_edital_aberto_compativel_nao_envia(self):
        b, envio = banco([antigo("p1", 100)]), Envio()
        r = lv.rodar(b, envio, [], FAC, enviar=True, agora=AGORA, hoje=HOJE)
        self.assertEqual((r["enviados"], r["sem_edital"]), (0, 1))
        self.assertEqual(envio.enviados, [])

    def test_respeita_o_limite_diario_e_a_reserva(self):
        b, envio = self.cenario(), Envio()
        b.d["notificacoes"] += [{"assinante_id": f"x{i}", "edital_id": "e", "enviado_em": HOJE + "T08:00:00+00:00"}
                                for i in range(alertas.LIMITE_DIARIO - alertas.RESERVA_URGENTE)]
        r = self.rodar(b, envio, enviar=True)
        self.assertEqual(r["enviados"], 0)
        self.assertTrue(r["parou_no_limite"])
        self.assertEqual(envio.enviados, [])

    def test_o_resumo_so_tem_contagens(self):
        b, envio = self.cenario(), Envio()
        r = self.rodar(b, envio, enviar=True)
        self.assertNotIn("@", str(r))
        self.assertTrue(all(isinstance(v, (int, bool)) for v in r.values()))

    def test_falha_de_envio_nao_registra_e_deixa_para_outra_vez(self):
        import requests

        class Falha:
            def enviar(self, *a, **k):
                raise requests.ConnectionError("fora do ar")
        b = banco([antigo("p1", 100)])
        r = lv.rodar(b, Falha(), ED, FAC, enviar=True, agora=AGORA, hoje=HOJE)
        self.assertEqual((r["enviados"], r["falhas_envio"]), (0, 1))
        self.assertEqual(b.d["notificacoes"], [])


class TextoDoEmail(unittest.TestCase):
    def itens(self):
        return lv.editais_abertos(PERFIL, ED, FAC, HOJE)

    def test_base_real_tem_editais_abertos_para_o_perfil_do_teste(self):
        self.assertGreaterEqual(len(self.itens()), 1)

    def test_assunto_e_corpo(self):
        a = assinante("p1", "pendente", (AGORA - 100 * H).isoformat())
        c = nutricao.Contexto(ED, FAC, "https://s", HOJE)
        itens = self.itens()
        assunto, html, texto = nutricao.lembrete_valor(a, c, itens, 7)
        n = len(itens)
        self.assertIn(f"{n} edita", assunto)
        self.assertIn("com o seu perfil", assunto)
        self.assertLessEqual(len(assunto), 75)
        for t in (html, texto):
            self.assertIn("Confirme para receber os prazos antes que fechem", t)
            self.assertIn("https://s/alerta/confirmar/?t=tok-p1", t)
            self.assertIn("não vou escrever de novo", t)
        self.assertIn("Se o botão não abrir", texto)
        self.assertLessEqual(html.count("Ver resumo e documentos"), nutricao.MAX_LEMBRETE_VALOR, "até 3 editais no e-mail")
        self.assertNotIn("urgente", texto.lower())

    def test_so_ate_tres_e_avisa_quantos_faltam(self):
        a = assinante("p1", "pendente", (AGORA - 100 * H).isoformat())
        c = nutricao.Contexto(ED, FAC, "https://s", HOJE)
        itens = self.itens()
        if len(itens) < 4:
            itens = (itens * 4)[:5]  # só para exercitar o corte
        _, html, texto = nutricao.lembrete_valor(a, c, itens, 7)
        self.assertEqual(html.count("Ver resumo e documentos"), 0)  # sem link por cartão
        self.assertEqual(html.count("border-radius:12px"), 3)
        self.assertRegex(texto, r"E mais \d+ editais? aberto")

    def test_singular(self):
        self.assertTrue(nutricao.assunto_lembrete_valor(1).startswith("1 edital aberto combina com o seu perfil"))
        self.assertTrue(nutricao.assunto_lembrete_valor(4).startswith("4 editais abertos combinam com o seu perfil"))


class Workflow(unittest.TestCase):
    TEXTO = (PASTA / ".github" / "workflows" / "lembrete_valor.yml").read_text(encoding="utf-8")

    def test_por_padrao_so_faz_o_ensaio(self):
        self.assertRegex(self.TEXTO, r"enviar:\s*\n(?:\s+.*\n)*?\s+default: false")

    def test_usa_a_fila_dos_alertas_para_nunca_enviar_junto(self):
        self.assertRegex(self.TEXTO, r"group: alertas")

    def test_nao_imprime_email(self):
        self.assertNotIn("print(a[", (PASTA / "lembrete_valor.py").read_text(encoding="utf-8"))
        self.assertNotRegex((PASTA / "lembrete_valor.py").read_text(encoding="utf-8"), r"print\(.*email")


if __name__ == "__main__":
    unittest.main()
