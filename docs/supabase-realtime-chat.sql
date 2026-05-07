-- Star Nutri - habilitar realtime do chat
-- Revise antes de executar no SQL Editor do Supabase.
--
-- Motivo:
-- O frontend assina INSERTs em public.chat_messages para atualizar o chat em
-- tempo real. Hoje a publication supabase_realtime nao contem tabelas.

do $$
begin
  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'chat_sessions'
  ) then
    alter publication supabase_realtime add table public.chat_sessions;
  end if;

  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'chat_messages'
  ) then
    alter publication supabase_realtime add table public.chat_messages;
  end if;
end $$;
