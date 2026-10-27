-- F03: the resident record. Entries are written only by the approval (F03-AC8) and keep
-- their origin: which document, who confirmed it, human or agent. Same rules as before:
-- RLS per ward, composite keys so no reference crosses wards, no delete, no rewriting.

create table public.medications (
  id uuid primary key default gen_random_uuid(),
  ward_id text not null references public.wards (id),
  resident_id uuid not null,
  name text not null,
  strength text,
  dosage jsonb not null default '{}',  -- {"morgens": "1", "mittags": "0", "abends": "1", "nachts": "0"}
  status text not null default 'active' check (status in ('active', 'discontinued')),
  created_by text not null default app.uid(),
  created_at timestamptz not null default now(),
  unique (id, ward_id),
  foreign key (resident_id, ward_id) references public.residents (id, ward_id)
);

-- History of every medication change; the origin of a medication is its latest event.
create table public.medication_events (
  id uuid primary key default gen_random_uuid(),
  ward_id text not null,
  medication_id uuid not null,
  kind text not null check (kind in ('new', 'changed', 'discontinued')),
  document_id uuid,
  before jsonb,
  after jsonb,
  actor_type text not null default app.actor_type(),
  created_by text not null default app.uid(),
  confirmed_by text not null default app.uid(),
  confirmed_by_name text not null default app.display_name(),
  created_at timestamptz not null default now(),
  foreign key (medication_id, ward_id) references public.medications (id, ward_id),
  foreign key (document_id, ward_id) references public.documents (id, ward_id)
);

create table public.diagnoses (
  id uuid primary key default gen_random_uuid(),
  ward_id text not null,
  resident_id uuid not null,
  text text not null,
  source_document_id uuid,
  actor_type text not null default app.actor_type(),
  created_by text not null default app.uid(),
  confirmed_by text not null default app.uid(),
  confirmed_by_name text not null default app.display_name(),
  created_at timestamptz not null default now(),
  foreign key (resident_id, ward_id) references public.residents (id, ward_id),
  foreign key (source_document_id, ward_id) references public.documents (id, ward_id)
);

create table public.follow_ups (  -- "Wiedervorlagen"
  id uuid primary key default gen_random_uuid(),
  ward_id text not null,
  resident_id uuid not null,
  title text not null,
  due_date date,
  status text not null default 'open' check (status in ('open', 'done')),
  done_by text,
  done_by_name text,
  done_at timestamptz,
  source_document_id uuid,
  actor_type text not null default app.actor_type(),
  created_by text not null default app.uid(),
  confirmed_by text not null default app.uid(),
  confirmed_by_name text not null default app.display_name(),
  created_at timestamptz not null default now(),
  foreign key (resident_id, ward_id) references public.residents (id, ward_id),
  foreign key (source_document_id, ward_id) references public.documents (id, ward_id)
);

create index medications_resident on public.medications (resident_id);
create index medication_events_medication on public.medication_events (medication_id, created_at);
create index diagnoses_resident on public.diagnoses (resident_id);
create index follow_ups_resident on public.follow_ups (resident_id);

-- Finished documents (approved/rejected) are frozen; only the search index status of
-- F05 may still change (F03-AC9).
create or replace function app.freeze_finished_documents() returns trigger
language plpgsql as $$
begin
  if old.status in ('approved', 'rejected') and (
       new.status is distinct from old.status
       or new.resident_id is distinct from old.resident_id
       or new.doc_type is distinct from old.doc_type
       or new.document_date is distinct from old.document_date
       or new.ocr_pages is distinct from old.ocr_pages
       or new.suggestion is distinct from old.suggestion
       or new.suggestion_model is distinct from old.suggestion_model
       or new.error_code is distinct from old.error_code
       or new.approved_by is distinct from old.approved_by
       or new.approved_by_name is distinct from old.approved_by_name
       or new.approved_at is distinct from old.approved_at) then
    raise exception 'document is % and cannot be changed', old.status
      using errcode = 'check_violation';
  end if;
  return new;
end $$;
revoke all on function app.freeze_finished_documents() from public;

create trigger documents_freeze_finished
  before update on public.documents
  for each row execute function app.freeze_finished_documents();

do $$
declare t text;
begin
  foreach t in array array['medications', 'medication_events', 'diagnoses', 'follow_ups'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('alter table public.%I force row level security', t);
    execute format('revoke all on public.%I from public, anon, authenticated', t);
    execute format('grant select, insert on public.%I to authenticated', t);
    execute format(
      'create policy %I on public.%I for select to authenticated using (ward_id = any (app.ward_ids()))',
      t || '_select', t);
  end loop;
end $$;

-- Updates only where the record needs them, column by column:
grant update (strength, dosage, status) on public.medications to authenticated;  -- changed, stopped
grant update (status, done_by, done_by_name, done_at) on public.follow_ups to authenticated;  -- F04

create policy medications_update on public.medications for update to authenticated
  using (ward_id = any (app.ward_ids())) with check (ward_id = any (app.ward_ids()));
create policy follow_ups_update on public.follow_ups for update to authenticated
  using (ward_id = any (app.ward_ids())) with check (ward_id = any (app.ward_ids()));

-- Inserts: own ward, and who did it comes from the claims, never from the request.
create policy medications_insert on public.medications for insert to authenticated
  with check (ward_id = any (app.ward_ids()) and created_by = app.uid());
create policy medication_events_insert on public.medication_events for insert to authenticated
  with check (ward_id = any (app.ward_ids()) and created_by = app.uid()
              and confirmed_by = app.uid() and confirmed_by_name = app.display_name()
              and actor_type = app.actor_type());
create policy diagnoses_insert on public.diagnoses for insert to authenticated
  with check (ward_id = any (app.ward_ids()) and created_by = app.uid()
              and confirmed_by = app.uid() and confirmed_by_name = app.display_name()
              and actor_type = app.actor_type());
create policy follow_ups_insert on public.follow_ups for insert to authenticated
  with check (ward_id = any (app.ward_ids()) and created_by = app.uid()
              and confirmed_by = app.uid() and confirmed_by_name = app.display_name()
              and actor_type = app.actor_type());
