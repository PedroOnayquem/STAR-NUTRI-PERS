-- Persist one isolated active task per conversation/user and serialize agent
-- turns so concurrent browser tabs cannot interleave tool results.

begin;

alter table public.ai_conversation_state
  alter column pending_action drop not null;

alter table public.ai_conversation_state
  add column if not exists state_kind text not null default 'confirmation',
  add column if not exists task_domain text,
  add column if not exists task_intent text,
  add column if not exists task_status text,
  add column if not exists task_slots jsonb not null default '{}'::jsonb,
  add column if not exists required_slots text[] not null default '{}'::text[],
  add column if not exists missing_slots text[] not null default '{}'::text[],
  add column if not exists ambiguous_slots text[] not null default '{}'::text[],
  add column if not exists allowed_tools text[] not null default '{}'::text[],
  add column if not exists last_message_id uuid,
  add column if not exists processing_message_id uuid,
  add column if not exists processing_expires_at timestamptz,
  add column if not exists state_version bigint not null default 1;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'ai_conversation_state_kind_check'
      and conrelid = 'public.ai_conversation_state'::regclass
  ) then
    alter table public.ai_conversation_state
      add constraint ai_conversation_state_kind_check
      check (state_kind in ('idle', 'task', 'confirmation'));
  end if;

  if not exists (
    select 1
    from pg_constraint
    where conname = 'ai_conversation_state_task_status_check'
      and conrelid = 'public.ai_conversation_state'::regclass
  ) then
    alter table public.ai_conversation_state
      add constraint ai_conversation_state_task_status_check
      check (
        task_status is null
        or task_status in (
          'new', 'understand', 'needs_clarification', 'waiting_user',
          'ready', 'executing', 'validating', 'completed', 'failed',
          'blocked', 'pending_confirmation'
        )
      );
  end if;
end
$$;

alter table public.ai_action_logs
  drop constraint if exists ai_action_logs_status_check;

alter table public.ai_action_logs
  add constraint ai_action_logs_status_check
  check (
    status in (
      'executed', 'skipped', 'failed', 'pending_confirmation',
      'waiting_clarification', 'blocked'
    )
  );

create or replace function public.increment_ai_conversation_state_version()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  new.state_version := old.state_version + 1;
  return new;
end;
$$;

revoke all on function public.increment_ai_conversation_state_version() from public;
revoke all on function public.increment_ai_conversation_state_version() from anon;
revoke all on function public.increment_ai_conversation_state_version() from authenticated;

drop trigger if exists ai_conversation_state_increment_version
  on public.ai_conversation_state;
create trigger ai_conversation_state_increment_version
before update on public.ai_conversation_state
for each row execute function public.increment_ai_conversation_state_version();

create or replace function public.claim_ai_conversation_turn(
  p_conversation_id uuid,
  p_user_id uuid,
  p_message_id uuid,
  p_ttl_seconds integer default 180
)
returns boolean
language plpgsql
security invoker
set search_path = ''
as $$
declare
  claimed boolean := false;
  safe_ttl integer := least(greatest(coalesce(p_ttl_seconds, 180), 30), 600);
begin
  insert into public.ai_conversation_state (
    conversation_id,
    user_id,
    pending_action,
    pending_payload,
    state_kind,
    processing_message_id,
    processing_expires_at,
    expires_at
  )
  values (
    p_conversation_id,
    p_user_id,
    null,
    '{}'::jsonb,
    'idle',
    p_message_id,
    now() + make_interval(secs => safe_ttl),
    now() + interval '30 minutes'
  )
  on conflict (conversation_id, user_id) do update
  set processing_message_id = excluded.processing_message_id,
      processing_expires_at = excluded.processing_expires_at,
      expires_at = greatest(
        public.ai_conversation_state.expires_at,
        excluded.expires_at
      )
  where public.ai_conversation_state.processing_message_id = p_message_id
     or public.ai_conversation_state.processing_expires_at is null
     or public.ai_conversation_state.processing_expires_at <= now()
  returning true into claimed;

  return coalesce(claimed, false);
end;
$$;

create or replace function public.release_ai_conversation_turn(
  p_conversation_id uuid,
  p_user_id uuid,
  p_message_id uuid
)
returns void
language sql
security invoker
set search_path = ''
as $$
  update public.ai_conversation_state
  set processing_message_id = null,
      processing_expires_at = null
  where conversation_id = p_conversation_id
    and user_id = p_user_id
    and processing_message_id = p_message_id;
$$;

revoke all on function public.claim_ai_conversation_turn(uuid, uuid, uuid, integer)
  from public, anon, authenticated;
revoke all on function public.release_ai_conversation_turn(uuid, uuid, uuid)
  from public, anon, authenticated;
grant execute on function public.claim_ai_conversation_turn(uuid, uuid, uuid, integer)
  to service_role;
grant execute on function public.release_ai_conversation_turn(uuid, uuid, uuid)
  to service_role;

-- State is backend-owned. Keeping direct client writes would let a user alter
-- allowed_tools or inject slots before a service-role agent run.
revoke all on public.ai_conversation_state from anon;
revoke all on public.ai_conversation_state from authenticated;
grant select, insert, update, delete on public.ai_conversation_state to service_role;

comment on table public.ai_conversation_state is
  'Conversation-isolated active AI task, slots, confirmations and short-lived turn lock.';
comment on column public.ai_conversation_state.task_slots is
  'Structured slots for the active task; never reconstructed solely from a short follow-up.';

commit;
