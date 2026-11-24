// Radar na VOLTA (24/11/2026): quem já escolheu a cidade e volta ao site (radar restaurado do localStorage) tem de ver
// o feixe girando. Antes, a restauração pulava a abertura e o feixe ficava parado em -90° ("radar quebrado").
// Os outros testes abrem o site sempre como visita nova e não pegavam isso.
// Uso: BASE=http://localhost:8000 node radar_volta.mjs
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://localhost:8000';
let falhas = 0;
const ok = (c, m) => { console.log((c ? 'ok   ' : 'FALHA ') + m); if (!c) falhas++; };
const b = await chromium.launch();
for (const [vp, nome] of [[{ width: 1440, height: 900 }, 'computador'], [{ width: 375, height: 812 }, 'celular']]) {
  for (const rm of ['no-preference', 'reduce']) {
    const c = await b.newContext({ viewport: vp, reducedMotion: rm });
    const p = await c.newPage();
    await p.goto(BASE + '/', { waitUntil: 'networkidle' });
    await p.fill('#rp-cidade', 'Andradina'); await p.waitForTimeout(400); await p.keyboard.press('Enter'); await p.waitForTimeout(1200);
    for (const como of ['recarregou', 'nova aba']) {
      const q = como === 'recarregou' ? p : await c.newPage();
      if (como === 'recarregou') await q.reload({ waitUntil: 'networkidle' }); else await q.goto(BASE + '/', { waitUntil: 'networkidle' });
      await q.waitForTimeout(2500);
      const r = await q.evaluate(() => {
        const f = document.querySelector('.r3-feixe'), cs = getComputedStyle(f);
        return { vis: cs.visibility, anim: f.getAnimations().some(a => a.playState === 'running'), restaurado: !!document.querySelector('#rp-cidade')?.value };
      });
      if (rm === 'reduce') ok(r.vis === 'hidden', `${nome}, movimento reduzido, ${como}: feixe escondido (nada parado na tela)`);
      else ok(r.anim && r.vis === 'visible', `${nome}, ${como} com o radar salvo: feixe girando`);
    }
    await c.close();
  }
}
await b.close();
console.log(falhas ? `\n${falhas} FALHA(S)` : '\ntudo certo');
process.exit(falhas ? 1 : 0);
