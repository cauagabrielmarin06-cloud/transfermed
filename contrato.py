"""
Contrato dos dados publicados (T6.3): o formato de cada JSON de `data/` como compromisso estável.

`contrato_dados.json` (em tests/) guarda, por arquivo, cada campo (caminho) com os tipos aceitos e se é obrigatório (presente
em todos os registros quando o contrato foi gravado). O teste (tests/test_contrato_dados.py) quebra se um campo obrigatório ou comum
(presente em metade ou mais dos registros) sumir, mudar de nome ou mudar de tipo. Campo novo e opcional é permitido (mudança aditiva): não quebra nada que já leia os dados. int e float contam como `num`;
`null` (não informado) nunca quebra o formato.

Mudar o formato de propósito: rode `python contrato.py --gravar`, descreva a mudança em docs/DADOS.md e suba `versao`.
Uso:  python contrato.py            # confere (código de saída 1 se o formato quebrou)
      python contrato.py --gravar   # regrava o contrato a partir dos dados de hoje
"""
import json
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent
ARQUIVO = PASTA / "tests" / "contrato_dados.json"
# arquivo -> caminhos cujo dicionário tem chaves livres (id, URL, UF...): descrevemos o valor com "*"
MAPAS = {
    "editais": ["evidencias", "conferir_campos"],
    "arquivo_pdfs": ["documentos"],
    "retratos": ["paginas", "pdfs"],
    "cobertura_emec": [""],
    "situacao_resultados": [""],
    "quarentena": ["editais"],
}
# o contrato vale para o que é publicado: edital achado pelo robô (fonte_dados "robo") ainda não está conferido e
# não pode travar a publicação por ter menos campos
FILTROS = {"editais": lambda r: r.get("fonte_dados") == "manual"}
PRESENCA_COMUM = 0.5   # campo presente em ao menos metade dos registros quando o contrato foi gravado é "comum"
PRESENCA_MINIMA = 0.25  # e não pode cair abaixo disto (renomear um campo comum derruba a presença a zero)
OPCIONAIS = {"quarentena"}  # criado pelo monitor na primeira execução (data/guardiao.json é resumo interno, fora do contrato)
# campos que só existem enquanto há um problema (PDF que não abre): sumir quando tudo volta ao normal não é quebra de formato
CONDICIONAIS = {"retratos": {"pdfs.*.falha_desde", "pdfs.*.ultimo_erro"}}
ARQUIVOS = ["faculdades", "editais", "resultados", "situacao_resultados", "arquivo_pdfs", "cobertura_emec", "retratos", "faculdades_exterior", "quarentena"]


def tipo(v):
    if v is None:
        return "null"
    return {bool: "bool", int: "num", float: "num", str: "str", list: "list", dict: "dict"}[type(v)]


def campos(valor, caminho, mapas, saida, registro):
    """Acumula em `saida[caminho] = {tipos}` e `registro[caminho] = n de registros com o campo`."""
    saida.setdefault(caminho, set()).add(tipo(valor))
    if isinstance(valor, dict):
        if caminho in mapas:
            for v in valor.values():
                campos(v, caminho + ".*" if caminho else "*", mapas, saida, registro)
            return
        for k, v in valor.items():
            campos(v, f"{caminho}.{k}" if caminho else k, mapas, saida, registro)
    elif isinstance(valor, list):
        for v in valor:
            if isinstance(v, (dict, list)):
                campos(v, caminho + "[]", mapas, saida, registro)
            else:
                saida.setdefault(caminho + "[]", set()).add(tipo(v))


def descrever(nome, dados):
    mapas = set(MAPAS.get(nome, []))
    registros = [r for r in dados if FILTROS.get(nome, lambda r: True)(r)] if isinstance(dados, list) else [dados]
    tipos, presentes = {}, {}
    for r in registros:
        achados = {}
        campos(r, "", mapas, achados, None)
        for caminho, ts in achados.items():
            tipos.setdefault(caminho, set()).update(ts)
            presentes[caminho] = presentes.get(caminho, 0) + 1
    # só caminhos de nível de registro contam para "obrigatório"; dentro de listas o campo depende de haver itens
    obrigatorio = {c for c, n in presentes.items() if n == len(registros) and "[]" not in c and "*" not in c}
    total = max(len(registros), 1)
    return {"forma": "lista" if isinstance(dados, list) else "objeto",
            "campos": {c: {"tipos": sorted(t), "obrigatorio": c in obrigatorio, "presenca": round(presentes[c] / total, 2)}
                       for c, t in sorted(tipos.items()) if c != ""}}


