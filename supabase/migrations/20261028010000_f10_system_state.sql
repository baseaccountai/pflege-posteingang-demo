-- F10-AC7: maintenance flag for the nightly reset.
-- Only the reset (admin connection) switches it; the API reads it through
-- app.in_maintenance() and refuses writes with 503 while it is set. The flag is just the
-- message for visitors: correctness comes from the reset being one transaction whose
-- TRUNCATE waits for running transactions and blocks new ones until it commits.

create table public.system_state (
  id boolean primary key default true check (id),  -- exactly one row
  maintenance boolean not null default false,
  updated_at timestamptz not null default now()
);
insert into public.system_state default values;

alter table public.system_state enable row level security;
revoke all on public.system_state from public, anon, authenticated;

create or replace function app.in_maintenance() returns boolean
language sql stable security definer set search_path = public, pg_temp as $$
  select coalesce((select maintenance from public.system_state), false)
$$;
revoke all on function app.in_maintenance() from public, anon;
grant execute on function app.in_maintenance() to authenticated;
