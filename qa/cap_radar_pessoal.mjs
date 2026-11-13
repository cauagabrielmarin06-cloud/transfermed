// Capturas do radar pessoal (375 e 1280 px) em cada estado, para revisar à mão: node cap_radar_pessoal.mjs
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const b = await chromium.launch();
for (const [nome, op] of [['375', { viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true }], ['1280', { viewport: { width: 1280, height: 900 } }]]) {
  const ctx = await b.newContext(op);
  await ctx.addInitScript(() => { try { sessionStorage.setItem('tm_abertura', '1'); } catch (e) {} });
  const p = await ctx.newPage();
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  const foto = (n) => p.screenshot({ path: `screenshots/pessoal-${n}-${nome}.png` });
  await foto('1-inicio');
  await p.click('#rp-cidade'); await p.type('#rp-cidade', 'Ribeirão Pr', { delay: 20 }); await p.waitForSelector('#rp-lista li');
  await foto('2-sugestoes');
  await p.click('#rp-lista li:first-child'); await p.waitForTimeout(1300);
  await foto('3-cidade');
  await p.click('.rp-pilula input[value="4"]'); await p.waitForTimeout(700);
  await p.evaluate(() => document.querySelector('.rp-num').scrollIntoView({ block: 'start' }));
  await foto('4-periodo');
  await p.evaluate(() => document.querySelector('.rp-top').scrollIntoView({ block: 'start' }));
  await foto('5-resultado');
  await p.evaluate(() => { const l = window.TM_radar; const a = document.querySelector('.r3-pontos .pt')._g.itens[0]; l.abrir(a.sigla, a.uf); });
  await p.waitForTimeout(400);
  await foto('6-ponto');
  await ctx.close();
}
await b.close();
