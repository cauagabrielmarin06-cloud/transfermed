"""Instagram de 24/11/2026: o gerador publicou um post reprovado (imagem "Portador de diploma" com legenda "transferência", e pilar "armadilha"
sem armadilha concreta). Regras novas, na origem e na checagem automática:
(1) (M) a legenda usa a mesma modalidade da imagem;
(2) (R) post de armadilha só sai com um item real do Raio-X, com página; sem isso o gerador troca de pauta.
Dados de teste fixos (tests/test_instagram_dia.py) e o post reprovado guardado em tests/fixtures; nada de edital real com prazo."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))
import instagram_checagem as ck  # noqa: E402
import instagram_dia as dia  # noqa: E402
from tests.test_instagram_dia import EDITAIS, FACS, RESULTADOS, TERCA  # noqa: E402

REPROVADO = Path(__file__).resolve().parent / "fixtures" / "instagram_post_reprovado_2026-11-24"
SOCIAL = PASTA / "docs" / "social"


def _editais(**mud_e900):
    eds = copy.deepcopy(EDITAIS)
    next(e for e in eds if e["id"] == "e900").update(mud_e900)
    return eds


def _armadilha(editais=None, resultados=None):
    return dia.post_armadilha(editais or EDITAIS, FACS, TERCA, resultados=RESULTADOS if resultados is None else resultados)


def _problemas(r, editais=None, resultados=None):
    return ck.checar(r, editais or EDITAIS, FACS, TERCA, padrao=False, resultados=RESULTADOS if resultados is None else resultados, pasta_social=Path(tempfile.gettempdir()) / "sem-vizinhos")


class PostReprovadoDe24_11(unittest.TestCase):
    """O post de 24/11 exatamente como foi gerado: a checagem nova TEM de reprová-lo (e, antes dela, ele passava)."""

    def setUp(self):
        self.post = ck.post_de_pasta(REPROVADO)
        e = dict(EDITAIS[0], id="c396ff22dfa7", faculdade_id="f0", modalidade="portador_diploma", inscricao_fim="2026-12-07")
        self.editais = [e]

    def test_a_legenda_fala_em_transferencia_para_um_edital_de_portador_de_diploma(self):
        p = [x for x in ck.checar(self.post, self.editais, FACS, "2026-11-24", padrao=False, resultados=[]) if x.startswith("(M)")]
        self.assertEqual(len(p), 2, p)
        self.assertTrue(any("legenda não nomeia essa modalidade" in x and "Portador de diploma" in x for x in p), p)
        self.assertTrue(any("fala em “transferência”" in x for x in p), p)

    def test_a_armadilha_nao_tem_item_do_raio_x(self):
        p = [x for x in ck.checar(self.post, self.editais, FACS, "2026-11-24", padrao=False, resultados=[]) if x.startswith("(R)")]
        self.assertEqual(len(p), 1, p)
        self.assertIn("sem item real do Raio-X", p[0])


class LegendaComAModalidadeDaImagem(unittest.TestCase):
    def test_cada_modalidade_e_nomeada_igual_na_imagem_e_na_legenda(self):
        casos = {"portador_diploma": ("Portador de diploma", "portador de diploma"), "externa": ("Transferência externa", "transferência externa"),
                 "interna": ("Transferência interna", "transferência interna"), "exterior": ("Para quem estuda no exterior", "transferência para quem estuda no exterior")}
        for mod, (na_imagem, na_legenda) in casos.items():
            r = _armadilha(_editais(modalidade=mod))
            self.assertIsNotNone(r, mod)
            self.assertIn(na_imagem, " ".join(r["textos"]), mod)
            self.assertIn(na_legenda, r["legenda"].lower(), mod)
            self.assertEqual(_problemas(r, _editais(modalidade=mod)), [], mod)

    def test_portador_de_diploma_nunca_vira_transferencia_na_legenda(self):
        r = _armadilha(_editais(modalidade="portador_diploma"))
        legenda = r["legenda"].replace("#transferenciamedicina", "").replace("#transferenciaexterna", "")
        self.assertNotRegex(legenda.lower(), r"\btransfer[êe]ncia\b")

    def test_a_checagem_barra_legenda_e_imagem_com_modalidades_diferentes(self):
        eds = _editais(modalidade="portador_diploma")
        r = _armadilha(eds)
        r["legenda"] = r["legenda"].replace("no processo para portador de diploma", "na transferência")
        p = _problemas(r, eds)
        self.assertEqual(len([x for x in p if x.startswith("(M)")]), 2, p)

    def test_modalidade_externa_com_legenda_de_diploma_tambem_e_barrada(self):
        r = _armadilha(_editais(modalidade="externa"))
        r["legenda"] = r["legenda"].replace("na transferência externa", "no processo para portador de diploma")
        p = [x for x in _problemas(r) if x.startswith("(M)")]
        self.assertTrue(any("Transferência externa" in x for x in p), p)


class ArmadilhaSoComItemRealDoRaioX(unittest.TestCase):
    def test_com_item_real_gera_a_armadilha_com_as_duas_paginas_e_passa_na_checagem(self):
        r = _armadilha()
        self.assertEqual(r["tipo"], "armadilha-do-edital")
        self.assertEqual(r["gancho"], "FAC0: 10 vagas, 3 classificados")
        self.assertEqual([(f["campo"], f["pagina"]) for f in r["fatos"]], [("raio_x_vagas", "2"), ("raio_x_classificados", "4")])
        self.assertIn("edital, p. 2 · resultado, p. 4", " ".join(r["textos"]))
        self.assertEqual(_problemas(r), [])

    def test_sem_item_do_raio_x_o_gerador_troca_de_pauta(self):
        self.assertIsNone(_armadilha(resultados=[]))
        with mock.patch.object(ck, "_resultados_reais", return_value=[]):
            r, nota = dia.escolher(EDITAIS, FACS, TERCA, padrao=False)
        self.assertNotEqual(r["tipo"], "armadilha-do-edital")
        self.assertIn("post_armadilha: sem dado seguro", nota)
        self.assertIn("usou a reserva", nota)

    def test_nada_de_armadilha_com_taxa_e_prazo_de_edital_aberto(self):
        """O post de 24/11 era isto: taxa e prazo de um edital aberto. Edital aberto não tem item de Raio-X, então não vira armadilha."""
        aberto = next(e for e in EDITAIS if e["taxa_inscricao"] and e["inscricao_fim"] >= TERCA)
        resultados = [dict(RESULTADOS[0], edital_id=aberto["id"])]
        self.assertIsNone(_armadilha(resultados=resultados))

    def test_item_incompleto_nao_serve(self):
        def com(**mudanca):
            r = copy.deepcopy(RESULTADOS)
            for chave, valor in mudanca.items():
                grandeza, campo = chave.split("__")
                nome = {"vagas_do_edital": "vagas_ofertadas", "classificados_dentro_das_vagas": "aprovados"}[grandeza]
                r[0]["numeros"][nome][campo] = valor
            return r
        for ruim in (com(vagas_do_edital__pagina=""), com(classificados_dentro_das_vagas__pagina="4, 5 e 6"), com(classificados_dentro_das_vagas__fonte_url=""),
                     com(vagas_do_edital__fonte_url="http://sem-https.br/x.pdf"), com(classificados_dentro_das_vagas__valor=10), com(classificados_dentro_das_vagas__valor=0),
                     com(classificados_dentro_das_vagas__grandeza="a_revisar")):
            self.assertIsNone(_armadilha(resultados=ruim), ruim[0]["numeros"])

    def test_edital_em_conferir_nao_serve(self):
        self.assertIsNone(_armadilha(_editais(status="conferir", conferir_campos={"vagas": "tabela confusa"})))
        self.assertIsNone(_armadilha(_editais(fonte_dados="robo")))

    def test_a_checagem_barra_armadilha_sem_o_raio_x_ou_com_pagina_trocada(self):
        r = _armadilha()
        self.assertEqual(_problemas(r), [])
        self.assertTrue([x for x in _problemas(r, resultados=[]) if x.startswith("(R)")])
        trocada = dict(r, fatos=[dict(f) for f in r["fatos"]])   # (o post tem imagens: não dá para deepcopy)
        trocada["fatos"][1]["pagina"] = "9"
        self.assertTrue([x for x in _problemas(trocada) if x.startswith("(R)")], "página diferente da do Raio-X")
        sem_campo = dict(r, fatos=[dict(f, campo="inscricao_fim") for f in r["fatos"]])
        self.assertTrue([x for x in _problemas(sem_campo) if x.startswith("(R)")], "fato que não é do Raio-X")

    def test_pauta_curada_pelo_dono_fica_fora_da_regra(self):
        r = _armadilha()
        r["fatos"] = [{"faculdade": "FAC0", "edital": "e900", "campo": "documentos", "pagina": "4"}]
        self.assertTrue([x for x in _problemas(r) if x.startswith("(R)")])
        for marca in ({"curado": True}, {"revisado": True}, {"pauta": "BANCO #6"}):
            self.assertEqual([x for x in _problemas(dict(r, **marca)) if x.startswith("(R)")], [], marca)

    def test_o_mesmo_item_nao_volta_em_outro_post(self):
        with tempfile.TemporaryDirectory() as t:
            pasta = Path(t) / "2026-11-03"
            pasta.mkdir()
            (pasta / "post.json").write_text(json.dumps({"tipo": "numeros-do-raio-x", "usados": ["e900"]}), encoding="utf-8")
            with mock.patch.object(dia, "SOCIAL", Path(t)):
                self.assertIsNone(_armadilha())
                self.assertEqual(dia._ja_usados_na_armadilha(TERCA), {"e900"})
                self.assertEqual(dia._ja_usados_na_armadilha("2026-11-03"), set(), "a pasta do próprio dia pode ser regerada")


class DiaSemPostNaoDeixaPostVelho(unittest.TestCase):
    def test_sem_post_apaga_o_post_reprovado_que_estava_na_pasta(self):
        with tempfile.TemporaryDirectory() as t:
            pasta = Path(t) / TERCA
            pasta.mkdir()
            for nome in ("post.json", "legenda.txt", "fontes.txt", "01.jpg"):
                (pasta / nome).write_text("velho", encoding="utf-8")
            so_conferir = [dict(e, status="conferir") for e in EDITAIS]
            with mock.patch.object(dia, "SOCIAL", Path(t)), mock.patch.object(dia, "PRIVADO", Path(t) / "sem_privado" / "instagram"), \
                    mock.patch.object(ck, "_resultados_reais", return_value=[]):
                situacao, _ = dia.gerar_dia(TERCA, (so_conferir, FACS))
            self.assertEqual(situacao, "sem-post")
            self.assertEqual(sorted(p.name for p in pasta.iterdir()), ["SEM_POST.txt"])


class PostsDe24a29DeNovembro(unittest.TestCase):
    """Os arquivos de docs/social de 24 a 29/11 (regerados com o gerador corrigido) passam nas duas regras novas, com os dados reais de cada dia."""

    def test_nenhum_post_de_24_a_29_tem_problema_de_modalidade_ou_de_armadilha(self):
        editais, facs = dia._dados()
        existentes = 0
        for d in ("2026-11-24", "2026-11-25", "2026-11-26", "2026-11-27", "2026-11-28", "2026-11-29"):
            pasta = SOCIAL / d
            if not (pasta / "post.json").exists():
                self.assertTrue((pasta / "SEM_POST.txt").exists() or not pasta.exists(), d)
                self.assertFalse(list(pasta.glob("*.jpg")) if pasta.exists() else [], f"{d}: sem post, mas com imagem")
                continue
            existentes += 1
            post = ck.post_de_pasta(pasta)
            ruins = [x for x in ck.checar(post, editais, facs, d, padrao=False) if x.startswith(("(M)", "(R)"))]
            self.assertEqual(ruins, [], d)
        self.assertGreaterEqual(existentes, 1)


if __name__ == "__main__":
    unittest.main()
