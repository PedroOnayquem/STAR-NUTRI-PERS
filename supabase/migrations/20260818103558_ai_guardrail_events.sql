begin;

-- Auditable security decisions made around the Star Nutri AI boundary.
-- Message bodies are intentionally not stored. content_hash supports correlation
-- while redacted_excerpt is short and stripped of common direct identifiers.

create table if not exists public.ai_guardrail_events (
  id uuid primary key default gen_random_uuid(),
  actor_user_id uuid not null references public.profiles(id) on delete restrict,
  actor_role public.user_role not null,
  patient_id uuid references public.patients(id) on delete set null,
  nutritionist_id uuid references public.nutritionists(id) on delete set null,
  chat_scope text not null check (chat_scope in ('nutritionist', 'patient')),
  chat_id uuid,
  message_id uuid,
  stage text not null check (stage in ('context', 'input', 'output', 'provider')),
  category text not null,
  action text not null check (action in ('allowed', 'blocked', 'safe_completed', 'redacted', 'failed')),
  severity text not null check (severity in ('info', 'warning', 'high', 'critical')),
  rule_ids text[] not null default '{}'::text[],
  content_hash text check (content_hash is null or length(content_hash) = 64),
  redacted_excerpt text check (redacted_excerpt is null or char_length(redacted_excerpt) <= 180),
  reason text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists ai_guardrail_events_actor_created_idx
  on public.ai_guardrail_events (actor_user_id, created_at desc);
create index if not exists ai_guardrail_events_patient_created_idx
  on public.ai_guardrail_events (patient_id, created_at desc)
  where patient_id is not null;
create index if not exists ai_guardrail_events_nutritionist_created_idx
  on public.ai_guardrail_events (nutritionist_id, created_at desc)
  where nutritionist_id is not null;
create index if not exists ai_guardrail_events_action_category_created_idx
  on public.ai_guardrail_events (action, category, created_at desc);
create index if not exists ai_guardrail_events_chat_created_idx
  on public.ai_guardrail_events (chat_scope, chat_id, created_at desc)
  where chat_id is not null;

alter table public.ai_guardrail_events enable row level security;

drop policy if exists "Admins view AI guardrail events" on public.ai_guardrail_events;
create policy "Admins view AI guardrail events"
on public.ai_guardrail_events
for select
to authenticated
using ((select public.is_admin()));

-- The backend writes with service_role. Authenticated clients can only read
-- through the admin RLS policy; they cannot insert, update, or delete events.
grant select on public.ai_guardrail_events to authenticated;
grant select, insert on public.ai_guardrail_events to service_role;
revoke insert, update, delete on public.ai_guardrail_events from anon, authenticated;

notify pgrst, 'reload schema';

commit;
