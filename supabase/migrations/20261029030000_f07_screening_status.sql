-- F07-AC1: the injection check is a step of its own between OCR and field suggestion.
-- (A new enum value cannot be used in the migration that adds it - hence its own file.)
alter type public.document_status add value 'screening' after 'processing';
