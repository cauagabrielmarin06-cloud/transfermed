"""Diagnóstico do envio de e-mails (roda só à mão, no GitHub Actions, com as chaves dos segredos).
O log do repositório é público: e-mails saem mascarados (c***@hotmail.com) e nada de token ou perfil.
Mostra: cadastros no Supabase (estado e horários), eventos do Brevo de cada um (entregue, rejeitado, spam...)
e a autenticação do domínio de envio no Brevo (SPF, DKIM, DMARC)."""
import os

import requests


def mascara(email):
    nome, _, dominio = (email or "").partition("@")
    return f"{nome[:1]}***@{dominio}"


def main():
    sb = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1"
    chave = os.environ["SUPABASE_SERVICE_KEY"]
    cab_sb = {"apikey": chave, "Authorization": f"Bearer {chave}"}
    brevo = {"api-key": os.environ["BREVO_API_KEY"], "accept": "application/json"}
    remetente = os.environ.get("REMETENTE_EMAIL", "")

    linhas = requests.get(f"{sb}/assinantes?select=email,status,criado_em,confirmacao_enviada_em,confirmado_em&order=criado_em",
                          headers=cab_sb, timeout=30).json()
    print(f"== Supabase: {len(linhas)} cadastro(s)")
    for a in linhas:
        print(f"- {mascara(a['email'])}: {a['status']} | criado {a['criado_em']} | confirmação enviada "
              f"{a.get('confirmacao_enviada_em')} | confirmado {a.get('confirmado_em')}")
        r = requests.get("https://api.brevo.com/v3/smtp/statistics/events", headers=brevo, timeout=30,
                         params={"email": a["email"], "days": 30, "limit": 50, "sort": "desc"})
        eventos = r.json().get("events", []) if r.ok else []
        if not r.ok:
            print(f"    Brevo respondeu {r.status_code}")
        for ev in eventos:
            print(f"    {ev.get('date')} {ev.get('event')}: {ev.get('subject')} {('(' + ev['reason'] + ')') if ev.get('reason') else ''}")
        if r.ok and not eventos:
            print("    nenhum evento no Brevo")
        b = requests.get(f"https://api.brevo.com/v3/smtp/blockedContacts", headers=brevo, timeout=30,
                         params={"limit": 100}).json()
        if any(c.get("email", "").lower() == a["email"].lower() for c in b.get("contacts", [])):
            print("    BLOQUEADO no Brevo (lista de contatos bloqueados)")

    dominio = remetente.partition("@")[2] or "transfermed.com.br"
    d = requests.get(f"https://api.brevo.com/v3/senders/domains/{dominio}", headers=brevo, timeout=30)
    print(f"== Domínio {dominio} no Brevo: HTTP {d.status_code}")
    if d.ok:
        j = d.json()
        print(f"   verificado: {j.get('verified')} | autenticado: {j.get('authenticated')}")
        for nome, reg in (j.get("dns_records") or {}).items():
            print(f"   {nome}: status={reg.get('status')} tipo={reg.get('type')} host={reg.get('host_name')} valor={reg.get('value')}")
    s = requests.get("https://api.brevo.com/v3/senders", headers=brevo, timeout=30)
    if s.ok:
        for x in s.json().get("senders", []):
            print(f"== remetente {mascara(x.get('email'))} ativo={x.get('active')}")


if __name__ == "__main__":
    main()
