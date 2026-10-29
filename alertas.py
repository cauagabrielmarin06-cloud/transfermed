"""
Alertas por e-mail do Transfermed (roda no GitHub Actions a cada 30 minutos, ou na mão).

O que faz, nesta ordem:
  1. apaga cadastros que não confirmaram o e-mail em 7 dias (não guardar dado sem necessidade)
  2. envia o e-mail de confirmação para quem se cadastrou (dupla confirmação: ninguém cadastra o e-mail de outra pessoa)
  3. para cada alerta ativo, procura editais compatíveis com o perfil que ainda não foram avisados e envia um e-mail
Todo e-mail tem o link de descadastro, que apaga os dados (LGPD).

Configuração (segredos do GitHub):
  SUPABASE_URL, SUPABASE_SERVICE_KEY   banco dos alertas (plano grátis do Supabase)
  BREVO_API_KEY, REMETENTE_EMAIL        envio dos e-mails (plano grátis do Brevo: 300 por dia)
  REMETENTE_NOME (opcional), SITE_URL (opcional)
  CONTATO_DESTINO (opcional)            e-mail do dono que recebe o formulário de contato (sem ele, as mensagens esperam)
Sem essas variáveis, ou com --simular, nada sai do computador: o banco vira um arquivo local e os e-mails viram
arquivos .html em .trabalho/emails/ para conferência.
"""
import argparse
import json
import math
import os
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

import requests

import gerar_site
from gerar_site import MODALIDADES, fmt, dinheiro, publicavel, novo_detectado, situacao, slug_edital, vagas_texto

PASTA = Path(__file__).resolve().parent
SITE_URL = gerar_site.SITE_URL
LIMITE_DIARIO = 280            # o plano grátis do Brevo permite 300 e-mails por dia
DIAS_PARA_CONFIRMAR = 7
GENERICAS = {"universidade", "universitario", "universitaria", "centro", "faculdade", "faculdades", "escola", "instituto",
             "medicina", "ciencias", "saude", "campus", "de", "da", "do", "das", "dos", "e", "a", "o", "uni", "federal", "estadual"}


# ---------------------------------------------------------------- compatibilidade (mesma regra de docs/assets/app.js)

def norm(s):
    return "".join(c for c in unicodedata.normalize("NFKD", str(s or "")) if not unicodedata.combining(c)).lower().strip()


def km(a, b):
    r = math.radians
    h = math.sin(r(b[0] - a[0]) / 2) ** 2 + math.cos(r(a[0])) * math.cos(r(b[0])) * math.sin(r(b[1] - a[1]) / 2) ** 2
    return round(2 * 6371 * math.asin(math.sqrt(h)))


def mesma_faculdade(digitado, fac):
    q = norm(digitado)
    if not q:
        return False
    nome, sigla = norm(fac["nome"]), norm(fac["sigla"])
    if q in (sigla, nome):
        return True
    tokens = set(t for t in re.split(r"[^a-z0-9]+", nome) if t)
    sig = [t for t in re.split(r"[^a-z0-9]+", q) if len(t) >= 3 and t not in GENERICAS]
    return bool(sig) and all(t in tokens for t in sig)


def semestres_da_vaga(rotulo):
    txt = str(rotulo or "")
    nums = [int(n) for n in re.findall(r"\d+", txt)]
    if not nums:
        return None
    lista = nums
    if len(nums) >= 2 and re.search(r"\s(ao?|até)\s|[-–]", txt, re.I):
        lista = list(range(nums[0], nums[1] + 1))
    if re.search(r"s[ée]rie|ano", txt, re.I):
        lista = [s for n in lista for s in (2 * n - 1, 2 * n)]
    return lista


