"""
Relatório semanal do sócio (Parte F): os números da semana que passou (segunda a domingo), comparados com a semana
anterior, e a curva das últimas 8 semanas. Chega por e-mail só para o dono (o repositório é público: nada destes
números vai para issue, registro do Actions ou arquivo no Git).

O que entra:
  - visitas, diagnósticos iniciados e concluídos, inscrições no alerta (eventos sem cookies da tabela `eventos`)
  - inscritos novos, confirmados na semana e total ativo (só datas e situação dos assinantes, nunca o e-mail)
  - editais novos conferidos (ciclo atual e histórico), retificações, achados do robô (comparação da base no Git)
  - prazos da semana que começa, editais "conferir" ainda em aberto, issues abertas da checagem diária
  - estrutura do banco: funções e tabelas do supabase/schema.sql que ainda não existem no Supabase

  python relatorio.py              simulação: mostra o relatório no terminal (útil no computador do dono)
  python relatorio.py --enviar     envia para CONTATO_DESTINO (workflow "Relatório semanal", segunda às 8h)

Configuração: SUPABASE_URL, SUPABASE_SERVICE_KEY, BREVO_API_KEY, REMETENTE_EMAIL, CONTATO_DESTINO; GITHUB_TOKEN e
GITHUB_REPOSITORY (opcionais) para contar as issues. Sem Supabase, os números do site saem como "sem dados".
"""
import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

import requests

import radar

PASTA = Path(__file__).resolve().parent
BRASILIA = timezone(timedelta(hours=-3))  # sem horário de verão desde 2019
SEMANAS_CURVA = 8
# linhas do relatório: (evento medido, rótulo)
FUNIL = [("visita", "Visitas (páginas abertas)"), ("diagnostico_iniciado", "Diagnósticos iniciados"),
         ("diagnostico_concluido", "Diagnósticos concluídos"), ("ver_edital", "Editais abertos no site"),
         ("alerta_inscrito", "Pedidos de alerta"), ("isca", "Checklist em PDF baixado"),
         ("compartilhar_whatsapp", "Compartilhamentos no WhatsApp"),
         ("radar_ponto", "Toques em faculdades no radar"), ("porta_brasil", "Escolheram \"Estudo no Brasil\""),
         ("porta_exterior", "Escolheram \"Estudo fora do Brasil\"")]


# ---------------------------------------------------------------- períodos

def semana_passada(hoje):
    """(segunda, domingo) da última semana completa antes de `hoje`."""
    domingo = hoje - timedelta(days=hoje.weekday() + 1)
    return domingo - timedelta(days=6), domingo


def dia_local(quando):
    """Timestamp do Supabase (ISO com fuso) -> data em Brasília."""
    if not quando:
        return None
    return datetime.fromisoformat(quando.replace("Z", "+00:00")).astimezone(BRASILIA).date()


def variacao(atual, anterior):
    if atual is None or anterior is None:
        return ""
    if anterior == 0:
        return "novo" if atual else "="
    p = round((atual - anterior) * 100 / anterior)
    return "=" if p == 0 else f"{p:+d}%"


# ---------------------------------------------------------------- números do site (Supabase)

def somar_eventos(eventos, ini, fim):
    c = Counter()
    for e in eventos:
        if ini <= date.fromisoformat(e["dia"]) <= fim:
            c[e["nome"]] += e["total"]
    return c


def contar_assinantes(assinantes, ini, fim):
    novos = sum(1 for a in assinantes if (d := dia_local(a.get("criado_em"))) and ini <= d <= fim)
    confirmados = sum(1 for a in assinantes if (d := dia_local(a.get("confirmado_em"))) and ini <= d <= fim)
    ativos = sum(1 for a in assinantes if a.get("status") == "ativo" and (d := dia_local(a.get("confirmado_em"))) and d <= fim)
    return {"novos": novos, "confirmados": confirmados, "ativos": ativos}


