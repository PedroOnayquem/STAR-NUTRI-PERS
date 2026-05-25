-- Consolidate permissive RLS policies so PostgreSQL evaluates fewer policy
-- branches per row while preserving the existing access rules.

drop policy if exists "Admin vê logs" on public.activity_logs;
drop policy if exists "Nutricionista vê logs dos pacientes" on public.activity_logs;
create policy "Usuários autorizados veem logs"
on public.activity_logs
for select
using (
  (select is_admin())
  or exists (
    select 1
    from public.patients p
    where p.id = activity_logs.patient_id
      and p.nutritionist_id = (select get_current_nutritionist_id())
  )
);

drop policy if exists "Admin gerencia nutricionistas" on public.nutritionists;
drop policy if exists "Admin vê nutricionistas" on public.nutritionists;
drop policy if exists "Nutricionista vê próprio cadastro" on public.nutritionists;
create policy "Usuários autorizados veem nutricionistas"
on public.nutritionists
for select
using (
  (select is_admin())
  or user_id = (select auth.uid())
);
create policy "Admin insere nutricionistas"
on public.nutritionists
for insert
with check ((select is_admin()));
create policy "Admin atualiza nutricionistas"
on public.nutritionists
for update
using ((select is_admin()))
with check ((select is_admin()));
create policy "Admin remove nutricionistas"
on public.nutritionists
for delete
using ((select is_admin()));

drop policy if exists "Admin vê pacientes" on public.patients;
drop policy if exists "Nutricionista vê seus pacientes" on public.patients;
drop policy if exists "Paciente vê próprio cadastro" on public.patients;
create policy "Usuários autorizados veem pacientes"
on public.patients
for select
using (
  (select is_admin())
  or nutritionist_id = (select get_current_nutritionist_id())
  or user_id = (select auth.uid())
);

drop policy if exists "Admin pode atualizar perfis" on public.profiles;
drop policy if exists "Usuário pode atualizar parte do próprio perfil" on public.profiles;
create policy "Usuários autorizados atualizam perfis"
on public.profiles
for update
using (
  (select is_admin())
  or id = (select auth.uid())
)
with check (
  (select is_admin())
  or id = (select auth.uid())
);

drop policy if exists "Nutricionista gerencia dietas" on public.diets;
drop policy if exists "Nutricionista vê dietas dos pacientes" on public.diets;
drop policy if exists "Paciente vê suas dietas" on public.diets;
create policy "Usuários autorizados veem dietas"
on public.diets
for select
using (
  (select is_admin())
  or nutritionist_id = (select get_current_nutritionist_id())
  or patient_id = (select get_current_patient_id())
);
create policy "Nutricionista cria dietas"
on public.diets
for insert
with check (nutritionist_id = (select get_current_nutritionist_id()));
create policy "Nutricionista atualiza dietas"
on public.diets
for update
using (nutritionist_id = (select get_current_nutritionist_id()))
with check (nutritionist_id = (select get_current_nutritionist_id()));
create policy "Nutricionista remove dietas"
on public.diets
for delete
using (nutritionist_id = (select get_current_nutritionist_id()));

drop policy if exists "Nutricionista gerencia refeições" on public.diet_meals;
drop policy if exists "Usuários autorizados veem refeições" on public.diet_meals;
create policy "Usuários autorizados veem refeições"
on public.diet_meals
for select
using (
  exists (
    select 1
    from public.diets d
    where d.id = diet_meals.diet_id
      and (
        (select is_admin())
        or d.nutritionist_id = (select get_current_nutritionist_id())
        or d.patient_id = (select get_current_patient_id())
      )
  )
);
create policy "Nutricionista cria refeições"
on public.diet_meals
for insert
with check (
  exists (
    select 1
    from public.diets d
    where d.id = diet_meals.diet_id
      and d.nutritionist_id = (select get_current_nutritionist_id())
  )
);
create policy "Nutricionista atualiza refeições"
on public.diet_meals
for update
using (
  exists (
    select 1
    from public.diets d
    where d.id = diet_meals.diet_id
      and d.nutritionist_id = (select get_current_nutritionist_id())
  )
)
with check (
  exists (
    select 1
    from public.diets d
    where d.id = diet_meals.diet_id
      and d.nutritionist_id = (select get_current_nutritionist_id())
  )
);
create policy "Nutricionista remove refeições"
on public.diet_meals
for delete
using (
  exists (
    select 1
    from public.diets d
    where d.id = diet_meals.diet_id
      and d.nutritionist_id = (select get_current_nutritionist_id())
  )
);

drop policy if exists "Nutricionista gerencia condições" on public.patient_health_conditions;
drop policy if exists "Nutricionista vê condições dos seus pacientes" on public.patient_health_conditions;
drop policy if exists "Paciente vê suas condições" on public.patient_health_conditions;
create policy "Usuários autorizados veem condições"
on public.patient_health_conditions
for select
using (
  (select is_admin())
  or patient_id = (select get_current_patient_id())
  or exists (
    select 1
    from public.patients p
    where p.id = patient_health_conditions.patient_id
      and p.nutritionist_id = (select get_current_nutritionist_id())
  )
);
create policy "Nutricionista cria condições"
on public.patient_health_conditions
for insert
with check (
  exists (
    select 1
    from public.patients p
    where p.id = patient_health_conditions.patient_id
      and p.nutritionist_id = (select get_current_nutritionist_id())
  )
);
create policy "Nutricionista atualiza condições"
on public.patient_health_conditions
for update
using (
  exists (
    select 1
    from public.patients p
    where p.id = patient_health_conditions.patient_id
      and p.nutritionist_id = (select get_current_nutritionist_id())
  )
)
with check (
  exists (
    select 1
    from public.patients p
    where p.id = patient_health_conditions.patient_id
      and p.nutritionist_id = (select get_current_nutritionist_id())
  )
);
create policy "Nutricionista remove condições"
on public.patient_health_conditions
for delete
using (
  exists (
    select 1
    from public.patients p
    where p.id = patient_health_conditions.patient_id
      and p.nutritionist_id = (select get_current_nutritionist_id())
  )
);

