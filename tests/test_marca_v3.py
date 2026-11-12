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


if __name__ == "__main__":
    unittest.main()
