begin;

drop policy if exists "Admin atualiza nutricionistas" on public.nutritionists;
drop policy if exists "Nutricionista atualiza próprio perfil profissional" on public.nutritionists;

create policy "Usuários autorizados atualizam nutricionistas"
on public.nutritionists
for update
to authenticated
using (
  (select public.is_admin())
  or user_id = (select auth.uid())
)
with check (
  (select public.is_admin())
  or user_id = (select auth.uid())
);

notify pgrst, 'reload schema';

commit;
