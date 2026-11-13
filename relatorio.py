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
import tempo
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

import requests

import entregabilidade
import radar

PASTA = Path(__file__).resolve().parent
BRASILIA = tempo.BRASILIA
SEMANAS_CURVA = 8
# linhas do relatório: (evento medido, rótulo)
FUNIL = [("visita", "Visitas (páginas abertas)"), ("diagnostico_iniciado", "Diagnósticos iniciados"),
         ("diagnostico_concluido", "Diagnósticos concluídos"), ("ver_edital", "Editais abertos no site"),
         ("alerta_inscrito", "Pedidos de alerta"), ("isca", "Checklist em PDF baixado"),
         ("compartilhar_whatsapp", "Compartilhamentos no WhatsApp"),
         ("radar_ponto", "Toques em faculdades no radar"), ("porta_brasil", "Escolheram \"Estudo no Brasil\""),
         ("porta_exterior", "Escolheram \"Estudo fora do Brasil\""), ("pro_interesse", "Interesse no plano futuro (lista de espera)"),
         ("indicar_colega", "Cliques em \"Avise um colega\"")]


# ---------------------------------------------------------------- períodos

def semana_passada(hoje):
    """(segunda, domingo) da última semana completa antes de `hoje`."""
    domingo = hoje - timedelta(days=hoje.weekday() + 1)
    return domingo - timedelta(days=6), domingo


def dia_local(quando):
    """Timestamp do Supabase (ISO com fuso) -> data em Brasília."""
    if not quando:
        return None
    return tempo.dia_local(quando)


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


CANAIS = {"google": "Google", "instagram": "Instagram", "whatsapp": "WhatsApp", "facebook": "Facebook", "grupo": "Grupos de estudantes",
          "indicacao": "Indicação de colega", "email": "E-mail", "outro_site": "Outro site", "direto": "Direto (sem origem)"}
CANAIS_DE_INDICACAO = ("indicacao", "grupo", "whatsapp")


def origem_dos_inscritos(assinantes, ini, fim):
    """{canal: {"novos": n, "confirmados": n}} da semana. Inscrito de antes da medição (sem canal) vai para
    "sem_medicao"; canal desconhecido vira "outro_site". Só códigos: nunca endereço, nome ou e-mail."""
    saida = {}
    for a in assinantes:
        canal = a.get("canal")
        canal = "sem_medicao" if not canal else (canal if canal in CANAIS else "outro_site")
        linha = saida.setdefault(canal, {"novos": 0, "confirmados": 0})
        if (d := dia_local(a.get("criado_em"))) and ini <= d <= fim:
            linha["novos"] += 1
        if (d := dia_local(a.get("confirmado_em"))) and ini <= d <= fim:
            linha["confirmados"] += 1
    return {c: v for c, v in saida.items() if v["novos"] or v["confirmados"]}


PORTAS = {"diagnostico": "Diagnóstico", "seguir": "Seguir edital ou faculdade", "outra": "Outras páginas (início, lista de editais, exterior)",
          "sem_medicao": "Antes da medição"}


def porta_do_contexto(contexto):
    """Mesma regra do app.js (portaDoPedido): o contexto do formulário de alerta vira a porta de entrada."""
    if contexto == "diagnostico":
        return "diagnostico"
    return "seguir" if contexto.startswith(("edital_", "faculdade_")) else "outra"


