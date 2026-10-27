-- F10-AC10: daily and per-session quotas, enforced by the database.
-- Callers can only book through app.consume_quota; limits and counters are not writable
-- for them. The function runs as quota_owner (security definer), the only role with
-- rights on these two tables.

do $$
begin
  if not exists (select from pg_roles where rolname = 'quota_owner') then
    create role quota_owner nologin noinherit nobypassrls;
  end if;
end $$;
grant quota_owner to current_user;  -- needed to hand the function over below

create table public.quota_limits (
  kind text primary key,
  scope text not null check (scope in ('global', 'session')),  -- global: per day
  max_count int not null check (max_count >= 0)
);

insert into public.quota_limits (kind, scope, max_count) values
  ('upload', 'session', 5),        -- uploads per login session (F02-AC10), whole session
  ('ocr_page', 'global', 100),     -- per calendar day in Europe/Berlin
  ('llm_call', 'global', 300),     -- every attempt, retries included
  ('embed_chunk', 'global', 500);

create table public.usage_counters (
  period text not null,            -- '2026-10-27' (daily) or 'lifetime' (session quotas)
  kind text not null references public.quota_limits (kind),
  subject text not null,           -- 'global' or the session hash from the BFF assertion
  count int not null check (count >= 0),
  primary key (period, kind, subject)
);

alter table public.quota_limits enable row level security;
alter table public.usage_counters enable row level security;
revoke all on public.quota_limits, public.usage_counters from public, anon, authenticated;
grant select on public.quota_limits to quota_owner;
grant select, insert, update on public.usage_counters to quota_owner;
create policy quota_limits_owner on public.quota_limits for select to quota_owner using (true);
create policy usage_counters_owner on public.usage_counters for all to quota_owner
  using (true) with check (true);

-- Books `amount` units or nothing. True if booked, false if the limit would be exceeded.
-- The insert ... on conflict ... where is one atomic statement: parallel callers queue on
-- the row and can never push the count above the limit, also not with the first booking.
create or replace function app.consume_quota(p_kind text, p_subject text, p_amount int)
returns boolean
language plpgsql security definer set search_path = app, pg_temp as $$
declare
  v_limit int;
  v_scope text;
  v_period text;
  v_subject text;
  v_booked boolean;
begin
  if p_amount is null or p_amount < 1 or p_amount > 20 then
    raise exception 'amount must be between 1 and 20' using errcode = 'invalid_parameter_value';
  end if;
  select max_count, scope into v_limit, v_scope from public.quota_limits where kind = p_kind;
  if not found then
    raise exception 'unknown quota kind' using errcode = 'invalid_parameter_value';
  end if;
  if v_scope = 'global' then
    -- The subject of a daily quota is always 'global': a caller cannot dodge it.
    v_subject := 'global';
    v_period := ((now() at time zone 'Europe/Berlin')::date)::text;
  else
    if p_subject is null or p_subject !~ '^[0-9a-f]{64}$' then
      raise exception 'session quota needs a session hash' using errcode = 'invalid_parameter_value';
    end if;
    v_subject := p_subject;
    v_period := 'lifetime';
  end if;
  if p_amount > v_limit then
    return false;
  end if;
  insert into public.usage_counters as u (period, kind, subject, count)
  values (v_period, p_kind, v_subject, p_amount)
  on conflict (period, kind, subject) do update
    set count = u.count + excluded.count
    where u.count + excluded.count <= v_limit
  returning true into v_booked;
  return coalesce(v_booked, false);
end $$;

-- A new owner needs CREATE on the schema for the hand-over only; taken back right after.
grant usage, create on schema app to quota_owner;
alter function app.consume_quota(text, text, int) owner to quota_owner;
revoke create on schema app from quota_owner;
revoke all on function app.consume_quota(text, text, int) from public, anon;
grant execute on function app.consume_quota(text, text, int) to authenticated;
