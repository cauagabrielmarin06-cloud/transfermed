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

  // Origem de quem se inscreve no alerta (sem cookies, sem rastrear a pessoa): o canal da PRIMEIRA visita fica guardado
  // no próprio aparelho e vai junto com o perfil do alerta (perfil.canal). Só códigos fixos; nunca o endereço de origem.
  const CANAIS = ['google', 'instagram', 'whatsapp', 'facebook', 'grupo', 'indicacao', 'email', 'outro_site', 'direto'];
  function canalDaVisita(url, referrer, agente) {
    const q = new URLSearchParams(url.search);
    const marca = norm(q.get('utm_source') || q.get('canal') || (['brasil', 'exterior', 'app'].includes(q.get('origem')) ? '' : q.get('origem')));
    const MAPA = {instagram: 'instagram', ig: 'instagram', whatsapp: 'whatsapp', wpp: 'whatsapp', zap: 'whatsapp', facebook: 'facebook', fb: 'facebook',
      grupo: 'grupo', grupos: 'grupo', telegram: 'grupo', indicacao: 'indicacao', amigo: 'indicacao', google: 'google', bing: 'google',
      email: 'email', newsletter: 'email'};
    if (marca) return MAPA[marca] || 'outro_site';
    // navegador interno dos apps: vale mesmo quando vem com referenciador (o app às vezes manda o do próprio site)
    if (/Instagram/i.test(agente)) return 'instagram';
    if (/FBAN|FBAV/.test(agente)) return 'facebook';
    const host = hostDoReferrer(referrer);
    if (host && !/(^|\.)transfermed\.com\.br$/.test(host)) {
      if (/(^|\.)(google|bing|duckduckgo|yahoo|ecosia)\./.test(host)) return 'google';
      if (/(^|\.)instagram\.com$/.test(host) || host === 'com.instagram.android') return 'instagram';  // inclui l.instagram.com e o app (android-app://com.instagram.android)
      if (/(^|\.)(facebook|fb|m\.facebook|l\.facebook|lm\.facebook)\.com$|^fb\.me$/.test(host) || /^com\.facebook\./.test(host)) return 'facebook';
      if (/(^|\.)(whatsapp\.com|wa\.me)$/.test(host) || host === 'com.whatsapp') return 'whatsapp';
      if (/(^|\.)(t\.me|telegram\.org)$/.test(host) || host === 'org.telegram.messenger') return 'grupo';
      if (host === 'com.google.android.googlequicksearchbox') return 'google';
      if (host === 'com.google.android.gm') return 'email';
      return 'outro_site';
    }
    return 'direto';
  }
  // só o domínio de quem mandou a pessoa (nunca o endereço completo, o caminho ou a busca); no Android o app vem como android-app://<pacote>
  function hostDoReferrer(referrer) {
    try { return new URL(referrer).hostname.replace(/^www\./, '').toLowerCase().slice(0, 60); } catch (e) { return ''; }
  }
  function canalDoInscrito() {
    const salvo = armazem.ler('tm_canal', null);
    if (salvo && CANAIS.includes(salvo.c) && salvo.c !== 'direto') return salvo.c;
    let c = 'direto';
    try {
      c = canalDaVisita(new URL(location.href), document.referrer, navigator.userAgent || '');
      if (c !== 'direto') {
        const r = c === 'outro_site' ? hostDoReferrer(document.referrer) : '';  // o domínio só é guardado quando o canal é "outro site"
        armazem.gravar('tm_canal', r && /^[a-z0-9.-]+$/.test(r) ? {c, em: hoje(), r} : {c, em: hoje()});
      }
    } catch (e) { /* fica direto */ }
    return c;
  }
  function refDoInscrito() {
    const salvo = armazem.ler('tm_canal', null);
    return salvo && salvo.c === 'outro_site' && /^[a-z0-9.-]{1,60}$/.test(salvo.r || '') ? salvo.r : '';
  }
  canalDoInscrito();  // a primeira visita decide o canal, mesmo que a pessoa só se inscreva dias depois
  window.TM_CANAL = {canalDaVisita, canalDoInscrito, refDoInscrito};

  const MODALIDADES = {
    externa: ['Transferência externa', 'Para quem cursa Medicina em outra faculdade'],
    interna: ['Transferência interna', 'Edital da própria faculdade, para os alunos dela; veja no edital quem pode'],
    exterior: ['Para quem estuda no exterior', 'Edital próprio para alunos de faculdades estrangeiras'],
    portador_diploma: ['Portador de diploma (novo título)', 'Para quem já concluiu uma graduação (obtenção de novo título); veja no edital quem ele aceita'],
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
    if (s === 'contínuo') return {cls: 'ok', txt: e.fluxo === 'vagas' ? 'Inscrições abertas até completar as vagas' : 'Pedidos o ano todo (sem edital)'};
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

  // Período aceito pelo edital: 's' = 'sim' | 'nao' | 'conferir'. "conferir" = o quadro de vagas não deixa o período claro (sem quadro, só
  // cadastro reserva ou rótulo sem número); o radar pessoal o mostra como "confirme no edital" e não o conta. Mesma regra do alertas.motivos.
  function periodoStatus(e, semestre) {
    const mod = e.mod || 'externa';
    if (!semestre || !(mod === 'externa' || mod === 'exterior')) return {s: 'sim', rotulos: []};
    const comVaga = (Array.isArray(e.vagas) ? e.vagas : []).filter(v => v.vagas !== 0);
    if (!comVaga.length) return {s: 'conferir', rotulos: []};
    const alvo = [semestre, semestre + 1], rotulos = [];
    let incerto = false;
    for (const v of comVaga) {
      const ss = semestresDaVaga(v.semestre);
      if (ss === null) incerto = true; else if (ss.some(x => alvo.includes(x))) rotulos.push(v.semestre);
    }
    return rotulos.length ? {s: 'sim', rotulos} : incerto ? {s: 'conferir', rotulos: []} : {s: 'nao', rotulos: []};
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
      if (mod === 'portador_diploma') motivos.push('para quem já tem diploma de graduação (obtenção de novo título)');
      if (mod === 'interna') motivos.push('interna: só para alunos desta faculdade');
    }
    if (p.origem === 'exterior' && e.ext === false) motivos.push('não aceita quem estuda no exterior');
    if (p.origem === 'brasil' && mod === 'exterior') motivos.push('edital só para quem estuda no exterior');
    if (p.transferiu === 'sim' && e.exc === true) motivos.push('não aceita quem já fez transferência');
    if (mesma && mod !== 'interna') motivos.push('é a sua faculdade atual');
    if (p.tipo !== 'todas' && f.tipo) {
      const publica = f.tipo.startsWith('pública');
      if ((p.tipo === 'publica') !== publica) motivos.push(`é ${f.tipo}`);
    }
    if (p.curso === 'medicina' && p.semestre && periodoStatus(e, p.semestre).s === 'nao') motivos.push(`sem vagas para quem está no ${p.semestre}º semestre`);
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
    // "Salvo no seu plano ✓" com o caminho para o plano (no próprio Meu plano a tela já mostra o resultado)
    if (document.body.dataset.pagina !== 'minha-lista') {
      b.parentNode.querySelectorAll('.salvo-aviso').forEach(a => a.remove());
      if (agora) {
        const aviso = document.createElement('span');
        aviso.className = 'salvo-aviso'; aviso.setAttribute('role', 'status');
        aviso.innerHTML = `Salvo no seu plano ✓ <a href="${RAIZ}minha-lista/">Ver meu plano</a>`;
        b.insertAdjacentElement('afterend', aviso);
      }
    }
  });
  // eventos simples do funil marcados no HTML (data-medir="abrir_pdf" etc.)
  document.addEventListener('click', ev => { const a = ev.target.closest('[data-medir]'); if (a) medir(a.dataset.medir); });

  function compativeis(p) {
    return TM.editais.map(e => ({e, r: avaliar(e, p)})).filter(x => !x.r.motivos.length);
  }

  // ---------------------------------------------------------------- calendário .ics
  // nome curto do edital: sigla, e a cidade quando a sigla ainda não a traz (mesma regra do gerar_site.eventos_ics)
  function nomeEdital(e) {
    const f = TM.faculdades[e.fid] || {};
    return f.cidade && !norm(f.sigla).includes(norm(f.cidade)) ? `${f.sigla} ${f.cidade}` : (f.sigla || 'Medicina');
  }
  // data em "conferir" (aviso do edital) nunca vira evento, choque, linha do tempo nem célula da comparação
  const CHAVE_CONFERIR = {ini: 'inscricao_inicio', fim: 'inscricao_fim', prova: 'data_prova', res: 'resultado', mat: 'data_matricula', taxa: 'taxa_inscricao',
    vagas: 'vagas', ext: 'aceita_curso_exterior', crit: 'criterio_selecao'};
  function conferido(e, campo) {
    const conf = e.conf || [];
    return !conf.includes('edital') && !conf.includes(CHAVE_CONFERIR[campo] || campo);
  }
  function ics(editais, opcoes = {}) {
    const d8 = s => s.replace(/-/g, '');
    const mais1 = s => { const d = new Date(s + 'T12:00:00'); d.setDate(d.getDate() + 1); return d.toISOString().slice(0, 10); };
    const txt = s => String(s).replace(/([,;\\])/g, '\\$1').replace(/\n/g, '\\n');
    const stamp = new Date().toISOString().replace(/[-:]/g, '').slice(0, 15) + 'Z';
    // só eventos de um dia (nunca uma barra atravessando semanas), mesmo formato do gerar_site.eventos_ics
    const DATAS = [['ini', 'ini', 'abertura das inscrições', []], ['fim', 'fim', 'último dia de inscrição', ['-P6DT15H', '-P1DT15H']],
      ['prova', 'prova', 'prova', ['-P1DT15H']], ['res', 'resultado', 'resultado', []], ['mat', 'matricula', 'matrícula', []]];
    const ev = [];
    for (const e of editais) {
      const nome = nomeEdital(e);
      const ficha = new URL(`${RAIZ}edital/${e.slug}/`, location.href).href;
      const descricao = txt(`Ficha no Transfermed: ${ficha}\nEdital oficial: ${e.url}\nConfira sempre no edital oficial.`);
      for (const [campo, sufixo, rotulo, alarmes] of DATAS) {
        if (!e[campo] || !conferido(e, campo) || (opcoes.campos && !opcoes.campos.includes(campo)) || (opcoes.desde && e[campo] < opcoes.desde)) continue;
        const titulo = `${nome}: ${rotulo}`;
        ev.push(['BEGIN:VEVENT', `UID:${e.id}-${sufixo}@transfermed`, `DTSTAMP:${stamp}`, `DTSTART;VALUE=DATE:${d8(e[campo])}`,
          `DTEND;VALUE=DATE:${d8(mais1(e[campo]))}`, `SUMMARY:${txt(titulo)}`, `DESCRIPTION:${descricao}`, `URL:${ficha}`, 'TRANSP:TRANSPARENT',
          ...alarmes.flatMap(g => ['BEGIN:VALARM', 'ACTION:DISPLAY', `DESCRIPTION:${txt(titulo)}`, `TRIGGER:${g}`, 'END:VALARM']),
          'END:VEVENT'].join('\r\n'));
      }
    }
    // linhas com mais de 75 bytes continuam na seguinte, começando com espaço (regra do formato .ics)
    const dobrar = l => { const out = []; let at = ''; for (const c of l) { if (new TextEncoder().encode(at + c).length > (out.length ? 74 : 75)) { out.push(at); at = ''; } at += c; } out.push(at); return out.join('\r\n '); };
    return ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Transfermed//Radar//PT', 'CALSCALE:GREGORIAN', ...ev, 'END:VCALENDAR']
      .join('\r\n').split('\r\n').map(dobrar).join('\r\n') + '\r\n';
  }
  function baixarIcs(editais, nome, opcoes) {
    const url = URL.createObjectURL(new Blob([ics(editais, opcoes)], {type: 'text/calendar'}));
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
      return `<li><a href="${esc(webcal)}" data-assinar="${esc(https)}" data-assinar-nome="${esc('Transferência de Medicina: ' + TM.faculdades[f].sigla)}" aria-expanded="false" data-medir="assinar_agenda">Assinar os prazos da ${esc(TM.faculdades[f].sigla)}</a></li>`;
    }).join('');
    // calendário único no Supabase (função agenda): uma assinatura com todas as faculdades da pessoa
    const cfg = window.TM_CONFIG || {};
    if (cfg.agendaUnica && cfg.supabaseUrl && fids.length <= 30) {  // a função agenda junta até 30 faculdades
      const https = `${cfg.supabaseUrl}/rest/v1/rpc/agenda?f=${fids.map(encodeURIComponent).join(',')}&apikey=${encodeURIComponent(cfg.supabaseAnon)}`;
      const webcal = https.replace(/^https?:/, 'webcal:');
      return `<div class="agenda-unica" id="${id}">
        <p class="acoes"><a class="botao sec" href="${esc(webcal)}" data-assinar="${esc(https)}" data-assinar-nome="Meus prazos (Transfermed)" aria-expanded="false" data-medir="assinar_agenda">Assinar meus prazos (${fids.length} ${fids.length === 1 ? 'faculdade' : 'faculdades'})</a></p>
        <details class="agenda-ajuda"><summary>Como assinar no Google, iPhone ou Outlook</summary>
          <p>Um calendário só, que se atualiza sozinho quando um edital muda ou essas faculdades publicam edital novo.</p>
          <ul><li><strong>iPhone e iPad:</strong> toque em "Assinar meus prazos" e confirme "Assinar".</li>
          <li><strong>Computador e Android:</strong> toque em "Assinar meus prazos" e escolha Google Agenda, Outlook ou "Copiar link do calendário" (para colar em outro app de agenda).</li></ul>
          <p class="dica">Se você salvar mais editais, assine de novo para incluir as faculdades novas. Prefere um arquivo? <button type="button" class="link-botao" data-baixar-ics>Baixar .ics</button> (não se atualiza).</p>
        </details></div>`;
    }
    return `<details class="agenda-ajuda" id="${id}"><summary>Assinar meus prazos (${fids.length} ${fids.length === 1 ? 'faculdade' : 'faculdades'})</summary>
      <p>Cada assinatura se atualiza sozinha quando o edital muda ou a faculdade publica edital novo.</p>
      <ul>${links}</ul>
      <p class="dica">iPhone e iPad: toque em "Assinar" e confirme. Computador e Android: toque em "Assinar" e escolha Google Agenda, Outlook ou "Copiar link do calendário".
      Prefere um arquivo? <button type="button" class="link-botao" data-baixar-ics>Baixar .ics</button> (não se atualiza).</p></details>`;
  }
  // Botões "Assinar" (a[data-assinar]): o webcal:// só tem app associado no iPhone/iPad. No computador e no Android o
  // clique abre um painel com Google Agenda, Outlook e "Copiar link do calendário" (nenhum botão depende do protocolo).
  const ehIOS = () => /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  function painelOpcoes(link) {
    const https = link.dataset.assinar;
    const webcal = https.replace(/^https?:/, 'webcal:');
    const nome = link.dataset.assinarNome || 'Prazos de transferência (Transfermed)';
    const p = document.createElement('div');
    p.className = 'assinar-opcoes';
    p.setAttribute('role', 'group');
    p.setAttribute('aria-label', 'Como assinar o calendário');
    p.innerHTML = `<a class="botao sec" href="https://calendar.google.com/calendar/r?cid=${encodeURIComponent(webcal)}" target="_blank" rel="noopener" data-medir="assinar_agenda">Adicionar ao Google Agenda<span class="oculto"> (abre em nova aba)</span></a>
      <a class="botao sec" href="https://outlook.live.com/calendar/0/addfromweb?url=${encodeURIComponent(https)}&amp;name=${encodeURIComponent(nome)}" target="_blank" rel="noopener" data-medir="assinar_agenda">Adicionar ao Outlook<span class="oculto"> (abre em nova aba)</span></a>
      <button type="button" class="botao sec" data-copiar-cal>Copiar link do calendário</button>
      <p class="dica" aria-live="polite" data-copiar-msg></p>`;
    p.querySelector('[data-copiar-cal]').addEventListener('click', async () => {
      const msg = p.querySelector('[data-copiar-msg]');
      try {
        await navigator.clipboard.writeText(https);
        msg.textContent = 'Link copiado. No seu app de agenda, escolha "Adicionar calendário por URL" (ou "Da Internet") e cole.';
      } catch (e) {  // navegador sem acesso à área de transferência (ex.: dentro do Instagram): o link fica à mão
        msg.innerHTML = 'Não deu para copiar sozinho. Copie o link abaixo e cole no seu app de agenda:';
        const campo = Object.assign(document.createElement('input'), {type: 'text', value: https, readOnly: true, className: 'campo-link'});
        campo.setAttribute('aria-label', 'Link do calendário');
        msg.after(campo); campo.focus(); campo.select();
      }
      medir('assinar_agenda');
    });
    return p;
  }
  document.addEventListener('click', ev => {
    const link = ev.target.closest('a[data-assinar]');
    if (!link || ehIOS()) return;  // iPhone/iPad: o webcal:// abre o app Calendário
    ev.preventDefault();
    // o painel entra logo depois da linha de botões; numa lista, dentro do próprio item
    const item = link.closest('li');
    const ancora = item || link.closest('.acoes') || link;
    const vizinho = item ? item.querySelector('.assinar-opcoes') : ancora.nextElementSibling;
    let p = vizinho && vizinho.classList.contains('assinar-opcoes') ? vizinho : null;
    if (!p) { p = painelOpcoes(link); if (item) item.append(p); else ancora.after(p); }
    else p.hidden = !p.hidden;
    link.setAttribute('aria-expanded', String(!p.hidden));
    if (!p.hidden) p.querySelector('a').focus();
  });

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

  // ---------------------------------------------------------------- radar da home (chips, grupos, cartão, abertura)
  // Regras com cópia fiel em gerar_site.py (ponto_radar, no_filtro, resumo_radar): mudar aqui é mudar lá.
  const semMovimento = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
  function estadoEdital(e) {
    if (e.fluxo === 'vagas') return 'aberto';
    if (e.fluxo) return 'contínuo';
    const h = hoje();
    if (!e.fim || h > e.fim) return 'encerrado';
    return e.ini && h < e.ini ? 'em breve' : 'aberto';
  }
  function radarPontos() {
    const porFac = {};
    for (const e of TM.editais) (porFac[e.fid] = porFac[e.fid] || []).push(e);
    const h = hoje(), mesHoje = Number(h.slice(5, 7)), prox = mesHoje % 12 + 1;
    return Object.values(TM.faculdades).map(f => {
      const eds = porFac[f.id] || [];
      const abertos = eds.filter(e => estadoEdital(e) === 'aberto'), breve = eds.filter(e => estadoEdital(e) === 'em breve');
      let ed = null, dias = null, st, quando;
      if (abertos.length) {
        const comFim = abertos.filter(e => e.fluxo !== 'vagas').sort((a, b) => a.fim.localeCompare(b.fim));
        ed = comFim[0] || abertos[0];
        if (comFim.length) {
          dias = diasEntre(h, ed.fim);
          st = dias <= 7 ? 'encerra' : 'aberto';
          quando = dias <= 0 ? 'encerra hoje' : `encerra em ${dias} ${dias === 1 ? 'dia' : 'dias'}`;
        } else { st = 'aberto'; quando = 'abertas até completar as vagas'; }
      } else if (breve.length) {
        ed = breve.slice().sort((a, b) => a.ini.localeCompare(b.ini))[0];
        st = 'breve'; quando = `inscrições abrem em ${fmt(ed.ini)}`;
      } else if (eds.some(e => e.fluxo === true)) {
        ed = eds.find(e => e.fluxo === true); st = 'sem'; quando = 'pedidos o ano todo, sem edital';
      } else {
        const meses = f.meses || [];
        const mes = meses.includes(prox) ? prox : meses.includes(mesHoje) ? mesHoje : null;
        [st, quando] = mes ? ['breve', `costuma abrir em ${MESES[mes - 1]}`] : ['sem', 'sem edital aberto agora'];
      }
      let req = ((ed && ed.quem) || '').split(';')[0].trim();
      if (req.length > 110) req = req.slice(0, 107).replace(/\s+\S*$/, '') + '…';
      const [x, y] = proj(f.lat, f.lon);
      return {fid: f.id, sigla: f.sigla, nome: f.nome, cidade: f.cidade, uf: f.uf, x, y, st, dias, quando, req,
              slug: ed ? ed.slug : null, n: abertos.length, ext: abertos.some(e => e.ext === true), pub: (f.tipo || '').startsWith('pública')};
    });
  }
  const aberta = p => p.st === 'aberto' || p.st === 'encerra';
  const FILTROS = {
    abertos: p => aberta(p) || p.st === 'breve', semana: p => p.st === 'encerra',
    exterior: p => aberta(p) && p.ext, publicas: p => p.pub
  };
  const plural = (k, um, varios) => `${k} ${k === 1 ? um : varios}`;
  function resumoRadar(pontos, filtro) {
    const dentro = pontos.filter(FILTROS[filtro]), n = dentro.filter(aberta).length;
    if (filtro === 'abertos') {
      const nb = dentro.filter(p => p.st === 'breve').length;
      return plural(n, 'faculdade com inscrição aberta', 'faculdades com inscrição aberta') + (nb ? ` · ${nb} ${nb === 1 ? 'abre' : 'abrem'} em breve` : '');
    }
    if (filtro === 'semana') return plural(n, 'faculdade com inscrição encerrando em até 7 dias', 'faculdades com inscrição encerrando em até 7 dias');
    if (filtro === 'exterior') return plural(n, 'faculdade com inscrição aberta aceita', 'faculdades com inscrição aberta aceitam') + ' quem vem do exterior';
    return plural(dentro.length, 'faculdade pública', 'faculdades públicas') + ` · ${n} com inscrição aberta`;
  }
  const ORDEM_ST = {encerra: 0, aberto: 1, breve: 2, conferir: 2, sem: 3};
  const ordenarPontos = l => l.slice().sort((a, b) => ORDEM_ST[a.st] - ORDEM_ST[b.st] || (a.dias ?? 999) - (b.dias ?? 999) || a.sigla.localeCompare(b.sigla));
  const linkPonto = p => p.slug ? `${RAIZ}edital/${esc(p.slug)}/` : `${RAIZ}faculdade/${esc(p.fid)}/`;


  // ---------------------------------------------------------------- radar pessoal (Parte C): "De onde você quer sair?"
  // Uma pergunta (cidade) e dois controles (período e distância). O mapa responde na hora, com a MESMA conta do diagnóstico
  // (avaliar + periodoStatus) sobre os dados já publicados; nada é enviado a servidor. Estado no localStorage (tm_radar).
  // `api` vem do radarHome: pontos, vista, desenhar, definirPessoal. Devolve true se abriu já no radar salvo do aluno.
  const QUALQUER_KM = 1600;  // fim do controle deslizante = "qualquer distância" (igual a gerar_site.KM_MAX)
  function poligonoRaio(c, km) {  // círculo geodésico projetado (a elipse que o mapa de fato mostra)
    const R = 6371, [la, lo] = c.map(v => v * Math.PI / 180), d = km / R, pts = [];
    for (let i = 0; i < 72; i++) {
      const b = i * 2 * Math.PI / 72;
      const la2 = Math.asin(Math.sin(la) * Math.cos(d) + Math.cos(la) * Math.sin(d) * Math.cos(b));
      const lo2 = lo + Math.atan2(Math.sin(b) * Math.sin(d) * Math.cos(la), Math.cos(d) - Math.sin(la) * Math.sin(la2));
      pts.push(proj(la2 * 180 / Math.PI, lo2 * 180 / Math.PI));
    }
    return pts;
  }
  const textoKmRadar = km => km >= QUALQUER_KM ? 'qualquer distância' : `até ${km.toLocaleString('pt-BR')} km`;
  const paraFimDePrazo = x => (x.e.fim && !x.e.fluxo ? 0 : 1);
  const porPrazo = (a, b) => paraFimDePrazo(a) - paraFimDePrazo(b) || String(a.e.fim).localeCompare(String(b.e.fim)) || (a.dist ?? 1e9) - (b.dist ?? 1e9);
  const quandoFecha = dias => dias <= 0 ? 'fecha hoje' : `fecha em ${dias} ${dias === 1 ? 'dia' : 'dias'}`;

  function radarPessoal(api) {
    const raiz = $('#rp');
    if (!raiz) return false;
    const campo = $('#rp-cidade'), lista = $('#rp-lista'), dica = $('#rp-dica');
    const parteCont = $('#rp-cont'), parteRes = $('#rp-res');
    const cont = {get hidden() { return parteCont.hidden; }, set hidden(v) { parteCont.hidden = v; parteRes.hidden = v; }};  // as duas metades do painel aparecem e somem juntas
    const nEl = $('#rp-n'), nTxt = $('#rp-n-txt'), primeira = $('#rp-primeira'), top = $('#rp-top'), todos = $('#rp-todos');
    const mais = $('#rp-mais'), maisP = $('#rp-mais-p'), conferirEl = $('#rp-conferir'), vazio = $('#rp-vazio'), onde = $('#rp-onde'), novosEl = $('#rp-novos');
    const km = $('#rp-km'), kmV = $('#rp-km-v'), completo = $('#r3-completo'), fig = api.fig;
    campo.disabled = false;

    // ---- fato do dia ("Hoje o robô viu"): o HTML é gerado uma vez por dia; aberto dias depois, diz a data da rodada
    const robo = $('#rp-robo');
    if (robo && robo.dataset.dia && robo.dataset.dia !== hoje()) {
      const hj = $('.rp-hj', robo);
      if (hj) hj.textContent = `Em ${fmt(robo.dataset.dia).slice(0, 5)}`;
    }

    // ---- cidades: a lista completa (assets/municipios.json) só baixa no primeiro foco; sem rede, as cidades das faculdades
    let cidades = null, carregando = null;
    const preparar = js => {
      const comFac = new Set(Object.values(TM.faculdades).map(f => norm(f.cidade) + '|' + f.uf));
      cidades = js.map(([n, uf, la, lo]) => ({n, uf, la, lo, q: norm(n).replace(/[^a-z0-9]+/g, ' ').trim(), fac: comFac.has(norm(n) + '|' + uf)}));
    };
    const daBase = () => {
      const vistos = new Map();
      for (const f of Object.values(TM.faculdades)) vistos.set(`${f.cidade}|${f.uf}`, [f.cidade, f.uf, f.lat, f.lon]);
      return [...vistos.values()];
    };
    const carregar = () => carregando || (carregando = fetch(RAIZ + 'assets/municipios.json').then(r => r.json()).then(preparar)
      .catch(() => { preparar(daBase()); dica.textContent = 'Sem internet: só as cidades das faculdades estão na lista.'; }));
    function buscar(texto) {  // "Ribeirão Pr" acha Ribeirão Preto; "palmas to" acha Palmas (TO); sem acento e sem maiúscula
      const q = norm(texto).replace(/[^a-z0-9]+/g, ' ').trim();
      if (q.length < 2 || !cidades) return [];
      const termos = q.split(' ');
      const achadas = cidades.filter(c => {
        const nome = c.q.split(' '), uf = norm(c.uf);
        let i = 0;
        return termos.every(t => {
          if (t === uf) return true;
          while (i < nome.length) if (nome[i++].startsWith(t)) return true;
          return false;
        });
      });
      const ini = c => (c.q.startsWith(q) ? 0 : 1);
      return achadas.sort((a, b) => ini(a) - ini(b) || (b.fac - a.fac) || a.n.length - b.n.length || a.n.localeCompare(b.n, 'pt')).slice(0, 6);
    }
    let sugestoes = [], ativa = -1;
    const fecharLista = () => { lista.hidden = true; campo.setAttribute('aria-expanded', 'false'); campo.removeAttribute('aria-activedescendant'); ativa = -1; };
    function pintarLista() {
      lista.innerHTML = sugestoes.map((c, i) => `<li role="option" id="rp-o-${i}" data-i="${i}" aria-selected="${i === ativa}">${esc(c.n)}<small>${esc(c.uf)}${c.fac ? ' · tem faculdade' : ''}</small></li>`).join('');
      lista.hidden = !sugestoes.length;
      campo.setAttribute('aria-expanded', String(sugestoes.length > 0));
      if (ativa >= 0) campo.setAttribute('aria-activedescendant', `rp-o-${ativa}`); else campo.removeAttribute('aria-activedescendant');
    }
    async function digitou() {
      dica.classList.remove('erro');
      await carregar();
      const t = campo.value.trim();
      sugestoes = buscar(t); ativa = sugestoes.length ? 0 : -1;
      pintarLista();
      dica.textContent = !t || sugestoes.length || t.length < 3 ? 'Escolha a cidade na lista. Nada é enviado: o cálculo roda no seu aparelho.' : 'Não achamos essa cidade. Confira o nome (ex.: Ribeirão Preto).';
      if (t.length >= 3 && !sugestoes.length) dica.classList.add('erro');
    }
    campo.addEventListener('focus', carregar);
    campo.addEventListener('input', digitou);
    campo.addEventListener('keydown', ev => {
      if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
        if (!sugestoes.length) return;
        ev.preventDefault();
        ativa = (ativa + (ev.key === 'ArrowDown' ? 1 : -1) + sugestoes.length) % sugestoes.length; pintarLista();
        $(`#rp-o-${ativa}`, lista).scrollIntoView({block: 'nearest'});
      } else if (ev.key === 'Enter') {
        ev.preventDefault();
        if (sugestoes.length) escolherCidade(sugestoes[Math.max(ativa, 0)]);
      } else if (ev.key === 'Escape' && !lista.hidden) { ev.preventDefault(); fecharLista(); }
    });
    lista.addEventListener('mousedown', ev => ev.preventDefault());  // o clique na opção não tira o foco do campo antes da escolha
    lista.addEventListener('click', ev => { const li = ev.target.closest('li[data-i]'); if (li) escolherCidade(sugestoes[Number(li.dataset.i)]); });
    campo.addEventListener('blur', () => setTimeout(fecharLista, 120));

    // ---- a conta: a mesma do diagnóstico (avaliar), só editais com inscrição aberta hoje
    const estado = {cidade: null, nome: '', coords: null, semestre: 0, raio: 400};
    const perfil = () => ({curso: 'medicina', origem: 'brasil', faculdade: '', tipo: 'todas', semestre: estado.semestre || 0, coords: estado.coords,
      raio: estado.raio >= QUALQUER_KM ? 0 : estado.raio, taxaMax: null});
    function chances() {
      const p = perfil(), sim = [], conferir = [];
      for (const e of TM.editais) {
        if (estadoEdital(e) !== 'aberto') continue;
        const r = avaliar(e, p);
        if (r.motivos.length) continue;
        const per = periodoStatus(e, estado.semestre);
        if (per.s === 'nao') continue;
        (per.s === 'sim' ? sim : conferir).push({e, f: TM.faculdades[e.fid] || {}, dist: r.dist, per});
      }
      return {sim: sim.sort(porPrazo), conferir: conferir.sort(porPrazo)};
    }
    // gancho dos testes de navegador: a conta do diagnóstico (avaliar) direta, para comparar com o número do painel
    window.TM_radar_teste = {periodo: periodoStatus, contar: pf => TM.editais.filter(e => estadoEdital(e) === 'aberto'
      && !avaliar(e, {curso: 'medicina', origem: 'brasil', faculdade: '', tipo: 'todas', taxaMax: null, ...pf}).motivos.length && periodoStatus(e, pf.semestre).s === 'sim').length};
    const diasDe = x => (x.e.fim && !x.e.fluxo ? diasEntre(hoje(), x.e.fim) : null);
    const linkPdf = e => (e.pv && /\.pdf($|[?#])/i.test(e.url || '')
      ? `<p class="periodo"><a href="${esc(e.url)}#page=${e.pv}" target="_blank" rel="noopener" data-medir="abrir_pdf">Ver no PDF, p. ${e.pv} →<span class="oculto"> (abre em nova aba)</span></a></p>` : '');
    function pontosPessoais(res) {
      const porFid = new Map();
      for (const [lista, chave] of [[res.sim, 'sim'], [res.conferir, 'conferir']])
        for (const x of lista) { const g = porFid.get(x.e.fid) || {sim: [], conferir: []}; g[chave].push(x); porFid.set(x.e.fid, g); }
      const base = new Map(api.pontos.map(p => [p.fid, p])), out = [];
      for (const [fid, g] of porFid) {
        const b = base.get(fid);
        if (!b) continue;
        const x = g.sim[0] || g.conferir[0], dias = g.sim.length ? diasDe(x) : null;
        const st = !g.sim.length ? 'conferir' : dias !== null && dias <= 7 ? 'encerra' : 'aberto';
        const quando = !g.sim.length ? 'confirme o período no edital' : dias === null ? 'inscrições abertas até completar as vagas' : quandoFecha(dias);
        const det = [
          g.sim.length && x.per.rotulos.length ? `<p class="periodo">Aceita o seu período · vagas: ${esc(x.per.rotulos.join(' · '))}</p>` : '',
          !g.sim.length ? '<p class="avisa">O quadro de vagas não deixa o período claro: confirme no edital.</p>' : '',
          g.sim.length && x.e.fim && !x.e.fluxo ? `<p class="periodo">Fecha ${fmt(x.e.fim)}</p>` : '',
          x.e.exc === true ? '<p class="avisa">Não aceita quem já fez transferência.</p>' : '',
          linkPdf(x.e)].join('');
        out.push({...b, st, dias, quando, slug: x.e.slug, n: g.sim.length, per: x.per.s, det});
      }
      return out;
    }

    // ---- mapa: centralizar na cidade, círculo do raio, radar que gira a partir dali
    const aneis = $('.r3-aneis', fig), gPessoa = $('.r3-pessoa', fig), feixe = api.feixe;
    const aneisOriginal = aneis.getAttribute('transform');
    function vistaDoRaio() {
      if (estado.raio >= QUALQUER_KM) return '0 0 400 400';
      const pts = poligonoRaio(estado.coords, estado.raio), xs = pts.map(q => q[0]), ys = pts.map(q => q[1]);
      const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
      const lado = Math.max(70, (x1 - x0) * 1.25, (y1 - y0) * 1.25);
      if (lado >= 400) return '0 0 400 400';
      const vx = Math.max(0, Math.min(400 - lado, (x0 + x1) / 2 - lado / 2)), vy = Math.max(0, Math.min(400 - lado, (y0 + y1) / 2 - lado / 2));
      return `${vx.toFixed(1)} ${vy.toFixed(1)} ${lado.toFixed(1)} ${lado.toFixed(1)}`;
    }
    function desenharPessoa() {  // chamado a cada desenho do mapa (o tamanho em tela depende do zoom)
      gPessoa.textContent = '';
      if (!estado.coords) return;
      const k = api.escala(), [x, y] = proj(estado.coords[0], estado.coords[1]);
      if (estado.raio < QUALQUER_KM) {
        const d = poligonoRaio(estado.coords, estado.raio).map((q, i) => `${i ? 'L' : 'M'}${q[0].toFixed(1)} ${q[1].toFixed(1)}`).join('') + 'Z';
        const c = document.createElementNS(NS, 'path'); c.setAttribute('class', 'raio'); c.setAttribute('d', d); gPessoa.append(c);
      }
      for (const [cl, r] of [['eu-anel', 11 / k], ['eu', 5.5 / k]]) {
        const c = document.createElementNS(NS, 'circle'); c.setAttribute('class', cl); c.setAttribute('cx', x.toFixed(1)); c.setAttribute('cy', y.toFixed(1)); c.setAttribute('r', r.toFixed(2)); gPessoa.append(c);
      }
    }
    function moverRadar() {  // o feixe e os anéis passam a sair da cidade, com o raio do círculo escolhido
      const [x, y] = proj(estado.coords[0], estado.coords[1]);
      const escala = estado.raio >= QUALQUER_KM ? 1 : Math.max(.12, Math.min(1, (estado.raio / 111.2 * 10) / 150));
      aneis.setAttribute('transform', `translate(${x.toFixed(1)} ${y.toFixed(1)}) scale(${escala.toFixed(3)})`);
      api.moverCentro(x, y);
    }
    function girar() {
      if (semMovimento() || !feixe.animate) return;
      feixe.animate([{transform: 'rotate(-90deg)'}, {transform: 'rotate(270deg)'}], {duration: 900, easing: 'linear'});
    }
    function acender() {  // as faculdades do radar acendem uma a uma, da mais perto para a mais longe (até 0,9 s no total)
      if (semMovimento()) return;
      const [cx, cy] = proj(estado.coords[0], estado.coords[1]);
      const pts = [...api.gPts.querySelectorAll('.pt')].map(a => ({a, d: Math.hypot(a._g.x - cx, a._g.y - cy)})).sort((u, v) => u.d - v.d);
      pts.forEach(({a}, i) => a.animate([{opacity: 0, transform: 'scale(.3)'}, {opacity: 1, transform: 'scale(1.3)', offset: .6}, {opacity: 1, transform: 'scale(1)'}],
        {duration: 320, delay: Math.min(580, i * 580 / Math.max(1, pts.length)), easing: 'ease-out', fill: 'backwards'}));
    }

    // ---- painel: número que conta, os 3 que fecham primeiro, "+ N no seu radar"
    let nMostrado = 0, nToken = 0;
    function contar(alvo) {
      const token = ++nToken, de = nMostrado;
      if (semMovimento() || de === alvo) { nMostrado = alvo; nEl.textContent = alvo; return; }
      const t0 = performance.now(), dur = 420;
      (function passo(t) {
        if (token !== nToken) return;
        const f = Math.min(1, (t - t0) / dur);
        nMostrado = Math.round(de + (alvo - de) * (1 - Math.pow(1 - f, 3)));
        nEl.textContent = nMostrado;
        if (f < 1) requestAnimationFrame(passo); else { nMostrado = alvo; nEl.textContent = alvo; }
      })(t0);
    }
    const linhaEdital = (x, conferir) => {
      const dias = diasDe(x), st = conferir ? 'conferir' : dias !== null && dias <= 7 ? 'encerra' : 'aberto';
      const q = conferir ? 'confirme no edital' : dias === null ? 'aberto' : quandoFecha(dias);
      return `<li><a href="${RAIZ}edital/${esc(x.e.slug)}/"><i class="${st}" aria-hidden="true"></i><span class="rp-nome"><b>${esc(x.f.sigla)}</b><small>${esc(x.f.cidade)}/${esc(x.f.uf)}</small></span><span class="rp-q ${st}">${esc(q)}</span></a></li>`;
    };
    let ultimo = null;
    function pintar(res) {
      ultimo = res;
      const n = res.sim.length, sem = estado.semestre;
      const [nome, uf] = [estado.nome, (estado.cidade || '').slice(-2)];
      onde.textContent = `${nome} · ${uf}${sem ? ` · ${sem}º período` : ''} · ${textoKmRadar(estado.raio)}`;
      contar(n);
      nTxt.innerHTML = `<span class="oculto">${n} </span>` + (sem ? `${n === 1 ? 'edital aberto que aceita' : 'editais abertos que aceitam'} o seu período` : `${n === 1 ? 'edital aberto' : 'editais abertos'} ${estado.raio >= QUALQUER_KM ? 'no Brasil' : textoKmRadar(estado.raio)}`);
      const dias = res.sim.map(diasDe).filter(d => d !== null);
      primeira.textContent = dias.length ? `A primeira ${quandoFecha(Math.min(...dias))}.` : '';
      vazio.hidden = n > 0;
      top.innerHTML = res.sim.slice(0, 3).map(x => linhaEdital(x, false)).join('');
      todos.innerHTML = res.sim.slice(3).map(x => linhaEdital(x, false)).join('');
      todos.hidden = true; mais.setAttribute('aria-expanded', 'false');
      maisP.hidden = n <= 3;
      mais.textContent = `+ ${n - 3} no seu radar`;
      conferirEl.hidden = !res.conferir.length;
      if (res.conferir.length) conferirEl.innerHTML = `Mais ${res.conferir.length} com o período <b>a confirmar no edital</b> (não entram na conta): `
        + res.conferir.map(x => `<a href="${RAIZ}edital/${esc(x.e.slug)}/">${esc(x.f.sigla)}</a>`).join(', ') + '.';
    }
    mais.addEventListener('click', () => {
      const abrir = todos.hidden;
      todos.hidden = !abrir; mais.setAttribute('aria-expanded', String(abrir));
      mais.textContent = abrir ? 'Mostrar menos' : `+ ${(ultimo ? ultimo.sim.length : 0) - 3} no seu radar`;
    });

    let quadro = 0;
    function aplicar({vista, revelar} = {}) {
      const res = chances();
      const pts = pontosPessoais(res);
      const n = res.sim.length;
      const resumo = `${n} ${n === 1 ? 'edital aberto' : 'editais abertos'}${estado.semestre ? ` · ${estado.semestre}º período` : ''} · ${textoKmRadar(estado.raio)}`;
      moverRadar();
      api.definirPessoal({pontos: pts, resumo}, vista === 'animar' ? vistaDoRaio() : vista === 'ajustar' ? vistaDoRaio() : null, vista === 'animar');
      pintar(res);
      fig.classList.add('pessoal'); completo.hidden = false;
      if (revelar) { girar(); acender(); }
      return res;
    }
    api.aoDesenhar(desenharPessoa);
    function salvar() {
      armazem.gravar('tm_radar', {cidade: estado.cidade, nome: estado.nome, coords: estado.coords, semestre: estado.semestre, raio: estado.raio});
    }
    const guardarVistos = res => armazem.gravar('tm_radar_vistos', res.sim.map(x => x.e.id));

    function escolherCidade(c) {
      if (!c) return;
      estado.cidade = `${c.n} - ${c.uf}`; estado.nome = c.n; estado.coords = [c.la, c.lo];
      campo.value = `${c.n} · ${c.uf}`;
      sugestoes = []; fecharLista(); dica.textContent = ''; dica.classList.remove('erro');
      cont.hidden = false; novosEl.hidden = true;
      const res = aplicar({vista: 'animar', revelar: true});
      guardarVistos(res); salvar();
      medir('radar_cidade');
      campo.blur();
      $('#rp-n-txt').closest('.rp-num').scrollIntoView({block: 'nearest', behavior: semMovimento() ? 'auto' : 'smooth'});
    }

    // período em pílulas e distância no controle deslizante
    raiz.querySelectorAll('input[name="rp-periodo"]').forEach(r => r.addEventListener('change', () => {
      estado.semestre = Number(r.value);
      guardarVistos(aplicar({vista: null})); salvar(); medir('radar_periodo');
    }));
    const textoSlider = () => {
      const t = textoKmRadar(estado.raio); kmV.textContent = t; km.setAttribute('aria-valuetext', t);
      km.style.setProperty('--p', `${((estado.raio - Number(km.min)) / (Number(km.max) - Number(km.min)) * 100).toFixed(1)}%`);  // trecho preenchido da barra
    };
    km.addEventListener('input', () => {
      estado.raio = Number(km.value); textoSlider();
      if (quadro) return;
      quadro = requestAnimationFrame(() => { quadro = 0; aplicar({vista: 'ajustar'}); });  // um desenho por quadro, mesmo arrastando rápido
    });
    km.addEventListener('change', () => { cancelAnimationFrame(quadro); quadro = 0; guardarVistos(aplicar({vista: 'ajustar'})); salvar(); medir('radar_distancia'); });

    function sairDoModo() {  // o radar volta a sair do centro do Brasil e o mapa a mostrar todas as faculdades
      aneis.setAttribute('transform', aneisOriginal); api.moverCentro(...api.centroOriginal);
      fig.classList.remove('pessoal'); completo.hidden = true;
    }
    function trocarCidade() {
      estado.cidade = null; estado.coords = null; estado.nome = '';
      campo.value = ''; cont.hidden = true; novosEl.hidden = true;
      armazem.apagar('tm_radar'); armazem.apagar('tm_radar_vistos');
      aneis.setAttribute('transform', aneisOriginal); api.moverCentro(...api.centroOriginal);
      sairDoModo();
      api.definirPessoal(null, '0 0 400 400', true);
      campo.focus();
    }
    $('#rp-trocar').addEventListener('click', trocarCidade);
    completo.addEventListener('click', () => {  // volta ao mapa de todas as faculdades; o painel continua com o seu radar
      sairDoModo();
      api.definirPessoal(null, '0 0 400 400', true);
    });
    api.aoSair(sairDoModo);

    // alerta já preenchido com o que a pessoa escolheu (a mesma função do cartão da home; o consentimento nunca vem marcado)
    $('#rp-avise').addEventListener('click', () => {
      medir('radar_alerta');
      const form = $('#form-alerta'), secao = $('#alerta');
      if (!form || !secao) { location.href = RAIZ + 'diagnostico/'; return; }
      const base = {curso: 'medicina', origem: 'brasil', cidade: estado.cidade, coords: estado.coords, raio: estado.raio >= QUALQUER_KM ? 0 : estado.raio, tipo: 'todas',
        ...(estado.semestre ? {semestre: estado.semestre} : {})};
      form.dataset.perfilBase = JSON.stringify(base);
      let nota = $('#alerta-radar');
      if (!nota) {
        nota = document.createElement('p'); nota.id = 'alerta-radar'; nota.className = 'alerta-radar';
        form.insertBefore(nota, form.firstChild);
      }
      nota.innerHTML = `Alerta do seu radar: ${estado.semestre ? `${estado.semestre}º período · ` : ''}${esc(textoKmRadar(estado.raio))} de ${esc(estado.nome)}. <button type="button" class="link-botao" id="alerta-radar-tirar">Tirar</button>`;
      $('#alerta-radar-tirar').addEventListener('click', () => { form.dataset.perfilBase = '{"curso": "medicina"}'; nota.remove(); });
      secao.scrollIntoView({block: 'center', behavior: semMovimento() ? 'auto' : 'smooth'});
      form.elements.email.focus({preventScroll: true});
    });

    // ---- volta do aluno: a home abre no radar salvo, com o que mudou desde a última visita (só se houver novos)
    const salvo = armazem.ler('tm_radar', null);
    const coordsOk = c => Array.isArray(c) && c.length === 2 && c.every(v => typeof v === 'number' && isFinite(v));
    if (salvo && coordsOk(salvo.coords) && typeof salvo.nome === 'string') {
      estado.cidade = String(salvo.cidade || ''); estado.nome = salvo.nome; estado.coords = salvo.coords;
      estado.semestre = Math.max(0, Math.min(12, Number(salvo.semestre) || 0));
      estado.raio = Math.max(100, Math.min(QUALQUER_KM, Number(salvo.raio) || 400));
      campo.value = `${estado.nome} · ${estado.cidade.slice(-2)}`;
      km.value = String(estado.raio); textoSlider();
      const pil = raiz.querySelector(`input[name="rp-periodo"][value="${estado.semestre}"]`); if (pil) pil.checked = true;
      cont.hidden = false;
      const antes = armazem.ler('tm_radar_vistos', null);
      const res = aplicar({vista: 'ajustar'});
      const novos = Array.isArray(antes) ? res.sim.filter(x => !antes.includes(x.e.id)) : [];
      if (novos.length) {
        novosEl.hidden = false;
        novosEl.textContent = `O que mudou desde a sua última visita: ${novos.length} ${novos.length === 1 ? 'edital novo' : 'editais novos'} (${novos.slice(0, 3).map(x => x.f.sigla).join(', ')}${novos.length > 3 ? '…' : ''}).`;
      }
      guardarVistos(res);
      raiz.classList.remove('salvo');
      return true;
    }
    raiz.classList.remove('salvo');  // dado salvo inválido ou ausente: solta o espaço reservado
    textoSlider();
    return false;
  }

  function radarHome(fig) {
    const svg = $('.r3-svg', fig), gPts = $('.r3-pontos', fig), gFundo = $('.r3-fundo', fig), feixe = $('.r3-feixe', fig);
    const cartao = $('#r3-cartao'), resumo = $('#r3-resumo'), lista = $('#lista3'), titulo = $('#t-lista'), mais = $('#lista3-mais');
    const caixaMapa = $('.r3-mapa', fig);
    const BRASIL = '0 0 400 400';
    let [CX, CY] = (() => { const m = $('.r3-aneis', fig).getAttribute('transform').match(/([\d.]+) ([\d.]+)/); return [Number(m[1]), Number(m[2])]; })();
    const pontos = radarPontos();
    let filtro = 'abertos', vista = BRASIL, aberto = null, listaAberta = false;
    let pessoal = null, depois = null, aoSair = null;  // radar pessoal: {pontos, resumo} (só as faculdades do radar do aluno) e o gancho que desenha o raio
    const CENTRO0 = [CX, CY];
    const visiveis = () => pessoal ? pessoal.pontos : pontos.filter(FILTROS[filtro]);
    gPts.removeAttribute('aria-hidden');

    // px por unidade do mapa (o SVG encaixa pela largura ou pela altura: a matriz da tela já considera os dois)
    const escala = () => { const m = svg.getScreenCTM(); return m && m.a ? m.a : svg.getBoundingClientRect().width / Number(vista.split(' ')[2]); };
    const angulo = (x, y) => ((Math.atan2(y - CY, x - CX) * 180 / Math.PI + 90) % 360 + 360) % 360;  // 0 = norte, horário
    function grupos(lst) {
      const lim = 44 / escala();  // alvos de 44 px nunca se sobrepõem: pontos mais próximos que isso viram um grupo
      const gs = [];
      for (const p of ordenarPontos(lst)) {
        const g = gs.find(g => Math.hypot(g.x - p.x, g.y - p.y) < lim);
        if (g) g.itens.push(p); else gs.push({x: p.x, y: p.y, itens: [p]});
      }
      return gs;
    }
    const el = (t, a) => { const n = document.createElementNS(NS, t); for (const k in a) n.setAttribute(k, a[k]); return n; };
    function desenhar() {
      svg.setAttribute('viewBox', vista);
      const k = escala(), r = 5 / k;
      feixe.style.visibility = vista === BRASIL || pessoal ? '' : 'hidden';  // ampliado, o feixe vira faixas largas (no radar pessoal ele tem o tamanho do raio)
      gFundo.textContent = ''; gPts.textContent = '';
      const dentro = visiveis(), ids = new Set(dentro.map(p => p.fid));
      for (const p of pontos) if (!ids.has(p.fid)) gFundo.append(el('circle', {cx: p.x.toFixed(1), cy: p.y.toFixed(1), r: (2 / k).toFixed(2)}));
      for (const g of grupos(dentro)) {
        const a = el('a', {class: 'pt', href: g.itens.length > 1 ? '#' : linkPonto(g.itens[0]), role: 'button', 'aria-expanded': 'false', 'aria-controls': 'r3-cartao'});
        a.dataset.ang = angulo(g.x, g.y).toFixed(1);
        a.append(el('circle', {class: 'alvo', cx: g.x.toFixed(1), cy: g.y.toFixed(1), r: (22 / k).toFixed(2)}));
        if (g.itens.length > 1) {
          a.classList.add('grupo');
          a.append(el('circle', {class: 'nucleo', cx: g.x.toFixed(1), cy: g.y.toFixed(1), r: (12 / k).toFixed(2)}));
          const t = el('text', {x: g.x.toFixed(1), y: g.y.toFixed(1), 'font-size': (11 / k).toFixed(2)});
          t.textContent = g.itens.length; a.append(t);
          a.setAttribute('aria-label', `Grupo de ${g.itens.length} faculdades: ${g.itens.map(p => p.sigla).join(', ')}`);
        } else {
          const p = g.itens[0];
          a.classList.add(p.st);
          if (p.st === 'encerra') a.append(el('circle', {class: 'onda', cx: p.x.toFixed(1), cy: p.y.toFixed(1), r: r.toFixed(2)}));
          a.append(el('circle', {class: 'nucleo', cx: p.x.toFixed(1), cy: p.y.toFixed(1), r: (p.st === 'sem' ? r * .7 : r).toFixed(2)}));
          a.setAttribute('aria-label', `${p.sigla}, ${p.cidade}/${p.uf}: ${p.quando}`);
        }
        a.addEventListener('click', ev => { ev.preventDefault(); medir(g.itens.length > 1 ? 'radar_grupo' : 'radar_ponto'); abrir(g, a); });
        a._g = g;
        gPts.append(a);
      }
      const txt = pessoal ? pessoal.resumo : resumoRadar(pontos, filtro);
      resumo.textContent = txt; titulo.textContent = txt;
      svg.setAttribute('aria-label', `Mapa: ${txt}. A lista completa está logo abaixo.`);
      fig.querySelectorAll('[data-uf]').forEach(b => {
        const n = dentro.filter(p => p.uf === b.dataset.uf && aberta(p)).length;
        b.innerHTML = `${esc(b.dataset.uf)} · <b>${n}</b><span class="oculto"> ${n === 1 ? 'faculdade' : 'faculdades'} com inscrição aberta (${esc(b.dataset.nome)})</span>`;
      });
      fig.querySelectorAll('[data-vista]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.vista === vista)));
      listar(dentro);
      if (depois) depois();
    }
    function listar(dentro) {
      const l = ordenarPontos(dentro);
      lista.innerHTML = l.map((p, i) => `<li${i >= 8 && !listaAberta ? ' hidden' : ''}><a href="${linkPonto(p)}"><i class="${p.st}" aria-hidden="true"></i><span><b>${esc(p.sigla)}</b><small>${esc(p.cidade)}/${esc(p.uf)}</small></span><span class="q ${p.st}">${esc(p.quando)}</span></a></li>`).join('')
        || '<li class="vazio">Nenhuma faculdade neste filtro hoje.</li>';
      if (mais) { mais.hidden = listaAberta || l.length <= 8; mais.textContent = `Mostrar todas as ${l.length} faculdades`; }
    }
    if (mais) mais.addEventListener('click', () => { listaAberta = true; lista.querySelectorAll('li[hidden]').forEach(li => li.hidden = false); mais.hidden = true; });

    // cartão (computador) e gaveta (celular)
    const celular = () => matchMedia('(max-width:860px)').matches;
    function abrir(g, alvo) {
      if (aberto && aberto !== alvo) aberto.setAttribute('aria-expanded', 'false');
      aberto = alvo; alvo.setAttribute('aria-expanded', 'true');
      const topo = '<span class="alca" aria-hidden="true"></span><button type="button" class="fechar" aria-label="Fechar">×</button>';
      if (g.itens.length > 1) {
        cartao.innerHTML = `${topo}<h3 id="r3-cartao-t" tabindex="-1">${g.itens.length} faculdades aqui</h3><p class="onde">Toque numa para ver os detalhes</p>
          <ul>${g.itens.map((p, i) => `<li><button type="button" data-i="${i}"><span><b>${esc(p.sigla)}</b> · ${esc(p.cidade)}/${esc(p.uf)}</span><small class="${p.st}">${esc(p.quando)}</small></button></li>`).join('')}</ul>`;
        cartao.querySelectorAll('[data-i]').forEach(b => b.addEventListener('click', () => { medir('radar_ponto'); abrir({x: g.x, y: g.y, itens: [g.itens[Number(b.dataset.i)]], de: g}, alvo); }));
      } else {
        const p = g.itens[0];
        const sit = p.quando.charAt(0).toUpperCase() + p.quando.slice(1);
        cartao.innerHTML = `${topo}${g.de ? '<button type="button" class="voltar">← Voltar ao grupo</button>' : ''}<h3 id="r3-cartao-t" tabindex="-1">${esc(p.nome)}</h3><p class="onde">${esc(p.cidade)}/${esc(p.uf)}</p>
          <p class="sit ${p.st}">${esc(sit)}</p>${p.det || ''}${p.req ? `<p class="req"><b>Quem pode:</b> ${esc(p.req)}</p>` : ''}
          <div class="bts"><a class="botao" href="${linkPonto(p)}">${p.slug ? 'Ver edital' : 'Ver faculdade'}</a><a class="botao sec" href="${RAIZ}faculdade/${esc(p.fid)}/#alerta">Me avise</a></div>`;
        const v = $('.voltar', cartao);
        if (v) v.addEventListener('click', () => abrir(g.de, alvo));
      }
      $('.fechar', cartao).addEventListener('click', fecharCartao);
      cartao.hidden = false;
      if (!celular()) posicionar(alvo);
      requestAnimationFrame(() => cartao.classList.add('aberto'));
      $('#r3-cartao-t').focus({preventScroll: true});
    }
    function posicionar(alvo) {
      // dentro da área do mapa e ao lado do ponto: nunca por cima dos estados, dos chips ou da legenda
      cartao.style.left = cartao.style.top = '0px';
      const cx = caixaMapa.getBoundingClientRect(), b = alvo.querySelector('.alvo').getBoundingClientRect();
      const w = cartao.offsetWidth, h = cartao.offsetHeight;
      const px = b.left - cx.left + b.width / 2, py = b.top - cx.top + b.height / 2;
      let x = px + 26 + w <= cx.width ? px + 26 : px - 26 - w;
      x = Math.max(0, Math.min(x, cx.width - w));
      const y = Math.max(0, Math.min(py - h / 2, cx.height - h));
      cartao.style.left = x + 'px'; cartao.style.top = y + 'px';
    }
    function fecharCartao() { const a = aberto; fechar(); if (a) a.focus({preventScroll: true}); }
    function fechar() {
      cartao.classList.remove('aberto'); cartao.hidden = true;
      if (aberto) aberto.setAttribute('aria-expanded', 'false');
      aberto = null;
    }
    document.addEventListener('keydown', ev => { if (ev.key === 'Escape' && aberto) fecharCartao(); });
    document.addEventListener('click', ev => { if (aberto && !ev.composedPath().some(n => n === cartao || (n.classList && n.classList.contains('pt')))) fechar(); });

    function escolher(k) {
      if (pessoal) { pessoal = null; vista = BRASIL; if (aoSair) aoSair(); }  // escolher um filtro do mapa completo sai do radar pessoal
      filtro = k;
      fig.querySelectorAll('.chip').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.filtro === k)));
      fechar(); desenhar();
    }
    fig.querySelectorAll('.chip').forEach(b => b.addEventListener('click', () => { medir('radar_chip_' + b.dataset.filtro); escolher(b.dataset.filtro); }));
    fig.querySelectorAll('[data-vista]').forEach(b => b.addEventListener('click', () => {
      if (b.dataset.uf) medir('radar_estado');
      vista = b.dataset.vista; fechar(); desenhar();
    }));
    let anim = 0;
    function deslizar(de, para) {  // a câmera vai da vista antiga para a nova em 550 ms (os pontos já estão no tamanho da vista nova)
      cancelAnimationFrame(anim);
      const a = de.split(' ').map(Number), b = para.split(' ').map(Number), t0 = performance.now();
      (function passo(t) {
        const f = Math.min(1, (t - t0) / 550), k = f < .5 ? 2 * f * f : 1 - Math.pow(-2 * f + 2, 2) / 2;
        svg.setAttribute('viewBox', a.map((v, i) => (v + (b[i] - v) * k).toFixed(2)).join(' '));
        if (f < 1) anim = requestAnimationFrame(passo); else svg.setAttribute('viewBox', para);
      })(t0);
    }
    let espera;
    addEventListener('resize', () => { clearTimeout(espera); espera = setTimeout(() => { if (!aberto) desenhar(); }, 150); });

    // textos ao vivo (o site pode ser aberto dias depois de gerado)
    const abertosEd = TM.editais.filter(e => estadoEdital(e) === 'aberto');
    const nFac = new Set(abertosEd.map(e => e.fid)).size, dias = pontos.filter(p => aberta(p) && p.dias !== null).map(p => p.dias);
    const vbr = $('[data-vivo-br]'), vex = $('[data-vivo-ex]'), nAb = $('#n-abertos');
    if (vbr) {
      if (abertosEd.length) {
        const d = dias.length ? Math.min(...dias) : null;
        vbr.textContent = `${abertosEd.length} ${abertosEd.length === 1 ? 'edital aberto' : 'editais abertos'} em ${plural(nFac, 'faculdade', 'faculdades')}`
          + (d === null ? '' : d <= 0 ? ' · o próximo encerra hoje' : ` · o próximo encerra em ${d} ${d === 1 ? 'dia' : 'dias'}`);
      } else { vbr.textContent = 'nenhum edital aberto hoje'; $('[data-frase-br]').textContent = 'Veja quando abre o próximo edital pra você.'; }
    }
    if (vex) { const n = abertosEd.filter(e => e.ext === true).length; vex.textContent = `${n} ${n === 1 ? 'edital aberto aceita' : 'editais abertos aceitam'} quem vem do exterior`; }
    if (nAb) nAb.textContent = abertosEd.length;
    const vivo = $('#r3-vivo');
    if (vivo && TM.gerado_em) {
      const atraso = diasEntre(TM.gerado_em, hoje()), hora = TM.gerado_hora ? ` às ${TM.gerado_hora}` : '';
      if (atraso > 1) vivo.innerHTML = `<span>atualizado em ${esc(fmt(TM.gerado_em))}${esc(hora)}</span>`;
      else vivo.lastElementChild.textContent = `atualizado ${atraso === 1 ? 'ontem' : 'hoje'}${hora}`;
    }

    desenhar();
    let restaurado = false;
    try {
      restaurado = radarPessoal({
        fig, pontos, gPts, feixe, escala, centroOriginal: CENTRO0,
        moverCentro: (x, y) => { CX = x; CY = y; },
        aoDesenhar: f => { depois = f; },
        aoSair: f => { aoSair = f; },
        definirPessoal(obj, alvo, animar) {  // obj null = volta ao mapa de todas; alvo = viewBox de chegada (animado, 0,55 s)
          pessoal = obj; fechar();
          const de = svg.getAttribute('viewBox');
          if (alvo) vista = alvo;
          desenhar();
          if (animar && alvo && de !== vista && !semMovimento()) deslizar(de, vista);
        }
      });
    } catch (erro) { console.error('radar pessoal', erro); }
    if (!restaurado) abertura();

    // abertura (uma vez por sessão, menos de 2 s): varredura, pontos acendem na ordem do feixe, contagem
    function abertura(forcar) {
      if (window.TM_ABERTURA_MANUAL && !forcar) { window.TM_abertura = () => abertura(true); return; }  // gravação do GIF
      let vista1 = false;
      try { vista1 = sessionStorage.getItem('tm_abertura') === '1'; sessionStorage.setItem('tm_abertura', '1'); } catch (e) { /* sem armazenamento */ }
      if (semMovimento() || (vista1 && !forcar) || !feixe.animate) { feixe.classList.add('girando'); return; }
      const DUR = 1500;
      const txt = $('.r3-varrendo', fig);
      const ordem = pontos.map(p => ({p, t: angulo(p.x, p.y) / 360 * DUR})).sort((a, b) => a.t - b.t);
      const total = pontos.length;
      txt.hidden = false;
      const giro = feixe.animate([{transform: 'rotate(-90deg)'}, {transform: 'rotate(270deg)'}], {duration: DUR, easing: 'linear'});
      giro.finished.then(() => feixe.classList.add('girando'), () => feixe.classList.add('girando'));
      gPts.querySelectorAll('.pt').forEach(a => a.animate(
        [{opacity: 0, transform: 'scale(.3)'}, {opacity: 1, transform: 'scale(1.35)', offset: .6}, {opacity: 1, transform: 'scale(1)'}],
        {duration: 420, delay: Number(a.dataset.ang) / 360 * DUR, easing: 'ease-out', fill: 'backwards'}));
      // o texto segue o relógio do próprio feixe: conta o que ele já varreu
      let fim = null;
      (function passo(t) {
        const dt = giro.playState === 'finished' ? DUR + (t - (fim ??= t)) : Number(giro.currentTime) || 0;
        let fac = 0, ed = 0;
        for (const o of ordem) { if (o.t > dt) break; fac++; ed += o.p.n; }
        txt.textContent = dt < DUR ? `${fac} faculdades varridas · ${ed} editais abertos` : `${total} faculdades varridas · ${abertosEd.length} editais abertos`;
        if (dt < DUR + 900) requestAnimationFrame(passo);
        else txt.animate([{opacity: 1}, {opacity: 0}], {duration: 250}).finished.then(() => { txt.hidden = true; });
      })(performance.now());
    }
    window.TM_radar = {abrir: (sigla, uf) => {  // usado pelos testes de navegador
      if (uf) { vista = $(`[data-uf="${uf}"]`, fig).dataset.vista; desenhar(); }
      const p = pontos.find(p => p.sigla === sigla && (!uf || p.uf === uf));
      const a = [...gPts.querySelectorAll('.pt')].find(a => a._g && a._g.itens.some(i => i.fid === p.fid));  // por fid: no radar pessoal os pontos são cópias
      if (a) abrir(a._g.itens.length > 1 ? {x: p.x, y: p.y, itens: [a._g.itens.find(i => i.fid === p.fid)], de: a._g} : a._g, a);
      return Boolean(a);
    }, pontos};
  }
  const r3 = $('#radar3');
  if (r3) radarHome(r3);

  // números da base contam de 0 até o valor real quando entram na tela (uma vez; sem animação se pedido)
  const numeros = document.querySelector('.numeros');
  if (numeros && 'IntersectionObserver' in window && !semMovimento()) {
    const obs = new IntersectionObserver(ents => {
      if (!ents.some(x => x.isIntersecting)) return;
      obs.disconnect();
      numeros.querySelectorAll('[data-conta]').forEach(b => {
        const alvo = Number(b.textContent), t0 = performance.now();
        if (!alvo) return;
        (function passo(t) {
          const f = Math.min((t - t0) / 900, 1);
          b.textContent = Math.round(alvo * (1 - Math.pow(1 - f, 3)));
          if (f < 1) requestAnimationFrame(passo);
        })(t0);
      });
    });
    obs.observe(numeros);
  }

  // prazos mais próximos: passam devagar; pausa ao tocar, ao passar o mouse, no foco e no botão
  const car = $('#prazos');
  if (car) {
    const pontos = (window.TM_radar && window.TM_radar.pontos) || radarPontos();
    const prox = pontos.filter(p => aberta(p) && p.dias !== null).sort((a, b) => a.dias - b.dias || a.sigla.localeCompare(b.sigla)).slice(0, 3);
    const faixa = $('.faixa', car);
    if (!prox.length) car.hidden = true;
    else faixa.innerHTML = prox.map((p, i) => `<li class="item${i ? '' : ' ativo'}"><b>${esc(p.sigla)}</b> ${esc(p.cidade)}/${esc(p.uf)} · ${esc(p.quando)} · <a href="${linkPonto(p)}">Ver edital</a></li>`).join('');
    if (prox.length > 1 && !semMovimento()) {
      const bt = $('.car-pausa', car);
      let i = 0, parado = false, fixo = false;
      bt.hidden = false;
      const pintar = () => { bt.setAttribute('aria-label', fixo ? 'Continuar' : 'Pausar'); bt.innerHTML = fixo
        ? '<svg aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M7 4l13 8-13 8z"/></svg>'
        : '<svg aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M6 4h4v16H6zM14 4h4v16h-4z"/></svg>'; };
      bt.addEventListener('click', () => { fixo = !fixo; pintar(); });
      ['pointerenter', 'focusin', 'touchstart'].forEach(t => faixa.addEventListener(t, () => { parado = true; }, {passive: true}));
      ['pointerleave', 'focusout'].forEach(t => faixa.addEventListener(t, () => { parado = false; }));
      setInterval(() => {
        if (parado || fixo || document.hidden) return;
        i = (i + 1) % prox.length;
        faixa.querySelectorAll('.item').forEach((n, k) => n.classList.toggle('ativo', k === i));
      }, 4500);
    } else car.classList.add('parado');
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

  // "Avise um colega" (indicação): desligado por padrão; liga com a variável INDICACAO=1 (window.TM_CONFIG.indicacao). Sem recompensa,
  // sem identificar quem indicou: o link leva ?origem=indicacao, que o relatório conta como canal de indicação.
  function blocoIndicar() {
    if (!(window.TM_CONFIG || {}).indicacao) return '';
    const link = 'https://www.transfermed.com.br/?origem=indicacao';
    const texto = 'Estou usando o Transfermed para ver onde posso transferir Medicina: editais abertos, prazos e documentos conferidos no PDF oficial. É grátis.';
    return `<div class="indicar" id="indicar-colega"><p><strong>Conhece alguém que quer transferir?</strong> Avise um colega: leva um minuto.</p>
      <p class="acoes"><a class="botao sec" href="https://wa.me/?text=${encodeURIComponent(texto + ' ' + link)}" target="_blank" rel="noopener" data-medir="indicar_colega">Avisar um colega no WhatsApp<span class="oculto"> (abre em nova aba)</span></a>
      <button type="button" class="botao sec" data-copiar-indicacao="${esc(link)}">Copiar o link</button></p></div>`;
  }
  document.addEventListener('click', async ev => {
    const b = ev.target.closest('[data-copiar-indicacao]');
    if (!b) return;
    medir('indicar_colega');
    try { await navigator.clipboard.writeText(b.dataset.copiarIndicacao); b.textContent = 'Link copiado ✓'; } catch (_) { b.textContent = b.dataset.copiarIndicacao; }
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
      if (foco && document.activeElement && form.contains(document.activeElement)) { foco.setAttribute('tabindex', '-1'); foco.focus({preventScroll: true}); }
      // etapa nova começa do topo do cartão (com a barra "Etapa X de 4"), nunca no meio dele ou no rodapé
      if (form.getBoundingClientRect().top < 0) form.scrollIntoView({block: 'start'});
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
      resultado(p, () => mostrar(0));
      medir('diagnostico_concluido');
    });
    mostrar(porta === 'brasil' || porta === 'exterior' ? 1 : 0);
    medir('diagnostico_iniciado');
    if (salvo && location.hash === '#resultado') resultado(salvo, () => mostrar(0));
  }

  // com o resultado na tela, o formulário recolhe numa linha com o perfil (antes ficava a etapa 4 aberta em cima)
  function textoPerfil(p) {
    const partes = [p.origem === 'exterior' ? 'Estudo no exterior' : 'Estudo no Brasil'];
    if (p.semestre) partes.push(`${p.semestre}º semestre`);
    if (p.cidade && p.raio) partes.push(`até ${Number(p.raio).toLocaleString('pt-BR')} km de ${p.cidade}`);
    else if (p.cidade) partes.push(`perto de ${p.cidade}`);
    partes.push({publica: 'só públicas', particular: 'só particulares'}[p.tipo] || 'públicas e particulares');
    if (p.taxaMax != null) partes.push(`taxa até R$ ${p.taxaMax.toLocaleString('pt-BR')}`);
    return partes.join(' · ');
  }

  function resultado(p, refazer) {
    const caixa = $('#resultado');
    const form = $('#diag'), lead = document.querySelector('.heroi .lead');
    const todos = ordenar(TM.editais.map(e => ({e, r: avaliar(e, p)})));
    const aptos = todos.filter(x => !x.r.motivos.length);
    // edital "até completar as vagas" (fluxo === 'vagas') é edital aberto; o pedido sem edital fica à parte
    const abertos = aptos.filter(x => situacao(x.e) === 'aberto' || x.e.fluxo === 'vagas');
    const continuos = aptos.filter(x => situacao(x.e) === 'contínuo' && x.e.fluxo !== 'vagas');
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
    let html = `<div class="perfil-resumo"><p><strong>Seu perfil:</strong> ${esc(textoPerfil(p))}</p>
      <button type="button" class="link-botao" id="res-mudar">Mudar respostas</button></div>
    <p class="frase-resultado">${abertos.length
      ? `Você atende a <strong>${abertos.length} ${abertos.length === 1 ? 'edital aberto' : 'editais abertos'}</strong> agora.${diasPrazo != null ? ` O prazo mais próximo encerra ${diasPrazo <= 0 ? '<strong>hoje</strong>' : `em <strong>${diasPrazo} ${diasPrazo === 1 ? 'dia' : 'dias'}</strong>`} (${sigla(comPrazo[0])}).` : ''}`
      : `Nenhum edital aberto agora para o seu perfil.${breveEdital.length + historico.length ? ` ${breveEdital.length + historico.length === 1 ? 'Uma faculdade deve' : `${breveEdital.length + historico.length} faculdades devem`} abrir nos próximos meses: veja abaixo e receba o aviso quando abrir.` : ' Receba o aviso quando abrir.'}`}</p>
    <div class="acoes acoes-resultado">
      ${$('#form-alerta') ? '<a class="botao atalho-alerta" href="#alerta">Receber aviso de novos editais para o meu perfil</a>' : ''}
      ${abertos.length + breveEdital.length ? `<button type="button" class="botao sec" id="res-salvar">Salvar todos na lista</button>` : ''}
    </div>
    ${painelAssinar(abertos.concat(breveEdital).map(x => x.e), 'res-agenda')}
    ${typeof blocoIndicar === 'function' ? blocoIndicar() : ''}
    <div class="painel-resultado">
      <div class="painel-numeros">
        ${maisPerto ? `<div class="numero"><b>${maisPerto.r.dist < 5 ? 'Na cidade' : maisPerto.r.dist.toLocaleString('pt-BR') + ' km'}</b><span>o mais perto: ${sigla(maisPerto)}</span></div>` : ''}
        ${diasPrazo != null ? `<div class="numero ${diasPrazo <= 2 ? 'n-alerta' : diasPrazo <= 10 ? 'n-aviso' : ''}"><b>${diasPrazo <= 0 ? 'hoje' : diasPrazo + (diasPrazo === 1 ? ' dia' : ' dias')}</b><span>prazo mais curto: ${sigla(comPrazo[0])}</span></div>` : ''}
        <div class="numero"><b>${breveEdital.length + historico.length}</b><span>devem abrir nos próximos meses</span></div>
      </div>
      ${miniMapa(abertos.concat(breveEdital), p.coords)}
    </div>
    `;

    const perto = p.coords ? ', do mais perto para o mais longe' : '';
    html += `<h2 id="res-titulo">Abertos agora para você</h2>
      <p class="sub">${abertos.length} ${abertos.length === 1 ? 'edital' : 'editais'}${perto}.</p>`;
    const LIMITE = 5;  // os mais perto (ou mais urgentes) primeiro; o resto abre no botão, sem recarregar
    html += abertos.length ? abertos.slice(0, LIMITE).map(x => cartao(x.e, x.r)).join('')
      + (abertos.length > LIMITE ? `<div id="res-resto" hidden>${abertos.slice(LIMITE).map(x => cartao(x.e, x.r)).join('')}</div>
        <p class="acoes"><button type="button" class="botao sec" id="res-ver-todos" aria-controls="res-resto" aria-expanded="false">Ver todos os ${abertos.length}</button></p>` : '')
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
    const breve = breveEdital.map(x => cartao(x.e, x.r)).concat(historico.map(({f, dist}) => {
      const meses = (f.meses || []).filter(m => proximos.includes(m)).map(m => MESES[m - 1]);
      return `<article class="cartao"><h3><a href="${RAIZ}faculdade/${esc(f.id)}/">${esc(f.nome)}</a></h3>
        <div class="local">${esc(f.cidade)}/${esc(f.uf)} · ${esc(f.tipo)}${dist != null ? ` · <strong>${textoKm(dist)}</strong>` : ''}</div>
        <div class="etiquetas"><span class="et aviso">Costuma abrir em ${meses.join(' ou ')}</span></div>
        <p class="dica">Ainda não há edital publicado. A previsão vem dos editais anteriores desta faculdade.</p></article>`;
    }));
    // como nos abertos: 5 primeiro e o resto no botão (no celular a lista passava de 30 cartões)
    html += breve.slice(0, LIMITE).join('') + (breve.length > LIMITE ? `<div id="res-resto-breve" hidden>${breve.slice(LIMITE).join('')}</div>
      <p class="acoes"><button type="button" class="botao sec" data-ver-todos="res-resto-breve" aria-controls="res-resto-breve" aria-expanded="false">Ver todos os ${breve.length} que abrem em breve</button></p>` : '');

    if (encerrados.length) html += `<details><summary>Encerrados (${encerrados.length}): o último de cada faculdade, para se preparar para o próximo</summary>${encerrados.map(x => cartao(x.e, x.r)).join('')}</details>`;
    if (fora.length) html += `<details><summary>Onde você não se encaixa agora, e por quê (${fora.length})</summary>${fora.map(x => cartao(x.e, x.r)).join('')}</details>`;
    html += `<p class="dica espaco-24">Seu perfil ficou salvo só neste navegador. Na próxima visita, a página inicial mostra o que mudou.
      "Atende aos requisitos" quer dizer que o edital não exclui o seu perfil. Quem decide a vaga e o aproveitamento é a faculdade.</p>`;
    caixa.innerHTML = html;
    caixa.hidden = false;
    const alerta = $('#alerta');
    if (alerta) alerta.hidden = false;
    const proEspera = $('#pro-espera');  // teste R1 (lista de espera do plano futuro): só mede o interesse, sem coletar nada
    if (proEspera) {
      proEspera.hidden = false;
      const botaoPro = $('#pro-interesse');
      if (botaoPro && !botaoPro.dataset.pronto) {
        botaoPro.dataset.pronto = '1';
        botaoPro.addEventListener('click', () => {
          medir('pro_interesse');
          proEspera.innerHTML = '<p>Anotado, obrigado. Isso nos ajuda a decidir o que construir. Nada foi cobrado nem pedido.</p>';
        });
      }
    }
    if (form) form.hidden = true;
    if (lead) lead.hidden = true;
    $('#res-mudar').addEventListener('click', () => {
      caixa.hidden = true;
      if (alerta) alerta.hidden = true;
      if (proEspera) proEspera.hidden = true;
      if (lead) lead.hidden = false;
      form.hidden = false;
      if (refazer) refazer();
      form.scrollIntoView({block: 'start'});
      const foco = form.querySelector('.etapa.ativa legend, .etapa.ativa .rotulo');
      if (foco) { foco.setAttribute('tabindex', '-1'); foco.focus({preventScroll: true}); }
    });
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
    const verTodos = $('#res-ver-todos');
    if (verTodos) verTodos.dataset.verTodos = 'res-resto';
    caixa.querySelectorAll('[data-ver-todos]').forEach(b => b.addEventListener('click', () => {
      const resto = document.getElementById(b.dataset.verTodos);
      resto.hidden = false;
      b.parentElement.remove();
      const primeiro = resto.querySelector('h3 a');
      if (primeiro) primeiro.focus();
    }));
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
    document.querySelectorAll('.contador').forEach(cont => {
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
    });
    // bloco "Não perca o prazo": a barra e o "Hoje" também seguem o dia da visita
    const faixa = $('.prazo-barra');
    if (faixa) {
      const ini = faixa.dataset.inicio, fim = faixa.dataset.fim, total = diasEntre(ini, fim);
      faixa.value = total > 0 ? Math.min(100, Math.max(0, diasEntre(ini, h) / total * 100)) : 0;
      const rot = $('.rot-hoje'); if (rot) rot.textContent = `Hoje · ${fmt(h).slice(0, 5)}`;
    }
    // "Adicionar à minha agenda": no Android o link do Google Agenda abre o app; nos demais, baixa o .ics de evento único
    const agendar = $('a[data-agenda-google]');
    if (agendar && /Android/i.test(navigator.userAgent)) {
      agendar.href = agendar.dataset.agendaGoogle; agendar.target = '_blank'; agendar.rel = 'noopener'; agendar.removeAttribute('download');
    }
    // barra fixa do prazo (celular): aparece depois do primeiro scroll e some quando o bloco do lembrete está na tela
    const barraPrazo = $('#barra-prazo'), blocoLembrete = $('#lembrete');
    if (barraPrazo && blocoLembrete && barraPrazo.dataset.fim >= h) {
      const d = diasEntre(h, barraPrazo.dataset.fim);
      barraPrazo.querySelector('.bp-quando').textContent = d === 0 ? 'fecha hoje' : `fecha em ${d} ${d === 1 ? 'dia' : 'dias'}`;
      const estreito = matchMedia('(max-width: 768px)');
      let rolou = false, noBloco = false;
      const atualizarBarra = () => { barraPrazo.hidden = !(estreito.matches && rolou && !noBloco); };
      if ('IntersectionObserver' in window) new IntersectionObserver(es => { noBloco = es[0].isIntersecting; atualizarBarra(); }).observe(blocoLembrete);
      addEventListener('scroll', () => { if (!rolou && scrollY > 40) { rolou = true; atualizarBarra(); } }, {passive: true});
      estreito.addEventListener('change', atualizarBarra);
      barraPrazo.querySelector('a').addEventListener('click', ev => {
        ev.preventDefault();
        blocoLembrete.scrollIntoView({block: 'start', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'});
        const campo = $('#email-alerta'); if (campo) campo.focus({preventScroll: true});
      });
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
    const vivos = ordenar(TM.editais.filter(e => ['aberto', 'em breve'].includes(situacao(e)) || e.fluxo === 'vagas').map(e => ({e, r: null})));
    const n = $('#n-abertos');
    if (n) n.textContent = TM.editais.filter(e => situacao(e) === 'aberto' || e.fluxo === 'vagas').length;
    const limite = Number(caixa.dataset.limite) || vivos.length;  // home: só os mais urgentes; /editais/: todos
    caixa.innerHTML = vivos.length ? vivos.slice(0, limite).map(x => cartao(x.e, x.r)).join('') : '<div class="vazio">Nenhum edital aberto hoje.</div>';
  }

  // ---------------------------------------------------------------- alertas por e-mail (Supabase, só funções públicas)
  const CFG = window.TM_CONFIG || {};
  const alertasAtivos = () => Boolean(CFG.supabaseUrl && CFG.supabaseAnon);
  async function rpc(nome, args) {
    // chave antiga (JWT, "anon") vai também no Authorization; a nova (sb_publishable_...) vai só no apikey
    const cabecalhos = {apikey: CFG.supabaseAnon, 'Content-Type': 'application/json'};
    if (CFG.supabaseAnon.startsWith('eyJ')) cabecalhos.Authorization = `Bearer ${CFG.supabaseAnon}`;
    if (nome === 'inscrever' && args && args.p_perfil) {
      const extra = {canal: canalDoInscrito()};
      const ref = refDoInscrito();
      if (ref) extra.ref = ref;
      if (args.porta) { extra.porta = args.porta; args = {p_email: args.p_email, p_perfil: args.p_perfil, p_consentimento: args.p_consentimento}; }
      args = {...args, p_perfil: {...args.p_perfil, ...extra}};
    }
    const r = await fetch(`${CFG.supabaseUrl}/rest/v1/rpc/${nome}`, {method: 'POST', headers: cabecalhos, body: JSON.stringify(args)});
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  }

  // por qual porta a pessoa entrou: o diagnóstico ou "seguir" um edital/faculdade (o resto: início, lista de editais, exterior)
  const portaDoPedido = ctx => ctx === 'diagnostico' ? 'diagnostico' : /^(edital|faculdade)_/.test(ctx || '') ? 'seguir' : 'outra';

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
      const estados = [...form.querySelectorAll('input[name="estado"]:checked')].map(i => i.value);  // chips da home (sem chip: todos os estados)
      const perfil = {...(d.comPerfil ? perfilDoDiagnostico(p) : base), ...(estados.length ? {estados} : {}), seguir: seguir()};
      const botao = form.querySelector('button');
      botao.disabled = true; msg.textContent = 'Enviando…';
      try {
        const r = await rpc('inscrever', {p_email: email, p_perfil: perfil, p_consentimento: CFG.consentimento, porta: portaDoPedido(d.contexto)});
        if (r === 'pendente' || r === 'atualizado') {
          armazem.gravar('tm_alerta', {email, em: hoje(), seguir: perfil.seguir});
          medir('alerta_inscrito');
          medir('alerta_inscrito_' + (d.contexto || 'outro'));
          if ($('#lembrete')) medir('lembrete_email');  // bloco "Não perca o prazo" da ficha
          msg.textContent = '';
          passo2(email, perfil, r);
        } else {
          msg.textContent = RESPOSTAS[r] || 'Não deu certo agora. Tente de novo em alguns minutos.';
        }
      } catch (e) {  // a mensagem do navegador ("Failed to fetch") não diz nada a quem está do outro lado
        msg.textContent = 'Não deu certo agora (sem conexão?). Confira a internet e tente de novo em alguns minutos.';
      }
      botao.disabled = false;
    });
  }

  function passo2(email, enviado, r) {
    const caixa = $('#alerta-passo2'), form = $('#form-alerta');
    const quando = CFG.envioImediato ? 'Em 1 ou 2 minutos' : 'Em até 1 hora';
    const confirmar = r === 'pendente'
      ? `<strong>Falta 1 clique.</strong> Confira seu e-mail (e o spam) e clique em confirmar. ${quando} chega uma mensagem de alertas@transfermed.com.br com o assunto "Confirme seu alerta do Transfermed: falta 1 clique". Sem o clique, nenhum alerta é enviado.`
      : `Seu alerta já estava ativo: atualizamos as suas preferências. ${quando} chega um e-mail para ${esc(email)} confirmando a mudança.`;
    const naoChegou = `<p class="nao-chegou">Não chegou em ${CFG.envioImediato ? '2 minutos' : '1 hora'}? Procure em <strong>Spam</strong> e em <strong>Promoções</strong> (Gmail) e marque como "não é spam".
      ${r === 'pendente' ? '<br><button type="button" class="botao sec" id="reenviar">Não chegou? Reenviar</button> <span id="reenviar-msg" role="status"></span>' : ''}</p>`;
    const isca = $('#alerta a[data-medir="isca"]');
    const linkIsca = isca ? `<p><a class="botao sec" href="${esc(isca.getAttribute('href'))}" download data-medir="isca">Baixar o checklist de documentos (PDF)</a></p>` : '';
    const p = armazem.ler('tm_perfil', null);
    const v = {...(p ? perfilDoDiagnostico(p) : {}), ...enviado};
    form.hidden = true;
    const garantia = $('#alerta .garantia');
    if (garantia) garantia.hidden = true;
    // Reenviar: a mesma regra do inscrever no banco (pendente que pede de novo recebe a confirmação de novo, no máximo a cada 10 minutos);
    // o navegador também guarda a hora do último pedido para não chamar à toa e dizer quanto falta.
    const ligarReenvio = () => {
      const botao = $('#reenviar'), msg = $('#reenviar-msg');
      if (!botao) return;
      botao.addEventListener('click', async () => {
        const ultimo = Number((armazem.ler('tm_reenvio', {}) || {})[email]) || 0;
        const falta = Math.ceil((ultimo + 600000 - Date.now()) / 60000);
        if (falta > 0) { msg.textContent = `Já reenviamos há pouco. Espere ${falta} min e procure em Spam e Promoções antes de pedir de novo.`; return; }
        botao.disabled = true; msg.textContent = 'Reenviando…';
        try {
          const res = await rpc('inscrever', {p_email: email, p_perfil: enviado, p_consentimento: CFG.consentimento});
          armazem.gravar('tm_reenvio', {...(armazem.ler('tm_reenvio', {}) || {}), [email]: Date.now()});
          msg.textContent = res === 'pendente' ? 'Pedido feito. Em 1 ou 2 minutos chega outro e-mail; procure também em Spam e Promoções.' : 'Seu alerta já está ativo. Nada a reenviar.';
        } catch (e) { msg.textContent = 'Não deu certo agora. Tente de novo em alguns minutos.'; }
        botao.disabled = false;
      });
    };
    setTimeout(ligarReenvio, 0);  // depois de a caixa ser montada abaixo
    if (enviado.curso && enviado.semestre) {  // o perfil completo já foi no passo 1 (diagnóstico)
      caixa.innerHTML = `<p class="ok-caixa" tabindex="-1">${r === 'pendente' ? '' : '<strong>Pronto.</strong> '}${confirmar}</p>${naoChegou}${linkIsca}`;
    } else {
      const semestres = Array.from({length: 12}, (_, i) => `<option value="${i + 1}">${i + 1}º semestre</option>`).join('');
      caixa.innerHTML = `<p class="ok-caixa" tabindex="-1"><strong>Passo 1 de 2 feito.</strong> ${confirmar}</p>${naoChegou}${linkIsca}
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
          tipo: f.tipo.value, taxaMax: v.taxaMax ?? null, ...(enviado.estados ? {estados: enviado.estados} : {}), seguir: enviado.seguir};
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
    if (!alvo || alvo.hidden || $('#lembrete') || !alertasAtivos() || !['edital', 'faculdade', 'exterior'].includes(document.body.dataset.pagina)) return;  // na ficha com o bloco do lembrete, a barra fixa é a do bloco (B3)
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
    const alvo = $('.v3-acao .quadros');
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
  // fica no cabeçalho, antes da lupa: não cobre conteúdo. Se o texto empurrar o menu para outra linha, vira só ícone
  // (o nome acessível continua "Nova versão disponível, atualizar")
  function avisoNovaVersao() {
    const nav = $('.topo .nav');
    if (!nav || $('.nova-versao')) return;
    const topo = $('.topo > .wrap'), altura = topo.offsetHeight;
    const aviso = document.createElement('button');
    aviso.type = 'button';
    aviso.className = 'nova-versao';
    aviso.setAttribute('aria-label', 'Nova versão disponível, atualizar');
    aviso.innerHTML = '<svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 12a8 8 0 1 1-2.3-5.7"/><path d="M20 4v5h-5"/></svg><span class="nv-txt">Nova versão · atualizar</span>';
    aviso.addEventListener('click', () => location.reload());
    nav.insertBefore(aviso, $('.busca-botao', nav) || nav.firstChild);
    const marca = $('.topo .marca'), toca = () => { const a = aviso.getBoundingClientRect(), m = marca ? marca.getBoundingClientRect() : {right: 0};
      return a.left < m.right + 2; };
    if (topo.offsetHeight > altura + 1 || toca()) aviso.classList.add('so-icone');
  }
  window.TM_avisoNovaVersao = avisoNovaVersao;  // os testes de navegador mostram o aviso sem esperar uma versão nova
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

  // ---------------------------------------------------------------- Meu plano (Parte D): tudo calculado aqui, com os editais salvos neste aparelho
  const MES3 = ['JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN', 'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ'];
  const ETAPAS_PLANO = [['fim', 'último dia de inscrição'], ['prova', 'prova'], ['res', 'resultado']];
  const quando = d => d === 0 ? 'hoje' : d === 1 ? 'amanhã' : `faltam ${d} dias`;
  const listaE = nomes => nomes.length < 2 ? nomes.join('') : nomes.slice(0, -1).join(', ') + ' e ' + nomes[nomes.length - 1];
  const NUM_EXT = {2: ['Duas', 'dois', 'duas'], 3: ['Três', 'três', 'três'], 4: ['Quatro', 'quatro', 'quatro']};
  const salvosDoAparelho = () => armazem.ler('tm_marcados', []).map(id => TM.editais.find(e => e.id === id)).filter(Boolean);

  // linha do tempo: só datas conferidas e que ainda não passaram
  function eventosDoPlano(salvos, h) {
    const ev = [];
    for (const e of salvos) for (const [campo, rotulo] of ETAPAS_PLANO) {
      const d = e[campo];
      if (!d || d < h || !conferido(e, campo)) continue;
      ev.push({data: d, campo, rotulo, e, pg: (e.pg || {})[campo] || ''});
    }
    return ev.sort((a, b) => a.data.localeCompare(b.data) || ETAPAS_PLANO.findIndex(x => x[0] === a.campo) - ETAPAS_PLANO.findIndex(x => x[0] === b.campo)
      || nomeEdital(a.e).localeCompare(nomeEdital(b.e), 'pt-BR'));
  }
  // provas no mesmo dia em faculdades ou campi diferentes (ids de faculdade diferentes); data em "conferir" não conta
  function detectarChoques(salvos, h) {
    const por = {};
    for (const e of salvos) if (e.prova && e.prova >= h && conferido(e, 'prova')) (por[e.prova] = por[e.prova] || []).push(e);
    return Object.keys(por).sort().map(data => {
      const vistos = new Set(), es = por[data].filter(e => !vistos.has(e.fid) && vistos.add(e.fid));
      return {data, es};
    }).filter(c => c.es.length >= 2);
  }
  function textoChoque(c) {
    const n = c.es.length, [Cap, minus, fem] = NUM_EXT[n] || [`${n}`, `${n}`, `${n}`];
    return `<strong>${Cap} provas no mesmo dia:</strong> ${esc(listaE(c.es.map(nomeEdital)))} marcam prova em ${fmt(c.data).slice(0, 5)}. `
      + `Leia os ${minus} editais e decida antes de pagar as ${fem} taxas.`;
  }
  // documentos de todos: só agrupa item com o mesmo nome (sem acento, caixa e pontuação); na dúvida, ficam separados
  const chaveDoc = s => norm(s).replace(/[^a-z0-9]+/g, ' ').trim();
  function agruparDocumentos(salvos) {
    const grupos = new Map();
    for (const e of salvos) (e.docs || []).forEach((d, i) => {
      const k = chaveDoc(d);
      if (!k) return;
      if (!grupos.has(k)) grupos.set(k, {chave: k, rotulo: d, itens: []});
      grupos.get(k).itens.push({id: e.id, i});
    });
    return [...grupos.values()].map(g => ({...g, pedem: new Set(g.itens.map(x => x.id)).size}))
      .sort((a, b) => b.pedem - a.pedem);  // sort estável: empate fica na ordem em que apareceu
  }
  const feitoDoc = (g, marcados) => g.itens.every(x => (marcados[x.id] || []).includes(x.i));
  function marcarDoc(g, feito) {
    const por = {};
    g.itens.forEach(x => { (por[x.id] = por[x.id] || []).push(x.i); });
    for (const id of Object.keys(por)) {
      const s = new Set(armazem.ler('tm_check_' + id, []));
      por[id].forEach(i => feito ? s.add(i) : s.delete(i));
      armazem.gravar('tm_check_' + id, [...s].sort((a, b) => a - b));
    }
  }
  const lerMarcados = salvos => Object.fromEntries(salvos.map(e => [e.id, armazem.ler('tm_check_' + e.id, [])]));
  window.TM_PLANO = {eventosDoPlano, detectarChoques, textoChoque, agruparDocumentos, conferido, ics, nomeEdital};

  // comparar: até 3 editais salvos; "conferir" fica "conferir", sem cor de melhor ou pior e sem ordenar por valor (colunas na ordem em que foram salvos)
  const MAX_COMPARAR = 3;
  function celulaComparar(e, campo, texto) {
    if (texto == null) return '<span class="cp-conf">conferir</span>';
    const m = /^p\. (\d+)/.exec((e.pg || {})[campo] || '');
    const pdf = m && /\.pdf($|[?#])/i.test(e.url || '');
    return (pdf ? `<a href="${esc(e.url)}#page=${m[1]}" target="_blank" rel="noopener" data-medir="abrir_pdf">${texto}<span class="oculto"> (abre o PDF na página ${m[1]}, em nova aba)</span></a>` : texto)
      + (m ? `<small class="cp-pg">p. ${m[1]}</small>` : '');
  }
  function linhasComparar(e) {
    const ok = c => conferido(e, c);
    const vagas = !ok('vagas') || !Array.isArray(e.vagas) || !e.vagas.length ? null
      : e.vagas.filter(v => v.vagas).map(v => `${esc(v.semestre)}: ${v.vagas}`).join(' · ') || 'só cadastro reserva';
    return {
      fim: e.fluxo ? 'sem prazo fixo' : e.fim && ok('fim') ? esc(fmt(e.fim)) + (e.ps ? ' <small class="cp-pg">prazo seguro</small>' : '') : null,
      taxa: e.taxa != null && ok('taxa') ? (e.taxa === 0 ? 'grátis' : esc(dinheiro(e.taxa).replace(',00', ''))) : null,
      prova: e.prova && ok('prova') ? esc(fmt(e.prova)) : null,
      vagas,
      ext: e.ext != null && ok('ext') ? (e.ext ? 'sim' : 'não') : null,
      crit: e.crit && ok('crit') ? esc(e.crit) : null
    };
  }
  function htmlComparar(es) {
    const ROT = [['fim', 'Fecha'], ['taxa', 'Taxa'], ['prova', 'Prova'], ['vagas', 'Vagas'], ['ext', 'Exterior'], ['crit', 'Seleção']];
    const cols = es.map(e => ({e, v: linhasComparar(e)}));
    return `<div class="cp-rola" role="region" aria-label="Comparação dos editais escolhidos" tabindex="0"><table class="cp-tabela"><thead><tr><td></td>`
      + cols.map(c => `<th scope="col"><a href="${RAIZ}edital/${esc(c.e.slug)}/">${esc(nomeEdital(c.e))}</a></th>`).join('') + '</tr></thead><tbody>'
      + ROT.map(([k, r]) => `<tr><th scope="row">${r}</th>${cols.map(c => `<td>${celulaComparar(c.e, k, c.v[k])}</td>`).join('')}</tr>`).join('')
      + '</tbody></table></div><p class="cp-nota">Cada célula abre a página do PDF de onde saiu (quando o edital é um PDF). “conferir”: o edital não traz o dado ou ele está com aviso.</p>';
  }

  // "O que mudou": cartão de retificação (mesmo texto da ficha), só com antes e depois guardados
  function htmlRetificacao(e) {
    const r = e.ret;
    if (!r) return '';
    const f = TM.faculdades[e.fid] || {};
    const corpo = (r.m || []).length
      ? `<dl class="ret-lista">${r.m.map(([rot, antes, depois, pg]) => `<div class="ret-linha"><dt>${esc(rot)}</dt><dd><s>${esc(antes)}</s> <span aria-hidden="true">→</span><span class="oculto"> agora </span> <b>${esc(depois)}</b>${pg ? ` <span class="pag">${esc(pg)}</span>` : ''}</dd></div>`).join('')}</dl>`
      : `<p class="ret-fonte">O que mudou não está guardado com antes e depois. <a href="${esc(r.link)}" target="_blank" rel="noopener">Leia a versão nova<span class="oculto"> (abre em nova aba)</span></a>.</p>`;
    return `<section class="cartao-ret"><span class="ret-selo">Retificado em ${fmt(r.em).slice(0, 5)}</span><h3>O que mudou no edital da ${esc(f.sigla)}</h3>${corpo}</section>`;
  }

  // convite para instalar (só no Meu plano e depois de salvar 1 edital); fechado, não volta por 30 dias
  let promptInstalar = null;
  addEventListener('beforeinstallprompt', ev => { ev.preventDefault(); promptInstalar = ev; if (document.body.dataset.pagina === 'minha-lista') convidarInstalar(); });
  addEventListener('appinstalled', () => { promptInstalar = null; armazem.gravar('tm_app', {instalado: hoje()}); medir('app_instalado'); const c = $('#convite-app'); if (c) c.hidden = true; });
  const jaInstalado = () => matchMedia('(display-mode: standalone)').matches || navigator.standalone === true || Boolean((armazem.ler('tm_app', null) || {}).instalado);
  const fechadoRecente = () => { const f = armazem.ler('tm_app', null); return f && f.fechado && diasEntre(f.fechado, hoje()) < 30; };
  function convidarInstalar() {
    const caixa = $('#convite-app');
    if (!caixa || !armazem.ler('tm_marcados', []).length || jaInstalado() || fechadoRecente()) return;
    const ios = /iPhone|iPad|iPod/.test(navigator.userAgent) && !/CriOS|FxiOS/.test(navigator.userAgent) || (/Macintosh/.test(navigator.userAgent) && navigator.maxTouchPoints > 1);
    if (!promptInstalar && !ios) return;  // sem como instalar neste navegador: nada de convite que não leva a lugar nenhum
    caixa.querySelector('.ca-acao').innerHTML = promptInstalar
      ? '<button type="button" class="botao" id="instalar-app">Instalar</button>'
      : '<p class="ca-ios">No iPhone: toque em <b>Compartilhar</b> e depois em <b>Adicionar à Tela de Início</b>.</p>';
    caixa.hidden = false;
    const botao = $('#instalar-app');
    if (botao) botao.addEventListener('click', async () => { try { promptInstalar.prompt(); await promptInstalar.userChoice; } catch (e) { /* o navegador decide */ } promptInstalar = null; caixa.hidden = true; });
    $('#fechar-app').addEventListener('click', () => { armazem.gravar('tm_app', {...(armazem.ler('tm_app', null) || {}), fechado: hoje()}); caixa.hidden = true; });
  }

  function paginaMinhaLista() {
    const caixa = $('#minha-lista');
    const h = hoje();
    const marcados = armazem.ler('tm_marcados', []);
    const salvos = salvosDoAparelho()
      .sort((a, b) => (ORDEM[situacao(a)] - ORDEM[situacao(b)]) || String(a.fim || '9999').localeCompare(String(b.fim || '9999')));
    if (!salvos.length) {
      const proximos = TM.editais.filter(e => situacao(e) === 'aberto' && e.fim && e.fim >= h && conferido(e, 'fim')).sort((a, b) => a.fim.localeCompare(b.fim)).slice(0, 3);
      caixa.innerHTML = `<div class="vazio">Nenhum edital salvo ainda. Toque em “☆ Salvar na minha lista” num edital para montar o seu plano: prazos, provas no mesmo dia e documentos.
        <p class="acoes"><a class="botao" href="${RAIZ}diagnostico/">Descobrir onde posso transferir</a></p></div>`
        + (proximos.length ? `<h2 class="mp-titulo">Os que encerram primeiro</h2>${proximos.map(e => cartao(e, null)).join('')}` : '');
      return;
    }
    const eventos = eventosDoPlano(salvos, h), choques = detectarChoques(salvos, h), diaChoque = new Set(choques.map(c => c.data));
    const chip = ev => {
      const d = diasEntre(h, ev.data), cls = diaChoque.has(ev.data) && ev.campo === 'prova' ? 'mp-verm' : ev.campo === 'fim' && d <= 2 ? 'mp-verm' : ev.campo === 'fim' && d <= 10 ? 'mp-ambar' : 'mp-verde';
      return `<span class="mp-dia ${cls}"><b>${ev.data.slice(8)}</b><small>${MES3[Number(ev.data.slice(5, 7)) - 1]}</small></span>`;
    };
    const linhas = eventos.map(ev => `<li>${chip(ev)}<div><p><b>${esc(nomeEdital(ev.e))}</b> · ${ev.rotulo}</p><small>${quando(diasEntre(h, ev.data))}${ev.pg ? ` · ${esc(ev.pg)}` : ''}</small></div></li>`).join('');
    const comEvento = new Set(eventos.map(x => x.e.id)).size;
    const semData = salvos.filter(e => !eventos.some(x => x.e.id === e.id));
    const docs = agruparDocumentos(salvos);
    const comDocs = salvos.filter(e => (e.docs || []).length).length;
    const minimo = comDocs >= 2 && docs.some(g => g.pedem >= 2) ? 2 : 1, comuns = docs.filter(g => g.pedem >= minimo), unicos = docs.filter(g => g.pedem < minimo);
    const feitos = lerMarcados(salvos), nFeitos = comuns.filter(g => feitoDoc(g, feitos)).length;
    const linhaDoc = (g, i) => `<li><label><input type="checkbox" data-doc="${i}"${feitoDoc(g, feitos) ? ' checked' : ''}><span>${esc(g.rotulo)}</span></label><small>pedem ${g.pedem} de ${comDocs}</small></li>`;
    const escolhidos = (marcados.length > MAX_COMPARAR && armazem.ler('tm_comparar', null) || marcados.slice(0, MAX_COMPARAR)).filter(id => marcados.includes(id)).slice(0, MAX_COMPARAR);
    const ordemSalvos = marcados.map(id => salvos.find(e => e.id === id)).filter(Boolean);
    caixa.innerHTML = `<p class="mp-eyebrow">Meu plano · ${salvos.length} ${salvos.length === 1 ? 'edital salvo' : 'editais salvos'}</p>
      <h2 class="mp-titulo" id="mp-titulo" tabindex="-1">Seus próximos prazos</h2>
      ${choques.map(c => `<div class="mp-choque" role="alert">${textoChoque(c)}</div>`).join('')}
      <section class="mp-bloco" aria-labelledby="mp-titulo">
        ${eventos.length ? `<ul class="mp-linha">${linhas}</ul>` : '<p class="dica">Nenhuma data conferida pela frente nos editais salvos. Abra cada edital para ver o que a faculdade ainda precisa confirmar.</p>'}
        ${semData.length ? `<p class="dica">Sem data conferida para o plano: ${esc(listaE(semData.map(nomeEdital)))}. As datas aparecem aqui quando estiverem conferidas no edital.</p>` : ''}
        ${eventos.length ? `<button type="button" class="botao mp-agenda" id="mp-agenda">Pôr os ${comEvento} na minha agenda</button>
        <p class="dica">Um arquivo de agenda com os prazos acima e alarme 7 e 2 dias antes do fim das inscrições, às 9h. Não se atualiza sozinho: se a faculdade mudar uma data, o plano daqui muda, mas o arquivo já baixado, não.</p>` : ''}
      </section>
      ${docs.length ? `<section class="mp-bloco" aria-labelledby="mp-docs"><div class="mp-docs-topo"><h3 id="mp-docs">${minimo === 2 ? 'Documentos de todos' : 'Documentos'}</h3><span id="mp-docs-n">${nFeitos} de ${comuns.length}</span></div>
        <div class="progresso fino" aria-hidden="true"><i id="mp-docs-barra" style="width:${comuns.length ? nFeitos / comuns.length * 100 : 0}%"></i></div>
        <ul class="check mp-docs" id="mp-docs-lista">${comuns.map((g, i) => linhaDoc(g, i)).join('')}</ul>
        ${unicos.length ? `<details class="mp-so-um"><summary>Documentos de um edital só (${unicos.length})</summary><ul class="check mp-docs" id="mp-docs-unicos">${unicos.map((g, i) => linhaDoc(g, comuns.length + i)).join('')}</ul></details>` : ''}
        <p class="dica">O que você marca aqui também aparece marcado no checklist de cada edital. Só agrupamos documentos escritos exatamente do mesmo jeito${comDocs < salvos.length ? `; ${salvos.length - comDocs} ${salvos.length - comDocs === 1 ? 'edital salvo não tem' : 'editais salvos não têm'} lista transcrita (veja no edital)` : ''}.</p></section>` : ''}
      ${ordemSalvos.length >= 2 ? `<section class="mp-bloco" aria-labelledby="mp-comp"><h3 id="mp-comp">Comparar os que você escolheu</h3>
        ${ordemSalvos.length > MAX_COMPARAR ? `<fieldset class="mp-escolha"><legend>Escolha até ${MAX_COMPARAR}</legend>${ordemSalvos.map(e => `<label class="mp-pilula"><input type="checkbox" data-comparar="${esc(e.id)}"${escolhidos.includes(e.id) ? ' checked' : ''}${!escolhidos.includes(e.id) && escolhidos.length >= MAX_COMPARAR ? ' disabled' : ''}><span>${esc(nomeEdital(e))}</span></label>`).join('')}</fieldset>` : ''}
        <div id="mp-tabela">${escolhidos.length >= 2 ? htmlComparar(escolhidos.map(id => salvos.find(e => e.id === id))) : '<p class="dica">Escolha pelo menos 2 editais para comparar.</p>'}</div></section>` : ''}
      ${salvos.filter(e => e.ret).map(htmlRetificacao).join('')}
      <h3 class="mp-titulo espaco-24">Editais salvos</h3>
      ${salvos.map(e => cartao(e, null)).join('')}
      ${painelAssinar(salvos, 'cal-lista')}
      <aside class="convite-app" id="convite-app" hidden><img src="${RAIZ}assets/marca/logo-192-v3.png" alt="" width="56" height="56"><div><b>Transfermed no seu celular</b><p>Abra como app, direto nos seus prazos.</p></div>
        <div class="ca-acao"></div><button type="button" class="link-botao" id="fechar-app">Agora não</button></aside>`;
    ligarPainelAssinar($('#cal-lista'), salvos, 'transfermed-minha-lista.ics');
    if (escolhidos.length >= 2 && !paginaMinhaLista.mediu) { paginaMinhaLista.mediu = true; medir('comparar_aberto'); }
    const agenda = $('#mp-agenda');
    if (agenda) agenda.addEventListener('click', () => { baixarIcs(salvos, 'transfermed-meu-plano.ics', {campos: ['fim', 'prova', 'res'], desde: hoje()}); medir('plano_agenda'); });
    const todosDocs = [...comuns, ...unicos];
    caixa.querySelectorAll('input[data-doc]').forEach(c => c.addEventListener('change', () => {
      marcarDoc(todosDocs[Number(c.dataset.doc)], c.checked);
      const f = lerMarcados(salvos), n = comuns.filter(g => feitoDoc(g, f)).length;
      $('#mp-docs-n').textContent = `${n} de ${comuns.length}`;
      $('#mp-docs-barra').style.width = `${comuns.length ? n / comuns.length * 100 : 0}%`;
      if (c.checked) medir('checklist_usado');
    }));
    caixa.querySelectorAll('input[data-comparar]').forEach(c => c.addEventListener('change', () => {
      const ids = [...caixa.querySelectorAll('input[data-comparar]:checked')].map(x => x.dataset.comparar).slice(0, MAX_COMPARAR);
      armazem.gravar('tm_comparar', ids);
      paginaMinhaLista();
      const alvo = caixa.querySelector(`input[data-comparar="${CSS.escape(c.dataset.comparar)}"]`); if (alvo) alvo.focus();
    }));
    convidarInstalar();
  }
  // tirar (ou pôr) a estrela num cartão da página refaz o plano na hora
  document.addEventListener('click', ev => {
    if (!ev.target.closest('[data-marcar]') || document.body.dataset.pagina !== 'minha-lista') return;
    setTimeout(() => { paginaMinhaLista(); const t = $('#mp-titulo'); if (t && !document.activeElement.closest('#minha-lista')) t.focus({preventScroll: true}); }, 0);
  });

  // ---------------------------------------------------------------- menu do celular (☰ no cabeçalho)
  function menuCelular() {
    const botao = $('.menu-botao'), menu = $('#menu-celular');
    if (!botao || !menu) return;
    const fechar = () => { menu.hidden = true; botao.setAttribute('aria-expanded', 'false'); };
    botao.addEventListener('click', () => {
      const abrir = menu.hidden;
      menu.hidden = !abrir;
      botao.setAttribute('aria-expanded', String(abrir));
    });
    document.addEventListener('keydown', ev => { if (ev.key === 'Escape' && !menu.hidden) { fechar(); botao.focus(); } });
    document.addEventListener('click', ev => { if (!menu.hidden && !menu.contains(ev.target) && !botao.contains(ev.target)) fechar(); });
    $('.busca-botao') && $('.busca-botao').addEventListener('click', fechar);
  }

  medir('visita');
  busca();
  menuCelular();
  quemFaz();
  contarLista();
  formularioContato();
  const pagina = document.body.dataset.pagina;
  if (pagina === 'inicio') { listaAbertos(); provaSocial(); }
  if (pagina === 'editais') { listaAbertos(); paginaInicio(); }
  if (pagina === 'diagnostico') paginaDiagnostico();
  formularioAlerta();
  barraAlerta();
  if (pagina === 'edital') paginaEdital();
  if (pagina === 'alerta') paginaAlerta();
  if (pagina === 'minha-lista') paginaMinhaLista();
})();
