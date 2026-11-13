// Parte D: Meu plano (/minha-lista/), comparar, "O que mudou" e convite do app.
// - linha do tempo só com datas conferidas; aviso de duas provas no mesmo dia (faculdades ou campi diferentes), nunca com data em "conferir";
// - "Pôr os N na minha agenda": .ics válido (biblioteca icalendar) com alarmes 7 e 2 dias antes do fim, só de datas conferidas;
// - documentos de todos: só agrupa nome igual, mostra "pedem X de N" e o progresso é o MESMO do checklist de cada edital;
// - comparar até 3 (colunas na ordem em que foram salvos, "conferir" como "conferir", sem cor de melhor/pior);
// - cartão "Retificado em" com antes riscado e depois; convite de instalar só depois de salvar 1 edital, fechado não volta por 30 dias;
// - lista vazia mostra os 3 que encerram primeiro; 375 e 1280 px sem rolagem horizontal; console limpo; medição só com contagens.
// uso: (site em http://127.0.0.1:8765, ou BASE=<site no ar>)  node meu_plano.mjs
import { chromium, webkit } from 'playwright';
import { execFileSync } from 'node:child_process';
import { writeFileSync, mkdirSync } from 'node:fs';

const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const falhas = [];
const ok = (c, t) => { console.log((c ? 'ok   ' : 'FALHA ') + t); if (!c) falhas.push(t); };
const b = await (process.env.NAVEGADOR === 'webkit' ? webkit : chromium).launch();

async function nova(op = {}, salvos = null, extra = {}) {
  const ctx = await b.newContext({ acceptDownloads: true, ...op });
  const medidos = [];
  await ctx.addInitScript(() => { window.TM_MEDIR_TESTE = true; try { sessionStorage.setItem('tm_abertura', '1'); } catch (e) {} });
  if (salvos) await ctx.addInitScript(([s, x]) => { try { if (!localStorage.getItem('tm_marcados')) localStorage.setItem('tm_marcados', JSON.stringify(s)); for (const [k, v] of Object.entries(x)) if (!localStorage.getItem(k)) localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }, [salvos, extra]);
  await ctx.route(/\/rest\/v1\/rpc\//, async (r) => {
    try { medidos.push(JSON.parse(r.request().postData() || '{}').p_nome); } catch (e) {}
    await r.fulfill({ status: 200, contentType: 'application/json', body: 'null' });
  });
  const p = await ctx.newPage();
  const erros = [];
  p.on('pageerror', (e) => erros.push(e.message));
  p.on('console', (m) => m.type() === 'error' && erros.push(m.text()));
  return { ctx, p, erros, medidos };
}

// ---- dados reais do site: escolhe os editais pelos fatos, não por id fixo
const sonda = await nova();
await sonda.p.goto(BASE + '/minha-lista/', { waitUntil: 'load' });
const dados = await sonda.p.evaluate(() => {
  const h = (() => { const d = new Date(); return new Date(d.getTime() - d.getTimezoneOffset() * 6e4).toISOString().slice(0, 10); })();
  const conf = (e, c) => !(e.conf || []).includes('edital') && !(e.conf || []).includes(c);
  const vivos = window.TM.editais.filter((e) => e.fim && e.fim >= h);
  const porProva = {};
  for (const e of vivos) if (e.prova && e.prova >= h && conf(e, 'data_prova')) (porProva[e.prova] = porProva[e.prova] || []).push(e);
  const choque = Object.values(porProva).map((l) => { const v = new Set(); return l.filter((e) => !v.has(e.fid) && v.add(e.fid)); }).find((l) => l.length >= 2) || null;
  const comProva = vivos.filter((e) => e.prova && conf(e, 'data_prova') && (!choque || !choque.some((c) => c.id === e.id)));
  const comRet = window.TM.editais.find((e) => e.ret && (e.ret.m || []).length && e.fim >= h) || null;
  const comConferir = vivos.find((e) => (e.conf || []).includes('data_prova') || (e.conf || []).includes('edital')) || null;
  const abertos = vivos.sort((x, y) => x.fim.localeCompare(y.fim));
  return { h, choque: choque && choque.map((e) => e.id), semChoque: comProva.slice(0, 3).map((e) => e.id), ret: comRet && comRet.id, conferir: comConferir && comConferir.id,
    primeiros: abertos.filter((e) => !(e.conf || []).includes('edital') && !(e.conf || []).includes('inscricao_fim')).slice(0, 3).map((e) => e.id), todos: abertos.map((e) => e.id) };
});
await sonda.ctx.close();
console.log('dados reais do dia:', JSON.stringify({ ...dados, todos: dados.todos.length }));

