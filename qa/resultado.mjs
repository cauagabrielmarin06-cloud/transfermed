// Resultado do diagnóstico no celular: o formulário recolhe numa linha "Seu perfil" e "Mudar respostas" volta à etapa 1.
// uso: BASE=<site> node qa/resultado.mjs   (padrão: servidor local 127.0.0.1:8765)
import { chromium, devices } from 'playwright';
const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const b = await chromium.launch();
const ctx = await b.newContext({ ...devices['iPhone 13'], viewport: { width: 390, height: 844 } });
await ctx.route('**/rest/v1/rpc/**', r => r.fulfill({ status: 200, contentType: 'application/json', body: '0' }));
const p = await ctx.newPage(); const erros = [];
p.on('pageerror', e => erros.push(String(e)));
let falhas = 0;
const conferir = (ok, txt) => { console.log(ok ? 'ok  ' : 'FALHA', txt); if (!ok) falhas++; };
async function concluir() {
  for (let i = 0; i < 6 && await p.locator('#resultado').isHidden(); i++) {
    if (await p.locator('#semestre').isVisible()) await p.selectOption('#semestre', '3');
    await p.locator('#seguir').click(); await p.waitForTimeout(250);
  }
}
await p.goto(BASE + '/diagnostico/', { waitUntil: 'load' });
await p.getByText('No Brasil', { exact: true }).click();
await concluir();
conferir(await p.locator('#resultado').isVisible(), 'resultado aparece');
conferir(await p.locator('#diag').isHidden(), 'formulário recolhe quando o resultado aparece');
const resumo = await p.locator('.perfil-resumo').textContent().catch(() => '');
conferir(/3º semestre/.test(resumo || ''), `linha "Seu perfil" com as respostas (${(resumo || '').trim().replace(/\s+/g, ' ')})`);
const topo = await p.locator('.frase-resultado').evaluate(el => el.getBoundingClientRect().top).catch(() => 1e9);
conferir(topo < 400, `frase do resultado no alto da tela (${Math.round(topo)} px)`);
if (await p.locator('#res-mudar').count()) {
  await p.locator('#res-mudar').click(); await p.waitForTimeout(250);
  conferir(await p.locator('#diag').isVisible() && await p.locator('#resultado').isHidden(), '"Mudar respostas" mostra o formulário e esconde o resultado');
  conferir((await p.locator('#passo-txt').textContent()).includes('Etapa 1'), 'volta à etapa 1');
  await concluir();
  conferir(await p.locator('#resultado').isVisible() && await p.locator('#diag').isHidden(), 'refazer chega de novo ao resultado');
} else conferir(false, 'botão "Mudar respostas" existe');
await p.goto(BASE + '/diagnostico/#resultado', { waitUntil: 'load' }); await p.waitForTimeout(300);
conferir(await p.locator('#diag').isHidden() && await p.locator('.perfil-resumo').isVisible(), 'perfil salvo (#resultado) abre já recolhido');
conferir(!erros.length, 'console limpo ' + erros.join(' | '));
await b.close();
console.log(falhas ? `${falhas} falha(s)` : 'resultado do diagnóstico: tudo certo');
process.exit(falhas ? 1 : 0);
