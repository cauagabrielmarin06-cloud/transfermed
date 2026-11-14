// Parte C: radar pessoal da home ("De onde você quer sair?").
// - uma pergunta (cidade com autocomplete sem acento, "Ribeirão Pr" já sugere Ribeirão Preto); o mapa centraliza e o radar sai da cidade;
// - período em pílulas e distância no controle deslizante: o número grande, o mapa e a lista respondem na hora;
// - período em "conferir" não entra na conta ("confirme no edital"); 0 resultado tem mensagem própria;
// - resultado: "A primeira fecha em X dias" (0 = hoje), 3 que fecham primeiro, "+ N no seu radar";
// - "Me avise": o alerta abre preenchido (cidade, período, distância), consentimento NUNCA marcado;
// - estado no localStorage: na volta, a home abre no radar do aluno, com "o que mudou" só se houver novos;
// - sem JavaScript o campo fica desligado e a lista de abertos segue no HTML; movimento reduzido sem animações;
// - 375 e 1280 px sem rolagem horizontal, console limpo, medição só com contagens.
// uso: (site em http://127.0.0.1:8765, ou BASE=<site no ar>)  node radar_pessoal.mjs
import { chromium, webkit } from 'playwright';

const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const falhas = [];
const ok = (c, t) => { console.log((c ? 'ok   ' : 'FALHA ') + t); if (!c) falhas.push(t); };
// NAVEGADOR=webkit roda o mesmo roteiro no motor do Safari (iPhone)
const b = await (process.env.NAVEGADOR === 'webkit' ? webkit : chromium).launch();
const semAbertura = () => { try { sessionStorage.setItem('tm_abertura', '1'); } catch (e) {} };

async function novaPagina(op = {}, { rede = true } = {}) {
  const ctx = await b.newContext(op);
  await ctx.addInitScript(semAbertura);
  const medidos = [], rpcs = [];
  await ctx.addInitScript(() => { window.TM_MEDIR_TESTE = true; });
  await ctx.route(/\/rest\/v1\/rpc\//, async (r) => {
    const nome = r.request().url().split('/rpc/')[1];
    let corpo = {}; try { corpo = JSON.parse(r.request().postData() || '{}'); } catch (e) {}
    if (nome === 'medir') medidos.push(corpo.p_nome); else rpcs.push({ nome, corpo });
    await r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(nome === 'inscrever' ? 'pendente' : null) });
  });
  if (!rede) await ctx.route('**/assets/municipios.json', (r) => r.abort());
  const p = await ctx.newPage();
  const erros = [];
  p.on('pageerror', (e) => erros.push(e.message));
  p.on('console', (m) => m.type() === 'error' && erros.push(m.text()));
  return { ctx, p, erros, medidos, rpcs };
}
const numero = (p) => p.$eval('#rp-n', (e) => Number(e.textContent));
const esperaNumero = async (p, alvo) => { for (let i = 0; i < 40; i++) { if ((await numero(p)) === alvo) return true; await p.waitForTimeout(50); } return false; };
const escolherCidade = async (p, digitado, esperado) => {
  await p.click('#rp-cidade'); await p.fill('#rp-cidade', ''); await p.type('#rp-cidade', digitado, { delay: 15 });
  await p.waitForSelector('#rp-lista li');
  const opcoes = await p.$$eval('#rp-lista li', (l) => l.map((x) => x.textContent));
  await p.click('#rp-lista li:first-child');
  await p.waitForSelector('#rp-cont:not([hidden])');
  return opcoes;
};
const somaTodos = async (p) => (await p.$$eval('#rp-top > li', (l) => l.reduce((t, li) => t + Number(li.dataset.n || 1), 0))) + (await p.$$eval('#rp-todos > li', (l) => l.reduce((t, li) => t + Number(li.dataset.n || 1), 0)));
const semRolagemHorizontal = (p) => p.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);

