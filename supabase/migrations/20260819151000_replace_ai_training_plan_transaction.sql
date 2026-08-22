-- Replacement is destructive, so the application queues human confirmation
-- before calling this server-only transaction.
begin;

create or replace function public.replace_ai_training_plan(
  p_nutritionist_id uuid,
  p_patient_id uuid,
  p_title text,
  p_objective text,
  p_restrictions jsonb,
  p_observations text,
  p_days jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_result jsonb;
begin
  if not exists (
    select 1 from public.patients patient
    where patient.id = p_patient_id
      and patient.nutritionist_id = p_nutritionist_id
  ) then
    raise exception using errcode = '42501', message = 'Patient does not belong to the authenticated nutritionist workspace.';
  end if;

  update public.training_plans
  set status = 'archived'
  where patient_id = p_patient_id
    and nutritionist_id = p_nutritionist_id
    and status = 'active';
  update public.workouts
  set is_active = false
  where patient_id = p_patient_id
    and nutritionist_id = p_nutritionist_id
    and is_active = true;

  v_result := public.create_ai_training_plan(
    p_nutritionist_id, p_patient_id, p_title, p_objective,
    p_restrictions, p_observations, p_days
  );
  return v_result || jsonb_build_object('replaced', true);
end;
$$;

revoke all on function public.replace_ai_training_plan(uuid, uuid, text, text, jsonb, text, jsonb)
from public, anon, authenticated;
grant execute on function public.replace_ai_training_plan(uuid, uuid, text, text, jsonb, text, jsonb)
to service_role;

notify pgrst, 'reload schema';

commit;
