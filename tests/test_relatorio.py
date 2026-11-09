"""Testes do relatório semanal do sócio. Rodar com: python -m unittest discover tests"""
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import relatorio  # noqa: E402

FAC = {"ufla": {"sigla": "UFLA", "cidade": "Lavras"}}
# variáveis do relatório vazias (o resto do ambiente, como o PATH do git, fica)
VAZIO = {v: "" for v in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "BREVO_API_KEY", "REMETENTE_EMAIL", "CONTATO_DESTINO",
                         "GITHUB_TOKEN", "GITHUB_REPOSITORY")}


class BancoFalso:
    def __init__(self, eventos, assinantes, expostos, notificacoes=()):
        self._e, self._a, self._x, self._n = eventos, assinantes, expostos, list(notificacoes)

    def notificacoes(self, desde):
        return [n for n in self._n if n["enviado_em"][:10] >= desde.isoformat()]

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


class TesteR1(unittest.TestCase):
    def test_taxa_de_interesse_no_relatorio_e_evento_no_banco(self):
        import re
        sql = (relatorio.PASTA / "supabase" / "schema.sql").read_text(encoding="utf-8")
        self.assertIn("'pro_interesse'", sql)
        self.assertIn("pro_interesse", [c for c, _ in relatorio.FUNIL])
        ev = {c: 0 for c, _ in relatorio.FUNIL}
        ev.update(diagnostico_concluido=40, pro_interesse=6)
        d = {"semana": (date(2026, 10, 26), date(2026, 11, 1)), "gerado_em": "x", "eventos": ev, "eventos_ant": dict(ev, pro_interesse=0),
             "assinantes": None, "assinantes_ant": None, "curva": [], "base": None, "prazos": [], "conferir": [], "issues": None,
             "faltando": [], "cobertura": None, "cobertura_ant": None}
        _, _, texto = relatorio.montar(d, FAC)
        self.assertRegex(texto, r"meta do teste R1: 10%\): 15% \(anterior 0%\)")


class OrigemDosInscritos(unittest.TestCase):
    INI, FIM = date(2026, 10, 26), date(2026, 11, 1)
    A = [{"status": "ativo", "criado_em": "2026-10-27T12:00:00+00:00", "confirmado_em": "2026-10-27T12:05:00+00:00", "canal": "instagram"},
         {"status": "ativo", "criado_em": "2026-10-28T12:00:00+00:00", "confirmado_em": None, "canal": "grupo"},
         {"status": "ativo", "criado_em": "2026-10-29T12:00:00+00:00", "confirmado_em": None, "canal": "indicacao"},
         {"status": "ativo", "criado_em": "2026-10-30T12:00:00+00:00", "confirmado_em": None, "canal": "google"},
         {"status": "ativo", "criado_em": "2026-10-30T12:00:00+00:00", "confirmado_em": None},                       # antes da medição
         {"status": "ativo", "criado_em": "2026-10-30T12:00:00+00:00", "confirmado_em": None, "canal": "https://x.br/?a=b"},  # lixo
         {"status": "ativo", "criado_em": "2026-09-01T12:00:00+00:00", "confirmado_em": None, "canal": "google"}]  # fora da semana

    def test_conta_por_canal_na_semana(self):
        o = relatorio.origem_dos_inscritos(self.A, self.INI, self.FIM)
        self.assertEqual(o["instagram"], {"novos": 1, "confirmados": 1})
        self.assertEqual(o["google"], {"novos": 1, "confirmados": 0})
        self.assertEqual(o["sem_medicao"]["novos"], 1)
        self.assertEqual(o["outro_site"]["novos"], 1, "canal que não é código conhecido nunca aparece como veio")
        self.assertNotIn("https://x.br/?a=b", o)

    def test_percentual_de_indicacao_so_sobre_os_medidos(self):
        o = relatorio.origem_dos_inscritos(self.A, self.INI, self.FIM)
        self.assertEqual(relatorio.pct_indicacao(o), 40)  # grupo + indicação em 5 medidos
        self.assertIsNone(relatorio.pct_indicacao({}))

    def test_a_consulta_pede_so_o_canal_e_nunca_o_email(self):
        import inspect
        fonte = inspect.getsource(relatorio.Banco.assinantes)
        consulta = fonte.split("select=")[1].split("&")[0]
        self.assertIn("canal:perfil->>canal", consulta)
        self.assertNotIn("email", consulta)

    def test_bloco_aparece_no_relatorio_com_a_meta(self):
        d = {"semana": (self.INI, self.FIM), "gerado_em": "x", "eventos": None, "eventos_ant": None, "assinantes": None,
             "assinantes_ant": None, "curva": [], "base": None, "prazos": [], "conferir": [], "issues": None, "faltando": [],
             "cobertura": None, "cobertura_ant": None, "origem": relatorio.origem_dos_inscritos(self.A, self.INI, self.FIM)}
        _, _, texto = relatorio.montar(d, FAC)
        self.assertIn("Origem dos inscritos no alerta", texto)
        self.assertIn("meta H1: 25%", texto)


