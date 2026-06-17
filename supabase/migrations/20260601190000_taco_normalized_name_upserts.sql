alter table public.taco_foods
  add column if not exists normalized_name text;

update public.taco_foods
set normalized_name = coalesce(nullif(normalized_name, ''), nullif(search_name, ''))
where normalized_name is null
  and search_name is not null;

drop index if exists public.taco_foods_code_unique_idx;

create unique index if not exists taco_foods_code_unique
  on public.taco_foods (code)
  where code is not null;

create unique index if not exists taco_foods_normalized_name_unique
  on public.taco_foods (normalized_name)
  where normalized_name is not null;
