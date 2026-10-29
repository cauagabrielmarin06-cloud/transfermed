// Cabeçalho no celular: em nenhuma largura de 320 a 768 px dois elementos visíveis do cabeçalho se sobrepõem, nada
// sai da tela e só aparecem a marca, a lupa (Buscar) e o menu (☰), todos com nome. Também em altura reduzida
// (navegador do Instagram: barras do app em cima e embaixo). No computador, o menu ☰ não aparece.
// uso: (com o site servido em http://127.0.0.1:8765)  node cabecalho.mjs  → relatorios/cabecalho.json
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';

const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const PAGINAS = ['/', '/diagnostico/', '/edital/unex-jequie-externa-2027-1-cebb92/', '/minha-lista/', '/sobre/'];
const LARGURAS = [320, 344, 360, 375, 390, 412, 430, 480, 600, 700, 768];
const falhas = [];
const b = await chromium.launch();
for (const [largura, altura] of [...LARGURAS.map(w => [w, 844]), [390, 664], [360, 600], [1280, 800]]) {
  const p = await b.newPage({ viewport: { width: largura, height: altura }, hasTouch: largura <= 768, isMobile: largura <= 768 });
  for (const url of PAGINAS) {
    await p.goto(BASE + url, { waitUntil: 'load' });
    const r = await p.evaluate(() => {
      const topo = document.querySelector('.topo > .wrap');
      const visivel = el => { const c = el.getBoundingClientRect(), s = getComputedStyle(el);
        return c.width > 0 && c.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && el.offsetParent !== null; };
      const itens = [...topo.querySelectorAll('a, button')].filter(visivel).map(el => {
        const c = el.getBoundingClientRect();
        const nome = (el.getAttribute('aria-label') || el.textContent || '').trim();
        return { cls: el.className.baseVal ?? el.className, nome, x1: c.left, x2: c.right, y1: c.top, y2: c.bottom };
      });
      return { itens, largura: document.documentElement.clientWidth, rolagem: document.documentElement.scrollWidth > innerWidth };
    });
    const onde = `${url} @${largura}x${altura}`;
    const it = r.itens;
    for (let i = 0; i < it.length; i++) {
      const a = it[i];
      if (!a.nome) falhas.push(`${onde}: "${a.cls}" sem nome`);
      if (a.x1 < 0 || a.x2 > r.largura + 0.5) falhas.push(`${onde}: "${a.nome}" sai da tela`);
      for (let j = i + 1; j < it.length; j++) {
        const c = it[j];
        if (a.x1 < c.x2 - 0.5 && c.x1 < a.x2 - 0.5 && a.y1 < c.y2 - 0.5 && c.y1 < a.y2 - 0.5) falhas.push(`${onde}: "${a.nome}" sobrepõe "${c.nome}"`);
      }
    }
    if (r.rolagem) falhas.push(`${onde}: rolagem lateral`);
    const classes = it.map(x => String(x.cls));
    if (largura <= 768) {
      const esperado = ['marca', 'busca-botao', 'menu-botao'];
      if (classes.join() !== esperado.join()) falhas.push(`${onde}: cabeçalho com ${classes.join(', ')} (esperado: marca, lupa e menu)`);
      if (it.length === 3 && !(it[0].x2 < it[1].x1 && Math.abs((it[1].y1 + it[1].y2) - (it[2].y1 + it[2].y2)) < 2)) falhas.push(`${onde}: lupa e menu fora da linha da marca`);
    } else if (classes.includes('menu-botao')) falhas.push(`${onde}: menu ☰ aparece no computador`);
  }
  if (largura <= 768) {  // o menu abre com os 5 itens com texto
    await p.goto(BASE + '/', { waitUntil: 'load' });
    if (!(await p.locator('.menu-botao').isVisible())) { falhas.push(`menu @${largura}: sem o botão ☰`); await p.close(); continue; }
    await p.locator('.menu-botao').click();
    const itens = (await p.locator('#menu-celular a').allTextContents()).map(t => t.replace(/\d+$/, '').trim());
    const esperado = ['Diagnóstico', 'Estudo no exterior', 'Minha lista', 'Quem faz o Transfermed', 'Contato'];
    if (itens.join('|') !== esperado.join('|') || !(await p.locator('#menu-celular').isVisible())) falhas.push(`menu @${largura}: ${itens.join(', ')}`);
  }
  await p.close();
}
await b.close();
mkdirSync('relatorios', { recursive: true });
writeFileSync('relatorios/cabecalho.json', JSON.stringify(falhas, null, 2));
for (const f of falhas) console.log('FALHA', f);
console.log(falhas.length ? `\n${falhas.length} falha(s)` : 'cabeçalho sem sobreposição em todas as larguras');
process.exit(falhas.length ? 1 : 0);
