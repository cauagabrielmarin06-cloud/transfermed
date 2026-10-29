"""Confere no site publicado (não na cópia local) que o sitemap.xml e o robots.txt respondem 200, com o tipo certo e o
conteúdo certo, inclusive pelo domínio sem "www" (que redireciona). Roda na checagem diária; as falhas viram issue.
uso: python qa/publicado.py  → qa/relatorios/publicado.json (lista de falhas; vazia = tudo certo)
"""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from gerar_site import SITE_URL  # noqa: E402

NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
SAIDA = RAIZ / "qa" / "relatorios" / "publicado.json"


def conferir_sitemap(status, tipo, corpo, minimo):
    falhas = []
    if status != 200:
        return [f"sitemap.xml respondeu {status}"]
    if "xml" not in (tipo or ""):
        falhas.append(f"sitemap.xml com Content-Type {tipo!r} (esperado XML)")
    try:
        locs = [u.find("s:loc", NS).text for u in ET.fromstring(corpo).findall("s:url", NS)]
    except ET.ParseError as erro:
        return falhas + [f"sitemap.xml não é XML válido: {erro}"]
    if len(locs) < minimo:
        falhas.append(f"sitemap.xml com {len(locs)} endereços (o publicado no repositório tem {minimo})")
    fora = [u for u in locs if not u.startswith(SITE_URL + "/")]
    if fora:
        falhas.append(f"sitemap.xml com endereço fora de {SITE_URL}: {fora[0]}")
    return falhas


def conferir_robots(status, tipo, corpo):
    if status != 200:
        return [f"robots.txt respondeu {status}"]
    falhas = []
    if not (tipo or "").startswith("text/plain"):
        falhas.append(f"robots.txt com Content-Type {tipo!r} (esperado text/plain)")
    if f"Sitemap: {SITE_URL}/sitemap.xml" not in corpo:
        falhas.append("robots.txt sem a linha Sitemap apontando para o sitemap publicado")
    return falhas


def main():
    local = (RAIZ / "docs" / "sitemap.xml").read_text(encoding="utf-8")
    minimo = local.count("<url>")
    falhas = []
    sem_www = SITE_URL.replace("://www.", "://")
    for base in dict.fromkeys([SITE_URL, sem_www]):
        try:
            r = requests.get(f"{base}/sitemap.xml", timeout=30)
            falhas += [f"{base}: {f}" for f in conferir_sitemap(r.status_code, r.headers.get("content-type"), r.content, minimo)]
            r = requests.get(f"{base}/robots.txt", timeout=30)
            falhas += [f"{base}: {f}" for f in conferir_robots(r.status_code, r.headers.get("content-type"), r.text)]
        except requests.RequestException as erro:
            falhas.append(f"{base}: sem resposta ({type(erro).__name__})")
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(falhas, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n".join(falhas) or "sitemap.xml e robots.txt publicados: ok")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
