"""Itens do privado/PADRAO_DE_QUALIDADE.md (seção 3) que viraram checagem automática do Instagram (10/11/2026):
2 prazo vencendo em menos de 48 h, 3 gancho com até 8 palavras, 6 tamanho das letras e área vazia, 8 rodapé de fonte em cada tela com dado,
9 até 7 hashtags e "Confira sempre o edital oficial". Cada teste prova que pega o defeito (post ruim reprova) e que o post bom passa."""
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))
import instagram_cartoes as cart  # noqa: E402
import instagram_checagem as ck  # noqa: E402
import instagram_dia as dia  # noqa: E402
import instagram_visual as vis  # noqa: E402
from tests.test_instagram_checagem import ANTIGO, HOJE, _post  # noqa: E402
from tests.test_instagram_dia import EDITAIS, FACS  # noqa: E402

FIXT = Path(__file__).resolve().parent / "fixtures"
SOCIAL = PASTA / "docs" / "social"


def _regras(problemas, item):
    return [p for p in problemas if p.startswith(f"({item})")]


class P2Prazo48h(unittest.TestCase):
    def ck(self, texto, data="2026-11-10"):
        return _regras(ck.checar(_post(textos=[texto], data=data), EDITAIS, FACS, data), "P2")

    def test_prazo_amanha_reprova(self):
        self.assertTrue(self.ck("Inscrições até 11/11/2026"))
        self.assertTrue(self.ck("fecha amanhã, até 11/11"))

    def test_prazo_no_dia_seguinte_ao_dos_48h_passa(self):
        # publicado 10/11 às 12h: 12/11 às 23h59 está a mais de 48 h; 11/11 não
        self.assertEqual(self.ck("Inscrições até 12/11/2026"), [])
        self.assertEqual(self.ck("Inscrições até 16/11"), [])

    def test_prazo_ja_vencido_reprova_e_data_por_extenso_tambem(self):
        self.assertTrue(self.ck("Inscrições até 05/11/2026"))
        self.assertTrue(self.ck("fecham até 11 de novembro"))
        self.assertEqual(self.ck("fecham até 9 de dezembro"), [])

    def test_data_de_calendario_e_numero_de_portaria_nao_sao_prazo(self):
        self.assertEqual(self.ck("Editais abertos · semana de 10/11. Portaria 24/2026, p. 3, item 5.3"), [])
        self.assertEqual(self.ck("Os editais abertos desde 03/11 fecham até 20/11"), [])

    def test_faixa_de_datas_vale_pelo_fim(self):
        self.assertEqual(self.ck("De 02 a 07/12, só cartão"), [])
        self.assertTrue(self.ck("De 09 a 11/11, só cartão"))

    def test_o_dia_da_publicacao_e_o_do_post_nao_o_do_relogio(self):
        self.assertTrue(self.ck("Inscrições até 11/11", data="2026-11-10"))
        self.assertEqual(self.ck("Inscrições até 11/11", data="2026-11-08"), [])

    def test_link_com_data_na_legenda_nao_conta(self):
        leg = "Confira sempre o edital oficial.\nImagens (https): https://www.transfermed.com.br/social/2026-11-10/01.jpg"
        self.assertEqual(_regras(ck.checar(_post(legenda=leg, data="2026-11-10"), EDITAIS, FACS, HOJE), "P2"), [])

    def test_prazo_virando_o_ano(self):
        self.assertEqual(self.ck("Inscrições até 10/01", data="2026-12-28"), [])


class P3Gancho(unittest.TestCase):
    def ck(self, gancho):
        return _regras(ck.checar(_post(gancho=gancho), EDITAIS, FACS, HOJE), "P3")

    def test_oito_palavras_passa_nove_reprova(self):
        self.assertEqual(self.ck("Estas 3 faculdades fecham a inscrição até 23/11"), [])
        self.assertTrue(self.ck("Nesta faculdade, depois de 1º/12 o boleto não vale"))

    def test_valor_em_reais_conta_uma_palavra(self):
        self.assertEqual(self.ck("Taxas de R$ 100 a R$ 825 nestes 30 editais"), [])

    def test_gancho_comprido_do_post_anterior_do_11_11_reprovaria(self):
        self.assertTrue(self.ck("Estas 3 faculdades fecham a inscrição de transferência em Medicina até 23/11"))


