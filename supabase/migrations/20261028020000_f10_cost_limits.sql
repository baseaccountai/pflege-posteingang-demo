-- F10-AC11: daily limits so that a day with every quota used up costs at most 0.50 EUR.
-- Calculation: apps/api/app/costs.py (conservative prices, ADR 0003), checked by
-- apps/api/tests/rls/test_daily_cost.py against this table.
--   50 OCR pages x 0.004          = 0.200
--   100 LLM calls x 0.00206 (max) = 0.206
--   500 chunks x 800 tokens x 1e-7 = 0.040   -> 0.446 EUR
update public.quota_limits set max_count = 50 where kind = 'ocr_page';
update public.quota_limits set max_count = 100 where kind = 'llm_call';
