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
import tempo
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path
from urllib.parse import quote, urlparse

import funcoes
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

# formulário de contato: no ar e ligado por padrão (funcoes.py); CONTATO_ATIVO=0 no GitHub desliga
CONTATO_ATIVO = funcoes.ligada("CONTATO_ATIVO")
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
    "interna": ("Transferência interna", "Edital da própria faculdade, para os alunos dela; veja no edital quem pode"),
    "exterior": ("Para quem estuda no exterior", "Edital próprio para alunos de faculdades estrangeiras"),
    "portador_diploma": ("Portador de diploma (novo título)", "Para quem já concluiu uma graduação (obtenção de novo título); veja no edital quem ele aceita"),
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
PROXIMO_UF = None  # próximo estado da fila: botão "XX · em breve". Sem próximo enquanto a expansão está pausada (prioridade SP, MG, BA, RJ, PR)
# Prioridade de cobertura (dono, 01/11/2026): profundidade antes de largura. Esta é a ordem de botões, chips e links.
PRIORITARIOS = ["SP", "MG", "BA", "RJ", "PR"]
# Só entra aqui o estado que cumpre TODO o "completo" do ROADMAP (100% do e-MEC cadastrado, robô diário nos acessíveis,
# editais abertos completos, histórico). Hoje nenhum: a linha da home não afirma o que ainda não foi verificado.
COMPLETOS = []


def ordem_uf(uf):
    """Prioritários na ordem fixa, depois os demais por nome."""
    return (PRIORITARIOS.index(uf), "") if uf in PRIORITARIOS else (len(PRIORITARIOS), NOMES_UF.get(uf, uf))


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
TEXTO_ATUALIZADO = {"diagnostico/": "2026-10-28", "sobre/": "2026-10-28", "contato/": "2026-10-28", "privacidade/": "2026-11-09"}
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


def ate_vagas(ed):
    """Edital com inscrições abertas "até completar as vagas" (sem data final; ex.: Afya 02/2027). O fluxo contínuo
    sem edital (pedido direto, ex.: UNILAGO) é fluxo_continuo True."""
    return ed.get("fluxo_continuo") == "vagas"


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
        return "ok", "Inscrições abertas até completar as vagas" if ate_vagas(ed) else "Pedidos o ano todo (sem edital)"
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


# logo v2 aprovada em 06/11/2026. Arquivos com -v3 no nome: o navegador não mostra o ícone antigo guardado em cache.
# Ficam em docs/assets/marca/ (versionados; o robô não os recria nem apaga). A imagem de prévia provisória é a logo 512.
MARCA = "assets/marca/"
OG_LOGO = MARCA + "logo-512-v3.png"


def layout(titulo, descricao, corpo, raiz, pagina, caminho, imagem=OG_LOGO, ativo=None, extra_body="", estruturados=()):
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
<meta property="og:image:width" content="{512 if imagem == OG_LOGO else 1200}">
<meta property="og:image:height" content="{512 if imagem == OG_LOGO else 630}">
<meta name="twitter:card" content="{'summary' if imagem == OG_LOGO else 'summary_large_image'}">
<meta name="theme-color" content="#0F5C4D">
<link rel="icon" href="{raiz}{MARCA}favicon-v3.svg" type="image/svg+xml" sizes="any">
<link rel="icon" href="{raiz}{MARCA}favicon-v3.ico" sizes="48x48">
<link rel="apple-touch-icon" href="{raiz}{MARCA}logo-180-v3.png">
<link rel="manifest" href="{raiz}manifest.webmanifest">
<link rel="preload" href="{raiz}assets/inter.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{raiz}assets/estilo.css?v={versao_assets()}">
{json_ld(*estruturados)}</head>
<body data-pagina="{pagina}" data-raiz="{raiz}"{extra_body}>
<a class="pular" href="#conteudo">Pular para o conteúdo</a>
<header class="topo"><div class="wrap">
  <div class="topo-marca"><a class="marca" href="{raiz}"><img src="{raiz}{MARCA}transfermed-logo-v3.svg" alt="" width="36" height="36"><span><b>Transfermed</b><small>Seu radar de transferência de Medicina</small></span></a>{quem_faz_botao()}</div>
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
    <div><a class="marca" href="{raiz}"><img src="{raiz}{MARCA}transfermed-logo-v3.svg" alt="" width="28" height="28"><b>Transfermed</b></a>
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


QUARENTENA = PASTA / "data" / "quarentena.json"
def aviso_alterado(desde):
    return f"O edital foi alterado em {fmt(desde)}. Confira o PDF antes de enviar documentos."


def aplicar_quarentena(editais, caminho=None):
    """Quarentena (guardião, T6.2): edital publicado cujo PDF mudou depois da última conferência vira "conferir" no prazo, na
    página, nos e-mails e nos cartões, em vez de continuar afirmando uma data que pode ter mudado. Só em memória: o arquivo
    data/editais.json não é alterado. Sai sozinha quando `conferido_em` passa a ser igual ou posterior a `desde`."""
    try:
        q = json.loads((caminho or QUARENTENA).read_text(encoding="utf-8")).get("editais", {})
    except (OSError, ValueError):
        return editais
    for ed in editais:
        item = q.get(ed.get("id"))
        if not item or (ed.get("conferido_em") or "") >= item["desde"]:
            continue
        campos = dict(ed.get("conferir_campos") or {})
        campos.setdefault("inscricao_fim", aviso_alterado(item["desde"]))
        ed["status"], ed["conferir_campos"], ed["em_quarentena"], ed["alterado_em"] = "conferir", campos, True, item["desde"]
    return editais


PDFS_FORA = {}  # chave do documento -> primeiro dia em que o PDF deixou de abrir (preenchido em main())
FALHAS_PARA_AVISAR_PDF = 2  # dias seguidos sem abrir (uma falha isolada pode ser instabilidade do site da faculdade)


def chave_documento(url):
    """Mesma regra de radar.chave_url (não se importa o radar aqui: ele importa este módulo)."""
    u = re.sub(r"^https?://(www\.)?", "", (url or "").strip())
    return re.sub(r"(%20|\s)+$", "", u).lower()


def pdfs_fora_do_ar(caminho=None):
    """{chave: dia}: PDFs de edital que o monitor não consegue abrir há 2 dias seguidos ou mais (data de retratos.json)."""
    try:
        pdfs = json.loads((caminho or PASTA / "data" / "retratos.json").read_text(encoding="utf-8")).get("pdfs", {})
    except (OSError, ValueError):
        return {}
    fora = {}
    for chave, x in pdfs.items():
        if (x.get("falhas_seguidas") or 0) >= FALHAS_PARA_AVISAR_PDF:
            fora[chave] = x.get("falha_desde") or (date.fromisoformat(x["verificado_em"]) - timedelta(days=x["falhas_seguidas"] - 1)).isoformat()
    return fora


def avisos_do_pdf(ed, fac):
    """Avisos visíveis no topo da ficha: edital alterado depois da última conferência e PDF fora do ar no site da faculdade."""
    caixas = []
    if ed.get("alterado_em"):
        caixas.append(f'<div class="aviso-caixa"><strong>Atenção:</strong> {e(aviso_alterado(ed["alterado_em"]))}</div>')
    desde = PDFS_FORA.get(chave_documento(ed.get("url_edital")))
    if desde and not ed.get("fluxo_continuo"):
        pagina = (fac.get("paginas_editais") or [fac.get("site")])[0]
        link = f' <a href="{e(pagina)}" target="_blank" rel="noopener">Ver a página de transferência da faculdade<span class="oculto"> (abre em nova aba)</span></a>.' if pagina else ""
        caixas.append(f'<div class="aviso-caixa"><strong>Atenção:</strong> O PDF do edital está fora do ar no site da faculdade desde {fmt(desde)}.{link}</div>')
    for url in ed.get("pdfs_em_espera") or []:   # documento listado na página oficial que não abre (o monitor tenta de novo todo dia)
        desde = PDFS_FORA.get(chave_documento(url))
        if desde:
            caixas.append(f'<div class="aviso-caixa"><strong>Atenção:</strong> Uma retificação deste edital está listada na página oficial, mas o PDF está fora do ar desde {fmt(desde)}. '
                          f'Confira a página da faculdade antes de enviar documentos.</div>')
    return "".join(caixas)


def problemas_do_checklist(ed):
    """Regras para um checklist poder ir ao ar: data da conferência, página em todo item, prazo em toda etapa e nenhum "conferir"."""
    c = ed.get("checklist")
    if not c:
        return []
    erros = []
    if not c.get("conferido_em"):
        erros.append("sem data de conferência")
    for et in c.get("etapas", []):
        if not et.get("prazo"):
            erros.append(f"etapa sem prazo: {et.get('titulo')}")
        for i in et.get("itens", []):
            if not i.get("pagina"):
                erros.append(f"item sem página: {i.get('texto')}")
            if "conferir" in " ".join(str(v) for v in i.values()).lower():
                erros.append(f"item ainda a conferir: {i.get('texto')}")
    return erros


def bloco_checklist(ed):
    """Checklist por edital, publicado só quando fechou: cada item com a página do PDF e a data da conferência; sem "conferir"
    (o que não fecha fica em rascunho, fora da base). Estrutura em ed["checklist"]: {conferido_em, etapas[{titulo, prazo, itens[{texto, pagina, obs}]}], aviso}."""
    c = ed.get("checklist")
    if not c or not c.get("etapas") or problemas_do_checklist(ed):
        return ""
    etapas = ""
    for et in c["etapas"]:
        itens = "".join(f'<li>{e(i["texto"])} <span class="pag">({e(i["pagina"])})</span>'
                        + (f'<br><small>{e(i["obs"])}</small>' if i.get("obs") else "") + "</li>" for i in et["itens"])
        etapas += f'<h4>{e(et["titulo"])}</h4><p><strong>Prazo:</strong> {e(et["prazo"])}</p><ul class="lista-regras">{itens}</ul>'
    aviso = f'<p class="dica">{e(c["aviso"])}</p>' if c.get("aviso") else ""
    return (f'<section class="checklist-edital" aria-labelledby="t-checklist-{ed["id"]}"><h3 id="t-checklist-{ed["id"]}">Checklist de documentos e prazos</h3>'
            f'{etapas}{aviso}<p class="dica">Conferido nos PDFs do edital em {fmt(c["conferido_em"])}. Confira sempre o edital oficial antes de enviar documentos.</p></section>')


def fora_dos_emails(ed):
    return bool(CAMPOS_PRAZO & set(campos_conferir(ed)))


# Prazo final diferente em duas fontes oficiais (edital x página da faculdade): o edital entra no site e nos e-mails
# com a data mais cedo como prazo seguro (inscricao_fim) e o aviso com as duas datas.
# prazo_divergente = {"edital": "AAAA-MM-DD", "edital_onde": "p. 1 e 3", "pagina": "AAAA-MM-DD", "url_pagina": "..."}
#
# Contradição de prazo dentro do próprio edital (decisão do dono, 12/11/2026): duas datas para o fim da inscrição, os dois trechos com página.
# prazo_contraditorio = {"datas": [{"data": "AAAA-MM-DD", "onde": "2º aditivo, p. 3"}, {"data": "AAAA-MM-DD", "onde": "edital consolidado, p. 2"}]}
# A ficha, o alerta e o lembrete usam a data mais cedo como limite seguro; `inscricao_fim` guarda essa mesma data e o campo sai de `conferir_campos`.
def datas_contraditorias(ed):
    return [x["data"] for x in (ed.get("prazo_contraditorio") or {}).get("datas") or [] if x.get("data")]


def prazo_seguro(ed):
    datas = datas_contraditorias(ed)
    if datas:
        return min(datas)
    d = ed.get("prazo_divergente")
    return min(d["edital"], d["pagina"]) if d else ed.get("inscricao_fim")