def curva(eventos, assinantes, fim, n=SEMANAS_CURVA):
    """Últimas n semanas (mais antiga primeiro): visitas, diagnósticos concluídos, confirmados e ativos no fim de cada uma."""
    linhas = []
    for k in range(n - 1, -1, -1):
        f = fim - timedelta(days=7 * k)
        i = f - timedelta(days=6)
        ev = somar_eventos(eventos, i, f) if eventos is not None else None
        ass = contar_assinantes(assinantes, i, f) if assinantes is not None else None
        linhas.append({"semana": i, "visitas": ev["visita"] if ev is not None else None,
                       "diagnosticos": ev["diagnostico_concluido"] if ev is not None else None,
                       "confirmados": ass["confirmados"] if ass else None, "ativos": ass["ativos"] if ass else None})
    return linhas


class Banco:
    def __init__(self, url, chave):
        self.url = url.rstrip("/") + "/rest/v1"
        self.h = {"apikey": chave}
        if chave.startswith("eyJ"):
            self.h["Authorization"] = f"Bearer {chave}"

    def _todos(self, caminho):
        """Lê a tabela inteira em páginas de 1000 linhas (limite do Supabase)."""
        linhas, ini = [], 0
        while True:
            r = requests.get(self.url + caminho, headers={**self.h, "Range": f"{ini}-{ini + 999}"}, timeout=30)
            r.raise_for_status()
            lote = r.json()
            linhas += lote
            if len(lote) < 1000:
                return linhas
            ini += 1000

    def eventos(self, desde):
        return self._todos(f"/eventos?select=dia,nome,total&dia=gte.{desde.isoformat()}&order=dia")

    def assinantes(self):
        return self._todos("/assinantes?select=status,criado_em,confirmado_em&order=criado_em")  # nunca o e-mail

    def estrutura(self):
        """Nomes de tabelas e funções que a API do Supabase expõe (documento OpenAPI, sem dados)."""
        r = requests.get(self.url + "/", headers={**self.h, "Accept": "application/openapi+json"}, timeout=30)
        r.raise_for_status()
        caminhos = r.json().get("paths", {})
        return {c.strip("/") for c in caminhos if c != "/"}


def faltando_no_banco(schema_sql, expostos):
    """Funções e tabelas do schema.sql que o Supabase ainda não tem (o dono ainda não rodou o schema.sql novo)."""
    funcoes = set(re.findall(r"create or replace function public\.(\w+)", schema_sql))
    tabelas = set(re.findall(r"create table if not exists public\.(\w+)", schema_sql))
    return sorted({f"função {f}" for f in funcoes if f"rpc/{f}" not in expostos}
                  | {f"tabela {t}" for t in tabelas if t not in expostos})


# ---------------------------------------------------------------- números do radar (base no Git)

def base_em(quando):
    """data/editais.json como estava no fim do dia `quando` (último commit até lá); None se não houver histórico."""
    try:
        sha = subprocess.run(["git", "log", "-1", f"--before={quando.isoformat()} 23:59:59 -0300", "--format=%H", "--",
                              "data/editais.json"], cwd=PASTA, capture_output=True, text=True, check=True).stdout.strip()
        if not sha:
            return None
        texto = subprocess.run(["git", "show", f"{sha}:data/editais.json"], cwd=PASTA, capture_output=True,
                               check=True).stdout.decode("utf-8")
        return json.loads(texto)
    except (subprocess.CalledProcessError, ValueError, OSError):  # sem git ou sem histórico
        return None


def mudancas_da_base(antes, depois, ini):
    """Editais conferidos novos (do ciclo atual: não encerrados no início da semana; o resto é histórico), retificações
    novas e achados do robô ainda não conferidos."""
    if antes is None:
        return None
    ids_antes = {e["id"] for e in antes if e.get("fonte_dados") == "manual"}
    retif_antes = {u for e in antes for u in e.get("retificacoes") or []}
    novos = [e for e in depois if e.get("fonte_dados") == "manual" and e["id"] not in ids_antes]
    atuais = [e for e in novos if radar.situacao(e, ini.isoformat()) != "encerrado"]
    achados_antes = {e["id"] for e in antes if e.get("fonte_dados") != "manual"}
    return {"novos_atuais": atuais, "novos_historico": len(novos) - len(atuais),
            "retificacoes": sorted({u for e in depois for u in e.get("retificacoes") or []} - retif_antes),
            "achados_robo": [e for e in depois if e.get("fonte_dados") != "manual" and e["id"] not in achados_antes]}


