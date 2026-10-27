"""Testes do monitor diário e da sincronização de issues. Rodar com: python -m unittest discover tests"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import issues  # noqa: E402
import monitor  # noqa: E402

FAC = {"x": {"id": "x", "sigla": "FX", "cidade": "Cidade", "nome": "Faculdade X", "ultima_conferencia": "2026-10-20"}}


def edital(**kw):
    base = {"id": "e1", "faculdade_id": "x", "url_edital": "https://x.br/e.pdf", "fonte_dados": "manual", "status": "ok",
            "modalidade": "externa", "semestre_ingresso": "2027.1", "inscricao_inicio": "2026-10-01",
            "inscricao_fim": "2026-10-30"}
    return {**base, **kw}


def issue(numero, achado, estado="open", fonte="monitor", estado_marca="aberta", hash_=None, titulo=None):
    corpo = issues.montar_corpo(achado, fonte, estado_marca)
    if hash_:
        corpo = corpo.replace(f"hash={issues.impressao(achado)}", f"hash={hash_}")
    return {"number": numero, "state": estado, "title": titulo or achado["titulo"], "body": corpo}


class Prazos(unittest.TestCase):
    def test_avisa_prazo_de_ate_7_dias(self):
        a = monitor.checar_prazos([edital()], FAC, "2026-10-26")
        prazos = [x for x in a if x["etiqueta"] == "prazo"]
        self.assertEqual(len(prazos), 1)
        self.assertIn("em 4 dias (30/10/2026)", prazos[0]["titulo"])
        self.assertEqual(monitor.checar_prazos([edital()], FAC, "2026-10-20"), [])

    def test_nao_avisa_o_que_nao_foi_conferido_a_mao(self):
        self.assertEqual(monitor.checar_prazos([edital(fonte_dados="regras")], FAC, "2026-10-26"), [])

    def test_data_impossivel_e_status_conferir(self):
        a = monitor.checar_prazos([edital(inscricao_inicio="2026-11-05", inscricao_fim="2026-11-01",
                                          status="conferir", observacao="Retificação publicada em 2026-10-25")],
                                  FAC, "2026-10-26")
        etiquetas = sorted(x["etiqueta"] for x in a)
        self.assertEqual(etiquetas, ["conferir", "retificação"])

    def test_ficha_sem_conferencia_ha_mais_de_30_dias(self):
        velha = {"x": {**FAC["x"], "ultima_conferencia": "2026-08-01"}}
        a = monitor.checar_prazos([], velha, "2026-10-26")
        self.assertEqual([x["chave"] for x in a], ["fichas-sem-conferencia"])

    def test_correcao_segura_so_mexe_na_situacao(self):
        e = edital(situacao="aberto", inscricao_fim="2026-10-20")
        antes = dict(e)
        mudados = monitor.corrigir_situacoes([e], "2026-10-26")
        self.assertEqual(e["situacao"], "encerrado")
        self.assertEqual(len(mudados), 1)
        self.assertEqual({k: v for k, v in e.items() if k != "situacao"}, {k: v for k, v in antes.items() if k != "situacao"})

    def test_anexos_vigiados_uma_vez_so(self):
        # rodada de 26/10/2026: datas e vagas do IDOMED vêm dos anexos, que o monitor não vigiava
        anexo = "https://x.br/anexo1-calendario.pdf"
        a = edital(anexos=[anexo])
        b = edital(id="e2", faculdade_id="y", anexos=[anexo])  # outro câmpus, mesmo edital unificado
        docs = monitor.documentos_vigiados([a, b], "2026-10-26")
        self.assertEqual(sorted(docs), ["https://x.br/anexo1-calendario.pdf", "https://x.br/e.pdf"])
        self.assertEqual(len(docs[anexo]), 2)
        self.assertEqual(monitor.documentos_vigiados([edital(inscricao_fim="2026-10-01")], "2026-10-26"), {})

    def test_fluxo_continuo_com_aviso_nao_e_pendencia(self):
        # UNILAGO: formulário contínuo, sem edital; o aviso é permanente e não há PDF para conferir
        e = edital(fluxo_continuo=True, status="conferir", inscricao_inicio=None, inscricao_fim=None)
        self.assertEqual([x for x in monitor.checar_prazos([e], FAC, "2026-10-26") if x["chave"].startswith("conferir")], [])

    def test_pagina_que_abre_sem_link_nao_e_falha(self):
        # caso real (FMUSP): Fuvest bloqueada + página da faculdade aberta sem edital agora
        fontes = ["https://www.fuvest.br/transferencia/", "https://www.fm.usp.br/graduacao/transferencia"]
        self.assertFalse(monitor.falhou_tudo(["fuvest: 403"], fontes, []))
        self.assertTrue(monitor.falhou_tudo(["fuvest: 403", "fm: timeout"], fontes, []))
        self.assertFalse(monitor.falhou_tudo(["fuvest: 403", "fm: timeout"], fontes, [("u", "r")]))

    def test_ancora_aleatoria_nao_e_link_novo(self):
        # caso real (UMC, 26/10/2026): #collapse-<aleatório> mudava a cada carregamento e virou "link novo"
        self.assertEqual(monitor.sem_ancora("https://umc.br/transferencia-medicina/#collapse-b16849"),
                         monitor.sem_ancora("https://www.umc.br/transferencia-medicina/#collapse-e76c96"))

    def test_excecoes_de_links(self):
        regras = monitor.excecoes()
        self.assertTrue(monitor.excecao("https://unitau.br/concursos", regras))
        self.assertFalse(monitor.excecao("https://ub.edu.br/editais/", regras))


class Issues(unittest.TestCase):
    A = monitor.achado("prazo:e1", "prazo", "Prazo: FX encerra em 4 dias", "corpo", estavel="prazo:e1:2026-10-30")

    def test_cria_o_que_nao_existe(self):
        self.assertEqual([x[0] for x in issues.planejar([self.A], [], "monitor")], ["criar"])

    def test_nunca_duplica_issue_aberta(self):
        self.assertEqual(issues.planejar([self.A], [issue(7, self.A)], "monitor"), [])
        self.assertEqual(issues.planejar([self.A, self.A], [], "monitor").__len__(), 1)

    def test_atualiza_contagem_sem_mudar_a_identidade(self):
        amanha = {**self.A, "titulo": "Prazo: FX encerra em 3 dias"}
        acoes = issues.planejar([amanha], [issue(7, self.A)], "monitor")
        self.assertEqual([(x[0], x[1]) for x in acoes], [("atualizar", 7)])
        self.assertEqual(issues.impressao(amanha), issues.impressao(self.A))

    def test_respeita_fechamento_manual_e_reabre_o_que_o_robo_fechou(self):
        fechada_por_pessoa = issue(7, self.A, estado="closed")
        self.assertEqual(issues.planejar([self.A], [fechada_por_pessoa], "monitor"), [])
        fechada_pelo_robo = issue(7, self.A, estado="closed", estado_marca="auto")
        self.assertEqual([x[0] for x in issues.planejar([self.A], [fechada_pelo_robo], "monitor")], ["reabrir"])
        mudou = issue(7, self.A, estado="closed", hash_="000000000000")
        self.assertEqual([x[0] for x in issues.planejar([self.A], [mudou], "monitor")], ["reabrir"])

    def test_fecha_sozinha_so_o_que_pode_fechar(self):
        novo = monitor.achado("novo:e2", "edital-novo", "Edital novo", "c", auto_fecha=False)
        acoes = issues.planejar([], [issue(7, self.A), issue(8, novo)], "monitor")
        self.assertEqual([(x[0], x[1]) for x in acoes], [("fechar", 7)])

    def test_cada_fonte_cuida_das_suas_issues(self):
        self.assertEqual(issues.planejar([], [issue(7, self.A, fonte="qualidade")], "monitor"), [])

    def test_ignora_pull_requests_e_issues_de_pessoas(self):
        pr = {**issue(7, self.A), "pull_request": {}}
        humana = {"number": 9, "state": "open", "title": "dúvida", "body": "texto sem marca"}
        self.assertEqual([x[0] for x in issues.planejar([self.A], [pr, humana], "monitor")], ["criar"])


if __name__ == "__main__":
    unittest.main()
