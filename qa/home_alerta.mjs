// B4: cartão de alerta da home. Chips de estado vão no perfil, o consentimento nunca vem marcado e o texto guardado é o completo.
// uso: (com o site em http://127.0.0.1:8765)  node home_alerta.mjs
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const falhas = []; const ok = (c, t) => { if (!c) falhas.push(t); console.log((c ? 'ok   ' : 'FALHA ') + t); };
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 375, height: 800 }, isMobile: true, hasTouch: true });
const chamadas = [];
await ctx.route('**/rest/v1/rpc/**', async r => {
  const nome = r.request().url().split('/rpc/')[1]; chamadas.push({ nome, corpo: JSON.parse(r.request().postData() || '{}') });
  await r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(nome === 'inscrever' ? 'pendente' : 0) });
});
const p = await ctx.newPage(); const erros = [];
p.on('pageerror', e => erros.push(String(e))); p.on('console', m => m.type() === 'error' && erros.push(m.text()));
await p.goto(BASE + '/', { waitUntil: 'load' }); await p.waitForTimeout(500);
ok(!(await p.locator('#consentimento').isChecked()), 'consentimento começa desmarcado');
ok(await p.locator('input[name="estado"]:checked').count() === 0, 'nenhum estado marcado de início');
await p.fill('#email-alerta', 'teste@exemplo.com');
await p.click('button[type="submit"]'); await p.waitForTimeout(300);
ok(!chamadas.some(c => c.nome === 'inscrever'), 'sem marcar a caixa, não envia');
ok(/autorização/.test(await p.textContent('#alerta-msg')), 'mensagem pede a autorização');
await p.locator('.chip-estado', { hasText: 'SP' }).click();
await p.locator('.chip-estado', { hasText: 'Exterior' }).click();
await p.locator('.consent-ver summary').click();
ok(await p.locator('.consent-ver p').isVisible(), '"O que vou receber" abre o texto completo');
await p.check('#consentimento');
await p.click('button[type="submit"]'); await p.waitForSelector('#alerta-passo2:not([hidden])');
const ins = chamadas.find(c => c.nome === 'inscrever');
ok(ins && ins.corpo.p_email === 'teste@exemplo.com', 'chamou inscrever com o e-mail');
ok(JSON.stringify(ins.corpo.p_perfil.estados) === JSON.stringify(['SP', 'EXTERIOR']), 'estados no perfil: ' + JSON.stringify(ins.corpo.p_perfil.estados));
ok(ins.corpo.p_perfil.curso === 'medicina', 'perfil de medicina');
ok(/alertas de editais de transferência de Medicina/.test(ins.corpo.p_consentimento) && ins.corpo.p_consentimento.length > 250, 'guarda o texto de consentimento completo');
// passo 2 mantém os estados
await p.selectOption('#p2-semestre', '3'); await p.click('#form-perfil button[type="submit"]'); await p.waitForTimeout(400);
const seg = chamadas.filter(c => c.nome === 'inscrever')[1];
ok(seg && JSON.stringify(seg.corpo.p_perfil.estados) === JSON.stringify(['SP', 'EXTERIOR']), 'o passo 2 não perde os estados');
ok(erros.length === 0, 'console limpo ' + erros.join(' | '));
await b.close();
console.log(falhas.length ? `${falhas.length} falha(s)` : 'tudo certo'); process.exit(falhas.length ? 1 : 0);
