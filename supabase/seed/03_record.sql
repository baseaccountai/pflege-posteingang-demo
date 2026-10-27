-- Seed (F10-AC1): the record behind the seed documents (02_documents.sql).
-- Every entry names its source document and who confirmed it, like an approval writes it
-- (F03). Times are relative to the moment the seed runs, so the markers "neu"/"geändert"
-- (7 days) and the overdue follow-ups look the same after every nightly reset.
--
-- Seed users: 'seed:pflege-wb1' / 'seed:pflege-wb2' stand for the demo nurses; one entry
-- was created by the agent ('agent:posteingang') and confirmed by a nurse (F04-AC6).

-- Medications: current state; the history is in medication_events below.
insert into public.medications (id, ward_id, resident_id, name, strength, dosage, status, created_by, created_at) values
  -- Hr. Muster-Bauer: older than samples/medikationsplan_muster-bauer.pdf (F03-AC7 demo)
  ('a1ed0000-0000-0000-0000-000000000001', 'wb1', '11111111-1111-1111-1111-111111111111', 'Ramipril', '5 mg', '{"morgens":"1","mittags":"0","abends":"0","nachts":"0"}', 'active', 'seed:pflege-wb1', now() - interval '70 days'),
  ('a1ed0000-0000-0000-0000-000000000002', 'wb1', '11111111-1111-1111-1111-111111111111', 'Metformin', '500 mg', '{"morgens":"1","mittags":"0","abends":"1","nachts":"0"}', 'active', 'seed:pflege-wb1', now() - interval '70 days'),
  ('a1ed0000-0000-0000-0000-000000000003', 'wb1', '11111111-1111-1111-1111-111111111111', 'Simvastatin', '20 mg', '{"morgens":"0","mittags":"0","abends":"1","nachts":"0"}', 'active', 'seed:pflege-wb1', now() - interval '70 days'),
  -- Fr. Beispiel: Ibuprofen stopped 3 days ago, Metamizol new
  ('a1ed0000-0000-0000-0000-000000000004', 'wb1', '33333333-3333-3333-3333-333333333333', 'Ibuprofen', '400 mg', '{"morgens":"1","mittags":"0","abends":"1","nachts":"0"}', 'discontinued', 'seed:pflege-wb1', now() - interval '54 days'),
  ('a1ed0000-0000-0000-0000-000000000005', 'wb1', '33333333-3333-3333-3333-333333333333', 'Colecalciferol', '1000 I.E.', '{"morgens":"1","mittags":"0","abends":"0","nachts":"0"}', 'active', 'seed:pflege-wb1', now() - interval '54 days'),
  ('a1ed0000-0000-0000-0000-000000000006', 'wb1', '33333333-3333-3333-3333-333333333333', 'Metamizol', '500 mg', '{"morgens":"1","mittags":"1","abends":"1","nachts":"0"}', 'active', 'seed:pflege-wb1', now() - interval '3 days'),
  -- Hr. Probe: Bisoprolol raised 5 days ago
  ('a1ed0000-0000-0000-0000-000000000007', 'wb1', '44444444-4444-4444-4444-444444444444', 'Apixaban', '5 mg', '{"morgens":"1","mittags":"0","abends":"1","nachts":"0"}', 'active', 'seed:pflege-wb1', now() - interval '66 days'),
  ('a1ed0000-0000-0000-0000-000000000008', 'wb1', '44444444-4444-4444-4444-444444444444', 'Bisoprolol', '2,5 mg', '{"morgens":"1","mittags":"0","abends":"0","nachts":"0"}', 'active', 'seed:pflege-wb1', now() - interval '66 days'),
  -- Fr. Testfeld: older than samples/ueberleitungsbogen_testfeld.pdf (Pantoprazol 40 -> 20 mg)
  ('a1ed0000-0000-0000-0000-000000000009', 'wb2', '22222222-2222-2222-2222-222222222222', 'Bisoprolol', '2,5 mg', '{"morgens":"1","mittags":"0","abends":"0","nachts":"0"}', 'active', 'seed:pflege-wb2', now() - interval '55 days'),
  ('a1ed0000-0000-0000-0000-000000000010', 'wb2', '22222222-2222-2222-2222-222222222222', 'Pantoprazol', '40 mg', '{"morgens":"1","mittags":"0","abends":"0","nachts":"0"}', 'active', 'seed:pflege-wb2', now() - interval '55 days'),
  -- Hr. Exempel: new 6 days ago
  ('a1ed0000-0000-0000-0000-000000000011', 'wb2', '55555555-5555-5555-5555-555555555555', 'Levodopa/Benserazid', '100/25 mg', '{"morgens":"1","mittags":"1","abends":"1","nachts":"0"}', 'active', 'seed:pflege-wb2', now() - interval '6 days'),
  -- Fr. Vorlage
  ('a1ed0000-0000-0000-0000-000000000012', 'wb2', '66666666-6666-6666-6666-666666666666', 'Levothyroxin', '50 µg', '{"morgens":"1","mittags":"0","abends":"0","nachts":"0"}', 'active', 'seed:pflege-wb2', now() - interval '50 days'),
  ('a1ed0000-0000-0000-0000-000000000013', 'wb2', '66666666-6666-6666-6666-666666666666', 'Mirtazapin', '15 mg', '{"morgens":"0","mittags":"0","abends":"0","nachts":"1"}', 'active', 'seed:pflege-wb2', now() - interval '50 days');

