drop policy if exists "Nutricionista ve suas importacoes" on public.patient_imports;
drop policy if exists "Paciente ve importacoes vinculadas" on public.patient_imports;

create policy "Usuarios autorizados veem importacoes"
on public.patient_imports
for select
using (
  (select is_admin())
  or nutritionist_id = (select get_current_nutritionist_id())
  or exists (
    select 1
    from public.patients p
    where p.id = patient_imports.patient_id
      and p.id = (select get_current_patient_id())
  )
);

revoke execute on function public.notify_patient_appointment_change() from public, anon, authenticated;
revoke execute on function public.set_patient_appointment_user() from public, anon, authenticated;