def motivos(ed, p, fac):
    """Lista de motivos pelos quais o edital NÃO serve para o perfil (vazia = atende aos requisitos)."""
    m = []
    mod = ed.get("modalidade") or "externa"
    mesma = mesma_faculdade(p.get("faculdade"), fac)
    if p.get("curso") == "saude":
        if mod in ("externa", "exterior"):
            m.append("exige estar cursando Medicina")
        if mod == "interna" and not mesma:
            m.append("interna de outra faculdade")
    else:
        if mod == "portador_diploma":
            m.append("para outro curso da saúde")
        if mod == "interna":
            m.append("interna")
    if p.get("origem") == "exterior" and ed.get("aceita_curso_exterior") is False:
        m.append("não aceita exterior")
    if p.get("origem") == "brasil" and mod == "exterior":
        m.append("só exterior")
    if p.get("transferiu") == "sim" and ed.get("exclui_quem_ja_transferiu") is True:
        m.append("não aceita quem já transferiu")
    if mesma and mod != "interna":
        m.append("é a faculdade atual")
    if p.get("tipo", "todas") != "todas" and fac.get("tipo"):
        if (p["tipo"] == "publica") != fac["tipo"].startswith("pública"):
            m.append("tipo")
    if p.get("curso") == "medicina" and mod in ("externa", "exterior") and ed.get("vagas") and p.get("semestre"):
        alvo = {p["semestre"], p["semestre"] + 1}
        com_vaga = [v for v in ed["vagas"] if v.get("vagas") != 0]
        if com_vaga and not any((semestres_da_vaga(v["semestre"]) is None) or (set(semestres_da_vaga(v["semestre"])) & alvo) for v in com_vaga):
            m.append("semestre sem vaga")
    if p.get("taxaMax") is not None and ed.get("taxa_inscricao") is not None and ed["taxa_inscricao"] > p["taxaMax"]:
        m.append("taxa acima do limite")
    if p.get("coords") and p.get("raio") and fac.get("lat") is not None and km(p["coords"], [fac["lat"], fac["lon"]]) > p["raio"]:
        m.append("distância")
    return m


def novidades(p, editais, faculdades, ja_avisados, hoje):
    """Editais vivos, compatíveis e ainda não avisados. Só vai por e-mail o que foi conferido no PDF e não tem ponto
    em aberto: edital "conferir" e edital só detectado pelo robô ficam no site, com aviso, mas nunca em e-mail."""
    itens = []
    for ed in editais:
        fac = faculdades.get(ed["faculdade_id"])
        if not fac or not publicavel(ed) or ed.get("status") == "conferir":
            continue
        if situacao(ed, hoje) in ("aberto", "em breve") and ed["id"] not in ja_avisados and not motivos(ed, p, fac):
            itens.append(("conferido", ed, fac))
    itens.sort(key=lambda t: t[1].get("inscricao_fim") or "9999")
    return itens


# ---------------------------------------------------------------- e-mails

ESTILO = "font-family:Arial,Helvetica,sans-serif;color:#1A1F1C;line-height:1.5"


def moldura(titulo, corpo_html, token):
    descad = f"{SITE_URL}/alerta/descadastrar/?t={token}"
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(titulo)}</title></head><body style="margin:0;background:#F7F5F1;padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#FFFFFF;border-radius:14px;{ESTILO}">
<tr><td style="background:#0F5C4D;border-radius:14px 14px 0 0;padding:18px 24px;color:#FFFFFF;font-size:18px;font-weight:bold">Transfermed
<div style="font-size:13px;font-weight:normal;color:#CFE8DF">Seu radar de transferência de Medicina</div></td></tr>
<tr><td style="padding:24px"><h1 style="font-size:20px;margin:0 0 12px">{escape(titulo)}</h1>{corpo_html}</td></tr>
<tr><td style="padding:16px 24px 24px;font-size:12px;color:#565B57;border-top:1px solid #E4E0D8">
Cada informação vem do edital oficial. Quem decide a vaga e o aproveitamento das matérias é sempre a faculdade.<br>
<a href="{descad}" style="color:#565B57">Cancelar os alertas e apagar meus dados</a> · <a href="{SITE_URL}/privacidade/" style="color:#565B57">Privacidade</a>
</td></tr></table></td></tr></table></body></html>"""


def resumo_perfil(p):
    partes = ["Medicina" if p.get("curso") == "medicina" else "outro curso da saúde",
              "no exterior" if p.get("origem") == "exterior" else "no Brasil"]
    if p.get("semestre"):
        partes.append(f"{p['semestre']}º semestre")
    if p.get("cidade"):
        partes.append(f"até {p['raio']} km de {p['cidade']}" if p.get("raio") else f"distâncias a partir de {p['cidade']}")
    if p.get("tipo") in ("publica", "particular"):
        partes.append("só faculdades públicas" if p["tipo"] == "publica" else "só faculdades particulares")
    return ", ".join(partes)


def email_confirmacao(assinante):
    link = f"{SITE_URL}/alerta/confirmar/?t={assinante['token']}"
    corpo = f"""<p>Recebemos um pedido para enviar alertas de editais de transferência de Medicina para este e-mail.</p>
