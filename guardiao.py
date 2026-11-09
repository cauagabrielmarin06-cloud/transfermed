"""
Guardião diário do Transfermed (T6.2): confere o SITE NO AR, por https, e vigia a base.

O que confere (tudo só leitura; nunca envia e-mail real nem escreve em nenhum serviço):
1. Site: home responde 200 por https, certificado com mais de 14 dias, http redireciona para https, o sitemap abre e todas as
   páginas dele respondem 200, e o site no ar é o mesmo que o repositório (o `sw.js` carrega a versão da geração).
2. Prazos: edital com prazo vencido que a página no ar ainda mostra como aberto ("Inscrições abertas até ...").
3. PDFs: o edital de cada inscrição aberta ainda abre (o hash e a retificação silenciosa são do monitor.py).
4. E-mail: registros públicos do domínio remetente (SPF, DKIM do Brevo, DMARC, MX) por DNS sobre https. Não envia teste.
5. Quarentena: edital publicado cujo PDF mudou depois da última conferência entra em data/quarentena.json e vira "conferir"
   no site e nos e-mails (gerar_site.aplicar_quarentena), em vez de afirmar uma data que pode ter mudado.
   Dado novo do robô (fonte_dados "robo") nunca é publicado: o guardião só conta quantos esperam conferência.

Saída: qa/relatorios/achados_guardiao.json (o issues.py abre ou atualiza uma issue por falha, sem duplicar) e
data/guardiao.json (resumo da execução e do histórico, sem dado pessoal, para a linha semanal do relatório).

Uso:  python guardiao.py [--sem-rede] [--hoje AAAA-MM-DD]
"""
import argparse
import json
import re
import socket
import ssl
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

import gerar_site
import monitor
import radar
import seguranca_rls

PASTA = Path(__file__).resolve().parent
SITE = "https://www.transfermed.com.br"
DOMINIO = "transfermed.com.br"
SAIDA = PASTA / "qa" / "relatorios" / "achados_guardiao.json"
RESUMO = PASTA / "data" / "guardiao.json"
DIAS_CERTIFICADO = 14
ESPERA_DEPLOY = (0, 300, 300)  # segundos antes de cada tentativa de ver a versão nova no ar
DIAS_HISTORICO = 56
UA = {"User-Agent": "Mozilla/5.0 (compatible; TransfermedGuardiao/1.0; +https://www.transfermed.com.br)"}


def achado(chave, titulo, corpo, etiqueta="qualidade", auto_fecha=True):
    return monitor.achado(f"guardiao:{chave}", etiqueta, f"Guardião: {titulo}"[:120], corpo, auto_fecha=auto_fecha)


def hoje_brasilia():
    return (datetime.now(timezone.utc) - timedelta(hours=3)).date().isoformat()


# ---------------------------------------------------------------- 0. segurança do banco (RLS)

def checar_rls(testar=seguranca_rls.testar, credenciais=seguranca_rls.credenciais_publicas):
    """Com a chave pública do site, nenhuma tabela pode devolver linha. Vazou: issue `workflow` (a mais urgente), sem fechar sozinha
    no mesmo dia do vazamento; não deu para testar: issue também (segurança não testada não é segurança). Só contagens no texto."""
    url, chave = credenciais()
    if not url or not chave:
        res = {}
        v, tabs = "nao_testado", ["(sem URL ou chave pública)"]
    else:
        res = testar(url, chave)
        v, tabs = seguranca_rls.veredito(res)
    if v == "ok":
        return [], {"rls_anon": "ok", "rls_conferido_em": hoje_brasilia()}
    if v == "vazou":
        return [achado("rls", "a chave pública leu dados do Supabase (RLS falhou)",
                       "A chave pública (anon) do site devolveu linhas nas tabelas: " + ", ".join(tabs) + ".\n\n"
                       "**Fazer agora:** `alter table public.<tabela> enable row level security;` e `revoke all on public.<tabela> from anon, authenticated;` "
                       "(ver `supabase/schema.sql`), depois `python seguranca_rls.py` e este workflow de novo. Avisar o dono. "
                       f"Resultado (só contagens): `{json.dumps(res)}`", etiqueta="workflow", auto_fecha=False)], {"rls_anon": "VAZOU"}
    return [achado("rls_nao_testado", "não deu para testar o RLS do Supabase",
                   "O teste com a chave pública não conseguiu uma resposta em: " + ", ".join(tabs) + f". Resultado: `{json.dumps(res)}`",
                   etiqueta="workflow")], {"rls_anon": "nao_testado"}


# ---------------------------------------------------------------- 1. site no ar

