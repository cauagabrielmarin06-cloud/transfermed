// Captura do resultado do radar pessoal (chips "por que entrou", campi agrupados, mandar/baixar) em 375 px, claro e escuro.
// uso: BASE=http://127.0.0.1:8766 node cap_resultado_e3.mjs   → qa/screenshots/parte-e/
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
const BASE = process.env.BASE || 'http://127.0.0.1:8765';
mkdirSync('screenshots/parte-e', { recursive: true });
const b = await chromium.launch();
for (const tema of ['light', 'dark']) {
  const ctx = await b.newContext({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true, colorScheme: tema });
  await ctx.addInitScript(() => { try { sessionStorage.setItem('tm_abertura', '1'); } catch (e) {} });
  const p = await ctx.newPage();
  await p.goto(BASE + '/?de=sao-paulo-sp&p=4&km=1600&origem=compartilhar', { waitUntil: 'networkidle' });
  await p.waitForSelector('#rp-cont:not([hidden])');
  await p.waitForTimeout(900);
  if (await p.$('#rp-top .rp-grupo > button')) await p.click('#rp-top .rp-grupo > button');
  await p.$eval('#rp-top', (e) => e.scrollIntoView({ block: 'start' }));
  await p.evaluate(() => window.scrollBy(0, -70));
  await p.waitForTimeout(300);
  await p.screenshot({ path: `screenshots/parte-e/resultado-375-${tema}.png` });
  await p.$eval('.rp-envio', (e) => e.scrollIntoView({ block: 'center' }));
  await p.click('#rp-que');
  await p.waitForTimeout(300);
  await p.screenshot({ path: `screenshots/parte-e/mandar-375-${tema}.png` });
  await ctx.close();
}
await b.close();
