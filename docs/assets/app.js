/* Transfermed: lógica do site (diagnóstico, jornada, checklist, calendário). Dados em window.TM (dados.js). */
(function () {
  'use strict';
  const TM = window.TM || {faculdades: {}, editais: []};
  const RAIZ = document.body.dataset.raiz || './';
  const $ = (s, el = document) => el.querySelector(s);

  // ---------------------------------------------------------------- utilidades
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  const norm = s => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
  const hoje = () => { const d = new Date(); return new Date(d.getTime() - d.getTimezoneOffset() * 6e4).toISOString().slice(0, 10); };
  const fmt = d => d ? d.split('-').reverse().join('/') : '?';
  const dinheiro = v => 'R$ ' + Number(v).toFixed(2).replace('.', ',');
  const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];
  const diasEntre = (a, b) => Math.round((Date.parse(b) - Date.parse(a)) / 864e5);
  // eventos do funil, sem cookies: o Supabase só soma 1 em (dia, evento, tipo de página). Nada de IP, identificador
  // ou endereço completo. Mede só no site publicado (ou no teste do funil, que liga window.TM_MEDIR_TESTE).
  const medir = nome => {
    try {
      const cfg = window.TM_CONFIG || {};
      if (!cfg.supabaseUrl || !cfg.supabaseAnon) return;
      if (!/(^|\.)transfermed\.com\.br$/.test(location.hostname) && !window.TM_MEDIR_TESTE) return;
      const cab = {apikey: cfg.supabaseAnon, 'Content-Type': 'application/json'};
      if (cfg.supabaseAnon.startsWith('eyJ')) cab.Authorization = `Bearer ${cfg.supabaseAnon}`;
      fetch(`${cfg.supabaseUrl}/rest/v1/rpc/medir`, {method: 'POST', headers: cab, keepalive: true,
        body: JSON.stringify({p_nome: nome, p_pagina: document.body.dataset.pagina || 'outra'})}).catch(() => {});
    } catch (e) { /* medição nunca quebra o site */ }
  };

  // cópia em memória: navegadores que bloqueiam o armazenamento (aba anônima, navegador do Instagram/WhatsApp)
  // ainda guardam o perfil enquanto a página estiver aberta, e o alerta funciona
  const memoria = {};
  const armazem = {
    ler(chave, padrao) {
      try { const v = localStorage.getItem(chave); if (v) return JSON.parse(v); } catch (e) { /* sem armazenamento */ }
      return chave in memoria ? memoria[chave] : padrao;
    },
    gravar(chave, valor) { memoria[chave] = valor; try { localStorage.setItem(chave, JSON.stringify(valor)); } catch (e) { /* idem */ } },
    apagar(chave) { delete memoria[chave]; try { localStorage.removeItem(chave); } catch (e) { /* idem */ } }
  };

  const MODALIDADES = {
    externa: ['Transferência externa', 'Para quem cursa Medicina em outra faculdade'],
    interna: ['Transferência interna', 'Para quem já estuda outro curso nesta faculdade'],
    exterior: ['Para quem estuda no exterior', 'Edital próprio para alunos de faculdades estrangeiras'],
    portador_diploma: ['Outro curso da saúde ou diplomado', 'Para aluno de outro curso da saúde ou formado na área'],
    ex_officio: ['Ex officio', 'Transferência obrigatória por lei']
  };

  // situação calculada no dia da visita (o site pode ser aberto dias depois da última atualização)
  function situacao(e) {
    if (e.fluxo) return 'contínuo';
    const h = hoje();
    if (!e.fim) return e.sit === 'encerrado' ? 'encerrado' : 'desconhecida';
    if (h > e.fim) return 'encerrado';
    if (e.ini && h < e.ini) return 'em breve';
    return 'aberto';
  }
  const ORDEM = {'aberto': 0, 'em breve': 1, 'contínuo': 2, 'desconhecida': 3, 'encerrado': 4};

  // urgência real, calculada das datas do edital
  function urgencia(e) {
    const s = situacao(e);
    if (s === 'aberto') {
      const d = diasEntre(hoje(), e.fim);
      if (d <= 2) return {cls: 'alerta', txt: d <= 0 ? 'Encerra hoje' : `Encerra em ${d === 1 ? '1 dia' : '2 dias'}`};
      if (d <= 10) return {cls: 'aviso', txt: `Inscrições encerram em ${d} dias`};
      return {cls: 'ok', txt: `Inscrições abertas até ${fmt(e.fim)}`};
    }
    if (s === 'em breve') return {cls: 'aviso', txt: `Inscrições abrem em ${fmt(e.ini)}`};
    if (s === 'contínuo') return {cls: 'ok', txt: 'Pedidos o ano todo (sem edital)'};
    if (s === 'encerrado') return {cls: '', txt: `Encerrado${e.fim ? ' em ' + fmt(e.fim) : ''}`};
    return {cls: '', txt: 'Datas no edital'};
  }

  function km(a, b) {
    const R = 6371, rad = x => x * Math.PI / 180;
    const dLa = rad(b[0] - a[0]), dLo = rad(b[1] - a[1]);
    const h = Math.sin(dLa / 2) ** 2 + Math.cos(rad(a[0])) * Math.cos(rad(b[0])) * Math.sin(dLo / 2) ** 2;
    return Math.round(2 * R * Math.asin(Math.sqrt(h)));
  }

  // "3º ao 6º", "5º ano", "2ª série", "1º ao 6º termo" -> semestres
  function semestresDaVaga(rotulo) {
    const txt = String(rotulo || '');
    const nums = (txt.match(/\d+/g) || []).map(Number);
    if (!nums.length) return null;
    let lista = nums;
    if (nums.length >= 2 && /\s(ao?|até)\s|[-–]/i.test(txt)) { lista = []; for (let i = nums[0]; i <= nums[1]; i++) lista.push(i); }
    return /s[ée]rie|ano/i.test(txt) ? lista.flatMap(n => [2 * n - 1, 2 * n]) : lista;
  }

  // ---------------------------------------------------------------- compatibilidade
  // "UB" não pode casar com "Universidade de Uberaba (UNIUBE)": compara a sigla inteira ou um trecho longo do nome
  const GENERICAS = new Set(['universidade', 'universitario', 'universitaria', 'centro', 'faculdade', 'faculdades', 'escola',
    'instituto', 'medicina', 'ciencias', 'saude', 'campus', 'de', 'da', 'do', 'das', 'dos', 'e', 'a', 'o', 'uni', 'federal', 'estadual']);
  function mesmaFaculdade(digitado, f) {
    const q = norm(digitado);
    if (!q || !f.nome) return false;
    const nome = norm(f.nome), sigla = norm(f.sigla);
    if (q === sigla || q === nome) return true;
    const tokensNome = new Set(nome.split(/[^a-z0-9]+/).filter(Boolean));
    const significativas = q.split(/[^a-z0-9]+/).filter(t => t.length >= 3 && !GENERICAS.has(t));
    return significativas.length > 0 && significativas.every(t => tokensNome.has(t));
  }

  function avaliar(e, p) {
    const f = TM.faculdades[e.fid] || {};
    const motivos = [];
    const mesma = mesmaFaculdade(p.faculdade, f);
    const mod = e.mod || 'externa';
    if (p.curso === 'saude') {
      if (mod === 'externa' || mod === 'exterior') motivos.push('exige estar cursando Medicina');
      if (mod === 'interna' && !mesma) motivos.push('transferência interna: só para alunos desta faculdade');
    } else {
      if (mod === 'portador_diploma') motivos.push('para quem é de outro curso da saúde ou já formado');
      if (mod === 'interna') motivos.push('para alunos de outro curso desta faculdade');
    }
    if (p.origem === 'exterior' && e.ext === false) motivos.push('não aceita quem estuda no exterior');
    if (p.origem === 'brasil' && mod === 'exterior') motivos.push('edital só para quem estuda no exterior');
    if (p.transferiu === 'sim' && e.exc === true) motivos.push('não aceita quem já fez transferência');
    if (mesma && mod !== 'interna') motivos.push('é a sua faculdade atual');
    if (p.tipo !== 'todas' && f.tipo) {
      const publica = f.tipo.startsWith('pública');
      if ((p.tipo === 'publica') !== publica) motivos.push(`é ${f.tipo}`);
    }
    if (p.curso === 'medicina' && (mod === 'externa' || mod === 'exterior') && Array.isArray(e.vagas) && e.vagas.length && p.semestre) {
      const alvo = [p.semestre, p.semestre + 1];
      const comVaga = e.vagas.filter(v => v.vagas !== 0);
      if (comVaga.length && !comVaga.some(v => { const ss = semestresDaVaga(v.semestre); return ss === null || ss.some(s => alvo.includes(s)); }))
        motivos.push(`sem vagas para quem está no ${p.semestre}º semestre`);
    }
    if (p.taxaMax != null && e.taxa != null && e.taxa > p.taxaMax) motivos.push(`taxa de ${dinheiro(e.taxa)} acima do seu limite`);
    const dist = p.coords && f.lat != null ? km(p.coords, [f.lat, f.lon]) : null;
    if (dist != null && p.raio && dist > p.raio) motivos.push(`fica a ${dist.toLocaleString('pt-BR')} km (acima de ${p.raio} km)`);
    return {motivos, dist};
  }

  function ordenar(lista) {
    const dist = x => (x.r && x.r.dist != null ? x.r.dist : 1e9);
    return lista.sort((a, b) => (ORDEM[situacao(a.e)] - ORDEM[situacao(b.e)]) || (dist(a) - dist(b)) || String(a.e.fim).localeCompare(String(b.e.fim)));
  }

  // distância em texto: a faculdade da própria cidade é "na sua cidade", não "0 km"
  const textoKm = d => d < 5 ? 'na sua cidade' : `${d.toLocaleString('pt-BR')} km de você`;

  // ---------------------------------------------------------------- cartão de edital
  function textoVagas(e) {
    if (!Array.isArray(e.vagas) || !e.vagas.length) return 'Vagas: confira no edital';
    // "2º ao 7º" -> "do 2º ao 7º"; "5º ano" -> "no 5º ano" (mesma regra do gerar_site.no_semestre)
    const no = s => /^n[aã]o informado$/i.test(String(s || '').trim()) ? ''
      : !s || !/^\d/.test(s) ? `: ${s || 'confira no edital'}` : (s.includes(' ao ') ? ' do ' : ' no ') + s;
    return e.vagas.filter(v => v.vagas !== 0).map(v => v.vagas ? `${v.vagas} ${v.vagas === 1 ? 'vaga' : 'vagas'}${no(v.semestre)}` : `vagas${no(v.semestre)}`).join(' · ') || 'Só cadastro reserva';
  }

  function cartao(e, r) {
    const f = TM.faculdades[e.fid] || {};
    const [modNome, modQuem] = MODALIDADES[e.mod] || MODALIDADES.externa;
    const u = urgencia(e);
    const dist = r && r.dist != null ? ` · <strong>${textoKm(r.dist)}</strong>` : '';
    const marcado = (armazem.ler('tm_marcados', [])).includes(e.id);
    return `<article class="cartao">
      <h3><a href="${RAIZ}edital/${esc(e.slug)}/">${esc(f.nome)}</a></h3>
      <div class="local">${esc(f.cidade)}/${esc(f.uf)} · ${esc(f.tipo)}${dist}</div>
      <p class="quem"><strong>${modNome}:</strong> ${esc(e.quem || modQuem)}</p>
      <div class="etiquetas">
        <span class="et ${u.cls}">${u.txt}</span>
        ${r && !r.motivos.length && ['aberto', 'em breve'].includes(situacao(e)) ? '<span class="et ok">você atende</span>' : ''}
        ${e.sem ? `<span class="et">ingresso ${esc(e.sem)}</span>` : ''}
        ${e.taxa != null ? `<span class="et">${e.taxa === 0 ? 'inscrição gratuita' : 'taxa ' + dinheiro(e.taxa)}</span>` : ''}
        ${e.status === 'conferir' ? '<span class="et aviso">tem aviso: veja o resumo</span>' : ''}
      </div>
      <div class="pequeno">${esc(e.fluxo ? 'Vagas: confirme com a faculdade' : textoVagas(e))}</div>
      ${r && r.motivos.length ? `<ul class="nao">${r.motivos.map(m => `<li>${esc(m)}</li>`).join('')}</ul>` : ''}
      <div class="rodape-cartao">
        <a href="${RAIZ}edital/${esc(e.slug)}/">Ver resumo e documentos</a>
        <a href="${esc(e.url)}" target="_blank" rel="noopener">${e.fluxo ? 'Página oficial' : 'Edital oficial'}<span class="oculto"> (abre em nova aba)</span></a>
        <button type="button" class="botao sec peq" data-marcar="${esc(e.id)}" aria-pressed="${marcado}">${marcado ? ROTULO_SALVO : ROTULO_SALVAR}</button>
      </div>
    </article>`;
  }

  // ---------------------------------------------------------------- minha lista (estrela; só no navegador)
  const ROTULO_SALVO = '★ Na minha lista', ROTULO_SALVAR = '☆ Salvar na minha lista';
  function contarLista() {
    const n = armazem.ler('tm_marcados', []).filter(id => TM.editais.some(e => e.id === id)).length;
    document.querySelectorAll('.lista-n').forEach(el => { el.textContent = n; el.hidden = !n; });
    document.querySelectorAll('.lista-icone').forEach(a => a.setAttribute('aria-label', n ? `Minha lista: ${n} ${n === 1 ? 'edital salvo' : 'editais salvos'}` : 'Minha lista'));
  }
  function alternarMarcado(id) {
    const m = armazem.ler('tm_marcados', []);
    const i = m.indexOf(id);
    if (i >= 0) m.splice(i, 1); else m.push(id);
    armazem.gravar('tm_marcados', m);
    return i < 0;
  }
  document.addEventListener('click', ev => {
    const b = ev.target.closest('[data-marcar]');
    if (!b) return;
    const agora = alternarMarcado(b.dataset.marcar);
    document.querySelectorAll(`[data-marcar="${CSS.escape(b.dataset.marcar)}"]`).forEach(o => {
      o.setAttribute('aria-pressed', agora);
      o.textContent = agora ? ROTULO_SALVO : ROTULO_SALVAR;
    });
    if (agora) medir('salvar_lista');
    contarLista();
  });
  // eventos simples do funil marcados no HTML (data-medir="abrir_pdf" etc.)
  document.addEventListener('click', ev => { const a = ev.target.closest('[data-medir]'); if (a) medir(a.dataset.medir); });

  function compativeis(p) {
    return TM.editais.map(e => ({e, r: avaliar(e, p)})).filter(x => !x.r.motivos.length);
  }

  // ---------------------------------------------------------------- calendário .ics
  function ics(editais) {
    const d8 = s => s.replace(/-/g, '');
    const mais1 = s => { const d = new Date(s + 'T12:00:00'); d.setDate(d.getDate() + 1); return d.toISOString().slice(0, 10); };
    const txt = s => String(s).replace(/([,;\\])/g, '\\$1');
    const stamp = new Date().toISOString().replace(/[-:]/g, '').slice(0, 15) + 'Z';
    const ev = [];
    const evento = (id, ini, fim, titulo, e, alarme) => ev.push(['BEGIN:VEVENT', `UID:${id}@transfermed`, `DTSTAMP:${stamp}`,
      `DTSTART;VALUE=DATE:${d8(ini)}`, `DTEND;VALUE=DATE:${d8(fim)}`, `SUMMARY:${txt(titulo)}`,
      `DESCRIPTION:${txt('Confira sempre o edital oficial: ' + e.url)}`, `URL:${e.url}`,
      ...(alarme ? ['BEGIN:VALARM', 'ACTION:DISPLAY', `DESCRIPTION:${txt(titulo)}`, 'TRIGGER:-P3D', 'END:VALARM'] : []), 'END:VEVENT'].join('\r\n'));
    for (const e of editais) {
      const nome = (TM.faculdades[e.fid] || {}).sigla || 'Medicina';
      if (e.ini && e.fim) evento(`${e.id}-insc`, e.ini, mais1(e.fim), `Inscrições abertas: transferência ${nome}`, e, false);
      if (e.fim) evento(`${e.id}-fim`, e.fim, mais1(e.fim), `Último dia de inscrição: ${nome}`, e, true);
      if (e.prova) evento(`${e.id}-prova`, e.prova, mais1(e.prova), `Prova de transferência: ${nome}`, e, true);
    }
    // linhas com mais de 75 bytes continuam na seguinte, começando com espaço (regra do formato .ics)
    const dobrar = l => { const out = []; let at = ''; for (const c of l) { if (new TextEncoder().encode(at + c).length > (out.length ? 74 : 75)) { out.push(at); at = ''; } at += c; } out.push(at); return out.join('\r\n '); };
    return ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Transfermed//Radar//PT', 'CALSCALE:GREGORIAN', ...ev, 'END:VCALENDAR']
      .join('\r\n').split('\r\n').map(dobrar).join('\r\n') + '\r\n';
  }
  function baixarIcs(editais, nome) {
    const url = URL.createObjectURL(new Blob([ics(editais)], {type: 'text/calendar'}));
    const a = Object.assign(document.createElement('a'), {href: url, download: nome});
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  // "Assinar meus prazos": cada faculdade tem um calendário para assinar (faculdade/<id>/prazos.ics) que se atualiza
  // sozinho, inclusive com o próximo edital. O .ics avulso fica como opção discreta (não se atualiza).
  function painelAssinar(editais, id) {
    const fids = [...new Set(editais.filter(e => e.fim || e.prova).map(e => e.fid))].filter(f => TM.faculdades[f]);
    if (!fids.length) return '';
    const links = fids.map(f => {
      const https = new URL(`${RAIZ}faculdade/${f}/prazos.ics`, location.href).href;
      const webcal = https.replace(/^https?:/, 'webcal:');
      return `<li><a href="${esc(webcal)}" data-medir="assinar_agenda">Assinar ${esc(TM.faculdades[f].sigla)}</a>
        · <a href="https://calendar.google.com/calendar/r?cid=${encodeURIComponent(webcal)}" target="_blank" rel="noopener" data-medir="assinar_agenda">no Google Agenda<span class="oculto"> (abre em nova aba)</span></a></li>`;
    }).join('');
    return `<details class="agenda-ajuda" id="${id}"><summary>Assinar meus prazos (${fids.length} ${fids.length === 1 ? 'faculdade' : 'faculdades'})</summary>
      <p>Cada assinatura se atualiza sozinha quando o edital muda ou a faculdade publica edital novo.</p>
      <ul>${links}</ul>
      <p class="dica">iPhone: toque em "Assinar" e confirme. Google: use o link "no Google Agenda" e toque em "Adicionar". Outlook: Adicionar calendário › Da Internet › cole o endereço do link "Assinar".
      Prefere um arquivo? <button type="button" class="link-botao" data-baixar-ics>Baixar .ics</button> (não se atualiza).</p></details>`;
  }
  function ligarPainelAssinar(raizEl, editais, nome) {
    const b = raizEl && raizEl.querySelector('[data-baixar-ics]');
    if (b) b.addEventListener('click', () => { baixarIcs(editais.filter(e => e.fim || e.prova), nome); medir('adicionar_agenda'); });
  }

  // ---------------------------------------------------------------- mapa-radar
  // mesma projeção do gerar_site.py: x = (lon + 74) * 10 ; y = (6 - lat) * 10
  const proj = (lat, lon) => [(lon + 74) * 10, (6 - lat) * 10];
  const NS = 'http://www.w3.org/2000/svg';

  function situacaoFaculdade(fid) {
    let melhor = 'neutro';
    for (const e of TM.editais) {
      if (e.fid !== fid) continue;
      const s = situacao(e);
      if (s === 'aberto' || s === 'contínuo') return 'aberto';
      if (s === 'em breve') melhor = 'breve';
    }
    return melhor;
  }

  function ajustarPontos(svg) {
    const vb = svg.viewBox.baseVal;
    const r = Math.max(1.6, Math.min(6, vb.width / 70));
    svg.querySelectorAll('.ponto circle').forEach(c => c.setAttribute('r', r));
    svg.querySelectorAll('.aneis circle').forEach(c => c.style.strokeWidth = vb.width / 300);
    const voce = svg.querySelector('.voce');
    if (voce) { voce.querySelector('circle').setAttribute('r', r * 1.15); voce.querySelector('text').style.fontSize = (vb.width / 38) + 'px'; voce.querySelector('text').setAttribute('dy', -r * 1.8); }
  }

  function prepararMapa(fig) {
    const svg = fig.querySelector('svg');
    // situação recalculada no dia da visita
    svg.querySelectorAll('.ponto').forEach(a => { a.classList.remove('aberto', 'breve', 'neutro'); a.classList.add(situacaoFaculdade(a.dataset.fid)); });
    const p = armazem.ler('tm_perfil', null);
    if (p && p.coords) {
      const [x, y] = proj(p.coords[0], p.coords[1]);
      const voce = svg.querySelector('.voce');
      voce.setAttribute('transform', `translate(${x.toFixed(1)} ${y.toFixed(1)})`);
      voce.hidden = false;
      svg.querySelector('.aneis').setAttribute('transform', `translate(${x.toFixed(1)} ${y.toFixed(1)})`);
      // a visão regional passa a ser centrada em quem está vendo (quem mora na Bahia vê a Bahia)
      const regiao = fig.querySelector('[data-perto]');
      const [w, h] = [150, 140];
      const vx = Math.min(Math.max(x - w / 2, 0), 400 - w), vy = Math.min(Math.max(y - h / 2, 0), 400 - h);
      regiao.dataset.vista = `${vx.toFixed(1)} ${vy.toFixed(1)} ${w} ${h}`;
      regiao.hidden = false;
    }
    fig.querySelectorAll('[data-vista]').forEach(b => b.addEventListener('click', () => {
      svg.setAttribute('viewBox', b.dataset.vista);
      fig.querySelectorAll('[data-vista]').forEach(o => o.setAttribute('aria-pressed', o === b));
      ajustarPontos(svg);
    }));
    ajustarPontos(svg);
  }
  document.querySelectorAll('figure.radar').forEach(prepararMapa);

  // minimapa do resultado: só as faculdades compatíveis + você
  function miniMapa(itens, coords) {
    const pts = itens.map(x => { const f = TM.faculdades[x.e.fid]; return {f, xy: proj(f.lat, f.lon), cls: ['aberto', 'contínuo'].includes(situacao(x.e)) ? 'aberto' : 'breve'}; });
    const todos = pts.map(p => p.xy).concat(coords ? [proj(coords[0], coords[1])] : []);
    if (!todos.length) return '';
    const xs = todos.map(p => p[0]), ys = todos.map(p => p[1]);
    let [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const lado = Math.max(60, x1 - x0, y1 - y0) * 1.25;
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    const vb = `${(cx - lado / 2).toFixed(1)} ${(cy - lado / 2).toFixed(1)} ${lado.toFixed(1)} ${lado.toFixed(1)}`;
    const r = Math.max(1.4, Math.min(4.2, lado / 70));
    const vistos = {};
    const circulos = pts.map(p => {
      const k = p.xy.map(v => v.toFixed(0)).join(','); const n = vistos[k] = (vistos[k] || 0) + 1;
      const dx = n > 1 ? [0, r * 1.6, -r * 1.6, 0, 0][n % 5] : 0, dy = n > 1 ? [0, 0, 0, r * 1.6, -r * 1.6][n % 5] : 0;
      return `<a href="${RAIZ}faculdade/${esc(p.f.id)}/" class="ponto ${p.cls}"><circle cx="${(p.xy[0] + dx).toFixed(1)}" cy="${(p.xy[1] + dy).toFixed(1)}" r="${r}"/><title>${esc(p.f.sigla)} (${esc(p.f.cidade)})</title></a>`;
    }).join('');
    const voce = coords ? (() => { const [x, y] = proj(coords[0], coords[1]); return `<g class="voce" aria-hidden="true" transform="translate(${x.toFixed(1)} ${y.toFixed(1)})"><circle r="${r * 1.15}"/><text dy="${-r * 1.8}" style="font-size:${lado / 30}px">você</text></g>`; })() : '';
    return `<figure class="radar mini"><svg viewBox="${vb}" role="group" aria-label="Mapa das faculdades em que você atende aos requisitos" class="radar-svg"><use href="${RAIZ}assets/brasil.svg#br" class="br" x="0" y="0" width="400" height="400" aria-hidden="true"/><g class="pontos">${circulos}</g>${voce}</svg>
      <figcaption class="legenda"><span><i class="l-aberto"></i>Aberto</span><span><i class="l-breve"></i>Abre em breve</span>${coords ? '<span><i class="l-voce"></i>Você</span>' : ''}</figcaption></figure>`;
  }

  // ---------------------------------------------------------------- compartilhar
  document.addEventListener('click', async ev => {
    const b = ev.target.closest('[data-compartilhar]');
    if (!b) return;
    const texto = b.closest('.compartilhar').dataset.texto;
    const url = location.href.split('#')[0];
    if (navigator.share) { try { await navigator.share({title: document.title, text: texto, url}); return; } catch (e) { if (e.name === 'AbortError') return; } }
    const caixa = b.closest('.compartilhar');
    let menu = caixa.querySelector('.menu-compartilhar');
    if (menu) { menu.remove(); return; }
    menu = document.createElement('div');
    menu.className = 'menu-compartilhar';
    menu.innerHTML = `<a href="https://wa.me/?text=${encodeURIComponent(texto + ' ' + url)}" target="_blank" rel="noopener" data-medir="compartilhar_whatsapp">WhatsApp</a><button type="button" data-copiar>Copiar link</button>`;
    caixa.appendChild(menu);
    menu.querySelector('[data-copiar]').addEventListener('click', async e2 => {
      try { await navigator.clipboard.writeText(url); e2.target.textContent = 'Link copiado ✓'; } catch (_) { e2.target.textContent = url; }
    });
  });

  // ---------------------------------------------------------------- página: início
  function paginaInicio() {
    const caixa = $('#jornada');
    const p = armazem.ler('tm_perfil', null);
    const marcados = armazem.ler('tm_marcados', []).map(id => TM.editais.find(e => e.id === id)).filter(Boolean);
    if (!caixa) return;
    if (!p && !marcados.length) return;
    let html = '<h2 id="titulo-jornada">Minha jornada</h2>';
    if (p) {
      const vivos = compativeis(p).filter(x => ['aberto', 'em breve', 'contínuo'].includes(situacao(x.e)));
      const vistos = armazem.ler('tm_vistos', []);
      const novos = vivos.filter(x => !vistos.includes(x.e.id));
      html += novos.length
        ? `<div class="ok-caixa"><strong>${novos.length} ${novos.length === 1 ? 'edital novo compatível' : 'editais novos compatíveis'} com você</strong> desde a sua última visita.</div>`
        : `<p class="sub">Nada novo desde a sua última visita. Hoje há ${vivos.length} ${vivos.length === 1 ? 'edital aberto ou abrindo' : 'editais abertos ou abrindo'} para o seu perfil.</p>`;
      html += ordenar(novos.length ? novos : vivos).slice(0, 3).map(x => cartao(x.e, x.r)).join('');
      armazem.gravar('tm_vistos', vivos.map(x => x.e.id));
      html += `<p class="acoes"><a class="botao peq" href="${RAIZ}diagnostico/#resultado">Ver meu diagnóstico completo</a></p>`;
    }
    if (marcados.length) {
      html += `<h3 class="espaco-24">Minha lista</h3>`;
      html += marcados.map(e => {
        const docs = armazem.ler('tm_check_' + e.id, []).length, total = (e.docs || []).length;
        const u = urgencia(e), f = TM.faculdades[e.fid] || {};
        return `<div class="cartao"><h3><a href="${RAIZ}edital/${esc(e.slug)}/">${esc(f.nome)}</a></h3>
          <div class="etiquetas"><span class="et ${u.cls}">${u.txt}</span>${total ? `<span class="et">documentos: ${docs} de ${total}</span>` : ''}</div></div>`;
      }).join('');
      html += '<p class="acoes"><button type="button" class="botao sec peq" id="cal-jornada">Baixar calendário com todos os prazos</button></p>';
    }
    html += '<p class="dica">Seus dados ficam só neste navegador. <button type="button" class="linkbtn" id="apagar">Apagar meus dados</button></p>';
    caixa.innerHTML = html;
    caixa.hidden = false;
    const cal = $('#cal-jornada');
    if (cal) cal.addEventListener('click', () => baixarIcs(marcados, 'transfermed-prazos.ics'));
    $('#apagar').addEventListener('click', () => {
      Object.keys(localStorage).filter(k => k.startsWith('tm_')).forEach(k => armazem.apagar(k));
      caixa.innerHTML = '<p class="ok-caixa">Pronto: seus dados foram apagados deste navegador.</p>';
    });
  }

  // ---------------------------------------------------------------- página: diagnóstico
  function paginaDiagnostico() {
    const form = $('#diag');
    if (!form) return;
    const etapas = [...form.querySelectorAll('.etapa')];
    const barra = $('#barra'), passoTxt = $('#passo-txt');
    let atual = 0;
    let cidades = new Map((window.CAPITAIS || []).map(([n, uf, la, lo]) => [`${n} - ${uf}`, [la, lo]]));
    const lista = $('#lista-cidades');
    const preencherCidades = () => { lista.innerHTML = [...cidades.keys()].sort((a, b) => a.localeCompare(b, 'pt')).map(c => `<option value="${esc(c)}">`).join(''); };
    preencherCidades();
    let carregando = null;
    // lista completa de municípios, hospedada no próprio site (só baixa quando o aluno chega na etapa da cidade)
    const carregarCidades = () => carregando || (carregando = fetch(RAIZ + 'assets/municipios.json')
      .then(r => r.json())
      .then(js => { cidades = new Map(js.map(([n, uf, la, lo]) => [`${n} - ${uf}`, [la, lo]])); preencherCidades(); })
      .catch(() => { $('#dica-cidade').textContent = 'Sem internet: só as capitais estão disponíveis. Escolha a mais próxima.'; }));
    $('#cidade').addEventListener('focus', carregarCidades);
    // "palmas", "Palmas TO", "palmas/to" ou "Palmas - TO". Nome repetido em mais de um estado (Palmas, Bom Jesus,
    // Rio Branco) nunca é adivinhado: a pessoa escolhe, senão a distância sairia errada em milhares de km
    const simples = s => norm(s).replace(/[^a-z0-9]+/g, ' ').trim();
    const nomeDe = k => k.slice(0, k.lastIndexOf(' - '));
    const ufDe = k => k.slice(k.lastIndexOf(' - ') + 3).toLowerCase();
    const resolverCidade = c => {
      if (cidades.has(c)) return {chave: c};
      const q = simples(c), chaves = [...cidades.keys()];
      let achadas = chaves.filter(k => simples(nomeDe(k)) === q);
      const comUf = q.match(/^(.+) ([a-z]{2})$/);
      if (!achadas.length && comUf) achadas = chaves.filter(k => simples(nomeDe(k)) === comUf[1] && ufDe(k) === comUf[2]);
      if (!achadas.length && q.length >= 4) achadas = chaves.filter(k => simples(nomeDe(k)).startsWith(q));
      if (achadas.length === 1) return {chave: achadas[0]};
      if (achadas.length > 1 && achadas.length <= 8) return {opcoes: achadas.sort((a, b) => a.localeCompare(b, 'pt'))};
      return {};
    };
    const acharCidade = c => cidades.get(resolverCidade(c).chave) || null;
    // a distância só faz sentido com uma cidade: sem ela, o campo fica desligado e vale "qualquer distância"
    const raio = form.elements.raio;
    const atualizarRaio = () => {
      raio.disabled = !form.elements.cidade.value.trim();
      $('#dica-raio').hidden = !raio.disabled;
    };
    form.elements.cidade.addEventListener('input', atualizarRaio);
    // a lista de sugestões acompanha a resposta "onde você estuda": faculdades da base ou do exterior
    const campoFac = $('#faculdade');
    const atualizarFaculdades = () => {
      const fora = form.elements.origem.value === 'exterior';
      const nomes = fora ? (TM.exterior || []) : Object.values(TM.faculdades).map(f => f.nome);
      $('#lista-facul').innerHTML = nomes.map(n => `<option value="${esc(n)}">`).join('');
      campoFac.placeholder = fora ? 'Ex.: Universidad Central del Paraguay' : 'Ex.: Universidade Brasil';
      $('#dica-faculdade').textContent = fora
        ? 'Escolha da lista ou escreva o nome. Fica guardado no seu perfil; o resultado não depende dele.'
        : 'Serve para não sugerir a sua própria faculdade e para achar transferência interna.';
    };
    // trocou Brasil <-> exterior: faculdade escolhida da outra lista sai do campo (senão o perfil fica incoerente e uma
    // faculdade brasileira esquecida no campo esconderia os editais dela de quem estuda fora)
    const doBrasil = new Set(Object.values(TM.faculdades).map(f => f.nome));
    const doExterior = new Set(TM.exterior || []);
    for (const r of form.elements.origem) r.addEventListener('change', () => {
      const outra = form.elements.origem.value === 'exterior' ? doBrasil : doExterior;
      if (outra.has(campoFac.value.trim())) campoFac.value = '';
      atualizarFaculdades();
    });
    const sem = $('#semestre');
    for (let i = 1; i <= 12; i++) sem.add(new Option(i + 'º semestre', i));

    // perfil salvo volta preenchido
    const salvo = armazem.ler('tm_perfil', null);
    if (salvo) {
      for (const [k, v] of Object.entries(salvo)) {
        const campos = form.elements[k];
        if (!campos || v == null) continue;
        if (campos instanceof RadioNodeList) { for (const c of campos) c.checked = c.value === String(v); } else campos.value = v;
      }
    }
    form.elements.curso.value = 'medicina';  // por enquanto o diagnóstico é só para quem cursa Medicina
    // porta de entrada do início (?origem=brasil|exterior): a primeira pergunta já vem respondida
    const porta = new URLSearchParams(location.search).get('origem');
    if (porta === 'brasil' || porta === 'exterior') for (const c of form.elements.origem) c.checked = c.value === porta;
    atualizarFaculdades();
    atualizarRaio();

    function mostrar(i) {
      etapas.forEach((el, j) => el.classList.toggle('ativa', j === i));
      atual = i;
      barra.style.width = `${((i + 1) / etapas.length) * 100}%`;
      barra.parentElement.setAttribute('aria-valuenow', i + 1);
      passoTxt.textContent = `Etapa ${i + 1} de ${etapas.length}`;
      $('#passo-nome').textContent = etapas[i].dataset.nome || '';
      $('#voltar').hidden = i === 0;
      $('#seguir').textContent = i === etapas.length - 1 ? 'Ver onde posso transferir' : 'Continuar';
      if (etapas[i].dataset.etapa === 'onde') carregarCidades();
      const foco = etapas[i].querySelector('legend, .rotulo');
      if (foco && document.activeElement && form.contains(document.activeElement)) { foco.setAttribute('tabindex', '-1'); foco.focus(); }
    }
    async function validar(i) {
      if (etapas[i].dataset.etapa !== 'onde') return true;
      const campo = form.elements.cidade, c = campo.value.trim(), erro = $('#erro-cidade');
      if (!c) { erro.hidden = true; return true; }
      await carregarCidades();  // sempre com a lista completa: só com as capitais, "Palmas" pareceria não ter dúvida
      const r = resolverCidade(c);
      if (r.chave) { campo.value = r.chave; erro.hidden = true; return true; }
      erro.textContent = r.opcoes
        ? `Existe mais de uma cidade com esse nome: ${r.opcoes.join(', ')}. Escolha a sua na lista.`
        : 'Não achamos essa cidade. Comece a digitar e escolha na lista (ex.: Fernandópolis - SP).';
      erro.hidden = false;
      campo.focus();
      return false;
    }
    $('#voltar').addEventListener('click', () => mostrar(Math.max(0, atual - 1)));
    form.addEventListener('submit', async ev => {
      ev.preventDefault();
      if (!(await validar(atual))) return;
      if (atual < etapas.length - 1) { mostrar(atual + 1); return; }
      const fd = new FormData(form);
      const c = (fd.get('cidade') || '').trim();
      const taxa = (fd.get('taxaMax') || '').trim();
      const p = {
        origem: fd.get('origem'), curso: fd.get('curso'), faculdade: (fd.get('faculdade') || '').trim(),
        semestre: Number(fd.get('semestre')), transferiu: fd.get('transferiu'), cidade: c,
        coords: c ? acharCidade(c) : null,
        raio: Number(fd.get('raio')), tipo: fd.get('tipo'), taxaMax: taxa === '' ? null : Number(taxa)
      };
      armazem.gravar('tm_perfil', p);
      resultado(p);
      medir('diagnostico_concluido');
    });
    mostrar(porta === 'brasil' || porta === 'exterior' ? 1 : 0);
    medir('diagnostico_iniciado');
    if (salvo && location.hash === '#resultado') resultado(salvo);
  }

  function resultado(p) {
    const caixa = $('#resultado');
    const todos = ordenar(TM.editais.map(e => ({e, r: avaliar(e, p)})));
    const aptos = todos.filter(x => !x.r.motivos.length);
    const abertos = aptos.filter(x => situacao(x.e) === 'aberto');
    const continuos = aptos.filter(x => situacao(x.e) === 'contínuo');  // pedido sem edital: não conta como edital aberto
    const breveEdital = aptos.filter(x => situacao(x.e) === 'em breve');
    // editais novos achados pelo robô e ainda não conferidos: só filtra o que dá para saber (distância e tipo)
    const novos = (TM.novos || []).map(n => ({n, f: TM.faculdades[n.fid]})).filter(({f}) => f &&
      !(p.tipo !== 'todas' && ((p.tipo === 'publica') !== String(f.tipo).startsWith('pública'))) &&
      !(p.coords && p.raio && km(p.coords, [f.lat, f.lon]) > p.raio));
    // encerrados: só o mais recente de cada faculdade e modalidade (o histórico completo fica na página da faculdade)
    const ultimo = new Map();
    for (const x of aptos.filter(x => ['encerrado', 'desconhecida'].includes(situacao(x.e)))) {
      const k = x.e.fid + '|' + x.e.mod, antes = ultimo.get(k);
      if (!antes || String(x.e.fim || '') > String(antes.e.fim || '')) ultimo.set(k, x);
    }
    const encerrados = [...ultimo.values()];
    const fora = todos.filter(x => x.r.motivos.length && ['aberto', 'em breve', 'contínuo'].includes(situacao(x.e)));

    // abrem em breve pelo histórico: faculdades compatíveis, sem edital vivo, que costumam abrir nos próximos 3 meses
    const mes = new Date().getMonth() + 1;
    const proximos = [0, 1, 2, 3].map(k => ((mes - 1 + k) % 12) + 1);
    // faculdade que já tem edital vivo (mesmo que não sirva para o aluno) não entra na previsão
    const comEditalVivo = new Set(todos.filter(x => ['aberto', 'em breve', 'contínuo'].includes(situacao(x.e))).map(x => x.e.fid));
    const historico = Object.values(TM.faculdades).filter(f => {
      if (comEditalVivo.has(f.id) || !(f.meses || []).some(m => proximos.includes(m))) return false;
      if (p.origem === 'exterior' && f.ext === 'não') return false;
      if (p.tipo !== 'todas' && ((p.tipo === 'publica') !== String(f.tipo).startsWith('pública'))) return false;
      if (p.coords && p.raio && f.lat != null && km(p.coords, [f.lat, f.lon]) > p.raio) return false;
      return TM.editais.some(e => e.fid === f.id) || f.meses.length;
    }).map(f => ({f, dist: p.coords && f.lat != null ? km(p.coords, [f.lat, f.lon]) : null}))
      .sort((a, b) => (a.dist ?? 1e9) - (b.dist ?? 1e9));

    // resumo no topo: quantos, o mais perto e o prazo mais curto
    const comPrazo = abertos.filter(x => x.e.fim).sort((a, b) => a.e.fim.localeCompare(b.e.fim));
    const maisPerto = abertos.filter(x => x.r.dist != null).sort((a, b) => a.r.dist - b.r.dist)[0];
    const diasPrazo = comPrazo.length ? diasEntre(hoje(), comPrazo[0].e.fim) : null;
    const sigla = x => esc((TM.faculdades[x.e.fid] || {}).sigla);
    let html = `<p class="frase-resultado">${abertos.length
      ? `Você atende a <strong>${abertos.length} ${abertos.length === 1 ? 'edital aberto' : 'editais abertos'}</strong> agora.${diasPrazo != null ? ` O prazo mais próximo encerra ${diasPrazo <= 0 ? '<strong>hoje</strong>' : `em <strong>${diasPrazo} ${diasPrazo === 1 ? 'dia' : 'dias'}</strong>`} (${sigla(comPrazo[0])}).` : ''}`
      : `Nenhum edital aberto agora para o seu perfil.${breveEdital.length + historico.length ? ` ${breveEdital.length + historico.length === 1 ? 'Uma faculdade deve' : `${breveEdital.length + historico.length} faculdades devem`} abrir nos próximos meses: veja abaixo e receba o aviso quando abrir.` : ' Receba o aviso quando abrir.'}`}</p>
    <div class="painel-resultado">
      <div class="painel-numeros">
        <div class="numero destaque-num"><b>${abertos.length}</b><span>${abertos.length === 1 ? 'edital aberto' : 'editais abertos'} em que você atende aos requisitos</span></div>
        ${maisPerto ? `<div class="numero"><b>${maisPerto.r.dist < 5 ? 'Na cidade' : maisPerto.r.dist.toLocaleString('pt-BR') + ' km'}</b><span>o mais perto: ${sigla(maisPerto)}</span></div>` : ''}
        ${diasPrazo != null ? `<div class="numero ${diasPrazo <= 2 ? 'n-alerta' : diasPrazo <= 10 ? 'n-aviso' : ''}"><b>${diasPrazo <= 0 ? 'hoje' : diasPrazo + (diasPrazo === 1 ? ' dia' : ' dias')}</b><span>prazo mais curto: ${sigla(comPrazo[0])}</span></div>` : ''}
        <div class="numero"><b>${breveEdital.length + historico.length}</b><span>devem abrir nos próximos meses</span></div>
      </div>
      ${miniMapa(abertos.concat(breveEdital), p.coords)}
    </div>
    <div class="acoes acoes-resultado">
      ${$('#form-alerta') ? '<a class="botao atalho-alerta" href="#alerta">Receber aviso de novos editais para o meu perfil</a>' : ''}
      ${abertos.length + breveEdital.length ? `<button type="button" class="botao sec" id="res-salvar">Salvar todos na lista</button>` : ''}
    </div>
    ${painelAssinar(abertos.concat(breveEdital).map(x => x.e), 'res-agenda')}`;
    const perto = p.coords ? ', do mais perto para o mais longe' : '';
    html += `<h2 id="res-titulo">Abertos agora para você</h2>
      <p class="sub">${abertos.length} ${abertos.length === 1 ? 'edital' : 'editais'}${perto}.</p>`;
    html += abertos.length ? abertos.map(x => cartao(x.e, x.r)).join('')
      : '<div class="vazio">Nenhum edital aberto agora para o seu perfil. Veja abaixo onde deve abrir em breve.</div>';
    if (novos.length) {
      html += `<h2>Editais novos, ainda não conferidos</h2><p class="sub">O radar encontrou estes editais no site oficial, mas ainda não conferiu as regras. Abra o PDF para ver se servem para você.</p>`;
      html += novos.map(({n, f}) => `<article class="cartao cartao-novo"><h3><a href="${RAIZ}faculdade/${esc(f.id)}/">${esc(f.nome)}</a></h3>
        <div class="local">${esc(f.cidade)}/${esc(f.uf)} · ${esc(f.tipo)}${p.coords ? ` · <strong>${textoKm(km(p.coords, [f.lat, f.lon]))}</strong>` : ''}</div>
        <div class="etiquetas"><span class="et aviso">Detectado em ${fmt(n.det)}</span><span class="et">dados ainda não conferidos</span></div>
        <div class="rodape-cartao"><a href="${esc(n.url)}" target="_blank" rel="noopener">Abrir edital oficial<span class="oculto"> (abre em nova aba)</span></a></div></article>`).join('');
    }
    if (continuos.length) {
      html += `<h2>Sem edital: pedidos o ano todo</h2><p class="sub">Estas faculdades recebem pedidos de transferência sem processo seletivo publicado. Não há vagas nem prazos informados: confirme direto com a faculdade.</p>`;
      html += continuos.map(x => cartao(x.e, x.r)).join('');
    }

    html += '<h2>Abrem em breve</h2>';
    if (!breveEdital.length && !historico.length) html += '<div class="vazio">Nenhuma previsão para os próximos meses com o seu perfil.</div>';
    html += breveEdital.map(x => cartao(x.e, x.r)).join('');
    html += historico.map(({f, dist}) => {
      const meses = (f.meses || []).filter(m => proximos.includes(m)).map(m => MESES[m - 1]);
      return `<article class="cartao"><h3><a href="${RAIZ}faculdade/${esc(f.id)}/">${esc(f.nome)}</a></h3>
        <div class="local">${esc(f.cidade)}/${esc(f.uf)} · ${esc(f.tipo)}${dist != null ? ` · <strong>${textoKm(dist)}</strong>` : ''}</div>
        <div class="etiquetas"><span class="et aviso">Costuma abrir em ${meses.join(' ou ')}</span><span class="et">previsão pelo histórico</span></div>
        <p class="dica">Ainda não há edital publicado. A previsão vem dos editais anteriores desta faculdade.</p></article>`;
    }).join('');

    if (encerrados.length) html += `<details><summary>Encerrados (${encerrados.length}): o último de cada faculdade, para se preparar para o próximo</summary>${encerrados.map(x => cartao(x.e, x.r)).join('')}</details>`;
    if (fora.length) html += `<details><summary>Onde você não se encaixa agora, e por quê (${fora.length})</summary>${fora.map(x => cartao(x.e, x.r)).join('')}</details>`;
    html += `<p class="dica espaco-24">Seu perfil ficou salvo só neste navegador. Na próxima visita, a página inicial mostra o que mudou.
      "Atende aos requisitos" quer dizer que o edital não exclui o seu perfil. Quem decide a vaga e o aproveitamento é a faculdade.</p>`;
    caixa.innerHTML = html;
    caixa.hidden = false;
    const alerta = $('#alerta');
    if (alerta) alerta.hidden = false;
    const vivosAptos = abertos.concat(breveEdital);
    const salvarTodos = $('#res-salvar');
    if (salvarTodos) salvarTodos.addEventListener('click', () => {
      const m = armazem.ler('tm_marcados', []);
      for (const x of vivosAptos) if (!m.includes(x.e.id)) m.push(x.e.id);
      armazem.gravar('tm_marcados', m);
      caixa.querySelectorAll('[data-marcar]').forEach(b => { if (m.includes(b.dataset.marcar)) { b.setAttribute('aria-pressed', 'true'); b.textContent = ROTULO_SALVO; } });
      salvarTodos.textContent = `★ ${vivosAptos.length} ${vivosAptos.length === 1 ? 'edital salvo' : 'editais salvos'} na lista`;
      salvarTodos.disabled = true;
      contarLista();
      medir('salvar_lista');
    });
    ligarPainelAssinar($('#res-agenda'), vivosAptos.map(x => x.e), 'transfermed-meus-prazos.ics');
    const atalho = $('a.atalho-alerta');
    if (atalho) atalho.addEventListener('click', ev => {
      ev.preventDefault();
      alerta.scrollIntoView({block: 'start'});
      $('#email-alerta').focus({preventScroll: true});
    });
    armazem.gravar('tm_vistos', aptos.filter(x => ['aberto', 'em breve', 'contínuo'].includes(situacao(x.e))).map(x => x.e.id));
    $('#res-titulo').setAttribute('tabindex', '-1');
    $('#res-titulo').focus();
    caixa.scrollIntoView({block: 'start'});
  }

  // ---------------------------------------------------------------- página: edital
  function paginaEdital() {
    const id = document.body.dataset.edital;
    const e = TM.editais.find(x => x.id === id);
    if (!e) return;
    const u = urgencia(e), alvo = $('#urgencia');
    if (alvo) { alvo.className = 'et ' + u.cls; alvo.textContent = u.txt; }
    const chave = 'tm_check_' + id;
    const lista = [...document.querySelectorAll('#checklist input')];
    const feitos = new Set(armazem.ler(chave, []));
    const atualizar = () => {
      $('#check-prog').textContent = `${feitos.size} de ${lista.length} documentos separados`;
      const barra = $('#check-barra');
      if (barra) barra.style.width = `${lista.length ? (feitos.size / lista.length) * 100 : 0}%`;
    };
    // linha do tempo e contagem recalculadas no dia da visita (a página pode ter sido gerada ontem)
    const h = hoje();
    const linha = $('.linha');
    if (linha) {
      const marcos = [...linha.querySelectorAll('.marco[data-d]')];
      const liHoje = linha.querySelector('.marco.hoje');
      marcos.forEach(m => {
        const d = m.dataset.d;
        m.classList.remove('feito', 'agora', 'futuro');
        m.classList.add(d < h ? 'feito' : d === h ? 'agora' : 'futuro');
        m.querySelector('.nome').textContent = (d === h ? 'Hoje · ' : '') + m.dataset.nome;
      });
      if (liHoje) {
        liHoje.hidden = marcos.some(m => m.dataset.d === h);
        liHoje.querySelector('.data').textContent = fmt(h);
        linha.insertBefore(liHoje, marcos.find(m => h < m.dataset.d) || null);
      }
    }
    const cont = $('.contador');
    if (cont) {
      const ini = cont.dataset.inicio, fim = cont.dataset.fim;
      let num, txt, cls = '';
      if (ini && h < ini) { const d = diasEntre(h, ini); num = d; txt = `${d === 1 ? 'dia' : 'dias'} para abrirem as inscrições`; }
      else if (fim && h <= fim) {
        const d = diasEntre(h, fim);
        if (d === 0) { num = 'Hoje'; txt = 'é o último dia de inscrição'; cls = 'c-alerta'; }
        else { num = d; txt = `${d === 1 ? 'dia' : 'dias'} para o fim das inscrições`; cls = d <= 2 ? 'c-alerta' : d <= 10 ? 'c-aviso' : ''; }
      }
      if (num == null) cont.hidden = true;
      else {
        cont.querySelector('b').textContent = num;
        cont.querySelector('span').textContent = txt;
        cont.classList.toggle('c-alerta', cls === 'c-alerta');
        cont.classList.toggle('c-aviso', cls === 'c-aviso');
      }
    }
    const marcar = $('[data-marcar]');
    if (marcar && armazem.ler('tm_marcados', []).includes(id)) { marcar.setAttribute('aria-pressed', 'true'); marcar.textContent = ROTULO_SALVO; }
    // "Posso?": quem já fez o diagnóstico vê se atende, com o motivo (as mesmas regras do resultado)
    const perfil = armazem.ler('tm_perfil', null), caixaPosso = $('#voce-atende');
    if (perfil && caixaPosso) {
      const r = avaliar(e, perfil);
      caixaPosso.className = 'voce-atende ' + (r.motivos.length ? 'nao-atende' : 'atende');
      caixaPosso.innerHTML = r.motivos.length
        ? `<strong>Você não atende porque</strong> ${r.motivos.map(esc).join('; ')}. <a href="${RAIZ}diagnostico/">Refazer o diagnóstico</a>`
        : `<strong>Você atende aos requisitos</strong> deste edital pelo seu diagnóstico${r.dist != null ? ` (${textoKm(r.dist)})` : ''}. Quem decide a vaga é a faculdade.`;
      caixaPosso.hidden = false;
    }
    medir('ver_edital');
    lista.forEach((c, i) => {
      c.checked = feitos.has(i);
      c.addEventListener('change', () => {
        c.checked ? feitos.add(i) : feitos.delete(i);
        armazem.gravar(chave, [...feitos]);
        atualizar();
        if (feitos.size === 1 && c.checked) medir('checklist_usado');
      });
    });
    if (lista.length) atualizar();
  }

  // ---------------------------------------------------------------- página: lista de abertos (início)
  function listaAbertos() {
    const caixa = $('#abertos');
    if (!caixa) return;
    const vivos = ordenar(TM.editais.filter(e => ['aberto', 'em breve'].includes(situacao(e))).map(e => ({e, r: null})));
    $('#n-abertos').textContent = vivos.filter(x => situacao(x.e) === 'aberto').length;
    caixa.innerHTML = vivos.length ? vivos.map(x => cartao(x.e, x.r)).join('') : '<div class="vazio">Nenhum edital aberto hoje.</div>';
  }

  // ---------------------------------------------------------------- alertas por e-mail (Supabase, só funções públicas)
  const CFG = window.TM_CONFIG || {};
  const alertasAtivos = () => Boolean(CFG.supabaseUrl && CFG.supabaseAnon);
  async function rpc(nome, args) {
    // chave antiga (JWT, "anon") vai também no Authorization; a nova (sb_publishable_...) vai só no apikey
    const cabecalhos = {apikey: CFG.supabaseAnon, 'Content-Type': 'application/json'};
    if (CFG.supabaseAnon.startsWith('eyJ')) cabecalhos.Authorization = `Bearer ${CFG.supabaseAnon}`;
    const r = await fetch(`${CFG.supabaseUrl}/rest/v1/rpc/${nome}`, {method: 'POST', headers: cabecalhos, body: JSON.stringify(args)});
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  }

  // perfil do diagnóstico no formato que o robô dos alertas usa
  const perfilDoDiagnostico = p => ({origem: p.origem, curso: p.curso, faculdade: p.faculdade || '', semestre: p.semestre, transferiu: p.transferiu,
    cidade: p.cidade || '', coords: p.coords || null, raio: p.raio || 0, tipo: p.tipo, taxaMax: p.taxaMax});
  const RESPOSTAS = {
    email_invalido: 'Confira o e-mail: parece incompleto.',
    sem_consentimento: 'Para enviar alertas, precisamos que você marque a caixa de autorização.',
    perfil_invalido: 'Faça o diagnóstico de novo: o perfil salvo está incompleto.'
  };

  // inscrição em duas etapas: 1) e-mail e consentimento (com o que a chamada pede: seguir a faculdade, lembrar o
  // prazo); 2) o perfil, pré-preenchido pelo diagnóstico. Dupla confirmação pelo e-mail continua valendo.
  function formularioAlerta() {
    const form = $('#form-alerta');
    if (!form) return;
    const msg = $('#alerta-msg');
    if (!alertasAtivos()) {
      msg.textContent = 'Os alertas por e-mail estão sendo ativados. Por enquanto, salve o seu perfil: a página inicial mostra o que mudou a cada visita.';
      form.querySelectorAll('input, button').forEach(el => { el.disabled = true; });
      return;
    }
    const d = form.dataset;
    const salvo = armazem.ler('tm_alerta', null);
    if (salvo && salvo.email) form.elements.email.value = salvo.email;
    // o pedido desta página somado aos pedidos anteriores feitos neste navegador (o banco também soma)
    const seguir = () => {
      const antes = (armazem.ler('tm_alerta', null) || {}).seguir || {};
      const junta = (lista, novo) => [...new Set([...(lista || []), ...(novo ? [novo] : [])])].slice(-30);
      return {faculdades: junta(antes.faculdades, d.seguirFaculdade), lembretes: junta(antes.lembretes, d.lembrete)};
    };
    form.addEventListener('submit', async ev => {
      ev.preventDefault();
      const email = form.elements.email.value.trim();
      // campo-armadilha para robôs; se o preenchimento automático do navegador cair nele, a pessoa precisa saber
      if (form.elements.campo_extra.value) { form.elements.campo_extra.value = ''; msg.textContent = 'Não deu certo: o navegador preencheu um campo escondido. Clique no botão de novo.'; return; }
      if (!/^[^@\s]+@[^@\s]+\.[a-z]{2,}$/i.test(email)) { msg.textContent = 'Confira o e-mail: parece incompleto.'; form.elements.email.focus(); return; }
      if (!form.elements.consentimento.checked) { msg.textContent = 'Para enviar alertas, precisamos que você marque a caixa de autorização.'; return; }
      const p = armazem.ler('tm_perfil', null);
      if (d.comPerfil && !p) { msg.textContent = 'Faça o diagnóstico primeiro: o alerta usa o seu perfil.'; return; }
      let base = {};
      try { base = JSON.parse(d.perfilBase || '{}'); } catch (e) { /* sem perfil de base */ }
      const perfil = {...(d.comPerfil ? perfilDoDiagnostico(p) : base), seguir: seguir()};
      const botao = form.querySelector('button');
      botao.disabled = true; msg.textContent = 'Enviando…';
      try {
        const r = await rpc('inscrever', {p_email: email, p_perfil: perfil, p_consentimento: CFG.consentimento});
        if (r === 'pendente' || r === 'atualizado') {
          armazem.gravar('tm_alerta', {email, em: hoje(), seguir: perfil.seguir});
          medir('alerta_inscrito');
          medir('alerta_inscrito_' + (d.contexto || 'outro'));
          msg.textContent = '';
          passo2(email, perfil, r);
        } else {
          msg.textContent = RESPOSTAS[r] || `Não deu certo agora (código: ${String(r).slice(0, 40)}). Tente de novo em alguns minutos.`;
        }
      } catch (e) {
        msg.textContent = `Não deu certo agora (${e.message || 'sem conexão'}). Tente de novo em alguns minutos.`;
      }
      botao.disabled = false;
    });
  }

  function passo2(email, enviado, r) {
    const caixa = $('#alerta-passo2'), form = $('#form-alerta');
    const quando = CFG.envioImediato ? 'Em 1 ou 2 minutos' : 'Em até 1 hora';
    const confirmar = r === 'pendente'
      ? `${quando} chega um e-mail de alertas@transfermed.com.br para você confirmar. Se não aparecer, procure no lixo eletrônico (Hotmail e Outlook), no spam ou na aba Promoções.`
      : `Seu alerta já estava ativo: atualizamos as suas preferências. ${quando} chega um e-mail para ${esc(email)} confirmando a mudança.`;
    const isca = $('#alerta .sub a[data-medir="isca"]');
    const linkIsca = isca ? `<p><a class="botao sec" href="${esc(isca.getAttribute('href'))}" download data-medir="isca">Baixar o checklist de documentos (PDF)</a></p>` : '';
    const p = armazem.ler('tm_perfil', null);
    const v = {...(p ? perfilDoDiagnostico(p) : {}), ...enviado};
    form.hidden = true;
    const garantia = $('#alerta .garantia');
    if (garantia) garantia.hidden = true;
    if (enviado.curso && enviado.semestre) {  // o perfil completo já foi no passo 1 (diagnóstico)
      caixa.innerHTML = `<p class="ok-caixa" tabindex="-1"><strong>Pronto.</strong> ${confirmar}</p>${linkIsca}`;
    } else {
      const semestres = Array.from({length: 12}, (_, i) => `<option value="${i + 1}">${i + 1}º semestre</option>`).join('');
      caixa.innerHTML = `<p class="ok-caixa" tabindex="-1"><strong>Passo 1 de 2 feito.</strong> ${confirmar}</p>${linkIsca}
        <form id="form-perfil" class="form-perfil" novalidate aria-labelledby="t-passo2">
          <h3 id="t-passo2">Passo 2 (opcional): para quais editais avisar?</h3>
          <p class="dica">${p ? 'Preenchemos com o seu diagnóstico. Confira e salve.' : 'Com o perfil, avisamos de todos os editais que servem para você.'}</p>
          <fieldset><legend class="rotulo">Onde você estuda Medicina?</legend><div class="opcoes">
            <label><input type="radio" name="origem" value="brasil">No Brasil</label>
            <label><input type="radio" name="origem" value="exterior">No exterior</label></div></fieldset>
          <label class="rotulo" for="p2-semestre">Em que semestre você está?</label>
          <select id="p2-semestre" name="semestre"><option value="">Escolha</option>${semestres}</select>
          <fieldset><legend class="rotulo">Tipo de faculdade</legend><div class="opcoes">
            <label><input type="radio" name="tipo" value="todas">Pública ou particular</label>
            <label><input type="radio" name="tipo" value="publica">Só pública</label>
            <label><input type="radio" name="tipo" value="particular">Só particular</label></div></fieldset>
          ${v.cidade && v.raio ? `<label class="consentimento"><input type="checkbox" name="manter_raio" checked> <span>Só faculdades até ${Number(v.raio)} km de ${esc(v.cidade)} (do seu diagnóstico)</span></label>` : ''}
          <div class="acoes"><button type="submit" class="botao">Salvar meu perfil</button><button type="button" class="botao sec" data-pular>Agora não</button></div>
          <p class="dica" id="perfil-msg" role="status" aria-live="polite"></p>
        </form>`;
      const f = $('#form-perfil');
      const marcar = (nome, valor) => { const el = f.querySelector(`[name="${nome}"][value="${valor}"]`); if (el) el.checked = true; };
      marcar('origem', v.origem === 'exterior' ? 'exterior' : 'brasil');
      marcar('tipo', ['publica', 'particular'].includes(v.tipo) ? v.tipo : 'todas');
      if (v.semestre) f.semestre.value = String(v.semestre);
      f.querySelector('[data-pular]').addEventListener('click', () => {
        f.outerHTML = '<p class="dica">Tudo bem. Você pode completar o perfil depois, refazendo o <a href="' + RAIZ + 'diagnostico/">diagnóstico</a>.</p>';
      });
      f.addEventListener('submit', async ev => {
        ev.preventDefault();
        const m = $('#perfil-msg');
        if (!f.semestre.value) { m.textContent = 'Escolha o semestre: é ele que diz em quais editais há vaga para você.'; f.semestre.focus(); return; }
        const manter = f.manter_raio && f.manter_raio.checked;
        const perfil = {origem: f.origem.value, curso: v.curso || 'medicina', faculdade: v.faculdade || '', semestre: Number(f.semestre.value),
          transferiu: v.transferiu || '', cidade: manter ? v.cidade : '', coords: manter ? v.coords : null, raio: manter ? v.raio : 0,
          tipo: f.tipo.value, taxaMax: v.taxaMax ?? null, seguir: enviado.seguir};
        const botao = f.querySelector('button[type="submit"]');
        botao.disabled = true; m.textContent = 'Salvando…';
        try {
          const r2 = await rpc('inscrever', {p_email: email, p_perfil: perfil, p_consentimento: CFG.consentimento});
          if (r2 === 'pendente' || r2 === 'atualizado') {
            medir('alerta_perfil');
            f.outerHTML = '<p class="ok-caixa">Perfil salvo. Os avisos vão seguir este perfil, além das faculdades que você pediu.</p>';
            return;
          }
          m.textContent = RESPOSTAS[r2] || 'Não deu certo agora. Tente de novo em alguns minutos.';
        } catch (e) {
          m.textContent = 'Não deu certo agora (sem conexão?). Tente de novo em alguns minutos.';
        }
        botao.disabled = false;
      });
    }
    caixa.hidden = false;
    $('.ok-caixa', caixa).focus();
  }

  // no máximo uma barra, só nas fichas e em "Estudo no exterior", depois de 60% de leitura; fechada, não volta mais
  function barraAlerta() {
    const alvo = $('#alerta');
    if (!alvo || alvo.hidden || !alertasAtivos() || !['edital', 'faculdade', 'exterior'].includes(document.body.dataset.pagina)) return;
    if (armazem.ler('tm_alerta', null) || armazem.ler('tm_barra_fechada', false)) return;
    let barra = null, mostrada = false;
    const formNaTela = () => { const r = alvo.getBoundingClientRect(); return r.top < innerHeight && r.bottom > 0; };
    const fechar = guardar => { if (barra) barra.remove(); barra = null; if (guardar) armazem.gravar('tm_barra_fechada', true); };
    const aoRolar = () => {
      if (mostrada) { if (barra && formNaTela()) fechar(false); return; }  // o formulário apareceu: a barra sai
      const lido = (scrollY + innerHeight) / document.documentElement.scrollHeight;
      if (lido < 0.6 || formNaTela() || $('#form-alerta').hidden) return;
      mostrada = true;
      barra = document.createElement('div');
      barra.className = 'barra-alerta';
      barra.setAttribute('role', 'region');
      barra.setAttribute('aria-label', 'Aviso por e-mail');
      barra.innerHTML = `<p>${esc($('#t-alerta').textContent)}</p><a class="botao" href="#alerta">Quero</a>
        <button type="button" class="barra-fechar" aria-label="Fechar e não mostrar de novo">×</button>`;
      document.body.appendChild(barra);
      barra.querySelector('.barra-fechar').addEventListener('click', () => fechar(true));
      barra.querySelector('a').addEventListener('click', ev => {
        ev.preventDefault(); fechar(true); medir('barra_alerta');
        alvo.scrollIntoView({block: 'start'}); $('#email-alerta').focus({preventScroll: true});
      });
    };
    addEventListener('scroll', aoRolar, {passive: true});
  }

  async function paginaAlerta() {
    const caixa = $('#alerta-acao');
    const acao = caixa.dataset.acao;
    const token = new URLSearchParams(location.search).get('t') || '';
    if (!/^[0-9a-f-]{36}$/i.test(token)) { caixa.innerHTML = '<p>Link incompleto. Abra de novo o link do e-mail (às vezes ele quebra ao copiar).</p>'; return; }
    if (!alertasAtivos()) { caixa.innerHTML = '<p>Os alertas ainda não estão ativos neste site.</p>'; return; }
    try {
      const r = await rpc(acao, {p_token: token});
      if (acao === 'confirmar') {
        if (r === 'ok') medir('alerta_confirmado');
        caixa.innerHTML = r === 'ok'
          ? '<p class="ok-caixa"><strong>Alerta confirmado.</strong> Você vai receber um e-mail quando abrir edital compatível com o seu perfil. O primeiro pode trazer os que já estão abertos.</p>'
          : '<p>Não encontramos este cadastro. Ele pode ter sido cancelado ou ter passado de 7 dias sem confirmação. Faça o diagnóstico de novo para se inscrever.</p>';
      } else {
        caixa.innerHTML = r === 'ok'
          ? '<p class="ok-caixa"><strong>Pronto: alertas cancelados e dados apagados.</strong> Seu e-mail e o seu perfil saíram do nosso banco.</p>'
          : '<p>Este cadastro já não existe: nada mais a apagar.</p>';
        armazem.apagar('tm_alerta');
      }
    } catch (e) {
      caixa.innerHTML = '<p>Não deu certo agora (sem conexão?). Tente abrir o link de novo em alguns minutos.</p>';
    }
  }

  // prova social só com número real de alertas confirmados, e só depois de passar de 100
  async function provaSocial() {
    const alvo = $('.heroi-texto .acoes');
    if (!alvo || !alertasAtivos()) return;
    try {
      const n = await rpc('total_alertas', {});
      if (Number(n) > 100) alvo.insertAdjacentHTML('afterend', `<p class="prova-social"><strong>${Number(n).toLocaleString('pt-BR')} estudantes</strong> recebem os alertas do radar.</p>`);
    } catch (e) { /* sem número, sem frase */ }
  }

  // textos de prazo gravados nas páginas são recalculados no dia da visita (o site pode ficar dias sem ser regerado)
  function atualizarPrazos() {
    document.querySelectorAll('[data-prazo][data-fim]').forEach(el => {
      const u = urgencia({ini: el.dataset.ini, fim: el.dataset.fim});
      el.className = 'et ' + u.cls;
      el.textContent = u.txt;
    });
    const faixa = $('.faixa-prazo[data-fim]');
    if (faixa) {
      const d = diasEntre(hoje(), faixa.dataset.fim);
      if (d < 0) faixa.hidden = true;
      else faixa.querySelector('[data-quando]').textContent = d === 0 ? 'hoje' : `em ${d} ${d === 1 ? 'dia' : 'dias'}`;
    }
  }
  atualizarPrazos();

  // aplicativo: funciona sem internet com a última versão vista
  // quando um service worker novo assume uma página já aberta, ela ainda roda o app antigo: avisa para recarregar
  function avisoNovaVersao() {
    if ($('.nova-versao')) return;
    const aviso = document.createElement('div');
    aviso.className = 'nova-versao';
    aviso.setAttribute('role', 'status');
    aviso.innerHTML = '<span>Nova versão disponível</span><button type="button" class="link-botao">atualizar</button>';
    aviso.querySelector('button').addEventListener('click', () => location.reload());
    document.body.appendChild(aviso);
  }
  if ('serviceWorker' in navigator) {
    const tinhaControle = !!navigator.serviceWorker.controller;
    navigator.serviceWorker.addEventListener('controllerchange', () => { if (tinhaControle) avisoNovaVersao(); });
  }
  if ('serviceWorker' in navigator && location.protocol === 'https:') {
    window.addEventListener('load', () => navigator.serviceWorker.register(RAIZ + 'sw.js', {updateViaCache: 'none'})
      .then(reg => document.addEventListener('visibilitychange', () => { if (!document.hidden) reg.update().catch(() => {}); }))
      .catch(() => {}));
  }

  // ---------------------------------------------------------------- busca por faculdade (lupa do topo, todas as páginas)
  function busca() {
    const painel = $('#busca'), campo = $('#busca-campo'), lista = $('#busca-lista');
    if (!painel) return;
    const botoes = [...document.querySelectorAll('[data-abrir-busca]')];
    const novas = new Set((TM.novos || []).map(n => n.fid));
    const faculdades = Object.values(TM.faculdades).map(f => ({f, chave: norm(`${f.nome} ${f.sigla} ${f.cidade} ${f.uf}`)}));
    const estado = f => {
      const s = situacaoFaculdade(f.id);
      if (s === 'aberto') return '<span class="et ok">inscrições abertas</span>';
      if (s === 'breve') return '<span class="et aviso">abre em breve</span>';
      if (novas.has(f.id)) return '<span class="et aviso">edital novo, a conferir</span>';
      return '<span class="et">sem edital aberto</span>';
    };
    // todas as palavras digitadas precisam aparecer; sigla exata e começo do nome vêm primeiro
    const procurar = q => {
      const termos = norm(q).split(/\s+/).filter(Boolean);
      if (!termos.length) return [];
      const nota = ({f}) => {
        const sigla = norm(f.sigla), nome = norm(f.nome);
        if (sigla === norm(q)) return 0;
        if (sigla.startsWith(termos[0]) || nome.startsWith(termos[0])) return 1;
        if (nome.split(/[^a-z0-9]+/).some(p => p.startsWith(termos[0]))) return 2;
        return 3;
      };
      return faculdades.filter(x => termos.every(t => x.chave.includes(t)))
        .sort((a, b) => nota(a) - nota(b) || a.f.nome.localeCompare(b.f.nome, 'pt')).slice(0, 8);
    };
    const mostrar = () => {
      const q = campo.value.trim();
      if (!q) { lista.innerHTML = `<li class="busca-dica">${faculdades.length} faculdades na base. Digite o nome, a sigla (ex.: UNIFESP) ou a cidade.</li>`; return; }
      const achadas = procurar(q);
      lista.innerHTML = achadas.length
        ? achadas.map(({f}) => `<li><a href="${RAIZ}faculdade/${esc(f.id)}/"><b>${esc(f.nome)}</b><span>${esc(f.cidade)}/${esc(f.uf)} · ${esc(f.tipo)} ${estado(f)}</span></a></li>`).join('')
        : '<li class="busca-dica">Nenhuma faculdade com esse nome na base. A cobertura está crescendo: tente a sigla ou a cidade.</li>';
    };
    const abrir = () => {
      painel.hidden = false;
      botoes.forEach(b => b.setAttribute('aria-expanded', 'true'));
      mostrar();
      campo.focus();
    };
    const fechar = () => {
      painel.hidden = true;
      botoes.forEach(b => b.setAttribute('aria-expanded', 'false'));
    };
    botoes.forEach(b => b.addEventListener('click', ev => { ev.stopPropagation(); painel.hidden ? abrir() : fechar(); }));
    campo.addEventListener('input', mostrar);
    campo.addEventListener('keydown', ev => {
      const links = [...lista.querySelectorAll('a')];
      if (ev.key === 'Enter' && links[0]) { ev.preventDefault(); location.href = links[0].href; }
      if (ev.key === 'ArrowDown' && links[0]) { ev.preventDefault(); links[0].focus(); }
    });
    lista.addEventListener('keydown', ev => {
      const links = [...lista.querySelectorAll('a')], i = links.indexOf(document.activeElement);
      if (ev.key === 'ArrowDown' && i < links.length - 1) { ev.preventDefault(); links[i + 1].focus(); }
      if (ev.key === 'ArrowUp') { ev.preventDefault(); (i > 0 ? links[i - 1] : campo).focus(); }
    });
    document.addEventListener('keydown', ev => {
      if (ev.key === 'Escape' && !painel.hidden) { fechar(); botoes[0].focus(); }
      const digitando = /^(input|textarea|select)$/i.test(document.activeElement.tagName);
      if (ev.key === '/' && !digitando && painel.hidden) { ev.preventDefault(); abrir(); }
    });
    document.addEventListener('click', ev => { if (!painel.hidden && !painel.contains(ev.target)) fechar(); });
    // /?busca=termo (o atalho de busca que o Google mostra) abre a busca já preenchida
    const pedida = new URLSearchParams(location.search).get('busca');
    if (pedida) { campo.value = pedida.slice(0, 80); abrir(); }
  }

  // ---------------------------------------------------------------- "Quem faz o Transfermed?" (fechado por padrão)
  // celular: painel que sobe de baixo (arrastar para baixo fecha); computador: expande no lugar
  function quemFaz() {
    const caixa = $('[data-quem-faz]');
    if (!caixa) return;
    const botao = $('.quem-faz-botao'), painel = $('.qf-painel', caixa), fundo = $('.qf-fundo', caixa);
    if (!botao) return;
    const celular = () => matchMedia('(max-width: 640px)').matches;
    const abrir = () => {
      // no computador o painel abre logo abaixo do cabeçalho (que fica fixo no topo ao rolar)
      document.documentElement.style.setProperty('--altura-topo', `${Math.round($('.topo').getBoundingClientRect().bottom)}px`);
      painel.hidden = false;
      fundo.hidden = !celular();
      botao.setAttribute('aria-expanded', 'true');
      painel.focus();
      medir('quem_faz_aberto');
    };
    const fechar = (devolverFoco = true) => {
      if (painel.hidden) return;
      painel.hidden = true;
      fundo.hidden = true;
      painel.style.transform = '';
      botao.setAttribute('aria-expanded', 'false');
      if (devolverFoco) botao.focus();
    };
    botao.addEventListener('click', ev => { ev.stopPropagation(); painel.hidden ? abrir() : fechar(); });
    $('.qf-fechar', caixa).addEventListener('click', () => fechar());
    fundo.addEventListener('click', () => fechar());
    document.addEventListener('keydown', ev => { if (ev.key === 'Escape') fechar(); });
    document.addEventListener('click', ev => { if (!painel.hidden && !painel.contains(ev.target)) fechar(false); });
    let y0 = null;
    painel.addEventListener('touchstart', ev => { y0 = ev.touches[0].clientY; }, {passive: true});
    painel.addEventListener('touchmove', ev => {
      const d = y0 === null ? 0 : ev.touches[0].clientY - y0;
      if (d > 0 && celular()) painel.style.transform = `translateY(${d}px)`;
    }, {passive: true});
    painel.addEventListener('touchend', ev => {
      if (y0 === null) return;
      const d = ev.changedTouches[0].clientY - y0;
      y0 = null;
      painel.style.transform = '';
      if (d > 80 && celular()) fechar();
    });
  }

  // ---------------------------------------------------------------- contato (/contato/ e fim de /sobre/)
  function formularioContato() {
    const form = $('#form-contato');
    if (!form) return;
    const f = form.elements, msg = $('#contato-msg');
    const pedido = new URLSearchParams(location.search).get('motivo');
    if ([...f.motivo.options].some(o => o.value === pedido)) f.motivo.value = pedido;
    const p = armazem.ler('tm_perfil', null);  // quem já fez o diagnóstico não digita de novo
    if (p) {
      const origem = form.querySelector(`[name="origem"][value="${p.origem === 'exterior' ? 'exterior' : 'brasil'}"]`);
      if (origem) origem.checked = true;
      if (p.faculdade) f.faculdade.value = p.faculdade;
      if (p.semestre) f.semestre.value = String(p.semestre);
    }
    if (!CFG.contato || !alertasAtivos()) {
      msg.textContent = 'O formulário está sendo ativado e ainda não envia mensagens. Volte em alguns dias.';
      form.querySelector('button[type="submit"]').disabled = true;
      return;
    }
    form.addEventListener('submit', async ev => {
      ev.preventDefault();
      if (f.campo_extra.value) { f.campo_extra.value = ''; msg.textContent = 'O navegador preencheu um campo escondido. Toque em "Mandar minha mensagem" de novo.'; return; }
      const dados = {nome: f.nome.value.trim(), email: f.email.value.trim(), motivo: f.motivo.value, origem: f.origem.value,
        faculdade: f.faculdade.value.trim(), semestre: f.semestre.value, mensagem: f.mensagem.value.trim()};
      if (!dados.nome) { msg.textContent = 'Escreva o seu nome.'; f.nome.focus(); return; }
      if (!/^[^@\s]+@[^@\s]+\.[a-z]{2,}$/i.test(dados.email)) { msg.textContent = 'Confira o e-mail: parece incompleto.'; f.email.focus(); return; }
      if (dados.mensagem.length < 5) { msg.textContent = 'Escreva a sua mensagem.'; f.mensagem.focus(); return; }
      if (!f.consentimento.checked) { msg.textContent = 'Para responder, preciso que você marque a caixa de autorização.'; return; }
      const botao = form.querySelector('button[type="submit"]');
      botao.disabled = true;
      msg.textContent = 'Enviando…';
      try {
        const consentimento = form.querySelector('.consentimento span').textContent.replace(/\s*Privacidade\.\s*$/, '').trim();
        let r = await rpc('contato', {p_dados: dados, p_consentimento: consentimento});
        // banco ainda com a lista antiga de motivos (antes de rodar o schema.sql novo): vai como dúvida, com o assunto
        if (r === 'dados_invalidos' && ['sugestao', 'outro'].includes(dados.motivo))
          r = await rpc('contato', {p_dados: {...dados, motivo: 'duvida', assunto: dados.motivo}, p_consentimento: consentimento});
        if (r === 'ok') {
          medir('contato_enviado');
          form.innerHTML = `<p class="ok-caixa"><strong>Recebi sua mensagem.</strong> Respondo em até 3 dias úteis. Enquanto isso, ative o alerta para ser avisado quando abrir edital para o seu perfil.</p>
            <p><a class="botao" href="${RAIZ}diagnostico/">Receber aviso de editais para o meu perfil</a></p>`;
          return;
        }
        msg.textContent = {email_invalido: 'Confira o e-mail: parece incompleto.', limite: 'Recebi várias mensagens suas hoje. Respondo todas em até 3 dias úteis.'}[r]
          || 'Não deu certo agora. Tente de novo em alguns minutos.';
      } catch (e) {
        msg.textContent = 'Não deu certo agora (sem conexão?). Tente de novo em alguns minutos.';
      }
      botao.disabled = false;
    });
  }

  function paginaMinhaLista() {
    const caixa = $('#minha-lista');
    const ids = armazem.ler('tm_marcados', []);
    const salvos = ids.map(id => TM.editais.find(e => e.id === id)).filter(Boolean)
      .sort((a, b) => (ORDEM[situacao(a)] - ORDEM[situacao(b)]) || String(a.fim || '9999').localeCompare(String(b.fim || '9999')));
    if (!salvos.length) {
      caixa.innerHTML = `<div class="vazio">Nenhum edital salvo ainda. Toque na estrela (☆ Salvar na minha lista) num edital para guardar aqui.
        <p class="acoes"><a class="botao" href="${RAIZ}diagnostico/">Descobrir onde posso transferir</a></p></div>`;
      return;
    }
    caixa.innerHTML = salvos.map(e => cartao(e, null)).join('')
      + painelAssinar(salvos, 'cal-lista');
    ligarPainelAssinar($('#cal-lista'), salvos, 'transfermed-minha-lista.ics');
  }

  medir('visita');
  busca();
  quemFaz();
  contarLista();
  formularioContato();
  const pagina = document.body.dataset.pagina;
  if (pagina === 'inicio') { listaAbertos(); paginaInicio(); provaSocial(); }
  if (pagina === 'diagnostico') paginaDiagnostico();
  formularioAlerta();
  barraAlerta();
  if (pagina === 'edital') paginaEdital();
  if (pagina === 'alerta') paginaAlerta();
  if (pagina === 'minha-lista') paginaMinhaLista();
})();
