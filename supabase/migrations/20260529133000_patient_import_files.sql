create table if not exists public.patient_import_files (
  id uuid primary key default gen_random_uuid(),
  import_id uuid not null references public.patient_imports(id) on delete cascade,
  file_url text,
  file_type text,
  mime_type text,
  original_file_name text,
  file_size_bytes bigint,
  extracted_text text,
  order_index int,
  created_at timestamptz not null default now()
);

create index if not exists patient_import_files_import_order_idx
  on public.patient_import_files (import_id, order_index asc);

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'patient_import_files_file_type_check'
  ) then
    alter table public.patient_import_files
      add constraint patient_import_files_file_type_check
      check (file_type is null or file_type in ('pdf', 'jpg', 'jpeg', 'png'));
  end if;
end $$;

insert into public.patient_import_files (
  import_id,
  file_url,
  file_type,
  mime_type,
  original_file_name,
  file_size_bytes,
  extracted_text,
  order_index
)
select
  pi.id,
  pi.file_url,
  pi.file_type,
  pi.mime_type,
  pi.original_file_name,
  pi.file_size_bytes,
  null,
  0
from public.patient_imports pi
where pi.file_url is not null
  and not exists (
    select 1
    from public.patient_import_files pif
    where pif.import_id = pi.id
  );

alter table public.patient_import_files enable row level security;

drop policy if exists "Nutricionista ve arquivos de importacoes" on public.patient_import_files;
drop policy if exists "Paciente ve arquivos de importacoes vinculadas" on public.patient_import_files;
drop policy if exists "Nutricionista cria arquivos de importacoes" on public.patient_import_files;

create policy "Nutricionista ve arquivos de importacoes"
on public.patient_import_files
for select
using (
  exists (
    select 1
    from public.patient_imports pi
    where pi.id = patient_import_files.import_id
      and (
        pi.nutritionist_id = (select get_current_nutritionist_id())
        or (select is_admin())
      )
  )
);

create policy "Paciente ve arquivos de importacoes vinculadas"
on public.patient_import_files
for select
using (
  exists (
    select 1
    from public.patient_imports pi
    join public.patients p on p.id = pi.patient_id
    where pi.id = patient_import_files.import_id
      and p.id = (select get_current_patient_id())
  )
);

create policy "Nutricionista cria arquivos de importacoes"
on public.patient_import_files
for insert
with check (
  exists (
    select 1
    from public.patient_imports pi
    where pi.id = patient_import_files.import_id
      and (
        pi.nutritionist_id = (select get_current_nutritionist_id())
        or (select is_admin())
      )
  )
);

grant select, insert on public.patient_import_files to authenticated;

notify pgrst, 'reload schema';
