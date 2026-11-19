"""
Resumo diário das falhas de workflow (09/11/2026): UM e-mail, só para o dono (CONTATO_DESTINO), e SÓ se existir issue com a etiqueta
"workflow" aberta há mais de 2 horas, ou seja, uma falha que ninguém corrigiu. Sem issue velha: não envia nada (e o log diz isso).

Por que 2 horas: o vigia já repete sozinho as falhas do próprio GitHub (3 vezes, de 15 em 15 minutos) e só abre issue se continuar
falhando; uma issue ainda aberta depois de 2 h é falha que precisa de uma pessoa.

O registro do Actions é público: o script só imprime quantas issues entraram no resumo, nunca os títulos nem o e-mail.
19/11/2026: "exige ação" passou a querer dizer "o workflow ainda falha". A issue que continua aberta mas cujo workflow já rodou VERDE
depois (o caso das issues 155 a 189, corrigidas e só não fechadas) não entra no e-mail: seria o mesmo aviso todo dia sobre algo
resolvido, e o dono deixa de ler. Se não der para consultar o último resultado (API fora), a issue entra (melhor avisar a mais).
Roda por resumo_falhas.yml (todo dia, 8h30 de Brasília). Texto simples, sem rastreador.

uso: python resumo_falhas.py [--enviar]       (sem --enviar só mostra; lê GITHUB_REPOSITORY e GITHUB_TOKEN)
"""
import argparse
import os
import re
import sys
from datetime import datetime, timezone

import requests

API = "https://api.github.com"
HORAS = 2


def parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def selecionar(issues, agora, horas=HORAS):
    """Issues de workflow ainda abertas há mais de `horas` horas (as mais antigas primeiro). Pull requests nunca entram."""
    velhas = []
    for i in issues:
        if i.get("pull_request") or i.get("state", "open") != "open":
            continue
        if not any((x.get("name") if isinstance(x, dict) else x) == "workflow" for x in i.get("labels") or []):
            continue
        idade = (agora - parse(i["created_at"])).total_seconds() / 3600
        if idade > horas:
            velhas.append((idade, i))
    return [i for _, i in sorted(velhas, key=lambda t: -t[0])]


def arquivo_do_workflow(corpo):
    """`monitor.yml` tirado da marca invisível `chave=workflow:monitor.yml:falha:123` que o vigia grava no corpo da issue; None se não houver."""
    m = re.search(r"chave=workflow:([A-Za-z0-9_.-]+\.ya?ml):", corpo or "")
    return m.group(1) if m else None


def ainda_falha(issue, ultimo_resultado):
    """True se a issue exige ação: o último resultado do workflow dela não é sucesso (ou não deu para saber).
    `ultimo_resultado(arquivo)` devolve 'success', 'failure'... ou None (desconhecido)."""
    arquivo = arquivo_do_workflow(issue.get("body"))
    if not arquivo:
        return True
    try:
        return ultimo_resultado(arquivo) != "success"
    except Exception:  # noqa: BLE001 - API fora: na dúvida, avisa
        return True


def buscar_ultimo_resultado(repo, token, arquivo, http=None):
    """Conclusão da última rodada JÁ TERMINADA do workflow na main (success, failure, timed_out...), ignorando cancelada e pulada."""
    r = (http or requests).get(f"{API}/repos/{repo}/actions/workflows/{arquivo}/runs", timeout=30,
                               params={"status": "completed", "branch": "main", "per_page": 10},
                               headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    r.raise_for_status()
    for run in r.json().get("workflow_runs", []):
        if run.get("conclusion") in ("success", "failure", "timed_out", "startup_failure"):
            return run["conclusion"]
    return None


def causa(corpo):
    m = re.search(r"\*\*Causa provável:\*\*\s*(.+)", corpo or "")
    return re.sub(r"[*`]", "", m.group(1)).strip() if m else "veja a issue"


def montar(selecionadas, agora):
    n = len(selecionadas)
    assunto = f"Transfermed: {n} falha{'s' if n > 1 else ''} de workflow sem correção há mais de {HORAS} h"
    linhas = [f"Há {n} issue{'s' if n > 1 else ''} de workflow aberta{'s' if n > 1 else ''} há mais de {HORAS} horas "
              "(o vigia já repetiu sozinho o que era falha do GitHub; o que sobrou precisa de você ou da próxima sessão).", ""]
    for i in selecionadas:
        horas = int((agora - parse(i["created_at"])).total_seconds() // 3600)
        linhas += [f"- {i['title']}", f"  aberta há {horas} h · causa provável: {causa(i.get('body'))}", f"  {i['html_url']}", ""]
    linhas.append("Regra do projeto: corrigir a causa, rodar o workflow de novo, confirmar o sucesso e só então fechar a issue.")
    return assunto, "\n".join(linhas) + "\n"


def buscar(repo, token, http=None):
    http = http or requests
    r = http.get(f"{API}/repos/{repo}/issues", params={"labels": "workflow", "state": "open", "per_page": 100}, timeout=30,
                 headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    r.raise_for_status()
    return r.json()


def enviar(assunto, texto, env=None, http=None):
    """Brevo, texto simples, só para o dono. Devolve (ok, status)."""
    env = env or os.environ
    faltam = [v for v in ("BREVO_API_KEY", "REMETENTE_EMAIL", "CONTATO_DESTINO") if not env.get(v)]
    if faltam:
        return False, "faltam " + ", ".join(faltam)
    r = (http or requests).post("https://api.brevo.com/v3/smtp/email", timeout=30,
                                headers={"api-key": env["BREVO_API_KEY"], "Content-Type": "application/json"},
                                json={"sender": {"email": env["REMETENTE_EMAIL"], "name": "Transfermed (falhas)"},
                                      "to": [{"email": env["CONTATO_DESTINO"]}], "subject": assunto, "textContent": texto})
    return r.ok, f"HTTP {r.status_code}"


def main(argv=None, agora=None, issues=None, http=None, ultimo_resultado=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--enviar", action="store_true")
    args = ap.parse_args(argv)
    agora = agora or datetime.now(timezone.utc)
    if issues is None:
        issues = buscar(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"], http)
    velhas = selecionar(issues, agora)
    if ultimo_resultado is None:
        repo, token = os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_TOKEN", "")
        ultimo_resultado = lambda arq: buscar_ultimo_resultado(repo, token, arq, http)  # noqa: E731
    sel = [i for i in velhas if ainda_falha(i, ultimo_resultado)]
    if not sel:
        extra = f" ({len(velhas)} já voltou a passar: só falta fechar a issue)" if velhas else ""
        print(f"Resumo de falhas: nenhuma falha que exija ação{extra}; nada a enviar")
        return 0
    assunto, texto = montar(sel, agora)
    if not args.enviar:
        print(assunto + "\n\n" + texto)
        return 0
    ok, situacao = enviar(assunto, texto, http=http)
    print(f"Resumo de falhas: {len(sel)} issue(s) antiga(s); envio ao dono: {situacao}")  # público: só a contagem e a situação
    return 0 if ok else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
