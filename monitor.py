"""
Monitor diário do Transfermed (Camada 1, sem IA). Roda no GitHub Actions (monitor.yml).

O que faz:
1. Retratos: para cada faculdade, guarda em data/retratos.json o conjunto de links de edital achados nas páginas de
   seleção (mesmos filtros do robô) e o hash dos PDFs dos editais publicados que ainda estão valendo. Se algo mudar
   (link novo de edital, PDF trocado, página fora do ar), vira um achado.
2. Prazos e coerência: inscrições que encerram em até 7 dias, datas impossíveis, editais publicados marcados para
   conferir e fichas sem conferência há mais de 30 dias.
3. Editais novos achados pelo robô e ainda não conferidos; retificações pendentes (pelo estado da base).
4. Correção automática segura: se a situação gravada de um edital está velha (ex.: "aberto" depois do prazo),
   recalcula e gera o site de novo. O workflow só publica se os testes passarem.

Saída: qa/relatorios/achados_monitor.json (uma lista de achados), que o issues.py transforma em issues.

Uso:
  python monitor.py                 # tudo
  python monitor.py --sem-rede      # só prazos, coerência e revisões pendentes (sem visitar sites)
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import radar
import gerar_site

PASTA = Path(__file__).resolve().parent
RETRATOS = PASTA / "data" / "retratos.json"
SAIDA = PASTA / "qa" / "relatorios" / "achados_monitor.json"
EXCECOES = PASTA / "qa" / "links_excecoes.txt"
SITE = "https://www.transfermed.com.br"
DIAS_PRAZO = 7
DIAS_SEM_CONFERENCIA = 30
FALHAS_PARA_AVISAR = 3  # dias seguidos de erro numa página que já abriu antes


def excecoes():
    linhas = EXCECOES.read_text(encoding="utf-8").splitlines() if EXCECOES.exists() else []
    return [re.compile(l.strip()) for l in linhas if l.strip() and not l.startswith("#")]


def excecao(url, regras):
    return any(r.search(url) for r in regras)


def fmt(iso):
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso else "?"


def link_edital(ed):
    return f"{SITE}/edital/{gerar_site.slug_edital(ed)}/"


def achado(chave, etiqueta, titulo, corpo, auto_fecha=True, estavel=None):
    """auto_fecha: o issues.py fecha a issue sozinho quando o problema some (prazo passou, página voltou...).
    Edital novo e retificação não fecham sozinhos: precisam de alguém que leia o PDF."""
    d = {"chave": chave, "etiqueta": etiqueta, "titulo": titulo, "corpo": corpo, "auto_fecha": auto_fecha}
    if estavel:
        d["estavel"] = estavel  # o que identifica o problema sem as partes que mudam todo dia
    return d


# ---------------------------------------------------------------- prazos e coerência (sem rede)

def checar_prazos(editais, faculdades, hoje):
    achados = []
    limite = (date.fromisoformat(hoje) + timedelta(days=DIAS_PRAZO)).isoformat()
    for e in editais:
        if not gerar_site.publicavel(e):
            continue
        fac = faculdades.get(e["faculdade_id"], {})
        nome = f'{fac.get("sigla", e["faculdade_id"])} ({fac.get("cidade", "?")})'
        sit = radar.situacao(e, hoje)
        fim = e.get("inscricao_fim")
        if sit == "aberto" and fim and fim <= limite:
            dias = (date.fromisoformat(fim) - date.fromisoformat(hoje)).days
            quando = "hoje" if dias == 0 else ("amanhã" if dias == 1 else f"em {dias} dias")
            achados.append(achado(
                f"prazo:{e['id']}", "prazo",
                f"Prazo: {nome}, {gerar_site.MODALIDADES.get(e.get('modalidade'), (e.get('modalidade'),))[0].lower()}, "
                f"encerra {quando} ({fmt(fim)})",
                f"**{fac.get('nome', nome)}** · {e.get('modalidade')} · ingresso {e.get('semestre_ingresso', '?')}\n\n"
                f"- Inscrições até **{fmt(fim)}**\n- Página: {link_edital(e)}\n- Edital oficial: {e['url_edital']}\n\n"
                "Conferir se não saiu prorrogação ou retificação antes do fim do prazo.",
                estavel=f"prazo:{e['id']}:{fim}"))
        if sit != "encerrado":
            problemas = radar.problemas_de_data(e, hoje)
            if problemas:
                achados.append(achado(
                    f"datas:{e['id']}", "conferir", f"Datas incoerentes: {nome} ({e.get('semestre_ingresso', '?')})",
                    "Problemas achados por código:\n" + "".join(f"- {p}\n" for p in problemas) +
                    f"\nPágina: {link_edital(e)}\nEdital oficial: {e['url_edital']}\n\n"
                    "Conferir no PDF. Se o próprio edital estiver errado, manter `status: conferir` e explicar na `observacao`."))
            if e.get("status") == "conferir":
                obs = radar.normalizar(e.get("observacao") or "")
                retif = "retificacao publicada" in obs or "o pdf mudou" in obs
                achados.append(achado(
                    f"conferir:{e['id']}", "retificação" if retif else "conferir", f"Conferir: {nome} ({e.get('semestre_ingresso', '?')}, {e.get('modalidade')})",
                    f"O edital está publicado com aviso de conferência.\n\n> {e.get('observacao') or 'sem observação'}\n\n"
                    f"Página: {link_edital(e)}\nEdital oficial: {e['url_edital']}\n\n"
                    "Resolver: ler o PDF oficial (e retificações), confirmar ou corrigir os dados e, se ficar tudo certo, "
                    "passar para `status: ok`."))
    antigas = sorted((f.get("ultima_conferencia") or "0000-00-00", f["id"]) for f in faculdades.values()
                     if (f.get("ultima_conferencia") or "0000-00-00") <
                     (date.fromisoformat(hoje) - timedelta(days=DIAS_SEM_CONFERENCIA)).isoformat())
    if antigas:
        achados.append(achado(
            "fichas-sem-conferencia", "conferir", f"{len(antigas)} ficha(s) sem conferência há mais de {DIAS_SEM_CONFERENCIA} dias",
            "Fichas cuja `ultima_conferencia` passou do limite (conferir site, página de editais e histórico):\n\n" +
            "".join(f"- `{fid}`: {fmt(d) if d != '0000-00-00' else 'nunca'}\n" for d, fid in antigas[:80])))
    return achados


def checar_revisao(editais, faculdades, hoje):
    """Editais novos achados pelo robô e ainda não conferidos à mão (o achado some quando o edital é revisado:
    vira `fonte_dados: manual` ou sai da base)."""
    achados = []
    for e in editais:
        if not gerar_site.novo_detectado(e, hoje):
            continue
        fac = faculdades.get(e["faculdade_id"], {})
        achados.append(achado(
            f"novo:{e['id']}", "edital-novo", f"Edital novo detectado: {fac.get('sigla', e['faculdade_id'])} ({fac.get('cidade', '?')})",
            f"O robô achou em {fmt(e.get('detectado_em'))} um PDF que parece edital do ciclo atual e ainda não foi "
            f"conferido:\n\n{e['url_edital']}\n\nLeitura automática (pode estar errada): ingresso "
            f"{e.get('semestre_ingresso', '?')}, inscrições {fmt(e.get('inscricao_inicio'))} a {fmt(e.get('inscricao_fim'))}.\n\n"
            "Ler o PDF oficial. Se for edital de transferência de Medicina do ciclo atual, preencher os dados com a página "
            "de cada campo em `evidencias` e `fonte_dados: manual`. Se não for (anexo, resultado, outro curso), tirar da "
            "base e marcar a URL como `conhecida` em processados.json."))
    return achados


def corrigir_situacoes(editais, hoje):
    """Única correção feita sem pedir: a situação (aberto/encerrado...) é calculada pelas datas do edital."""
    mudados = []
    for e in editais:
        nova = radar.situacao(e, hoje)
        if e.get("situacao") != nova:
            mudados.append(f'{e["faculdade_id"]} {e.get("semestre_ingresso", "")}: {e.get("situacao")} -> {nova}')
            e["situacao"] = nova
    return mudados


# ---------------------------------------------------------------- retratos (com rede)

def assinatura(urls):
    return hashlib.sha256("\n".join(sorted(urls)).encode()).hexdigest()[:16]


def sem_ancora(url):
    """A parte depois do # não é outro documento (a UMC gera âncoras aleatórias a cada carregamento)."""
    return radar.chave_url(url.split("#")[0])


