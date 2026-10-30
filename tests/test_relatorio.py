"""Testes do relatório semanal do sócio. Rodar com: python -m unittest discover tests"""
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import relatorio  # noqa: E402

FAC = {"ufla": {"sigla": "UFLA", "cidade": "Lavras"}}
# variáveis do relatório vazias (o resto do ambiente, como o PATH do git, fica)
VAZIO = {v: "" for v in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "BREVO_API_KEY", "REMETENTE_EMAIL", "CONTATO_DESTINO",
                         "GITHUB_TOKEN", "GITHUB_REPOSITORY")}


class BancoFalso:
    def __init__(self, eventos, assinantes, expostos):
        self._e, self._a, self._x = eventos, assinantes, expostos

    def eventos(self, desde):
        return [e for e in self._e if e["dia"] >= desde.isoformat()]

    def assinantes(self):
        return self._a

    def estrutura(self):
        return self._x


class Periodos(unittest.TestCase):
    def test_semana_passada_e_de_segunda_a_domingo(self):
        self.assertEqual(relatorio.semana_passada(date(2026, 11, 2)), (date(2026, 10, 26), date(2026, 11, 1)))
        self.assertEqual(relatorio.semana_passada(date(2026, 11, 5)), (date(2026, 10, 26), date(2026, 11, 1)))
        self.assertEqual(relatorio.semana_passada(date(2026, 11, 8)), (date(2026, 10, 26), date(2026, 11, 1)), "domingo: a semana dele ainda não acabou")

    def test_confirmacao_tarde_da_noite_conta_no_dia_de_brasilia(self):
        # 01/11 às 23h30 em Brasília = 02/11 02:30 UTC: conta no domingo
        self.assertEqual(relatorio.dia_local("2026-11-02T02:30:00+00:00"), date(2026, 11, 1))

    def test_variacao(self):
        self.assertEqual(relatorio.variacao(150, 100), "+50%")
        self.assertEqual(relatorio.variacao(50, 100), "-50%")
        self.assertEqual(relatorio.variacao(3, 0), "novo")
        self.assertEqual(relatorio.variacao(0, 0), "=")


class Numeros(unittest.TestCase):
    EVENTOS = [{"dia": "2026-10-20", "nome": "visita", "total": 40}, {"dia": "2026-10-27", "nome": "visita", "total": 50},
               {"dia": "2026-10-28", "nome": "visita", "total": 10}, {"dia": "2026-10-28", "nome": "diagnostico_concluido", "total": 4}]
    ASSINANTES = [{"status": "ativo", "criado_em": "2026-10-20T12:00:00+00:00", "confirmado_em": "2026-10-20T12:05:00+00:00"},
                  {"status": "ativo", "criado_em": "2026-10-27T12:00:00+00:00", "confirmado_em": "2026-10-28T12:00:00+00:00"},
                  {"status": "pendente", "criado_em": "2026-10-30T12:00:00+00:00", "confirmado_em": None}]

    def test_semana_e_anterior(self):
        ini, fim = date(2026, 10, 26), date(2026, 11, 1)
        self.assertEqual(relatorio.somar_eventos(self.EVENTOS, ini, fim)["visita"], 60)
        self.assertEqual(relatorio.somar_eventos(self.EVENTOS, date(2026, 10, 19), date(2026, 10, 25))["visita"], 40)
        self.assertEqual(relatorio.contar_assinantes(self.ASSINANTES, ini, fim), {"novos": 2, "confirmados": 1, "ativos": 2})

    def test_curva_tem_8_semanas_e_ativos_acumulados(self):
        c = relatorio.curva(self.EVENTOS, self.ASSINANTES, date(2026, 11, 1))
        self.assertEqual(len(c), 8)
        self.assertEqual(c[-1]["semana"], date(2026, 10, 26))
        self.assertEqual([x["ativos"] for x in c[-2:]], [1, 2])
        self.assertEqual([x["visitas"] for x in c[-2:]], [40, 60])

    def test_estrutura_aponta_o_que_falta_no_banco(self):
        sql = "create table if not exists public.eventos (\ncreate or replace function public.medir(\ncreate or replace function public.agenda("
        self.assertEqual(relatorio.faltando_no_banco(sql, {"eventos", "rpc/medir"}), ["função agenda"])

    def test_base_separa_ciclo_atual_historico_e_retificacao(self):
        antes = [{"id": "a", "fonte_dados": "manual", "retificacoes": ["r1"]}]
        depois = antes + [
            {"id": "b", "fonte_dados": "manual", "faculdade_id": "ufla", "inscricao_fim": "2026-11-04", "retificacoes": ["r2"]},
            {"id": "c", "fonte_dados": "manual", "faculdade_id": "ufla", "inscricao_fim": "2025-06-01"},
            {"id": "d", "fonte_dados": "manual", "faculdade_id": "ufla", "semestre_ingresso": "2026.1"},  # sem prazo, encerrado
            {"id": "e", "fonte_dados": "regras", "faculdade_id": "ufla", "url_edital": "https://x/e.pdf"}]
        m = relatorio.mudancas_da_base(antes, depois, date(2026, 10, 26))
        self.assertEqual([e["id"] for e in m["novos_atuais"]], ["b"])
        self.assertEqual(m["novos_historico"], 2)
        self.assertEqual(m["retificacoes"], ["r2"])
        self.assertEqual([e["id"] for e in m["achados_robo"]], ["e"])


class Envio(unittest.TestCase):
    def test_relatorio_completo_sem_email_de_ninguem(self):
        banco = BancoFalso(Numeros.EVENTOS, Numeros.ASSINANTES, {"eventos", "assinantes"})
        with mock.patch.object(relatorio, "issues_abertas", return_value={"qualidade": 2}):
            d, fac = relatorio.coletar(date(2026, 11, 2), banco)
        assunto, html, texto = relatorio.montar(d, fac)
        self.assertIn("Semana de 26/10 a 01/11", assunto)
        self.assertIn("60 visitas (+50%)", assunto)
        self.assertIn("Visitas (páginas abertas): 60 (anterior 40) +50%", texto)
        self.assertIn("Alertas ativos no fim da semana: 2 (anterior 1) +100%", texto)
        self.assertIn("qualidade: 2", texto)
        self.assertIn("Supabase desatualizado", texto)
        self.assertNotRegex(html + texto, r"[\w.-]+@[\w-]+\.", "nenhum endereço de e-mail no relatório")

    def test_sem_enviar_nao_chama_o_brevo(self):
        with mock.patch.object(relatorio.requests, "post") as post, mock.patch("builtins.print"), \
                mock.patch.dict("os.environ", VAZIO):
            self.assertEqual(relatorio.main(["--hoje", "2026-11-02"]), 0)
        post.assert_not_called()

    def test_registro_publico_do_envio_nao_mostra_numeros(self):
        env = {"BREVO_API_KEY": "k", "REMETENTE_EMAIL": "r@x.br", "CONTATO_DESTINO": "d@x.br"}
        saida = []
        with mock.patch.object(relatorio.requests, "post") as post, mock.patch("builtins.print", side_effect=saida.append), \
                mock.patch.dict("os.environ", {**VAZIO, **env}):
            post.return_value = mock.Mock(ok=True, status_code=201)
            self.assertEqual(relatorio.main(["--enviar", "--hoje", "2026-11-02"]), 0)
        self.assertEqual(post.call_args.kwargs["json"]["to"], [{"email": "d@x.br"}])
        self.assertEqual(saida, ["Relatório da semana 26/10 a 01/11: envio HTTP 201"])


if __name__ == "__main__":
    unittest.main()