def dias_do_certificado(host, porta=443):
    ctx = ssl.create_default_context()
    with socket.create_connection((host, porta), timeout=20) as s, ctx.wrap_socket(s, server_hostname=host) as t:
        fim = t.getpeercert()["notAfter"]
    return (datetime.fromtimestamp(ssl.cert_time_to_seconds(fim), timezone.utc) - datetime.now(timezone.utc)).days


def versao_do_sw(texto):
    m = re.search(r"const CACHE = '([^']+)'", texto or "")
    return m.group(1) if m else None


def checar_site(http, site=SITE, sw_local=None, espera=ESPERA_DEPLOY, dormir=time.sleep, certificado=dias_do_certificado):
    achados, host = [], re.sub(r"^https?://", "", site)
    try:
        r = http.get(site + "/", timeout=30)
        if r.status_code != 200:
            achados.append(achado("home", "a página inicial não responde 200", f"{site}/ devolveu {r.status_code}.", "link-quebrado"))
    except requests.RequestException as ex:
        achados.append(achado("home", "o site não abre", f"{site}/ falhou: {type(ex).__name__}: {str(ex)[:200]}", "link-quebrado"))
        return achados
    try:
        dias = certificado(host)
        if dias < DIAS_CERTIFICADO:
            achados.append(achado("certificado", f"certificado vence em {dias} dia(s)", f"O certificado https de {host} vence em {dias} dia(s)."))
    except (OSError, ssl.SSLError, KeyError) as ex:
        achados.append(achado("certificado", "não foi possível ler o certificado", f"{host}: {type(ex).__name__}: {str(ex)[:200]}"))
    try:
        r = http.get("http://" + host + "/", timeout=30, allow_redirects=False)
        if not (300 <= r.status_code < 400 and r.headers.get("location", "").startswith("https://")):
            achados.append(achado("http-sem-redirecionar", "http não redireciona para https", f"http://{host}/ devolveu {r.status_code} "
                                  f"(location: {r.headers.get('location')})."))
    except requests.RequestException as ex:
        achados.append(achado("http-sem-redirecionar", "http não respondeu", f"http://{host}/: {type(ex).__name__}: {str(ex)[:200]}"))
    if sw_local:  # o site no ar precisa ser a geração do repositório (deploy parado = prazo velho no ar)
        no_ar = None
        for seg in espera:
            dormir(seg)
            try:
                no_ar = versao_do_sw(http.get(site + "/sw.js", timeout=30).text)
            except requests.RequestException:
                no_ar = None
            if no_ar == sw_local:
                break
        if no_ar != sw_local:
            achados.append(achado("deploy-defasado", "o site no ar não é a versão do repositório",
                                  f"A versão do `sw.js` no ar é {no_ar}, a do repositório é {sw_local}, mesmo depois de {sum(espera) // 60} min. "
                                  "O GitHub Pages pode ter falhado: ver a aba Actions (pages build and deployment)."))
    return achados


def urls_do_sitemap(texto):
    return re.findall(r"<loc>([^<]+)</loc>", texto)


def checar_sitemap(http, site=SITE, simultaneos=8):
    try:
        r = http.get(site + "/sitemap.xml", timeout=30)
        urls = urls_do_sitemap(r.text) if r.status_code == 200 else []
    except requests.RequestException:
        urls = []
    if not urls:
        return [achado("sitemap", "o sitemap não abre ou está vazio", f"{site}/sitemap.xml sem páginas.", "link-quebrado")], 0

    def status(u):
        for _ in range(2):
            try:
                return u, http.get(u, timeout=30).status_code
            except requests.RequestException:
                time.sleep(2)
        return u, 0
    with ThreadPoolExecutor(simultaneos) as ex:
        ruins = [(u, c) for u, c in ex.map(status, urls) if c != 200]
    if not ruins:
        return [], len(urls)
    lista = "\n".join(f"- {u}: {c or 'sem resposta'}" for u, c in ruins[:30])
    return [achado("sitemap-paginas", f"{len(ruins)} página(s) do sitemap não respondem 200",
                   f"De {len(urls)} páginas do sitemap, {len(ruins)} falharam:\n{lista}", "link-quebrado")], len(urls)


# ---------------------------------------------------------------- 2. prazos vencidos ainda abertos no ar

def editais_do_dados_js(texto):
    """Lista de editais (id, slug, fim) do dados.js publicado, sem depender do resto do arquivo."""
    return [{"slug": m.group(1), "fim": m.group(2)} for m in re.finditer(r'"slug":"([^"]+)".*?"fim":(?:"(\d{4}-\d{2}-\d{2})"|null)', texto) if m.group(2)]


