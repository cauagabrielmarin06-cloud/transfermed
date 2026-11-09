"""Funções aprovadas e no ar vêm ligadas no código (só "0" desliga) e a publicação trava se o Raio-X sumir das fichas.

Incidente de 06/11/2026: gerar o site sem RAIO_X=1 tirou o Raio-X de 58 fichas do ar por algumas horas. Estes testes rodam depois de
gerar_site.py no radar e no monitor, antes de qualquer commit: se o número de fichas com Raio-X cair abaixo do piso, nada é publicado.

Para subir o piso (depois de uma recoleta que acrescenta fichas): rode `python gerar_site.py` e grave o novo número em
tests/piso_raio_x.json. Para BAIXAR o piso (um edital reaberto, por exemplo), escreva o motivo no campo "motivo_ultima_baixa".
"""
import json
import os
import re
import subprocess
import sys
import unittest
from datetime import date
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))
import funcoes  # noqa: E402
import gerar_site  # noqa: E402

PISO = json.loads((PASTA / "tests" / "piso_raio_x.json").read_text(encoding="utf-8"))["fichas_com_raio_x"]


def _com_ambiente(valor):
    """Importa funcoes e gerar_site num processo novo, com RAIO_X (e as outras) no valor dado; None = variável inexistente."""
    env = {k: v for k, v in os.environ.items() if k not in funcoes.LIGADAS_POR_PADRAO}
    if valor is not None:
        env.update({k: valor for k in funcoes.LIGADAS_POR_PADRAO})
    env["GITHUB_ACTIONS"] = "true"  # não ler privado/variaveis.env
    codigo = ("import gerar_site, funcoes; print(gerar_site.RAIO_X_ATIVO, gerar_site.CONTATO_ATIVO, "
              "all(funcoes.ligada(n) for n in funcoes.LIGADAS_POR_PADRAO))")
    r = subprocess.run([sys.executable, "-c", codigo], cwd=PASTA, env=env, capture_output=True, text=True, timeout=120)
    return r.stdout.split()


class FuncoesLigadasPorPadrao(unittest.TestCase):
    def test_sem_variavel_ou_com_variavel_vazia_esta_ligada(self):
        for valor in (None, "", "1"):
            self.assertEqual(_com_ambiente(valor), ["True", "True", "True"], f"valor={valor!r}")

    def test_so_o_zero_desliga(self):
        self.assertEqual(_com_ambiente("0"), ["False", "False", "False"])

    def test_todas_as_funcoes_da_lista_existem_no_ar(self):
        self.assertEqual(set(funcoes.LIGADAS_POR_PADRAO),
                         {"RAIO_X", "CONTATO_ATIVO", "ENVIO_IMEDIATO", "AGENDA_UNICA", "ALERTAS_ATIVOS", "ARQUIVAR_NO_ARCHIVE", "INDICACAO"})

    def test_nenhum_codigo_volta_a_exigir_a_variavel_igual_a_1(self):
        """Impede a regressão: `os.environ.get("RAIO_X") == "1"` voltaria a apagar a função do ar numa geração sem variável."""
        nomes = "|".join(funcoes.LIGADAS_POR_PADRAO)
        padrao = re.compile(r'environ(?:\.get\(|\[)\s*["\'](?:%s)["\'][^\n]*?==\s*["\']1["\']' % nomes)
        achados = []
        for arq in PASTA.glob("*.py"):
            for n, linha in enumerate(arq.read_text(encoding="utf-8").splitlines(), 1):
                if padrao.search(linha):
                    achados.append(f"{arq.name}:{n}: {linha.strip()}")
        self.assertEqual(achados, [], "use funcoes.ligada(nome) em vez de comparar a variável com \"1\"")

    def test_funcao_ainda_nao_aprovada_continua_desligada(self):
        self.assertNotIn("DESCADASTRO_UM_CLIQUE", funcoes.LIGADAS_POR_PADRAO)


class IndicacaoLigadaPorPadrao(unittest.TestCase):
    """09/11/2026: "Avise um colega" vem ligado no código; gerar o site sem variável não pode tirá-lo do ar."""

    def _cfg(self, valor):
        env = {k: v for k, v in os.environ.items() if k != "INDICACAO"}
        env["GITHUB_ACTIONS"] = "true"
        if valor is not None:
            env["INDICACAO"] = valor
        codigo = ("import gerar_site, funcoes; print(funcoes.ligada('INDICACAO'))")
        return subprocess.run([sys.executable, "-c", codigo], cwd=PASTA, env=env, capture_output=True, text=True, timeout=120).stdout.split()

    def test_sem_variavel_ou_vazia_liga_e_so_zero_desliga(self):
        self.assertEqual([self._cfg(v) for v in (None, "", "1", "0")], [["True"], ["True"], ["True"], ["False"]])

    def test_o_site_gerado_leva_a_configuracao_de_indicacao(self):
        dados = (PASTA / "docs" / "dados.js").read_text(encoding="utf-8")
        self.assertIn('"indicacao": true', dados)

    def test_o_codigo_usa_a_funcao_ligada_e_nao_a_variavel_igual_a_1(self):
        fonte = (PASTA / "gerar_site.py").read_text(encoding="utf-8")
        self.assertIn('funcoes.ligada("INDICACAO")', fonte)
        self.assertNotIn('environ.get("INDICACAO")', fonte)


class PisoDoRaioX(unittest.TestCase):
    def test_o_piso_e_um_numero_razoavel(self):
        self.assertGreaterEqual(PISO, 60)

    def test_fichas_geradas_com_raio_x_nao_caem_abaixo_do_piso(self):
        """O que vai ao ar: conta as fichas em docs/edital/ que trazem o bloco do Raio-X."""
        n = sum(1 for p in (PASTA / "docs" / "edital").glob("*/index.html") if 'id="t-raiox"' in p.read_text(encoding="utf-8"))
        self.assertGreaterEqual(n, PISO, f"só {n} fichas com Raio-X (piso {PISO}): o site foi gerado com RAIO_X=0 ou o bloco quebrou. "
                                         "Gere de novo com `python gerar_site.py` (sem RAIO_X=0) antes de publicar")

    def test_a_base_continua_rendendo_o_bloco_para_o_piso_de_fichas(self):
        """Independe dos arquivos gerados: aplica a regra do bloco sobre os dados de hoje."""
        editais = json.loads((PASTA / "data" / "editais.json").read_text(encoding="utf-8"))
        hoje = date.today().isoformat()
        n = sum(1 for e in editais if gerar_site.publicavel(e) and gerar_site.bloco_raio_x(e, hoje))
        self.assertGreaterEqual(n, PISO, f"a regra do Raio-X só rende {n} fichas (piso {PISO})")


if __name__ == "__main__":
    unittest.main()