// ---- 1. lógica pura (os mesmos objetos que o gerador publica)
{
  const { p, ctx } = await nova();
  await p.goto(BASE + '/minha-lista/', { waitUntil: 'load' });
  const r = await p.evaluate(() => {
    const T = window.TM_PLANO, fac = (fid) => { window.TM.faculdades[fid] = window.TM.faculdades[fid] || { id: fid, sigla: fid.toUpperCase(), cidade: 'X', uf: 'SP' }; return fid; };
    const ed = (id, fid, o = {}) => ({ id, fid: fac(fid), slug: id, url: 'x.pdf', prova: '2099-12-13', fim: '2099-12-01', docs: [], ...o });
    const A = ed('a', 'aaa'), B = ed('b', 'bbb'), C = ed('c', 'ccc', { prova: '2099-12-14' });
    const h = '2026-11-13';
    const out = {};
    out.dois = T.detectarChoques([A, B, C], h).map((c) => [c.data, c.es.map((e) => e.id)]);
    out.semChoque = T.detectarChoques([A, C], h).length;
    out.provaEmConferir = T.detectarChoques([A, { ...B, conf: ['data_prova'] }], h).length;
    out.editalEmConferir = T.detectarChoques([A, { ...B, conf: ['edital'] }], h).length;
    out.outroCampoEmConferir = T.detectarChoques([A, { ...B, conf: ['resultado'] }], h).length;
    out.mesmaFaculdade = T.detectarChoques([A, ed('a2', 'aaa')], h).length;
    out.passado = T.detectarChoques([{ ...A, prova: '2026-01-01' }, { ...B, prova: '2026-01-01' }], h).length;
    out.tres = T.textoChoque({ data: '2099-12-13', es: [A, B, ed('d', 'ddd')] });
    out.dois_txt = T.textoChoque({ data: '2099-12-13', es: [A, B] });
    const ev = T.eventosDoPlano([{ ...A, res: '2099-12-20', conf: ['resultado'] }, B], h);
    out.eventos = ev.map((e) => `${e.e.id}:${e.campo}`);
    out.semDataEmConferir = T.eventosDoPlano([{ ...A, conf: ['inscricao_fim', 'data_prova'] }], h).length;
    const d1 = ed('d1', 'x1', { docs: ['RG e CPF', 'Histórico escolar completo', 'Histórico escolar completo original', 'Comprovante de residência'] });
    const d2 = ed('d2', 'x2', { docs: ['rg e cpf.', 'Historico Escolar Completo', 'Foto 3x4'] });
    const g = T.agruparDocumentos([d1, d2]);
    out.grupos = g.map((x) => [x.rotulo, x.pedem]);
    out.itens = g.find((x) => x.rotulo === 'RG e CPF').itens;
    return out;
  });
  ok(JSON.stringify(r.dois) === JSON.stringify([['2099-12-13', ['a', 'b']]]), 'choque: A e B no mesmo dia, C (outro dia) fora');
  ok(r.semChoque === 0, 'sem choque quando as provas são em dias diferentes');
  ok(r.provaEmConferir === 0 && r.editalEmConferir === 0, 'data de prova em "conferir" (ou edital inteiro em conferir) nunca gera choque');
  ok(r.outroCampoEmConferir === 1, 'outro campo em conferir (resultado) não esconde a prova');
  ok(r.mesmaFaculdade === 0, 'dois editais da mesma faculdade no mesmo dia não disparam o aviso');
  ok(r.passado === 0, 'prova que já passou não gera aviso');
  ok(r.dois_txt.startsWith('<strong>Duas provas no mesmo dia:</strong>') && /marcam prova em 13\/12\. Leia os dois editais e decida antes de pagar as duas taxas\./.test(r.dois_txt), 'texto do aviso (2): ' + r.dois_txt);
  ok(/^<strong>Três provas no mesmo dia:<\/strong> AAA X, BBB X e DDD X marcam/.test(r.tres) && /os três editais.*as três taxas/.test(r.tres), 'texto do aviso (3): ' + r.tres);
  ok(JSON.stringify(r.eventos) === JSON.stringify(['a:fim', 'b:fim', 'a:prova', 'b:prova']) , 'linha do tempo em ordem de data, sem o resultado em conferir: ' + r.eventos.join(' '));
  ok(r.semDataEmConferir === 0, 'fim e prova em conferir: nenhuma data entra na linha do tempo');
  ok(JSON.stringify(r.grupos) === JSON.stringify([['RG e CPF', 2], ['Histórico escolar completo', 2], ['Histórico escolar completo original', 1], ['Comprovante de residência', 1], ['Foto 3x4', 1]]),
    'documentos: só nome igual agrupa (sem acento/caixa/ponto); "…original" fica separado: ' + JSON.stringify(r.grupos));
  ok(r.itens.length === 2, 'o grupo guarda o edital e a posição de cada item (para marcar o checklist de cada um)');
  await ctx.close();
}

