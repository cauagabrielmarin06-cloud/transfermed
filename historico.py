"""
Histórico de editais: auditoria do que cada edital guarda e previsão de abertura por faculdade.

Só lê a base (data/editais.json, data/faculdades.json, data/retratos.json); não muda edital nem site.
  python historico.py --auditar            campos que faltam em cada edital conferido
  python historico.py --prever             previsão da próxima abertura de cada faculdade, com a confiança
  python historico.py --prever --salvar    grava data/previsao_aberturas.json (o site ainda não usa)

A previsão usa só editais conferidos à mão (fonte_dados = manual) e nunca vira data certa: é uma janela
("costuma abrir entre 01/08 e 20/08"), com a base de ciclos que a sustenta.
"""
import argparse
import json
import re
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

PASTA = Path(__file__).resolve().parent
EDITAIS = PASTA / "data" / "editais.json"
FACULDADES = PASTA / "data" / "faculdades.json"
RETRATOS = PASTA / "data" / "retratos.json"
SAIDA = PASTA / "data" / "previsao_aberturas.json"

# o que um edital precisa guardar para o histórico servir (campo -> nome para o relatório)
CAMPOS = {"inscricao_inicio": "início das inscrições", "inscricao_fim": "fim das inscrições",
          "data_prova": "data da prova/análise", "vagas": "vagas", "taxa_inscricao": "taxa",
          "quem_pode": "requisitos", "documentos": "documentos", "criterio_selecao": "formato da seleção",
          "evidencias": "página do PDF de cada dado"}
CRITERIO_SEM_PROVA = ("analise curricular", "análise curricular", "ordem de", "histórico", "historico", "entrevista")


def chave_url(url):
    """Mesma chave do radar.py e do monitor.py (sem https, sem www, minúsculas)."""
    u = re.sub(r"^https?://(www\.)?", "", (url or "").strip())
    return re.sub(r"(%20|\s)+$", "", u).lower()


def ler(p, padrao):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else padrao


def faltando(ed):
    """Campos do histórico que o edital não tem. Prova não é exigida quando a seleção é só análise de documentos."""
    falta = [nome for campo, nome in CAMPOS.items() if not ed.get(campo)]
    sem_prova = any(t in (ed.get("criterio_selecao") or "").lower() for t in CRITERIO_SEM_PROVA)
    if sem_prova and "data da prova/análise" in falta:
        falta.remove("data da prova/análise")
    return falta


def auditar(E, retratos):
    conferidos = [e for e in E if e.get("fonte_dados") == "manual"]
    pdfs = retratos.get("pdfs", {})
    linhas, completos = [], 0
    for e in sorted(conferidos, key=lambda x: (x["faculdade_id"], x.get("semestre_ingresso") or "")):
        falta = faltando(e)
        chave = chave_url(e["url_edital"])
        if chave not in pdfs or not pdfs[chave].get("hash"):
            falta.append("retrato (hash) do PDF")
        if not falta:
            completos += 1
        else:
            linhas.append(f"- {e['faculdade_id']} {e.get('semestre_ingresso') or '?'} ({e.get('modalidade')}): {', '.join(falta)}")
    return completos, len(conferidos), linhas


def ciclo(ed):
    """(tipo do ingresso, ano do ingresso, data de referência do ciclo) ou None."""
    s = (ed.get("semestre_ingresso") or "").strip()
    if len(s) >= 6 and s[:4].isdigit() and s[4] == "." and s[5] in "12":
        ano, tipo = int(s[:4]), s[5]
        return tipo, ano, date(ano, 1 if tipo == "1" else 7, 1)
    if s[:4].isdigit() and "anual" in s:
        return "anual", int(s[:4]), date(int(s[:4]), 1, 1)
    return None


def prever(E, hoje):
    """Para cada faculdade e tipo de ingresso: dias da abertura em relação ao começo do semestre de ingresso,
    um valor por ciclo (a primeira abertura do ciclo, quando há várias chamadas)."""
    por = {}
    for e in E:
        if e.get("fonte_dados") != "manual" or not e.get("inscricao_inicio"):
            continue
        c = ciclo(e)
        if not c:
            continue
        tipo, ano, ref = c
        dias = (date.fromisoformat(e["inscricao_inicio"]) - ref).days
        ciclos = por.setdefault((e["faculdade_id"], tipo), {})
        ciclos[ano] = min(dias, ciclos.get(ano, dias))
    previsoes = {}
    for (fid, tipo), ciclos in por.items():
        valores = list(ciclos.values())
        n, espalhamento = len(valores), max(valores) - min(valores)
        if n >= 3 and espalhamento <= 30:
            confianca = "alta"
        elif n >= 2 and espalhamento <= 45:
            confianca = "média"
        else:
            confianca = "baixa"
        meio, folga = statistics.median(valores), max(10, espalhamento / 2 + 5)
        ano = max(ciclos) + 1
        while True:  # próximo ciclo que ainda não abriu
            ref = date(ano, 1 if tipo in ("1", "anual") else 7, 1)
            ini, fim = ref + timedelta(days=meio - folga), ref + timedelta(days=meio + folga)
            if fim >= hoje:
                break
            ano += 1
        rotulo = f"{ano}.{tipo}" if tipo != "anual" else f"{ano} (anual)"
        previsoes.setdefault(fid, []).append({
            "ingresso": rotulo, "janela_inicio": ini.isoformat(), "janela_fim": fim.isoformat(), "confianca": confianca,
            "base": sorted(f"{a}.{tipo}" if tipo != "anual" else str(a) for a in ciclos),
            "texto": f"Costuma abrir entre {ini:%d/%m} e {fim:%d/%m} (ingresso {rotulo}); confiança {confianca}, "
                     f"com base em {n} ciclo{'s' if n > 1 else ''}."})
    for lista in previsoes.values():
        lista.sort(key=lambda p: p["janela_inicio"])
    return previsoes


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--auditar", action="store_true")
    ap.add_argument("--prever", action="store_true")
    ap.add_argument("--salvar", action="store_true")
    args = ap.parse_args(argv)
    E = ler(EDITAIS, [])
    if args.auditar or not args.prever:
        completos, total, linhas = auditar(E, ler(RETRATOS, {}))
        print(f"Editais conferidos com histórico completo: {completos} de {total}\n" + "\n".join(linhas))
    if args.prever:
        prev = prever(E, date.today())
        nomes = {f["id"]: f["sigla"] for f in ler(FACULDADES, [])}
        conta = {}
        for fid, lista in sorted(prev.items()):
            for p in lista:
                conta[p["confianca"]] = conta.get(p["confianca"], 0) + 1
                print(f"{nomes.get(fid, fid)}: {p['texto']}")
        print(f"\nFaculdades com previsão: {len(prev)} | por confiança: {conta}")
        if args.salvar:
            SAIDA.write_text(json.dumps({"gerado_em": date.today().isoformat(), "faculdades": prev},
                                        ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"Gravado em {SAIDA.relative_to(PASTA)}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
