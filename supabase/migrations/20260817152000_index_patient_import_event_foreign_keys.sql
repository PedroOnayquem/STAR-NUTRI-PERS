create index if not exists patient_import_events_actor_user_idx
  on public.patient_import_events (actor_user_id)
  where actor_user_id is not null;

create index if not exists patient_import_events_file_idx
  on public.patient_import_events (file_id)
  where file_id is not null;
