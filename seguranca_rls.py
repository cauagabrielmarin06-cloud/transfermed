"""Teste de segurança semanal (09/11/2026): com a chave PÚBLICA (anon) que está no site, tenta ler cada tabela do Supabase.
O esperado é zero linhas (erro de permissão ou lista vazia). Se alguma tabela devolver QUALQUER linha, o RLS falhou: o
guardião abre uma issue `workflow` na hora e o dono precisa ativar o RLS e revogar a leitura pública.

A chave anon é pública por desenho (vai no docs/dados.js); este teste não usa nenhum segredo. O resultado só tem contagens,
nunca o conteúdo de uma linha (o log do Actions é público).

Uso:  python seguranca_rls.py          (lê a URL e a chave do docs/dados.js do repositório)
      SUPABASE_URL / SUPABASE_ANON_KEY no ambiente têm prioridade
Saída 0 = nada vazou; 1 = vazou ou não deu para testar.
"""
import json
import os
import re
import sys
from pathlib import Path

import requests

PASTA = Path(__file__).resolve().parent
TABELAS = ("assinantes", "notificacoes", "mensagens", "eventos", "disparos")


def credenciais_publicas():
    url, chave = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_ANON_KEY")
    if url and chave:
        return url.rstrip("/"), chave
    txt = (PASTA / "docs" / "dados.js").read_text(encoding="utf-8")
    m = re.search(r"window\.TM_CONFIG\s*=\s*(\{.*\});", txt)
    cfg = json.loads(m.group(1)) if m else {}
    return (cfg.get("supabaseUrl") or "").rstrip("/"), cfg.get("supabaseAnon") or ""


def testar(url, chave, tabelas=TABELAS, sessao=requests):
    """{tabela: {"http": código, "linhas": n}}; linhas > 0 é vazamento. Falha de rede vira http None (não conta como seguro)."""
    cab = {"apikey": chave, "Authorization": f"Bearer {chave}", "Prefer": "count=exact", "Range": "0-4"}
    saida = {}
    for t in tabelas:
        try:
            r = sessao.get(f"{url}/rest/v1/{t}", params={"select": "*"}, headers=cab, timeout=30)
        except requests.RequestException:
            saida[t] = {"http": None, "linhas": None}
            continue
        linhas = 0
        if r.ok:
            try:
                corpo = r.json()
                linhas = len(corpo) if isinstance(corpo, list) else 1
            except ValueError:
                linhas = None
            total = (r.headers.get("Content-Range") or "").split("/")[-1]
            if total.isdigit():
                linhas = max(linhas or 0, int(total))
        saida[t] = {"http": r.status_code, "linhas": linhas}
    return saida


def veredito(res):
    """('ok'|'vazou'|'nao_testado', [tabelas])."""
    vazou = [t for t, v in res.items() if v["linhas"]]
    if vazou:
        return "vazou", vazou
    incertas = [t for t, v in res.items() if v["http"] is None or v["linhas"] is None]
    return ("nao_testado", incertas) if incertas else ("ok", [])


def main():
    url, chave = credenciais_publicas()
    if not url or not chave:
        print("Sem URL ou chave pública do Supabase.")
        return 1
    res = testar(url, chave)
    v, tabs = veredito(res)
    print("RLS com a chave pública:", json.dumps(res, ensure_ascii=False))
    print({"ok": "OK: nenhuma tabela legível com a chave pública.",
           "vazou": "VAZAMENTO: a chave pública leu linhas de " + ", ".join(tabs) + ". Ativar o RLS e revogar o acesso na hora.",
           "nao_testado": "Não deu para testar: " + ", ".join(tabs)}[v])
    return 0 if v == "ok" else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
