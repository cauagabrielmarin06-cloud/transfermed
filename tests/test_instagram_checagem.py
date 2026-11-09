"""Checagem que trava o post do Instagram (instagram_checagem.py, 09/11/2026).

Nasceu do post de 10/11, que dizia "Leia antes de pagar a taxa" a partir de um edital em "conferir" que não cita taxa. O post antigo está em
tests/fixtures/instagram_post_antigo_2026-11-10 e TEM de ser reprovado; o novo, gerado agora, tem de passar."""
import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))
import instagram_checagem as ck  # noqa: E402
import instagram_dia as dia  # noqa: E402
from tests.test_instagram_dia import EDITAIS, FACS, TERCA, _edital  # noqa: E402

ANTIGO = Path(__file__).resolve().parent / "fixtures" / "instagram_post_antigo_2026-11-10"
HOJE = "2026-11-10"


def _unip_como_estava():
    """O edital da UNIP como estava nos dados em 09/11/2026: status conferir, sem taxa conferida, com a observação do número do edital."""
    f = dict(FACS["f0"], id="unip-campinas", sigla="UNIP", cidade="Campinas", uf="SP")
    e = _edital(1, "2027-02-12", id="39c910ec7b14", faculdade_id="unip-campinas", status="conferir", taxa_inscricao=None,
                conferir_campos={"taxa_inscricao": "O edital não cita taxa de inscrição.", "numero_edital": "conferir"},
                outras_restricoes=["Até 3 disciplinas em adaptação"], evidencias={"outras_restricoes": "2 (itens 2.1), 2 e 3 (item 3.2)", "inscricao_fim": "2 (item 3.2)"})
    return [e] + [x for x in EDITAIS], dict(FACS, **{"unip-campinas": f})


def _post(**kw):
    base = {"tipo": "teste", "usados": ["e000"], "fatos": [{"faculdade": "FAC0", "edital": "e000", "campo": "inscricao_fim", "pagina": "2"}],
            "textos": ["Estes 5 editais"], "legenda": "Confira o edital oficial.", "alts": []}
    base.update(kw)
    return base


class PostAntigoReprovado(unittest.TestCase):
    def test_o_post_antigo_de_10_11_e_reprovado(self):
        eds, facs = _unip_como_estava()
        problemas = ck.checar(ck.post_de_pasta(ANTIGO), eds, facs, HOJE)
        texto = " | ".join(problemas)
        self.assertTrue(problemas, "o post antigo passou na checagem")
        self.assertIn("(a) edital 39c910ec7b14", texto)
        self.assertIn("status 'conferir'", texto)
        self.assertIn("(b) o texto fala em taxa", texto)  # "pagar a taxa" num edital sem taxa conferida

    def test_o_post_novo_de_10_11_passa(self):
        r, nota = dia.escolher(EDITAIS, FACS, TERCA)
        self.assertEqual(r["tipo"], "armadilha-do-edital", nota)
        self.assertEqual(ck.checar(r, EDITAIS, FACS, TERCA), [])
        texto = r["legenda"] + " ".join(r["textos"])
        self.assertNotIn("pagar a taxa", texto)
        with tempfile.TemporaryDirectory() as tmp:  # o que foi gravado em disco também passa (é o que a checagem relê)
            dia.gravar(r, nota, TERCA, Path(tmp) / TERCA)
            self.assertEqual(ck.checar(ck.post_de_pasta(Path(tmp) / TERCA), EDITAIS, FACS, TERCA), [])

    def test_o_post_novo_gerado_agora_no_repositorio_passa(self):
        pasta = PASTA / "docs" / "social" / HOJE
        if not (pasta / "post.json").exists():
            self.skipTest("sem post de 10/11 na pasta (podada)")
        post = ck.post_de_pasta(pasta)
        self.assertIn("usados", json.loads((pasta / "post.json").read_text(encoding="utf-8")))
        editais, facs = dia._dados()
        self.assertEqual(ck.checar(post, editais, facs, HOJE), [])