def por_porta(assinantes, eventos, hoje):
    """Inscritos por porta (diagnóstico × seguir edital) e a taxa de confirmação de cada uma.
    Coorte: cadastros criados de hoje-6 até ontem. O cadastro não confirmado só é apagado aos 7 dias, então a coorte inteira ainda está
    no banco e a taxa não perde quem sumiu; limite: quem se inscreveu há menos de 3 dias ainda pode confirmar (a taxa sobe um pouco).
    Pedidos de alerta em 28 dias: contadores anônimos do site (`alerta_inscrito_<contexto>`), que não dependem do cadastro. Só contagens."""
    ini, fim = hoje - timedelta(days=6), hoje - timedelta(days=1)
    saida = {}

    def linha(porta):
        return saida.setdefault(porta, {"coorte": 0, "confirmados": 0, "ativos_total": 0, "pedidos_28d": 0, "pct": None})

    for a in assinantes:
        l = linha(a.get("porta") if a.get("porta") in PORTAS else "sem_medicao")
        if a.get("status") == "ativo":
            l["ativos_total"] += 1
        d = dia_local(a.get("criado_em"))
        if d and ini <= d <= fim:
            l["coorte"] += 1
            l["confirmados"] += a.get("status") == "ativo"
    for e in eventos or []:
        nome = e.get("nome", "")
        if nome.startswith("alerta_inscrito_") and hoje - timedelta(days=27) <= date.fromisoformat(e["dia"]) <= hoje:
            linha(porta_do_contexto(nome[len("alerta_inscrito_"):]))["pedidos_28d"] += e["total"]
    for v in saida.values():
        v["pct"] = round(100 * v["confirmados"] / v["coorte"]) if v["coorte"] else None
    return {p: v for p, v in saida.items() if any(v[k] for k in ("coorte", "ativos_total", "pedidos_28d"))}


def sites_de_origem(assinantes):
    """Domínios do canal "outro_site" (agregado: domínio e quantidade; nunca endereço completo, nunca a pessoa) e quantos "outro_site" e
    "direto" não têm origem detalhada (inscritos antes de 09/11/2026, quando o domínio e a regra do navegador do Instagram entraram)."""
    dominios = Counter()
    sem_dominio = direto = 0
    for a in assinantes:
        if a.get("canal") == "outro_site":
            ref = a.get("ref") or ""
            if re.fullmatch(r"[a-z0-9.-]{1,60}", ref):
                dominios[ref] += 1
            else:
                sem_dominio += 1
        elif a.get("canal") == "direto":
            direto += 1
    return {"dominios": dominios.most_common(15), "outro_site_sem_dominio": sem_dominio, "direto": direto}


def taxa_de_confirmacao(eventos, ini, fim):
    """Confirmados ÷ pedidos de alerta no período, pelos contadores anônimos do site (`alerta_inscrito` e `alerta_confirmado`). Vem dos
    eventos e não do cadastro porque o cadastro não confirmado é apagado em 7 dias (LGPD) e sumiria do denominador. Limite: quem confirma
    hoje pode ter pedido na semana passada, e quem pede de novo conta mais de uma vez; por isso vale ler a janela de 28 dias.
    Devolve {"pedidos": n, "confirmados": n, "pct": int|None}; None sem Supabase."""
    if eventos is None:
        return None
    c = somar_eventos(eventos, ini, fim)
    pedidos, conf = c["alerta_inscrito"], c["alerta_confirmado"]
    return {"pedidos": pedidos, "confirmados": conf, "pct": round(100 * conf / pedidos) if pedidos else None}


def numeros_do_dia(assinantes, notificacoes, hoje, brevo=None, eventos=None, filtro_de_teste=None):
    """Os números que abrem todo relatório (pedido do dono, 08/11/2026): alertas confirmados no total, novos nos últimos 7 dias,
    por origem, e alertas enviados nos últimos 7 dias. `hoje` entra na janela (hoje e os 6 dias anteriores). Só contagens e códigos.
    notificacoes: linhas de `notificacoes` (um e-mail de alerta por inscrito e edital); None se o banco não respondeu.
    brevo: {"enviados": n, "entregues": n} do Brevo na mesma janela, ou None."""
    ini = hoje - timedelta(days=6)
    por_origem = {}
    for a in assinantes:
        canal = a.get("canal")
        canal = "sem_medicao" if not canal else (canal if canal in CANAIS else "outro_site")
        linha = por_origem.setdefault(canal, {"ativos": 0, "novos_7d": 0, "confirmados_7d": 0})
        confirmado = dia_local(a.get("confirmado_em"))
        if a.get("status") == "ativo" and confirmado and confirmado <= hoje:
            linha["ativos"] += 1
        if (d := dia_local(a.get("criado_em"))) and ini <= d <= hoje:
            linha["novos_7d"] += 1
        if confirmado and ini <= confirmado <= hoje:
            linha["confirmados_7d"] += 1
    noti = None
    if notificacoes is not None:
        na_janela = [n for n in notificacoes if (d := dia_local(n.get("enviado_em"))) and ini <= d <= hoje]
        noti = {"alertas": len(na_janela), "inscritos": len({n["assinante_id"] for n in na_janela})}
    return {"janela": (ini, hoje),
            "confirmados_total": sum(v["ativos"] for v in por_origem.values()),
            "pendentes_total": sum(1 for a in assinantes if a.get("status") != "ativo"),
            "novos_7d": sum(v["novos_7d"] for v in por_origem.values()),
            "confirmados_7d": sum(v["confirmados_7d"] for v in por_origem.values()),
            "por_origem": {c: v for c, v in por_origem.items() if v["ativos"] or v["novos_7d"] or v["confirmados_7d"]},
            "enviados": noti, "brevo": brevo, "filtro_de_teste": filtro_de_teste,
            "por_porta": por_porta(assinantes, eventos, hoje), "sites": sites_de_origem(assinantes),
            "taxa_7d": taxa_de_confirmacao(eventos, ini, hoje), "taxa_28d": taxa_de_confirmacao(eventos, hoje - timedelta(days=27), hoje)}


