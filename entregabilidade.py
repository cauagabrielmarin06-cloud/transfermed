"""
Entregabilidade dos e-mails automáticos (10/11/2026): o contrato que todo modelo de e-mail do alerta cumpre ANTES de ir ao ar, o
descadastro em um clique com sonda, a leitura do rastreamento do Brevo e a nota do mail-tester.

Contrato (`checar_email`, usado nos testes e na nota automática):
  1. multipart: versão em texto simples junto do HTML, com o mesmo conteúdo;
  2. primeira linha "Você pediu um alerta no Transfermed." (HTML e texto);
  3. no máximo 2 links distintos (a ação e o de cancelar), todos direto em https://www.transfermed.com.br, sem redirecionador;
  4. sem palavras de venda, sem imagens, sem pixel de rastreio, sem MAIÚSCULAS nem "!!" no assunto;
  5. rodapé que diz por que a pessoa recebe o e-mail e como sair;
  6. HTML leve (menos de 40 KB).

Brevo: no envio transacional por API não existe opção por mensagem para desligar o rastreamento de cliques e de abertura (a
documentação não tem esse campo; desligar é pedido ao suporte e, pelo que o Brevo publica, só no plano Enterprise). O que o código
garante: HTML sem pixel e links diretos. `rastreio_brevo` lê o relatório do Brevo e mostra se ainda há abertura/clique registrados.

Descadastro em um clique (RFC 8058): o endereço é a Edge Function `descadastrar` do Supabase. Vem LIGADO por padrão (funcoes.py), mas só
vale se a função existir de fato: `um_clique_url` faz uma sonda (POST com token falso; função no ar responde 400, ausente responde 404)
e, se ela não está no ar, os e-mails saem com o link da página do site e o resumo da rodada avisa.
"""
import re
import time

import funcoes

SITE = "https://www.transfermed.com.br"
ABERTURA = "Você pediu um alerta no Transfermed."
MAX_LINKS = 2
MAX_HTML = 40_000
PALAVRAS_DE_VENDA = re.compile(
    r"\bgr[aá]tis\b|\bpromo[cç][aã]o\b|\bofertas?\b|\bdescontos?\b|\bganhe\b|\bcompre\b|\bcomprar\b|\bimperd[ií]vel\b|"
    r"\burgente\b|\b[uú]ltima chance\b|\bclique aqui\b|\b100\s?%|\bsem risco\b|\bdinheiro\b|\bpr[eê]mio\b|\bparab[eé]ns\b|\bgarant\w+|"
    r"\bsó hoje\b|\baproveite\b|\bagora mesmo\b", re.I)
URL = re.compile(r"https?://[^\s\"'<>)\]]+", re.I)
REDIRECIONADORES = re.compile(r"sendibt|sibautomation|brevo\.com/|mailin\.fr|r\.mail|click\.|track\.|links\.", re.I)


def _urls(texto):
    return {u.rstrip(".,;") for u in URL.findall(texto)}


def checar_email(assunto, html, texto):
    """Lista de problemas (vazia = o modelo cumpre o contrato de entregabilidade)."""
    problemas = []
    if not (texto or "").strip():
        problemas.append("sem versão em texto simples (precisa ser multipart)")
    elif not texto.strip().startswith(ABERTURA):
        problemas.append(f"a primeira linha do texto não é “{ABERTURA}”")
    corpo = re.sub(r"(?s)<head>.*?</head>|<style.*?</style>", "", html or "")
    primeiro = re.search(r"(?s)<p[ >].*?</p>", re.sub(r"(?s)<div style=\"display:none.*?</div>", "", corpo))  # 1º parágrafo do conteúdo
    if not primeiro or re.sub(r"<[^>]+>", "", primeiro.group(0)).strip() != ABERTURA:
        problemas.append(f"o primeiro parágrafo do HTML não é “{ABERTURA}”")
    previa = re.search(r"(?s)<div style=\"display:none[^>]*>(.*?)</div>", corpo)
    if previa and not previa.group(1).strip().startswith(ABERTURA):
        problemas.append("a prévia (texto que aparece ao lado do assunto) não começa pela abertura")
    visivel = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", corpo)).strip()
    links = _urls(" ".join(re.findall(r'href="([^"]+)"', html or ""))) | _urls(texto or "")
    if len(links) > MAX_LINKS:
        problemas.append(f"{len(links)} links distintos (o máximo é {MAX_LINKS}): " + ", ".join(sorted(l.split("?")[0] for l in links)))
    for u in links:
        if not u.startswith(SITE + "/") and not u.startswith("https://s/"):  # "https://s" é o site fictício dos testes
            problemas.append(f"link fora de {SITE}: {u.split('?')[0]}")
        if REDIRECIONADORES.search(u):
            problemas.append(f"link de redirecionamento/rastreio: {u.split('?')[0]}")
    if re.search(r"<img\b", html or "", re.I):
        problemas.append("tem imagem no HTML")
    if re.search(r"width=[\"']?1[\"']?\s+height=[\"']?1|display:none[^>]*<img", html or "", re.I):
        problemas.append("tem pixel de rastreio")
    for onde, t in (("assunto", assunto), ("texto", texto or ""), ("HTML", visivel)):
        for m in PALAVRAS_DE_VENDA.finditer(t):
            problemas.append(f"palavra de venda no {onde}: “{m.group(0)}”")
    letras = re.sub(r"[^A-Za-zÀ-ÿ]", "", assunto or "")
    if len(letras) > 6 and letras.isupper():
        problemas.append("assunto em MAIÚSCULAS")
    if "!!" in (assunto or "") or (assunto or "").count("!") > 1:
        problemas.append("exclamações demais no assunto")
    if len(html or "") > MAX_HTML:
        problemas.append(f"HTML pesado ({len(html)} bytes; máximo {MAX_HTML})")
    rodape = (texto or "").split("\n--\n")[-1] if "\n--\n" in (texto or "") else ""
    if not re.search(r"Você recebe este e-mail porque", rodape) or not re.search(r"\bsair\b", rodape) or "/alerta/descadastrar/" not in rodape:
        problemas.append("o rodapé não diz por que a pessoa recebe o e-mail e como sair (com o link de cancelar)")
    return problemas


