# Ações reais da IA

## Arquitetura auditada

O Star Nutri usa React/Vite no frontend, FastAPI no backend e Supabase para Auth, Postgres, Storage e Realtime. O frontend envia o JWT do Supabase; o backend valida esse token em `/auth/v1/user`, busca `profiles.role` e somente então resolve o cadastro em `nutritionists` ou `patients`.

O vínculo profissional é `patients.nutritionist_id -> nutritionists.id`. Toda abertura de chat profissional passa por `resolve_nutritionist_patient`. O paciente é resolvido por `patients.user_id = auth user id`; um `patient_id` livre do navegador não define sua identidade.

A implementação reutiliza as estruturas existentes:

- identidade: `profiles`, `nutritionists`, `patients`;
- evolução: `patient_main_metrics`, `patient_variable_metrics`;
- lesões: `patient_health_conditions`;
- dieta: `diets`, `diet_meals`, `diet_meal_items`, `taco_foods`;
- treino: `workouts`, `workout_exercises`, `training_plans`, `training_days`, `training_exercises`;
- arquivos: `patient_imports`, `patient_import_files` e Storage privado;
- conversas separadas: `nutritionist_*` e `patient_*`;
- IA: `ai_conversation_memories`, `ai_conversation_state`, `ai_action_logs`, `ai_guardrail_events`.

Não existe uma API paralela. O fluxo continua em `/api/chat/nutritionist/*` e `/api/chat/patient/*`, com SSE `session`, `action`, `delta`, `done` e `error`.

## Autorização

```text
JWT -> perfil real -> role real -> chat do ator -> paciente do nutricionista
    -> allowlist por papel/escopo -> validação de ID/nome -> operação
    -> confirmação da linha gravada -> auditoria -> resposta
```

Paciente possui zero tools operacionais. Seu contexto de leitura é recarregado a cada mensagem; pedidos de persistência recebem resposta determinística antes do modelo e do executor. O executor também nega por padrão: toda tool fora da lista explícita de leitura exige ator e chat de nutricionista.

No chat profissional geral, leituras por nome são filtradas pelo `nutritionist_id` autenticado. Mutações clínicas amplas exigem paciente em foco; a correção de nascimento já existente permanece a exceção simples por nome.

## Tools do nutricionista

| Grupo | Tools |
|---|---|
| Leitura do paciente | `search_patient_by_name`, `get_patient_profile`, `get_patient_metrics`, `get_patient_conditions`, `get_patient_summary` |
| Perfil/evolução | `update_patient_profile`, `update_patient_birth_date`, `register_weight_change`, `register_progress` |
| Condições | `register_injury`, `add_observation` |
| Dieta | `create_diet_plan`, `update_diet_plan`, `add_food_to_meal`, `add_taco_food_to_meal` |
| TACO | `search_taco_foods`, `get_taco_food`, `calculate_taco_food_nutrients` |
| Treino | `create_training_plan`, `add_workout_observation` |
| Agenda | `create_appointment`, `create_patient_appointment` |
| Controle | `request_confirmation` |

As definições em `AGENT_TOOLS` têm nome, descrição e JSON Schema. O backend valida papel, escopo, paciente e campos permitidos. Erros retornam `success=false`; a resposta só pode afirmar uma alteração quando houver mutação com `status=executed`.

## Dados atuais, dietas e treinos

O contexto clínico é remontado antes de cada turno. Ao criar treino, objetivo, métricas e condições atuais entram no contexto; condições atuais viram restrições quando o modelo não fornece uma lista. O plano é salvo nas tabelas estruturadas e no modelo `workouts` consumido pela interface.

Dietas exigem refeições estruturadas. Se já houver dieta ativa, `create_diet_plan` salva a nova inativa para não substituir silenciosamente o plano atual. `update_diet_plan` altera apenas campos não destrutivos e não ativa, substitui ou exclui planos.

## Confirmação e alto impacto

- Baixo impacto: nova métrica, lesão, observação, alimento, dieta/treino adicional sem substituição.
- Alto impacto: exclusão, cancelamento, ativação que substitua plano vigente e sobrescrita integral.
- Tools destrutivas não são expostas nesta versão. `ai_conversation_state` suporta confirmação em dois turnos para ações permitidas, vinculada a conversa, usuário e paciente, com expiração de 30 minutos.

## Auditoria, RLS e privacidade

Toda tool avaliada grava `ai_action_logs` com ator, papel, nutricionista, paciente, conversa, mensagem, tool, intenção, status, sucesso, confirmação e erro. Texto clínico livre e PII são redigidos no payload de auditoria.

A migration `20260819120000_harden_ai_action_scope.sql` restringe a auditoria a administradores e ao nutricionista proprietário e exige ownership do paciente nas mutações RLS de dietas, treinos e planos estruturados. A service role permanece somente no backend.

## Testes

`backend/tests/test_ai_agent_permissions.py` cobre os 20 cenários obrigatórios: consultas e alterações do nutricionista; lesão, treino e dieta; paciente autorizado/não autorizado; chat somente leitura; tentativas de peso, treino e lesão; acesso cruzado; elevação de papel; prompt injection; manipulação de ID; falhas de tool/banco; confirmação; auditoria; e falsa alegação de sucesso. Há regressões adicionais para resposta natural e para impedir que uma leitura seja usada como prova de escrita.
