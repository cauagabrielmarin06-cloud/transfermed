// Origem do inscrito: o canal da primeira visita vira perfil.canal no pedido de inscrição (só códigos fixos).
// uso: (site em http://127.0.0.1:8765, ou BASE=<site no ar>)  node canal.mjs
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const IG = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Instagram 300.0.0.0';
const CASOS = [
  ['link da bio do Instagram', '/diagnostico/?origem=instagram', null, null, 'instagram'],
  ['origem do diagnóstico (brasil) não é canal', '/diagnostico/?origem=brasil', null, null, 'direto'],
  ['utm_source whatsapp', '/?utm_source=whatsapp', null, null, 'whatsapp'],
  ['busca do Google', '/', 'https://www.google.com/', null, 'google'],
  ['navegador do Instagram sem referência', '/', null, IG, 'instagram'],
  ['grupo', '/?origem=grupo', null, null, 'grupo'],
  ['marca desconhecida vira outro_site (nunca o texto)', '/?origem=https://x.br/a@b.com', null, null, 'outro_site'],
  ['direto', '/', null, null, 'direto'],
];
const falhas = [];
const nav = await chromium.launch();
for (const [nome, url, ref, ua, esperado] of CASOS) {
  const ctx = await nav.newContext(ua ? { userAgent: ua } : {});
  const pag = await ctx.newPage();
  await pag.goto(BASE + url, ref ? { referer: ref } : {});
  await pag.waitForTimeout(200);
  const c = await pag.evaluate(() => window.TM_CANAL && window.TM_CANAL.canalDoInscrito());
  if (c !== esperado) falhas.push(`${nome}: esperado ${esperado}, veio ${c}`);
  if (esperado !== 'direto') {
    // primeira visita decide: uma visita seguinte direta não apaga o canal
    await pag.goto(BASE + '/sobre/');
    const depois = await pag.evaluate(() => window.TM_CANAL.canalDoInscrito());
    if (depois !== esperado) falhas.push(`${nome}: canal perdido na visita seguinte (${depois})`);
  }
  await ctx.close();
}
// o pedido de inscrição leva perfil.canal (e nada além de um código)
{
  const ctx = await nav.newContext();
  const pag = await ctx.newPage();
  const corpos = [];
  await pag.route('**/rest/v1/rpc/**', async (rota) => {
    const req = rota.request();
    if (req.url().includes('/rpc/inscrever')) corpos.push(JSON.parse(req.postData() || '{}'));
    await rota.fulfill({ status: 200, contentType: 'application/json', body: '"pendente"' });
  });
  await pag.goto(BASE + '/diagnostico/?utm_source=instagram');
  const config = await pag.evaluate(() => Boolean(window.TM_CONFIG && window.TM_CONFIG.supabaseUrl));
  if (!config) { console.log('aviso: sem Supabase configurado neste site; pedido de inscrição não testado'); }
  else {
    await pag.goto(BASE + '/sobre/');   // visita seguinte: o canal da primeira continua
    await pag.goto(BASE + '/diagnostico/');
    await pag.getByText('No Brasil', { exact: true }).click();
    for (let i = 0; i < 6 && await pag.locator('#resultado').isHidden(); i++) {
      if (await pag.locator('#semestre').isVisible()) await pag.selectOption('#semestre', '3');
      await pag.locator('#seguir').click();
      await pag.waitForTimeout(300);
    }
    await pag.fill('#email-alerta', 'teste.canal@exemplo.org');
    await pag.check('#consentimento');
    await pag.locator('#form-alerta button[type=submit]').click();
    await pag.waitForTimeout(800);
    if (!corpos.length) falhas.push('inscrição: nenhum pedido de inscrever foi enviado');
    else if (corpos[0].p_perfil.canal !== 'instagram') falhas.push(`inscrição: perfil.canal = ${corpos[0].p_perfil.canal}`);
    else if (!/^[a-z_]+$/.test(corpos[0].p_perfil.canal)) falhas.push('inscrição: canal fora do formato de código');
  }
  await ctx.close();
}
await nav.close();
if (falhas.length) { console.error(falhas.join('\n')); process.exit(1); }
console.log(`ok: ${CASOS.length} origens de inscrito`);