def prazos_da_semana(editais, ini):
    fim = ini + timedelta(days=6)
    return sorted((e for e in editais if e.get("fonte_dados") == "manual" and e.get("inscricao_fim")
                   and ini.isoformat() <= e["inscricao_fim"] <= fim.isoformat()), key=lambda e: e["inscricao_fim"])


def conferir_em_aberto(editais, hoje):
    return [e for e in editais if e.get("fonte_dados") == "manual" and e.get("status") == "conferir"
            and radar.situacao(e, hoje.isoformat()) != "encerrado"]


def issues_abertas(token, repo):
    """Issues abertas da checagem por etiqueta (só a contagem)."""
    if not (token and repo):
        return None
    r = requests.get(f"https://api.github.com/repos/{repo}/issues", params={"state": "open", "per_page": 100}, timeout=30,
                     headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    r.raise_for_status()
    return Counter(l["name"] for i in r.json() if "pull_request" not in i for l in i.get("labels", []))


# ---------------------------------------------------------------- montagem

def fmt(d):
    return f"{d[8:10]}/{d[5:7]}" if isinstance(d, str) else d.strftime("%d/%m")


def nome(e, faculdades):
    f = faculdades.get(e["faculdade_id"], {})
    mod = {"interna": ", interna", "portador_diploma": ", portador de diploma", "exterior": ", vindos do exterior"}
    return f"{f.get('sigla', e['faculdade_id'])} ({f.get('cidade', '?')}{mod.get(e.get('modalidade'), '')})"


def montar(d, faculdades):
    """Assunto, HTML e texto do relatório a partir do dicionário de números."""
    ini, fim = d["semana"]
    linhas = []  # (rótulo, valor, semana anterior, variação)
    if d["eventos"] is None:
        linhas.append(("Números do site", "sem dados (Supabase indisponível)", "", ""))
    else:
        for chave, rot in FUNIL:
            a, b = d["eventos"][chave], d["eventos_ant"][chave]
            linhas.append((rot, a, b, variacao(a, b)))
    if d["assinantes"] is not None:
        a, b = d["assinantes"], d["assinantes_ant"]
        linhas += [("Inscritos novos no alerta", a["novos"], b["novos"], variacao(a["novos"], b["novos"])),
                   ("Inscritos confirmados na semana", a["confirmados"], b["confirmados"], variacao(a["confirmados"], b["confirmados"])),
                   ("Alertas ativos no fim da semana", a["ativos"], b["ativos"], variacao(a["ativos"], b["ativos"]))]
    m = d["base"]
    if m is not None:
        linhas += [("Editais novos do ciclo atual (conferidos)", len(m["novos_atuais"]), "", ""),
                   ("Editais antigos acrescentados ao histórico", m["novos_historico"], "", ""),
                   ("Retificações registradas", len(m["retificacoes"]), "", ""),
                   ("Achados do robô a conferir", len(m["achados_robo"]), "", "")]
    blocos = []
    if m and m["novos_atuais"]:
        blocos.append(("Editais novos do ciclo atual", [f"{nome(e, faculdades)}: {e.get('semestre_ingresso') or 'semestre ?'}"
                                                         f"{', inscrições até ' + fmt(e['inscricao_fim']) if e.get('inscricao_fim') else ''}"
                                                         for e in m["novos_atuais"]]))
    if m and m["achados_robo"]:
        blocos.append(("Achados do robô (ler o PDF)", [f"{nome(e, faculdades)}: {e['url_edital']}" for e in m["achados_robo"]]))
    blocos.append(("Prazos desta semana", [f"{fmt(e['inscricao_fim'])}: {nome(e, faculdades)}"
                                           f"{' (prazo a conferir)' if 'inscricao_fim' in (e.get('conferir_campos') or {}) else ''}"
                                           for e in d["prazos"]] or ["Nenhum."]))
    blocos.append(("Editais em aberto marcados \"conferir\"", [f"{nome(e, faculdades)}: {', '.join(e.get('conferir_campos') or {'edital': ''})}"
                                                              for e in d["conferir"]] or ["Nenhum."]))
    if d["issues"] is not None:
        blocos.append(("Issues abertas da checagem", [f"{k}: {v}" for k, v in sorted(d["issues"].items())] or ["Nenhuma."]))
    if d["faltando"]:
        blocos.append(("Supabase desatualizado (rodar o supabase/schema.sql no SQL Editor)", d["faltando"]))

    titulo = f"Semana de {fmt(ini)} a {fmt(fim)}"
    v = d["eventos"]["visita"] if d["eventos"] is not None else None
    assunto = f"[Transfermed] Relatório semanal: {titulo}" + (f" · {v} visitas ({variacao(v, d['eventos_ant']['visita'])})" if v is not None else "")

    td = "padding:6px 8px;border-bottom:1px solid #E4E0D8"
    tabela = "".join(f"<tr><td style=\"{td}\">{escape(r)}</td><td style=\"{td};text-align:right;font-weight:bold\">{escape(str(a))}</td>"
                     f"<td style=\"{td};text-align:right;color:#565B57\">{escape(str(b))}</td><td style=\"{td};text-align:right\">{escape(c)}</td></tr>"
                     for r, a, b, c in linhas)
    cab = f"<tr><th style=\"{td};text-align:left\"></th><th style=\"{td};text-align:right\">Semana</th><th style=\"{td};text-align:right\">Anterior</th><th style=\"{td}\"></th></tr>"
    curva_html = "".join(f"<tr><td style=\"{td}\">{c['semana'].strftime('%d/%m')}</td>"
                         + "".join(f"<td style=\"{td};text-align:right\">{'–' if c[k] is None else c[k]}</td>" for k in ("visitas", "diagnosticos", "confirmados", "ativos"))
                         + "</tr>" for c in d["curva"])
    curva_cab = (f"<tr><th style=\"{td};text-align:left\">Semana de</th><th style=\"{td};text-align:right\">Visitas</th>"
                 f"<th style=\"{td};text-align:right\">Diagnósticos</th><th style=\"{td};text-align:right\">Confirmados</th>"
                 f"<th style=\"{td};text-align:right\">Ativos</th></tr>")
    listas = "".join(f"<h2 style=\"font-size:16px;margin:20px 0 6px\">{escape(t)}</h2><ul style=\"margin:0;padding-left:20px\">"
                     + "".join(f"<li>{escape(x)}</li>" for x in itens) + "</ul>" for t, itens in blocos)
    html = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(titulo)}</title></head><body style="margin:0;background:#F7F5F1;padding:24px 12px;font-family:Arial,sans-serif;color:#1F2421">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:620px;margin:0 auto;background:#FFFFFF;border-radius:14px">
