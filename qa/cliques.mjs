// Auditoria de cliques: todo elemento clicável das páginas principais tem de produzir um efeito visível (navegar,
// abrir aba, baixar, mudar a página, rolar, mover o foco, mostrar validação) nos 4 ambientes: computador (Chromium),
// Android (Chromium), iPhone (WebKit) e navegador do Instagram no iPhone (WebKit). Links do próprio site: status HTTP
// conferido (sem 404). O banco (Supabase) é simulado: nenhum envio real sai daqui.
// uso: (site servido em http://127.0.0.1:8765, ou BASE=<site no ar>)  node cliques.mjs   → relatorios/cliques.json
import { chromium, webkit, devices } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';

const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const IG = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 300.0.0.0';
const AMBIENTES = [
  ['computador', chromium, { viewport: { width: 1280, height: 900 } }],
  ['android', chromium, { ...devices['Pixel 7'] }],
  ['iphone', webkit, { ...devices['iPhone 13'] }],
  ['instagram', webkit, { ...devices['iPhone 13'], userAgent: IG }],
];
const SELETOR = 'a[href], button, summary, [role="button"], input[type="checkbox"], input[type="radio"], input[type="submit"]';

// efeitos observados dentro da página (montado antes de qualquer script do site)
const SONDA = () => {
  window.__ef = { mut: 0, ev: 0 };
  const ligar = () => new MutationObserver((l) => { window.__ef.mut += l.length; })
    .observe(document.documentElement, { subtree: true, childList: true, attributes: true, characterData: true });
  if (document.documentElement) ligar(); else document.addEventListener('DOMContentLoaded', ligar);
  for (const t of ['input', 'change', 'toggle', 'copy', 'hashchange', 'scroll', 'invalid']) addEventListener(t, () => { window.__ef.ev++; }, true);
};

async function concluirDiagnostico(p) {
  await p.getByText('No Brasil', { exact: true }).click();
  for (let i = 0; i < 6 && await p.locator('#resultado').isHidden(); i++) {
    if (await p.locator('#semestre').isVisible()) await p.selectOption('#semestre', '3');
    await p.locator('#seguir').click(); await p.waitForTimeout(250);
  }
}

async function paginas(ctx) {
  // ficha de edital e de faculdade tiradas da lista de abertos (as que existem hoje)
  const p = await ctx.newPage();
  await p.goto(`${BASE}/editais/`, { waitUntil: 'domcontentloaded' });
  const edital = new URL(await p.locator('#abertos a[href*="/edital/"]').first().getAttribute('href'), p.url()).pathname;
  await p.goto(BASE + edital, { waitUntil: 'domcontentloaded' });
  const id = await p.$eval('[data-edital]', (el) => el.dataset.edital);
  const faculdade = new URL(await p.locator('a[href*="/faculdade/"]').first().getAttribute('href'), p.url()).pathname;
  await p.close();
  return [
    ['home', '/'], ['diagnóstico', '/diagnostico/'], ['resultado', '/diagnostico/', concluirDiagnostico],
    ['ficha de edital', edital], ['ficha de faculdade', faculdade], ['estado', '/estado/rj/'], ['exterior', '/exterior/'],
    ['editais', '/editais/'], ['minha lista', '/minha-lista/', null, id], ['sobre', '/sobre/'], ['contato', '/contato/'],
    ['privacidade', '/privacidade/'], ['alerta: confirmar', '/alerta/confirmar/?t=00000000-0000-4000-8000-000000000000'],
    ['alerta: descadastrar', '/alerta/descadastrar/?t=00000000-0000-4000-8000-000000000000'],
  ];
}

const statusCache = new Map();
async function status(ctx, url) {
  if (!statusCache.has(url)) {
    statusCache.set(url, ctx.request.get(url, { maxRedirects: 3, timeout: 20000 }).then((r) => r.status()).catch(() => 0));
  }
  return statusCache.get(url);
}