-- Medication history: one event per change, each from its document.
insert into public.medication_events (ward_id, medication_id, kind, document_id, before, after, actor_type, created_by, confirmed_by, confirmed_by_name, created_at) values
  ('wb1', 'a1ed0000-0000-0000-0000-000000000001', 'new', '5eed0000-0000-0000-0000-000000000001', null, '{"name":"Ramipril","strength":"5 mg","dosage":{"morgens":"1","mittags":"0","abends":"0","nachts":"0"}}', 'human', 'seed:pflege-wb1', 'seed:pflege-wb1', 'Pflegekraft WB1', now() - interval '70 days'),
  ('wb1', 'a1ed0000-0000-0000-0000-000000000002', 'new', '5eed0000-0000-0000-0000-000000000001', null, '{"name":"Metformin","strength":"500 mg","dosage":{"morgens":"1","mittags":"0","abends":"1","nachts":"0"}}', 'human', 'seed:pflege-wb1', 'seed:pflege-wb1', 'Pflegekraft WB1', now() - interval '70 days'),
  ('wb1', 'a1ed0000-0000-0000-0000-000000000003', 'new', '5eed0000-0000-0000-0000-000000000001', null, '{"name":"Simvastatin","strength":"20 mg","dosage":{"morgens":"0","mittags":"0","abends":"1","nachts":"0"}}', 'human', 'seed:pflege-wb1', 'seed:pflege-wb1', 'Pflegekraft WB1', now() - interval '70 days'),
  ('wb1', 'a1ed0000-0000-0000-0000-000000000004', 'new', '5eed0000-0000-0000-0000-000000000002', null, '{"name":"Ibuprofen","strength":"400 mg","dosage":{"morgens":"1","mittags":"0","abends":"1","nachts":"0"}}', 'human', 'seed:pflege-wb1', 'seed:pflege-wb1', 'Pflegekraft WB1', now() - interval '54 days'),
  ('wb1', 'a1ed0000-0000-0000-0000-000000000004', 'discontinued', '5eed0000-0000-0000-0000-000000000003', '{"name":"Ibuprofen","strength":"400 mg","dosage":{"morgens":"1","mittags":"0","abends":"1","nachts":"0"}}', null, 'human', 'seed:pflege-wb1', 'seed:pflege-wb1', 'Pflegekraft WB1', now() - interval '3 days'),
  ('wb1', 'a1ed0000-0000-0000-0000-000000000005', 'new', '5eed0000-0000-0000-0000-000000000002', null, '{"name":"Colecalciferol","strength":"1000 I.E.","dosage":{"morgens":"1","mittags":"0","abends":"0","nachts":"0"}}', 'human', 'seed:pflege-wb1', 'seed:pflege-wb1', 'Pflegekraft WB1', now() - interval '54 days'),
  ('wb1', 'a1ed0000-0000-0000-0000-000000000006', 'new', '5eed0000-0000-0000-0000-000000000003', null, '{"name":"Metamizol","strength":"500 mg","dosage":{"morgens":"1","mittags":"1","abends":"1","nachts":"0"}}', 'human', 'seed:pflege-wb1', 'seed:pflege-wb1', 'Pflegekraft WB1', now() - interval '3 days'),
  ('wb1', 'a1ed0000-0000-0000-0000-000000000007', 'new', '5eed0000-0000-0000-0000-000000000004', null, '{"name":"Apixaban","strength":"5 mg","dosage":{"morgens":"1","mittags":"0","abends":"1","nachts":"0"}}', 'human', 'seed:pflege-wb1', 'seed:pflege-wb1', 'Pflegekraft WB1', now() - interval '66 days'),
  ('wb1', 'a1ed0000-0000-0000-0000-000000000008', 'new', '5eed0000-0000-0000-0000-000000000004', null, '{"name":"Bisoprolol","strength":"1,25 mg","dosage":{"morgens":"1","mittags":"0","abends":"0","nachts":"0"}}', 'human', 'seed:pflege-wb1', 'seed:pflege-wb1', 'Pflegekraft WB1', now() - interval '66 days'),
  ('wb1', 'a1ed0000-0000-0000-0000-000000000008', 'changed', '5eed0000-0000-0000-0000-000000000005', '{"name":"Bisoprolol","strength":"1,25 mg","dosage":{"morgens":"1","mittags":"0","abends":"0","nachts":"0"}}', '{"name":"Bisoprolol","strength":"2,5 mg","dosage":{"morgens":"1","mittags":"0","abends":"0","nachts":"0"}}', 'human', 'seed:pflege-wb1', 'seed:pflege-wb1', 'Pflegekraft WB1', now() - interval '5 days'),
  ('wb2', 'a1ed0000-0000-0000-0000-000000000009', 'new', '5eed0000-0000-0000-0000-000000000006', null, '{"name":"Bisoprolol","strength":"2,5 mg","dosage":{"morgens":"1","mittags":"0","abends":"0","nachts":"0"}}', 'human', 'seed:pflege-wb2', 'seed:pflege-wb2', 'Pflegekraft WB2', now() - interval '55 days'),
  ('wb2', 'a1ed0000-0000-0000-0000-000000000010', 'new', '5eed0000-0000-0000-0000-000000000006', null, '{"name":"Pantoprazol","strength":"40 mg","dosage":{"morgens":"1","mittags":"0","abends":"0","nachts":"0"}}', 'human', 'seed:pflege-wb2', 'seed:pflege-wb2', 'Pflegekraft WB2', now() - interval '55 days'),
  ('wb2', 'a1ed0000-0000-0000-0000-000000000011', 'new', '5eed0000-0000-0000-0000-000000000007', null, '{"name":"Levodopa/Benserazid","strength":"100/25 mg","dosage":{"morgens":"1","mittags":"1","abends":"1","nachts":"0"}}', 'human', 'seed:pflege-wb2', 'seed:pflege-wb2', 'Pflegekraft WB2', now() - interval '6 days'),
  ('wb2', 'a1ed0000-0000-0000-0000-000000000012', 'new', '5eed0000-0000-0000-0000-000000000008', null, '{"name":"Levothyroxin","strength":"50 µg","dosage":{"morgens":"1","mittags":"0","abends":"0","nachts":"0"}}', 'human', 'seed:pflege-wb2', 'seed:pflege-wb2', 'Pflegekraft WB2', now() - interval '50 days'),
  ('wb2', 'a1ed0000-0000-0000-0000-000000000013', 'new', '5eed0000-0000-0000-0000-000000000008', null, '{"name":"Mirtazapin","strength":"15 mg","dosage":{"morgens":"0","mittags":"0","abends":"0","nachts":"1"}}', 'human', 'seed:pflege-wb2', 'seed:pflege-wb2', 'Pflegekraft WB2', now() - interval '50 days');

