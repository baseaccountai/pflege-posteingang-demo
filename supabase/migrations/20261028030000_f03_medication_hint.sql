-- Decision 2A (Codex review Phase 3 #5): the hint of a medication ("bei Bedarf", "zur
-- Nacht") is approved and kept like strength and dosage; before, it was lost on approval.
alter table public.medications
  add column hint text check (char_length(hint) <= 500);

-- A changed hint is a change of the medication (F03-AC7), written by the approval.
grant update (hint) on public.medications to authenticated;
