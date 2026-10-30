"""
Gera o site estático em docs/ a partir de data/faculdades.json e data/editais.json.

Páginas: início (com o mapa-radar), diagnóstico, estudo no exterior, uma por faculdade e uma por edital
(com linha do tempo, calendário .ics e imagem de prévia para WhatsApp/redes). Também gera o manifesto
do aplicativo (PWA) e o service worker. Roda no fim do radar.py ou sozinho: `python gerar_site.py`.

Só entram nas listas, no diagnóstico e nas páginas de edital os editais conferidos à mão (fonte_dados
"manual"). Os lidos só pelo robô aparecem no histórico da faculdade, marcados como "não revisado".
"""
import hashlib
import json
import os
import re
import shutil
import unicodedata
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path
from urllib.parse import quote, urlparse

import isca as isca_mod

PASTA = Path(__file__).resolve().parent
DOCS = PASTA / "docs"
# endereço público do site (as prévias de WhatsApp/redes precisam de link completo)
SITE_URL = (os.environ.get("SITE_URL") or "https://www.transfermed.com.br").rstrip("/")
# alertas: endereço do Supabase e chave pública "anon" (feita para ficar no navegador; só chama as funções do banco)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
CONTATO_EMAIL = os.environ.get("CONTATO_EMAIL", "")
# fora do GitHub (geração local), as variáveis públicas do GitHub vêm de privado/variaveis.env (KEY=VALOR por linha):
# sem isso, uma geração local publicada desligava o contato e o aviso de envio imediato
_VARS_LOCAIS = Path(__file__).resolve().parent / "privado" / "variaveis.env"
if not os.environ.get("GITHUB_ACTIONS") and _VARS_LOCAIS.exists():
    for _linha in _VARS_LOCAIS.read_text(encoding="utf-8").splitlines():
        _k, _, _v = _linha.partition("=")
        if _k.strip() and not _k.startswith("#"):
            os.environ.setdefault(_k.strip(), _v.strip())

# formulário de contato: só liga quando a tabela "mensagens" existir no Supabase (variável CONTATO_ATIVO=1 no GitHub)
CONTATO_ATIVO = os.environ.get("CONTATO_ATIVO", "") == "1"
# foto do dono: só aparece depois de aprovada (os arquivos entram em docs/assets/sobre/ à mão; o original nunca)
FOTO = "assets/sobre/caua"
FOTO_ALT = "Cauã Marin, estudante de Medicina, durante aula de semiologia"  # contato do responsável pelos dados (página de privacidade)
CONSENTIMENTO = ("Quero receber por e-mail alertas de editais de transferência de Medicina compatíveis com o meu perfil, "
                 "os lembretes de prazo que eu pedir, um resumo semanal quando houver novidade e, nas duas primeiras "
                 "semanas, algumas dicas sobre transferência. Sei que posso cancelar a qualquer momento pelo link presente em todo e-mail, o que apaga os meus dados.")
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]
MODALIDADES = {
    "externa": ("Transferência externa", "Para quem cursa Medicina em outra faculdade"),
    "interna": ("Transferência interna", "Para quem já estuda outro curso nesta faculdade"),
    "exterior": ("Para quem estuda no exterior", "Edital próprio para alunos de faculdades estrangeiras"),
    "portador_diploma": ("Outro curso da saúde ou diplomado", "Para aluno de outro curso da saúde ou formado na área"),
    "ex_officio": ("Ex officio", "Transferência obrigatória por lei"),
}
CAPITAIS = [["Rio Branco", "AC", -9.975, -67.81], ["Maceió", "AL", -9.665, -35.735], ["Macapá", "AP", 0.034, -51.069],
            ["Manaus", "AM", -3.119, -60.022], ["Salvador", "BA", -12.971, -38.511], ["Fortaleza", "CE", -3.732, -38.527],
            ["Brasília", "DF", -15.794, -47.882], ["Vitória", "ES", -20.315, -40.312], ["Goiânia", "GO", -16.686, -49.264],
            ["São Luís", "MA", -2.53, -44.303], ["Cuiabá", "MT", -15.601, -56.097], ["Campo Grande", "MS", -20.469, -54.62],
            ["Belo Horizonte", "MG", -19.917, -43.935], ["Belém", "PA", -1.456, -48.49], ["João Pessoa", "PB", -7.115, -34.864],
            ["Curitiba", "PR", -25.428, -49.273], ["Recife", "PE", -8.048, -34.877], ["Teresina", "PI", -5.092, -42.804],
            ["Rio de Janeiro", "RJ", -22.907, -43.173], ["Natal", "RN", -5.795, -35.209], ["Porto Alegre", "RS", -30.035, -51.218],
            ["Porto Velho", "RO", -8.762, -63.904], ["Boa Vista", "RR", 2.82, -60.672], ["Florianópolis", "SC", -27.595, -48.548],
            ["São Paulo", "SP", -23.551, -46.633], ["Aracaju", "SE", -10.947, -37.073], ["Palmas", "TO", -10.184, -48.333]]
# mapa: mesma projeção de app.js (x = (lon + 74) * 10 ; y = (6 - lat) * 10)
VISTA_BRASIL = "0 0 400 400"
VISTA_REGIAO = "190 195 150 140"  # vira "Perto de você" quando há perfil salvo (app.js)
NOMES_UF = {"AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal",
            "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul",
            "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco", "PI": "Piauí",
            "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima",
            "SC": "Santa Catarina", "SP": "São Paulo", "SE": "Sergipe", "TO": "Tocantins"}
# "na Bahia", "no Paraná", "em São Paulo"
PREP_UF = {"BA": "na", "PB": "na", **{uf: "no" for uf in ("AC", "AP", "AM", "CE", "DF", "ES", "MA", "PA", "PI", "PR", "RJ", "RN", "RS", "TO")}}
# estados com página própria: os com 5 ou mais faculdades na base (a mesma regra dos botões do mapa); preenchido no main
ESTADOS = []


def em_uf(uf):
    return f"{PREP_UF.get(uf, 'em')} {NOMES_UF.get(uf, uf)}"


def trilha_estado(raiz, uf):
    return f' › <a href="{raiz}estado/{uf.lower()}/">{e(NOMES_UF.get(uf, uf))}</a>' if uf in ESTADOS else ""


def rodape_estados(raiz):
    if not ESTADOS:
        return ""
    links = " · ".join(f'<a href="{raiz}estado/{uf.lower()}/">{e(NOMES_UF.get(uf, uf))}</a>' for uf in ESTADOS)
    return f'<div><p><strong>Por estado:</strong> {links}</p></div>'


# data em que o texto das páginas institucionais mudou pela última vez (vai para o lastmod do sitemap)
TEXTO_ATUALIZADO = {"diagnostico/": "2026-10-28", "sobre/": "2026-10-28", "contato/": "2026-10-28", "privacidade/": "2026-10-28"}
CENTRO_RADAR = (-20.2836, -50.2463)  # Fernandópolis


def e(texto):
    return escape(str(texto if texto is not None else ""), quote=True)


def fmt(d):
    return "/".join(reversed(d.split("-"))) if d else "?"


def dinheiro(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def slug(texto):
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def slug_edital(ed):
    return f"{ed['faculdade_id']}-{ed.get('modalidade', 'externa')}-{slug(ed.get('semestre_ingresso') or 'sem-data')}-{ed['id'][:6]}"


def publicavel(ed):
    """Só vai para as listas e o diagnóstico com dados completos o que foi conferido à mão."""
    return ed.get("fonte_dados") == "manual"


def novo_detectado(ed, hoje, dias=60):
    """Edital achado pelo robô e ainda não revisado: aparece só como aviso ("novo, confira no PDF"),
    sem datas nem vagas, para o aluno não perder o edital e o site não afirmar o que não foi conferido."""
    if publicavel(ed) or not ed.get("detectado_em"):
        return False
    recente = (date.fromisoformat(hoje) - date.fromisoformat(ed["detectado_em"])).days <= dias
    return recente and parece_atual(ed, hoje, dias)


def parece_atual(ed, hoje, dias=60):
    """Só é "novo" o edital com sinal de ser do ciclo atual. A leitura automática erra datas, e uma faculdade
    recém-incluída traz de uma vez os PDFs dos últimos 2 anos: sem isso, edital de 2024 apareceria como novo."""
    if ed.get("inscricao_fim"):
        return ed["inscricao_fim"] >= hoje
    if ed.get("inscricao_inicio") and ed["inscricao_inicio"] >= hoje:
        return True
    d = date.fromisoformat(hoje)
    m = re.match(r"(20\d\d)(?:\.([12]))?", str(ed.get("semestre_ingresso") or ""))
    if m:  # ingresso no próximo semestre ou depois
        proximo = (d.year, 2) if d.month <= 6 else (d.year + 1, 1)
        return (int(m.group(1)), int(m.group(2) or 1)) >= proximo
    m = re.search(r"/uploads/(20\d\d)/(\d\d)/", ed.get("url_edital", ""))
    if m:  # PDF publicado há pouco (pasta de envio do WordPress)
        return (d - date(int(m.group(1)), int(m.group(2)), 1)).days <= dias + 31
    return False


def com_robo(f):
    """Faculdade em que o robô visita de fato a página onde saem os editais (sem pendência na ficha)."""
    return bool(f.get("paginas_editais") or f.get("wordpress") or f.get("api_noticias")) and not f.get("pendente")


def proj(lat, lon):
    return (lon + 74) * 10, (6 - lat) * 10


def situacao(ed, hoje):
    if ed.get("fluxo_continuo"):
        return "contínuo"
    fim, ini = ed.get("inscricao_fim"), ed.get("inscricao_inicio")
    if not fim:
        return "encerrado" if ed.get("situacao") == "encerrado" else "desconhecida"
    if hoje > fim:
        return "encerrado"
    if ini and hoje < ini:
        return "em breve"
    return "aberto"


def texto_situacao(ed, hoje):
    s = situacao(ed, hoje)
    if s == "aberto":
        dias = (date.fromisoformat(ed["inscricao_fim"]) - date.fromisoformat(hoje)).days
        if dias <= 2:
            return "alerta", "Encerra hoje" if dias <= 0 else f"Encerra em {dias} {'dia' if dias == 1 else 'dias'}"
        if dias <= 10:
            return "aviso", f"Inscrições encerram em {dias} dias"
        return "ok", f"Inscrições abertas até {fmt(ed['inscricao_fim'])}"
    if s == "em breve":
        return "aviso", f"Inscrições abrem em {fmt(ed['inscricao_inicio'])}"
    if s == "contínuo":
        return "ok", "Pedidos o ano todo (sem edital)"
    if s == "encerrado":
        return "", f"Encerrado{' em ' + fmt(ed['inscricao_fim']) if ed.get('inscricao_fim') else ''}"
    return "", "Datas no edital"


def documentos(ed):
    return (ed.get("documentos") or []), not ed.get("documentos")


def dominio(url):
    """'https://www.famerp.br/?s=x' -> 'famerp.br' (texto do link; o endereço completo continua no href)."""
    return re.sub(r"^www\.", "", urlparse(url).netloc) or url


def no_semestre(sem):
    """'2º ao 7º' -> 'do 2º ao 7º'; '5º ano' -> 'no 5º ano'; 'a definir no edital' -> ': a definir no edital'."""
    if (sem or "").strip().lower() in ("não informado", "nao informado"):
        return ""  # "8 vagas", sem semestre
    if not sem or not sem[0].isdigit():
        return f": {sem or 'confira no edital'}"
    return (" do " if " ao " in sem else " no ") + sem


def vagas_texto(ed):
    vagas = ed.get("vagas") or []
    partes = []
    for v in vagas:
        if v.get("vagas"):
            partes.append(f"{v['vagas']} {'vaga' if v['vagas'] == 1 else 'vagas'}{no_semestre(v['semestre'])}")
        elif v.get("vagas") == 0:
            partes.append(f"cadastro reserva{no_semestre(v['semestre'])}")
        else:
            partes.append(f"vagas{no_semestre(v['semestre'])} (quantidade: confira no edital)")
    return " · ".join(partes) or "Confira no edital"


def total_vagas(ed):
    nums = [v["vagas"] for v in ed.get("vagas") or [] if v.get("vagas")]
    return sum(nums) if nums else None


# ---------------------------------------------------------------- layout

def json_ld(*objetos):
    """Dados estruturados (schema.org) para o Google entender a página."""
    return "".join('<script type="application/ld+json">' + json.dumps({"@context": "https://schema.org", **o}, ensure_ascii=False).replace("</", "<\\/")
                   + "</script>\n" for o in objetos if o)


def trilha_ld(*itens):
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i, "name": nome, "item": f"{SITE_URL}/{caminho}"} for i, (nome, caminho) in enumerate(itens, 1)]}


def layout(titulo, descricao, corpo, raiz, pagina, caminho, imagem="og/inicio.png", ativo=None, extra_body="", estruturados=()):
    # no celular o menu vira uma linha de ícones: o nome continua no link (só some da tela) para leitor de tela
    icones = {"diagnostico/": '<path d="M9 4h6v3H9z"/><path d="M8 5H6v16h12V5h-2"/><path d="M9 14l2 2 4-4"/>',
              "exterior/": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3.5 3 14.5 0 18M12 3c-3 3.5-3 14.5 0 18"/>'}
    nav = [("", "Início"), ("diagnostico/", "Diagnóstico"), ("exterior/", "Estudo no exterior")]
    links = "".join(f'<a href="{raiz}{href}" class="nav-{href.strip("/") or "inicio"}"{" aria-current=\"page\"" if ativo == href else ""}>'
                    + (f'<svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{icones[href]}</svg>' if href in icones else "")
                    + f'<span class="rotulo-nav">{nome}</span></a>' for href, nome in nav)
    url = f"{SITE_URL}/{caminho}"
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(titulo)}</title>
<meta name="description" content="{e(descricao)}">
<link rel="canonical" href="{e(url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Transfermed">
<meta property="og:locale" content="pt_BR">
<meta property="og:title" content="{e(titulo)}">
<meta property="og:description" content="{e(descricao)}">
<meta property="og:url" content="{e(url)}">
<meta property="og:image" content="{SITE_URL}/{imagem}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#0F5C4D">
<link rel="icon" href="{raiz}assets/logo.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="{raiz}assets/icone-192.png">
<link rel="manifest" href="{raiz}manifest.webmanifest">
<link rel="preload" href="{raiz}assets/inter.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{raiz}assets/estilo.css?v={versao_assets()}">
{json_ld(*estruturados)}</head>
<body data-pagina="{pagina}" data-raiz="{raiz}"{extra_body}>
<a class="pular" href="#conteudo">Pular para o conteúdo</a>
<header class="topo"><div class="wrap">
  <div class="topo-marca"><a class="marca" href="{raiz}"><img src="{raiz}assets/logo.svg" alt="" width="36" height="36"><span><b>Transfermed</b><small>Seu radar de transferência de Medicina</small></span></a>{quem_faz_botao()}</div>
  <nav class="nav" aria-label="Principal">{links}<button type="button" class="busca-botao" data-abrir-busca aria-expanded="false" aria-controls="busca"><svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg><span class="rotulo-nav">Buscar</span></button><a class="lista-icone" href="{raiz}minha-lista/" aria-label="Minha lista"><svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"><path d="M12 3l2.8 5.7 6.2.9-4.5 4.4 1 6.2L12 17.3 6.5 20.2l1-6.2L3 9.6l6.2-.9z"/></svg><span class="lista-n" hidden></span></a><button type="button" class="menu-botao" aria-expanded="false" aria-controls="menu-celular"><svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg><span class="oculto">Menu</span></button></nav>
