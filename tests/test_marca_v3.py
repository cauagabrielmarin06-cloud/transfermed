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

    def test_icones_maskable_tem_fundo_solido_e_a_logo_nos_80_centrais(self):
        """E1.9: o ícone maskable não tem canto transparente nem borda de outra cor; a logo cabe na zona segura (80% centrais)."""
        from PIL import Image
        m = json.loads((DOCS / "manifest.webmanifest").read_text(encoding="utf-8"))
        mask = [i for i in m["icons"] if i["purpose"] == "maskable"]
        any_ = [i for i in m["icons"] if i["purpose"] == "any"]
        self.assertEqual(sorted(i["sizes"] for i in mask), ["192x192", "512x512"])
        self.assertFalse({i["src"] for i in mask} & {i["src"] for i in any_}, '"maskable" só nos arquivos próprios, os "any" ficam como estão')
        for i in mask:
            lado = int(i["sizes"].split("x")[0])
            im = Image.open(DOCS / i["src"]).convert("RGBA")
            self.assertEqual(im.size, (lado, lado))
            self.assertEqual(i["type"], "image/png")
            alfas = im.getchannel("A").getextrema()
            self.assertEqual(alfas, (255, 255), "sem pixel transparente")
            for xy in ((0, 0), (lado - 1, 0), (0, lado - 1), (lado - 1, lado - 1), (lado // 2, 0), (0, lado // 2), (lado - 1, lado // 2), (lado // 2, lado - 1)):
                self.assertEqual(im.getpixel(xy)[:3], (0x0B, 0x1E, 0x2C), f"{i['src']} {xy}: fundo sólido #0B1E2C")
            margem = round(lado * 0.10) - 1  # 10% de cada lado: a logo fica nos 80% centrais (1 px de tolerância)
            fundo = (0x0B, 0x1E, 0x2C)
            fora = [(x, y) for x in range(lado) for y in range(lado) if (x < margem or x >= lado - margem or y < margem or y >= lado - margem)
                    and max(abs(a - b) for a, b in zip(im.getpixel((x, y))[:3], fundo)) > 8]
            self.assertEqual(fora, [], f"{i['src']}: conteúdo fora da zona segura de 80%")
            dentro = sum(1 for x in range(lado // 4, 3 * lado // 4) for y in range(lado // 4, 3 * lado // 4) if im.getpixel((x, y))[:3] != fundo)
            self.assertGreater(dentro, lado, "a logo está no centro")

    def test_o_verificador_dos_icones_pega_o_icone_antigo(self):
        """O ícone 'any' (cantos transparentes) reprova a regra do maskable: prova que o teste pega o defeito."""
        from PIL import Image
        antigo = Image.open(DOCS / "assets" / "marca" / "logo-512-v3.png").convert("RGBA")
        self.assertNotEqual(antigo.getchannel("A").getextrema(), (255, 255))

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


if __name__ == "__main__":
    unittest.main()
