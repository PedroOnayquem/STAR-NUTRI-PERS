begin;

alter table public.ai_conversation_state
  add column if not exists task_evidence jsonb not null default '{}'::jsonb,
  add column if not exists context_entities jsonb not null default '{}'::jsonb;

alter table public.ai_action_logs
  add column if not exists duration_ms bigint;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'ai_action_logs_duration_ms_check'
      and conrelid = 'public.ai_action_logs'::regclass
  ) then
    alter table public.ai_action_logs
      add constraint ai_action_logs_duration_ms_check
      check (duration_ms is null or duration_ms >= 0);
  end if;
end
$$;

alter table public.ai_conversation_memories
  add column if not exists search_document tsvector
  generated always as (
    to_tsvector(
      'portuguese'::regconfig,
      coalesce(summary, '') || ' ' || coalesce(key_facts::text, '')
    )
  ) stored;

create index if not exists ai_conversation_memories_search_document_idx
  on public.ai_conversation_memories using gin (search_document);

create or replace function public.search_ai_conversation_memories(
  p_user_id uuid,
  p_chat_type text,
  p_patient_id uuid,
  p_nutritionist_id uuid,
  p_query text,
  p_limit integer default 6
)
returns setof public.ai_conversation_memories
language sql
stable
security invoker
set search_path = ''
as $$
  select memory.*
  from public.ai_conversation_memories as memory
  where memory.user_id = p_user_id
    and memory.chat_type = p_chat_type
    and memory.patient_id is not distinct from p_patient_id
    and memory.nutritionist_id is not distinct from p_nutritionist_id
    and nullif(btrim(p_query), '') is not null
    and memory.search_document @@ websearch_to_tsquery(
      'portuguese'::regconfig,
      p_query
    )
  order by
    ts_rank(
      memory.search_document,
      websearch_to_tsquery('portuguese'::regconfig, p_query)
    ) desc,
    memory.last_message_at desc nulls last,
    memory.updated_at desc
  limit least(greatest(coalesce(p_limit, 6), 1), 12);
$$;

revoke all on function public.search_ai_conversation_memories(
  uuid, text, uuid, uuid, text, integer
) from public, anon, authenticated;
grant execute on function public.search_ai_conversation_memories(
  uuid, text, uuid, uuid, text, integer
) to service_role;

comment on column public.ai_conversation_state.task_evidence is
  'Bounded authoritative tool evidence retained for contextual follow-up turns.';
comment on column public.ai_conversation_state.context_entities is
  'Conversation-scoped entity identifiers such as the currently referenced patient.';
comment on column public.ai_action_logs.duration_ms is
  'Backend-measured tool or agent-run duration in milliseconds.';

notify pgrst, 'reload schema';

commit;
