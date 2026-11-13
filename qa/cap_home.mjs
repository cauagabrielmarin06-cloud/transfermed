// Capturas da home (alerta + painel) em 375 e 1280 px. uso: node cap_home.mjs
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const b = await chromium.launch();
for (const w of [375, 1280]) {
  const ctx = await b.newContext({ viewport: { width: w, height: 900 }, isMobile: w < 600, hasTouch: w < 600 });
  await ctx.route('**/rest/v1/rpc/**', r => r.fulfill({ status: 200, contentType: 'application/json', body: '0' }));
  const p = await ctx.newPage(); const erros = [];
  p.on('pageerror', e => erros.push(String(e))); p.on('console', m => m.type() === 'error' && erros.push(m.text()));
  await p.goto(BASE + '/', { waitUntil: 'load' }); await p.waitForTimeout(800);
  const alvo = p.locator('.blocos-vivos'); await alvo.scrollIntoViewIfNeeded(); await p.waitForTimeout(300);
  await alvo.screenshot({ path: `screenshots/home-alerta-${w}.png` });
  console.log(w, 'erros:', erros.length ? erros : 'nenhum');
  await ctx.close();
}
await b.close();
