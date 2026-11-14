// Radar pessoal: o círculo do raio fica INTEIRO na vista do mapa e o feixe não passa do círculo (14/11/2026).
// Antes: a vista era recortada em 0..400 e cortava o círculo (ex.: Andradina, 1.550 km), e o piso .12 da escala fazia
// o feixe sair do círculo abaixo de ~200 km. Uso: BASE=http://localhost:8000 node radar_circulo.mjs
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://localhost:8000';
const casos = [['Andradina', [100, 150, 400, 1000, 1550]], ['Porto Alegre', [1550]], ['Manaus', [1550]]];
let falhas = 0;
const ok = (c, m) => { console.log((c ? 'ok   ' : 'FALHA ') + m); if (!c) falhas++; };
const b = await chromium.launch();
for (const [vp, nome] of [[{ width: 1440, height: 900 }, 'computador'], [{ width: 375, height: 812 }, 'celular']]) {
  const p = await b.newPage({ viewport: vp });
  for (const [cidade, kms] of casos) {
    await p.goto(BASE + '/', { waitUntil: 'networkidle' });
    await p.fill('#rp-cidade', cidade); await p.waitForTimeout(400); await p.keyboard.press('Enter'); await p.waitForTimeout(900);
    for (const km of kms) {
      await p.evaluate(km => { const s = document.querySelector('input[type=range]'); s.value = km; s.dispatchEvent(new Event('input', { bubbles: true })); s.dispatchEvent(new Event('change', { bubbles: true })); }, km);
      await p.waitForTimeout(1100);  // a câmera desliza até a vista nova
      const r = await p.evaluate(() => {
        const svg = document.querySelector('.r3-svg'), raio = document.querySelector('.r3-pessoa .raio');
        if (!raio) return null;
        const v = svg.getAttribute('viewBox').split(/\s+/).map(Number), bb = raio.getBBox();
        const dentro = bb.x >= v[0] - .5 && bb.y >= v[1] - .5 && bb.x + bb.width <= v[0] + v[2] + .5 && bb.y + bb.height <= v[1] + v[3] + .5;
        const m = document.querySelector('.r3-aneis').getAttribute('transform').match(/scale\(([\d.]+)\)/);
        const feixe = 150 * (m ? Number(m[1]) : 1), circ = bb.height / 2;  // raio do feixe x meia altura do círculo (norte-sul)
        return { dentro, feixe, circ };
      });
      if (!r) { ok(false, `${nome} ${cidade} ${km} km: sem círculo`); continue; }
      ok(r.dentro, `${nome} ${cidade} ${km} km: círculo inteiro na vista`);
      ok(r.feixe <= r.circ * 1.08, `${nome} ${cidade} ${km} km: feixe (${r.feixe.toFixed(1)}) não passa do círculo (${r.circ.toFixed(1)})`);
    }
  }
  await p.close();
}
await b.close();
console.log(falhas ? `\n${falhas} FALHA(S)` : '\ntudo certo');
process.exit(falhas ? 1 : 0);
