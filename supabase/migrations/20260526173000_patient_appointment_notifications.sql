alter table public.patient_appointments
  add column if not exists patient_user_id uuid references public.profiles(id) on delete cascade;

update public.patient_appointments appointment
set patient_user_id = patient.user_id
from public.patients patient
where patient.id = appointment.patient_id
  and appointment.patient_user_id is null;

alter table public.patient_appointments
  alter column patient_user_id set not null;

create index if not exists patient_appointments_patient_user_date_idx
  on public.patient_appointments (patient_user_id, date desc, start_time desc);

create table if not exists public.notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  patient_id uuid references public.patients(id) on delete cascade,
  appointment_id uuid references public.patient_appointments(id) on delete cascade,
  title text not null,
  message text not null,
  type text not null check (
    type in (
      'appointment_created',
      'appointment_updated',
      'appointment_cancelled',
      'appointment_reminder'
    )
  ),
  read boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists notifications_user_read_created_idx
  on public.notifications (user_id, read, created_at desc);
create index if not exists notifications_patient_created_idx
  on public.notifications (patient_id, created_at desc);
create index if not exists notifications_appointment_created_idx
  on public.notifications (appointment_id, created_at desc);

alter table public.notifications enable row level security;

drop policy if exists "Usuarios veem suas notificacoes" on public.notifications;
drop policy if exists "Usuarios atualizam suas notificacoes" on public.notifications;

create policy "Usuarios veem suas notificacoes"
on public.notifications
for select
to authenticated
using (
  (select is_admin())
  or user_id = (select auth.uid())
);

create policy "Usuarios atualizam suas notificacoes"
on public.notifications
for update
to authenticated
using (user_id = (select auth.uid()))
with check (user_id = (select auth.uid()));

grant select, update on public.notifications to authenticated;

create or replace function public.set_patient_appointment_user()
returns trigger
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  resolved_user_id uuid;
begin
  select p.user_id
  into resolved_user_id
  from public.patients p
  where p.id = new.patient_id;

  if resolved_user_id is null then
    raise exception 'Paciente do agendamento nao encontrado.';
  end if;

  new.patient_user_id = resolved_user_id;
  return new;
end;
$$;

drop trigger if exists set_patient_appointment_user on public.patient_appointments;
create trigger set_patient_appointment_user
before insert or update of patient_id
on public.patient_appointments
for each row execute function public.set_patient_appointment_user();

create or replace function public.notify_patient_appointment_change()
returns trigger
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  notification_type text;
  notification_title text;
  notification_message text;
  formatted_date text;
  formatted_time text;
begin
  if tg_op = 'UPDATE' then
    if old.title is not distinct from new.title
      and old.type is not distinct from new.type
      and old.description is not distinct from new.description
      and old.date is not distinct from new.date
      and old.start_time is not distinct from new.start_time
      and old.end_time is not distinct from new.end_time
      and old.location is not distinct from new.location
      and old.meeting_link is not distinct from new.meeting_link
      and old.status is not distinct from new.status
      and old.notes is not distinct from new.notes then
      return new;
    end if;
  end if;

  formatted_date := to_char(new.date, 'DD/MM/YYYY');
  formatted_time := left(new.start_time::text, 5);

  if tg_op = 'INSERT' then
    notification_type := 'appointment_created';
    notification_title := 'Novo acompanhamento agendado';
    notification_message := new.title || ' em ' || formatted_date || ' as ' || formatted_time || '.';
  elsif new.status = 'cancelado' and old.status is distinct from new.status then
    notification_type := 'appointment_cancelled';
    notification_title := 'Agendamento cancelado';
    notification_message := new.title || ' de ' || formatted_date || ' as ' || formatted_time || ' foi cancelado.';
  else
    notification_type := 'appointment_updated';
    notification_title := 'Agendamento atualizado';
    notification_message := new.title || ' agora esta marcado para ' || formatted_date || ' as ' || formatted_time || '.';
  end if;

  insert into public.notifications (
    user_id,
    patient_id,
    appointment_id,
    title,
    message,
    type
  )
  values (
    new.patient_user_id,
    new.patient_id,
    new.id,
    notification_title,
    notification_message,
    notification_type
  );

  return new;
end;
$$;

drop trigger if exists notify_patient_appointment_change on public.patient_appointments;
create trigger notify_patient_appointment_change
after insert or update
on public.patient_appointments
for each row execute function public.notify_patient_appointment_change();

do $$
begin
  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'patient_appointments'
  ) then
    alter publication supabase_realtime add table public.patient_appointments;
  end if;

  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'notifications'
  ) then
    alter publication supabase_realtime add table public.notifications;
  end if;
end $$;
