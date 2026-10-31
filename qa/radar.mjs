// Radar da home (v3), em computador, Android, iPhone e no navegador do Instagram:
// - tocar num ponto abre o cartão (computador) ou a gaveta (celular), com faculdade, situação, "Ver edital" e "Me avise";
//   tocar num grupo lista as faculdades; Esc fecha e devolve o foco;
// - cada chip muda o mapa e a lista juntos (mesmas faculdades, mesma contagem no texto);
// - a contagem dos estados no navegador é a mesma do HTML gerado da base;
// - todo ponto e grupo tem alvo de toque de pelo menos 44 px;
// - o aviso de nova versão fica no cabeçalho, sem cobrir nada e sem empurrar o menu para outra linha (320 a 1440 px);
// - com prefers-reduced-motion, nada se mexe e tudo aparece pronto;
// - no celular em 4G: CLS 0 e LCP abaixo de 2,5 s.
// uso: (site servido em http://127.0.0.1:8765, ou BASE=<site no ar>)  node radar.mjs
import { chromium, webkit, devices } from 'playwright';

const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const INSTAGRAM = 'Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/126.0.0.0 Mobile Safari/537.36 Instagram 340.0.0.0.0 Android';
const falhas = [];
const conferir = (ok, txt) => { console.log(ok ? 'ok   ' : 'FALHA', txt); if (!ok) falhas.push(txt); };
const cr = await chromium.launch(), wk = await webkit.launch();
const AMBIENTES = [
  ['computador', cr, { viewport: { width: 1280, height: 900 } }],
  ['android', cr, { ...devices['Pixel 7'] }],
  ['iphone', wk, { ...devices['iPhone 13'] }],
  ['instagram', cr, { ...devices['Pixel 7'], userAgent: INSTAGRAM }],
];
const semAbertura = () => { try { sessionStorage.setItem('tm_abertura', '1'); } catch (e) {} };