<p><a href="{link}" style="display:inline-block;background:#0F5C4D;color:#FFFFFF;text-decoration:none;padding:12px 20px;border-radius:10px;font-weight:bold">Confirmar meus alertas</a></p>
<p style="font-size:14px;color:#565B57">Perfil: {escape(resumo_perfil(assinante['perfil']))}.<br>
Se não foi você, ignore este e-mail: sem a confirmação, o cadastro é apagado em {DIAS_PARA_CONFIRMAR} dias.</p>"""
    texto = (f"Confirme seus alertas do Transfermed: {link}\n\nSe não foi você, ignore: o cadastro é apagado em {DIAS_PARA_CONFIRMAR} dias.\n"
             f"Cancelar e apagar dados: {SITE_URL}/alerta/descadastrar/?t={assinante['token']}")
    return "Confirme seus alertas de transferência de Medicina", moldura("Falta só confirmar", corpo, assinante["token"]), texto


def email_alerta(assinante, itens, hoje):
    blocos, linhas_txt = [], []
    for tipo, ed, fac in itens:
        if tipo == "conferido":
            cls, prazo = gerar_site.texto_situacao(ed, hoje)
            cor = {"alerta": "#B42318", "aviso": "#7A4D00"}.get(cls, "#17694F")
            nome_mod = MODALIDADES.get(ed.get("modalidade"), MODALIDADES["externa"])[0]
            taxa = "" if ed.get("taxa_inscricao") is None else (" · inscrição gratuita" if ed["taxa_inscricao"] == 0 else f" · taxa {dinheiro(ed['taxa_inscricao'])}")
            pagina = f"{SITE_URL}/edital/{slug_edital(ed)}/"
            aviso = '<br><span style="color:#7A4D00">Atenção: o edital tem um ponto a confirmar (veja o resumo).</span>' if ed.get("status") == "conferir" else ""
            blocos.append(f"""<div style="border:1px solid #E4E0D8;border-radius:12px;padding:14px 16px;margin:0 0 12px">
<strong>{escape(fac['nome'])}</strong><br><span style="font-size:14px;color:#565B57">{escape(fac['cidade'])}/{escape(fac['uf'])} · {escape(nome_mod)}{' · ingresso ' + escape(ed['semestre_ingresso']) if ed.get('semestre_ingresso') else ''}</span><br>
<span style="font-weight:bold;color:{cor}">{escape(prazo)}</span><span style="font-size:14px">{escape(taxa)} · {escape(vagas_texto(ed))}</span>{aviso}<br>
<a href="{pagina}" style="color:#17694F">Ver resumo e documentos</a> · <a href="{escape(ed['url_edital'])}" style="color:#17694F">Edital oficial</a></div>""")
            linhas_txt.append(f"- {fac['nome']}: {prazo}. {pagina}")
        else:
            blocos.append(f"""<div style="border:1px dashed #E8A33D;border-radius:12px;padding:14px 16px;margin:0 0 12px">