class P9Legenda(unittest.TestCase):
    def ck(self, legenda):
        return _regras(ck.checar(_post(legenda=legenda), EDITAIS, FACS, HOJE), "P9")

    def test_sete_hashtags_passa_oito_reprova(self):
        base = "Confira sempre o edital oficial.\n"
        self.assertEqual(self.ck(base + " ".join(f"#t{i}" for i in range(7))), [])
        self.assertTrue(any("8 hashtags" in x for x in self.ck(base + " ".join(f"#t{i}" for i in range(8)))))

    def test_sem_confira_sempre_reprova(self):
        self.assertTrue(self.ck("Veja os editais. #medicina"))
        self.assertEqual(self.ck("Prazos conferidos. CONFIRA SEMPRE O EDITAL OFICIAL. #medicina"), [])

    def test_hashtag_de_link_nao_conta(self):
        self.assertEqual(self.ck("Confira sempre o edital oficial.\nhttps://www.transfermed.com.br/p/#a #b"), [])


class P8RodapeDeFonte(unittest.TestCase):
    def ck(self, telas):
        return _regras(ck.checar(_post(telas=telas), EDITAIS, FACS, HOJE), "P8")

    def test_tela_com_dado_sem_rodape_reprova(self):
        t = [{"tipo": "capa", "kicker": "k", "titulo": "Estas 3 faculdades fecham até 23/11", "apoio": "a", "botao": "b"}]
        self.assertTrue(self.ck(t))

    def test_tela_com_dado_e_rodape_passa(self):
        t = [{"tipo": "capa", "kicker": "k", "titulo": "Fecham até 23/11", "apoio": "a", "fonte": "Fontes: edital, p. 2", "botao": "b"}]
        self.assertEqual(self.ck(t), [])

    def test_tela_sem_dado_nao_precisa_de_rodape_e_contador_nao_e_dado(self):
        t = [{"tipo": "chamada", "titulo": "Seu documento está pronto?", "apoio": "2/4", "botao": "Ative o alerta", "rodape": "Confira sempre o edital oficial."}]
        self.assertEqual(self.ck(t), [])

    def test_valor_em_reais_e_vagas_sao_dado(self):
        self.assertTrue(self.ck([{"tipo": "chamada", "titulo": "Taxa de R$ 200", "apoio": "", "botao": "", "rodape": ""}]))
        self.assertTrue(self.ck([{"tipo": "chamada", "titulo": "Abrem 12 vagas", "apoio": "", "botao": "", "rodape": ""}]))

    def test_post_sem_telas_declaradas_reprova(self):
        self.assertTrue(self.ck([]))


