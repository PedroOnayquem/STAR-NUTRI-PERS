-- Add covering indexes for new AI agent foreign keys flagged by the database linter.

create index if not exists ai_action_logs_nutritionist_created_idx
  on public.ai_action_logs (nutritionist_id, created_at desc);

create index if not exists appointments_created_by_idx
  on public.appointments (created_by);
