"""Marca: só a logo v3 está no ar. Os ícones e a logo antigos foram para privado/arquivo/marca-antiga/ (12/11/2026);
nenhum arquivo publicado, o manifest nem o service worker pode voltar a citar imagem de marca fora de assets/marca/*-v3.*."""
import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))
DOCS = PASTA / "docs"

# Qualquer caminho de imagem cujo nome fala de marca (icone, icon, logo, favicon, apple-touch).
REF = re.compile(r"[\w./:@-]*(?:icone|icon|logo|favicon|apple-touch)[\w.-]*\.(?:png|ico|svg|jpe?g|webp)", re.I)
TEXTOS = {".html", ".js", ".css", ".json", ".webmanifest", ".xml", ".txt"}


def referencias_fora_da_v3(texto):
    """Devolve as citações de imagem de marca que não são assets/marca/*-v3.* (versão com -v3 antes da extensão)."""
    return sorted({m for m in REF.findall(texto) if not re.search(r"(?:^|/)marca/[\w-]*-v3\.\w+$", m)})


def arquivos_de_texto():
    for p in sorted(DOCS.rglob("*")):
        if p.is_file() and p.suffix.lower() in TEXTOS and "social" not in p.relative_to(DOCS).parts[:1]:
            yield p


class MarcaSoV3(unittest.TestCase):
    def test_o_verificador_pega_a_marca_antiga(self):
        """Prova que o teste pega o defeito: com a logo antiga ele reprova."""
        self.assertEqual(referencias_fora_da_v3('<link rel="icon" href="./assets/icone-192.png">'), ["./assets/icone-192.png"])
        self.assertEqual(referencias_fora_da_v3("'assets/logo.svg'"), ["assets/logo.svg"])
        self.assertEqual(referencias_fora_da_v3('"src": "assets/marca/logo-192.png"'), ["assets/marca/logo-192.png"])
        self.assertEqual(referencias_fora_da_v3('"src": "assets/marca/logo-192-v3.png"'), [])
        self.assertEqual(referencias_fora_da_v3("https://www.transfermed.com.br/assets/marca/logo-512-v3.png"), [])

    def test_nenhum_arquivo_publicado_cita_marca_fora_da_v3(self):
        achados = {}
        for p in arquivos_de_texto():
            fora = referencias_fora_da_v3(p.read_text(encoding="utf-8", errors="ignore"))
            if fora:
                achados[str(p.relative_to(DOCS))] = fora
        self.assertEqual(achados, {}, "arquivo publicado cita ícone ou logo fora de assets/marca/*-v3.*")

    def test_manifest_so_cita_icones_v3_em_assets_marca(self):
        m = json.loads((DOCS / "manifest.webmanifest").read_text(encoding="utf-8"))
        self.assertTrue(m["icons"])
        for icone in m["icons"]:
            self.assertRegex(icone["src"], r"^assets/marca/[\w-]+-v3\.png$")
            self.assertTrue((DOCS / icone["src"]).exists(), icone["src"])

    def test_nenhum_arquivo_de_marca_antigo_na_pasta_publicada(self):
        soltos = [str(p.relative_to(DOCS)) for p in DOCS.rglob("*")
                  if p.is_file() and re.search(r"icone|icon|logo|favicon|apple-touch", p.name, re.I)
                  and "marca" not in p.relative_to(DOCS).parts and p.relative_to(DOCS).parts[0] != "social"]
        # favicon.ico na raiz é cópia idêntica da v3 (navegadores pedem /favicon.ico sem consultar o HTML)
        v3 = hashlib.md5((DOCS / "assets" / "marca" / "favicon-v3.ico").read_bytes()).hexdigest()
        for s in list(soltos):
            if s == "favicon.ico" and hashlib.md5((DOCS / s).read_bytes()).hexdigest() == v3:
                soltos.remove(s)
        self.assertEqual(soltos, [])
        for p in DOCS.glob("assets/marca/*"):
            self.assertIn("-v3.", p.name, f"{p.name} não é da logo v3")


FUNDO = (0x0B, 0x1E, 0x2C)  # #0B1E2C