</div>
{menu_celular(raiz, ativo)}
<div class="busca" id="busca" hidden role="search"><div class="wrap">
  <label class="oculto" for="busca-campo">Buscar faculdade pelo nome, sigla ou cidade</label>
  <input type="search" id="busca-campo" placeholder="Nome, sigla ou cidade da faculdade" autocomplete="off" enterkeyhint="go">
  <ul class="busca-lista" id="busca-lista" aria-live="polite"></ul>
</div></div></header>
{quem_faz_painel(raiz)}
<main id="conteudo">
{corpo}
</main>
<footer class="rodape"><div class="wrap">
  <div class="rodape-grid">
    <div><a class="marca" href="{raiz}"><img src="{raiz}assets/logo.svg" alt="" width="28" height="28"><b>Transfermed</b></a>
      <p>Cada informação vem do edital oficial, com link e data de conferência. Quem decide a vaga e o aproveitamento das matérias é sempre a faculdade.</p></div>
    {rodape_estados(raiz)}<div><p><strong>Sem cadastro.</strong> Seus dados ficam só no seu navegador.</p><p>Distâncias em linha reta, aproximadas.</p><p><a href="{raiz}sobre/">Quem faz</a> · <a href="{raiz}contato/">Contato</a> · <a href="{raiz}privacidade/">Privacidade</a></p></div>
  </div>
</div></footer>
<script src="{raiz}dados.js?v={versao_assets()}" defer></script><script src="{raiz}assets/app.js?v={versao_assets()}" defer></script>
</body>
</html>
"""


def versao_assets():
    """Impressão digital do estilo e do app: muda o endereço (?v=) quando eles mudam, e o navegador não mistura
    página nova com arquivo antigo guardado (o GitHub Pages deixa guardar por 10 min)."""
    h = hashlib.sha1()
    for nome in ("estilo.css", "app.js"):
        h.update((DOCS / "assets" / nome).read_bytes())
    return h.hexdigest()[:10]


# Conferência por campo: só o campo com problema fica "conferir" ({"campo": "aviso"} em conferir_campos); o resto do
# edital, verificado no PDF, segue normal no site e nos e-mails. Prazo final duvidoso (ou o edital inteiro) tira o
# edital dos e-mails até ser resolvido. "conferir" sem campos (marcação do robô) vale para o edital inteiro.
CAMPOS_PRAZO = {"inscricao_fim", "edital"}
CAMPOS_NA_FICHA = {"quem_pode", "vagas", "aceita_curso_exterior", "exclui_quem_ja_transferiu", "taxa_inscricao",
                   "data_prova", "criterio_selecao", "inscricao_fim", "resultado", "documentos"}


def campos_conferir(ed):
    if ed.get("status") != "conferir":
        return {}
    return ed.get("conferir_campos") or {"edital": ed.get("observacao") or "Este edital tem um ponto a conferir."}


def fora_dos_emails(ed):
    return bool(CAMPOS_PRAZO & set(campos_conferir(ed)))


# Prazo final diferente em duas fontes oficiais (edital x página da faculdade): o edital entra no site e nos e-mails
# com a data mais cedo como prazo seguro (inscricao_fim) e o aviso com as duas datas.
# prazo_divergente = {"edital": "AAAA-MM-DD", "edital_onde": "p. 1 e 3", "pagina": "AAAA-MM-DD", "url_pagina": "..."}
def prazo_seguro(ed):
    d = ed.get("prazo_divergente")
    return min(d["edital"], d["pagina"]) if d else ed.get("inscricao_fim")


def aviso_prazo_seguro(ed):
    d = ed.get("prazo_divergente")
    if not d:
        return ""
    onde = f" ({d['edital_onde']})" if d.get("edital_onde") else ""
    return (f"O edital diz {fmt(d['edital'])}{onde} e a página da faculdade diz {fmt(d['pagina'])}. "
            f"Para não correr risco, considere {fmt(prazo_seguro(ed))}.")


def avisos(ed):
    """Todos os avisos do edital, por campo: os de conferência e o do prazo seguro (no campo inscricao_fim)."""
    a = dict(campos_conferir(ed))
    if ed.get("prazo_divergente"):
        a["inscricao_fim"] = aviso_prazo_seguro(ed)
    return a


def aviso_campo(ed, campo):
    aviso = avisos(ed).get(campo)
    return f'<span class="aviso-campo"><strong>Atenção:</strong> {e(aviso)}</span>' if aviso else ""


def etiqueta_conferir(ed):
    return '<span class="et aviso">tem aviso: veja o resumo</span>' if avisos(ed) else ""


def atributos_prazo(ed):
    """Datas no HTML para o JavaScript recalcular a etiqueta de prazo no dia da visita."""
    return "".join(f' data-{k}="{ed[c]}"' for k, c in (("ini", "inscricao_inicio"), ("fim", "inscricao_fim")) if ed.get(c))


def cartao_simples(ed, fac, raiz, hoje):
    """Cartão estático (o JavaScript troca por um mais completo quando carrega)."""
    cls, txt = texto_situacao(ed, hoje)
    nome, quem = MODALIDADES.get(ed.get("modalidade"), MODALIDADES["externa"])
    return f"""<article class="cartao"><h3><a href="{raiz}edital/{slug_edital(ed)}/">{e(fac['nome'])}</a></h3>
<div class="local">{e(fac['cidade'])}/{e(fac['uf'])} · {e(fac['tipo'])}</div>
<p class="quem"><strong>{nome}:</strong> {e(ed.get('quem_pode') or quem)}</p>
<div class="etiquetas"><span class="et {cls}" data-prazo{atributos_prazo(ed)}>{e(txt)}</span>{f'<span class="et">ingresso {e(ed["semestre_ingresso"])}</span>' if ed.get('semestre_ingresso') else ''}{etiqueta_conferir(ed)}</div></article>"""


def cartao_novo(ed, fac, raiz):
    """Edital detectado pelo robô e ainda não revisado: só o essencial e o link oficial."""
    return f"""<article class="cartao cartao-novo"><h3><a href="{raiz}faculdade/{fac['id']}/">{e(fac['nome'])}</a></h3>
<div class="local">{e(fac['cidade'])}/{e(fac['uf'])} · {e(fac['tipo'])}</div>
<div class="etiquetas"><span class="et aviso">Novo edital detectado em {fmt(ed['detectado_em'])}</span><span class="et">dados ainda não conferidos</span></div>
<p class="dica">O radar encontrou este edital no site oficial, mas ainda não conferiu datas, vagas e regras. Abra o PDF para ver se ele serve para você.</p>
<div class="rodape-cartao"><a href="{e(ed['url_edital'])}" target="_blank" rel="noopener">Abrir edital oficial<span class="oculto"> (abre em nova aba)</span></a></div></article>"""


def botao_whatsapp(texto, url):
    """Envio direto no WhatsApp (link wa.me com o texto e o endereço da página): o jeito mais comum de passar adiante."""
    return (f'<a class="botao sec peq" href="https://wa.me/?text={quote(texto + " " + url, safe="")}" target="_blank" rel="noopener" '
            f'data-medir="compartilhar_whatsapp">Enviar no WhatsApp<span class="oculto"> (abre em nova aba)</span></a>')


def botoes_compartilhar(texto):
    return (f'<div class="compartilhar" data-texto="{e(texto)}"><button type="button" class="botao sec peq" data-compartilhar>'
            '<svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4"/></svg>'
            'Compartilhar</button></div>')


# ---------------------------------------------------------------- mapa-radar

def vistas_estados(F, minimo=5):
    """Enquadramento de cada estado coberto (com pelo menos `minimo` faculdades), na proporção do mapa."""
    por_uf = {}
    for f in F.values():
        por_uf.setdefault(f["uf"], []).append(proj(f["lat"], f["lon"]))
    vistas = []
    for uf, pts in sorted(por_uf.items(), key=lambda kv: NOMES_UF.get(kv[0], kv[0])):
        if len(pts) < minimo:
            continue
        xs, ys = [x for x, _ in pts], [y for _, y in pts]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        w = max(max(xs) - min(xs), (max(ys) - min(ys)) / 0.93, 60) + 24
        h = w * 0.93
        vistas.append((uf, f"{cx - w / 2:.1f} {cy - h / 2:.1f} {w:.1f} {h:.1f}"))
    return vistas


def mapa_svg(F, E, hoje, raiz, id_mapa="mapa"):
    """Mapa do Brasil com cada faculdade como um ponto, na cor da situação real."""
    estado = {}
    for x in E:
        s = situacao(x, hoje)
        atual = estado.get(x["faculdade_id"], "sem")
        ordem = {"aberto": 0, "contínuo": 1, "em breve": 2, "encerrado": 3, "desconhecida": 3, "sem": 4}
        if ordem[s] < ordem[atual]:
            estado[x["faculdade_id"]] = s
    rotulo = {"aberto": "inscrições abertas", "contínuo": "pedidos o ano todo", "em breve": "abre em breve",
              "encerrado": "sem edital aberto", "desconhecida": "sem edital aberto", "sem": "não publicou transferência recentemente"}
    classe = {"aberto": "aberto", "contínuo": "aberto", "em breve": "breve"}
    vistos = {}
    pontos = []
    for fid, f in sorted(F.items(), key=lambda kv: {"aberto": 2, "contínuo": 2, "em breve": 1}.get(estado.get(kv[0], "sem"), 0)):
        x, y = proj(f["lat"], f["lon"])
        chave = (round(x, 1), round(y, 1))
        n = vistos.get(chave, 0)
        vistos[chave] = n + 1
        if n:  # faculdades na mesma cidade: espalha um pouco em volta
            x += [1.6, -1.6, 0, 0, 1.2, -1.2][n % 6]
            y += [0, 0, 1.6, -1.6, 1.2, -1.2][n % 6]
        s = estado.get(fid, "sem")
        if s not in classe:  # o mapa mostra só quem está com inscrição aberta ou abrindo; as demais, pela busca
            continue
        pontos.append(f'<a href="{raiz}faculdade/{fid}/" class="ponto {classe.get(s, "neutro")}" data-fid="{fid}">'
                      f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2"/><title>{e(f["sigla"])} ({e(f["cidade"])}): {rotulo[s]}</title></a>')
    cx, cy = proj(*CENTRO_RADAR)
    abertos = sum(1 for s in estado.values() if s in ("aberto", "contínuo"))
    estados = "".join(f'<button type="button" data-vista="{v}" aria-pressed="false">{e(NOMES_UF.get(uf, uf))}</button>'
                      for uf, v in vistas_estados(F))
    return f"""<figure class="radar" id="{id_mapa}">
  <div class="radar-topo">
    <div class="vistas" role="group" aria-label="Área do mapa">
      <button type="button" data-vista="{VISTA_BRASIL}" aria-pressed="true">Brasil</button>
      <button type="button" data-vista="{VISTA_REGIAO}" data-perto aria-pressed="false" hidden>Perto de você</button>
    </div>
    <span class="radar-ao-vivo"><i></i>atualizado {fmt(hoje)}</span>
  </div>
  <svg viewBox="{VISTA_BRASIL}" role="group" aria-labelledby="{id_mapa}-t" class="radar-svg" preserveAspectRatio="xMidYMid meet">
    <title id="{id_mapa}-t">Mapa das faculdades com inscrições abertas ou abrindo: {abertos} abertas</title>
    <defs>
      <radialGradient id="{id_mapa}-g"><stop offset="0" stop-color="var(--verde)" stop-opacity=".35"/><stop offset="1" stop-color="var(--verde)" stop-opacity="0"/></radialGradient>
    </defs>
    <use href="{raiz}assets/brasil.svg#br" class="br" x="0" y="0" width="400" height="400" aria-hidden="true"/>
    <g class="aneis" aria-hidden="true" transform="translate({cx:.1f} {cy:.1f})">
      <circle r="25"/><circle r="50"/><circle r="75"/>
      <g class="varredura"><path d="M0 0 L0 -80 A80 80 0 0 1 56.6 -56.6 Z" fill="url(#{id_mapa}-g)"/></g>
    </g>
    <g class="pontos">{''.join(pontos)}</g>
    <g class="voce" hidden aria-hidden="true"><circle r="3.4"/><text dy="-6">você</text></g>
  </svg>
  <div class="vistas vistas-estados" role="group" aria-label="Ver um estado">{estados}</div>
  <figcaption class="legenda">
    <span><i class="l-aberto"></i>Aberto</span><span><i class="l-breve"></i>Abre em breve</span><span class="legenda-nota">Sem edital aberto: <button type="button" class="link-botao" data-abrir-busca aria-expanded="false" aria-controls="busca">busque pelo nome</button></span>
  </figcaption>
</figure>"""


# ---------------------------------------------------------------- páginas

ISCA = {"total": 0, "exterior": 0}  # editais usados no checklist em PDF (preenchido pelo main antes das páginas)


def bloco_alerta(raiz, titulo, sub, contexto, botao="Quero receber", seguir_fac=None, lembrete=None, perfil_base=None,
                 com_perfil=False, oculto=False, discreto=False, exterior=False):
    """Inscrição em duas etapas (o app.js cuida): 1) e-mail e consentimento; 2) o perfil, pré-preenchido pelo
    diagnóstico. Os data-* dizem o que a chamada pede: seguir uma faculdade, lembrar um prazo ou um perfil de base
    (ex.: "Estudo no exterior"). Um por página (os ids são fixos)."""
    dados = f' data-contexto="{e(contexto)}"'
    if seguir_fac:
        dados += f' data-seguir-faculdade="{e(seguir_fac)}"'
    if lembrete:
        dados += f' data-lembrete="{e(lembrete)}"'
    if perfil_base:
        dados += f' data-perfil-base="{e(json.dumps(perfil_base, ensure_ascii=False))}"'
    if com_perfil:
        dados += ' data-com-perfil="1"'
    arq, n = (isca_mod.ARQUIVO_EXTERIOR, ISCA["exterior"]) if exterior and ISCA["exterior"] else (isca_mod.ARQUIVO, ISCA["total"])
    isca = (f' Na hora, você recebe o <a href="{raiz}{arq}" data-medir="isca">checklist de documentos em PDF</a> '
            f'(baseado em {n} {"editais conferidos" + (" que aceitam quem vem do exterior" if arq == isca_mod.ARQUIVO_EXTERIOR else "")}).') if n else ""
    return f"""<section id="alerta" class="alerta-caixa{' discreto' if discreto else ''}"{' hidden' if oculto else ''} aria-labelledby="t-alerta">
    <h2 id="t-alerta">{e(titulo)}</h2>
    <p class="sub">{e(sub)}{isca}</p>
    <form id="form-alerta" class="form-alerta" novalidate{dados}>
      <label class="rotulo" for="email-alerta">Seu e-mail</label>
      <input type="email" id="email-alerta" class="campo-alerta" name="email" autocomplete="email" inputmode="email" required placeholder="voce@exemplo.com">
      <label class="consentimento"><input type="checkbox" id="consentimento" name="consentimento" required> <span>{e(CONSENTIMENTO)} <a href="{raiz}privacidade/">Como usamos seus dados</a>.</span></label>
      <button type="submit" class="botao{' sec' if discreto else ''}">{e(botao)}</button>
      <div class="pote" aria-hidden="true"><label>Não preencha <input type="text" name="campo_extra" tabindex="-1" autocomplete="off" data-1p-ignore data-lpignore="true"></label></div>
      <p class="dica" id="alerta-msg" role="status" aria-live="polite"></p>
    </form>
    <p class="garantia">Grátis. Sem spam. Cancele em um clique.</p>
    <div id="alerta-passo2" class="alerta-passo2" hidden></div>
  </section>"""


# Perguntas frequentes da página inicial (também vão como FAQPage para o Google). Só o que o site faz de verdade.
FAQ = [
    ("É grátis?", "Sim. O diagnóstico, as fichas dos editais, o checklist de documentos e os alertas por e-mail são gratuitos."),
    ("Vocês garantem a vaga?", "Não. Mostramos se você atende aos requisitos de cada edital. Quem decide a vaga e o aproveitamento "
     "das matérias é sempre a faculdade, seguindo o edital."),
    ("De onde vêm os dados?", "Do edital oficial de cada faculdade, lido no PDF. Cada dado mostra a página do edital de onde saiu e a "
     "data da conferência. Quando um edital muda ou se contradiz, a ficha mostra um aviso. Nenhuma faculdade paga para aparecer."),
    ("Vou receber spam?", "Não. Você recebe só o que pedir: alertas de editais compatíveis com o seu perfil, os lembretes de prazo "
     "que pedir, um resumo semanal quando houver novidade e, nas duas primeiras semanas, algumas dicas. Fora o e-mail de confirmação, "
     "no máximo um por dia, e todo e-mail tem o link para cancelar e apagar seus dados."),
    ("Preciso me cadastrar?", "Não para usar o site: o diagnóstico e a sua lista ficam só no seu navegador. O e-mail só é pedido "
     "se você quiser receber os alertas."),
]


def bloco_faq():
    itens = "".join(f"<details><summary>{e(q)}</summary><p>{e(r)}</p></details>" for q, r in FAQ)
    return f'<section class="faq" aria-labelledby="t-faq"><h2 id="t-faq">Perguntas frequentes</h2>{itens}</section>'


def faq_estruturado():
    return {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": r}}
                                                for q, r in FAQ]}


def depoimentos():
    """Depoimentos reais, com autorização (data/depoimentos.json: [{"texto", "nome", "contexto"}]). Sem nenhum, não há seção."""
    arq = PASTA / "data" / "depoimentos.json"
    lista = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else []
    if not lista:
        return ""
    itens = "".join(f'<figure class="depoimento"><blockquote>{e(d["texto"])}</blockquote>'
                    f'<figcaption>{e(d["nome"])}{", " + e(d["contexto"]) if d.get("contexto") else ""}</figcaption></figure>'
                    for d in lista)
    return f'<section class="depoimentos" aria-labelledby="t-depo"><h2 id="t-depo">Quem já usou</h2><div class="grade-3">{itens}</div></section>'


LIMITE_HOME = 5  # editais na página inicial; o resto fica em /editais/


def pagina_editais(F, E, gerado, hoje, novos=()):
    """Todos os editais abertos ou abrindo, o mapa, os números da base e os detectados pelo robô (saíram da home)."""
    raiz = "../"
    vivos = sorted([x for x in E if situacao(x, hoje) in ("aberto", "em breve")], key=lambda x: x.get("inscricao_fim") or "")
    abertos = sum(situacao(x, hoje) == "aberto" for x in E)
    conferidos = sum(1 for x in E if x.get("conferido_em"))
    ativos = sum(1 for f in F.values() if com_robo(f))
    estaticos = "".join(cartao_simples(x, F[x["faculdade_id"]], raiz, hoje) for x in vivos)
    bloco_novos = ""
    if novos:
        bloco_novos = (f'<h2>Detectados pelo robô, ainda sem conferência</h2><div class="grade-cartoes">'
                       + "".join(cartao_novo(x, F[x["faculdade_id"]], raiz) for x in novos) + "</div>")
    corpo = f"""
