// Resultado do diagnóstico: mostra 5 editais e o botão "Ver todos os N", que abre o resto.
// uso: (com o site servido em http://127.0.0.1:8765)  node ver_todos.mjs
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 375, height: 812 } });
await ctx.addInitScript(() => localStorage.setItem('tm_perfil', JSON.stringify({ origem: 'brasil', curso: 'medicina', faculdade: '',
  semestre: 3, transferiu: 'nao', cidade: 'Salvador - BA', coords: [-12.9718, -38.5011], raio: 0, tipo: 'todas', taxaMax: null })));
const p = await ctx.newPage();
const erros = []; p.on('pageerror', e => erros.push(String(e)));
await p.goto(BASE + '/diagnostico/#resultado', { waitUntil: 'load' });
await p.waitForSelector('#res-titulo');
const antes = await p.locator('#resultado article.cartao:visible').count();
const ocultos = await p.locator('#res-resto article.cartao').count();
const botao = p.locator('#res-ver-todos');
const texto = await botao.textContent();
await botao.click();
const depois = await p.locator('#resultado article.cartao:visible').count();
const n = Number(texto.match(/\d+/)[0]);
console.log({ antes, ocultos, texto, depois, erros });
const ok = ocultos === n - 5 && depois === antes + ocultos && !erros.length;
console.log(ok ? 'ok' : 'FALHA');
await b.close();
process.exit(ok ? 0 : 1);