# ---------------------------------------------------------------- descadastro em um clique

def um_clique_url(supabase_url, http=None, ambiente=None):
    """(url, situacao): url da Edge Function `descadastrar` se a função está LIGADA e NO AR; senão (None, motivo). A sonda manda um
    POST com token falso (sem apagar ninguém): 400 = função no ar e sem exigir chave; 404 = não implantada; 401/403 = exige JWT."""
    desligada = (not funcoes.ligada("DESCADASTRO_UM_CLIQUE")) if ambiente is None else ambiente.get("DESCADASTRO_UM_CLIQUE", "1").strip() == "0"
    if desligada:
        return None, "desligado pela variável (valor 0)"
    url = supabase_url.rstrip("/") + "/functions/v1/descadastrar"
    if http is None:
        import requests as http
    try:
        r = http.post(url + "?t=sonda-sem-token", data={"List-Unsubscribe": "One-Click"}, timeout=20)
    except Exception as e:  # noqa: BLE001 - rede fora do ar não pode derrubar o envio
        return None, f"sonda sem resposta ({type(e).__name__}): link da página do site"
    if r.status_code == 400:
        return url, "no ar"
    if r.status_code == 404:
        return None, "Edge Function descadastrar não implantada (404): link da página do site"
    if r.status_code in (401, 403):
        return None, f"Edge Function exige JWT ({r.status_code}): desligue Verify JWT; link da página do site"
    return None, f"sonda respondeu HTTP {r.status_code}: link da página do site"


# ---------------------------------------------------------------- rastreamento do Brevo (só leitura)

def rastreio_brevo(chave, http=None, dias=7):
    """{'aberturas': n, 'cliques': n, 'enviados': n} do relatório agregado do Brevo, ou None se a consulta falhar. Mais de zero
    aberturas/cliques = o rastreamento do Brevo ainda está ligado na conta (pedir o desligamento ao suporte)."""
    if http is None:
        import requests as http
    try:
        r = http.get("https://api.brevo.com/v3/smtp/statistics/aggregatedReport", params={"days": dias}, timeout=30,
                     headers={"api-key": chave, "accept": "application/json"})
        if r.status_code != 200:
            return None
        j = r.json()
        return {"aberturas": int(j.get("opens", 0) or 0), "cliques": int(j.get("clicks", 0) or 0), "enviados": int(j.get("requests", 0) or 0)}
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- nota do mail-tester

LIMITE_NOTA = 9.0


def ler_nota(corpo_json):
    """A nota (0 a 10) do JSON do mail-tester, ou None. A documentação não nomeia o campo da nota final: aceita `mark`, `score` ou
    `note` no objeto principal; se vier só a soma dos descontos (`mark` <= 0 em cada teste), a nota é 10 + soma."""
    if not isinstance(corpo_json, dict) or corpo_json.get("status") is False:
        return None
    for chave in ("mark", "score", "note", "grade"):
        v = corpo_json.get(chave)
        if isinstance(v, (int, float)) and 0 <= v <= 10:
            return float(v)
    descontos = [t.get("mark") for t in corpo_json.values() if isinstance(t, dict) and isinstance(t.get("mark"), (int, float))]
    return round(10 + sum(descontos), 1) if descontos else None


