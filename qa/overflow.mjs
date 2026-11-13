// Rolagem lateral no celular: scrollWidth tem de ser igual a clientWidth em 375 e 390 px.
// uso: BASE=https://www.transfermed.com.br node overflow.mjs   (padrão: http://127.0.0.1:8765, site local)
// Sai com código 1 se alguma página estoura e mostra os elementos que passam da borda.
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const PAGINAS = (process.env.PAGINAS || ['/', '/edital/unex-jequie-externa-2027-1-cebb92/', '/edital/afya-itaperuna-externa-2027-1-73eb7c/',
  '/faculdade/afya-itaperuna/', '/faculdade/uniube/', '/faculdade/univassouras-vassouras/',
  '/edital/uniube-externa-2027-1-2a698c/', '/edital/ucb-realengo-externa-2027-1-cbedcc/', '/alerta/confirmar/', '/diagnostico/', '/exterior/', '/minha-lista/', '/editais/'].join(',')).split(',');
const LARGURAS = [375, 390];
const b = await chromium.launch();
let falhas = 0;
for (const w of LARGURAS) {
  const ctx = await b.newContext({ viewport: { width: w, height: 800 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true });
  await ctx.route('**/rest/v1/rpc/**', r => r.fulfill({ status: 200, contentType: 'application/json', body: '0' }));
  for (const caminho of PAGINAS) {
    const p = await ctx.newPage();
    const resp = await p.goto(BASE + caminho, { waitUntil: 'load' });
    await p.waitForTimeout(400);
    const r = await p.evaluate(() => {
      const de = document.documentElement; const largura = de.clientWidth;
      const fora = [...document.querySelectorAll('body *')].filter(el => {
        const c = el.getBoundingClientRect(); if (!c.width) return false;
        // ignora o que mora dentro de um contêiner que rola por conta própria
        for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) { const o = getComputedStyle(a).overflowX; if (o === 'auto' || o === 'scroll' || o === 'hidden') return false; }
        return c.right > largura + 0.5 || c.left < -0.5;
      }).slice(0, 5).map(el => el.tagName + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).join('.') : '') + ' ' + Math.round(el.getBoundingClientRect().right));
      return { sw: de.scrollWidth, cw: largura, fora };
    });
    const ok = resp && resp.ok() && r.sw === r.cw;
    if (!ok) falhas++;
    console.log(`${ok ? 'ok   ' : 'FALHA'} ${w}px ${caminho} scrollWidth=${r.sw} clientWidth=${r.cw}${r.fora.length ? ' fora: ' + r.fora.join(' | ') : ''}${resp && resp.ok() ? '' : ' HTTP ' + (resp && resp.status())}`);
    await p.close();
  }
  await ctx.close();
}
await b.close();
console.log(falhas ? `${falhas} página(s) com rolagem lateral` : 'nenhuma rolagem lateral');
process.exit(falhas ? 1 : 0);
