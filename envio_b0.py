"""Envio de UM e-mail institucional do B0 (Perfil oficial grátis) pelo Brevo, a partir de contato@transfermed.com.br.

O conteúdo (destinatário, assunto, texto) NÃO fica no repositório público: vem do segredo B0_PAYLOAD (JSON) do GitHub, que o Actions mascara nos logs.
Só texto (sem HTML): o Brevo não insere pixel de abertura; nenhum link é reescrito. Nada do conteúdo ou do endereço é impresso: só o código da mensagem.
Uso (workflow envio_b0.yml): B0_PAYLOAD='{"para": "...", "assunto": "...", "corpo": "..."}' BREVO_API_KEY=... python envio_b0.py
"""
import json
import os
import sys

import requests

REMETENTE = "contato@transfermed.com.br"
NOME = "Cauã, do Transfermed"


def montar(payload):
    """Corpo da chamada do Brevo: texto puro, sem rastreador, resposta para o próprio remetente."""
    for campo in ("para", "assunto", "corpo"):
        if not isinstance(payload.get(campo), str) or not payload[campo].strip():
            raise ValueError(f"payload sem {campo}")
    if "@" not in payload["para"] or " " in payload["para"].strip():
        raise ValueError("destinatário inválido")
    return {"sender": {"email": REMETENTE, "name": NOME},
            "to": [{"email": payload["para"].strip(), "contactPixelTrackingConsent": False}],
            "replyTo": {"email": REMETENTE},
            "subject": payload["assunto"].strip(),
            "textContent": payload["corpo"].strip() + "\n"}


def enviar(payload, chave, post=None):
    r = (post or requests.post)("https://api.brevo.com/v3/smtp/email", timeout=30, json=montar(payload),
             headers={"api-key": chave, "Content-Type": "application/json", "accept": "application/json"})
    if r.status_code >= 300:
        return None, r.status_code, (r.text or "")[:200].replace(payload["para"], "[destinatário]")
    return (r.json() or {}).get("messageId"), r.status_code, ""


def main():
    try:
        payload = json.loads(os.environ["B0_PAYLOAD"])
        chave = os.environ["BREVO_API_KEY"]
    except (KeyError, ValueError):
        print("faltam B0_PAYLOAD (JSON) ou BREVO_API_KEY")
        return 2
    msg, status, erro = enviar(payload, chave)
    if msg is None:
        print(f"FALHOU: HTTP {status} {erro}")
        return 1
    print(f"enviado: HTTP {status}, messageId {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
