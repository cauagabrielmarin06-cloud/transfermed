"""Reconferência por sorteio (passo 4 do MELHORIA.md): sorteia editais publicados e confere, na página do PDF
indicada em `evidencias`, se as datas, a taxa e as vagas estão escritas lá. Campos de texto (critério, quem pode)
ficam para leitura humana: o script só diz onde olhar.

uso: python qa/reconferir.py [--n 3] [--faculdade ID ...] [--semente 42]
Sai com código 1 se algum dado numérico não for encontrado na página citada (então: abrir o PDF e conferir).
"""
import argparse
import io
import json
import random
import re
import sys
from pathlib import Path

import pypdf
import requests

RAIZ = Path(__file__).resolve().parent.parent
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130 Safari/537.36"}
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]


def data_na_pagina(iso, texto):
    """Aceita 24/09/2026, 24/09/26, 24/09 (ano só no fim do período: "24/09 à 18/11/2026") e "24 de setembro"."""
    a, m, d = iso[:4], iso[5:7], iso[8:10]
    if f"{d}/{m}/{a}" in texto or f"{d}/{m}/{a[2:]}" in texto or re.search(rf"\b{d}/{m}\b(?!/\d)", texto):
        return True
    return re.search(rf"\b{int(d)}º?\s*de\s*{MESES[int(m) - 1]}", texto, re.I) is not None


def conferir(e, paginas):
    """[(campo, valor, página, 'confere'|'não achei'|'ler')] para cada campo com evidência."""
    linhas = []
    for campo, p in (e.get("evidencias") or {}).items():
        v, t = e.get(campo), paginas.get(p, "") if isinstance(p, int) else ""
        if v in (None, "", []):
            continue
        if campo in ("inscricao_inicio", "inscricao_fim", "data_prova"):
            ok = data_na_pagina(v, t)
        elif campo == "taxa_inscricao":
            ok = f"{v:.2f}".replace(".", ",") in t or re.search(rf"\b{int(v)}\b", t) is not None
        elif campo == "vagas":
            ok = all(re.search(rf"\b0?{x['vagas']}\b", t) for x in v if isinstance(x, dict) and x.get("vagas") is not None)
        else:
            linhas.append((campo, v, p, "ler"))
            continue
        linhas.append((campo, v, p, "confere" if ok else "não achei"))
    return linhas


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--faculdade", nargs="*", default=[])
    ap.add_argument("--semente", type=int)
    args = ap.parse_args(argv)
    editais = [e for e in json.loads((RAIZ / "data" / "editais.json").read_text(encoding="utf-8"))
               if e.get("fonte_dados") == "manual" and e.get("evidencias") and not e.get("fluxo_continuo")]
    escolhidos = [e for e in editais if e["faculdade_id"] in args.faculdade]
    resto = [e for e in editais if e not in escolhidos]
    random.Random(args.semente).shuffle(resto)
    escolhidos += resto[:max(0, args.n - len(escolhidos))]
    falhas = 0
    for e in escolhidos:
        print(f"\n=== {e['faculdade_id']} · {e.get('semestre_ingresso')} · {e['modalidade']}\n    {e['url_edital']}")
        try:
            pdf = pypdf.PdfReader(io.BytesIO(requests.get(e["url_edital"], headers=H, timeout=60).content))
            paginas = {i + 1: re.sub(r"\s+", " ", p.extract_text() or "") for i, p in enumerate(pdf.pages)}
        except Exception as ex:  # noqa: BLE001
            print(f"    não abriu ({type(ex).__name__}): conferir no navegador")
            falhas += 1
            continue
        for campo, v, p, res in conferir(e, paginas):
            mostra = [(x.get("semestre"), x.get("vagas")) for x in v if isinstance(x, dict)] if campo == "vagas" else v
            if isinstance(mostra, list) and mostra and isinstance(mostra[0], str):
                mostra = f"{len(mostra)} itens"
            print(f"    {campo:22} p.{p}: {str(mostra)[:70]:72} {res}")
            falhas += res == "não achei"
    print(f"\n{len(escolhidos)} edital(is) reconferido(s); {falhas} dado(s) não encontrado(s) na página citada.")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
