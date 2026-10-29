-- Transfermed: banco dos alertas por e-mail (Supabase, plano grátis).
-- Cole este arquivo inteiro em Supabase > SQL Editor > New query > Run. Pode rodar de novo sem problema.
--
-- Segurança: o site (chave "anon", pública) NÃO lê nem altera as tabelas. Ele só chama três funções:
--   inscrever  -> cria ou atualiza um cadastro pendente
--   confirmar  -> ativa o cadastro pelo link do e-mail
--   descadastrar -> APAGA o cadastro e o histórico (LGPD: eliminação a pedido do titular)
-- Só o robô (chave "service_role", guardada em segredo no GitHub) lê a lista para enviar os e-mails.

create table if not exists public.assinantes (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  perfil jsonb not null,
  token uuid not null default gen_random_uuid(),
  status text not null default 'pendente' check (status in ('pendente', 'ativo')),
  consentimento_texto text not null,
  consentimento_em timestamptz not null default now(),
  confirmacao_enviada_em timestamptz,
  confirmado_em timestamptz,
  criado_em timestamptz not null default now()
);
create unique index if not exists assinantes_email_unico on public.assinantes (lower(email));
-- quem já está ativo e pede de novo recebe na hora um "seu alerta foi atualizado" (no máximo a cada 10 minutos)
alter table public.assinantes add column if not exists atualizacao_pendente boolean not null default false;
alter table public.assinantes add column if not exists atualizacao_avisada_em timestamptz;