// ---- 2. .ics: cada edital salvo, alarmes, só datas conferidas (icalendar valida)
{
  const { p, ctx } = await nova();
  await p.goto(BASE + '/minha-lista/', { waitUntil: 'load' });
  const texto = await p.evaluate(() => {
    const fac = (fid) => { window.TM.faculdades[fid] = window.TM.faculdades[fid] || { id: fid, sigla: fid.toUpperCase(), cidade: 'X', uf: 'SP' }; return fid; };
    const ed = (id, fid, o = {}) => ({ id, fid: fac(fid), slug: id, url: 'https://x.edu/e.pdf', prova: '2099-12-13', fim: '2099-12-01', res: '2099-12-20', ini: '2099-11-01', docs: [], ...o });
    return window.TM_PLANO.ics([ed('a', 'aaa'), ed('b', 'bbb', { conf: ['resultado', 'data_prova'] })], { campos: ['fim', 'prova', 'res'], desde: '2026-11-13' });
  });
  mkdirSync('relatorios', { recursive: true });
  writeFileSync('relatorios/plano.ics', texto);
  const py = `import icalendar,sys\nc=icalendar.Calendar.from_ical(open('relatorios/plano.ics','rb').read())\nev=[e for e in c.walk('VEVENT')]\nprint('|'.join(sorted(str(e['SUMMARY'])+'='+','.join(str(a['TRIGGER'].dt) for a in e.walk('VALARM')) for e in ev)))`;
  let saida = '';
  try { saida = execFileSync('python', ['-c', py], { encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } }).trim(); } catch (e) { saida = 'ERRO ' + e.message; }
  console.log('   ' + saida);
  ok(!saida.startsWith('ERRO'), 'o .ics do plano abre na biblioteca icalendar');
  ok(/AAA X: último dia de inscrição=-7 days, 9:00:00,-2 days, 9:00:00/.test(saida), 'fim da inscrição: alarmes 7 e 2 dias antes, às 9h');
  ok(/AAA X: prova=-2 days, 9:00:00/.test(saida) && /AAA X: resultado=/.test(saida), 'prova e resultado conferidos entram');
  ok(!/BBB X: (prova|resultado)/.test(saida) && /BBB X: último dia de inscrição/.test(saida), 'prova e resultado em conferir NÃO entram no .ics; o fim conferido entra');
  ok(!/abertura|matr/i.test(saida), 'o plano leva só fim, prova e resultado');
  await ctx.close();
}

const AMBIENTES = [['celular 375', { viewport: { width: 375, height: 800 }, isMobile: true, hasTouch: true }], ['computador 1280', { viewport: { width: 1280, height: 900 } }]];
const semRolagem = (p) => p.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);
mkdirSync('screenshots', { recursive: true });

