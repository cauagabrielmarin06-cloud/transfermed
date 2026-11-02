// Visitante antigo: o navegador guarda um perfil (tm_perfil) de versões anteriores do diagnóstico, com campos que
// mudaram de nome, valores que não existem mais ou lixo. A página nunca pode ficar em branco nem dar erro.
// uso: (site em http://127.0.0.1:8765, ou BASE=<site no ar>)  node visitante_antigo.mjs
import { chromium } from 'playwright';

const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const PERFIS = {
  'objeto vazio': {},
  'campos antigos': { semestre_atual: 4, faculdade: 'xxx', curso: 'direito', origem: 'marte', raio: 'longe' },
  'faculdade que não existe mais': { origem: 'brasil', faculdade_origem: 'faculdade-que-saiu', semestre: '99', cidade: 'Lugar Nenhum' },
  'valores nulos': { origem: null, semestre: null, faculdade_origem: null },
  'texto solto': 'perfil antigo',
  'lista': [1, 2, 3],
  'número': 42,
  'JSON quebrado': '{"origem":',
};
const nav = await chromium.launch();
const falhas = [];
for (const [nome, perfil] of Object.entries(PERFIS)) {
  for (const largura of [390, 1280]) {
    const ctx = await nav.newContext({ viewport: { width: largura, height: 900 } });
    const pag = await ctx.newPage();
    const erros = [];
    pag.on('pageerror', (e) => erros.push(e.message));
    pag.on('console', (m) => { if (m.type() === 'error') erros.push(m.text()); });
    const bruto = typeof perfil === 'string' && nome === 'JSON quebrado' ? perfil : JSON.stringify(perfil);
    await pag.addInitScript(`try { localStorage.setItem('tm_perfil', ${JSON.stringify(bruto)}); } catch (e) {}`);
    for (const url of ['/diagnostico/', '/diagnostico/#resultado', '/', '/minha-lista/']) {
      erros.length = 0;
      await pag.goto(BASE + url, { waitUntil: 'load' });
      await pag.waitForTimeout(400);
      const info = await pag.evaluate(() => {
        const vis = (el) => !!el && el.getBoundingClientRect().height > 0 && getComputedStyle(el).visibility !== 'hidden';
        const form = document.querySelector('#diag');
        return {
          texto: document.body.innerText.trim().length,
          h1: !!document.querySelector('h1') && vis(document.querySelector('h1')),
          formVisivel: form ? vis(form) : null,
          etapaAtiva: document.querySelectorAll('.etapa.ativa, [data-etapa].ativa').length,
          resultado: vis(document.querySelector('#resultado')) ? document.querySelector('#resultado').innerText.trim().length : 0,
        };
      });
      const onde = `${nome} · ${largura}px · ${url}`;
      if (info.texto < 200 || !info.h1) falhas.push(`${onde}: página em branco (${info.texto} caracteres)`);
      if (url === '/diagnostico/' && info.formVisivel === false) falhas.push(`${onde}: formulário invisível`);
      if (url === '/diagnostico/' && info.etapaAtiva === 0 && info.resultado === 0) falhas.push(`${onde}: nenhuma etapa nem resultado à vista`);
      if (erros.length) falhas.push(`${onde}: erros no console: ${erros.slice(0, 2).join(' | ')}`);
    }
    await ctx.close();
  }
}
await nav.close();
if (falhas.length) { console.error('FALHAS:\n' + falhas.join('\n')); process.exit(1); }
console.log(`ok: visitante antigo (${Object.keys(PERFIS).length} perfis x 2 larguras x 4 páginas)`);