for (const [amb, nav, op] of AMBIENTES) {
  const c = await nav.newContext({ ...op, colorScheme: 'dark' });
  await c.addInitScript(semAbertura);
  // medição ligada, com o banco simulado: os toques do teste não entram na contagem real
  const medidos = [];
  await c.addInitScript(() => { window.TM_MEDIR_TESTE = true; });
  await c.route(/\/rest\/v1\/rpc\/medir/, (r) => { try { medidos.push(JSON.parse(r.request().postData()).p_nome); } catch (e) {} r.fulfill({ status: 204, body: '' }); });
  const p = await c.newPage();
  const erros = [];
  p.on('pageerror', (e) => erros.push(e.message));
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  const estatico = await p.evaluate(async (base) => {  // HTML como veio do gerador, antes do JavaScript
    const html = await (await fetch(base + '/')).text();
    return [...html.matchAll(/data-uf="(\w\w)"[^>]*>\w\w · <b>(\d+)<\/b>/g)].map((m) => [m[1], m[2]]);
  }, BASE);

  // estados: o navegador recalcula e chega ao mesmo número da base
  const vivos = await p.$$eval('.r3-estados [data-uf]', (bs) => bs.map((b) => [b.dataset.uf, b.querySelector('b').textContent]));
  conferir(estatico.length >= 5 && JSON.stringify(vivos) === JSON.stringify(estatico), `${amb}: contagem dos estados igual à base (${vivos.map((x) => x.join(' ')).join(', ')})`);

  // chips: mapa e lista juntos
  for (const chip of await p.$$eval('.chip', (bs) => bs.map((b) => b.dataset.filtro))) {
    await p.click(`.chip[data-filtro="${chip}"]`);
    const r = await p.evaluate(() => {
      const noMapa = [...document.querySelectorAll('.r3-pontos .pt')].reduce((s, a) => s + (a._g ? a._g.itens.length : 1), 0);
      const naLista = document.querySelectorAll('#lista3 li:not(.vazio)').length;
      const abertasMapa = [...document.querySelectorAll('.r3-pontos .pt')].flatMap((a) => a._g.itens).filter((x) => x.st === 'aberto' || x.st === 'encerra').length;
      return { noMapa, naLista, abertasMapa, resumo: document.querySelector('#r3-resumo').textContent, titulo: document.querySelector('#t-lista').textContent,
               pressed: document.querySelector('.chip[aria-pressed="true"]').dataset.filtro };
    });
    const n = Number(r.resumo.match(/\d+/)[0]);
    const numeroCerto = chip === 'publicas' ? n === r.noMapa : n === r.abertasMapa;
    conferir(r.pressed === chip && r.noMapa === r.naLista && r.resumo === r.titulo && numeroCerto,
      `${amb}: chip "${chip}" muda mapa (${r.noMapa}) e lista (${r.naLista}) juntos — "${r.resumo}"`);
  }
  await p.click('.chip[data-filtro="abertos"]');

  // alvos de 44 px
  const pequenos = await p.$$eval('.r3-pontos .pt .alvo', (cs) => cs.map((c) => c.getBoundingClientRect()).filter((b) => b.width < 43.5 || b.height < 43.5).length);
  conferir(pequenos === 0, `${amb}: todo ponto com alvo de toque de 44 px (${pequenos} menores)`);

  // tocar num ponto sozinho abre o cartão/gaveta
  await p.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; scrollTo(0, document.querySelector('.r3').getBoundingClientRect().top + scrollY - 10); });
  let ponto = p.locator('.r3-pontos .pt:not(.grupo)').first();
  if (!(await ponto.count())) { await p.click('.r3-estados [data-uf="SP"]'); ponto = p.locator('.r3-pontos .pt:not(.grupo)').first(); }
  const rotulo = await ponto.getAttribute('aria-label');
  await ponto.click();
  await p.waitForTimeout(350);
  const cartao = await p.evaluate(() => {
    const c = document.querySelector('#r3-cartao'), b = c.getBoundingClientRect();
    const est = document.querySelector('.r3-estados').getBoundingClientRect();
    return { visivel: !c.hidden && b.height > 50, titulo: c.querySelector('h3').textContent, botoes: [...c.querySelectorAll('.bts a')].map((a) => a.textContent),
             sit: c.querySelector('.sit') && c.querySelector('.sit').textContent, foco: document.activeElement === c.querySelector('h3'),
             fixo: getComputedStyle(c).position === 'fixed', cobreEstados: b.bottom > est.top + 1 && b.top < est.bottom - 1 && getComputedStyle(c).position !== 'fixed',
             dentroDaTela: b.left >= -1 && b.right <= innerWidth + 1 };
  });
  const sigla = rotulo.split(',')[0];
  conferir(cartao.visivel && cartao.titulo.includes(sigla) && cartao.botoes.length === 2 && /Me avise/.test(cartao.botoes[1]) && cartao.sit && cartao.foco,
    `${amb}: tocar em ${sigla} abre ${cartao.fixo ? 'a gaveta' : 'o cartão'} (${cartao.sit}; ${cartao.botoes.join(' / ')})`);
  conferir(cartao.fixo === (amb !== 'computador'), `${amb}: ${amb === 'computador' ? 'cartão ao lado do ponto' : 'gaveta que sobe de baixo'}`);
  conferir(!cartao.cobreEstados && cartao.dentroDaTela, `${amb}: o cartão não cobre os botões dos estados e não sai da tela`);
  await p.keyboard.press('Escape');
  await p.waitForTimeout(100);
  const fechou = await p.evaluate(() => document.querySelector('#r3-cartao').hidden && document.activeElement.classList.contains('pt'));
  conferir(fechou, `${amb}: Esc fecha e devolve o foco ao ponto`);

  // grupo: lista as faculdades e abre cada uma
  await p.click('.r3-estados [data-vista="0 0 400 400"]');
  const grupo = p.locator('.r3-pontos .pt.grupo').first();
  if (await grupo.count()) {
    const n = Number(await grupo.locator('text').textContent());
    await grupo.click(); await p.waitForTimeout(300);
    const itens = await p.locator('#r3-cartao li button').count();
    await p.locator('#r3-cartao li button').first().click(); await p.waitForTimeout(200);
    const abriu = await p.locator('#r3-cartao .bts a').count();
    conferir(itens === n && abriu === 2, `${amb}: tocar no grupo lista as ${n} faculdades e cada uma abre o cartão`);
    await p.keyboard.press('Escape');
  } else conferir(true, `${amb}: sem grupos nesta largura`);

  // estado: botão aproxima o mapa e separa os pontos
  await p.click('.r3-estados [data-uf="SP"]');
  const vb = await p.$eval('.r3-svg', (s) => s.getAttribute('viewBox'));
  conferir(vb !== '0 0 400 400' && await p.$eval('.r3-estados [data-uf="SP"]', (b) => b.getAttribute('aria-pressed')) === 'true', `${amb}: botão SP aproxima o mapa`);

  // quadros: filtram o radar e mostram "Continuar o diagnóstico"
  await p.click('.quadro[data-origem="exterior"]');
  const q = await p.evaluate(() => ({ filtro: document.querySelector('.chip[aria-pressed="true"]').dataset.filtro, seguir: !document.querySelector('.seguir').hidden,
                                       href: document.querySelector('.seguir a').getAttribute('href'), url: location.pathname }));
  conferir(q.filtro === 'exterior' && q.seguir && q.href === 'diagnostico/?origem=exterior' && q.url === '/', `${amb}: "Estudo fora do Brasil" filtra o radar e prepara o diagnóstico`);
  await p.click('.seguir a');
  await p.waitForURL(/diagnostico/);
  const resp = await p.$eval('input[name="origem"][value="exterior"]', (i) => i.checked);
  conferir(resp, `${amb}: o diagnóstico abre com "exterior" respondido`);
  const faltam = ['radar_chip_semana', 'radar_chip_exterior', 'radar_ponto', 'radar_grupo', 'radar_estado', 'porta_exterior'].filter((n) => !medidos.includes(n));
  conferir(!faltam.length, `${amb}: cada toque mede o evento certo${faltam.length ? ' — faltam ' + faltam.join(', ') : ''}`);
  conferir(!erros.length, `${amb}: sem erros de JavaScript${erros.length ? ' — ' + erros.join(' | ') : ''}`);
  await c.close();
}

