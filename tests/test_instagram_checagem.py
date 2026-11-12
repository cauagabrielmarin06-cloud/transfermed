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
UCB = Path(__file__).resolve().parent / "fixtures" / "instagram_post_ucb_2026-11-10"  # reprovado em 09/11: resumo entre aspas, 5 páginas, gancho vago
HOJE = "2026-11-10"


def _unip_como_estava():
    """O edital da UNIP como estava nos dados em 09/11/2026: status conferir, sem taxa conferida, com a observação do número do edital."""
    f = dict(FACS["f0"], id="unip-campinas", sigla="UNIP", cidade="Campinas", uf="SP")
    e = _edital(1, "2027-02-12", id="39c910ec7b14", faculdade_id="unip-campinas", status="conferir", taxa_inscricao=None,
                conferir_campos={"taxa_inscricao": "O edital não cita taxa de inscrição.", "numero_edital": "conferir"},
                outras_restricoes=["Até 3 disciplinas em adaptação"], evidencias={"outras_restricoes": "2 (itens 2.1), 2 e 3 (item 3.2)", "inscricao_fim": "2 (item 3.2)"})
    return [e] + [x for x in EDITAIS], dict(FACS, **{"unip-campinas": f})


class RegraAPorCampo(unittest.TestCase):
    """A regra (a) vale por campo: dúvida em resultado/vagas não impede um post que só usa o prazo; dúvida no prazo impede."""

    def _eds(self, **mud):
        eds = [dict(e) for e in EDITAIS]
        eds[0].update(mud)
        return eds

    def test_duvida_em_outro_campo_nao_reprova_post_que_so_usa_o_prazo(self):
        eds = self._eds(status="conferir", conferir_campos={"resultado": "p. 2 e p. 7 divergem", "vagas": "tabela confusa"})
        self.assertEqual(ck.checar(_post(), eds, FACS, HOJE), [])

    def test_prazo_em_conferir_reprova_como_o_da_unex_vitoria_da_conquista(self):
        eds = self._eds(status="conferir", conferir_campos={"inscricao_fim": "o aditivo diz 2026 e o consolidado 2027"})
        p = ck.checar(_post(), eds, FACS, HOJE)
        self.assertTrue(any(x.startswith("(a)") and "inscricao_fim" in x for x in p), p)

    def test_campo_usado_sem_pagina_reprova(self):
        fatos = [{"faculdade": "FAC0", "edital": "e000", "campo": "inscricao_fim", "pagina": ""}]
        self.assertTrue(any("sem página" in x for x in ck.checar(_post(fatos=fatos), EDITAIS, FACS, HOJE)))

    def test_status_conferir_sem_campos_detalhados_reprova(self):
        p = ck.checar(_post(), self._eds(status="conferir", conferir_campos=None), FACS, HOJE)
        self.assertTrue(any("sem conferir_campos detalhado" in x for x in p), p)

    def test_faculdade_no_formato_do_fontes_md(self):
        eds, facs = [dict(e) for e in EDITAIS], FACS
        sigla = facs[eds[0]["faculdade_id"]]["sigla"]
        for nome in (sigla, f"{sigla} São Caetano", f"{sigla.lower()} externa"):
            fatos = [{"faculdade": nome, "edital": "e000", "campo": "inscricao_fim", "pagina": "2"}]
            self.assertEqual(ck.checar(_post(fatos=fatos), eds, facs, HOJE), [], nome)
        fatos = [{"faculdade": "Outra Coisa", "edital": "e000", "campo": "inscricao_fim", "pagina": "2"}]
        self.assertTrue(any("sem faculdade conhecida" in x for x in ck.checar(_post(fatos=fatos), eds, facs, HOJE)))

    def test_post_de_11_11_do_dono_passa_com_os_dados_reais(self):
        editais, facs = dia._dados()
        post = ck.post_de_pasta(PASTA / "docs" / "social" / "2026-11-11")
        self.assertEqual(ck.checar(post, editais, facs, "2026-11-11"), [])

    def test_post_com_o_prazo_da_unex_vitoria_da_conquista_reprova_nos_dados_reais(self):
        editais, facs = dia._dados()
        unex = next(e for e in editais if e["id"] == "e76ba561b489")
        self.assertTrue(unex["prazo_contraditorio"], "12/11/2026: duas datas no edital = prazo seguro na ficha; o post não pode afirmar o prazo")
        sigla = facs[unex["faculdade_id"]]["sigla"]
        post = _post(usados=[unex["id"]], fatos=[{"faculdade": sigla, "edital": unex["id"], "campo": "inscricao_fim", "pagina": "3"}])
        p = ck.checar(post, editais, facs, "2026-11-11")
        self.assertTrue(any(x.startswith("(a)") and "inscricao_fim" in x for x in p), p)


