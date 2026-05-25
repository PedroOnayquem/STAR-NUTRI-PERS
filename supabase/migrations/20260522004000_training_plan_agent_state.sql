-- Structured training plans and pending AI action state.

alter table public.ai_action_logs
  add column if not exists user_id uuid references public.profiles(id) on delete set null,
  add column if not exists conversation_id uuid,
  add column if not exists intent text,
  add column if not exists payload jsonb not null default '{}'::jsonb,
  add column if not exists success boolean,
  add column if not exists error_message text;

update public.ai_action_logs
set user_id = actor_user_id
where user_id is null;

update public.ai_action_logs
set conversation_id = chat_id
where conversation_id is null;

update public.ai_action_logs
set payload = input
where payload = '{}'::jsonb
  and input is not null
  and input <> '{}'::jsonb;

update public.ai_action_logs
set success = (status = 'executed')
where success is null;

update public.ai_action_logs
set error_message = error
where error_message is null
  and error is not null;

create index if not exists ai_action_logs_user_created_idx
  on public.ai_action_logs (user_id, created_at desc);
create index if not exists ai_action_logs_conversation_created_idx
  on public.ai_action_logs (conversation_id, created_at desc);
create index if not exists ai_action_logs_intent_created_idx
  on public.ai_action_logs (intent, created_at desc);
create index if not exists ai_action_logs_success_created_idx
  on public.ai_action_logs (success, created_at desc);

