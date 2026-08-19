begin;

-- Move the temporary-password flag to server-owned Auth metadata. Existing
-- values are preserved so this migration does not unexpectedly lock users out.
update auth.users
set raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb)
  || jsonb_build_object(
    'must_change_password',
    lower(coalesce(raw_user_meta_data ->> 'must_change_password', 'false')) = 'true'
  )
where coalesce(raw_user_meta_data, '{}'::jsonb) ? 'must_change_password'
  and not (coalesce(raw_app_meta_data, '{}'::jsonb) ? 'must_change_password');

update auth.users
set raw_user_meta_data = coalesce(raw_user_meta_data, '{}'::jsonb)
  - 'must_change_password'
  - 'role'
where coalesce(raw_user_meta_data, '{}'::jsonb)
  ?| array['must_change_password', 'role'];

-- Authenticated users only need to read their own profile through RLS. Profile
-- writes are deliberately restricted to the backend service role so role and
-- activation state cannot be self-promoted from the browser.
revoke all privileges on table public.profiles from anon, authenticated, service_role;
grant select on table public.profiles to authenticated;
grant select, insert, update, delete on table public.profiles to service_role;

-- TRUNCATE bypasses row-level security. REFERENCES and TRIGGER are also never
-- needed by browser roles. Remove these grants from every exposed table.
do $revoke_dangerous_table_privileges$
declare
  target record;
begin
  for target in
    select ns.nspname as schema_name, cls.relname as table_name
    from pg_class cls
    join pg_namespace ns on ns.oid = cls.relnamespace
    where ns.nspname = 'public'
      and cls.relkind in ('r', 'p')
  loop
    execute format(
      'revoke truncate, references, trigger on table %I.%I from anon, authenticated',
      target.schema_name,
      target.table_name
    );
  end loop;
end;
$revoke_dangerous_table_privileges$;

-- Keep a pending temporary-password session away from the Data API, Storage,
-- and Realtime until the server-owned flag has been cleared.
create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create or replace function private.password_change_complete()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select coalesce((
    select case
      when coalesce(u.raw_app_meta_data, '{}'::jsonb) ? 'must_change_password'
        then lower(coalesce(u.raw_app_meta_data ->> 'must_change_password', 'false')) <> 'true'
      else lower(coalesce(u.raw_user_meta_data ->> 'must_change_password', 'false')) <> 'true'
    end
    from auth.users u
    where u.id = (select auth.uid())
  ), false);
$$;

revoke all on function private.password_change_complete() from public, anon, authenticated;
grant usage on schema private to authenticated, service_role;
grant execute on function private.password_change_complete() to authenticated, service_role;

do $add_password_change_gate$
declare
  target record;
begin
  for target in
    select ns.nspname as schema_name, cls.relname as table_name
    from pg_class cls
    join pg_namespace ns on ns.oid = cls.relnamespace
    where (
        ns.nspname = 'public'
        or (ns.nspname = 'storage' and cls.relname = 'objects')
      )
      and cls.relkind in ('r', 'p')
      and cls.relrowsecurity
  loop
    execute format(
      'drop policy if exists %I on %I.%I',
      'Temporary password gate',
      target.schema_name,
      target.table_name
    );
    execute format(
      'create policy %I on %I.%I as restrictive for all to authenticated using ((select private.password_change_complete())) with check ((select private.password_change_complete()))',
      'Temporary password gate',
      target.schema_name,
      target.table_name
    );
  end loop;
end;
$add_password_change_gate$;

-- Harden the trial helper on installations where its earlier migration has
-- already run. The conditional keeps this migration safe on divergent legacy
-- histories where the function or trial columns do not exist yet.
do $harden_patient_access_function$
begin
  if to_regprocedure('public.patient_has_premium_access(uuid)') is not null
     and exists (
       select 1
       from information_schema.columns
       where table_schema = 'public'
         and table_name = 'patients'
         and column_name = 'access_status'
     ) then
    execute $function$
      create or replace function public.patient_has_premium_access(patient_id uuid)
      returns boolean
      language sql
      stable
      security invoker
      set search_path = ''
      as $body$
        select exists (
          select 1
          from public.patients p
          where p.id = $1
            and p.access_status in ('TRIAL', 'ACTIVE')
            and (
              p.access_status = 'ACTIVE'
              or p.trial_ends_at is null
              or p.trial_ends_at > now()
            )
            and (
              p.id = (select public.get_current_patient_id())
              or p.nutritionist_id = (select public.get_current_nutritionist_id())
              or (select public.is_admin())
            )
        );
      $body$;
    $function$;

    revoke execute on function public.patient_has_premium_access(uuid) from public, anon;
    grant execute on function public.patient_has_premium_access(uuid) to authenticated, service_role;
  end if;
end;
$harden_patient_access_function$;

-- These helpers intentionally use SECURITY DEFINER to avoid recursive RLS,
-- but every referenced object is schema-qualified and the lookup path is empty.
alter function public.current_user_role() set search_path = '';
alter function public.get_current_nutritionist_id() set search_path = '';
alter function public.get_current_patient_id() set search_path = '';
alter function public.is_admin() set search_path = '';
alter function public.is_nutritionist() set search_path = '';
alter function public.is_patient() set search_path = '';

notify pgrst, 'reload schema';

commit;
