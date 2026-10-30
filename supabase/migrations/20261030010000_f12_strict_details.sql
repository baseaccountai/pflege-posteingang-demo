-- Codex review F12: app.log_event checked only the keys of `details`, so an allowed key
-- could still carry a resident name, a sentence or a token (F12-AC3). Now every key has
-- its own form: rule ids, tools and error codes are lower-case identifiers, the layer is
-- one of three, a proposal id is a UUID, pages are numbers.
--
-- The model name stays free text up to 100 characters: it comes from the backend's
-- configuration (MISTRAL_CHAT_MODEL, ...), never from a user. A backend that wanted to
-- write contents could do so anyway; that trust is named in the threat model.
--
-- `create or replace` keeps the owner (audit_owner) and the grants of the function.

create or replace function app.log_event(
  p_action text, p_outcome text, p_model text,
  p_document uuid, p_resident uuid, p_details jsonb
) returns void
language plpgsql security definer set search_path = app, pg_temp as $$
declare
  v_ward text;
  v_key text;
  v_value jsonb;
begin
  if p_action is null or p_action not in ('ocr', 'screening', 'extraction', 'question',
      'agent_task', 'agent_tool', 'blocked', 'quota_exhausted') then
    raise exception 'action not allowed: %', p_action using errcode = 'invalid_parameter_value';
  end if;
  if p_outcome is null or p_outcome not in ('ok', 'blocked', 'error') then
    raise exception 'unknown outcome' using errcode = 'invalid_parameter_value';
  end if;
  if p_model is not null and char_length(p_model) > 100 then
    raise exception 'model name too long' using errcode = 'invalid_parameter_value';
  end if;
  for v_key, v_value in select * from jsonb_each(coalesce(p_details, '{}')) loop
    if v_key not in ('rule_id', 'layer', 'tool', 'error_code', 'proposal_id', 'pages') then
      raise exception 'detail not allowed: %', v_key using errcode = 'invalid_parameter_value';
    end if;
    -- Each key its own form: no capitals, no spaces, so neither a name nor a sentence
    -- nor a (base64) token fits in.
    -- (The CASE is in parentheses: PL/pgSQL ends an IF condition at the first THEN.)
    if not (case v_key
      when 'layer' then jsonb_typeof(v_value) = 'string'
        and (v_value #>> '{}') in ('hidden_text', 'pattern', 'classifier')
      when 'proposal_id' then jsonb_typeof(v_value) = 'string' and (v_value #>> '{}')
        ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
      when 'pages' then jsonb_typeof(v_value) = 'array' and jsonb_array_length(v_value) <= 100
        and not exists (select from jsonb_array_elements(v_value) e where jsonb_typeof(e) <> 'number')
      else jsonb_typeof(v_value) = 'string' and (v_value #>> '{}') ~ '^[a-z0-9][a-z0-9_.:-]{0,63}$'
    end) then
      raise exception 'detail % is not an identifier of its kind', v_key
        using errcode = 'invalid_parameter_value';
    end if;
  end loop;

  -- The ward: that of the document or resident, which must be one of the caller's wards;
  -- otherwise the caller's only ward, or none if there are several.
  if p_document is not null then
    select ward_id into v_ward from public.documents where id = p_document;
  elsif p_resident is not null then
    select ward_id into v_ward from public.residents where id = p_resident;
  elsif cardinality(app.ward_ids()) = 1 then
    v_ward := (app.ward_ids())[1];
  end if;
  if (p_document is not null or p_resident is not null)
     and (v_ward is null or not v_ward = any (app.ward_ids())) then
    raise exception 'not in the caller''s wards' using errcode = 'insufficient_privilege';
  end if;
  if p_document is not null and p_resident is not null and not exists (
      select from public.residents where id = p_resident and ward_id = v_ward) then
    raise exception 'not in the caller''s wards' using errcode = 'insufficient_privilege';
  end if;
  if app.uid() is null then
    raise exception 'no caller' using errcode = 'insufficient_privilege';
  end if;

  perform app.write_audit_event(v_ward, p_action, p_outcome, p_model, p_document,
    p_resident, p_details);
end $$;
