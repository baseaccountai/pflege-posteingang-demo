-- F07: injection check before the field suggestion (F07-AC1, AC5) and its findings (AC6).

alter table public.documents
  add column screening_result text check (screening_result in ('clean', 'suspicious', 'not_screened')),
  -- The pages as the models may see them: suspicious sections replaced. Field suggestion
  -- and indexing read only this column, never ocr_pages (F07-AC5).
  add column screened_pages jsonb;

-- Documents from before F07 were never checked; say so instead of calling them clean.
-- (Visitor documents are removed by the nightly reset; the seed brings its own result.)
update public.documents
set screened_pages = ocr_pages, screening_result = 'not_screened'
where ocr_pages is not null;

-- The database keeps the check in the path, even if the application had a bug:
--  * extracting only from screening, and only with a result and cleaned pages
--  * ready_for_review only with a result
--  * entering screening (a new check or a retry) clears an old result
create function app.require_screening() returns trigger
language plpgsql as $$
begin
  if new.status = 'screening' and old.status is distinct from 'screening' then
    new.screening_result := null;
    new.screened_pages := null;
  end if;
  if new.status = 'extracting' and old.status is distinct from 'extracting' and (
       old.status is distinct from 'screening'
       or new.screening_result is null or new.screened_pages is null) then
    raise exception 'extracting needs a finished injection check' using errcode = 'check_violation';
  end if;
  if new.status = 'ready_for_review' and new.screening_result is null then
    raise exception 'review needs a finished injection check' using errcode = 'check_violation';
  end if;
  return new;
end $$;
revoke all on function app.require_screening() from public;

create trigger documents_require_screening
  before update on public.documents
  for each row execute function app.require_screening();

-- Finished documents stay frozen, now including the check result (F03-AC9).
create or replace function app.freeze_finished_documents() returns trigger
language plpgsql as $$
begin
  if old.status in ('approved', 'rejected') and (
       new.status is distinct from old.status
       or new.resident_id is distinct from old.resident_id
       or new.doc_type is distinct from old.doc_type
       or new.document_date is distinct from old.document_date
       or new.ocr_pages is distinct from old.ocr_pages
       or new.screened_pages is distinct from old.screened_pages
       or new.screening_result is distinct from old.screening_result
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

-- A check that cannot run fails the document with its own code (F07-AC7).
alter table public.documents drop constraint documents_error_code_check;
alter table public.documents add constraint documents_error_code_check check (error_code in (
  'ocr_unavailable', 'llm_unavailable', 'quota_exceeded', 'timeout',
  'unreadable_text', 'not_care_document', 'pseudonymization_failed', 'screening_unavailable'));

-- Findings (F07-AC6): what was found, where, by which layer. The excerpt is document
-- content (at most 500 characters), with the same rights as the document itself.
create table public.injection_findings (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null,
  ward_id text not null references public.wards (id),
  page int not null check (page >= 1),
  start_offset int,               -- in the page's markdown; null: hidden text the OCR missed
  end_offset int,
  layer text not null check (layer in ('hidden_text', 'pattern', 'classifier')),
  rule_id text not null,
  category text not null,
  excerpt text not null check (length(excerpt) <= 500),
  explanation text not null,
  created_at timestamptz not null default now(),
  foreign key (document_id, ward_id) references public.documents (id, ward_id) on delete cascade
);
create index injection_findings_document on public.injection_findings (document_id);

alter table public.injection_findings enable row level security;
alter table public.injection_findings force row level security;
revoke all on public.injection_findings from public, anon, authenticated;
grant select, insert on public.injection_findings to authenticated;  -- never changed
create policy injection_findings_select on public.injection_findings
  for select to authenticated using (ward_id = any (app.ward_ids()));
create policy injection_findings_insert on public.injection_findings
  for insert to authenticated with check (ward_id = any (app.ward_ids()));
