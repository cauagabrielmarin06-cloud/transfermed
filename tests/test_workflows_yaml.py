"""Todo workflow do GitHub Actions é um YAML válido (24/11/2026: um passo novo do qualidade.yml tinha ": " no nome, o YAML quebrou e a Qualidade
não rodou nenhuma vez; a suíte não notou). Pede o pacote PyYAML; sem ele o teste é pulado."""
import unittest
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

FLUXOS = sorted((Path(__file__).resolve().parent.parent / ".github" / "workflows").glob("*.yml"))


@unittest.skipIf(yaml is None, "PyYAML não instalado")
class WorkflowsValidos(unittest.TestCase):
    def test_ha_workflows(self):
        self.assertGreaterEqual(len(FLUXOS), 10)

    def test_cada_workflow_e_yaml_valido_com_jobs_e_passos(self):
        for f in FLUXOS:
            with self.subTest(workflow=f.name):
                doc = yaml.safe_load(f.read_text(encoding="utf-8"))
                self.assertIsInstance(doc, dict, f.name)
                self.assertTrue(doc.get("jobs"), f"{f.name}: sem jobs")
                for nome, job in doc["jobs"].items():
                    self.assertTrue(job.get("steps") or job.get("uses"), f"{f.name}/{nome}: sem passos")
                    for passo in job.get("steps") or []:
                        self.assertTrue(passo.get("run") or passo.get("uses"), f"{f.name}/{nome}: passo sem run nem uses: {passo.get('name')}")


if __name__ == "__main__":
    unittest.main()
