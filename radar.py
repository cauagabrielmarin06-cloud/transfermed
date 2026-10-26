"""
Radar de editais de transferência de Medicina (externa, interna e para quem estuda no exterior).

Roda sozinho (uma vez por dia pelo GitHub Actions, ou na mão com `python radar.py`):
  1. visita as páginas de cada faculdade em data/faculdades.json
  2. acha links de editais de transferência de Medicina (ignora resultados, gabaritos e outros cursos)
  3. ignora o que já processou (detecta retificações pelo conteúdo e pelo nome do arquivo)
  4. lê o PDF e extrai os dados com a página de cada informação (regras simples, ou IA se houver ANTHROPIC_API_KEY)
  5. confere as datas por código (fim antes do início, ano errado...) e marca "conferir" quando algo não fecha
  6. salva data/editais.json, docs/editais.json (site) e data/relatorio_qualidade.md
"""
import hashlib
import io
import json
import os
import re
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

import gerar_site

PASTA = Path(__file__).resolve().parent
FACULDADES = PASTA / "data" / "faculdades.json"
EDITAIS = PASTA / "data" / "editais.json"
PROCESSADOS = PASTA / "data" / "processados.json"
ULTIMA_EXECUCAO = PASTA / "data" / "ultima_execucao.json"
RELATORIO = PASTA / "data" / "relatorio_qualidade.md"
SITE_DADOS = PASTA / "docs" / "editais.json"
SITE_FACULDADES = PASTA / "docs" / "faculdades.json"

HEADERS = {"User-Agent": "Mozilla/5.0 (RadarEditaisMedicina; +https://www.transfermed.com.br)"}
TIMEOUT = 30
MAX_PDFS_POR_FACULDADE = 15

MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}
# campos que todo edital deveria ter (o relatório lista os que ficaram vazios)
CAMPOS_ESSENCIAIS = ("modalidade", "semestre_ingresso", "inscricao_fim", "vagas", "taxa_inscricao",
                     "criterio_selecao", "aceita_curso_exterior")
NAO_EDITAL = ("resultado", "gabarito", "classificac", "classificad", "convoca", "aprovados", "homologa",
              "chamada", "lista de", "recurso", "deferid", "local de prova", "locais de prova", "cronograma de matricula",
              "preliminar", "inscritos", "ranking", "calendario")
OUTROS_CURSOS = ("enfermagem", "psicologia", "odontologia", "farmacia", "fisioterapia", "nutricao", "biomedicina",
                 "direito", "engenharia", "veterinaria", "agronomia", "administracao", "pedagogia", "residencia")
EDITAL_GERAL = ("demais cursos", "cursos presenciais", "a distancia", "todos os cursos")  # editais de vários cursos
JANELA_DIAS = 730  # histórico: editais dos últimos 2 anos


# ---------------------------------------------------------------- utilidades

def normalizar(texto):
    """minúsculas e sem acentos, para comparar palavras."""
    texto = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


def ler_json(caminho, padrao):
    try:
        return json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return padrao


def salvar_json(caminho, dados):
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    Path(caminho).write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def chave_url(url):
    """Mesmo PDF com ou sem www/https/espaço no fim conta como um só."""
    u = re.sub(r"^https?://(www\.)?", "", (url or "").strip())
    return re.sub(r"(%20|\s)+$", "", u).lower()


def id_do_edital(url, faculdade_id, modalidade):
    return hashlib.sha1(f"{url}|{faculdade_id}|{modalidade}".encode("utf-8")).hexdigest()[:12]


def fala_de_medicina(t):
    t = t.replace("medicina veterinaria", "").replace("_", " ")
    return re.search(r"\bmedicina\b|\bmed\b", t) is not None  # palavra inteira: "biomedicina" não conta


