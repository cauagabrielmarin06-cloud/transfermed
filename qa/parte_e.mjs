// Parte E (14/11/2026): revisão profunda do radar pessoal. Cada verificação reprova o site antigo (rode com BASE=https://www.transfermed.com.br antes da publicação).
// E1.1 radar parado em "reduzir movimento"; E1.2 painel "O robô hoje" depois da meia-noite (dia de Brasília); E1.4 mapa dentro da janela do celular;
// E1.5 resultado sem repetir; E1.6 pílulas em grade; E1.7 campi agrupados; E1.8 (choque) está em meu_plano.mjs; E3.x mais abaixo.
// uso: (site em http://127.0.0.1:8765, ou BASE=<site no ar>)  node parte_e.mjs
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';

const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const falhas = [];
const ok = (c, t) => { console.log((c ? 'ok   ' : 'FALHA ') + t); if (!c) falhas.push(t); };
const b = await chromium.launch();
const semAbertura = () => { try { sessionStorage.setItem('tm_abertura', '1'); } catch (e) {} };

async function nova(op = {}) {
  const ctx = await b.newContext(op);
  await ctx.addInitScript(semAbertura);
  const p = await ctx.newPage();
  const erros = [];
  p.on('pageerror', (e) => erros.push(e.message));
  p.on('console', (m) => m.type() === 'error' && erros.push(m.text()));
  return { ctx, p, erros };
}
const escolher = async (p, texto = 'Andradina') => {
  await p.click('#rp-cidade'); await p.fill('#rp-cidade', ''); await p.type('#rp-cidade', texto, { delay: 12 });
  await p.waitForSelector('#rp-lista li'); await p.click('#rp-lista li:first-child');
  await p.waitForSelector('#rp-cont:not([hidden])');
};
const caixa = (p, sel) => p.$eval(sel, (e) => { const r = e.getBoundingClientRect(); return { t: r.top, b: r.bottom, l: r.left, r: r.right, w: r.width, h: r.height }; });

// ---- E1.1 radar parado: em movimento reduzido o feixe some (só anéis e pontos); com movimento ele continua
for (const [mov, esperado] of [['reduce', 'hidden'], ['no-preference', 'visible']]) {
  const { ctx, p } = await nova({ viewport: { width: 375, height: 812 }, reducedMotion: mov });
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  await p.waitForTimeout(mov === 'reduce' ? 200 : 2000);
  const v = await p.$eval('.r3-feixe', (e) => getComputedStyle(e).visibility);
  ok(v === esperado, `E1.1 (${mov}): feixe ${esperado} (era ${v})`);
  if (mov === 'reduce') {
    ok(await p.$$eval('.r3-aneis circle', (c) => c.every((x) => getComputedStyle(x).visibility !== 'hidden') && c.length >= 3), 'E1.1: os anéis seguem visíveis');
    ok((await p.$$eval('.r3-pontos .pe, .r3-pontos .pt', (c) => c.length)) > 0, 'E1.1: os pontos seguem no mapa');
  }
  await ctx.close();
}

