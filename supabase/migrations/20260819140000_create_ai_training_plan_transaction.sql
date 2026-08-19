-- Persist the structured plan and the legacy workout consumed by the UI in one
-- transaction. The RPC is server-only and verifies tenant ownership itself.

create or replace function public.create_ai_training_plan(
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
  v_day record;
  v_day_id uuid;
  v_exercise record;
  v_exercises_count integer := 0;
  v_plan_id uuid;
  v_restrictions_text text;
  v_workout_description text;
  v_workout_id uuid;
begin
  if not exists (
    select 1
    from public.patients patient
    where patient.id = p_patient_id
      and patient.nutritionist_id = p_nutritionist_id
  ) then
    raise exception using
      errcode = '42501',
      message = 'Patient does not belong to the authenticated nutritionist workspace.';
  end if;

  if nullif(btrim(p_title), '') is null then
    raise exception using errcode = '22023', message = 'Training plan title is required.';
  end if;

  if jsonb_typeof(p_days) is distinct from 'array'
     or jsonb_array_length(p_days) = 0 then
    raise exception using errcode = '22023', message = 'Training plan days must be a non-empty array.';
  end if;

  if jsonb_typeof(coalesce(p_restrictions, '[]'::jsonb)) is distinct from 'array' then
    raise exception using errcode = '22023', message = 'Training plan restrictions must be an array.';
  end if;

  select string_agg(restriction, ', ' order by position)
  into v_restrictions_text
  from jsonb_array_elements_text(coalesce(p_restrictions, '[]'::jsonb))
    with ordinality as item(restriction, position);

  v_workout_description := nullif(
    concat_ws(
      E'\n',
      case when nullif(btrim(p_objective), '') is not null
        then 'Objetivo: ' || btrim(p_objective) end,
      case when nullif(v_restrictions_text, '') is not null
        then 'Restricoes: ' || v_restrictions_text end,
      case when nullif(btrim(p_observations), '') is not null
        then 'Observacoes: ' || btrim(p_observations) end
    ),
    ''
  );

  insert into public.training_plans (
    nutritionist_id,
    patient_id,
    title,
    objective,
    restrictions,
    observations,
    status,
    created_by_ai
  ) values (
    p_nutritionist_id,
    p_patient_id,
    btrim(p_title),
    nullif(btrim(p_objective), ''),
    coalesce(p_restrictions, '[]'::jsonb),
    nullif(btrim(p_observations), ''),
    'active',
    true
  )
  returning id into v_plan_id;

  insert into public.workouts (
    nutritionist_id,
    patient_id,
    title,
    description,
    frequency_per_week,
    is_active
  ) values (
    p_nutritionist_id,
    p_patient_id,
    btrim(p_title),
    coalesce(v_workout_description, 'Treino criado pela IA do Star Nutri.'),
    jsonb_array_length(p_days),
    true
  )
  returning id into v_workout_id;

  for v_day in
    select item.value, item.ordinality
    from jsonb_array_elements(p_days) with ordinality as item(value, ordinality)
  loop
    if jsonb_typeof(v_day.value) is distinct from 'object'
       or nullif(btrim(v_day.value ->> 'name'), '') is null
       or jsonb_typeof(v_day.value -> 'exercises') is distinct from 'array'
       or jsonb_array_length(v_day.value -> 'exercises') = 0 then
      raise exception using errcode = '22023', message = 'Each training day requires a name and exercises.';
    end if;

    insert into public.training_days (
      training_plan_id,
      name,
      focus,
      order_index
    ) values (
      v_plan_id,
      btrim(v_day.value ->> 'name'),
      nullif(btrim(v_day.value ->> 'focus'), ''),
      v_day.ordinality - 1
    )
    returning id into v_day_id;

    for v_exercise in
      select item.value, item.ordinality
      from jsonb_array_elements(v_day.value -> 'exercises')
        with ordinality as item(value, ordinality)
    loop
      if jsonb_typeof(v_exercise.value) is distinct from 'object'
         or nullif(btrim(v_exercise.value ->> 'exercise_name'), '') is null then
        raise exception using errcode = '22023', message = 'Each exercise requires a name.';
      end if;

      insert into public.training_exercises (
        training_day_id,
        muscle_group,
        exercise_name,
        sets,
        reps,
        rest,
        load_guidance,
        notes,
        order_index
      ) values (
        v_day_id,
        nullif(btrim(v_exercise.value ->> 'muscle_group'), ''),
        btrim(v_exercise.value ->> 'exercise_name'),
        case when jsonb_typeof(v_exercise.value -> 'sets') = 'number'
          then greatest((v_exercise.value ->> 'sets')::integer, 1) end,
        nullif(btrim(v_exercise.value ->> 'reps'), ''),
        nullif(btrim(v_exercise.value ->> 'rest'), ''),
        nullif(btrim(v_exercise.value ->> 'load_guidance'), ''),
        nullif(btrim(v_exercise.value ->> 'notes'), ''),
        v_exercise.ordinality - 1
      );

      insert into public.workout_exercises (
        workout_id,
        exercise_name,
        muscle_group,
        sets,
        reps,
        rest_time,
        load_info,
        notes
      ) values (
        v_workout_id,
        btrim(v_exercise.value ->> 'exercise_name'),
        nullif(btrim(v_exercise.value ->> 'muscle_group'), ''),
        case when jsonb_typeof(v_exercise.value -> 'sets') = 'number'
          then greatest((v_exercise.value ->> 'sets')::integer, 1) end,
        nullif(btrim(v_exercise.value ->> 'reps'), ''),
        nullif(btrim(v_exercise.value ->> 'rest'), ''),
        nullif(btrim(v_exercise.value ->> 'load_guidance'), ''),
        nullif(btrim(v_exercise.value ->> 'notes'), '')
      );

      v_exercises_count := v_exercises_count + 1;
    end loop;
  end loop;

  return jsonb_build_object(
    'training_plan_id', v_plan_id,
    'workout_id', v_workout_id,
    'days_count', jsonb_array_length(p_days),
    'exercises_count', v_exercises_count
  );
end;
$$;

revoke all on function public.create_ai_training_plan(uuid, uuid, text, text, jsonb, text, jsonb)
from public, anon, authenticated;
grant execute on function public.create_ai_training_plan(uuid, uuid, text, text, jsonb, text, jsonb)
to service_role;

notify pgrst, 'reload schema';
