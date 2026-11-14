// Parte E (14/11/2026): revisão profunda do radar pessoal. Cada verificação reprova o site antigo (rode com BASE=https://www.transfermed.com.br antes da publicação).
// E1.1 radar parado em "reduzir movimento"; E1.2 painel "O robô hoje" depois da meia-noite (dia de Brasília); E1.4 mapa dentro da janela do celular;
// E1.5 resultado sem repetir; E1.6 pílulas em grade; E1.7 campi agrupados; E1.8 (choque) está em meu_plano.mjs; E3.x mais abaixo.
// uso: (site em http://127.0.0.1:8765, ou BASE=<site no ar>)  node parte_e.mjs
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync } from 'node:fs';

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
  // invariante que vale com qualquer dado do dia: uma faculdade (nome antes do " – Campus") nunca aparece em duas linhas
  const dispersas = await p.evaluate(() => {
    const base = (f) => String(f.nome || f.sigla).split(' – ')[0].trim(), onde = {};
    document.querySelectorAll('#rp-top > li, #rp-todos > li').forEach((li, i) => li.querySelectorAll('a').forEach((a) => {
      const ed = window.TM.editais.find((e) => a.getAttribute('href').includes('/' + e.slug + '/')), b = base(window.TM.faculdades[ed.fid]);
      (onde[b] = onde[b] || new Set()).add(i);
    }));
    return Object.entries(onde).filter(([, v]) => v.size > 1).map(([k]) => k);
  });
  ok(dispersas.length === 0, `E1.7: nenhuma faculdade aparece em duas linhas (${dispersas.join(', ') || 'ok'})`);
  if (!grupos.length) console.log('   (nenhuma faculdade com 2+ campi abertos hoje: o agrupamento visual não pôde ser exercitado com o dado real)');
  else ok(true, `E1.7: faculdades com mais de um campus agrupadas (${grupos.map((g) => `${g.nome} · ${g.sub} · ${g.q}`).join('; ')})`);
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

// ---- E2 menos ruído: um painel do robô, faixa sob a pergunta, sem "Prazo mais próximo" com o radar ativo
for (const [amb, op] of [['celular 375', { viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true }], ['computador 1440', { viewport: { width: 1440, height: 900 } }]]) {
  const { ctx, p } = await nova(op);
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  const antes = await p.evaluate(() => ({
    selo: !!document.querySelector('.rp-selo'), vivo: !!document.querySelector('#r3-vivo'), textoAoVivo: /ao vivo/i.test(document.querySelector('.heroi').textContent),
    paineis: document.querySelectorAll('.painel-robo').length, ticker: !!document.querySelector('#prazos') && document.querySelector('#prazos').getClientRects().length > 0,
    ordem: (() => { const q = document.querySelector('.rp-pergunta').getBoundingClientRect().top, f = document.querySelector('#rp-robo').getBoundingClientRect(); return [q, f.top, f.height]; })() }));
  ok(!antes.selo && !antes.vivo && !antes.textoAoVivo, `E2 ${amb}: sem selo "Radar ao vivo" nem "Ao vivo" no mapa (nada no herói diz "ao vivo")`);
  ok(antes.paineis <= 1, `E2 ${amb}: no máximo um painel do robô (${antes.paineis})`);
  ok(antes.ordem[1] > antes.ordem[0] && antes.ordem[1] - antes.ordem[0] < 200, `E2 ${amb}: a faixa do robô fica logo abaixo da pergunta (${antes.ordem[1] - antes.ordem[0] | 0} px)`);
  ok(antes.ticker, `E2 ${amb}: sem cidade, o "Prazo mais próximo" continua na home`);
  await escolher(p);
  await p.waitForTimeout(900);
  if (await p.$('#prazos')) ok(!(await p.$eval('#prazos', (e) => e.getClientRects().length > 0)), `E2 ${amb}: com o radar pessoal ativo o "Prazo mais próximo" sai da home`);
  if (larg_cel(op)) ok(!(await p.$eval('#rp-robo', (e) => e.getClientRects().length > 0)), `E2 ${amb}: escolhida a cidade, a faixa dá lugar ao mapa`);
  await p.click('#rp-trocar');
  if (await p.$('#prazos')) ok(await p.$eval('#prazos', (e) => e.getClientRects().length > 0), `E2 ${amb}: "Trocar cidade" devolve o "Prazo mais próximo"`);
  await ctx.close();
}
function larg_cel(op) { return op.viewport.width < 861; }

