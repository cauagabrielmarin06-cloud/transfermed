"""Testes do gerador do site. Rodar com: python -m unittest discover tests"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gerar_site  # noqa: E402


class Publicacao(unittest.TestCase):
    def test_so_publica_conferido_a_mao(self):
        self.assertTrue(gerar_site.publicavel({"fonte_dados": "manual"}))
        self.assertFalse(gerar_site.publicavel({"fonte_dados": "regras"}))
        self.assertFalse(gerar_site.publicavel({"fonte_dados": "ia"}))


class NovosDetectados(unittest.TestCase):
    HOJE = "2026-10-24"

    def test_novo_do_robo_aparece_sem_dados(self):
        self.assertTrue(gerar_site.novo_detectado({"fonte_dados": "regras", "detectado_em": "2026-10-20",
                                                   "url_edital": "https://x.br/wp-content/uploads/2026/10/edital.pdf"}, self.HOJE))
        self.assertTrue(gerar_site.novo_detectado({"fonte_dados": "regras", "detectado_em": "2026-10-20",
                                                   "semestre_ingresso": "2027.1"}, self.HOJE))

    def test_carga_inicial_nao_vira_novo(self):
        # faculdade recém-incluída: PDFs antigos achados hoje não são "novos"
        for velho in ({"semestre_ingresso": "2026.1"}, {"url_edital": "https://x.br/wp-content/uploads/2025/06/e.pdf"}, {}):
            self.assertFalse(gerar_site.novo_detectado({"fonte_dados": "regras", "detectado_em": "2026-10-20", **velho}, self.HOJE))

    def test_nao_mostra_conferido_antigo_ou_encerrado(self):
        self.assertFalse(gerar_site.novo_detectado({"fonte_dados": "manual", "detectado_em": "2026-10-20"}, self.HOJE))
        self.assertFalse(gerar_site.novo_detectado({"fonte_dados": "regras"}, self.HOJE))  # carga inicial, sem data
        self.assertFalse(gerar_site.novo_detectado({"fonte_dados": "regras", "detectado_em": "2026-06-01"}, self.HOJE))
        self.assertFalse(gerar_site.novo_detectado({"fonte_dados": "regras", "detectado_em": "2026-10-20",
                                                    "inscricao_fim": "2026-10-01"}, self.HOJE))

    def test_robo_ativo_exige_pagina_sem_pendencia(self):
        self.assertTrue(gerar_site.com_robo({"paginas_editais": ["https://x"]}))
        self.assertFalse(gerar_site.com_robo({"paginas_editais": ["https://x"], "pendente": "achar a página certa"}))
        self.assertFalse(gerar_site.com_robo({"paginas_editais": []}))


class Situacao(unittest.TestCase):
    HOJE = "2026-10-24"

    def test_urgencia_real(self):
        self.assertEqual(gerar_site.texto_situacao({"inscricao_fim": "2026-10-25"}, self.HOJE)[0], "alerta")
        self.assertEqual(gerar_site.texto_situacao({"inscricao_fim": "2026-10-29"}, self.HOJE),
                         ("aviso", "Inscrições encerram em 5 dias"))
        self.assertEqual(gerar_site.texto_situacao({"inscricao_fim": "2026-12-03"}, self.HOJE)[0], "ok")
        self.assertEqual(gerar_site.texto_situacao({"inscricao_fim": "2026-07-06"}, self.HOJE)[0], "")


class Calendario(unittest.TestCase):
    def test_linhas_no_maximo_75_bytes(self):
        linha = "DESCRIPTION:Confira sempre o edital oficial: https://exemplo.com.br/" + "a" * 120
        for parte in gerar_site.dobrar(linha).split("\r\n"):
            self.assertLessEqual(len(parte.encode("utf-8")), 75)

    def test_ics_tem_prazos(self):
        ed = {"id": "x1", "url_edital": "https://exemplo/edital.pdf", "inscricao_inicio": "2026-10-01",
              "inscricao_fim": "2026-10-29", "data_prova": "2026-10-31"}
        ics = gerar_site.ics_estatico(ed, {"sigla": "UB"})
        self.assertIn("DTSTART;VALUE=DATE:20261029", ics)
        self.assertIn("TRIGGER:-P3D", ics)
        self.assertEqual(ics.count("BEGIN:VEVENT"), 3)


class Mapa(unittest.TestCase):
    def test_projecao_bate_com_o_javascript(self):
        # Fernandópolis: x = (lon + 74) * 10 ; y = (6 - lat) * 10
        x, y = gerar_site.proj(-20.2836, -50.2463)
        self.assertAlmostEqual(x, 237.537, places=2)
        self.assertAlmostEqual(y, 262.836, places=2)


if __name__ == "__main__":
    unittest.main()


class Exterior(unittest.TestCase):
    def test_sugestoes_do_exterior_sem_repetir_e_com_pais(self):
        lista = json.loads((Path(__file__).resolve().parent.parent / "data" / "faculdades_exterior.json").read_text(encoding="utf-8"))["faculdades"]
        nomes = [x["nome"] for x in lista]
        self.assertEqual(len(nomes), len(set(nomes)))
        self.assertTrue(all(x["pais"] in {"Paraguai", "Bolívia", "Argentina", "Uruguai"} for x in lista))


class Textos(unittest.TestCase):
    def test_contador_no_ultimo_dia_e_depois(self):
        self.assertEqual(gerar_site.contador_prazo("2026-10-01", "2026-10-29", "2026-10-29")[:2], ("Hoje", "é o último dia de inscrição"))
        self.assertEqual(gerar_site.contador_prazo("2026-11-01", "2026-11-29", "2026-10-28")[1], "dias para abrirem as inscrições")
        self.assertIsNone(gerar_site.contador_prazo("2026-10-01", "2026-10-29", "2026-10-30"))

    def test_marco_de_hoje_nao_duplica(self):
        html = gerar_site.linha_do_tempo({"inscricao_inicio": "2026-10-01", "inscricao_fim": "2026-10-29"}, "2026-10-29")
        self.assertIn("Hoje · Último dia de inscrição", html)
        self.assertIn('class="marco hoje" hidden', html)

    def test_vagas_com_preposicao_certa(self):
        self.assertEqual(gerar_site.vagas_texto({"vagas": [{"semestre": "2º ao 7º", "vagas": None}]}),
                         "vagas do 2º ao 7º (quantidade: confira no edital)")
        self.assertEqual(gerar_site.vagas_texto({"vagas": [{"semestre": "5º ano", "vagas": 2}, {"semestre": "3º", "vagas": 1}]}),
                         "2 vagas no 5º ano · 1 vaga no 3º")
        self.assertEqual(gerar_site.vagas_texto({"vagas": [{"semestre": "não informado", "vagas": 8}]}), "8 vagas")


class AvisoDaFicha(unittest.TestCase):
    """Bug de 26/10/2026: toda pendência desconhecida virava "falta descobrir onde publica", mesmo com a página conhecida."""
    def test_motivo_certo_para_cada_pendencia(self):
        casos = {
            "a página de transferência carrega os editais por script (o robô não lê)": "não consegue ler sozinho",
            "o site recusa acesso automático (bloqueio anti-robô)": "não permite a leitura automática",
            "os editais saem numa página nova da EconRio a cada semestre": "página nova a cada semestre",
            "transferência por pedido direto à faculdade, sem edital publicado": "pedido direto",
            "descobrir a página onde esta faculdade publica os editais de transferência": "Ainda falta descobrir",
        }
        for pendente, esperado in casos.items():
            self.assertIn(esperado, gerar_site.aviso_pendente({"pendente": pendente}), pendente)

    def test_nenhuma_ficha_real_com_pagina_conhecida_diz_falta_descobrir(self):
        fichas = json.loads((Path(gerar_site.__file__).parent / "data" / "faculdades.json").read_text(encoding="utf-8"))
        for f in fichas:
            if f.get("pendente") and "descobrir" not in f["pendente"] and not f.get("aviso_publico"):
                self.assertNotIn("Ainda falta descobrir", gerar_site.aviso_pendente(f), f["id"])


class HtmlValido(unittest.TestCase):
    """Erros achados pelo html-validate e pelo axe em 26/10/2026 (QA antes da publicação)."""
    PASTA = Path(gerar_site.__file__).parent / "docs"

    def paginas(self):
        return list(self.PASTA.rglob("index.html"))

    def test_titulo_curto_usa_a_primeira_opcao_que_cabe(self):
        self.assertEqual(gerar_site.titulo_curto("a" * 71, "curto"), "curto")
        self.assertEqual(gerar_site.titulo_curto("cabe", "outro"), "cabe")

    def test_titulos_ate_95_caracteres(self):
        # formatos pedidos pelo dono (ex.: exterior, 81): o termo de busca vem primeiro, o Google corta só o fim
        import html, re
        for p in self.paginas():
            t = html.unescape(re.search(r"<title>(.*?)</title>", p.read_text(encoding="utf-8"), re.S).group(1))
            self.assertLessEqual(len(t), 95, f"{p}: {t}")

    def test_sem_espaco_no_fim_da_linha_e_doctype_maiusculo(self):
        import re
        for p in self.paginas():
            s = p.read_text(encoding="utf-8")
            self.assertTrue(s.startswith("<!DOCTYPE html>"), p)
            self.assertIsNone(re.search(r"[ \t]+\r?\n", s), p)

    def test_fieldset_sempre_com_legend(self):
        import re
        s = (self.PASTA / "diagnostico" / "index.html").read_text(encoding="utf-8")
        for m in re.finditer(r"<fieldset>\s*<(\w+)", s):
            self.assertEqual(m.group(1), "legend")

    def test_mapa_com_links_nao_e_imagem(self):
        # role="img" esconde os links dos pontos dos leitores de tela (axe: nested-interactive)
        s = (self.PASTA / "index.html").read_text(encoding="utf-8")
        self.assertNotIn('role="img" aria-labelledby="mapa', s)
        self.assertNotIn('role="img" aria-label="Mapa', (self.PASTA / "assets" / "app.js").read_text(encoding="utf-8"))

    def test_mapa_abre_no_brasil_com_atalhos_dos_estados(self):
        s = (self.PASTA / "editais" / "index.html").read_text(encoding="utf-8")  # o mapa saiu da home (29/10)
        self.assertIn(f'<svg viewBox="{gerar_site.VISTA_BRASIL}"', s)
        self.assertIn('aria-pressed="true">Brasil</button>', s)
        for nome in ("Bahia", "Minas Gerais", "Mato Grosso do Sul", "São Paulo"):
            self.assertIn(f'aria-pressed="false">{nome}</button>', s)

    def test_titulo_e_descricao_unicos_em_cada_pagina(self):
        import re
        titulos, descricoes = {}, {}
        for p in self.paginas():
            s = p.read_text(encoding="utf-8")
            t = re.search(r"<title>(.*?)</title>", s).group(1)
            d = re.search(r'<meta name="description" content="(.*?)"', s).group(1)
            self.assertLessEqual(len(t), 95, p)
            self.assertNotIn(t, titulos, f"{p} repete o título de {titulos.get(t)}")
            self.assertNotIn(d, descricoes, f"{p} repete a descrição de {descricoes.get(d)}")
            titulos[t], descricoes[d] = p, p

    def test_schema_do_edital_tem_data_de_encerramento(self):
        import re
        editais = {x["id"]: x for x in json.loads((self.PASTA / "editais.json").read_text(encoding="utf-8"))}
        vistos = 0
        for p in (self.PASTA / "edital").glob("*/index.html"):
            s = p.read_text(encoding="utf-8")
            x = editais[re.search(r'data-edital="([^"]+)"', s).group(1)]
            blocos = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', s)]
            prog = [b for b in blocos if b["@type"] == "EducationalOccupationalProgram"]
            self.assertEqual(len(prog), 1, p)
            if x.get("inscricao_fim") and not x.get("fluxo_continuo"):
                self.assertEqual(prog[0]["applicationDeadline"], x["inscricao_fim"], p)
                vistos += 1
        self.assertGreater(vistos, 0)
        inicio = (self.PASTA / "index.html").read_text(encoding="utf-8")
        self.assertIn('"@type": "WebSite"', inicio)
        self.assertIn('"@type": "CollegeOrUniversity"', (self.PASTA / "faculdade" / "ufba-salvador" / "index.html").read_text(encoding="utf-8"))

    def test_sitemap_tem_todas_as_paginas_publicas(self):
        mapa = (self.PASTA / "sitemap.xml").read_text(encoding="utf-8")
        for p in self.paginas():
            caminho = p.parent.relative_to(self.PASTA).as_posix()
            url = f"{gerar_site.SITE_URL}/" + ("" if caminho == "." else caminho + "/")
            if 'name="robots" content="noindex"' in p.read_text(encoding="utf-8"):  # alerta, minha lista
                self.assertNotIn(f"<loc>{url}</loc>", mapa)
            else:
                self.assertIn(f"<loc>{url}</loc>", mapa)
        robots = (self.PASTA / "robots.txt").read_text(encoding="utf-8")
        self.assertIn(f"Sitemap: {gerar_site.SITE_URL}/sitemap.xml", robots)

    def test_service_worker_html_da_rede_e_assume_na_hora(self):
        sw = (self.PASTA / "sw.js").read_text(encoding="utf-8")
        self.assertIn("{cache: 'no-cache'}", sw)  # HTML sem a cópia do navegador
        instalar = sw[sw.index("'install'"):sw.index("'activate'")]
        self.assertLess(instalar.index("self.skipWaiting()"), instalar.index("waitUntil"))  # não depende da cópia da base
        self.assertIn("caches.delete", sw)
        self.assertIn("self.clients.claim()", sw)
        self.assertIn("updateViaCache: 'none'", (self.PASTA / "assets" / "app.js").read_text(encoding="utf-8"))

    def test_sem_estilo_inline_nas_paginas_geradas(self):
        for p in self.paginas():
            self.assertNotIn(' style="', p.read_text(encoding="utf-8"), p)


class OrdemDoHistorico(unittest.TestCase):
    """Rodada de melhoria 1: sem data de fim, "2026.1" passava na frente de "2026.2" (comparação de texto)."""
    def test_mais_novo_primeiro_mesmo_sem_data(self):
        eds = [{"semestre_ingresso": "2026.1"}, {"semestre_ingresso": "2026.2", "inscricao_fim": "2026-06-22"},
               {"semestre_ingresso": "2027.1", "inscricao_fim": "2026-11-18"}, {"semestre_ingresso": "2025 (anual)"}]
        ordem = [e["semestre_ingresso"] for e in sorted(eds, key=gerar_site.ordem_historico, reverse=True)]
        self.assertEqual(ordem, ["2027.1", "2026.2", "2026.1", "2025 (anual)"])


class Confianca(unittest.TestCase):
    """Etapa 2: "Quem faz", /sobre/ e /contato/."""
    DOCS = gerar_site.DOCS

    def ler(self, caminho):
        return (self.DOCS / caminho).read_text(encoding="utf-8")

    def test_quem_faz_no_cabecalho_de_todas_as_paginas_fechado_e_sem_foto(self):
        for pagina in self.DOCS.rglob("index.html"):
            html = pagina.read_text(encoding="utf-8")
            cabecalho = html[html.index('<header class="topo">'):html.index("</header>")]
            self.assertIn('class="quem-faz-botao" aria-expanded="false" aria-controls="quem-faz"', cabecalho, pagina)
            self.assertRegex(html, r'class="qf-painel"[^>]*hidden', "o painel começa fechado")
            painel = html[html.index("data-quem-faz"):html.index("<main")]
            self.assertNotIn("<img", painel, "o painel não tem foto")
            self.assertEqual(html.count('id="quem-faz"'), 1, pagina)
        self.assertNotIn("assets/sobre/", self.ler("index.html"), "a foto não aparece na página inicial")

    def test_consultoria_so_na_historia_da_sobre(self):
        achados = [f.relative_to(self.DOCS).as_posix() for f in self.DOCS.rglob("*") if f.suffix in (".html", ".js")
                   and "consultoria" in f.read_text(encoding="utf-8").lower()]
        self.assertEqual(achados, ["sobre/index.html"])
        self.assertEqual(self.ler("sobre/index.html").lower().count("consultoria"), 1)
        self.assertIn("comecei a ajudar outros estudantes, um por um, em uma consultoria", self.ler("sobre/index.html"))

    def test_sobre_tem_o_texto_do_dono_e_contato(self):
        html = self.ler("sobre/index.html")
        self.assertIn("<p>Oi, eu sou o Cauã.</p>", html)
        self.assertIn("Espero que o Transfermed deixe esse caminho um pouco mais leve.", html)
        self.assertIn("Nenhuma faculdade paga para aparecer aqui ou para ficar em destaque.", html)
        self.assertIn("O papel do Transfermed é te ajudar a chegar preparado.", html)
        self.assertIn("Eu leio todas as mensagens.", html)
        self.assertIn('id="form-contato"', html)
        self.assertIn('"@type": "AboutPage"', html)

    def test_contato_sem_email_pessoal_sem_preco_e_consentimento_desmarcado(self):
        for pagina in ("contato/index.html", "sobre/index.html", "index.html"):
            html = self.ler(pagina)
            self.assertNotIn("mailto:", html, pagina)
            self.assertNotIn("@gmail", html, pagina)
            self.assertNotRegex(html, r"R\$\s?\d", f"nenhum preço em {pagina}")
        html = self.ler("contato/index.html")
        self.assertRegex(html, r'<input type="checkbox" name="consentimento" required>', "consentimento nunca pré-marcado")
        for motivo in ("Encontrei um erro", "Tenho uma dúvida", "Tenho uma sugestão", "Outro assunto"):
            self.assertIn(motivo, html)
        self.assertIn('name="campo_extra"', html, "honeypot")

    def test_configuracao_publica_nao_some_sem_variaveis(self):
        js = self.ler("dados.js")
        cfg = json.loads(js.split("window.TM_CONFIG=", 1)[1].rstrip().rstrip(";"))
        self.assertTrue(cfg["supabaseUrl"].startswith("https://"), "o formulário de alerta não pode sair do ar")


class Produto(unittest.TestCase):
    """Etapa 3: portas de entrada, mapa só com abertas, ficha em 3 blocos e Minha lista."""
    DOCS = gerar_site.DOCS
    E = [x for x in json.loads((gerar_site.PASTA / "data" / "editais.json").read_text(encoding="utf-8")) if gerar_site.publicavel(x)]

    def ficha(self, ed):
        return (self.DOCS / "edital" / gerar_site.slug_edital(ed) / "index.html").read_text(encoding="utf-8")

    def test_inicio_tem_duas_portas_e_mapa_so_com_abertas(self):
        html = (self.DOCS / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="diagnostico/?origem=brasil"><b>Estudo Medicina no Brasil</b>', html)
        self.assertIn('href="diagnostico/?origem=exterior"><b>Estudo Medicina no exterior</b>', html)
        self.assertNotIn('class="ponto neutro"', html)
        self.assertNotIn("sem edital na base", html)

    def test_ficha_em_tres_blocos_na_ordem(self):
        for ed in self.E:
            html = self.ficha(ed)
            i, j, k = (html.index(f'id="t-{b}"') for b in ("posso", "quando", "preciso"))
            self.assertTrue(i < j < k, ed["id"])
            if ed.get("conferido_em") and not ed.get("fluxo_continuo"):
                self.assertIn(f"Conferido no edital oficial em {gerar_site.fmt(ed['conferido_em'])}", html)

    def test_ficha_nao_deduz_documentos_nem_dados(self):
        for ed in self.E:
            html = self.ficha(ed)
            self.assertNotIn("costumam pedir", html, "lista genérica de documentos é dedução")
            if not ed.get("documentos"):
                self.assertNotIn('id="checklist"', html)
                self.assertIn("ainda não foi transcrita aqui", html)
            if ed.get("taxa_inscricao") is None and not ed.get("fluxo_continuo"):
                self.assertRegex(html, r"<dt>Taxa de inscrição</dt><dd>não informado no edital")

    def test_unilago_avisa_pagina_fora_do_ar(self):
        aviso = "A página de transferência da UNILAGO está fora do ar desde 29/10/2026. Confirme diretamente com a faculdade."
        self.assertIn(aviso, (self.DOCS / "faculdade" / "unilago" / "index.html").read_text(encoding="utf-8"))
        ed = next(x for x in self.E if x["faculdade_id"] == "unilago")
        self.assertIn(aviso, self.ficha(ed))

    def test_minha_lista_fora_do_google_e_no_menu(self):
        html = (self.DOCS / "minha-lista" / "index.html").read_text(encoding="utf-8")
        self.assertIn('name="robots" content="noindex"', html)
        self.assertIn('class="lista-icone" href="../minha-lista/"', (self.DOCS / "sobre" / "index.html").read_text(encoding="utf-8"))
        self.assertIn("Disallow: /minha-lista/", (self.DOCS / "robots.txt").read_text(encoding="utf-8"))


class Google(unittest.TestCase):
    """Parte 3: sitemap, títulos únicos, JSON-LD válido, canonical e links estado ↔ faculdade ↔ edital."""
    DOCS = gerar_site.DOCS

    def publicas(self):
        mapa = (self.DOCS / "sitemap.xml").read_text(encoding="utf-8")
        import re
        urls = re.findall(r"<loc>([^<]+)</loc>", mapa)
        for u in urls:
            caminho = u[len(gerar_site.SITE_URL) + 1:]
            yield u, (self.DOCS / caminho / "index.html").read_text(encoding="utf-8")

    def test_sitemap_com_lastmod_real_e_so_paginas_que_existem(self):
        import re
        mapa = (self.DOCS / "sitemap.xml").read_text(encoding="utf-8")
        datas = re.findall(r"<lastmod>(\d{4}-\d\d-\d\d)</lastmod>", mapa)
        self.assertEqual(len(datas), mapa.count("<url>"))
        E = [x for x in json.loads((gerar_site.PASTA / "data" / "editais.json").read_text(encoding="utf-8")) if gerar_site.publicavel(x)]
        for x in E[:20]:  # lastmod do edital = a data mais nova do próprio dado (conferência, leitura, detecção)
            d = max(v for v in (x.get("conferido_em"), x.get("atualizado_em"), x.get("detectado_em"), "2026-01-01") if v)[:10]
            self.assertIn(f"/edital/{gerar_site.slug_edital(x)}/</loc><lastmod>{d}</lastmod>", mapa)
        for u, html in self.publicas():
            self.assertNotIn('content="noindex"', html, u)

    def test_titulo_descricao_e_canonical_unicos(self):
        import re
        titulos, descricoes = {}, {}
        for u, html in self.publicas():
            titulo = re.search(r"<title>([^<]+)</title>", html).group(1)
            desc = re.search(r'<meta name="description" content="([^"]+)"', html).group(1)
            self.assertIn(f'<link rel="canonical" href="{u}">', html)
            self.assertNotIn(titulo, titulos, f"título repetido em {u} e {titulos.get(titulo)}")
            self.assertNotIn(desc, descricoes, f"descrição repetida em {u}")
            titulos[titulo], descricoes[desc] = u, u

    def test_formatos_de_titulo(self):
        ler = lambda c: (self.DOCS / c / "index.html").read_text(encoding="utf-8")
        self.assertIn("<title>Transferência de Medicina do exterior para o Brasil: onde, quando e o que precisa</title>", ler("exterior"))
        self.assertIn("<title>Transferência de Medicina na Bahia: editais abertos e prazos</title>", ler("estado/ba"))
        self.assertRegex(ler("faculdade/famerp"), r"<title>Transferência de Medicina na FAMERP \(São José do Rio Preto\) — edital 20\d\d, prazos e documentos</title>")

    def test_json_ld_valido_e_completo(self):
        import re
        tipos = set()
        for f in self.DOCS.rglob("index.html"):
            for bloco in re.findall(r'<script type="application/ld\+json">(.*?)</script>', f.read_text(encoding="utf-8"), re.S):
                obj = json.loads(bloco)  # falha aqui se a sintaxe estiver errada
                self.assertEqual(obj["@context"], "https://schema.org")
                tipos.add(obj["@type"])
                if obj["@type"] == "EducationalOccupationalProgram" and obj.get("applicationDeadline"):
                    self.assertIn(gerar_site.fmt(obj["applicationDeadline"]), f.read_text(encoding="utf-8"), "prazo do JSON-LD visível na página")
        for t in ("WebSite", "Organization", "AboutPage", "ContactPage", "CollegeOrUniversity", "EducationalOccupationalProgram", "CollectionPage", "BreadcrumbList"):
            self.assertIn(t, tipos)
        inicio = (self.DOCS / "index.html").read_text(encoding="utf-8")
        self.assertIn('"urlTemplate": "https://www.transfermed.com.br/?busca={search_term_string}"', inicio)

    def test_links_estado_faculdade_edital(self):
        estado = (self.DOCS / "estado" / "sp" / "index.html").read_text(encoding="utf-8")
        F = [f for f in json.loads((gerar_site.PASTA / "data" / "faculdades.json").read_text(encoding="utf-8")) if f["uf"] == "SP"]
        for f in F:
            self.assertIn(f'href="../../faculdade/{f["id"]}/"', estado)
        self.assertIn('href="../../estado/sp/"', (self.DOCS / "faculdade" / "famerp" / "index.html").read_text(encoding="utf-8"))
        ficha = next((self.DOCS / "edital").glob("famerp-*/index.html")).read_text(encoding="utf-8")
        self.assertIn('href="../../estado/sp/"', ficha)
        self.assertIn('href="../../faculdade/famerp/"', ficha)
        self.assertIn('href="./estado/ba/">Bahia</a>', (self.DOCS / "index.html").read_text(encoding="utf-8"))


class SitemapPublicado(unittest.TestCase):
    """O GitHub Pages publica só a pasta docs/: sitemap.xml e robots.txt precisam estar nela, na raiz."""

    def test_sitemap_e_robots_na_pasta_publicada(self):
        import xml.etree.ElementTree as ET
        self.assertEqual(gerar_site.DOCS, gerar_site.PASTA / "docs")
        for nome in ("sitemap.xml", "robots.txt"):
            self.assertTrue((gerar_site.DOCS / nome).is_file(), f"docs/{nome} não existe")
        for nome in ("sitemap.xml", "robots.txt"):
            self.assertFalse((gerar_site.PASTA / nome).exists(), f"{nome} gerado fora de docs/ (não é publicado)")
        ET.fromstring((gerar_site.DOCS / "sitemap.xml").read_bytes())  # XML válido
        robots = (gerar_site.DOCS / "robots.txt").read_text(encoding="utf-8")
        self.assertIn(f"Sitemap: {gerar_site.SITE_URL}/sitemap.xml", robots)
        ignorado = __import__("subprocess").run(["git", "check-ignore", "-q", "docs/sitemap.xml", "docs/robots.txt"],
                                                cwd=gerar_site.PASTA).returncode
        self.assertNotEqual(ignorado, 0, "sitemap.xml ou robots.txt está no .gitignore")

    def test_conferencia_do_site_publicado(self):
        sys.path.insert(0, str(gerar_site.PASTA / "qa"))
        import publicado
        xml_ok = (gerar_site.DOCS / "sitemap.xml").read_bytes()
        n = xml_ok.count(b"<url>")
        self.assertEqual(publicado.conferir_sitemap(200, "application/xml", xml_ok, n), [])
        self.assertIn("sitemap.xml respondeu 404", publicado.conferir_sitemap(404, "text/html", b"", n))
        self.assertTrue(publicado.conferir_sitemap(200, "text/html", b"<html>", n))
        self.assertEqual(publicado.conferir_robots(200, "text/plain; charset=utf-8", (gerar_site.DOCS / "robots.txt").read_text(encoding="utf-8")), [])
        self.assertTrue(publicado.conferir_robots(200, "text/plain", "User-agent: *"))
        ruim = xml_ok.replace(b"<loc>https://", b"<loc>http://", 1)
        self.assertTrue(any("http://" in f for f in publicado.conferir_sitemap(200, "application/xml", ruim, n)))
        self.assertEqual(publicado.enderecos_inseguros('<link rel="canonical" href="https://x/">'), [])
        self.assertEqual(publicado.enderecos_inseguros('<meta property="og:image" content="http://x/a.png">'), ["http://x/a.png"])

    def test_nenhum_endereco_http_nas_paginas_geradas(self):
        sys.path.insert(0, str(gerar_site.PASTA / "qa"))
        import publicado
        for f in gerar_site.DOCS.rglob("index.html"):
            self.assertEqual(publicado.enderecos_inseguros(f.read_text(encoding="utf-8")), [], f)


class MedicaoDoFunil(unittest.TestCase):
    """Todo evento que o site dispara é aceito pela função medir do Supabase (senão a contagem some calada)."""

    def test_eventos_do_site_estao_na_lista_do_banco(self):
        import re
        raiz = Path(gerar_site.__file__).parent
        js = (raiz / "docs" / "assets" / "app.js").read_text(encoding="utf-8")
        sql = (raiz / "supabase" / "schema.sql").read_text(encoding="utf-8")
        lista = sql[sql.index("create or replace function public.medir"):]
        lista = set(re.findall(r"'([a-z_]+)'", lista[:lista.index("then")]))
        usados = set(re.findall(r"medir\('([a-z_]+)'\)", js))
        usados |= set(re.findall(r'data-medir="([a-z_]+)"', js + (raiz / "gerar_site.py").read_text(encoding="utf-8")))
        contextos = set()
        for html in (gerar_site.DOCS).rglob("index.html"):
            contextos |= set(re.findall(r'data-contexto="([a-z_]+)"', html.read_text(encoding="utf-8")))
        usados |= {f"alerta_inscrito_{c}" for c in contextos | {"outro"}}
        self.assertTrue({"visita", "diagnostico_concluido", "alerta_inscrito", "alerta_confirmado", "ver_edital",
                         "compartilhar_whatsapp"} <= usados)
        self.assertEqual(usados - lista, set(), "eventos que o banco recusaria")

    def test_privacidade_explica_a_contagem(self):
        html = (gerar_site.DOCS / "privacidade" / "index.html").read_text(encoding="utf-8")
        self.assertIn("Contagem de uso, sem cookies", html)


class FaqEDepoimentos(unittest.TestCase):
    def test_faq_na_home_e_no_json_ld(self):
        html = (gerar_site.DOCS / "index.html").read_text(encoding="utf-8")
        for q in ("É grátis?", "Vocês garantem a vaga?", "De onde vêm os dados?", "Vou receber spam?"):
            self.assertIn(f"<summary>{q}</summary>", html)
        self.assertIn('"@type": "FAQPage"', html)

    def test_sem_depoimento_real_nao_ha_secao(self):
        arq = gerar_site.PASTA / "data" / "depoimentos.json"
        if not arq.exists() or not json.loads(arq.read_text(encoding="utf-8")):
            self.assertEqual(gerar_site.depoimentos(), "")
            self.assertNotIn("Quem já usou", (gerar_site.DOCS / "index.html").read_text(encoding="utf-8"))


class PaginaExterior(unittest.TestCase):
    def test_exterior_com_dados_e_isca_propria(self):
        html = (gerar_site.DOCS / "exterior" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("Documentos que costumam pedir", html, "lista genérica trocada pelos pedidos dos editais")
        self.assertIn("Abertos agora para quem vem do exterior", html)
        self.assertIn("checklist-documentos-transferencia-medicina-exterior.pdf", html)
        self.assertTrue((gerar_site.DOCS / "checklist-documentos-transferencia-medicina-exterior.pdf").exists())
        self.assertIn("UB</a>: Tradução juramentada e apostila de Haia", html)
        self.assertIn('href="../diagnostico/?origem=exterior"', html)


class WhatsApp(unittest.TestCase):
    def test_toda_ficha_de_edital_tem_enviar_no_whatsapp(self):
        fichas = list((gerar_site.DOCS / "edital").glob("*/index.html"))
        self.assertTrue(fichas)
        for f in fichas:
            html = f.read_text(encoding="utf-8")
            self.assertIn('data-medir="compartilhar_whatsapp">Enviar no WhatsApp', html, f.parent.name)
            self.assertIn("https://wa.me/?text=", html)
            self.assertIn(f"transfermed.com.br%2Fedital%2F{f.parent.name}%2F", html.replace("%3A%2F%2Fwww.", "."), f.parent.name)


class Agenda(unittest.TestCase):
    def test_ficha_com_google_agenda_e_assinatura(self):
        html = (gerar_site.DOCS / "edital" / "unime-externa-2027-1-3d14f3" / "index.html").read_text(encoding="utf-8")
        self.assertIn("https://calendar.google.com/calendar/render?action=TEMPLATE", html)
        self.assertIn("dates=20261118/20261119", html, "último dia como evento de dia inteiro")
        self.assertIn('href="webcal://www.transfermed.com.br/faculdade/unime/prazos.ics"', html)
        self.assertIn('href="prazos.ics" download>Baixar .ics</a>', html, ".ics só como opção discreta")
        self.assertNotIn('class="botao sec" href="prazos.ics"', html)

    def test_toda_faculdade_tem_calendario_para_assinar(self):
        import json as _json
        F = _json.loads((gerar_site.PASTA / "data" / "faculdades.json").read_text(encoding="utf-8"))
        for f in F:
            ics = (gerar_site.DOCS / "faculdade" / f["id"] / "prazos.ics").read_bytes().decode("utf-8")
            self.assertTrue(ics.startswith("BEGIN:VCALENDAR\r\n"), f["id"])
            self.assertIn("X-WR-CALNAME:", ics)
            self.assertIn("REFRESH-INTERVAL;VALUE=DURATION:PT12H", ics)


class HomeEnxuta(unittest.TestCase):
    """Home de 29/10: título e portas, prazo mais próximo, 5 editais com "Ver todos", como funciona, confiança e FAQ."""

    def test_home_so_com_o_essencial(self):
        html = (gerar_site.DOCS / "index.html").read_text(encoding="utf-8")
        main = html[html.index("<main"):html.index("</main>")]
        self.assertEqual(main.count('<article class="cartao'), gerar_site.LIMITE_HOME)
        self.assertIn('href="editais/">Ver todos os', main)
        for fora in ('figure class="radar', 'id="form-alerta"', "faixa-numeros", 'id="jornada"'):
            self.assertNotIn(fora, main)
        for dentro in ('class="portas"', "Como funciona", "Por que dá para confiar", "Perguntas frequentes"):
            self.assertIn(dentro, main)

    def test_editais_tem_o_resto(self):
        html = (gerar_site.DOCS / "editais" / "index.html").read_text(encoding="utf-8")
        for dentro in ('figure class="radar', 'id="form-alerta"', 'id="n-abertos"', 'id="jornada"'):
            self.assertIn(dentro, html)
