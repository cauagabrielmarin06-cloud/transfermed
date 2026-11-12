"""Imprime os números do dia (só contagens, sem e-mail e sem enviar nada). Mesmo cálculo do relatório semanal."""
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import relatorio  # noqa: E402


def main():
    banco = relatorio.Banco(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    hoje = relatorio.dia_local(datetime.now(timezone.utc).isoformat()) or date.today()
    ass = banco.assinantes()
    try:
        noti = banco.notificacoes(hoje - timedelta(days=6))
    except Exception:
        noti = None
    try:
        ev = banco.eventos(hoje - timedelta(days=60))
    except Exception:
        ev = None
    n = relatorio.numeros_do_dia(ass, noti, hoje, eventos=ev, filtro_de_teste=getattr(banco, "filtro_de_teste", None))
    for linha in relatorio.texto_numeros_do_dia(n)[:6]:
        print(linha)


if __name__ == "__main__":
    main()
