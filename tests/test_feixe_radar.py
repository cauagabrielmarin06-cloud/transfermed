"""O feixe do radar é UMA cunha lisa com gradiente (14/11/2026).

Antes eram 16 fatias com opacidades diferentes: nas emendas apareciam riscos e o dono viu o radar como "travado/quebrado".
"""
import re
import unittest

import gerar_site


class FeixeLiso(unittest.TestCase):
    def test_uma_cunha_com_gradiente_e_a_borda(self):
        f = gerar_site.feixe_radar()
        self.assertEqual(len(re.findall(r'<path class="cunha"', f)), 1)
        self.assertEqual(len(re.findall(r"<path", f)), 2, "só a cunha e a borda: nada de fatias")
        self.assertIn('id="r3-grad"', f)
        self.assertNotIn("fill-opacity", f)

    def test_css_pinta_a_cunha_com_o_gradiente(self):
        css = (gerar_site.DOCS / "assets" / "estilo.css").read_text(encoding="utf-8")
        self.assertIn(".r3-feixe .cunha{fill:url(#r3-grad)}", css)
        self.assertNotIn(".r3-feixe path{fill:", css, "regra antiga pintaria a cunha de cor sólida por cima do gradiente")


if __name__ == "__main__":
    unittest.main()