class P6LeituraNoCelular(unittest.TestCase):
    def test_imagens_do_dono_antes_da_correcao_reprovam(self):
        antigas = FIXT / "instagram_imagens_antigas"
        p1 = vis.problemas(antigas / "2026-11-11-02-cartao-unico.jpg")
        self.assertTrue(any("área vazia" in x for x in p1), p1)       # cartão único com metade da tela vazia
        self.assertTrue(any("mínimo 26" in x for x in p1), p1)        # rodapé de fonte de ~22 px
        p2 = vis.problemas(antigas / "2026-11-10-01-armadilha.jpg")
        self.assertTrue(any("mínimo 26" in x for x in p2), p2)

    def test_imagem_do_robo_antigo_de_10_11_reprova(self):
        p = vis.problemas(ANTIGO / "01.jpg")
        self.assertTrue(any("mínimo 26" in x for x in p), p)

    def test_imagens_atuais_dos_tres_posts_passam(self):
        for d in ("2026-11-09", "2026-11-10", "2026-11-11"):
            if not (SOCIAL / d).exists():
                continue
            for im in sorted((SOCIAL / d).glob("[0-9][0-9].jpg")):
                self.assertEqual(vis.problemas(im), [], im)

    def test_imagem_sintetica_com_letra_pequena_e_tela_vazia(self):
        from PIL import Image, ImageDraw
        import gerar_site as g
        with tempfile.TemporaryDirectory() as tmp:
            im = Image.new("RGB", (1080, 1350), "#0B1E2C")
            d = ImageDraw.Draw(im)
            d.text((72, 300), "Titulo grande aqui", font=g._fonte(90, "Bold"), fill="white")
            d.text((72, 420), "texto de apoio pequeno demais para ler", font=g._fonte(20), fill="white")
            alvo = Path(tmp) / "a.jpg"
            im.save(alvo)
            p = vis.problemas(alvo)
            self.assertTrue(any("mínimo 26" in x for x in p), p)
            self.assertTrue(any("área vazia" in x for x in p), p)
            im = Image.new("RGB", (1080, 1350), "#0B1E2C")
            d = ImageDraw.Draw(im)
            d.text((72, 300), "Titulo grande aqui", font=g._fonte(90, "Bold"), fill="white")
            d.text((72, 420), "texto de apoio no tamanho certo para o celular", font=g._fonte(34), fill="white")
            d.rounded_rectangle((72, 560, 1008, 1200), radius=26, fill="#12293E")
            alvo = Path(tmp) / "b.jpg"
            im.save(alvo)
            self.assertEqual(vis.problemas(alvo), [])

    def test_titulo_pequeno_demais_reprova(self):
        from PIL import Image, ImageDraw
        import gerar_site as g
        with tempfile.TemporaryDirectory() as tmp:
            im = Image.new("RGB", (1080, 1350), "#0B1E2C")
            d = ImageDraw.Draw(im)
            d.text((72, 300), "Titulo pequeno demais", font=g._fonte(30, "Bold"), fill="white")
            d.rounded_rectangle((72, 400, 1008, 1250), radius=26, fill="#12293E")
            alvo = Path(tmp) / "c.jpg"
            im.save(alvo)
            self.assertTrue(any("texto principal" in x for x in vis.problemas(alvo)))


class PostsDoDono(unittest.TestCase):
    """Os posts de 09, 10 e 11/11 passam nos itens do padrão; o de 10 e o de 11 passam em todas as regras com os dados reais."""

    @classmethod
    def setUpClass(cls):
        cls.editais, cls.facs = dia._dados()

    def _pasta(self, d):
        if not (SOCIAL / d / "post.json").exists():
            self.skipTest(f"pasta de {d} podada (o robô guarda 14 dias)")
        return SOCIAL / d

    def test_09_10_e_11_passam_nos_itens_2_3_6_8_9(self):
        for d in ("2026-11-09", "2026-11-10", "2026-11-11"):
            post = ck.post_de_pasta(self._pasta(d))
            self.assertEqual(ck.checar_padrao(post, d), [], d)

    def test_10_e_11_passam_em_todas_as_regras_com_os_dados_reais(self):
        for d in ("2026-11-10", "2026-11-11"):
            self.assertEqual(ck.checar(ck.post_de_pasta(self._pasta(d)), self.editais, self.facs, d), [], d)

    def test_09_so_reprova_se_um_edital_dele_voltar_a_conferir(self):
        """O de 09/11 (já publicado) cita a UVA; se a UVA estiver em 'conferir' (retificação de 09/11), só a regra (a) reprova, nenhum item do padrão."""
        post = ck.post_de_pasta(self._pasta("2026-11-09"))
        p = ck.checar(post, self.editais, self.facs, "2026-11-09")
        self.assertEqual([x for x in p if not x.startswith("(a)")], [], p)

    def test_o_gancho_de_cada_post_e_o_titulo_da_primeira_tela(self):
        for d in ("2026-11-09", "2026-11-10", "2026-11-11"):
            post = ck.post_de_pasta(self._pasta(d))
            titulo = post["telas"][0].get("titulo")
            self.assertEqual(post["gancho"], titulo, d)
            self.assertLessEqual(len(post["gancho"].split()), 8)

    def test_o_antigo_de_10_11_do_robo_reprova_pelos_itens_novos(self):
        p = ck.checar(ck.post_de_pasta(ANTIGO), self.editais, self.facs, "2026-11-10")
        for item in ("P6", "P8"):
            self.assertTrue(_regras(p, item), (item, p))
        self.assertTrue(any("mínimo 26" in x for x in _regras(p, "P6")))


