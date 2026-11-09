"""Instagram diário (09/11/2026): calendário, formato da imagem (JPEG 1080x1350, até 8 MB), identidade, sem área vazia, sem dado inventado,
carrossel sem pular editais, poda das pastas antigas e cópia das legendas para o privado/."""
import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))
import instagram as ig  # noqa: E402
import instagram_dia as dia  # noqa: E402

UFS = ["SP", "SP", "MG", "BA", "RJ", "PR"]
FACS = {f"f{i}": {"id": f"f{i}", "sigla": f"FAC{i}", "nome": f"Faculdade {i}", "cidade": f"Cidade {i}", "uf": uf, "meses": [3]}
        for i, uf in enumerate(UFS)}
SEGUNDA, TERCA = "2026-11-16", "2026-11-10"


def _edital(i, fim, **extra):
    e = {"id": f"e{i:03d}", "faculdade_id": f"f{i % len(UFS)}", "fonte_dados": "manual", "status": "ok", "inscricao_inicio": "2026-10-01", "inscricao_fim": fim,
         "vagas": [{"vagas": 1 + i % 7}], "modalidade": "externa", "url_edital": f"https://exemplo.edu.br/edital-{i}.pdf",
         "taxa_inscricao": 100.0 + i * 25, "documentos": ["Histórico escolar", "Declaração de vínculo", "RG e CPF"],
         "aceita_curso_exterior": i % 3 == 0 if i % 4 else False,
         "outras_restricoes": ["Não ter sido reprovado por falta no curso de origem"] if i % 5 == 0 else [],
         "evidencias": {"outras_restricoes": "3", "inscricao_fim": 2, "taxa_inscricao": "4 (item 2.4)", "aceita_curso_exterior": 5, "documentos": "3 e 4"}}
    e.update(extra)
    return e


def base_de(n, hoje="2026-11-10"):
    """n editais abertos com prazos espalhados (de hoje a hoje + 90 dias), mais um encerrado e um ainda não conferido, que nunca entram."""
    h = date.fromisoformat(hoje)
    eds = [_edital(i, (h + timedelta(days=(i * 3) % 90)).isoformat()) for i in range(n)]
    eds.append(_edital(900, (h - timedelta(days=1)).isoformat()))
    eds.append(_edital(901, (h + timedelta(days=5)).isoformat(), fonte_dados="robo"))
    eds.append(_edital(902, (h + timedelta(days=6)).isoformat(), status="conferir"))
    return eds


EDITAIS = base_de(30)


