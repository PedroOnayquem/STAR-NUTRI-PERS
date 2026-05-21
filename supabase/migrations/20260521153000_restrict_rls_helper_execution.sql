-- RLS helper functions are needed by authenticated policies, but should not be
-- executable by anonymous clients through the exposed RPC surface.

revoke execute on function public.current_user_role() from public;
revoke execute on function public.get_current_nutritionist_id() from public;
revoke execute on function public.get_current_patient_id() from public;
revoke execute on function public.is_admin() from public;
revoke execute on function public.is_nutritionist() from public;
revoke execute on function public.is_patient() from public;

grant execute on function public.current_user_role() to authenticated, service_role;
grant execute on function public.get_current_nutritionist_id() to authenticated, service_role;
grant execute on function public.get_current_patient_id() to authenticated, service_role;
grant execute on function public.is_admin() to authenticated, service_role;
grant execute on function public.is_nutritionist() to authenticated, service_role;
grant execute on function public.is_patient() to authenticated, service_role;
