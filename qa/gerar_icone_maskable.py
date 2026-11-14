"""Gera os ícones "maskable" do app (Parte E1.9, 14/11/2026): fundo sólido #0B1E2C ocupando o quadrado inteiro e a logo v3 nos 80% centrais
(a zona segura de ícone maskable é um círculo de 80% do lado). Os ícones logo-192-v3.png e logo-512-v3.png (cantos transparentes) ficam só como "any".
uso (na raiz do projeto):  python qa/gerar_icone_maskable.py"""
from pathlib import Path

from PIL import Image, ImageDraw

MARCA = Path(__file__).resolve().parent.parent / "docs" / "assets" / "marca"
FUNDO = (0x0B, 0x1E, 0x2C, 255)
ZONA = 0.80


DISCO = (24, 24, 488, 488)  # o disco escuro da logo de 512 px (fora dele a imagem tem fundo branco opaco); a cor do disco é a do fundo


def maskable(origem: Path, lado: int) -> Image.Image:
    logo = Image.open(origem).convert("RGBA").crop(DISCO)
    mascara = Image.new("L", (logo.width * 4, logo.height * 4), 0)  # círculo suavizado (4x e volta): sem borda serrilhada
    ImageDraw.Draw(mascara).ellipse((0, 0, mascara.width - 1, mascara.height - 1), fill=255)
    logo.putalpha(mascara.resize(logo.size, Image.LANCZOS))
    tela = Image.new("RGBA", (lado, lado), FUNDO)
    miolo = round(lado * ZONA)
    logo = logo.resize((miolo, miolo), Image.LANCZOS)
    tela.alpha_composite(logo, ((lado - miolo) // 2, (lado - miolo) // 2))
    return tela


if __name__ == "__main__":
    base = MARCA / "logo-512-v3.png"
    for lado in (512, 192):
        destino = MARCA / f"logo-maskable-{lado}-v3.png"
        maskable(base, lado).convert("RGB").save(destino, optimize=True)
        print(destino.name, lado)
