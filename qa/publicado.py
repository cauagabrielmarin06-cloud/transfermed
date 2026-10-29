"""Confere no site publicado (não na cópia local) que o sitemap.xml e o robots.txt respondem 200, com o tipo certo e o
conteúdo certo, inclusive pelo domínio sem "www" (que redireciona), e que nenhuma página do sitemap tem endereço
http:// na canonical, no og:url, no og:image ou no JSON-LD. Roda na checagem diária; as falhas viram issue.
uso: python qa/publicado.py  → qa/relatorios/publicado.json (lista de falhas; vazia = tudo certo)
"""
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from gerar_site import SITE_URL  # noqa: E402

NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}  # identificador do formato: a norma exige "http://"


def enderecos_inseguros(html):
    """Endereços http:// na canonical, no og:url, no og:image e no JSON-LD de uma página (lista vazia = tudo https)."""
    achados = re.findall(r'<link rel="canonical" href="(http://[^"]*)"', html)
    achados += re.findall(r'<meta property="og:(?:url|image)" content="(http://[^"]*)"', html)
    for bloco in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        achados += re.findall(r'"(http://[^"]*)"', bloco)
    return achados
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
    inseguros = [u for u in locs if not u.startswith("https://")]
    inseguros += [u for u in re.findall(rb"http://[^\s\"<]+", corpo) if u != NS["s"].encode()]
    inseguros = list(dict.fromkeys(u.decode() if isinstance(u, bytes) else u for u in inseguros))
    if inseguros:
        falhas.append(f"sitemap.xml com {len(inseguros)} endereço(s) http://, ex.: {inseguros[0]!r}")
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
    # todas as páginas do sitemap, como o Google as recebe
    sessao = requests.Session()
    for loc in re.findall(r"<loc>([^<]+)</loc>", local):
        try:
            r = sessao.get(loc, timeout=30)
        except requests.RequestException as erro:
            falhas.append(f"{loc}: sem resposta ({type(erro).__name__})")
            continue
        if r.status_code != 200:
            falhas.append(f"{loc}: respondeu {r.status_code}")
            continue
        ruins = enderecos_inseguros(r.text)
        if ruins:
            falhas.append(f"{loc}: {len(ruins)} endereço(s) http:// na canonical, no og ou no JSON-LD, ex.: {ruins[0]}")
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(falhas, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n".join(falhas) or "sitemap.xml e robots.txt publicados: ok")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
