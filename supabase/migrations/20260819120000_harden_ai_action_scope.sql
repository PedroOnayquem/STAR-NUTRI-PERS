-- Defense in depth for AI-operated clinical writes.
-- The backend still authorizes every tool call; these policies prevent a
-- nutritionist from linking a record to a patient owned by another workspace
-- through the public Data API.

drop policy if exists "Nutricionista cria dietas" on public.diets;
drop policy if exists "Nutricionista atualiza dietas" on public.diets;
drop policy if exists "Nutricionista remove dietas" on public.diets;
drop policy if exists "Nutritionist inserts diets for owned patients" on public.diets;
drop policy if exists "Nutritionist updates diets for owned patients" on public.diets;
drop policy if exists "Nutritionist deletes diets for owned patients" on public.diets;

create policy "Nutritionist inserts diets for owned patients"
on public.diets for insert to authenticated
with check (
  nutritionist_id = (select public.get_current_nutritionist_id())
  and exists (
    select 1 from public.patients p
    where p.id = diets.patient_id
      and p.nutritionist_id = (select public.get_current_nutritionist_id())
  )
);

create policy "Nutritionist updates diets for owned patients"
on public.diets for update to authenticated
using (
  nutritionist_id = (select public.get_current_nutritionist_id())
  and exists (
    select 1 from public.patients p
    where p.id = diets.patient_id
      and p.nutritionist_id = (select public.get_current_nutritionist_id())
  )
)
with check (
  nutritionist_id = (select public.get_current_nutritionist_id())
  and exists (
    select 1 from public.patients p
    where p.id = diets.patient_id
      and p.nutritionist_id = (select public.get_current_nutritionist_id())
  )
);

create policy "Nutritionist deletes diets for owned patients"
on public.diets for delete to authenticated
using (
  nutritionist_id = (select public.get_current_nutritionist_id())
  and exists (
    select 1 from public.patients p
    where p.id = diets.patient_id
      and p.nutritionist_id = (select public.get_current_nutritionist_id())
  )
);

drop policy if exists "Nutricionista cria treinos" on public.workouts;
drop policy if exists "Nutricionista atualiza treinos" on public.workouts;
drop policy if exists "Nutricionista remove treinos" on public.workouts;
drop policy if exists "Nutritionist inserts workouts for owned patients" on public.workouts;
drop policy if exists "Nutritionist updates workouts for owned patients" on public.workouts;
drop policy if exists "Nutritionist deletes workouts for owned patients" on public.workouts;

create policy "Nutritionist inserts workouts for owned patients"
on public.workouts for insert to authenticated
with check (
  nutritionist_id = (select public.get_current_nutritionist_id())
  and exists (
    select 1 from public.patients p
    where p.id = workouts.patient_id
      and p.nutritionist_id = (select public.get_current_nutritionist_id())
  )
);

create policy "Nutritionist updates workouts for owned patients"
on public.workouts for update to authenticated
using (
  nutritionist_id = (select public.get_current_nutritionist_id())
  and exists (
    select 1 from public.patients p
    where p.id = workouts.patient_id
      and p.nutritionist_id = (select public.get_current_nutritionist_id())
  )
)
with check (
  nutritionist_id = (select public.get_current_nutritionist_id())
  and exists (
    select 1 from public.patients p
    where p.id = workouts.patient_id
      and p.nutritionist_id = (select public.get_current_nutritionist_id())
  )
);

create policy "Nutritionist deletes workouts for owned patients"
on public.workouts for delete to authenticated
using (
  nutritionist_id = (select public.get_current_nutritionist_id())
  and exists (
    select 1 from public.patients p
    where p.id = workouts.patient_id
      and p.nutritionist_id = (select public.get_current_nutritionist_id())
  )
);

drop policy if exists "Nutricionista cria planos de treino" on public.training_plans;
drop policy if exists "Nutricionista atualiza planos de treino" on public.training_plans;
drop policy if exists "Nutricionista remove planos de treino" on public.training_plans;
drop policy if exists "Nutritionist inserts training plans for owned patients" on public.training_plans;
drop policy if exists "Nutritionist updates training plans for owned patients" on public.training_plans;
drop policy if exists "Nutritionist deletes training plans for owned patients" on public.training_plans;

create policy "Nutritionist inserts training plans for owned patients"
on public.training_plans for insert to authenticated
with check (
  nutritionist_id = (select public.get_current_nutritionist_id())
  and exists (
    select 1 from public.patients p
    where p.id = training_plans.patient_id
      and p.nutritionist_id = (select public.get_current_nutritionist_id())
  )
);

create policy "Nutritionist updates training plans for owned patients"
on public.training_plans for update to authenticated
using (
  nutritionist_id = (select public.get_current_nutritionist_id())
  and exists (
    select 1 from public.patients p
    where p.id = training_plans.patient_id
      and p.nutritionist_id = (select public.get_current_nutritionist_id())
  )
)
with check (
  nutritionist_id = (select public.get_current_nutritionist_id())
  and exists (
    select 1 from public.patients p
    where p.id = training_plans.patient_id
      and p.nutritionist_id = (select public.get_current_nutritionist_id())
  )
);

create policy "Nutritionist deletes training plans for owned patients"
on public.training_plans for delete to authenticated
using (
  nutritionist_id = (select public.get_current_nutritionist_id())
  and exists (
    select 1 from public.patients p
    where p.id = training_plans.patient_id
      and p.nutritionist_id = (select public.get_current_nutritionist_id())
  )
);

-- Audit payloads can contain before/after snapshots. Patients do not need this
-- internal operational trail; admins and the owning nutritionist may inspect it.
drop policy if exists "Users view authorized AI action logs" on public.ai_action_logs;
drop policy if exists "Admins and owning nutritionists view AI action logs" on public.ai_action_logs;
create policy "Admins and owning nutritionists view AI action logs"
on public.ai_action_logs for select to authenticated
using (
  (select public.is_admin())
  or nutritionist_id = (select public.get_current_nutritionist_id())
);

revoke all privileges on public.ai_action_logs from anon, authenticated, service_role;
grant select on public.ai_action_logs to authenticated;
grant select, insert on public.ai_action_logs to service_role;

-- This trigger function is invoked internally by Postgres and must not be an
-- exposed RPC endpoint for API roles.
revoke execute on function public.set_nutritionist_chat_scope()
from public, anon, authenticated, service_role;

notify pgrst, 'reload schema';
