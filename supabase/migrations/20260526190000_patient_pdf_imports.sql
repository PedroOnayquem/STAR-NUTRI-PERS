create table if not exists public.patient_imports (
  id uuid primary key default gen_random_uuid(),
  patient_id uuid references public.patients(id) on delete set null,
  nutritionist_id uuid not null references public.nutritionists(id) on delete cascade,
  file_url text,
  file_path text,
  source_type text not null default 'bioimpedance_pdf',
  extracted_payload jsonb not null default '{}'::jsonb,
  confidence_payload jsonb not null default '{}'::jsonb,
  status text not null default 'processed'
    check (status in ('processed', 'linked', 'failed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists patient_imports_patient_created_idx
  on public.patient_imports (patient_id, created_at desc);
create index if not exists patient_imports_nutritionist_created_idx
  on public.patient_imports (nutritionist_id, created_at desc);
create index if not exists patient_imports_status_idx
  on public.patient_imports (status);

alter table public.patient_variable_metrics
  add column if not exists source_type text,
  add column if not exists source_import_id uuid references public.patient_imports(id) on delete set null;

create index if not exists patient_variable_metrics_source_import_idx
  on public.patient_variable_metrics (source_import_id);

drop trigger if exists set_patient_imports_updated_at on public.patient_imports;
create trigger set_patient_imports_updated_at
before update on public.patient_imports
for each row execute function public.update_updated_at_column();

alter table public.patient_imports enable row level security;

drop policy if exists "Nutricionista ve suas importacoes" on public.patient_imports;
drop policy if exists "Paciente ve importacoes vinculadas" on public.patient_imports;
drop policy if exists "Nutricionista cria suas importacoes" on public.patient_imports;
drop policy if exists "Nutricionista atualiza suas importacoes" on public.patient_imports;

create policy "Nutricionista ve suas importacoes"
on public.patient_imports
for select
using (
  nutritionist_id = (select get_current_nutritionist_id())
  or (select is_admin())
);

create policy "Paciente ve importacoes vinculadas"
on public.patient_imports
for select
using (
  exists (
    select 1
    from public.patients p
    where p.id = patient_imports.patient_id
      and p.id = (select get_current_patient_id())
  )
);

create policy "Nutricionista cria suas importacoes"
on public.patient_imports
for insert
with check (
  nutritionist_id = (select get_current_nutritionist_id())
  or (select is_admin())
);

create policy "Nutricionista atualiza suas importacoes"
on public.patient_imports
for update
using (
  nutritionist_id = (select get_current_nutritionist_id())
  or (select is_admin())
)
with check (
  nutritionist_id = (select get_current_nutritionist_id())
  or (select is_admin())
);

grant select, insert, update on public.patient_imports to authenticated;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'patient-imports',
  'patient-imports',
  false,
  10485760,
  array['application/pdf']
)
on conflict (id) do update
set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "Nutricionista le PDFs importados" on storage.objects;
drop policy if exists "Nutricionista envia PDFs importados" on storage.objects;

create policy "Nutricionista le PDFs importados"
on storage.objects
for select
using (
  bucket_id = 'patient-imports'
  and (
    (storage.foldername(name))[1] = (select get_current_nutritionist_id())::text
    or (select is_admin())
  )
);

create policy "Nutricionista envia PDFs importados"
on storage.objects
for insert
with check (
  bucket_id = 'patient-imports'
  and (
    (storage.foldername(name))[1] = (select get_current_nutritionist_id())::text
    or (select is_admin())
  )
);
