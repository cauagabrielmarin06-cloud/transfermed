"""
Inscrição de teste completa, em simulação (nada é enviado e nada toca o Supabase):
  1. usa as chamadas que o site faria (gravadas pelo qa/inscricao.mjs em qa/relatorios/inscricao.json);
  2. passa por inscrever -> confirmação -> confirmar, com a mesma regra do supabase/schema.sql (BancoSimulado);
  3. roda o alertas.py dia a dia (do dia da confirmação até o lembrete de 2 dias), com ALERTAS_ATIVOS ligado só
     dentro do banco simulado, e grava cada e-mail em privado/emails_exemplos/ e o texto de todos em privado/EMAILS.md.
uso: python qa/simular_inscricao.py
"""
import json
import shutil
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
import alertas  # noqa: E402
import nutricao  # noqa: E402

SAIDA = RAIZ / "privado" / "emails_exemplos"
CONFIRMA = date(2026, 10, 29)
DIAS = [CONFIRMA + timedelta(days=d) for d in range(0, 21)]


def main():
    chamadas = json.loads((RAIZ / "qa" / "relatorios" / "inscricao.json").read_text(encoding="utf-8"))
    faculdades = {f["id"]: f for f in json.loads((RAIZ / "data" / "faculdades.json").read_text(encoding="utf-8"))}
    editais = json.loads((RAIZ / "data" / "editais.json").read_text(encoding="utf-8"))
    shutil.rmtree(SAIDA, ignore_errors=True)
    pasta_banco = RAIZ / ".trabalho" / "simulacao_inscricao"
    shutil.rmtree(pasta_banco, ignore_errors=True)
    banco = alertas.BancoSimulado(pasta_banco / "banco.json")
    t0 = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    for c in chamadas:
        r = banco.inscrever(c["p_email"], c["p_perfil"], c["p_consentimento"], agora=t0)
        print("inscrever:", r)
    # um inscrito antigo (confirmado em 01/10, perfil Brasil): mostra o resumo de segunda com novidade de verdade
    antigo = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    banco.inscrever("teste.antigo@exemplo.com", {k: v for k, v in chamadas[1]["p_perfil"].items() if k != "seguir"},
                    chamadas[1]["p_consentimento"], agora=antigo)
    banco.confirmar(next(x["token"] for x in banco.assinantes() if x["email"] == "teste.antigo@exemplo.com"), agora=antigo)
    for a in banco.assinantes():
        print("perfil guardado:", a["email"], json.dumps(a["perfil"], ensure_ascii=False))

    registro = []  # (dia, para, assunto, texto)

    class Envio(alertas.EnvioSimulado):
        def enviar(self, para, assunto, html, texto, token, responder_para=None):
            super().enviar(para, assunto, html, texto, token, responder_para)
            registro.append((self.dia, para, assunto, texto))

    envio = Envio(SAIDA)
    envio.dia = CONFIRMA.isoformat()
    # confirmação (o e-mail de sempre), depois o clique no link
    alertas.rodar(banco, envio, editais, faculdades, hoje=CONFIRMA.isoformat(), agora=t0)
    for a in banco.assinantes():
        banco.confirmar(a["token"], agora=antigo if a["email"].startswith("teste.antigo") else t0)
    for dia in DIAS:
        envio.dia = dia.isoformat()
        agora = datetime(dia.year, dia.month, dia.day, 12, 0, tzinfo=timezone.utc)  # 9h de Brasília
        resumo = alertas.rodar(banco, envio, editais, faculdades, hoje=dia.isoformat(), agora=agora, novos_ativos=True)
        if any(resumo["novos"].values()) or resumo["alertas"] or resumo["confirmacoes"]:
            print(dia, "alertas:", resumo["alertas"], "novos:", resumo["novos"])

    # simulação sem ALERTAS_ATIVOS: monta os e-mails, mas não registra nada (pode ligar depois sem repetir)
    antes = json.loads((pasta_banco / "banco.json").read_text(encoding="utf-8"))["notificacoes"]
    contador = alertas.EnvioContador()
    alertas.rodar(alertas.BancoSimulado(pasta_banco / "banco.json"), contador, editais, faculdades, hoje=CONFIRMA.isoformat(),
                  agora=t0, novos_ativos=False, envio_teste=contador)
    depois = json.loads((pasta_banco / "banco.json").read_text(encoding="utf-8"))["notificacoes"]
    assert antes == depois, "a simulação não pode registrar nada no banco"

    linhas = ["# E-mails do alerta (exemplos gerados na inscrição de teste)", "",
              f"Gerado por `python qa/simular_inscricao.py` em {date.today().strftime('%d/%m/%Y')}. Três inscritos de teste: "
              "um da ficha da Unime (\"Me lembre 7 e 2 dias antes\", perfil Brasil, 5º semestre) e um da página "
              "\"Estudo no exterior\" (pulou o passo 2), mais um inscrito antigo (confirmado em 01/10) para mostrar o resumo de segunda. Os arquivos .html estão em `privado/emails_exemplos/`.", "",
              "**Nada disto sai de verdade enquanto a variável `ALERTAS_ATIVOS` não for `1`.** O alerta de edital e a "
              "confirmação continuam como estão.", ""]
    for dia, para, assunto, texto in registro:
        linhas += [f"## {dia[8:10]}/{dia[5:7]} · {assunto}", f"_Para: {para}_", "", "```", texto, "```", ""]
    (RAIZ / "privado" / "EMAILS.md").write_text("\n".join(linhas), encoding="utf-8")
    print(f"\n{len(registro)} e-mails gerados; texto em privado/EMAILS.md")


if __name__ == "__main__":
    main()
