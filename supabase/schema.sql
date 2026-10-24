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
    -- atualiza o perfil; se ainda não confirmou, o robô reenvia a confirmação (no máximo 1 vez por dia)
    update public.assinantes
       set perfil = p_perfil, consentimento_texto = p_consentimento, consentimento_em = now()
     where id = v_atual.id;
    return case when v_atual.status = 'ativo' then 'atualizado' else 'pendente' end;
  end if;
  insert into public.assinantes (email, perfil, consentimento_texto) values (v_email, p_perfil, p_consentimento);
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