<div class="wrap">
  <nav class="trilha" aria-label="Você está em"><a href="{raiz}">Início</a> › Editais abertos</nav>
  <section class="heroi"><h1>Editais de transferência de Medicina abertos</h1>
    <p class="lead">Todos os editais conferidos com inscrições abertas ou abrindo, do prazo mais curto para o mais longo.</p>
    <div class="acoes"><a class="botao" href="{raiz}diagnostico/">Ver só os que servem para mim</a></div></section>
  <section id="jornada" class="jornada" hidden aria-labelledby="titulo-jornada"></section>
  <div id="abertos" class="grade-cartoes">{estaticos or '<div class="vazio">Nenhum edital aberto hoje.</div>'}</div>
  {bloco_novos}
  <h2>No mapa</h2>
  <div class="heroi-mapa">{mapa_svg(F, E, hoje, raiz)}</div>
  <div class="numeros faixa-numeros-in" role="group" aria-label="Números da base">
    <div class="numero"><b>{len(F)}</b><span>faculdades na base ({ativos} com o robô visitando todo dia)</span></div>
    <div class="numero"><b>{conferidos}</b><span>editais conferidos no PDF oficial, com a página de cada dado</span></div>
    <div class="numero"><b id="n-abertos">{abertos}</b><span>com inscrições abertas hoje</span></div>
    <div class="numero"><b class="data">{fmt(gerado)}</b><span>última atualização do radar</span></div>
  </div>
  {bloco_alerta(raiz, "Prefere receber por e-mail?", "Avisamos quando abrir edital de transferência de Medicina. Depois do e-mail, você pode ajustar o perfil (semestre, Brasil ou exterior).", "editais", botao="Receber os editais por e-mail", perfil_base={"curso": "medicina"}, discreto=True)}
</div>"""
    desc = "Todos os editais de transferência de Medicina com inscrições abertas ou abrindo, conferidos no PDF oficial, com prazo, vagas e mapa."
    return layout("Editais de transferência de Medicina abertos agora | Transfermed", desc, corpo, raiz, "editais", "editais/",
                  estruturados=(trilha_ld(("Início", ""), ("Editais abertos", "editais/")),))


def pagina_inicio(F, E, gerado, hoje, novos=()):
    vivos = sorted([x for x in E if situacao(x, hoje) in ("aberto", "em breve")], key=lambda x: x.get("inscricao_fim") or "")
    proximo = min((x for x in E if situacao(x, hoje) == "aberto"), key=lambda x: x["inscricao_fim"], default=None)
    estaticos = "".join(cartao_simples(x, F[x["faculdade_id"]], "./", hoje) for x in vivos[:LIMITE_HOME])
    destaque = ""
    if proximo:
        dias = (date.fromisoformat(proximo["inscricao_fim"]) - date.fromisoformat(hoje)).days
        quando = "hoje" if dias <= 0 else f"em {dias} {'dia' if dias == 1 else 'dias'}"
        destaque = (f'<p class="faixa-prazo" data-fim="{proximo["inscricao_fim"]}"><span class="pulso" aria-hidden="true"></span><strong>Prazo mais próximo:</strong> '
                    f'{e(F[proximo["faculdade_id"]]["sigla"])} encerra <span data-quando>{quando}</span> ({fmt(proximo["inscricao_fim"])}). '
                    f'<a href="edital/{slug_edital(proximo)}/">Ver edital</a></p>')
    corpo = f"""
<section class="heroi heroi-inicio"><div class="wrap heroi-grid heroi-home">
  <div class="heroi-texto">
    <span class="selo">Grátis · sem cadastro · dados do edital oficial</span>
    <h1>Descubra em 1 minuto onde você pode <span class="destaque">transferir Medicina</span>.</h1>
    <p class="lead">O radar confere os editais de transferência das faculdades, um por um, e mostra só onde você atende aos requisitos: do mais perto para o mais longe.</p>
    <div class="portas" role="group" aria-label="Por onde começar">
      <a class="porta" href="diagnostico/?origem=brasil"><b>Estudo Medicina no Brasil</b><span>Veja para onde dá para transferir</span></a>
      <a class="porta" href="diagnostico/?origem=exterior"><b>Estudo Medicina no exterior</b><span>Veja quem aceita quem vem de fora</span></a>
    </div>
  </div>
  <div class="heroi-mapa">{mapa_svg(F, E, hoje, "./")}</div>
  <div class="heroi-pos">
    <p class="ja-sabe">Já sabe para qual faculdade quer ir? <button type="button" class="link-botao" data-abrir-busca>Buscar pelo nome</button></p>
    {destaque}
  </div>
</div></section>
<div class="wrap">
  <section aria-labelledby="t-abertos">
    <div class="secao-topo"><h2 id="t-abertos">Encerram primeiro</h2><a href="diagnostico/">Ver só os que servem para mim →</a></div>
    <div id="abertos" class="grade-cartoes" data-limite="{LIMITE_HOME}">{estaticos or '<div class="vazio">Nenhum edital aberto hoje.</div>'}</div>
    {f'<p class="acoes"><a class="botao sec" href="editais/">Ver todos os {len(vivos)} editais abertos ou abrindo</a></p>' if len(vivos) > LIMITE_HOME else ''}
  </section>
  <section aria-labelledby="t-como" class="como">
    <h2 id="t-como">Como funciona</h2>
    <ol class="passos passos-grade">
      <li><strong>Responda 4 etapas</strong><span>Onde estuda, semestre e até onde aceita ir.</span></li>
      <li><strong>O radar confere as regras</strong><span>De cada edital aberto, no PDF oficial.</span></li>
      <li><strong>Veja onde se encaixa</strong><span>E receba aviso quando abrir um novo.</span></li>
    </ol>
  </section>
  <section class="confianca" aria-labelledby="t-confianca">
    <h2 id="t-confianca">Por que dá para confiar</h2>
    <div class="grade-3">
      <div><strong>Lido no PDF oficial</strong><p>Cada informação mostra a página do edital de onde saiu.</p></div>
      <div><strong>Conferido de novo</strong><p>Quando um edital muda ou se contradiz, ele aparece com aviso até ser revisado.</p></div>
      <div><strong>Sem promessa</strong><p>Mostramos se você atende aos requisitos. Quem decide a vaga é a faculdade.</p></div>
    </div>
  </section>
  {bloco_faq()}
</div>"""
    desc = "Descubra em 1 minuto em quais editais de transferência de Medicina você pode se inscrever. Grátis, sem cadastro, com dados do edital oficial."
    estruturados = ({"@type": "WebSite", "name": "Transfermed", "url": f"{SITE_URL}/", "description": desc, "inLanguage": "pt-BR",
                     "potentialAction": {"@type": "SearchAction", "target": {"@type": "EntryPoint", "urlTemplate": f"{SITE_URL}/?busca={{search_term_string}}"},
                                         "query-input": "required name=search_term_string"}},
                    {"@type": "Organization", "name": "Transfermed", "url": f"{SITE_URL}/", "logo": f"{SITE_URL}/assets/icone-512.png"},
                    faq_estruturado())
    return layout("Transfermed: descubra onde transferir Medicina", desc, corpo, "./", "inicio", "", ativo="", estruturados=estruturados)


def pagina_diagnostico():
    corpo = """
<div class="wrap estreito">
  <section class="heroi">
    <h1>Onde você pode transferir?</h1>
    <p class="lead">Responda 4 etapas curtas e veja na hora os editais em que você pode se inscrever. Sem cadastro.</p>
  </section>
  <noscript><div class="aviso-caixa">O diagnóstico precisa de JavaScript ligado no navegador.</div></noscript>
  <form id="diag" class="cartao formulario" novalidate>
    <div class="form-topo"><p class="etapa-titulo" id="passo-txt" aria-live="polite">Etapa 1 de 4</p><p class="etapa-nome" id="passo-nome">Onde você estuda</p></div>
    <div class="progresso" role="progressbar" aria-label="Progresso do diagnóstico" aria-valuemin="1" aria-valuemax="4" aria-valuenow="1"><i id="barra"></i></div>

    <div class="etapa ativa" data-etapa="curso" data-nome="Onde você estuda">
      <fieldset><legend>Onde você estuda hoje?</legend>
        <div class="opcoes">
          <label><input type="radio" name="origem" value="brasil" checked>No Brasil</label>
          <label><input type="radio" name="origem" value="exterior">No exterior (Paraguai, Bolívia, Argentina...)</label>
        </div></fieldset>
      <input type="hidden" name="curso" value="medicina">
    </div>

    <div class="etapa" data-etapa="faculdade" data-nome="Sua faculdade">
      <div class="campo"><label class="rotulo" for="faculdade">Em qual faculdade você estuda?</label>
        <input type="text" id="faculdade" name="faculdade" list="lista-facul" autocomplete="off" placeholder="Ex.: Universidade Brasil">
        <datalist id="lista-facul"></datalist>
        <p class="dica" id="dica-faculdade">Assim não sugerimos a sua própria faculdade e achamos a transferência interna dela, se houver.</p></div>
      <div class="campo"><label class="rotulo" for="semestre">Em que semestre você está agora?</label>
        <select id="semestre" name="semestre"></select></div>
      <fieldset><legend>Você já fez transferência de Medicina alguma vez?</legend>
        <div class="opcoes">
          <label><input type="radio" name="transferiu" value="nao" checked>Não</label>
          <label><input type="radio" name="transferiu" value="sim">Sim</label>
        </div>
        <p class="dica">Alguns editais não aceitam quem já se transferiu uma vez.</p></fieldset>
    </div>

    <div class="etapa" data-etapa="onde" data-nome="Distância">
      <div class="campo"><label class="rotulo" for="cidade">De qual cidade medimos a distância até as faculdades?</label>
        <input type="text" id="cidade" name="cidade" list="lista-cidades" autocomplete="off" placeholder="Ex.: Fernandópolis - SP" aria-describedby="dica-cidade">
        <datalist id="lista-cidades"></datalist>
        <p class="dica" id="dica-cidade">Pode ser onde você mora ou onde está a sua família. Opcional: sem cidade, mostramos todas as faculdades, sem a distância.</p>
        <p class="erro" id="erro-cidade" hidden>Escolha uma cidade da lista (ex.: Fernandópolis - SP).</p></div>
      <div class="campo"><label class="rotulo" for="raio">Até que distância dessa cidade você aceita estudar?</label>
        <select id="raio" name="raio">
          <option value="150">Até 150 km</option><option value="300">Até 300 km</option><option value="600">Até 600 km</option>
          <option value="1200">Até 1.200 km</option><option value="0" selected>Qualquer distância</option>
        </select>
        <p class="dica" id="dica-raio">Escolha uma cidade acima para limitar a distância.</p></div>
    </div>

    <div class="etapa" data-etapa="preferencias" data-nome="Tipo e taxa">
      <fieldset><legend>Que tipo de faculdade serve para você?</legend>
        <div class="opcoes">
          <label><input type="radio" name="tipo" value="todas" checked>Pública ou particular</label>
          <label><input type="radio" name="tipo" value="publica">Só pública</label>
          <label><input type="radio" name="tipo" value="particular">Só particular</label>
        </div></fieldset>
      <div class="campo"><label class="rotulo" for="taxaMax">Quanto você pode pagar, no máximo, de taxa de inscrição (R$)?</label>
        <input type="number" id="taxaMax" name="taxaMax" min="0" step="10" inputmode="numeric" placeholder="Ex.: 400">
        <p class="dica">Opcional: em branco, mostramos editais com qualquer taxa.</p></div>
    </div>

    <div class="acoes"><button type="button" class="botao sec" id="voltar" hidden>Voltar</button><button type="submit" class="botao" id="seguir">Continuar</button></div>
  </form>
  <section id="resultado" hidden aria-live="polite"></section>
  {{ALERTA}}
