-- Destructive-looking operations in this verification are fully rolled back.
-- Run only against a linked project that contains at least one patient.
begin;

create temp table rls_probe (
  patient_id uuid not null,
  patient_user_id uuid not null,
  nutritionist_id uuid not null,
  nutritionist_user_id uuid not null,
  plan_id uuid not null default gen_random_uuid(),
  day_id uuid not null default gen_random_uuid(),
  exercise_id uuid not null default gen_random_uuid()
) on commit drop;

insert into rls_probe (
  patient_id,
  patient_user_id,
  nutritionist_id,
  nutritionist_user_id
)
select p.id, p.user_id, p.nutritionist_id, n.user_id
from public.patients p
join public.nutritionists n on n.id = p.nutritionist_id
limit 1;

do $verify$
begin
  if not exists (select 1 from rls_probe) then
    raise exception 'Structured training RLS verification requires one patient.';
  end if;
end
$verify$;

update public.patients p
set
  access_status = 'ACTIVE',
  activated_at = now(),
  expired_at = null,
  is_active = true
from rls_probe probe
where p.id = probe.patient_id;

insert into public.training_plans (id, patient_id, nutritionist_id, title)
select plan_id, patient_id, nutritionist_id, 'RLS verification plan'
from rls_probe;

insert into public.training_days (id, training_plan_id, name)
select day_id, plan_id, 'RLS verification day'
from rls_probe;

insert into public.training_exercises (id, training_day_id, exercise_name)
select exercise_id, day_id, 'RLS verification exercise'
from rls_probe;

create temp table rls_probe_results (
  scenario text primary key,
  premium_access boolean not null,
  plans bigint not null,
  days bigint not null,
  exercises bigint not null
) on commit drop;

grant select on table rls_probe to authenticated;
grant insert, select on table rls_probe_results to authenticated;

select set_config(
  'request.jwt.claims',
  jsonb_build_object(
    'sub', patient_user_id,
    'role', 'authenticated',
    'app_metadata', jsonb_build_object('must_change_password', false)
  )::text,
  true
)
from rls_probe;
set local role authenticated;

insert into rls_probe_results
select
  'active_patient',
  public.patient_has_premium_access(probe.patient_id),
  (select count(*) from public.training_plans where id = probe.plan_id),
  (select count(*) from public.training_days where id = probe.day_id),
  (select count(*) from public.training_exercises where id = probe.exercise_id)
from rls_probe probe;

reset role;

update public.patients p
set
  access_status = 'TRIAL',
  trial_days = 7,
  trial_started_at = now(),
  trial_ends_at = now() + interval '7 days',
  activated_at = null,
  expired_at = null,
  is_active = true
from rls_probe probe
where p.id = probe.patient_id;

set local role authenticated;

insert into rls_probe_results
select
  'finite_trial_patient',
  public.patient_has_premium_access(probe.patient_id),
  (select count(*) from public.training_plans where id = probe.plan_id),
  (select count(*) from public.training_days where id = probe.day_id),
  (select count(*) from public.training_exercises where id = probe.exercise_id)
from rls_probe probe;

reset role;

update public.patients p
set
  access_status = 'EXPIRED',
  expired_at = now(),
  is_active = false
from rls_probe probe
where p.id = probe.patient_id;

set local role authenticated;

insert into rls_probe_results
select
  'expired_patient',
  public.patient_has_premium_access(probe.patient_id),
  (select count(*) from public.training_plans where id = probe.plan_id),
  (select count(*) from public.training_days where id = probe.day_id),
  (select count(*) from public.training_exercises where id = probe.exercise_id)
from rls_probe probe;

reset role;

select set_config(
  'request.jwt.claims',
  jsonb_build_object(
    'sub', nutritionist_user_id,
    'role', 'authenticated',
    'app_metadata', jsonb_build_object('must_change_password', false)
  )::text,
  true
)
from rls_probe;
set local role authenticated;

insert into rls_probe_results
select
  'nutritionist',
  public.patient_has_premium_access(probe.patient_id),
  (select count(*) from public.training_plans where id = probe.plan_id),
  (select count(*) from public.training_days where id = probe.day_id),
  (select count(*) from public.training_exercises where id = probe.exercise_id)
from rls_probe probe;

reset role;

do $verify$
declare
  probe_patient_id uuid := (select patient_id from rls_probe);
begin
  begin
    update public.patients
    set access_status = 'TRIAL', trial_ends_at = null
    where id = probe_patient_id;
    raise exception 'TRIAL without an end date was accepted.';
  exception
    when check_violation then null;
  end;

  begin
    update public.patients
    set access_status = 'TRIAL', trial_ends_at = 'infinity'::timestamptz
    where id = probe_patient_id;
    raise exception 'TRIAL with an infinite end date was accepted.';
  exception
    when check_violation then null;
  end;

  if not exists (
    select 1
    from rls_probe_results
    where scenario = 'active_patient'
      and premium_access
      and plans = 1
      and days = 1
      and exercises = 1
  ) then
    raise exception 'Active patient could not read the complete structured plan.';
  end if;

  if not exists (
    select 1
    from rls_probe_results
    where scenario = 'finite_trial_patient'
      and premium_access
      and plans = 1
      and days = 1
      and exercises = 1
  ) then
    raise exception 'Finite trial patient could not read the complete structured plan.';
  end if;

  if not exists (
    select 1
    from rls_probe_results
    where scenario = 'expired_patient'
      and not premium_access
      and plans = 0
      and days = 0
      and exercises = 0
  ) then
    raise exception 'Expired patient retained structured training access.';
  end if;

  if not exists (
    select 1
    from rls_probe_results
    where scenario = 'nutritionist'
      and plans = 1
      and days = 1
      and exercises = 1
  ) then
    raise exception 'Nutritionist lost access to the patient structured plan.';
  end if;
end
$verify$;

rollback;
