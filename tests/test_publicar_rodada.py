"""publicar_rodada.sh (issue #111, 09/11/2026): o radar falhou porque alguém publicou durante a rodada e o rebase parou em conflito nos arquivos
gerados (docs/dados.js, index.html, sw.js); o laço antigo repetia `git pull` com o rebase pendente até desistir. Reproduz isso em repositórios temporários."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent
BASH = shutil.which("bash")


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=True,
                          env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}).stdout


@unittest.skipUnless(BASH, "sem bash")
class PublicarRodada(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.remoto = self.tmp / "remoto.git"
        git(self.tmp, "init", "-q", "--bare", "-b", "main", str(self.remoto))
        self.a, self.b = self.tmp / "a", self.tmp / "b"
        git(self.tmp, "clone", "-q", str(self.remoto), str(self.a))
        (self.a / "docs").mkdir()
        (self.a / "docs" / "dados.js").write_text("v0\n", encoding="utf-8")
        (self.a / "data.json").write_text("{}\n", encoding="utf-8")
        git(self.a, "checkout", "-q", "-b", "main")
        git(self.a, "add", "."); git(self.a, "commit", "-q", "-m", "base"); git(self.a, "push", "-q", "origin", "main")
        git(self.tmp, "clone", "-q", str(self.remoto), str(self.b))
        shutil.copy(PASTA / "publicar_rodada.sh", self.b / "publicar_rodada.sh")

    def rodar(self, *args):
        return subprocess.run([BASH, "publicar_rodada.sh", *args], cwd=self.b, capture_output=True, text=True, encoding="utf-8",
                              env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                                   "GIT_EDITOR": "true"}, timeout=120)

    def test_conflito_em_arquivo_gerado_nao_derruba_a_rodada(self):
        # a rodada (clone b) gera docs/dados.js; enquanto isso alguém publica outra versão do mesmo arquivo (clone a)
        (self.b / "docs" / "dados.js").write_text("da rodada\n", encoding="utf-8")
        (self.b / "data.json").write_text('{"editais": 1}\n', encoding="utf-8")
        git(self.b, "add", "."); git(self.b, "commit", "-q", "-m", "rodada")
        (self.a / "docs" / "dados.js").write_text("de outro commit\n", encoding="utf-8")
        (self.a / "outro.txt").write_text("código novo\n", encoding="utf-8")
        git(self.a, "add", "."); git(self.a, "commit", "-q", "-m", "outro"); git(self.a, "push", "-q", "origin", "main")
        r = self.rodar()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        git(self.a, "pull", "-q", "--rebase")
        self.assertEqual((self.a / "docs" / "dados.js").read_text(encoding="utf-8"), "da rodada\n", "vale o que a rodada gerou")
        self.assertTrue((self.a / "outro.txt").exists(), "o que o outro commit trouxe não se perde")
        self.assertEqual((self.a / "data.json").read_text(encoding="utf-8"), '{"editais": 1}\n')

    def test_sem_conflito_publica_na_primeira(self):
        (self.b / "data.json").write_text('{"x": 1}\n', encoding="utf-8")
        git(self.b, "add", "."); git(self.b, "commit", "-q", "-m", "rodada")
        self.assertEqual(self.rodar().returncode, 0)

    def test_o_laco_antigo_falhava_nesse_cenario(self):
        # prova que o cenário é o do defeito: pull --rebase simples para em conflito
        (self.b / "docs" / "dados.js").write_text("da rodada\n", encoding="utf-8")
        git(self.b, "add", "."); git(self.b, "commit", "-q", "-m", "rodada")
        (self.a / "docs" / "dados.js").write_text("de outro commit\n", encoding="utf-8")
        git(self.a, "add", "."); git(self.a, "commit", "-q", "-m", "outro"); git(self.a, "push", "-q", "origin", "main")
        antigo = subprocess.run(["git", "pull", "--rebase"], cwd=self.b, capture_output=True, text=True, encoding="utf-8")
        self.assertNotEqual(antigo.returncode, 0)
        subprocess.run(["git", "rebase", "--abort"], cwd=self.b, capture_output=True)


class OsWorkflowsUsamOScript(unittest.TestCase):
    def test_radar_e_monitor_regeneram_o_site_depois_de_mesclar(self):
        for arq in ("radar.yml", "monitor.yml"):
            self.assertIn("bash publicar_rodada.sh regenerar", (PASTA / ".github" / "workflows" / arq).read_text(encoding="utf-8"), arq)

    def test_script_usa_x_theirs_e_aborta_rebase_parado(self):
        t = (PASTA / "publicar_rodada.sh").read_text(encoding="utf-8")
        self.assertIn("-X theirs", t)
        self.assertIn("git rebase --abort", t)


if __name__ == "__main__":
    unittest.main()