def falhou_tudo(erros, fontes, links):
    """Página "fora do ar" só quando todas as fontes da ficha deram erro. Uma página que abre sem link de edital
    (nada publicado agora) não é falha, mesmo que outra fonte da mesma ficha esteja bloqueada."""
    return bool(erros) and not links and len(erros) >= len(fontes)


def retratar_paginas(faculdades, editais, processados, retratos, regras, hoje):
    achados, conhecidos = [], {radar.chave_url(e["url_edital"]) for e in editais} | set(processados)
    paginas = retratos.setdefault("paginas", {})
    nunca_abriram = []
    for fac in faculdades.values():
        if not (fac.get("paginas_editais") or fac.get("wordpress") or fac.get("api_noticias")):
            continue
        resumo = {"erros": []}
        links = radar.coletar_links(fac, resumo)
        anterior = paginas.get(fac["id"], {})
        fontes = fac.get("paginas_editais", []) + ([fac["wordpress"]] if fac.get("wordpress") else [])
        bloqueado = all(excecao(u, regras) for u in fontes) if fontes else False
        if falhou_tudo(resumo["erros"], fontes, links):
            falhas = anterior.get("falhas_seguidas", 0) + 1
            paginas[fac["id"]] = {**anterior, "falhas_seguidas": falhas, "ultimo_erro": resumo["erros"][0][:300],
                                  "verificado_em": hoje}
            if bloqueado:
                continue
            if anterior.get("ultimo_ok") and falhas >= FALHAS_PARA_AVISAR:
                achados.append(achado(
                    f"fora-do-ar:{fac['id']}", "link-quebrado", f"Página de editais fora do ar: {fac['sigla']} ({fac['cidade']})",
                    f"A página não abre há {falhas} dias seguidos (último sucesso em {fmt(anterior['ultimo_ok'])}).\n\n"
                    f"Erro: `{resumo['erros'][0][:300]}`\n\nPáginas da ficha:\n" + "".join(f"- {u}\n" for u in fontes) +
                    "\nConferir no navegador. Se o endereço mudou, atualizar `paginas_editais` na ficha."))
            elif not anterior.get("ultimo_ok"):
                nunca_abriram.append((fac, resumo["erros"][0]))
            continue
        urls = sorted({sem_ancora(u) for u, _ in links})
        antes = {sem_ancora(u) for u in anterior.get("links", [])}
        novos = [u for u in urls if u not in antes and u not in conhecidos]
        if anterior.get("links") is not None and novos:  # no primeiro retrato não há com o que comparar
            achados.append(achado(
                f"pagina-nova:{fac['id']}:{assinatura(novos)}", "edital-novo",
                f"Link novo na página de editais: {fac['sigla']} ({fac['cidade']})",
                "Links que parecem edital e não existiam no retrato anterior "
                f"({fmt(anterior.get('verificado_em'))}):\n\n" + "".join(f"- https://{u}\n" for u in novos[:20]) +
                "\nO robô vai ler esses PDFs na próxima rodada; confira se algum é edital de transferência de Medicina "
                "do ciclo atual e preencha à mão a partir do PDF.", auto_fecha=False))
        paginas[fac["id"]] = {"links": urls, "hash": assinatura(urls), "verificado_em": hoje, "ultimo_ok": hoje,
                              "falhas_seguidas": 0}
    nunca_abriram = [(f, e) for f, e in nunca_abriram if not f.get("pendente")]
    if nunca_abriram:
        achados.append(achado(
            "paginas-sem-acesso", "link-quebrado", f"{len(nunca_abriram)} página(s) de editais que o GitHub não consegue abrir",
            "Estas fichas têm página de editais, mas ela nunca abriu nos servidores do GitHub (bloqueio, certificado ou "
            "lentidão). Conferir no navegador: se abrir, incluir o site em `qa/links_excecoes.txt`; se mudou de "
            "endereço, corrigir a ficha.\n\n" +
            "".join(f"- `{f['id']}`: {e[:160]}\n" for f, e in nunca_abriram)))
    return achados