def texto_numeros_do_dia(n):
    ini, fim = n["janela"]
    linhas = [f"Alertas confirmados (ativos) no total: {n['confirmados_total']} (aguardando confirmação: {n['pendentes_total']})",
              f"Inscritos novos nos últimos 7 dias ({ini.strftime('%d/%m')} a {fim.strftime('%d/%m')}): {n['novos_7d']} "
              f"(confirmaram nesse período: {n['confirmados_7d']})"]
    ordem = sorted(n["por_origem"].items(), key=lambda kv: (-kv[1]["novos_7d"], -kv[1]["ativos"]))
    linhas.append("Por origem (ativos no total · novos em 7 dias): " + ("; ".join(
        f"{CANAIS.get(c, 'antes da medição' if c == 'sem_medicao' else c)} {v['ativos']} · {v['novos_7d']}" for c, v in ordem) or "sem dados"))
    e = n["enviados"]
    linhas.append("Alertas enviados nos últimos 7 dias: " + (f"{e['alertas']} e-mails de edital para {e['inscritos']} inscritos (registro do Supabase)"
                                                              if e is not None else "não medido (Supabase não respondeu)"))
    for rot, chave in (("7 dias", "taxa_7d"), ("28 dias", "taxa_28d")):
        t = n.get(chave)
        if t is not None:
            linhas.append(f"Taxa de confirmação em {rot}: " + (f"{t['pct']}% ({t['confirmados']} confirmaram ÷ {t['pedidos']} pedidos de alerta)"
                                                                   if t["pct"] is not None else "sem pedidos no período"))
    if n.get("filtro_de_teste") is False:
        linhas.append("ATENÇÃO: os e-mails de teste do dono estão contados nestes números (rodar o schema.sql novo no Supabase e cadastrar os e-mails em emails_teste).")
    elif n.get("filtro_de_teste"):
        linhas.append("E-mails de teste do dono: fora destes números (lista só no Supabase).")
    portas = n.get("por_porta") or {}
    if portas:
        linhas.append("Por porta (inscritos dos últimos 7 dias, sem hoje: confirmaram até agora; pedidos de alerta em 28 dias; ativos no total): " + "; ".join(
            f"{PORTAS[p]} {v['confirmados']} de {v['coorte']}" + (f" ({v['pct']}%)" if v["pct"] is not None else "") + f" · {v['pedidos_28d']} · {v['ativos_total']}"
            for p, v in sorted(portas.items(), key=lambda kv: -kv[1]["coorte"])))
    sites = n.get("sites")
    if sites and (sites["dominios"] or sites["outro_site_sem_dominio"] or sites["direto"]):
        linhas.append("Outro site, por domínio de origem: " + ("; ".join(f"{d} {q}" for d, q in sites["dominios"]) or "nenhum domínio registrado ainda")
                      + f". Sem domínio registrado (antes de 09/11/2026): {sites['outro_site_sem_dominio']} em outro site e {sites['direto']} direto. "
                      "O cadastro não guarda o referenciador de quem já estava inscrito, então não dá para provar quantos eram Instagram; "
                      "a partir de 09/11 o navegador do app e o android-app:// do Instagram entram como Instagram.")
    b = n.get("brevo")
    if b:
        linhas.append(f"Brevo nos últimos 7 dias: {b['enviados']} e-mails transacionais enviados, {b['entregues']} entregues")
    linhas += entregabilidade.linhas_relatorio(b)
    return linhas


