-- Cover the ai_conversation_state.user_id foreign key for deletes and state cleanup.

create index if not exists ai_conversation_state_user_idx
  on public.ai_conversation_state (user_id);
