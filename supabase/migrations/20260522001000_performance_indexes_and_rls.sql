-- Performance pass: add covering indexes for hot filters/orders and reduce RLS per-row auth calls.

create index if not exists activity_logs_user_created_idx
  on public.activity_logs (user_id, created_at desc);

create index if not exists activity_logs_patient_created_idx
  on public.activity_logs (patient_id, created_at desc);

create index if not exists diet_meals_diet_created_idx
  on public.diet_meals (diet_id, created_at);

create index if not exists diets_nutritionist_created_idx
  on public.diets (nutritionist_id, created_at desc);

create index if not exists diets_patient_active_created_idx
  on public.diets (patient_id, is_active desc, created_at desc);

create index if not exists patient_health_conditions_patient_created_idx
  on public.patient_health_conditions (patient_id, created_at desc);

create index if not exists patient_main_metrics_patient_created_idx
  on public.patient_main_metrics (patient_id, created_at desc);

create index if not exists patient_main_metrics_defined_by_idx
  on public.patient_main_metrics (defined_by);

create index if not exists patient_variable_metrics_patient_recorded_idx
  on public.patient_variable_metrics (patient_id, recorded_at desc, created_at desc);

create index if not exists workouts_nutritionist_created_idx
  on public.workouts (nutritionist_id, created_at desc);

create index if not exists workouts_patient_active_created_idx
  on public.workouts (patient_id, is_active desc, created_at desc);

create index if not exists workout_exercises_workout_created_idx
  on public.workout_exercises (workout_id, created_at);

drop policy if exists "Usuário pode ver seu próprio perfil" on public.profiles;
create policy "Usuário pode ver seu próprio perfil"
on public.profiles
for select
to authenticated
using (
  id = (select auth.uid())
  or (select public.is_admin())
);

drop policy if exists "Usuário pode atualizar parte do próprio perfil" on public.profiles;
create policy "Usuário pode atualizar parte do próprio perfil"
on public.profiles
for update
to authenticated
using (id = (select auth.uid()))
with check (id = (select auth.uid()));

drop policy if exists "Nutricionista vê próprio cadastro" on public.nutritionists;
create policy "Nutricionista vê próprio cadastro"
on public.nutritionists
for select
to authenticated
using (user_id = (select auth.uid()));

drop policy if exists "Paciente vê próprio cadastro" on public.patients;
create policy "Paciente vê próprio cadastro"
on public.patients
for select
to authenticated
using (user_id = (select auth.uid()));
