"""
Vigia dos workflows: confere se cada robô do GitHub Actions rodou no horário e terminou bem; se não, abre uma issue com a causa provável.

Duas faltas viram issue (etiqueta "workflow", fonte "workflows" no issues.py):
1. A última execução terminou com falha ou estouro de tempo. A issue NÃO fecha sozinha: a próxima sessão lê a causa, corrige e fecha
   (regra no CLAUDE.md: issue de workflow vem antes de qualquer outra tarefa). Uma issue por execução que falhou.
2. O workflow agendado não rodou no horário: a última execução é mais velha que a margem de cada um. Essa fecha sozinha quando ele volta a rodar.

Roda a cada hora e logo depois que qualquer workflow falha (vigia_workflows.yml), e também no guardião diário.
Só lê a API do GitHub (token do próprio job, com `actions: read`); nunca dispara nada.

Uso:  python vigia_workflows.py [--sem-rede]     (lê GITHUB_REPOSITORY e GITHUB_TOKEN)
"""
import argparse
import json
import os
import sys
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
}
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


def checar(execucoes, agora, passos_com_falha=lambda run_id: []):
    """execucoes: {arquivo: [execuções da API, a mais nova primeiro]}. Função pura (os testes a conferem)."""
    achados = []
    for arq, (nome, horas) in WORKFLOWS.items():
        runs = execucoes.get(arq)
        if runs is None:
            continue
        concluidas = [r for r in runs if r.get("conclusion") and r["conclusion"] not in ("cancelled", "skipped")]
        if concluidas and concluidas[0]["conclusion"] in FALHAS:
            r = concluidas[0]
            achados.append(achado(
                f"{arq}:falha:{r['id']}", f"Workflow «{nome}» falhou em {r['created_at'][:10]} {r['created_at'][11:16]} UTC",
                f"O workflow **{nome}** (`{arq}`) terminou com `{r['conclusion']}` em {r['created_at']} (gatilho: {r.get('event')}).\n\n"
                f"**Causa provável:** {causa_provavel(passos_com_falha(r['id']))}\n\n"
                f"Log: {r.get('html_url')}\n\n"
                "Regra do projeto: a próxima sessão corrige esta issue **antes de qualquer outra tarefa**, roda o workflow de novo, "
                "confirma que terminou com sucesso e só então fecha a issue.", auto_fecha=False))
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
    achados = checar(execs, datetime.now(timezone.utc), api.passos_com_falha)
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps({"achados": achados}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Vigia dos workflows: {len(achados)} achado(s)")
    for a in achados:
        print(f"  {a['titulo']}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
