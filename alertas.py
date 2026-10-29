"""
Alertas por e-mail do Transfermed (roda no GitHub Actions a cada 30 minutos, ou na mão).

O que faz, nesta ordem:
  1. apaga cadastros que não confirmaram o e-mail em 7 dias (não guardar dado sem necessidade)
  2. envia o e-mail de confirmação para quem se cadastrou (dupla confirmação: ninguém cadastra o e-mail de outra pessoa)
  3. para cada alerta ativo, procura editais compatíveis com o perfil que ainda não foram avisados e envia um e-mail
  4. e-mails novos (nutricao.py): avisos das faculdades seguidas, boas-vindas com o checklist, dicas dos dias 2 a 14,
     lembretes 7 e 2 dias antes do prazo e resumo de segunda. Só saem de verdade com a variável ALERTAS_ATIVOS=1;
     sem ela rodam em simulação: são montados e contados, mas não enviados nem registrados no banco.
Todo e-mail tem o link de descadastro, que apaga os dados (LGPD).

Configuração (segredos do GitHub):
  SUPABASE_URL, SUPABASE_SERVICE_KEY   banco dos alertas (plano grátis do Supabase)
  BREVO_API_KEY, REMETENTE_EMAIL        envio dos e-mails (plano grátis do Brevo: 300 por dia)
  REMETENTE_NOME (opcional), SITE_URL (opcional)
  CONTATO_DESTINO (opcional)            e-mail do dono que recebe o formulário de contato (sem ele, as mensagens esperam)
  ALERTAS_ATIVOS (variável, opcional)   "1" liga os e-mails novos do item 4; sem ela, só simulação
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
import uuid
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

import requests

import gerar_site
import nutricao
from gerar_site import publicavel, situacao

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
    em aberto no prazo: edital com prazo final (ou o edital inteiro) a conferir e edital só detectado pelo robô ficam
    no site, com aviso, mas nunca em e-mail. Campo duvidoso que não é o prazo vai com o aviso ao lado.
    Quem se inscreveu só para seguir faculdades (perfil sem curso) não recebe o alerta geral."""
    itens = []
    if not p.get("curso"):
        return itens
    for ed in editais:
        fac = faculdades.get(ed["faculdade_id"])
        if not fac or not publicavel(ed) or gerar_site.fora_dos_emails(ed):
            continue
        if situacao(ed, hoje) in ("aberto", "em breve") and ed["id"] not in ja_avisados and not motivos(ed, p, fac):
            itens.append(("conferido", ed, fac))
    itens.sort(key=lambda t: t[1].get("inscricao_fim") or "9999")
    return itens


# ---------------------------------------------------------------- e-mails (montados no nutricao.py)

seguidas = nutricao.seguidas
resumo_perfil = nutricao.resumo_perfil


def novidades_seguidas(p, editais, faculdades, ja_avisados, hoje):
    """Editais conferidos e vivos das faculdades que a pessoa segue ("Avise-me quando abrir"). Vale o pedido explícito:
    distância, tipo e taxa não filtram; continuam valendo as regras do edital (modalidade, exterior, quem já transferiu)."""
    ignorar = {"distância", "tipo", "taxa acima do limite"}
    base = {k: v for k, v in (p or {}).items() if k != "seguir"}
    base.setdefault("curso", "medicina")
    itens = []
    for ed in editais:
        fac = faculdades.get(ed["faculdade_id"])
        if not fac or fac["id"] not in seguidas(p) or not publicavel(ed) or gerar_site.fora_dos_emails(ed):
            continue
        if situacao(ed, hoje) in ("aberto", "em breve") and ed["id"] not in ja_avisados and not set(motivos(ed, base, fac)) - ignorar:
            itens.append(("conferido", ed, fac))
    itens.sort(key=lambda t: t[1].get("inscricao_fim") or "9999")
    return itens


def email_confirmacao(assinante):
    return nutricao.confirmacao(assinante, SITE_URL, DIAS_PARA_CONFIRMAR)


