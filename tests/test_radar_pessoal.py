"""13/11/2026 · Parte C: radar pessoal da home. O que o gerador entrega (a lógica do navegador é testada em qa/radar_pessoal.mjs)."""
import re
import sys
import unittest
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))
import gerar_site  # noqa: E402

F = {"a": {"id": "a", "nome": "Faculdade A", "sigla": "FA", "cidade": "X", "uf": "SP"}}
HOJE = "2026-11-12"


class PaginaDoCampo(unittest.TestCase):
    def test_aceita_inteiro_intervalo_e_texto_com_pagina(self):
        for ev, esperado in ((3, 3), ("1-2", 1), ("p. 4", 4), ("2, 3", 2)):
            self.assertEqual(gerar_site.pagina_do_campo({"evidencias": {"vagas": ev}}, "vagas"), esperado, ev)

    def test_sem_numero_claro_nao_chuta(self):
        for ev in (None, "", "no anexo", 0, -2, True):
            self.assertIsNone(gerar_site.pagina_do_campo({"evidencias": {"vagas": ev}}, "vagas"), repr(ev))
        self.assertIsNone(gerar_site.pagina_do_campo({}, "vagas"))

    def test_so_entra_nos_dados_quando_ha_pagina(self):
        js = (gerar_site.DOCS / "dados.js").read_text(encoding="utf-8")
        self.assertIn('"pv":', js, "o cartão do ponto precisa da página do quadro de vagas para 'Ver no PDF, p. X'")
        self.assertNotIn('"pv":null', js)


class FatoDoDia(unittest.TestCase):
    EXEC = {"executado_em_utc": "2026-11-12T12:00:00Z", "novos": [], "atualizados": [], "retificacoes": []}
    RETR = {"executado_em_utc": "2026-11-12T12:05:00Z", "paginas": {"p1": {"ultimo_ok": HOJE}, "p2": {"ultimo_ok": HOJE}, "velha": {"ultimo_ok": "2026-11-01"}}}

    def test_retificacao_tem_prioridade_e_link(self):
        ex = {**self.EXEC, "retificacoes": ["UVA: http://x.edu/ret.pdf"], "novos": ["Outra: http://y.edu/n.pdf"]}
        html, dia = gerar_site.fato_do_dia(F, HOJE, ex, self.RETR)
        self.assertIn("UVA", html)
        self.assertIn("retificação publicada", html)
        self.assertIn('href="http://x.edu/ret.pdf"', html)
        self.assertEqual(dia, HOJE)

    def test_sem_mudanca_conta_as_paginas_lidas_hoje(self):
        html, dia = gerar_site.fato_do_dia(F, HOJE, self.EXEC, self.RETR)
        self.assertIn("<b>2</b> páginas de faculdades", html)  # a página de 01/11 não conta
        self.assertIn("Nenhuma mudança nos editais", html)
        self.assertEqual(dia, HOJE)

    def test_sem_rodada_hoje_nao_inventa_fato(self):
        html, dia = gerar_site.fato_do_dia(F, "2026-11-14", self.EXEC, self.RETR)
        self.assertEqual(dia, "")
        self.assertIn("todo dia", html)
        self.assertNotIn("Hoje", html)

    def test_nome_com_html_sai_escapado(self):
        ex = {**self.EXEC, "novos": ["<script>x</script>: http://y.edu/n.pdf"]}
        html, _ = gerar_site.fato_do_dia(F, HOJE, ex, self.RETR)
        self.assertNotIn("<script>", html)


class RadarPessoalNoHtml(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = gerar_site.radar_pessoal(F, HOJE)
        cls.home = (gerar_site.DOCS / "index.html").read_text(encoding="utf-8")

    def test_uma_pergunta_com_campo_rotulado_e_combobox(self):
        self.assertIn('<label class="rp-pergunta" for="rp-cidade">De onde você quer sair?</label>', self.html)
        self.assertIn('role="combobox"', self.html)
        self.assertIn('aria-controls="rp-lista"', self.html)

    def test_sem_javascript_o_campo_fica_desligado_com_aviso(self):
        self.assertRegex(self.html, r'<input id="rp-cidade"[^>]*\bdisabled>')
        self.assertIn("<noscript>", self.html)
        self.assertIn('href="editais/"', self.html)
        self.assertNotRegex(self.html, r'<div class="rp" id="rp"[^>]*hidden', "escondido pelo HTML geraria salto de layout (CLS) quando o JS liga")

    def test_doze_periodos_em_botoes_de_radio_nunca_marcados(self):
        pilulas = re.findall(r'<input type="radio" name="rp-periodo" value="(\d+)"([^>]*)>', self.html)
        self.assertEqual([int(v) for v, _ in pilulas], list(range(1, 13)))
        self.assertTrue(all("checked" not in resto for _, resto in pilulas))

    def test_controle_de_distancia_de_100_a_1500_km_e_qualquer_distancia(self):
        self.assertRegex(self.html, r'<input type="range" id="rp-km" min="100" max="1600" step="50" value="400"')
        js = (gerar_site.DOCS / "assets" / "app.js").read_text(encoding="utf-8")
        self.assertIn(f"const QUALQUER_KM = {gerar_site.KM_MAX};", js, "o fim do controle é 'qualquer distância' nos dois lados")
        self.assertEqual((gerar_site.KM_MIN, gerar_site.KM_MAX - 100), (100, 1500))

    def test_selo_conta_as_faculdades_reais(self):
        self.assertIn("<b>1</b> faculdades", self.html)  # N vem de len(F), nunca de número fixo
        self.assertIn(f'<b>{len(__import__("json").loads((PASTA / "data" / "faculdades.json").read_text(encoding="utf-8")))}</b> faculdades', self.home)

    def test_resultado_tem_os_textos_do_plano(self):
        for t in ("Me avise quando abrir mais uma assim", "Seu radar fica salvo neste aparelho", "Mudou de ideia?", "Aumente a distância ou ative o alerta",
                  "Em que período você está?", "Até onde você vai?"):
            self.assertIn(t, self.html)

    def test_home_tem_o_radar_pessoal_antes_do_mapa_e_os_atalhos_depois(self):
        i, j, k = (self.home.index(t) for t in ('id="rp"', 'figure class="r3"', 'class="quadros"'))
        self.assertTrue(i < j < k)
        self.assertIn('href="exterior/"', self.home)

    def test_consentimento_do_alerta_da_home_continua_desmarcado(self):
        m = re.search(r'<input[^>]*id="consentimento"[^>]*>', self.home)
        self.assertIsNotNone(m)
        self.assertNotIn("checked", m.group(0))


class MesmaContaNoJsENoRobo(unittest.TestCase):
    """periodoStatus (app.js) tem de seguir a regra do alertas.motivos: o aluno vê no site o mesmo recorte que recebe por e-mail."""

    def test_regra_do_periodo_esta_nos_dois_lados(self):
        js = (gerar_site.DOCS / "assets" / "app.js").read_text(encoding="utf-8")
        py = (PASTA / "alertas.py").read_text(encoding="utf-8")
        self.assertIn("const alvo = [semestre, semestre + 1]", js)
        self.assertIn('alvo = {p["semestre"], p["semestre"] + 1}', py)
        self.assertIn("periodoStatus(e, p.semestre).s === 'nao'", js, "o diagnóstico usa a mesma função do radar pessoal")


if __name__ == "__main__":
    unittest.main()
