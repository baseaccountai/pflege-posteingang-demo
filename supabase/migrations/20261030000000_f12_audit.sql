-- F12: the audit log for the care manager (PDL). Who did what with AI - human or agent,
-- with which model, and what was blocked. No contents: no document or question texts, no
-- resident names, no tokens (F12-AC3).
--
-- Two ways in, both run as audit_owner (security definer), the only role with rights on
-- the table:
--   1. triggers on the business tables write state changes in the same transaction as the
--      change - no change without its event, no event without its change (F12-AC4, AC8);
--   2. app.log_event() for model calls, questions, tools and blocks, with a fixed list of
--      actions (F12-AC9). The backend calls it after the call, in a transaction of its own.
-- Actor, actor type and ward always come from the claims of the session (F12-AC4).

do $$
begin
  if not exists (select from pg_roles where rolname = 'audit_owner') then
    create role audit_owner nologin noinherit nobypassrls;
  end if;
end $$;
grant audit_owner to current_user;  -- needed to hand the functions over below

create table public.audit_events (
  id bigint generated always as identity primary key,
  at timestamptz not null default now(),
  ward_id text,                     -- null: not tied to one ward (e.g. a question of the PDL)
  action text not null,
  outcome text not null check (outcome in ('ok', 'blocked', 'error')),
  actor_type text not null check (actor_type in ('human', 'agent')),
  actor_sub text not null,
  actor_name text not null,
  on_behalf_of_name text,           -- agent only: the user it works for
  model text,
  -- No foreign keys: the log outlives what it describes and must not block the reset.
  document_id uuid,
  resident_id uuid,
  details jsonb not null default '{}'
);
create index audit_events_ward on public.audit_events (ward_id, id desc);

alter table public.audit_events enable row level security;
alter table public.audit_events force row level security;
revoke all on public.audit_events from public, anon, authenticated;
grant select on public.audit_events to authenticated;
grant insert on public.audit_events to audit_owner;

-- F12-AC6: only the PDL reads, and only her wards plus events without a ward.
create policy audit_events_select on public.audit_events for select to authenticated
  using (app.role() = 'pdl' and (ward_id is null or ward_id = any (app.ward_ids())));
create policy audit_events_insert on public.audit_events for insert to audit_owner
  with check (true);

-- F12-AC5: nobody changes or deletes an event, not even an admin. Only the nightly reset
-- empties the table, with TRUNCATE (statement level, no row triggers).
create function app.audit_events_append_only() returns trigger
language plpgsql as $$
begin
  raise exception 'audit events cannot be changed or deleted';
end $$;
create trigger audit_events_append_only
  before update or delete on public.audit_events
  for each row execute function app.audit_events_append_only();

-- audit_owner checks that a document or resident belongs to the caller's wards.
grant usage on schema app to audit_owner;
grant execute on function app.claims(), app.ward_ids(), app.uid(), app.actor_type(),
  app.display_name() to audit_owner;
grant select (id, ward_id) on public.documents, public.residents to audit_owner;
create policy documents_audit_owner on public.documents for select to audit_owner using (true);
create policy residents_audit_owner on public.residents for select to audit_owner using (true);

-- One event with the actor from the claims. Without claims (seed, reset, test setup) there
-- is nobody to name, so nothing is written; the API always sets claims.
create function app.write_audit_event(
  p_ward text, p_action text, p_outcome text, p_model text,
  p_document uuid, p_resident uuid, p_details jsonb
) returns void
language plpgsql security definer set search_path = app, pg_temp as $$
declare
  v_agent boolean := app.actor_type() = 'agent';
begin
  if app.uid() is null then
    return;
  end if;
  insert into public.audit_events (ward_id, action, outcome, actor_type, actor_sub,
    actor_name, on_behalf_of_name, model, document_id, resident_id, details)
  values (p_ward, p_action, p_outcome, case when v_agent then 'agent' else 'human' end,
    app.uid(), case when v_agent then 'KI-Agent' else app.display_name() end,
    case when v_agent then app.display_name() end,
    p_model, p_document, p_resident, coalesce(p_details, '{}'));
end $$;

-- Way 1: triggers --------------------------------------------------------------------
create function app.audit_document() returns trigger
language plpgsql security definer set search_path = app, pg_temp as $$
declare
  v_action text;
  v_outcome text := 'ok';
  v_details jsonb := '{}';
  v_model text;
begin
  if tg_op = 'INSERT' then
    v_action := 'upload';
  elsif new.status = 'approved' then
    v_action := 'approval';
  elsif new.status = 'rejected' then
    v_action := 'rejection';
  else
    v_action := 'status_change';
    v_details := jsonb_build_object('status', new.status);
    if new.status in ('failed', 'unreadable') then
      v_outcome := 'error';
      v_details := v_details || jsonb_strip_nulls(jsonb_build_object('error_code', new.error_code));
    end if;
    if new.status = 'ready_for_review' then
      v_model := new.suggestion_model;
    end if;
  end if;
  perform app.write_audit_event(new.ward_id, v_action, v_outcome, v_model, new.id,
    new.resident_id, v_details);
  return null;
end $$;

create trigger documents_audit_insert
  after insert on public.documents
  for each row execute function app.audit_document();
