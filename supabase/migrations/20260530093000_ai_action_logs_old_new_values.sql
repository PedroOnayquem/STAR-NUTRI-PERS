-- Store explicit before/after scalar values for AI actions that update records.

alter table public.ai_action_logs
  add column if not exists old_value jsonb,
  add column if not exists new_value jsonb;

notify pgrst, 'reload schema';