class RegraA(unittest.TestCase):
    def _com(self, **mud):
        eds = [dict(e) for e in EDITAIS]
        eds[0].update(mud)
        return eds

    def test_edital_so_com_status_ok_e_conferido_a_mao(self):
        for mud, trecho in (({"status": "conferir"}, "status 'conferir'"), ({"status": None}, "status None"),
                            ({"fonte_dados": "regras"}, "lido só automaticamente"), ({"conferir_campos": {"vagas": "x"}}, "campo em 'conferir'"),
                            ({"observacao": "Lido automaticamente; conferir no PDF"}, "pede conferência")):
            with self.subTest(mud):
                p = ck.checar(_post(), self._com(**mud), FACS, HOJE)
                self.assertTrue(any(x.startswith("(a)") and trecho in x for x in p), p)
        self.assertEqual(ck.checar(_post(), EDITAIS, FACS, HOJE), [])

    def test_post_sem_edital_declarado_ou_com_edital_inexistente_e_reprovado(self):
        self.assertTrue(any(x.startswith("(a)") for x in ck.checar(_post(usados=[], fatos=[]), EDITAIS, FACS, HOJE)))
        self.assertTrue(any("não existe" in x for x in ck.checar(_post(usados=["zzz"]), EDITAIS, FACS, HOJE)))

    def test_gerador_nunca_usa_edital_em_conferir(self):
        usados = set()
        for d in (date.fromisoformat(HOJE) + timedelta(days=i) for i in range(7)):
            r, _ = dia.escolher(EDITAIS, FACS, d.isoformat())
            usados |= set(r["usados"])
        ruins = {e["id"] for e in EDITAIS if e.get("status") != "ok" or e.get("fonte_dados") != "manual"}
        self.assertTrue(ruins and usados)
        self.assertFalse(usados & ruins, usados & ruins)


class RegraB(unittest.TestCase):
    def total(self):
        return ck._universo(EDITAIS, FACS, HOJE)["editais"]

    def test_quantidade_parcial_exige_estes(self):
        n = self.total()
        self.assertGreater(n, 8)
        p = ck.checar(_post(textos=["7 editais fecham esta semana"]), EDITAIS, FACS, HOJE)
        self.assertTrue(any(x.startswith("(b)") and "Estes 7 editais" in x for x in p), p)
        self.assertEqual(ck.checar(_post(textos=["Estes 7 editais fecham esta semana"]), EDITAIS, FACS, HOJE), [])
        self.assertEqual(ck.checar(_post(textos=["ESTES 7 editais"]), EDITAIS, FACS, HOJE), [])
        self.assertEqual(ck.checar(_post(textos=[f"{n} editais abertos"]), EDITAIS, FACS, HOJE), [], "o total exato pode ser afirmado")
        self.assertTrue(ck.checar(_post(textos=[f"{n - 1} editais abertos"]), EDITAIS, FACS, HOJE))

    def test_todos_nenhum_unico_sao_reprovados(self):
        for frase in ("Todos os editais aceitam", "nenhum edital cobra taxa", "o único edital aberto", "todas as faculdades abriram"):
            with self.subTest(frase):
                self.assertTrue(any(x.startswith("(b)") for x in ck.checar(_post(legenda=frase), EDITAIS, FACS, HOJE)))
        self.assertEqual(ck.checar(_post(legenda="Nem todo edital aceita quem estudou fora."), EDITAIS, FACS, HOJE), [])

    def test_a_legenda_tambem_e_examinada(self):
        self.assertTrue(ck.checar(_post(legenda="9 editais fecham"), EDITAIS, FACS, HOJE))