class NumerosDoDia(unittest.TestCase):
    """Pedido do dono (08/11/2026): confirmados no total, novos em 7 dias, por origem e alertas enviados abrem todo relatório."""
    HOJE = date(2026, 11, 8)

    def assinantes(self):
        def a(status, criado, confirmado, canal):
            return {"status": status, "criado_em": criado, "confirmado_em": confirmado, "canal": canal}
        return [a("ativo", "2026-10-20T12:00:00+00:00", "2026-10-20T12:05:00+00:00", "google"),     # antes da janela
                a("ativo", "2026-11-05T12:00:00+00:00", "2026-11-05T12:05:00+00:00", "google"),     # novo e confirmado em 7 dias
                a("ativo", "2026-11-07T12:00:00+00:00", "2026-11-07T12:05:00+00:00", "instagram"),
                a("ativo", "2026-11-07T12:00:00+00:00", "2026-11-07T12:05:00+00:00", "grupo"),
                a("pendente", "2026-11-08T12:00:00+00:00", None, "direto"),                         # novo, ainda não confirmou
                a("ativo", "2026-09-01T12:00:00+00:00", "2026-09-01T12:05:00+00:00", None)]         # de antes da medição

    def test_totais_e_janela_de_sete_dias(self):
        n = relatorio.numeros_do_dia(self.assinantes(), [], self.HOJE)
        self.assertEqual((n["confirmados_total"], n["pendentes_total"], n["novos_7d"], n["confirmados_7d"]), (5, 1, 4, 3))
        self.assertEqual(n["janela"], (date(2026, 11, 2), date(2026, 11, 8)))

    def test_por_origem(self):
        o = relatorio.numeros_do_dia(self.assinantes(), [], self.HOJE)["por_origem"]
        self.assertEqual(o["google"], {"ativos": 2, "novos_7d": 1, "confirmados_7d": 1})
        self.assertEqual(o["instagram"]["novos_7d"], 1)
        self.assertEqual(o["grupo"]["ativos"], 1)
        self.assertEqual(o["direto"], {"ativos": 0, "novos_7d": 1, "confirmados_7d": 0})
        self.assertEqual(o["sem_medicao"]["ativos"], 1)

    def test_alertas_enviados_so_contam_a_janela(self):
        noti = [{"assinante_id": "a", "enviado_em": "2026-11-07T12:00:00+00:00"}, {"assinante_id": "a", "enviado_em": "2026-11-08T09:00:00+00:00"},
                {"assinante_id": "b", "enviado_em": "2026-11-01T12:00:00+00:00"}]
        self.assertEqual(relatorio.numeros_do_dia(self.assinantes(), noti, self.HOJE)["enviados"], {"alertas": 2, "inscritos": 1})
        self.assertIsNone(relatorio.numeros_do_dia(self.assinantes(), None, self.HOJE)["enviados"])

    def test_relatorio_abre_com_os_numeros_do_dia(self):
        banco = BancoFalso([], self.assinantes(), set(),
                           [{"assinante_id": "a", "enviado_em": "2026-11-07T12:00:00+00:00"}])
        with mock.patch.dict("os.environ", VAZIO):
            d, fac = relatorio.coletar(self.HOJE, banco)
        _, html, texto = relatorio.montar(d, fac)
        self.assertLess(texto.index("NÚMEROS DE HOJE"), texto.index("Inscritos novos no alerta"))
        for t in ("Alertas confirmados (ativos) no total: 5", "Inscritos novos nos últimos 7 dias", "Google 2 · 1", "Alertas enviados nos últimos 7 dias: 1 e-mails"):
            self.assertIn(t, texto)
        self.assertLess(html.index("Números de hoje"), html.index("Inscritos novos no alerta"))

    def test_sem_supabase_diz_que_nao_mediu_em_vez_de_inventar(self):
        with mock.patch.dict("os.environ", VAZIO):
            d, fac = relatorio.coletar(self.HOJE, None)
        _, _, texto = relatorio.montar(d, fac)
        self.assertIn("Números de hoje indisponíveis", texto)