<strong>{escape(fac['nome'])}</strong><br><span style="font-size:14px;color:#565B57">{escape(fac['cidade'])}/{escape(fac['uf'])}</span><br>
<span style="color:#7A4D00;font-weight:bold">Novo edital detectado em {fmt(ed['detectado_em'])}</span> · <span style="font-size:14px">dados ainda não conferidos: veja no PDF se serve para você</span><br>
<a href="{escape(ed['url_edital'])}" style="color:#17694F">Abrir edital oficial</a></div>""")
            linhas_txt.append(f"- {fac['nome']}: novo edital detectado (dados ainda não conferidos). {ed['url_edital']}")
    n = len(itens)
    assunto = f"{n} {'edital' if n == 1 else 'editais'} de transferência para o seu perfil" if n > 1 else f"Edital de transferência: {itens[0][2]['sigla']}"
    corpo = (f"<p>Encontramos {'um edital' if n == 1 else f'{n} editais'} que combina{'' if n == 1 else 'm'} com o seu perfil "
             f"({escape(resumo_perfil(assinante['perfil']))}).</p>{''.join(blocos)}"
             f"<p style=\"font-size:14px\"><a href=\"{SITE_URL}/diagnostico/\" style=\"color:#17694F\">Ver meu diagnóstico completo</a></p>")
    texto = "Editais para o seu perfil:\n" + "\n".join(linhas_txt) + f"\n\nCancelar e apagar dados: {SITE_URL}/alerta/descadastrar/?t={assinante['token']}"
    return assunto, moldura("Novidades no seu radar", corpo, assinante["token"]), texto


MOTIVOS_CONTATO = dict(gerar_site.MOTIVOS_CONTATO)
PRAZOS_CONTATO = {"proximo-edital": "no próximo edital aberto", "6-meses": "nos próximos 6 meses", "1-ano": "em até 1 ano",
                  "pesquisando": "ainda pesquisando"}


def moldura_simples(titulo, corpo_html):
    """Moldura dos e-mails que não são alerta (contato): sem link de descadastro, porque não há cadastro."""
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(titulo)}</title></head><body style="margin:0;background:#F7F5F1;padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;background:#FFFFFF;border-radius:14px;{ESTILO}">
<tr><td style="background:#0F5C4D;border-radius:14px 14px 0 0;padding:18px 24px;color:#FFFFFF;font-size:18px;font-weight:bold">Transfermed</td></tr>
<tr><td style="padding:24px"><h1 style="font-size:20px;margin:0 0 12px">{escape(titulo)}</h1>{corpo_html}</td></tr>
<tr><td style="padding:16px 24px 24px;font-size:12px;color:#565B57;border-top:1px solid #E4E0D8">
Você recebeu este e-mail porque escreveu pelo formulário de contato do Transfermed. Quem decide a vaga é a faculdade.<br>
<a href="{SITE_URL}/privacidade/" style="color:#565B57">Privacidade</a></td></tr></table></body></html>"""


def email_contato_dono(m):
    d = m["dados"]
    campos = [("Nome", d.get("nome")), ("E-mail", d.get("email")), ("Motivo", MOTIVOS_CONTATO.get(d.get("motivo"), d.get("motivo"))),
              ("Estuda", "no exterior" if d.get("origem") == "exterior" else "no Brasil"), ("Faculdade", d.get("faculdade")),
              ("Semestre", d.get("semestre")), ("Estados de interesse", d.get("estados")),
              ("Prazo desejado", PRAZOS_CONTATO.get(d.get("prazo"), d.get("prazo")))]
    linhas = "".join(f"<tr><td style=\"padding:4px 12px 4px 0;color:#565B57\">{k}</td><td>{escape(str(v))}</td></tr>" for k, v in campos if v)
    corpo = f"<table>{linhas}</table><p style=\"white-space:pre-wrap\">{escape(d.get('mensagem', ''))}</p><p style=\"font-size:13px;color:#565B57\">Responda este e-mail para falar direto com a pessoa.</p>"
    texto = "\n".join(f"{k}: {v}" for k, v in campos if v) + "\n\n" + d.get("mensagem", "")
    assunto = f"[Contato · {MOTIVOS_CONTATO.get(d.get('motivo'), 'mensagem')}] {d.get('nome', '')[:60]}"
    return assunto, moldura_simples("Nova mensagem pelo site", corpo), texto


def email_contato_resposta(m):
    corpo = (f"<p>Olá, {escape(m['dados'].get('nome', '').split(' ')[0])}.</p>"
             "<p>Recebi sua mensagem. Respondo em até 3 dias úteis. Enquanto isso, ative o alerta para ser avisado quando abrir edital para o seu perfil.</p>"
             f"<p><a href=\"{SITE_URL}/diagnostico/\" style=\"display:inline-block;background:#0F5C4D;color:#FFFFFF;text-decoration:none;padding:12px 20px;border-radius:10px;font-weight:bold\">Receber aviso de editais para o meu perfil</a></p>"
             "<p>Cauã, do Transfermed</p>")
    texto = ("Recebi sua mensagem. Respondo em até 3 dias úteis. Enquanto isso, ative o alerta para ser avisado quando abrir "
             f"edital para o seu perfil: {SITE_URL}/diagnostico/\n\nCauã, do Transfermed")
    return "Recebi sua mensagem", moldura_simples("Recebi sua mensagem", corpo), texto