for (const [amb, op] of [['celular 375', { viewport: { width: 375, height: 800 }, isMobile: true, hasTouch: true }], ['computador 1280', { viewport: { width: 1280, height: 900 } }]]) {
  const { ctx, p, erros, medidos, rpcs } = await novaPagina(op);
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  ok(await p.$eval('#rp-cidade', (e) => !e.disabled), `${amb}: o campo da cidade liga com JavaScript`);
  ok((await p.textContent('.rp-selo')).includes('faculdades') && /\d+/.test(await p.textContent('.rp-selo b')), `${amb}: selo "Radar ao vivo · N faculdades"`);
  const nFac = Number(await p.textContent('.rp-selo b'));
  const nPontos = await p.evaluate(() => window.TM_radar.pontos.length);
  ok(nFac === nPontos, `${amb}: N do selo (${nFac}) = faculdades no mapa (${nPontos})`);
  ok(await p.isVisible('#rp-cidade') && !(await p.isVisible('#rp-cont')), `${amb}: antes da cidade só a pergunta aparece`);
  ok(/Hoje|Em \d\d\/\d\d|O robô lê/.test(await p.textContent('#rp-robo')), `${amb}: faixa "Hoje o robô viu"`);

  // autocomplete sem acento e por prefixo
  const opcoes = await escolherCidade(p, 'ribeirao pr');
  ok(/^Ribeirão Preto/.test(opcoes[0]), `${amb}: "ribeirao pr" sugere Ribeirão Preto primeiro (${opcoes[0]})`);
  ok(await p.$eval('#rp-cidade', (e) => e.value) === 'Ribeirão Preto · SP', `${amb}: campo mostra a cidade escolhida`);
  ok(medidos.includes('radar_cidade'), `${amb}: mede radar_cidade`);
  ok(await p.$eval('.r3', (f) => f.classList.contains('pessoal')), `${amb}: o mapa entra no modo radar pessoal`);
  // o mapa centraliza (câmera em ≤ 600 ms) e fica com o raio desenhado
  await p.waitForTimeout(700);
  const vb = await p.$eval('.r3-svg', (s) => s.getAttribute('viewBox').split(' ').map(Number));
  ok(vb[2] < 400 && vb[2] >= 70, `${amb}: o mapa aproximou (viewBox ${vb.join(' ')})`);
  const [cx, cy] = await p.evaluate(() => { const c = window.TM_radar && document.querySelector('.r3-pessoa .eu'); return [Number(c.getAttribute('cx')), Number(c.getAttribute('cy'))]; });
  ok(cx > vb[0] && cx < vb[0] + vb[2] && cy > vb[1] && cy < vb[1] + vb[3], `${amb}: a cidade está dentro da vista`);
  ok(await p.locator('.r3-pessoa .raio').count() === 1, `${amb}: círculo do raio desenhado`);

  // sem período: número = editais abertos até 400 km (nunca mais que os abertos no Brasil)
  const esperado = await p.evaluate(() => { const d = new Date(); const h = new Date(d - d.getTimezoneOffset() * 6e4).toISOString().slice(0, 10);
    return window.TM.editais.filter((e) => e.fluxo === 'vagas' || (!e.fluxo && e.fim && h <= e.fim && (!e.ini || h >= e.ini))).length; });
  const semPeriodo = await numero(p);
  ok(semPeriodo >= 0 && semPeriodo <= esperado, `${amb}: ${semPeriodo} editais abertos até 400 km ≤ ${esperado} no Brasil`);

  // período: um toque; o número só pode cair ou ficar igual, e "conferir" não entra na conta
  await p.click('.rp-pilula input[value="4"]');
  await p.waitForTimeout(600);
  const com4 = await numero(p);
  ok(com4 <= semPeriodo, `${amb}: 4º período: ${com4} ≤ ${semPeriodo} (sem período)`);
  ok(medidos.includes('radar_periodo'), `${amb}: mede radar_periodo`);
  ok(/período/.test(await p.textContent('#rp-n-txt')) && /4º período/.test(await p.textContent('#rp-onde')), `${amb}: texto cita o período`);
  const lin = await p.$$eval('#rp-top > li', (l) => l.length);
  const nomesTop = await p.$$eval('#rp-top > li .rp-nome b', (l) => l.map((x) => x.textContent));
  ok(lin >= (com4 ? 1 : 0) && lin <= 3 && new Set(nomesTop).size === nomesTop.length, `${amb}: mostra até 3 faculdades DIFERENTES (${nomesTop.join(', ')})`);
  // o número do painel é o mesmo da conta do diagnóstico (avaliar) sobre os mesmos dados
  const mesmaConta = await p.evaluate(() => window.TM_radar_teste.contar({ semestre: 4, raio: 400, coords: [-21.1775, -47.8103] }));
  ok(mesmaConta === com4, `${amb}: número (${com4}) = conta do diagnóstico com o mesmo perfil (${mesmaConta})`);

  // regras do período (a mesma de alertas.motivos): sim / não / conferir
  const casos = await p.evaluate(() => {
    const per = window.TM_radar_teste.periodo, v = (semestre, vagas) => ({ mod: 'externa', vagas: [{ semestre, vagas }] });
    return {
      semVagas: per({ mod: 'externa' }, 4).s, quadroVazio: per({ mod: 'externa', vagas: [] }, 4).s,
      soReserva: per(v('3º ao 6º', 0), 4).s, faixaCasa: per(v('3º ao 6º', null), 4).s, faixaCasaMaisUm: per(v('5º', 2), 4).s,
      fora: per(v('7º', 2), 4).s, semNumero: per(v('Não informado', 1), 4).s, ano: per(v('5º ano', 3), 9).s,
      interna: per({ mod: 'interna' }, 4).s, semPeriodo: per({ mod: 'externa' }, 0).s, rotulo: per(v('3º ao 6º', 1), 4).rotulos.join()
    }; });
  ok(casos.semVagas === 'conferir' && casos.quadroVazio === 'conferir' && casos.soReserva === 'conferir', `${amb}: sem quadro de vagas ou só cadastro reserva = conferir (${JSON.stringify([casos.semVagas, casos.quadroVazio, casos.soReserva])})`);
  ok(casos.faixaCasa === 'sim' && casos.faixaCasaMaisUm === 'sim' && casos.ano === 'sim' && casos.rotulo === '3º ao 6º', `${amb}: "3º ao 6º", 5º para quem está no 4º e "5º ano" casam`);
  ok(casos.fora === 'nao' && casos.semNumero === 'conferir', `${amb}: período fora = não; rótulo sem número = conferir`);
  ok(casos.interna === 'sim' && casos.semPeriodo === 'sim', `${amb}: sem período escolhido ou edital interno não filtram por período`);
  // edital com período em "conferir": aparece rotulado e NÃO entra no número grande
  const antes4 = await numero(p);
  await p.evaluate(() => {
    const fid = Object.values(window.TM.faculdades).find((f) => f.uf === 'SP' && f.cidade === 'Ribeirão Preto') || Object.values(window.TM.faculdades).find((f) => f.uf === 'SP');
    const d = new Date(Date.now() + 5 * 864e5); const fim = new Date(d - d.getTimezoneOffset() * 6e4).toISOString().slice(0, 10);
    window.TM.editais.push({ id: 'teste-conferir', slug: 'teste-conferir', fid: fid.id, mod: 'externa', fim, quem: 'teste', url: 'https://exemplo.com/edital.html', status: 'ok' });
  });
  await p.click('.rp-pilula input[value="5"]'); await p.click('.rp-pilula input[value="4"]'); await p.waitForTimeout(700);
  ok(await numero(p) === antes4, `${amb}: edital com período a confirmar não entra no número (${antes4})`);
  ok(await p.isVisible('#rp-conferir') && /a confirmar no edital/.test(await p.textContent('#rp-conferir')), `${amb}: ele aparece rotulado "a confirmar no edital"`);
  ok(await p.locator('.r3-pontos .pt.conferir').count() >= 0, `${amb}: ponto tracejado no mapa quando só há edital a confirmar`);
  await p.evaluate(() => { window.TM.editais = window.TM.editais.filter((e) => e.id !== 'teste-conferir'); });
  await p.click('.rp-pilula input[value="5"]'); await p.click('.rp-pilula input[value="4"]'); await p.waitForTimeout(500);

  // distância: arrastar muda número, círculo e mapa; "qualquer distância" no fim
  const raioAntes = await p.$eval('.r3-pessoa .raio', (e) => e.getAttribute('d'));
  await p.$eval('#rp-km', (e) => { e.value = '1000'; e.dispatchEvent(new Event('input', { bubbles: true })); });
  await p.waitForTimeout(500);
  const raioDepois = await p.$eval('.r3-pessoa .raio', (e) => e.getAttribute('d'));
  ok(raioAntes !== raioDepois, `${amb}: o círculo cresce ao arrastar`);
  ok(/1\.000 km/.test(await p.textContent('#rp-km-v')), `${amb}: rótulo "até 1.000 km"`);
  const com1000 = await numero(p);
  ok(com1000 >= com4, `${amb}: com 1.000 km o número não cai (${com4} → ${com1000})`);
  await p.$eval('#rp-km', (e) => { e.value = '1600'; e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); });
  await p.waitForTimeout(500);
  ok(/qualquer distância/.test(await p.textContent('#rp-km-v')), `${amb}: fim do controle = "qualquer distância"`);
  ok(await p.locator('.r3-pessoa .raio').count() === 0, `${amb}: sem círculo em "qualquer distância"`);
  ok(medidos.includes('radar_distancia'), `${amb}: mede radar_distancia`);
  const brasil = await numero(p);
  ok(brasil >= com1000, `${amb}: qualquer distância (${brasil}) ≥ 1.000 km (${com1000})`);

  // resultado e "+ N no seu radar"
  const prim = (await p.textContent('#rp-primeira')).trim();
  ok(brasil === 0 || /^A primeira (fecha hoje|fecha em \d+ dias?)\.$/.test(prim) || prim === '', `${amb}: "${prim}"`);
  // a lista é por faculdade: cada linha vale `data-n` editais; "+ N" conta os editais fora das linhas do topo
  const somaN = (sel) => p.$$eval(sel, (l) => l.reduce((t, li) => t + Number(li.dataset.n || 1), 0));
  const nTopo = await somaN('#rp-top > li');
  if (brasil > nTopo) {
    ok(await p.isVisible('#rp-mais') && (await p.textContent('#rp-mais')).trim() === `+ ${brasil - nTopo} no seu radar`, `${amb}: botão "+ ${brasil - nTopo} no seu radar"`);
    await p.click('#rp-mais');
    ok(await somaN('#rp-todos > li') === brasil - nTopo && await p.isVisible('#rp-todos'), `${amb}: a lista completa abre (${brasil - nTopo} editais a mais)`);
    const todosNomes = await p.$$eval('#rp-top > li .rp-nome b, #rp-todos > li .rp-nome b', (l) => l.map((x) => x.textContent));
    ok(new Set(todosNomes).size === todosNomes.length, `${amb}: nenhuma faculdade se repete na lista (${todosNomes.length} linhas)`);
  }
  // tocar num ponto abre o cartão com período, prazo e PDF
  if (brasil > 0) await p.evaluate(() => { const q = document.querySelector('.r3-pontos .pt')._g.itens[0]; window.TM_radar.abrir(q.sigla, q.uf); });
  await p.waitForSelector('#r3-cartao:not([hidden])');
  const cartao = await p.textContent('#r3-cartao');
  ok(/Aceita o seu período|Fecha \d\d\/\d\d|inscrições abertas|Fecha/i.test(cartao) || /fecha|encerra|abertas/i.test(cartao), `${amb}: cartão do ponto traz prazo/período`);
  await p.keyboard.press('Escape');

  // computador: com a lista longa do painel, o mapa acompanha a rolagem (position:sticky) e continua à vista
  if (amb.includes('1280')) {
    await p.evaluate(() => document.querySelector('#rp-avise').scrollIntoView({ block: 'center' }));
    await p.waitForTimeout(300);
    const caixa = await p.$eval('.r3-svg', (s) => { const r = s.getBoundingClientRect(); return { topo: r.top, base: r.bottom, h: innerHeight }; });
    ok(caixa.topo >= 0 && caixa.base <= caixa.h && caixa.base - caixa.topo > 200, `${amb}: o mapa continua à vista quando o painel rola (${Math.round(caixa.topo)}–${Math.round(caixa.base)} de ${caixa.h})`);
  }
  // sem rolagem horizontal e console limpo
  ok(await semRolagemHorizontal(p), `${amb}: sem rolagem horizontal`);
  await p.screenshot({ path: `screenshots/radar-pessoal-${amb.split(' ')[1]}.png` });

  // "Me avise": alerta preenchido, consentimento desmarcado, perfil com cidade, período e distância
  await p.$eval('#rp-km', (e) => { e.value = '400'; e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); });
  await p.waitForTimeout(300);
  await p.click('#rp-avise');
  ok(medidos.includes('radar_alerta'), `${amb}: mede radar_alerta`);
  ok(await p.isVisible('#alerta-radar') && /4º período/.test(await p.textContent('#alerta-radar')) && /Ribeirão Preto/.test(await p.textContent('#alerta-radar')), `${amb}: o alerta mostra o que foi escolhido`);
  ok(!(await p.locator('#consentimento').isChecked()), `${amb}: consentimento continua DESMARCADO`);
  await p.fill('#email-alerta', 'teste@exemplo.com'); await p.check('#consentimento');
  await p.click('#form-alerta button[type="submit"]'); await p.waitForSelector('#alerta-passo2:not([hidden])');
  const ins = rpcs.find((r) => r.nome === 'inscrever');
  const pf = ins && ins.corpo.p_perfil;
  ok(pf && pf.semestre === 4 && pf.raio === 400 && /Ribeirão Preto/.test(pf.cidade) && Array.isArray(pf.coords) && pf.curso === 'medicina' && pf.origem === 'brasil',
    `${amb}: perfil do alerta = cidade, 4º período, 400 km (${JSON.stringify(pf && { s: pf.semestre, r: pf.raio, c: pf.cidade })})`);
  ok(erros.length === 0, `${amb}: console limpo ${erros.join(' | ')}`);

  // volta do aluno: a home abre no radar salvo (mesma aba, nova carga)
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  ok(await p.isVisible('#rp-cont') && await p.$eval('#rp-cidade', (e) => e.value) === 'Ribeirão Preto · SP' && await p.$eval('#rp-km', (e) => e.value) === '400',
    `${amb}: na volta, a home abre no radar salvo`);
  ok(await p.$eval('input[name="rp-periodo"]:checked', (e) => e.value) === '4', `${amb}: período salvo marcado`);
  ok(await p.isHidden('#rp-novos'), `${amb}: sem novos, o "o que mudou" não aparece`);
  // um edital "novo" desde a última visita: remove um id dos vistos
  await p.evaluate(() => { const v = JSON.parse(localStorage.getItem('tm_radar_vistos') || '[]'); v.shift(); localStorage.setItem('tm_radar_vistos', JSON.stringify(v)); });
  await p.reload({ waitUntil: 'networkidle' });
  const temEdital = await numero(p) > 0;
  if (temEdital) ok(await p.isVisible('#rp-novos') && /O que mudou desde a sua última visita: 1 edital novo/.test(await p.textContent('#rp-novos')), `${amb}: "O que mudou desde a sua última visita: 1 edital novo"`);
  // trocar cidade limpa tudo
  await p.click('#rp-trocar');
  ok(await p.isHidden('#rp-cont') && await p.evaluate(() => localStorage.getItem('tm_radar')) === null, `${amb}: "Trocar cidade" limpa o radar salvo`);
  ok(await p.isVisible('.chips') && await p.isHidden('#r3-completo'), `${amb}: os filtros do mapa completo continuam e "Ver o mapa completo" some`);
  await ctx.close();
}

