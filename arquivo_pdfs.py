"""Arquivo permanente dos PDFs dos editais e versões das retificações (ROADMAP, item 6).

Por que existe: o ativo do Transfermed é a base verificada. Se a faculdade tirar o PDF do ar ou trocar o arquivo no
mesmo endereço, a fonte de cada dado some. Este módulo guarda, para sempre:

1. `data/arquivo_pdfs.json`: para cada documento (edital, anexo, retificação) o hash SHA-256, o tamanho, quando foi
   visto pela primeira vez e as versões seguintes (o hash antigo nunca é apagado), mais o endereço da cópia pública
   no Internet Archive (Save Page Now). Os PDFs em si não vão para o Git (pesariam o repositório).
2. `versoes` dentro de cada edital de `data/editais.json`: quando um dado conferido muda (retificação ou nova
   leitura), o valor antigo fica registrado ao lado do novo, com a data.

Uso:
    python arquivo_pdfs.py --resumo                    # quantos editais têm hash e cópia
    python arquivo_pdfs.py                             # guarda o hash do que falta (em lotes)
    ARQUIVAR_NO_ARCHIVE=1 python arquivo_pdfs.py       # e pede a cópia pública no Internet Archive (opt-in)
    python arquivo_pdfs.py --versoes --base HEAD       # compara editais.json com o do commit e grava as mudanças
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import tempo
from datetime import date
from pathlib import Path

import requests

import funcoes
import gerar_site
import radar

PASTA = Path(__file__).resolve().parent
ARQUIVO = PASTA / "data" / "arquivo_pdfs.json"
RETRATOS = PASTA / "data" / "retratos.json"
MAX_DOWNLOADS = 60      # por execução: o que sobrar fica para o dia seguinte
MAX_ARQUIVAR = int(os.environ.get("ARQUIVAR_LOTE", "12"))  # pedidos ao Internet Archive por execução (o serviço limita o ritmo)
MAX_TENTATIVAS = 5      # depois disso a cópia pública fica como "sem cópia" e aparece no resumo
PAUSA_ARCHIVE = 6       # segundos entre pedidos

# Campos cujo valor, ao mudar, vira uma versão (o resto, como datas de conferência, não conta)
CAMPOS_VERSIONADOS = (
    "numero_edital", "url_edital", "modalidade", "semestre_ingresso", "inscricao_inicio", "inscricao_fim",
    "data_prova", "data_resultado", "matricula_texto", "resultado_texto", "taxa_inscricao", "vagas", "vagas_texto",
    "criterio_selecao", "quem_pode", "aceita_curso_exterior", "exclui_quem_ja_transferiu", "documentos",
    "outras_restricoes", "retificacoes", "anexos",
)


# ---------------------------------------------------------------- versões das retificações

def diferencas(antigo, novo):
    """{campo: [antes, depois]} dos campos versionados que mudaram. Campo que só passou a existir (ou sumiu) conta."""
    mudou = {}
    for campo in CAMPOS_VERSIONADOS:
        a, b = antigo.get(campo), novo.get(campo)
        if a in (None, "", []) and b in (None, "", []):
            continue
        if a != b:
            mudou[campo] = [a, b]
    return mudou


def registrar_versoes(antigos, novos, hoje, motivo="reconferência"):
    """Grava em `versoes` de cada edital de `novos` o que mudou em relação a `antigos` (listas de editais).
    Não repete uma versão idêntica já registrada. Devolve quantos editais ganharam versão."""
    por_id = {e["id"]: e for e in antigos}
    ganharam = 0
    for ed in novos:
        ant = por_id.get(ed["id"])
        if ant is None:
            continue
        mudou = diferencas(ant, ed)
        if not mudou:
            continue
        versoes = ed.setdefault("versoes", list(ant.get("versoes") or []))
        if any(v.get("mudou") == mudou for v in versoes):
            continue
        versoes.append({"em": hoje, "motivo": motivo, "mudou": mudou})
        ganharam += 1
    return ganharam


def editais_do_commit(ref):
    saida = subprocess.run(["git", "show", f"{ref}:data/editais.json"], cwd=PASTA, capture_output=True, check=True)
    return json.loads(saida.stdout.decode("utf-8"))


# ---------------------------------------------------------------- arquivo dos PDFs

def documentos_da_base(editais):
    """{url: [ids dos editais]} de todo documento que sustenta um edital publicado (inclusive os encerrados)."""
    docs = {}
    for e in editais:
        if not gerar_site.publicavel(e):
            continue
        urls = [e["url_edital"], *(e.get("anexos") or []), *(e.get("retificacoes") or [])]
        for url in dict.fromkeys(u for u in urls if u):
            docs.setdefault(url, []).append(e["id"])
    return docs


def registrar_hash(entrada, conteudo, hoje):
    """Atualiza a entrada com o conteúdo baixado. O hash antigo vai para `versoes`, nunca é apagado."""
    h = hashlib.sha256(conteudo).hexdigest()
    if entrada.get("sha256") and entrada["sha256"] != h:
        entrada.setdefault("versoes", []).append({"em": hoje, "sha256": entrada["sha256"], "bytes": entrada.get("bytes")})
        entrada["copia_publica"] = None          # o arquivo mudou: a cópia antiga não vale mais
        entrada["tentativas_arquivo"] = 0
    entrada.update({"sha256": h, "bytes": len(conteudo), "ultimo_visto": hoje})
    entrada.setdefault("primeiro_visto", hoje)
    entrada.pop("erro", None)
    return h


def pedir_copia_publica(url):
    """Internet Archive (Save Page Now). Devolve o endereço da cópia ou None. Falha de rede nunca derruba a rotina."""
    try:
        r = requests.get("https://web.archive.org/save/" + url, headers=radar.HEADERS, timeout=90, allow_redirects=True)
    except requests.RequestException:
        return None
    local = r.headers.get("Content-Location") or ""
    if r.status_code < 400 and local.startswith("/web/"):
        return "https://web.archive.org" + local
    if r.status_code < 400 and "web.archive.org/web/" in r.url:
        return r.url
    return None


def atualizar(editais, hoje, arquivo=None, baixar=radar.baixar_pdf, arquivar=None, pausa=PAUSA_ARCHIVE, retratos=None):
    """Baixa e guarda o hash dos documentos que ainda não têm e, se `arquivar` for dado, pede cópia pública dos que não
    têm. O pedido ao Internet Archive é opt-in (variável ARQUIVAR_NO_ARCHIVE=1 no GitHub): envia endereços a um serviço
    público, então só roda com a decisão do dono. Devolve o dict atualizado e um resumo do que fez."""
    arquivo = arquivo if arquivo is not None else {"documentos": {}}
    docs = arquivo.setdefault("documentos", {})
    retratos_pdfs = (retratos or {}).get("pdfs", {})
    feito = {"baixados": 0, "falhas": 0, "copias": 0, "versoes_novas": 0}
    for url, ids in documentos_da_base(editais).items():
        chave = radar.chave_url(url)
        entrada = docs.setdefault(chave, {"url": url})
        entrada["url"], entrada["editais"] = url, sorted(ids)
        vigiado = retratos_pdfs.get(chave, {}).get("hash")
        if vigiado and entrada.get("sha256") and vigiado != entrada["sha256"]:
            # o monitor já baixou hoje: usa o hash dele, sem baixar de novo
            entrada.setdefault("versoes", []).append({"em": hoje, "sha256": entrada["sha256"], "bytes": entrada.get("bytes")})
            entrada.update({"sha256": vigiado, "ultimo_visto": hoje, "copia_publica": None, "tentativas_arquivo": 0})
            feito["versoes_novas"] += 1
        elif vigiado and not entrada.get("sha256"):
            entrada.update({"sha256": vigiado, "ultimo_visto": hoje, "primeiro_visto": hoje})
        if entrada.get("sha256") or entrada.get("nao_e_pdf"):
            continue
        if feito["baixados"] + feito["falhas"] >= MAX_DOWNLOADS:
            continue
        try:
            conteudo = baixar(url)
        except Exception as ex:  # noqa: BLE001 - qualquer falha de rede conta como "não abriu"
            conteudo, erro = None, f"{type(ex).__name__}: {str(ex)[:160]}"
        else:
            erro = None if conteudo is not None else "o endereço não devolve um PDF"
        if conteudo is None:
            entrada.update({"erro": erro, "falhas_seguidas": entrada.get("falhas_seguidas", 0) + 1, "ultimo_erro_em": hoje})
            feito["falhas"] += 1
            if erro == "o endereço não devolve um PDF":
                entrada["nao_e_pdf"] = True      # página da faculdade (fluxo contínuo): quem a vigia é o retrato de páginas
            continue
        registrar_hash(entrada, conteudo, hoje)
        feito["baixados"] += 1
    pedidos = 0
    for entrada in (docs.values() if arquivar else ()):
        if pedidos >= MAX_ARQUIVAR:
            break
        if not entrada.get("sha256") or entrada.get("copia_publica") or entrada.get("tentativas_arquivo", 0) >= MAX_TENTATIVAS:
            continue
        entrada["tentativas_arquivo"] = entrada.get("tentativas_arquivo", 0) + 1
        pedidos += 1
        copia = arquivar(entrada["url"])
        if copia:
            entrada["copia_publica"], entrada["arquivado_em"] = copia, hoje
            feito["copias"] += 1
        if pausa:
            time.sleep(pausa)
    arquivo["atualizado_em"] = hoje
    return arquivo, feito


def resumo(editais, arquivo):
    """Cobertura do arquivo: por edital publicado, se o PDF principal tem hash e cópia pública."""
    docs = (arquivo or {}).get("documentos", {})
    total = com_hash = com_copia = 0
    sem = []
    for e in editais:
        if not gerar_site.publicavel(e):
            continue
        d = docs.get(radar.chave_url(e["url_edital"]), {})
        if d.get("nao_e_pdf"):
            continue            # página da faculdade, não PDF
        total += 1
        com_hash += bool(d.get("sha256"))
        com_copia += bool(d.get("copia_publica"))
        if not d.get("sha256") or not d.get("copia_publica"):
            sem.append(e["id"])
    return {"editais_com_pdf": total, "com_hash": com_hash, "com_copia_publica": com_copia, "faltando": sem}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--resumo", action="store_true")
    ap.add_argument("--versoes", action="store_true", help="grava em `versoes` o que mudou desde --base")
    ap.add_argument("--base", default="HEAD")
    ap.add_argument("--hoje", default=tempo.hoje().isoformat())
    ap.add_argument("--com-archive", action="store_true", help="também pede cópia pública ao Internet Archive (só com a decisão do dono)")
    args = ap.parse_args(argv)
    editais = radar.ler_json(radar.EDITAIS, [])
    arquivo = radar.ler_json(ARQUIVO, {"documentos": {}})
    if args.resumo:
        r = resumo(editais, arquivo)
        print(f"Editais com PDF: {r['editais_com_pdf']} · com hash: {r['com_hash']} · com cópia pública: {r['com_copia_publica']}")
        return 0
    if args.versoes:
        n = registrar_versoes(editais_do_commit(args.base), editais, args.hoje)
        if n:
            radar.salvar_json(radar.EDITAIS, editais)
        print(f"Editais com versão nova registrada: {n}")
        return 0
    retratos = radar.ler_json(RETRATOS, {})
    arquivo, feito = atualizar(editais, args.hoje, arquivo, retratos=retratos,
                               arquivar=pedir_copia_publica if (args.com_archive or funcoes.ligada("ARQUIVAR_NO_ARCHIVE")) else None)
    radar.salvar_json(ARQUIVO, arquivo)
    r = resumo(editais, arquivo)
    print(f"Baixados: {feito['baixados']} · falhas: {feito['falhas']} · cópias novas: {feito['copias']} · versões novas: {feito['versoes_novas']}")
    print(f"Editais com PDF: {r['editais_com_pdf']} · com hash: {r['com_hash']} · com cópia pública: {r['com_copia_publica']}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
