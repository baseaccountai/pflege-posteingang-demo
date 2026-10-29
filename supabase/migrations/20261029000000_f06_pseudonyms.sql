-- F06: every resident gets a stable code for placeholders ("Bewohner_A17"), and the
-- backend gets a directory of all residents' names to replace them before a model call.

-- A random, unused code: one letter and two digits. Random on purpose - a hash of the
-- name could be reversed with a list of names.
create function app.new_pseudonym() returns text
language plpgsql volatile
set search_path = ''
as $$
declare
  code text;
begin
  loop
    code := chr(65 + floor(random() * 26)::int) || lpad(floor(random() * 100)::int::text, 2, '0');
    exit when not exists (select from public.residents where pseudonym = code);
  end loop;
  return code;
end;
$$;
revoke all on function app.new_pseudonym() from public;

alter table public.residents add column pseudonym text;
update public.residents set pseudonym = app.new_pseudonym();
alter table public.residents
  alter column pseudonym set default app.new_pseudonym(),
  alter column pseudonym set not null,
  add constraint residents_pseudonym_format check (pseudonym ~ '^[A-Z][0-9]{2}$'),
  add constraint residents_pseudonym_unique unique (pseudonym);

-- Names and birth dates of ALL residents (also other wards), so that a WB2 name in a WB1
-- document is replaced as well (F06-AC2). This deliberately bypasses RLS, therefore:
-- only the backend login role may call it, before it switches to `authenticated`. No
-- caller principal (nurse, PDL, agent) and no `anon` can (F06-AC8).
create function app.pseudonym_directory()
returns table (resident_id uuid, pseudonym text, display_name text, birth_date date)
language sql stable security definer
set search_path = ''
as $$
  select r.id, r.pseudonym, r.display_name, r.birth_date from public.residents r
$$;
revoke all on function app.pseudonym_directory() from public, anon, authenticated;
grant usage on schema app to api_gateway;
grant execute on function app.pseudonym_directory() to api_gateway;