def email_alerta(assinante, itens, hoje):
    ctx = nutricao.Contexto([ed for _, ed, _ in itens], {fac["id"]: fac for _, _, fac in itens}, SITE_URL, hoje)
    return nutricao.alerta(assinante, ctx, [(ed, fac) for _, ed, fac in itens])


def email_novo(assinante, assunto, titulo, corpo):
    return nutricao.finalizar(assinante, SITE_URL, assunto, titulo, corpo)


ESTILO = nutricao.ESTILO
MOTIVOS_CONTATO = dict(gerar_site.MOTIVOS_CONTATO)


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
    motivo = MOTIVOS_CONTATO.get(d.get("assunto") or d.get("motivo"), d.get("motivo"))  # "assunto": banco com a lista antiga
    campos = [("Nome", d.get("nome")), ("E-mail", d.get("email")), ("Motivo", motivo),
              ("Estuda", "no exterior" if d.get("origem") == "exterior" else "no Brasil"), ("Faculdade", d.get("faculdade")),
              ("Semestre", d.get("semestre"))]
    linhas = "".join(f"<tr><td style=\"padding:4px 12px 4px 0;color:#565B57\">{k}</td><td>{escape(str(v))}</td></tr>" for k, v in campos if v)
    corpo = f"<table>{linhas}</table><p style=\"white-space:pre-wrap\">{escape(d.get('mensagem', ''))}</p><p style=\"font-size:13px;color:#565B57\">Responda este e-mail para falar direto com a pessoa.</p>"
    texto = "\n".join(f"{k}: {v}" for k, v in campos if v) + "\n\n" + d.get("mensagem", "")
    assunto = f"[Contato · {motivo or 'mensagem'}] {d.get('nome', '')[:60]}"
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
        base = "id,email,perfil,token,status,criado_em,confirmacao_enviada_em,confirmado_em,consentimento_texto"
        try:
            return self._req("GET", f"/assinantes?select={base},atualizacao_pendente")
        except requests.HTTPError:  # schema.sql antigo (sem a coluna): segue sem o aviso de alerta atualizado
            return self._req("GET", f"/assinantes?select={base}")

    def marcar_atualizacao_avisada(self, ident, quando):
        self._req("PATCH", f"/assinantes?id=eq.{ident}", json={"atualizacao_pendente": False, "atualizacao_avisada_em": quando})

    def marcar_confirmacao_enviada(self, ident, quando):
        self._req("PATCH", f"/assinantes?id=eq.{ident}", json={"confirmacao_enviada_em": quando})

    def apagar(self, ident):
        self._req("DELETE", f"/assinantes?id=eq.{ident}")

    def avisados(self, ident):
        return {n["edital_id"] for n in self._req("GET", f"/notificacoes?select=edital_id&assinante_id=eq.{ident}")}

    def registrar_avisos(self, ident, ids, quando=None):  # o banco grava a hora (enviado_em = now())
        self._req("POST", "/notificacoes", json=[{"assinante_id": ident, "edital_id": i} for i in ids],
                  headers={"Prefer": "resolution=ignore-duplicates"})

    def mensagens_pendentes(self):
        return self._req("GET", "/mensagens?select=id,dados,criado_em&encaminhada_em=is.null&order=criado_em")

    def marcar_encaminhada(self, ident, quando):
        self._req("PATCH", f"/mensagens?id=eq.{ident}", json={"encaminhada_em": quando})

    def apagar_mensagens_antigas(self, antes_de):
        self._req("DELETE", f"/mensagens?encaminhada_em=lt.{antes_de}")

    def receberam_hoje(self, hoje):
        """Quem já recebeu algum e-mail hoje (além da confirmação)."""
        return {x["assinante_id"] for x in self._req("GET", f"/notificacoes?select=assinante_id&enviado_em=gte.{hoje}")}

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

    def inscrever(self, email, perfil, consentimento, agora=None):
        """Mesma regra da função inscrever do supabase/schema.sql (usada na inscrição de teste)."""
        agora = (agora or datetime.now(timezone.utc)).isoformat()
        email = email.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", email) or len(email) > 200:
            return "email_invalido"
        if not isinstance(perfil, dict) or len(json.dumps(perfil)) > 2000:
            return "perfil_invalido"
        if not consentimento or len(consentimento) < 20:
            return "sem_consentimento"
        atual = next((a for a in self.d["assinantes"] if a["email"] == email), None)
        if atual:
            velho = atual["perfil"]
            novo = {k: v for k, v in (perfil if "curso" in perfil else {**velho, **perfil}).items() if k != "seguir"}
            novo["seguir"] = {k: sorted(set((velho.get("seguir") or {}).get(k, [])) | set((perfil.get("seguir") or {}).get(k, [])))
                              for k in ("faculdades", "lembretes")}
            atual.update(perfil=novo, consentimento_texto=consentimento, consentimento_em=agora)
            if atual["status"] == "ativo":
                atual["atualizacao_pendente"] = True
            else:
                atual["confirmacao_enviada_em"] = None  # pediu de novo: reenvia a confirmação na hora
            self._salvar()
            return "atualizado" if atual["status"] == "ativo" else "pendente"
        self.d["assinantes"].append({"id": str(uuid.uuid4()), "email": email, "perfil": perfil, "token": str(uuid.uuid4()),
                                     "status": "pendente", "consentimento_texto": consentimento, "consentimento_em": agora,
                                     "confirmacao_enviada_em": None, "confirmado_em": None, "criado_em": agora})
        self._salvar()
        return "pendente"

    def marcar_atualizacao_avisada(self, ident, quando):
        for a in self.d["assinantes"]:
            if a["id"] == ident:
                a.update(atualizacao_pendente=False, atualizacao_avisada_em=quando)
        self._salvar()

    def confirmar(self, token, agora=None):
        for a in self.d["assinantes"]:
            if a["token"] == token:
                a["status"] = "ativo"
                a["confirmado_em"] = a.get("confirmado_em") or (agora or datetime.now(timezone.utc)).isoformat()
                self._salvar()
                return "ok"
        return "nao_encontrado"

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

    def registrar_avisos(self, ident, ids, quando=None):
        agora = quando or datetime.now(timezone.utc).isoformat()
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

    def receberam_hoje(self, hoje):
        return {x["assinante_id"] for x in self.d["notificacoes"] if x["enviado_em"] >= hoje}

    def enviados_hoje(self, hoje):
        n = {x["assinante_id"] for x in self.d["notificacoes"] if x["enviado_em"] >= hoje}
        c = [a for a in self.d["assinantes"] if (a.get("confirmacao_enviada_em") or "") >= hoje]
        return len(n) + len(c)