def carregar(nome):
    arq = PASTA / "data" / f"{nome}.json"
    if not arq.exists():
        return None
    return json.loads(arq.read_text(encoding="utf-8"))


def gerar():
    contrato = {"versao": 1, "arquivos": {}}
    for nome in ARQUIVOS:
        dados = carregar(nome)
        if dados is not None:
            contrato["arquivos"][nome] = descrever(nome, dados)
    return contrato


def conferir(contrato, nome, dados):
    """Lista de quebras do formato (vazia = compatível). Campo novo não é quebra."""
    esperado, quebras = contrato["arquivos"][nome], []
    if (esperado["forma"] == "lista") != isinstance(dados, list):
        return [f"{nome}: era {esperado['forma']}"]
    atual = descrever(nome, dados)["campos"]
    for caminho, regra in esperado["campos"].items():
        if caminho not in atual:
            if caminho in CONDICIONAIS.get(nome, ()):
                continue
            if regra["obrigatorio"] or regra.get("presenca", 0) >= PRESENCA_COMUM:
                quebras.append(f"{nome}: campo sumiu de todos os registros ou mudou de nome: {caminho}")
            continue
        if regra.get("presenca", 0) >= PRESENCA_COMUM and atual[caminho]["presenca"] < PRESENCA_MINIMA and "[]" not in caminho and "*" not in caminho:
            quebras.append(f"{nome}: campo comum quase sumiu ({atual[caminho]['presenca']:.0%} dos registros): {caminho}")
        novos = set(atual[caminho]["tipos"]) - set(regra["tipos"]) - {"null"}  # "não informado" (null) nunca quebra o formato
        if novos:
            quebras.append(f"{nome}.{caminho}: tipo mudou ({'/'.join(regra['tipos'])} → {'/'.join(sorted(novos))})")
        if regra["obrigatorio"] and not atual[caminho]["obrigatorio"]:
            quebras.append(f"{nome}: campo obrigatório ficou ausente em algum registro: {caminho}")
    return quebras


DOC = PASTA / "docs" / "DADOS.md"
INI, FIM = "<!-- contrato:inicio -->", "<!-- contrato:fim -->"
QUEBRA = chr(10)


def tabela_do_contrato(contrato):
    """Texto do bloco de campos de docs/DADOS.md, sempre igual ao contrato (o teste confere)."""
    linhas = [f"Versão do contrato: {contrato['versao']}.", ""]
    for nome, a in contrato["arquivos"].items():
        linhas += [f"### data/{nome}.json ({a['forma']})", "", "| Campo | Tipo | Obrigatório |", "|---|---|---|"]
        linhas += [f"| `{c}` | {' ou '.join(r['tipos'])} | {'sim' if r['obrigatorio'] else 'não'} |" for c, r in a["campos"].items()]
        linhas.append("")
    return QUEBRA.join(linhas)


def gravar_doc(contrato):
    texto = DOC.read_text(encoding="utf-8")
    antes, resto = texto.split(INI, 1)
    _, depois = resto.split(FIM, 1)
    DOC.write_text(antes + INI + QUEBRA + tabela_do_contrato(contrato) + QUEBRA + FIM + depois, encoding="utf-8")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--gravar" in argv:
        novo = gerar()
        ARQUIVO.write_text(json.dumps(novo, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        gravar_doc(json.loads(ARQUIVO.read_text(encoding="utf-8")))
        print("Contrato gravado em", ARQUIVO.relative_to(PASTA))
        return 0
    contrato = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    quebras = []
    for nome in contrato["arquivos"]:
        dados = carregar(nome)
        if dados is None:
            if nome not in OPCIONAIS:
                quebras.append(f"{nome}: arquivo sumiu")
            continue
        quebras += conferir(contrato, nome, dados)
    for q in quebras:
        print("QUEBROU:", q)
    print("Contrato dos dados:", "compatível" if not quebras else f"{len(quebras)} quebra(s)")
    return 1 if quebras else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
