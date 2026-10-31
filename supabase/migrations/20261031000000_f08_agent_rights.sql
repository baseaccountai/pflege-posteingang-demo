-- F08-AC7: what the agent may do, decided by the database (RLS), not by the prompt.
--
-- The agent acts with the nurse's identity (same sub, same wards) and actor_type = 'agent'
-- in the claims (ADR 0012). So far every policy only asked "which ward?" - the agent could
-- write wherever the nurse can. Now:
--   - it reads the record of its ward (residents, documents, chunks, medication, diagnoses,
--     follow-ups) like the nurse - and nothing of another ward;
--   - it writes only two things: a proposal (agent_proposals, status open) and a follow-up
--     for a proposal that a human has confirmed (at most one per proposal);
--   - originals, injection findings and the audit log stay closed to it.
--
-- Mechanism: RESTRICTIVE policies. Postgres combines them with AND with the existing
-- (permissive) ones, so every rule from F01-F07 stays and the agent rule comes on top -
-- nothing existing is rewritten.

-- 1. Proposals ---------------------------------------------------------------------------
create table public.agent_proposals (
  id uuid primary key default gen_random_uuid(),
  ward_id text not null,
  resident_id uuid not null,
  kind text not null default 'follow_up' check (kind in ('follow_up')),
  title text not null check (char_length(title) between 1 and 120),
  due_date date,
  created_for text not null default app.uid(),  -- the nurse the agent works for
  status text not null default 'open' check (status in ('open', 'confirmed', 'dismissed')),
  -- expired = still open and past expires_at (F08-AC5: valid for 15 minutes)
  expires_at timestamptz not null default now() + interval '15 minutes',
  created_at timestamptz not null default now(),
  decided_at timestamptz,
  unique (id, ward_id),  -- target of the follow-up's composite foreign key
  foreign key (resident_id, ward_id) references public.residents (id, ward_id)
);
create index agent_proposals_created_for on public.agent_proposals (created_for, created_at desc);

alter table public.agent_proposals enable row level security;
alter table public.agent_proposals force row level security;
revoke all on public.agent_proposals from public, anon, authenticated;
grant select on public.agent_proposals to authenticated;
-- Column by column: status, recipient and expiry come from the defaults, never from a caller.
grant insert (ward_id, resident_id, title, due_date) on public.agent_proposals to authenticated;
grant update (status) on public.agent_proposals to authenticated;  -- decided_at: trigger
-- no delete: a proposal is decided or expires

create policy agent_proposals_select on public.agent_proposals for select to authenticated
  using (ward_id = any (app.ward_ids()) and created_for = app.uid());
-- Only the agent proposes ...
create policy agent_proposals_insert on public.agent_proposals for insert to authenticated
  with check (app.actor_type() = 'agent' and ward_id = any (app.ward_ids())
              and created_for = app.uid() and status = 'open');
-- ... only the human it works for decides, once, before it expires (F08-AC6).
create policy agent_proposals_decide on public.agent_proposals for update to authenticated
  using (app.actor_type() = 'human' and created_for = app.uid()
         and ward_id = any (app.ward_ids()) and status = 'open' and expires_at > now())
  with check (status in ('confirmed', 'dismissed'));

-- When it was decided comes from the database clock, not from the request.
create function app.stamp_decision() returns trigger
language plpgsql as $$
begin
  if new.status is distinct from old.status then
    new.decided_at := now();
  end if;
  return new;
end $$;
revoke all on function app.stamp_decision() from public;
create trigger agent_proposals_stamp_decision
  before update on public.agent_proposals
  for each row execute function app.stamp_decision();

-- 2. The follow-up of a confirmed proposal -----------------------------------------------
alter table public.follow_ups add column proposal_id uuid unique;  -- at most one per proposal
alter table public.follow_ups add foreign key (proposal_id, ward_id)
  references public.agent_proposals (id, ward_id);

-- Humans write follow-ups as before (never for a proposal); the agent only for a proposal
-- its nurse confirmed within the last two minutes, with exactly the proposed content.
create policy follow_ups_insert_agent on public.follow_ups as restrictive
  for insert to authenticated
  with check (
    (app.actor_type() = 'human' and proposal_id is null)
    or (app.actor_type() = 'agent' and exists (
      select 1 from public.agent_proposals p
      where p.id = follow_ups.proposal_id
        and p.ward_id = follow_ups.ward_id
        and p.resident_id = follow_ups.resident_id
        and p.title = follow_ups.title
        and p.due_date is not distinct from follow_ups.due_date
        and p.status = 'confirmed'
        and p.created_for = app.uid()
        and p.decided_at > now() - interval '2 minutes'))
  );

-- 3. Every other write: humans only ------------------------------------------------------
do $$
declare
  w record;
begin
  for w in select * from (values
      ('documents', 'insert'), ('documents', 'update'),
      ('document_files', 'insert'),
      ('chunks', 'insert'), ('chunks', 'delete'),
      ('injection_findings', 'insert'),
      ('medications', 'insert'), ('medications', 'update'),
      ('medication_events', 'insert'),
      ('diagnoses', 'insert'),
      ('follow_ups', 'update')) as t(tbl, cmd)
  loop
    execute format(
      'create policy %I on public.%I as restrictive for %s to authenticated %s',
      w.tbl || '_' || w.cmd || '_humans', w.tbl, w.cmd,
      case w.cmd
        when 'insert' then 'with check (app.actor_type() = ''human'')'
        when 'update' then 'using (app.actor_type() = ''human'') with check (app.actor_type() = ''human'')'
        else 'using (app.actor_type() = ''human'')'
      end);
  end loop;
end $$;

-- 4. Closed to the agent even for reading ------------------------------------------------
-- Originals (it works with the OCR text and chunks), findings (they quote the attack) and
-- the audit log (for the human PDL, not for the PDL's agent).
create policy document_files_select_humans on public.document_files as restrictive
  for select to authenticated using (app.actor_type() = 'human');
create policy injection_findings_select_humans on public.injection_findings as restrictive
  for select to authenticated using (app.actor_type() = 'human');
create policy audit_events_select_humans on public.audit_events as restrictive
  for select to authenticated using (app.actor_type() = 'human');

-- 5. F12-AC4: proposal, confirmation and dismissal are logged by trigger -----------------
create function app.audit_proposal() returns trigger
language plpgsql security definer set search_path = app, pg_temp as $$
begin
  perform app.write_audit_event(new.ward_id,
    case when tg_op = 'INSERT' then 'agent_proposal' else 'proposal_' || new.status end,
    'ok', null, null, new.resident_id, jsonb_build_object('proposal_id', new.id));
  return null;
end $$;

grant create on schema app to audit_owner;
alter function app.audit_proposal() owner to audit_owner;
revoke create on schema app from audit_owner;
revoke all on function app.audit_proposal() from public, anon, authenticated;

create trigger agent_proposals_audit_insert
  after insert on public.agent_proposals
  for each row execute function app.audit_proposal();
create trigger agent_proposals_audit_decision
  after update of status on public.agent_proposals
  for each row when (new.status is distinct from old.status)
  execute function app.audit_proposal();
