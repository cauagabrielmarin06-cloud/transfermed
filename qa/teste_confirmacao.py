"""Envia ao DONO (CONTATO_DESTINO) as 3 versões do e-mail de confirmação, pelo mesmo Brevo e remetente dos e-mails reais, para ele ver
no Gmail do celular se chegam na caixa de entrada ou no spam e se o botão abre. O link leva um token de teste (a página diz que não
encontrou o cadastro): serve para conferir entrega e aparência, não para confirmar. Nada é impresso além de "enviado" (registro público).
Uso (só pelo workflow manual teste_confirmacao.yml):  python qa/teste_confirmacao.py"""
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import alertas  # noqa: E402
import nutricao  # noqa: E402


def main():
    destino = os.environ["CONTATO_DESTINO"]
    envio = alertas.EnvioBrevo(os.environ["BREVO_API_KEY"], os.environ["REMETENTE_EMAIL"], os.environ.get("REMETENTE_NOME", "Cauã, do Transfermed"))
    assinante = {"email": destino, "token": str(uuid.uuid4()), "perfil": {"curso": "medicina", "origem": "brasil", "semestre": 4}}
    for etapa in range(3):
        assunto, html, texto = nutricao.confirmacao(assinante, alertas.SITE_URL, alertas.DIAS_PARA_CONFIRMAR, etapa)
        envio.enviar(destino, assunto, html, texto, assinante["token"])
        print(f"enviado: versão {etapa}")

if __name__ == "__main__":
    main()
