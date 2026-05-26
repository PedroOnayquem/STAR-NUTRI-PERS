alter table public.nutritionist_chats
  alter column patient_id drop not null;

drop index if exists public.nutritionist_chats_owner_patient_idx;
create index if not exists nutritionist_chats_owner_patient_idx
  on public.nutritionist_chats (nutritionist_id, patient_id, updated_at desc);