async function auditar([amb, motor, cfg]) {
  const nav = await motor.launch();
  const ctx = await nav.newContext({ ...cfg, ...(motor === chromium ? { permissions: ['clipboard-read', 'clipboard-write'] } : {}) });
  await ctx.addInitScript(SONDA);
  // banco simulado: inscrição, contato, medição e confirmação respondem como o Supabase
  await ctx.route(/\/(rest|functions)\/v1\//, (r) => r.fulfill({ status: 200, contentType: 'application/json', body: '{"ok":true}' }));
  const lista = await paginas(ctx);
  const linhas = [];
  for (const [nome, caminho, preparar, salvo] of lista) {
    const abrir = async () => {
      const p = await ctx.newPage();
      p.on('dialog', (d) => { p.__dialogo = true; d.dismiss().catch(() => {}); });
      p.on('download', () => { p.__download = true; });
      p.on('pageerror', (e) => linhas.push({ amb, pagina: nome, elemento: '(página)', problema: 'erro de JavaScript: ' + e.message }));
      // cada clique começa do zero: o que um clique anterior salvou (lista, perfil) mudaria a página e a posição dos
      // elementos; só a Minha lista começa com um edital salvo
      await p.addInitScript((id) => { try { localStorage.clear(); sessionStorage.clear(); if (id) localStorage.setItem('tm_marcados', JSON.stringify([id])); } catch (e) {} }, salvo || null);
      for (let t = 0; t < 3; t++) {  // servidor local é simples: uma nova tentativa se demorar
        try { await p.goto(BASE + caminho, { waitUntil: 'domcontentloaded', timeout: 30000 }); break; } catch (e) { if (t === 2) throw e; }
      }
      await p.waitForLoadState('load', { timeout: 8000 }).catch(() => {});
      if (preparar) await preparar(p);
      await p.waitForTimeout(300);
      return p;
    };
    let p = await abrir();
    // elementos visíveis, sem repetir o mesmo botão de cartões iguais (texto + classe + destino)
    const alvos = await p.$$eval(SELETOR, (els) => {
      const vistos = new Map(), out = [];
      els.forEach((el, i) => {
        const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
        if (!r.width || !r.height || cs.visibility === 'hidden' || el.closest('[hidden]')) return;
        if (el.checkVisibility && !el.checkVisibility({ visibilityProperty: true, opacityProperty: true })) return;
        if (el.classList.contains('pular')) { out.push({ i, tag: 'a', texto: 'Pular para o conteúdo', pular: true }); return; }
        const texto = (el.innerText || el.value || el.getAttribute('aria-label') || el.title || '').trim().replace(/\s+/g, ' ').slice(0, 70);
        const href = el.getAttribute('href');
        const chave = `${el.tagName}|${texto}|${el.className}|${href && href.replace(/\/edital\/[^/]+\//, '/edital/*/')}`;
        const n = (vistos.get(chave) || 0) + 1; vistos.set(chave, n);
        if (n > 2) return;
        out.push({ i, chave, n, tag: el.tagName.toLowerCase(), texto, href, alvo: el.getAttribute('target'), tipo: el.type || '',
                   js: !!(el.dataset.assinar || el.dataset.copiar || el.dataset.abrirBusca || el.dataset.baixarIcs) });
      });
      return out;
    });
    for (const a of alvos) {
      const rotulo = `${a.tag} "${a.texto || a.href || '?'}"`;
      const linha = { amb, pagina: nome, elemento: rotulo, problema: '' };
      // links comuns: destino conferido (sem 404) e protocolo que todo aparelho abre
      if (a.tag === 'a' && a.href && !a.href.startsWith('#') && !a.js) {
        const url = new URL(a.href, p.url());
        if (!/^(https?|mailto|tel|webcal):$/.test(url.protocol)) linha.problema = `protocolo ${url.protocol}`;
        else if (url.protocol === 'webcal:') linha.problema = 'link webcal:// sem o painel de opções (não abre no Windows/Android)';
        else if (url.origin === new URL(BASE).origin) {
          const s = await status(ctx, url.href.split('#')[0]);
          if (s >= 400 || s === 0) linha.problema = `destino responde ${s}`;
        }
        linha.efeito = linha.problema ? '' : (url.origin === new URL(BASE).origin ? 'navega' : 'abre site externo');
        linhas.push(linha);
        continue;
      }
      if (a.href && a.href.startsWith('webcal:') && /iphone|instagram/.test(amb)) { linha.efeito = 'webcal (app Calendário)'; linhas.push(linha); continue; }
      // link de pular: só aparece pelo teclado (Tab na página nova, Enter leva ao conteúdo)
      if (a.pular) {
        // no iPhone não há Tab (o link serve ao teclado); no resultado, o próprio diagnóstico deixou o foco no
        // formulário: o link é o mesmo da página do diagnóstico, testada logo antes
        if (/iphone|instagram/.test(amb) || preparar) {
          linha.efeito = preparar ? 'igual ao do diagnóstico' : 'não se aplica (sem teclado no iPhone)';
          linhas.push(linha);
          continue;
        }
        await p.close(); p = await abrir();
        await p.keyboard.press('Tab');
        const ok1 = await p.evaluate(() => !!document.activeElement && document.activeElement.classList.contains('pular')
          && document.activeElement.getBoundingClientRect().left >= 0);
        await p.keyboard.press('Enter'); await p.waitForTimeout(200);
        const ok2 = await p.evaluate(() => location.hash === '#conteudo');
        linha.efeito = ok1 && ok2 ? 'teclado: aparece no Tab e leva ao conteúdo' : '';
        if (!linha.efeito) linha.problema = ok1 ? 'Enter não leva ao conteúdo' : 'não aparece no primeiro Tab';
        linhas.push(linha);
        continue;
      }
      // clicáveis por script (botões, resumos, âncoras internas): clique de verdade numa página nova (nada aberto
      // por um clique anterior pode cobrir o próximo) e procura de efeito
      await p.close(); p = await abrir();
      // pela identidade (tag, texto, classe e destino), não pela posição: o radar da home agrupa pontos conforme a
      // largura, e a quantidade de elementos antes de um botão pode mudar de uma carga para outra
      const pos = await p.$$eval(SELETOR, (els, [chave, n]) => {
        let k = 0;
        return els.findIndex((el) => {
          const texto = (el.innerText || el.value || el.getAttribute('aria-label') || el.title || '').trim().replace(/\s+/g, ' ').slice(0, 70);
          const href = el.getAttribute('href');
          const c = `${el.tagName}|${texto}|${el.className}|${href && href.replace(/\/edital\/[^/]+\//, '/edital/*/')}`;
          return c === chave && ++k === n;
        });
      }, [a.chave, a.n]);
      const alvo = pos >= 0 ? (await p.$$(SELETOR))[pos] : (a.chave ? null : (await p.$$(SELETOR))[a.i]);
      if (!alvo) { linha.problema = 'sumiu ao recarregar'; linhas.push(linha); continue; }
      const antes = await p.evaluate(() => ({ ...window.__ef, y: scrollY, url: location.href, foco: document.activeElement && document.activeElement.outerHTML.slice(0, 120) }));
      const abas = ctx.pages().length;
      p.__dialogo = p.__download = false;
      try { await alvo.click({ timeout: 4000 }); } catch (e) {
        const motivo = e.message.split('\n').find((l) => /intercepts|not visible|outside of the viewport/.test(l)) || e.message.split('\n')[0];
        linha.problema = 'não dá para clicar: ' + motivo.trim().slice(0, 140); linhas.push(linha); continue;
      }
      await p.waitForTimeout(450);
      const nova = ctx.pages().length > abas;
      if (nova) for (const x of ctx.pages().slice(abas)) await x.close();
      let efeito = nova ? 'abre aba' : p.__download ? 'baixa arquivo' : p.__dialogo ? 'diálogo' : '';
      if (!efeito && p.url() !== antes.url) efeito = new URL(p.url()).pathname === new URL(antes.url).pathname ? 'rola/âncora' : 'navega';
      if (!efeito) {
        const depois = await p.evaluate(() => ({ ...window.__ef, y: scrollY, foco: document.activeElement && document.activeElement.outerHTML.slice(0, 120),
          invalido: !!document.querySelector('form :invalid') && !!document.activeElement && !!document.activeElement.closest('form') }));
        if (depois.mut !== antes.mut) efeito = 'muda a página';
        else if (depois.y !== antes.y) efeito = 'rola';
        else if (depois.ev !== antes.ev) efeito = 'altera campo';
        else if (depois.foco !== antes.foco) efeito = 'move o foco';
        else if (depois.invalido) efeito = 'mostra validação';
      }
      linha.efeito = efeito;
      if (!efeito) linha.problema = 'clique sem efeito visível';
      linhas.push(linha);
    }
    await p.close();
  }
  await nav.close();
  return linhas;
}

// dois ambientes por vez (o servidor local não aguenta os quatro juntos)
const todas = [...(await Promise.all(AMBIENTES.slice(0, 2).map(auditar))), ...(await Promise.all(AMBIENTES.slice(2).map(auditar)))].flat();
mkdirSync('relatorios', { recursive: true });
writeFileSync('relatorios/cliques.json', JSON.stringify(todas, null, 1));
const falhas = todas.filter((l) => l.problema);
for (const amb of AMBIENTES.map((a) => a[0])) {
  const d = todas.filter((l) => l.amb === amb);
  console.log(`${amb}: ${d.length} cliques, ${d.filter((l) => l.problema).length} com problema`);
}
for (const f of falhas) console.log(`FALHA ${f.amb} · ${f.pagina} · ${f.elemento}: ${f.problema}`);
process.exit(falhas.length ? 1 : 0);