def cabecalhos_descadastro(token, um_clique=None):
    """List-Unsubscribe dos alertas. Com `um_clique` (endereço da Edge Function supabase/functions/descadastrar),
    vale o descadastro em um clique do próprio programa de e-mail (RFC 8058, exigido por Gmail e Yahoo); sem ela, o
    endereço é a página do site."""
    if um_clique:
        return {"List-Unsubscribe": f"<{um_clique}?t={token}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}
    return {"List-Unsubscribe": f"<{SITE_URL}/alerta/descadastrar/?t={token}>"}


class EnvioBrevo:
    def __init__(self, chave, remetente, nome, um_clique=None):
        self.chave, self.remetente, self.nome, self.um_clique = chave, remetente, nome, um_clique

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
            corpo["headers"] = cabecalhos_descadastro(token, self.um_clique)
        if responder_para:
            corpo["replyTo"] = {"email": responder_para}
        r = requests.post("https://api.brevo.com/v3/smtp/email", timeout=30, headers={"api-key": self.chave, "Content-Type": "application/json"},
                          json=corpo)
        r.raise_for_status()


class EnvioContador:
    """Simulação no GitHub Actions: só conta (o registro é público; nenhum e-mail ou conteúdo é impresso)."""
    def __init__(self):
        self.enviados = []

    def enviar(self, para, assunto, html, texto, token, responder_para=None):
        self.enviados.append(assunto)


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

def rodar(banco, envio, editais, faculdades, hoje=None, agora=None, novos_ativos=False, envio_teste=None):
    """novos_ativos=False (padrão, sem ALERTAS_ATIVOS): os e-mails novos vão para envio_teste e não são registrados."""
    hoje = hoje or date.today().isoformat()
    agora = agora or datetime.now(timezone.utc)
    resumo = {"apagados_sem_confirmar": 0, "confirmacoes": 0, "alertas": 0, "itens_avisados": 0, "parou_no_limite": False,
              "pendentes": 0, "ativos": 0, "falhas_envio": [], "novos_ativos": novos_ativos,
              "novos": {t: 0 for t in PRIORIDADE if t != "alerta"}, "simulados": {t: 0 for t in PRIORIDADE}}
    ctx = nutricao.Contexto(editais, faculdades, SITE_URL, hoje)
    envio_teste = envio_teste or EnvioContador()
    restante = LIMITE_DIARIO - banco.enviados_hoje(hoje)
    assinantes = banco.assinantes()
    receberam_hoje = banco.receberam_hoje(hoje)
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

        if a.get("atualizacao_pendente"):  # pediu de novo no site já estando ativo: aviso na hora (como a confirmação)
            email = email_novo(a, *nutricao.atualizacao(a, ctx))
            if not novos_ativos:
                envio_teste.enviar(a["email"], *email, a["token"])
            elif enviar(a, *email):
                banco.marcar_atualizacao_avisada(a["id"], agora.isoformat())
                resumo["atualizacoes"] = resumo.get("atualizacoes", 0) + 1
        if a["id"] in receberam_hoje:
            continue  # no máximo 1 e-mail por pessoa por dia (a confirmação não conta); o resto espera a vez
        ja = banco.avisados(a["id"])
        geral = novidades(a["perfil"], editais, faculdades, ja, hoje)
        plano = planejar(a, ctx, ja, editais, faculdades, hoje, agora, geral)
        if novos_ativos:
            escolha = plano[0] if plano else None
        else:
            # simulação: conta o que sairia com ALERTAS_ATIVOS; de verdade, só o alerta de editais de sempre
            if plano:
                envio_teste.enviar(a["email"], *plano[0][1], a["token"])
                resumo["simulados"][plano[0][0]] += 1
            escolha = ("alerta", email_alerta(a, geral, hoje), [ed["id"] for _, ed, _ in geral]) if geral else None
        if not escolha:
            continue
        if restante <= 0:
            resumo["parou_no_limite"] = True
            break
        tipo, (assunto, html, texto), chaves = escolha
        if enviar(a, assunto, html, texto):
            banco.registrar_avisos(a["id"], chaves, agora.isoformat())
            receberam_hoje.add(a["id"])
            restante -= 1
            if tipo == "alerta":
                resumo["alertas"] += 1
                resumo["itens_avisados"] += len(chaves)
            else:
                resumo["novos"][tipo] += 1
    return resumo


# prioridade quando vence mais de um e-mail no mesmo dia (só sai um; os outros têm janela e saem nos dias seguintes;
# o resumo que perde a vez fica para o dia seguinte, e o que cai junto com um lembrete vai no mesmo e-mail)
PRIORIDADE = {"lembrete_perto": 0, "boas_vindas": 1, "alerta": 2, "lembrete_longe": 3, "resumo_semanal": 4, "sequencia": 5}


def planejar(a, ctx, ja, editais, faculdades, hoje, agora, geral):
    """[(tipo, (assunto, html, texto), chaves a registrar)] que vencem hoje, do mais importante para o menos.
    As chaves vão para a tabela de notificações ("seq:2", "lembrete7:<edital>", "resumo:2026-11-02", id do edital)
    e impedem repetição. No dia da confirmação, as boas-vindas levam os editais do perfil: não sai alerta separado."""
    p = a.get("perfil") or {}
    vistos = {ed["id"] for _, ed, _ in geral}
    itens = geral + [x for x in novidades_seguidas(p, editais, faculdades, ja, hoje) if x[1]["id"] not in vistos]
    pares = [(ed, fac) for _, ed, fac in itens]
    saida = []
    passo = nutricao.passo_devido(a, hoje, ja)
    if passo == 0:
        saida.append(("boas_vindas", email_novo(a, *nutricao.boas_vindas(a, ctx, pares)), ["seq:0"] + [ed["id"] for ed, _ in pares]))
    elif itens:
        saida.append(("alerta", nutricao.alerta(a, ctx, pares), [ed["id"] for ed, _ in pares]))
    if passo not in (None, 0):
        saida.append(("sequencia", email_novo(a, *nutricao.PASSOS[passo](a, ctx)), [f"seq:{passo}"]))
    resumo = None
    if nutricao.MARCA_CONSENTIMENTO in (a.get("consentimento_texto") or "") and nutricao.resumo_devido(a, ctx, agora, ja):
        vivos = novidades(p, editais, faculdades, set(), hoje) + novidades_seguidas(p, editais, faculdades, set(), hoje)
        resumo = nutricao.resumo_semanal(a, ctx, list({ed["id"]: (ed, fac) for _, ed, fac in vivos}.values()))
    for tipo, falta, ed, fac in nutricao.lembretes_devidos(a, ctx, ja):
        perto = tipo == nutricao.LEMBRETE_PERTO
        # quem pediu o lembrete já perto do prazo recebe só o último (o de longe fica marcado como passado)
        chaves = [f"lembrete{tipo}:{ed['id']}"] + ([f"lembrete{nutricao.LEMBRETE_LONGE}:{ed['id']}"] if perto else [])
        email = nutricao.lembrete(a, ctx, tipo, falta, ed, fac)
        if resumo:  # resumo e lembrete no mesmo dia: um e-mail só, o lembrete no topo (o mais urgente) e o resumo abaixo
            email, chaves, resumo = nutricao.lembrete_com_resumo(email, resumo), chaves + [f"resumo:{hoje}"], None
        saida.append(("lembrete_perto" if perto else "lembrete_longe", email_novo(a, *email), chaves))
    if resumo:
        saida.append(("resumo_semanal", email_novo(a, *resumo), [f"resumo:{hoje}"]))
    saida.sort(key=lambda t: PRIORIDADE[t[0]])
    if resumo and saida[0][0] != "resumo_semanal":  # o resumo perdeu a vez: fica para amanhã, nunca é descartado
        saida[0] = (saida[0][0], saida[0][1], saida[0][2] + [f"resumo_adiado:{nutricao.segunda_da_semana(hoje)}"])
    return saida


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
        # DESCADASTRO_UM_CLIQUE=1 depois de implantada e testada a Edge Function "descadastrar"
        um_clique = (os.environ["SUPABASE_URL"].rstrip("/") + "/functions/v1/descadastrar"
                     if os.environ.get("DESCADASTRO_UM_CLIQUE") == "1" else None)
        envio = EnvioBrevo(os.environ["BREVO_API_KEY"], os.environ["REMETENTE_EMAIL"], os.environ.get("REMETENTE_NOME") or "Cauã, do Transfermed",
                           um_clique)
    novos_ativos = os.environ.get("ALERTAS_ATIVOS") == "1"
    teste = EnvioSimulado(PASTA / ".trabalho" / "emails_simulados") if args.simular else EnvioContador()
    resumo = rodar(banco, envio, editais, faculdades, novos_ativos=novos_ativos, envio_teste=teste)
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
