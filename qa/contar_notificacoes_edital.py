"""Conta (só números) as notificações registradas para um edital: por chave e por pessoas distintas.
Uso: python qa/contar_notificacoes_edital.py <id do edital>. Nunca imprime e-mail, nome ou id de pessoa."""
import os
import sys

import requests


def main():
    ident = sys.argv[1]
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1"
    chave = os.environ["SUPABASE_SERVICE_KEY"]
    h = {"apikey": chave}
    if chave.startswith("eyJ"):
        h["Authorization"] = f"Bearer {chave}"
    r = requests.get(f"{url}/notificacoes?select=assinante_id,edital_id,enviado_em&edital_id=like.*{ident}*", headers=h, timeout=30)
    r.raise_for_status()
    linhas = r.json()
    por_chave = {}
    for x in linhas:
        por_chave.setdefault(x["edital_id"], set()).add(x["assinante_id"])
    print(f"edital {ident}: {len(linhas)} notificações, {len({x['assinante_id'] for x in linhas})} pessoas distintas")
    for k, v in sorted(por_chave.items()):
        print(f"  chave {k}: {len(v)} pessoas")
    datas = {}
    for x in linhas:
        d = (x.get("enviado_em") or "")[:16].replace("T", " ")
        datas[d] = datas.get(d, 0) + 1
    for d, n in sorted(datas.items()):
        print(f"  enviado em {d} (UTC): {n}")
    ids = {x["assinante_id"] for x in linhas}
    todos = requests.get(f"{url}/assinantes?select=id,status,confirmado_em", headers=h, timeout=30)
    todos.raise_for_status()
    dele = [x for x in todos.json() if x["id"] in ids]
    print(f"  dessas pessoas: {sum(1 for x in dele if x.get('confirmado_em'))} confirmadas de {len(dele)}")
    # Quantas pessoas pediram lembrete deste edital (perfil.seguir.lembretes), só contagem
    a = requests.get(f"{url}/assinantes?select=perfil,status", headers=h, timeout=30)
    a.raise_for_status()
    pediram = sum(1 for p in a.json() if ident in ((((p.get("perfil") or {}).get("seguir") or {}).get("lembretes")) or []))
    print(f"  pessoas que pediram lembrete deste edital: {pediram}")


if __name__ == "__main__":
    main()
