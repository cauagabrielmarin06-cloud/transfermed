// Radar no computador (19/11/2026), revisão do dono:
// 1) o cartão do mapa (fixo na rolagem) cabe inteiro na janela em telas de 1100x700 a 1920x1080 (antes, em 1280x800, o rodapé do mapa ficava fora);
// 2) no radar pessoal, o mapa conta o mesmo que o número grande: soma dos grupos + pontos sozinhos que aceitam o período = N
//    (antes, um grupo "2" misturava 1 edital do período com 1 "a confirmar");
// 3) no radar pessoal, estado com 0 no raio some dos chips.
// Uso: BASE=http://localhost:8000 node radar_computador.mjs
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://localhost:8000';
let falhas = 0;
const ok = (c, m) => { console.log((c ? 'ok   ' : 'FALHA ') + m); if (!c) falhas++; };
const b = await chromium.launch();
for (const [w, h] of [[1100, 700], [1280, 720], [1280, 800], [1440, 900], [1920, 1080]]) {
  const p = await b.newPage({ viewport: { width: w, height: h } });
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  await p.fill('#rp-cidade', 'Andradina'); await p.waitForTimeout(400); await p.keyboard.press('Enter'); await p.waitForTimeout(1000);
  await p.check('input[name=rp-periodo][value="5"]', { force: true }); await p.waitForTimeout(800);
  await p.evaluate(() => window.scrollBy(0, 500));
  await p.waitForFunction(() => new Promise(r => { const a = scrollY; setTimeout(() => r(scrollY === a), 200); }), null, { timeout: 5000 });
  await p.waitForTimeout(700);
  const r = await p.evaluate(() => {
    const c = document.querySelector('.r3').getBoundingClientRect();
    const n = Number((document.querySelector('.r3-svg').closest('figure').textContent.match(/(\d+) editais? abert/) || [])[1]);
    let soma = 0;
    document.querySelectorAll('.r3-svg a.pt').forEach(a => {
      if (a.classList.contains('grupo')) { if (!a.classList.contains('conferir')) soma += Number(a.textContent); }
      else if (!a.classList.contains('conferir') && !a.classList.contains('sem')) soma += 1;
    });
    const zeros = [...document.querySelectorAll('[data-uf]')].filter(b => !b.hidden && /·\s*0\b/.test(b.textContent)).length;
    return { cabe: c.top >= 0 && c.bottom <= innerHeight + 1, fundo: Math.round(c.bottom), n, soma, zeros, sw: document.documentElement.scrollWidth, iw: innerWidth };
  });
  ok(r.cabe, `${w}x${h}: cartão do mapa inteiro na janela (fundo ${r.fundo} ≤ ${h})`);
  ok(r.soma === r.n, `${w}x${h}: o mapa conta ${r.soma}, o número diz ${r.n}`);
  ok(r.zeros === 0, `${w}x${h}: nenhum estado com 0 nos chips do radar pessoal (${r.zeros})`);
  ok(r.sw === r.iw, `${w}x${h}: sem rolagem lateral`);
  await p.close();
}
await b.close();
console.log(falhas ? `\n${falhas} FALHA(S)` : '\ntudo certo');
process.exit(falhas ? 1 : 0);
