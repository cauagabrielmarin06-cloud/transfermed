// Logo nova no cabeçalho em 360, 768 e 1280 px: aparece, tem alt, altura de 32 a 40 px, sem rolagem horizontal, favicon carrega.
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://localhost:8765';
const b = await chromium.launch(); let falhas = 0;
for (const w of [360, 768, 1280]) {
  const ctx = await b.newContext({ viewport: { width: w, height: 800 } }); const p = await ctx.newPage();
  const erros = []; p.on('console', m => m.type() === 'error' && erros.push(m.text()));
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  const r = await p.evaluate(async () => {
    const i = document.querySelector('.topo .marca img'); const box = i.getBoundingClientRect();
    const ic = [...document.querySelectorAll('link[rel~=icon],link[rel=apple-touch-icon]')].map(l => l.href);
    const ok = await Promise.all(ic.map(u => fetch(u).then(x => x.ok)));
    return { alt: i.alt, w: box.width, h: box.height, carregou: i.naturalWidth > 0, scroll: document.documentElement.scrollWidth > innerWidth, icones: ic.length, iconesOk: ok.every(Boolean) };
  });
  const bom = r.alt === 'Transfermed' && r.h >= 32 && r.h <= 40 && r.carregou && !r.scroll && r.iconesOk && r.icones === 3 && !erros.length;
  console.log(w, JSON.stringify(r), erros.length ? erros : '', bom ? 'OK' : 'FALHOU'); if (!bom) falhas++;
  await p.screenshot({ path: `screenshots/logo-${w}.png`, clip: { x: 0, y: 0, width: w, height: 90 } });
}
await b.close(); process.exit(falhas ? 1 : 0);
