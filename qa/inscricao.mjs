// Inscrição de teste em duas etapas, no navegador, sem tocar no Supabase de verdade: as chamadas ao banco são
// interceptadas e gravadas em relatorios/inscricao.json (o qa/simular_inscricao.py usa esse arquivo).
// uso: (com o site servido em http://127.0.0.1:8765)  node inscricao.mjs
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';

const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const EDITAL = '/edital/unime-externa-2027-1-3d14f3/';
const chamadas = [];
const falhas = [];
const ok = (cond, texto) => { if (!cond) falhas.push(texto); console.log((cond ? 'ok   ' : 'FALHA ') + texto); };

const navegador = await chromium.launch();
async function pagina(largura = 375) {
  const ctx = await navegador.newContext({ viewport: { width: largura, height: 812 } });
  const p = await ctx.newPage();
  const erros = [];
  p.on('console', m => { if (m.type() === 'error') erros.push(m.text()); });
  p.on('pageerror', e => erros.push(String(e)));
  await p.route('**/rest/v1/rpc/**', async rota => {
    const nome = rota.request().url().split('/rpc/')[1];
    const corpo = JSON.parse(rota.request().postData() || '{}');
    chamadas.push({ nome, corpo });
    await rota.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(nome === 'inscrever' ? 'pendente' : 0) });
  });
  return { p, ctx, erros };
}
mkdirSync('screenshots/inscricao', { recursive: true });

// 1) ficha com prazo: "Me lembre 7 e 2 dias antes", depois o perfil
{
  const { p, ctx, erros } = await pagina();
  await p.goto(BASE + EDITAL);
  const form = p.locator('#form-alerta');
  ok(await form.getAttribute('data-lembrete') !== null, 'ficha com prazo pede lembrete');
  ok(!(await p.locator('#consentimento').isChecked()), 'consentimento começa desmarcado');
  ok(await p.getByText('Grátis. Sem spam. Cancele em um clique.').isVisible(), 'garantia sob o formulário');
  await p.fill('#email-alerta', 'teste.brasil@exemplo.com');
  await p.locator('#form-alerta button[type=submit]').click();
  ok(/autorização/.test(await p.textContent('#alerta-msg')), 'sem marcar a caixa, não envia');
  await p.check('#consentimento');
  await p.locator('#form-alerta button[type=submit]').click();
  await p.waitForSelector('#form-perfil');
  await p.screenshot({ path: 'screenshots/inscricao/passo2-375.png', fullPage: false });
  ok(await p.locator('#form-alerta').isHidden(), 'passo 1 some depois de enviado');
  ok(await p.locator('#alerta-passo2 a[data-medir="isca"]').count() === 1, 'checklist em PDF oferecido na hora');
  await p.locator('#form-perfil button[type=submit]').click();
  ok(/semestre/.test(await p.textContent('#perfil-msg')), 'passo 2 pede o semestre');
  await p.selectOption('#p2-semestre', '5');
  await p.locator('#form-perfil button[type=submit]').click();
  await p.waitForSelector('#alerta-passo2 >> text=Perfil salvo');
  await p.screenshot({ path: 'screenshots/inscricao/fim-375.png', fullPage: false });
  ok(erros.length === 0, 'console limpo na ficha (' + erros.join(' | ') + ')');
  await ctx.close();
}

// 2) "Estudo no exterior": perfil de base do exterior, pula o passo 2
{
  const { p, ctx, erros } = await pagina(1280);
  await p.goto(BASE + '/exterior/');
  await p.fill('#email-alerta', 'teste.exterior@exemplo.com');
  await p.check('#consentimento');
  await p.locator('#form-alerta button[type=submit]').click();
  await p.waitForSelector('#form-perfil');
  ok(await p.locator('#form-perfil input[name=origem][value=exterior]').isChecked(), 'passo 2 pré-preenchido com "exterior"');
  await p.getByRole('button', { name: 'Agora não' }).click();
  ok(await p.getByText('Você pode completar o perfil depois').isVisible(), '"Agora não" fecha o passo 2');
  await p.screenshot({ path: 'screenshots/inscricao/exterior-1280.png', fullPage: false });
  ok(erros.length === 0, 'console limpo no exterior (' + erros.join(' | ') + ')');
  await ctx.close();
}

// 3) barra inferior: só depois de 60% de leitura; fechada, não volta (nem ao recarregar)
{
  const { p, ctx, erros } = await pagina();
  await p.goto(BASE + '/faculdade/famerp/');
  ok(await p.locator('.barra-alerta').count() === 0, 'sem barra ao abrir a página');
  await p.evaluate(() => scrollTo(0, document.documentElement.scrollHeight));
  await p.waitForTimeout(300);
  const temBarra = await p.locator('.barra-alerta').count();
  const alvoVisivel = await p.evaluate(() => { const r = document.querySelector('#alerta').getBoundingClientRect(); return r.top < innerHeight && r.bottom > 0; });
  ok(temBarra === 1 || alvoVisivel, 'barra aparece depois de 60% (ou o formulário já está na tela)');
  if (temBarra) {
    await p.screenshot({ path: 'screenshots/inscricao/barra-375.png', fullPage: false });
    await p.click('.barra-fechar');
    await p.reload();
    await p.evaluate(() => scrollTo(0, document.documentElement.scrollHeight * 0.7));
    await p.waitForTimeout(300);
    ok(await p.locator('.barra-alerta').count() === 0, 'barra fechada não volta');
  }
  ok(erros.length === 0, 'console limpo na faculdade (' + erros.join(' | ') + ')');
  await ctx.close();
}
await navegador.close();

const inscricoes = chamadas.filter(c => c.nome === 'inscrever').map(c => c.corpo);
ok(inscricoes.length === 3, `3 chamadas a inscrever (2 da ficha, 1 do exterior): ${inscricoes.length}`);
if (inscricoes.length === 3) {
  const [p1, p2, ext] = inscricoes.map(c => c.p_perfil);
  ok(p1.seguir.lembretes.length === 1 && p1.seguir.faculdades.includes('unime') && !p1.curso, 'passo 1 da ficha: só seguir e lembrete');
  ok(p2.curso === 'medicina' && p2.semestre === 5 && p2.origem === 'brasil' && p2.seguir.lembretes.length === 1, 'passo 2: perfil completo, pedido mantido');
  ok(ext.origem === 'exterior' && ext.curso === 'medicina', 'exterior: perfil de base');
  ok(inscricoes.every(c => /dicas sobre transferência/.test(c.p_consentimento)), 'consentimento com o texto novo');
}
mkdirSync('relatorios', { recursive: true });
writeFileSync('relatorios/inscricao.json', JSON.stringify(inscricoes, null, 1));
console.log(falhas.length ? `\n${falhas.length} falha(s)` : '\nTudo certo.');
process.exit(falhas.length ? 1 : 0);
