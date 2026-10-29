"""Junta os resultados da verificação diária de qualidade (qualidade.yml) em achados para o issues.py.
Um achado por verificação que falhou; cada um fecha sozinho quando a verificação volta a passar.

uso: python qa/achados_qualidade.py --testes ok|falhou [--html ...] [--links ...] [--axe ...] [--interacoes ...]
     [--lighthouse pasta]
"""
import argparse
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "qa" / "relatorios" / "achados_qualidade.json"
EXCECOES = RAIZ / "qa" / "links_excecoes.txt"
RUN = ""  # link da execução do Actions (preenchido por --execucao)
METAS = {"accessibility": 90, "best-practices": 90, "seo": 90, "performance": 70}


def achado(chave, etiqueta, titulo, corpo):
    return {"chave": chave, "etiqueta": etiqueta, "titulo": titulo, "corpo": corpo + (f"\n\nExecução: {RUN}" if RUN else ""),
            "auto_fecha": True}


def ler(caminho):
    p = Path(caminho) if caminho else None
    if not p or not p.exists() or not p.stat().st_size:
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def ler_lista(caminho):
    """Como ler(), mas um arquivo com [] (nenhuma falha) não é confundido com "não rodou"."""
    p = Path(caminho)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() and p.stat().st_size else None


def excecoes():
    return [re.compile(l.strip()) for l in EXCECOES.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("#")]


def checar_html(rel):
    erros = [(f["filePath"].split("docs")[-1], m) for f in rel or [] for m in f.get("messages", [])]
    if not erros:
        return []
    linhas = "".join(f"- `{arq}:{m.get('line')}` {m.get('ruleId')}: {m.get('message')}\n" for arq, m in erros[:40])
    return [achado("qualidade:html", "qualidade", f"HTML inválido em {len({a for a, _ in erros})} página(s)",
                   f"O html-validate apontou {len(erros)} problema(s). Corrigir no gerador (`gerar_site.py`), não nas "
                   f"páginas.\n\n{linhas}")]


def checar_links(rel, editais_publicados):
    if rel is None:
        return [achado("qualidade:links", "link-quebrado", "A checagem de links não rodou", "Ver o registro da execução.")]
    regras = excecoes()
    quebrados = [l for l in rel.get("links", []) if l.get("state") == "BROKEN" and not any(r.search(l["url"]) for r in regras)]
    internos = [l for l in quebrados if "127.0.0.1" in l["url"] or "localhost" in l["url"]]
    pdfs = [l for l in quebrados if l["url"] in editais_publicados]
    outros = [l for l in quebrados if l not in internos and l not in pdfs]
    achados = []
    if internos:
        achados.append(achado("qualidade:links-internos", "link-quebrado", f"{len(internos)} link(s) interno(s) quebrado(s)",
                              "Links do próprio site que não abrem (corrigir no gerador):\n\n" +
                              "".join(f"- {l['status']} {l['url'].split('8765')[-1]} ← {l.get('parent', '').split('8765')[-1]}\n"
                                      for l in internos[:40])))
    if pdfs or outros:
        corpo = ""
        if pdfs:
            corpo += "**Editais publicados com link que não abre:**\n\n" + "".join(
                f"- {l['status']} {l['url']}\n" for l in pdfs) + "\n"
        if outros:
            corpo += "**Outros links externos (sites oficiais):**\n\n" + "".join(
                f"- {l['status']} {l['url']} ← {l.get('parent', '').split('8765')[-1]}\n" for l in outros[:40])
        corpo += ("\nConferir no navegador. Se abrir normalmente (bloqueio a robôs ou certificado), incluir o site em "
                  "`qa/links_excecoes.txt` com o motivo; se a faculdade mudou o endereço, corrigir a ficha ou o edital.")
        achados.append(achado("qualidade:links-externos", "link-quebrado",
                              f"{len(pdfs) + len(outros)} link(s) externo(s) quebrado(s)" + (f", {len(pdfs)} de edital" if pdfs else ""),
                              corpo))
    return achados


