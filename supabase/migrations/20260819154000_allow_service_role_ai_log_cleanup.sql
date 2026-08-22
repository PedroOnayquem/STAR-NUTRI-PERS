-- Audit logs stay read-only to application users. The trusted backend role
-- needs scoped deletion for administrative retention and isolated E2E cleanup.
begin;

grant delete on table public.ai_action_logs to service_role;

commit;
