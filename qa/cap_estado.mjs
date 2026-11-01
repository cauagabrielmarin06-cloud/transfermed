import { chromium } from 'playwright';
import { AxeBuilder } from '@axe-core/playwright';
const b = await chromium.launch();
for (const [w, h] of [[375, 800], [1280, 900]]) {
  const c = await b.newContext({ viewport: { width: w, height: h } });
  await c.addInitScript(() => { try { sessionStorage.setItem('tm_abertura', '1'); } catch (e) {} });
  const p = await c.newPage(); const erros = [];
  p.on('console', (m) => m.type() === 'error' && erros.push(m.text())); p.on('pageerror', (e) => erros.push(e.message));
  for (const [n, u] of [['estado-pr', '/estado/pr/'], ['edital-fpp', '/edital/' + (process.env.SLUG || '') + '/'], ['inicio', '/']]) {
    await p.goto('http://127.0.0.1:8765' + u, { waitUntil: 'networkidle' });
    const rolagem = await p.evaluate(() => document.documentElement.scrollWidth > innerWidth);
    const ax = (await new AxeBuilder({ page: p }).analyze()).violations.map((v) => v.id);
    console.log(w, n, 'rolagem lateral:', rolagem, 'axe:', ax.join(',') || 'ok', 'console:', erros.length);
    await p.screenshot({ path: `screenshots/${n}-${w === 375 ? 375 : 1280}.png`, fullPage: n !== 'inicio' });
  }
}
await b.close();