def aviso_prazo_seguro(ed):
    c = ed.get("prazo_contraditorio")
    if c and datas_contraditorias(ed):
        lidas = "; ".join(f"{fmt(x['data'])}" + (f" ({x['onde']})" if x.get("onde") else "") for x in sorted(c["datas"], key=lambda x: x["data"]))
        return (f"Prazo seguro: {fmt(prazo_seguro(ed))}. O edital também cita outra data; confirme com a faculdade. "
                f"Datas lidas no edital: {lidas}.")
    d = ed.get("prazo_divergente")
    if not d:
        return ""
    onde = f" ({d['edital_onde']})" if d.get("edital_onde") else ""
    return (f"O edital diz {fmt(d['edital'])}{onde} e a página da faculdade diz {fmt(d['pagina'])}. "
            f"Para não correr risco, considere {fmt(prazo_seguro(ed))}.")


def avisos(ed):
    """Todos os avisos do edital, por campo: os de conferência e o do prazo seguro (no campo inscricao_fim)."""
    a = dict(campos_conferir(ed))
    if ed.get("prazo_divergente") or datas_contraditorias(ed):
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
    for uf, pts in sorted(por_uf.items(), key=lambda kv: ordem_uf(kv[0])):
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
        s = "aberto" if ate_vagas(x) else situacao(x, hoje)  # edital até completar as vagas: inscrições abertas
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


def bloco_numeros(F, E, gerado, hoje):
    """Números da base (home, logo abaixo do mapa, e /editais/), tirados dos dados: nada digitado à mão.
    "Abertas hoje" é recalculado no navegador (#n-abertos), porque o site pode ser aberto dias depois de gerado."""
    abertos = sum(situacao(x, hoje) == "aberto" or ate_vagas(x) for x in E)
    return f"""<div class="numeros faixa-numeros-in" role="group" aria-label="Números da base">
    <div class="numero"><b data-conta>{len(F)}</b><span>faculdades monitoradas</span></div>
    <div class="numero"><b data-conta>{len(E)}</b><span>editais conferidos no PDF oficial, com a página de cada dado</span></div>
    <div class="numero"><b id="n-abertos" data-conta>{abertos}</b><span>editais com inscrição aberta hoje</span></div>
    <div class="numero numero-data"><span>Atualizado em</span><b class="data">{fmt(gerado)}</b></div>
  </div>"""


