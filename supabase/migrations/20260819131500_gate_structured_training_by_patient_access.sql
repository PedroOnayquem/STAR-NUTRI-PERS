begin;

-- A trial without an explicit end date must fail closed. Existing legacy rows
-- are expired before the invariant is enforced for future writes.
update public.patients
set
  access_status = 'EXPIRED',
  expired_at = coalesce(expired_at, now()),
  is_active = false
where access_status = 'TRIAL'
  and (trial_ends_at is null or not isfinite(trial_ends_at));

alter table public.patients
drop constraint if exists patients_trial_requires_end_at;

alter table public.patients
add constraint patients_trial_requires_end_at
check (
  access_status <> 'TRIAL'
  or (trial_ends_at is not null and isfinite(trial_ends_at))
);

create or replace function public.patient_has_premium_access(patient_id uuid)
returns boolean
language sql
stable
security invoker
set search_path = ''
as $$
  select exists (
    select 1
    from public.patients p
    where p.id = $1
      and (
        p.access_status = 'ACTIVE'
        or (
          p.access_status = 'TRIAL'
          and p.trial_ends_at is not null
          and isfinite(p.trial_ends_at)
          and p.trial_ends_at > now()
        )
      )
      and (
        p.id = (select public.get_current_patient_id())
        or p.nutritionist_id = (select public.get_current_nutritionist_id())
        or (select public.is_admin())
      )
  );
$$;

revoke execute on function public.patient_has_premium_access(uuid) from public, anon;
grant execute on function public.patient_has_premium_access(uuid) to authenticated, service_role;

drop policy if exists "Usuários autorizados veem planos de treino" on public.training_plans;
create policy "Usuários autorizados veem planos de treino"
on public.training_plans
for select
to authenticated
using (
  (select public.is_admin())
  or nutritionist_id = (select public.get_current_nutritionist_id())
  or (
    patient_id = (select public.get_current_patient_id())
    and (select public.patient_has_premium_access(patient_id))
  )
);

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
        or (
          plan.patient_id = (select public.get_current_patient_id())
          and (select public.patient_has_premium_access(plan.patient_id))
        )
      )
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
        or (
          plan.patient_id = (select public.get_current_patient_id())
          and (select public.patient_has_premium_access(plan.patient_id))
        )
      )
  )
);

notify pgrst, 'reload schema';

commit;
