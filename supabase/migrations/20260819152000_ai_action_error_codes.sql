begin;

alter table public.ai_action_logs
  add column if not exists error_code text;

create index if not exists ai_action_logs_error_code_created_idx
  on public.ai_action_logs (error_code, created_at desc)
  where error_code is not null;

commit;
