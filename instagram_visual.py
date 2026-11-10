"""Medição de legibilidade das imagens do post do Instagram (10/11/2026, itens 6 do privado/PADRAO_DE_QUALIDADE.md).

Mede o que está nos pixels, sem OCR e sem depender de quem fez a imagem (robô ou revisão do dono):
  - tamanho estimado de cada linha de texto (px em uma imagem de 1080 de largura), fora do cabeçalho com o logo;
  - maior retângulo vazio da tela (sem texto, painel ou botão), em fração da área.
Texto = pixel que contrasta forte com o fundo da própria linha. Painéis e botões = corridas longas desses pixels, mais a cor dos cartões.
Os anéis do radar e os pontos de enfeite não contam como conteúdo (são finos ou pequenos demais para ter 3 letras).

O tamanho da fonte sai da altura da linha: sem descendente (g, p, q, y, parênteses) a linha tem ~0,76 da fonte; com descendente, ~0,97;
linha só de maiúsculas, ~0,73. É uma estimativa, boa até ±2 px; os limites do padrão (36 e 26 px) são folgados para isso.
"""
from pathlib import Path

CABECALHO = 200          # px do topo: logo, nome e contador de telas (marca fixa, fora da medição)
CONTRASTE = 80           # diferença de luminância para valer como texto
CORRIDA_H, CORRIDA_V = 120, 140   # corrida contínua acima disto é painel/botão/barra, não letra
CELULA = 10              # grade do retângulo vazio


def _corridas(v, folga=0):
    import numpy as np
    idx = np.flatnonzero(v)
    out = []
    if len(idx) == 0:
        return out
    ini = ant = idx[0]
    for i in idx[1:]:
        if i - ant > folga + 1:
            out.append((int(ini), int(ant)))
            ini = i
        ant = i
    out.append((int(ini), int(ant)))
    return out


def _tirar_corridas(m, limite):
    """Zera as corridas horizontais maiores que `limite` e devolve o que foi zerado (painéis, botões)."""
    import numpy as np
    tirado = np.zeros_like(m)
    for i in range(m.shape[0]):
        for a, b in _corridas(m[i]):
            if b - a + 1 > limite:
                m[i, a:b + 1] = False
                tirado[i, a:b + 1] = True
    return tirado


def analisar(caminho):
    """Devolve {"linhas": [{"y", "x0", "x1", "alt", "tam"}], "vazio": fração da tela, "menor": px, "maior": px, "w", "h"}."""
    import numpy as np
    from PIL import Image
    im = Image.open(caminho).convert("RGB")
    cor = np.asarray(im).astype(int)
    lum = np.asarray(im.convert("L")).astype(int)
    h, w = lum.shape
    forte = np.abs(lum - np.median(lum, axis=1)[:, None]) > CONTRASTE
    cheio = _tirar_corridas(forte, CORRIDA_H)
    vert = _tirar_corridas(forte.T.copy(), CORRIDA_V)
    forte = forte & ~vert.T
    cheio |= vert.T
    forte[:CABECALHO] = False

    linhas = []
    for y0, y1 in _corridas(forte.any(axis=1), 4):
        sub = forte[y0:y1 + 1]
        for c0, c1 in _corridas(sub.any(axis=0), 30):
            seg = sub[:, c0:c1 + 1]
            letras = _corridas(seg.any(axis=0), 1)
            if len(letras) < 3:   # ponto de enfeite, traço, ícone: não é texto
                continue
            ys = np.flatnonzero(seg.any(axis=1))
            alt = int(ys[-1] - ys[0] + 1)
            topos, bases = [], []
            for a, b in letras:
                yy = np.flatnonzero(seg[:, a:b + 1].any(axis=1))
                topos.append(int(yy[0]))
                bases.append(int(yy[-1]))
            base = float(np.median(bases))
            desce = (max(bases) - base) >= 0.12 * alt
            maiusc = sum(1 for t, b in zip(topos, bases) if (b - t + 1) >= 0.85 * alt) / len(letras) >= 0.8
            if maiusc:
                tam = alt / 0.73
            elif desce:
                tam = alt / 0.97
            else:
                tam = alt / 0.76
            linhas.append({"y": int(y0 + ys[0]), "x0": int(c0), "x1": int(c1), "alt": alt, "tam": round(tam)})

    # ocupação: texto, painéis/botões (corridas longas), cartões (cor próxima do fundo mas fixa e em área grande) e o cabeçalho
    ocup = cheio.copy()
    ocup[:CABECALHO] = True
    for l in linhas:
        ocup[max(0, l["y"] - 6):l["y"] + l["alt"] + 6, max(0, l["x0"] - 6):l["x1"] + 7] = True
    fundo = cor[5, 5]
    dif = np.abs(cor - fundo).sum(axis=2)
    cartao = (dif >= 12) & (dif < 70)
    gh, gw = h // CELULA, w // CELULA
    blocos = cartao[:gh * CELULA, :gw * CELULA].reshape(gh, CELULA, gw, CELULA).mean(axis=(1, 3)) > 0.6
    grade = ocup[:gh * CELULA, :gw * CELULA].reshape(gh, CELULA, gw, CELULA).any(axis=(1, 3)) | blocos
    return {"linhas": linhas, "vazio": _maior_vazio(grade) * CELULA * CELULA / float(w * h),
            "menor": min((l["tam"] for l in linhas), default=0), "maior": max((l["tam"] for l in linhas), default=0), "w": w, "h": h}


def _maior_vazio(grade):
    """Área (em células) do maior retângulo sem nenhuma célula ocupada (histograma por linha)."""
    gh, gw = grade.shape
    alturas = [0] * gw
    melhor = 0
    for i in range(gh):
        for j in range(gw):
            alturas[j] = 0 if grade[i, j] else alturas[j] + 1
        pilha = []
        for j in range(gw + 1):
            at = alturas[j] if j < gw else 0
            ini = j
            while pilha and pilha[-1][1] >= at:
                ini, a = pilha.pop()
                melhor = max(melhor, a * (j - ini))
            pilha.append((ini, at))
    return melhor


def problemas(caminho, minimo_principal=36, minimo_apoio=26, vazio_max=1 / 3):
    """Lista de problemas de leitura no celular de uma imagem (vazia = ok). Item 6 do padrão."""
    nome = Path(caminho).name
    r = analisar(caminho)
    out = []
    if not r["linhas"]:
        return [f"{nome}: nenhum texto legível encontrado"]
    if r["maior"] < minimo_principal:
        out.append(f"{nome}: o maior texto tem ~{r['maior']} px (mínimo {minimo_principal} px para o texto principal)")
    for l in r["linhas"]:
        if l["tam"] < minimo_apoio:
            out.append(f"{nome}: texto de ~{l['tam']} px na altura y={l['y']} (mínimo {minimo_apoio} px para apoio e rodapé)")
    if r["vazio"] > vazio_max:
        out.append(f"{nome}: área vazia de {r['vazio'] * 100:.0f}% da tela (máximo {vazio_max * 100:.0f}%)")
    return out
