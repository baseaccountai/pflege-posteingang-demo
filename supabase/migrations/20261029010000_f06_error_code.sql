-- F06-AC10: a document whose text could not be pseudonymised safely is not sent to a model;
-- it fails with its own code (retry possible, like the other failures of the pipeline).
alter table public.documents drop constraint documents_error_code_check;
alter table public.documents add constraint documents_error_code_check check (error_code in (
  'ocr_unavailable', 'llm_unavailable', 'quota_exceeded', 'timeout',
  'unreadable_text', 'not_care_document', 'pseudonymization_failed'));
