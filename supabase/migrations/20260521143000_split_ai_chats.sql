-- Split AI chat storage into professional nutritionist chats and private patient chats.
-- The legacy chat_sessions/chat_messages tables are intentionally left in place,
-- but their RLS policies are removed so authenticated clients can no longer read
-- mixed historical chat data through the public API.

create table if not exists public.nutritionist_chats (
  id uuid primary key default gen_random_uuid(),
  nutritionist_id uuid not null references public.nutritionists(id) on delete cascade,
  patient_id uuid not null references public.patients(id) on delete cascade,
  title text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.nutritionist_messages (
  id uuid primary key default gen_random_uuid(),
  chat_id uuid not null references public.nutritionist_chats(id) on delete cascade,
  sender public.message_sender not null,
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint nutritionist_messages_sender_check
    check (sender in ('nutritionist'::public.message_sender, 'ai'::public.message_sender))
);

create table if not exists public.patient_chats (
  id uuid primary key default gen_random_uuid(),
  patient_id uuid not null references public.patients(id) on delete cascade,
  title text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.patient_messages (
  id uuid primary key default gen_random_uuid(),
  chat_id uuid not null references public.patient_chats(id) on delete cascade,
  sender public.message_sender not null,
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint patient_messages_sender_check
    check (sender in ('patient'::public.message_sender, 'ai'::public.message_sender))
);

create index if not exists nutritionist_chats_owner_patient_idx
  on public.nutritionist_chats (nutritionist_id, patient_id, updated_at desc);
create index if not exists nutritionist_chats_patient_idx
  on public.nutritionist_chats (patient_id);
create index if not exists nutritionist_messages_chat_created_idx
  on public.nutritionist_messages (chat_id, created_at);
create index if not exists patient_chats_owner_idx
  on public.patient_chats (patient_id, updated_at desc);
create index if not exists patient_messages_chat_created_idx
  on public.patient_messages (chat_id, created_at);

alter table public.nutritionist_chats enable row level security;
alter table public.nutritionist_messages enable row level security;
alter table public.patient_chats enable row level security;
alter table public.patient_messages enable row level security;
alter table public.chat_sessions enable row level security;
alter table public.chat_messages enable row level security;

do $$
declare
  policy_to_drop record;
begin
  for policy_to_drop in
    select tablename, policyname
    from pg_policies
    where schemaname = 'public'
      and tablename in (
        'chat_sessions',
        'chat_messages',
        'nutritionist_chats',
        'nutritionist_messages',
        'patient_chats',
        'patient_messages'
      )
  loop
    execute format(
      'drop policy if exists %I on public.%I',
      policy_to_drop.policyname,
      policy_to_drop.tablename
    );
  end loop;
end $$;

create policy "Nutritionists select own professional chats"
on public.nutritionist_chats
for select
to authenticated
using (
  (select auth.uid()) is not null
  and nutritionist_id = public.get_current_nutritionist_id()
);

create policy "Nutritionists select own professional messages"
on public.nutritionist_messages
for select
to authenticated
using (
  exists (
    select 1
    from public.nutritionist_chats chat
    where chat.id = nutritionist_messages.chat_id
      and chat.nutritionist_id = public.get_current_nutritionist_id()
  )
);

create policy "Patients select own personal chats"
on public.patient_chats
for select
to authenticated
using (
  (select auth.uid()) is not null
  and patient_id = public.get_current_patient_id()
);

create policy "Patients select own personal messages"
on public.patient_messages
for select
to authenticated
using (
  exists (
    select 1
    from public.patient_chats chat
    where chat.id = patient_messages.chat_id
      and chat.patient_id = public.get_current_patient_id()
  )
);

grant select on public.nutritionist_chats to authenticated;
grant select on public.nutritionist_messages to authenticated;
grant select on public.patient_chats to authenticated;
grant select on public.patient_messages to authenticated;

insert into public.nutritionist_chats (
  id,
  nutritionist_id,
  patient_id,
  title,
  created_at,
  updated_at
)
select
  session.id,
  patient.nutritionist_id,
  session.patient_id,
  coalesce(nullif(session.title, ''), 'Conversa profissional'),
  coalesce(session.created_at, now()),
  coalesce(session.updated_at, session.created_at, now())
from public.chat_sessions session
join public.patients patient on patient.id = session.patient_id
where exists (
    select 1
    from public.chat_messages message
    where message.session_id = session.id
      and message.sender = 'nutritionist'::public.message_sender
  )
  or not exists (
    select 1
    from public.chat_messages message
    where message.session_id = session.id
  )
on conflict (id) do nothing;

insert into public.nutritionist_messages (
  id,
  chat_id,
  sender,
  content,
  metadata,
  created_at
)
select
  message.id,
  message.session_id,
  message.sender,
  message.content,
  coalesce(message.metadata, '{}'::jsonb),
  coalesce(message.created_at, now())
from public.chat_messages message
where message.sender in (
    'nutritionist'::public.message_sender,
    'ai'::public.message_sender
  )
  and exists (
    select 1
    from public.chat_messages nutritionist_message
    where nutritionist_message.session_id = message.session_id
      and nutritionist_message.sender = 'nutritionist'::public.message_sender
  )
on conflict (id) do nothing;

insert into public.patient_chats (
  id,
  patient_id,
  title,
  created_at,
  updated_at
)
select
  session.id,
  session.patient_id,
  coalesce(nullif(session.title, ''), 'Conversa pessoal'),
  coalesce(session.created_at, now()),
  coalesce(session.updated_at, session.created_at, now())
from public.chat_sessions session
where not exists (
    select 1
    from public.chat_messages message
    where message.session_id = session.id
      and message.sender = 'nutritionist'::public.message_sender
  )
  and exists (
    select 1
    from public.chat_messages message
    where message.session_id = session.id
      and message.sender = 'patient'::public.message_sender
  )
on conflict (id) do nothing;

insert into public.patient_messages (
  id,
  chat_id,
  sender,
  content,
  metadata,
  created_at
)
select
  message.id,
  message.session_id,
  message.sender,
  message.content,
  coalesce(message.metadata, '{}'::jsonb),
  coalesce(message.created_at, now())
from public.chat_messages message
where message.sender in (
    'patient'::public.message_sender,
    'ai'::public.message_sender
  )
  and not exists (
    select 1
    from public.chat_messages nutritionist_message
    where nutritionist_message.session_id = message.session_id
      and nutritionist_message.sender = 'nutritionist'::public.message_sender
  )
on conflict (id) do nothing;

do $$
begin
  if exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'chat_sessions'
  ) then
    alter publication supabase_realtime drop table public.chat_sessions;
  end if;

  if exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'chat_messages'
  ) then
    alter publication supabase_realtime drop table public.chat_messages;
  end if;

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
end $$;