class RegraC(unittest.TestCase):
    def test_fato_sem_pagina_ou_sem_faculdade(self):
        sem_pagina = [{"faculdade": "FAC0", "edital": "e000", "campo": "inscricao_fim", "pagina": ""}]
        self.assertTrue(any("sem página" in x for x in ck.checar(_post(fatos=sem_pagina), EDITAIS, FACS, HOJE)))
        sem_fac = [{"faculdade": "", "edital": "e000", "campo": "inscricao_fim", "pagina": "2"}]
        self.assertTrue(any("sem faculdade" in x for x in ck.checar(_post(fatos=sem_fac), EDITAIS, FACS, HOJE)))
        self.assertTrue(any("nenhum fato" in x for x in ck.checar(_post(fatos=[]), EDITAIS, FACS, HOJE)))

    def test_pagina_do_dado(self):
        self.assertEqual(ck.pagina_txt(5), "5")
        self.assertEqual(ck.pagina_txt("2 (itens 1.8 e 1.9)"), "2")
        self.assertEqual(ck.pagina_txt("2 (itens 2.1), 2 e 3 (item 3.2)"), "2 e 3")
        self.assertEqual(ck.pagina_txt("Anexo 1, p. 1"), "Anexo 1, p. 1")
        for vazio in (None, "", "sem página", False):
            self.assertEqual(ck.pagina_txt(vazio), "")

    def test_gerador_nao_usa_edital_sem_pagina_do_dado(self):
        eds = [dict(e, evidencias={}) for e in EDITAIS]
        r, nota = dia.escolher(eds, FACS, TERCA)
        self.assertIsNone(r, nota)

    def test_todo_post_gerado_tem_faculdade_e_pagina_em_cada_fato(self):
        for i in range(7):
            d = (date.fromisoformat(HOJE) + timedelta(days=i)).isoformat()
            r, _ = dia.escolher(EDITAIS, FACS, d)
            self.assertEqual({f["edital"] for f in r["fatos"]}, set(r["usados"]))
            for f in r["fatos"]:
                self.assertTrue(f["faculdade"] and f["pagina"], (d, f))


class RegraD(unittest.TestCase):
    def test_chance_ranking_promessa(self):
        for frase in ("Aumente a sua chance de passar", "o ranking das faculdades", "As melhores faculdades", "vaga garantida", "é uma promessa",
                      "a aprovação é certa", "top 5 editais", "a faculdade mais fácil"):
            with self.subTest(frase):
                self.assertTrue(any(x.startswith("(d)") for x in ck.checar(_post(legenda=frase), EDITAIS, FACS, HOJE)), frase)

    def test_texto_comum_passa(self):
        self.assertEqual(ck.checar(_post(legenda="Confira o edital oficial. Os prazos podem mudar."), EDITAIS, FACS, HOJE), [])


class Trava(unittest.TestCase):
    def test_post_reprovado_nao_e_gravado_e_o_dia_cai_na_reserva_ou_fica_sem_post(self):
        so_conferir = [dict(e, status="conferir") for e in EDITAIS]
        r, nota = dia.escolher(so_conferir, FACS, TERCA)
        self.assertIsNone(r)
        self.assertIn("nenhum formato passou", nota)

    def test_o_gerador_aplica_a_checagem_a_cada_formato(self):
        """Um formato que passa a afirmar 'todos' é barrado em escolher(): o dia cai na reserva e a nota diz o porquê."""
        original = dia.CALENDARIO[1]

        def ruim(editais, facs, hoje):
            r = original(editais, facs, hoje)
            r["legenda"] += "\nTodos os editais estão aqui.\n"
            return r
        dia.CALENDARIO[1] = ruim
        try:
            r, nota = dia.escolher(EDITAIS, FACS, TERCA)
        finally:
            dia.CALENDARIO[1] = original
        self.assertNotEqual(r["tipo"], "armadilha-do-edital")
        self.assertIn("reprovado na checagem", nota)
        self.assertIn("(b)", nota)

    def test_dados_reais_qualquer_dia_ou_passa_ou_nao_sai(self):
        """Vale para qualquer estado da base real: cada dia da semana ou gera um post que passa, ou não gera nada."""
        editais, facs = dia._dados()
        for i in range(7):
            d = (date.fromisoformat(HOJE) + timedelta(days=i)).isoformat()
            r, nota = dia.escolher(editais, facs, d)
            if r is None:
                self.assertIn("nenhum formato passou", nota)
            else:
                self.assertEqual(ck.checar(r, editais, facs, d), [], f"{d}: {r['tipo']}")
                self.assertEqual({f["edital"] for f in r["fatos"]}, set(r["usados"]))


if __name__ == "__main__":
    unittest.main()
