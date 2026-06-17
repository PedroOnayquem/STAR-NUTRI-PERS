alter table public.nutritionist_chats
  alter column patient_id drop not null;

alter table public.nutritionist_chats
  add column if not exists chat_scope text not null default 'patient';

update public.nutritionist_chats
set chat_scope = case when patient_id is null then 'general' else 'patient' end
where chat_scope is null
   or (patient_id is null and chat_scope <> 'general')
   or (patient_id is not null and chat_scope <> 'patient');

alter table public.nutritionist_chats
  drop constraint if exists nutritionist_chats_chat_scope_check;

alter table public.nutritionist_chats
  add constraint nutritionist_chats_chat_scope_check
  check (chat_scope in ('general', 'patient'));

alter table public.nutritionist_chats
  drop constraint if exists nutritionist_chats_scope_patient_check;

alter table public.nutritionist_chats
  add constraint nutritionist_chats_scope_patient_check
  check (
    (chat_scope = 'general' and patient_id is null)
    or (chat_scope = 'patient' and patient_id is not null)
  );

create or replace function public.set_nutritionist_chat_scope()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if new.patient_id is null then
    new.chat_scope := 'general';
  elsif new.chat_scope is null or new.chat_scope = 'general' then
    new.chat_scope := 'patient';
  end if;
  return new;
end;
$$;

drop trigger if exists nutritionist_chats_scope_from_patient on public.nutritionist_chats;
create trigger nutritionist_chats_scope_from_patient
before insert or update of patient_id, chat_scope on public.nutritionist_chats
for each row execute function public.set_nutritionist_chat_scope();

create index if not exists nutritionist_chats_owner_scope_idx
  on public.nutritionist_chats (nutritionist_id, chat_scope, updated_at desc);

create table if not exists public.taco_foods (
  id uuid primary key default gen_random_uuid(),
  code text,
  name text not null,
  search_name text,
  normalized_name text,
  category text,
  moisture_g numeric,
  energy_kcal numeric,
  energy_kj numeric,
  protein_g numeric,
  lipid_g numeric,
  cholesterol_mg numeric,
  carbohydrate_g numeric,
  fiber_g numeric,
  ash_g numeric,
  calcium_mg numeric,
  magnesium_mg numeric,
  manganese_mg numeric,
  phosphorus_mg numeric,
  iron_mg numeric,
  sodium_mg numeric,
  potassium_mg numeric,
  copper_mg numeric,
  zinc_mg numeric,
  retinol_mcg numeric,
  re_mcg numeric,
  rae_mcg numeric,
  thiamine_mg numeric,
  riboflavin_mg numeric,
  pyridoxine_mg numeric,
  niacin_mg numeric,
  vitamin_c_mg numeric,
  source text not null default 'TACO',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop index if exists public.taco_foods_code_unique_idx;
create unique index if not exists taco_foods_code_unique
  on public.taco_foods (code)
  where code is not null;

create unique index if not exists taco_foods_normalized_name_unique
  on public.taco_foods (normalized_name)
  where normalized_name is not null;

create index if not exists idx_taco_foods_name
  on public.taco_foods using gin (to_tsvector('portuguese', coalesce(search_name, name)));

create index if not exists idx_taco_foods_category
  on public.taco_foods (category);

drop trigger if exists taco_foods_updated_at on public.taco_foods;
create trigger taco_foods_updated_at
before update on public.taco_foods
for each row execute function public.update_updated_at_column();

alter table public.taco_foods enable row level security;

drop policy if exists "Authenticated users read TACO foods" on public.taco_foods;
create policy "Authenticated users read TACO foods"
on public.taco_foods
for select
to authenticated
using ((select auth.uid()) is not null);

grant select on public.taco_foods to authenticated;
grant all on public.taco_foods to service_role;

create table if not exists public.diet_meal_items (
  id uuid primary key default gen_random_uuid(),
  meal_id uuid not null references public.diet_meals(id) on delete cascade,
  taco_food_id uuid references public.taco_foods(id) on delete set null,
  custom_food_name text,
  quantity_g numeric not null check (quantity_g > 0),
  energy_kcal numeric,
  protein_g numeric,
  carbohydrate_g numeric,
  lipid_g numeric,
  fiber_g numeric,
  sodium_mg numeric,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint diet_meal_items_food_source_check
    check (taco_food_id is not null or nullif(trim(custom_food_name), '') is not null)
);

create index if not exists diet_meal_items_meal_created_idx
  on public.diet_meal_items (meal_id, created_at);

create index if not exists diet_meal_items_taco_food_idx
  on public.diet_meal_items (taco_food_id);

drop trigger if exists diet_meal_items_updated_at on public.diet_meal_items;
create trigger diet_meal_items_updated_at
before update on public.diet_meal_items
for each row execute function public.update_updated_at_column();

alter table public.diet_meal_items enable row level security;

drop policy if exists "Authorized users read diet meal items" on public.diet_meal_items;
create policy "Authorized users read diet meal items"
on public.diet_meal_items
for select
to authenticated
using (
  exists (
    select 1
    from public.diet_meals meal
    join public.diets diet on diet.id = meal.diet_id
    where meal.id = diet_meal_items.meal_id
      and (
        (select is_admin())
        or diet.nutritionist_id = (select get_current_nutritionist_id())
        or diet.patient_id = (select get_current_patient_id())
      )
  )
);

drop policy if exists "Nutritionists insert diet meal items" on public.diet_meal_items;
create policy "Nutritionists insert diet meal items"
on public.diet_meal_items
for insert
to authenticated
with check (
  exists (
    select 1
    from public.diet_meals meal
    join public.diets diet on diet.id = meal.diet_id
    where meal.id = diet_meal_items.meal_id
      and diet.nutritionist_id = (select get_current_nutritionist_id())
  )
);

drop policy if exists "Nutritionists update diet meal items" on public.diet_meal_items;
create policy "Nutritionists update diet meal items"
on public.diet_meal_items
for update
to authenticated
using (
  exists (
    select 1
    from public.diet_meals meal
    join public.diets diet on diet.id = meal.diet_id
    where meal.id = diet_meal_items.meal_id
      and diet.nutritionist_id = (select get_current_nutritionist_id())
  )
)
with check (
  exists (
    select 1
    from public.diet_meals meal
    join public.diets diet on diet.id = meal.diet_id
    where meal.id = diet_meal_items.meal_id
      and diet.nutritionist_id = (select get_current_nutritionist_id())
  )
);

drop policy if exists "Nutritionists delete diet meal items" on public.diet_meal_items;
create policy "Nutritionists delete diet meal items"
on public.diet_meal_items
for delete
to authenticated
using (
  exists (
    select 1
    from public.diet_meals meal
    join public.diets diet on diet.id = meal.diet_id
    where meal.id = diet_meal_items.meal_id
      and diet.nutritionist_id = (select get_current_nutritionist_id())
  )
);

grant select, insert, update, delete on public.diet_meal_items to authenticated;
grant all on public.diet_meal_items to service_role;