// ---- E3.1 "por que entrou": chips de período e distância em linha reta
{
  const { ctx, p } = await nova({ viewport: { width: 375, height: 900 }, isMobile: true, hasTouch: true });
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  await escolher(p, 'São Paulo');
  await p.evaluate(() => { const k = document.querySelector('#rp-km'); k.value = k.max; k.dispatchEvent(new Event('input', { bubbles: true })); k.dispatchEvent(new Event('change', { bubbles: true })); });
  await p.waitForTimeout(500);
  const semPeriodo = await p.$$eval('#rp-top .rp-porque em, #rp-todos .rp-porque em', (l) => l.map((e) => e.textContent));
  ok(semPeriodo.length > 0 && semPeriodo.every((t) => /^(≈ [\d.]+ km|< 10 km)$/.test(t)), `E3.1: sem período só a distância (${semPeriodo.slice(0, 3).join(' | ')})`);
  await p.tap('label.rp-pilula:has(input[value="4"])');
  const chips = await p.$$eval('#rp-top > li, #rp-todos > li', (l) => l.map((li) => [...li.querySelectorAll('.rp-porque')].map((c) => [...c.querySelectorAll('em')].map((e) => e.textContent))));
  const flat = chips.flat();
  ok(flat.length > 0 && flat.every((c) => c.includes('aceita 4º') && c.some((t) => /^≈ [\d.]+ km$|^< 10 km$/.test(t))), `E3.1: cada linha diz "aceita 4º" e "≈ N km" (${JSON.stringify(flat.slice(0, 2))})`);
  ok(flat.flat().filter((t) => t.startsWith('≈')).every((t) => Number(t.replace(/\D/g, '')) % 10 === 0), 'E3.1: a distância sai arredondada de 10 em 10 km');
  // a distância mostrada confere com a conta (linha reta, Andradina → faculdade)
  const conf = await p.evaluate(() => {
    const rad = (x) => x * Math.PI / 180, R = 6371, a = [-23.5505, -46.6333];
    const li = document.querySelector('#rp-top > li:not(.rp-grupo)'); if (!li) return null;
    const href = li.querySelector('a').getAttribute('href');
    const ed = window.TM.editais.find((e) => href.includes('/' + e.slug + '/')), f = window.TM.faculdades[ed.fid];
    const h = Math.sin(rad(f.lat - a[0]) / 2) ** 2 + Math.cos(rad(a[0])) * Math.cos(rad(f.lat)) * Math.sin(rad(f.lon - a[1]) / 2) ** 2;
    return { real: Math.round(2 * R * Math.asin(Math.sqrt(h)) / 10) * 10, mostrado: li.querySelector('.rp-porque em:last-child').textContent };
  });
  if (conf) ok(Number(conf.mostrado.replace(/\D/g, '')) === conf.real || (conf.real < 10 && conf.mostrado === '< 10 km'), `E3.1: a distância mostrada (${conf.mostrado}) é a da conta (${conf.real} km)`);
  await p.tap('#rp-que');
  const que = await p.textContent('#rp-que-txt');
  ok(await p.isVisible('#rp-que-txt') && /linha reta/.test(que) && (await p.getAttribute('#rp-que', 'aria-expanded')) === 'true', 'E3.1: "O que são esses rótulos?" explica a linha reta');
  await ctx.close();
}

async function semRolagem(p) { return p.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth); }

