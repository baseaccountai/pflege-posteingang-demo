-- F02: documents and their original files. Same rules as residents: rows stay in their
-- ward (RLS + composite keys), cannot move, are never deleted by users.
-- Files live in Postgres, not in Supabase Storage (ADR 0010), so RLS covers them too.

create type public.document_status as enum (
  'uploaded', 'processing', 'extracting', 'ready_for_review',
  'approved', 'rejected', 'unreadable', 'failed'
);
create type public.doc_type as enum ('arztbrief', 'medikationsplan', 'ueberleitungsbogen', 'sonstiges');
create type public.indexing_status as enum ('pending', 'done', 'failed');

create table public.documents (
  id uuid primary key default gen_random_uuid(),
  ward_id text not null references public.wards (id),
  resident_id uuid,                      -- null until the review confirms the resident (F03)
  doc_type public.doc_type,
  status public.document_status not null default 'uploaded',
  -- Why the document is failed/unreadable (F02-AC7, F02-AC8); shown as a message.
  error_code text check (error_code in (
    'ocr_unavailable', 'llm_unavailable', 'quota_exceeded', 'timeout',
    'unreadable_text', 'not_care_document')),
  ocr_pages jsonb,                       -- [{page, markdown}]
  suggestion jsonb,                      -- F03
  suggestion_model text,
  document_date date,
  uploaded_by text not null default app.uid(),
  upload_session text not null,          -- sid_hash from the BFF assertion (F02-AC10)
  attempts int not null default 0,
  status_changed_at timestamptz not null default now(),
  approved_by text,
  approved_by_name text,
  approved_at timestamptz,
  indexing_status public.indexing_status,
  created_at timestamptz not null default now(),
  unique (id, ward_id),                  -- target of composite foreign keys (document + ward)
  -- A document can only point to a resident of its own ward.
  foreign key (resident_id, ward_id) references public.residents (id, ward_id)
);

create index documents_ward_created on public.documents (ward_id, created_at desc);

create table public.document_files (
  document_id uuid primary key,
  ward_id text not null,
  mime text not null check (mime in ('image/jpeg', 'image/png', 'application/pdf')),
  size_bytes int not null check (size_bytes between 1 and 4 * 1024 * 1024),
  content bytea not null check (octet_length(content) <= 4 * 1024 * 1024),
  foreign key (document_id, ward_id) references public.documents (id, ward_id)
);

-- ward_id, uploader and session never change; resident_id only once from null to a value.
create or replace function app.protect_document_identity() returns trigger
language plpgsql as $$
begin
  if new.ward_id is distinct from old.ward_id then
    raise exception 'ward_id cannot be changed' using errcode = 'check_violation';
  end if;
  if old.resident_id is not null and new.resident_id is distinct from old.resident_id then
    raise exception 'resident_id is already set' using errcode = 'check_violation';
  end if;
  if new.uploaded_by is distinct from old.uploaded_by
     or new.upload_session is distinct from old.upload_session
     or new.created_at is distinct from old.created_at then
    raise exception 'upload data cannot be changed' using errcode = 'check_violation';
  end if;
  return new;
end $$;
revoke all on function app.protect_document_identity() from public;

create trigger documents_protect_identity
  before update on public.documents
  for each row execute function app.protect_document_identity();

alter table public.documents enable row level security;
alter table public.documents force row level security;
alter table public.document_files enable row level security;
alter table public.document_files force row level security;

-- Supabase grants new tables to anon/authenticated by default; start from nothing.
revoke all on public.documents, public.document_files from public, anon, authenticated;
grant select, insert, update on public.documents to authenticated;
grant select, insert on public.document_files to authenticated;  -- files are never changed

create policy documents_select on public.documents
  for select to authenticated using (ward_id = any (app.ward_ids()));
create policy documents_insert on public.documents
  for insert to authenticated
  with check (ward_id = any (app.ward_ids()) and uploaded_by = app.uid());
create policy documents_update on public.documents
  for update to authenticated
  using (ward_id = any (app.ward_ids())) with check (ward_id = any (app.ward_ids()));

create policy document_files_select on public.document_files
  for select to authenticated using (ward_id = any (app.ward_ids()));
create policy document_files_insert on public.document_files
  for insert to authenticated with check (ward_id = any (app.ward_ids()));
