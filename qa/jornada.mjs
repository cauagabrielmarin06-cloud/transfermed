// Auditoria como estudante, no celular (375 px, 4G simulado): home → diagnóstico → resultado → ficha → alerta →
// agenda → minha lista. Uma captura da tela por passo (o que a pessoa vê, sem rolar a página inteira), tempo até o
// maior conteúdo aparecer (LCP) e erros de console. O Supabase é interceptado (nada real é gravado).
// uso: (com o site servido em http://127.0.0.1:8765)  node jornada.mjs  → screenshots/jornada/*.png e relatorios/jornada.json
import { chromium, devices } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';

const BASE = process.env.BASE || 'http://127.0.0.1:8765';
mkdirSync('screenshots/jornada', { recursive: true });
const passos = [];
const navegador = await chromium.launch();
const ctx = await navegador.newContext({ ...devices['iPhone 12'], viewport: { width: 375, height: 812 } });
await ctx.route('**/rest/v1/rpc/**', rota => rota.fulfill({ status: 200, contentType: 'application/json',
  body: JSON.stringify({ inscrever: 'pendente', confirmar: 'ok' }[rota.request().url().split('/rpc/')[1]] ?? 0) }));
const p = await ctx.newPage();
const cdp = await ctx.newCDPSession(p);
await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 150, downloadThroughput: 1.6e6 / 8, uploadThroughput: 750e3 / 8 });
await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
const erros = [];
p.on('console', m => { if (m.type() === 'error') erros.push(m.text()); });
p.on('pageerror', e => erros.push(String(e)));
await p.addInitScript(() => {
  window.__lcp = 0; window.__cls = 0;
  new PerformanceObserver(l => { for (const e of l.getEntries()) window.__lcp = e.startTime; }).observe({ type: 'largest-contentful-paint', buffered: true });
  new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; }).observe({ type: 'layout-shift', buffered: true });
});
let n = 0;
async function passo(nome, nota = '') {
  await p.waitForTimeout(400);
  const arq = `screenshots/jornada/${String(++n).padStart(2, '0')}-${nome}.png`;
  await p.screenshot({ path: arq });
  const m = await p.evaluate(() => ({ lcp: Math.round(window.__lcp), cls: Number(window.__cls.toFixed(3)), url: location.pathname + location.hash,
    altura: document.documentElement.scrollHeight }));
  passos.push({ passo: nome, arq, nota, ...m, erros: erros.splice(0) });
  console.log(`${nome}: LCP ${m.lcp} ms · CLS ${m.cls} · altura ${m.altura}px ${nota}`);
}

await p.goto(BASE + '/', { waitUntil: 'load' });
await passo('home');
await p.locator('a[href*="diagnostico"]').filter({ hasText: /diagn|onde posso|descubr/i }).first().click();
await p.waitForURL(/diagnostico/);
await passo('diagnostico-1');
await p.getByText('No Brasil', { exact: true }).click();
await p.locator('#seguir').click();
await passo('diagnostico-2');
await p.selectOption('#semestre', '3');
await p.locator('#seguir').click();
await passo('diagnostico-3');
await p.fill('#cidade', 'Salvador - BA');
await p.locator('#seguir').click();
await passo('diagnostico-4');
for (let i = 0; i < 3 && await p.locator('#resultado').isHidden(); i++) { await p.locator('#seguir').click(); await p.waitForTimeout(300); }
await passo('resultado-topo');
await p.mouse.wheel(0, 700);
await passo('resultado-rolado');
const primeiro = p.locator('#resultado article.cartao h3 a').first();
const destino = await primeiro.getAttribute('href');
await primeiro.click();
await p.waitForLoadState('load');
await passo('ficha', destino);
await p.locator('#t-quando').scrollIntoViewIfNeeded();
await passo('ficha-quando');
await p.locator('.agenda').scrollIntoViewIfNeeded();
await passo('ficha-agenda');
await p.locator('#alerta').scrollIntoViewIfNeeded();
await passo('ficha-alerta');
await p.fill('#email-alerta', 'teste.jornada@exemplo.com');
await p.check('#consentimento');
await p.locator('#form-alerta button[type=submit]').click();
await p.waitForSelector('#alerta-passo2:not([hidden])');
await passo('ficha-alerta-enviado');
await p.locator('[data-marcar]').first().click();
await p.goto(BASE + '/minha-lista/', { waitUntil: 'load' });
await passo('minha-lista');
await p.mouse.wheel(0, 600);
await passo('minha-lista-rolado');

await navegador.close();
mkdirSync('relatorios', { recursive: true });
writeFileSync('relatorios/jornada.json', JSON.stringify(passos, null, 2));