def _post(**kw):
    base = {"tipo": "teste", "usados": ["e000"], "fatos": [{"faculdade": "FAC0", "edital": "e000", "campo": "inscricao_fim", "pagina": "2"}],
            "textos": ["Estes 5 editais"], "gancho": "Estes 5 editais fecham em até 14 dias", "legenda": "Confira sempre o edital oficial.", "alts": []}
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


class PostUcbReprovado(unittest.TestCase):
    def test_o_post_da_ucb_e_reprovado_pelas_tres_regras_novas(self):
        editais, facs = dia._dados()
        problemas = ck.checar(ck.post_de_pasta(UCB), editais, facs, HOJE)
        for regra in ("(e)", "(f)", "(g)"):
            self.assertTrue(any(x.startswith(regra) for x in problemas), (regra, problemas))
        texto = " | ".join(problemas)
        self.assertIn("O EDITAL DIZ", texto.upper())
        self.assertIn("4, 5, 6, 8 e 9", texto)
        self.assertIn("Leia o edital com atenção", texto)

    def test_o_post_revisado_de_10_11_passa(self):
        pasta = PASTA / "docs" / "social" / HOJE
        post = ck.post_de_pasta(pasta)
        self.assertEqual(post["usados"], ["0bfe52b7ab9f", "ebbabac553c6"])
        self.assertNotIn("“", " ".join(post["textos"]) + post["legenda"])
        self.assertEqual(ck.checar(post, [e for e in dia._dados()[0]], dia._dados()[1], HOJE), [])


