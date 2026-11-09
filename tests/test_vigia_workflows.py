"""Vigia dos workflows: falha ou atraso de qualquer robô vira issue com a causa provável. Nada acessa a rede."""
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))
import issues  # noqa: E402
import vigia_workflows as v  # noqa: E402

AGORA = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)


def run(id_, horas_atras, conclusao="success", evento="schedule"):
    t = (AGORA - timedelta(hours=horas_atras)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"id": id_, "created_at": t, "conclusion": conclusao, "event": evento, "html_url": f"https://github.com/x/y/actions/runs/{id_}"}


def saudavel():
    return {arq: [run(1, 1)] for arq in v.WORKFLOWS}


class Vigia(unittest.TestCase):
    def test_tudo_certo_nao_abre_nada(self):
        self.assertEqual(v.checar(saudavel(), AGORA), [])

    def test_falha_abre_issue_com_causa_provavel_e_nao_fecha_sozinha(self):
        e = saudavel()
        e["monitor.yml"] = [run(42, 3, "failure")]
        a = v.checar(e, AGORA, lambda rid: ["Testes (antes de publicar qualquer correção)"] if rid == 42 else [])
        self.assertEqual(len(a), 1)
        self.assertEqual(a[0]["etiqueta"], "workflow")
        self.assertFalse(a[0]["auto_fecha"], "a próxima sessão corrige e fecha: não pode sumir sozinha")
        self.assertIn("um teste travou", a[0]["corpo"])
        self.assertIn("antes de qualquer outra tarefa", a[0]["corpo"])
        self.assertIn("/runs/42", a[0]["corpo"])

    def test_push_recusado_tem_causa_propria(self):
        self.assertIn("push", v.causa_provavel(["Salvar resultados no repositório"]))

    def test_cada_execucao_que_falhou_e_uma_issue_diferente(self):
        a = v.checar({**saudavel(), "radar.yml": [run(7, 1, "failure")]}, AGORA)
        b = v.checar({**saudavel(), "radar.yml": [run(8, 1, "failure")]}, AGORA)
        self.assertNotEqual(a[0]["chave"], b[0]["chave"])

    def test_execucao_cancelada_ou_pulada_nao_e_falha(self):
        e = saudavel()
        e["qualidade.yml"] = [run(5, 1, "cancelled"), run(4, 25, "success")]
        self.assertEqual(v.checar(e, AGORA), [])

    def test_workflow_que_nao_rodou_no_horario_abre_issue_que_fecha_sozinha(self):
        e = saudavel()
        e["alertas.yml"] = [run(9, 4)]  # margem de 3 h
        a = v.checar(e, AGORA)
        self.assertEqual(len(a), 1)
        self.assertTrue(a[0]["auto_fecha"])
        self.assertIn("não rodou no horário", a[0]["titulo"])

    def test_dentro_da_margem_nao_alerta(self):
        e = saudavel()
        e["alertas.yml"] = [run(9, 2.5)]
        e["radar.yml"] = [run(3, 26)]
        self.assertEqual(v.checar(e, AGORA), [])

    def test_manual_sem_execucao_nao_alerta_mas_falha_alerta(self):
        e = saudavel()
        e["envio_b0.yml"] = []
        self.assertEqual(v.checar(e, AGORA), [])
        e["envio_b0.yml"] = [run(11, 50, "failure", "workflow_dispatch")]
        self.assertEqual(len(v.checar(e, AGORA)), 1)

    def test_workflow_que_nunca_rodou_alerta(self):
        e = saudavel()
        e["monitor.yml"] = []
        self.assertIn("nunca rodou", v.checar(e, AGORA)[0]["titulo"])

    def test_descricao_de_etiqueta_cabe_no_limite_do_github(self):
        # o GitHub recusa descrição com mais de 100 caracteres (422) e isso derrubou o passo das issues na primeira rodada real
        for nome, (cor, desc) in issues.ETIQUETAS.items():
            self.assertLessEqual(len(desc), 100, nome)
            self.assertRegex(cor, r"^[0-9a-f]{6}$")
            self.assertLessEqual(len(nome), 50)

    def test_issues_py_aceita_a_fonte_e_a_etiqueta(self):
        self.assertIn("workflow", issues.ETIQUETAS)
        a = v.checar({**saudavel(), "radar.yml": [run(7, 1, "failure")]}, AGORA)
        acoes = issues.planejar(a, [], "workflows")
        self.assertEqual([x[0] for x in acoes], ["criar"])


class CoberturaDosWorkflows(unittest.TestCase):
    """Workflow novo sem vigia = falha silenciosa: o teste obriga a listar."""
    def nomes(self):
        out = {}
        for p in (PASTA / ".github" / "workflows").glob("*.yml"):
            m = re.search(r"^name:\s*(.+)$", p.read_text(encoding="utf-8"), re.M)
            out[p.name] = m.group(1).strip().strip('"')
        return out

    def test_todo_workflow_esta_na_lista_do_vigia_com_o_nome_certo(self):
        nomes = self.nomes()
        nomes.pop("vigia_workflows.yml")
        self.assertEqual(sorted(nomes), sorted(v.WORKFLOWS), "workflow novo: acrescente em vigia_workflows.WORKFLOWS e no gatilho do vigia")
        for arq, (nome, _) in v.WORKFLOWS.items():
            self.assertEqual(nomes[arq], nome)

    def test_o_gatilho_do_vigia_lista_todos_os_workflows(self):
        texto = (PASTA / ".github" / "workflows" / "vigia_workflows.yml").read_text(encoding="utf-8")
        bloco = texto.split("workflows:", 1)[1].split("types:", 1)[0]
        for nome, _ in v.WORKFLOWS.values():
            self.assertIn(f'"{nome}"', bloco)

    def test_o_guardiao_diario_tambem_confere_os_workflows(self):
        self.assertIn("vigia_workflows.py", (PASTA / ".github" / "workflows" / "guardiao.yml").read_text(encoding="utf-8"))

    def test_os_workflows_que_escrevem_no_repositorio_tentam_o_push_de_novo(self):
        for arq in ("radar.yml", "monitor.yml", "guardiao.yml"):
            t = (PASTA / ".github" / "workflows" / arq).read_text(encoding="utf-8")
            self.assertIn("bash publicar_rodada.sh", t, arq)

    def test_a_qualidade_gera_o_site_de_hoje_antes_dos_testes(self):
        t = (PASTA / ".github" / "workflows" / "qualidade.yml").read_text(encoding="utf-8")
        self.assertLess(t.index("python gerar_site.py"), t.index("python -m unittest discover tests"))


if __name__ == "__main__":
    unittest.main()