create table if not exists public.training_plans (
  id uuid primary key default gen_random_uuid(),
  patient_id uuid not null references public.patients(id) on delete cascade,
  nutritionist_id uuid not null references public.nutritionists(id) on delete cascade,
  title text not null,
  objective text,
  restrictions jsonb not null default '[]'::jsonb,
  observations text,
  status text not null default 'active' check (status in ('draft', 'active', 'archived')),
  created_by_ai boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.training_days (
  id uuid primary key default gen_random_uuid(),
  training_plan_id uuid not null references public.training_plans(id) on delete cascade,
  name text not null,
  focus text,
  order_index integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.training_exercises (
  id uuid primary key default gen_random_uuid(),
  training_day_id uuid not null references public.training_days(id) on delete cascade,
  muscle_group text,
  exercise_name text not null,
  sets integer,
  reps text,
  rest text,
  load_guidance text,
  notes text,
  order_index integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.ai_conversation_state (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null,
  user_id uuid not null references public.profiles(id) on delete cascade,
  patient_id uuid references public.patients(id) on delete cascade,
  pending_action text not null,
  pending_payload jsonb not null default '{}'::jsonb,
  target_entity text,
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint ai_conversation_state_conversation_user_key unique (conversation_id, user_id)
);

create index if not exists training_plans_patient_created_idx
  on public.training_plans (patient_id, created_at desc);
create index if not exists training_plans_nutritionist_created_idx
  on public.training_plans (nutritionist_id, created_at desc);
create index if not exists training_plans_status_created_idx
  on public.training_plans (status, created_at desc);
create index if not exists training_days_plan_order_idx
  on public.training_days (training_plan_id, order_index);
create index if not exists training_exercises_day_order_idx
  on public.training_exercises (training_day_id, order_index);
create index if not exists ai_conversation_state_lookup_idx
  on public.ai_conversation_state (conversation_id, user_id, expires_at desc);
create index if not exists ai_conversation_state_patient_idx
  on public.ai_conversation_state (patient_id, updated_at desc);

drop trigger if exists training_plans_updated_at on public.training_plans;
create trigger training_plans_updated_at
before update on public.training_plans
for each row execute function public.update_updated_at_column();

drop trigger if exists training_days_updated_at on public.training_days;
create trigger training_days_updated_at
before update on public.training_days
for each row execute function public.update_updated_at_column();

drop trigger if exists training_exercises_updated_at on public.training_exercises;
create trigger training_exercises_updated_at
before update on public.training_exercises
for each row execute function public.update_updated_at_column();

drop trigger if exists ai_conversation_state_updated_at on public.ai_conversation_state;
create trigger ai_conversation_state_updated_at
before update on public.ai_conversation_state
for each row execute function public.update_updated_at_column();

alter table public.training_plans enable row level security;
alter table public.training_days enable row level security;
alter table public.training_exercises enable row level security;
alter table public.ai_conversation_state enable row level security;

drop policy if exists "Usuários autorizados veem planos de treino" on public.training_plans;
create policy "Usuários autorizados veem planos de treino"
on public.training_plans
for select
to authenticated
using (
  (select public.is_admin())
  or nutritionist_id = (select public.get_current_nutritionist_id())
  or patient_id = (select public.get_current_patient_id())
);

drop policy if exists "Nutricionista cria planos de treino" on public.training_plans;
create policy "Nutricionista cria planos de treino"
on public.training_plans
for insert
to authenticated
with check (nutritionist_id = (select public.get_current_nutritionist_id()));

drop policy if exists "Nutricionista atualiza planos de treino" on public.training_plans;
create policy "Nutricionista atualiza planos de treino"
on public.training_plans
for update
to authenticated
using (nutritionist_id = (select public.get_current_nutritionist_id()))
with check (nutritionist_id = (select public.get_current_nutritionist_id()));

drop policy if exists "Nutricionista remove planos de treino" on public.training_plans;
create policy "Nutricionista remove planos de treino"
on public.training_plans
for delete
to authenticated
using (nutritionist_id = (select public.get_current_nutritionist_id()));

drop policy if exists "Usuários autorizados veem dias de treino" on public.training_days;
create policy "Usuários autorizados veem dias de treino"
on public.training_days
for select
to authenticated
using (
  exists (
    select 1
    from public.training_plans plan
    where plan.id = training_days.training_plan_id
      and (
        (select public.is_admin())
        or plan.nutritionist_id = (select public.get_current_nutritionist_id())
        or plan.patient_id = (select public.get_current_patient_id())
      )
  )
);

drop policy if exists "Nutricionista cria dias de treino" on public.training_days;
create policy "Nutricionista cria dias de treino"
on public.training_days
for insert
to authenticated
with check (
  exists (
    select 1
    from public.training_plans plan
    where plan.id = training_days.training_plan_id
      and plan.nutritionist_id = (select public.get_current_nutritionist_id())
  )
);

drop policy if exists "Nutricionista atualiza dias de treino" on public.training_days;
create policy "Nutricionista atualiza dias de treino"
on public.training_days
for update
to authenticated
using (
  exists (
    select 1
    from public.training_plans plan
    where plan.id = training_days.training_plan_id
      and plan.nutritionist_id = (select public.get_current_nutritionist_id())
  )
)
with check (
  exists (
    select 1
    from public.training_plans plan
    where plan.id = training_days.training_plan_id
      and plan.nutritionist_id = (select public.get_current_nutritionist_id())
  )
);

drop policy if exists "Nutricionista remove dias de treino" on public.training_days;
create policy "Nutricionista remove dias de treino"
on public.training_days
for delete
to authenticated
using (
  exists (
    select 1
    from public.training_plans plan
    where plan.id = training_days.training_plan_id
      and plan.nutritionist_id = (select public.get_current_nutritionist_id())
  )
);

drop policy if exists "Usuários autorizados veem exercícios de treino" on public.training_exercises;
create policy "Usuários autorizados veem exercícios de treino"
on public.training_exercises
for select
to authenticated
using (
  exists (
    select 1
    from public.training_days day
    join public.training_plans plan on plan.id = day.training_plan_id
    where day.id = training_exercises.training_day_id
      and (
        (select public.is_admin())
        or plan.nutritionist_id = (select public.get_current_nutritionist_id())
        or plan.patient_id = (select public.get_current_patient_id())
      )
  )
);

drop policy if exists "Nutricionista cria exercícios de treino" on public.training_exercises;
create policy "Nutricionista cria exercícios de treino"
on public.training_exercises
for insert
to authenticated
with check (
  exists (
    select 1
    from public.training_days day
    join public.training_plans plan on plan.id = day.training_plan_id
    where day.id = training_exercises.training_day_id
      and plan.nutritionist_id = (select public.get_current_nutritionist_id())
  )
);

drop policy if exists "Nutricionista atualiza exercícios de treino" on public.training_exercises;
create policy "Nutricionista atualiza exercícios de treino"
on public.training_exercises
for update
to authenticated
using (
  exists (
    select 1
    from public.training_days day
    join public.training_plans plan on plan.id = day.training_plan_id
    where day.id = training_exercises.training_day_id
      and plan.nutritionist_id = (select public.get_current_nutritionist_id())
  )
)
with check (
  exists (
    select 1
    from public.training_days day
    join public.training_plans plan on plan.id = day.training_plan_id
    where day.id = training_exercises.training_day_id
      and plan.nutritionist_id = (select public.get_current_nutritionist_id())
  )
);

drop policy if exists "Nutricionista remove exercícios de treino" on public.training_exercises;
create policy "Nutricionista remove exercícios de treino"
on public.training_exercises
for delete
to authenticated
using (
  exists (
    select 1
    from public.training_days day
    join public.training_plans plan on plan.id = day.training_plan_id
    where day.id = training_exercises.training_day_id
      and plan.nutritionist_id = (select public.get_current_nutritionist_id())
  )
);

drop policy if exists "Usuários gerenciam próprio estado do agente" on public.ai_conversation_state;
create policy "Usuários gerenciam próprio estado do agente"
on public.ai_conversation_state
for all
to authenticated
using (
  user_id = (select auth.uid())
  or (select public.is_admin())
)
with check (
  user_id = (select auth.uid())
  or (select public.is_admin())
);

grant select on public.training_plans to authenticated;
grant select on public.training_days to authenticated;
grant select on public.training_exercises to authenticated;
grant select, insert, update, delete on public.ai_conversation_state to authenticated;

do $$
begin
  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'training_plans'
  ) then
    alter publication supabase_realtime add table public.training_plans;
  end if;

  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'training_days'
  ) then
    alter publication supabase_realtime add table public.training_days;
  end if;

  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'training_exercises'
  ) then
    alter publication supabase_realtime add table public.training_exercises;
  end if;
end $$;
