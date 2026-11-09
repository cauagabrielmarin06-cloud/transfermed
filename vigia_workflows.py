"""
Vigia dos workflows: confere se cada robô do GitHub Actions rodou no horário e terminou bem; se não, abre uma issue com a causa provável.

Duas faltas viram issue (etiqueta "workflow", fonte "workflows" no issues.py):
1. A última execução terminou com falha ou estouro de tempo. A issue NÃO fecha sozinha: a próxima sessão lê a causa, corrige e fecha
   (regra no CLAUDE.md: issue de workflow vem antes de qualquer outra tarefa). Uma issue por execução que falhou.
2. O workflow agendado não rodou no horário: a última execução é mais velha que a margem de cada um. Essa fecha sozinha quando ele volta a rodar.

Roda a cada hora e logo depois que qualquer workflow falha (vigia_workflows.yml), e também no guardião diário.

Falha do PRÓPRIO GITHUB (09/11/2026) não é falha nossa e não abre issue de cara: "No jobs were run" (nenhum job criado), erro de
infraestrutura do runner (shutdown signal, lost communication...), cancelamento pelo GitHub ou incidente ativo em githubstatus.com
na hora da execução. Nesses casos o vigia espera 15 minutos, repete a execução (API `rerun`) e confere; até 3 vezes. Só se continuar
falhando abre a issue (e, se a repetição falhar por causa nossa, abre a issue da falha real). O vigia termina verde em todos esses casos.
Para não duplicar efeito, uma execução que chegou a rodar jobs só é repetida nos workflows de IDEMPOTENTES (os que enviam e-mail a
inscritos ou ao dono não entram); sem nenhum job rodado, repetir é seguro para todos.
Com `actions: write` (só para a repetição); nunca dispara outro workflow nem envia e-mail.

Uso:  python vigia_workflows.py [--sem-rede]     (lê GITHUB_REPOSITORY e GITHUB_TOKEN)
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

PASTA = Path(__file__).resolve().parent
SAIDA = PASTA / "qa" / "relatorios" / "achados_workflows.json"
API = "https://api.github.com"
# arquivo -> (nome, horas máximas sem rodar; None = só manual, vigia apenas a falha).
# As margens cobrem o atraso normal do agendador do GitHub (até ~1 h) sem esperar um dia inteiro.
WORKFLOWS = {
    "alertas.yml": ("Alertas por e-mail", 3),
    "radar.yml": ("Radar de editais", 27),
    "monitor.yml": ("Monitor de editais e prazos", 27),
    "qualidade.yml": ("Qualidade do site", 27),
    "guardiao.yml": ("Guardião do site no ar", 27),
    "relatorio.yml": ("Relatório semanal", 24 * 7 + 3),
    "envio_b0.yml": ("Envio B0 (Perfil oficial grátis)", None),
    "diagnostico-email.yml": ("Diagnóstico de e-mail (manual)", None),
    "teste_confirmacao.yml": ("Teste do e-mail de confirmação (manual)", None),
    "lembrete_valor.yml": ("Lembrete com valor (envio único, manual)", None),
    "instagram_dia.yml": ("Instagram do dia seguinte", 27),
    "resumo_falhas.yml": ("Resumo diário de falhas (e-mail ao dono)", 27),
}
# Execuções que já rodaram jobs só são repetidas se o workflow é seguro de repetir (não manda e-mail a inscritos nem faz envio avulso).
IDEMPOTENTES = {"radar.yml", "monitor.yml", "qualidade.yml", "guardiao.yml", "instagram_dia.yml", "resumo_falhas.yml"}
TENTATIVAS, ESPERA_S, LIMITE_EXECUCAO_S = 3, 15 * 60, 40 * 60
INFRA_MENSAGENS = re.compile(
    r"runner has received a shutdown signal|lost communication with the server|hosted runner.{0,40}(encountered an error|did not)|"
    r"internal server error|service unavailable|bad gateway|the job was not acquired|failed to (download|resolve) action|"
    r"unable to (download|resolve) action|no jobs were run|could not resolve host|connection (reset|timed out)", re.I)
STATUS_INCIDENTES = "https://www.githubstatus.com/api/v2/incidents.json"
FALHAS = {"failure", "timed_out", "startup_failure"}

# palavra no nome do passo que falhou -> causa provável (o log da execução confirma)
CAUSAS = [
    ("teste", "um teste travou a publicação de propósito: leia o FAIL no log e corrija o DADO que o causou, não o teste "
              "(se o teste estiver errado para um estado real dos dados, corrija o código com um teste que prove o defeito)"),
    ("salvar", "o push para o repositório foi recusado (conflito ou erro do GitHub): rode de novo; se repetir, veja o log do `git push`"),
    ("guardar", "o push para o repositório foi recusado (conflito ou erro do GitHub): rode de novo; se repetir, veja o log do `git push`"),
    ("rodar", "o próprio robô quebrou (exceção em Python): veja o Traceback no log"),
    ("instalar", "falha ao instalar dependências (pip ou npm): confira requirements.txt e a disponibilidade do pacote"),
    ("enviar", "o envio falhou no Brevo (chave, remetente não verificado ou limite): veja o código HTTP no log"),
    ("falhar se", "um passo anterior falhou (os testes): veja o primeiro passo marcado com falha no log"),
]


def parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def causa_provavel(passos_com_falha):
    for nome in passos_com_falha:
        baixo = nome.lower()
        for palavra, causa in CAUSAS:
            if palavra in baixo:
                return f"passo «{nome}»: {causa}."
    if passos_com_falha:
        return f"passo «{passos_com_falha[0]}» falhou; a causa só aparece no log."
    return "nenhum passo registrado com falha (cancelado pelo GitHub, estouro de tempo ou falha ao iniciar): veja o log."


def achado(chave, titulo, corpo, auto_fecha):
    return {"chave": f"workflow:{chave}", "etiqueta": "workflow", "titulo": titulo[:120], "corpo": corpo, "auto_fecha": auto_fecha}


def achado_de_falha(arq, nome, r, causa, extra=""):
    return achado(
        f"{arq}:falha:{r['id']}", f"Workflow «{nome}» falhou em {r['created_at'][:10]} {r['created_at'][11:16]} UTC",
        f"O workflow **{nome}** (`{arq}`) terminou com `{r['conclusion']}` em {r['created_at']} (gatilho: {r.get('event')}).\n\n"
        f"**Causa provável:** {causa}\n\n{extra}"
        f"Log: {r.get('html_url')}\n\n"
        "Regra do projeto: a próxima sessão corrige esta issue **antes de qualquer outra tarefa**, roda o workflow de novo, "
        "confirma que terminou com sucesso e só então fecha a issue.", auto_fecha=False)


def incidente_ativo(run, incidentes):
    """Nome do incidente do GitHub (Actions) que cobria a hora da execução, ou None. incidentes: lista de githubstatus.com/api/v2/incidents.json."""
    ini = parse(run["created_at"])
    fim = parse(run.get("updated_at") or run["created_at"])
    for i in incidentes or []:
        nomes = [i.get("name", "")] + [c.get("name", "") for c in i.get("components") or []]
        if not any(re.search(r"actions", n, re.I) for n in nomes):
            continue
        comeco = parse(i["created_at"]) - timedelta(minutes=15)
        fim_inc = parse(i["resolved_at"]) + timedelta(minutes=30) if i.get("resolved_at") else datetime.max.replace(tzinfo=timezone.utc)
        if comeco <= fim and ini <= fim_inc:
            return i.get("name")
    return None


def falha_de_infra(run, jobs, anotacoes=(), incidentes=()):
    """Motivo (texto) se a execução falhou por culpa do GitHub, senão None. Função pura.
    jobs: lista de jobs da execução (API); anotacoes: textos das anotações dos jobs com falha."""
    conclusao = run.get("conclusion")
    if conclusao in FALHAS and not jobs:
        return "nenhum job foi executado («No jobs were run»: o GitHub não iniciou a execução)"
    for texto in anotacoes:
        m = INFRA_MENSAGENS.search(texto or "")
        if m:
            return f"erro de infraestrutura do runner: «{m.group(0)}»"
    if conclusao in FALHAS or conclusao == "cancelled":
        inc = incidente_ativo(run, incidentes)
        if inc:
            return f"incidente ativo no GitHub Actions («{inc}») durante a execução"
    return None


def checar(execucoes, agora, passos_com_falha=lambda run_id: [], infra=lambda run: None):
    """execucoes: {arquivo: [execuções da API, a mais nova primeiro]}. Função pura (os testes a conferem).
    infra(run) -> motivo se a falha foi do próprio GitHub: essa execução NÃO vira issue aqui (ela vai para `retentar`)."""
    achados = []
    for arq, (nome, horas) in WORKFLOWS.items():
        runs = execucoes.get(arq)
        if runs is None:
            continue
        concluidas = [r for r in runs if r.get("conclusion") and r["conclusion"] not in ("cancelled", "skipped")]
        if concluidas and concluidas[0]["conclusion"] in FALHAS and not infra(concluidas[0]):
            r = concluidas[0]
            achados.append(achado_de_falha(arq, nome, r, causa_provavel(passos_com_falha(r["id"]))))
        if horas and runs:
            ultima = max(parse(r["created_at"]) for r in runs)
            atraso = agora - ultima
            if atraso > timedelta(hours=horas):
                achados.append(achado(
                    f"{arq}:parado", f"Workflow «{nome}» não rodou no horário (última execução há {int(atraso.total_seconds() // 3600)} h)",
                    f"O workflow **{nome}** (`{arq}`) deveria rodar pelo menos a cada {horas} h e a última execução foi em {ultima.isoformat()}.\n\n"
                    "**Causa provável:** o GitHub pausa agendamentos de repositório sem atividade por 60 dias, ou o agendador atrasou/pulou "
                    "a rodada, ou o workflow foi desativado. Veja a aba Actions e reative o workflow; rode-o à mão uma vez.", auto_fecha=True))
        elif horas and not runs:
            achados.append(achado(f"{arq}:parado", f"Workflow «{nome}» nunca rodou", "Nenhuma execução encontrada na API.", auto_fecha=True))
    return achados


def candidatas_a_retentar(execucoes, infra):
    """[(arquivo, nome, execução, motivo)] das últimas execuções que falharam (ou foram canceladas) por culpa do GitHub."""
    saida = []
    for arq, (nome, _) in WORKFLOWS.items():
        runs = [r for r in execucoes.get(arq) or [] if r.get("conclusion") and r["conclusion"] != "skipped"]
        if runs and runs[0]["conclusion"] in FALHAS | {"cancelled"}:
            motivo = infra(runs[0])
            if motivo:
                saida.append((arq, nome, runs[0], motivo))
    return saida


def retentar(api, candidatas, dormir=None, tentativas=TENTATIVAS, espera=ESPERA_S, infra=lambda run: None, passos=lambda i: []):
    """Espera 15 min, repete a execução e confere; até `tentativas` vezes. Devolve os achados que sobraram (issue só se continuar falhando)."""
    dormir = dormir or time.sleep
    achados, pendentes = [], list(candidatas)
    for n in range(1, tentativas + 1):
        if not pendentes:
            break
        dormir(espera)
        seguintes = []
        for arq, nome, r, motivo in pendentes:
            if r.get("jobs_rodaram") and arq not in IDEMPOTENTES:  # já rodou job: repetir poderia duplicar um envio
                achados.append(achado_de_falha(arq, nome, r, motivo, "Não repeti sozinho: o workflow já rodava jobs e não é seguro repetir (poderia duplicar envio).\n\n"))
                continue
            try:
                novo = api.repetir(r)
            except Exception as e:  # noqa: BLE001 - qualquer erro da API aqui vira issue, nunca derruba o vigia
                achados.append(achado_de_falha(arq, nome, r, motivo, f"A repetição automática falhou ({type(e).__name__}).\n\n"))
                continue
            print(f"  {nome}: repetido ({n}/{tentativas}) -> {novo.get('conclusion')}")
            if novo.get("conclusion") == "success":
                continue
            outro = infra(novo)
            if outro is None and novo.get("conclusion") in FALHAS:  # falhou de verdade, por culpa nossa
                achados.append(achado_de_falha(arq, nome, novo, causa_provavel(passos(novo["id"])), "Falha real: apareceu depois de repetir uma falha do GitHub.\n\n"))
            elif novo.get("conclusion") in FALHAS | {"cancelled"}:
                seguintes.append((arq, nome, novo, outro or motivo))
        pendentes = seguintes
    for arq, nome, r, motivo in pendentes:
        achados.append(achado_de_falha(arq, nome, dict(r, conclusion=r["conclusion"] if r.get("conclusion") in FALHAS else "failure"), motivo,
                                       f"Continuou falhando em {tentativas} repetições automáticas, espaçadas de {espera // 60} min (falha do GitHub: {motivo}).\n\n"))
    return achados


class Api:
    def __init__(self, repo, token, http=None):
        self.repo, self.http = repo, http or requests.Session()
        self.http.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                                  "X-GitHub-Api-Version": "2022-11-28"})

    def get(self, caminho, **params):
        r = self.http.get(f"{API}/repos/{self.repo}{caminho}", params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def execucoes(self, arquivo):
        return self.get(f"/actions/workflows/{arquivo}/runs", per_page=10)["workflow_runs"]

    def jobs(self, run_id):
        return self.get(f"/actions/runs/{run_id}/jobs", per_page=30)["jobs"]

    def anotacoes(self, run_id):
        """Textos das anotações dos jobs que falharam (é onde o GitHub escreve «runner has received a shutdown signal» etc.)."""
        textos = []
        try:
            for j in self.jobs(run_id):
                if j.get("conclusion") in FALHAS | {"cancelled"} and j.get("check_run_url"):
                    r = self.http.get(j["check_run_url"] + "/annotations", timeout=30)
                    if r.ok:
                        textos += [a.get("message") or "" for a in r.json()]
        except (requests.RequestException, KeyError, ValueError):
            pass
        return textos

    def incidentes(self):
        try:  # sem o token do GitHub: é outro site
            return requests.get(STATUS_INCIDENTES, timeout=20).json().get("incidents", [])
        except (requests.RequestException, ValueError):
            return []

    def classificar(self, run, incidentes):
        try:
            jobs = self.jobs(run["id"])
        except (requests.RequestException, KeyError, ValueError):
            return None  # não deu para perguntar: trata como falha comum (issue)
        run["jobs_rodaram"] = bool(jobs)
        return falha_de_infra(run, jobs, self.anotacoes(run["id"]) if jobs else (), incidentes)

    def repetir(self, run, dormir=None, limite=LIMITE_EXECUCAO_S):
        """Repete a execução (só os jobs que falharam, ou tudo se nenhum job rodou) e espera terminar. Devolve a execução atualizada."""
        rota = f"/actions/runs/{run['id']}/rerun-failed-jobs" if run.get("jobs_rodaram") else f"/actions/runs/{run['id']}/rerun"
        r = self.http.post(f"{API}/repos/{self.repo}{rota}", timeout=30)
        r.raise_for_status()
        dormir = dormir or time.sleep
        espera = 0
        while espera <= limite:
            dormir(30)
            espera += 30
            atual = self.get(f"/actions/runs/{run['id']}")
            if atual.get("status") == "completed" and atual.get("run_attempt", 1) > run.get("run_attempt", 1):
                atual["jobs_rodaram"] = bool(self.jobs(run["id"]))
                return atual
        raise TimeoutError("a repetição não terminou no tempo limite")

    def passos_com_falha(self, run_id):
        try:
            jobs = self.get(f"/actions/runs/{run_id}/jobs", per_page=30)["jobs"]
        except (requests.RequestException, KeyError, ValueError):
            return []
        return [p["name"] for j in jobs for p in j.get("steps", []) if p.get("conclusion") == "failure"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sem-rede", action="store_true")
    ap.parse_args(argv)
    api = Api(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"])
    execs = {}
    for arq in WORKFLOWS:
        try:
            execs[arq] = api.execucoes(arq)
        except requests.RequestException as e:
            # não conseguir perguntar à API não é falha do workflow: sai sem achado para não fechar nem abrir nada por engano
            print(f"  {arq}: API indisponível ({type(e).__name__}); ignorado nesta rodada")
    incidentes = api.incidentes()
    infra = lambda run: api.classificar(run, incidentes)  # noqa: E731
    achados = checar(execs, datetime.now(timezone.utc), api.passos_com_falha, infra)
    candidatas = candidatas_a_retentar(execs, infra)
    if candidatas:
        print(f"Falha do GitHub em {len(candidatas)} workflow(s): repetindo sozinho em {ESPERA_S // 60} min, até {TENTATIVAS} vezes")
        for _, nome, _, motivo in candidatas:
            print(f"  {nome}: {motivo}")
        achados += retentar(api, candidatas, infra=infra, passos=api.passos_com_falha)
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps({"achados": achados}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Vigia dos workflows: {len(achados)} achado(s)")
    for a in achados:
        print(f"  {a['titulo']}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