</div>"""
    corpo = corpo.replace("{{ALERTA}}", bloco_alerta("../", "Receba um aviso quando abrir edital para você",
                                                     "Só o e-mail. Usamos o perfil acima para escolher os editais. Sem senha, sem cadastro longo.",
                                                     "diagnostico", com_perfil=True, oculto=True))
    return layout("Diagnóstico: onde posso transferir Medicina | Transfermed", "Responda 4 etapas curtas e veja os editais de transferência de Medicina abertos para o seu perfil, os que abrem em breve e onde você não se encaixa.", corpo, "../", "diagnostico", "diagnostico/", ativo="diagnostico/")


def evid(ed, campo):
    p = (ed.get("evidencias") or {}).get(campo)
    if p in (None, ""):
        return ""
    return f' <span class="pag">p. {e(p)}</span>' if isinstance(p, int) else f' <span class="pag">{e(p)}</span>'


def contador_prazo(inicio, fim, hoje):
    """Número grande da linha do tempo; o app.js refaz a mesma conta no dia da visita."""
    if inicio and hoje < inicio:
        d = (date.fromisoformat(inicio) - date.fromisoformat(hoje)).days
        return str(d), f"{'dia' if d == 1 else 'dias'} para abrirem as inscrições", ""
    if fim and hoje <= fim:
        d = (date.fromisoformat(fim) - date.fromisoformat(hoje)).days
        if d == 0:
            return "Hoje", "é o último dia de inscrição", "c-alerta"
        return str(d), f"{'dia' if d == 1 else 'dias'} para o fim das inscrições", "c-alerta" if d <= 2 else "c-aviso" if d <= 10 else ""
    return None


def linha_do_tempo(ed, hoje):
    marcos = []
    if ed.get("inscricao_inicio"):
        marcos.append((ed["inscricao_inicio"], "Inscrições abrem"))
    if ed.get("inscricao_fim"):
        marcos.append((ed["inscricao_fim"], "Último dia de inscrição"))
    if ed.get("data_prova"):
        marcos.append((ed["data_prova"], "Prova"))
    if not marcos:
        return ""
    marcos.sort()
    # "Hoje" fica entre os marcos; quando um marco é hoje, ele mesmo vira "Hoje · ..." (o app.js reposiciona na visita)
    marco_hoje = any(d == hoje for d, _ in marcos)
    li_hoje = f'<li class="marco hoje"{" hidden" if marco_hoje else ""}><span class="data">{fmt(hoje)}</span><span class="nome">Hoje</span></li>'
    itens = []
    for d, nome in marcos:
        if li_hoje and hoje < d:
            itens.append(li_hoje)
            li_hoje = ""
        estado = "feito" if d < hoje else ("agora" if d == hoje else "futuro")
        rotulo = f"Hoje · {nome}" if d == hoje else nome
        itens.append(f'<li class="marco {estado}" data-d="{d}" data-nome="{e(nome)}"><span class="data">{fmt(d)}</span><span class="nome">{e(rotulo)}</span></li>')
    itens.append(li_hoje)
    contador = ""
    c = contador_prazo(ed.get("inscricao_inicio"), ed.get("inscricao_fim"), hoje) if situacao(ed, hoje) in ("aberto", "em breve") else None
    if c:
        contador = (f'<div class="contador {c[2]}" data-inicio="{ed.get("inscricao_inicio") or ""}" data-fim="{ed.get("inscricao_fim") or ""}">'
                    f'<b>{c[0]}</b><span>{c[1]}</span></div>')
    return f'<div class="tempo">{contador}<ol class="linha" aria-label="Linha do tempo">{"".join(itens)}</ol></div>'


def distintivos_edital(E, F):
    """O que separa editais da mesma faculdade, modalidade e semestre no título (UB: 4 externas em 2026.1):
    o número curto do edital ("034/2026") e, se ainda empatar, a data de encerramento."""
    grupos = {}
    for x in E:
        f = F[x["faculdade_id"]]
        grupos.setdefault((f["sigla"], f["cidade"], x.get("modalidade"), x.get("semestre_ingresso")), []).append(x)
    dist = {}
    for eds in grupos.values():
        if len(eds) < 2:
            continue
        nums = {x["id"]: (re.search(r"\d+/\d{4}", x.get("numero_edital") or "") or [""])[0] for x in eds}
        for x in eds:
            partes = [nums[x["id"]]] if nums[x["id"]] and list(nums.values()).count(nums[x["id"]]) == 1 else []
            if not partes and x.get("inscricao_fim"):
                partes = [f"até {fmt(x['inscricao_fim'])}"]
            dist[x["id"]] = " ".join(partes) or slug_edital(x)[-6:]
    return dist


def etapas_depois(ed, ni):
    """Resultado e matrícula na ficha: a data (ou o texto, quando a etapa não tem data fixa) com a página do edital.
    Antes de transcritos, uma linha só manda para o edital; transcrito um, o outro que faltar é "não informado"."""
    def periodo(ini, fim):
        return f"{fmt(ini)} a {fmt(fim)}" if fim and fim != ini else fmt(ini)

    res = e(ed["resultado_texto"]) if ed.get("resultado_texto") else (fmt(ed["data_resultado"]) if ed.get("data_resultado") else "")
    mat = (e(ed["matricula_texto"]) if ed.get("matricula_texto")
           else (periodo(ed["data_matricula"], ed.get("data_matricula_fim")) if ed.get("data_matricula") else ""))
    if not res and not mat:
        return (f'<div><dt>Resultado e matrícula</dt><dd>ainda não transcritos aqui: veja no edital'
                f'{evid(ed, "resultado")}{aviso_campo(ed, "resultado")}</dd></div>')
    return (f'<div><dt>Resultado</dt><dd>{res or ni}{evid(ed, "data_resultado") if res else ""}{aviso_campo(ed, "resultado")}</dd></div>'
            f'<div><dt>Matrícula</dt><dd>{mat or ni}{evid(ed, "data_matricula") if mat else ""}</dd></div>')


def pagina_edital(ed, fac, hoje, imagem, distintivo=""):
    """Ficha do edital em 3 blocos: Posso? · Quando · O que preciso. Só dado conferido; o que o edital não traz
    aparece como "não informado", e o que ainda não foi transcrito manda para o PDF (nunca deduzido)."""
    raiz = "../../"
    nome_mod, quem_mod = MODALIDADES.get(ed.get("modalidade"), MODALIDADES["externa"])
    cls, txt = texto_situacao(ed, hoje)
    # fluxo contínuo não tem edital: os textos falam da página oficial e da faculdade
    fluxo = bool(ed.get("fluxo_continuo"))
    confira = "confirme com a faculdade" if fluxo else "confira no edital"
    ni = "não informado pela faculdade" if fluxo else "não informado no edital"
    inscr = (f"{fmt(ed.get('inscricao_inicio'))} a {fmt(ed.get('inscricao_fim'))}" if ed.get("inscricao_inicio")
             else (f"até {fmt(ed['inscricao_fim'])}" if ed.get("inscricao_fim") else ("o ano todo" if fluxo else ni)))
    taxa = ("gratuita" if ed.get("taxa_inscricao") == 0 else dinheiro(ed["taxa_inscricao"])) if ed.get("taxa_inscricao") is not None else ni
    sim_nao = {True: "Sim", False: "Não", None: ni}

    def lista_dl(itens):
        # campo duvidoso: o aviso fica ao lado dele; sem valor publicado, aparece "a conferir" em vez de "não informado"
        return "".join(f'<div{" class=\"largo\"" if largo else ""}><dt>{t}</dt><dd>'
                       f'{"a conferir" if aviso_campo(ed, c) and v == ni else v}{evid(ed, c)}{aviso_campo(ed, c)}</dd></div>'
                       for t, v, c, largo in itens)

    posso = lista_dl([("Quem pode se inscrever", e(ed.get("quem_pode") or quem_mod), "quem_pode", True),
                      ("Vagas", e(vagas_texto(ed) if ed.get("vagas") else ni), "vagas", True),
                      ("Aceita quem estuda no exterior", sim_nao.get(ed.get("aceita_curso_exterior"), ni), "aceita_curso_exterior", False),
                      ("Exclui quem já transferiu", sim_nao.get(ed.get("exclui_quem_ja_transferiu"), ni), "exclui_quem_ja_transferiu", False)])
    restr = "".join(f"<li>{e(r)}</li>" for r in ed.get("outras_restricoes") or [])
    preciso = lista_dl([("Taxa de inscrição", taxa, "taxa_inscricao", False),
                        ("Prova", fmt(ed["data_prova"]) if ed.get("data_prova") else ni, "data_prova", False),
                        ("Como é a seleção", e(ed.get("criterio_selecao") or ni), "criterio_selecao", True)])
    docs = ed.get("documentos") or []
    pag_docs = evid(ed, "documentos")
    if docs:
        check = ("<p class=\"sub\">" + ("Lista tirada da página oficial" if fluxo else "Lista tirada do edital") + f"{pag_docs}. "
                 "Marque o que já separou: fica salvo só neste navegador.</p>"
                 '<div class="check-topo"><div class="progresso fino" aria-hidden="true"><i id="check-barra"></i></div><p class="dica" id="check-prog" aria-live="polite"></p></div>'
                 '<ul class="check" id="checklist">' + "".join(f'<li><label><input type="checkbox"><span>{e(d)}</span></label></li>' for d in docs) + "</ul>")
    else:
        check = (f'<div class="aviso-caixa">A lista de documentos deste edital ainda não foi transcrita aqui. Veja a lista exata no '
                 f'<a href="{e(ed["url_edital"])}" target="_blank" rel="noopener">{"página oficial" if fluxo else "edital oficial"}<span class="oculto"> (abre em nova aba)</span></a>.</div>')
    if fluxo:
        autoridade = f"Dados tirados da página oficial da faculdade, conferida em {fmt(ed.get('conferido_em') or ed.get('atualizado_em'))}."
    elif ed.get("conferido_em"):
        autoridade = f"Conferido no edital oficial em {fmt(ed['conferido_em'])}. \"p.\" é a página do PDF de onde saiu cada dado."
    else:
        autoridade = f"Lido no edital oficial em {fmt(ed.get('atualizado_em'))}, ainda não reconferido. \"p.\" é a página do PDF de onde saiu cada dado."
    retif = "".join(f'<li><a href="{e(r)}" target="_blank" rel="noopener">Retificação {i}</a></li>' for i, r in enumerate(dict.fromkeys(ed.get("retificacoes") or []), 1))
    total = total_vagas(ed)
    compart = f"{nome_mod} para Medicina na {fac['sigla']} ({fac['cidade']}/{fac['uf']}): {txt.lower()}."
    tempo = linha_do_tempo(ed, hoje) or f'<p class="sub">Datas: {ni}.</p>'
    agenda = bloco_agenda(ed, fac) if ed.get("inscricao_fim") or ed.get("data_prova") else ""
    # lembrete só com prazo real e conferido; sem isso (encerrado, fluxo contínuo, data a conferir), seguir a faculdade
    if (not fluxo and not fora_dos_emails(ed) and ed.get("inscricao_fim")
            and situacao(ed, hoje) in ("aberto", "em breve")
            and (date.fromisoformat(ed["inscricao_fim"]) - date.fromisoformat(hoje)).days > 2):
        chamada = bloco_alerta(raiz, "Me lembre 7 e 2 dias antes do prazo",
                               f"Um e-mail 7 dias e outro 2 dias antes de {fmt(ed['inscricao_fim'])}, com a lista de documentos "
                               f"deste edital. Você também passa a receber os próximos editais da {fac['sigla']}.",
                               "edital_lembrete", botao="Me lembre do prazo", seguir_fac=fac["id"], lembrete=ed["id"])
    else:
        chamada = bloco_alerta(raiz, f"Avise-me quando a {fac['sigla']} abrir o próximo edital",
                               "Um e-mail quando sair edital conferido desta faculdade, com o resumo e os documentos.",
                               "edital_seguir", botao="Avise-me", seguir_fac=fac["id"])
    # avisos de campos que a ficha não mostra numa linha própria (semestre, calendário, edital inteiro) vão no topo
    fora_da_ficha = [a for c, a in avisos(ed).items() if c not in CAMPOS_NA_FICHA]
    caixa_conferir = "".join(f'<div class="aviso-caixa"><strong>Atenção:</strong> {e(a)}</div>' for a in fora_da_ficha)
    corpo = f"""
<div class="wrap estreito">
  <nav class="trilha" aria-label="Você está em"><a href="{raiz}">Início</a>{trilha_estado(raiz, fac['uf'])} › <a href="{raiz}faculdade/{fac['id']}/">{e(fac['sigla'])}</a> › Edital</nav>
  <section class="heroi heroi-edital">
    <p class="sobre"><a href="{raiz}faculdade/{fac['id']}/">{e(fac['nome'])}</a> · {e(fac['cidade'])}/{e(fac['uf'])} · {e(fac['tipo'])}</p>
    <h1>{e(nome_mod)}{' · ingresso ' + e(ed['semestre_ingresso']) if ed.get('semestre_ingresso') else ''}</h1>
    <div class="etiquetas"><span class="et {cls}" id="urgencia">{e(txt)}</span>{f'<span class="et">{e(ed["numero_edital"])}</span>' if ed.get('numero_edital') else ''}{f'<span class="et">{total} vagas</span>' if total else ''}{etiqueta_conferir(ed)}</div>
    <div class="acoes">
      <a class="botao" href="{e(ed['url_edital'])}" target="_blank" rel="noopener" data-medir="abrir_pdf">{'Abrir página oficial' if fluxo else 'Abrir edital oficial'}<span class="oculto"> (abre em nova aba)</span></a>
      <button type="button" class="botao sec" data-marcar="{ed["id"]}" aria-pressed="false">☆ Salvar na minha lista</button>
      {botao_whatsapp(compart, f"{SITE_URL}/edital/{slug_edital(ed)}/")}
      {botoes_compartilhar(compart)}
    </div>
  </section>
  <p class="autoridade"><svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l8 4v6c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/></svg>{autoridade}</p>
  {caixa_conferir}
  <section class="bloco-ficha" aria-labelledby="t-posso">
    <h2 id="t-posso"><span class="n-bloco">1</span>Posso me inscrever?</h2>
    <div id="voce-atende" class="voce-atende" hidden></div>
    <dl class="resumo">{posso}</dl>
    {f'<h3>Regras que pesam</h3><ul class="lista-regras">{restr}</ul>' if restr else ''}
  </section>
  <section class="bloco-ficha" aria-labelledby="t-quando">
    <h2 id="t-quando"><span class="n-bloco">2</span>Quando</h2>
    <dl class="resumo"><div><dt>Inscrições</dt><dd>{inscr}{evid(ed, "inscricao_fim")}{aviso_campo(ed, "inscricao_fim")}</dd></div>{etapas_depois(ed, ni)}</dl>
    {tempo}
    {agenda}
  </section>
  <section class="bloco-ficha" aria-labelledby="t-preciso">
    <h2 id="t-preciso"><span class="n-bloco">3</span>O que preciso</h2>
    <dl class="resumo">{preciso}</dl>
    <h3>Documentos</h3>
    {aviso_campo(ed, "documentos")}{check}
  </section>
  {f'<h2>Retificações</h2><ul>{retif}</ul>' if retif else ''}
  {chamada}
  <p class="dica espaco-32">"Você atende aos requisitos" não garante vaga nem aproveitamento de matérias: quem decide é a faculdade, seguindo {'as regras dela' if fluxo else 'o edital'}.</p>