def abertos_sem_conferir(editais, hoje):
    """(sem_conferir, abertos): dos editais abertos que o projeto confere à mão, quantos não têm status "conferir" nem campo em conferir_campos.
    Meta do mutirão: sem_conferir == abertos. `hoje` é um date."""
    abertos = [e for e in editais if e.get("fonte_dados") == "manual" and e.get("inscricao_fim") and radar.situacao(e, hoje.isoformat()) != "encerrado"]
    limpos = [e for e in abertos if e.get("status") != "conferir" and not (e.get("conferir_campos") or {})]
    return len(limpos), len(abertos)


def respostas_das_faculdades(arquivo=None):
    """Quantas faculdades responderam ao B0, lendo a coluna Resposta de privado/b2b/envios.md (registro manual do dono, fora do Git).
    None se o arquivo não existe (no GitHub Actions): a resposta chega ao e-mail do dono e o robô não a vê."""
    arquivo = Path(arquivo or PASTA / "privado" / "b2b" / "envios.md")
    if not arquivo.exists():
        return None
    respondeu = set()
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        c = [x.strip() for x in linha.strip().strip("|").split("|")]
        if len(c) >= 5 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", c[0]) and c[4]:
            respondeu.add(c[1].lower())
    return len(respondeu)


def cinco_numeros(d):
    """Os 5 números que abrem o relatório semanal, cada um com a semana anterior (pedido do dono, 10/11/2026). Texto, uma linha por número;
    o que não deu para medir diz o motivo (nada é estimado)."""
    def par(a, b, fmt_=str):
        return f"{fmt_(a)} (semana anterior: {fmt_(b)})" if b is not None else fmt_(a)

    linhas = []
    a, b = d.get("assinantes"), d.get("assinantes_ant")
    linhas.append("1. Alertas confirmados (ativos; os e-mails de teste só ficam de fora se estiverem em emails_teste): "
                  + (par(a["ativos"], b["ativos"]) + " · meta: 300" if a and b else "não medido (Supabase não respondeu)"))
    e, ea = d.get("eventos"), d.get("eventos_ant")
    if e is not None and ea is not None:
        def taxa(x):
            return f"{round(100 * x['alerta_confirmado'] / x['alerta_inscrito'])}% ({x['alerta_confirmado']} de {x['alerta_inscrito']} pedidos)" if x["alerta_inscrito"] else "sem pedidos"
        linhas.append("2. Taxa de confirmação (confirmados ÷ pedidos de alerta, contadores do site): " + par(e, ea, taxa))
    else:
        linhas.append("2. Taxa de confirmação: não medida (Supabase não respondeu)")
    o, oa = d.get("origem"), d.get("origem_ant")
    if o is not None and oa is not None:
        canais = sorted(set(o) | set(oa), key=lambda c: -(o.get(c, {}).get("novos", 0)))
        txt = "; ".join(f"{CANAIS.get(c, 'antes da medição' if c == 'sem_medicao' else c)} {o.get(c, {}).get('novos', 0)} (ant. {oa.get(c, {}).get('novos', 0)})" for c in canais)
        linhas.append("3. Inscritos novos por origem (semana · anterior): " + (txt or "nenhum inscrito nas duas semanas"))
    else:
        linhas.append("3. Inscritos novos por origem: não medido (Supabase não respondeu)")
    ab = d.get("abertos_sem_conferir")
    ab_ant = d.get("abertos_sem_conferir_ant")
    if ab:
        txt = f"{ab[0]} de {ab[1]} editais abertos sem nenhum campo em conferir"
        linhas.append("4. Abertos com zero \"conferir\": " + txt + (f" (semana anterior: {ab_ant[0]} de {ab_ant[1]})" if ab_ant else " (semana anterior: sem retrato da base)")
                      + " · meta: todos")
    r = d.get("respostas_faculdades")
    linhas.append("5. Respostas das faculdades ao B0: " + (f"{r} (total desde o 1º envio; sem comparação semanal, o registro é manual em privado/b2b/envios.md)" if r is not None
                  else "não medido aqui: a resposta chega ao e-mail do dono e o robô não a vê; rode `python relatorio.py` no computador do dono para contar o registro"))
    return linhas


