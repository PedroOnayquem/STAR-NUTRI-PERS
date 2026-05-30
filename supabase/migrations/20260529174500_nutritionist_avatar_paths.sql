alter table public.nutritionists
add column if not exists avatar_path text,
add column if not exists logo_path text;

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

notify pgrst, 'reload schema';