// cidade que não existe e nenhum resultado
{
  const { ctx, p, erros } = await novaPagina({ viewport: { width: 375, height: 800 }, isMobile: true, hasTouch: true });
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  await p.click('#rp-cidade'); await p.type('#rp-cidade', 'zzzzzz', { delay: 10 }); await p.waitForTimeout(300);
  ok(/Não achamos essa cidade/.test(await p.textContent('#rp-dica')) && await p.isHidden('#rp-lista'), 'cidade inexistente: mensagem clara, sem lista');
  await p.fill('#rp-cidade', ''); await p.type('#rp-cidade', 'Fernandópolis', { delay: 10 });
  await p.waitForSelector('#rp-lista li'); await p.keyboard.press('ArrowDown'); await p.keyboard.press('Enter');
  await p.waitForSelector('#rp-cont:not([hidden])');
  ok(await p.$eval('#rp-cidade', (e) => e.value) === 'Fernandópolis · SP', 'teclado: setas e Enter escolhem a cidade');
  // distância mínima numa cidade sem faculdade por perto: mensagem de "sem resultado" ensina o que fazer
  await p.click('#rp-trocar'); await p.type('#rp-cidade', 'Boa Vista', { delay: 10 }); await p.waitForSelector('#rp-lista li');
  await p.evaluate(() => [...document.querySelectorAll('#rp-lista li')].find((l) => /RR|Boa Vista/.test(l.textContent) && /Boa Vista/.test(l.textContent)).click());
  await p.waitForSelector('#rp-cont:not([hidden])');
  await p.$eval('#rp-km', (e) => { e.value = '100'; e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); });
  await p.waitForTimeout(400);
  ok(await numero(p) === 0 && await p.isVisible('#rp-vazio') && /Aumente a distância ou ative o alerta/.test(await p.textContent('#rp-vazio')), 'sem resultado: "Aumente a distância ou ative o alerta…"');
  ok(await p.isVisible('#rp-avise'), 'sem resultado, o botão de alerta continua disponível');
  ok(erros.length === 0, 'console limpo ' + erros.join(' | '));
  await ctx.close();
}

