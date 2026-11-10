"""Funções aprovadas e no ar: vêm LIGADAS no código. A variável do GitHub (ou do ambiente) só serve para DESLIGAR, com o valor "0".

Por que: antes elas dependiam de variável "=1". Uma geração do site sem a variável (sessão local, teste) apagava do ar o que o
robô mantinha ligado (em 06/11/2026 isso tirou o Raio-X de 58 fichas por algumas horas). Variável ausente ou vazia
(`${{ vars.X }}` vira texto vazio quando a variável não existe) = ligada.

Função nova ou ainda não aprovada NÃO entra aqui: continua desligada até alguém ligar.
Ao aprovar uma função nova e colocá-la no ar, acrescente o nome em LIGADAS_POR_PADRAO.
"""
import os

LIGADAS_POR_PADRAO = (
    "RAIO_X",               # bloco "Raio-X da concorrência" nas fichas de edital encerrado
    "CONTATO_ATIVO",        # formulário de contato
    "ENVIO_IMEDIATO",       # confirmação do alerta em ~1 minuto
    "AGENDA_UNICA",         # agenda única dos prazos
    "ALERTAS_ATIVOS",       # e-mails novos do alerta (lembretes e resumo)
    "ARQUIVAR_NO_ARCHIVE",  # cópia pública dos PDFs no Internet Archive
    "DESCADASTRO_UM_CLIQUE",  # List-Unsubscribe-Post (RFC 8058): ligada em 10/11/2026, com sonda da Edge Function (entregabilidade.py)
    "INDICACAO",            # "Avise um colega" no resultado do diagnóstico (ligada em 09/11/2026, decisão do dono de 08/11)
)


def ligada(nome):
    """True a menos que a variável valha exatamente "0"."""
    return os.environ.get(nome, "1").strip() != "0"