// ---- E3.2 mandar meu radar: o link reabre o mesmo radar
{
  const { ctx, p, erros } = await nova({ viewport: { width: 1440, height: 900 }, permissions: ['clipboard-read', 'clipboard-write'] });
  const medidos = [];
  await ctx.addInitScript(() => { window.TM_MEDIR_TESTE = true; });
  await ctx.route(/\/rest\/v1\/rpc\/medir/, async (r) => { try { medidos.push(JSON.parse(r.request().postData()).p_nome); } catch (e) {} await r.fulfill({ status: 200, contentType: 'application/json', body: 'null' }); });
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  await escolher(p);
  await p.click('label.rp-pilula:has(input[value="7"])');
  await p.waitForTimeout(800);  // a contagem do número grande dura 0,4 s
  const nOriginal = Number(await p.textContent('#rp-n'));
  await p.click('#rp-mandar');
  await p.waitForFunction(() => document.querySelector('#rp-msg').textContent.length > 0);
  const link = await p.evaluate(() => navigator.clipboard.readText());
  ok(new URL(link).search === '?de=andradina-sp&p=7&km=400&origem=compartilhar', `E3.2 computador: o botão copia o link (${link})`);
  ok(/Link copiado/.test(await p.textContent('#rp-msg')), 'E3.2: avisa "Link copiado"');
  ok(medidos.includes('radar_compartilhar'), 'E3.2: mede radar_compartilhar (só contagem)');
  ok(erros.length === 0, 'E3.2: console limpo ' + erros.join('|'));
  await ctx.close();
  // abrir o link num aparelho limpo, e sobre um radar já salvo de outra cidade
  for (const [rotulo, antes] of [['aparelho limpo', null], ['com outro radar salvo', { cidade: 'Salvador - BA', nome: 'Salvador', coords: [-12.9714, -38.5014], semestre: 3, raio: 1000 }]]) {
    const o = await nova({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true });
    if (antes) await o.ctx.addInitScript((v) => { try { localStorage.setItem('tm_radar', JSON.stringify(v)); } catch (e) {} }, antes);
    await o.p.goto(link.replace(/^https?:\/\/[^/]+/, BASE), { waitUntil: 'networkidle' });
    await o.p.waitForSelector('#rp-cont:not([hidden])');
    await o.p.waitForTimeout(500);
    const est = await o.p.evaluate(() => ({
      n: Number(document.querySelector('#rp-n').textContent), onde: document.querySelector('#rp-onde').textContent,
      periodo: (document.querySelector('input[name="rp-periodo"]:checked') || {}).value, km: document.querySelector('#rp-km').value,
      guardado: localStorage.getItem('tm_radar'), carrossel: !!document.querySelector('#prazos') && document.querySelector('#prazos').getClientRects().length > 0 }));
    ok(est.n === nOriginal && /Andradina/.test(est.onde) && est.periodo === '7' && est.km === '400', `E3.2 ${rotulo}: o link abre o mesmo radar (${est.n} editais, ${est.onde.trim()})`);
    ok(antes ? est.guardado === JSON.stringify(antes) : est.guardado === null, `E3.2 ${rotulo}: abrir o link não grava nada no aparelho até a pessoa mexer`);
    ok(!est.carrossel, `E3.2 ${rotulo}: com o radar do link ativo, o "Prazo mais próximo" não aparece`);
    ok(await semRolagem(o.p), `E3.2 ${rotulo}: sem rolagem lateral`);
    await o.p.click('label.rp-pilula:has(input[value="8"])');
    ok(JSON.parse(await o.p.evaluate(() => localStorage.getItem('tm_radar'))).nome === 'Andradina', `E3.2 ${rotulo}: ao mexer num controle o radar passa a ficar salvo`);
    ok(o.erros.length === 0, 'E3.2: console limpo ' + o.erros.join('|'));
    await o.ctx.close();
  }
  // link inválido ou de cidade desconhecida: a home abre normal
  for (const ruim of ['?de=nao-existe-zz&p=7&km=400', '?de=%3Cscript%3E&p=99&km=abc', '?de=andradina-sp&p=99&km=5']) {
    const o = await nova({ viewport: { width: 375, height: 812 } });
    await o.p.goto(BASE + '/' + ruim, { waitUntil: 'networkidle' });
    await o.p.waitForTimeout(500);
    const est = await o.p.evaluate(() => ({ cont: !document.querySelector('#rp-cont').hidden, salvo: document.documentElement.classList.contains('rp-salvo'),
      periodo: (document.querySelector('input[name="rp-periodo"]:checked') || {}).value || '', km: document.querySelector('#rp-km').value }));
    if (ruim.includes('andradina')) ok(est.cont && est.periodo === '' && est.km === '400', `E3.2 ${ruim}: período e distância inválidos caem no padrão (sem período, 400 km) (${est.periodo || 'sem período'}, ${est.km} km)`);
    else ok(!est.cont && !est.salvo, `E3.2 ${ruim}: link inválido, home normal e sem espaço reservado`);
    ok(o.erros.length === 0, 'console limpo ' + o.erros.join('|'));
    await o.ctx.close();
  }
  // celular com Web Share: o botão chama navigator.share com o link
  const m = await nova({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  await m.ctx.addInitScript(() => { window.__compartilhou = null; navigator.share = async (d) => { window.__compartilhou = d; }; });
  await m.p.goto(BASE + '/', { waitUntil: 'networkidle' });
  await escolher(m.p);
  await m.p.tap('label.rp-pilula:has(input[value="7"])');
  await m.p.tap('#rp-mandar');
  const d = await m.p.evaluate(() => window.__compartilhou);
  ok(d && /\?de=andradina-sp&p=7&km=400&origem=compartilhar$/.test(d.url) && /Andradina/.test(d.text), `E3.2 celular: usa a folha de compartilhar do aparelho (${d && d.url})`);
  await m.ctx.close();
}

// ---- E3.3 cartão para o story
{
  const { ctx, p, erros } = await nova({ viewport: { width: 1280, height: 900 }, acceptDownloads: true });
  await ctx.addInitScript(() => { window.__textos = []; const f = CanvasRenderingContext2D.prototype.fillText; CanvasRenderingContext2D.prototype.fillText = function (t, ...r) { window.__textos.push(String(t)); return f.call(this, t, ...r); }; });
  const medidos = [];
  await ctx.addInitScript(() => { window.TM_MEDIR_TESTE = true; });
  await ctx.route(/\/rest\/v1\/rpc\/medir/, async (r) => { try { medidos.push(JSON.parse(r.request().postData()).p_nome); } catch (e) {} await r.fulfill({ status: 200, contentType: 'application/json', body: 'null' }); });
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  await escolher(p);
  await p.click('label.rp-pilula:has(input[value="7"])');
  await p.waitForTimeout(800);
  const nEd = Number(await p.textContent('#rp-n'));
  const [dl] = await Promise.all([p.waitForEvent('download'), p.click('#rp-baixar')]);
  mkdirSync('relatorios', { recursive: true });
  const arq = 'relatorios/meu-radar.png';
  await dl.saveAs(arq);
  const png = readFileSync(arq);
  ok(png.subarray(1, 4).toString() === 'PNG' && png.readUInt32BE(16) === 1080 && png.readUInt32BE(20) === 1920, `E3.3: baixa um PNG 1080×1920 (${png.readUInt32BE(16)}×${png.readUInt32BE(20)}, ${dl.suggestedFilename()})`);
  const textos = await p.evaluate(() => window.__textos);
  const cima3 = await p.$$eval('#rp-top > li .rp-nome b', (l) => l.map((x) => x.textContent));
  ok(textos.includes('Saindo de Andradina') && textos.includes('7º período · até 400 km'), `E3.3: "Saindo de Andradina · 7º período" (${textos.filter((t) => /Saindo|período/.test(t)).join(' / ')})`);
  ok(textos.includes(String(nEd)), `E3.3: o número grande (${nEd}) é o do radar`);
  ok(cima3.every((n) => textos.includes(n)), `E3.3: os 3 primeiros (nome e prazo): ${cima3.join(', ')}`);
  ok(textos.includes('transfermed.com.br') && textos.includes('Confira sempre o edital oficial.'), 'E3.3: rodapé "transfermed.com.br" e "Confira sempre o edital oficial."');
  const hojeBR = new Date().toLocaleDateString('pt-BR', { timeZone: 'America/Sao_Paulo' });
  ok(textos.some((t) => t.includes(hojeBR)), `E3.3: a data do dia (${hojeBR}) está no cartão`);
  ok(!textos.some((t) => /@|\d{4,5}-?\d{4}|ranking|melhor/i.test(t)), 'E3.3: nenhum dado pessoal, contato ou ranking no cartão');
  ok(medidos.includes('radar_story'), 'E3.3: mede radar_story (só contagem)');
  ok(erros.length === 0, 'E3.3: console limpo ' + erros.join('|'));
  await ctx.close();
}

await b.close();
console.log(falhas.length ? `\n${falhas.length} FALHA(S)` : '\nTUDO CERTO');
process.exit(falhas.length ? 1 : 0);
