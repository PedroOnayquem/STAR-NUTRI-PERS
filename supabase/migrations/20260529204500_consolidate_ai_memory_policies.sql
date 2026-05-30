drop policy if exists "Nutricionistas veem memorias profissionais autorizadas" on public.ai_conversation_memories;
drop policy if exists "Pacientes veem memorias pessoais autorizadas" on public.ai_conversation_memories;
drop policy if exists "Admins veem memorias de IA" on public.ai_conversation_memories;

create policy "Usuarios autorizados veem memorias de IA"
on public.ai_conversation_memories
for select
to authenticated
using (
  (
    chat_type = 'nutritionist_professional'
    and nutritionist_id = (select public.get_current_nutritionist_id())
  )
  or (
    chat_type = 'patient_personal'
    and patient_id = (select public.get_current_patient_id())
  )
  or (select public.is_admin())
);

notify pgrst, 'reload schema';