def brevo_7_dias(chave, http=None):
    """Totais do Brevo na janela de 7 dias (e-mails transacionais pedidos e entregues). None se a API não responder."""
    try:
        r = (http or requests).get("https://api.brevo.com/v3/smtp/statistics/aggregatedReport", params={"days": 7},
                                   headers={"api-key": chave}, timeout=30)
        r.raise_for_status()
        j = r.json()
        return {"enviados": j.get("requests", 0), "entregues": j.get("delivered", 0), "aberturas": j.get("opens", 0), "cliques": j.get("clicks", 0)}
    except (requests.RequestException, ValueError):
        return None


def pct_indicacao(origem):
    """% dos inscritos novos que vieram de indicação, grupo ou WhatsApp (meta do ROADMAP: 25% no H1); None sem dados."""
    medidos = sum(v["novos"] for c, v in origem.items() if c != "sem_medicao")
    if not medidos:
        return None
    return round(100 * sum(v["novos"] for c, v in origem.items() if c in CANAIS_DE_INDICACAO) / medidos)


AMOSTRA_MINIMA = 30  # abaixo disto a porcentagem engana: mostramos o número absoluto e dizemos "amostra pequena"


def retorno_30_dias(assinantes, hoje):
    """T6.4, só com o que já existe no banco (sem mudar o schema): dos alertas ativos há 30 dias ou mais, quantos VOLTARAM ao site
    para atualizar o alerta (`atualizacao_avisada_em` preenchido). Limite honesto: o descadastro apaga o cadastro (LGPD), então não
    há como contar quem saiu; o que se mede é o retorno de quem ficou. Sem dado pessoal: só contagens, por canal de origem."""
    limite = hoje - timedelta(days=30)
    coorte = [a for a in assinantes if a.get("status") == "ativo" and (d := dia_local(a.get("confirmado_em"))) and d <= limite]
    voltaram = [a for a in coorte if a.get("atualizacao_avisada_em")]
    por_canal = {}
    for a in coorte:
        c = por_canal.setdefault(a.get("canal") or "sem_medicao", {"coorte": 0, "voltaram": 0})
        c["coorte"] += 1
        c["voltaram"] += 1 if a.get("atualizacao_avisada_em") else 0
    confirmados = [d for a in assinantes if a.get("status") == "ativo" and (d := dia_local(a.get("confirmado_em")))]
    primeira = (min(confirmados) + timedelta(days=30)) if confirmados else None
    return {"coorte": len(coorte), "voltaram": len(voltaram), "por_canal": por_canal, "primeira_coorte_em": primeira,
            "amostra_pequena": len(coorte) < AMOSTRA_MINIMA}


