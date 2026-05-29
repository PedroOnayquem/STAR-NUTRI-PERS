alter table public.patient_imports
  add column if not exists file_type text,
  add column if not exists original_file_name text,
  add column if not exists file_size_bytes bigint,
  add column if not exists mime_type text,
  add column if not exists error_message text;

alter table public.patient_imports
  alter column source_type set default 'bioimpedance_report';

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'patient_imports_file_type_check'
  ) then
    alter table public.patient_imports
      add constraint patient_imports_file_type_check
      check (file_type is null or file_type in ('pdf', 'jpg', 'jpeg', 'png'));
  end if;
end $$;

update public.patient_imports
set file_type = 'pdf'
where file_type is null
  and source_type = 'bioimpedance_pdf';

update public.patient_imports
set file_type = case
  when lower(coalesce(mime_type, '')) = 'application/pdf' then 'pdf'
  when lower(coalesce(mime_type, '')) = 'image/png' then 'png'
  when lower(coalesce(mime_type, '')) = 'image/jpeg' then 'jpg'
  when lower(coalesce(file_url, '')) like '%.pdf' then 'pdf'
  when lower(coalesce(file_url, '')) like '%.png' then 'png'
  when lower(coalesce(file_url, '')) like '%.jpeg' then 'jpeg'
  when lower(coalesce(file_url, '')) like '%.jpg' then 'jpg'
  else file_type
end
where file_type is null;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'patient-imports',
  'patient-imports',
  false,
  10485760,
  array['application/pdf', 'image/jpeg', 'image/png']
)
on conflict (id) do update
set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

notify pgrst, 'reload schema';