</div>"""
    titulo = f"{nome_mod} em Medicina: {fac['nome']}"
    # semestre e número do edital no título e na descrição: a mesma faculdade tem vários editais (UB: 4 em 2026.1)
    sem = f" {ed['semestre_ingresso']}" if ed.get("semestre_ingresso") else ""
    num = f", {ed['numero_edital']}" if ed.get("numero_edital") else ""
    # um PDF pode abrir transferência e portador de diploma: a modalidade entra para a descrição não repetir
    mod = f", {nome_mod.lower()}" if ed.get("modalidade") not in (None, "externa") else ""
    onde = f"{fac['sigla']} ({fac['cidade']}/{fac['uf']}){mod}{', ingresso ' + ed['semestre_ingresso'] if sem else ''}{num}"
    desc = (f"{onde}. {txt}. Vagas e taxa: {confira}. Resumo, documentos e link da página oficial." if fluxo
            else f"{onde}. {txt}. {vagas_texto(ed)}. Taxa: {taxa}. Resumo, documentos e link do edital oficial.")
    url = f"{SITE_URL}/edital/{slug_edital(ed)}/"
    programa = {"@type": "EducationalOccupationalProgram", "name": f"Medicina: {nome_mod.lower()}{sem}", "url": url,
                "provider": {"@type": "CollegeOrUniversity", "name": fac["nome"], "url": fac["site"]}}
    if ed.get("inscricao_inicio"):
        programa["applicationStartDate"] = ed["inscricao_inicio"]
    if ed.get("inscricao_fim") and not fluxo:
        programa["applicationDeadline"] = ed["inscricao_fim"]
    estruturados = (trilha_ld(("Início", ""), *([(NOMES_UF[fac["uf"]], f"estado/{fac['uf'].lower()}/")] if fac["uf"] in ESTADOS else []),
                              (fac["sigla"], f"faculdade/{fac['id']}/"), ("Edital", f"edital/{slug_edital(ed)}/")),
                    {"@type": "WebPage", "name": titulo, "description": desc, "inLanguage": "pt-BR",
                     "dateModified": ed.get("conferido_em") or ed.get("atualizado_em"),
                     "about": {"@type": "CollegeOrUniversity", "name": fac["nome"], "url": fac["site"]},
                     "citation": ed["url_edital"]},
                    programa)
    dist = f", {distintivo}" if distintivo else ""
    return layout(titulo_curto(f"{nome_mod}{sem}: {fac['sigla']} ({fac['cidade']}){dist} | Transfermed",
                               f"{nome_mod}{sem}: {fac['sigla']} ({fac['cidade']}){dist}",
                               f"{nome_mod}{sem}: {fac['sigla']}{dist}"),
                  desc, corpo, raiz, "edital", f"edital/{slug_edital(ed)}/", imagem,
                  extra_body=f' data-edital="{ed["id"]}"', estruturados=estruturados)


def titulo_curto(*opcoes, limite=70):
    """Título da aba e do Google: a primeira opção que cabe em `limite` caracteres (o Google corta os mais longos)."""
    for t in opcoes:
        if len(t) <= limite:
            return t
    return opcoes[-1]


def aviso_pendente(fac):
    """Aviso da ficha: o texto público de como a faculdade faz a transferência, ou o motivo da ficha incompleta
    (a nota "pendente" é interna, não vai para o site)."""
    if fac.get("aviso_publico"):
        return f'<div class="aviso-caixa">{e(fac["aviso_publico"])}</div>'
    if not fac.get("pendente"):
        return ""
    p = fac["pendente"].lower()
    if "nenhum edital" in p:
        txt = "Não encontramos edital de transferência de Medicina desta faculdade nos últimos 2 anos. Confira no site oficial."
    elif "não ficam listados" in p or "sem uma lista" in p:
        txt = "Esta faculdade não deixa os editais de transferência listados no site. Confira no site oficial a cada semestre."
    elif "por script" in p:
        txt = ("Esta faculdade mostra os editais numa página que o nosso robô não consegue ler sozinho, "
               "então um edital novo pode demorar a aparecer aqui. Confira no site oficial.")
    elif "bloqueia" in p or "recusa" in p or "não respondeu" in p:
        txt = ("O site desta faculdade não permite a leitura automática, então o robô não acompanha os editais "
               "todo dia. Confira no site oficial.")
    elif "página nova" in p:
        txt = ("Os editais desta faculdade saem numa página nova a cada semestre, então o próximo pode demorar "
               "a aparecer aqui. Confira no site oficial.")
    elif "pedido direto" in p or "sem edital" in p:
        txt = ("Esta faculdade faz a transferência por pedido direto, sem edital publicado. "
               "Confira as condições no site oficial.")
    else:
        txt = "Ainda falta descobrir onde esta faculdade publica os editais de transferência. Enquanto isso, confira no site oficial."
    return f'<div class="aviso-caixa">{txt}</div>'


def ordem_historico(ed):
    """Mais novo primeiro: semestre de ingresso, depois fim das inscrições. Antes comparava "2026.1" com
    "2026-06-22" como texto quando faltava a data, e o 2026.1 ficava acima do 2026.2."""
    m = re.match(r"(20\d\d)(?:\.([12]))?", str(ed.get("semestre_ingresso") or ""))
    sem = (int(m.group(1)), int(m.group(2) or 0)) if m else (0, 0)
    return (sem, ed.get("inscricao_fim") or "")


def pagina_faculdade(fac, eds, hoje, imagem):
    raiz = "../../"
    eds = sorted(eds, key=ordem_historico, reverse=True)
    vivos = [x for x in eds if publicavel(x) and situacao(x, hoje) in ("aberto", "em breve", "contínuo")]
    novos = [x for x in eds if novo_detectado(x, hoje)]
    meses = fac.get("meses", [])

    def linha(x):
        nome = e(MODALIDADES.get(x.get("modalidade"), MODALIDADES["externa"])[0])
        datas = (f"{fmt(x['inscricao_inicio'])} a {fmt(x.get('inscricao_fim'))}" if x.get("inscricao_inicio")
                 else f"até {fmt(x['inscricao_fim'])}" if x.get("inscricao_fim") else "—")
        if publicavel(x):
            ingresso = f"<a href=\"{raiz}edital/{slug_edital(x)}/\">{e(x.get('semestre_ingresso') or '?')}</a>"
            sit = e(texto_situacao(x, hoje)[1]) + (" · tem aviso" if x.get("status") == "conferir" else "")
        else:
            ingresso = f"<a href=\"{e(x['url_edital'])}\" target=\"_blank\" rel=\"noopener\">{e(x.get('semestre_ingresso') or 'PDF')}</a>"
            sit = '<span class="nao-revisado">não revisado: confira no PDF</span>'
        return f"<tr><td>{ingresso}</td><td>{nome}</td><td>{datas}</td><td>{sit}</td></tr>"

    linhas = "".join(linha(x) for x in eds)
    ext = {"sim": "Aceita quem estuda no exterior", "não": "Não aceita quem estuda no exterior"}.get(fac.get("aceita_exterior"), "Quem estuda no exterior: depende do edital")
    lat, lon = fac["lat"], fac["lon"]
    mapa = (f'<iframe class="mapa" loading="lazy" title="Mapa: {e(fac["cidade"])}" '
            f'src="https://www.openstreetmap.org/export/embed.html?bbox={lon - .08:.4f}%2C{lat - .05:.4f}%2C{lon + .08:.4f}%2C{lat + .05:.4f}&amp;layer=mapnik&amp;marker={lat:.4f}%2C{lon:.4f}"></iframe>'
            '<p class="dica">Posição aproximada (centro da cidade).</p>')
    abre = ", ".join(MESES[m - 1] for m in meses)
    corpo = f"""
<div class="wrap estreito">
  <nav class="trilha" aria-label="Você está em"><a href="{raiz}">Início</a>{trilha_estado(raiz, fac['uf'])} › {e(fac['sigla'])}</nav>
  <section class="heroi heroi-edital">
    <p class="sobre">{e(fac['cidade'])}/{e(fac['uf'])} · {e(fac['tipo'])}</p>
    <h1>{e(fac['nome'])}</h1>
    <div class="etiquetas">
      {''.join(f'<span class="et">{e(MODALIDADES.get(m, (m,))[0])}</span>' for m in fac.get('modalidades_costuma_abrir') or [])}
      {f'<span class="et aviso">Costuma abrir em {e(abre)}</span>' if meses else ''}
      <span class="et">{e(ext)}</span>
    </div>
    <div class="acoes">{botoes_compartilhar(f"Transferência de Medicina na {fac['sigla']} ({fac['cidade']}/{fac['uf']}): editais e prazos")}</div>
  </section>
  {aviso_pendente(fac)}
  <h2>Próximos prazos</h2>
  {''.join(cartao_simples(x, fac, raiz, hoje) for x in vivos) + ''.join(cartao_novo(x, fac, raiz) for x in novos) or '<div class="vazio">Nenhum edital aberto agora.' + (f' Pelo histórico, costuma abrir em {e(abre)}.' if meses else '') + '</div>'}
  {bloco_alerta(raiz, f"Avise-me quando a {fac['sigla']} abrir" if not vivos else f"Receber os próximos editais da {fac['sigla']}",
                "Um e-mail quando sair edital conferido desta faculdade, com o resumo e os documentos.",
                "faculdade_seguir", botao="Avise-me", seguir_fac=fac["id"])}
  <h2>Histórico de editais</h2>
  {f'<div class="tabela"><table><thead><tr><th scope="col">Ingresso</th><th scope="col">Modalidade</th><th scope="col">Inscrições</th><th scope="col">Situação</th></tr></thead><tbody>{linhas}</tbody></table></div>' if linhas else '<div class="vazio">Não publicou transferência recentemente (nenhum edital nos últimos 2 anos).</div>'}
  <h2>Ficha</h2>
  <ul>
    <li>Site oficial: <a href="{e(fac['site'])}" target="_blank" rel="noopener">{e(dominio(fac['site']))}</a></li>
    {''.join(f'<li>Onde publica os editais: <a href="{e(p)}" target="_blank" rel="noopener">página de editais{f" {i}" if len(fac["paginas_editais"]) > 1 else ""} ({e(dominio(p))})</a></li>' for i, p in enumerate(fac.get('paginas_editais', []), 1))}
    <li>Última conferência: {fmt(fac.get('ultima_conferencia'))}</li>
  </ul>
  {f'<p class="sub">{e(fac["observacoes"])}</p>' if fac.get('observacoes') else ''}
  <h2>Onde fica</h2>
  {mapa}
</div>"""
    artigo = "no" if fac["nome"].split()[0] in ("Centro", "Instituto") else "na"  # "no Centro Universitário", "na Universidade"
    desc = f"Transferência de Medicina {artigo} {fac['nome']} ({fac['cidade']}/{fac['uf']}): editais, quando costuma abrir, prazos e documentos."
    estruturados = (trilha_ld(("Início", ""), *([(NOMES_UF[fac["uf"]], f"estado/{fac['uf'].lower()}/")] if fac["uf"] in ESTADOS else []), (fac["sigla"], f"faculdade/{fac['id']}/")),
                    {"@type": "CollegeOrUniversity", "name": fac["nome"], "alternateName": fac["sigla"], "url": fac["site"],
                     "address": {"@type": "PostalAddress", "addressLocality": fac["cidade"], "addressRegion": fac["uf"], "addressCountry": "BR"}})
    # "edital 2027": o ano de ingresso do edital conferido mais recente; sem edital, não promete ano
    anos = [m.group(1) for x in eds if publicavel(x) for m in [re.match(r"(20\d\d)", str(x.get("semestre_ingresso") or ""))] if m]
    cauda = f" — edital {max(anos)}, prazos e documentos" if anos else " — editais, prazos e documentos"
    return layout(titulo_curto(f"Transferência de Medicina {artigo} {fac['nome']} ({fac['cidade']}){cauda}",
                               f"Transferência de Medicina {artigo} {fac['sigla']} ({fac['cidade']}){cauda}",
                               f"Transferência de Medicina {artigo} {fac['sigla']}{cauda}", limite=95),
                  desc, corpo, raiz, "faculdade", f"faculdade/{fac['id']}/", imagem,
                  estruturados=estruturados)


def pagina_estado(uf, facs, E, hoje):
    """Uma página por estado: editais abertos ou abrindo e todas as faculdades monitoradas (por cidade, sem ranking)."""
    raiz = "../../"
    nome = NOMES_UF.get(uf, uf)
    ids = {f["id"] for f in facs}
    vivos = sorted((x for x in E if x["faculdade_id"] in ids and situacao(x, hoje) in ("aberto", "em breve", "contínuo")),
                   key=lambda x: x.get("inscricao_fim") or "9999")
    por_id = {f["id"]: f for f in facs}
    cartoes = "".join(cartao_simples(x, por_id[x["faculdade_id"]], raiz, hoje) for x in vivos)

    def estado_fac(f):
        s = {situacao(x, hoje) for x in E if x["faculdade_id"] == f["id"]}
        if s & {"aberto", "contínuo"}:
            return '<span class="et ok">inscrições abertas</span>'
        if "em breve" in s:
            return '<span class="et aviso">abre em breve</span>'
        return '<span class="et">sem edital aberto agora</span>' if s else '<span class="et">não publicou transferência recentemente</span>'

    linhas = "".join(f'<tr><td><a href="{raiz}faculdade/{f["id"]}/">{e(f["nome"])}</a></td><td>{e(f["cidade"])}</td><td>{e(f["tipo"])}</td><td>{estado_fac(f)}</td></tr>'
                     for f in sorted(facs, key=lambda f: (slug(f["cidade"]), slug(f["nome"]))))
    abertos = sum(1 for x in vivos if situacao(x, hoje) == "aberto")
    corpo = f"""
<div class="wrap estreito">
  <nav class="trilha" aria-label="Você está em"><a href="{raiz}">Início</a> › {e(nome)}</nav>
  <section class="heroi">
    <h1>Transferência de Medicina {e(em_uf(uf))}</h1>
    <p class="lead">{len(facs)} {'escola médica monitorada' if len(facs) == 1 else 'escolas médicas monitoradas'} {e(em_uf(uf))}, com os editais conferidos no PDF oficial. Hoje, {abertos} {'edital está' if abertos == 1 else 'editais estão'} com inscrições abertas.</p>
    <div class="acoes"><a class="botao" href="{raiz}diagnostico/">Descobrir onde posso transferir</a></div>
  </section>
  <h2>Inscrições abertas ou abrindo {e(em_uf(uf))}</h2>
  <div class="grade-cartoes">{cartoes or '<div class="vazio">Nenhum edital aberto ou abrindo agora neste estado.</div>'}</div>
  <h2>Todas as faculdades monitoradas {e(em_uf(uf))}</h2>
  <p class="sub">Em ordem de cidade. A situação é recalculada a cada atualização do radar.</p>
  <div class="tabela"><table><thead><tr><th scope="col">Faculdade</th><th scope="col">Cidade</th><th scope="col">Tipo</th><th scope="col">Agora</th></tr></thead><tbody>{linhas}</tbody></table></div>
</div>"""
    desc = (f"Editais de transferência de Medicina {em_uf(uf)}: {len(vivos)} com inscrições abertas ou abrindo, prazos e documentos "
            f"conferidos no PDF oficial de {len(facs)} faculdades.")
    estruturados = (trilha_ld(("Início", ""), (nome, f"estado/{uf.lower()}/")),
                    {"@type": "CollectionPage", "name": f"Transferência de Medicina {em_uf(uf)}", "url": f"{SITE_URL}/estado/{uf.lower()}/",
                     "inLanguage": "pt-BR", "description": desc,
                     "mainEntity": {"@type": "ItemList", "numberOfItems": len(facs), "itemListElement": [
                         {"@type": "ListItem", "position": i, "url": f"{SITE_URL}/faculdade/{f['id']}/", "name": f["nome"]}
                         for i, f in enumerate(sorted(facs, key=lambda f: (slug(f["cidade"]), slug(f["nome"]))), 1)]}})
    return layout(f"Transferência de Medicina {em_uf(uf)}: editais abertos e prazos", desc, corpo, raiz, "estado", f"estado/{uf.lower()}/",
                  estruturados=estruturados)


def pagina_exterior(F, E, hoje):
    raiz = "../"
    aceitam = {}
    for x in E:
        if x.get("aceita_curso_exterior") is True or x.get("modalidade") == "exterior":
            aceitam.setdefault(x["faculdade_id"], []).append(x)
    linhas = ""
    for fid, eds in sorted(aceitam.items(), key=lambda kv: F[kv[0]]["nome"]):
        f = F[fid]
        vivo = [x for x in eds if situacao(x, hoje) in ("aberto", "em breve")]
        cls, status = texto_situacao(vivo[0], hoje) if vivo else ("", "sem edital aberto agora")
        linhas += (f"<tr><td><a href=\"{raiz}faculdade/{fid}/\">{e(f['nome'])}</a></td><td>{e(f['cidade'])}/{e(f['uf'])}</td>"
                   f"<td><span class=\"et {cls}\">{e(status)}</span></td></tr>")
    reais = [x for x in E if not x.get("fluxo_continuo")]
    aceitaram = sum(1 for x in reais if x.get("aceita_curso_exterior") is True or x.get("modalidade") == "exterior")
    vivos = sorted((x for x in E if (x.get("aceita_curso_exterior") is True or x.get("modalidade") == "exterior")
                    and situacao(x, hoje) in ("aberto", "em breve")), key=lambda x: x.get("inscricao_fim") or "9999")
    cartoes = "".join(cartao_simples(x, F[x["faculdade_id"]], raiz, hoje) for x in vivos)
    # o que os editais conferidos pedem a quem vem de fora (só o transcrito, com a página do PDF)
    rx = re.compile(r"apostila|consular|tradu[cç][aã]o|estrangeir|exterior|equival|revalid", re.I)
    pedidos = ""
    for b in isca_mod.editais_com_lista(isca_mod.do_exterior(E), F):
        docs = [re.sub(r"(?i)^(para )?quem (vem|estuda) (do|no) exterior:\s*", "", d) for d in b["ed"]["documentos"] if rx.search(d)]
        docs = [d[:1].upper() + d[1:] for d in docs]
        if docs:
            fonte = f' <span class="pag">{e(b["pagina"])}</span>' if b["pagina"] else ""
            pedidos += (f'<li><a href="{raiz}edital/{slug_edital(b["ed"])}/">{e(" / ".join(dict.fromkeys(b["siglas"])))}</a>: '
                        f'{e("; ".join(docs))}{fonte}</li>')
    corpo = f"""
