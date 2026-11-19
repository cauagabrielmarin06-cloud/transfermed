// Guia Exterior → Brasil 2027: o botão "Comprar", o preço e as chamadas só existem com link de compra real (guia.py).
// Confere o que o visitante vê, nas duas situações (o script descobre qual é a do site que está servido), e a medição.
// uso: (site em http://127.0.0.1:8765, ou BASE=<site no ar>)  node guia_exterior.mjs
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const falhas = [];
const nav = await chromium.launch();

async function abrir(caminho, largura = 375) {
  const ctx = await nav.newContext({ viewport: { width: largura, height: 812 } });
  await ctx.addInitScript(() => { window.TM_MEDIR_TESTE = true; });
  const eventos = [], erros = [];
  await ctx.route('**/rest/v1/rpc/medir', async rota => {
    eventos.push(JSON.parse(rota.request().postData() || '{}').p_nome);
    await rota.fulfill({ status: 200, contentType: 'application/json', body: 'null' });
  });
  await ctx.route(/^https:\/\/(?!www\.transfermed|.*supabase)/, rota => rota.abort());  // nunca sai do site nem abre a plataforma de verdade
  const pag = await ctx.newPage();
  pag.on('pageerror', e => erros.push(String(e)));
  await pag.goto(BASE + caminho);
  await pag.waitForTimeout(400);
  return { ctx, pag, eventos, erros };
}

const g = await abrir('/guia-exterior/');
const ativo = (await g.pag.locator('[data-medir="guia_comprar"]').count()) > 0;
console.log(`guia: ${ativo ? 'À VENDA (com link)' : 'pré-lançamento (sem link)'}`);
const html = await g.pag.content();
const noindex = (await g.pag.locator('meta[name="robots"][content="noindex"]').count()) > 0;
if (noindex === ativo) falhas.push(`noindex deveria ser ${!ativo}, é ${noindex}`);
if (!(await g.pag.locator('h1').innerText()).includes('Guia Exterior')) falhas.push('h1 do guia ausente');
if (await g.pag.locator('#consentimento').isChecked()) falhas.push('consentimento pré-marcado');
if (g.erros.length) falhas.push('erros de JavaScript no guia: ' + g.erros.join(' | '));
if (!ativo) {
  if (/Comprar|R\$/.test(await g.pag.locator('main').innerText())) falhas.push('pré-lançamento mostra botão ou preço');
} else {
  const b = g.pag.locator('[data-medir="guia_comprar"]');
  const href = await b.getAttribute('href');
  if (!/^https:\/\//.test(href)) falhas.push('link de compra não é https: ' + href);
  if ((await b.getAttribute('rel')) !== 'noopener' || (await b.getAttribute('target')) !== '_blank') falhas.push('botão sem noopener/_blank');
  const caixa = await b.boundingBox();
  if (caixa.height < 44) falhas.push(`botão Comprar com ${Math.round(caixa.height)} px de altura (< 44)`);
  const [aba] = await Promise.all([g.ctx.waitForEvent('page', { timeout: 3000 }).catch(() => null), b.click()]);
  await g.pag.waitForTimeout(500);
  if (!g.eventos.includes('guia_comprar')) falhas.push('clique em Comprar não mediu guia_comprar: ' + g.eventos);
  if (aba) await aba.close();
}
await g.ctx.close();

// chamadas: só existem com o guia à venda
const ex = await abrir('/exterior/');
const chamadaExt = await ex.pag.locator('.guia-chamada a[href$="guia-exterior/"]').count();
if ((chamadaExt > 0) !== ativo) falhas.push(`chamada na /exterior/: ${chamadaExt} com guia ${ativo ? 'à venda' : 'em pré-lançamento'}`);
if (ativo && chamadaExt) {
  await Promise.all([ex.pag.waitForURL('**/guia-exterior/'), ex.pag.locator('.guia-chamada a').click()]);
  if (!ex.eventos.includes('guia_chamada')) falhas.push('clique na chamada da /exterior/ não mediu guia_chamada: ' + ex.eventos);
}
await ex.ctx.close();

const ini = await abrir('/', 1280);
const radar = ini.pag.locator('#guia-radar');
if ((await radar.count() > 0) !== ativo) falhas.push('chamada do radar na home não acompanha o estado do guia');
if (ativo) {
  if (!(await radar.isHidden())) falhas.push('chamada do radar já aparece sem o chip "Aceitam do exterior"');
  await ini.pag.locator('.chip[data-filtro="exterior"]').click();
  if (!(await radar.isVisible())) falhas.push('chamada do radar não aparece com o chip do exterior');
  await radar.locator('a').click({ trial: true });  // alcançável por clique
  await ini.pag.locator('.chip[data-filtro="abertos"]').click();
  if (!(await radar.isHidden())) falhas.push('chamada do radar não some ao trocar de chip');
}
await ini.ctx.close();

// sitemap e robots
const sm = await (await fetch(BASE + '/sitemap.xml')).text();
if (sm.includes('/guia-exterior/') !== ativo) falhas.push('sitemap não acompanha o estado do guia');
await nav.close();
if (falhas.length) { console.error('FALHAS:\n' + falhas.join('\n')); process.exit(1); }
console.log('ok: guia exterior (' + (ativo ? 'à venda' : 'pré-lançamento') + ')');