insert into public.diagnoses (ward_id, resident_id, text, source_document_id, actor_type, created_by, confirmed_by, confirmed_by_name, created_at) values
  ('wb1', '11111111-1111-1111-1111-111111111111', 'Diabetes mellitus Typ 2', '5eed0000-0000-0000-0000-000000000001', 'human', 'seed:pflege-wb1', 'seed:pflege-wb1', 'Pflegekraft WB1', now() - interval '70 days'),
  ('wb1', '11111111-1111-1111-1111-111111111111', 'Arterielle Hypertonie', '5eed0000-0000-0000-0000-000000000001', 'human', 'seed:pflege-wb1', 'seed:pflege-wb1', 'Pflegekraft WB1', now() - interval '70 days'),
  ('wb1', '33333333-3333-3333-3333-333333333333', 'Gonarthrose beidseits', '5eed0000-0000-0000-0000-000000000002', 'human', 'seed:pflege-wb1', 'seed:pflege-wb1', 'Pflegekraft WB1', now() - interval '54 days'),
  ('wb1', '33333333-3333-3333-3333-333333333333', 'Osteoporose', '5eed0000-0000-0000-0000-000000000002', 'human', 'seed:pflege-wb1', 'seed:pflege-wb1', 'Pflegekraft WB1', now() - interval '54 days'),
  ('wb1', '44444444-4444-4444-4444-444444444444', 'Vorhofflimmern', '5eed0000-0000-0000-0000-000000000004', 'human', 'seed:pflege-wb1', 'seed:pflege-wb1', 'Pflegekraft WB1', now() - interval '66 days'),
  ('wb1', '44444444-4444-4444-4444-444444444444', 'COPD GOLD 2', '5eed0000-0000-0000-0000-000000000004', 'human', 'seed:pflege-wb1', 'seed:pflege-wb1', 'Pflegekraft WB1', now() - interval '66 days'),
  ('wb2', '22222222-2222-2222-2222-222222222222', 'Diabetes mellitus Typ 2, diätetisch eingestellt', '5eed0000-0000-0000-0000-000000000006', 'human', 'seed:pflege-wb2', 'seed:pflege-wb2', 'Pflegekraft WB2', now() - interval '55 days'),
  ('wb2', '22222222-2222-2222-2222-222222222222', 'Refluxkrankheit', '5eed0000-0000-0000-0000-000000000006', 'human', 'seed:pflege-wb2', 'seed:pflege-wb2', 'Pflegekraft WB2', now() - interval '55 days'),
  ('wb2', '55555555-5555-5555-5555-555555555555', 'Morbus Parkinson', '5eed0000-0000-0000-0000-000000000007', 'human', 'seed:pflege-wb2', 'seed:pflege-wb2', 'Pflegekraft WB2', now() - interval '6 days'),
  ('wb2', '55555555-5555-5555-5555-555555555555', 'Sturzneigung', '5eed0000-0000-0000-0000-000000000007', 'human', 'seed:pflege-wb2', 'seed:pflege-wb2', 'Pflegekraft WB2', now() - interval '6 days'),
  ('wb2', '66666666-6666-6666-6666-666666666666', 'Hypothyreose', '5eed0000-0000-0000-0000-000000000008', 'human', 'seed:pflege-wb2', 'seed:pflege-wb2', 'Pflegekraft WB2', now() - interval '50 days'),
  ('wb2', '66666666-6666-6666-6666-666666666666', 'Depressive Episode', '5eed0000-0000-0000-0000-000000000008', 'human', 'seed:pflege-wb2', 'seed:pflege-wb2', 'Pflegekraft WB2', now() - interval '50 days');