// ---- E1.2 painel "O robô hoje" com o relógio de Brasília
const painelHtml = execFileSync('python', ['-c', `
import sys; sys.path.insert(0, '..')
import gerar_site as g
F = {"a": {"id": "a", "nome": "A", "sigla": "A", "cidade": "X", "uf": "SP"}}
r = {"atualizado_em": "2026-11-13", "executado_em_utc": "2026-11-13T09:00:20Z", "paginas": {"p": {"ultimo_ok": "2026-11-13"}}, "pdfs": {}}
e = {"executado_em_utc": "2026-11-13T09:17:30Z", "novos": [], "atualizados": [], "retificacoes": []}
sys.stdout.buffer.write(g.painel_robo(F, "2026-11-13", "", e, r).encode("utf-8"))
`], { cwd: new URL('.', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1') }).toString('utf8');
ok(painelHtml.includes('data-rodada="2026-11-13T09:17:30Z"'), 'E1.2: o gerador entrega o painel com data-dia e data-rodada');
for (const [relogio, titulo, quando, prox, rotulo] of [
  ['2026-11-13T12:30:00Z', 'O robô hoje · ao vivo', 'hoje', 'amanhã', '09h30 de 13/11 (a rodada acabou de rodar)'],
  ['2026-11-14T03:30:00Z', 'Última rodada · 13/11', 'em 13/11', 'hoje', '00h30 de 14/11 (virou o dia)'],
  ['2026-11-14T15:00:00Z', 'Última rodada · 13/11', 'em 13/11', 'amanhã', '12h00 de 14/11 (o dia seguinte)'],
  ['2026-11-13T23:00:00Z', 'O robô hoje · última leitura', 'hoje', 'amanhã', '20h00 de 13/11 (mais de 12 h da rodada)'],
]) {
  const { ctx, p, erros } = await nova({ viewport: { width: 1280, height: 900 }, timezoneId: 'UTC' });  // o aparelho em UTC: só o dia de Brasília vale
  await p.route(BASE + '/', async (r) => { const res = await r.fetch(); let html = await res.text(); html = html.replace(/<section class="painel-robo"[\s\S]*?<\/section>/, '').replace('</body>', painelHtml + '</body>'); await r.fulfill({ response: res, body: html }); });
  await p.clock.install({ time: new Date(relogio) });
  await p.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await p.waitForSelector('.painel-robo');
  await p.clock.runFor(200);
  const t = (await p.textContent('.painel-robo [data-robo-titulo]')).trim();
  const rod = (await p.textContent('.painel-robo .rodape-robo')).replace(/\s+/g, ' ').trim();
  ok(t === titulo, `E1.2 ${rotulo}: título "${t}"`);
  ok(rod.includes(`Nenhuma mudança nos editais ${quando}`) && rod.includes(`próxima leitura ${prox} às 06h17`), `E1.2 ${rotulo}: rodapé "${rod}"`);
  ok(erros.length === 0, 'E1.2: console limpo ' + erros.join('|'));
  await ctx.close();
}

// ---- E1.4, E1.5, E1.6: celular 375 x 812 (Andradina, 7º período)
for (const [larg, alt] of [[375, 812], [390, 844], [320, 640]]) {
  const { ctx, p, erros } = await nova({ viewport: { width: larg, height: alt }, isMobile: true, hasTouch: true });
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  await escolher(p);
  await p.tap('label.rp-pilula:has(input[value="7"])');
  await p.waitForTimeout(1400);  // a rolagem suave termina
  const pil = await p.$eval('.rp-pilulas', (c) => ({ sw: c.scrollWidth, cw: c.clientWidth, n: c.children.length, ov: getComputedStyle(c).overflowX }));
  ok(pil.n === 12 && pil.sw <= pil.cw + 1, `E1.6 ${larg}px: 12 pílulas sem rolagem lateral (${pil.sw} ≤ ${pil.cw}, overflow ${pil.ov})`);
  const cx = await caixa(p, '.rp-pilulas');
  const alvos = await p.$$eval('.rp-pilula span', (l) => l.map((e) => { const r = e.getBoundingClientRect(); return [r.left, r.right, r.width, r.height]; }));
  ok(alvos.every((a) => a[0] >= cx.l - 0.5 && a[1] <= cx.r + 0.5), `E1.6 ${larg}px: nenhuma pílula cortada nas bordas`);
  ok(alvos.every((a) => a[3] >= 44 && a[2] >= 44), `E1.6 ${larg}px: alvo de toque ≥ 44 px de altura (largura mín. ${Math.min(...alvos.map((a) => a[2])).toFixed(0)})`);
  if (larg === 375 || larg === 390) {
    const [n, km, mapa] = [await caixa(p, '#rp-n'), await caixa(p, '#rp-km'), await caixa(p, '.r3-svg')];
    ok(n.t >= 0 && km.b <= alt && mapa.t >= 0 && mapa.b <= alt, `E1.4 ${larg}x${alt}: número grande (${n.t | 0}), controle (${km.b | 0}) e mapa (${mapa.t | 0}–${mapa.b | 0}) dentro da janela`);
  }
  const lista = await p.evaluate(() => { const s = document.querySelector('.lista-radar'); const v = (e) => !!e && e.getClientRects().length > 0 && getComputedStyle(e).visibility !== 'hidden';
    return { ul: v(s.querySelector('.lista3')), titulo: v(s.querySelector('.secao-topo')), link: v([...s.querySelectorAll('a.botao')].find((a) => /Ver os \d+ editais abertos/.test(a.textContent))) }; });
  ok(!lista.ul && !lista.titulo && lista.link, `E1.5 ${larg}px: com o radar ativo a seção de baixo vira só o link "Ver os N editais abertos" (${JSON.stringify(lista)})`);
  ok(erros.length === 0, 'console limpo ' + erros.join('|'));
  await ctx.close();
}
{ // sair do radar pessoal devolve a lista; sem cidade a lista está lá desde o início
  const { ctx, p } = await nova({ viewport: { width: 375, height: 812 } });
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  ok(await p.$eval('.lista-radar .lista3', (e) => e.getClientRects().length > 0), 'E1.5: sem radar pessoal a lista de faculdades continua na home');
  await escolher(p);
  await p.click('#r3-completo');
  ok(await p.$eval('.lista-radar .lista3', (e) => e.getClientRects().length > 0), 'E1.5: "Ver o mapa completo" devolve a lista');
  await ctx.close();
}

// ---- E1.7 campi agrupados (São Paulo, qualquer distância: várias faculdades com mais de um campus)
{
  const { ctx, p } = await nova({ viewport: { width: 375, height: 900 }, isMobile: true, hasTouch: true });
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  await escolher(p, 'São Paulo');
  await p.evaluate(() => { const k = document.querySelector('#rp-km'); k.value = k.max; k.dispatchEvent(new Event('input', { bubbles: true })); k.dispatchEvent(new Event('change', { bubbles: true })); });
  await p.waitForTimeout(400);
  const nEditais = Number(await p.textContent('#rp-n'));
  if ((await p.$$('#rp-mais')).length && (await p.isVisible('#rp-mais'))) await p.click('#rp-mais');
  const info = await p.evaluate(() => {
    const linhas = [...document.querySelectorAll('#rp-top > li, #rp-todos > li')];
    return {
      linhas: linhas.map((li) => ({ grupo: li.classList.contains('rp-grupo'), nome: li.querySelector('.rp-nome b').textContent, sub: li.querySelector('.rp-nome small').textContent, q: li.querySelector('.rp-q').textContent,
        campi: li.classList.contains('rp-grupo') ? li.querySelectorAll('.rp-campi a').length : 1 })),
    };
  });
  const grupos = info.linhas.filter((l) => l.grupo);
  ok(grupos.length >= 1, `E1.7: há faculdade com mais de um campus agrupada (${grupos.map((g) => `${g.nome} · ${g.sub} · ${g.q}`).join('; ')})`);
  ok(grupos.every((g) => /^\d+ (campi|editais)$/.test(g.sub) && /^(fecha|aberto)/.test(g.q) && g.campi >= 2), 'E1.7: cada grupo diz "N campi" e quando fecha o primeiro');
  ok(info.linhas.reduce((t, l) => t + l.campi, 0) === nEditais, `E1.7: a soma dos campi das linhas (${info.linhas.reduce((t, l) => t + l.campi, 0)}) = o número grande (${nEditais})`);
  if (grupos.length) {
    const g = await p.$('.rp-grupo > button');
    ok((await g.getAttribute('aria-expanded')) === 'false' && await p.$eval('.rp-grupo .rp-campi', (e) => e.hidden), 'E1.7: o grupo começa fechado');
    await g.scrollIntoViewIfNeeded(); await g.click();
    ok((await g.getAttribute('aria-expanded')) === 'true' && await p.$eval('.rp-grupo .rp-campi', (e) => !e.hidden && e.querySelectorAll('a').length >= 2), 'E1.7: tocar na linha abre os campi, cada um com o seu link');
    const alto = await g.evaluate((e) => e.getBoundingClientRect().height);
    ok(alto >= 44, `E1.7: a linha do grupo tem alvo ≥ 44 px (${alto | 0})`);
  }
  await ctx.close();
}

await b.close();
console.log(falhas.length ? `\n${falhas.length} FALHA(S)` : '\nTUDO CERTO');
process.exit(falhas.length ? 1 : 0);
