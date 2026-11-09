// "Avise um colega": ligado por padrão desde 09/11/2026 (INDICACAO=0 desliga: TM_CONFIG.indicacao some e nada aparece); o link leva ?origem=indicacao,
// o clique mede 'indicar_colega' e nada identifica quem indicou. Capturas em 390 e 1280.
// uso: (site em http://127.0.0.1:8765, ou BASE=<site no ar>)  node indicacao.mjs
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const falhas = [];
const nav = await chromium.launch();
async function ate_resultado(pag) {
  await pag.goto(BASE + '/diagnostico/');
  await pag.getByText('No Brasil', { exact: true }).click();
  for (let i = 0; i < 6 && await pag.locator('#resultado').isHidden(); i++) {
    if (await pag.locator('#semestre').isVisible()) await pag.selectOption('#semestre', '3');
    await pag.locator('#seguir').click();
    await pag.waitForTimeout(300);
  }
}
for (const ligado of [false, true]) {
  for (const w of [390, 1280]) {
    const ctx = await nav.newContext({ viewport: { width: w, height: 900 } });
    const pag = await ctx.newPage();
    const medidos = [];
    await pag.addInitScript(() => { window.TM_MEDIR_TESTE = true; });
    await pag.route('**/rest/v1/rpc/medir', async (rota) => { medidos.push(JSON.parse(rota.request().postData() || '{}').p_nome); await rota.fulfill({ status: 200, body: 'null', contentType: 'application/json' }); });
    if (!ligado) await pag.route('**/dados.js*', async (rota) => { const r = await rota.fetch(); await rota.fulfill({ response: r, body: (await r.text()) + '\ndelete window.TM_CONFIG.indicacao;' }); });
    else if (!(await (await fetch(BASE + '/dados.js')).text()).includes('"indicacao": true')) { falhas.push('dados.js publicado sem a indicação ligada por padrão'); await ctx.close(); continue; }
    await ate_resultado(pag);
    const bloco = pag.locator('#indicar-colega');
    if (!ligado) { if (await bloco.count()) falhas.push(`${w}px: bloco apareceu com a indicação desligada`); await ctx.close(); continue; }
    if (!(await bloco.isVisible())) { falhas.push(`${w}px: bloco não apareceu ligado`); await ctx.close(); continue; }
    const href = await bloco.locator('a').first().getAttribute('href');
    if (!decodeURIComponent(href).includes('?origem=indicacao')) falhas.push(`${w}px: link sem origem=indicacao`);
    if (/@|\d{3}\.\d{3}/.test(decodeURIComponent(href))) falhas.push(`${w}px: link leva dado pessoal`);
    const caixa = await bloco.locator('a').first().boundingBox();
    if (!caixa || caixa.height < 40) falhas.push(`${w}px: área de toque pequena`);
    await bloco.scrollIntoViewIfNeeded();
    await pag.screenshot({ path: `screenshots/indicar-${w}.png` });
    await bloco.locator('[data-copiar-indicacao]').click();
    await pag.waitForTimeout(300);
    if (!medidos.includes('indicar_colega')) falhas.push(`${w}px: clique não mediu indicar_colega`);
    if ((await pag.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)) > 0) falhas.push(`${w}px: rolagem lateral`);
    await ctx.close();
  }
}
await nav.close();
if (falhas.length) { console.error(falhas.join('\n')); process.exit(1); }
console.log('ok: "Avise um colega" ligado por padrão, some só com INDICACAO=0');
