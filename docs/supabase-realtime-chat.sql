-- Star Nutri - habilitar realtime do chat IA
-- Revise antes de executar no SQL Editor do Supabase.
--
-- Motivo:
-- O frontend assina INSERTs separados em public.nutritionist_messages e
-- public.patient_messages. O agente tambem publica logs e mutacoes clinicas
-- para atualizar prontuario, dieta e agenda sem refresh.
-- As tabelas antigas chat_sessions/chat_messages nao devem permanecer na
-- publication para evitar historico misturado.

do $$
begin
  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'nutritionist_messages'
  ) then
    alter publication supabase_realtime add table public.nutritionist_messages;
  end if;

  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'patient_messages'
  ) then
    alter publication supabase_realtime add table public.patient_messages;
  end if;

  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'ai_action_logs'
  ) then
    alter publication supabase_realtime add table public.ai_action_logs;
  end if;

  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'appointments'
  ) then
    alter publication supabase_realtime add table public.appointments;
  end if;

  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'patient_health_conditions'
  ) then
    alter publication supabase_realtime add table public.patient_health_conditions;
  end if;

  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'patient_variable_metrics'
  ) then
    alter publication supabase_realtime add table public.patient_variable_metrics;
  end if;

  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'diet_meals'
  ) then
    alter publication supabase_realtime add table public.diet_meals;
  end if;
end $$;