def texto_retorno(r, hoje):
    """Linhas do relatório sobre o retorno em 30 dias (sempre com o n visível)."""
    if r["coorte"] == 0:
        quando = f" A primeira coorte completa de 30 dias fecha em {fmt(r['primeira_coorte_em'])}." if r["primeira_coorte_em"] and r["primeira_coorte_em"] > hoje else ""
        return [f"Ainda não há alerta ativo com 30 dias ou mais.{quando}"]
    pct = f"{round(100 * r['voltaram'] / r['coorte'])}%"
    linhas = [f"{r['coorte']} alerta(s) ativo(s) com 30 dias ou mais; {r['voltaram']} voltaram ao site para atualizar o alerta ({pct})"
              + (f". Amostra pequena (menos de {AMOSTRA_MINIMA}): não tirar conclusão." if r["amostra_pequena"] else ".")]
    linhas += [f"{CANAIS.get(c, 'Antes da medição' if c == 'sem_medicao' else c)}: {v['voltaram']} de {v['coorte']}" for c, v in sorted(r["por_canal"].items(), key=lambda kv: -kv[1]["coorte"])]
    linhas.append("Quem se descadastra tem o cadastro apagado (LGPD): este número mede o retorno de quem ficou, não a saída.")
    return linhas


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

    COLUNAS_MEDICAO = "id,status,criado_em,confirmado_em,atualizacao_avisada_em,canal,ref,porta,com_diagnostico"

    def assinantes(self):
        """Cadastros SEM os e-mails de teste do dono (a lista fica só no Supabase: tabela emails_teste), lidos pela visão assinantes_medicao.
        Se a visão ainda não existe (o schema.sql novo não foi rodado), cai na tabela inteira e marca `filtro_de_teste = False`: o relatório
        avisa que os testes do dono estão contados. Nunca pede o e-mail."""
        self.filtro_de_teste = True
        try:
            return self._todos(f"/assinantes_medicao?select={self.COLUNAS_MEDICAO}&order=criado_em")
        except requests.HTTPError as erro:
            if erro.response is None or erro.response.status_code not in (400, 404):
                raise
        self.filtro_de_teste = False
        return self._todos("/assinantes?select=id,status,criado_em,confirmado_em,atualizacao_avisada_em,canal:perfil->>canal,ref:perfil->>ref,"
                           "porta:perfil->>porta,com_diagnostico:perfil->>curso&order=criado_em")  # só campos do perfil; nunca o e-mail

    def notificacoes(self, desde):
        """Alertas enviados desde a data: só o id do inscrito (um código sem significado) e o momento; nunca o e-mail."""
        return self._todos(f"/notificacoes?select=assinante_id,enviado_em&enviado_em=gte.{desde.isoformat()}&order=enviado_em")

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
    visoes = set(re.findall(r"create or replace view public\.(\w+)", schema_sql))
    return sorted({f"função {f}" for f in funcoes if f"rpc/{f}" not in expostos}
                  | {f"tabela {t}" for t in tabelas if t not in expostos}
                  | {f"visão {v}" for v in visoes if v not in expostos})


# ---------------------------------------------------------------- números do radar (base no Git)

