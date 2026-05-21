-- Legacy chat tables are kept only as an archive for service-role migrations.
-- No browser/authenticated role should read or write these mixed-scope tables.

drop policy if exists "Legacy chat sessions blocked" on public.chat_sessions;
drop policy if exists "Legacy chat messages blocked" on public.chat_messages;

create policy "Legacy chat sessions blocked"
on public.chat_sessions
for all
to anon, authenticated
using (false)
with check (false);

create policy "Legacy chat messages blocked"
on public.chat_messages
for all
to anon, authenticated
using (false)
with check (false);
