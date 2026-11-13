"""Relógio único do Transfermed: toda data e "hoje" do site, do radar, do monitor e dos alertas vêm daqui, em America/Sao_Paulo.

Os runners do GitHub Actions rodam em UTC: `date.today()` ali vira "amanhã" a partir das 21h de Brasília, e o site mostrava
"Atualizado em 13/11" às 21h53 de 12/11. Nenhum módulo deve chamar date.today(), datetime.now() sem fuso ou datetime.utcnow().
Timestamps de registro (criado_em, confirmado_em, executado_em_utc) continuam em UTC com fuso explícito: isso é instante, não "dia".

Para testar, troque o relógio com `tempo.RELOGIO = lambda: datetime(2026, 11, 13, 2, 30, tzinfo=timezone.utc)` (ou use `tempo.fixar`).
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BRASILIA = ZoneInfo("America/Sao_Paulo")
RELOGIO = None  # só os testes mexem: função sem argumentos que devolve um datetime com fuso


def agora_utc():
    """Instante atual com fuso UTC (para carimbos de registro)."""
    return (RELOGIO() if RELOGIO else datetime.now(timezone.utc)).astimezone(timezone.utc)


def agora():
    """Instante atual em Brasília."""
    return agora_utc().astimezone(BRASILIA)


def hoje():
    return agora().date()


def hoje_iso():
    return hoje().isoformat()


def hora_hm():
    return agora().strftime("%H:%M")


def dia_local(quando):
    """Timestamp ISO (com 'Z' ou fuso) -> data em Brasília; ISO sem fuso é tratado como UTC. Vazio -> None."""
    if not quando:
        return None
    d = datetime.fromisoformat(str(quando).replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(BRASILIA).date()


def dia_local_iso(quando):
    d = dia_local(quando)
    return d.isoformat() if d else ""


@contextmanager
def fixar(instante):
    """Teste: `with tempo.fixar(datetime(2026, 11, 13, 2, 30, tzinfo=timezone.utc)):` -> em Brasília são 23:30 de 12/11."""
    global RELOGIO
    antes = RELOGIO
    RELOGIO = lambda: instante
    try:
        yield
    finally:
        RELOGIO = antes
