-- F04-AC8: marking a follow-up done. Like "freigegeben von" (F03), "erledigt von" comes
-- from the claims, never from the request; a done follow-up stays done (no reopening,
-- no rewriting who did it).

drop policy follow_ups_update on public.follow_ups;

create policy follow_ups_update on public.follow_ups for update to authenticated
  using (ward_id = any (app.ward_ids()) and status = 'open')
  with check (ward_id = any (app.ward_ids()) and status = 'done'
              and done_by = app.uid() and done_by_name = app.display_name()
              and done_at is not null);
