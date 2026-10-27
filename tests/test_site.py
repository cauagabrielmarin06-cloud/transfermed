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

    def test_titulos_ate_70_caracteres(self):
        import html, re
        for p in self.paginas():
            t = html.unescape(re.search(r"<title>(.*?)</title>", p.read_text(encoding="utf-8"), re.S).group(1))
            self.assertLessEqual(len(t), 70, f"{p}: {t}")

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
        s = (self.PASTA / "index.html").read_text(encoding="utf-8")
        self.assertIn(f'<svg viewBox="{gerar_site.VISTA_BRASIL}"', s)
        self.assertIn('aria-pressed="true">Brasil</button>', s)
        for nome in ("Bahia", "Minas Gerais", "Mato Grosso do Sul", "São Paulo"):
            self.assertIn(f'aria-pressed="false">{nome}</button>', s)

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