// aviso de nova versão: no cabeçalho, sem empurrar o menu nem cobrir nada
for (const w of [320, 360, 390, 430, 768, 1024, 1280, 1440]) {
  const c = await cr.newContext({ viewport: { width: w, height: 800 }, isMobile: w < 768, hasTouch: w < 768 });
  await c.route(/\/rest\/v1\/rpc\/medir/, (r) => r.fulfill({ status: 204, body: '' }));
  await c.addInitScript(semAbertura);
  const p = await c.newPage();
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  const antes = await p.$eval('.topo > .wrap', (t) => t.offsetHeight);
  await p.evaluate(() => window.TM_avisoNovaVersao());
  const r = await p.evaluate(() => {
    const topo = document.querySelector('.topo > .wrap'), av = document.querySelector('.nova-versao'), a = av.getBoundingClientRect();
    const outros = [...topo.querySelectorAll('a, button')].filter((el) => el !== av && el.offsetParent && el.getBoundingClientRect().width > 0)
      .filter((el) => { const b = el.getBoundingClientRect(); return a.left < b.right - .5 && b.left < a.right - .5 && a.top < b.bottom - .5 && b.top < a.bottom - .5; });
    return { altura: topo.offsetHeight, nome: av.getAttribute('aria-label'), sobrepoe: outros.map((o) => o.className || o.textContent),
             dentro: a.left >= 0 && a.right <= innerWidth, icone: av.classList.contains('so-icone') };
  });
  conferir(r.altura <= antes + 1 && !r.sobrepoe.length && r.dentro && r.nome === 'Nova versão disponível, atualizar',
    `${w}px: aviso no cabeçalho ${r.icone ? '(só ícone)' : '(com texto)'} sem empurrar o menu (${antes}→${r.altura}px)${r.sobrepoe.length ? ' cobre ' + r.sobrepoe : ''}`);
  await c.close();
}

// sem movimento: tudo pronto, nada animando
{
  const c = await cr.newContext({ ...devices['Pixel 7'], reducedMotion: 'reduce' });
  await c.route(/\/rest\/v1\/rpc\/medir/, (r) => r.fulfill({ status: 204, body: '' }));
  const p = await c.newPage();
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  await p.waitForTimeout(300);
  const r = await p.evaluate(() => ({ anims: document.getAnimations().filter((a) => a.playState === 'running').length,
                                      varrendo: document.querySelector('.r3-varrendo').hidden, numero: document.querySelector('#n-abertos').textContent,
                                      pontos: [...document.querySelectorAll('.r3-pontos .pt')].every((a) => getComputedStyle(a).opacity === '1') }));
  conferir(r.anims === 0 && r.varrendo && r.pontos && Number(r.numero) > 0, `sem movimento: nada animando (${r.anims}), pontos e números prontos (${r.numero} abertos)`);
  await c.close();
}

// desempenho no celular em 4G (abertura ligada, primeira visita)
{
  const c = await cr.newContext({ ...devices['Pixel 7'] });
  await c.route(/\/rest\/v1\/rpc\/medir/, (r) => r.fulfill({ status: 204, body: '' }));
  const p = await c.newPage();
  const cdp = await c.newCDPSession(p);
  await cdp.send('Network.enable');
  await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 150, downloadThroughput: 9 * 1024 * 1024 / 8, uploadThroughput: 3 * 1024 * 1024 / 8 });
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
  await p.addInitScript(() => {
    window.__cls = 0; window.__lcp = 0;
    new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; }).observe({ type: 'layout-shift', buffered: true });
    new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lcp = e.startTime; }).observe({ type: 'largest-contentful-paint', buffered: true });
  });
  await p.goto(BASE + '/', { waitUntil: 'load' });
  await p.waitForTimeout(3500);
  const r = await p.evaluate(() => ({ cls: window.__cls, lcp: window.__lcp }));
  conferir(r.cls === 0, `celular 4G: CLS ${r.cls.toFixed(4)}`);
  conferir(r.lcp > 0 && r.lcp < 2500, `celular 4G: LCP ${Math.round(r.lcp)} ms`);
  await c.close();
}

await cr.close(); await wk.close();
console.log(falhas.length ? `${falhas.length} falha(s)` : 'ok: radar da home');
process.exit(falhas.length ? 1 : 0);
