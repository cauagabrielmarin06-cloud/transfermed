// Deslocamento de layout (CLS) das páginas principais no celular, com rede e processador lentos (os elementos que o
// JavaScript monta chegam tarde, que é quando o layout pula). Falha se alguma página passar de 0,1.
// Minha lista é medida vazia e com um edital salvo; o resultado, depois do diagnóstico.
// uso: (site servido em http://127.0.0.1:8765, ou BASE=<site no ar>)  node cls.mjs
import { chromium, devices } from 'playwright';

const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const LIMITE = 0.1;
const b = await chromium.launch();
const falhas = [];

async function medir(nome, caminho, { salvo, depois } = {}) {
  const c = await b.newContext({ ...devices['Pixel 7'] });
  await c.route(/\/(rest|functions)\/v1\//, (r) => r.fulfill({ status: 200, contentType: 'application/json', body: '0' }));
  const p = await c.newPage();
  const cdp = await c.newCDPSession(p);
  await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 150, downloadThroughput: 1.6e6 / 8, uploadThroughput: 750e3 / 8 });
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
  await p.addInitScript((id) => {
    try { if (id) localStorage.setItem('tm_marcados', JSON.stringify([id])); } catch (e) {}
    window.__cls = 0; window.__fontes = [];
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) {
        if (e.hadRecentInput) continue;
        window.__cls += e.value;
        window.__fontes.push(`${e.value.toFixed(3)} ${(e.sources || []).map((s) => s.node ? (s.node.id || String(s.node.className || s.node.nodeName)).slice(0, 40) : '?').join(', ')}`);
      }
    }).observe({ type: 'layout-shift', buffered: true });
  }, salvo || null);
  await p.goto(BASE + caminho, { waitUntil: 'load', timeout: 60000 });
  if (depois) await depois(p);
  await p.waitForTimeout(4000);
  const r = await p.evaluate(() => ({ cls: window.__cls, fontes: window.__fontes }));
  const ok = r.cls <= LIMITE;
  console.log(`${ok ? 'ok   ' : 'FALHA'} ${nome}: CLS ${r.cls.toFixed(3)}${r.fontes.length ? ' — ' + r.fontes.join(' | ') : ''}`);
  if (!ok) falhas.push(nome);
  await c.close();
}

// ficha de edital e de faculdade: um edital aberto de hoje (o mesmo vai salvo na Minha lista)
const p0 = await b.newPage();
await p0.goto(BASE + '/editais/', { waitUntil: 'domcontentloaded' });
const edital = new URL(await p0.locator('#abertos a[href*="/edital/"]').first().getAttribute('href'), p0.url()).pathname;
await p0.goto(BASE + edital, { waitUntil: 'domcontentloaded' });
const id = await p0.$eval('[data-edital]', (el) => el.dataset.edital);
const faculdade = new URL(await p0.locator('a[href*="/faculdade/"]').first().getAttribute('href'), p0.url()).pathname;
await p0.close();

const diagnostico = async (p) => {
  await p.getByText('No Brasil', { exact: true }).click();
  for (let i = 0; i < 6 && await p.locator('#resultado').isHidden(); i++) {
    if (await p.locator('#semestre').isVisible()) await p.selectOption('#semestre', '3');
    await p.locator('#seguir').click(); await p.waitForTimeout(300);
  }
};
for (const [nome, caminho, op] of [
  ['home', '/'], ['diagnóstico', '/diagnostico/'], ['resultado', '/diagnostico/', { depois: diagnostico }],
  ['ficha de edital', edital], ['ficha de faculdade', faculdade], ['estado', '/estado/sp/'], ['exterior', '/exterior/'],
  ['editais', '/editais/'], ['minha lista (vazia)', '/minha-lista/'], ['minha lista (com edital)', '/minha-lista/', { salvo: id }],
  ['sobre', '/sobre/'], ['contato', '/contato/'], ['privacidade', '/privacidade/'],
  ['alerta: confirmar', '/alerta/confirmar/?t=00000000-0000-4000-8000-000000000000'],
  ['alerta: descadastrar', '/alerta/descadastrar/?t=00000000-0000-4000-8000-000000000000'],
]) await medir(nome, caminho, op);

await b.close();
console.log(falhas.length ? `${falhas.length} página(s) acima de ${LIMITE}: ${falhas.join(', ')}` : `ok: CLS até ${LIMITE} em todas as páginas`);
process.exit(falhas.length ? 1 : 0);
