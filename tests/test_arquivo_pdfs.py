"""Arquivo permanente dos PDFs e versões das retificações (sem rede: download e Internet Archive são simulados)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import arquivo_pdfs  # noqa: E402

ED = {"id": "e1", "faculdade_id": "f1", "fonte_dados": "manual", "url_edital": "https://x.br/edital.pdf",
      "retificacoes": ["https://x.br/retif1.pdf"], "inscricao_fim": "2026-10-29", "vagas_texto": "5 vagas",
      "conferido_em": "2026-10-20"}


class Versoes(unittest.TestCase):
    def test_retificacao_nao_apaga_o_valor_antigo(self):
        antigo = dict(ED)
        novo = dict(ED, inscricao_fim="2026-11-18", conferido_em="2026-11-02")
        n = arquivo_pdfs.registrar_versoes([antigo], [novo], "2026-11-02", "retificação 1")
        self.assertEqual(n, 1)
        v = novo["versoes"][0]
        self.assertEqual(v["mudou"], {"inscricao_fim": ["2026-10-29", "2026-11-18"]})
        self.assertEqual((v["em"], v["motivo"]), ("2026-11-02", "retificação 1"))

    def test_data_de_conferencia_sozinha_nao_vira_versao(self):
        novo = dict(ED, conferido_em="2026-11-02")
        self.assertEqual(arquivo_pdfs.registrar_versoes([dict(ED)], [novo], "2026-11-02"), 0)
        self.assertNotIn("versoes", novo)

    def test_nao_repete_a_mesma_versao_e_mantem_as_antigas(self):
        antigo = dict(ED, versoes=[{"em": "2026-10-25", "motivo": "x", "mudou": {"vagas_texto": ["4", "5 vagas"]}}])
        novo = dict(ED, inscricao_fim="2026-11-18", versoes=list(antigo["versoes"]))
        arquivo_pdfs.registrar_versoes([antigo], [novo], "2026-11-02")
        arquivo_pdfs.registrar_versoes([antigo], [novo], "2026-11-03")
        self.assertEqual(len(novo["versoes"]), 2, "a antiga fica e a nova entra uma vez só")

    def test_edital_novo_nao_gera_versao(self):
        self.assertEqual(arquivo_pdfs.registrar_versoes([], [dict(ED)], "2026-11-02"), 0)


class Arquivo(unittest.TestCase):
    def setUp(self):
        self.baixados, self.pedidos = [], []

    def baixar(self, url):
        self.baixados.append(url)
        return b"%PDF-1.4 " + url.encode()

    def arquivar(self, url):
        self.pedidos.append(url)
        return "https://web.archive.org/web/20261102/" + url

    def rodar(self, editais, arquivo=None, hoje="2026-11-02", baixar=None, retratos=None, arquivar=None):
        return arquivo_pdfs.atualizar(editais, hoje, arquivo, baixar=baixar or self.baixar, arquivar=arquivar or self.arquivar,
                                      pausa=0, retratos=retratos)

    def test_todo_edital_conferido_ganha_hash_e_copia_inclusive_encerrado(self):
        encerrado = dict(ED, id="e2", url_edital="https://x.br/velho.pdf", retificacoes=[], inscricao_fim="2024-01-01")
        arquivo, feito = self.rodar([ED, encerrado])
        r = arquivo_pdfs.resumo([ED, encerrado], arquivo)
        self.assertEqual((r["editais_com_pdf"], r["com_hash"], r["com_copia_publica"], r["faltando"]), (2, 2, 2, []))
        self.assertEqual(feito["baixados"], 3, "dois editais e uma retificação")

    def test_sem_a_decisao_do_dono_nada_vai_ao_internet_archive(self):
        arquivo, feito = arquivo_pdfs.atualizar([ED], "2026-11-02", None, baixar=self.baixar, pausa=0)
        self.assertEqual(self.pedidos, [])
        self.assertEqual(feito["copias"], 0)
        self.assertTrue(all(d.get("sha256") and "tentativas_arquivo" not in d for d in arquivo["documentos"].values()))

    def test_o_que_nao_foi_conferido_fica_de_fora(self):
        arquivo, _ = self.rodar([dict(ED, fonte_dados="radar")])
        self.assertEqual(arquivo["documentos"], {})

    def test_segunda_rodada_nao_baixa_nem_pede_de_novo(self):
        arquivo, _ = self.rodar([ED])
        self.baixados.clear(), self.pedidos.clear()
        self.rodar([ED], arquivo)
        self.assertEqual((self.baixados, self.pedidos), ([], []))

    def test_hash_antigo_nunca_e_apagado_quando_o_arquivo_muda(self):
        arquivo, _ = self.rodar([ED])
        chave = arquivo_pdfs.radar.chave_url(ED["url_edital"])
        antigo = arquivo["documentos"][chave]["sha256"]
        # o monitor (retratos) viu outro hash no mesmo endereço
        self.rodar([ED], arquivo, hoje="2026-11-05", retratos={"pdfs": {chave: {"hash": "novohash"}}})
        d = arquivo["documentos"][chave]
        self.assertEqual(d["sha256"], "novohash")
        self.assertEqual(d["versoes"], [{"em": "2026-11-05", "sha256": antigo, "bytes": d["versoes"][0]["bytes"]}])
        self.assertEqual(self.pedidos.count(ED["url_edital"]), 2, "o arquivo mudou: pede cópia nova")

    def test_falha_de_download_e_internet_archive_nao_derrubam(self):
        def quebra(url):
            raise OSError("fora do ar")
        arquivo, feito = self.rodar([ED], baixar=quebra)
        self.assertEqual(feito["falhas"], 2)
        r = arquivo_pdfs.resumo([ED], arquivo)
        self.assertEqual(r["com_hash"], 0)
        self.assertEqual(r["faltando"], ["e1"])
        # Internet Archive recusando: o hash fica, a cópia fica pendente e tenta de novo depois
        arquivo2, _ = arquivo_pdfs.atualizar([ED], "2026-11-02", None, baixar=self.baixar, arquivar=lambda u: None, pausa=0)
        d = arquivo2["documentos"][arquivo_pdfs.radar.chave_url(ED["url_edital"])]
        self.assertTrue(d["sha256"])
        self.assertEqual((d.get("copia_publica"), d["tentativas_arquivo"]), (None, 1))

    def test_pagina_que_nao_e_pdf_nao_conta_como_falta(self):
        fluxo = dict(ED, id="e3", url_edital="https://x.br/pagina", retificacoes=[])
        arquivo, _ = self.rodar([fluxo], baixar=lambda u: None)
        self.assertEqual(arquivo_pdfs.resumo([fluxo], arquivo)["editais_com_pdf"], 0)


if __name__ == "__main__":
    unittest.main()