def problemas_maskable(imagem, lado):
    """Um ícone "maskable" precisa: ser lado x lado, sem transparência, ter o fundo sólido #0B1E2C até a borda e nada de logo fora da zona
    segura (círculo de raio 40% do lado, a partir do centro). Devolve a lista de problemas (vazia = serve)."""
    problemas = []
    if imagem.size != (lado, lado):
        problemas.append(f"tamanho {imagem.size}")
    if "A" in imagem.getbands() and imagem.getchannel("A").getextrema()[0] < 255:
        problemas.append("tem transparência")
    px = imagem.convert("RGB").load()
    cantos = [px[0, 0], px[lado - 1, 0], px[0, lado - 1], px[lado - 1, lado - 1]]
    if any(c != FUNDO for c in cantos):
        problemas.append(f"cantos fora do fundo sólido #0B1E2C: {cantos}")
    centro, raio = lado / 2, lado * 0.40 + 1.5
    def e_fundo(c):  # tolerância de 8 por canal: a reamostragem da borda do aro deixa o fundo 1 ou 2 níveis acima ou abaixo
        return all(abs(a - b) <= 8 for a, b in zip(c, FUNDO))
    fora = sum(1 for y in range(lado) for x in range(lado)
               if ((x + .5 - centro) ** 2 + (y + .5 - centro) ** 2) ** .5 > raio and not e_fundo(px[x, y]))
    if fora:
        problemas.append(f"{fora} pixel(s) de logo fora da zona segura (80% central)")
    if px[lado // 2, lado // 2] == FUNDO:
        problemas.append("sem logo no centro")
    return problemas


class IconesMaskable(unittest.TestCase):
    """Parte D (14/11/2026): os ícones "maskable" têm fundo sólido e a logo na zona segura; os "any" continuam com cantos transparentes."""

    def test_o_verificador_pega_o_icone_com_cantos_transparentes(self):
        """Prova que o teste pega o defeito: o ícone "any" (cantos transparentes, logo até a borda) não serve como maskable."""
        from PIL import Image
        antigo = Image.open(DOCS / "assets" / "marca" / "logo-512-v3.png")
        self.assertTrue(problemas_maskable(antigo, 512))

    def test_arquivos_maskable_sao_solidos_e_a_logo_cabe_na_zona_segura(self):
        from PIL import Image
        for lado in (512, 192):
            arq = DOCS / "assets" / "marca" / f"logo-maskable-{lado}-v3.png"
            self.assertTrue(arq.exists(), arq.name)
            self.assertEqual(problemas_maskable(Image.open(arq), lado), [], arq.name)

    def test_o_gerador_reproduz_os_arquivos_publicados(self):
        from PIL import Image
        sys.path.insert(0, str(PASTA / "qa"))
        import gerar_icones_maskable as g
        logo = Image.open(DOCS / "assets" / "marca" / "logo-512-v3.png").convert("RGBA")
        logo = logo.crop(logo.getchannel("A").getbbox())
        lado = max(logo.size)
        quadrada = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
        quadrada.paste(logo, ((lado - logo.width) // 2, (lado - logo.height) // 2))
        for tam in (512, 192):
            publicado = Image.open(DOCS / "assets" / "marca" / f"logo-maskable-{tam}-v3.png").convert("RGB")
            self.assertEqual(g.gerar(tam, quadrada).tobytes(), publicado.tobytes(), f"logo-maskable-{tam}-v3.png está diferente do gerador")

    def test_manifest_usa_os_maskable_so_como_maskable_e_os_any_so_como_any(self):
        m = json.loads((DOCS / "manifest.webmanifest").read_text(encoding="utf-8"))
        for i in m["icons"]:
            self.assertIn(i["purpose"], ("any", "maskable"), "cada ícone serve a um uso só (sem 'any maskable')")
        mask = sorted(i["src"] for i in m["icons"] if i["purpose"] == "maskable")
        self.assertEqual(mask, ["assets/marca/logo-maskable-192-v3.png", "assets/marca/logo-maskable-512-v3.png"])
        comum = sorted(i["src"] for i in m["icons"] if i["purpose"] == "any")
        self.assertEqual(comum, ["assets/marca/logo-192-v3.png", "assets/marca/logo-512-v3.png"])
        for i in m["icons"]:
            self.assertTrue((DOCS / i["src"]).exists(), i["src"])


if __name__ == "__main__":
    unittest.main()