def parece_edital(rotulo, pagina_de_transferencia=False):
    """Decide se um link é edital de transferência de Medicina (externa ou interna).

    Numa página que já é de transferência (ex.: .../transferencia), basta o link falar em "edital".
    """
    t = re.sub(r"[-_]+", " ", normalizar(rotulo))
    if any(p in t for p in NAO_EDITAL + EDITAL_GERAL):
        return False
    if any(c in t for c in OUTROS_CURSOS) and not fala_de_medicina(t):
        return False
    if "transfer" in t and fala_de_medicina(t):
        return True
    return pagina_de_transferencia and ("edital" in t or "retifica" in t)


def eh_retificacao(rotulo):
    t = normalizar(rotulo)
    return any(p in t for p in ("retifica", "ratifica", "aditamento", "aditivo", "errata", "deliberac"))


def modalidade_provavel(rotulo, inicio_texto):
    """Palpite da modalidade: primeiro pelo nome do link, depois pelo título do PDF."""
    r = re.sub(r"[-_]+", " ", normalizar(rotulo))
    t = normalizar(inicio_texto[:2500])
    if "estrangeir" in r:
        return "exterior"
    if "interna" in r:
        return "interna"
    if "externa" in r:
        return "externa"
    if "transferencia interna" in t:
        return "interna"
    if re.search(r"(ies|instituic\w*|faculdades?|universidades?) estrangeir|cursando no exterior", t):
        return "exterior"
    if "portador de diploma" in t and "transfer" not in t:
        return "portador_diploma"
    if "ex officio" in t or "ex-officio" in t:
        return "ex_officio"
    return "externa"


# ---------------------------------------------------------------- coleta

def links_de_pagina(url):
    """Abre uma página (HTML ou JSON) e devolve [(url, rótulo)] que parecem edital de transferência de Medicina."""
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    pagina_transf = "transfer" in normalizar(url)
    achados = []
    if resp.text.lstrip().startswith(("[", "{")):
        return achados  # JSON: tratado por links_api_noticias
    sopa = BeautifulSoup(resp.text, "html.parser")
    for a in sopa.find_all("a", href=True):
        href = urljoin(resp.url, a["href"].strip())
        rotulo = f"{a.get_text(' ', strip=True)} {href}"
        if href.startswith("http") and not href.endswith("=") and parece_edital(rotulo, pagina_transf):
            achados.append((href, rotulo))
    return achados


def links_wordpress(base):
    """Sites em WordPress: pergunta direto à biblioteca de mídia por PDFs de transferência."""
    achados = []
    for termo in ("transferencia medicina", "transferência medicina", "transferencia", "transferência interna"):
        api = f"{base.rstrip('/')}/wp-json/wp/v2/media"
        resp = requests.get(api, headers=HEADERS, timeout=TIMEOUT,
                            params={"search": termo, "mime_type": "application/pdf", "per_page": 50})
        if resp.status_code != 200:
            continue
        for item in resp.json():
            href = item.get("source_url", "")
            rotulo = f"{item.get('title', {}).get('rendered', '')} {href}"
            if parece_edital(rotulo):
                achados.append((href, rotulo))
    return achados


def links_api_noticias(cfg):
    """Sites que publicam editais como notícias com anexos (ex.: UNIFUNEC).

    cfg = {"lista": url, "detalhe": url com {id}, "anexo": url com {id}}
    """
    achados = []
    lista = requests.get(cfg["lista"], headers=HEADERS, timeout=TIMEOUT).json()
    for noticia in (lista if isinstance(lista, list) else lista.get("data", [])):
        titulo = noticia.get("title", "")
        if not parece_edital(titulo):
            continue
        detalhe = requests.get(cfg["detalhe"].format(id=noticia["idInterno"]), headers=HEADERS, timeout=TIMEOUT).json()
        anexos = detalhe.get("attachments") or "[]"
        for anexo in (json.loads(anexos) if isinstance(anexos, str) else anexos):
            nome = anexo.get("Name", "")
            rotulo = f"{titulo} {nome}"
            n = normalizar(nome)
            if "edital" in n or "retifica" in n:  # ignora resultados e homologações anexados
                if not any(p in n for p in NAO_EDITAL):
                    achados.append((cfg["anexo"].format(id=anexo["Id"]), rotulo))
    return achados