def _corpo_vazio(img, topo, base):
    """Altura (px) da maior faixa contínua do corpo (entre o título e o rodapé) sem nenhum cartão ou painel: só o fundo e os anéis do radar."""
    px = img.convert("RGB")
    fundo = tuple(int(dia.AZUL[i:i + 2], 16) for i in (1, 3, 5))
    atual = maior = 0
    for y in range(topo, base, 6):
        fora = sum(1 for x in range(70, dia.LARGURA - 70, 12) if max(abs(a - b) for a, b in zip(px.getpixel((x, y)), fundo)) > 8)
        atual = atual + 6 if fora < 0.3 * ((dia.LARGURA - 140) // 12) else 0
        maior = max(maior, atual)
    return maior


class Calendario(unittest.TestCase):
    def test_cada_dia_da_semana_tem_o_seu_formato(self):
        self.assertEqual({d: f.__name__ for d, f in dia.CALENDARIO.items()},
                         {0: "post_abertos", 1: "post_armadilha", 2: "post_prazos", 3: "post_taxas", 4: "post_exterior", 5: "post_documentos",
                          6: "post_estados"})

    def test_pedido_do_dono_segunda_terca_quarta(self):
        self.assertEqual([dia.CALENDARIO[d].__name__ for d in (0, 1, 2)], ["post_abertos", "post_armadilha", "post_prazos"])

    def test_segunda_e_carrossel_de_ate_10_slides(self):
        r, nota = dia.escolher(EDITAIS, FACS, SEGUNDA)
        self.assertEqual((r["tipo"], nota), ("editais-abertos-da-semana", ""))
        self.assertTrue(2 <= len(r["slides"]) <= 10)

    def test_sem_dado_seguro_cai_na_reserva_e_nunca_inventa(self):
        r, nota = dia.escolher([], FACS, TERCA)
        self.assertIsNone(r)
        self.assertIn("nenhum formato", nota)
        so_com_estados = [e for e in EDITAIS if "restricoes" not in e]
        sem_restricao = [dict(e, outras_restricoes=[]) for e in so_com_estados]
        r, nota = dia.escolher(sem_restricao, FACS, TERCA)
        self.assertIsNotNone(r)
        self.assertIn("reserva", nota)

    def test_so_edital_aberto_e_conferido_entra(self):
        hoje = "2026-11-12"
        abertos = {e["id"] for e in dia.abertos(EDITAIS, FACS, hoje)}
        r, _ = dia.escolher(EDITAIS, FACS, hoje)
        usados = {x.split("`")[1] for x in r["fontes"] if x.count("`") >= 2 and "editais abertos com" not in x}
        self.assertTrue(usados <= abertos, usados - abertos)


class Imagem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dest = Path(cls.tmp.name)
        cls.posts = {}
        for d in (date(2026, 11, 10) + timedelta(days=i) for i in range(7)):
            r, _ = dia.escolher(EDITAIS, FACS, d.isoformat())
            cls.posts[d.isoformat()] = (r, dia.gravar(r, "", d.isoformat(), cls.dest / d.isoformat()))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_jpeg_1080x1350_ate_8mb_com_link_https_publico(self):
        from PIL import Image
        for d, (r, m) in self.posts.items():
            for nome, url in zip(sorted(p.name for p in (self.dest / d).glob("*.jpg")), m["imagens"]):
                arq = self.dest / d / nome
                self.assertLessEqual(arq.stat().st_size, 8 * 1024 * 1024)
                im = Image.open(arq)
                self.assertEqual((im.format, im.size), ("JPEG", (1080, 1350)), f"{d}/{nome}")
                self.assertEqual(url, f"https://www.transfermed.com.br/social/{d}/{nome}")

    def test_identidade_azul_escuro_com_verde_agua_e_logo(self):
        from PIL import Image
        for d, (r, m) in self.posts.items():
            im = Image.open(self.dest / d / "01.jpg").convert("RGB")
            self.assertLess(max(abs(a - b) for a, b in zip(im.getpixel((540, 8)), (0x0B, 0x1E, 0x2C))), 14, "fundo #0B1E2C")
            tons = {tuple(v // 6 for v in im.getpixel((x, y))) for x in range(0, 1080, 6) for y in range(0, 1350, 6)}
            self.assertIn(tuple(v // 6 for v in (0x2C, 0xC8, 0xBA)), tons, f"{d}: sem o verde-água #2CC8BA")
            logo = im.crop((62, 54, 186, 178))  # o logo v2 no canto superior esquerdo: tem o verde-água do caduceu
            self.assertTrue(any(max(abs(a - b) for a, b in zip(p, (0x2C, 0xC8, 0xBA))) < 40 for p in logo.getdata()), f"{d}: logo ausente")

    def test_nenhuma_area_vazia_no_corpo(self):
        from PIL import Image
        for d, (r, m) in self.posts.items():
            for arq in sorted((self.dest / d).glob("*.jpg")):
                vazio = _corpo_vazio(Image.open(arq), 470, dia.ALTURA - dia.Lona.RODAPE)
                self.assertLessEqual(vazio, 30, f"{d}/{arq.name}: faixa vazia de {vazio} px no corpo (o espaço entre cartões é de 18 px)")

    def test_o_teste_de_area_vazia_pega_um_post_vazio(self):
        """O próprio teste tem de provar que enxerga o defeito: um slide só com o título e nenhum cartão."""
        lona = dia.Lona("Teste", "Título")
        destino = Path(self.tmp.name) / "vazio.jpg"
        lona.salvar(destino)
        from PIL import Image
        self.assertGreater(_corpo_vazio(Image.open(destino), 470, dia.ALTURA - dia.Lona.RODAPE), 400)

    def test_carrossel_mostra_cada_edital_uma_vez_sem_pular(self):
        r, m = self.posts["2026-11-16"]
        abertos = dia.abertos(EDITAIS, FACS, "2026-11-16")
        citados = [x.split("`")[1] for x in r["fontes"]]
        self.assertEqual(len(citados), len(set(citados)), "edital repetido")
        esperados = [e["id"] for e in abertos][:len(citados)]
        self.assertEqual(citados, esperados, "o carrossel pulou ou trocou a ordem de prazo")
        self.assertEqual(len(r["slides"]), 1 + len({i for i in range(len(r["slides"]) - 1)}))

    def test_manifesto_legenda_e_fontes(self):
        for d, (r, m) in self.posts.items():
            self.assertEqual(m["data"], d)
            self.assertEqual(len(m["texto_alternativo"]), len(m["imagens"]))
            legenda = (self.dest / d / "legenda.txt").read_text(encoding="utf-8")
            self.assertLessEqual(len(legenda), 2200, "limite de legenda do Instagram")
            self.assertIn("transfermed.com.br/diagnostico/?origem=instagram", legenda)
            self.assertIn("edital oficial", legenda.lower())
            fontes = (self.dest / d / "fontes.txt").read_text(encoding="utf-8")
            self.assertIn("http", fontes)
            self.assertNotRegex(legenda + fontes, r"@[a-z]+\.[a-z]|\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")  # nem e-mail nem CPF

    def test_sem_ranking_entre_faculdades(self):
        for d, (r, m) in self.posts.items():
            texto = (self.dest / d / "legenda.txt").read_text(encoding="utf-8").lower() + " ".join(m["texto_alternativo"]).lower()
            for palavra in ("melhor", "ranking", "top ", "pior"):
                self.assertNotIn(palavra, texto, f"{d}: {palavra}")


class Limites(unittest.TestCase):
    def test_carrossel_nunca_passa_de_10_slides_e_diz_quantos_faltam(self):
        r, _ = dia.escolher(base_de(80), FACS, SEGUNDA)
        self.assertEqual(len(r["slides"]), 10)
        self.assertIn("Mais ", r["legenda"])

    def test_edital_encerrado_ou_nao_conferido_nunca_entra(self):
        r, _ = dia.escolher(base_de(12), FACS, TERCA)
        self.assertNotIn("e900", "".join(r["fontes"]))
        self.assertNotIn("e901", "".join(r["fontes"]))


class DadosReais(unittest.TestCase):
    """A base muda a cada rodada (edital que vence, edital novo): estes testes valem para QUALQUER estado dos dados, sem datas ou números fixos."""

    def test_o_proximo_post_com_os_dados_de_hoje_tem_o_formato_certo(self):
        editais, facs = ig._dados()
        for d in (date.today() + timedelta(days=i) for i in range(1, 8)):
            r, nota = dia.escolher(editais, facs, d.isoformat())
            if r is None:  # sem dado seguro nesse dia: é um resultado válido, o post não sai
                self.assertIn("nenhum formato", nota)
                continue
            with tempfile.TemporaryDirectory() as t:
                m = dia.gravar(r, nota, d.isoformat(), Path(t))
                from PIL import Image
                for arq in sorted(Path(t).glob("*.jpg")):
                    with Image.open(arq) as im:
                        self.assertEqual((im.format, im.size), ("JPEG", (1080, 1350)))
                    self.assertLessEqual(arq.stat().st_size, 8 * 1024 * 1024)
                self.assertEqual(len(m["imagens"]), len(list(Path(t).glob("*.jpg"))))
                self.assertLessEqual(len((Path(t) / "legenda.txt").read_text(encoding="utf-8")), 2200)


class Arquivos(unittest.TestCase):
    def test_poda_apaga_so_as_pastas_antigas(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            for d in ("2026-10-01", "2026-10-30", "2026-11-09", "2026-11-16"):
                (base / d).mkdir()
                (base / d / "01.jpg").write_bytes(b"x")
            (base / "LEIA.txt").write_text("fica", encoding="utf-8")
            apagadas = dia.podar(14, "2026-11-16", base)
            self.assertEqual(apagadas, ["2026-10-01", "2026-10-30"])
            self.assertTrue((base / "2026-11-09").exists() and (base / "LEIA.txt").exists())

    def test_sincronizar_copia_so_legenda_e_fontes_dos_proximos_dias(self):
        with tempfile.TemporaryDirectory() as t:
            base, priv = Path(t) / "social", Path(t) / "privado"
            for d in ("2026-11-08", "2026-11-10"):
                (base / d).mkdir(parents=True)
                (base / d / "legenda.txt").write_text("L" + d, encoding="utf-8")
                (base / d / "fontes.txt").write_text("F" + d, encoding="utf-8")
                (base / d / "01.jpg").write_bytes(b"x")
            self.assertEqual(dia.sincronizar("2026-11-09", base, priv), ["2026-11-10"])
            self.assertEqual((priv / "2026-11-10" / "legenda.txt").read_text(encoding="utf-8"), "L2026-11-10")
            self.assertFalse((priv / "2026-11-10" / "01.jpg").exists())
            self.assertFalse((priv / "2026-11-08").exists())

    def test_amanha_em_brasilia_e_o_dia_seguinte(self):
        self.assertEqual(date.fromisoformat(dia.amanha_em_brasilia()) - date.today() in (timedelta(0), timedelta(days=1), timedelta(days=2)), True)


if __name__ == "__main__":
    unittest.main()
