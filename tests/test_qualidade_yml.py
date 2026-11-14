"""qualidade.yml sem `|| true` (14/11/2026): um passo que falha deixa o workflow vermelho de verdade (antes, 40 páginas com HTML inválido e uma
conferência de ficha quebrada passavam em silêncio). O portão dos links reprova só o que é defeito do site; link externo quebrado é issue."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA / "qa"))
import portao_links  # noqa: E402

YML = PASTA / ".github" / "workflows" / "qualidade.yml"


def passos(texto):
    """Quebra o YAML em passos (blocos que começam em '      - ')."""
    return re.split(r"(?m)^(?=      - )", texto.split("    steps:\n", 1)[1])


class QualidadeSemSilencio(unittest.TestCase):
    def setUp(self):
        self.texto = YML.read_text(encoding="utf-8")

    def test_nenhum_passo_engole_a_falha_com_or_true(self):
        self.assertNotIn("|| true", self.texto)
        self.assertNotIn("||true", self.texto)

    def test_so_dois_passos_continuam_apos_falha_e_cada_um_tem_portao(self):
        com = [p.split("\n", 1)[0] for p in passos(self.texto) if "continue-on-error: true" in p]
        self.assertEqual(len(com), 2, com)  # os testes de Python (travados por "Falhar se os testes falharam") e o rastreamento de links
        self.assertIn("Falhar se os testes falharam", self.texto)
        self.assertIn("python qa/portao_links.py", self.texto)

    def test_as_verificacoes_rodam_mesmo_depois_de_uma_falha(self):
        """Sem `if: !cancelled()` a primeira falha pularia as demais e as issues não seriam abertas."""
        for p in passos(self.texto):
            if re.search(r"run: (node \w+\.mjs|npx html-validate|python qa/publicado\.py|python qa/achados_qualidade\.py|python issues\.py)", p):
                self.assertIn("if: ${{ !cancelled() }}", p, p.split("\n", 1)[0])

    def test_os_passos_de_navegador_do_workflow_existem(self):
        for m in re.finditer(r"node (\w+\.mjs)", self.texto):
            self.assertTrue((PASTA / "qa" / m.group(1)).exists(), m.group(1))


class PortaoDosLinks(unittest.TestCase):
    def avaliar(self, corpo, passo="failure"):
        with tempfile.TemporaryDirectory() as d:
            arq = Path(d) / "links.json"
            if corpo is not None:
                arq.write_text(corpo if isinstance(corpo, str) else json.dumps(corpo), encoding="utf-8")
            return portao_links.avaliar(arq, passo)

    def link(self, url, estado="OK", status=200):
        return {"url": url, "state": estado, "status": status, "parent": "http://127.0.0.1:8765/"}

    def test_link_externo_quebrado_nao_reprova(self):
        rel = {"links": [self.link("http://127.0.0.1:8765/"), self.link("https://faculdade.exemplo/edital.pdf", "BROKEN", 404)]}
        self.assertEqual(self.avaliar(rel), [])

    def test_link_interno_quebrado_reprova(self):
        rel = {"links": [self.link("http://127.0.0.1:8765/"), self.link("http://127.0.0.1:8765/faculdade/nao-existe/", "BROKEN", 404)]}
        achados = self.avaliar(rel)
        self.assertEqual(len(achados), 1)
        self.assertIn("nao-existe", achados[0])

    def test_rastreamento_sem_resultado_reprova(self):
        self.assertTrue(self.avaliar(None))
        self.assertTrue(self.avaliar(""))
        self.assertTrue(self.avaliar("{nao e json"))
        self.assertTrue(self.avaliar({"links": []}))

    def test_falha_do_linkinator_sem_link_quebrado_reprova(self):
        rel = {"links": [self.link("http://127.0.0.1:8765/")]}
        self.assertEqual(self.avaliar(rel, "success"), [])
        self.assertTrue(self.avaliar(rel, "failure"))

    def test_estado_sem_problema_passa(self):
        self.assertEqual(self.avaliar({"links": [self.link("http://127.0.0.1:8765/")]}, "success"), [])


class HtmlSemPapelRedundante(unittest.TestCase):
    def test_nenhuma_pagina_usa_div_com_role_region(self):
        """html-validate (prefer-native-element): <div role="region"> deve ser <section aria-label>. Eram 40 fichas de edital com a barra de prazo."""
        achados = [str(p.relative_to(PASTA / "docs")) for p in (PASTA / "docs").rglob("index.html")
                   if re.search(r'<div\b[^>]*\brole="region"', p.read_text(encoding="utf-8"))]
        self.assertEqual(achados, [])


class ScriptsDeQaRodamPeloWorkflow(unittest.TestCase):
    def test_numeros_do_dia_importa_os_modulos_da_raiz(self):
        """Rodando como o contar_notificacoes.yml (python qa/numeros_do_dia.py), sem as chaves do banco o script deve parar na chave que falta
        (KeyError), nunca em ModuleNotFoundError ('No module named tempo', falha de 14/11/2026 no workflow)."""
        import os
        import subprocess
        env = {k: v for k, v in os.environ.items() if k not in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY")}
        p = subprocess.run([sys.executable, "qa/numeros_do_dia.py"], cwd=PASTA, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertNotEqual(p.returncode, 0)
        self.assertNotIn("ModuleNotFoundError", p.stderr)
        self.assertIn("SUPABASE_URL", p.stderr)


if __name__ == "__main__":
    unittest.main()
