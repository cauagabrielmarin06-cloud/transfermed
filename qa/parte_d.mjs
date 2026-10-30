// Parte D: o bloco "Quando" das fichas mostra resultado e matrícula transcritos, com a página do edital.
// uso: node parte_d.mjs   (BASE=<site> para conferir outro endereço) → screenshots/parte-d/<ficha>-<largura>.png
// Falha se a ficha voltar à linha "ainda não transcritos" ou perder a página de uma das etapas.
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
const BASE = process.env.BASE || 'http://127.0.0.1:8765';
mkdirSync('screenshots/parte-d', { recursive: true });
const FICHAS = [
  ['unoeste', '/edital/unoeste-jau-externa-2027-1-0bfe52/', '14/12/2026', '14/12/2026 a 17/12/2026'],
  ['unime', '/edital/unime-externa-2027-1-3d14f3/', '25/11/2026', '27/11/2026 a 03/12/2026'],
  ['unex-vca', '/edital/unex-vca-externa-2027-1-e76ba5/', '1 dia útil', '2 dias úteis'],
  ['idomed-exterior', '/edital/idomed-alagoinhas-exterior-2027-1-3efda2/', '02/02/2027', '03/02/2027'],
];
const b = await chromium.launch();
let falhas = 0;
for (const [nome, caminho, res, mat] of FICHAS) {
  for (const largura of [375, 1280]) {
    const p = await b.newPage({ viewport: { width: largura, height: 900 } });
    const erros = [];
    p.on('console', m => { if (m.type() === 'error') erros.push(m.text()); });
    const resp = await p.goto(BASE + caminho, { waitUntil: 'networkidle' });
    const bloco = p.locator('#t-quando').locator('xpath=..');
    const linha = async dt => (await bloco.locator(`dt:text-is("${dt}") + dd`).innerText({ timeout: 3000 }).catch(() => '')).trim();
    const r = await linha('Resultado'), m = await linha('Matrícula');
    const problemas = resp && resp.ok() ? [] : [`página não abriu (${resp && resp.status()})`];
    if (!r.includes(res)) problemas.push(`resultado "${r}" sem "${res}"`);
    if (!m.includes(mat)) problemas.push(`matrícula "${m}" sem "${mat}"`);
    if (await bloco.locator('.pag').count() < 3) problemas.push('falta a página em alguma etapa');
    if (erros.length) problemas.push('console: ' + erros.join(' | '));
    const lateral = await p.evaluate(() => document.documentElement.scrollWidth > innerWidth);
    if (lateral) problemas.push('rolagem lateral');
    if (await bloco.count()) await bloco.screenshot({ path: `screenshots/parte-d/${nome}-${largura}.png` });
    console.log(`${nome} @${largura}: ${problemas.length ? 'FALHA ' + problemas.join('; ') : 'ok'}`);
    falhas += problemas.length;
    await p.close();
  }
}
await b.close();
process.exit(falhas ? 1 : 0);