def retratar_pdfs(editais, faculdades, retratos, regras, hoje):
    """Hash dos PDFs dos editais publicados que ainda valem: se trocar, é retificação silenciosa; se sumir, link quebrado."""
    achados, pdfs = [], retratos.setdefault("pdfs", {})
    for e in editais:
        if not gerar_site.publicavel(e) or radar.situacao(e, hoje) == "encerrado" or e.get("fluxo_continuo"):
            continue
        url, chave = e["url_edital"], radar.chave_url(e["url_edital"])
        fac = faculdades.get(e["faculdade_id"], {})
        nome = f'{fac.get("sigla", e["faculdade_id"])} ({fac.get("cidade", "?")})'
        anterior = pdfs.get(chave, {})
        try:
            conteudo = radar.baixar_pdf(url)
            erro = None if conteudo is not None else "o endereço não devolve um PDF"
        except Exception as ex:  # noqa: BLE001 - qualquer falha de rede conta como "não abriu"
            conteudo, erro = None, f"{type(ex).__name__}: {str(ex)[:200]}"
        if conteudo is None:
            falhas = anterior.get("falhas_seguidas", 0) + 1
            pdfs[chave] = {**anterior, "falhas_seguidas": falhas, "ultimo_erro": erro, "verificado_em": hoje}
            if not excecao(url, regras) and (anterior.get("ultimo_ok") or falhas >= FALHAS_PARA_AVISAR):
                achados.append(achado(
                    f"pdf-quebrado:{e['id']}", "link-quebrado", f"Edital oficial não abre: {nome}",
                    f"O PDF do edital publicado não abriu ({erro}), {falhas} dia(s) seguido(s).\n\n"
                    f"Edital: {url}\nPágina: {link_edital(e)}\n\n"
                    "Conferir no navegador. Se a faculdade trocou o endereço, atualizar `url_edital` (e conferir se o "
                    "conteúdo é o mesmo)."))
            continue
        h = hashlib.sha256(conteudo).hexdigest()
        if anterior.get("hash") and anterior["hash"] != h:
            achados.append(achado(
                f"pdf-trocado:{e['id']}:{h[:12]}", "retificação", f"PDF do edital mudou: {nome}",
                f"O arquivo do edital publicado foi trocado no mesmo endereço (retrato de {fmt(anterior.get('verificado_em'))} "
                f"× hoje).\n\nEdital: {url}\nPágina: {link_edital(e)}\n\n"
                "Pode ser retificação silenciosa: reler o PDF e conferir datas, vagas e requisitos.", auto_fecha=False))
        pdfs[chave] = {"hash": h, "verificado_em": hoje, "ultimo_ok": hoje, "falhas_seguidas": 0}
    return achados


