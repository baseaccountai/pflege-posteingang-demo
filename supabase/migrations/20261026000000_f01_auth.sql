-- F01: wards, residents, claim helpers, roles and the BFF session store.
-- Isolation by ward is enforced here (RLS), not in application code.

-- Claim helpers ---------------------------------------------------------------
-- The API sets `request.jwt.claims` per transaction (see apps/api/app/db.py).
-- Without claims every helper returns an empty value, so policies match nothing.
create schema if not exists app;

create or replace function app.claims() returns jsonb
language sql stable security invoker as $$
  select coalesce(nullif(current_setting('request.jwt.claims', true), '')::jsonb, '{}'::jsonb)
$$;

create or replace function app.ward_ids() returns text[]
language sql stable security invoker as $$
  select coalesce(array(select jsonb_array_elements_text(app.claims() -> 'ward_ids')), '{}')
$$;

create or replace function app.role() returns text
language sql stable security invoker as $$ select app.claims() ->> 'app_role' $$;

create or replace function app.uid() returns text
language sql stable security invoker as $$ select app.claims() ->> 'sub' $$;

create or replace function app.actor_type() returns text
language sql stable security invoker as $$ select app.claims() ->> 'actor_type' $$;

create or replace function app.display_name() returns text
language sql stable security invoker as $$ select app.claims() ->> 'display_name' $$;

-- Prevents moving rows between wards or residents after creation.
create or replace function app.prevent_reassignment() returns trigger
language plpgsql as $$
begin
  if new.ward_id is distinct from old.ward_id then
    raise exception 'ward_id cannot be changed' using errcode = 'check_violation';
  end if;
  return new;
end $$;

revoke all on schema app from public;
revoke all on all functions in schema app from public;
grant usage on schema app to authenticated;
grant execute on all functions in schema app to authenticated;

-- Tables -----------------------------------------------------------------------
create table public.wards (
  id text primary key,
  name text not null
);

create table public.residents (
  id uuid primary key default gen_random_uuid(),
  ward_id text not null references public.wards (id),
  display_name text not null,
  birth_date date,
  room text,
  created_at timestamptz not null default now(),
  unique (id, ward_id)  -- target of composite foreign keys (resident + ward)
);

create trigger residents_prevent_reassignment
  before update on public.residents
  for each row execute function app.prevent_reassignment();

alter table public.wards enable row level security;
alter table public.wards force row level security;
alter table public.residents enable row level security;
alter table public.residents force row level security;

-- Supabase grants new tables to anon/authenticated by default; start from nothing.
revoke all on public.wards, public.residents from public, anon, authenticated;
grant select on public.wards, public.residents to authenticated;

create policy wards_select on public.wards
  for select to authenticated using (id = any (app.ward_ids()));

create policy residents_select on public.residents
  for select to authenticated using (ward_id = any (app.ward_ids()));

-- Roles ------------------------------------------------------------------------
-- Passwords are set per environment, never in migrations.
do $$
begin
  if not exists (select from pg_roles where rolname = 'api_gateway') then
    create role api_gateway login noinherit nobypassrls;
  end if;
  if not exists (select from pg_roles where rolname = 'bff_session') then
    create role bff_session login noinherit nobypassrls;
  end if;
end $$;

-- api_gateway may only switch to `authenticated` (set local role), nothing else.
grant authenticated to api_gateway;

-- BFF session store (not exposed through the Supabase REST API) ----------------
create schema if not exists bff;
revoke all on schema bff from public;

create table bff.sessions (
  id_hash bytea primary key,           -- sha256 of the random session id in the cookie
  sub text not null,
  app_role text not null,
  display_name text not null,
  tokens_enc bytea not null,           -- AES-256-GCM (access, refresh, id token)
  access_expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  revoked_at timestamptz
);

grant usage on schema bff to bff_session;
grant select, insert, update, delete on bff.sessions to bff_session;