def baixar_pdf(url):
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    inicio = resp.content.find(b"%PDF", 0, 2048)  # alguns servidores mandam bytes antes do cabeçalho
    if inicio < 0:
        return None
    return resp.content[inicio:]


def paginas_do_pdf(conteudo):
    leitor = PdfReader(io.BytesIO(conteudo))
    return [(pagina.extract_text() or "") for pagina in leitor.pages]


# ---------------------------------------------------------------- extração

def _data_iso(dia, mes, ano):
    try:
        return date(int(ano), int(mes), int(dia)).isoformat()
    except ValueError:
        return None


def datas_no_trecho(trecho):
    datas = []
    for d, m, a in re.findall(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", trecho):
        datas.append(_data_iso(d, m, a))
    for d, mes, a in re.findall(r"\b(\d{1,2})(?:º)?\s+de\s+([a-zç]+)\s+de\s+(\d{4})", normalizar(trecho)):
        if mes in MESES:
            datas.append(_data_iso(d, MESES[mes], a))
    return [d for d in datas if d]


def extrair_por_regras(paginas):
    """Extração simples, guardando em `evidencias` a página onde cada informação foi achada."""
    dados, evid = {}, {}

    def achar(padrao):
        for n, pagina in enumerate(paginas, 1):
            m = re.search(padrao, normalizar(pagina))
            if m:
                return m, n
        return None, None

    m, pag = achar(r"\b(20\d\d)\s*[./]\s*([12])\b")
    if m:
        dados["semestre_ingresso"], evid["semestre_ingresso"] = f"{m.group(1)}.{m.group(2)}", pag
    else:
        m, pag = achar(r"\b(1|2|primeiro|segundo)[ºo°]?\s+semestre(?:\s+letivo)?\s+de\s+(20\d\d)")
        if m:
            n = "1" if m.group(1) in ("1", "primeiro") else "2"
            dados["semestre_ingresso"], evid["semestre_ingresso"] = f"{m.group(2)}.{n}", pag

    # período de inscrição: datas que aparecem em linhas que falam de inscrição
    datas = []
    for n, pagina in enumerate(paginas, 1):
        linhas = [l.strip() for l in pagina.splitlines() if l.strip()]
        for i, linha in enumerate(linhas):
            if "inscri" in normalizar(linha):
                for d in datas_no_trecho(" ".join(linhas[i:i + 2])):
                    datas.append((d, n))
    if datas:
        (ini, p_ini), (fim, p_fim) = min(datas), max(datas)
        dados.update(inscricao_inicio=ini, inscricao_fim=fim)
        evid.update(inscricao_inicio=p_ini, inscricao_fim=p_fim)

    m, pag = achar(r"taxa[^\n]{0,120}?r\$\s*([\d.]+,\d{2})")
    if m:
        dados["taxa_inscricao"], evid["taxa_inscricao"] = float(m.group(1).replace(".", "").replace(",", ".")), pag
    elif achar(r"inscricao (e|sera) gratuita")[0]:
        dados["taxa_inscricao"], evid["taxa_inscricao"] = 0.0, achar(r"inscricao (e|sera) gratuita")[1]

    criterios = []
    for padrao, nome in ((r"prova (objetiva|escrita|teorica|pratica|de multipla|on-?line)|multipla escolha|redacao", "prova"),
                         (r"media (aritmetica |global )?(simples )?(das notas )?(do|das) (historico|disciplinas)", "média do histórico"),
                         (r"analise (do |de )?(historico|curricul|documental|dos documentos)", "análise de histórico/documentos"),
                         (r"entrevista", "entrevista")):
        m, pag = achar(padrao)
        if m:
            criterios.append(nome)
            evid.setdefault("criterio_selecao", pag)
    if criterios:
        dados["criterio_selecao"] = ", ".join(dict.fromkeys(criterios))

    m, pag = achar(r"brasileiras? ou estrangeiras?|nacionais ou estrangeiras|ies estrangeiras|cursos? de medicina (ministrados? )?no exterior")
    if m:
        dados["aceita_curso_exterior"], evid["aceita_curso_exterior"] = True, pag
    else:
        m, pag = achar(r"(ies|instituic\w*( de ensino superior)?) (brasileiras?|nacionais?|sediadas? no brasil)|originarios de instituicoes nacionais")
        if m:
            dados["aceita_curso_exterior"], evid["aceita_curso_exterior"] = False, pag

    m, pag = achar(r"(ja tiver|ja tenham|tenha) realizado transferencia|transferencia anterior")
    if m:
        dados["exclui_quem_ja_transferiu"], evid["exclui_quem_ja_transferiu"] = True, pag

    # vagas: guarda as frases sobre vagas para conferência (estruturar tabela é frágil)
    trechos = []
    for n, pagina in enumerate(paginas, 1):
        for l in pagina.splitlines():
            if re.search(r"\bvagas?\b", normalizar(l)) and re.search(r"\d", l):
                trechos.append(l.strip())
                evid.setdefault("vagas_texto", n)
    if trechos:
        dados["vagas_texto"] = list(dict.fromkeys(trechos))[:6]

    dados["evidencias"] = evid
    return dados


def extrair_com_ia(paginas):
    """Usa a API do Claude quando existir ANTHROPIC_API_KEY. Custa pouco por edital."""
    chave = os.environ.get("ANTHROPIC_API_KEY")
    if not chave:
        return None
    texto = "\n".join(f"[página {n}]\n{p}" for n, p in enumerate(paginas, 1))
    instrucao = (
        "Você recebe o texto de um edital de transferência para o curso de Medicina no Brasil, com marcadores [página N]. "
        "Responda SOMENTE com um JSON com as chaves: modalidade (externa | interna | exterior | portador_diploma | ex_officio), "
        "numero_edital, semestre_ingresso (AAAA.S), inscricao_inicio e inscricao_fim (AAAA-MM-DD), data_prova (AAAA-MM-DD), "
        "vagas (lista de {semestre, vagas}), taxa_inscricao (número em reais; 0 se gratuita), criterio_selecao (curto), "
        "quem_pode (frase curta), aceita_curso_exterior (true/false/null), exclui_quem_ja_transferiu (true/false/null), "
        "documentos (lista curta), outras_restricoes (lista curta), "
        "evidencias (objeto: para cada campo preenchido, o número da página onde está), "
        "inconsistencias (lista de contradições ou datas impossíveis encontradas no próprio edital). "
        "Use null quando o edital não disser. Nunca invente."
    )
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": chave, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={
            "model": os.environ.get("RADAR_MODELO", "claude-haiku-5-5"),
            "max_tokens": 2500,
            "messages": [{"role": "user", "content": f"{instrucao}\n\n<edital>\n{texto[:80000]}\n</edital>"}],
        },
        timeout=180,
    )
    resp.raise_for_status()
    saida = resp.json()["content"][0]["text"]
    inicio, fim = saida.find("{"), saida.rfind("}")
    return json.loads(saida[inicio:fim + 1])