def checar_prazos_no_ar(http, hoje, site=SITE):
    try:
        lista = editais_do_dados_js(http.get(site + "/dados.js", timeout=30).text)
    except requests.RequestException as ex:
        return [achado("dados", "dados.js não abre", f"{type(ex).__name__}: {str(ex)[:200]}", "link-quebrado")], 0
    vencidos = [e for e in lista if e["fim"] < hoje]

    def mostra_aberto(e):
        try:
            return e["slug"] if re.search(r"Inscrições abertas até", http.get(f"{site}/edital/{e['slug']}/", timeout=30).text) else None
        except requests.RequestException:
            return None
    with ThreadPoolExecutor(8) as ex:
        errados = [x for x in ex.map(mostra_aberto, vencidos) if x]
    if not errados:
        return [], len(lista)
    return [achado("prazo-vencido-aberto", f"{len(errados)} edital(is) com prazo vencido ainda aberto(s) no ar",
                   "As páginas abaixo mostram \"Inscrições abertas até\" depois do prazo:\n" + "\n".join(f"- {site}/edital/{s}/" for s in errados),
                   "prazo")], len(lista)


# ---------------------------------------------------------------- 3. PDFs dos editais abertos

def checar_pdfs_abertos(editais, hoje, http, regras=()):
    ruins = []
    for e in editais:
        if not gerar_site.publicavel(e) or radar.situacao(e, hoje) != "aberto" or e.get("fluxo_continuo") or monitor.excecao(e["url_edital"], regras):
            continue
        try:
            r = http.get(e["url_edital"], timeout=40, stream=True)
            codigo = r.status_code
            r.close()
        except requests.RequestException:
            codigo = 0
        if codigo != 200:
            ruins.append((e, codigo))
    if not ruins:
        return []
    corpo = "\n".join(f"- {e['url_edital']}: {c or 'sem resposta'} (edital {e['id']})" for e, c in ruins)
    return [achado("pdfs", f"{len(ruins)} PDF(s) de edital aberto não abrem", corpo + "\n\nConferir no navegador; o monitor.py cuida do hash.", "link-quebrado")]


# ---------------------------------------------------------------- 4. e-mail (DNS público)

def dns_txt(http, nome, tipo="TXT"):
    r = http.get("https://dns.google/resolve", params={"name": nome, "type": tipo}, timeout=20)
    return [a.get("data", "").strip('"').replace('" "', "") for a in r.json().get("Answer", [])]


def checar_email(http, dominio=DOMINIO, consulta=dns_txt):
    problemas, politica = [], None
    try:
        spf = [t for t in consulta(http, dominio) if t.lower().startswith("v=spf1")]
        if not spf:
            problemas.append("SPF ausente")
        elif not re.search(r"brevo|sendinblue", spf[0], re.I):
            problemas.append("SPF não autoriza o Brevo")
        dmarc = [t for t in consulta(http, "_dmarc." + dominio) if t.lower().startswith("v=dmarc1")]
        if not dmarc:
            problemas.append("DMARC ausente")
        else:
            m = re.search(r"\bp=(\w+)", dmarc[0])
            politica = m.group(1) if m else None
        dkim = [s for s in ("brevo1", "brevo2", "mail") if consulta(http, f"{s}._domainkey.{dominio}", "CNAME") or consulta(http, f"{s}._domainkey.{dominio}")]
        if not dkim:
            problemas.append("DKIM do Brevo não encontrado (brevo1/brevo2/mail._domainkey)")
        if not consulta(http, dominio, "MX"):
            problemas.append("MX ausente")
    except (requests.RequestException, ValueError) as ex:
        return [], None, f"consulta DNS indisponível ({type(ex).__name__})"  # falha do próprio DNS-sobre-https não vira alarme falso
    if not problemas:
        return [], politica, None
    return [achado("email", "autenticação do e-mail com problema", "- " + "\n- ".join(problemas) +
                   "\n\nSem isso os alertas vão para o spam. Só leitura: nenhum e-mail foi enviado.")], politica, None


# ---------------------------------------------------------------- 5. quarentena

def calcular_quarentena(editais, retratos_pdfs_trocados, anterior, hoje):
    """`retratos_pdfs_trocados`: {url: dia em que o monitor viu o hash mudar}. Entra na quarentena o edital publicado e
    vigente cujo documento mudou depois de `conferido_em`. Sai sozinha quando a conferência é refeita (ver gerar_site)."""
    q = {}
    for e in editais:
        if not gerar_site.publicavel(e) or radar.situacao(e, hoje) == "encerrado":
            continue
        for url in [e["url_edital"], *e.get("anexos", [])]:
            dia = retratos_pdfs_trocados.get(url)
            if dia and dia > (e.get("conferido_em") or ""):
                q[e["id"]] = {"desde": dia, "motivo": "pdf_trocado", "url": url}
    for eid, item in (anterior or {}).items():  # o que já estava e ainda não foi reconferido continua
        ed = next((x for x in editais if x["id"] == eid), None)
        if ed and eid not in q and (ed.get("conferido_em") or "") < item["desde"]:
            q[eid] = item
    return q


