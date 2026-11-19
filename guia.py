"""Guia Exterior → Brasil: o interruptor da venda (plano de receita de 19/11/2026).

O botão "Comprar", o preço e as chamadas nas outras páginas SÓ existem quando há um link de compra real. Sem link, a página
/guia-exterior/ é gerada em pré-lançamento (fora do Google, sem botão, sem preço, sem ninguém apontando para ela).

Onde fica o link (nunca no Git; o repositório é público e a estratégia fica em privado/):
  1. variável de ambiente LINK_COMPRA_GUIA (os robôs do GitHub Actions: Settings > Variables > LINK_COMPRA_GUIA);
  2. senão, a primeira linha de privado/receita/link_compra.txt (a máquina do dono e as sessões do Claude Code).
Os robôs rodam sem a pasta privado/: sem a variável, o próximo `gerar_site.py` deles tira o botão do ar. Por isso o gerar_site imprime
o estado do guia no fim e tests/test_guia.py confere que todo workflow que gera o site recebe a variável.

O preço é opcional, na mesma lógica: variável GUIA_PRECO ou a primeira linha de privado/receita/preco.txt, no formato "R$ 47" ou
"R$ 47,00". Sem preço, a página não cita valor (o valor aparece na página de pagamento da plataforma).
"""
import os
import re
from pathlib import Path
from urllib.parse import urlparse

PASTA = Path(__file__).resolve().parent
ARQUIVO_LINK = PASTA / "privado" / "receita" / "link_compra.txt"
ARQUIVO_PRECO = PASTA / "privado" / "receita" / "preco.txt"
PRECO = re.compile(r"^R\$ ?\d{1,4}(,\d{2})?$")


def _primeira_linha(arquivo):
    try:
        for linha in Path(arquivo).read_text(encoding="utf-8-sig").splitlines():
            if linha.strip():
                return linha.strip()
    except OSError:
        pass
    return ""


def link_valido(valor):
    """https, com domínio, sem usuário/senha na URL, sem espaço nem aspas: um link de pagamento de verdade, não texto solto."""
    v = (valor or "").strip()
    if not v or len(v) > 300 or re.search(r"[\s\"'<>]", v):
        return ""
    try:
        u = urlparse(v)
    except ValueError:
        return ""
    if u.scheme != "https" or not u.hostname or "." not in u.hostname or u.username or u.password:
        return ""
    return v


def link_compra(env=None, arquivo=None):
    """O link de compra válido, ou "" (pré-lançamento)."""
    env = os.environ if env is None else env
    return link_valido(env.get("LINK_COMPRA_GUIA", "")) or link_valido(_primeira_linha(arquivo or ARQUIVO_LINK))


def preco(env=None, arquivo=None):
    """"R$ 47" se informado e no formato certo; senão "" (a página não cita preço)."""
    env = os.environ if env is None else env
    for valor in (env.get("GUIA_PRECO", "").strip(), _primeira_linha(arquivo or ARQUIVO_PRECO)):
        if PRECO.match(valor):
            return valor
    return ""


def ativo(env=None, arquivo=None):
    return bool(link_compra(env, arquivo))


def estado(env=None, arquivo=None):
    """Uma linha para o registro da geração: o estado nunca muda sem aparecer no log."""
    if link_compra(env, arquivo):
        return "Guia Exterior: ATIVO (botão de compra e chamadas no site)"
    return "Guia Exterior: pré-lançamento (sem link de compra: página fora do Google, sem botão, sem preço, sem chamadas)"
