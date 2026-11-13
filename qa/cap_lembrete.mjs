// Capturas do bloco "Não perca o prazo" em 375 e 1280 px. uso: PAGINAS=edital/x,edital/y node cap_lembrete.mjs
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const caminhos = (process.env.PAGINAS || 'edital/fpp-curitiba-externa-2027-1-528d5e').split(',').map(c => '/' + c.split('/').filter(Boolean).join('/') + '/');
mkdirSync('screenshots', { recursive: true });
const b = await chromium.launch();
for (const w of [375, 1280]) {
  const ctx = await b.newContext({ viewport: { width: w, height: 900 }, isMobile: w < 600, hasTouch: w < 600, deviceScaleFactor: 1 });
  await ctx.route('**/rest/v1/rpc/**', r => r.fulfill({ status: 200, contentType: 'application/json', body: '0' }));
  for (const c of caminhos) {
    const p = await ctx.newPage(); const erros = [];
    p.on('pageerror', e => erros.push(String(e))); p.on('console', m => m.type() === 'error' && erros.push(m.text()));
    await p.goto(BASE + c, { waitUntil: 'load' }); await p.waitForTimeout(500);
    const el = p.locator('#lembrete'); await el.scrollIntoViewIfNeeded();
    const nome = c.replace(/\W+/g, '-').replace(/^-|-$/g, '').slice(0, 40);
    await el.screenshot({ path: `screenshots/lembrete-${nome}-${w}.png` });
    console.log(w, c, 'erros:', erros.length ? erros : 'nenhum');
    await p.close();
  }
  await ctx.close();
}
await b.close();