def checar_axe(rel):
    if rel is None:
        return [achado("qualidade:paginas", "qualidade", "A verificação das páginas (axe e console) não rodou",
                       "Ver o registro da execução.")]
    problemas = []
    for r in rel:
        itens = [f"axe {v['id']} [{v['impacto']}]: {' ; '.join(v['alvos'])}" for v in r.get("axeGraves", [])]
        itens += [f"console: {c}" for c in r.get("console", [])]
        itens += [f"requisição: {f}" for f in r.get("falhas", [])]
        if r.get("rolagemLateral"):
            itens.append(f"rolagem lateral (largura {r.get('larguraPagina')} px)")
        if r.get("pequenos") and r.get("largura", 0) < 500:
            itens.append("alvos de toque menores que 24 px: " + ", ".join(r["pequenos"][:8]))
        problemas += [f"- **{r['pagina']}** @{r['largura']}px: {i}\n" for i in itens]
    if not problemas:
        return []
    return [achado("qualidade:paginas", "qualidade", f"{len(problemas)} problema(s) de acessibilidade ou de página",
                   "Achados nas páginas principais (375 px e 1280 px):\n\n" + "".join(problemas[:60]))]


def checar_interacoes(rel):
    if rel is None:
        return [achado("qualidade:interacoes", "qualidade", "O teste de interações do início não rodou",
                       "Ver o registro da execução (`qa/interacoes.mjs`).")]
    if not rel:
        return []
    return [achado("qualidade:interacoes", "qualidade", f"{len(rel)} interação(ões) do início quebrada(s)",
                   'O `qa/interacoes.mjs` clica em "Buscar pelo nome", nos botões do mapa ("Brasil" e estados) e confere o '
                   "service worker:\n\n" + "".join(f"- **{r['teste']}** @{r['largura']}: {r['erro']}\n" for r in rel))]


def checar_publicado(rel):
    """sitemap.xml e robots.txt no site no ar (qa/publicado.py): sem eles o Google não lê o mapa do site."""
    if rel is None:
        return [achado("qualidade:publicado", "qualidade", "A conferência do sitemap publicado não rodou",
                       "Ver o registro da execução (`qa/publicado.py`).")]
    if not rel:
        return []
    return [achado("qualidade:publicado", "qualidade", "sitemap.xml ou robots.txt com problema no site publicado",
                   "O Google Search Console não consegue ler o sitemap enquanto isso não for corrigido:\n\n"
                   + "".join(f"- {f}\n" for f in rel))]


def checar_lighthouse(pasta):
    achados = []
    for arq in sorted(Path(pasta).glob("*.json")) if pasta else []:
        r = json.loads(arq.read_text(encoding="utf-8"))
        notas = {k: round((c.get("score") or 0) * 100) for k, c in r.get("categories", {}).items()}
        abaixo = {k: v for k, v in notas.items() if k in METAS and v < METAS[k]}
        if abaixo:
            nome = arq.stem
            achados.append(achado(f"qualidade:lighthouse:{nome}", "qualidade",
                                  f"Lighthouse abaixo da meta em {nome}: " + ", ".join(f"{k} {v}" for k, v in abaixo.items()),
                                  f"Página: {r.get('finalDisplayedUrl') or r.get('requestedUrl')}\n\nNotas (celular): " +
                                  ", ".join(f"{k} {v}" for k, v in notas.items()) +
                                  f"\n\nMetas: " + ", ".join(f"{k} ≥ {v}" for k, v in METAS.items())))
    return achados


def main(argv=None):
    global RUN
    ap = argparse.ArgumentParser()
    ap.add_argument("--testes", choices=["ok", "falhou"], required=True)
    ap.add_argument("--html")
    ap.add_argument("--links")
    ap.add_argument("--axe")
    ap.add_argument("--interacoes")
    ap.add_argument("--lighthouse")
    ap.add_argument("--publicado")
    ap.add_argument("--execucao", default="")
    args = ap.parse_args(argv)
    RUN = args.execucao
    editais = json.loads((RAIZ / "data" / "editais.json").read_text(encoding="utf-8"))
    publicados = {e["url_edital"] for e in editais if e.get("fonte_dados") == "manual"}
    achados = []
    if args.testes == "falhou":
        achados.append(achado("qualidade:testes", "qualidade", "Testes automáticos falhando",
                              "`python -m unittest discover tests` falhou: nada é publicado até corrigir."))
    achados += checar_html(ler(args.html)) if args.html else []
    achados += checar_links(ler(args.links), publicados) if args.links else []
    achados += checar_axe(ler(args.axe)) if args.axe else []
    achados += checar_interacoes(ler_lista(args.interacoes)) if args.interacoes else []
    achados += checar_lighthouse(args.lighthouse) if args.lighthouse else []
    achados += checar_publicado(ler_lista(args.publicado)) if args.publicado else []
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps({"achados": achados}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Achados de qualidade: {len(achados)}")
    for a in achados:
        print(f"  [{a['etiqueta']}] {a['titulo']}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
