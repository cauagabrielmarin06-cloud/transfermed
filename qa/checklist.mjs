// Checklist de documentos na ficha do edital: aparece com página e data, sem rolagem horizontal, sem erro de console e sem violação do axe.
import { chromium } from 'playwright';
import { AxeBuilder } from '@axe-core/playwright';
const BASE = process.env.BASE || 'http://localhost:8765';
const PAGINAS = ['edital/fpp-curitiba-externa-2027-1-528d5e/', 'edital/unoeste-jau-externa-2027-1-0bfe52/', 'edital/uniube-externa-2027-1-2a698c/'];
const b = await chromium.launch(); let falhas = 0;
for (const [i, pag] of PAGINAS.entries()) for (const w of [390, 1280]) {
  const ctx = await b.newContext({ viewport: { width: w, height: 900 } }); const p = await ctx.newPage(); const erros = [];
  p.on('console', m => m.type() === 'error' && erros.push(m.text()));
  await p.goto(`${BASE}/${pag}`, { waitUntil: 'networkidle' });
  const r = await p.evaluate(() => ({ check: !!document.querySelector('.checklist-edital'), paginas: document.querySelectorAll('.checklist-edital .pag').length,
    data: /Conferido nos PDFs do edital em \d\d\/\d\d\/\d{4}/.test(document.body.innerText), scroll: document.documentElement.scrollWidth > innerWidth,
    avisoPdf: /fora do ar no site da faculdade desde \d\d\/\d\d\/\d{4}/.test(document.body.innerText) }));
  const axe = (await new AxeBuilder({ page: p }).analyze()).violations.map(v => v.id);
  const esperado = i < 2 ? (r.check && r.paginas > 3 && r.data) : (!r.check && r.avisoPdf);
  const ok = esperado && !r.scroll && !erros.length && !axe.length;
  console.log(pag.split('/')[1].slice(0, 22), w, JSON.stringify(r), axe.length ? axe : '', erros.length ? erros : '', ok ? 'OK' : 'FALHOU'); if (!ok) falhas++;
  if (i === 0 && w === 390) await p.screenshot({ path: 'screenshots/checklist-390.png', fullPage: false, clip: { x: 0, y: 0, width: 390, height: 900 } });
  await ctx.close();
}
await b.close(); process.exit(falhas ? 1 : 0);
