create table if not exists public.ai_conversation_memories (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null,
  user_id uuid not null references public.profiles(id) on delete cascade,
  patient_id uuid references public.patients(id) on delete cascade,
  nutritionist_id uuid references public.nutritionists(id) on delete cascade,
  chat_type text not null check (
    chat_type in ('nutritionist_professional', 'patient_personal')
  ),
  summary text not null,
  key_facts jsonb not null default '{}'::jsonb,
  last_message_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint ai_conversation_memories_unique_context
    unique (conversation_id, user_id, chat_type)
);

create index if not exists ai_conversation_memories_user_type_updated_idx
  on public.ai_conversation_memories (user_id, chat_type, updated_at desc);
create index if not exists ai_conversation_memories_patient_type_updated_idx
  on public.ai_conversation_memories (patient_id, chat_type, updated_at desc);
create index if not exists ai_conversation_memories_nutritionist_type_updated_idx
  on public.ai_conversation_memories (nutritionist_id, chat_type, updated_at desc);
create index if not exists ai_conversation_memories_conversation_idx
  on public.ai_conversation_memories (conversation_id);

drop trigger if exists ai_conversation_memories_updated_at on public.ai_conversation_memories;
create trigger ai_conversation_memories_updated_at
before update on public.ai_conversation_memories
for each row execute function public.update_updated_at_column();

alter table public.ai_conversation_memories enable row level security;

drop policy if exists "Nutricionistas veem memorias profissionais autorizadas" on public.ai_conversation_memories;
create policy "Nutricionistas veem memorias profissionais autorizadas"
on public.ai_conversation_memories
for select
to authenticated
using (
  chat_type = 'nutritionist_professional'
  and nutritionist_id = (select public.get_current_nutritionist_id())
);

drop policy if exists "Pacientes veem memorias pessoais autorizadas" on public.ai_conversation_memories;
create policy "Pacientes veem memorias pessoais autorizadas"
on public.ai_conversation_memories
for select
to authenticated
using (
  chat_type = 'patient_personal'
  and patient_id = (select public.get_current_patient_id())
);

drop policy if exists "Admins veem memorias de IA" on public.ai_conversation_memories;
create policy "Admins veem memorias de IA"
on public.ai_conversation_memories
for select
to authenticated
using ((select public.is_admin()));

grant select on public.ai_conversation_memories to authenticated;

notify pgrst, 'reload schema';