# ---------------------------------------------------------------- execução

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sem-rede", action="store_true", help="não visita sites (só prazos, coerência e robô)")
    ap.add_argument("--hoje", default=date.today().isoformat())
    args = ap.parse_args(argv)
    hoje = args.hoje
    faculdades = {f["id"]: f for f in radar.ler_json(radar.FACULDADES, [])}
    editais = radar.ler_json(radar.EDITAIS, [])
    processados = {radar.chave_url(u): v for u, v in radar.ler_json(radar.PROCESSADOS, {}).items()}
    retratos = radar.ler_json(RETRATOS, {})
    regras = excecoes()

    achados = checar_prazos(editais, faculdades, hoje)
    achados += checar_revisao(editais, faculdades, hoje)
    if not args.sem_rede:
        achados += retratar_paginas(faculdades, editais, processados, retratos, regras, hoje)
        achados += retratar_pdfs(editais, faculdades, retratos, regras, hoje)
        retratos["atualizado_em"] = hoje
        radar.salvar_json(RETRATOS, retratos)

    mudados = corrigir_situacoes(editais, hoje)
    if mudados:
        radar.salvar_json(radar.EDITAIS, editais)
        radar.salvar_json(radar.SITE_DADOS, editais)
        gerar_site.main()
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps({"gerado_em": hoje, "correcoes": mudados, "achados": achados},
                                ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Achados: {len(achados)}")
    for a in achados:
        print(f"  [{a['etiqueta']}] {a['titulo']}")
    print(f"Correções automáticas (situação): {len(mudados)}")
    for m in mudados:
        print(f"  {m}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