drop policy if exists "Nutricionista gerencia métricas principais" on public.patient_main_metrics;
drop policy if exists "Nutricionista vê métricas principais" on public.patient_main_metrics;
drop policy if exists "Paciente vê suas métricas principais" on public.patient_main_metrics;
create policy "Usuários autorizados veem métricas principais"
on public.patient_main_metrics
for select
using (
  (select is_admin())
  or patient_id = (select get_current_patient_id())
  or exists (
    select 1
    from public.patients p
    where p.id = patient_main_metrics.patient_id
      and p.nutritionist_id = (select get_current_nutritionist_id())
  )
);
create policy "Nutricionista cria métricas principais"
on public.patient_main_metrics
for insert
with check (
  exists (
    select 1
    from public.patients p
    where p.id = patient_main_metrics.patient_id
      and p.nutritionist_id = (select get_current_nutritionist_id())
  )
);
create policy "Nutricionista atualiza métricas principais"
on public.patient_main_metrics
for update
using (
  exists (
    select 1
    from public.patients p
    where p.id = patient_main_metrics.patient_id
      and p.nutritionist_id = (select get_current_nutritionist_id())
  )
)
with check (
  exists (
    select 1
    from public.patients p
    where p.id = patient_main_metrics.patient_id
      and p.nutritionist_id = (select get_current_nutritionist_id())
  )
);
create policy "Nutricionista remove métricas principais"
on public.patient_main_metrics
for delete
using (
  exists (
    select 1
    from public.patients p
    where p.id = patient_main_metrics.patient_id
      and p.nutritionist_id = (select get_current_nutritionist_id())
  )
);

drop policy if exists "Nutricionista cria métricas variáveis" on public.patient_variable_metrics;
drop policy if exists "Paciente cria suas métricas variáveis" on public.patient_variable_metrics;
drop policy if exists "Nutricionista vê métricas variáveis" on public.patient_variable_metrics;
drop policy if exists "Paciente vê suas métricas variáveis" on public.patient_variable_metrics;
create policy "Usuários autorizados veem métricas variáveis"
on public.patient_variable_metrics
for select
using (
  (select is_admin())
  or patient_id = (select get_current_patient_id())
  or exists (
    select 1
    from public.patients p
    where p.id = patient_variable_metrics.patient_id
      and p.nutritionist_id = (select get_current_nutritionist_id())
  )
);
create policy "Usuários autorizados criam métricas variáveis"
on public.patient_variable_metrics
for insert
with check (
  patient_id = (select get_current_patient_id())
  or exists (
    select 1
    from public.patients p
    where p.id = patient_variable_metrics.patient_id
      and p.nutritionist_id = (select get_current_nutritionist_id())
  )
);

drop policy if exists "Nutricionista gerencia treinos" on public.workouts;
drop policy if exists "Nutricionista vê treinos dos pacientes" on public.workouts;
drop policy if exists "Paciente vê seus treinos" on public.workouts;
create policy "Usuários autorizados veem treinos"
on public.workouts
for select
using (
  (select is_admin())
  or nutritionist_id = (select get_current_nutritionist_id())
  or patient_id = (select get_current_patient_id())
);
create policy "Nutricionista cria treinos"
on public.workouts
for insert
with check (nutritionist_id = (select get_current_nutritionist_id()));
create policy "Nutricionista atualiza treinos"
on public.workouts
for update
using (nutritionist_id = (select get_current_nutritionist_id()))
with check (nutritionist_id = (select get_current_nutritionist_id()));
create policy "Nutricionista remove treinos"
on public.workouts
for delete
using (nutritionist_id = (select get_current_nutritionist_id()));

drop policy if exists "Nutricionista gerencia exercícios" on public.workout_exercises;
drop policy if exists "Usuários autorizados veem exercícios" on public.workout_exercises;
create policy "Usuários autorizados veem exercícios"
on public.workout_exercises
for select
using (
  exists (
    select 1
    from public.workouts w
    where w.id = workout_exercises.workout_id
      and (
        (select is_admin())
        or w.nutritionist_id = (select get_current_nutritionist_id())
        or w.patient_id = (select get_current_patient_id())
      )
  )
);
create policy "Nutricionista cria exercícios"
on public.workout_exercises
for insert
with check (
  exists (
    select 1
    from public.workouts w
    where w.id = workout_exercises.workout_id
      and w.nutritionist_id = (select get_current_nutritionist_id())
  )
);
create policy "Nutricionista atualiza exercícios"
on public.workout_exercises
for update
using (
  exists (
    select 1
    from public.workouts w
    where w.id = workout_exercises.workout_id
      and w.nutritionist_id = (select get_current_nutritionist_id())
  )
)
with check (
  exists (
    select 1
    from public.workouts w
    where w.id = workout_exercises.workout_id
      and w.nutritionist_id = (select get_current_nutritionist_id())
  )
);
create policy "Nutricionista remove exercícios"
on public.workout_exercises
for delete
using (
  exists (
    select 1
    from public.workouts w
    where w.id = workout_exercises.workout_id
      and w.nutritionist_id = (select get_current_nutritionist_id())
  )
);
