-- Operational AI agent support: auditable tool execution and appointments.

create table if not exists public.ai_action_logs (
  id uuid primary key default gen_random_uuid(),
  actor_user_id uuid not null references public.profiles(id) on delete restrict,
  actor_role public.user_role not null,
  patient_id uuid references public.patients(id) on delete set null,
  nutritionist_id uuid references public.nutritionists(id) on delete set null,
  chat_scope text not null check (chat_scope in ('nutritionist', 'patient')),
  chat_id uuid,
  message_id uuid,
  tool_name text not null,
  status text not null check (
    status in ('executed', 'skipped', 'failed', 'pending_confirmation')
  ),
  requires_confirmation boolean not null default false,
  input jsonb not null default '{}'::jsonb,
  result jsonb not null default '{}'::jsonb,
  before_state jsonb,
  after_state jsonb,
  error text,
  created_at timestamptz not null default now()
);

create table if not exists public.appointments (
  id uuid primary key default gen_random_uuid(),
  nutritionist_id uuid not null references public.nutritionists(id) on delete cascade,
  patient_id uuid not null references public.patients(id) on delete cascade,
  title text not null,
  scheduled_at timestamptz not null,
  status text not null default 'scheduled' check (
    status in ('scheduled', 'rescheduled', 'cancelled', 'completed')
  ),
  notes text,
  created_by uuid references public.profiles(id) on delete set null,
  created_by_ai boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists ai_action_logs_actor_created_idx
  on public.ai_action_logs (actor_user_id, created_at desc);
create index if not exists ai_action_logs_patient_created_idx
  on public.ai_action_logs (patient_id, created_at desc);
create index if not exists ai_action_logs_chat_idx
  on public.ai_action_logs (chat_scope, chat_id, created_at desc);
create index if not exists appointments_nutritionist_scheduled_idx
  on public.appointments (nutritionist_id, scheduled_at desc);
create index if not exists appointments_patient_scheduled_idx
  on public.appointments (patient_id, scheduled_at desc);

alter table public.ai_action_logs enable row level security;
alter table public.appointments enable row level security;

drop policy if exists "Users view authorized AI action logs" on public.ai_action_logs;
drop policy if exists "Users view authorized appointments" on public.appointments;

create policy "Users view authorized AI action logs"
on public.ai_action_logs
for select
to authenticated
using (
  actor_user_id = (select auth.uid())
  or public.is_admin()
  or patient_id = public.get_current_patient_id()
  or nutritionist_id = public.get_current_nutritionist_id()
);

create policy "Users view authorized appointments"
on public.appointments
for select
to authenticated
using (
  public.is_admin()
  or patient_id = public.get_current_patient_id()
  or nutritionist_id = public.get_current_nutritionist_id()
);

grant select on public.ai_action_logs to authenticated;
grant select on public.appointments to authenticated;

do $$
begin
  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'ai_action_logs'
  ) then
    alter publication supabase_realtime add table public.ai_action_logs;
  end if;

  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'appointments'
  ) then
    alter publication supabase_realtime add table public.appointments;
  end if;

  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'patient_health_conditions'
  ) then
    alter publication supabase_realtime add table public.patient_health_conditions;
  end if;

  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'patient_variable_metrics'
  ) then
    alter publication supabase_realtime add table public.patient_variable_metrics;
  end if;

  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'diet_meals'
  ) then
    alter publication supabase_realtime add table public.diet_meals;
  end if;
end $$;