def gravar_quarentena(novos_trocados, hoje, editais, caminho=gerar_site.QUARENTENA):
    """Chamado pelo monitor quando vê um PDF trocado. Devolve a quarentena resultante."""
    try:
        atual = json.loads(caminho.read_text(encoding="utf-8")).get("editais", {})
    except (OSError, ValueError):
        atual = {}
    q = calcular_quarentena(editais, novos_trocados, atual, hoje)
    caminho.write_text(json.dumps({"atualizado_em": hoje, "editais": q}, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    return q


def esperando_conferencia(editais, hoje):
    return sum(1 for e in editais if not gerar_site.publicavel(e) and gerar_site.novo_detectado(e, hoje))


# ---------------------------------------------------------------- resumo e execução

def atualizar_resumo(resumo, hoje, achados, extra, caminho=RESUMO):
    hist = [h for h in (resumo.get("historico") or []) if h["dia"] != hoje]
    hist.append({"dia": hoje, "falhas": len(achados), "chaves": sorted(a["chave"] for a in achados)})
    limite = (date.fromisoformat(hoje) - timedelta(days=DIAS_HISTORICO)).isoformat()
    novo = {"ultima_execucao": hoje, "historico": [h for h in hist if h["dia"] >= limite], **extra}
    caminho.write_text(json.dumps(novo, ensure_ascii=False, indent=1), encoding="utf-8")
    return novo


def linha_semanal(resumo, hoje):
    """Uma linha para o relatório de segunda: dias vigiados na semana e falhas, mais a política do DMARC."""
    if not resumo:
        return "Guardião: ainda sem execução registrada."
    ini = (date.fromisoformat(hoje) - timedelta(days=7)).isoformat()
    sem = [h for h in resumo.get("historico", []) if h["dia"] > ini]
    if not sem:
        return "Guardião: nenhuma execução nos últimos 7 dias (conferir o workflow guardiao.yml)."
    com = [h for h in sem if h["falhas"]]
    q = resumo.get("quarentena", 0)
    txt = f"Guardião: {len(sem)} de 7 dias vigiados, " + ("nenhuma falha" if not com else f"falhas em {len(com)} dia(s): " + ", ".join(sorted({c for h in com for c in h['chaves']})))
    txt += f"; {q} edital(is) em quarentena; {resumo.get('aguardando_conferencia', 0)} do robô esperando conferência"
    if resumo.get("rls_anon"):
        txt += f"; RLS com a chave pública: {resumo['rls_anon']} (conferido em {resumo.get('rls_conferido_em', '?')})"
    if resumo.get("dmarc"):
        txt += f"; DMARC p={resumo['dmarc']}"
    return txt + "."


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sem-rede", action="store_true")
    ap.add_argument("--hoje", default=hoje_brasilia())
    ap.add_argument("--sem-deploy", action="store_true", help="não espera o deploy (teste local)")
    args = ap.parse_args(argv)
    hoje = args.hoje
    editais = radar.ler_json(radar.EDITAIS, [])
    resumo = radar.ler_json(RESUMO, {})
    achados, extra = [], {}
    try:
        quarentena = json.loads(gerar_site.QUARENTENA.read_text(encoding="utf-8")).get("editais", {})
    except (OSError, ValueError):
        quarentena = {}
    extra["quarentena"] = len(quarentena)
    extra["aguardando_conferencia"] = esperando_conferencia(editais, hoje)
    if not args.sem_rede:
        http = requests.Session()
        http.headers.update(UA)
        sw_local = versao_do_sw((PASTA / "docs" / "sw.js").read_text(encoding="utf-8"))
        achados += checar_site(http, sw_local=sw_local, espera=(0,) if args.sem_deploy else ESPERA_DEPLOY)
        a, n = checar_sitemap(http)
        achados += a
        extra["paginas_no_sitemap"] = n
        a, n = checar_prazos_no_ar(http, hoje)
        achados += a
        achados += checar_pdfs_abertos(editais, hoje, http, monitor.excecoes())
        a, ext = checar_rls()
        achados += a
        extra.update(ext)
        a, politica, indisp = checar_email(http)
        achados += a
        extra["dmarc"] = politica
        if indisp:
            print("E-mail:", indisp)
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps({"gerado_em": hoje, "achados": achados}, ensure_ascii=False, indent=2), encoding="utf-8")
    atualizar_resumo(resumo, hoje, achados, extra)
    print(f"Guardião em {hoje}: {len(achados)} falha(s)")
    for a in achados:
        print(f"  [{a['etiqueta']}] {a['titulo']}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
