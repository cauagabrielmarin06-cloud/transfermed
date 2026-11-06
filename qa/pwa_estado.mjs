// Estado real do PWA no site no ar (https): manifest, service worker, ícones e instalabilidade segundo o Chrome. Só lê.
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'https://www.transfermed.com.br';
const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 390, height: 800 } }); const p = await ctx.newPage();
await p.goto(BASE + '/', { waitUntil: 'networkidle' });
await p.waitForFunction(() => navigator.serviceWorker.ready.then(() => true), null, { timeout: 15000 }).catch(() => {});
const r = await p.evaluate(async () => {
  const link = document.querySelector('link[rel=manifest]');
  const m = link ? await (await fetch(link.href)).json() : null;
  const reg = await navigator.serviceWorker.getRegistration();
  const icones = m ? await Promise.all(m.icons.map(async i => { const x = await fetch(new URL(i.src, link.href)); return [i.src, x.status]; })) : [];
  return { https: location.protocol === 'https:', manifest: !!m, nome: m && m.name, display: m && m.display, start: m && m.start_url, icones,
    sw: reg ? { escopo: reg.scope, ativo: !!reg.active, estado: reg.active && reg.active.state } : null,
    controlado: !!navigator.serviceWorker.controller, appleTouch: document.querySelector('link[rel=apple-touch-icon]')?.href };
});
const cdp = await ctx.newCDPSession(p); await cdp.send('Page.enable');
const inst = await cdp.send('Page.getInstallabilityErrors').catch(e => ({ erro: String(e) }));
console.log(JSON.stringify({ ...r, erros_de_instalacao_chrome: inst.installabilityErrors ?? inst }, null, 1));
await b.close();
