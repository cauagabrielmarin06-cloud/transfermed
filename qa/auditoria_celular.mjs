// Auditoria do celular: páginas principais em 360, 390 e 430 px e no navegador do Instagram (390x664).
// Falha com rolagem lateral, erro de console ou alvo de toque menor que 44 px de altura
// (fora links dentro de texto corrido, que a WCAG 2.5.8 dispensa).
// uso: BASE=<site> node qa/auditoria_celular.mjs   (padrão: servidor local 127.0.0.1:8765)
import { chromium, devices } from 'playwright';
const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const MIN = 44;
const IG = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 340.0.0.22.109';
const aparelhos = {
  '360': { viewport: { width: 360, height: 780 } },
  '390': { viewport: { width: 390, height: 844 } },
  '430': { viewport: { width: 430, height: 932 } },
  instagram: { viewport: { width: 390, height: 664 }, userAgent: IG },
};
const paginas = ['/', '/editais/', '/exterior/', '/estado/ba/', '/faculdade/ufba-salvador/', '/edital/unex-jequie-externa-2027-1-cebb92/',
  '/sobre/', '/contato/', '/minha-lista/', '/diagnostico/', '/privacidade/'];
const b = await chromium.launch();
let falhas = 0;
for (const [nome, cfg] of Object.entries(aparelhos)) {
  const ctx = await b.newContext({ ...devices['iPhone 13'], ...cfg });
  await ctx.route('**/rest/v1/rpc/**', r => r.fulfill({ status: 200, contentType: 'application/json', body: '0' }));
  for (const caminho of paginas) {
    const p = await ctx.newPage(); const erros = [];
    p.on('pageerror', e => erros.push(String(e)));
    p.on('console', m => { if (m.type() === 'error' && !/WebGL|tile\.openstreetmap/i.test(m.text())) erros.push(m.text()); });
    await p.goto(BASE + caminho, { waitUntil: 'load' }); await p.waitForTimeout(400);
    const r = await p.evaluate((MIN) => {
      const lateral = document.documentElement.scrollWidth > innerWidth + 1;
      const pequenos = [...document.querySelectorAll('a,button,input:not([type=hidden]),select,summary,label:has(input)')].filter(el => {
        const s = getComputedStyle(el); if (s.visibility === 'hidden' || el.closest('[hidden],dialog:not([open])')) return false;
        const q = el.getBoundingClientRect(); if (!q.width || !q.height) return false;
        if (el.tagName === 'A' && s.display === 'inline' && el.closest('p,li,dd,td,small,figcaption,.nota')) return false;
        if (el.matches('input[type=checkbox],input[type=radio]') && el.closest('label')) return false; // o alvo é o rótulo
        if (el.closest('svg,.leaflet-container')) return false; // pontos do mapa: o mapa tem a lista logo abaixo
        return q.height < MIN;
      }).map(el => { const q = el.getBoundingClientRect(); return `${el.tagName.toLowerCase()}${el.className ? '.' + String(el.className).split(' ')[0] : ''} ${Math.round(q.width)}x${Math.round(q.height)} "${(el.textContent || el.getAttribute('aria-label') || el.name || '').trim().replace(/\s+/g, ' ').slice(0, 30)}"`; });
      return { lateral, pequenos: [...new Set(pequenos)] };
    }, MIN);
    const prob = [];
    if (r.lateral) prob.push('rolagem lateral');
    if (erros.length) prob.push('console: ' + erros.slice(0, 2).join(' | '));
    if (r.pequenos.length) prob.push(`${r.pequenos.length} alvos < ${MIN} px: ` + r.pequenos.slice(0, 8).join('; '));
    if (prob.length) { falhas++; console.log(`FALHA ${nome} ${caminho}\n   ` + prob.join('\n   ')); }
    await p.close();
  }
  await ctx.close();
}
await b.close();
console.log(falhas ? `${falhas} página(s) com problema` : 'auditoria do celular: tudo certo');
process.exit(falhas ? 1 : 0);
