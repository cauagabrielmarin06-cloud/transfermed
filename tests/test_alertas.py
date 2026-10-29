"""Testes dos alertas por e-mail (sem conta nenhuma: banco em arquivo e e-mails em memória)."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import alertas  # noqa: E402

PASTA = Path(__file__).resolve().parent.parent
HOJE = "2026-10-24"
AGORA = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
FAC = {f["id"]: f for f in json.loads((PASTA / "data" / "faculdades.json").read_text(encoding="utf-8"))}
ED = json.loads((PASTA / "data" / "editais.json").read_text(encoding="utf-8"))
PERFIL = {"origem": "brasil", "curso": "medicina", "faculdade": "", "semestre": 2, "transferiu": "nao",
          "cidade": "Fernandópolis - SP", "coords": [-20.2836, -50.2463], "raio": 300, "tipo": "todas", "taxaMax": None}


class Envio:
    def __init__(self):
        self.enviados = []

    def enviar(self, para, assunto, html, texto, token, responder_para=None):
        self.enviados.append({"para": para, "assunto": assunto, "html": html, "texto": texto})


def banco(assinantes):
    caminho = Path(tempfile.mkdtemp()) / "banco.json"
    caminho.write_text(json.dumps({"assinantes": assinantes, "notificacoes": []}), encoding="utf-8")
    return alertas.BancoSimulado(caminho)


def assinante(ident, status, criado, perfil=PERFIL, **extra):
    return {"id": ident, "email": f"{ident}@exemplo.com", "perfil": perfil, "token": f"tok-{ident}", "status": status,
            "criado_em": criado, "confirmacao_enviada_em": None, **extra}


class SoConferido(unittest.TestCase):
    def test_email_nunca_leva_edital_conferir_nem_so_do_robo(self):
        hoje = "2026-10-24"
        base = next(x for x in ED if x.get("fonte_dados") == "manual" and alertas.situacao(x, hoje) == "aberto")
        fac = {base["faculdade_id"]: FAC[base["faculdade_id"]]}
        perfil = {**PERFIL, "coords": None, "raio": 0, "semestre": None}
        ok = alertas.novidades(perfil, [base], fac, set(), hoje)
        conferir = alertas.novidades(perfil, [{**base, "status": "conferir"}], fac, set(), hoje)
        robo = alertas.novidades(perfil, [{**base, "fonte_dados": "robo", "detectado_em": hoje}], fac, set(), hoje)
        self.assertEqual(len(ok), 1)
        self.assertEqual(conferir, [])
        self.assertEqual(robo, [])


class Fluxo(unittest.TestCase):
    def test_confirmacao_alerta_sem_repetir_e_limpeza(self):
        b = banco([assinante("novo", "pendente", "2026-10-24T10:00:00+00:00"),
                   assinante("velho", "pendente", "2026-10-10T10:00:00+00:00"),
                   assinante("ativo", "ativo", "2026-10-01T10:00:00+00:00")])
        e = Envio()
        r = alertas.rodar(b, e, ED, FAC, HOJE, AGORA)
        self.assertEqual(r["apagados_sem_confirmar"], 1, "pendente há mais de 7 dias é apagado")
        self.assertEqual(r["confirmacoes"], 1)
        self.assertEqual(r["alertas"], 1)
        conf = next(x for x in e.enviados if x["para"] == "novo@exemplo.com")
        self.assertIn("/alerta/confirmar/?t=tok-novo", conf["html"])
        alerta = next(x for x in e.enviados if x["para"] == "ativo@exemplo.com")
        self.assertIn("Universidade de Uberaba", alerta["html"])
        self.assertNotIn("Universidade Brasil", alerta["html"], "edital marcado 'conferir' não vai em e-mail")
        self.assertIn("/alerta/descadastrar/?t=tok-ativo", alerta["html"], "todo e-mail tem descadastro")
        self.assertIn("/alerta/descadastrar/?t=tok-ativo", alerta["texto"])
        self.assertNotIn("velho", [a["id"] for a in b.assinantes()])

        e2 = Envio()
        r2 = alertas.rodar(b, e2, ED, FAC, HOJE, AGORA)
        self.assertEqual(r2["alertas"], 0, "não repete edital já avisado")
        self.assertEqual(r2["confirmacoes"], 0, "não reenvia confirmação antes de 24 h")

    def test_falha_de_envio_nao_trava_os_outros(self):
        class Falha(Envio):
            def enviar(self, para, *resto):
                if para.startswith("a@"):
                    raise alertas.requests.ConnectionError("fora do ar")
                super().enviar(para, *resto)
        b = banco([assinante("a", "pendente", "2026-10-24T10:00:00Z"), assinante("b", "pendente", "2026-10-24T10:00:00Z")])
        envio = Falha()
        r = alertas.rodar(b, envio, ED, FAC, HOJE, AGORA)
        self.assertEqual(r["confirmacoes"], 1)
        self.assertEqual(r["pendentes"], 2)
        self.assertEqual(r["falhas_envio"], [{"http": None, "codigo": "ConnectionError"}])
        self.assertNotIn("@", json.dumps(r))  # o registro do GitHub é público
        self.assertIsNone(next(x for x in b.assinantes() if x["id"] == "a")["confirmacao_enviada_em"])  # tenta de novo depois

    def test_resumo_do_perfil_no_email(self):
        self.assertEqual(alertas.resumo_perfil({**PERFIL, "raio": 0, "tipo": "publica"}),
                         "Medicina, no Brasil, 2º semestre, distâncias a partir de Fernandópolis - SP, só faculdades públicas")
        self.assertIn("até 300 km de Fernandópolis - SP", alertas.resumo_perfil(PERFIL))

    def test_perfil_incompativel_nao_recebe(self):
        perfil = dict(PERFIL, semestre=11, raio=150, tipo="publica")
        b = banco([assinante("x", "ativo", "2026-10-01T10:00:00+00:00", perfil)])
        e = Envio()
        alertas.rodar(b, e, ED, FAC, HOJE, AGORA)
        self.assertEqual(e.enviados, [])

    def test_limite_diario(self):
        antigo = alertas.LIMITE_DIARIO
        alertas.LIMITE_DIARIO = 1
        try:
            b = banco([assinante(f"p{i}", "pendente", "2026-10-24T10:00:00+00:00") for i in range(3)])
            e = Envio()
            r = alertas.rodar(b, e, ED, FAC, HOJE, AGORA)
            self.assertEqual(len(e.enviados), 1)
            self.assertTrue(r["parou_no_limite"])
        finally:
            alertas.LIMITE_DIARIO = antigo


class Compatibilidade(unittest.TestCase):
    def test_mesma_faculdade(self):
        ub, uniube = FAC["ub-fernandopolis"], FAC["uniube"]
        self.assertTrue(alertas.mesma_faculdade("UB", ub))
        self.assertFalse(alertas.mesma_faculdade("UB", uniube))
        self.assertFalse(alertas.mesma_faculdade("Universidade", uniube))
        self.assertTrue(alertas.mesma_faculdade("Universidade de Uberaba", uniube))

    def test_vagas_por_serie_e_ano(self):
        self.assertEqual(alertas.semestres_da_vaga("2ª série"), [3, 4])
        self.assertEqual(alertas.semestres_da_vaga("5º ano"), [9, 10])
        self.assertEqual(alertas.semestres_da_vaga("2º ao 6º"), [2, 3, 4, 5, 6])


if __name__ == "__main__":
    unittest.main()


class Contato(unittest.TestCase):
    def test_encaminha_ao_dono_responde_e_apaga_depois_de_90_dias(self):
        b = banco([])
        b.d["mensagens"] = [
            {"id": "m1", "dados": {"nome": "Ana Souza", "email": "ana@exemplo.com", "motivo": "consultoria", "mensagem": "Quero ajuda",
                                   "estados": "SP", "prazo": "6-meses"}, "criado_em": "2026-10-24T10:00:00+00:00"},
            {"id": "velha", "dados": {"email": "x@exemplo.com"}, "encaminhada_em": "2026-06-01T00:00:00+00:00"}]
        e = Envio()
        n = alertas.encaminhar_contato(b, e, "dono@exemplo.com", AGORA)
        self.assertEqual(n, 1)
        self.assertEqual([x["para"] for x in e.enviados], ["dono@exemplo.com", "ana@exemplo.com"])
        self.assertIn("Consultoria individual", e.enviados[0]["assunto"])
        self.assertIn("Respondo em até 3 dias úteis", e.enviados[1]["html"])
        self.assertEqual([m["id"] for m in b.d["mensagens"]], ["m1"], "encaminhada há mais de 90 dias é apagada")
        self.assertEqual(alertas.encaminhar_contato(b, Envio(), "dono@exemplo.com", AGORA), 0, "não encaminha duas vezes")

    def test_sem_destino_a_mensagem_espera(self):
        b = banco([])
        b.d["mensagens"] = [{"id": "m1", "dados": {"nome": "A", "email": "a@exemplo.com", "motivo": "duvida", "mensagem": "Oi oi"}}]
        self.assertEqual(alertas.encaminhar_contato(b, Envio(), "", AGORA), 0)
        self.assertEqual(len(b.mensagens_pendentes()), 1)
