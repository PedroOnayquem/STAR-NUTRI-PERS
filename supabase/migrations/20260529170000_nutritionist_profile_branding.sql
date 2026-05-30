alter table public.nutritionists
add column if not exists avatar_url text,
add column if not exists avatar_path text,
add column if not exists logo_url text,
add column if not exists logo_path text,
add column if not exists clinic_name text,
add column if not exists professional_name text,
add column if not exists phone text;

alter table public.nutritionists
add column if not exists bio text;

drop policy if exists "Nutricionista atualiza próprio perfil profissional" on public.nutritionists;
create policy "Nutricionista atualiza próprio perfil profissional"
on public.nutritionists
for update
to authenticated
using (user_id = (select auth.uid()))
with check (user_id = (select auth.uid()));

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'nutritionist-avatars',
  'nutritionist-avatars',
  true,
  5242880,
  array['image/png', 'image/jpeg', 'image/webp']::text[]
)
on conflict (id) do update
set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "Todos visualizam logos de nutricionistas" on storage.objects;
create policy "Todos visualizam logos de nutricionistas"
on storage.objects
for select
using (bucket_id = 'nutritionist-avatars');

drop policy if exists "Nutricionista envia propria logo" on storage.objects;
create policy "Nutricionista envia propria logo"
on storage.objects
for insert
to authenticated
with check (
  bucket_id = 'nutritionist-avatars'
  and (storage.foldername(name))[1] = (select get_current_nutritionist_id())::text
);

drop policy if exists "Nutricionista atualiza propria logo" on storage.objects;
create policy "Nutricionista atualiza propria logo"
on storage.objects
for update
to authenticated
using (
  bucket_id = 'nutritionist-avatars'
  and (storage.foldername(name))[1] = (select get_current_nutritionist_id())::text
)
with check (
  bucket_id = 'nutritionist-avatars'
  and (storage.foldername(name))[1] = (select get_current_nutritionist_id())::text
);

drop policy if exists "Nutricionista remove propria logo" on storage.objects;
create policy "Nutricionista remove propria logo"
on storage.objects
for delete
to authenticated
using (
  bucket_id = 'nutritionist-avatars'
  and (storage.foldername(name))[1] = (select get_current_nutritionist_id())::text
);

notify pgrst, 'reload schema';
