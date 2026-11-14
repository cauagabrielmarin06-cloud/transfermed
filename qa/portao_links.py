"""Portão dos links do qualidade.yml.

O linkinator sai com código 1 quando QUALQUER link está quebrado, inclusive os externos (site de faculdade fora do ar, bloqueio a robô).
Esses viram issue "link-quebrado" (achados_qualidade.py) e não devem deixar o workflow vermelho. Este portão reprova só o que é defeito do
próprio site ou da checagem:
  - o rastreamento não gerou resultado (JSON ausente, vazio ou ilegível);
  - o linkinator falhou e não listou nenhum link (parou antes de terminar);
  - algum link INTERNO (127.0.0.1) está quebrado e não está em qa/links_excecoes.txt.

uso: python qa/portao_links.py qa/relatorios-links.json [resultado_do_passo: success|failure]"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from achados_qualidade import excecoes  # noqa: E402


def avaliar(caminho, resultado_do_passo="success"):
    """Devolve a lista de problemas (vazia = portão aberto)."""
    p = Path(caminho)
    if not p.exists() or not p.stat().st_size:
        return ["a checagem de links não gerou resultado (o linkinator parou antes de terminar)"]
    try:
        rel = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return ["o resultado da checagem de links não é um JSON válido"]
    links = rel.get("links") or []
    if not links:
        return ["a checagem de links não listou nenhum link"]
    if resultado_do_passo == "failure" and not any(l.get("state") == "BROKEN" for l in links):
        return ["o linkinator falhou, mas não listou nenhum link quebrado (parou no meio)"]
    regras = excecoes()
    internos = [l for l in links if l.get("state") == "BROKEN" and "127.0.0.1" in l.get("url", "") and not any(r.search(l["url"]) for r in regras)]
    return [f"link interno quebrado: {l.get('status')} {l['url']} (de {l.get('parent', '?')})" for l in internos]


if __name__ == "__main__":
    problemas = avaliar(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "success")
    for linha in problemas:
        print("::error::" + linha)
    if not problemas:
        print("Links internos: nenhum quebrado.")
    sys.exit(1 if problemas else 0)
