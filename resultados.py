"""Resultados publicados dos editais (ROADMAP, item 9d; pilar P1 "Raio-X da concorrência").

REGRA ABSOLUTA: só números agregados (vagas, inscritos, aprovados), cada um com a página da fonte. NUNCA nomes, CPF,
matrícula, e-mail ou qualquer dado pessoal, nem em `data/resultados.json` nem em arquivo temporário. Por isso o
formato é fechado: só estas chaves, só inteiros nos números e só códigos fixos nas ressalvas. Qualquer outra coisa
(um nome numa observação, um CPF num endereço) é rejeitada por `validar` e pelos testes.

Formato de `data/resultados.json` (lista):
{"edital_id": "...", "faculdade_id": "...", "status": "publicado" | "nao_publicado",
 "numeros": {"vagas_ofertadas": {"valor": 30, "pagina": "2", "grandeza": "vagas_do_edital"}, "inscritos": {...}, "aprovados": {...}},
 "fonte_url": "https://...", "ressalva": "so_aprovados", "conferido_em": "2026-11-02"}
`status: nao_publicado` não tem números, leva um `motivo` (código) e a ficha mostra "resultado não publicado".
`grandeza` diz o que o número representa (classificados dentro das vagas, convocados para a próxima etapa, etc.).
"""
import json
import re
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent
ARQUIVO = PASTA / "data" / "resultados.json"

CHAVES = {"edital_id", "faculdade_id", "status", "numeros", "fonte_url", "ressalva", "conferido_em", "motivo"}
# O que cada número representa (cada faculdade publica de um jeito: comparar sem saber a grandeza engana quem decide)
GRANDEZAS = {
    "vagas_ofertadas": {"vagas_do_edital", "vagas_somadas_por_periodo", "vagas_remanescentes"},
    "inscritos": {"candidatos_inscritos", "candidatos_na_relacao_oficial"},
    "aprovados": {"classificados_dentro_das_vagas", "convocados_para_proxima_etapa", "deferidos_para_matricula",
                  "classificados_somando_chamadas", "classificados_somando_campi", "linhas_da_lista_de_aprovados", "a_revisar"},
}
# Por que não há número (só para status nao_publicado)
MOTIVOS = {"individual_por_email", "ainda_nao_divulgado", "sem_lista_publica_encontrada", "bloqueado_para_o_robo",
           "imagem_sem_texto_legivel", "resultado_de_outro_edital", "a_confirmar"}
NUMEROS = {"vagas_ofertadas", "inscritos", "aprovados"}
STATUS = {"publicado", "nao_publicado"}
RESSALVAS = {
    "sem_inscritos_publicados",   # a faculdade divulga os aprovados, não o total de inscritos
    "so_aprovados",               # só a lista de aprovados/classificados foi publicada
    "lista_parcial",              # a lista cobre só parte das vagas ou das chamadas
    "chamadas_multiplas",         # soma de mais de uma chamada
    "resultado_em_imagem",        # o resultado está em imagem: números lidos à mão
    "",
}
PADRAO_CPF = re.compile(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}")
PADRAO_EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
PADRAO_URL = re.compile(r"https?://[^\s\"'<>]+")


