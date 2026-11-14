"""B4 (12/11/2026): painel "O robô hoje" (só a rodada do dia, com a hora real), cartão de alerta com estados e números da home."""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import alertas  # noqa: E402
import gerar_site  # noqa: E402

HOJE = "2026-11-13"
F = {"a": {"id": "a", "nome": "Faculdade A", "sigla": "FA", "cidade": "X", "uf": "SP"}}


def retratos(utc="2026-11-13T09:00:20Z", ok=HOJE, paginas=3, pdfs=2):
    return {"atualizado_em": HOJE, "executado_em_utc": utc,
            "paginas": {f"p{i}": {"ultimo_ok": ok} for i in range(paginas)} | {"velha": {"ultimo_ok": "2026-11-01"}},
            "pdfs": {f"d{i}": {"ultimo_ok": ok} for i in range(pdfs)}}


def execucao(utc="2026-11-13T09:17:30Z", **kw):
    return {"executado_em": "2026-11-13T09:17:30", "executado_em_utc": utc, "novos": [], "atualizados": [], "retificacoes": [], **kw}


class HoraDaRodada(unittest.TestCase):
    def test_utc_vira_brasilia(self):
        self.assertEqual(gerar_site._quando_brasilia("2026-11-13T09:17:30Z"), ("2026-11-13", "06:17"))
        self.assertEqual(gerar_site._quando_brasilia("2026-11-13T02:00:00Z"), ("2026-11-12", "23:00"), "o dia é o de Brasília: 02h UTC de 13/11 ainda é 12/11 aqui")

    def test_texto_ausente_ou_fora_do_formato(self):
        for ruim in (None, "", "ontem", "2026-11-13T09:17:30"):
            self.assertEqual(gerar_site._quando_brasilia(ruim), (None, None))

    def test_a_proxima_leitura_e_a_do_workflow_do_radar(self):
        yml = (gerar_site.PASTA / ".github" / "workflows" / "radar.yml").read_text(encoding="utf-8")
        minuto, hora_utc = re.search(r'cron:\s*"(\d+) (\d+) \* \* \*"', yml).groups()
        brasilia = (int(hora_utc) - 3) % 24
        self.assertEqual(gerar_site.PROXIMA_LEITURA, f"{brasilia:02d}h{int(minuto):02d}")


class EventosDoRobo(unittest.TestCase):
    def test_sem_rodada_hoje_nao_ha_painel(self):
        self.assertEqual(gerar_site.eventos_do_robo(F, HOJE, {}, {}), ([], False, False))
        ontem = gerar_site.eventos_do_robo(F, HOJE, execucao("2026-11-12T09:17:30Z", novos=["X: http://a"]), retratos("2026-11-12T09:00:00Z"))
        self.assertEqual(ontem, ([], False, False), "dado de ontem nunca aparece como se fosse de hoje")
        self.assertEqual(gerar_site.painel_robo(F, HOJE, "", {}, {}), "")

    def test_arquivo_sem_o_campo_novo_nao_quebra(self):
        antigo = {"executado_em": "2026-11-13T09:17:30", "novos": ["X: http://a"], "atualizados": [], "retificacoes": []}
        self.assertEqual(gerar_site.eventos_do_robo(F, HOJE, antigo, {"atualizado_em": HOJE, "paginas": {}, "pdfs": {}}), ([], False, False))

    def test_dia_quieto(self):
        linhas, mudou, lista = gerar_site.eventos_do_robo(F, HOJE, execucao(), retratos())
        self.assertFalse(mudou)
        self.assertFalse(lista)
        self.assertEqual(linhas[0], ("06:00", "Leu <b>3</b> páginas de faculdades e <b>2</b> PDFs de edital"), "só conta o que foi lido hoje")
        html = gerar_site.painel_robo(F, HOJE, "", execucao(), retratos())
        self.assertIn("Nenhuma mudança nos editais hoje · próxima leitura amanhã às 06h17", re.sub(r"<[^>]+>", "", html))
        self.assertIn('data-dia="2026-11-13" data-rodada="2026-11-13T09:17:30Z"', html, "o navegador decide o texto pelo dia de Brasília (E1.2)")
        self.assertIn("data-robo-titulo", html)
        self.assertNotIn("ver tudo o que mudou", html)
        self.assertIn("<time>06:17</time>", html)

    def test_com_mudancas_tem_link_so_se_houver_lista(self):
        ex = execucao(retificacoes=["Faculdade A (FA): http://x/r.pdf (1 edital(is) marcado(s))"], novos=["Faculdade B: http://x/n.pdf"])
        linhas, mudou, lista = gerar_site.eventos_do_robo(F, HOJE, ex, retratos())
        self.assertTrue(mudou and lista)
        textos = [t for _, t in linhas]
        self.assertIn("Faculdade A (FA): <mark>retificação publicada</mark>", textos)
        self.assertIn("Faculdade B: <mark>edital novo, em conferência</mark>", textos)
        html = gerar_site.painel_robo(F, HOJE, "", ex, retratos())
        self.assertIn('<a href="editais/#detectados">ver tudo o que mudou</a>', html)
        self.assertNotIn("Nenhuma mudança", html)
        so_retificacao = gerar_site.painel_robo(F, HOJE, "", execucao(retificacoes=["Faculdade A: http://x/r.pdf"]), retratos())
        self.assertNotIn("ver tudo o que mudou", so_retificacao, "sem lista de detectados, sem link")

    def test_no_maximo_4_linhas(self):
        ex = execucao(novos=[f"Faculdade {i}: http://x/{i}.pdf" for i in range(9)])
        linhas, _, _ = gerar_site.eventos_do_robo(F, HOJE, ex, retratos())
        self.assertEqual(len(linhas), 4)
        self.assertIn("<b>7</b> outras mudanças", linhas[-1][1])

    def test_nome_de_faculdade_e_escapado(self):
        linhas, _, _ = gerar_site.eventos_do_robo(F, HOJE, execucao(novos=["<b>X</b> & Cia: http://x/n.pdf"]), retratos())
        self.assertIn("&lt;b&gt;X&lt;/b&gt; &amp; Cia", linhas[-1][1])

    def test_so_radar_sem_monitor(self):
        linhas, mudou, _ = gerar_site.eventos_do_robo(F, HOJE, execucao(), {})
        self.assertEqual([h for h, _ in linhas], ["06:17"])
        self.assertFalse(mudou)


