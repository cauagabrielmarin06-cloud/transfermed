"""Canário do relógio: gera o site e roda a suíte inteira com um "hoje" simulado.

Por que existe (19/11/2026): a Unime encerrou em 18/11 e um teste que fixava essa ficha derrubou 8 workflows; testes presos ao
estado real dos dados (prazo que vence, edital que abre, "tem pelo menos um aberto") só falham no dia em que o dado muda.
Este script adianta o relógio (tempo.RELOGIO, o relógio único do projeto) para uma data em que o estado dos dados é outro
(tudo vencido, só o futuro distante, virada de dia em Brasília) e roda `gerar_site.py` + `unittest` desse jeito. Teste que depende
da data real aparece aqui, hoje, e não numa madrugada qualquer.

Uso (numa cópia limpa do repositório, porque gerar_site.py reescreve docs/):
    git worktree add ../canario HEAD && cd ../canario
    python qa/relogio_simulado.py 2027-03-01T12:00:00-03:00 [test_site ...]   (módulos opcionais)
Sem argumento, usa uma lista de datas e roda uma de cada vez (cada uma num processo novo).
"""
import runpy
import subprocess
import sys
import unittest
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(1, str(RAIZ / "tests"))

# Datas que mudam o estado dos dados: virada de dia (21h+ em Brasília = dia seguinte em UTC), meio do semestre, tudo vencido.
DATAS = ["2026-11-19T23:40:00-03:00", "2026-12-20T12:00:00-03:00", "2027-02-10T12:00:00-03:00", "2027-08-01T12:00:00-03:00"]


def rodar(quando, modulos=()):
    import tempo
    instante = datetime.fromisoformat(quando)
    assert instante.tzinfo, "informe o fuso (ex.: -03:00)"
    tempo.RELOGIO = lambda: instante
    print(f"== relógio simulado: {quando} (hoje em Brasília = {tempo.hoje_iso()})", flush=True)
    argv, sys.argv = sys.argv, ["gerar_site.py"]
    runpy.run_path(str(RAIZ / "gerar_site.py"), run_name="__main__")
    if modulos:  # só estes módulos (ex.: test_funcoes_ligadas): para investigar uma falha sem rodar a suíte inteira
        suite = unittest.defaultTestLoader.loadTestsFromNames(list(modulos))
    else:
        suite = unittest.defaultTestLoader.discover(str(RAIZ / "tests"))
    res = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if res.wasSuccessful() else 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(rodar(sys.argv[1], sys.argv[2:]))
    falhas = [d for d in DATAS if subprocess.run([sys.executable, __file__, d], cwd=RAIZ).returncode]
    print("\nFalharam:", falhas or "nenhuma")
    sys.exit(1 if falhas else 0)
