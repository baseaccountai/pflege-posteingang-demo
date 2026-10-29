-- Codex review phase 6: the application role may only take the steps of the state machine
-- (F02 design + F07); a programming error cannot jump over the injection check, e.g.
-- screening -> approved. Admin work (reset, migrations, test setup) is not affected.
create function app.allowed_document_transition() returns trigger
language plpgsql as $$
begin
  if current_user <> 'authenticated' or new.status = old.status then
    return new;
  end if;
  if (old.status, new.status) not in (
    ('uploaded', 'processing'), ('uploaded', 'failed'),
    ('processing', 'screening'), ('processing', 'unreadable'), ('processing', 'failed'),
    ('screening', 'extracting'), ('screening', 'failed'),
    ('extracting', 'ready_for_review'), ('extracting', 'failed'),
    ('failed', 'processing'), ('failed', 'screening'),
    ('ready_for_review', 'approved'), ('ready_for_review', 'rejected')
  ) then
    raise exception 'document cannot go from % to %', old.status, new.status
      using errcode = 'check_violation';
  end if;
  return new;
end $$;
revoke all on function app.allowed_document_transition() from public;

create trigger documents_allowed_transition
  before update of status on public.documents
  for each row execute function app.allowed_document_transition();