class RegrasEFG(unittest.TestCase):
    def ck(self, **kw):
        return ck.checar(_post(**kw), EDITAIS, FACS, HOJE)

    def test_e_aspas_e_o_edital_diz_sem_texto_literal(self):
        for frase in ("A regra: “matrícula em 48h”", 'A regra: "matrícula em 48h"', "O edital diz que a matrícula é rápida", "o edital exige histórico"):
            with self.subTest(frase):
                self.assertTrue(any(x.startswith("(e)") for x in self.ck(legenda=frase)), frase)
        self.assertTrue(any(x.startswith("(e)") for x in self.ck(textos=["Estes 5 editais", "O EDITAL DIZ: algo"])))
        self.assertEqual(self.ck(legenda="Está no edital, página 2. Confira sempre o edital oficial."), [])

    def test_e_trecho_literal_do_pdf_com_pagina_unica_libera_a_aspa(self):
        lit = [{"edital": "e000", "trecho": "matrícula em até 48 horas", "pagina": "5"}]
        self.assertEqual(self.ck(legenda="Item 5.1: “matrícula em até 48 horas”. Confira sempre o edital oficial.", literais=lit), [])
        self.assertTrue(self.ck(legenda="Item 5.1: “matrícula em até 24 horas”.", literais=lit))  # outro texto: continua reprovado
        sem_pagina = [{"edital": "e000", "trecho": "matrícula em até 48 horas", "pagina": ""}]
        self.assertTrue(self.ck(legenda="Item 5.1: “matrícula em até 48 horas”.", literais=sem_pagina))

    def test_f_pagina_unica_por_fato(self):
        for pag in ("4, 5, 6, 8 e 9", "2 e 3", "", "sem página"):
            with self.subTest(pag):
                fato = [{"faculdade": "FAC0", "edital": "e000", "campo": "inscricao_fim", "pagina": pag}]
                self.assertTrue(any(x.startswith(("(f)", "(c)")) for x in self.ck(fatos=fato)), pag)
        for pag in ("3", "Anexo 1, p. 1"):
            fato = [{"faculdade": "FAC0", "edital": "e000", "campo": "inscricao_fim", "pagina": pag}]
            self.assertEqual(self.ck(fatos=fato), [], pag)
        for frase in ("No PDF, uma destas páginas: 4, 5 e 6", "págs. 4 e 5", "páginas 4 e 5"):
            self.assertTrue(any(x.startswith("(f)") for x in self.ck(legenda=frase)), frase)
        self.assertEqual(self.ck(legenda="Edital, p. 3, item 5.3. Confira sempre o edital oficial."), [])

    def test_g_gancho_com_fato_concreto(self):
        for gancho in ("", "Leia o edital com atenção", "Detalhes que mudam tudo", "Descubra onde se inscrever", "Quanto custa se inscrever?"):
            with self.subTest(gancho):
                self.assertTrue(any(x.startswith("(g)") for x in self.ck(gancho=gancho)), gancho)
        self.assertEqual(self.ck(gancho="UNOESTE: taxa R$ 200, inscrição até 07/12"), [])
        # 12/11/2026: gancho sem número vale se for pergunta ou fato concreto e tiver ponto de apoio (termo do edital ou sigla dos fatos)
        for gancho in ("Nota alta decide nestes editais?", "Toda prova de transferência é presencial?", "FAC0 aceita curso do exterior?"):
            with self.subTest(gancho):
                self.assertEqual(self.ck(gancho=gancho), [], gancho)
        for gancho in ("Você sabia disso?", "Isso muda tudo para você"):
            with self.subTest(gancho):
                self.assertTrue(any("não é específico" in x for x in self.ck(gancho=gancho)), gancho)

    def test_gerador_nunca_gera_aspas_pagina_multipla_ou_gancho_vago(self):
        for i in range(7):
            d = (date.fromisoformat(HOJE) + timedelta(days=i)).isoformat()
            r, _ = dia.escolher(EDITAIS, FACS, d, padrao=False)
            self.assertRegex(r["gancho"], r"\d", d)
            self.assertNotRegex(r["legenda"] + " ".join(r["textos"]), "[“”\"]", d)
            self.assertTrue(all(ck.pagina_unica(f["pagina"]) for f in r["fatos"]), d)
            self.assertIn(r["gancho"], " ".join(r["textos"]).replace("\n", " ").replace("  ", " "), f"{d}: o gancho tem de ser o título desenhado na imagem")


