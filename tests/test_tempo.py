"""13/11/2026: o relógio do site é o de Brasília. O runner roda em UTC: às 21h53 de 12/11 em Brasília já é 13/11 em UTC, e o
rodapé mostrava "Atualizado em 13/11/2026". Estes testes fixam o relógio em 12/11 23:30 de Brasília (02:30Z de 13/11) e exigem 12/11."""
import ast
import json
import re
import shutil
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))
import alertas  # noqa: E402
import gerar_site  # noqa: E402
import guardiao  # noqa: E402
import instagram_dia  # noqa: E402
import lembrete_valor  # noqa: E402
import relatorio  # noqa: E402
import tempo  # noqa: E402

# 23:30 de 12/11/2026 em Brasília = 02:30 de 13/11/2026 em UTC
NOITE = datetime(2026, 11, 13, 2, 30, tzinfo=timezone.utc)


class Relogio(unittest.TestCase):
    def test_de_noite_o_dia_e_o_de_brasilia(self):
        with tempo.fixar(NOITE):
            self.assertEqual(tempo.hoje_iso(), "2026-11-12")
            self.assertEqual(tempo.hora_hm(), "23:30")
            self.assertEqual(tempo.agora_utc().date().isoformat(), "2026-11-13", "o instante UTC continua sendo 13/11")

    def test_o_relogio_volta_ao_normal_depois_do_fixar(self):
        with tempo.fixar(NOITE):
            pass
        self.assertIsNone(tempo.RELOGIO)
        self.assertLessEqual(abs((tempo.agora_utc() - datetime.now(timezone.utc)).total_seconds()), 5)

    def test_virada_do_dia_em_brasilia(self):
        for utc, dia in (("2026-11-13T02:59:59", "2026-11-12"), ("2026-11-13T03:00:00", "2026-11-13"), ("2026-11-13T00:00:00", "2026-11-12")):
            with tempo.fixar(datetime.fromisoformat(utc).replace(tzinfo=timezone.utc)):
                self.assertEqual(tempo.hoje_iso(), dia, utc)

    def test_dia_local_de_timestamp(self):
        self.assertEqual(tempo.dia_local("2026-11-13T02:30:00Z"), date(2026, 11, 12))
        self.assertEqual(tempo.dia_local("2026-11-13T02:30:00+00:00"), date(2026, 11, 12))
        self.assertEqual(tempo.dia_local("2026-11-13T02:30:00"), date(2026, 11, 12), "sem fuso vale UTC")
        self.assertEqual(tempo.dia_local_iso("2026-11-13T12:00:00Z"), "2026-11-13")
        self.assertIsNone(tempo.dia_local(None))
        self.assertEqual(tempo.dia_local_iso(""), "")

    def test_os_outros_modulos_usam_o_mesmo_relogio(self):
        with tempo.fixar(NOITE):
            self.assertEqual(guardiao.hoje_brasilia(), "2026-11-12")
            self.assertEqual(instagram_dia.amanha_em_brasilia(), "2026-11-13")
            self.assertEqual(relatorio.dia_local(NOITE.isoformat()), date(2026, 11, 12))
            self.assertEqual(lembrete_valor.tempo.dia_local_iso(NOITE.isoformat()), "2026-11-12")

    def test_a_rodada_de_alertas_usa_o_dia_de_brasilia(self):
        """alertas.rodar sem `hoje`: o dia dos 'faltam N dias' e do limite diário é o de Brasília."""
        visto = {}

        class Banco:
            def enviados_hoje(self, hoje):
                visto["hoje"] = hoje
                raise StopIteration

        with tempo.fixar(NOITE):
            with self.assertRaises(StopIteration):
                alertas.rodar(Banco(), None, [], {})
        self.assertEqual(visto["hoje"], "2026-11-12")


class SiteGeradoDeNoite(unittest.TestCase):
    def test_gerar_site_as_21h53_de_12_11_nao_mostra_13_11(self):
        """Gera o site inteiro (numa pasta temporária) com o relógio em 12/11 23:30 de Brasília: rodapé, dados.js e hora dizem 12/11."""
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp) / "docs"
            docs.mkdir()
            shutil.copytree(gerar_site.DOCS / "assets", docs / "assets")  # o gerador lê os assets para versionar o CSS
            with tempo.fixar(NOITE), mock.patch.object(gerar_site, "DOCS", docs), mock.patch("builtins.print"):
                gerar_site.main()
            dados = (docs / "dados.js").read_text(encoding="utf-8")
            self.assertEqual(re.search(r'"gerado_em":\s*"([\d-]+)"', dados).group(1), "2026-11-12")
            self.assertEqual(re.search(r'"gerado_hora":\s*"([\d:]+)"', dados).group(1), "23:30")
            for pagina in (docs / "index.html", docs / "editais" / "index.html"):
                html = pagina.read_text(encoding="utf-8")
                self.assertIn("12/11/2026", html, f"{pagina.name}: faltou a data de Brasília")
                self.assertNotIn("13/11/2026", html, f"{pagina.name}: apareceu a data em UTC")


class NenhumRelogioProprio(unittest.TestCase):
    """Trava a regressão: ninguém volta a chamar date.today(), datetime.now() sem fuso ou utcnow() fora do tempo.py."""

    def test_sem_date_today_nem_now_sem_fuso(self):
        ruins = []
        for arq in list(PASTA.glob("*.py")) + list((PASTA / "qa").glob("*.py")):
            if arq.name == "tempo.py":
                continue
            for no in ast.walk(ast.parse(arq.read_text(encoding="utf-8"))):
                if not (isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)):
                    continue
                f = no.func
                dono = f.value.id if isinstance(f.value, ast.Name) else ""
                if (dono == "date" and f.attr == "today") or f.attr in ("utcnow", "utcfromtimestamp"):
                    ruins.append(f"{arq.name}:{no.lineno} {dono}.{f.attr}()")
                elif dono == "datetime" and f.attr in ("now", "today") and not no.args and not no.keywords:
                    ruins.append(f"{arq.name}:{no.lineno} datetime.{f.attr}() sem fuso")
        self.assertEqual(ruins, [], "use tempo.hoje()/tempo.agora()/tempo.agora_utc()")


if __name__ == "__main__":
    unittest.main()
