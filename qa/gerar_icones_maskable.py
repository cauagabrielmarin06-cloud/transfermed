"""Gera os ícones "maskable" do app (docs/assets/marca/logo-maskable-512-v3.png e -192-v3.png).

Por que: o Android recorta o ícone do app numa máscara (círculo, quadrado arredondado, gota...). Um ícone "maskable" precisa ter o fundo
até a borda (sem cantos transparentes) e tudo que importa dentro da zona segura: o círculo central de 80% do lado. Aqui o fundo é o azul
da logo (#0B1E2C) e a logo v3 inteira, com o seu aro, cabe dentro dos 80% centrais; qualquer máscara do Android só corta fundo liso.
Os ícones "any" (logo-192-v3.png e logo-512-v3.png, com cantos transparentes) continuam como estão.

uso:  python qa/gerar_icones_maskable.py        (usa só a logo-512-v3.png, que já está no repositório)"""
from pathlib import Path

from PIL import Image

MARCA = Path(__file__).resolve().parent.parent / "docs" / "assets" / "marca"
FUNDO = (0x0B, 0x1E, 0x2C)  # #0B1E2C: o azul do disco da logo v3
ZONA_SEGURA = 0.80          # a logo ocupa 80% do lado (o aro da logo é o limite)


def gerar(lado, logo):
    """Fundo sólido de lado x lado com a logo centralizada em 80% do lado, sem transparência."""
    quadro = Image.new("RGB", (lado, lado), FUNDO)
    miolo = round(lado * ZONA_SEGURA)
    pequena = logo.resize((miolo, miolo), Image.LANCZOS)
    pos = ((lado - miolo) // 2, (lado - miolo) // 2)
    quadro.paste(pequena, pos, pequena)
    return quadro


def main():
    logo = Image.open(MARCA / "logo-512-v3.png").convert("RGBA")
    # o disco da logo ocupa a imagem quase toda (4 a 508 de 512): recorta a margem transparente para que o "80%" seja do disco
    logo = logo.crop(logo.getchannel("A").getbbox())
    lado = max(logo.size)
    quadrada = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    quadrada.paste(logo, ((lado - logo.width) // 2, (lado - logo.height) // 2))
    for tam in (512, 192):
        destino = MARCA / f"logo-maskable-{tam}-v3.png"
        gerar(tam, quadrada).save(destino, optimize=True)
        print("gerado", destino.relative_to(MARCA.parent.parent.parent))


if __name__ == "__main__":
    main()
