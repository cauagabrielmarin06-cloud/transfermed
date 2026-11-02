"""Auditoria de precisão independente (ROADMAP 7). Mensal.

1. `python auditoria.py amostrar AAAA-MM`: sorteia (semente = o mês) editais conferidos e vigentes e grava em
   privado/auditoria/AAAA-MM/pedido_cego.json SÓ o link do edital e os campos a ler (nenhum valor da base): é o que
   o subagente "cego" recebe. Grava também privado/auditoria/AAAA-MM/gabarito.json (os valores da base, que o subagente
   nunca vê) e `para_o_dono.md` com 10 campos para o dono conferir à mão no PDF.
2. O subagente lê os PDFs e grava `respostas_cego.json` ({edital_id: {campo: valor}}).
3. `python auditoria.py comparar AAAA-MM`: compara com o gabarito, grava `resultado.json` e imprime a taxa de acerto.

Nada disso vai para o Git (privado/). A taxa entra no relatório semanal do mês seguinte.
"""
import json
import random
import re
import sys
from datetime import date
from pathlib import Path

import gerar_site as g

PASTA = Path(__file__).resolve().parent
RAIZ_AUDITORIA = PASTA / "privado" / "auditoria"
CAMPOS = ["inscricao_fim", "inscricao_inicio", "data_prova", "taxa_inscricao", "vagas_total", "aceita_curso_exterior", "numero_edital"]
PERGUNTAS = {
    "inscricao_fim": "Último dia de inscrição (AAAA-MM-DD), ou 'nao_consta'",
    "inscricao_inicio": "Primeiro dia de inscrição (AAAA-MM-DD), ou 'nao_consta'",
    "data_prova": "Data da prova (AAAA-MM-DD), ou 'nao_consta' (sem prova: 'sem_prova')",
    "taxa_inscricao": "Taxa de inscrição em reais (número, ex. 150.00), ou 'nao_consta' (isenta: 0)",
    "vagas_total": "Total de vagas ofertadas para Medicina neste edital (número inteiro, somando os períodos), ou 'nao_consta'",
    "aceita_curso_exterior": "O edital aceita quem cursou no exterior? 'sim', 'nao' ou 'nao_consta'",
    "numero_edital": "Número do edital como escrito (ex. '034/2026'), ou 'nao_consta'",
}


def valor_da_base(ed, campo):
    if campo == "vagas_total":
        t = g.total_vagas(ed)
        return t if t else None
    v = ed.get(campo)
    if campo == "aceita_curso_exterior":
        return {True: "sim", False: "nao", None: None}.get(v)
    return v


def normalizar(campo, v):
    """Forma comparável: datas AAAA-MM-DD, números como float, texto sem espaços e sem 'edital nº'."""
    if v is None:
        return "nao_consta"
    if isinstance(v, str) and v.strip().lower() in ("nao_consta", "não consta", "nao consta", ""):
        return "nao_consta"
    if campo == "taxa_inscricao":
        try:
            return round(float(str(v).replace("R$", "").replace(".", "").replace(",", ".")) if isinstance(v, str) and "," in v else float(v), 2)
        except (TypeError, ValueError):
            return str(v)
    if campo == "vagas_total":
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return str(v)
    if campo == "numero_edital":
        m = re.search(r"\d+\s*/\s*\d{4}|\d+", str(v))
        return re.sub(r"\s", "", m.group(0)).lstrip("0") if m else str(v).strip().lower()
    return str(v).strip().lower()


def amostrar(mes, n_editais=10, n_dono=10):
    hoje = f"{mes}-15"
    editais = json.loads((PASTA / "data" / "editais.json").read_text(encoding="utf-8"))
    vigentes = [e for e in editais if g.publicavel(e) and not e.get("fluxo_continuo") and e["url_edital"].lower().split("?")[0].endswith(".pdf")
                and not e.get("conferir_campos") and e.get("inscricao_fim")]
    rnd = random.Random(mes)
    sorteados = rnd.sample(sorted(vigentes, key=lambda e: e["id"]), min(n_editais, len(vigentes)))
    pasta = RAIZ_AUDITORIA / mes
    pasta.mkdir(parents=True, exist_ok=True)
    pedido = [{"edital_id": e["id"], "pdf": e["url_edital"], "campos": {c: PERGUNTAS[c] for c in CAMPOS}} for e in sorteados]
    gabarito = {e["id"]: {c: valor_da_base(e, c) for c in CAMPOS} for e in sorteados}
    (pasta / "pedido_cego.json").write_text(json.dumps(pedido, ensure_ascii=False, indent=1), encoding="utf-8")
    (pasta / "gabarito.json").write_text(json.dumps(gabarito, ensure_ascii=False, indent=1), encoding="utf-8")
    # 10 campos para o dono (outros editais, para não repetir a amostra cega): só os que têm página registrada
    outros = [e for e in vigentes if e["id"] not in gabarito and (e.get("evidencias") or {}).get("inscricao_fim")]
    escolhidos = rnd.sample(sorted(outros, key=lambda e: e["id"]), min(n_dono, len(outros)))
    linhas = [f"# Conferência do dono ({mes}): 10 campos\n", "Abra o PDF, vá à página indicada e diga se o valor do site está igual ao edital (sim/não).\n",
              "| edital | campo | valor no site | página | PDF |", "|---|---|---|---|---|"]
    for e in escolhidos:
        campo = rnd.choice(["inscricao_fim", "taxa_inscricao", "data_prova"])
        v = valor_da_base(e, campo)
        if v is None:
            campo, v = "inscricao_fim", e["inscricao_fim"]
        pag = (e.get("evidencias") or {}).get(campo) or (e.get("evidencias") or {}).get("inscricao_fim")
        linhas.append(f"| {e['id']} | {campo} | {v} | {pag} | {e['url_edital']} |")
    (pasta / "para_o_dono.md").write_text("\n".join(linhas), encoding="utf-8")
    return pasta, len(sorteados)


def comparar(mes):
    pasta = RAIZ_AUDITORIA / mes
    gabarito = json.loads((pasta / "gabarito.json").read_text(encoding="utf-8"))
    respostas = json.loads((pasta / "respostas_cego.json").read_text(encoding="utf-8"))
    total = acertos = 0
    divergencias = []
    for eid, campos in gabarito.items():
        for campo, esperado in campos.items():
            if eid not in respostas or campo not in respostas[eid]:
                continue
            total += 1
            a, b = normalizar(campo, esperado), normalizar(campo, respostas[eid][campo])
            if a == b or (campo == "data_prova" and a == "nao_consta" and b == "sem_prova"):
                acertos += 1
            else:
                divergencias.append({"edital_id": eid, "campo": campo, "base": a, "leitor_cego": b})
    taxa = round(100 * acertos / total, 1) if total else None
    resultado = {"mes": mes, "campos_comparados": total, "acertos": acertos, "taxa_acerto_pct": taxa, "divergencias": divergencias}
    (pasta / "resultado.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    return resultado


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    acao = sys.argv[1] if len(sys.argv) > 1 else "amostrar"
    mes = sys.argv[2] if len(sys.argv) > 2 else date.today().strftime("%Y-%m")
    if acao == "amostrar":
        print(amostrar(mes))
    else:
        r = comparar(mes)
        print(f"{r['acertos']} de {r['campos_comparados']} campos iguais: {r['taxa_acerto_pct']}%")
        for d in r["divergencias"]:
            print("  divergência:", d)
