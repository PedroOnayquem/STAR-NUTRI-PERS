create table if not exists public.patient_appointments (
  id uuid primary key default gen_random_uuid(),
  patient_id uuid not null references public.patients(id) on delete cascade,
  nutritionist_id uuid not null references public.nutritionists(id) on delete cascade,
  title text not null,
  type text not null check (
    type in (
      'acompanhamento',
      'consulta',
      'reuniao',
      'avaliacao',
      'retorno',
      'revisao_dieta',
      'revisao_treino',
      'outro'
    )
  ),
  description text,
  date date not null,
  start_time time not null,
  end_time time,
  location text,
  meeting_link text,
  status text not null default 'agendado' check (
    status in ('agendado', 'confirmado', 'concluido', 'cancelado', 'faltou')
  ),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists patient_appointments_patient_idx
  on public.patient_appointments (patient_id, date desc, start_time desc);
create index if not exists patient_appointments_nutritionist_idx
  on public.patient_appointments (nutritionist_id, date desc, start_time desc);
create index if not exists patient_appointments_date_idx
  on public.patient_appointments (date);
create index if not exists patient_appointments_status_idx
  on public.patient_appointments (status);
create index if not exists patient_appointments_created_idx
  on public.patient_appointments (created_at desc);

drop trigger if exists patient_appointments_updated_at on public.patient_appointments;
create trigger patient_appointments_updated_at
before update on public.patient_appointments
for each row execute function public.update_updated_at_column();

alter table public.patient_appointments enable row level security;

drop policy if exists "Usuarios autorizados veem agenda de pacientes" on public.patient_appointments;
drop policy if exists "Nutricionista cria agenda dos seus pacientes" on public.patient_appointments;
drop policy if exists "Nutricionista atualiza agenda dos seus pacientes" on public.patient_appointments;
drop policy if exists "Nutricionista remove agenda dos seus pacientes" on public.patient_appointments;

create policy "Usuarios autorizados veem agenda de pacientes"
on public.patient_appointments
for select
to authenticated
using (
  (select is_admin())
  or patient_id = (select get_current_patient_id())
  or exists (
    select 1
    from public.patients p
    where p.id = patient_appointments.patient_id
      and p.nutritionist_id = (select get_current_nutritionist_id())
      and patient_appointments.nutritionist_id = (select get_current_nutritionist_id())
  )
);

create policy "Nutricionista cria agenda dos seus pacientes"
on public.patient_appointments
for insert
to authenticated
with check (
  nutritionist_id = (select get_current_nutritionist_id())
  and exists (
    select 1
    from public.patients p
    where p.id = patient_appointments.patient_id
      and p.nutritionist_id = (select get_current_nutritionist_id())
  )
);

create policy "Nutricionista atualiza agenda dos seus pacientes"
on public.patient_appointments
for update
to authenticated
using (
  nutritionist_id = (select get_current_nutritionist_id())
  and exists (
    select 1
    from public.patients p
    where p.id = patient_appointments.patient_id
      and p.nutritionist_id = (select get_current_nutritionist_id())
  )
)
with check (
  nutritionist_id = (select get_current_nutritionist_id())
  and exists (
    select 1
    from public.patients p
    where p.id = patient_appointments.patient_id
      and p.nutritionist_id = (select get_current_nutritionist_id())
  )
);

create policy "Nutricionista remove agenda dos seus pacientes"
on public.patient_appointments
for delete
to authenticated
using (
  nutritionist_id = (select get_current_nutritionist_id())
  and exists (
    select 1
    from public.patients p
    where p.id = patient_appointments.patient_id
      and p.nutritionist_id = (select get_current_nutritionist_id())
  )
);

grant select, insert, update, delete on public.patient_appointments to authenticated;