<div class="wrap estreito">
  <section class="heroi">
    <span class="selo">Paraguai, Bolívia, Argentina e outros</span>
    <h1>Estuda Medicina fora do Brasil?</h1>
    <p class="lead">Voltar no meio do curso parece impossível: muitos editais nem aceitam quem vem de faculdade estrangeira, e cada um pede documentos diferentes, com apostila e tradução. Mas há caminho: dos {len(reais)} editais que conferimos, {aceitaram} aceitaram quem estuda no exterior.</p>
    <div class="acoes"><a class="botao grande" href="{raiz}diagnostico/?origem=exterior">Ver onde eu posso me inscrever</a></div>
  </section>
  <h2>Abertos agora para quem vem do exterior</h2>
  <p class="sub">Só editais conferidos que aceitam aluno de faculdade estrangeira, do prazo mais curto para o mais longo.</p>
  <div class="grade-cartoes">{cartoes or '<div class="vazio">Nenhum edital aberto agora para quem vem do exterior. Receba o aviso quando abrir.</div>'}</div>
  {bloco_alerta(raiz, "Receba os editais que aceitam quem estuda no exterior", "Um e-mail quando abrir edital conferido que aceita aluno de faculdade estrangeira. Depois, se quiser, ajuste o semestre e a distância.", "exterior", perfil_base={"origem": "exterior", "curso": "medicina"}, exterior=True)}
  <h2>Faculdades com editais que aceitaram quem estuda no exterior</h2>
  <p class="sub">Aceitar em um edital não garante que o próximo também aceite: confira sempre o edital vigente.</p>
  {f'<div class="tabela"><table><thead><tr><th scope="col">Faculdade</th><th scope="col">Cidade</th><th scope="col">Agora</th></tr></thead><tbody>{linhas}</tbody></table></div>' if linhas else '<div class="vazio">Nenhuma faculdade com edital que aceite quem estuda no exterior por enquanto.</div>'}
  <h2>O que os editais pedem a quem vem de fora</h2>
  <p class="sub">Tirado de cada edital conferido, com a página do PDF. Clique na faculdade para ver a lista completa.</p>
  {f'<ul class="lista-regras">{pedidos}</ul>' if pedidos else ''}
  <div class="aviso-caixa">Cada edital tem a sua lista e os seus prazos: alguns pedem visto consular em vez de apostila. Confira sempre na ficha do edital.</div>
  <h2>Passo a passo</h2>
  <ol class="passos">
    <li><strong>Peça os documentos na sua faculdade com antecedência.</strong> Histórico, ementas e declaração de matrícula demoram a sair.</li>
    <li><strong>Apostile no país onde estuda</strong> e faça a tradução juramentada. Guarde os originais.</li>
    <li><strong>Escolha editais que aceitem quem estuda no exterior.</strong> O diagnóstico já filtra isso para você.</li>
    <li><strong>Confira o semestre com vaga e o critério.</strong> Muitos editais fazem prova; outros só analisam o histórico.</li>
    <li><strong>Acompanhe os prazos.</strong> Marque os editais e baixe o calendário: a jornada avisa quando surgir edital novo para o seu perfil.</li>
  </ol>
  <p class="dica">Transferência não é revalidação de diploma: ela vale para quem ainda está cursando.</p>
</div>"""
    return layout("Transferência de Medicina do exterior para o Brasil: onde, quando e o que precisa", "Faculdades que aceitam transferência de quem estuda Medicina no Paraguai, Bolívia ou Argentina, documentos (apostila de Haia, tradução juramentada, ementas) e passo a passo.", corpo, raiz, "exterior", "exterior/", "og/exterior.png", ativo="exterior/")


def pagina_privacidade():
    contato = (f'pelo e-mail <a href="mailto:{e(CONTATO_EMAIL)}">{e(CONTATO_EMAIL)}</a>' if CONTATO_EMAIL
               else "pelo link de cancelamento presente em todo e-mail que enviamos")
    corpo = f"""
<div class="wrap estreito texto-longo">
  <section class="heroi"><h1>Privacidade</h1>
  <p class="lead">Pedimos o mínimo possível e explicamos tudo aqui, em português simples (Lei Geral de Proteção de Dados, Lei 13.709/2018).</p></section>
  <h2>Sem cadastro para usar o site</h2>
  <p>O diagnóstico, a jornada, o checklist e o calendário funcionam sem conta. As respostas ficam guardadas só no seu navegador (armazenamento local) e não chegam até nós. Você pode apagar tudo no botão "Apagar meus dados", na página inicial.</p>
  <h2>Alertas por e-mail (opcional)</h2>
  <ul class="lista-regras">
    <li><strong>O que guardamos:</strong> seu e-mail e o perfil do diagnóstico (onde estuda, curso, semestre, cidade aproximada, distância, tipo de faculdade e limite de taxa), além das faculdades que você pediu para seguir e dos prazos que pediu para lembrar. Não pedimos nome, CPF, telefone, histórico ou documentos.</li>
    <li><strong>Para quê:</strong> avisar quando abrir um edital compatível com o seu perfil ou de uma faculdade que você segue, lembrar os prazos que você pediu, mandar um resumo às segundas quando houver novidade e, nas duas primeiras semanas, 4 e-mails com dicas sobre transferência. Não vendemos nem repassamos seus dados, e não mandamos propaganda de terceiros.</li>
    <li><strong>Base legal:</strong> o seu consentimento, dado ao marcar a caixa e confirmar pelo link enviado ao seu e-mail.</li>
    <li><strong>Por quanto tempo:</strong> enquanto o alerta estiver ativo. Cadastros não confirmados são apagados em 7 dias.</li>
    <li><strong>Seus direitos:</strong> cancelar e apagar tudo a qualquer momento pelo link presente em todo e-mail. O cancelamento apaga o cadastro e o histórico de avisos na hora.</li>
    <li><strong>Quem processa:</strong> os dados ficam guardados no Supabase e os e-mails são enviados pelo Brevo, serviços usados só para essa finalidade.</li>
  </ul>
  <h2>Contagem de uso, sem cookies</h2>
  <p>Para saber se o site ajuda, contamos quantas vezes por dia cada ação acontece (por exemplo: "diagnóstico concluído na página do diagnóstico"). Guardamos só o dia, o nome da ação e o tipo de página. Não guardamos IP, identificador, endereço completo da página nem nada que diga quem você é, e não usamos cookies.</p>
  <h2>O que não fazemos</h2>
  <p>Não usamos cookies de rastreamento nem ferramentas de propaganda. A fonte e os mapas do site são servidos pelo próprio site (o mapa de rua da página de cada faculdade vem do OpenStreetMap).</p>
  <h2>Contato</h2>
  <p>Dúvidas ou pedidos sobre seus dados: {contato}.</p>
</div>"""
    return layout("Privacidade | Transfermed", "Como o Transfermed trata seus dados: sem cadastro para usar o site, alertas por e-mail opcionais e cancelamento que apaga tudo.",
                  corpo, "../", "privacidade", "privacidade/")


def foto_aprovada():
    return (DOCS / f"{FOTO}.webp").exists() and (DOCS / f"{FOTO}.jpg").exists()


PESSOA_SVG = ('<svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" '
              'stroke-linecap="round"><circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/></svg>')


def menu_celular(raiz, ativo=None):
    """Menu do celular (botão ☰ do cabeçalho): no celular, o cabeçalho fica só com a marca, a busca e este botão."""
    itens = [("diagnostico/", "Diagnóstico"), ("exterior/", "Estudo no exterior"), ("minha-lista/", "Minha lista"),
             ("sobre/", "Quem faz o Transfermed"), ("contato/", "Contato")]
    links = "".join(f'<li><a href="{raiz}{h}"{' aria-current="page"' if ativo == h else ""}>{n}'
                    + ('<span class="lista-n" hidden></span>' if h == "minha-lista/" else "") + "</a></li>" for h, n in itens)
    return f'<nav class="menu-celular" id="menu-celular" aria-label="Menu" hidden><div class="wrap"><ul>{links}</ul></div></nav>'


def quem_faz_botao():
    """Gatilho no cabeçalho: "Quem faz o Transfermed?" no computador, "Quem faz?" no celular (ícone se não couber)."""
    return ('<button type="button" class="quem-faz-botao" aria-expanded="false" aria-controls="quem-faz" aria-label="Quem faz o Transfermed?">'
            f'{PESSOA_SVG}<span class="qf-longo">Quem faz o Transfermed?</span><span class="qf-curto">Quem faz?</span></button>')


def quem_faz_painel(raiz):
    """Painel fechado por padrão e sem foto (a foto fica só na /sobre/). Fica fora do cabeçalho: o desfoque do
    cabeçalho (backdrop-filter) prenderia o painel fixo dentro dele, e no celular ele precisa subir de baixo."""
    return f"""<div class="quem-faz" data-quem-faz>
  <div class="qf-fundo" hidden></div>
  <section class="qf-painel" id="quem-faz" aria-label="Quem faz o Transfermed" tabindex="-1" hidden>
    <div class="qf-alca" aria-hidden="true"></div>
    <button type="button" class="qf-fechar" aria-label="Fechar">×</button>
    <p>Estudante de Medicina. Comecei no Paraguai e transferi para o Brasil. Criei o Transfermed para que outras pessoas não passem pelo que eu passei.</p>
    <a class="qf-link" href="{raiz}sobre/">Conheça a história completa →</a>
  </section>
</div>"""


MOTIVOS_CONTATO = [("erro", "Encontrei um erro"), ("duvida", "Tenho uma dúvida"), ("sugestao", "Tenho uma sugestão"),
                   ("outro", "Outro assunto")]
CONSENTIMENTO_CONTATO = ("Autorizo o Transfermed a usar estes dados só para responder a esta mensagem. "
                         "Eles são apagados em até 90 dias depois da resposta.")


def formulario_contato(raiz):
    motivos = "".join(f'<option value="{v}">{e(n)}</option>' for v, n in MOTIVOS_CONTATO)
    semestres = '<option value="">Escolha</option>' + "".join(f'<option value="{i}">{i}º</option>' for i in range(1, 13))
    return f"""<form id="form-contato" class="cartao formulario contato" novalidate>
  <div class="campo"><label class="rotulo" for="c-nome">Seu nome</label><input type="text" id="c-nome" name="nome" autocomplete="name" required maxlength="120"></div>
  <div class="campo"><label class="rotulo" for="c-email">Seu e-mail</label><input id="c-email" name="email" type="email" autocomplete="email" inputmode="email" required maxlength="200"></div>
  <div class="campo"><label class="rotulo" for="c-motivo">Motivo</label><select id="c-motivo" name="motivo">{motivos}</select></div>
  <fieldset><legend>Onde você estuda?</legend><div class="opcoes">
    <label><input type="radio" name="origem" value="brasil" checked>No Brasil</label>
    <label><input type="radio" name="origem" value="exterior">No exterior</label></div></fieldset>
  <div class="campo"><label class="rotulo" for="c-faculdade">Faculdade</label><input type="text" id="c-faculdade" name="faculdade" maxlength="160" placeholder="Ex.: Universidade Brasil"></div>
  <div class="campo"><label class="rotulo" for="c-semestre">Semestre</label><select id="c-semestre" name="semestre">{semestres}</select></div>
  <div class="campo"><label class="rotulo" for="c-mensagem">Mensagem</label><textarea id="c-mensagem" name="mensagem" rows="5" required maxlength="3000"></textarea></div>
  <label class="consentimento"><input type="checkbox" name="consentimento" required> <span>{e(CONSENTIMENTO_CONTATO)} <a href="{raiz}privacidade/">Privacidade</a>.</span></label>
  <div class="pote" aria-hidden="true"><label>Não preencha <input type="text" name="campo_extra" tabindex="-1" autocomplete="off" data-1p-ignore data-lpignore="true"></label></div>
  <button type="submit" class="botao">Mandar minha mensagem</button>
  <p class="dica">Grátis. Sem spam. Resposta em até 3 dias úteis.</p>
  <p class="dica" id="contato-msg" role="status" aria-live="polite"></p>
</form>"""


SOBRE_TEXTO = """<p>Oi, eu sou o Cauã.</p>
<p>Hoje estou no 7º período de Medicina na Universidade Brasil, em Fernandópolis (SP). Mas meu caminho não começou aqui.</p>
<p>Comecei a faculdade no Paraguai. No meu primeiro ano de curso, perdi meu pai. Foi o período mais difícil da minha vida, e mesmo assim eu decidi seguir em frente. Continuei estudando e consegui transferir meu curso para o Brasil.</p>
<p>O que mais me marcou na transferência foi a sensação de estar perdido: editais espalhados em sites diferentes, prazos curtos, regras confusas e pouca gente para explicar. Quando consegui, quis que ninguém mais precisasse passar por isso sem saber por onde começar.</p>
<p>Foi assim que comecei a ajudar outros estudantes, um por um, em uma consultoria focada em quem queria transferir. Com o tempo, percebi que muitas das dúvidas se repetiam e que eu podia alcançar muito mais gente se organizasse tudo em um só lugar.</p>
<p>O Transfermed nasceu disso. O formato mudou, mas a ideia continua a mesma: te ajudar nesse caminho. Ele reúne os editais em um lugar só, conferidos no documento oficial, e mostra para onde você pode transferir, quando e o que precisa. Seja você alguém que estuda no exterior e quer voltar, seja alguém que já estuda no Brasil e quer ficar mais perto de casa.</p>
<p>Se você está vivendo esse momento agora, eu sei como é. Espero que o Transfermed deixe esse caminho um pouco mais leve.</p>
<h2>Como funciona</h2>
<p>Cada informação vem do PDF oficial do edital, e você consegue ver a página exata de onde ela saiu. Um robô visita os sites das faculdades todos os dias, e, quando algo muda ou não bate, o edital aparece com aviso até eu revisar.</p>
<h2>Independência</h2>
<p>Nenhuma faculdade paga para aparecer aqui ou para ficar em destaque. Eu estudo na Universidade Brasil, e ela aparece com o mesmo critério de todas as outras.</p>
<h2>O que o Transfermed não faz</h2>
<p>Ele não garante vaga e não decide o aproveitamento das matérias. Quem decide é sempre a faculdade. O papel do Transfermed é te ajudar a chegar preparado.</p>"""


def pagina_sobre():
    raiz = "../"
    foto = ""
    if foto_aprovada():
        foto = (f'<picture class="sobre-foto"><source type="image/webp" srcset="{raiz}{FOTO}.webp">'
                f'<img src="{raiz}{FOTO}.jpg" alt="{e(FOTO_ALT)}" width="518" height="758" loading="lazy" decoding="async"></picture>')
    corpo = f"""