-- Follow-ups: open, overdue (due today or earlier, F04) and done.
insert into public.follow_ups (ward_id, resident_id, title, due_date, status, done_by, done_by_name, done_at, source_document_id, actor_type, created_by, confirmed_by, confirmed_by_name, created_at) values
  ('wb1', '11111111-1111-1111-1111-111111111111', 'HbA1c-Kontrolle beim Hausarzt', current_date + 12, 'open', null, null, null, '5eed0000-0000-0000-0000-000000000001', 'human', 'seed:pflege-wb1', 'seed:pflege-wb1', 'Pflegekraft WB1', now() - interval '70 days'),
  ('wb1', '33333333-3333-3333-3333-333333333333', 'Schmerzen mit der NRS-Skala erfassen', current_date - 2, 'open', null, null, null, '5eed0000-0000-0000-0000-000000000002', 'human', 'seed:pflege-wb1', 'seed:pflege-wb1', 'Pflegekraft WB1', now() - interval '54 days'),
  -- The agent's entry (F04-AC6): proposed by the agent, confirmed by the nurse.
  ('wb1', '33333333-3333-3333-3333-333333333333', 'Termin Orthopädie vereinbaren', current_date + 7, 'open', null, null, null, '5eed0000-0000-0000-0000-000000000003', 'agent', 'agent:posteingang', 'seed:pflege-wb1', 'Pflegekraft WB1', now() - interval '3 days'),
  ('wb1', '44444444-4444-4444-4444-444444444444', 'Kardiologische Kontrolle vereinbaren', current_date - 25, 'done', 'seed:pflege-wb1', 'Pflegekraft WB1', now() - interval '20 days', '5eed0000-0000-0000-0000-000000000004', 'human', 'seed:pflege-wb1', 'seed:pflege-wb1', 'Pflegekraft WB1', now() - interval '66 days'),
  ('wb2', '22222222-2222-2222-2222-222222222222', 'Blutzuckertagesprofil erstellen', current_date + 3, 'open', null, null, null, '5eed0000-0000-0000-0000-000000000006', 'human', 'seed:pflege-wb2', 'seed:pflege-wb2', 'Pflegekraft WB2', now() - interval '55 days'),
  ('wb2', '55555555-5555-5555-5555-555555555555', 'Neurologische Kontrolle', current_date + 21, 'open', null, null, null, '5eed0000-0000-0000-0000-000000000007', 'human', 'seed:pflege-wb2', 'seed:pflege-wb2', 'Pflegekraft WB2', now() - interval '6 days'),
  ('wb2', '66666666-6666-6666-6666-666666666666', 'TSH-Kontrolle beim Hausarzt', current_date - 4, 'done', 'seed:pflege-wb2', 'Pflegekraft WB2', now() - interval '3 days', '5eed0000-0000-0000-0000-000000000008', 'human', 'seed:pflege-wb2', 'seed:pflege-wb2', 'Pflegekraft WB2', now() - interval '50 days'),
  ('wb2', '66666666-6666-6666-6666-666666666666', 'Gewicht wöchentlich kontrollieren', current_date - 1, 'open', null, null, null, '5eed0000-0000-0000-0000-000000000008', 'human', 'seed:pflege-wb2', 'seed:pflege-wb2', 'Pflegekraft WB2', now() - interval '50 days');
