// Teste R1: o aviso discreto do plano futuro só aparece no resultado do diagnóstico, o clique mede 'pro_interesse'
// e não coleta nada (nenhum campo, nenhum e-mail). Capturas em 390 e 1280.
// uso: (site em http://127.0.0.1:8765, ou BASE=<site no ar>)  node pro_espera.mjs
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const falhas = [];
const nav = await chromium.launch();
for (const w of [390, 1280]) {
  const ctx = await nav.newContext({ viewport: { width: w, height: 900 } });
  const pag = await ctx.newPage();
  const medidos = [];
  await pag.addInitScript(() => { window.TM_MEDIR_TESTE = true; });
  await pag.route('**/rest/v1/rpc/medir', async (rota) => { medidos.push(JSON.parse(rota.request().postData() || '{}').p_nome); await rota.fulfill({ status: 200, body: 'null', contentType: 'application/json' }); });
  await pag.goto(BASE + '/diagnostico/');
  if (await pag.locator('#pro-espera').isVisible()) falhas.push(`${w}px: aviso visível antes do resultado`);
  await pag.getByText('No Brasil', { exact: true }).click();
  for (let i = 0; i < 6 && await pag.locator('#resultado').isHidden(); i++) {
    if (await pag.locator('#semestre').isVisible()) await pag.selectOption('#semestre', '3');
    await pag.locator('#seguir').click();
    await pag.waitForTimeout(300);
  }
  if (!(await pag.locator('#pro-espera').isVisible())) { falhas.push(`${w}px: aviso não apareceu no resultado`); await ctx.close(); continue; }
  const campos = await pag.locator('#pro-espera input, #pro-espera textarea').count();
  if (campos) falhas.push(`${w}px: o aviso pede dados (${campos} campos)`);
  const texto = await pag.locator('#pro-espera').innerText();
  if (!/ainda não existe/.test(texto) || !/nada é cobrado/.test(texto)) falhas.push(`${w}px: o aviso não diz que o plano não existe e é grátis medir`);
  const caixa = await pag.locator('#pro-interesse').boundingBox();
  if (!caixa || caixa.height < 40) falhas.push(`${w}px: botão com área de toque pequena (${caixa && caixa.height}px)`);
  await pag.locator('#pro-espera').scrollIntoViewIfNeeded();
  await pag.screenshot({ path: `screenshots/pro-espera-${w}.png` });
  await pag.locator('#pro-interesse').click();
  await pag.waitForTimeout(300);
  if (!medidos.includes('pro_interesse')) falhas.push(`${w}px: clique não mediu pro_interesse (${medidos.join(',')})`);
  if (!/Anotado/.test(await pag.locator('#pro-espera').innerText())) falhas.push(`${w}px: sem confirmação depois do clique`);
  const rolagem = await pag.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  if (rolagem > 0) falhas.push(`${w}px: rolagem lateral`);
  await ctx.close();
}
await nav.close();
if (falhas.length) { console.error(falhas.join('\n')); process.exit(1); }
console.log('ok: aviso do plano futuro (R1) em 390 e 1280 px');
