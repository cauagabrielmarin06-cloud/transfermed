"""Funil de confirmação (08/11/2026): e-mail de confirmação com assunto claro, um lembrete em 24 h, um último em 72 h e depois nada.
Antes disso, quem não confirmava recebia a confirmação TODO DIA por 7 dias (6 a 7 e-mails iguais para 12 pessoas)."""
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))
sys.path.insert(0, str(PASTA / "tests"))
import alertas  # noqa: E402
import nutricao  # noqa: E402
from test_alertas import ED, FAC, Envio, assinante, banco  # noqa: E402

CRIADO = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
H = timedelta(hours=1)


class Etapas(unittest.TestCase):
    def test_primeiro_lembrete_so_depois_de_24h_e_so_uma_vez(self):
        e = alertas.etapa_da_confirmacao
        self.assertEqual(e(CRIADO, None, CRIADO), 0)
        primeiro = CRIADO + 5 * timedelta(minutes=1)
        self.assertIsNone(e(CRIADO, primeiro, CRIADO + 23 * H))
        self.assertEqual(e(CRIADO, primeiro, CRIADO + 24 * H), 1)
        self.assertIsNone(e(CRIADO, CRIADO + 25 * H, CRIADO + 49 * H), "o lembrete de 24 h já saiu: nada até as 72 h")

    def test_ultimo_lembrete_aos_72h_e_depois_nada(self):
        e = alertas.etapa_da_confirmacao
        self.assertIsNone(e(CRIADO, CRIADO + 25 * H, CRIADO + 71 * H))
        self.assertEqual(e(CRIADO, CRIADO + 25 * H, CRIADO + 72 * H), 2)
        for horas in (73, 96, 120, 150, 167):
            self.assertIsNone(e(CRIADO, CRIADO + 73 * H, CRIADO + horas * H), f"{horas} h")

    def test_quem_se_inscreve_de_novo_recebe_na_hora_e_o_ultimo_lembrete_continua_valendo(self):
        # o site zera confirmacao_enviada_em quando a pessoa pede de novo (pedido dela, não lembrete)
        self.assertEqual(alertas.etapa_da_confirmacao(CRIADO, None, CRIADO + 30 * H), 0)


class UmaSemanaReal(unittest.TestCase):
    """Roda o robô a cada 30 minutos por 8 dias com um inscrito que nunca confirma: no máximo 3 e-mails de confirmação."""

    def test_tres_emails_no_total_e_cadastro_apagado_aos_7_dias(self):
        b = banco([assinante("p", "pendente", CRIADO.isoformat())])
        envio = Envio()
        agora = CRIADO
        envios_em = []
        while agora < CRIADO + timedelta(days=8):
            antes = len(envio.enviados)
            r = alertas.rodar(b, envio, ED, FAC, agora.date().isoformat(), agora)
            if len(envio.enviados) > antes:
                envios_em.append((agora - CRIADO) / H)
            agora += timedelta(minutes=30)
        self.assertEqual(len(envio.enviados), 3, envios_em)
        assuntos = [x["assunto"] for x in envio.enviados]
        self.assertEqual(assuntos[0], nutricao.ASSUNTOS_CONFIRMACAO[0])
        self.assertIn("combinam com o seu perfil", assuntos[1])  # lembretes com valor (09/11/2026): há edital aberto do perfil
        self.assertTrue(assuntos[2].startswith("Último lembrete"))
        self.assertAlmostEqual(envios_em[1], 24, delta=1)
        self.assertAlmostEqual(envios_em[2], 72, delta=1)
        self.assertEqual(b.assinantes(), [], "aos 7 dias o cadastro não confirmado é apagado")

    def test_sem_edital_aberto_do_perfil_o_lembrete_continua_simples(self):
        b = banco([assinante("p", "pendente", CRIADO.isoformat())])
        envio = Envio()
        alertas.rodar(b, envio, [], FAC, "2026-11-01", CRIADO)
        alertas.rodar(b, envio, [], FAC, "2026-11-02", CRIADO + 25 * H)
        alertas.rodar(b, envio, [], FAC, "2026-11-04", CRIADO + 73 * H)
        self.assertEqual([x["assunto"] for x in envio.enviados], list(nutricao.ASSUNTOS_CONFIRMACAO))

    def test_lembrete_com_valor_mostra_ficha_prazo_e_botao_e_no_maximo_3(self):
        b = banco([assinante("p", "pendente", CRIADO.isoformat())])
        envio = Envio()
        base = alertas.editais_abertos(assinante("p", "pendente", CRIADO.isoformat())["perfil"], ED, FAC, "2026-11-02")
        self.assertTrue(base, "os dados reais precisam ter ao menos 1 edital aberto compatível em 02/11/2026")
        muitos = [dict(base[0][0], id=f"{base[0][0]['id']}-{i}") for i in range(5)]
        alertas.rodar(b, envio, muitos, FAC, "2026-11-01", CRIADO)
        alertas.rodar(b, envio, muitos, FAC, "2026-11-02", CRIADO + 25 * H)
        lembrete = envio.enviados[1]
        self.assertIn("5 editais abertos combinam com o seu perfil", lembrete["assunto"])
        self.assertIn("/alerta/confirmar/?t=", lembrete["html"])
        self.assertIn("E mais 2 editais abertos", lembrete["html"])
        self.assertEqual(lembrete["html"].count("Ver resumo e documentos"), 0, "cartões sem link próprio: no máximo 2 links por e-mail")
        self.assertEqual(lembrete["html"].count("border-radius:12px;padding:12px 14px"), 3, "até 3 cartões")
        self.assertNotIn("único lembrete", lembrete["html"])

    def test_resumo_separa_confirmacao_de_lembrete(self):
        b = banco([assinante("p", "pendente", CRIADO.isoformat())])
        envio = Envio()
        r0 = alertas.rodar(b, envio, ED, FAC, "2026-11-01", CRIADO)
        r1 = alertas.rodar(b, envio, ED, FAC, "2026-11-02", CRIADO + 25 * H)
        self.assertEqual((r0["confirmacoes"], r0["lembretes_de_confirmacao"]), (1, 0))
        self.assertEqual((r1["confirmacoes"], r1["lembretes_de_confirmacao"]), (0, 1))
        self.assertNotIn("@", str(r1))

    def test_quem_confirmou_nao_recebe_lembrete(self):
        b = banco([assinante("p", "ativo", CRIADO.isoformat(), confirmado_em=(CRIADO + H).isoformat())])
        envio = Envio()
        alertas.rodar(b, envio, [], FAC, "2026-11-02", CRIADO + 30 * H)
        self.assertFalse([x for x in envio.enviados if "falta 1 clique" in x["assunto"].lower()])


