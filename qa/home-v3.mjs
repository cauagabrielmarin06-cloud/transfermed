// Capturas da home v3 (radar que responde) em 360, 390, 430 e 1280 px, no tema escuro e no claro, com o cartão (computador)
// e a gaveta (celular) abertos, e o GIF da abertura (quadros em screenshots/home-v3/gif/).
// uso: (site servido em http://127.0.0.1:8765, ou BASE=<site no ar>)  node home-v3.mjs [--gif]
import { chromium, devices } from 'playwright';
import { mkdirSync } from 'node:fs';

const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const OUT = 'screenshots/home-v3/';
mkdirSync(OUT + 'gif', { recursive: true });
const b = await chromium.launch();
const erros = [];
const ver = (p) => { p.on('pageerror', (e) => erros.push(e.message)); p.on('console', (m) => m.type() === 'error' && erros.push(m.text())); };
const semAbertura = (c) => c.addInitScript(() => { try { sessionStorage.setItem('tm_abertura', '1'); } catch (e) {} });

for (const tema of ['dark', 'light']) {
  for (const w of [360, 390, 430]) {
    const c = await b.newContext({ ...devices['iPhone 13'], viewport: { width: w, height: 844 }, colorScheme: tema });
    await semAbertura(c);
    const p = await c.newPage(); ver(p);
    await p.goto(BASE + '/', { waitUntil: 'networkidle' });
    await p.waitForTimeout(1200);
    await p.screenshot({ path: `${OUT}home-${w}-${tema}.png`, fullPage: true });
    if (w === 390) {
      await p.evaluate(() => { const y = document.querySelector('.r3').getBoundingClientRect().top + scrollY - 12; document.documentElement.style.scrollBehavior = 'auto'; scrollTo(0, y); });
      await p.evaluate(() => window.TM_radar.abrir('USF', 'SP'));
      await p.waitForTimeout(450);
      await p.screenshot({ path: `${OUT}gaveta-390-${tema}.png` });
      await p.keyboard.press('Escape');
      await p.locator('.pt.grupo').first().click();
      await p.waitForTimeout(450);
      await p.screenshot({ path: `${OUT}grupo-390-${tema}.png` });
    }
    await c.close();
  }
  const c = await b.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: tema });
  await semAbertura(c);
  const d = await c.newPage(); ver(d);
  await d.goto(BASE + '/', { waitUntil: 'networkidle' });
  await d.waitForTimeout(1200);
  await d.evaluate(() => window.TM_radar.abrir('USF', 'SP'));
  await d.waitForTimeout(450);
  await d.screenshot({ path: `${OUT}home-1280-${tema}.png`, fullPage: true });
  await c.close();
}

{ // navegador do Instagram: barras do app em cima e embaixo (altura útil menor)
  const c = await b.newContext({ ...devices['Pixel 7'], viewport: { width: 390, height: 664 }, colorScheme: 'dark',
    userAgent: devices['Pixel 7'].userAgent + ' Instagram 340.0.0.0.0 Android' });
  await semAbertura(c);
  const p = await c.newPage(); ver(p);
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  await p.waitForTimeout(800);
  await p.screenshot({ path: `${OUT}instagram-390.png` });
  await p.evaluate(() => window.TM_radar.abrir('USF', 'SP'));
  await p.waitForTimeout(450);
  await p.screenshot({ path: `${OUT}instagram-390-gaveta.png` });
  await c.close();
}

if (process.argv.includes('--gif')) {
  // abertura de verdade, quadro a quadro (o relógio do navegador anda 70 ms entre as capturas)
  const c = await b.newContext({ ...devices['iPhone 13'], colorScheme: 'dark' });
  const g = await c.newPage(); ver(g);
  await c.addInitScript(() => { window.TM_ABERTURA_MANUAL = true; });
  await g.clock.install();
  await g.goto(BASE + '/', { waitUntil: 'load' });
  await g.waitForTimeout(300);
  await g.evaluate(() => { window.TM_abertura(); window.__anims = document.getAnimations(); window.__anims.forEach((a) => { a._inicio = 0; a.pause(); a.currentTime = 0; }); });
  // as animações (Web Animations e CSS) seguem o relógio do documento: são pausadas e postas no mesmo instante
  for (let i = 0; i < 40; i++) {
    await g.evaluate((t) => {
      for (const a of new Set([...window.__anims, ...document.getAnimations()])) {
        a._inicio ??= t; a.pause(); a.currentTime = t - a._inicio;
      }
    }, i * 70);
    await g.screenshot({ path: `${OUT}gif/f${String(i).padStart(3, '0')}.png` });
    await g.clock.runFor(70);
  }
  await c.close();
}
await b.close();
console.log(erros.length ? 'ERROS: ' + [...new Set(erros)].join(' | ') : 'sem erros no console');
process.exit(erros.length ? 1 : 0);