def base_em(quando, arquivo="editais.json"):
    """data/<arquivo> como estava no fim do dia `quando` (último commit até lá); None se não houver histórico."""
    try:
        sha = subprocess.run(["git", "log", "-1", f"--before={quando.isoformat()} 23:59:59 -0300", "--format=%H", "--",
                              f"data/{arquivo}"], cwd=PASTA, capture_output=True, text=True, check=True).stdout.strip()
        if not sha:
            return None
        texto = subprocess.run(["git", "show", f"{sha}:data/{arquivo}"], cwd=PASTA, capture_output=True,
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


# ---------------------------------------------------------------- cobertura dos estados prioritários

PRIORITARIOS = ["SP", "MG", "BA", "RJ", "PR"]  # mesma lista de gerar_site.PRIORITARIOS (um teste confere)


def cobertura_estados(faculdades, editais, hoje, emec=None):
    """Por estado prioritário: faculdades cadastradas (e % do e-MEC, quando data/cobertura_emec.json existir), % com robô
    diário (página de editais lida pelo robô e sem pendência) e editais abertos completos (sem campo a conferir)."""
    h = hoje.isoformat() if hasattr(hoje, "isoformat") else hoje
    saida = {}
    for uf in PRIORITARIOS:
        facs = [f for f in faculdades.values() if f.get("uf") == uf]
        ids = {f["id"] for f in facs}
        robo = [f for f in facs if not f.get("pendente") and (f.get("paginas_editais") or f.get("wordpress") or f.get("api_noticias"))]
        abertos = [x for x in editais if x["faculdade_id"] in ids and radar.situacao(x, h) == "aberto"]
        completos = [x for x in abertos if not x.get("conferir_campos")]
        dado = (emec or {}).get(uf)
        # `dado` é a contagem do e-MEC (número) ou {"emec": n, "correspondentes": m}: m = cursos do e-MEC que têm ficha na base
        # (a base pode ter fichas fora do e-MEC "em atividade", e isso não pode inflar a cobertura)
        total_emec = dado.get("emec") if isinstance(dado, dict) else dado
        casadas = dado.get("correspondentes", len(facs)) if isinstance(dado, dict) else len(facs)
        saida[uf] = {"cadastradas": len(facs), "emec": total_emec,
                     "pct_cadastradas": round(100 * casadas / total_emec) if total_emec else None,
                     "robo": len(robo), "pct_robo": round(100 * len(robo) / len(facs)) if facs else None,
                     "abertos": len(abertos), "abertos_completos": len(completos)}
    return saida


def carregar_emec():
    """Contagem de cursos de Medicina ativos por UF no e-MEC (data/cobertura_emec.json, números públicos); None se não houver."""
    try:
        return json.loads((PASTA / "data" / "cobertura_emec.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


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
        a, b = d["eventos"], d["eventos_ant"]
        taxa = lambda e: f"{round(100 * e['pro_interesse'] / e['diagnostico_concluido'])}%" if e.get("diagnostico_concluido") else "–"
        linhas.append(("Interesse no plano futuro ÷ diagnósticos concluídos (meta do teste R1: 10%)", taxa(a), taxa(b), ""))
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
    cinco = cinco_numeros(d)
    abertura = (texto_numeros_do_dia(d["numeros_do_dia"]) if d.get("numeros_do_dia")
                else ["Números de hoje indisponíveis: o Supabase não respondeu (nada foi estimado)."])
    blocos = []
    if m and m["novos_atuais"]:
        blocos.append(("Editais novos do ciclo atual", [f"{nome(e, faculdades)}: {e.get('semestre_ingresso') or 'semestre ?'}"
                                                         f"{', inscrições até ' + fmt(e['inscricao_fim']) if e.get('inscricao_fim') else ''}"
                                                         for e in m["novos_atuais"]]))
    if m and m["achados_robo"]:
        blocos.append(("Achados do robô (ler o PDF)", [f"{nome(e, faculdades)}: {e['url_edital']}" for e in m["achados_robo"]]))
    if d.get("retorno") is not None:
        blocos.append(("Retorno em 30 dias (quem já era inscrito)", texto_retorno(d["retorno"], d["semana"][1])))
    if d.get("guardiao"):
        blocos.append(("Guardião do site", [d["guardiao"]]))
    if d.get("origem") is not None:
        o, pi = d["origem"], pct_indicacao(d["origem"])
        itens = [f"{CANAIS.get(c, 'Antes da medição' if c == 'sem_medicao' else c)}: {v['novos']} novos, {v['confirmados']} confirmados"
                 for c, v in sorted(o.items(), key=lambda kv: -kv[1]["novos"])] or ["Nenhum inscrito na semana."]
        itens.append("Vindos de indicação, grupo ou WhatsApp: " + (f"{pi}% dos novos (meta H1: 25%)" if pi is not None else "sem dados medidos ainda"))
        blocos.append(("Origem dos inscritos no alerta", itens))
    if d.get("cobertura"):
        def linha_cob(uf, c, a):
            emec = f" de {c['emec']} no e-MEC ({c['pct_cadastradas']}%)" if c["emec"] else " (e-MEC: aguardando a contagem)"
            ant = (f" · semana anterior: {a[uf]['cadastradas']} cadastradas, robô {a[uf]['robo']}, abertos completos "
                   f"{a[uf]['abertos_completos']}/{a[uf]['abertos']}") if a else ""
            pr = f"{c['pct_robo']}%" if c["pct_robo"] is not None else "–"
            return (f"{uf}: {c['cadastradas']} cadastradas{emec} · robô diário em {c['robo']} ({pr}) · "
                    f"editais abertos completos {c['abertos_completos']} de {c['abertos']}{ant}")
        blocos.append(("Cobertura dos estados prioritários", [linha_cob(uf, c, d.get("cobertura_ant")) for uf, c in d["cobertura"].items()]))
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
<h2 style="font-size:16px;margin:0 0 6px">Os 5 números da semana</h2><ul style="margin:0 0 16px;padding-left:20px">{"".join(f"<li>{escape(x)}</li>" for x in cinco)}</ul>
<h2 style="font-size:16px;margin:0 0 6px">Números de hoje</h2><ul style="margin:0 0 16px;padding-left:20px">{"".join(f"<li>{escape(x)}</li>" for x in abertura)}</ul>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:14px">{cab}{tabela}</table>
<h2 style="font-size:16px;margin:20px 0 6px">Curva das últimas {len(d['curva'])} semanas</h2>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:14px">{curva_cab}{curva_html}</table>
{listas}
<p style="font-size:12px;color:#565B57;margin-top:24px">Visitas e diagnósticos contam eventos sem cookies (uma página aberta = uma visita).
Gerado em {escape(d['gerado_em'])}. Só você recebe este e-mail.</p></td></tr></table></body></html>"""
    texto = "\n".join([titulo, "", "OS 5 NÚMEROS DA SEMANA"] + [f"- {x}" for x in cinco] + ["", "NÚMEROS DE HOJE"] + [f"- {x}" for x in abertura] + [""] + [f"{r}: {a} (anterior {b}) {c}".rstrip() if b != "" else f"{r}: {a}" for r, a, b, c in linhas]
                      + ["", f"Curva ({len(d['curva'])} semanas): visitas, diagnósticos, confirmados, ativos"]
                      + [f"{c['semana'].strftime('%d/%m')}: " + ", ".join("–" if c[k] is None else str(c[k]) for k in ("visitas", "diagnosticos", "confirmados", "ativos")) for c in d["curva"]]
                      + [l for t, itens in blocos for l in ["", t] + [f"- {x}" for x in itens]])
    return assunto, html, texto


def linha_do_guardiao(hoje):
    """Uma linha por semana sobre o guardião diário (T6.2): dias vigiados, falhas, quarentena e DMARC."""
    import guardiao
    try:
        resumo = json.loads((PASTA / "data" / "guardiao.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        resumo = {}
    return guardiao.linha_semanal(resumo, hoje)


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
    numeros = None
    if assinantes is not None:
        try:
            noti = banco.notificacoes(hoje - timedelta(days=6))
        except requests.RequestException:
            noti = None
        filtro = getattr(banco, "filtro_de_teste", None)
        if noti is not None and filtro:  # os alertas enviados aos e-mails de teste também ficam de fora
            ids = {a["id"] for a in assinantes if a.get("id")}
            noti = [n for n in noti if n["assinante_id"] in ids]
        numeros = numeros_do_dia(assinantes, noti, hoje, brevo_7_dias(os.environ["BREVO_API_KEY"]) if os.environ.get("BREVO_API_KEY") else None,
                                 eventos, filtro)
    depois = base_em(fim) or editais
    try:
        issues = issues_abertas(*gh)
    except requests.RequestException:
        issues = None
    fac_ant, ed_ant = base_em(fim_ant, "faculdades.json"), base_em(fim_ant)
    cob = cobertura_estados(faculdades, editais, hoje, carregar_emec())
    cob_ant = (cobertura_estados({f["id"]: f for f in fac_ant}, ed_ant, fim_ant, carregar_emec())
               if fac_ant is not None and ed_ant is not None else None)
    d = {"semana": (ini, fim), "numeros_do_dia": numeros, "cobertura": cob, "cobertura_ant": cob_ant, "gerado_em": tempo.agora().strftime("%d/%m/%Y %H:%M"),
         "eventos": somar_eventos(eventos, ini, fim) if eventos is not None else None,
         "eventos_ant": somar_eventos(eventos, ini_ant, fim_ant) if eventos is not None else None,
         "assinantes": contar_assinantes(assinantes, ini, fim) if assinantes is not None else None,
         "assinantes_ant": contar_assinantes(assinantes, ini_ant, fim_ant) if assinantes is not None else None,
         "origem": origem_dos_inscritos(assinantes, ini, fim) if assinantes is not None else None,
         "origem_ant": origem_dos_inscritos(assinantes, ini_ant, fim_ant) if assinantes is not None else None,
         "abertos_sem_conferir": abertos_sem_conferir(editais, hoje),
         "abertos_sem_conferir_ant": abertos_sem_conferir(ed_ant, fim_ant) if ed_ant is not None else None,
         "respostas_faculdades": respostas_das_faculdades(),
         "retorno": retorno_30_dias(assinantes, fim) if assinantes is not None else None,
         "curva": curva(eventos, assinantes, fim),
         "base": mudancas_da_base(base_em(fim_ant), depois, ini),
         "prazos": prazos_da_semana(editais, hoje), "conferir": conferir_em_aberto(editais, hoje),
         "issues": issues, "faltando": faltando, "guardiao": linha_do_guardiao(hoje.isoformat() if hasattr(hoje, "isoformat") else hoje)}
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
    hoje = date.fromisoformat(args.hoje) if args.hoje else tempo.agora().date()
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