class TextoDoEmail(unittest.TestCase):
    A = {"token": "tok", "email": "a@x.com", "perfil": {"curso": "medicina"}}

    def test_assuntos(self):
        self.assertEqual(nutricao.ASSUNTOS_CONFIRMACAO[0], "Confirme seu alerta do Transfermed: falta 1 clique")
        for etapa in range(3):
            assunto, html, texto = nutricao.confirmacao(self.A, "https://s", 7, etapa)
            self.assertIn("falta 1 clique", assunto.lower())
            self.assertLessEqual(len(assunto), 70, "assunto curto aparece inteiro no celular")
            self.assertIn("https://s/alerta/confirmar/?t=tok", html)
            self.assertIn("https://s/alerta/confirmar/?t=tok", texto)
            self.assertIn("Se o botão não abrir", texto, "link em texto como plano B")

    def test_botao_funciona_no_gmail_e_no_celular(self):
        _, html, _ = nutricao.confirmacao(self.A, "https://s", 7)
        self.assertIn('name="viewport"', html)
        botao = re.search(r'<a href="https://s/alerta/confirmar/\?t=tok"[^>]*>', html).group(0)
        for estilo in ("display:inline-block", "padding:12px 20px", "color:#FFFFFF", "background:#0F5C4D"):
            self.assertIn(estilo, botao)  # estilos no próprio elemento: o Gmail apaga <style> e classes
        self.assertNotIn("<style", html)
        self.assertNotIn("<script", html)
        self.assertIn("max-width:560px", html)

    def test_lembretes_dizem_que_nenhum_alerta_foi_enviado_e_o_ultimo_diz_que_e_o_ultimo(self):
        _, _, t1 = nutricao.confirmacao(self.A, "https://s", 7, 1)
        _, _, t2 = nutricao.confirmacao(self.A, "https://s", 7, 2)
        self.assertIn("nenhum aviso foi enviado", t1)
        self.assertIn("último lembrete", t2)
        self.assertIn("não vou escrever de novo", t2)
        for t in (t1, t2):
            self.assertNotIn("urgente", t.lower())  # urgência só de prazo real
            self.assertNotIn("!!", t)

    def test_previa_do_email_aparece_no_celular(self):
        _, html, _ = nutricao.confirmacao(self.A, "https://s", 7)
        self.assertIn("display:none", html)
        self.assertIn("Um toque no botão", html)


class TelaDepoisDaInscricao(unittest.TestCase):
    JS = (PASTA / "docs" / "assets" / "app.js").read_text(encoding="utf-8")

    def test_diz_para_conferir_o_email_e_o_spam_e_clicar_em_confirmar(self):
        self.assertIn("Confira seu e-mail (e o spam) e clique em confirmar", self.JS)
        self.assertIn("Confirme seu alerta do Transfermed: falta 1 clique", self.JS, "o aluno procura o assunto exato")
        self.assertIn("alertas@transfermed.com.br", self.JS)

    def test_assunto_do_site_e_o_do_email(self):
        self.assertIn(nutricao.ASSUNTOS_CONFIRMACAO[0], self.JS)


if __name__ == "__main__":
    unittest.main()