def consultar_nota(usuario, sufixo, http=None, tentativas=12, espera_s=10, dormir=time.sleep):
    """Espera o mail-tester receber a mensagem e devolve (nota, detalhe). nota None = não deu para medir (detalhe diz por quê)."""
    if http is None:
        import requests as http
    url = f"https://www.mail-tester.com/{usuario}-{sufixo}"
    for i in range(tentativas):
        try:
            r = http.get(url, params={"format": "json"}, timeout=30)
            j = r.json() if r.status_code == 200 else None
        except Exception:  # noqa: BLE001
            j = None
        nota = ler_nota(j)
        if nota is not None:
            return nota, "ok"
        if i < tentativas - 1:
            dormir(espera_s)
    return None, "o mail-tester não devolveu a nota a tempo (mensagem não chegou ou serviço indisponível)"


def decidir(nota):
    """('ok'|'reprovado'|'nao_medido', texto). Só uma nota medida e abaixo de 9 trava a publicação."""
    if nota is None:
        return "nao_medido", "nota não medida"
    if nota < LIMITE_NOTA:
        return "reprovado", f"nota {nota:.1f}/10, abaixo de {LIMITE_NOTA:.0f}/10"
    return "ok", f"nota {nota:.1f}/10"


# ---------------------------------------------------------------- registro da nota (data/nota_entrega.json) e a trava

import hashlib
import json
import os
from pathlib import Path

REGISTRO = Path(__file__).resolve().parent / "data" / "nota_entrega.json"
MODELOS_FONTE = ("nutricao.py",)  # onde moram os modelos de e-mail: mudou aqui, a nota é medida de novo


def hash_modelos(base=None):
    """Impressão digital dos modelos de e-mail (fim de linha normalizado: o mesmo valor no Windows e no Linux)."""
    base = Path(base) if base else Path(__file__).resolve().parent
    h = hashlib.sha256()
    for nome in MODELOS_FONTE:
        h.update((base / nome).read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:16]


def ler_registro(caminho=None):
    try:
        return json.loads(Path(caminho or REGISTRO).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def nota_minima(ambiente=None):
    """9 por padrão; a variável NOTA_ENTREGA_MINIMA=0 é a chave do dono para liberar os envios se a nota oscilar por motivo externo."""
    try:
        return float(((ambiente if ambiente is not None else os.environ).get("NOTA_ENTREGA_MINIMA") or "").strip() or LIMITE_NOTA)
    except ValueError:
        return LIMITE_NOTA


def liberado(registro, hash_atual, ambiente=None):
    """(True|False, motivo). Os envios só param quando os modelos de ESTE hash foram medidos e a nota ficou abaixo do mínimo. Sem registro,
    registro de outro hash (modelo ainda não medido) ou nota não medida: segue enviando e o relatório mostra o que falta medir."""
    minimo = nota_minima(ambiente)
    if minimo <= 0:
        return True, "trava desligada (NOTA_ENTREGA_MINIMA=0)"
    if not registro or registro.get("hash") != hash_atual:
        return True, "modelos ainda sem nota (a medição roda a cada mudança de modelo)"
    nota = registro.get("nota")
    if registro.get("estado") == "reprovado" and isinstance(nota, (int, float)) and nota < minimo:
        return False, f"nota de entregabilidade {nota:.1f}/10, abaixo de {minimo:.0f}/10 (registro de {registro.get('gerado_em', '?')[:10]})"
    return True, "ok"


def linhas_relatorio(brevo=None, registro=None, hash_atual=None):
    """Linhas do relatório semanal: nota do mail-tester e rastreamento do Brevo, com a fonte e o que não deu para medir."""
    registro = registro if registro is not None else ler_registro()
    if registro and registro.get("nota") is not None:
        atual = "" if hash_atual is None or registro.get("hash") == hash_atual else " (de um modelo anterior: o atual ainda não foi medido)"
        linhas = [f"Entregabilidade (nota do mail-tester, medida em {registro.get('gerado_em', '?')[:10]}): {registro['nota']:.1f}/10{atual}"]
    else:
        motivo = (registro or {}).get("detalhe") or "nenhuma medição registrada"
        linhas = [f"Entregabilidade (mail-tester): nota não medida ({motivo})"]
    if brevo and brevo.get("aberturas") is not None:
        ligado = brevo["aberturas"] or brevo["cliques"]
        linhas.append(f"Rastreamento do Brevo em 7 dias: {brevo['aberturas']} aberturas e {brevo['cliques']} cliques registrados"
                      + (" (o rastreamento do Brevo ainda está ligado na conta: pedir o desligamento ao suporte)" if ligado else " (sem rastreamento)"))
    else:
        linhas.append("Rastreamento do Brevo: não medido (a API do Brevo não respondeu)")
    return linhas