def extrair_dados(paginas):
    try:
        dados = extrair_com_ia(paginas)
        if dados:
            return dados, "ia"
    except Exception as erro:  # se a IA falhar, cai nas regras
        print(f"   ! IA falhou ({erro}); usando regras simples")
    return extrair_por_regras(paginas), "regras"


# ---------------------------------------------------------------- conferência

def problemas_de_data(e, hoje):
    """Datas impossíveis ou suspeitas, detectadas por código."""
    problemas = []
    ini, fim, prova = e.get("inscricao_inicio"), e.get("inscricao_fim"), e.get("data_prova")
    ano = int(hoje[:4])
    for campo in ("inscricao_inicio", "inscricao_fim", "data_prova"):
        valor = e.get(campo)
        if valor and not (ano - 3 <= int(valor[:4]) <= ano + 2):
            problemas.append(f"{campo} com ano improvável ({valor})")
    if ini and fim and fim < ini:
        problemas.append(f"inscrição termina ({fim}) antes de começar ({ini})")
    if prova and ini and prova < ini:
        problemas.append(f"prova ({prova}) antes do início das inscrições ({ini})")
    m = re.match(r"(20\d\d)", str(e.get("semestre_ingresso") or ""))
    if m and fim and not (0 <= int(m.group(1)) - int(fim[:4]) <= 1):
        problemas.append(f"semestre de ingresso {e['semestre_ingresso']} não combina com inscrição em {fim[:4]}")
    return problemas