<div class="wrap estreito texto-longo">
  <section class="heroi"><h1>Quem faz o Transfermed</h1></section>
  <div class="sobre-grade">{foto}<div class="sobre-texto">{SOBRE_TEXTO}</div></div>
  <section class="contato-bloco" aria-labelledby="t-contato">
    <h2 id="t-contato">Fale comigo</h2>
    <p>Encontrou um erro, ficou com alguma dúvida ou tem uma ideia para melhorar? Me escreva pelo formulário abaixo. Eu leio todas as mensagens.</p>
    {formulario_contato(raiz)}
  </section>
</div>"""
    desc = ("Quem faz o Transfermed: Cauã Marin, estudante de Medicina que começou no Paraguai e transferiu para o Brasil. "
            "Como os dados são conferidos e por que o site é independente.")
    pessoa = {"@type": "Person", "name": "Cauã Marin", "jobTitle": "Estudante de Medicina",
              "affiliation": {"@type": "CollegeOrUniversity", "name": "Universidade Brasil"},
              "worksFor": {"@type": "Organization", "name": "Transfermed", "url": f"{SITE_URL}/"}}
    if foto_aprovada():
        pessoa["image"] = f"{SITE_URL}/{FOTO}.jpg"
    estruturados = ({"@type": "AboutPage", "name": "Quem faz o Transfermed", "url": f"{SITE_URL}/sobre/", "inLanguage": "pt-BR",
                     "description": desc, "mainEntity": pessoa},)
    return layout("Quem faz o Transfermed | Transfermed", desc, corpo, raiz, "sobre", "sobre/", estruturados=estruturados)


def pagina_contato():
    raiz = "../"
    corpo = f"""
<div class="wrap estreito">
  <section class="heroi"><h1>Contato</h1>
  <p class="lead">Encontrou um erro num edital, ficou com alguma dúvida ou tem uma ideia para melhorar? Respondo em até 3 dias úteis.</p></section>
  {formulario_contato(raiz)}
  <p class="dica espaco-32">Para saber quando abre edital para o seu perfil, o caminho mais rápido é o <a href="{raiz}diagnostico/">diagnóstico com alerta por e-mail</a>.</p>
</div>"""
    desc = "Fale com o Transfermed: avise de um erro, tire uma dúvida ou mande uma sugestão sobre transferência de Medicina."
    estruturados = ({"@type": "ContactPage", "name": "Contato | Transfermed", "url": f"{SITE_URL}/contato/", "inLanguage": "pt-BR",
                     "description": desc},)
    return layout("Contato | Transfermed", desc, corpo, raiz, "contato", "contato/", estruturados=estruturados)


def pagina_minha_lista():
    """Editais salvos com a estrela: ficam só no navegador (o app.js monta a lista). Página pessoal: fora do Google."""
    corpo = """
<div class="wrap estreito">
  <section class="heroi"><h1>Minha lista</h1>
  <p class="lead">Os editais que você salvou com a estrela, do prazo mais próximo para o mais distante. Fica só neste navegador, sem cadastro.</p></section>
  <noscript><div class="aviso-caixa">A lista precisa de JavaScript ligado no navegador.</div></noscript>
  <section id="minha-lista" aria-live="polite"></section>
</div>"""
    return layout("Minha lista | Transfermed", "Editais de transferência de Medicina que você salvou, com os prazos em ordem.", corpo, "../",
                  "minha-lista", "minha-lista/").replace('<meta name="description"', '<meta name="robots" content="noindex">\n<meta name="description"', 1)


def pagina_alerta(acao):
    textos = {"confirmar": ("Confirmando seu alerta…", "Confirmar alerta", "Confirmação do alerta por e-mail do Transfermed."),
              "descadastrar": ("Cancelando seus alertas…", "Cancelar alertas", "Cancelamento dos alertas por e-mail do Transfermed (apaga seus dados).")}
    carregando, titulo, descricao = textos[acao]
    corpo = f"""
<div class="wrap estreito">
  <section class="heroi"><h1>{titulo}</h1>
  <div id="alerta-acao" data-acao="{acao}" class="cartao" role="status" aria-live="polite"><p>{carregando}</p></div>
  <noscript><div class="aviso-caixa">Esta página precisa de JavaScript ligado no navegador.</div></noscript>
  <p class="acoes"><a class="botao sec" href="../../">Ir para o início</a></p></section>
</div>"""
    return layout(f"{titulo} | Transfermed", descricao, corpo, "../../", "alerta",
                  f"alerta/{acao}/").replace('<meta name="description"', '<meta name="robots" content="noindex">\n<meta name="description"', 1)


# ---------------------------------------------------------------- imagens de prévia (WhatsApp, redes)

def _fonte(tamanho, peso="Regular"):
    from PIL import ImageFont
    f = ImageFont.truetype(str(PASTA / "fontes" / "Inter.ttf"), tamanho)
    f.set_variation_by_name(peso)
    return f


def _quebrar(desenho, texto, fonte, largura):
    linhas, atual = [], ""
    for palavra in texto.split():
        teste = f"{atual} {palavra}".strip()
        if desenho.textlength(teste, font=fonte) <= largura:
            atual = teste
        else:
            linhas.append(atual)
            atual = palavra
    return linhas + [atual]


def _logo(desenho, x, y, r):
    desenho.ellipse((x - r, y - r, x + r, y + r), fill="#FFFFFF")
    for k, a in ((0.7, 90), (0.4, 160)):
        rr = r * k
        desenho.ellipse((x - rr, y - rr, x + rr, y + rr), outline=(15, 92, 77, a), width=max(2, r // 14))
    b, c = r * 0.12, r * 0.36
    desenho.rectangle((x - b, y - c, x + b, y + c), fill="#0F5C4D")
    desenho.rectangle((x - c, y - b, x + c, y + b), fill="#0F5C4D")
    desenho.ellipse((x + r * .45, y - r * .6, x + r * .65, y - r * .4), fill="#E8A33D")


def imagem_og(nome, sobretitulo, titulo, chips, rodape):
    """Imagem 1200x630. O nome do arquivo leva um hash do conteúdo: só regera quando algo muda."""
    from PIL import Image, ImageDraw
    conteudo = json.dumps([sobretitulo, titulo, chips, rodape], ensure_ascii=False)
    h = hashlib.sha1(conteudo.encode()).hexdigest()[:8]
    rel = f"og/{nome}-{h}.png"
    destino = DOCS / rel
    if destino.exists():
        return rel
    img = Image.new("RGB", (1200, 630), "#0F5C4D")
    d = ImageDraw.Draw(img, "RGBA")
    # anéis de radar ao fundo
    for i, raio in enumerate((520, 400, 280, 160)):
        d.ellipse((1050 - raio, 120 - raio, 1050 + raio, 120 + raio), outline=(227, 242, 236, 28 + i * 10), width=3)
    d.pieslice((1050 - 520, 120 - 520, 1050 + 520, 120 + 520), 200, 240, fill=(227, 242, 236, 22))
    _logo(d, 104, 104, 40)
    d.text((164, 78), "Transfermed", font=_fonte(34, "Bold"), fill="#FFFFFF")
    d.text((164, 118), "Seu radar de transferência de Medicina", font=_fonte(22), fill="#CFE8DF")
    d.text((72, 200), sobretitulo.upper(), font=_fonte(24, "SemiBold"), fill="#E8A33D")
    y = 240
    fonte_t = _fonte(62 if len(titulo) < 60 else 52, "Bold")
    for linha in _quebrar(d, titulo, fonte_t, 1040)[:3]:
        d.text((72, y), linha, font=fonte_t, fill="#FFFFFF")
        y += fonte_t.size + 10
    x, y = 72, max(y + 22, 440)
    fonte_c = _fonte(28, "SemiBold")
    for texto, cor, cor_txt in chips:
        w = d.textlength(texto, font=fonte_c) + 44
        if x + w > 1130:
            break
        d.rounded_rectangle((x, y, x + w, y + 56), radius=28, fill=cor)
        d.text((x + 22, y + 12), texto, font=fonte_c, fill=cor_txt)
        x += w + 14
    d.text((72, 560), rodape, font=_fonte(24), fill="#CFE8DF")
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, "PNG", optimize=True)
    return rel


def og_edital(ed, fac, hoje):
    # datas fixas (o WhatsApp guarda a prévia em cache; "faltam 5 dias" ficaria velho)
    s = situacao(ed, hoje)
    if s == "aberto":
        chips = [(f"Inscrições até {fmt(ed['inscricao_fim'])[:5]}", "#E8A33D", "#2B1A00")]
    elif s == "em breve":
        chips = [(f"Inscrições a partir de {fmt(ed['inscricao_inicio'])[:5]}", "#E8A33D", "#2B1A00")]
    elif s == "contínuo":
        chips = [("Pedidos o ano todo", "#E3F2EC", "#0A4338")]
    else:
        chips = [(texto_situacao(ed, hoje)[1], "#2E7565", "#FFFFFF")]
    total = total_vagas(ed)
    if total and not {"vagas", "edital"} & set(campos_conferir(ed)):  # número contestado não vai para a imagem
        chips.append((f"{total} vagas", "#2E7565", "#FFFFFF"))
    if ed.get("taxa_inscricao") is not None:
        chips.append(("Inscrição gratuita" if ed["taxa_inscricao"] == 0 else f"Taxa {dinheiro(ed['taxa_inscricao'])}", "#2E7565", "#FFFFFF"))
    nome_mod = MODALIDADES.get(ed.get("modalidade"), MODALIDADES["externa"])[0]
    sobre = f"{nome_mod}{' · ingresso ' + ed['semestre_ingresso'] if ed.get('semestre_ingresso') else ''}"
    return imagem_og(f"edital-{ed['id']}", sobre, fac["nome"], chips, f"{fac['cidade']}/{fac['uf']} · dados do edital oficial")


def og_faculdade(fac, eds, hoje):
    vivo = [x for x in eds if publicavel(x) and situacao(x, hoje) in ("aberto", "em breve", "contínuo")]
    chips = [(f"Inscrições até {fmt(vivo[0]['inscricao_fim'])[:5]}" if vivo[0].get("inscricao_fim") else "Pedidos o ano todo",
              "#E8A33D", "#2B1A00")] if vivo else [("Sem edital aberto no momento", "#2E7565", "#FFFFFF")]
    if fac.get("meses") and not vivo:
        chips.append((f"Costuma abrir em {MESES[fac['meses'][0] - 1]}", "#E8A33D", "#2B1A00"))
    return imagem_og(f"faculdade-{fac['id']}", f"Transferência de Medicina · {fac['cidade']}/{fac['uf']}", fac["nome"], chips,
                     "Editais, prazos e documentos conferidos no PDF oficial")


# ---------------------------------------------------------------- calendário

def dobrar(linha):
    """Formato .ics: linhas com mais de 75 bytes continuam na linha seguinte começando com espaço."""
    partes, atual = [], ""
    for c in linha:
        if len((atual + c).encode("utf-8")) > (75 if not partes else 74):
            partes.append(atual)
            atual = ""
        atual += c
    partes.append(atual)
    return "\r\n ".join(partes)


def nome_agenda(fac):
    """Faculdade e cidade no título do evento ("UNEX Jequié"), sem repetir a cidade que já está na sigla."""
    sigla, cidade = fac["sigla"], fac.get("cidade") or ""
    return sigla if not cidade or slug(cidade) in slug(sigla) else f"{sigla} {cidade}"


# Datas que viram evento de um dia na agenda (nunca um evento atravessando semanas): campo, sufixo do UID, título
# e alarmes. Resultado e matrícula entram quando transcritos do edital (Parte D).
DATAS_AGENDA = (("inscricao_inicio", "ini", "abertura das inscrições", ()),
                ("inscricao_fim", "fim", "último dia de inscrição", ("-P6DT15H", "-P1DT15H")),  # 7 e 2 dias antes, 9h
                ("data_prova", "prova", "prova", ("-P1DT15H",)),
                ("data_resultado", "resultado", "resultado", ()),
                ("data_matricula", "matricula", "matrícula", ()))


def eventos_ics(ed, fac):
    """Um evento de dia inteiro por data do edital (abertura, último dia, prova, resultado, matrícula). DTSTAMP fixo
    por edital: o arquivo só muda quando o edital muda (sem commit diário à toa)."""
    agora = (ed.get("conferido_em") or ed.get("detectado_em") or "2026-01-01")[:10].replace("-", "") + "T000000Z"

    def t(s):
        return re.sub(r"([,;\\])", r"\\\1", s).replace("\n", "\\n")

    ficha = f"{SITE_URL}/edital/{slug_edital(ed)}/"
    descricao = t(f"Ficha no Transfermed: {ficha}\nEdital oficial: {ed['url_edital']}\nConfira sempre no edital oficial.")
    nome = nome_agenda(fac)
    linhas = []
    for campo, sufixo, rotulo, alarmes in DATAS_AGENDA:
        dia = prazo_seguro(ed) if campo == "inscricao_fim" else ed.get(campo)
        if not dia:
            continue
        titulo = f"{nome}: {rotulo}"
        fim = (date.fromisoformat(dia) + timedelta(days=1)).isoformat()
        linhas += ["BEGIN:VEVENT", f"UID:{ed['id']}-{sufixo}@transfermed", f"DTSTAMP:{agora}",
                   f"DTSTART;VALUE=DATE:{dia.replace('-', '')}", f"DTEND;VALUE=DATE:{fim.replace('-', '')}",
                   f"SUMMARY:{t(titulo)}", f"DESCRIPTION:{descricao}", f"URL:{ficha}", "TRANSP:TRANSPARENT"]
        for gatilho in alarmes:
            linhas += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{t(titulo)}", f"TRIGGER:{gatilho}", "END:VALARM"]
        linhas.append("END:VEVENT")
    return linhas


def calendario(eventos, nome=None):
    """Arquivo .ics. Com nome, é um calendário para assinar (webcal): o app de agenda volta a buscar sozinho."""
    linhas = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Transfermed//Radar//PT", "CALSCALE:GREGORIAN"]
    if nome:
        linhas += [f"X-WR-CALNAME:{nome}", "REFRESH-INTERVAL;VALUE=DURATION:PT12H", "X-PUBLISHED-TTL:PT12H"]
    linhas += eventos + ["END:VCALENDAR"]
    return "\r\n".join(dobrar(l) for l in linhas) + "\r\n"


def ics_estatico(ed, fac):
    return calendario(eventos_ics(ed, fac))


def link_google_agenda(ed, fac, pagina_url):
    """Evento já preenchido no Google Agenda: o último dia de inscrição (ou a prova, se não houver prazo)."""
    dia, titulo = ((prazo_seguro(ed), f"{nome_agenda(fac)}: último dia de inscrição")
                   if ed.get("inscricao_fim") else (ed["data_prova"], f"{nome_agenda(fac)}: prova"))
    fim = (date.fromisoformat(dia) + timedelta(days=1)).isoformat()
    detalhes = f"Confira sempre o edital oficial: {ed['url_edital']}\nResumo e documentos: {pagina_url}"
    return ("https://calendar.google.com/calendar/render?action=TEMPLATE"
            f"&text={quote(titulo, safe='')}&dates={dia.replace('-', '')}/{fim.replace('-', '')}&details={quote(detalhes, safe='')}")


def assinatura_faculdade(fac):
    """Endereços do calendário da faculdade (todos os editais conferidos, presentes e futuros)."""
    https = f"{SITE_URL}/faculdade/{fac['id']}/prazos.ics"
    webcal = "webcal://" + https.split("://", 1)[1]
    return https, webcal, "https://calendar.google.com/calendar/r?cid=" + quote(webcal, safe="")


def bloco_agenda(ed, fac):
    """Google Agenda como ação principal; assinar o calendário da faculdade; o .ics fica discreto."""
    https, webcal, google_assinar = assinatura_faculdade(fac)
    pagina = f"{SITE_URL}/edital/{slug_edital(ed)}/"
    return f"""<div class="agenda">
      <div class="acoes"><a class="botao" href="{e(link_google_agenda(ed, fac, pagina))}" target="_blank" rel="noopener" data-medir="adicionar_agenda">Adicionar ao Google Agenda<span class="oculto"> (abre em nova aba)</span></a>
      <a class="botao sec" href="{e(webcal)}" data-medir="assinar_agenda">Assinar os prazos da {e(fac['sigla'])}</a></div>
      <details class="agenda-ajuda"><summary>Como assinar no Google, iPhone ou Outlook</summary>
        <p>A assinatura se atualiza sozinha quando o edital muda ou a {e(fac['sigla'])} publica edital novo.</p>
        <ul><li><strong>Google Agenda:</strong> <a href="{e(google_assinar)}" target="_blank" rel="noopener">abra este link</a> e toque em "Adicionar".</li>
        <li><strong>iPhone:</strong> toque em "Assinar os prazos" e confirme "Assinar".</li>
        <li><strong>Outlook:</strong> Adicionar calendário › Da Internet › cole <code>{e(https)}</code>.</li></ul>
        <p class="dica">O Google pode levar até um dia para mostrar uma mudança. Prefere um arquivo? <a href="prazos.ics" download>Baixar .ics</a> (não se atualiza).</p>
      </details></div>"""


# ---------------------------------------------------------------- aplicativo (PWA)

def arquivos_app():
    from PIL import Image, ImageDraw
    for tam in (192, 512):
        destino = DOCS / "assets" / f"icone-{tam}.png"
        if destino.exists():
            continue
        img = Image.new("RGB", (tam, tam), "#0F5C4D")
        d = ImageDraw.Draw(img, "RGBA")
        _logo(d, tam // 2, tam // 2, int(tam * 0.36))
        img.save(destino, "PNG", optimize=True)
    manifesto = {"name": "Transfermed: radar de transferência de Medicina", "short_name": "Transfermed",
                 "description": "Descubra onde você pode transferir Medicina e acompanhe os prazos.",
                 "start_url": "./", "scope": "./", "display": "standalone", "background_color": "#F7F5F1",
                 "theme_color": "#0F5C4D", "lang": "pt-BR",
                 "icons": [{"src": "assets/icone-192.png", "sizes": "192x192", "type": "image/png"},
                           {"src": "assets/icone-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}]}
    gravar(DOCS / "manifest.webmanifest", json.dumps(manifesto, ensure_ascii=False, indent=2))
    versao = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    gravar(DOCS / "sw.js", f"""// Transfermed: funciona sem internet com a última versão vista.
