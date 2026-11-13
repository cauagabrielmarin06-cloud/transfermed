"""Boletim semanal para grupos de estudantes (texto pronto para colar no WhatsApp). Gerado da base, sem inventar nada.
Quem posta é o dono, à mão: o programa só gera o texto em privado/boletim/AAAA-MM-DD.txt (nada é enviado nem publicado).
O link leva ?origem=grupo, que o relatório semanal conta como canal "grupos de estudantes".
uso: python boletim.py [--hoje AAAA-MM-DD]"""
import argparse
import json
import sys
import tempo
from datetime import date, timedelta
from pathlib import Path

import gerar_site as g
import instagram

PASTA = Path(__file__).resolve().parent
SAIDA = PASTA / "privado" / "boletim"
LINK = "https://www.transfermed.com.br/diagnostico/?origem=grupo"
MAX_LINHAS = 6


def montar(editais, facs, hoje):
    """Texto do boletim. Só edital conferido, aberto, com prazo firme; ordem por prazo (sem ranking)."""
    ab = instagram.abertos(editais, facs, hoje)
    h = date.fromisoformat(hoje)
    semana = (h + timedelta(days=7)).isoformat()
    encerram = [e for e in ab if e["inscricao_fim"] <= semana]
    recentes = [e for e in ab if (e.get("conferido_em") or "") >= (h - timedelta(days=7)).isoformat()
                and e["id"] not in {x["id"] for x in encerram}]
    exterior = [e for e in ab if e.get("aceita_curso_exterior") is True]

    def linha(e):
        f = facs[e["faculdade_id"]]
        vagas = g.total_vagas(e) if not {"vagas", "edital"} & set(g.campos_conferir(e)) else None
        mod = " · portador de diploma" if e.get("modalidade") == "portador_diploma" else ""
        return f"• {f['sigla']} ({f['cidade']}/{f['uf']}){mod}: até {g.fmt(e['inscricao_fim'])[:5]}" + (f" · {vagas} vagas" if vagas else "")

    L = [f"*Transferência de Medicina: boletim de {g.fmt(hoje)[:5]}*", "",
         f"Hoje há {len(ab)} editais abertos no radar do Transfermed (dados conferidos no PDF oficial)."]
    if encerram:
        L += ["", "*Encerram nos próximos 7 dias:*"] + [linha(e) for e in encerram[:MAX_LINHAS]]
        if len(encerram) > MAX_LINHAS:
            L.append(f"…e mais {len(encerram) - MAX_LINHAS} no site.")
    if recentes:
        L += ["", "*Editais conferidos esta semana:*"] + [linha(e) for e in recentes[:MAX_LINHAS]]
    if exterior:
        L += ["", f"Quem estuda fora do Brasil: {len(exterior)} dos editais abertos dizem aceitar aluno de faculdade estrangeira."]
    L += ["", "Veja em quais você pode se inscrever (1 minuto, grátis, sem cadastro):", LINK, "",
          "Confira sempre o edital oficial antes de pagar a taxa."]
    return "\n".join(L)


def gerar(hoje):
    editais = json.loads((PASTA / "data" / "editais.json").read_text(encoding="utf-8"))
    facs = {f["id"]: f for f in json.loads((PASTA / "data" / "faculdades.json").read_text(encoding="utf-8"))}
    texto = montar(editais, facs, hoje)
    SAIDA.mkdir(parents=True, exist_ok=True)
    destino = SAIDA / f"{hoje}.txt"
    destino.write_text(texto, encoding="utf-8")
    return destino, texto


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--hoje", default=tempo.hoje().isoformat())
    d, t = gerar(ap.parse_args().hoje)
    print(t)
    print(f"\n[gravado em {d}]")
