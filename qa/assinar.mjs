// Botões "Assinar" do calendário: no iPhone/iPad seguem no webcal:// (o app Calendário abre); no computador e no
// Android o clique abre o painel com Google Agenda, Outlook e "Copiar link do calendário" (bug de 31/10/2026: no
// Windows o webcal:// não tinha programa e o clique não fazia nada).
// uso: (site servido em http://127.0.0.1:8765, ou BASE=<site no ar>)  node assinar.mjs
import { chromium, webkit, devices } from 'playwright';

const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const IG = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 300.0.0.0';
const AMBIENTES = [
  ['computador (Chromium)', chromium, { viewport: { width: 1280, height: 900 } }, false],
  ['Android (Chromium)', chromium, { ...devices['Pixel 7'] }, false],
  ['iPhone (WebKit)', webkit, { ...devices['iPhone 13'] }, true],
  ['Instagram no iPhone (WebKit)', webkit, { ...devices['iPhone 13'], userAgent: IG }, true],
];

async function primeiraFichaComAgenda(pag) {
  await pag.goto(`${BASE}/editais/`, { waitUntil: 'load' });
  const links = await pag.$$eval('a[href*="/edital/"]', (as) => [...new Set(as.map((a) => a.href))]);
  for (const l of links.slice(0, 40)) {
    await pag.goto(l, { waitUntil: 'load' });
    if (await pag.$('a[data-assinar]')) return l;
  }
  throw new Error('nenhuma ficha com botão "Assinar"');
}

const falhas = [];
let ficha = null;
for (const [nome, motor, cfg, ios] of AMBIENTES) {
  const nav = await motor.launch();
  const ctx = await nav.newContext({ ...cfg, ...(motor === chromium ? { permissions: ['clipboard-read', 'clipboard-write'] } : {}) });
  const pag = await ctx.newPage();
  const erros = [];
  pag.on('pageerror', (e) => erros.push(e.message));
  try {
    ficha = ficha || await primeiraFichaComAgenda(pag);
    // páginas com botões "Assinar": ficha do edital e Minha lista (com um edital salvo)
    const id = await (async () => { await pag.goto(ficha, { waitUntil: 'load' }); return pag.$eval('[data-edital]', (el) => el.dataset.edital); })();
    for (const [onde, url, preparar] of [
      ['ficha', ficha, null],
      ['Minha lista', `${BASE}/minha-lista/`, () => localStorage.setItem('tm_marcados', JSON.stringify([window.__id]))],
    ]) {
      if (preparar) { await pag.addInitScript(`window.__id = ${JSON.stringify(id)}; (${preparar})()`); }
      await pag.goto(url, { waitUntil: 'load' });
      const sum = await pag.$('details.agenda-ajuda > summary');
      if (onde === 'Minha lista' && sum) await sum.click();
      const botao = pag.locator('a[data-assinar]').first();
      if (!(await botao.count())) { falhas.push(`${nome} · ${onde}: sem botão "Assinar"`); continue; }
      const href = await botao.getAttribute('href');
      if (!href.startsWith('webcal://')) falhas.push(`${nome} · ${onde}: href não é webcal:// (${href})`);
      if (ios) {
        // no iPhone o clique segue o webcal:// (não pode ser cancelado nem abrir painel)
        const cancelado = await botao.evaluate((a) => { let c = null; a.addEventListener('click', (e) => { c = e.defaultPrevented; e.preventDefault(); }, { once: true }); a.click(); return c; });
        if (cancelado) falhas.push(`${nome} · ${onde}: o clique foi cancelado (o webcal:// não abriria)`);
        if (await pag.locator('.assinar-opcoes').count()) falhas.push(`${nome} · ${onde}: painel aberto no iPhone`);
        continue;
      }
      await botao.click();
      const painel = pag.locator('.assinar-opcoes').first();
      if (!(await painel.isVisible())) { falhas.push(`${nome} · ${onde}: clique sem efeito (painel não apareceu)`); continue; }
      const textos = (await painel.locator('a, button').allInnerTexts()).map((t) => t.trim());
      for (const t of ['Adicionar ao Google Agenda', 'Adicionar ao Outlook', 'Copiar link do calendário']) {
        if (!textos.some((x) => x.startsWith(t))) falhas.push(`${nome} · ${onde}: falta "${t}"`);
      }
      const g = await painel.locator('a', { hasText: 'Google' }).getAttribute('href');
      const o = await painel.locator('a', { hasText: 'Outlook' }).getAttribute('href');
      if (!g.startsWith('https://calendar.google.com/calendar/r?cid=webcal')) falhas.push(`${nome} · ${onde}: link do Google errado`);
      if (!o.startsWith('https://outlook.live.com/calendar/0/addfromweb?url=https')) falhas.push(`${nome} · ${onde}: link do Outlook errado`);
      await painel.locator('button', { hasText: 'Copiar link' }).click();
      await pag.waitForTimeout(300);
      const msg = (await painel.locator('[data-copiar-msg]').innerText()).trim();
      if (!msg) falhas.push(`${nome} · ${onde}: "Copiar link" sem mensagem`);
      const copiado = await pag.evaluate(() => navigator.clipboard.readText().catch(() => null));
      if (copiado !== null && !/^https:\/\/.+\.ics/.test(copiado) && !/\/rpc\/agenda\?/.test(copiado)) falhas.push(`${nome} · ${onde}: copiou "${copiado}"`);
      // segundo clique fecha o painel (o botão não fica "morto")
      await botao.click();
      if (await painel.isVisible()) falhas.push(`${nome} · ${onde}: segundo clique não fechou o painel`);
    }
  } catch (e) {
    falhas.push(`${nome}: ${e.message.split('\n')[0]}`);
  }
  if (erros.length) falhas.push(`${nome}: erro de JavaScript: ${erros.join(' | ')}`);
  console.log(`${nome}: ${falhas.filter((f) => f.startsWith(nome)).length ? 'FALHOU' : 'ok'}`);
  await nav.close();
}
if (falhas.length) { console.log(falhas.join('\n')); process.exit(1); }
console.log(`ok: botões "Assinar" conferidos em ${AMBIENTES.length} ambientes (${ficha})`);
