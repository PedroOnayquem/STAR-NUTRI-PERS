-- Backfill only facts derivable from existing relational data. Processing
-- timestamps and durations remain null because they were never recorded.
update public.patient_imports pi
set
  uploaded_by_user_id = n.user_id,
  file_count = greatest(1, (
    select count(*)::integer
    from public.patient_import_files pif
    where pif.import_id = pi.id
  ))
from public.nutritionists n
where n.id = pi.nutritionist_id
  and (
    pi.uploaded_by_user_id is null
    or pi.file_count <> greatest(1, (
      select count(*)::integer
      from public.patient_import_files pif
      where pif.import_id = pi.id
    ))
  );
