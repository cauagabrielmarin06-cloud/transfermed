"""
Nota automática de entregabilidade (10/11/2026). A cada mudança dos modelos de e-mail (nutricao.py) o workflow entregabilidade.yml roda isto:

 1. confere o contrato de cada modelo (entregabilidade.checar_email): falhou = trava, sem enviar nada;
 2. envia uma cópia de cada modelo (confirmação, alerta e lembrete com valor, com dados FICTÍCIOS) para o mail-tester, com os mesmos
    cabeçalhos do envio real (List-Unsubscribe, one-click, Reply-To), usando a conta do dono (secret MAILTESTER_USUARIO);
 3. lê a nota (0 a 10) e grava em data/nota_entrega.json, com a impressão digital dos modelos;
 4. nota abaixo de 9 = sai com erro (workflow vermelho) e os envios reais (alertas.py, lembrete_valor.py) param até a correção.

Sem a conta do mail-tester (MAILTESTER_USUARIO) a nota fica "não medida" e o envio segue: nada é inventado. O registro é público:
só tem hash, data, nota e o motivo; nunca e-mail.

uso: python nota_entrega.py [--enviar]    (sem --enviar só confere o contrato)
"""
import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone

import alertas
import entregabilidade as en
import nutricao

HOJE_FICTICIO = "2026-11-18"


def modelos_de_teste(site):
    """Os modelos que mais pesam na entrega, com dados fictícios: ([(nome, (assunto, html, texto))], token)."""
    fac = {"id": "x", "nome": "Faculdade Exemplo", "sigla": "FEX", "cidade": "Cidade", "uf": "SP", "tipo": "particular", "lat": 0, "lon": 0}
    ed1 = {"id": "e1", "faculdade_id": "x", "fonte_dados": "manual", "modalidade": "externa", "url_edital": site + "/exemplo.pdf",
           "inscricao_inicio": "2026-11-01", "inscricao_fim": "2026-11-25", "conferido_em": "2026-11-09"}
    ed2 = dict(ed1, id="e2", inscricao_fim="2026-12-10")
    ctx = nutricao.Contexto([ed1, ed2], {"x": fac}, site, HOJE_FICTICIO)
    a = {"id": "a1", "email": "teste@exemplo.org", "token": str(uuid.uuid4()), "status": "pendente",
         "perfil": {"curso": "medicina", "origem": "brasil", "semestre": 5}}
    itens = [(ed1, fac), (ed2, fac)]
    return [("confirmação", nutricao.confirmacao(a, site, 7, 0)), ("alerta", nutricao.alerta(dict(a, status="ativo"), ctx, itens)),
            ("lembrete com valor", nutricao.lembrete_valor(a, ctx, itens, 7, 1))], a["token"]


def main(argv=None, env=None, http=None, dormir=None, agora=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--enviar", action="store_true")
    args = ap.parse_args(argv)
    env = os.environ if env is None else env
    modelos, token = modelos_de_teste(en.SITE)
    problemas = {nome: en.checar_email(*m) for nome, m in modelos}
    if any(problemas.values()):
        for nome, p in problemas.items():
            for x in p:
                print(f"  contrato do modelo “{nome}”: {x}")
        print("Entregabilidade: um modelo de e-mail descumpre o contrato; publicação travada")
        return 1
    print(f"Entregabilidade: {len(modelos)} modelos cumprem o contrato (multipart, abertura, até 2 links diretos, sem venda, rodapé)")
    registro = {"hash": en.hash_modelos(), "gerado_em": (agora or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
                "estado": "nao_medido", "nota": None, "detalhe": ""}
    usuario = (env.get("MAILTESTER_USUARIO") or "").strip()
    if not args.enviar:
        registro["detalhe"] = "só o contrato foi conferido (sem --enviar)"
    elif not usuario:
        registro["detalhe"] = "falta a conta do mail-tester (secret MAILTESTER_USUARIO)"
    elif not all(env.get(v) for v in ("BREVO_API_KEY", "REMETENTE_EMAIL")):
        registro["detalhe"] = "faltam BREVO_API_KEY ou REMETENTE_EMAIL"
    else:
        um_clique, situacao = en.um_clique_url(env["SUPABASE_URL"]) if env.get("SUPABASE_URL") else (None, "sem SUPABASE_URL")
        envio = alertas.EnvioBrevo(env["BREVO_API_KEY"], env["REMETENTE_EMAIL"], env.get("REMETENTE_NOME") or "Cauã, do Transfermed", um_clique,
                                   (env.get("REPLY_TO_EMAIL") or "").strip() or None)
        notas = {}
        for nome, (assunto, html, texto) in modelos:
            sufixo = uuid.uuid4().hex[:10]
            try:
                envio.enviar(f"{usuario}-{sufixo}@mail-tester.com", assunto, html, texto, token)
            except Exception as e:  # noqa: BLE001 - o registro é público: só o tipo do erro
                notas[nome] = (None, f"envio falhou ({type(e).__name__})")
                continue
            notas[nome] = en.consultar_nota(usuario, sufixo, http=http, **({"dormir": dormir} if dormir else {}))
        medidas = {n: v[0] for n, v in notas.items() if v[0] is not None}
        registro["modelos"] = {n: v[0] for n, v in notas.items()}
        registro["descadastro_um_clique"] = situacao
        if medidas:
            registro["nota"] = min(medidas.values())  # vale a pior
            registro["estado"], registro["detalhe"] = en.decidir(registro["nota"])
            if len(medidas) < len(notas):
                registro["detalhe"] += "; " + "; ".join(f"{n}: {v[1]}" for n, v in notas.items() if v[0] is None)
        else:
            registro["detalhe"] = "; ".join(f"{n}: {v[1]}" for n, v in notas.items())
    en.REGISTRO.write_text(json.dumps(registro, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Entregabilidade: estado {registro['estado']}"
          + (f", nota {registro['nota']:.1f}/10 (mínimo {en.nota_minima(env):.0f})" if registro["nota"] is not None else f" ({registro['detalhe']})"))
    if registro["estado"] == "reprovado" and en.nota_minima(env) > 0:
        print("Nota abaixo do mínimo: publicação travada até a correção dos modelos.")
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