// HTML sempre da rede (sem a cópia do navegador); o resto da rede primeiro; cópia local só se a rede cair.
// O service worker novo assume na hora e apaga os caches antigos.
const CACHE = 'tm-{versao}';
const BASE = ['./', 'assets/estilo.css', 'assets/app.js', 'assets/logo.svg', 'assets/brasil.svg', 'assets/inter.woff2', 'assets/municipios.json', 'dados.js'];
self.addEventListener('install', ev => {{
  self.skipWaiting();  // não espera as abas antigas fecharem, nem depende de a cópia da base dar certo
  ev.waitUntil(caches.open(CACHE).then(c => Promise.all(BASE.map(u => c.add(new Request(u, {{cache: 'reload'}})).catch(() => {{}})))));
}});
self.addEventListener('activate', ev => {{
  ev.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
}});
self.addEventListener('fetch', ev => {{
  const req = ev.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== location.origin) return;
  const html = req.mode === 'navigate' || (req.headers.get('accept') || '').includes('text/html');
  ev.respondWith(fetch(req, html ? {{cache: 'no-cache'}} : {{}}).then(res => {{
    if (res.ok) {{ const copia = res.clone(); caches.open(CACHE).then(c => c.put(req, copia)); }}
    return res;
  }}).catch(() => caches.match(req, {{ignoreSearch: true}}).then(r => r || (html ? caches.match('./') : Response.error()))));
}});
""")



# ---------------------------------------------------------------- execução

def gravar(caminho, texto):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if caminho.suffix == ".html":  # sem espaço sobrando no fim das linhas
        texto = re.sub(r"[ \t]+(?=\r?\n)", "", texto)
    caminho.write_text(texto, encoding="utf-8", newline="")


def main():
    F = {f["id"]: f for f in json.loads((PASTA / "data" / "faculdades.json").read_text(encoding="utf-8"))}
    todos = [x for x in json.loads((PASTA / "data" / "editais.json").read_text(encoding="utf-8")) if x.get("faculdade_id") in F]
    E = [x for x in todos if publicavel(x)]
    # a cópia pública da base acompanha o site (antes só o radar.py a regravava: gerar à mão deixava a cópia velha)
    shutil.copyfile(PASTA / "data" / "editais.json", DOCS / "editais.json")
    hoje = date.today().isoformat()
    por_uf = {}
    for f in F.values():
        por_uf.setdefault(f["uf"], []).append(f)
    ESTADOS[:] = sorted((uf for uf, fs in por_uf.items() if len(fs) >= 5), key=lambda uf: NOMES_UF.get(uf, uf))

    # meses em que cada faculdade costuma abrir: ficha + início das inscrições dos editais conferidos
    for f in F.values():
        meses = set(f.get("meses_costuma_abrir") or [])
        meses |= {int(x["inscricao_inicio"][5:7]) for x in E if x["faculdade_id"] == f["id"] and x.get("inscricao_inicio")}
        f["meses"] = sorted(meses)

    # dados compactos para o JavaScript (só editais conferidos)
    compactos = []
    for x in E:
        docs, _ = documentos(x)
        compactos.append({k: v for k, v in {
            "id": x["id"], "slug": slug_edital(x), "fid": x["faculdade_id"], "mod": x.get("modalidade"),
            "sem": x.get("semestre_ingresso"), "ini": x.get("inscricao_inicio"), "fim": prazo_seguro(x),
            "prova": x.get("data_prova"), "res": x.get("data_resultado"), "mat": x.get("data_matricula"), "vagas": x.get("vagas"), "taxa": x.get("taxa_inscricao"),
            "quem": x.get("quem_pode"), "ext": x.get("aceita_curso_exterior"), "exc": x.get("exclui_quem_ja_transferiu"),
            "docs": docs, "status": "conferir" if avisos(x) else x.get("status"), "url": x["url_edital"], "sit": x.get("situacao"),
            "fluxo": x.get("fluxo_continuo")}.items() if v not in (None, "", [])})
    facs = {fid: {"id": fid, "nome": f["nome"], "sigla": f["sigla"], "cidade": f["cidade"], "uf": f["uf"], "lat": f["lat"],
                  "lon": f["lon"], "tipo": f["tipo"], "meses": f["meses"], "ext": f.get("aceita_exterior")} for fid, f in F.items()}
    novos = sorted((x for x in todos if novo_detectado(x, hoje)), key=lambda x: x["detectado_em"], reverse=True)
    novos_js = [{"fid": x["faculdade_id"], "url": x["url_edital"], "det": x["detectado_em"]} for x in novos]
    # sugestões para quem estuda no exterior (só ajudam a digitar; não entram no cruzamento)
    exterior = [f"{x['nome']} – {x['pais']}" for x in json.loads((PASTA / "data" / "faculdades_exterior.json").read_text(encoding="utf-8"))["faculdades"]]
    # sem as variáveis (sessão local, monitor), mantém a configuração pública já publicada: antes o formulário de
    # alerta saía do ar até a próxima rodada do radar
    cfg = {"supabaseUrl": SUPABASE_URL, "supabaseAnon": SUPABASE_ANON_KEY}
    if not SUPABASE_URL and (DOCS / "dados.js").exists():
        m = re.search(r"window\.TM_CONFIG=(\{.*?\});", (DOCS / "dados.js").read_text(encoding="utf-8"))
        if m:
            antigo = json.loads(m.group(1))
            cfg = {"supabaseUrl": antigo.get("supabaseUrl", ""), "supabaseAnon": antigo.get("supabaseAnon", "")}
            if "CONTATO_ATIVO" not in os.environ and antigo.get("contato"):
                cfg["contato"] = True
            if "ENVIO_IMEDIATO" not in os.environ and antigo.get("envioImediato"):
                cfg["envioImediato"] = True
            if "AGENDA_UNICA" not in os.environ and antigo.get("agendaUnica"):
                cfg["agendaUnica"] = True
    if os.environ.get("AGENDA_UNICA") == "1":  # função agenda do schema.sql testada no Supabase
        cfg["agendaUnica"] = True
    if os.environ.get("ENVIO_IMEDIATO") == "1":  # token do GitHub no Vault do Supabase: confirmação em ~1 minuto
        cfg["envioImediato"] = True
    gravar(DOCS / "dados.js", "window.TM=" + json.dumps({"gerado_em": hoje, "faculdades": facs, "editais": compactos, "novos": novos_js,
                                                         "exterior": exterior},
                                                        ensure_ascii=False, separators=(",", ":"))
           + ";\nwindow.CAPITAIS=" + json.dumps(CAPITAIS, ensure_ascii=False, separators=(",", ":"))
           + ";\nwindow.TM_CONFIG=" + json.dumps({"contato": CONTATO_ATIVO, **cfg, "consentimento": CONSENTIMENTO}, ensure_ascii=False) + ";\n")

    # imagens de prévia (só as que mudaram são refeitas; as que sobraram são apagadas)
    usadas = {imagem_og("inicio", "Grátis · sem cadastro", "Descubra em 1 minuto onde você pode transferir Medicina",
                        [(f"{len(F)} faculdades", "#E3F2EC", "#0A4338"), (f"{sum(1 for x in E if x.get('conferido_em'))} editais conferidos", "#2E7565", "#FFFFFF")],
                        "Dados tirados do edital oficial"),
              imagem_og("exterior", "Paraguai · Bolívia · Argentina", "Estuda Medicina no exterior? Veja onde transferir no Brasil",
                        [("Documentos", "#2E7565", "#FFFFFF"), ("Passo a passo", "#2E7565", "#FFFFFF")], "Transfermed")}
    # nomes fixos para as páginas gerais (o HTML aponta para og/inicio.png e og/exterior.png)
    for fixo, variavel in (("og/inicio.png", sorted(u for u in usadas if "inicio" in u)[0]), ("og/exterior.png", sorted(u for u in usadas if "exterior" in u)[0])):
        shutil.copyfile(DOCS / variavel, DOCS / fixo)
        usadas.add(fixo)

    # isca do alerta: checklist em PDF só com as listas transcritas dos editais (o arquivo só muda se os dados mudarem)
    ISCA["total"] = isca_mod.gerar(E, F, DOCS / isca_mod.ARQUIVO, PASTA / "fontes" / "Inter.ttf", SITE_URL)
    ISCA["exterior"] = isca_mod.gerar(isca_mod.do_exterior(E), F, DOCS / isca_mod.ARQUIVO_EXTERIOR, PASTA / "fontes" / "Inter.ttf",
                                      SITE_URL, subtitulo="para quem estuda Medicina no exterior")

    for pasta in ("faculdade", "edital"):  # recriadas do zero (some o que saiu da base)
        shutil.rmtree(DOCS / pasta, ignore_errors=True)
    gravar(DOCS / "index.html", pagina_inicio(F, E, hoje, hoje, novos))
    gravar(DOCS / "editais" / "index.html", pagina_editais(F, E, hoje, hoje, novos))
    gravar(DOCS / "diagnostico" / "index.html", pagina_diagnostico())
    gravar(DOCS / "exterior" / "index.html", pagina_exterior(F, E, hoje))
    gravar(DOCS / "privacidade" / "index.html", pagina_privacidade())
    gravar(DOCS / "sobre" / "index.html", pagina_sobre())
    gravar(DOCS / "contato" / "index.html", pagina_contato())
    gravar(DOCS / "minha-lista" / "index.html", pagina_minha_lista())
    for acao in ("confirmar", "descadastrar"):
        gravar(DOCS / "alerta" / acao / "index.html", pagina_alerta(acao))
    shutil.rmtree(DOCS / "estado", ignore_errors=True)
    for uf in ESTADOS:
        facs = por_uf[uf]
        gravar(DOCS / "estado" / uf.lower() / "index.html", pagina_estado(uf, facs, E, hoje))
    for fid, f in F.items():
        eds = [x for x in todos if x["faculdade_id"] == fid]
        img = og_faculdade(f, eds, hoje)
        usadas.add(img)
        gravar(DOCS / "faculdade" / fid / "index.html", pagina_faculdade(f, eds, hoje, img))
    distintivos = distintivos_edital(E, F)
    for x in E:
        pasta = DOCS / "edital" / slug_edital(x)
        img = og_edital(x, F[x["faculdade_id"]], hoje)
        usadas.add(img)
        gravar(pasta / "index.html", pagina_edital(x, F[x["faculdade_id"]], hoje, img, distintivos.get(x["id"], "")))
        if x.get("inscricao_fim") or x.get("data_prova"):
            gravar(pasta / "prazos.ics", ics_estatico(x, F[x["faculdade_id"]]))
    # calendário para assinar de cada faculdade (existe mesmo sem edital: quem assina recebe o próximo sozinho)
    for f in F.values():
        eventos = [l for x in E if x["faculdade_id"] == f["id"] and (x.get("inscricao_fim") or x.get("data_prova"))
                   for l in eventos_ics(x, f)]
        gravar(DOCS / "faculdade" / f["id"] / "prazos.ics", calendario(eventos, f"Transferência de Medicina: {nome_agenda(f)}"))
    # sitemap.xml e robots.txt (para o Google achar todas as páginas)
    # lastmod real: a data do dado mais novo que a página mostra (conferência, leitura do robô, detecção), não "hoje"
    def data_ed(x):
        return max(d for d in (x.get("conferido_em"), x.get("atualizado_em"), x.get("detectado_em"), "2026-01-01") if d)[:10]

    def data_fac(f):
        return max([f.get("ultima_conferencia") or "2026-01-01"] + [data_ed(x) for x in todos if x["faculdade_id"] == f["id"]])[:10]

    geral = max(data_fac(f) for f in F.values())
    ext = [data_ed(x) for x in E if x.get("aceita_curso_exterior") is True or x.get("modalidade") == "exterior"]
    urls = [("", geral, "daily"), ("editais/", geral, "daily"), ("exterior/", max(ext) if ext else geral, "weekly")]
    urls += [(u, d, "monthly") for u, d in TEXTO_ATUALIZADO.items()]
    urls += [(f"estado/{uf.lower()}/", max(data_fac(f) for f in por_uf[uf]), "daily") for uf in ESTADOS]
    urls += [(f"faculdade/{fid}/", data_fac(f), "weekly") for fid, f in F.items()]
    urls += [(f"edital/{slug_edital(x)}/", data_ed(x), "weekly") for x in E]
    gravar(DOCS / "sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "".join(f"  <url><loc>{e(SITE_URL + '/' + u)}</loc><lastmod>{d}</lastmod><changefreq>{c}</changefreq></url>\n" for u, d, c in urls)
           + "</urlset>\n")
    gravar(DOCS / "robots.txt", f"User-agent: *\nAllow: /\nDisallow: /alerta/\nDisallow: /minha-lista/\n\nSitemap: {SITE_URL}/sitemap.xml\n")
    for velho in (DOCS / "og").glob("*.png"):
        if f"og/{velho.name}" not in usadas:
            velho.unlink()
    arquivos_app()
    print(f"Site gerado: {len(F)} faculdades, {len(E)} editais publicados ({len(todos) - len(E)} só no histórico), "
          f"{len(usadas)} imagens de prévia")


if __name__ == "__main__":
    main()