def validar(r):
    """Lista de problemas do registro (vazia = pode gravar)."""
    erros = []
    if not isinstance(r, dict):
        return ["registro não é um objeto"]
    extras = set(r) - CHAVES
    if extras:
        erros.append(f"chaves não permitidas: {sorted(extras)}")
    for c in ("edital_id", "faculdade_id", "status", "fonte_url", "conferido_em"):
        if not isinstance(r.get(c), str) or not r.get(c):
            erros.append(f"falta {c}")
    if r.get("status") not in STATUS:
        erros.append("status inválido")
    if r.get("ressalva", "") not in RESSALVAS:
        erros.append("ressalva fora da lista de códigos")
    url = r.get("fonte_url") or ""
    if not isinstance(url, str) or not PADRAO_URL.fullmatch(url):
        erros.append("fonte_url não é um endereço http(s)")
    elif PADRAO_CPF.search(url) or PADRAO_EMAIL.search(url):
        erros.append("fonte_url parece conter CPF ou e-mail")
    for c in ("edital_id", "faculdade_id", "conferido_em"):
        v = r.get(c)
        if isinstance(v, str) and (PADRAO_CPF.search(v) or PADRAO_EMAIL.search(v) or not re.fullmatch(r"[A-Za-z0-9_-]+", v)):
            erros.append(f"{c} com caracteres inesperados")
    nums = r.get("numeros", {})
    if not isinstance(nums, dict):
        return erros + ["numeros não é objeto"]
    if r.get("status") == "nao_publicado" and r.get("motivo") not in MOTIVOS:
        erros.append("nao_publicado precisa de motivo (código fixo)")
    if r.get("status") == "publicado" and "motivo" in r:
        erros.append("publicado não tem motivo")
    if r.get("status") == "nao_publicado" and nums:
        erros.append("resultado não publicado não pode ter números")
    if r.get("status") == "publicado" and not nums:
        erros.append("publicado sem números")
    if set(nums) - NUMEROS:
        erros.append(f"números não permitidos: {sorted(set(nums) - NUMEROS)}")
    for nome, item in nums.items():
        if not isinstance(item, dict) or set(item) != {"valor", "pagina", "grandeza"}:
            erros.append(f"{nome}: precisa de valor, pagina e grandeza")
            continue
        if item["grandeza"] not in GRANDEZAS.get(nome, set()):
            erros.append(f"{nome}: grandeza fora da lista de códigos")
        if not isinstance(item["valor"], int) or isinstance(item["valor"], bool) or not 0 <= item["valor"] <= 100000:
            erros.append(f"{nome}: valor precisa ser inteiro")
        if not isinstance(item["pagina"], str) or not re.fullmatch(r"[0-9]{1,3}|site", item["pagina"]):
            erros.append(f"{nome}: pagina precisa ser o número da página do PDF (ou 'site')")
    try:
        a, i = nums["aprovados"]["valor"], nums["inscritos"]["valor"]
        if isinstance(a, int) and isinstance(i, int) and a > i:
            erros.append("aprovados maiores que inscritos")
    except (KeyError, TypeError):
        pass
    return erros


def validar_todos(registros):
    """{posição: problemas}, incluindo edital repetido."""
    problemas, vistos = {}, set()
    for n, r in enumerate(registros):
        e = validar(r)
        if isinstance(r, dict):
            if r.get("edital_id") in vistos:
                e.append("edital repetido")
            vistos.add(r.get("edital_id"))
        if e:
            problemas[n] = e
    return problemas


def carregar():
    return json.loads(ARQUIVO.read_text(encoding="utf-8")) if ARQUIVO.exists() else []


def gravar(registros):
    problemas = validar_todos(registros)
    if problemas:
        raise ValueError(f"não gravado: {problemas}")
    ARQUIVO.write_text(json.dumps(registros, ensure_ascii=False, indent=1), encoding="utf-8")


def cobertura(editais, faculdades, registros, ufs=("SP", "MG", "BA", "RJ", "PR")):
    """Por UF: editais com registro, com números publicados e 'resultado não publicado'."""
    por_id = {r["edital_id"]: r for r in registros}
    saida = {}
    for uf in ufs:
        ids = [e["id"] for e in editais if faculdades.get(e["faculdade_id"], {}).get("uf") == uf and e["id"] in por_id]
        pub = sum(1 for i in ids if por_id[i]["status"] == "publicado")
        saida[uf] = {"considerados": len(ids), "com_numeros": pub, "nao_publicado": len(ids) - pub}
    return saida


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    regs = carregar()
    p = validar_todos(regs)
    print(f"{len(regs)} registros; problemas: {p or 'nenhum'}")
    sys.exit(1 if p else 0)
