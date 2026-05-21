-- The app now builds AI context inside the backend with explicit chat scopes.
-- Remove the old exposed context view so private clinical context is not
-- available through the public Data API surface.

drop view if exists public.patient_ai_context;

alter function public.current_user_role() set search_path = public, auth;
alter function public.get_current_nutritionist_id() set search_path = public, auth;
alter function public.get_current_patient_id() set search_path = public, auth;
alter function public.is_admin() set search_path = public, auth;
alter function public.is_nutritionist() set search_path = public, auth;
alter function public.is_patient() set search_path = public, auth;
alter function public.update_updated_at_column() set search_path = public, auth;
