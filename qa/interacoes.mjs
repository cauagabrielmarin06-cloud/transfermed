// Interações do início que já quebraram por cópia antiga do service worker: "Buscar pelo nome", botões do mapa
// ("Brasil" e estados) e o próprio service worker (assume na hora e apaga caches antigos).
// uso: (com o site servido em http://127.0.0.1:8765)  node interacoes.mjs  → relatorios/interacoes.json
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';

const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const LARGURAS = [[375, 812], [1280, 900]];
const falhas = [];

async function checar(nome, largura, fn) {
  try { await fn(); console.log(`ok    ${nome} @${largura}`); }
  catch (erro) { falhas.push({ teste: nome, largura, erro: String(erro.message || erro).split('\n')[0] }); console.log(`FALHOU ${nome} @${largura}: ${erro.message}`); }
}
function exigir(cond, msg) { if (!cond) throw new Error(msg); }

const navegador = await chromium.launch();
for (const [w, h] of LARGURAS) {
  const ctx = await navegador.newContext({ viewport: { width: w, height: h }, serviceWorkers: 'block' });
  const p = await ctx.newPage();
  await p.goto(BASE + '/', { waitUntil: 'load' });

  await checar('Buscar pelo nome abre a busca e acha faculdade', w, async () => {
    await p.getByRole('button', { name: 'Buscar pelo nome' }).click();
    await p.locator('#busca').waitFor({ state: 'visible', timeout: 3000 });
    await p.locator('#busca-campo').fill('UFBA');
    await p.locator('#busca-lista a').first().waitFor({ state: 'visible', timeout: 3000 });
    await p.keyboard.press('Escape');
  });

  await p.goto(BASE + '/', { waitUntil: 'load' });
  await checar('Mapa abre em Brasil e o botão Brasil volta da vista de estado', w, async () => {
    const svg = p.locator('figure.radar svg').first();
    const brasil = p.locator('figure.radar .vistas button', { hasText: /^Brasil$/ }).first();
    exigir(await svg.getAttribute('viewBox') === '0 0 400 400', 'o mapa não abriu em "Brasil"');
    await p.locator('.vistas-estados button').first().click();
    exigir(await svg.getAttribute('viewBox') !== '0 0 400 400', 'o botão do estado não mudou o mapa');
    await brasil.click();
    exigir(await svg.getAttribute('viewBox') === '0 0 400 400', 'o botão "Brasil" não voltou ao Brasil inteiro');
    exigir(await brasil.getAttribute('aria-pressed') === 'true', '"Brasil" não ficou marcado');
  });

  await checar('Cada botão de estado muda o mapa e fica marcado', w, async () => {
    const svg = p.locator('figure.radar svg').first();
    const estados = p.locator('.vistas-estados button');
    const n = await estados.count();
    exigir(n >= 4, `só ${n} botões de estado`);
    for (let i = 0; i < n; i++) {
      const b = estados.nth(i);
      await b.click();
      exigir(await svg.getAttribute('viewBox') === await b.getAttribute('data-vista'), `"${await b.textContent()}" não mudou o mapa`);
      exigir(await b.getAttribute('aria-pressed') === 'true', `"${await b.textContent()}" não ficou marcado`);
    }
  });
  await ctx.close();
}

// service worker: 127.0.0.1 conta como seguro, então dá para registrar aqui (no site o app.js só registra em https)
await checar('Service worker assume na hora e apaga caches antigos', 'sw', async () => {
  const ctx = await navegador.newContext();
  const p = await ctx.newPage();
  await p.goto(BASE + '/', { waitUntil: 'load' });
  const r = await p.evaluate(async () => {
    await caches.open('tm-antigo');
    await navigator.serviceWorker.register('sw.js', { updateViaCache: 'none' });
    await navigator.serviceWorker.ready;
    for (let i = 0; i < 50 && !navigator.serviceWorker.controller; i++) await new Promise(ok => setTimeout(ok, 100));
    return { controla: !!navigator.serviceWorker.controller, caches: await caches.keys() };
  });
  exigir(r.controla, 'o service worker novo não assumiu a página sem recarregar');
  exigir(!r.caches.includes('tm-antigo'), 'o cache antigo não foi apagado');
  exigir(r.caches.length === 1 && r.caches[0].startsWith('tm-'), `caches inesperados: ${r.caches.join(', ')}`);
  // HTML vem da rede: o que a página recebe é o que o servidor tem agora
  const servidor = await (await fetch(BASE + '/')).text();
  const pelaPagina = await p.evaluate(async () => (await fetch('./', { headers: { accept: 'text/html' } })).text());
  exigir(pelaPagina === servidor, 'o HTML veio de cópia, não da rede');
  // página já controlada que recebe um service worker novo mostra o aviso "Nova versão disponível"
  await p.reload({ waitUntil: 'load' });
  await p.evaluate(() => navigator.serviceWorker.dispatchEvent(new Event('controllerchange')));
  await p.locator('.nova-versao', { hasText: 'Nova versão disponível' }).waitFor({ state: 'visible', timeout: 3000 });
  await ctx.close();
});

await navegador.close();
mkdirSync('relatorios', { recursive: true });
writeFileSync('relatorios/interacoes.json', JSON.stringify(falhas, null, 2));
console.log(`\nInterações com falha: ${falhas.length}`);