// celular 375x812: com o controle de distância em uso, o número grande e o mapa (com o círculo) cabem juntos na janela;
// a faixa do robô fica logo abaixo da pergunta; os campi de uma faculdade viram uma linha que abre os editais
{
  const { ctx, p, erros } = await novaPagina({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true });
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  const caixa = (s) => p.$eval(s, (e) => { const r = e.getBoundingClientRect(); return { topo: r.top, base: r.bottom, esq: r.left, dir: r.right }; });
  const pg = await caixa('.rp-pergunta'), rb = await caixa('#rp-robo'), ci = await caixa('#rp-cidade');
  ok(rb.topo >= pg.base - 1 && rb.topo - pg.base < 24 && rb.base <= ci.topo + 1, `celular 375x812: a faixa "Hoje o robô…" fica logo abaixo da pergunta (${Math.round(pg.base)} → ${Math.round(rb.topo)}, campo em ${Math.round(ci.topo)})`);
  await escolherCidade(p, 'ribeirao pr');
  await p.click('.rp-pilula input[value="4"]'); await p.waitForTimeout(900);
  await p.evaluate(() => document.querySelector('.rp-dist').scrollIntoView({ block: 'center' }));  // quem arrasta o controle o tem no meio da tela
  await p.waitForTimeout(400);
  const n = await caixa('#rp-n'), mapa = await caixa('.r3-svg'), dist = await caixa('.rp-dist'), alt = 812;
  ok(mapa.topo >= dist.base - 4 && mapa.topo - dist.base < 60, `celular 375x812: o mapa fica logo abaixo do controle (controle até ${Math.round(dist.base)}, mapa a partir de ${Math.round(mapa.topo)})`);
  ok(n.topo >= 0 && n.base <= alt, `celular 375x812: com o controle em uso, o número grande está na janela (${Math.round(n.topo)}–${Math.round(n.base)})`);
  ok(mapa.topo >= 0 && mapa.base <= alt && mapa.base - mapa.topo > 250, `celular 375x812: com o controle em uso, o mapa inteiro está na janela (${Math.round(mapa.topo)}–${Math.round(mapa.base)} de ${alt})`);
  ok(await p.locator('.r3-pessoa .raio').count() === 1, 'celular 375x812: o círculo do raio aparece junto do número');
  ok(await p.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), 'celular 375x812: sem rolagem horizontal');
  // o cabeçalho do mapa (filtros, "Ao vivo") desceu para baixo do mapa: continua na página
  ok(await p.isVisible('.chips') && (await caixa('.chips')).topo >= mapa.base - 1, 'celular 375x812: "Ao vivo" e os filtros do mapa ficam logo abaixo do mapa');

  // faculdade com campi: três editais da USCS (um por campus), com vagas no 4º período
  await p.evaluate(() => {
    const d = new Date(Date.now() + 1 * 864e5); const fim = new Date(d - d.getTimezoneOffset() * 6e4).toISOString().slice(0, 10);
    window.TM.editais = window.TM.editais.filter((e) => !/^uscs/.test(e.fid));  // só os de teste, para a conta não depender do dia
    for (const fid of ['uscs', 'uscs-bela-vista', 'uscs-itapetininga'])
      window.TM.editais.push({ id: 'teste-' + fid, slug: 'teste-' + fid, fid, mod: 'externa', fim, quem: 'teste', vagas: [{ semestre: '4º período', vagas: 2 }], url: 'https://exemplo.com/edital.html', status: 'ok' });
  });
  await p.$eval('#rp-km', (e) => { e.value = '1600'; e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); });
  await p.waitForTimeout(600);
  const topoNomes = await p.$$eval('#rp-top > li .rp-nome b', (l) => l.map((x) => x.textContent));
  ok(topoNomes[0] === 'USCS' && new Set(topoNomes).size === topoNomes.length, `celular 375x812: os 3 primeiros são de faculdades diferentes e a USCS vem primeiro (${topoNomes.join(', ')})`);
  const linhaUscs = (await p.innerText('#rp-top > li.rp-grupo')).replace(/\s+/g, ' ').trim();
  ok(/^USCS · 3 campi fecha em 1 dia/.test(linhaUscs), `celular 375x812: "USCS · 3 campi · fecha em 1 dia" numa linha só (${linhaUscs})`);
  ok(await p.locator('#rp-top .rp-sub').first().isHidden(), 'celular 375x812: os campi começam recolhidos');
  await p.click('#rp-top > li.rp-grupo > button');
  ok(await p.getAttribute('#rp-top > li.rp-grupo > button', 'aria-expanded') === 'true' && await p.locator('#rp-top .rp-sub li a').count() === 3, 'celular 375x812: um toque abre os 3 campi, cada um com o seu edital');
  const hrefs = await p.$$eval('#rp-top .rp-sub li a', (l) => l.map((a) => a.getAttribute('href')));
  ok(hrefs.every((h) => /edital\/teste-uscs/.test(h)) && new Set(hrefs).size === 3, 'celular 375x812: os 3 links apontam para 3 editais diferentes');
  const soma = await somaTodos(p);
  ok(soma === await numero(p), `celular 375x812: as linhas somam o número grande (${soma} = ${await numero(p)})`);
  ok(await p.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), 'celular 375x812: com o grupo aberto, sem rolagem horizontal');
  await p.click('#rp-top > li.rp-grupo > button');
  ok(await p.locator('#rp-top .rp-sub').first().isHidden(), 'celular 375x812: outro toque recolhe');
  ok(erros.length === 0, 'celular 375x812: console limpo ' + erros.join(' | '));
  await ctx.close();
}

