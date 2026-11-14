// Parte E (14/11): capturas do radar pessoal da home, antes e depois de escolher a cidade (Andradina/SP, 7º período, 400 km),
// em 375 e 1440 px, tema claro e escuro, com e sem "reduzir movimento". Saída: qa/screenshots/parte-e/
// uso: (site em http://127.0.0.1:8765, ou BASE=<site no ar>)  node cap_parte_e.mjs
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';

const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const SAIDA = new URL('./screenshots/parte-e/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
mkdirSync(SAIDA, { recursive: true });
const b = await chromium.launch();
for (const [larg, alt, rotulo] of [[375, 812, '375'], [1440, 900, '1440']]) {
  for (const tema of ['light', 'dark']) {
    for (const mov of ['no-preference', 'reduce']) {
      const ctx = await b.newContext({ viewport: { width: larg, height: alt }, colorScheme: tema, reducedMotion: mov, isMobile: larg < 500, hasTouch: larg < 500 });
      await ctx.addInitScript(() => { try { sessionStorage.setItem('tm_abertura', '1'); } catch (e) {} });
      const p = await ctx.newPage();
      await p.goto(BASE + '/', { waitUntil: 'networkidle' });
      const nome = `${rotulo}-${tema}-${mov === 'reduce' ? 'reduzido' : 'normal'}`;
      await p.screenshot({ path: `${SAIDA}${nome}-1-antes.png` });
      await p.click('#rp-cidade'); await p.type('#rp-cidade', 'Andradina', { delay: 10 });
      await p.waitForSelector('#rp-lista li'); await p.click('#rp-lista li:first-child');
      await p.waitForSelector('#rp-cont:not([hidden])');
      await p.click('label.rp-pilula:has(input[value="7"])');
      await p.waitForTimeout(1500);
      await p.screenshot({ path: `${SAIDA}${nome}-2-depois.png` });
      await p.screenshot({ path: `${SAIDA}${nome}-3-pagina.png`, fullPage: true });
      await ctx.close();
    }
  }
}
await b.close();
console.log('capturas em', SAIDA);