class CartaoDeAlertaDaHome(unittest.TestCase):
    HTML = gerar_site.cartao_alerta_home("./")

    def test_chips_e_consentimento(self):
        for chip in ("SP", "MG", "BA", "RJ", "PR", "Exterior"):
            self.assertIn(f"<span>{chip}</span>", self.HTML)
        self.assertEqual(self.HTML.count('name="estado"'), 6)
        self.assertNotIn("checked", self.HTML, "nem chip nem consentimento vêm marcados")
        self.assertIn("Ativar alerta grátis", self.HTML)
        self.assertIn("O que vou receber", self.HTML)
        self.assertIn(gerar_site.e(gerar_site.CONSENTIMENTO), self.HTML)
        self.assertIn('data-contexto="inicio"', self.HTML)

    def test_na_home_abaixo_do_hero_e_antes_dos_numeros(self):
        html = (gerar_site.DOCS / "index.html").read_text(encoding="utf-8")
        self.assertLess(html.index('class="heroi v3"'), html.index('id="form-alerta"'))
        self.assertLess(html.index('id="form-alerta"'), html.index('aria-label="Números da base"'))
        ids = re.findall(r'\sid="([^"]+)"', html)
        self.assertEqual(sorted({i for i in ids if ids.count(i) > 1}), [], "ids repetidos na home")


class AlertaPorEstado(unittest.TestCase):
    FAC_SP = {"uf": "SP", "tipo": "particular"}
    FAC_BA = {"uf": "BA", "tipo": "particular"}

    def m(self, ed, p, fac):
        return alertas.motivos({"modalidade": "externa", **ed}, {"curso": "medicina", **p}, fac)

    def test_sem_estados_avisa_de_todos(self):
        self.assertNotIn("estado", self.m({}, {}, self.FAC_BA))

    def test_so_os_estados_escolhidos(self):
        p = {"estados": ["SP", "MG"]}
        self.assertNotIn("estado", self.m({}, p, self.FAC_SP))
        self.assertIn("estado", self.m({}, p, self.FAC_BA))

    def test_chip_exterior_traz_quem_aceita_curso_do_exterior(self):
        p = {"estados": ["EXTERIOR"]}
        self.assertNotIn("estado", self.m({"aceita_curso_exterior": True}, p, self.FAC_BA))
        self.assertNotIn("estado", self.m({"modalidade": "exterior"}, p, self.FAC_BA))
        self.assertIn("estado", self.m({"aceita_curso_exterior": False}, p, self.FAC_BA))
        self.assertIn("estado", self.m({}, p, self.FAC_BA), "sem confirmar que aceita, não entra")

    def test_estado_e_exterior_juntos(self):
        p = {"estados": ["SP", "EXTERIOR"]}
        self.assertNotIn("estado", self.m({}, p, self.FAC_SP))
        self.assertNotIn("estado", self.m({"aceita_curso_exterior": True}, p, self.FAC_BA))
        self.assertIn("estado", self.m({"aceita_curso_exterior": False}, p, self.FAC_BA))


class NumerosDaHomeComRotulo(unittest.TestCase):
    """Um número por conceito, com o rótulo dizendo o que conta (faculdades x editais)."""

    def test_rotulos_explicitos_e_numeros_iguais_aos_da_lista(self):
        html = (gerar_site.DOCS / "index.html").read_text(encoding="utf-8")
        main = html[html.index("<main"):html.index("</main>")]
        lista = main[main.index('id="lista3"'):]
        itens = len(re.findall(r"<li(?: hidden)?><a ", lista[:lista.index("</ul>")]))
        mostrar = re.search(r'id="lista3-mais">Mostrar todas as (\d+) faculdades</button>', main)
        self.assertTrue(mostrar, "o botão diz que são faculdades")
        self.assertEqual(int(mostrar.group(1)), itens)
        editais = int(re.search(r'href="editais/">Ver os (\d+) editais abertos</a>', main).group(1))
        n_abertos = int(re.search(r'id="n-abertos"[^>]*>(\d+)</b><span>editais com inscrição aberta hoje</span>', main).group(1))
        self.assertEqual(editais, n_abertos, "editais abertos: o mesmo número no botão e na faixa")
        self.assertNotIn("com inscrições abertas hoje", main)


if __name__ == "__main__":
    unittest.main()
