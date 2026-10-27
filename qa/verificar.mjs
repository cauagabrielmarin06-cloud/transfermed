// QA do site: capturas em 375 px e 1280 px, console, requisições com erro, layout e acessibilidade (axe).
// uso: (com o site servido em http://127.0.0.1:8765)  node verificar.mjs
import { chromium } from 'playwright';
import { AxeBuilder } from '@axe-core/playwright';
import { mkdirSync, writeFileSync } from 'node:fs';

const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const PERFIL = {  // aluno de Medicina em Salvador, 3º semestre, até 400 km
  origem: 'brasil', curso: 'medicina', faculdade: '', semestre: 3, transferiu: 'nao', cidade: 'Salvador - BA',
  coords: [-12.9718, -38.5011], raio: 400, tipo: 'todas', taxaMax: null,
};
export const PAGINAS = [
  ['inicio', '/'],
  ['diagnostico', '/diagnostico/'],
  ['resultado', '/diagnostico/#resultado', true],
  ['exterior', '/exterior/'],
  ['faculdade-pitagoras', '/faculdade/pitagoras-eunapolis/'],
  ['faculdade-famerp', '/faculdade/famerp/'],
  ['faculdade-ufba', '/faculdade/ufba-salvador/'],
  ['edital-unime', '/edital/unime-externa-2027-1-3d14f3/'],
  ['edital-idomed-exterior', '/edital/idomed-alagoinhas-exterior-2027-1-3efda2/'],
  ['alerta-confirmar', '/alerta/confirmar/'],
  ['privacidade', '/privacidade/'],
];
const LARGURAS = [[375, 812], [1280, 900]];
// PAGINAS="nome:/caminho/,nome2:/caminho2/" roda só essas (útil para conferir páginas novas gastando menos memória)
if (process.env.PAGINAS) {
  PAGINAS.length = 0;
  for (const par of process.env.PAGINAS.split(',')) { const [n, c] = par.split(':'); PAGINAS.push([n, c, c.includes('#resultado')]); }
}

// roda dentro da página: rolagem lateral, elementos que passam da tela, texto cortado e alvos de toque pequenos
function inspecionar(largura) {
  const doc = document.documentElement;
  const fora = [], cortado = [], pequenos = [];
  const descr = el => (el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
    (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).join('.') : '')).slice(0, 80);
  const rolavel = el => { for (let p = el.parentElement; p; p = p.parentElement) {
    const o = getComputedStyle(p).overflowX; if (o === 'auto' || o === 'scroll' || o === 'hidden') return true; } return false; };
  for (const el of document.body.querySelectorAll('*')) {
    const st = getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden') continue;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    if (r.right > largura + 1 && !rolavel(el) && st.position !== 'fixed') fora.push(descr(el));
    if (!el.classList.contains('oculto') && (st.overflow === 'hidden' || st.textOverflow === 'ellipsis') && el.scrollWidth > el.clientWidth + 1 &&
        el.children.length === 0 && el.textContent.trim()) cortado.push(descr(el) + ': ' + el.textContent.trim().slice(0, 40));
    if (el.matches('a, button, input:not([type=hidden]), select, textarea, summary, [role=button]')) {
      // links no meio de um texto são exceção na WCAG 2.5.8
      const noMapa = !!el.closest('svg');
      const noTexto = el.tagName === 'A' && st.display === 'inline' && /^(P|LI|SPAN|SMALL|TD|DD|H2|H3|H4)$/.test(el.parentElement.tagName);
      if (!noTexto && !noMapa && (r.width < 24 || r.height < 24)) pequenos.push(`${descr(el)} ${Math.round(r.width)}x${Math.round(r.height)}`);
    }
  }
  return { rolagemLateral: doc.scrollWidth > window.innerWidth + 1, larguraPagina: doc.scrollWidth,
           fora: [...new Set(fora)].slice(0, 15), cortado: [...new Set(cortado)].slice(0, 15), pequenos: [...new Set(pequenos)].slice(0, 20) };
}

const saida = process.env.SAIDA || 'screenshots';
mkdirSync(saida, { recursive: true });
mkdirSync('relatorios', { recursive: true });
const navegador = await chromium.launch();
const relatorio = [];
for (const [nome, caminho, comPerfil] of PAGINAS) {
  for (const [w, h] of LARGURAS) {
    const ctx = await navegador.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1,
                                             isMobile: w < 500, hasTouch: w < 500 });
    if (comPerfil) await ctx.addInitScript(p => localStorage.setItem('tm_perfil', p), JSON.stringify(PERFIL));
    const page = await ctx.newPage();
    const consoleMsgs = [], falhas = [];
    page.on('console', m => { if (['error', 'warning'].includes(m.type())) consoleMsgs.push(`${m.type()}: ${m.text()}`); });
    page.on('pageerror', e => consoleMsgs.push(`pageerror: ${e.message}`));
    page.on('requestfailed', r => falhas.push(`${r.failure()?.errorText} ${r.url()}`));
    page.on('response', r => { if (r.status() >= 400) falhas.push(`${r.status()} ${r.url()}`); });
    await page.goto(BASE + caminho, { waitUntil: 'networkidle' });
    await page.waitForTimeout(400);
    const layout = await page.evaluate(inspecionar, w);
    await page.screenshot({ path: `${saida}/${nome}-${w}.png`, fullPage: true });
    const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze();
    const graves = axe.violations.filter(v => ['serious', 'critical'].includes(v.impact))
      .map(v => ({ id: v.id, impacto: v.impact, ajuda: v.help, alvos: v.nodes.slice(0, 5).map(n => n.target.join(' ')) }));
    const leves = axe.violations.filter(v => !['serious', 'critical'].includes(v.impact)).map(v => `${v.id} (${v.impact})`);
    relatorio.push({ pagina: nome, largura: w, console: consoleMsgs, falhas, ...layout, axeGraves: graves, axeLeves: leves });
    await ctx.close();
  }
}
await navegador.close();
writeFileSync('relatorios/verificacao.json', JSON.stringify(relatorio, null, 2));
let problemas = 0;
for (const r of relatorio) {
  const itens = [];
  if (r.console.length) itens.push(`console: ${r.console.join(' | ')}`);
  if (r.falhas.length) itens.push(`requisições: ${r.falhas.join(' | ')}`);
  if (r.rolagemLateral) itens.push(`ROLAGEM LATERAL (largura ${r.larguraPagina})`);
  if (r.fora.length) itens.push(`passam da tela: ${r.fora.join(', ')}`);
  if (r.cortado.length) itens.push(`texto cortado: ${r.cortado.join(', ')}`);
  if (r.pequenos.length && r.largura < 500) itens.push(`alvos < 24px: ${r.pequenos.join(', ')}`);
  if (r.axeGraves.length) itens.push(`AXE: ${r.axeGraves.map(v => `${v.id}[${v.impacto}] ${v.alvos.join(' ; ')}`).join(' || ')}`);
  if (r.axeLeves.length) itens.push(`axe leves: ${r.axeLeves.join(', ')}`);
  problemas += itens.length;
  console.log(`\n## ${r.pagina} @${r.largura}: ${itens.length ? '' : 'ok'}`);
  for (const i of itens) console.log('  - ' + i);
}
console.log(`\nTotal de apontamentos: ${problemas}`);
