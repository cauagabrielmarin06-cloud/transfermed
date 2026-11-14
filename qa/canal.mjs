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
  ['radar compartilhado por um amigo (E3.2)', '/?de=andradina-sp&p=7&km=400&origem=compartilhar', null, null, 'indicacao'],
  ['marca desconhecida vira outro_site (nunca o texto)', '/?origem=https://x.br/a@b.com', null, null, 'outro_site'],
  ['direto', '/', null, null, 'direto'],
];
const falhas = [];
const nav = await chromium.launch();
// referenciadores que o navegador não deixa simular com `referer` (esquema android-app://) e o navegador interno com referência do próprio site:
// chamam a função direto, com a mesma regra do app (09/11/2026: o Instagram aparecia como outro_site ou direto)
{
  const ctx0 = await nav.newContext();
  const pag0 = await ctx0.newPage();
  await pag0.goto(BASE + '/');
  const casos = [
    ['l.instagram.com', 'https://l.instagram.com/?u=x', '', 'instagram'],
    ['instagram.com', 'https://www.instagram.com/', '', 'instagram'],
    ['app Android do Instagram', 'android-app://com.instagram.android/', '', 'instagram'],
    ['navegador do Instagram com referência do próprio site', 'https://www.transfermed.com.br/', IG, 'instagram'],
    ['navegador do Instagram com referência estranha', 'https://exemplo.com.br/', IG, 'instagram'],
    ['app do Facebook', 'android-app://com.facebook.katana', '', 'facebook'],
    ['app do WhatsApp', 'android-app://com.whatsapp', '', 'whatsapp'],
    ['app do Google', 'android-app://com.google.android.googlequicksearchbox', '', 'google'],
    ['site qualquer', 'https://blog.exemplo.com.br/post', '', 'outro_site'],
    ['sem referência', '', '', 'direto'],
  ];
  for (const [nome, ref, ua, esperado] of casos) {
    const c = await pag0.evaluate(([r, u]) => window.TM_CANAL.canalDaVisita(new URL(location.href), r, u), [ref, ua]);
    if (c !== esperado) falhas.push(`${nome}: esperado ${esperado}, veio ${c}`);
  }
  await ctx0.close();
}
// domínio de origem: só o domínio, só quando o canal é outro_site
{
  const ctx1 = await nav.newContext();
  const pag1 = await ctx1.newPage();
  await pag1.goto(BASE + '/', { referer: 'https://www.blog.exemplo.com.br/caminho/longo?busca=segredo#x' });
  await pag1.waitForTimeout(200);
  const r = await pag1.evaluate(() => [window.TM_CANAL.canalDoInscrito(), window.TM_CANAL.refDoInscrito(), localStorage.getItem('tm_canal')]);
  if (r[0] !== 'outro_site' || r[1] !== 'blog.exemplo.com.br') falhas.push(`domínio de origem: ${JSON.stringify(r)}`);
  if (/caminho|segredo|busca/.test(r[2] || '')) falhas.push('domínio de origem: guardou mais do que o domínio');
  await ctx1.close();
  const ctx2 = await nav.newContext();
  const pag2 = await ctx2.newPage();
  await pag2.goto(BASE + '/', { referer: 'https://l.instagram.com/' });
  await pag2.waitForTimeout(200);
  const r2 = await pag2.evaluate(() => [window.TM_CANAL.canalDoInscrito(), window.TM_CANAL.refDoInscrito()]);
  if (r2[0] !== 'instagram' || r2[1] !== '') falhas.push(`instagram não guarda domínio: ${JSON.stringify(r2)}`);
  await ctx2.close();
}
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
    else if (corpos[0].p_perfil.porta !== 'diagnostico') falhas.push(`inscrição: perfil.porta = ${corpos[0].p_perfil.porta}`);
    else if (corpos[0].porta !== undefined) falhas.push('inscrição: porta vazou para fora do perfil');
  }
  await ctx.close();
}
await nav.close();
if (falhas.length) { console.error(falhas.join('\n')); process.exit(1); }
console.log(`ok: ${CASOS.length} origens de inscrito`);