def pagina_editais(F, E, gerado, hoje, novos=()):
    """Todos os editais abertos ou abrindo, o mapa, os números da base e os detectados pelo robô (saíram da home)."""
    raiz = "../"
    vivos = sorted([x for x in E if situacao(x, hoje) in ("aberto", "em breve") or ate_vagas(x)],
                   key=lambda x: (x.get("inscricao_fim") is None, x.get("inscricao_fim") or ""))
    estaticos = "".join(cartao_simples(x, F[x["faculdade_id"]], raiz, hoje) for x in vivos)
    bloco_novos = ""
    if novos:
        bloco_novos = (f'<h2 id="detectados">Detectados pelo robô, ainda sem conferência</h2><div class="grade-cartoes">'
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
  {bloco_numeros(F, E, gerado, hoje)}
  {bloco_alerta(raiz, "Prefere receber por e-mail?", "Avisamos quando abrir edital de transferência de Medicina. Depois do e-mail, você pode ajustar o perfil (semestre, Brasil ou exterior).", "editais", botao="Receber os editais por e-mail", perfil_base={"curso": "medicina"}, discreto=True)}
</div>"""
    desc = "Todos os editais de transferência de Medicina com inscrições abertas ou abrindo, conferidos no PDF oficial, com prazo, vagas e mapa."
    return layout("Editais de transferência de Medicina abertos agora | Transfermed", desc, corpo, raiz, "editais", "editais/",
                  estruturados=(trilha_ld(("Início", ""), ("Editais abertos", "editais/")),))


# ---------------------------------------------------------------- radar da home
# As regras abaixo têm cópia fiel em app.js (radarPontos), que as recalcula no dia da visita: mudar aqui é mudar lá.
FILTROS_RADAR = (("abertos", "Abertos agora"), ("semana", "Encerram esta semana"),
                 ("exterior", "Aceitam quem vem do exterior"), ("publicas", "Públicas"))


def estado_edital(ed, hoje):
    """aberto | em breve | contínuo | encerrado (o edital "até completar as vagas" está aberto, sem data final)."""
    if ate_vagas(ed):
        return "aberto"
    if ed.get("fluxo_continuo"):
        return "contínuo"
    fim, ini = prazo_seguro(ed), ed.get("inscricao_inicio")
    if not fim or hoje > fim:
        return "encerrado"
    return "em breve" if ini and hoje < ini else "aberto"


def ponto_radar(f, eds, hoje):
    """Situação de uma faculdade no radar: aberto, encerra (até 7 dias), breve (edital com inscrição futura ou mês em
    que os editais anteriores abriram) ou sem."""
    H = date.fromisoformat(hoje)
    abertos = [x for x in eds if estado_edital(x, hoje) == "aberto"]
    breve = [x for x in eds if estado_edital(x, hoje) == "em breve"]
    ed, dias = None, None
    if abertos:
        com_fim = sorted((x for x in abertos if not ate_vagas(x)), key=prazo_seguro)
        ed = com_fim[0] if com_fim else abertos[0]
        if com_fim:
            dias = (date.fromisoformat(prazo_seguro(ed)) - H).days
            st = "encerra" if dias <= 7 else "aberto"
            quando = "encerra hoje" if dias <= 0 else f"encerra em {dias} {'dia' if dias == 1 else 'dias'}"
        else:
            st, quando = "aberto", "abertas até completar as vagas"
    elif breve:
        ed = min(breve, key=lambda x: x["inscricao_inicio"])
        st, quando = "breve", f"inscrições abrem em {fmt(ed['inscricao_inicio'])}"
    elif any(x.get("fluxo_continuo") is True for x in eds):
        ed = next(x for x in eds if x.get("fluxo_continuo") is True)
        st, quando = "sem", "pedidos o ano todo, sem edital"
    else:
        meses = f.get("meses") or []
        prox = H.month % 12 + 1
        mes = prox if prox in meses else H.month if H.month in meses else None
        st, quando = ("breve", f"costuma abrir em {MESES[mes - 1]}") if mes else ("sem", "sem edital aberto agora")
    req = ((ed or {}).get("quem_pode") or "").split(";")[0].strip()
    if len(req) > 110:
        req = req[:107].rsplit(" ", 1)[0] + "…"
    x, y = proj(f["lat"], f["lon"])
    return {"fid": f["id"], "sigla": f["sigla"], "nome": f["nome"], "cidade": f["cidade"], "uf": f["uf"], "x": x, "y": y,
            "st": st, "dias": dias, "quando": quando, "req": req, "slug": slug_edital(ed) if ed else None,
            "n": len(abertos), "ext": any(x.get("aceita_curso_exterior") is True for x in abertos),
            "pub": (f.get("tipo") or "").startswith("pública")}


def pontos_radar(F, E, hoje):
    por_fac = {}
    for x in E:
        por_fac.setdefault(x["faculdade_id"], []).append(x)
    return [ponto_radar(f, por_fac.get(fid, []), hoje) for fid, f in F.items()]


def no_filtro(p, filtro):
    aberta = p["st"] in ("aberto", "encerra")
    return {"abertos": aberta or p["st"] == "breve", "semana": p["st"] == "encerra",
            "exterior": aberta and p["ext"], "publicas": p["pub"]}[filtro]


def resumo_radar(pontos, filtro):
    """Linha logo abaixo dos chips: a contagem é sempre de faculdades (o mapa mostra faculdades)."""
    dentro = [p for p in pontos if no_filtro(p, filtro)]
    n = sum(p["st"] in ("aberto", "encerra") for p in dentro)
    plural = lambda k, um, varios: f"{k} {um if k == 1 else varios}"
    if filtro == "abertos":
        nb = sum(p["st"] == "breve" for p in dentro)
        return plural(n, "faculdade com inscrição aberta", "faculdades com inscrição aberta") + (f" · {nb} {'abre' if nb == 1 else 'abrem'} em breve" if nb else "")
    if filtro == "semana":
        return plural(n, "faculdade com inscrição encerrando em até 7 dias", "faculdades com inscrição encerrando em até 7 dias")
    if filtro == "exterior":
        return plural(n, "faculdade com inscrição aberta aceita", "faculdades com inscrição aberta aceitam") + " quem vem do exterior"
    return plural(len(dentro), "faculdade pública", "faculdades públicas") + f" · {n} com inscrição aberta"


def _lista_ufs(ufs):
    return ", ".join(ufs[:-1]) + f" e {ufs[-1]}" if len(ufs) > 1 else "".join(ufs)


def linha_cobertura(ufs):
    """Sem afirmar o que não foi verificado: "Cobertura completa" só para os de COMPLETOS; os prioritários ainda em
    andamento aparecem como "Em aprofundamento"; os demais, "Também monitoramos". Muda sozinha quando um estado entra."""
    ufs = sorted(set(ufs), key=ordem_uf)
    completos = [u for u in ufs if u in COMPLETOS]
    andamento = [u for u in PRIORITARIOS if u not in completos]
    outros = [u for u in ufs if u not in PRIORITARIOS]
    partes = []
    if completos:
        partes.append(f"Cobertura completa: {_lista_ufs(completos)}.")
    if andamento:
        partes.append(f"Em aprofundamento: {_lista_ufs(andamento)}.")
    if outros:
        partes.append(f"Também monitoramos: {_lista_ufs(outros)}.")
    return " ".join(partes)


def feixe_radar(raio=150, fatias=16, abertura=64):
    """Feixe da varredura: fatias finas com opacidade caindo atrás da borda (SVG não tem gradiente cônico)."""
    import math
    partes = []
    passo = abertura / fatias
    for i in range(fatias):
        a1, a2 = math.radians(-i * passo), math.radians(-(i + 1) * passo - 0.4)
        op = 0.42 * (1 - i / fatias) ** 1.6
        partes.append(f'<path d="M0 0L{raio * math.cos(a1):.1f} {raio * math.sin(a1):.1f}A{raio} {raio} 0 0 0 '
                      f'{raio * math.cos(a2):.1f} {raio * math.sin(a2):.1f}Z" fill-opacity="{op:.3f}"/>')
    return "".join(partes) + f'<path class="borda" d="M0 0L{raio} 0"/>'


def oculto_estado(n, nome):
    """Complemento para leitor de tela: o nome do botão começa pelo texto visível ("BA · 7")."""
    return f'<span class="oculto"> {"faculdade" if n == 1 else "faculdades"} com inscrição aberta ({e(nome)})</span>'


def radar_home(F, E, hoje, hora, pontos):
    cx, cy = proj(*CENTRO_RADAR)
    estados = []
    cobertos = [uf for uf, _ in vistas_estados(F)]
    for uf, vista in vistas_estados(F):
        if PROXIMO_UF and PROXIMO_UF not in cobertos and ordem_uf(PROXIMO_UF) < ordem_uf(uf):
            estados.append(f'<span class="em-breve">{PROXIMO_UF} · em breve</span>')
            cobertos.append(PROXIMO_UF)  # marcador: já posto
        n = sum(1 for p in pontos if p["uf"] == uf and no_filtro(p, "abertos") and p["st"] in ("aberto", "encerra"))
        estados.append(f'<button type="button" data-uf="{uf}" data-nome="{e(NOMES_UF.get(uf, uf))}" data-vista="{vista}" aria-pressed="false">'
                       f'{uf} · <b>{n}</b>{oculto_estado(n, NOMES_UF.get(uf, uf))}</button>')
    if PROXIMO_UF and PROXIMO_UF not in cobertos:
        estados.append(f'<span class="em-breve">{PROXIMO_UF} · em breve</span>')
    cobertos = [uf for uf, _ in vistas_estados(F)]
    chips = "".join(f'<button type="button" class="chip" data-filtro="{k}" aria-pressed="{str(k == "abertos").lower()}">{e(nome)}</button>'
                    for k, nome in FILTROS_RADAR)
    estaticos = "".join(f'<circle class="pe {p["st"]}" cx="{p["x"]:.1f}" cy="{p["y"]:.1f}" r="{3.2 if p["st"] != "sem" else 1.6}"/>'
                        for p in sorted(pontos, key=lambda p: p["st"] != "sem"))
    return f"""<figure class="r3" id="radar3" aria-labelledby="r3-resumo">
    <div class="r3-topo"><span class="ao-vivo" id="r3-vivo"><i aria-hidden="true"></i><b>Ao vivo</b> · <span>atualizado hoje às {hora}</span></span>
      <button type="button" class="link-botao" id="r3-completo" hidden>Ver o mapa completo</button></div>
    <div class="chips" role="group" aria-label="Filtrar o mapa e a lista">{chips}</div>
    <p class="r3-resumo" id="r3-resumo" aria-live="polite">{resumo_radar(pontos, "abertos")}</p>
    <div class="r3-mapa">
      <svg viewBox="{VISTA_BRASIL}" class="r3-svg" role="group" aria-label="Mapa: {e(resumo_radar(pontos, "abertos"))}. A lista completa está logo abaixo." preserveAspectRatio="xMidYMid meet">
        <use href="assets/brasil.svg#br" class="br" x="0" y="0" width="400" height="400" aria-hidden="true"/>
        <g class="r3-aneis" aria-hidden="true" transform="translate({cx:.1f} {cy:.1f})">
          <circle r="45"/><circle r="90"/><circle r="135"/>
          <g class="r3-feixe">{feixe_radar()}</g>
        </g>
        <g class="r3-fundo" aria-hidden="true"></g>
        <g class="r3-pessoa" aria-hidden="true"></g>
        <g class="r3-pontos" aria-hidden="true">{estaticos}</g>
      </svg>
      <span class="r3-varrendo" aria-hidden="true" hidden></span>
      <div class="r3-cartao" id="r3-cartao" role="dialog" aria-labelledby="r3-cartao-t" hidden></div>
    </div>
    <div class="r3-estados" role="group" aria-label="Ver um estado"><button type="button" data-vista="{VISTA_BRASIL}" aria-pressed="true">Brasil</button>{''.join(estados)}</div>
    <p class="r3-cobertura">{linha_cobertura(cobertos)}</p>
    <p class="r3-legenda" aria-hidden="true"><span><i class="l-aberto"></i>Aberto</span><span><i class="l-encerra"></i>Encerra em até 7 dias</span><span><i class="l-breve"></i>Abre em breve</span><span><i class="l-sem"></i>Sem edital agora</span></p>
  </figure>"""


def lista_radar(pontos):
    """Alternativa completa ao mapa (leitor de tela e quem prefere ler): muda junto com os chips (app.js)."""
    ordem = {"encerra": 0, "aberto": 1, "breve": 2, "sem": 3}
    dentro = sorted((p for p in pontos if no_filtro(p, "abertos")),
                    key=lambda p: (ordem[p["st"]], p["dias"] if p["dias"] is not None else 999, p["sigla"]))
    itens = "".join(f'<li{" hidden" if i >= LIMITE_LISTA_RADAR else ""}><a href="{f"edital/{p['slug']}/" if p["slug"] else f"faculdade/{p['fid']}/"}">'
                    f'<i class="{p["st"]}" aria-hidden="true"></i><span><b>{e(p["sigla"])}</b><small>{e(p["cidade"])}/{p["uf"]}</small></span>'
                    f'<span class="q {p["st"]}">{e(p["quando"])}</span></a></li>' for i, p in enumerate(dentro))
    return dentro, itens


LIMITE_LISTA_RADAR = 8


def carrossel_prazos(pontos):
    """Os 3 prazos mais próximos, um por faculdade."""
    prox = sorted((p for p in pontos if p["st"] in ("aberto", "encerra") and p["dias"] is not None), key=lambda p: (p["dias"], p["sigla"]))[:3]
    if not prox:
        return ""
    itens = "".join(f'<li class="item{" ativo" if i == 0 else ""}"><b>{e(p["sigla"])}</b> {e(p["cidade"])}/{p["uf"]} · {e(p["quando"])} · '
                    f'<a href="edital/{p["slug"]}/">Ver edital</a></li>' for i, p in enumerate(prox))
    return f"""<section class="carrossel" id="prazos" aria-roledescription="carrossel" aria-label="Prazos mais próximos">
      <p class="rot"><span class="pulso" aria-hidden="true"></span>Prazo mais próximo</p>
      <button type="button" class="car-pausa" aria-label="Pausar" hidden><svg aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M6 4h4v16H6zM14 4h4v16h-4z"/></svg></button>
      <ul class="faixa">{itens}</ul>
    </section>"""


EXECUCAO = PASTA / "data" / "ultima_execucao.json"
RETRATOS_ROBO = PASTA / "data" / "retratos.json"
PROXIMA_LEITURA = "06h17"  # o cron do radar.yml (17 9 * * * UTC = 06:17 em Brasília); tests/test_painel_robo.py confere
CHIPS_ESTADOS = (("SP", "SP"), ("MG", "MG"), ("BA", "BA"), ("RJ", "RJ"), ("PR", "PR"), ("EXTERIOR", "Exterior"))


def _lido(caminho):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _quando_brasilia(utc):
    """"2026-11-13T02:17:00Z" → (dia em Brasília "2026-11-12", "23:17" em Brasília). Texto fora do formato: (None, None)."""
    try:
        dt = datetime.strptime(utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None, None
    local = dt.astimezone(tempo.BRASILIA)
    return local.date().isoformat(), local.strftime("%H:%M")


def eventos_do_robo(F, hoje, execucao=None, retratos=None, detalhes=None):
    """Painel "O robô hoje" da home: SÓ o que a rodada de hoje registrou, com a hora real dela (o monitor lê as páginas e os
    PDFs; o radar acha editais novos e retificações). Devolve (linhas [(hora, html)], teve_mudanca, ha_lista); sem rodada hoje, ([], False, False):
    o painel não aparece (nada de dado de ontem como se fosse de hoje). `detalhes` = {url da retificação: "Taxa R$ 400 → R$ 250"} (mesmo cartão da ficha, Parte D3)."""
    execucao = _lido(EXECUCAO) if execucao is None else execucao
    retratos = _lido(RETRATOS_ROBO) if retratos is None else retratos
    linhas, mudancas = [], []
    dia_m, hora_m = _quando_brasilia(retratos.get("executado_em_utc"))
    if dia_m == hoje:
        paginas = sum(1 for v in (retratos.get("paginas") or {}).values() if v.get("ultimo_ok") == hoje)
        pdfs = sum(1 for v in (retratos.get("pdfs") or {}).values() if v.get("ultimo_ok") == hoje)
        if paginas or pdfs:
            linhas.append((hora_m, f"Leu <b>{paginas}</b> {'página' if paginas == 1 else 'páginas'} de faculdades e <b>{pdfs}</b> {'PDF' if pdfs == 1 else 'PDFs'} de edital"))
    dia_r, hora_r = _quando_brasilia(execucao.get("executado_em_utc"))
    radar_hoje = dia_r == hoje
    if radar_hoje:
        for chave, rotulo in (("retificacoes", "retificação publicada"), ("novos", "edital novo, em conferência"), ("atualizados", "edital atualizado")):
            for item in execucao.get(chave) or []:
                nome, _, url = str(item).partition(": http")
                extra = (detalhes or {}).get("http" + url.strip()) if chave == "retificacoes" and url.strip() else None
                mudancas.append((hora_r, f"{e(nome.strip())}: <mark>{rotulo}</mark>" + (f" · {e(extra)}" if extra else "")))
        if not mudancas:
            linhas.append((hora_r, "Procurou editais novos e retificações nas páginas das faculdades"))
    if not linhas and not mudancas:
        return [], False, False
    vaga = 4 - len(linhas)
    if len(mudancas) > vaga:
        mudancas = mudancas[:vaga - 1] + [(hora_r, f"<b>{len(mudancas) - vaga + 1}</b> outras mudanças")]
    linhas += mudancas
    tem_novos = bool(radar_hoje and execucao.get("novos"))
    return linhas, bool(mudancas), tem_novos


def detalhes_das_retificacoes(E):
    """{url de cada retificação: "Taxa R$ 400 → R$ 250"} dos editais com cartão de retificação que tem antes e depois (alimenta "O robô hoje")."""
    out = {}
    for ed in E:
        r = retificacao_do_edital(ed)
        if r and r["mudancas"]:
            txt = "; ".join(f'{m["rotulo"]} {m["antes"]} → {m["depois"]}' for m in r["mudancas"])
            for u in dict.fromkeys(ed.get("retificacoes") or []):
                out.setdefault(u, txt)
    return out


def painel_robo(F, hoje, raiz="", execucao=None, retratos=None, detalhes=None):
    """Painel escuro "O robô hoje". O HTML é gerado uma vez por dia; `data-dia` e `data-rodada` (UTC) deixam o app.js (painelRobo) trocar o
    texto no dia de Brasília de quem lê: depois da meia-noite vira "Última rodada · dd/mm" e a próxima leitura passa a ser "hoje às 06h17"."""
    linhas, mudou, ha_lista = eventos_do_robo(F, hoje, execucao, retratos, detalhes)
    if not linhas:
        return ""
    execucao = _lido(EXECUCAO) if execucao is None else execucao
    retratos = _lido(RETRATOS_ROBO) if retratos is None else retratos
    rodadas = [r for r in (retratos.get("executado_em_utc"), execucao.get("executado_em_utc")) if _quando_brasilia(r)[0] == hoje]
    rodada = max(rodadas) if rodadas else ""
    itens = "".join(f'<li><time>{h}</time><span>{t}</span></li>' for h, t in linhas)
    quando = '<span data-robo-quando>hoje</span>'
    prox = f'próxima leitura <span data-robo-prox>amanhã</span> às {PROXIMA_LEITURA}'
    rodape = "P" + prox[1:] if mudou else f"Nenhuma mudança nos editais {quando} · {prox}"
    if ha_lista:
        rodape += f' · <a href="{raiz}editais/#detectados">ver tudo o que mudou</a>'
    return (f'<section class="painel-robo" aria-labelledby="t-robo" data-dia="{hoje}" data-rodada="{rodada}" data-proxima="{PROXIMA_LEITURA}">'
            f'<h2 id="t-robo"><i aria-hidden="true"></i><span data-robo-titulo>O robô hoje · ao vivo</span></h2>'
            f'<ul>{itens}</ul><p class="rodape-robo">{rodape}</p></section>')


def fato_do_dia(F, hoje, execucao=None, retratos=None):
    """Faixa "Hoje o robô viu:" do radar pessoal: UM fato real da rodada do dia, com link. Prioridade: retificação, edital atualizado, edital novo.
    Sem mudança: "leu N páginas de faculdades. Nenhuma mudança nos editais." (N do monitor); sem rodada hoje: só a hora da próxima leitura.
    Devolve (html, dia_da_rodada ou "")."""
    execucao = _lido(EXECUCAO) if execucao is None else execucao
    retratos = _lido(RETRATOS_ROBO) if retratos is None else retratos
    dia_r, _ = _quando_brasilia(execucao.get("executado_em_utc"))
    if dia_r == hoje:
        for chave, rotulo in (("retificacoes", "retificação publicada"), ("atualizados", "edital atualizado"), ("novos", "edital novo, em conferência")):
            for item in execucao.get(chave) or []:
                nome, _, url = str(item).partition(": http")
                nome = nome.strip()
                if not nome:
                    continue
                ver = f' <a href="http{e(url.strip())}" target="_blank" rel="noopener">ver o edital<span class="oculto"> (abre em nova aba)</span></a>' if url.strip() else ""
                return f'<span class="rp-hj">Hoje</span> o robô viu: <b>{e(nome)}</b>, {rotulo}.{ver}', dia_r
    dia_m, _ = _quando_brasilia(retratos.get("executado_em_utc"))
    if dia_m == hoje:
        paginas = sum(1 for v in (retratos.get("paginas") or {}).values() if v.get("ultimo_ok") == hoje)
        if paginas:
            return (f'<span class="rp-hj">Hoje</span> o robô leu <b>{paginas}</b> {"página" if paginas == 1 else "páginas"} de faculdades. '
                    f'Nenhuma mudança nos editais.'), dia_m
    return f"O robô lê as páginas das faculdades todo dia, às {PROXIMA_LEITURA}.", ""


PERIODOS_RADAR = 12
KM_MIN, KM_MAX, KM_PASSO, KM_PADRAO = 100, 1600, 50, 400  # KM_MAX = "qualquer distância"


def radar_pessoal(F, hoje):
    """Radar pessoal da home (Parte C): uma pergunta ("De onde você quer sair?"), período em pílulas e distância num controle deslizante.
    Sem JavaScript o bloco inteiro fica escondido e valem os atalhos e a lista de editais abertos logo abaixo; o app.js (radarPessoal) liga tudo.
    A conta é a MESMA do diagnóstico (avaliar), sobre os dados já publicados."""
    fato, dia = fato_do_dia(F, hoje)
    pilulas = "".join(f'<label class="rp-pilula"><input type="radio" name="rp-periodo" value="{n}"><span>{n}º</span></label>'
                      for n in range(1, PERIODOS_RADAR + 1))
    return f"""<div class="rp" id="rp">
    <div class="rp-cima">
      <p class="rp-selo"><i aria-hidden="true"></i>Radar ao vivo · <b>{len(F)}</b> faculdades</p>
      <label class="rp-pergunta" for="rp-cidade">De onde você quer sair?</label>
      <div class="rp-busca">
        <input id="rp-cidade" type="text" role="combobox" aria-expanded="false" aria-controls="rp-lista" aria-autocomplete="list" aria-describedby="rp-dica"
          autocomplete="off" autocapitalize="off" spellcheck="false" enterkeyhint="go" placeholder="Digite a sua cidade" disabled>
        <ul id="rp-lista" class="rp-lista" role="listbox" aria-label="Cidades sugeridas" hidden></ul>
      </div>
      <p class="rp-dica" id="rp-dica" role="status" aria-live="polite">Escolha a cidade na lista. Nada é enviado: o cálculo roda no seu aparelho.</p>
      <noscript><p class="rp-sem-js">O radar pessoal precisa de JavaScript. Use os atalhos abaixo ou a <a href="editais/">lista dos editais abertos</a>.</p></noscript>
      <div class="rp-cont" id="rp-cont" hidden>
        <p class="rp-onde"><span id="rp-onde"></span> <button type="button" class="link-botao" id="rp-trocar">Trocar cidade</button></p>
        <p class="rp-novos" id="rp-novos" hidden></p>
        <div class="rp-num"><b id="rp-n" aria-hidden="true">0</b><span id="rp-n-txt" role="status" aria-live="polite"></span></div>
        <p class="rp-primeira" id="rp-primeira"></p>
        <fieldset class="rp-periodo"><legend>Em que período você está?</legend><div class="rp-pilulas">{pilulas}</div></fieldset>
        <div class="rp-dist">
          <div class="rp-dist-topo"><label for="rp-km">Até onde você vai?</label><output id="rp-km-v" for="rp-km"></output></div>
          <input type="range" id="rp-km" min="{KM_MIN}" max="{KM_MAX}" step="{KM_PASSO}" value="{KM_PADRAO}" aria-describedby="rp-km-v">
        </div>
      </div>
    </div>
    <div class="rp-res">
      <div id="rp-res" hidden>
        <ul class="rp-top" id="rp-top"></ul>
        <p class="rp-mais" id="rp-mais-p" hidden><button type="button" class="botao sec" id="rp-mais" aria-expanded="false" aria-controls="rp-todos"></button></p>
        <ul class="rp-top rp-todos" id="rp-todos" hidden></ul>
        <p class="rp-conferir" id="rp-conferir" hidden></p>
        <p class="rp-vazio" id="rp-vazio" hidden>Nenhum edital aberto com esse filtro agora. Aumente a distância ou ative o alerta: avisamos quando abrir.</p>
        <p class="rp-acao"><button type="button" class="botao" id="rp-avise">Me avise quando abrir mais uma assim</button></p>
        <p class="rp-nota">Seu radar fica salvo neste aparelho · sem cadastro · cada dado com a página do PDF</p>
        <p class="rp-ideia"><b>Mudou de ideia?</b> Arraste a distância ou troque o período: o radar recalcula na hora.</p>
      </div>
      <p class="rp-robo" id="rp-robo" data-dia="{dia}">{fato}</p>
    </div>
  </div>
  <script>try{{if(localStorage.getItem("tm_radar")){{document.getElementById("rp").classList.add("salvo");document.documentElement.classList.add("rp-salvo")}}}}catch(e){{}}</script>"""


def cartao_alerta_home(raiz):
    """Cartão de alerta abaixo do hero: estados (chips) + e-mail, na função de sempre (inscrever, mesmo consentimento guardado).
    Os estados vão no perfil ("estados": ["SP", "EXTERIOR"]); sem chip marcado, avisa de todos."""
    chips = "".join(f'<label class="chip-estado"><input type="checkbox" name="estado" value="{v}"><span>{r}</span></label>' for v, r in CHIPS_ESTADOS)
    n = ISCA["total"]
    pdf = (f'<a href="{raiz}{isca_mod.ARQUIVO}" data-medir="isca">checklist em PDF</a>' if n else "checklist em PDF")
    return f"""<section id="alerta" class="cartao-alerta-home" aria-labelledby="t-alerta-home">
    <h2 id="t-alerta-home">Saiba no dia em que o próximo edital abrir</h2>
    <p class="sub">Escolha os estados que você aceita. Sem escolher, avisamos de todos.</p>
    <form id="form-alerta" class="form-alerta" novalidate data-contexto="inicio" data-perfil-base='{{"curso": "medicina"}}'>
      <fieldset class="chips-estados"><legend class="oculto">Estados de interesse</legend>{chips}</fieldset>
      {campos_email_consentimento(raiz, "Ativar alerta grátis")}
    </form>
    <p class="garantia">Grátis · sem spam · {pdf} na hora</p>
    <div id="alerta-passo2" class="alerta-passo2" hidden></div>
  </section>"""


def pagina_inicio(F, E, gerado, hoje, novos=(), hora="06:00"):
    pontos = pontos_radar(F, E, hoje)
    abertos = [x for x in E if estado_edital(x, hoje) == "aberto"]
    fac_abertas = len({x["faculdade_id"] for x in abertos})
    ext = [x for x in abertos if x.get("aceita_curso_exterior") is True]
    dias = [p["dias"] for p in pontos if p["st"] in ("aberto", "encerra") and p["dias"] is not None]
    if abertos:
        frase_br = "Tem vaga aberta pra você agora. Quer ver onde?"
        prox = min(dias) if dias else None
        vivo_br = f"{len(abertos)} {'edital aberto' if len(abertos) == 1 else 'editais abertos'} em {fac_abertas} {'faculdade' if fac_abertas == 1 else 'faculdades'}" \
                  + ("" if prox is None else " · o próximo encerra hoje" if prox <= 0 else f" · o próximo encerra em {prox} {'dia' if prox == 1 else 'dias'}")
    else:
        frase_br, vivo_br = "Veja quando abre o próximo edital pra você.", "nenhum edital aberto hoje"
    vivo_ex = f"{len(ext)} {'edital aberto aceita' if len(ext) == 1 else 'editais abertos aceitam'} quem vem do exterior"
    seta = ('<svg class="seta" aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>')
    dentro, itens = lista_radar(pontos)
    n_lista = len(dentro)
    corpo = f"""
<section class="heroi v3" aria-labelledby="t-inicio"><div class="wrap v3-grid">
  <div class="v3-topo">
    <span class="selo">Grátis · sem cadastro · dados do edital oficial</span>
    <h1 id="t-inicio">Descubra em 1 minuto onde você pode <span class="destaque">transferir Medicina</span>.</h1>
    <p class="lead">Lemos cada edital pra você não perder a vaga.</p>
  </div>
  {radar_pessoal(F, hoje)}
  {radar_home(F, E, hoje, hora, pontos)}
  <div class="v3-acao">
    <p class="pergunta" id="t-pergunta">Prefere outro caminho?</p>
    <div class="quadros" role="group" aria-labelledby="t-pergunta">
      <a class="quadro" href="diagnostico/?origem=brasil" data-origem="brasil" data-medir="porta_brasil">{seta}<b>Estudo Medicina no Brasil</b>
        <span class="frase" data-frase-br>{frase_br}</span><span class="vivo"><i aria-hidden="true"></i><span data-vivo-br>{vivo_br}</span></span></a>
      <a class="quadro" href="exterior/" data-origem="exterior" data-medir="porta_exterior">{seta}<b>Estudo Medicina fora do Brasil</b>
        <span class="frase">Dá pra voltar. Veja quem aceita você.</span><span class="vivo"><i aria-hidden="true"></i><span data-vivo-ex>{vivo_ex}</span></span></a>
    </div>
    {carrossel_prazos(pontos)}
    <p class="ja-sabe">Já sabe para qual faculdade quer ir? <button type="button" class="link-botao" data-abrir-busca>Buscar pelo nome</button></p>
  </div>
</div></section>
<div class="wrap blocos-vivos">
  {painel_robo(F, hoje, detalhes=detalhes_das_retificacoes(E))}
  {cartao_alerta_home("./")}
</div>
<div class="wrap">
  {bloco_numeros(F, E, gerado, hoje)}
  <section aria-labelledby="t-lista" class="lista-radar">
    <div class="secao-topo"><h2 id="t-lista">{resumo_radar(pontos, "abertos")}</h2><a href="diagnostico/">Ver só os que servem para mim →</a></div>
    <ul class="lista3" id="lista3">{itens}</ul>
    <p class="acoes">{f'<button type="button" class="botao sec" id="lista3-mais">Mostrar todas as {n_lista} faculdades</button>' if n_lista > LIMITE_LISTA_RADAR else ''}
      <a class="botao sec" href="editais/">Ver os {len(abertos)} editais abertos</a></p>
  </section>
  <section aria-labelledby="t-como" class="como">
    <h2 id="t-como">Como funciona</h2>
    <ol class="passos passos-grade">
      <li><strong>Diga de onde você sai</strong><span>A cidade, o período e até onde aceita ir.</span></li>
      <li><strong>O radar confere as regras no PDF oficial</strong><span>De cada edital aberto, com a página de cada dado.</span></li>
      <li><strong>Veja onde se encaixa e ative o alerta</strong><span>E receba aviso quando abrir um novo.</span></li>
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
                    {"@type": "Organization", "name": "Transfermed", "url": f"{SITE_URL}/", "logo": f"{SITE_URL}/{MARCA}logo-512-v3.png"},
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
  <aside id="pro-espera" class="pro-espera" hidden><p>Quer lembretes de cada etapa (prova, resultado, matrícula) e a previsão de quando o edital costuma abrir? Isso seria um plano futuro: ainda não existe e nada é cobrado agora. Estamos só medindo o interesse.</p>
  <button type="button" class="link-botao" id="pro-interesse">Tenho interesse</button></aside>
</div>"""
    corpo = corpo.replace("{{ALERTA}}", bloco_alerta("../", "Receba um aviso quando abrir edital para você",
                                                     "Só o e-mail. Usamos o perfil acima para escolher os editais. Sem senha, sem cadastro longo.",
                                                     "diagnostico", com_perfil=True, oculto=True))
    return layout("Diagnóstico: onde posso transferir Medicina | Transfermed", "Responda 4 etapas curtas e veja os editais de transferência de Medicina abertos para o seu perfil, os que abrem em breve e onde você não se encaixa.", corpo, "../", "diagnostico", "diagnostico/", ativo="diagnostico/")


def pagina_do_campo(ed, campo):
    """Primeira página (inteiro) onde o PDF traz o campo: evidencias aceita 2, "1-2" ou "p. 3"; sem número claro, None (nada de chute)."""
    p = (ed.get("evidencias") or {}).get(campo)
    if isinstance(p, int) and not isinstance(p, bool):
        return p if p > 0 else None
    m = re.match(r"^\D{0,3}(\d{1,3})", str(p or ""))
    return int(m.group(1)) if m else None


def evid(ed, campo):
    p = (ed.get("evidencias") or {}).get(campo)
    if p in (None, ""):
        return ""
    return f' <span class="pag">p. {e(p)}</span>' if isinstance(p, int) else f' <span class="pag">{e(p)}</span>'


def pagina_e_item(ed, campo):
    """"p. 2, item 3.3" a partir de `evidencias` (só a primeira página e o item citado; sem número claro, vazio: nada de chute)."""
    n = pagina_do_campo(ed, campo)
    if not n:
        return ""
    m = re.search(r"\(((?:item|itens) [^;)]*)", str((ed.get("evidencias") or {}).get(campo) or ""))
    return f"p. {n}" + (f", {m.group(1).strip()}" if m else "")


# Parte D3 ("O que mudou"): campos que o cartão de retificação compara. (campo no edital, chave em conferir_campos, rótulo, tipo)
CAMPOS_RETIFICADOS = (("taxa_inscricao", "taxa_inscricao", "Taxa", "dinheiro"), ("inscricao_inicio", "inscricao_inicio", "Início das inscrições", "data"),
                      ("inscricao_fim", "inscricao_fim", "Fim das inscrições", "data"), ("data_prova", "data_prova", "Prova", "data"),
                      ("data_resultado", "resultado", "Resultado", "data"), ("data_matricula", "data_matricula", "Matrícula", "data"))


def retificacao_do_edital(ed):
    """Cartão "Retificado em dd/mm" (Parte D3). Só existe quando o histórico (`versoes`) traz um registro com `retificado_em` (a data da retificação,
    lida no documento; a data em que o robô leu não serve). Devolve None ou {"em", "mudancas": [{rotulo, antes, depois, pagina}], "link"}.
    `mudancas` só tem campo com o valor ANTES e o DEPOIS guardados, fora de `conferir_campos`; sem isso fica vazio e o texto é
    "leia a versão nova" (o link é o da retificação mais recente da lista, quando houver)."""
    regs = [v for v in ed.get("versoes") or [] if v.get("retificado_em")]
    if not regs:
        return None
    reg = max(regs, key=lambda v: v["retificado_em"])
    conf = set(campos_conferir(ed))
    tudo = "edital" in conf
    mudancas = []
    for campo, chave, rotulo, tipo in CAMPOS_RETIFICADOS:
        par = (reg.get("mudou") or {}).get(campo)
        if tudo or chave in conf or not (isinstance(par, list) and len(par) == 2) or par[0] in (None, "") or par[1] in (None, ""):
            continue
        fmt_v = (lambda v: dinheiro(v).replace(",00", "")) if tipo == "dinheiro" else fmt
        try:
            mudancas.append({"rotulo": rotulo, "antes": fmt_v(par[0]), "depois": fmt_v(par[1]), "pagina": pagina_e_item(ed, campo)})
        except (TypeError, ValueError, AttributeError):
            continue  # valor de outro tipo: sem antes/depois, cai no texto "leia a versão nova"
    urls = list(dict.fromkeys(ed.get("retificacoes") or []))
    return {"em": reg["retificado_em"], "mudancas": mudancas, "link": urls[-1] if urls else ed.get("url_edital")}


def dados_do_plano(ed, hoje):
    """Campos extras dos dados compactos para o Meu plano e o comparador (Parte D), só de edital que ainda interessa (todos menos os encerrados):
    `conf` = campos em "conferir" (a data ou o valor NÃO entra na linha do tempo, no choque, no .ics nem na comparação: aparece como "conferir");
    `ps` = o prazo é o "prazo seguro" de um edital que se contradiz (vale como data, com o aviso na ficha); `pg` = página de cada dado ("p. 2, item 3.3");
    `crit` = como é a seleção; `ret` = cartão de retificação (mesmo texto da ficha)."""
    if situacao(ed, hoje) == "encerrado":
        return {}
    r = retificacao_do_edital(ed)
    return {"conf": sorted(campos_conferir(ed)),
            "ps": True if (ed.get("prazo_divergente") or datas_contraditorias(ed)) else None,
            "pg": {k: t for k, t in (("fim", pagina_e_item(ed, "inscricao_fim")), ("prova", pagina_e_item(ed, "data_prova")),
                                     ("res", pagina_e_item(ed, "data_resultado")), ("taxa", pagina_e_item(ed, "taxa_inscricao")),
                                     ("ext", pagina_e_item(ed, "aceita_curso_exterior")), ("crit", pagina_e_item(ed, "criterio_selecao"))) if t},
            "crit": ed.get("criterio_selecao"),
            "ret": ({"em": r["em"], "m": [[m["rotulo"], m["antes"], m["depois"], m["pagina"]] for m in r["mudancas"]], "link": r["link"]} if r else None)}


def cartao_retificacao(ed, fac):
    """HTML do cartão de retificação da ficha ("" quando o edital não tem retificação registrada)."""
    r = retificacao_do_edital(ed)
    if not r:
        return ""
    dia = fmt(r["em"])[:5]
    if r["mudancas"]:
        def linha(m):
            pag = f' <span class="pag">{e(m["pagina"])}</span>' if m["pagina"] else ""
            return (f'<div class="ret-linha"><dt>{e(m["rotulo"])}</dt><dd><s>{e(m["antes"])}</s> <span aria-hidden="true">→</span>'
                    f'<span class="oculto"> agora </span> <b>{e(m["depois"])}</b>{pag}</dd></div>')
        linhas = "".join(linha(m) for m in r["mudancas"])
        corpo = f'<dl class="ret-lista">{linhas}</dl><p class="ret-fonte">Antes e depois guardados pelo robô; a página é a do PDF onde o dado novo está.</p>'
    else:
        corpo = (f'<p class="ret-fonte">O que mudou não está guardado com antes e depois. <a href="{e(r["link"])}" target="_blank" rel="noopener">Leia a versão nova'
                 f'<span class="oculto"> (abre em nova aba)</span></a>.</p>')
    return (f'<section class="cartao-ret" aria-labelledby="t-ret"><span class="ret-selo">Retificado em {dia}</span>'
            f'<h2 id="t-ret">O que mudou no edital da {e(fac["sigla"])}</h2>{corpo}</section>')


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


def linha_do_tempo(ed, hoje, contador=True):
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
    cont = ""
    c = contador_prazo(ed.get("inscricao_inicio"), ed.get("inscricao_fim"), hoje) if contador and situacao(ed, hoje) in ("aberto", "em breve") else None
    if c:
        cont = (f'<div class="contador {c[2]}" data-inicio="{ed.get("inscricao_inicio") or ""}" data-fim="{ed.get("inscricao_fim") or ""}">'
                    f'<b>{c[0]}</b><span>{c[1]}</span></div>')
    return f'<div class="tempo">{cont}<ol class="linha" aria-label="Linha do tempo">{"".join(itens)}</ol></div>'


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


# ---------------------------------------------------------------- Raio-X da concorrência (no ar e ligado por padrão; RAIO_X=0 desliga)

RAIO_X_ATIVO = funcoes.ligada("RAIO_X")
GRANDEZAS_TEXTO = {
    "vagas_do_edital": "vagas do edital", "vagas_somadas_por_periodo": "vagas somadas por período", "vagas_remanescentes": "vagas remanescentes",
    "candidatos_inscritos": "candidatos inscritos", "candidatos_na_relacao_oficial": "candidatos na relação oficial",
    "classificados_dentro_das_vagas": "classificados dentro das vagas", "convocados_para_proxima_etapa": "convocados para a próxima etapa",
    "deferidos_para_matricula": "deferidos para matrícula", "classificados_somando_chamadas": "classificados (soma das chamadas)",
    "classificados_somando_campi": "classificados (soma dos campi)", "linhas_da_lista_de_aprovados": "linhas da lista de aprovados",
}
ROTULO_NUMERO = {"vagas_ofertadas": "Vagas", "inscritos": "Inscritos", "aprovados": "Aprovados ou classificados"}
SEM_RESULTADO = {  # só motivos que continuam verdadeiros com o tempo; "ainda não divulgado" e "bloqueado" não aparecem
    "individual_por_email": "Resultado não publicado: a faculdade avisa cada candidato por e-mail.",
    "sem_lista_publica_encontrada": "Resultado não publicado no site da faculdade.",
}


def _json_publico(nome):
    try:
        return json.loads((PASTA / "data" / nome).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def pagina_texto(pagina):
    """"3" -> "página 3"; "1-2" -> "páginas 1 e 2"; "site" -> "no site da faculdade"."""
    if pagina == "site":
        return "no site da faculdade"
    if "-" in pagina:
        a, b = pagina.split("-")
        return f"páginas {e(a)} e {e(b)}" if int(b) == int(a) + 1 else f"páginas {e(a)} a {e(b)}"
    return "página " + e(pagina)


def numero_raio_x(v):
    """Um número do Raio-X com a sua própria página e o link do documento onde ele está. Sem fonte_url e página próprias, não aparece."""
    if not v.get("fonte_url") or not v.get("pagina"):
        return None
    return (f'{v["valor"]} <span class="sub">({pagina_texto(v["pagina"])} · '
            f'<a href="{e(v["fonte_url"])}" target="_blank" rel="noopener">ver fonte<span class="oculto"> (abre em nova aba)</span></a>)</span>')


def bloco_raio_x(ed, hoje, resultados=None, situacoes=None):
    """Raio-X da concorrência de uma seleção ENCERRADA: só o que a faculdade divulgou (vagas, inscritos, classificados, aprovados), cada número
    com o nome exato da grandeza, a página da fonte e o link. Nunca "chance". Sem dado: só diz "resultado não publicado" quando o motivo
    foi confirmado. Ligado por padrão (funcoes.py); RAIO_X=0 desliga."""
    if not RAIO_X_ATIVO or situacao(ed, hoje) != "encerrado":
        return ""
    resultados = resultados if resultados is not None else (_json_publico("resultados.json") or [])
    situacoes = situacoes if situacoes is not None else (_json_publico("situacao_resultados.json") or {})
    r = next((x for x in resultados if x["edital_id"] == ed["id"]), None)
    if r:
        itens = [(k, v) for k, v in r["numeros"].items() if v["grandeza"] in GRANDEZAS_TEXTO and numero_raio_x(v)]
        if itens:
            linhas = "".join(
                f'<div><dt>{e(GRANDEZAS_TEXTO[v["grandeza"]].capitalize())}</dt><dd>{numero_raio_x(v)}</dd></div>' for k, v in itens)
            aviso = ("" if any(k == "inscritos" for k, _ in itens) else
                     "<p class=\"sub\">A faculdade não divulgou quantos candidatos se inscreveram, então estes números não medem a concorrência.</p>")
            lista = " Soma de mais de uma chamada." if r.get("ressalva") == "chamadas_multiplas" else ""
            return (f'<section class="bloco-ficha raio-x" aria-labelledby="t-raiox"><h2 id="t-raiox">Raio-X da concorrência desta seleção</h2>'
                    f'<dl class="resumo">{linhas}</dl>{aviso}<p class="sub">Números divulgados pela própria faculdade, conferidos em {fmt(r["conferido_em"])}. Cada número traz a página e o link do documento onde está.{lista}</p></section>')
    motivo = SEM_RESULTADO.get(situacoes.get(ed["id"]))
    if motivo:
        return (f'<section class="bloco-ficha raio-x" aria-labelledby="t-raiox"><h2 id="t-raiox">Raio-X da concorrência desta seleção</h2>'
                f'<p>{e(motivo)}</p></section>')
    return ""


def pagina_edital(ed, fac, hoje, imagem, distintivo=""):
    """Ficha do edital em 3 blocos: Posso? · Quando · O que preciso. Só dado conferido; o que o edital não traz
    aparece como "não informado", e o que ainda não foi transcrito manda para o PDF (nunca deduzido)."""
    raiz = "../../"
    nome_mod, quem_mod = MODALIDADES.get(ed.get("modalidade"), MODALIDADES["externa"])
    cls, txt = texto_situacao(ed, hoje)
    # fluxo contínuo sem edital: os textos falam da página oficial e da faculdade
    fluxo = bool(ed.get("fluxo_continuo")) and not ate_vagas(ed)
    confira = "confirme com a faculdade" if fluxo else "confira no edital"
    ni = "não informado pela faculdade" if fluxo else "não informado no edital"
    inscr = (f"{fmt(ed.get('inscricao_inicio'))} a {fmt(ed.get('inscricao_fim'))}" if ed.get("inscricao_inicio")
             else (f"até {fmt(ed['inscricao_fim'])}" if ed.get("inscricao_fim") else ("até completar as vagas" if ate_vagas(ed) else "o ano todo" if fluxo else ni)))
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
    modo = modo_lembrete(ed, hoje)
    # a contagem fica no bloco do lembrete; na linha do tempo só quando o bloco não a mostra (ou quando a contagem é da abertura)
    tempo = (linha_do_tempo(ed, hoje, contador=modo not in ("completo", "agenda") or situacao(ed, hoje) == "em breve")
             or f'<p class="sub">Datas: {ni}.</p>')
    # bloco único "Não perca o prazo" (e-mail + agenda) logo depois da linha do tempo; encerrado e fluxo contínuo ficam só com
    # a chamada do fim da página ("avise-me do próximo"), e o prazo a 2 dias ou menos mantém a chamada: o lembrete já não cabe
    lembrete_bloco = bloco_lembrete(raiz, ed, fac, hoje, modo) if modo else ""
    if modo in ("completo", "email"):
        chamada = ""  # o formulário já está no bloco (os ids do formulário são únicos na página)
    else:
        chamada = bloco_alerta(raiz, f"Avise-me quando a {fac['sigla']} abrir o próximo edital",
                               "Um e-mail quando sair edital conferido desta faculdade, com o resumo e os documentos.",
                               "edital_seguir", botao="Avise-me", seguir_fac=fac["id"])
    # avisos de campos que a ficha não mostra numa linha própria (semestre, calendário, edital inteiro) vão no topo
    fora_da_ficha = [a for c, a in avisos(ed).items() if c not in CAMPOS_NA_FICHA]
    caixa_conferir = avisos_do_pdf(ed, fac) + "".join(f'<div class="aviso-caixa"><strong>Atenção:</strong> {e(a)}</div>' for a in fora_da_ficha)
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
  {cartao_retificacao(ed, fac)}
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
    {lembrete_bloco}
    {barra_prazo(ed, fac, hoje, modo)}
  </section>
  <section class="bloco-ficha" aria-labelledby="t-preciso">
    <h2 id="t-preciso"><span class="n-bloco">3</span>O que preciso</h2>
    <dl class="resumo">{preciso}</dl>
    <h3>Documentos</h3>
    {aviso_campo(ed, "documentos")}{check}
    {bloco_checklist(ed)}
  </section>
  {bloco_raio_x(ed, hoje)}
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
                  extra_body=f' data-edital="{ed["id"]}"' + (' data-barra-prazo="1"' if modo in ("completo", "agenda") else ""),
                  estruturados=estruturados)


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
    elif "por script" in p or "javascript" in p or "não reconhece o link" in p or "o robô não lê" in p:
        txt = ("Esta faculdade mostra os editais numa página que o nosso robô não consegue ler sozinho, "
               "então um edital novo pode demorar a aparecer aqui. Confira no site oficial.")
    elif "fora do ar" in p or "não aceitou conexão" in p:
        txt = ("O site desta faculdade estava fora do ar na nossa última consulta, então o robô não acompanha os "
               "editais todo dia. Confira no site oficial.")
    elif "bloqueia" in p or "recusa" in p or "não respondeu" in p:
        txt = ("O site desta faculdade não permite a leitura automática, então o robô não acompanha os editais "
               "todo dia. Confira no site oficial.")
    elif "página nova" in p:
        txt = ("Os editais desta faculdade saem numa página nova a cada semestre, então o próximo pode demorar "
               "a aparecer aqui. Confira no site oficial.")
    elif "pedido direto" in p or "sem edital" in p:
        txt = ("Esta faculdade faz a transferência por pedido direto, sem edital publicado. "
               "Confira as condições no site oficial.")
    elif any(t in p for t in ("não publica edital", "não tem página", "nenhuma página", "não mostra transferência")):
        txt = ("Não encontramos no site oficial um edital de transferência de Medicina desta faculdade. "
               "Confirme com a faculdade se ela aceita transferência.")
    else:
        txt = "Ainda falta descobrir onde esta faculdade publica os editais de transferência. Enquanto isso, confira no site oficial."
    return f'<div class="aviso-caixa">{txt}</div>'


def ordem_historico(ed):
    """Mais novo primeiro: semestre de ingresso, depois fim das inscrições. Antes comparava "2026.1" com
    "2026-06-22" como texto quando faltava a data, e o 2026.1 ficava acima do 2026.2."""
    m = re.match(r"(20\d\d)(?:\.([12]))?", str(ed.get("semestre_ingresso") or ""))
    sem = (int(m.group(1)), int(m.group(2) or 0)) if m else (0, 0)
    return (sem, ed.get("inscricao_fim") or "")


def aberturas_anteriores(eds, hoje):
    """Editais já encerrados, conferidos à mão, cuja data de início das inscrições está confirmada no PDF (campo fora de `conferir_campos`,
    edital sem dúvida geral e com a página registrada). Do mais novo para o mais antigo. Base de "Quando costuma abrir" na ficha."""
    boas = []
    for x in eds:
        conf = x.get("conferir_campos") or {}
        if (publicavel(x) and situacao(x, hoje) == "encerrado" and x.get("inscricao_inicio")
                and "inscricao_inicio" not in conf and "edital" not in conf
                and (x.get("evidencias") or {}).get("inscricao_inicio") not in (None, "")):
            boas.append(x)
    return sorted(boas, key=lambda x: (x["inscricao_inicio"], x["id"]), reverse=True)


def bloco_aberturas(eds, hoje, raiz):
    """"Quando costuma abrir" na ficha da faculdade: só com 2 ou mais editais anteriores confirmados, sem previsão (nenhuma data futura,
    nenhum mês "provável"), com o link da ficha de cada edital antigo e a página do PDF de onde veio a data. Menos de 2: não mostra nada."""
    antigos = aberturas_anteriores(eds, hoje)
    if len(antigos) < 2:
        return ""
    itens = "".join(
        f'<li><a href="{raiz}edital/{slug_edital(x)}/">{e(MODALIDADES.get(x.get("modalidade"), MODALIDADES["externa"])[0])}'
        f'{" · ingresso " + e(x["semestre_ingresso"]) if x.get("semestre_ingresso") else ""}</a>: '
        f'as inscrições abriram em {fmt(x["inscricao_inicio"])}{evid(x, "inscricao_inicio")}</li>' for x in antigos)
    return (f'<h2 id="quando-abre">Quando costuma abrir</h2>\n  <p class="sub">Sem previsão: não dá para saber quando sai o próximo edital. '
            f'Estas são as datas em que as inscrições abriram nos {len(antigos)} editais anteriores que temos desta faculdade, '
            f'cada uma tirada do próprio edital (página indicada).</p>\n  <ul class="aberturas">{itens}</ul>\n  ')


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
  {bloco_aberturas(eds, hoje, raiz)}<h2>Histórico de editais</h2>
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


def faq_estado(uf, facs, vivos, por_id, hoje):
    """Perguntas frequentes da página do estado. Toda resposta vem de números da base (nada digitado à mão, nada deduzido)."""
    abertos = [x for x in vivos if situacao(x, hoje) == "aberto"]
    siglas = list(dict.fromkeys(por_id[x["faculdade_id"]]["sigla"] for x in abertos))
    q = []
    if abertos:
        q.append((f"Quais faculdades de Medicina {em_uf(uf)} têm edital de transferência aberto agora?",
                  f"Hoje, {len(siglas)} {'faculdade tem' if len(siglas) == 1 else 'faculdades têm'} inscrições abertas {em_uf(uf)}: {', '.join(siglas)}. "
                  "A lista é recalculada a cada atualização do radar; confirme o prazo no edital oficial."))
    else:
        q.append((f"Quais faculdades de Medicina {em_uf(uf)} têm edital de transferência aberto agora?",
                  f"Hoje, nenhuma das {len(facs)} faculdades monitoradas {em_uf(uf)} tem inscrições abertas. Ative o aviso para saber quando abrir."))
    meses = {}
    for f in facs:
        for m in f.get("meses") or []:
            meses[m] = meses.get(m, 0) + 1
    if meses:
        top = sorted(meses.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        q.append((f"Quando os editais de transferência de Medicina costumam abrir {em_uf(uf)}?",
                  "Pelo histórico dos editais anteriores, os meses mais frequentes de abertura são "
                  + ", ".join(f"{MESES[m - 1]} ({n} {'faculdade' if n == 1 else 'faculdades'})" for m, n in top)
                  + ". É uma tendência, não uma promessa: cada faculdade decide a cada semestre."))
    ext = [x for x in abertos if x.get("aceita_curso_exterior") is True]
    nao = [x for x in abertos if x.get("aceita_curso_exterior") is False]
    if abertos:
        q.append(("Quem estuda Medicina fora do Brasil pode se inscrever?",
                  f"Entre os {len(abertos)} {'edital aberto' if len(abertos) == 1 else 'editais abertos'} {em_uf(uf)}, "
                  f"{len(ext)} {'diz' if len(ext) == 1 else 'dizem'} que {'aceita' if len(ext) == 1 else 'aceitam'} aluno de faculdade estrangeira e "
                  f"{len(nao)} {'diz' if len(nao) == 1 else 'dizem'} que não {'aceita' if len(nao) == 1 else 'aceitam'}. Os demais não informam. "
                  "Veja o que cada edital exige no guia de quem estuda fora."))
    taxas = [x["taxa_inscricao"] for x in abertos if x.get("taxa_inscricao") is not None and "taxa_inscricao" not in (x.get("conferir_campos") or {})]
    if taxas:
        d = lambda v: ("R$ " + f"{v:.2f}".replace(".", ","))
        q.append((f"Quanto custa a inscrição nos editais abertos {em_uf(uf)}?",
                  f"Nos editais abertos com taxa conferida, a inscrição vai de {d(min(taxas))} a {d(max(taxas))}. O valor vale para o edital; confirme no documento oficial."))
    return q


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
    # números reais da base (nada de e-MEC aqui: só entra quando a conferência por estado estiver feita)
    prazos = sorted((x for x in vivos if situacao(x, hoje) == "aberto" and x.get("inscricao_fim")), key=lambda x: x["inscricao_fim"])[:3]
    h = date.fromisoformat(hoje)
    prox_mes = h.month % 12 + 1
    com_edital = {x["faculdade_id"] for x in vivos}
    breve = [f for f in sorted(facs, key=lambda f: slug(f["cidade"])) if f["id"] not in com_edital
             and (prox_mes in (f.get("meses") or []) or h.month in (f.get("meses") or []))]
    com_ext = [x for x in vivos if x.get("aceita_curso_exterior") is True and situacao(x, hoje) == "aberto"]
    numeros = (f'<div class="numeros tres" role="group" aria-label="Números {e(em_uf(uf))}">'
               f'<div class="numero"><b>{len(facs)}</b><span>{"faculdade monitorada" if len(facs) == 1 else "faculdades monitoradas"}</span></div>'
               f'<div class="numero"><b>{abertos}</b><span>{"edital aberto agora" if abertos == 1 else "editais abertos agora"}</span></div>'
               f'<div class="numero"><b>{len(breve)}</b><span>costumam abrir em breve</span></div></div>')
    proximos = ("<h2>Próximos prazos</h2><ul class=\"lista-regras\">" + "".join(
        f'<li><a href="{raiz}edital/{slug_edital(x)}/">{e(por_id[x["faculdade_id"]]["sigla"])}</a>: inscrições até {fmt(x["inscricao_fim"])}</li>'
        for x in prazos) + "</ul>") if prazos else ""
    exterior = ("<h2>Aceitam quem vem do exterior</h2><p class=\"sub\">Editais abertos agora que aceitam aluno de faculdade estrangeira.</p>"
                f'<div class="grade-cartoes">{"".join(cartao_simples(x, por_id[x["faculdade_id"]], raiz, hoje) for x in com_ext)}</div>'
                f'<p class="sub"><a href="{raiz}exterior/">Guia de quem estuda fora do Brasil</a></p>') if com_ext and uf in PRIORITARIOS else ""
    em_breve = ("<h2>Costumam abrir em breve</h2><p class=\"sub\">Pelo histórico dos editais anteriores (não é data de abertura): "
                "receba o aviso quando sair.</p><ul class=\"lista-regras\">" + "".join(
                    f'<li><a href="{raiz}faculdade/{f["id"]}/#quando-abre">{e(f["sigla"])}</a> ({e(f["cidade"])}): costuma abrir em '
                    f'{MESES[(prox_mes if prox_mes in f["meses"] else h.month) - 1]}</li>' for f in breve) + "</ul>") if breve else ""
    perguntas = faq_estado(uf, facs, vivos, por_id, hoje)
    faq_html = ("<section class=\"faq\"><h2>Perguntas frequentes</h2>" + "".join(
        f"<details><summary>{e(q)}</summary><p>{e(a)}</p></details>" for q, a in perguntas) + "</section>") if perguntas else ""
    corpo = f"""
<div class="wrap estreito">
  <nav class="trilha" aria-label="Você está em"><a href="{raiz}">Início</a> › {e(nome)}</nav>
  <section class="heroi">
    <h1>Transferência de Medicina {e(em_uf(uf))}</h1>
    <p class="lead">{len(facs)} {'escola médica monitorada' if len(facs) == 1 else 'escolas médicas monitoradas'} {e(em_uf(uf))}, com os editais conferidos no PDF oficial. Hoje, {abertos} {'edital está' if abertos == 1 else 'editais estão'} com inscrições abertas.</p>
    <div class="acoes"><a class="botao" href="{raiz}diagnostico/">Descobrir onde posso transferir</a></div>
  </section>
  {numeros}
  <h2>Inscrições abertas ou abrindo {e(em_uf(uf))}</h2>
  <div class="grade-cartoes">{cartoes or '<div class="vazio">Nenhum edital aberto ou abrindo agora neste estado.</div>'}</div>
  {proximos}
  {exterior}
  {em_breve}
  <h2>Todas as faculdades monitoradas {e(em_uf(uf))}</h2>
  <p class="sub">Em ordem de cidade. A situação é recalculada a cada atualização do radar.</p>
  <div class="tabela"><table><thead><tr><th scope="col">Faculdade</th><th scope="col">Cidade</th><th scope="col">Tipo</th><th scope="col">Agora</th></tr></thead><tbody>{linhas}</tbody></table></div>
  {faq_html}
</div>"""
    desc = (f"Editais de transferência de Medicina {em_uf(uf)}: {len(vivos)} com inscrições abertas ou abrindo, prazos e documentos "
            f"conferidos no PDF oficial de {len(facs)} faculdades.")
    estruturados = (trilha_ld(("Início", ""), (nome, f"estado/{uf.lower()}/")),
                    {"@type": "CollectionPage", "name": f"Transferência de Medicina {em_uf(uf)}", "url": f"{SITE_URL}/estado/{uf.lower()}/",
                     "inLanguage": "pt-BR", "description": desc,
                     "mainEntity": {"@type": "ItemList", "numberOfItems": len(facs), "itemListElement": [
                         {"@type": "ListItem", "position": i, "url": f"{SITE_URL}/faculdade/{f['id']}/", "name": f["nome"]}
                         for i, f in enumerate(sorted(facs, key=lambda f: (slug(f["cidade"]), slug(f["nome"]))), 1)]}},
                    *([{"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
                                                          for q, a in perguntas]}] if perguntas else []))
    return layout(f"Transferência de Medicina {em_uf(uf)}: editais abertos e prazos", desc, corpo, raiz, "estado", f"estado/{uf.lower()}/",
                  estruturados=estruturados)


def pagina_exterior(F, E, hoje):
    raiz = "../"
    aceitam = {}
    for x in E:
        if x.get("aceita_curso_exterior") is True or x.get("modalidade") == "exterior":
            aceitam.setdefault(x["faculdade_id"], []).append(x)
    linhas = ""
    for fid, eds in sorted(aceitam.items(), key=lambda kv: (ordem_uf(F[kv[0]]["uf"]), F[kv[0]]["nome"])):
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
  <p class="sub">Aceitar em um edital não garante que o próximo também aceite: confira sempre o edital vigente. Começamos por SP, MG, BA, RJ e PR, os estados que estamos aprofundando.</p>
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
    <li><strong>O que guardamos:</strong> seu e-mail e o perfil do diagnóstico (onde estuda, curso, semestre, cidade aproximada, distância, tipo de faculdade e limite de taxa), além das faculdades que você pediu para seguir e dos prazos que pediu para lembrar. Também guardamos, só como código, como você chegou ao site (por exemplo Google ou Instagram; se veio de outro site, apenas o domínio dele, nunca o endereço completo) e por qual página pediu o alerta, para sabermos o que funciona. Não pedimos nome, CPF, telefone, histórico ou documentos.</li>
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
  <section class="heroi"><h1>Meu plano</h1>
  <p class="lead">Os editais que você salvou com a estrela, com os prazos em ordem, provas no mesmo dia, documentos e comparação. Tudo calculado neste navegador, sem cadastro.</p></section>
  <noscript><div class="aviso-caixa">O plano precisa de JavaScript ligado no navegador.</div></noscript>
  <section id="minha-lista" aria-live="polite"></section>
</div>"""
    return layout("Meu plano | Transfermed", "Editais de transferência de Medicina que você salvou, com os prazos em ordem, provas no mesmo dia e documentos.", corpo, "../",
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
        chips = [("Até completar as vagas" if ate_vagas(ed) else "Pedidos o ano todo", "#E3F2EC", "#0A4338")]
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
    chips = [(f"Inscrições até {fmt(vivo[0]['inscricao_fim'])[:5]}" if vivo[0].get("inscricao_fim")
              else "Até completar as vagas" if ate_vagas(vivo[0]) else "Pedidos o ano todo",
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


DIAS_SEMANA = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")


def fmt_curto(d):
    """AAAA-MM-DD → dd/mm."""
    return "/".join(reversed(d.split("-")[1:])) if d else "?"


def dia_da_semana(d):
    return DIAS_SEMANA[date.fromisoformat(d).weekday()]


ALARMES_LEMBRETE = ((7, "-P6DT15H"), (2, "-P1DT15H"))  # dias antes do fim; gatilho a partir da meia-noite do último dia (= 9h)


def alarmes_lembrete(ed, hoje):
    """Dias antes (7 e 2) cujo alarme ainda está no futuro: a 5 dias do fim, o alarme de 7 dias já passou e não se promete."""
    fim = date.fromisoformat(prazo_seguro(ed))
    return [(n, g) for n, g in ALARMES_LEMBRETE if fim - timedelta(days=n) > date.fromisoformat(hoje)]


def ics_lembrete(ed, fac, hoje):
    """.ics de evento único para o botão "Adicionar à minha agenda": o último dia de inscrição (data segura), com alarmes
    7 e 2 dias antes (às 9h, como no calendário da faculdade) e o link do edital na descrição. DTSTAMP fixo por edital."""
    agora = (ed.get("conferido_em") or ed.get("detectado_em") or "2026-01-01")[:10].replace("-", "") + "T000000Z"

    def t(s):
        return re.sub(r"([,;\\])", r"\\\1", s).replace("\n", "\\n")

    dia = prazo_seguro(ed)
    ficha = f"{SITE_URL}/edital/{slug_edital(ed)}/"
    titulo = f"{nome_agenda(fac)} · último dia de inscrição"
    fim = (date.fromisoformat(dia) + timedelta(days=1)).isoformat()
    descricao = t(f"Ficha no Transfermed: {ficha}\nEdital oficial: {ed['url_edital']}\nConfira sempre o horário limite no edital oficial.")
    linhas = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Transfermed//Radar//PT", "CALSCALE:GREGORIAN",
              "BEGIN:VEVENT", f"UID:{ed['id']}-lembrete@transfermed", f"DTSTAMP:{agora}",
              f"DTSTART;VALUE=DATE:{dia.replace('-', '')}", f"DTEND;VALUE=DATE:{fim.replace('-', '')}",
              f"SUMMARY:{t(titulo)}", f"DESCRIPTION:{descricao}", f"URL:{ficha}", "TRANSP:TRANSPARENT"]
    for _, gatilho in alarmes_lembrete(ed, hoje):  # 7 e 2 dias antes, às 9h
        linhas += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{t(titulo)}", f"TRIGGER:{gatilho}", "END:VALARM"]
    linhas += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(dobrar(l) for l in linhas) + "\r\n"


def modo_lembrete(ed, hoje):
    """Que versão do bloco "Não perca o prazo" a ficha mostra:
    "completo" (e-mail + agenda: prazo conferido, a mais de 2 dias), "agenda" (prazo conferido a 2 dias ou menos: o
    lembrete por e-mail já não cabe), "email" (aberto ou abrindo, sem prazo conferido: só o aviso por e-mail) ou "" (encerrado
    ou fluxo contínuo: a chamada comum do fim da página)."""
    if ed.get("fluxo_continuo") or situacao(ed, hoje) not in ("aberto", "em breve", "desconhecida"):
        return ""
    if fora_dos_emails(ed) or not ed.get("inscricao_fim"):
        return "email"
    dias = (date.fromisoformat(ed["inscricao_fim"]) - date.fromisoformat(hoje)).days
    return "completo" if dias > 2 else ("agenda" if dias >= 0 else "")


def campos_email_consentimento(raiz, botao):
    """Parte comum dos formulários curtos (bloco do lembrete na ficha e cartão da home): e-mail, consentimento NUNCA pré-marcado
    (texto curto, com o texto completo em "O que vou receber"), botão e o campo-armadilha. Os ids são fixos: um formulário por página."""
    return f"""<label class="rotulo" for="email-alerta">Seu e-mail</label>
        <input type="email" id="email-alerta" class="campo-alerta" name="email" autocomplete="email" inputmode="email" required placeholder="seu@email.com">
        <label class="consentimento"><input type="checkbox" id="consentimento" name="consentimento" required> <span>Quero receber os lembretes e alertas de editais por e-mail. Cancelo em um clique.</span></label>
        <details class="consent-ver"><summary>O que vou receber</summary><p>{e(CONSENTIMENTO)} <a href="{raiz}privacidade/">Como usamos seus dados</a>.</p></details>
        <button type="submit" class="botao">{e(botao)}</button>
        <div class="pote" aria-hidden="true"><label>Não preencha <input type="text" name="campo_extra" tabindex="-1" autocomplete="off" data-1p-ignore data-lpignore="true"></label></div>
        <p class="dica" id="alerta-msg" role="status" aria-live="polite"></p>"""


def barra_prazo(ed, fac, hoje, modo):
    """B3: barra fixa no celular ("FACX fecha em N dias · dd/mm · V vagas · Me lembre"): só ficha aberta com prazo conferido. O app.js
    mostra depois do primeiro scroll e esconde quando o bloco do lembrete está na tela; sem pop-up, sem esconder conteúdo (padding no body).
    Vagas só se conferidas e com número."""
    if modo not in ("completo", "agenda"):
        return ""
    fim = ed["inscricao_fim"]
    dias = (date.fromisoformat(fim) - date.fromisoformat(hoje)).days
    total = total_vagas(ed) if "vagas" not in campos_conferir(ed) else None
    quando = "fecha hoje" if dias == 0 else f"fecha em {dias} {'dia' if dias == 1 else 'dias'}"
    detalhe = fmt_curto(fim) + (f" · {total} {'vaga' if total == 1 else 'vagas'}" if total else "")
    return (f'<section class="barra-prazo" id="barra-prazo" hidden aria-label="Lembrete do prazo" data-fim="{fim}" data-sigla="{e(fac["sigla"])}">'
            f'<p><span class="bp-titulo">{e(fac["sigla"])} <span class="bp-quando">{quando}</span></span><span class="bp-detalhe">{detalhe}</span></p>'
            f'<a class="botao" href="#lembrete" data-medir="barra_alerta">Me lembre</a></section>')


ICONE_EMAIL = ('<svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
               'stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="M4 7l8 6 8-6"/></svg>')
ICONE_AGENDA = ('<svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
                'stroke-linecap="round" stroke-linejoin="round"><rect x="3.5" y="5" width="17" height="15" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/></svg>')


def bloco_lembrete(raiz, ed, fac, hoje, modo):
    """Um bloco só para não perder o prazo (substitui o botão do Google Agenda, o "assinar os prazos" e o cartão de e-mail
    do fim da página): contagem, barra do prazo e as duas formas de ser lembrado. A opção de e-mail é o formulário de
    sempre (mesmos ids, mesma função inscrever e o mesmo consentimento guardado); a da agenda baixa um .ics de evento
    único (no Android, o app.js troca pelo link do Google Agenda)."""
    sigla = fac["sigla"]
    fim, ini = ed.get("inscricao_fim"), ed.get("inscricao_inicio")
    com_email, com_agenda = modo in ("completo", "email"), modo in ("completo", "agenda")
    titulo = f"Não perca o prazo da {sigla}"
    cabeca = ""
    if modo != "email":
        dias = (date.fromisoformat(fim) - date.fromisoformat(hoje)).days
        num, txt = ("Hoje", "é o último dia de inscrição") if dias == 0 else (str(dias), f"{'dia' if dias == 1 else 'dias'} para o fim das inscrições")
        cls = "c-alerta" if dias <= 2 else "c-aviso" if dias <= 10 else ""
        barra = ""
        if ini and ini < fim:
            fracao = min(1, max(0, (date.fromisoformat(hoje) - date.fromisoformat(ini)).days / (date.fromisoformat(fim) - date.fromisoformat(ini)).days))
            barra = (f'<progress class="prazo-barra" max="100" value="{fracao * 100:.0f}" aria-hidden="true" data-inicio="{ini}" data-fim="{fim}"></progress>'
                     f'<p class="prazo-rotulos" aria-hidden="true"><span class="rot-hoje">Hoje · {fmt_curto(hoje)}</span><span>Fecha · {fmt_curto(fim)}</span></p>')
        cabeca = (f'<div class="contador {cls}" data-fim="{fim}"><b>{num}</b><span>{txt}</span></div>' + barra)
    pergunta = '<h3 class="lembrete-pergunta">Como você quer ser lembrado?</h3>' if modo == "completo" else ""
    email = ""
    if com_email:
        if modo == "completo":
            sub = ("7 dias e 2 dias antes, com a lista de documentos deste edital. "
                   "Se o prazo mudar, o lembrete acompanha a data nova.")
            contexto, botao, lembrete_id = "edital_lembrete", "Me lembre do prazo", ed["id"]
        else:
            sub = (f"A data final deste edital ainda não foi confirmada no PDF. Avisamos quando ela for confirmada e você também "
                   f"passa a receber os próximos editais da {sigla}.")
            contexto, botao, lembrete_id = "edital_seguir", "Me avise", None
        dados = f' data-contexto="{contexto}" data-seguir-faculdade="{e(fac["id"])}"' + (f' data-lembrete="{e(lembrete_id)}"' if lembrete_id else "")
        arq, n = isca_mod.ARQUIVO, ISCA["total"]
        pdf = (f'<a href="{raiz}{arq}" data-medir="isca">checklist em PDF</a>' if n else "checklist em PDF")
        email = f"""<div id="alerta" class="opcao opcao-email">
      <div class="opcao-topo"><span class="opcao-icone">{ICONE_EMAIL}</span><h3>Por e-mail</h3>{'<span class="selo">Recomendado</span>' if modo == "completo" else ""}</div>
      <p class="sub">{e(sub)}</p>
      <form id="form-alerta" class="form-alerta" novalidate{dados}>
        {campos_email_consentimento(raiz, botao)}
      </form>
      <p class="garantia">Grátis · sem spam · {pdf} na hora</p>
      <div id="alerta-passo2" class="alerta-passo2" hidden></div>
    </div>"""
    agenda = ""
    if com_agenda:
        dia = prazo_seguro(ed)
        pagina = f"{SITE_URL}/edital/{slug_edital(ed)}/"
        alarmes = [n for n, _ in alarmes_lembrete(ed, hoje)]
        txt_alarme = ("alarmes 7 e 2 dias antes" if alarmes == [7, 2] else f"alarme {alarmes[0]} dias antes" if alarmes else "sem alarme: o prazo está muito perto")
        agenda = f"""<div class="opcao opcao-agenda">
      <div class="opcao-topo"><span class="opcao-icone">{ICONE_AGENDA}</span><h3>Na agenda do celular</h3></div>
      <p class="sub">Cria um evento {"com alarme" if alarmes else "no calendário"}. Funciona no iPhone, no Android e no Outlook.</p>
      <p class="previa-evento"><strong>⏰ {e(nome_agenda(fac))} · último dia de inscrição</strong><span>{dia_da_semana(dia)}, {fmt(dia)} · {txt_alarme}</span></p>
      <a class="botao sec" href="lembrete.ics" download data-agenda-google="{e(link_google_agenda(ed, fac, pagina))}" data-medir="lembrete_agenda">Adicionar à minha agenda<span class="oculto"> (baixa um evento de calendário; no Android abre o Google Agenda)</span></a>
    </div>"""
    etapas = ""
    if ed.get("inscricao_fim") or ed.get("data_prova"):
        https, webcal, _ = assinatura_faculdade(fac)
        etapas = (f'<p class="lembrete-etapas">Vai prestar mais de uma etapa? <a href="{e(webcal)}" data-assinar="{e(https)}" '
                  f'data-assinar-nome="{e("Transferência de Medicina: " + nome_agenda(fac))}" aria-expanded="false" data-medir="lembrete_seguir">'
                  f'Seguir todos os prazos da {e(sigla)} na agenda</a>: inscrição, prova e resultado. '
                  f'Se a faculdade mudar uma data, sua agenda muda junto.</p>')
    return f"""<section id="lembrete" class="lembrete" aria-labelledby="t-lembrete">
    <h2 id="t-lembrete">{e(titulo)}</h2>
    {cabeca}
    {pergunta}
    {email}
    {agenda}
    {etapas}
  </section>"""


# ---------------------------------------------------------------- aplicativo (PWA)

def arquivos_app():
    manifesto = {"name": "Transfermed: radar de transferência de Medicina", "short_name": "Transfermed",
                 "description": "Descubra onde você pode transferir Medicina e acompanhe os prazos.",
                 "id": "./", "start_url": "./minha-lista/?origem=app", "scope": "./", "display": "standalone", "background_color": "#F7F5F1",
                 "theme_color": "#0F5C4D", "lang": "pt-BR",
                 # "any" = logo com cantos transparentes; "maskable" = arquivos próprios, fundo sólido #0B1E2C e a logo nos 80% centrais
                 # (qa/gerar_icone_maskable.py): o Android recorta o ícone sem cortar a logo nem mostrar fundo de outra cor
                 "icons": [{"src": MARCA + (f"logo-{t}-v3.png" if p == "any" else f"logo-maskable-{t}-v3.png"), "sizes": f"{t}x{t}", "type": "image/png", "purpose": p}
                           for t in (192, 512) for p in ("any", "maskable")]}
    gravar(DOCS / "manifest.webmanifest", json.dumps(manifesto, ensure_ascii=False, indent=2))
    versao = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    gravar(DOCS / "sw.js", f"""// Transfermed: funciona sem internet com a última versão vista.
// HTML sempre da rede (sem a cópia do navegador); o resto da rede primeiro; cópia local só se a rede cair.
// O service worker novo assume na hora e apaga os caches antigos.
const CACHE = 'tm-{versao}';
const BASE = ['./', 'assets/estilo.css', 'assets/app.js', 'assets/marca/transfermed-logo-v3.svg', 'assets/brasil.svg', 'assets/inter.woff2', 'assets/municipios.json', 'dados.js'];
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
  // HTML e dados (dados.js, editais.json, faculdades.json) sempre revalidados na rede: o app nunca mostra dado mais velho que a última rodada do robô
  const dado = ['dados.js', 'editais.json', 'faculdades.json'].some(n => new URL(req.url).pathname.endsWith('/' + n));
  ev.respondWith(fetch(req, html || dado ? {{cache: 'no-cache'}} : {{}}).then(res => {{
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
    todos = aplicar_quarentena([x for x in json.loads((PASTA / "data" / "editais.json").read_text(encoding="utf-8")) if x.get("faculdade_id") in F])
    E = [x for x in todos if publicavel(x)]
    PDFS_FORA.clear()
    PDFS_FORA.update(pdfs_fora_do_ar())
    # as cópias públicas da base acompanham o site (antes só o radar.py as regravava: gerar à mão deixava a cópia velha)
    for base in ("editais.json", "faculdades.json"):
        shutil.copyfile(PASTA / "data" / base, DOCS / base)
    hoje = tempo.hoje().isoformat()
    hora = tempo.hora_hm()  # horário de Brasília
    por_uf = {}
    for f in F.values():
        por_uf.setdefault(f["uf"], []).append(f)
    ESTADOS[:] = sorted((uf for uf, fs in por_uf.items() if len(fs) >= 5), key=ordem_uf)

    # meses em que cada faculdade costuma abrir: só com 2 ou mais editais anteriores confirmados (mesma regra do bloco "Quando costuma abrir" da ficha,
    # que mostra o link de cada um). Mês escrito à mão na ficha (meses_costuma_abrir) não vale sem esses editais.
    for f in F.values():
        antigos = aberturas_anteriores([x for x in E if x["faculdade_id"] == f["id"]], hoje)
        f["meses"] = sorted({int(x["inscricao_inicio"][5:7]) for x in antigos}) if len(antigos) >= 2 else []

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
            "fluxo": x.get("fluxo_continuo"), "pv": pagina_do_campo(x, "vagas"),
            # Parte D: o que o Meu plano e o comparador precisam (só dos que ainda interessam; encerrado não pesa no dados.js)
            **dados_do_plano(x, hoje)}.items() if v not in (None, "", [], {})})
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
    if funcoes.ligada("AGENDA_UNICA"):  # função agenda do schema.sql testada no Supabase; no ar, ligada por padrão
        cfg["agendaUnica"] = True
    if funcoes.ligada("INDICACAO"):  # "Avise um colega" no resultado do diagnóstico; ligado por padrão, só INDICACAO=0 desliga
        cfg["indicacao"] = True
    if funcoes.ligada("ENVIO_IMEDIATO"):  # token do GitHub no Vault do Supabase: confirmação em ~1 minuto; no ar, ligada por padrão
        cfg["envioImediato"] = True
    gravar(DOCS / "dados.js", "window.TM=" + json.dumps({"gerado_em": hoje, "gerado_hora": hora, "faculdades": facs, "editais": compactos, "novos": novos_js,
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
    gravar(DOCS / "index.html", pagina_inicio(F, E, hoje, hoje, novos, hora=hora))
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
        if modo_lembrete(x, hoje) in ("completo", "agenda"):  # evento único do botão "Adicionar à minha agenda"
            gravar(pasta / "lembrete.ics", ics_lembrete(x, F[x["faculdade_id"]], hoje))
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
