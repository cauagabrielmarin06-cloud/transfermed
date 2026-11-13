"""
Lembrete único com valor (09/11/2026) para quem se inscreveu, não confirmou e já passou da janela dos lembretes de 24 h e 72 h
(os pendentes de antes do funil novo, que receberam a confirmação todo dia): "N editais abertos combinam com o seu perfil".

Regras:
- só quem está pendente e ainda dentro dos 7 dias (depois disso o robô apaga o cadastro) e não cai nos lembretes normais de 24 h/72 h;
- só editais abertos e conferidos no PDF que combinam com o perfil (mesmas regras do alerta); sem nenhum edital, não envia;
- no máximo UM envio por pessoa, para sempre: o envio fica registrado em `notificacoes` com a chave "confirmacao_valor" (some junto
  com o cadastro, aos 7 dias, ou quando a pessoa cancela);
- respeita o limite diário do Brevo (alertas.LIMITE_DIARIO) e deixa a reserva dos e-mails urgentes;
- o log do Actions é público: só contagens, nunca e-mail nem conteúdo.

Uso:  python lembrete_valor.py             (ensaio: só conta quem receberia, não envia nada)
      python lembrete_valor.py --enviar    (envia de verdade; precisa dos segredos do Supabase/Brevo)
      python lembrete_valor.py --simular   (banco em arquivo e e-mails em .html)
"""
import argparse
import json
import os
import sys
import tempo
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

import alertas
import entregabilidade
import gerar_site
import nutricao

PASTA = Path(__file__).resolve().parent
CHAVE = "confirmacao_valor"  # linha em `notificacoes` que marca o envio único


editais_abertos = alertas.editais_abertos


def elegivel(a, agora, ja):
    """Pendente dentro dos 7 dias, que não cai nos lembretes normais (24 h/72 h) e ainda não recebeu este envio."""
    if a["status"] != "pendente" or CHAVE in ja:
        return False
    criado = datetime.fromisoformat(a["criado_em"].replace("Z", "+00:00"))
    if agora - criado > timedelta(days=alertas.DIAS_PARA_CONFIRMAR):
        return False
    ultima = a.get("confirmacao_enviada_em")
    ultima = datetime.fromisoformat(ultima.replace("Z", "+00:00")) if ultima else None
    # ainda na fila normal (a primeira confirmação, o lembrete de 24 h ou o de 72 h): não somar um e-mail a mais
    return alertas.etapa_da_confirmacao(criado, ultima, agora) is None and agora - criado >= alertas.LEMBRETE_2


def rodar(banco, envio, editais, faculdades, enviar=True, agora=None, hoje=None):
    """Retorna só contagens."""
    agora = agora or tempo.agora_utc()
    hoje = hoje or tempo.dia_local_iso(agora.isoformat())
    ctx = nutricao.Contexto(editais, faculdades, alertas.SITE_URL, hoje)
    r = {"pendentes": 0, "fora_da_regra": 0, "sem_edital": 0, "receberiam": 0, "enviados": 0, "parou_no_limite": False, "falhas_envio": 0,
         "ensaio": not enviar}
    restante = alertas.LIMITE_DIARIO - alertas.RESERVA_URGENTE - banco.enviados_hoje(hoje)
    for a in banco.assinantes():
        if a["status"] != "pendente":
            continue
        r["pendentes"] += 1
        ja = banco.avisados(a["id"])
        if not elegivel(a, agora, ja):
            r["fora_da_regra"] += 1
            continue
        itens = editais_abertos(a.get("perfil") or {}, editais, faculdades, hoje)
        if not itens:
            r["sem_edital"] += 1
            continue
        r["receberiam"] += 1
        if not enviar:
            continue
        if restante <= 0:
            r["parou_no_limite"] = True
            break
        try:
            envio.enviar(a["email"], *nutricao.lembrete_valor(a, ctx, itens, alertas.DIAS_PARA_CONFIRMAR), a["token"])
        except requests.RequestException:
            r["falhas_envio"] += 1
            if r["falhas_envio"] >= 3:
                break  # chave inválida ou Brevo fora do ar: não adianta insistir
            continue
        banco.registrar_avisos(a["id"], [CHAVE], agora.isoformat())  # se isto falhar, o erro sobe e nada mais é enviado
        r["enviados"] += 1
        restante -= 1
    return r


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--enviar", action="store_true", help="envia de verdade (sem isto, só conta quem receberia)")
    ap.add_argument("--simular", action="store_true", help="banco em arquivo e e-mails em .html")
    args = ap.parse_args(argv)
    faculdades = {f["id"]: f for f in json.loads((PASTA / "data" / "faculdades.json").read_text(encoding="utf-8"))}
    editais = gerar_site.aplicar_quarentena(json.loads((PASTA / "data" / "editais.json").read_text(encoding="utf-8")))
    if args.simular:
        banco = alertas.BancoSimulado(PASTA / ".trabalho" / "simulacao" / "banco.json")
        envio = alertas.EnvioSimulado(PASTA / ".trabalho" / "emails_valor")
    else:
        if not all(os.environ.get(v) for v in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "BREVO_API_KEY", "REMETENTE_EMAIL")):
            print("Faltam os segredos do Supabase/Brevo. Nada a fazer.")
            return 1
        liberado, motivo = entregabilidade.liberado(entregabilidade.ler_registro(), entregabilidade.hash_modelos())
        if not liberado:
            print(f"Envios parados pela trava de entregabilidade: {motivo}.")
            return 1
        banco = alertas.BancoSupabase(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
        um_clique, _ = entregabilidade.um_clique_url(os.environ["SUPABASE_URL"])
        envio = alertas.EnvioBrevo(os.environ["BREVO_API_KEY"], os.environ["REMETENTE_EMAIL"],
                                   os.environ.get("REMETENTE_NOME") or "Cauã, do Transfermed", um_clique,
                                   (os.environ.get("REPLY_TO_EMAIL") or "").strip() or None)
    r = rodar(banco, envio, editais, faculdades, enviar=args.enviar or False)
    print("Lembrete com valor:", json.dumps(r, ensure_ascii=False))
    return 1 if r["falhas_envio"] else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