class TaxaDeConfirmacao(unittest.TestCase):
    """O relatório mede o funil de confirmação (08/11/2026): confirmados ÷ pedidos de alerta, em 7 e em 28 dias."""
    HOJE = date(2026, 11, 8)

    def eventos(self):
        return [{"dia": "2026-11-07", "nome": "alerta_inscrito", "total": 10}, {"dia": "2026-11-07", "nome": "alerta_confirmado", "total": 4},
                {"dia": "2026-10-20", "nome": "alerta_inscrito", "total": 10}, {"dia": "2026-10-20", "nome": "alerta_confirmado", "total": 8},
                {"dia": "2026-10-01", "nome": "alerta_inscrito", "total": 99}]  # fora das duas janelas

    def test_sete_e_vinte_e_oito_dias(self):
        n = relatorio.numeros_do_dia([], [], self.HOJE, eventos=self.eventos())
        self.assertEqual(n["taxa_7d"], {"pedidos": 10, "confirmados": 4, "pct": 40})
        self.assertEqual(n["taxa_28d"], {"pedidos": 20, "confirmados": 12, "pct": 60})

    def test_sem_pedidos_nao_divide_por_zero_e_sem_banco_nao_inventa(self):
        self.assertIsNone(relatorio.numeros_do_dia([], [], self.HOJE, eventos=[])["taxa_7d"]["pct"])
        self.assertIsNone(relatorio.numeros_do_dia([], [], self.HOJE)["taxa_7d"])

    def test_aparece_no_topo_do_relatorio(self):
        banco = BancoFalso(self.eventos(), [], set())
        with mock.patch.dict("os.environ", VAZIO):
            d, fac = relatorio.coletar(self.HOJE, banco)
        _, _, texto = relatorio.montar(d, fac)
        self.assertIn("Taxa de confirmação em 7 dias: 40% (4 confirmaram ÷ 10 pedidos de alerta)", texto)
        self.assertLess(texto.index("Taxa de confirmação em 7 dias"), texto.index("Inscritos novos no alerta"))


if __name__ == "__main__":
    unittest.main()


class ConferirEventos(unittest.TestCase):
    def test_so_diz_se_gravou_sem_numeros(self):
        from datetime import date
        linhas = [{"dia": "2026-11-01", "nome": "radar_ponto", "total": 7}, {"dia": "2026-10-31", "nome": "porta_brasil", "total": 2}]
        r = relatorio.conferir_eventos(linhas, date(2026, 11, 1))
        self.assertIn("radar_ponto: gravado", r)
        self.assertIn("porta_brasil: ainda sem registro", r)
        self.assertFalse(any("7" in x for x in r))

    def test_eventos_conferidos_sao_os_do_banco(self):
        sql = (relatorio.PASTA / "supabase" / "schema.sql").read_text(encoding="utf-8")
        for n in relatorio.EVENTOS_RADAR:
            self.assertIn(f"'{n}'", sql)

class CoberturaEstados(unittest.TestCase):
    FACS = {"a": {"id": "a", "uf": "PR", "paginas_editais": ["https://x"]},
            "b": {"id": "b", "uf": "PR", "paginas_editais": ["https://y"], "pendente": "bloqueado"},
            "c": {"id": "c", "uf": "PR"}, "d": {"id": "d", "uf": "SP", "wordpress": "https://w"}}
    EDS = [{"faculdade_id": "a", "inscricao_inicio": "2026-10-01", "inscricao_fim": "2026-12-01"},
           {"faculdade_id": "d", "inscricao_inicio": "2026-10-01", "inscricao_fim": "2026-12-01", "conferir_campos": {"prova": "x"}}]

    def test_contas_por_estado(self):
        c = relatorio.cobertura_estados(self.FACS, self.EDS, "2026-11-01", {"PR": 4})
        self.assertEqual(c["PR"], {"cadastradas": 3, "emec": 4, "pct_cadastradas": 75, "robo": 1, "pct_robo": 33,
                                   "abertos": 1, "abertos_completos": 1})
        self.assertEqual((c["SP"]["abertos"], c["SP"]["abertos_completos"], c["SP"]["emec"]), (1, 0, None))
        self.assertEqual(list(c), relatorio.PRIORITARIOS)

    def test_correspondentes_nao_inflam_a_cobertura(self):
        # a base tem 3 fichas em PR, mas só 2 batem com cursos do e-MEC (de 4): 50%, não 75%
        c = relatorio.cobertura_estados(self.FACS, self.EDS, "2026-11-01", {"PR": {"emec": 4, "correspondentes": 2}})
        self.assertEqual((c["PR"]["emec"], c["PR"]["pct_cadastradas"], c["PR"]["cadastradas"]), (4, 50, 3))

    def test_mesma_lista_do_site(self):
        import gerar_site
        self.assertEqual(relatorio.PRIORITARIOS, gerar_site.PRIORITARIOS)

    def test_aparece_no_relatorio(self):
        c = relatorio.cobertura_estados(self.FACS, self.EDS, "2026-11-01")
        d = {"semana": (date(2026, 10, 19), date(2026, 10, 25)), "gerado_em": "x", "eventos": None, "eventos_ant": None,
             "assinantes": None, "assinantes_ant": None, "curva": [], "base": None, "prazos": [], "conferir": [], "issues": None,
             "faltando": [], "cobertura": c, "cobertura_ant": None}
        _, html, texto = relatorio.montar(d, FAC)
        self.assertIn("Cobertura dos estados prioritários", html)
        self.assertIn("PR: 3 cadastradas (e-MEC: aguardando a contagem)", texto)



