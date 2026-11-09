"""Falha do próprio GitHub (09/11/2026): o vigia reconhece, repete sozinho (15 min, até 3 vezes) e só abre issue se continuar falhando;
e o resumo diário de falhas (um e-mail só ao dono, só com issue de workflow aberta há mais de 2 h). Nada acessa a rede nem espera de verdade."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))
import resumo_falhas as rf  # noqa: E402
import vigia_workflows as v  # noqa: E402

AGORA = datetime(2026, 11, 9, 18, 30, tzinfo=timezone.utc)


def run(id_, conclusao="failure", horas_atras=0.2, tentativa=1, jobs_rodaram=False):
    t = (AGORA - timedelta(hours=horas_atras)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"id": id_, "created_at": t, "updated_at": t, "conclusion": conclusao, "status": "completed", "event": "schedule", "run_attempt": tentativa,
            "html_url": f"https://github.com/x/y/actions/runs/{id_}", "jobs_rodaram": jobs_rodaram}


def saudavel():
    return {arq: [run(1, "success", 1)] for arq in v.WORKFLOWS}


JOB_REAL = {"name": "rodar", "conclusion": "failure", "check_run_url": "x"}
INCIDENTE = {"name": "Incident with Actions and Checks API", "created_at": "2026-11-09T18:00:00Z", "resolved_at": None, "components": [{"name": "Actions"}]}


class ApiFalsa:
    """Responde como o GitHub: cada `repetir` devolve o próximo resultado da lista."""

    def __init__(self, resultados):
        self.resultados, self.repeticoes = list(resultados), []

    def repetir(self, r):
        self.repeticoes.append(r["id"])
        return self.resultados.pop(0)


class Reconhecer(unittest.TestCase):
    def test_no_jobs_were_run_e_falha_do_github(self):
        motivo = v.falha_de_infra(run(5), jobs=[])
        self.assertIn("No jobs were run", motivo)

    def test_falha_real_com_job_e_passo_que_falhou_nao_e_do_github(self):
        self.assertIsNone(v.falha_de_infra(run(5, jobs_rodaram=True), jobs=[JOB_REAL], anotacoes=["Process completed with exit code 1."], incidentes=[]))

    def test_erro_de_runner_e_cancelamento_pelo_github(self):
        for msg in ("The runner has received a shutdown signal.", "The hosted runner encountered an error while running your job.",
                    "Lost communication with the server", "Failed to download action 'actions/checkout@v4'"):
            with self.subTest(msg):
                self.assertTrue(v.falha_de_infra(run(5), jobs=[JOB_REAL], anotacoes=[msg]), msg)
        self.assertTrue(v.falha_de_infra(run(5, "cancelled"), jobs=[JOB_REAL], anotacoes=["The runner has received a shutdown signal."]))
        self.assertIsNone(v.falha_de_infra(run(5, "cancelled"), jobs=[JOB_REAL], anotacoes=[]), "cancelada por outra execução (concurrency) não é do GitHub")

    def test_incidente_ativo_so_vale_na_hora_da_execucao_e_so_de_actions(self):
        com_jobs = dict(jobs=[JOB_REAL], anotacoes=[])
        self.assertIn("Incident with Actions", v.falha_de_infra(run(5), incidentes=[INCIDENTE], **com_jobs))
        resolvido_cedo = dict(INCIDENTE, created_at="2026-11-08T08:00:00Z", resolved_at="2026-11-08T09:00:00Z")
        self.assertIsNone(v.falha_de_infra(run(5), incidentes=[resolvido_cedo], **com_jobs))
        outro = dict(INCIDENTE, name="Incident with Git Operations", components=[{"name": "Git Operations"}])
        self.assertIsNone(v.falha_de_infra(run(5), incidentes=[outro], **com_jobs))
        self.assertIsNone(v.falha_de_infra(run(5, "success"), jobs=[JOB_REAL], incidentes=[INCIDENTE]), "execução que deu certo não é falha")

    def test_falha_do_github_nao_vira_issue_em_checar_e_vai_para_a_repeticao(self):
        e = saudavel()
        e["relatorio.yml"] = [run(42)]
        infra = lambda r: v.falha_de_infra(r, jobs=[])  # noqa: E731 - "No jobs were run"
        self.assertEqual(v.checar(e, AGORA, infra=infra), [])
        cand = v.candidatas_a_retentar(e, infra)
        self.assertEqual([(c[0], c[2]["id"]) for c in cand], [("relatorio.yml", 42)])

    def test_falha_real_continua_abrindo_issue_na_hora(self):
        e = saudavel()
        e["monitor.yml"] = [run(42, jobs_rodaram=True)]
        infra = lambda r: v.falha_de_infra(r, jobs=[JOB_REAL], anotacoes=["Process completed with exit code 1."])  # noqa: E731
        a = v.checar(e, AGORA, lambda i: ["Testes (antes de publicar qualquer correção)"], infra)
        self.assertEqual(len(a), 1)
        self.assertIn("um teste travou", a[0]["corpo"])
        self.assertFalse(a[0]["auto_fecha"])
        self.assertEqual(v.candidatas_a_retentar(e, infra), [], "falha real não é repetida")


class Repetir(unittest.TestCase):
    def setUp(self):
        self.espera = []
        self.dormir = self.espera.append
        self.sem_job = lambda r: v.falha_de_infra(r, jobs=[]) if r.get("conclusion") in v.FALHAS else None
        self.cand = [("relatorio.yml", "Relatório semanal", run(42), "nenhum job foi executado")]

    def test_repete_em_15_minutos_e_se_deu_certo_nao_abre_issue(self):
        api = ApiFalsa([run(42, "success", tentativa=2, jobs_rodaram=True)])
        achados = v.retentar(api, self.cand, dormir=self.dormir, infra=self.sem_job)
        self.assertEqual((achados, api.repeticoes, self.espera), ([], [42], [900]))

    def test_se_continua_falhando_repete_3_vezes_e_so_entao_abre_issue(self):
        api = ApiFalsa([run(42, tentativa=n) for n in (2, 3, 4)])
        achados = v.retentar(api, self.cand, dormir=self.dormir, infra=self.sem_job)
        self.assertEqual(api.repeticoes, [42, 42, 42])
        self.assertEqual(self.espera, [900, 900, 900])
        self.assertEqual(len(achados), 1)
        self.assertIn("Continuou falhando em 3 repetições", achados[0]["corpo"])
        self.assertIn("15 min", achados[0]["corpo"])
        self.assertFalse(achados[0]["auto_fecha"])

    def test_deu_certo_na_segunda_repeticao(self):
        api = ApiFalsa([run(42, tentativa=2), run(42, "success", tentativa=3, jobs_rodaram=True)])
        self.assertEqual(v.retentar(api, self.cand, dormir=self.dormir, infra=self.sem_job), [])
        self.assertEqual(self.espera, [900, 900])

    def test_se_a_repeticao_falha_por_culpa_nossa_abre_a_issue_da_falha_real(self):
        real = run(42, tentativa=2, jobs_rodaram=True)
        api = ApiFalsa([real])
        achados = v.retentar(api, self.cand, dormir=self.dormir, infra=lambda r: None, passos=lambda i: ["Rodar o robô"])
        self.assertEqual(api.repeticoes, [42], "não repete uma falha real")
        self.assertEqual(len(achados), 1)
        self.assertIn("Falha real", achados[0]["corpo"])
        self.assertIn("o próprio robô quebrou", achados[0]["corpo"])

    def test_workflow_que_manda_email_nao_e_repetido_se_ja_rodou_job(self):
        cand = [("alertas.yml", "Alertas por e-mail", run(7, jobs_rodaram=True), "erro de infraestrutura do runner")]
        api = ApiFalsa([])
        achados = v.retentar(api, cand, dormir=self.dormir, infra=self.sem_job)
        self.assertEqual(api.repeticoes, [])
        self.assertIn("poderia duplicar envio", achados[0]["corpo"])

    def test_alertas_sem_nenhum_job_pode_ser_repetido(self):
        cand = [("alertas.yml", "Alertas por e-mail", run(7), "nenhum job foi executado")]
        api = ApiFalsa([run(7, "success", tentativa=2, jobs_rodaram=True)])
        self.assertEqual(v.retentar(api, cand, dormir=self.dormir, infra=self.sem_job), [])
        self.assertEqual(api.repeticoes, [7])

    def test_erro_na_api_de_repeticao_vira_issue_e_nao_derruba(self):
        class Quebrada(ApiFalsa):
            def repetir(self, r):
                raise RuntimeError("403")
        achados = v.retentar(Quebrada([]), self.cand, dormir=self.dormir, infra=self.sem_job)
        self.assertIn("repetição automática falhou", achados[0]["corpo"])


class VigiaDePontaAPonta(unittest.TestCase):
    """O main do vigia com a API simulada: «No jobs were run» e falha real, e o vigia termina verde (retorno 0) nos dois."""

    def _rodar(self, execs, jobs_por_run, resultados_repeticao):
        class Fake:
            def __init__(s, repo, token):
                s.repeticoes = []

            def execucoes(s, arq):
                return execs.get(arq, [run(1, "success", 1)])

            def incidentes(s):
                return []

            def classificar(s, r, incidentes):
                r["jobs_rodaram"] = bool(jobs_por_run.get(r["id"]))
                return v.falha_de_infra(r, jobs_por_run.get(r["id"], []), [], incidentes)

            def repetir(s, r):
                s.repeticoes.append(r["id"])
                return resultados_repeticao.pop(0)

            def passos_com_falha(s, rid):
                return ["Rodar o robô"] if rid == 99 else []
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(v, "Api", Fake), mock.patch.object(v, "SAIDA", Path(tmp) / "a.json"), \
                mock.patch.object(v.time, "sleep"), mock.patch.dict("os.environ", {"GITHUB_REPOSITORY": "x/y", "GITHUB_TOKEN": "t"}):
            codigo = v.main([], agora=AGORA)  # relógio fixo: o teste não pode depender da hora em que roda
            return codigo, json.loads((Path(tmp) / "a.json").read_text(encoding="utf-8"))["achados"]

    def test_no_jobs_were_run_que_se_resolve_na_repeticao_termina_verde_e_sem_issue(self):
        codigo, achados = self._rodar({"relatorio.yml": [run(42)]}, {}, [run(42, "success", tentativa=2)])
        self.assertEqual((codigo, achados), (0, []))

    def test_no_jobs_were_run_que_persiste_abre_uma_issue_e_ainda_termina_verde(self):
        codigo, achados = self._rodar({"relatorio.yml": [run(42)]}, {}, [run(42, tentativa=n) for n in (2, 3, 4)])
        self.assertEqual(codigo, 0)
        self.assertEqual(len(achados), 1)
        self.assertIn("No jobs were run", achados[0]["corpo"])

    def test_falha_real_abre_issue_sem_esperar_nem_repetir(self):
        codigo, achados = self._rodar({"monitor.yml": [run(99, jobs_rodaram=True)]}, {99: [JOB_REAL]}, [])
        self.assertEqual(codigo, 0)
        self.assertEqual(len(achados), 1)
        self.assertIn("o próprio robô quebrou", achados[0]["corpo"])


class ApiRepetirRota(unittest.TestCase):
    def test_usa_rerun_sem_job_e_rerun_failed_jobs_com_job(self):
        class Http:
            def __init__(s):
                s.headers, s.postadas = {}, []

            def post(s, url, timeout=None):
                s.postadas.append(url)
                return mock.Mock(raise_for_status=lambda: None)
        for rodaram, rota in ((False, "/rerun"), (True, "/rerun-failed-jobs")):
            http = Http()
            api = v.Api("x/y", "t", http=http)
            novo = dict(run(42, "success", tentativa=2), status="completed")
            with mock.patch.object(api, "get", side_effect=lambda caminho, **k: novo if caminho.endswith("/42") else {"jobs": [{"id": 1}]}):
                saida = api.repetir(dict(run(42), jobs_rodaram=rodaram), dormir=lambda s: None)
            self.assertTrue(http.postadas[0].endswith(f"/actions/runs/42{rota}"), http.postadas)
            self.assertEqual(saida["conclusion"], "success")


def issue(num, horas_atras, titulo="Workflow «Alertas por e-mail» falhou", etiqueta="workflow", **extra):
    t = (AGORA - timedelta(hours=horas_atras)).strftime("%Y-%m-%dT%H:%M:%SZ")
    i = {"number": num, "title": titulo, "created_at": t, "state": "open", "labels": [{"name": etiqueta}], "html_url": f"https://github.com/x/y/issues/{num}",
         "body": "**Causa provável:** passo «Rodar»: o próprio robô quebrou.\n\nLog: x"}
    i.update(extra)
    return i


class ResumoDiario(unittest.TestCase):
    ENV = {"BREVO_API_KEY": "k", "REMETENTE_EMAIL": "remetente@exemplo.org", "CONTATO_DESTINO": "dono@exemplo.org"}

    def _http(self):
        h = mock.Mock()
        h.post.return_value = mock.Mock(ok=True, status_code=201)
        return h

    def test_so_entra_issue_de_workflow_aberta_ha_mais_de_2_horas(self):
        sel = rf.selecionar([issue(1, 1.9), issue(2, 2.1), issue(3, 30), issue(4, 5, etiqueta="prazo"), issue(5, 5, pull_request={"url": "x"}),
                             issue(6, 5, state="closed")], AGORA)
        self.assertEqual([i["number"] for i in sel], [3, 2], "mais antiga primeiro; recente, outra etiqueta, PR e fechada ficam de fora")

    def test_sem_issue_velha_nao_envia_nada(self):
        http = self._http()
        with mock.patch.dict("os.environ", self.ENV):
            codigo = rf.main(["--enviar"], agora=AGORA, issues=[issue(1, 0.5)], http=http)
        self.assertEqual(codigo, 0)
        http.post.assert_not_called()

    def test_sem_nenhuma_issue_nao_envia_nada(self):
        http = self._http()
        with mock.patch.dict("os.environ", self.ENV):
            self.assertEqual(rf.main(["--enviar"], agora=AGORA, issues=[], http=http), 0)
        http.post.assert_not_called()

    def test_com_issue_velha_envia_um_email_so_ao_dono_em_texto_simples(self):
        http = self._http()
        with mock.patch.dict("os.environ", self.ENV):
            codigo = rf.main(["--enviar"], agora=AGORA, issues=[issue(1, 0.5), issue(2, 3), issue(3, 26)], http=http)
        self.assertEqual(codigo, 0)
        self.assertEqual(http.post.call_count, 1, "um e-mail só, não um por issue")
        corpo = http.post.call_args.kwargs["json"]
        self.assertEqual(corpo["to"], [{"email": "dono@exemplo.org"}])
        self.assertIn("2 falhas de workflow sem correção", corpo["subject"])
        self.assertNotIn("htmlContent", corpo, "texto simples, sem rastreador")
        self.assertIn("aberta há 26 h", corpo["textContent"])
        self.assertIn("https://github.com/x/y/issues/3", corpo["textContent"])
        self.assertNotIn("/issues/1\n", corpo["textContent"], "a issue de 30 min não entra")

    def test_o_registro_publico_nao_mostra_titulos_nem_enderecos(self):
        import io
        from contextlib import redirect_stdout
        http, saida = self._http(), io.StringIO()
        with mock.patch.dict("os.environ", self.ENV), redirect_stdout(saida):
            rf.main(["--enviar"], agora=AGORA, issues=[issue(2, 3, titulo="Workflow «Segredo» falhou")], http=http)
        self.assertNotIn("Segredo", saida.getvalue())
        self.assertNotIn("dono@", saida.getvalue())
        self.assertIn("1 issue(s) antiga(s)", saida.getvalue())

    def test_sem_segredos_nao_envia_e_avisa(self):
        http = self._http()
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertEqual(rf.main(["--enviar"], agora=AGORA, issues=[issue(2, 3)], http=http), 1)
        http.post.assert_not_called()

    def test_ciclo_completo_no_jobs_were_run_que_nao_se_resolve_chega_ao_dono_so_depois_de_2_horas(self):
        """O vigia só abre a issue depois das 3 repetições; o resumo só avisa o dono se ela continuar aberta por mais de 2 h."""
        api = ApiFalsa([run(42, tentativa=n) for n in (2, 3, 4)])
        achados = v.retentar(api, [("relatorio.yml", "Relatório semanal", run(42), "nenhum job foi executado")], dormir=lambda s: None,
                             infra=lambda r: v.falha_de_infra(r, jobs=[]))
        aberta = issue(10, 0.2, titulo=achados[0]["titulo"], body=achados[0]["corpo"])
        self.assertEqual(rf.selecionar([aberta], AGORA), [], "recém-aberta: ainda não incomoda o dono")
        depois = AGORA + timedelta(hours=2, minutes=5)
        self.assertEqual(len(rf.selecionar([aberta], depois)), 1)
        self.assertIn("No jobs were run", rf.montar(rf.selecionar([aberta], depois), depois)[1])


if __name__ == "__main__":
    unittest.main()
