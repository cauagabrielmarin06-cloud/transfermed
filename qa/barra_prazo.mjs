// B3: barra fixa do prazo no celular. Aparece depois do primeiro scroll, some quando o bloco do lembrete está na tela, não
// existe no computador, não cobre o conteúdo (padding no body) e "Me lembre" rola até o bloco.
// uso: (com o site em http://127.0.0.1:8765)  PAGINA=edital/x node barra_prazo.mjs
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const PAGINA = '/' + (process.env.PAGINA || 'edital/fpp-curitiba-externa-2027-1-528d5e').replace(/^\/+|\/+$/g, '') + '/';
mkdirSync('screenshots', { recursive: true });
const falhas = [];
const ok = (c, t) => { if (!c) falhas.push(t); console.log((c ? 'ok   ' : 'FALHA ') + t); };
const b = await chromium.launch();

const celular = await b.newContext({ viewport: { width: 375, height: 700 }, isMobile: true, hasTouch: true });
await celular.route('**/rest/v1/rpc/**', r => r.fulfill({ status: 200, contentType: 'application/json', body: '0' }));
const p = await celular.newPage(); const erros = [];
p.on('pageerror', e => erros.push(String(e))); p.on('console', m => m.type() === 'error' && erros.push(m.text()));
await p.goto(BASE + PAGINA, { waitUntil: 'load' }); await p.waitForTimeout(300);
const barra = p.locator('#barra-prazo');
ok(await barra.count() === 1, 'a ficha tem a barra');
ok(!(await barra.isVisible()), 'sem scroll, a barra não aparece');
await p.mouse.move(100, 300); await p.evaluate(() => scrollTo(0, 400)); await p.waitForTimeout(400);
ok(await barra.isVisible(), 'depois do primeiro scroll, a barra aparece');
const texto = (await barra.innerText()).replace(/\s+/g, ' ');
ok(/fecha (hoje|em \d+ dias?)/.test(texto) && /\d\d\/\d\d/.test(texto), `texto da barra: "${texto}"`);
ok(await p.evaluate(() => getComputedStyle(document.body).paddingBottom !== '0px'), 'padding-bottom no body');
await p.screenshot({ path: 'screenshots/barra-prazo-375.png' });
const sobre = await p.evaluate(() => { const r = document.querySelector('#barra-prazo').getBoundingClientRect(); return r.bottom <= innerHeight + 1 && r.height < 110; });
ok(sobre, 'barra baixa, colada no pé da tela');
await barra.locator('a').click(); await p.waitForTimeout(900);
const noBloco = await p.evaluate(() => { const r = document.querySelector('#lembrete').getBoundingClientRect(); return r.top < innerHeight && r.bottom > 0; });
ok(noBloco, '"Me lembre" leva ao bloco');
ok(!(await barra.isVisible()), 'com o bloco na tela, a barra some');
ok(await p.evaluate(() => document.activeElement && document.activeElement.id === 'email-alerta'), 'o campo de e-mail recebe o foco');
await p.evaluate(() => scrollTo(0, document.documentElement.scrollHeight)); await p.waitForTimeout(400);
ok(await barra.isVisible(), 'longe do bloco, a barra volta');
ok(erros.length === 0, 'console limpo ' + erros.join(' | '));
await celular.close();

const pc = await b.newContext({ viewport: { width: 1280, height: 800 } });
const q = await pc.newPage();
await q.goto(BASE + PAGINA, { waitUntil: 'load' }); await q.evaluate(() => scrollTo(0, 600)); await q.waitForTimeout(400);
ok(!(await q.locator('#barra-prazo').isVisible()), 'no computador, a barra não existe');
await pc.close();

// páginas sem prazo conferido não levam a barra
const sem = await (await b.newContext({ viewport: { width: 375, height: 700 }, isMobile: true })).newPage();
await sem.goto(BASE + '/edital/idomed-ribeirao-externa-2027-1-fd97a5/', { waitUntil: 'load' });
ok(await sem.locator('#barra-prazo').count() === 0, 'edital sem prazo conferido: sem barra');
await b.close();
console.log(falhas.length ? `${falhas.length} falha(s)` : 'tudo certo');
process.exit(falhas.length ? 1 : 0);