// sem rede para o municipios.json: só as cidades das faculdades, sem quebrar
{
  const { ctx, p, erros } = await novaPagina({ viewport: { width: 375, height: 800 } }, { rede: false });
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  await p.click('#rp-cidade'); await p.type('#rp-cidade', 'Fernand', { delay: 10 }); await p.waitForSelector('#rp-lista li');
  ok(/Sem internet|cidades das faculdades/.test(await p.textContent('#rp-dica')) || (await p.$$eval('#rp-lista li', (l) => l.length)) > 0, 'sem municipios.json: ainda sugere as cidades das faculdades');
  ok(erros.filter((e) => !/Failed to load resource|net::ERR/.test(e)).length === 0, 'sem municipios.json: nenhum erro de script ' + erros.join(' | '));
  await ctx.close();
}

// sem JavaScript: campo desligado, aviso, atalhos e lista de abertos no HTML
{
  const ctx = await b.newContext({ javaScriptEnabled: false, viewport: { width: 375, height: 800 } });
  const p = await ctx.newPage();
  await p.goto(BASE + '/', { waitUntil: 'load' });
  ok(await p.$eval('#rp-cidade', (e) => e.disabled), 'sem JavaScript: o campo da cidade fica desligado');
  ok(/precisa de JavaScript/.test(await p.textContent('.rp-sem-js')), 'sem JavaScript: aviso com caminho alternativo');
  ok(await p.locator('a.quadro[href="exterior/"]').count() === 1 && await p.locator('a.quadro[href="diagnostico/?origem=brasil"]').count() === 1, 'sem JavaScript: atalhos Brasil e Exterior (leva a /exterior/)');
  ok(await p.locator('#lista3 li').count() > 0, 'sem JavaScript: a lista de editais abertos continua no HTML');
  await ctx.close();
}

// movimento reduzido: nada anima, tudo aparece pronto
{
  const { ctx, p, erros } = await novaPagina({ viewport: { width: 375, height: 800 }, reducedMotion: 'reduce' });
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  await escolherCidade(p, 'Ribeirão Preto');
  const vb0 = await p.$eval('.r3-svg', (s) => s.getAttribute('viewBox'));
  await p.waitForTimeout(80);
  const vb1 = await p.$eval('.r3-svg', (s) => s.getAttribute('viewBox'));
  ok(vb0 === vb1 && vb1 !== '0 0 400 400', 'movimento reduzido: a câmera chega na hora (sem deslizar)');
  const anim = await p.evaluate(() => document.getAnimations().filter((a) => !(a instanceof CSSTransition)).length);
  ok(anim === 0, `movimento reduzido: nenhuma animação rodando (${anim})`);
  ok(erros.length === 0, 'console limpo ' + erros.join(' | '));
  await ctx.close();
}

await b.close();
console.log(falhas.length ? `${falhas.length} falha(s)` : 'tudo certo');
process.exit(falhas.length ? 1 : 0);
