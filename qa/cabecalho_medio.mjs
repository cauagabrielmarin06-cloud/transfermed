// Cabeçalho em tela média e grande (769–1280 px): sempre uma linha só (altura < 75 px), sem rolagem lateral.
// uso: (site em http://127.0.0.1:8765, ou BASE=<site no ar>)  node cabecalho_medio.mjs
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const PAGINAS = ['/', '/diagnostico/', '/exterior/', '/minha-lista/', '/sobre/', '/estado/sp/', '/editais/'];
const falhas = [];
const b = await chromium.launch();
const p = await b.newPage();
for (const w of [769, 800, 820, 821, 900, 980, 981, 1024, 1120, 1121, 1280]) {
  await p.setViewportSize({ width: w, height: 800 });
  for (const url of PAGINAS) {
    await p.goto(BASE + url, { waitUntil: 'load' });
    const r = await p.evaluate(() => ({ h: Math.round(document.querySelector('header.topo').getBoundingClientRect().height),
      rolagem: document.documentElement.scrollWidth - document.documentElement.clientWidth }));
    if (r.h >= 75) falhas.push(`${w}px ${url}: cabeçalho com ${r.h}px (quebrou em 2 linhas)`);
    if (r.rolagem > 0) falhas.push(`${w}px ${url}: rolagem lateral de ${r.rolagem}px`);
  }
}
await b.close();
if (falhas.length) { console.error(falhas.join('\n')); process.exit(1); }
console.log('ok: cabeçalho em uma linha de 769 a 1280 px');