def encaminhar_contato(banco, envio, destino, agora):
    """Mensagens novas do formulário: uma cópia para o dono (responder vai direto para a pessoa) e a resposta
    automática. Encaminhadas há mais de 90 dias são apagadas (o que a página de privacidade promete)."""
    feitos = 0
    # data com "Z", não "+00:00": na URL do Supabase o "+" vira espaço e a consulta é recusada
    banco.apagar_mensagens_antigas((agora - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    if not destino:
        return feitos
    for m in banco.mensagens_pendentes():
        try:
            envio.enviar(destino, *email_contato_dono(m), None, responder_para=m["dados"].get("email"))
            envio.enviar(m["dados"]["email"], *email_contato_resposta(m), None)
        except requests.RequestException:
            break  # tenta de novo na próxima rodada
        banco.marcar_encaminhada(m["id"], agora.isoformat())
        feitos += 1
    return feitos


# ---------------------------------------------------------------- banco e envio

class BancoSupabase:
    def __init__(self, url, chave):
        self.url = url.rstrip("/") + "/rest/v1"
        self.h = {"apikey": chave, "Content-Type": "application/json"}
        if chave.startswith("eyJ"):  # chave antiga (JWT) também vai no Authorization; as novas (sb_secret_...) só no apikey
            self.h["Authorization"] = f"Bearer {chave}"

    def _req(self, metodo, caminho, **kw):
        r = requests.request(metodo, self.url + caminho, headers={**self.h, **kw.pop("headers", {})}, timeout=30, **kw)
        r.raise_for_status()
        return r.json() if r.text else None

    def assinantes(self):
        return self._req("GET", "/assinantes?select=id,email,perfil,token,status,criado_em,confirmacao_enviada_em")

    def marcar_confirmacao_enviada(self, ident, quando):
        self._req("PATCH", f"/assinantes?id=eq.{ident}", json={"confirmacao_enviada_em": quando})

    def apagar(self, ident):
        self._req("DELETE", f"/assinantes?id=eq.{ident}")

    def avisados(self, ident):
        return {n["edital_id"] for n in self._req("GET", f"/notificacoes?select=edital_id&assinante_id=eq.{ident}")}

    def registrar_avisos(self, ident, ids):
        self._req("POST", "/notificacoes", json=[{"assinante_id": ident, "edital_id": i} for i in ids],
                  headers={"Prefer": "resolution=ignore-duplicates"})

    def mensagens_pendentes(self):
        return self._req("GET", "/mensagens?select=id,dados,criado_em&encaminhada_em=is.null&order=criado_em")

    def marcar_encaminhada(self, ident, quando):
        self._req("PATCH", f"/mensagens?id=eq.{ident}", json={"encaminhada_em": quando})

    def apagar_mensagens_antigas(self, antes_de):
        self._req("DELETE", f"/mensagens?encaminhada_em=lt.{antes_de}")

    def enviados_hoje(self, hoje):
        n = self._req("GET", f"/notificacoes?select=assinante_id&enviado_em=gte.{hoje}")
        c = self._req("GET", f"/assinantes?select=id&confirmacao_enviada_em=gte.{hoje}")
        return len({x["assinante_id"] for x in n}) + len(c)


class BancoSimulado:
    """Arquivo local no lugar do Supabase (para testar sem conta)."""

    def __init__(self, caminho):
        self.caminho = Path(caminho)
        self.d = json.loads(self.caminho.read_text(encoding="utf-8")) if self.caminho.exists() else {"assinantes": [], "notificacoes": []}
        self.d.setdefault("mensagens", [])

    def _salvar(self):
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho.write_text(json.dumps(self.d, ensure_ascii=False, indent=1), encoding="utf-8")

    def assinantes(self):
        return list(self.d["assinantes"])

    def marcar_confirmacao_enviada(self, ident, quando):
        for a in self.d["assinantes"]:
            if a["id"] == ident:
                a["confirmacao_enviada_em"] = quando
        self._salvar()

    def apagar(self, ident):
        self.d["assinantes"] = [a for a in self.d["assinantes"] if a["id"] != ident]
        self.d["notificacoes"] = [n for n in self.d["notificacoes"] if n["assinante_id"] != ident]
        self._salvar()

    def avisados(self, ident):
        return {n["edital_id"] for n in self.d["notificacoes"] if n["assinante_id"] == ident}

    def registrar_avisos(self, ident, ids):
        agora = datetime.now(timezone.utc).isoformat()
        ja = self.avisados(ident)
        self.d["notificacoes"] += [{"assinante_id": ident, "edital_id": i, "enviado_em": agora} for i in ids if i not in ja]
        self._salvar()

    def mensagens_pendentes(self):
        return [m for m in self.d["mensagens"] if not m.get("encaminhada_em")]

    def marcar_encaminhada(self, ident, quando):
        for m in self.d["mensagens"]:
            if m["id"] == ident:
                m["encaminhada_em"] = quando
        self._salvar()

    def apagar_mensagens_antigas(self, antes_de):
        self.d["mensagens"] = [m for m in self.d["mensagens"] if not m.get("encaminhada_em") or m["encaminhada_em"] >= antes_de]
        self._salvar()

    def enviados_hoje(self, hoje):
        n = {x["assinante_id"] for x in self.d["notificacoes"] if x["enviado_em"] >= hoje}
        c = [a for a in self.d["assinantes"] if (a.get("confirmacao_enviada_em") or "") >= hoje]
        return len(n) + len(c)


class EnvioBrevo:
    def __init__(self, chave, remetente, nome):
        self.chave, self.remetente, self.nome = chave, remetente, nome

    def manter_ativa(self):
        """A chave do Brevo expira após 90 dias sem uso: uma consulta leve por dia (sem enviar nada) a mantém ativa."""
        try:
            r = requests.get("https://api.brevo.com/v3/smtp/statistics/aggregatedReport", params={"days": 1}, timeout=30,
                             headers={"api-key": self.chave, "accept": "application/json"})
            return r.status_code  # 200 = chave válida; 401 = chave vencida ou errada
        except requests.RequestException:
            return None

    def enviar(self, para, assunto, html, texto, token, responder_para=None):
        corpo = {"sender": {"email": self.remetente, "name": self.nome}, "to": [{"email": para}], "subject": assunto,
                 "htmlContent": html, "textContent": texto}
        if token:
            corpo["headers"] = {"List-Unsubscribe": f"<{SITE_URL}/alerta/descadastrar/?t={token}>"}
        if responder_para:
            corpo["replyTo"] = {"email": responder_para}
        r = requests.post("https://api.brevo.com/v3/smtp/email", timeout=30, headers={"api-key": self.chave, "Content-Type": "application/json"},
                          json=corpo)
        r.raise_for_status()


class EnvioSimulado:
    """Grava os e-mails em arquivos .html em vez de enviar."""

    def __init__(self, pasta):
        self.pasta = Path(pasta)
        self.enviados = []

    def enviar(self, para, assunto, html, texto, token, responder_para=None):
        self.pasta.mkdir(parents=True, exist_ok=True)
        nome = f"{len(list(self.pasta.glob('*.html'))) + 1:03d}-{re.sub(r'[^a-z0-9]+', '-', para.lower())}.html"
        (self.pasta / nome).write_text(html.replace("<title>", f"<!-- Para: {para} | Assunto: {assunto} --><title>", 1), encoding="utf-8")
        self.enviados.append((para, assunto))


# ---------------------------------------------------------------- execução

def rodar(banco, envio, editais, faculdades, hoje=None, agora=None):
    hoje = hoje or date.today().isoformat()
    agora = agora or datetime.now(timezone.utc)
    resumo = {"apagados_sem_confirmar": 0, "confirmacoes": 0, "alertas": 0, "itens_avisados": 0, "parou_no_limite": False,
              "pendentes": 0, "ativos": 0, "falhas_envio": []}
    restante = LIMITE_DIARIO - banco.enviados_hoje(hoje)
    assinantes = banco.assinantes()
    # só contagens no registro: o log do GitHub Actions é público, nunca imprimir e-mails
    resumo["pendentes"] = sum(1 for a in assinantes if a["status"] == "pendente")
    resumo["ativos"] = len(assinantes) - resumo["pendentes"]

    def enviar(a, assunto, html, texto):
        """Um envio que falha não trava os outros; o erro fica no resumo (sem o e-mail) e o workflow fica vermelho."""
        try:
            envio.enviar(a["email"], assunto, html, texto, a["token"])
            return True
        except requests.RequestException as erro:
            r = getattr(erro, "response", None)
            codigo = None
            if r is not None:
                try:
                    codigo = r.json().get("code")
                except ValueError:
                    pass
            resumo["falhas_envio"].append({"http": getattr(r, "status_code", None), "codigo": codigo or type(erro).__name__})
            return False

    for a in assinantes:
        if len(resumo["falhas_envio"]) >= 3:
            break  # chave inválida ou Brevo fora do ar: não adianta insistir nesta rodada
        criado = datetime.fromisoformat(a["criado_em"].replace("Z", "+00:00"))
        if a["status"] == "pendente":
            if agora - criado > timedelta(days=DIAS_PARA_CONFIRMAR):
                banco.apagar(a["id"])
                resumo["apagados_sem_confirmar"] += 1
                continue
            ultima = a.get("confirmacao_enviada_em")
            if ultima and agora - datetime.fromisoformat(ultima.replace("Z", "+00:00")) < timedelta(hours=24):
                continue
            if restante <= 0:
                resumo["parou_no_limite"] = True
                break
            if not enviar(a, *email_confirmacao(a)):
                continue
            banco.marcar_confirmacao_enviada(a["id"], agora.isoformat())
            resumo["confirmacoes"] += 1
            restante -= 1
            continue

        itens = novidades(a["perfil"], editais, faculdades, banco.avisados(a["id"]), hoje)
        if not itens:
            continue
        if restante <= 0:
            resumo["parou_no_limite"] = True
            break
        if not enviar(a, *email_alerta(a, itens, hoje)):
            continue
        banco.registrar_avisos(a["id"], [ed["id"] if t == "conferido" else f"novo:{ed['id']}" for t, ed, _ in itens])
        resumo["alertas"] += 1
        resumo["itens_avisados"] += len(itens)
        restante -= 1
    return resumo


def main():
    ap = argparse.ArgumentParser(description="Envia confirmações e alertas por e-mail.")
    ap.add_argument("--simular", action="store_true", help="não usa Supabase nem Brevo: banco em arquivo e e-mails em .html")
    args = ap.parse_args()
    faculdades = {f["id"]: f for f in json.loads((PASTA / "data" / "faculdades.json").read_text(encoding="utf-8"))}
    editais = json.loads((PASTA / "data" / "editais.json").read_text(encoding="utf-8"))

    configurado = all(os.environ.get(v) for v in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "BREVO_API_KEY", "REMETENTE_EMAIL"))
    if not args.simular and not configurado:
        print("Alertas ainda não configurados (faltam os segredos do Supabase/Brevo). Nada a fazer.")
        return 0
    if args.simular:
        banco = BancoSimulado(PASTA / ".trabalho" / "simulacao" / "banco.json")
        envio = EnvioSimulado(PASTA / ".trabalho" / "emails")
    else:
        banco = BancoSupabase(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
        envio = EnvioBrevo(os.environ["BREVO_API_KEY"], os.environ["REMETENTE_EMAIL"], os.environ.get("REMETENTE_NOME", "Transfermed"))
    resumo = rodar(banco, envio, editais, faculdades)
    try:
        resumo["contatos_encaminhados"] = encaminhar_contato(banco, envio, os.environ.get("CONTATO_DESTINO", ""), datetime.now(timezone.utc))
    except requests.RequestException as erro:  # ex.: tabela "mensagens" ainda não criada no Supabase
        resumo["contatos_encaminhados"] = None
        resumo["contato_erro_http"] = getattr(getattr(erro, "response", None), "status_code", type(erro).__name__)
    if hasattr(envio, "manter_ativa"):
        # toda rodada (o GitHub atrasa os agendamentos, então "uma vez às 9h" podia nunca acontecer);
        # mantém a chave ativa e mostra no registro se ela ainda vale
        resumo["brevo_consulta_http"] = envio.manter_ativa()  # 200 = chave aceita
    print(json.dumps(resumo, ensure_ascii=False))
    if resumo["falhas_envio"]:
        print("Falha ao enviar e-mails: confira a chave BREVO_API_KEY e o remetente no Brevo.")
        return 1  # workflow vermelho: o GitHub avisa o dono do repositório por e-mail
    return 0


if __name__ == "__main__":
    sys.exit(main())