create trigger documents_audit_status
  after update of status on public.documents
  for each row when (new.status is distinct from old.status)
  execute function app.audit_document();

-- Record entries: which kind, never the text.
create function app.audit_record_entry() returns trigger
language plpgsql security definer set search_path = app, pg_temp as $$
declare
  v_document uuid;
  v_resident uuid;
begin
  if tg_table_name = 'medication_events' then
    v_document := new.document_id;
    select m.resident_id into v_resident from public.medications m where m.id = new.medication_id;
  else
    v_document := new.source_document_id;
    v_resident := new.resident_id;
  end if;
  perform app.write_audit_event(new.ward_id, 'record_entry', 'ok', null, v_document,
    v_resident, jsonb_build_object('entry', tg_argv[0]));
  return null;
end $$;

grant select (id, resident_id) on public.medications to audit_owner;
create policy medications_audit_owner on public.medications for select to audit_owner using (true);

create trigger medication_events_audit after insert on public.medication_events
  for each row execute function app.audit_record_entry('medication');
create trigger diagnoses_audit after insert on public.diagnoses
  for each row execute function app.audit_record_entry('diagnosis');
create trigger follow_ups_audit after insert on public.follow_ups
  for each row execute function app.audit_record_entry('follow_up');

-- Way 2: app.log_event ----------------------------------------------------------------
-- Only these actions (F12-AC9); state changes come from the triggers alone. Details only
-- with these keys and short values (identifiers, no texts - F12-AC3).
create function app.log_event(
  p_action text, p_outcome text, p_model text,
  p_document uuid, p_resident uuid, p_details jsonb
) returns void
language plpgsql security definer set search_path = app, pg_temp as $$
declare
  v_ward text;
  v_key text;
  v_value jsonb;
begin
  if p_action is null or p_action not in ('ocr', 'screening', 'extraction', 'question',
      'agent_task', 'agent_tool', 'blocked', 'quota_exhausted') then
    raise exception 'action not allowed: %', p_action using errcode = 'invalid_parameter_value';
  end if;
  if p_outcome is null or p_outcome not in ('ok', 'blocked', 'error') then
    raise exception 'unknown outcome' using errcode = 'invalid_parameter_value';
  end if;
  if p_model is not null and char_length(p_model) > 100 then
    raise exception 'model name too long' using errcode = 'invalid_parameter_value';
  end if;
  for v_key, v_value in select * from jsonb_each(coalesce(p_details, '{}')) loop
    if v_key not in ('rule_id', 'layer', 'tool', 'error_code', 'proposal_id', 'pages') then
      raise exception 'detail not allowed: %', v_key using errcode = 'invalid_parameter_value';
    end if;
    if not (
      (jsonb_typeof(v_value) = 'string' and char_length(v_value #>> '{}') <= 100)
      or jsonb_typeof(v_value) = 'number'
      or (jsonb_typeof(v_value) = 'array' and not exists (
            select from jsonb_array_elements(v_value) e where jsonb_typeof(e) <> 'number'))
    ) then
      raise exception 'detail % must be a short identifier or numbers', v_key
        using errcode = 'invalid_parameter_value';
    end if;
  end loop;

  -- The ward: that of the document or resident, which must be one of the caller's wards;
  -- otherwise the caller's only ward, or none if there are several.
  if p_document is not null then
    select ward_id into v_ward from public.documents where id = p_document;
  elsif p_resident is not null then
    select ward_id into v_ward from public.residents where id = p_resident;
  elsif cardinality(app.ward_ids()) = 1 then
    v_ward := (app.ward_ids())[1];
  end if;
  if (p_document is not null or p_resident is not null)
     and (v_ward is null or not v_ward = any (app.ward_ids())) then
    raise exception 'not in the caller''s wards' using errcode = 'insufficient_privilege';
  end if;
  if p_document is not null and p_resident is not null and not exists (
      select from public.residents where id = p_resident and ward_id = v_ward) then
    raise exception 'not in the caller''s wards' using errcode = 'insufficient_privilege';
  end if;
  if app.uid() is null then
    raise exception 'no caller' using errcode = 'insufficient_privilege';
  end if;

  perform app.write_audit_event(v_ward, p_action, p_outcome, p_model, p_document,
    p_resident, p_details);
end $$;

-- A new owner needs CREATE on the schema for the hand-over only; taken back right after.
grant create on schema app to audit_owner;
alter function app.write_audit_event(text, text, text, text, uuid, uuid, jsonb) owner to audit_owner;
alter function app.audit_document() owner to audit_owner;
alter function app.audit_record_entry() owner to audit_owner;
alter function app.log_event(text, text, text, uuid, uuid, jsonb) owner to audit_owner;
revoke create on schema app from audit_owner;

revoke all on function app.write_audit_event(text, text, text, text, uuid, uuid, jsonb),
  app.audit_document(), app.audit_record_entry(), app.audit_events_append_only(),
  app.log_event(text, text, text, uuid, uuid, jsonb) from public, anon, authenticated;
grant execute on function app.log_event(text, text, text, uuid, uuid, jsonb) to authenticated;
-- The triggers call write_audit_event as their owner audit_owner.
grant execute on function app.write_audit_event(text, text, text, text, uuid, uuid, jsonb)
  to audit_owner;
