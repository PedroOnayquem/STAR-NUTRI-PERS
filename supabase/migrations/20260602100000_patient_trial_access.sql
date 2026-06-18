alter table public.nutritionists
add column if not exists default_patient_trial_days integer not null default 7;

alter table public.nutritionists
drop constraint if exists nutritionists_default_patient_trial_days_check;

alter table public.nutritionists
add constraint nutritionists_default_patient_trial_days_check
check (default_patient_trial_days in (7, 14, 30));

alter table public.patients
add column if not exists access_status text not null default 'TRIAL',
add column if not exists trial_started_at timestamptz,
add column if not exists trial_ends_at timestamptz,
add column if not exists trial_days integer,
add column if not exists activated_at timestamptz,
add column if not exists expired_at timestamptz;

alter table public.patients
drop constraint if exists patients_access_status_check;

alter table public.patients
add constraint patients_access_status_check
check (access_status in ('TRIAL', 'ACTIVE', 'EXPIRED'));

alter table public.patients
drop constraint if exists patients_trial_days_check;

alter table public.patients
add constraint patients_trial_days_check
check (trial_days is null or trial_days in (7, 14, 30));

update public.patients
set
  access_status = case
    when is_active is false then 'EXPIRED'
    else 'ACTIVE'
  end,
  activated_at = case
    when is_active is not false and activated_at is null then coalesce(updated_at, created_at, now())
    else activated_at
  end
where access_status = 'TRIAL'
  and trial_started_at is null
  and trial_ends_at is null;

create index if not exists patients_nutritionist_access_status_idx
  on public.patients (nutritionist_id, access_status, trial_ends_at);

create or replace function public.patient_has_premium_access(patient_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public, auth
as $$
  select exists (
    select 1
    from public.patients p
    where p.id = patient_id
      and p.access_status in ('TRIAL', 'ACTIVE')
      and (
        p.access_status = 'ACTIVE'
        or p.trial_ends_at is null
        or p.trial_ends_at > now()
      )
  );
$$;

revoke execute on function public.patient_has_premium_access(uuid) from public;
grant execute on function public.patient_has_premium_access(uuid) to authenticated, service_role;

drop policy if exists "Usuários autorizados veem dietas" on public.diets;
create policy "Usuários autorizados veem dietas"
on public.diets
for select
using (
  (select is_admin())
  or nutritionist_id = (select get_current_nutritionist_id())
  or (
    patient_id = (select get_current_patient_id())
    and public.patient_has_premium_access(patient_id)
  )
);

drop policy if exists "Usuários autorizados veem treinos" on public.workouts;
create policy "Usuários autorizados veem treinos"
on public.workouts
for select
using (
  (select is_admin())
  or nutritionist_id = (select get_current_nutritionist_id())
  or (
    patient_id = (select get_current_patient_id())
    and public.patient_has_premium_access(patient_id)
  )
);

drop policy if exists "Usuários autorizados criam métricas variáveis" on public.patient_variable_metrics;
create policy "Usuários autorizados criam métricas variáveis"
on public.patient_variable_metrics
for insert
with check (
  (
    patient_id = (select get_current_patient_id())
    and public.patient_has_premium_access(patient_id)
  )
  or exists (
    select 1
    from public.patients p
    where p.id = patient_variable_metrics.patient_id
      and p.nutritionist_id = (select get_current_nutritionist_id())
  )
);