-- envio na hora: cada inscrição acorda o workflow "Alertas por e-mail" no GitHub (confirmação em cerca de 1 minuto,
-- sem esperar a rodada de 30 em 30 min). O token (fine-grained, só este repositório, permissão "Actions: read and
-- write") fica no Vault do Supabase: select vault.create_secret('<token>', 'github_token');
-- Sem o token, nada muda: a rodada agendada envia como antes.
create extension if not exists pg_net;
create table if not exists public.disparos (id int primary key default 1 check (id = 1), ultimo timestamptz not null);
alter table public.disparos enable row level security;
revoke all on public.disparos from anon, authenticated;

create or replace function public.acordar_envio()
returns void language plpgsql security definer set search_path = public as $$
declare
  v_token text;
begin
  -- no máximo um disparo a cada 20 s (várias inscrições juntas entram na mesma rodada)
  if exists (select 1 from public.disparos where ultimo > now() - interval '20 seconds') then
    return;
  end if;
  select decrypted_secret into v_token from vault.decrypted_secrets where name = 'github_token' limit 1;
  if v_token is null then
    return;
  end if;
  insert into public.disparos (id, ultimo) values (1, now()) on conflict (id) do update set ultimo = now();
  perform net.http_post(
    url := 'https://api.github.com/repos/cauagabrielmarin06-cloud/transfermed/actions/workflows/alertas.yml/dispatches',
    body := '{"ref": "main"}'::jsonb,
    headers := jsonb_build_object('Authorization', 'Bearer ' || v_token, 'Accept', 'application/vnd.github+json',
                                  'User-Agent', 'transfermed-supabase', 'Content-Type', 'application/json'));
exception when others then
  return;  -- o envio imediato nunca impede a inscrição
end $$;
revoke all on function public.acordar_envio() from public, anon, authenticated;

create table if not exists public.notificacoes (
  assinante_id uuid not null references public.assinantes (id) on delete cascade,
  edital_id text not null,
  enviado_em timestamptz not null default now(),
  primary key (assinante_id, edital_id)
);

alter table public.assinantes enable row level security;
alter table public.notificacoes enable row level security;
-- sem nenhuma "policy": quem usa a chave pública não enxerga nem altera as tabelas
revoke all on public.assinantes, public.notificacoes from anon, authenticated;

-- inscrever: valida o e-mail e o perfil, guarda o texto do consentimento aceito
create or replace function public.inscrever(p_email text, p_perfil jsonb, p_consentimento text)
returns text language plpgsql security definer set search_path = public as $$
declare
  v_email text := lower(trim(p_email));
  v_atual public.assinantes;
  v_novo jsonb;
begin
  if v_email !~ '^[^@\s]+@[^@\s]+\.[a-z]{2,}$' or length(v_email) > 200 then
    return 'email_invalido';
  end if;
  if p_perfil is null or jsonb_typeof(p_perfil) <> 'object' or length(p_perfil::text) > 2000 then
    return 'perfil_invalido';
  end if;
  if p_consentimento is null or length(p_consentimento) < 20 then
    return 'sem_consentimento';
  end if;
  select * into v_atual from public.assinantes where lower(email) = v_email;
  if found then
    -- atualiza o perfil e acorda o envio (confirmação reenviada ou aviso de alerta atualizado).
    -- "seguir" (faculdades e lembretes pedidos nas fichas) SOMA ao que já havia; um pedido sem curso (só seguir uma
    -- faculdade) não apaga o perfil do diagnóstico.
    v_novo := case when p_perfil ? 'curso' then p_perfil - 'seguir' else (v_atual.perfil - 'seguir') || (p_perfil - 'seguir') end;
    v_novo := v_novo || jsonb_build_object('seguir', jsonb_build_object(
      'faculdades', (select coalesce(jsonb_agg(distinct x), '[]'::jsonb) from (
          select jsonb_array_elements_text(coalesce(v_atual.perfil #> '{seguir,faculdades}', '[]')) x
          union select jsonb_array_elements_text(coalesce(p_perfil #> '{seguir,faculdades}', '[]'))) s),
      'lembretes', (select coalesce(jsonb_agg(distinct x), '[]'::jsonb) from (
          select jsonb_array_elements_text(coalesce(v_atual.perfil #> '{seguir,lembretes}', '[]')) x
          union select jsonb_array_elements_text(coalesce(p_perfil #> '{seguir,lembretes}', '[]'))) s)));
    if length(v_novo::text) > 4000 then
      return 'perfil_invalido';
    end if;
    update public.assinantes
       set perfil = v_novo, consentimento_texto = p_consentimento, consentimento_em = now(),
           -- pendente que pede de novo: a confirmação é reenviada na hora (no máximo a cada 10 min)
           confirmacao_enviada_em = case when status = 'pendente' and confirmacao_enviada_em < now() - interval '10 minutes'
                                         then null else confirmacao_enviada_em end,
           -- ativo que pede de novo: e-mail "seu alerta foi atualizado" (no máximo a cada 10 min)
           atualizacao_pendente = atualizacao_pendente
                                  or (status = 'ativo' and coalesce(atualizacao_avisada_em, 'epoch') < now() - interval '10 minutes')
     where id = v_atual.id;
    perform public.acordar_envio();
    return case when v_atual.status = 'ativo' then 'atualizado' else 'pendente' end;
  end if;
  insert into public.assinantes (email, perfil, consentimento_texto) values (v_email, p_perfil, p_consentimento);
  perform public.acordar_envio();
  return 'pendente';
end $$;

create or replace function public.confirmar(p_token uuid)
returns text language plpgsql security definer set search_path = public as $$
begin
  update public.assinantes set status = 'ativo', confirmado_em = coalesce(confirmado_em, now())
   where token = p_token;
  return case when found then 'ok' else 'nao_encontrado' end;
end $$;

create or replace function public.descadastrar(p_token uuid)
returns text language plpgsql security definer set search_path = public as $$
begin
  delete from public.assinantes where token = p_token;  -- apaga também as notificações (cascade)
  return case when found then 'ok' else 'nao_encontrado' end;
end $$;

-- número público e agregado (prova social só com dado real): quantos alertas ativos existem
create or replace function public.total_alertas()
returns integer language sql security definer set search_path = public as $$
  select count(*)::integer from public.assinantes where status = 'ativo';
$$;

revoke all on function public.inscrever(text, jsonb, text), public.confirmar(uuid), public.descadastrar(uuid), public.total_alertas() from public;
grant execute on function public.inscrever(text, jsonb, text), public.confirmar(uuid), public.descadastrar(uuid), public.total_alertas() to anon, authenticated;

-- ---------------------------------------------------------------- contato (formulário de /contato/ e /sobre/)
-- O site só chama a função "contato"; o robô de alertas encaminha a mensagem ao dono (segredo CONTATO_DESTINO),
-- manda a resposta automática e apaga a mensagem 90 dias depois de encaminhada.
create table if not exists public.mensagens (
  id uuid primary key default gen_random_uuid(),
  dados jsonb not null,
  consentimento_texto text not null,
  criado_em timestamptz not null default now(),
  encaminhada_em timestamptz
);
alter table public.mensagens enable row level security;
revoke all on public.mensagens from anon, authenticated;

create or replace function public.contato(p_dados jsonb, p_consentimento text)
returns text language plpgsql security definer set search_path = public as $$
declare
  v_email text := lower(trim(coalesce(p_dados->>'email', '')));
begin
  if p_dados is null or jsonb_typeof(p_dados) <> 'object' or length(p_dados::text) > 5000 then
    return 'dados_invalidos';
  end if;
  if v_email !~ '^[^@\s]+@[^@\s]+\.[a-z]{2,}$' or length(v_email) > 200 then
    return 'email_invalido';
  end if;
  if coalesce(p_dados->>'motivo', '') not in ('erro', 'duvida', 'sugestao', 'outro')
     or length(trim(coalesce(p_dados->>'nome', ''))) = 0 or length(trim(coalesce(p_dados->>'mensagem', ''))) < 5 then
    return 'dados_invalidos';
  end if;
  if p_consentimento is null or length(p_consentimento) < 20 then
    return 'sem_consentimento';
  end if;
  -- contra abuso: até 3 mensagens por e-mail por dia e 60 no total por hora
  if (select count(*) from public.mensagens where lower(dados->>'email') = v_email and criado_em > now() - interval '1 day') >= 3
     or (select count(*) from public.mensagens where criado_em > now() - interval '1 hour') >= 60 then
    return 'limite';
  end if;
  insert into public.mensagens (dados, consentimento_texto) values (p_dados, p_consentimento);
  return 'ok';
end $$;

revoke all on function public.contato(jsonb, text) from public;
grant execute on function public.contato(jsonb, text) to anon, authenticated;

-- ---------------------------------------------------------------- medição do funil (sem cookies)
-- Só contagens: dia, evento e tipo de página. Nada de IP, identificador, endereço completo ou dado pessoal.
-- Os nomes aceitos estão na lista abaixo (o teste tests/test_site.py confere que batem com o app.js).
create table if not exists public.eventos (
  dia date not null default (now() at time zone 'America/Sao_Paulo')::date,
  nome text not null,
  pagina text not null,
  total integer not null default 0,
  primary key (dia, nome, pagina)
);
alter table public.eventos enable row level security;  -- sem política: só a função abaixo e a service key escrevem/leem

create or replace function public.medir(p_nome text, p_pagina text)
returns void language plpgsql security definer set search_path = public as $$
begin
  if p_nome not in ('visita', 'diagnostico_iniciado', 'diagnostico_concluido', 'ver_edital', 'abrir_pdf', 'adicionar_agenda',
                    'checklist_usado', 'salvar_lista', 'quem_faz_aberto', 'isca', 'alerta_inscrito', 'alerta_perfil',
                    'alerta_confirmado', 'barra_alerta', 'assinar_agenda', 'compartilhar_whatsapp', 'contato_enviado',
                    'alerta_inscrito_inicio', 'alerta_inscrito_diagnostico', 'alerta_inscrito_edital_lembrete',
                    'alerta_inscrito_edital_seguir', 'alerta_inscrito_faculdade_seguir', 'alerta_inscrito_exterior',
                    'alerta_inscrito_outro')
     or coalesce(p_pagina, '') !~ '^[a-z0-9-]{1,30}$' then
    return;
  end if;
  insert into public.eventos (nome, pagina, total) values (p_nome, p_pagina, 1)
  on conflict (dia, nome, pagina) do update set total = public.eventos.total + 1;
end $$;

revoke all on function public.medir(text, text) from public;
grant execute on function public.medir(text, text) to anon, authenticated;
