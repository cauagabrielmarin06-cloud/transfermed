// Capturas das etapas 2 e 3 do diagnóstico (campos simples, sem fieldset) em 375 px.
import { chromium } from 'playwright';
const b = await chromium.launch();
const pg = await (await b.newContext({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true })).newPage();
const erros = []; pg.on('pageerror', e => erros.push(e.message)); pg.on('console', m => m.type() === 'error' && erros.push(m.text()));
await pg.goto('http://127.0.0.1:8765/diagnostico/', { waitUntil: 'networkidle' });
await pg.getByText('No Brasil', { exact: true }).click();
await pg.getByRole('button', { name: 'Continuar' }).click();
await pg.waitForTimeout(700);
await pg.screenshot({ path: 'screenshots/diagnostico-etapa2-375.png', fullPage: true });
await pg.fill('#faculdade', 'Universidade Brasil');
await pg.selectOption('#semestre', '3');
await pg.locator('input[name=transferiu]').first().check({ force: true });
await pg.getByRole('button', { name: 'Continuar' }).click();
await pg.waitForTimeout(700);
await pg.screenshot({ path: 'screenshots/diagnostico-etapa3-375.png', fullPage: true });
console.log('erros:', erros.length ? erros : 'nenhum');
await b.close();