class RevisadoPreservaTelas(unittest.TestCase):
    def test_copiar_de_novo_a_pasta_revisada_mantem_telas_e_gancho(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            privado, social = Path(tmp) / "privado", Path(tmp) / "social"
            rev = privado / "2026-11-11-revisado"
            rev.mkdir(parents=True)
            (rev / "01.jpg").write_bytes(b"jpg")
            (rev / "legenda.txt").write_text("Primeira linha muito comprida que passa de oito palavras com folga:\n\ntexto", encoding="utf-8")
            destino = social / "2026-11-11"
            destino.mkdir(parents=True)
            (destino / "post.json").write_text(json.dumps({"telas": [{"tipo": "capa", "titulo": "Gancho curto"}], "gancho": "Gancho curto"}), encoding="utf-8")
            self.assertTrue(dia.aplicar_revisado("2026-11-11", privado=privado, social=social))
            post = json.loads((destino / "post.json").read_text(encoding="utf-8"))
            self.assertEqual(post["gancho"], "Gancho curto")
            self.assertEqual(post["telas"][0]["titulo"], "Gancho curto")
            self.assertTrue(post["revisado"])


class RenderizadorDeTelas(unittest.TestCase):
    def test_cartao_unico_estica_e_nao_deixa_area_vazia(self):
        telas = [{"tipo": "cartoes", "kicker": "Fecha primeiro", "cartoes": [
            {"nome": "Universidade X (UX)", "detalhe": "Cidade/UF · transferência externa", "prazo": "Inscrições até 16/11/2026", "fonte": "edital, p. 2"}]}]
        with tempfile.TemporaryDirectory() as tmp:
            cart.renderizar(telas, tmp)
            self.assertEqual(vis.problemas(Path(tmp) / "01.jpg"), [])

    def test_textos_da_tela_inclui_rodape_de_fonte(self):
        t = {"tipo": "cartoes", "kicker": "k", "cartoes": [{"nome": "n", "detalhe": "d", "prazo": "p", "fonte": "edital, p. 2"}]}
        self.assertIn("edital, p. 2", cart.textos_da_tela(t))


class RoboComPadrao(unittest.TestCase):
    def test_o_que_o_robo_publica_passa_no_padrao_ou_nao_sai(self):
        editais, facs = dia._dados()
        for i in range(4):
            d = (date.fromisoformat(HOJE) + timedelta(days=i)).isoformat()
            r, nota = dia.escolher(editais, facs, d)
            if r is None:
                self.assertIn("nenhum formato passou", nota)
            else:
                self.assertEqual(ck.checar(r, editais, facs, d), [], f"{d}: {r['tipo']}")

    def test_cada_formato_do_robo_passa_inteiro_com_dados_reais_e_cita_a_pagina(self):
        """Item 8 nos 7 formatos (antes só a armadilha passava): toda tela com data, valor ou vagas termina com 'Fonte: ... p. N'."""
        editais, facs = dia._dados()
        formatos = [dia.post_abertos, dia.post_armadilha, dia.post_prazos, dia.post_taxas, dia.post_exterior, dia.post_documentos, dia.post_estados]
        passou = 0
        for f in formatos:
            r = f(editais, facs, HOJE)
            if r is None:
                continue  # sem dado seguro neste dia: o robô usa a reserva
            passou += 1
            self.assertEqual(ck.checar(r, editais, facs, HOJE), [], f.__name__)
            for i, sl in enumerate(r["slides"], 1):
                texto = " ".join(sl.textos)
                if ck.DADO_NA_TELA.search(texto):
                    self.assertRegex(texto, r"Fonte|edital, (regra )?p\.", (f.__name__, i))
                    self.assertTrue(ck.FONTE_NA_TELA.search(texto), (f.__name__, i))
        self.assertGreaterEqual(passou, 4)

    def test_capa_do_robo_nao_leva_data_solta_sem_fonte(self):
        editais, facs = dia._dados()
        r = dia.post_abertos(editais, facs, HOJE)
        self.assertIsNotNone(r)
        self.assertFalse(ck.DADO_NA_TELA.search(" ".join(r["slides"][0].textos)))

    def test_o_robo_reproduz_o_modelo_dos_posts_revisados(self):
        """Capa -> cartoes com faculdade, cidade, prazo e fonte -> chamada; um unico botao 'Ative o alerta gratis · link na bio'; legenda com lista e datas."""
        editais, facs = dia._dados()
        for f in (dia.post_abertos, dia.post_prazos, dia.post_exterior, dia.post_taxas, dia.post_documentos, dia.post_estados):
            r = f(editais, facs, HOJE)
            if r is None:
                continue
            tipos = [t["tipo"] for t in r["telas"]]
            self.assertEqual((tipos[0], tipos[-1]), ("capa", "chamada"), f.__name__)
            self.assertEqual(r["telas"][-1]["botao"], dia.BOTAO_ALERTA)
            self.assertEqual(r["legenda"].count(dia.CTA_LEGENDA), 1, f.__name__)
            self.assertLessEqual(len(r["legenda"].split("\n\n")[0].splitlines()), 4)
            self.assertTrue(len(r["alt"]) == len(r["slides"]) == len(r["telas"]))
        r = dia.post_abertos(editais, facs, HOJE)
        self.assertIsNotNone(r)
        cartoes = [c for t in r["telas"] if t["tipo"] == "cartoes" for c in t["cartoes"]]
        self.assertTrue(cartoes and all(c["nome"] and c["detalhe"] and c["prazo"].startswith("Inscrições até") and c["fonte"].startswith("edital, ") for c in cartoes))
        self.assertIn("• ", r["legenda"])

    def test_prazo_que_vence_em_menos_de_48h_sai_do_post_e_nao_derruba_o_post(self):
        hoje = "2026-11-10"
        amanha = (date.fromisoformat(hoje) + timedelta(days=1)).isoformat()
        em_2_dias = (date.fromisoformat(hoje) + timedelta(days=2)).isoformat()
        eds = [dict(EDITAIS[0], id="e990", inscricao_fim=amanha), dict(EDITAIS[1], id="e991", inscricao_fim=em_2_dias)]
        ids = {e["id"] for e in dia.abertos(eds, FACS, hoje)}
        self.assertNotIn("e990", ids)
        self.assertIn("e991", ids)

    def test_numero_no_fim_de_um_texto_nao_gruda_no_nome_da_faculdade_do_texto_seguinte(self):
        """'edital, p. 19' seguido do cartao 'Faculdades Pequeno Principe' nao e '19 faculdades' (falso positivo da regra b)."""
        post = _post(textos=["edital, p. 19\nFaculdades Pequeno Príncipe"])
        self.assertEqual([p for p in ck.checar(post, EDITAIS, FACS, HOJE, padrao=False) if p.startswith("(b)")], [])

    def test_o_robo_nao_grava_post_com_letra_pequena(self):
        """Antes da correção do rodapé (24 px), todo post do robô saía com letra abaixo de 26 px."""
        r, _ = dia.escolher(EDITAIS, FACS, "2026-11-10", padrao=False)
        self.assertEqual(_regras(ck.checar(r, EDITAIS, FACS, "2026-11-10"), "P6"), [])


if __name__ == "__main__":
    unittest.main()
