"""
Transforma achados (do monitor.py ou da qualidade) em issues no GitHub, sem duplicar.

Cada issue guarda no corpo uma marca invisível:  <!-- transfermed fonte=... chave=... hash=... auto=0|1 estado=... -->
- achado novo                         -> cria a issue (com a etiqueta do achado)
- issue aberta com a mesma chave      -> atualiza título e corpo se o conteúdo mudou (sem comentar: não gera aviso)
- issue fechada pelo robô (estado=auto) e o problema voltou -> reabre com um comentário
- issue fechada por uma pessoa        -> só reabre se o conteúdo mudou (senão respeita o fechamento)
- issue aberta cujo problema sumiu    -> fecha sozinha, mas só se o achado era do tipo que fecha sozinho
  (prazo, página fora do ar, qualidade). Edital novo e retificação esperam alguém ler o PDF.

Uso (no GitHub Actions, com GITHUB_TOKEN e GITHUB_REPOSITORY):
  python issues.py --fonte monitor --achados qa/relatorios/achados_monitor.json
  python issues.py --fonte qualidade --achados qa/relatorios/achados_qualidade.json
  python issues.py ... --simular        # só mostra o que faria, sem chamar o GitHub
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

API = "https://api.github.com"
MARCA = re.compile(r"<!-- transfermed (.*?) -->")
ETIQUETAS = {  # nome: (cor, descrição)
    "prazo": ("d93f0b", "Inscrições encerram em até 7 dias"),
    "edital-novo": ("0e8a16", "Edital novo ou link novo para conferir no PDF"),
    "retificação": ("fbca04", "Retificação, aditivo ou PDF alterado"),
    "link-quebrado": ("b60205", "Página, PDF ou link que não abre"),
    "qualidade": ("5319e7", "Testes, HTML, acessibilidade, links ou Lighthouse"),
    "conferir": ("c5def5", "Dado publicado que precisa de conferência no edital"),
}
MAX_CRIAR = 40  # proteção contra uma enxurrada de issues se algo der muito errado


def impressao(a):
    """O que define "o mesmo problema": `estavel` quando o achado tem partes que mudam todo dia (contagem do prazo)."""
    base = a.get("estavel") or f"{a['titulo']}\n{a['corpo']}"
    return hashlib.sha256(base.encode()).hexdigest()[:12]


def ler_marca(corpo):
    m = MARCA.search(corpo or "")
    if not m:
        return None
    return dict(par.split("=", 1) for par in m.group(1).split() if "=" in par)


def montar_corpo(a, fonte, estado="aberta"):
    marca = (f"<!-- transfermed fonte={fonte} chave={a['chave']} hash={impressao(a)} "
             f"auto={1 if a.get('auto_fecha', True) else 0} estado={estado} -->")
    rodape = ("\n\n---\n_Issue mantida pelo monitor do Transfermed. Ela é atualizada sozinha; "
              + ("fecha sozinha quando o problema some._" if a.get("auto_fecha", True)
                 else "feche depois de conferir no PDF oficial._"))
    return f"{a['corpo']}{rodape}\n{marca}"


def planejar(achados, existentes, fonte):
    """achados: lista do monitor/qualidade. existentes: issues do repositório (dicts da API do GitHub).
    Devolve [(ação, número_da_issue_ou_None, achado_ou_None)]. Função pura: é o que os testes conferem."""
    por_chave = {}
    for i in existentes:
        if "pull_request" in i:
            continue
        m = ler_marca(i.get("body"))
        if not m or m.get("fonte") != fonte:
            continue
        atual = por_chave.get(m["chave"])
        # se houver mais de uma (não deveria), vale a aberta; depois a mais recente
        if atual is None or (i["state"] == "open" and atual[0]["state"] != "open") or \
                (i["state"] == atual[0]["state"] and i["number"] > atual[0]["number"]):
            por_chave[m["chave"]] = (i, m)
    acoes, vistos = [], set()
    for a in achados:
        if a["chave"] in vistos:
            continue
        vistos.add(a["chave"])
        achou = por_chave.get(a["chave"])
        if not achou:
            acoes.append(("criar", None, a))
            continue
        issue, m = achou
        mudou = m.get("hash") != impressao(a)
        if issue["state"] == "open":
            if issue.get("title") != a["titulo"] or issue.get("body") != montar_corpo(a, fonte):
                acoes.append(("atualizar", issue["number"], a))
        elif m.get("estado") == "auto" or mudou:
            acoes.append(("reabrir", issue["number"], a))
    for chave, (issue, m) in por_chave.items():
        if issue["state"] == "open" and chave not in vistos and m.get("auto") == "1":
            acoes.append(("fechar", issue["number"], None))
    return acoes


class GitHub:
    def __init__(self, repo, token):
        self.repo, self.s = repo, requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                               "X-GitHub-Api-Version": "2022-11-28"})

    def _req(self, metodo, caminho, **kw):
        r = self.s.request(metodo, f"{API}/repos/{self.repo}{caminho}", timeout=30, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"{metodo} {caminho}: {r.status_code} {r.text[:300]}")
        return r.json() if r.text else {}

    def issues(self):
        todas, pagina = [], 1
        while True:
            lote = self._req("GET", "/issues", params={"state": "all", "per_page": 100, "page": pagina})
            todas += lote
            if len(lote) < 100:
                return todas
            pagina += 1

    def garantir_etiquetas(self):
        existentes = {e["name"] for e in self._req("GET", "/labels", params={"per_page": 100})}
        for nome, (cor, desc) in ETIQUETAS.items():
            if nome not in existentes:
                self._req("POST", "/labels", json={"name": nome, "color": cor, "description": desc})

    def criar(self, a, fonte):
        return self._req("POST", "/issues", json={"title": a["titulo"], "body": montar_corpo(a, fonte),
                                                  "labels": [a["etiqueta"]]})["number"]

    def atualizar(self, n, a, fonte, reabrir=False):
        dados = {"title": a["titulo"], "body": montar_corpo(a, fonte), "labels": [a["etiqueta"]]}
        if reabrir:
            dados["state"] = "open"
        self._req("PATCH", f"/issues/{n}", json=dados)
        if reabrir:
            self._req("POST", f"/issues/{n}/comments", json={"body": "O problema voltou a aparecer no monitor de hoje."})

    def fechar(self, n, issue_atual):
        corpo = re.sub(r"estado=\w+", "estado=auto", issue_atual.get("body") or "")
        self._req("POST", f"/issues/{n}/comments", json={"body": "Resolvido: o problema não apareceu no monitor de hoje."})
        self._req("PATCH", f"/issues/{n}", json={"state": "closed", "state_reason": "completed", "body": corpo})


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonte", required=True, choices=["monitor", "qualidade"])
    ap.add_argument("--achados", required=True)
    ap.add_argument("--simular", action="store_true")
    args = ap.parse_args(argv)
    dados = json.loads(Path(args.achados).read_text(encoding="utf-8"))
    achados = dados["achados"] if isinstance(dados, dict) else dados
    if args.simular:
        acoes = planejar(achados, [], args.fonte)
        print(f"(simulação, sem issues existentes) {len(acoes)} ação(ões):")
        for acao, n, a in acoes:
            print(f"  {acao} [{a['etiqueta']}] {a['titulo']}")
        return 0
    gh = GitHub(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"])
    gh.garantir_etiquetas()
    existentes = gh.issues()
    por_numero = {i["number"]: i for i in existentes}
    acoes = planejar(achados, existentes, args.fonte)
    criadas = 0
    resumo = {"criar": 0, "atualizar": 0, "reabrir": 0, "fechar": 0}
    for acao, n, a in acoes:
        if acao == "criar":
            if criadas >= MAX_CRIAR:
                print(f"  limite de {MAX_CRIAR} issues novas por rodada atingido; o resto fica para amanhã")
                continue
            n = gh.criar(a, args.fonte)
            criadas += 1
            time.sleep(1)  # o GitHub limita criações muito rápidas
        elif acao == "atualizar":
            gh.atualizar(n, a, args.fonte)
        elif acao == "reabrir":
            gh.atualizar(n, a, args.fonte, reabrir=True)
        elif acao == "fechar":
            gh.fechar(n, por_numero[n])
        resumo[acao] += 1
        print(f"  {acao} #{n}" + (f" [{a['etiqueta']}] {a['titulo']}" if a else ""))
    print("Resumo:", ", ".join(f"{k}: {v}" for k, v in resumo.items()))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