<tr><td style="background:#0F5C4D;border-radius:14px 14px 0 0;padding:18px 24px;color:#FFFFFF;font-size:18px;font-weight:bold">Transfermed · relatório semanal</td></tr>
<tr><td style="padding:24px"><h1 style="font-size:20px;margin:0 0 12px">{escape(titulo)}</h1>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:14px">{cab}{tabela}</table>
<h2 style="font-size:16px;margin:20px 0 6px">Curva das últimas {len(d['curva'])} semanas</h2>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:14px">{curva_cab}{curva_html}</table>
{listas}
<p style="font-size:12px;color:#565B57;margin-top:24px">Visitas e diagnósticos contam eventos sem cookies (uma página aberta = uma visita).
Gerado em {escape(d['gerado_em'])}. Só você recebe este e-mail.</p></td></tr></table></body></html>"""
    texto = "\n".join([titulo, ""] + [f"{r}: {a} (anterior {b}) {c}".rstrip() if b != "" else f"{r}: {a}" for r, a, b, c in linhas]
                      + ["", f"Curva ({len(d['curva'])} semanas): visitas, diagnósticos, confirmados, ativos"]
                      + [f"{c['semana'].strftime('%d/%m')}: " + ", ".join("–" if c[k] is None else str(c[k]) for k in ("visitas", "diagnosticos", "confirmados", "ativos")) for c in d["curva"]]
                      + [l for t, itens in blocos for l in ["", t] + [f"- {x}" for x in itens]])
    return assunto, html, texto


def coletar(hoje, banco=None, gh=(None, None)):
    ini, fim = semana_passada(hoje)
    ini_ant, fim_ant = ini - timedelta(days=7), ini - timedelta(days=1)
    faculdades = {f["id"]: f for f in json.loads((PASTA / "data" / "faculdades.json").read_text(encoding="utf-8"))}
    editais = json.loads((PASTA / "data" / "editais.json").read_text(encoding="utf-8"))
    eventos = assinantes = None
    faltando = []
    if banco is not None:
        try:
            eventos = banco.eventos(fim - timedelta(days=7 * SEMANAS_CURVA))
        except requests.RequestException:
            eventos = None
        try:
            assinantes = banco.assinantes()
        except requests.RequestException:
            assinantes = None
        try:
            faltando = faltando_no_banco((PASTA / "supabase" / "schema.sql").read_text(encoding="utf-8"), banco.estrutura())
        except requests.RequestException:
            faltando = ["não consegui ler a estrutura do Supabase"]
    depois = base_em(fim) or editais
    try:
        issues = issues_abertas(*gh)
    except requests.RequestException:
        issues = None
    d = {"semana": (ini, fim), "gerado_em": datetime.now(BRASILIA).strftime("%d/%m/%Y %H:%M"),
         "eventos": somar_eventos(eventos, ini, fim) if eventos is not None else None,
         "eventos_ant": somar_eventos(eventos, ini_ant, fim_ant) if eventos is not None else None,
         "assinantes": contar_assinantes(assinantes, ini, fim) if assinantes is not None else None,
         "assinantes_ant": contar_assinantes(assinantes, ini_ant, fim_ant) if assinantes is not None else None,
         "curva": curva(eventos, assinantes, fim),
         "base": mudancas_da_base(base_em(fim_ant), depois, ini),
         "prazos": prazos_da_semana(editais, hoje), "conferir": conferir_em_aberto(editais, hoje),
         "issues": issues, "faltando": faltando}
    return d, faculdades


EVENTOS_RADAR = ("radar_ponto", "radar_grupo", "radar_chip_abertos", "radar_chip_semana", "radar_chip_exterior",
                 "radar_chip_publicas", "radar_estado", "porta_brasil", "porta_exterior")


def conferir_eventos(linhas, dia, nomes=EVENTOS_RADAR):
    """Para cada evento: gravado no dia ou não. Só sim/não: o registro do Actions é público, nenhum número sai dali."""
    gravados = {x["nome"] for x in linhas if x["dia"] == dia.isoformat() and x.get("total")}
    return [f"{n}: {'gravado' if n in gravados else 'ainda sem registro'}" for n in nomes]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Relatório semanal do sócio.")
    ap.add_argument("--enviar", action="store_true", help="envia por e-mail para CONTATO_DESTINO (sem isto: só mostra)")
    ap.add_argument("--hoje", help="data de referência AAAA-MM-DD (padrão: hoje em Brasília)")
    ap.add_argument("--conferir-eventos", action="store_true", help="diz se cada evento do radar foi gravado hoje (sem números)")
    args = ap.parse_args(argv)
    hoje = date.fromisoformat(args.hoje) if args.hoje else datetime.now(BRASILIA).date()
    banco = (Banco(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
             if os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY") else None)
    if args.conferir_eventos:
        if not banco:
            print("Sem SUPABASE_URL e SUPABASE_SERVICE_KEY: não dá para conferir")
            return 1
        print("\n".join(conferir_eventos(banco.eventos(hoje), hoje)))
        return 0
    d, faculdades = coletar(hoje, banco, (os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")))
    assunto, html, texto = montar(d, faculdades)
    if not args.enviar:
        print(assunto + "\n\n" + texto)
        return 0
    faltam = [v for v in ("BREVO_API_KEY", "REMETENTE_EMAIL", "CONTATO_DESTINO") if not os.environ.get(v)]
    if faltam:
        print("Relatório não enviado: faltam " + ", ".join(faltam))
        return 1
    r = requests.post("https://api.brevo.com/v3/smtp/email", timeout=30,
                      headers={"api-key": os.environ["BREVO_API_KEY"], "Content-Type": "application/json"},
                      json={"sender": {"email": os.environ["REMETENTE_EMAIL"], "name": "Transfermed (relatório)"},
                            "to": [{"email": os.environ["CONTATO_DESTINO"]}], "subject": assunto,
                            "htmlContent": html, "textContent": texto})
    # o registro do Actions é público: só a situação do envio, nenhum número
    print(f"Relatório da semana {fmt(d['semana'][0])} a {fmt(d['semana'][1])}: envio HTTP {r.status_code}")
    return 0 if r.ok else 1


if __name__ == "__main__":
    sys.exit(main())