def status_do_edital(dados, paginas):
    if sum(len(p.strip()) for p in paginas) < 300:
        return "conferir"  # provavelmente PDF escaneado (imagem)
    if dados.get("inconsistencias"):
        return "conferir"
    essenciais = ("semestre_ingresso", "inscricao_fim", "criterio_selecao")
    return "ok" if all(dados.get(c) for c in essenciais) else "conferir"


def situacao(edital, hoje):
    if edital.get("fluxo_continuo"):
        return "fluxo contínuo"
    fim, inicio = edital.get("inscricao_fim"), edital.get("inscricao_inicio")
    if not fim:
        m = re.match(r"(20\d\d)\.([12])", str(edital.get("semestre_ingresso") or ""))
        if m:
            ano, mes = int(hoje[:4]), int(hoje[5:7])
            atual = (ano, 1 if mes <= 6 else 2)
            if (int(m.group(1)), int(m.group(2))) <= atual:
                return "encerrado"
        return "desconhecida"
    if hoje > fim:
        return "encerrado"
    if inicio and hoje < inicio:
        return "em breve"
    return "aberto"


def anotar(e, texto):
    """Acrescenta uma observação sem repetir."""
    atual = e.get("observacao") or ""
    if texto not in atual:
        e["observacao"] = f"{atual} {texto}".strip()


def completar_com_faculdade(e, faculdades):
    """Nome, cidade, tipo e coordenadas vêm sempre da ficha da faculdade (uma fonte só)."""
    f = faculdades.get(e.get("faculdade_id"))
    if not f:
        return
    e.update(instituicao=f["nome"], cidade_uf=f"{f['cidade']}/{f['uf']}", tipo=f["tipo"], lat=f["lat"], lon=f["lon"])


# ---------------------------------------------------------------- relatório

