-- Remove explicit anonymous EXECUTE grants left from earlier schema setup.

revoke execute on function public.current_user_role() from anon;
revoke execute on function public.get_current_nutritionist_id() from anon;
revoke execute on function public.get_current_patient_id() from anon;
revoke execute on function public.is_admin() from anon;
revoke execute on function public.is_nutritionist() from anon;
revoke execute on function public.is_patient() from anon;
