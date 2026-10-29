// Capturas no celular: iPhone (390x844) e navegador do Instagram (390x664: barras do app em cima e embaixo).
// uso: node celular.mjs antes|depois  → screenshots/celular/<fase>-<tela>-<aparelho>.png
import { chromium, devices } from 'playwright';
import { mkdirSync } from 'node:fs';
const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const fase = process.argv[2] || 'antes';
mkdirSync('screenshots/celular', { recursive: true });
const IG = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 340.0.0.22.109 (iPhone14,7; iOS 17_5; pt_BR; pt; scale=3.00; 1170x2532)';
const aparelhos = { iphone: { ...devices['iPhone 13'], viewport: { width: 390, height: 844 } },
  instagram: { ...devices['iPhone 13'], viewport: { width: 390, height: 664 }, userAgent: IG } };
const b = await chromium.launch();
for (const [nome, cfg] of Object.entries(aparelhos)) {
  const ctx = await b.newContext(cfg);
  await ctx.route('**/rest/v1/rpc/**', r => r.fulfill({ status: 200, contentType: 'application/json', body: '0' }));
  const p = await ctx.newPage(); const erros = []; p.on('pageerror', e => erros.push(String(e)));
  const foto = async (tela, inteira = false) => { await p.waitForTimeout(500); await p.screenshot({ path: `screenshots/celular/${fase}-${tela}-${nome}.png`, fullPage: inteira }); };
  await p.goto(BASE + '/', { waitUntil: 'load' }); await foto('home'); await foto('home-inteira', true);
  await p.goto(BASE + '/diagnostico/', { waitUntil: 'load' });
  await p.getByText('No Brasil', { exact: true }).click();
  for (let i = 0; i < 6 && await p.locator('#resultado').isHidden(); i++) { if (await p.locator('#semestre').isVisible()) await p.selectOption('#semestre', '3'); await p.locator('#seguir').click(); await p.waitForTimeout(300); }
  await p.locator('#resultado').scrollIntoViewIfNeeded(); await foto('resultado'); await foto('resultado-inteira', true);
  await p.goto(BASE + '/edital/unex-jequie-externa-2027-1-cebb92/', { waitUntil: 'load' }); await foto('ficha'); await foto('ficha-inteira', true);
  const largo = await p.evaluate(() => document.documentElement.scrollWidth > innerWidth);
  console.log(nome, 'erros:', erros.length, 'rolagem lateral:', largo);
  await ctx.close();
}
await b.close();