def relatorio_qualidade(faculdades, editais, resumo, hoje):
    linhas = [f"# Relatório de qualidade dos dados", "",
              f"Gerado em {resumo['executado_em']} pelo radar.py.", "",
              f"- Faculdades na base: **{len(faculdades)}**",
              f"- Editais na base: **{len(editais)}** (abertos agora: {sum(e['situacao'] == 'aberto' for e in editais)})",
              f"- Editais com status \"conferir\": **{sum(e.get('status') == 'conferir' for e in editais)}**", ""]

    sem_pagina = [f for f in faculdades.values()
                  if f.get("pendente") or not (f.get("paginas_editais") or f.get("wordpress") or f.get("api_noticias"))]
    linhas += ["## Faculdades sem página de editais definida", ""]
    linhas += [f"- **{f['nome']}** ({f['cidade']}/{f['uf']}): {f.get('pendente') or 'sem página cadastrada'}" for f in sem_pagina] or ["Nenhuma."]

    linhas += ["", "## Páginas com erro nesta execução", ""]
    linhas += [f"- {erro}" for erro in resumo["erros"] if "ficha incompleta" not in erro] or ["Nenhuma."]

    novos = [e for e in editais if e.get("detectado_em") and e.get("fonte_dados") != "manual"]
    linhas += ["", "## Editais novos detectados pelo robô (revisar à mão para publicar com dados)", ""]
    linhas += [f"- {e.get('instituicao')}: [{e.get('semestre_ingresso') or 'PDF'}]({e['url_edital']}) · detectado em {e['detectado_em']}"
               for e in novos] or ["Nenhum."]

    linhas += ["", "## Editais com status \"conferir\"", "", "| Faculdade | Modalidade | Edital | Motivo |", "|---|---|---|---|"]
    for e in editais:
        if e.get("status") == "conferir":
            motivo = (e.get("observacao") or "campos essenciais vazios").replace("|", "/")
            linhas.append(f"| {e.get('instituicao')} | {e.get('modalidade')} | [{e.get('numero_edital') or 'link'}]({e['url_edital']}) | {motivo} |")

    linhas += ["", "## Campos vazios", "", "| Faculdade | Edital | Campos vazios |", "|---|---|---|"]
    for e in editais:
        vazios = [c for c in CAMPOS_ESSENCIAIS if e.get(c) in (None, "", [])
                  and not (c == "inscricao_fim" and e.get("fluxo_continuo"))]
        if vazios:
            linhas.append(f"| {e.get('instituicao')} | {e.get('numero_edital') or e['url_edital']} | {', '.join(vazios)} |")

    linhas += ["", "## Editais sem página do PDF registrada (evidências)", ""]
    sem_evid = [e for e in editais if not e.get("evidencias")]
    linhas += [f"- {e.get('instituicao')}: {e.get('numero_edital') or e['url_edital']}" for e in sem_evid] or ["Nenhum."]

    linhas += ["", "## Datas impossíveis ou suspeitas (checagem automática)", ""]
    com_problema = [(e, problemas_de_data(e, hoje)) for e in editais]
    linhas += [f"- {e.get('instituicao')} ({e.get('numero_edital')}): {'; '.join(p)}" for e, p in com_problema if p] or ["Nenhuma."]
    RELATORIO.write_text("\n".join(linhas) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- execução

def cita_edital(texto, e):
    t = re.sub(r"\s+", " ", normalizar(texto))
    numero = re.search(r"\d{1,4}\s*/\s*20\d\d", str(e.get("numero_edital") or ""))
    if numero and re.sub(r"\s", "", numero.group(0)) in t.replace(" ", ""):
        return True
    m = re.match(r"(20\d\d)\.([12])", str(e.get("semestre_ingresso") or ""))
    return bool(m and re.search(rf"{m.group(1)}\s*[./-]\s*{m.group(2)}\b", t))


def antigo_demais(dados, hoje):
    """Fora da janela de 2 anos? Usa o fim das inscrições ou, sem ele, o início do semestre de ingresso."""
    referencia = dados.get("inscricao_fim")
    if not referencia:
        m = re.match(r"(20\d\d)\.([12])", str(dados.get("semestre_ingresso") or ""))
        if not m:
            return False
        referencia = f"{m.group(1)}-{'02' if m.group(2) == '1' else '08'}-01"
    try:
        return (date.fromisoformat(hoje) - date.fromisoformat(referencia)).days > JANELA_DIAS
    except ValueError:
        return False


def processar_link(fac, url, rotulo, ctx):
    editais, processados, resumo, hoje = ctx["editais"], ctx["processados"], ctx["resumo"], ctx["hoje"]
    nome, chave = fac["nome"], chave_url(url)
    conteudo = baixar_pdf(url)
    if conteudo is None:
        return  # não era PDF
    assinatura = hashlib.sha256(conteudo).hexdigest()
    anterior = processados.get(chave)
    if anterior in (assinatura, "conhecida", "antigo"):
        return  # já visto e não mudou
    registros = ctx["do_link"].get(chave, [])

    # PDF conferido à mão: só guarda a assinatura; se mudar depois, marca para conferir sem apagar os dados
    if registros and any(r.get("fonte_dados") == "manual" for r in registros):
        if anterior not in (None, "manual"):
            for r in registros:
                r["status"] = "conferir"
                anotar(r, f"O PDF mudou em {hoje} (possível retificação).")
            resumo["atualizados"].append(f"{nome}: {url}")
        processados[chave] = assinatura
        return

    paginas = paginas_do_pdf(conteudo)
    texto = "\n".join(paginas)
    # retificação/aditivo pelo nome do arquivo; pelo texto, só documento curto (edital completo "retificado" segue como edital)
    if eh_retificacao(rotulo) or ("retifica" in normalizar(texto[:600]) and len(paginas) <= 3):
        # só marca o edital que a retificação cita (pelo número ou pelo semestre de ingresso)
        alvos = [e for e in editais.values() if e.get("faculdade_id") == fac["id"] and e.get("situacao") != "encerrado"
                 and cita_edital(f"{rotulo} {texto}", e)]
        for e in alvos:
            e["status"] = "conferir"
            e.setdefault("retificacoes", []).append(url)
            anotar(e, f"Retificação publicada em {hoje}: confira as mudanças.")
        resumo["retificacoes"].append(f"{nome}: {url} ({len(alvos)} edital(is) marcado(s))")
        processados[chave] = assinatura
        return

    # edital geral (vários cursos) achado numa página de transferência: se nem cita Medicina, não interessa
    if not fala_de_medicina(normalizar(texto)):
        processados[chave] = assinatura
        return
    # portal com vários câmpus (ex.: Unesp): a ficha pode exigir que o PDF cite o câmpus
    if fac.get("exigir_texto") and not re.search(fac["exigir_texto"], normalizar(texto)):
        processados[chave] = assinatura
        return

    dados, origem = extrair_dados(paginas)
    if antigo_demais(dados, hoje):
        processados[chave] = "antigo"  # fora da janela de 2 anos: não entra na base
        resumo["antigos_ignorados"] += 1
        return
    modalidade = dados.get("modalidade") or modalidade_provavel(rotulo, texto)
    ident = id_do_edital(url, fac["id"], modalidade)
    novo = {
        "id": ident,
        "faculdade_id": fac["id"],
        "url_edital": url,
        "modalidade": modalidade,
        **{k: v for k, v in dados.items() if v not in (None, "", []) and k not in ("modalidade", "inconsistencias")},
        "fonte_dados": origem,
        "status": status_do_edital(dados, paginas),
        "atualizado_em": hoje,
        # o site mostra editais recém-descobertos como "novo, ainda não conferido" (sem afirmar datas ou vagas)
        "detectado_em": (editais.get(ident) or {}).get("detectado_em") or hoje,
    }
    if dados.get("inconsistencias"):
        anotar(novo, "Inconsistências no edital: " + "; ".join(dados["inconsistencias"]))
    if origem == "regras":  # regras simples erram (ex.: confundem números de resolução com semestre)
        novo["status"] = "conferir"
        anotar(novo, "Lido automaticamente por regras simples: confira semestre, datas e vagas no PDF.")
    if anterior and anterior != "manual":
        novo["status"] = "conferir"
        anotar(novo, "O PDF mudou desde a última leitura (possível retificação).")
        resumo["atualizados"].append(f"{nome}: {url}")
    else:
        resumo["novos"].append(f"{nome}: {url}")
    editais[ident] = novo  # substitui tudo: numa retificação, dados antigos podem estar errados
    processados[chave] = assinatura
    print(f"   + {modalidade} {novo.get('semestre_ingresso', '?')} [{novo['status']}] {url}")


def coletar_links(fac, resumo):
    nome = fac["nome"]
    links = []
    for pagina in fac.get("paginas_editais", []):
        try:
            links += links_de_pagina(pagina)
        except Exception as erro:
            resumo["erros"].append(f"{nome}: página {pagina} ({erro})")
    if fac.get("wordpress"):
        try:
            links += links_wordpress(fac["wordpress"])
        except Exception as erro:
            resumo["erros"].append(f"{nome}: busca WordPress ({erro})")
    if fac.get("api_noticias"):
        try:
            links += links_api_noticias(fac["api_noticias"])
        except Exception as erro:
            resumo["erros"].append(f"{nome}: API de notícias ({erro})")
    # campi que dividem o mesmo site: cada ficha fica só com os PDFs do seu campus
    exigir, excluir = fac.get("exigir_links"), fac.get("excluir_links")
    vistos, unicos = set(), []
    for url, rotulo in links:
        r = normalizar(rotulo)
        if (exigir and not re.search(exigir, r)) or (excluir and re.search(excluir, r)):
            continue
        if url not in vistos:
            vistos.add(url)
            unicos.append((url, rotulo))
    return unicos[:MAX_PDFS_POR_FACULDADE]


def main():
    faculdades = {f["id"]: f for f in ler_json(FACULDADES, [])}
    editais = {e["id"]: e for e in ler_json(EDITAIS, [])}
    processados = {chave_url(u): v for u, v in ler_json(PROCESSADOS, {}).items()}
    hoje = date.today().isoformat()
    resumo = {"executado_em": datetime.now().isoformat(timespec="seconds"),
              "novos": [], "atualizados": [], "retificacoes": [], "antigos_ignorados": 0, "erros": []}

    do_link = {}  # url -> registros (um PDF pode valer para vários campi ou modalidades)
    for e in editais.values():
        do_link.setdefault(chave_url(e["url_edital"]), []).append(e)
        for r in e.get("retificacoes", []):
            processados.setdefault(chave_url(r), "conhecida")
    ctx = {"editais": editais, "processados": processados, "do_link": do_link, "resumo": resumo, "hoje": hoje}

    for fac in faculdades.values():
        nome = fac["nome"]
        print(f"\n== {nome}")
        if fac.get("pendente"):
            resumo["erros"].append(f"{nome}: ficha incompleta ({fac['pendente']})")
        links = coletar_links(fac, resumo)
        print(f"   {len(links)} link(s) candidato(s)")
        for url, rotulo in links:
            try:
                processar_link(fac, url, rotulo, ctx)
            except Exception as erro:  # um PDF problemático não pode parar o robô
                resumo["erros"].append(f"{nome}: {url} ({type(erro).__name__}: {erro})")

    lista = sorted(editais.values(), key=lambda e: (e.get("inscricao_fim") or ""), reverse=True)
    for e in lista:
        completar_com_faculdade(e, faculdades)
        e["situacao"] = situacao(e, hoje)
        problemas = problemas_de_data(e, hoje)
        if problemas:
            e["status"] = "conferir"
            anotar(e, "Datas suspeitas: " + "; ".join(problemas) + ".")

    salvar_json(EDITAIS, lista)
    salvar_json(SITE_DADOS, lista)
    salvar_json(SITE_FACULDADES, list(faculdades.values()))
    salvar_json(PROCESSADOS, processados)
    salvar_json(ULTIMA_EXECUCAO, resumo)
    relatorio_qualidade(faculdades, lista, resumo, hoje)
    gerar_site.main()  # páginas do site (início, diagnóstico, faculdades, editais)

    print("\n================ RESUMO")
    print(f"Editais novos: {len(resumo['novos'])}")
    print(f"Editais alterados (retificação?): {len(resumo['atualizados'])}")
    print(f"Retificações encontradas: {len(resumo['retificacoes'])}")
    print(f"Total na base: {len(lista)} | abertos agora: {sum(e['situacao'] == 'aberto' for e in lista)}")
    print(f"Relatório de qualidade: {RELATORIO.relative_to(PASTA)}")
    if resumo["erros"]:
        print(f"Avisos ({len(resumo['erros'])}) - confira se o site mudou:")
        for erro in resumo["erros"]:
            print(f"  - {erro}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
