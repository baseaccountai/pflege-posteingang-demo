-- F07-AC4, AC7, AC9: the injection checker has daily quotas of its own, part of F10's daily
-- maximum of 0.50 EUR (app/costs.py, tests/rls/test_daily_cost.py):
--   guard_document: one call checks at most 20 000 characters of a document  -> 20 per day
--   guard_question: one call checks a question or agent task (<= 500 chars)   -> 100 per day
insert into public.quota_limits (kind, scope, max_count) values
  ('guard_document', 'global', 20),
  ('guard_question', 'global', 100);
