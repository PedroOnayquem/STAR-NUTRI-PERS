-- Real telemetry for patient file imports. Existing rows remain valid and are
-- deliberately not assigned synthetic processing timestamps or durations.

alter table public.patient_imports
  add column if not exists uploaded_by_user_id uuid references public.profiles(id) on delete set null,
  add column if not exists processing_started_at timestamptz,
  add column if not exists processed_at timestamptz,
  add column if not exists processing_duration_ms bigint,
  add column if not exists processing_stage text,
  add column if not exists error_code text,
  add column if not exists attempt_count integer not null default 1,
  add column if not exists file_count integer not null default 1;

alter table public.patient_imports drop constraint if exists patient_imports_status_check;
alter table public.patient_imports
  add constraint patient_imports_status_check
  check (status in ('pending', 'processing', 'processed', 'linked', 'failed')),
  add constraint patient_imports_processing_duration_check
  check (processing_duration_ms is null or processing_duration_ms >= 0),
  add constraint patient_imports_attempt_count_check check (attempt_count > 0),
  add constraint patient_imports_file_count_check check (file_count > 0);

alter table public.patient_import_files
  add column if not exists status text not null default 'processed',
  add column if not exists extraction_mode text,
  add column if not exists processing_started_at timestamptz,
  add column if not exists processed_at timestamptz,
  add column if not exists processing_duration_ms bigint,
  add column if not exists error_code text,
  add column if not exists error_message text;

alter table public.patient_import_files
  add constraint patient_import_files_status_check
  check (status in ('pending', 'processing', 'processed', 'failed')),
  add constraint patient_import_files_processing_duration_check
  check (processing_duration_ms is null or processing_duration_ms >= 0);

create table if not exists public.patient_import_events (
  id bigint generated always as identity primary key,
  import_id uuid not null references public.patient_imports(id) on delete cascade,
  file_id uuid references public.patient_import_files(id) on delete cascade,
  actor_user_id uuid references public.profiles(id) on delete set null,
  patient_id uuid references public.patients(id) on delete cascade,
  nutritionist_id uuid not null references public.nutritionists(id) on delete cascade,
  event_type text not null check (event_type in (
    'upload_received', 'processing_started', 'extraction_completed',
    'storage_completed', 'processing_completed', 'processing_failed',
    'linked_to_patient', 'ai_context_used', 'signed_url_generated',
    'query_failed'
  )),
  stage text,
  duration_ms bigint check (duration_ms is null or duration_ms >= 0),
  error_code text,
  error_message text,
  chat_scope text check (chat_scope is null or chat_scope in ('nutritionist', 'patient')),
  chat_id uuid,
  message_id uuid,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists patient_import_events_nutritionist_created_idx
  on public.patient_import_events (nutritionist_id, created_at desc, id desc);
create index if not exists patient_import_events_patient_created_idx
  on public.patient_import_events (patient_id, created_at desc, id desc)
  where patient_id is not null;
create index if not exists patient_import_events_import_created_idx
  on public.patient_import_events (import_id, created_at desc, id desc);
create index if not exists patient_import_events_failures_idx
  on public.patient_import_events (created_at desc, id desc)
  where event_type in ('processing_failed', 'query_failed');
create index if not exists patient_import_events_ai_usage_idx
  on public.patient_import_events (import_id, created_at desc)
  where event_type = 'ai_context_used';
create index if not exists patient_imports_uploaded_by_idx
  on public.patient_imports (uploaded_by_user_id)
  where uploaded_by_user_id is not null;

alter table public.patient_import_events enable row level security;

drop policy if exists "Usuarios autorizados veem eventos de importacao" on public.patient_import_events;
create policy "Usuarios autorizados veem eventos de importacao"
on public.patient_import_events
for select
to authenticated
using (
  (select public.is_admin())
  or nutritionist_id = (select public.get_current_nutritionist_id())
  or patient_id = (select public.get_current_patient_id())
);

-- One SELECT policy avoids duplicate permissive-policy evaluation and preserves
-- the same admin/nutritionist/patient visibility rules already used by imports.
drop policy if exists "Nutricionista ve arquivos de importacoes" on public.patient_import_files;
drop policy if exists "Paciente ve arquivos de importacoes vinculadas" on public.patient_import_files;
drop policy if exists "Usuarios autorizados veem arquivos de importacoes" on public.patient_import_files;
create policy "Usuarios autorizados veem arquivos de importacoes"
on public.patient_import_files
for select
to authenticated
using (
  exists (
    select 1
    from public.patient_imports pi
    where pi.id = patient_import_files.import_id
      and (
        (select public.is_admin())
        or pi.nutritionist_id = (select public.get_current_nutritionist_id())
        or pi.patient_id = (select public.get_current_patient_id())
      )
  )
);

-- Object paths are bioimpedance-imports/{nutritionist_id}/{import_id}/file.
-- foldername()[1] is the fixed prefix; the tenant id is at position 2.
drop policy if exists "Nutricionista envia PDFs importados" on storage.objects;
create policy "Nutricionista envia PDFs importados"
on storage.objects
for insert
to authenticated
with check (
  bucket_id = 'patient-imports'
  and (
    (storage.foldername(name))[2] = ((select public.get_current_nutritionist_id()))::text
    or (select public.is_admin())
  )
);

drop policy if exists "Nutricionista le PDFs importados" on storage.objects;
create policy "Nutricionista le PDFs importados"
on storage.objects
for select
to authenticated
using (
  bucket_id = 'patient-imports'
  and (
    (storage.foldername(name))[2] = ((select public.get_current_nutritionist_id()))::text
    or (select public.is_admin())
  )
);

revoke all on table public.patient_import_events from anon, authenticated;
grant select on table public.patient_import_events to authenticated;
grant select, insert on table public.patient_import_events to service_role;
revoke all on sequence public.patient_import_events_id_seq from anon, authenticated;
grant usage, select on sequence public.patient_import_events_id_seq to service_role;

comment on table public.patient_import_events is
  'Append-only audit and performance events for real patient import processing and AI-context usage.';
comment on column public.patient_import_events.event_type is
  'ai_context_used means derived metrics from the import were included in the model context; it does not claim the model quoted the file.';
