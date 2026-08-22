-- Atomically persist an AI-generated diet and its meals. Server-only and
-- tenant-scoped: no partial diet remains if any meal fails validation.
begin;

create or replace function public.create_ai_diet_plan(
  p_nutritionist_id uuid,
  p_patient_id uuid,
  p_title text,
  p_description text,
  p_calories integer,
  p_protein numeric,
  p_carbs numeric,
  p_fats numeric,
  p_water_goal_ml integer,
  p_is_active boolean,
  p_meals jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_diet_id uuid;
  v_meal record;
  v_meals_count integer := 0;
begin
  if not exists (
    select 1 from public.patients patient
    where patient.id = p_patient_id
      and patient.nutritionist_id = p_nutritionist_id
  ) then
    raise exception using errcode = '42501', message = 'Patient does not belong to the authenticated nutritionist workspace.';
  end if;
  if nullif(btrim(p_title), '') is null then
    raise exception using errcode = '22023', message = 'Diet title is required.';
  end if;
  if jsonb_typeof(p_meals) is distinct from 'array' or jsonb_array_length(p_meals) = 0 then
    raise exception using errcode = '22023', message = 'Diet meals must be a non-empty array.';
  end if;

  insert into public.diets (
    nutritionist_id, patient_id, title, description, calories,
    protein, carbs, fats, water_goal_ml, is_active
  ) values (
    p_nutritionist_id, p_patient_id, btrim(p_title), nullif(btrim(p_description), ''),
    p_calories, p_protein, p_carbs, p_fats, p_water_goal_ml, p_is_active
  ) returning id into v_diet_id;

  for v_meal in
    select item.value from jsonb_array_elements(p_meals) as item(value)
  loop
    if jsonb_typeof(v_meal.value) is distinct from 'object'
       or nullif(btrim(v_meal.value ->> 'meal_name'), '') is null
       or jsonb_typeof(v_meal.value -> 'foods') is distinct from 'array' then
      raise exception using errcode = '22023', message = 'Each meal requires a name and foods array.';
    end if;
    insert into public.diet_meals (diet_id, meal_name, meal_time, foods, notes)
    values (
      v_diet_id,
      btrim(v_meal.value ->> 'meal_name'),
      nullif(btrim(v_meal.value ->> 'meal_time'), ''),
      coalesce(v_meal.value -> 'foods', '[]'::jsonb),
      nullif(btrim(v_meal.value ->> 'notes'), '')
    );
    v_meals_count := v_meals_count + 1;
  end loop;

  return jsonb_build_object('diet_id', v_diet_id, 'meals_count', v_meals_count, 'is_active', p_is_active);
end;
$$;

revoke all on function public.create_ai_diet_plan(uuid, uuid, text, text, integer, numeric, numeric, numeric, integer, boolean, jsonb)
from public, anon, authenticated;
grant execute on function public.create_ai_diet_plan(uuid, uuid, text, text, integer, numeric, numeric, numeric, integer, boolean, jsonb)
to service_role;

notify pgrst, 'reload schema';

commit;