for (const [amb, op] of AMBIENTES) {
  const larg = op.viewport.width;
  console.log(`--- ${amb}`);

  // ---- 3. lista vazia
  {
    const { p, ctx, erros } = await nova(op);
    await p.goto(BASE + '/minha-lista/', { waitUntil: 'load' });
    await p.waitForSelector('#minha-lista .vazio');
    const n = await p.$$eval('#minha-lista article.cartao', (l) => l.length);
    const fins = await p.$$eval('#minha-lista article.cartao a[href*="/edital/"]', (l) => l.length);
    ok(n === 3 && fins >= 3, 'lista vazia: os 3 editais que encerram primeiro (com Salvar): ' + n);
    const rot = await p.$$eval('#minha-lista article.cartao [data-marcar]', (l) => l.map((x) => x.textContent.trim()));
    ok(rot.every((t) => t.startsWith('☆')), 'cada um com o botão Salvar');
    const ids = await p.$$eval('#minha-lista article.cartao [data-marcar]', (l) => l.map((x) => x.dataset.marcar));
    ok(JSON.stringify(ids) === JSON.stringify(dados.primeiros), 'são os 3 de prazo mais próximo e conferido: ' + ids.join(','));
    await p.screenshot({ path: `screenshots/plano-vazio-${larg}.png` });
    ok(await semRolagem(p), 'sem rolagem horizontal (vazio)');
    // salvar um deles refaz o plano na hora
    await p.click('#minha-lista article.cartao [data-marcar]');
    await p.waitForSelector('#mp-titulo');
    ok((await p.textContent('.mp-eyebrow')).includes('1 edital salvo'), 'salvar um cartão monta o plano na hora (1 edital salvo)');
    ok(erros.length === 0, 'console limpo (vazio): ' + erros.join(' | '));
    await ctx.close();
  }

  // ---- 4. plano com choque, documentos, comparar, retificação
  const escolha = [...(dados.choque || []), ...(dados.ret ? [dados.ret] : []), ...dados.semChoque].filter((v, i, a) => a.indexOf(v) === i).slice(0, 3);
  const { ctx, p, erros, medidos } = await nova(op, escolha);
  await p.goto(BASE + '/minha-lista/', { waitUntil: 'load' });
  await p.waitForSelector('#mp-titulo');
  ok((await p.textContent('.mp-eyebrow')).includes(`${escolha.length} editais salvos`), `eyebrow "Meu plano · ${escolha.length} editais salvos"`);
  ok((await p.textContent('#mp-titulo')) === 'Seus próximos prazos', 'título "Seus próximos prazos"');
  const nEv = await p.$$eval('.mp-linha li', (l) => l.length);
  ok(nEv >= escolha.length, `linha do tempo com ${nEv} datas`);
  const chips = await p.$$eval('.mp-linha li', (l) => l.map((x) => x.querySelector('.mp-dia').textContent.replace(/\s+/g, '') + ' ' + x.querySelector('p').textContent.trim() + ' | ' + x.querySelector(':scope > div small').textContent.trim()));
  console.log('   ' + chips.join('\n   '));
  const datas = await p.$$eval('.mp-linha li', (l) => l.map((x) => x.querySelector('.mp-dia').textContent.replace(/\s+/g, '')));
  ok(chips.every((c) => /faltam \d+ dias|hoje|amanhã/.test(c)), '"faltam N dias" em toda linha');
  if (dados.choque) {
    const alerta = await p.textContent('.mp-choque');
    ok(/(Duas|Três|Quatro) provas no mesmo dia/.test(alerta) && /Leia os (dois|três|quatro) editais e decida antes de pagar as (duas|três|quatro) taxas/.test(alerta), 'choque real do dia: ' + alerta.trim());
    ok((await p.$$eval('.mp-dia.mp-verm', (l) => l.length)) >= 2, 'as duas provas do choque ficam em vermelho');
  } else console.log('   (sem choque real hoje: coberto pela lógica pura)');
  ok(await p.$('#mp-agenda') !== null, 'botão "Pôr os N na minha agenda"');
  const rotulo = (await p.textContent('#mp-agenda')).trim();
  ok(/^Pôr os \d+ na minha agenda$/.test(rotulo), 'rótulo: ' + rotulo);
  // download do .ics
  const [dl] = await Promise.all([p.waitForEvent('download'), p.click('#mp-agenda')]);
  const arq = 'relatorios/plano-baixado.ics';
  await dl.saveAs(arq);
  let saida = '';
  try { saida = execFileSync('python', ['-c', `import icalendar;c=icalendar.Calendar.from_ical(open('${arq}','rb').read());print(len([e for e in c.walk('VEVENT')]))`], { encoding: 'utf8' }).trim(); } catch (e) { saida = 'ERRO'; }
  ok(/^\d+$/.test(saida) && Number(saida) >= nEv, `.ics baixado abre na icalendar com ${saida} eventos (a tela mostra ${nEv})`);
  ok(dl.suggestedFilename() === 'transfermed-meu-plano.ics', 'nome do arquivo ' + dl.suggestedFilename());
  // documentos
  const nDocs = await p.$$eval('#mp-docs-lista li', (l) => l.length);
  ok(nDocs > 0, `documentos de todos: ${nDocs} itens`);
  const pedem = await p.$$eval('#mp-docs-lista li small', (l) => l.map((x) => x.textContent));
  ok(pedem.every((t) => /^pedem \d+ de \d+$/.test(t)), 'cada item diz "pedem X de N": ' + pedem.slice(0, 3).join(' · '));
  const topo0 = (await p.textContent('#mp-docs-n')).trim();
  await p.check('#mp-docs-lista li:first-child input');
  const topo1 = (await p.textContent('#mp-docs-n')).trim();
  ok(topo0 !== topo1 && /^1 de \d+$/.test(topo1), `marcar um documento move o progresso (${topo0} → ${topo1})`);
  // o MESMO progresso no checklist de um edital que pede esse documento
  const alvo = await p.evaluate(() => { const g = window.TM_PLANO.agruparDocumentos(JSON.parse(localStorage.getItem('tm_marcados')).map((id) => window.TM.editais.find((e) => e.id === id))); const x = g[0].itens[0]; return { id: x.id, i: x.i, slug: window.TM.editais.find((e) => e.id === x.id).slug, docs: g[0].itens.length }; });
  const marcado = await p.evaluate((a) => (JSON.parse(localStorage.getItem('tm_check_' + a.id) || '[]')).includes(a.i), alvo);
  ok(marcado, 'o documento marcado no plano grava no checklist do edital (tm_check_<id>)');
  const p2 = await ctx.newPage();
  await p2.goto(`${BASE}/edital/${alvo.slug}/`, { waitUntil: 'load' });
  await p2.waitForSelector('#checklist input');
  const naFicha = await p2.$$eval('#checklist input', (l, i) => l[i] && l[i].checked, alvo.i);
  ok(naFicha === true, 'na ficha do edital o mesmo documento aparece marcado');
  // e o contrário: marcar na ficha reflete no plano
  const outro = await p2.$$eval('#checklist input', (l) => l.findIndex((x) => !x.checked));
  if (outro >= 0) { await p2.locator('#checklist input').nth(outro).check(); await p2.close();
    await p.reload({ waitUntil: 'load' }); await p.waitForSelector('#mp-titulo');
    const marcadosNoPlano = await p.$$eval('#mp-docs-lista input:checked, #mp-docs-unicos input:checked', (l) => l.length);
    ok(marcadosNoPlano >= 1, 'marcar na ficha também aparece no plano'); } else await p2.close();
  // comparar
  if (escolha.length >= 2) {
    const cols = await p.$$eval('.cp-tabela thead th', (l) => l.map((x) => x.textContent.trim()));
    ok(cols.length === escolha.length, `comparar: ${cols.length} colunas (${cols.join(', ')})`);
    const ordemSalva = await p.evaluate((ids) => ids.map((id) => window.TM_PLANO.nomeEdital(window.TM.editais.find((e) => e.id === id))), escolha);
    ok(JSON.stringify(cols) === JSON.stringify(ordemSalva), 'colunas na ordem em que foram salvos (nunca ordenadas por valor)');
    const rotulos = await p.$$eval('.cp-tabela tbody th', (l) => l.map((x) => x.textContent.trim()));
    ok(JSON.stringify(rotulos) === JSON.stringify(['Fecha', 'Taxa', 'Prova', 'Vagas', 'Exterior', 'Seleção']), 'linhas: ' + rotulos.join(', '));
    const semCor = await p.$$eval('.cp-tabela td, .cp-tabela th', (l) => l.every((x) => !/(melhor|pior|nota|ranking)/i.test(x.className + x.textContent)));
    ok(semCor, 'sem melhor/pior, nota ou ranking');
    const confs = await p.$$eval('.cp-tabela .cp-conf', (l) => l.length);
    console.log(`   células "conferir": ${confs}`);
    const rola = await p.$eval('.cp-rola', (e) => ({ pode: e.scrollWidth >= e.clientWidth, tab: e.getAttribute('tabindex') }));
    ok(rola.pode && rola.tab === '0', 'a tabela rola dentro do cartão e é alcançável pelo teclado');
    const links = await p.$$eval('.cp-tabela td a[href*="#page="]', (l) => l.map((a) => a.href));
    ok(links.every((h) => /\.pdf.*#page=\d+$/i.test(h)), `${links.length} células levam à página do PDF`);
    ok(medidos.includes('comparar_aberto'), 'medição comparar_aberto (só o nome do evento)');
  }
  ok(medidos.includes('plano_agenda'), 'medição plano_agenda');
  // retificação
  if (dados.ret && escolha.includes(dados.ret)) {
    const c = await p.$eval('.cartao-ret', (e) => ({ selo: e.querySelector('.ret-selo').textContent, riscado: e.querySelectorAll('s').length, novo: e.querySelectorAll('.ret-linha b').length, txt: e.textContent.replace(/\s+/g, ' ') }));
    ok(/^Retificado em \d\d\/\d\d$/.test(c.selo) && c.riscado >= 1 && c.novo >= 1, 'cartão "Retificado em dd/mm" com antes riscado e depois: ' + c.txt.slice(0, 120));
  }
  await p.screenshot({ path: `screenshots/plano-${larg}.png`, fullPage: true });
  ok(await semRolagem(p), 'sem rolagem horizontal (plano)');
  ok(erros.length === 0, 'console limpo (plano): ' + erros.join(' | '));
  await ctx.close();
}

// ---- 5. comparar com mais de 3 salvos: escolha de até 3
{
  const { ctx, p } = await nova({ viewport: { width: 375, height: 800 }, isMobile: true, hasTouch: true }, dados.todos.slice(0, 5));
  await p.goto(BASE + '/minha-lista/', { waitUntil: 'load' });
  await p.waitForSelector('.mp-escolha');
  ok((await p.$$eval('.mp-escolha input:checked', (l) => l.length)) === 3, 'com 5 salvos, 3 já vêm escolhidos');
  ok((await p.$$eval('.mp-escolha input:disabled', (l) => l.length)) === 2, 'os outros 2 ficam desligados até soltar um');
  const primeiro = await p.$eval('.mp-escolha input:checked', (e) => e.dataset.comparar);
  await p.click(`.mp-escolha input[data-comparar="${primeiro}"]`);
  ok((await p.$$eval('.cp-tabela thead th', (l) => l.length)) === 2, 'soltar um deixa 2 colunas');
  await p.reload({ waitUntil: 'load' }); await p.waitForSelector('.mp-escolha');
  ok((await p.$$eval('.cp-tabela thead th', (l) => l.length)) === 2, 'a escolha fica guardada no aparelho');
  await p.screenshot({ path: 'screenshots/plano-comparar-375.png', fullPage: true });
  ok(await semRolagem(p), 'sem rolagem horizontal (comparar com 5)');
  await ctx.close();
}

// ---- 6. convite do app: só com edital salvo, fechado não volta por 30 dias
{
  const { ctx, p, medidos } = await nova({ viewport: { width: 390, height: 800 }, isMobile: true, hasTouch: true }, dados.todos.slice(0, 1));
  await p.goto(BASE + '/minha-lista/', { waitUntil: 'load' });
  await p.waitForSelector('#mp-titulo');
  ok(await p.$eval('#convite-app', (e) => e.hidden), 'sem como instalar neste navegador: nenhum convite');
  await p.evaluate(() => { const ev = new Event('beforeinstallprompt', { cancelable: true }); ev.prompt = () => { window.__prompt = (window.__prompt || 0) + 1; }; ev.userChoice = Promise.resolve({ outcome: 'accepted' }); dispatchEvent(ev); });
  await p.waitForSelector('#convite-app:not([hidden])');
  ok((await p.textContent('#convite-app')).includes('Transfermed no seu celular'), 'convite aparece com o evento do navegador');
  await p.screenshot({ path: 'screenshots/plano-convite-390.png', fullPage: true });
  await p.click('#fechar-app');
  ok(await p.$eval('#convite-app', (e) => e.hidden), 'fechado, some');
  const salvo = await p.evaluate(() => JSON.parse(localStorage.getItem('tm_app') || '{}'));
  ok(Boolean(salvo.fechado), 'guarda o dia em que foi fechado (sem dado pessoal): ' + JSON.stringify(salvo));
  await p.reload({ waitUntil: 'load' }); await p.waitForSelector('#mp-titulo');
  await p.evaluate(() => { const ev = new Event('beforeinstallprompt', { cancelable: true }); ev.prompt = () => {}; ev.userChoice = Promise.resolve({}); dispatchEvent(ev); });
  await p.waitForTimeout(150);
  ok(await p.$eval('#convite-app', (e) => e.hidden), 'depois de fechar, não volta na visita seguinte');
  await p.evaluate(() => { const d = new Date(Date.now() - 31 * 864e5); localStorage.setItem('tm_app', JSON.stringify({ fechado: d.toISOString().slice(0, 10) })); });
  await p.reload({ waitUntil: 'load' }); await p.waitForSelector('#mp-titulo');
  await p.evaluate(() => { const ev = new Event('beforeinstallprompt', { cancelable: true }); ev.prompt = () => { window.__prompt = 1; }; ev.userChoice = Promise.resolve({}); dispatchEvent(ev); });
  await p.waitForSelector('#convite-app:not([hidden])');
  ok(true, 'passados 30 dias, o convite pode voltar');
  await p.click('#instalar-app');
  ok(await p.evaluate(() => window.__prompt === 1), 'o botão Instalar chama o diálogo do navegador');
  await p.evaluate(() => dispatchEvent(new Event('appinstalled')));
  await p.waitForTimeout(100);
  ok(medidos.includes('app_instalado'), 'medição app_instalado');
  await ctx.close();
  // sem edital salvo: nunca convida
  const v = await nova({ viewport: { width: 390, height: 800 } });
  await v.p.goto(BASE + '/minha-lista/', { waitUntil: 'load' });
  await v.p.waitForSelector('#minha-lista .vazio');
  await v.p.evaluate(() => { const ev = new Event('beforeinstallprompt', { cancelable: true }); ev.prompt = () => {}; ev.userChoice = Promise.resolve({}); dispatchEvent(ev); });
  await v.p.waitForTimeout(150);
  ok(await v.p.$('#convite-app') === null, 'lista vazia: não existe convite');
  await v.ctx.close();
  // iPhone (Safari): uma linha de instrução, sem botão
  const ip = await nova({ viewport: { width: 390, height: 800 }, isMobile: true, hasTouch: true, userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1' }, dados.todos.slice(0, 1));
  await ip.p.goto(BASE + '/minha-lista/', { waitUntil: 'load' });
  await ip.p.waitForSelector('#convite-app:not([hidden])');
  ok(/Compartilhar.*Adicionar à Tela de Início/.test(await ip.p.textContent('#convite-app')) && (await ip.p.$('#instalar-app')) === null, 'iPhone: "Compartilhar → Adicionar à Tela de Início", sem botão');
  await ip.ctx.close();
}

// ---- 7. sem JavaScript e com movimento reduzido
{
  const ctx = await b.newContext({ javaScriptEnabled: false, viewport: { width: 375, height: 800 } });
  const p = await ctx.newPage();
  await p.goto(BASE + '/minha-lista/', { waitUntil: 'load' });
  ok((await p.textContent('noscript')).includes('JavaScript'), 'sem JavaScript: aviso claro');
  await ctx.close();
}

await b.close();
console.log(falhas.length ? `\n${falhas.length} FALHA(S)` : '\nTudo certo.');
process.exit(falhas.length ? 1 : 0);
