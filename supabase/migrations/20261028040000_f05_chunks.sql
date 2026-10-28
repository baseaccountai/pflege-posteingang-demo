-- F05: chunks of approved documents with their embedding, for questions with sources.
-- Derived data: rebuilt from the document at any time, so - unlike the record - a nurse
-- may delete them (re-indexing replaces all chunks of a document, F05-AC1).
create extension if not exists vector with schema extensions;

create table public.chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null,
  ward_id text not null,
  resident_id uuid not null,
  doc_type public.doc_type,
  document_date date,
  page int not null check (page >= 1),
  heading text,
  content text not null,
  embedding extensions.vector(1024) not null,  -- mistral-embed; other models: same size
  embedding_model text not null,               -- vectors of different models are never compared
  created_at timestamptz not null default now(),
  -- Composite keys: a chunk cannot point into another ward. The nightly reset empties the
  -- documents with CASCADE, so the chunks go with them.
  foreign key (document_id, ward_id) references public.documents (id, ward_id) on delete cascade,
  foreign key (resident_id, ward_id) references public.residents (id, ward_id)
);
-- Exact search on purpose (no approximate index): a few hundred chunks are fast enough, and
-- an approximate index can lose hits once the ward/resident filter is applied (design F05).
create index chunks_document on public.chunks (document_id);
create index chunks_resident_model on public.chunks (resident_id, embedding_model);

alter table public.chunks enable row level security;
alter table public.chunks force row level security;
revoke all on public.chunks from public, anon, authenticated;
grant select, insert, delete on public.chunks to authenticated;  -- no update: replace instead

create policy chunks_select on public.chunks for select to authenticated
  using (ward_id = any (app.ward_ids()));
create policy chunks_delete on public.chunks for delete to authenticated
  using (ward_id = any (app.ward_ids()));
-- Only for an approved document of the own ward, and the metadata must be the document's:
-- a source never shows another resident, type or date than its document.
create policy chunks_insert on public.chunks for insert to authenticated
  with check (
    ward_id = any (app.ward_ids())
    and exists (
      select 1 from public.documents d
      where d.id = chunks.document_id
        and d.ward_id = chunks.ward_id
        and d.status = 'approved'
        and d.resident_id = chunks.resident_id
        and d.doc_type is not distinct from chunks.doc_type
        and d.document_date is not distinct from chunks.document_date
    )
  );

-- The search (F05-AC4, AC5). SECURITY INVOKER: it runs with the caller's rights, so RLS
-- decides which chunks exist - the function itself has no ward filter to forget.
create function app.match_chunks(
  query extensions.vector(1024), p_model text, p_resident uuid, p_limit int, p_min_sim float
)
returns table (
  id uuid, document_id uuid, resident_id uuid, doc_type public.doc_type, document_date date,
  page int, heading text, content text, similarity float
)
language sql stable security invoker set search_path = public, extensions, pg_temp as $$
  select c.id, c.document_id, c.resident_id, c.doc_type, c.document_date, c.page, c.heading,
         c.content, 1 - (c.embedding <=> query) as similarity
  from public.chunks c
  where c.embedding_model = p_model
    and (p_resident is null or c.resident_id = p_resident)
    and 1 - (c.embedding <=> query) >= p_min_sim
  order by c.embedding <=> query, c.id
  limit least(greatest(p_limit, 0), 6)  -- never more than 6 chunks to the LLM (AC4)
$$;

revoke execute on function app.match_chunks(extensions.vector, text, uuid, int, float)
  from public, anon;
grant execute on function app.match_chunks(extensions.vector, text, uuid, int, float)
  to authenticated;
