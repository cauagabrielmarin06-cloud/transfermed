// Funis medidos de ponta a ponta, no navegador e sem tocar no Supabase de verdade (as chamadas são interceptadas):
//   A) visita → diagnóstico → alerta inscrito → alerta confirmado
//   B) visita → ficha do edital → PDF, WhatsApp → alerta inscrito
// Confere também que a medição não manda nada além do evento e do tipo de página.
// uso: (com o site servido em http://127.0.0.1:8765)  node funil.mjs  → relatorios/funil.json
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';

const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const EDITAL = '/edital/unime-externa-2027-1-3d14f3/';
const falhas = [];
const ok = (cond, texto) => { if (!cond) falhas.push(texto); console.log((cond ? 'ok   ' : 'FALHA ') + texto); };

const navegador = await chromium.launch();
async function pagina() {
  const ctx = await navegador.newContext({ viewport: { width: 375, height: 812 } });
  await ctx.addInitScript(() => { window.TM_MEDIR_TESTE = true; });
  const eventos = [];
  const erros = [];
  await ctx.route('**/rest/v1/rpc/**', async rota => {
    const nome = rota.request().url().split('/rpc/')[1];
    const corpo = JSON.parse(rota.request().postData() || '{}');
    if (nome === 'medir') eventos.push(corpo);
    const resposta = { inscrever: 'pendente', confirmar: 'ok', medir: null }[nome] ?? 0;
    await rota.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(resposta) });
  });
  await ctx.route(/\.pdf$|wa\.me/, rota => rota.fulfill({ status: 200, body: '' }));  // não sai do teste
  const p = await ctx.newPage();
  p.on('console', m => { if (m.type() === 'error') erros.push(m.text()); });
  p.on('pageerror', e => erros.push(String(e)));
  const nomes = () => eventos.map(e => `${e.p_nome}@${e.p_pagina}`);
  const esperar = async nome => { for (let i = 0; i < 40 && !eventos.some(e => e.p_nome === nome); i++) await p.waitForTimeout(100); };
  return { ctx, p, eventos, erros, nomes, esperar };
}

try {
// A) visita → diagnóstico → alerta → confirmação
{
  const { ctx, p, eventos, erros, nomes, esperar } = await pagina();
  await p.goto(BASE + '/');
  await esperar('visita');
  await p.goto(BASE + '/diagnostico/');
  await p.getByText('No Brasil', { exact: true }).click();
  for (let i = 0; i < 6 && await p.locator('#resultado').isHidden(); i++) {
    if (await p.locator('#semestre').isVisible()) await p.selectOption('#semestre', '3');
    await p.locator('#seguir').click();  // "Continuar" nas etapas, outro texto na última
    await p.waitForTimeout(300);
  }
  ok(await p.locator('#resultado').isVisible(), 'diagnóstico chega ao resultado');
  await esperar('diagnostico_concluido');
  await p.fill('#email-alerta', 'teste.funil@exemplo.com');
  await p.check('#consentimento');
  await p.locator('#form-alerta button[type=submit]').click();
  await esperar('alerta_inscrito_diagnostico');
  await p.goto(BASE + '/alerta/confirmar/?t=123e4567-e89b-12d3-a456-426614174000');
  await esperar('alerta_confirmado');
  const n = nomes();
  console.log('   funil A:', n.join(' → '));
  for (const e of ['visita@inicio', 'visita@diagnostico', 'diagnostico_iniciado@diagnostico', 'diagnostico_concluido@diagnostico',
    'alerta_inscrito@diagnostico', 'alerta_inscrito_diagnostico@diagnostico', 'alerta_confirmado@alerta']) {
    ok(n.includes(e), `funil A mede ${e}`);
  }
  ok(n.indexOf('diagnostico_concluido@diagnostico') < n.indexOf('alerta_inscrito@diagnostico'), 'funil A na ordem');
  ok(eventos.every(e => Object.keys(e).sort().join() === 'p_nome,p_pagina'), 'medição só manda evento e tipo de página');
  ok(!JSON.stringify(eventos).includes('exemplo.com'), 'medição nunca leva o e-mail');
  ok(erros.length === 0, 'console limpo no funil A (' + erros.join(' | ') + ')');
  await ctx.close();
}

// B) visita → ficha → PDF e WhatsApp → alerta
{
  const { ctx, p, erros, nomes, esperar } = await pagina();
  await p.goto(BASE + '/');
  await esperar('visita');
  await p.goto(BASE + EDITAL);
  await esperar('ver_edital');
  const [pdf] = await Promise.all([ctx.waitForEvent('page'), p.locator('[data-medir="abrir_pdf"]').first().click()]);
  await pdf.close();
  await p.locator('[data-compartilhar]').first().click();
  const zap = p.locator('[data-medir="compartilhar_whatsapp"]').first();
  if (await zap.count()) {
    const [aba] = await Promise.all([ctx.waitForEvent('page'), zap.click()]);
    await aba.close();
  }
  await p.fill('#email-alerta', 'teste.funil@exemplo.com');
  await p.check('#consentimento');
  await p.locator('#form-alerta button[type=submit]').click();
  await esperar('alerta_inscrito_edital_lembrete');
  const n = nomes();
  console.log('   funil B:', n.join(' → '));
  for (const e of ['visita@inicio', 'visita@edital', 'ver_edital@edital', 'abrir_pdf@edital', 'compartilhar_whatsapp@edital',
    'alerta_inscrito@edital', 'alerta_inscrito_edital_lembrete@edital']) {
    ok(n.includes(e), `funil B mede ${e}`);
  }
  ok(erros.length === 0, 'console limpo no funil B (' + erros.join(' | ') + ')');
  await ctx.close();
}

} catch (erro) { ok(false, 'o teste do funil parou: ' + String(erro).split('\n')[0]); }
await navegador.close();
mkdirSync('relatorios', { recursive: true });
writeFileSync('relatorios/funil.json', JSON.stringify(falhas, null, 2));
console.log(falhas.length ? `\n${falhas.length} falha(s)` : '\nfunis medidos de ponta a ponta');
process.exit(falhas.length ? 1 : 0);
