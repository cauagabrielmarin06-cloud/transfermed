import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const b = await chromium.launch();
for (const tema of ['light', 'dark']) {
  const ctx = await b.newContext({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true, colorScheme: tema });
  await ctx.addInitScript(() => { try { sessionStorage.setItem('tm_abertura', '1'); } catch (e) {} });
  const p = await ctx.newPage();
  await p.goto(BASE + '/?de=andradina-sp&p=7&km=400&origem=compartilhar', { waitUntil: 'networkidle' });
  await p.waitForSelector('#rp-cont:not([hidden])');
  await p.click('#rp-que');
  await p.$eval('#rp-avise', (e) => e.scrollIntoView({ block: 'start' }));
  await p.evaluate(() => window.scrollBy(0, -330));
  await p.waitForTimeout(300);
  await p.screenshot({ path: `screenshots/parte-e/envio-375-${tema}.png` });
  await ctx.close();
}
await b.close();
