-- Seed (F10-AC1): two wards with three invented residents each.
-- Loaded by `supabase db reset` (local) and by the nightly reset (F10). The resident ids
-- are fixed: supabase/seed/02_documents.sql (generated) and 03_record.sql refer to them.
insert into public.wards (id, name) values
  ('wb1', 'WB 1'),
  ('wb2', 'WB 2');

insert into public.residents (id, ward_id, display_name, birth_date, room) values
  ('11111111-1111-1111-1111-111111111111', 'wb1', 'Hr. Muster-Bauer', '1941-04-03', '104'),
  ('33333333-3333-3333-3333-333333333333', 'wb1', 'Fr. Beispiel', '1936-06-17', '107'),
  ('44444444-4444-4444-4444-444444444444', 'wb1', 'Hr. Probe', '1939-02-28', '112'),
  ('22222222-2222-2222-2222-222222222222', 'wb2', 'Fr. Testfeld', '1938-09-12', '203'),
  ('55555555-5555-5555-5555-555555555555', 'wb2', 'Hr. Exempel', '1943-11-09', '208'),
  ('66666666-6666-6666-6666-666666666666', 'wb2', 'Fr. Vorlage', '1945-01-22', '211');