class RetornoEm30Dias(unittest.TestCase):
    """T6.4: usa só o que já existe (status, confirmado_em, atualizacao_avisada_em, canal); nunca e-mail."""
    HOJE = date(2026, 12, 6)

    def alerta(self, dias, voltou=False, canal="google", status="ativo"):
        d = (self.HOJE - timedelta(days=dias)).isoformat()
        return {"status": status, "criado_em": d + "T12:00:00+00:00", "confirmado_em": d + "T12:05:00+00:00",
                "atualizacao_avisada_em": (d + "T13:00:00+00:00") if voltou else None, "canal": canal}

    def test_sem_coorte_diz_quando_a_primeira_fecha(self):
        r = relatorio.retorno_30_dias([self.alerta(5), self.alerta(10)], self.HOJE)
        self.assertEqual((r["coorte"], r["voltaram"]), (0, 0))
        self.assertEqual(r["primeira_coorte_em"], self.HOJE - timedelta(days=10) + timedelta(days=30))
        self.assertIn("primeira coorte completa", relatorio.texto_retorno(r, self.HOJE)[0])

    def test_conta_quem_voltou_so_entre_os_ativos_com_30_dias_ou_mais(self):
        a = [self.alerta(40, True, "instagram"), self.alerta(31, False, "instagram"), self.alerta(30, True, "google"),
             self.alerta(29, True), self.alerta(60, True, status="pendente")]
        r = relatorio.retorno_30_dias(a, self.HOJE)
        self.assertEqual((r["coorte"], r["voltaram"]), (3, 2))
        self.assertEqual(r["por_canal"]["instagram"], {"coorte": 2, "voltaram": 1})

    def test_amostra_pequena_e_avisada_e_o_n_aparece(self):
        r = relatorio.retorno_30_dias([self.alerta(40, True), self.alerta(41)], self.HOJE)
        texto = " ".join(relatorio.texto_retorno(r, self.HOJE))
        self.assertTrue(r["amostra_pequena"])
        self.assertIn("2 alerta(s) ativo(s) com 30 dias ou mais; 1 voltaram", texto)
        self.assertIn("Amostra pequena", texto)
        self.assertIn("não a saída", texto)

    def test_amostra_grande_nao_leva_o_aviso(self):
        r = relatorio.retorno_30_dias([self.alerta(40 + i, i % 2 == 0) for i in range(40)], self.HOJE)
        self.assertFalse(r["amostra_pequena"])
        self.assertNotIn("Amostra pequena", " ".join(relatorio.texto_retorno(r, self.HOJE)))

    def test_nada_pessoal_na_saida(self):
        a = self.alerta(40, True)
        a["email"] = "pessoa@exemplo.com"
        texto = str(relatorio.retorno_30_dias([a], self.HOJE)) + " ".join(relatorio.texto_retorno(relatorio.retorno_30_dias([a], self.HOJE), self.HOJE))
        self.assertNotIn("pessoa@exemplo.com", texto)

    def test_consulta_ao_banco_pede_so_colunas_sem_email(self):
        import inspect
        fonte = inspect.getsource(relatorio.Banco.assinantes)
        self.assertIn("atualizacao_avisada_em", fonte)
        self.assertNotIn("email", fonte)