class PostRevisado(unittest.TestCase):
    def test_o_robo_nao_sobrescreve_post_revisado_pelo_dono(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp) / "2026-11-10"
            pasta.mkdir()
            (pasta / "post.json").write_text('{"revisado": true}', encoding="utf-8")
            (pasta / "legenda.txt").write_text("do dono", encoding="utf-8")
            self.assertTrue(dia.revisado_pelo_dono(pasta))
            with mock.patch.object(dia, "SOCIAL", Path(tmp)), mock.patch.object(dia, "PRIVADO", Path(tmp) / "sem-privado"):
                self.assertEqual(dia.main(["--data", "2026-11-10"]), 0)
            self.assertEqual((pasta / "legenda.txt").read_text(encoding="utf-8"), "do dono")
            self.assertFalse(dia.revisado_pelo_dono(Path(tmp) / "nao-existe"))

    def test_pasta_revisada_do_dono_tem_prioridade_sobre_o_robo(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            privado, social = Path(tmp) / "privado", Path(tmp) / "social"
            rev = privado / "2026-11-11-revisado"
            rev.mkdir(parents=True)
            for n in ("01", "02"):
                (rev / f"{n}.jpg").write_bytes(b"jpg" + n.encode())
            (rev / "legenda.txt").write_text("Estas 3 faculdades fecham até 23/11:" + chr(10)*2 + "texto", encoding="utf-8")
            (rev / "FONTES.md").write_text("| Faculdade | id | Até | Página |" + chr(10) + "|---|---|---|---|" + chr(10) + "| USCS | 41a0eb874829 | 16/11 | p. 2 (item 3.3) |" + chr(10), encoding="utf-8")
            velha = social / "2026-11-11"
            velha.mkdir(parents=True)
            (velha / "01.jpg").write_bytes(b"do robo")
            with mock.patch.object(dia, "SOCIAL", social), mock.patch.object(dia, "PRIVADO", privado):
                self.assertEqual(dia.main(["--data", "2026-11-11"]), 0)
            self.assertEqual((velha / "01.jpg").read_bytes(), b"jpg01")
            self.assertEqual((velha / "02.jpg").read_bytes(), b"jpg02")
            self.assertTrue(dia.revisado_pelo_dono(velha))
            post = json.loads((velha / "post.json").read_text(encoding="utf-8"))
            self.assertEqual(len(post["imagens"]), 2)
            self.assertEqual(post["fatos"][0]["pagina"], "2")

    def test_o_post_de_10_11_no_repositorio_esta_marcado_como_revisado(self):
        self.assertTrue(dia.revisado_pelo_dono(PASTA / "docs" / "social" / HOJE))


class RegraA(unittest.TestCase):
    def _com(self, **mud):
        eds = [dict(e) for e in EDITAIS]
        eds[0].update(mud)
        return eds

    def test_edital_so_com_status_ok_e_conferido_a_mao(self):
        for mud, trecho in (({"status": "conferir"}, "status 'conferir' sem conferir_campos"), ({"status": None}, "status None"),
                            ({"fonte_dados": "regras"}, "lido só automaticamente"), ({"conferir_campos": {"inscricao_fim": "x"}}, "campo usado no post em 'conferir'"),
                            ({"conferir_campos": {"edital": "x"}}, "campo usado no post em 'conferir'"),
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
            r, _ = dia.escolher(EDITAIS, FACS, d.isoformat(), padrao=False)
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
        self.assertEqual(ck.checar(_post(legenda="Nem todo edital aceita quem estudou fora. Confira sempre o edital oficial."), EDITAIS, FACS, HOJE), [])

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
        r, nota = dia.escolher(eds, FACS, TERCA, padrao=False)
        self.assertIsNone(r, nota)

    def test_todo_post_gerado_tem_faculdade_e_pagina_em_cada_fato(self):
        for i in range(7):
            d = (date.fromisoformat(HOJE) + timedelta(days=i)).isoformat()
            r, _ = dia.escolher(EDITAIS, FACS, d, padrao=False)
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
        self.assertEqual(ck.checar(_post(legenda="Confira sempre o edital oficial. Os prazos podem mudar."), EDITAIS, FACS, HOJE), [])


class Trava(unittest.TestCase):
    def test_post_reprovado_nao_e_gravado_e_o_dia_cai_na_reserva_ou_fica_sem_post(self):
        so_conferir = [dict(e, status="conferir") for e in EDITAIS]
        r, nota = dia.escolher(so_conferir, FACS, TERCA, padrao=False)
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
            r, nota = dia.escolher(EDITAIS, FACS, TERCA, padrao=False)
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
            r, nota = dia.escolher(editais, facs, d, padrao=False)
            if r is None:
                self.assertIn("nenhum formato passou", nota)
            else:
                self.assertEqual(ck.checar(r, editais, facs, d, padrao=False), [], f"{d}: {r['tipo']}")
                self.assertEqual({f["edital"] for f in r["fatos"]}, set(r["usados"]))


if __name__ == "__main__":
    unittest.main()
