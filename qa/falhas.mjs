// Sem internet ou com o banco fora do ar, o alerta e o contato mostram uma mensagem clara em português (nada de
// "Failed to fetch"), e o formulário vazio diz o que falta. Banco simulado: nenhum envio real sai daqui.
// uso: (site servido em http://127.0.0.1:8765, ou BASE=<site no ar>)  node falhas.mjs
import { chromium, devices } from 'playwright';

const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const b = await chromium.launch();
const ctx = await b.newContext({ ...devices['Pixel 7'] });
const p = await ctx.newPage();
const falhas = [];
const conferir = (ok, txt) => { console.log(ok ? 'ok   ' : 'FALHA', txt); if (!ok) falhas.push(txt); };
const ruim = /failed to fetch|load failed|networkerror|typeerror|undefined|null/i;

// 1) alerta: sem e-mail, depois sem conexão
await ctx.route(/\/(rest|functions)\/v1\//, (r) => r.abort('internetdisconnected'));
await p.goto(`${BASE}/exterior/`, { waitUntil: 'domcontentloaded' });
const form = p.locator('#form-alerta').first();
await form.scrollIntoViewIfNeeded();
await form.locator('button[type="submit"]').click();
await p.waitForTimeout(300);
const vazio = (await form.locator('#alerta-msg').innerText()).trim();
conferir(vazio.length > 0 && !ruim.test(vazio), `alerta vazio diz o que falta ("${vazio}")`);
await form.locator('#email-alerta').fill('teste@exemplo.com');
await form.locator('#consentimento').check();
await form.locator('button[type="submit"]').click();
await p.waitForTimeout(800);
const semRede = (await form.locator('#alerta-msg').innerText()).trim();
conferir(/conex|internet/i.test(semRede) && !ruim.test(semRede), `alerta sem conexão: mensagem clara ("${semRede}")`);

// 2) contato: sem conexão
await p.goto(`${BASE}/contato/`, { waitUntil: 'domcontentloaded' });
const c = p.locator('#form-contato');
if (await c.count()) {
  await c.locator('button[type="submit"]').click();
  await p.waitForTimeout(300);
  const v2 = (await c.locator('#contato-msg').innerText()).trim();
  conferir(v2.length > 0 && !ruim.test(v2), `contato vazio diz o que falta ("${v2}")`);
  await c.locator('#c-nome').fill('Teste');
  await c.locator('#c-email').fill('teste@exemplo.com');
  await c.locator('#c-mensagem').fill('Mensagem de teste');
  await c.locator('input[name="consentimento"]').check();
  await c.locator('button[type="submit"]').click();
  await p.waitForTimeout(800);
  const m = (await c.locator('#contato-msg').innerText()).trim();
  conferir(/conex|internet/i.test(m) && !ruim.test(m), `contato sem conexão: mensagem clara ("${m}")`);
} else conferir(true, 'contato desligado neste site (sem formulário)');

// 3) confirmação do alerta com o banco fora do ar
await p.goto(`${BASE}/alerta/confirmar/?t=00000000-0000-4000-8000-000000000000`, { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1200);
const conf = (await p.locator('main').innerText()).trim();
conferir(/conex|tente/i.test(conf) && !ruim.test(conf), 'confirmação sem conexão: mensagem clara');

await b.close();
console.log(falhas.length ? `${falhas.length} falha(s)` : 'ok: falhas de rede com mensagem clara');
process.exit(falhas.length ? 1 : 0);
