# Arquitetura do Star Nutri

O Star Nutri e um SaaS de gestao nutricional com IA para nutricionistas acompanharem pacientes, dietas, treinos, metricas, individualidades clinicas e conversas inteligentes. A arquitetura deve separar claramente frontend, backend, banco/auth e camada de IA, mantendo seguranca, escalabilidade e manutencao futura.

## 1. Visao Geral

```text
Frontend React + TypeScript + Tailwind
        |
        | Supabase Auth, leitura segura, realtime
        v
Supabase Auth + Postgres + RLS + Storage + Realtime
        ^
        |
Backend FastAPI
        |
        | service role somente no servidor
        v
Camada de IA ChatGPT
```

Responsabilidades principais:

- Frontend: experiencia do usuario, formularios, dashboards, chat, navegacao e estados locais.
- Supabase: autenticacao, banco Postgres, RLS, realtime, storage e auditoria.
- Backend FastAPI: regras sensiveis, integracoes protegidas, orquestracao do chat IA, logs e validacoes server-side.
- Camada de IA: montagem de contexto clinico, politicas de seguranca, chamada ao ChatGPT e persistencia das respostas.

## 2. Estrutura de Pastas do Frontend

```text
src/
  app/
    App.tsx
    providers/
      AppProviders.tsx
      AuthProvider.tsx
      ThemeProvider.tsx
      QueryProvider.tsx
    routes/
      AppRoutes.tsx
      ProtectedRoute.tsx
      RoleRoute.tsx

  assets/
    images/
    icons/

  components/
    layout/
      AppShell.tsx
      Sidebar.tsx
      Header.tsx
      MobileNav.tsx
      PageHeader.tsx
    ui/
      Button.tsx
      Input.tsx
      Textarea.tsx
      Select.tsx
      Dialog.tsx
      Drawer.tsx
      Tabs.tsx
      Badge.tsx
      Card.tsx
      Table.tsx
      EmptyState.tsx
      StatCard.tsx
      Skeleton.tsx
      Toast.tsx
    forms/
      FormField.tsx
      FormSection.tsx
      DynamicMetricFields.tsx
      FoodListField.tsx
      ExerciseListField.tsx
    patient/
      PatientCard.tsx
      PatientSummary.tsx
      PatientTimeline.tsx
      PatientAlerts.tsx
    diet/
      DietCard.tsx
      DietMealEditor.tsx
      MacroSummary.tsx
    workout/
      WorkoutCard.tsx
      ExerciseEditor.tsx
    metrics/
      MetricCard.tsx
      MetricHistory.tsx
      MetricChart.tsx
    chat/
      ChatBox.tsx
      ChatMessage.tsx
      ChatComposer.tsx
      AiContextPreview.tsx

  features/
    auth/
      pages/
        LoginPage.tsx
      hooks/
        useAuth.ts
      services/
        authService.ts
      types.ts
    admin/
      pages/
        AdminDashboardPage.tsx
        NutritionistsPage.tsx
      components/
    nutritionist/
      pages/
        NutritionistDashboardPage.tsx
        PatientsPage.tsx
        PatientDetailsPage.tsx
      components/
    patient/
      pages/
        PatientDashboardPage.tsx
        PatientMetricsPage.tsx
        PatientChatPage.tsx
      components/
    diets/
      services/
        dietService.ts
      hooks/
        useDiets.ts
      types.ts
    workouts/
      services/
        workoutService.ts
      hooks/
        useWorkouts.ts
      types.ts
    metrics/
      services/
        metricService.ts
      hooks/
        useMetrics.ts
      types.ts
    chat/
      services/
        chatService.ts
      hooks/
        useChatSession.ts
      types.ts

  hooks/
    useDebounce.ts
    useMediaQuery.ts
    usePersistedState.ts

  lib/
    supabase.ts
    apiClient.ts
    permissions.ts
    formatters.ts
    constants.ts

  stores/
    authStore.ts
    uiStore.ts

  styles/
    globals.css

  types/
    database.ts
    domain.ts
    api.ts

  main.tsx
  vite-env.d.ts
```

Diretriz:

- `components/ui`: componentes genericos, sem regra de negocio.
- `components/*`: componentes reutilizaveis por dominio.
- `features/*`: telas, hooks, services e tipos especificos de cada modulo.
- `lib/*`: clientes externos, helpers e regras compartilhadas.
- `stores/*`: estado global minimo.
- `types/*`: tipos globais e tipos gerados do Supabase.

## 3. Estrutura do Backend FastAPI

```text
backend/
  app/
    main.py

    core/
      config.py
      security.py
      logging.py
      errors.py
      rate_limit.py

    api/
      deps.py
      routes/
        health.py
        auth.py
        admin.py
        nutritionists.py
        patients.py
        diets.py
        workouts.py
        metrics.py
        chat.py
        ai.py

    schemas/
      auth.py
      profiles.py
      patients.py
      diets.py
      workouts.py
      metrics.py
      chat.py
      ai.py

    services/
      supabase_service.py
      auth_service.py
      profile_service.py
      patient_service.py
      diet_service.py
      workout_service.py
      metric_service.py
      chat_service.py
      ai_context_service.py
      openai_service.py
      audit_service.py

    repositories/
      base_repository.py
      profile_repository.py
      patient_repository.py
      diet_repository.py
      workout_repository.py
      metric_repository.py
      chat_repository.py

    policies/
      role_policy.py
      chat_policy.py
      patient_access_policy.py

    jobs/
      reminders.py
      patient_alerts.py

    tests/
      test_health.py
      test_ai_context.py
      test_permissions.py

  requirements.txt
  README.md
```

Responsabilidades:

- `api/routes`: entrada HTTP, validacao simples e resposta.
- `schemas`: Pydantic para request/response.
- `services`: regras de negocio e orquestracao.
- `repositories`: acesso ao Supabase/Postgres.
- `policies`: regras de permissao por perfil.
- `core`: configuracao, seguranca, logs e erros.

## 4. Organizacao dos Modulos

Modulos principais:

- Auth e perfil
- Admin
- Nutricionistas
- Pacientes
- Dietas
- Treinos
- Metricas principais
- Metricas variaveis
- Condicoes e individualidades
- Chat IA
- Auditoria
- Configuracoes do SaaS

Cada modulo deve ter:

- Tipos de dominio.
- Service no frontend.
- Hook de leitura/mutacao.
- Rotas/telas.
- Service no backend quando envolver regra sensivel.
- Testes das regras criticas.

## 5. Autenticacao com Supabase

Fluxo:

1. Usuario informa email e senha no frontend.
2. Frontend chama `supabase.auth.signInWithPassword`.
3. Supabase retorna session/JWT.
4. Frontend busca `profiles` pelo `user.id`.
5. App valida `is_active`.
6. App redireciona por perfil:
   - `admin` -> `/admin`
   - `nutritionist` -> `/nutritionist`
   - `patient` -> `/patient`
7. Chamadas ao Supabase usam o JWT do usuario e respeitam RLS.
8. Chamadas sensiveis ao backend enviam `Authorization: Bearer <access_token>`.
9. Backend valida o JWT e aplica regras adicionais.

Arquivos recomendados:

```text
src/features/auth/hooks/useAuth.ts
src/features/auth/services/authService.ts
src/app/providers/AuthProvider.tsx
src/app/routes/ProtectedRoute.tsx
src/app/routes/RoleRoute.tsx
backend/app/api/deps.py
backend/app/services/auth_service.py
backend/app/policies/role_policy.py
```

Regras:

- Nutricionista nao se cadastra livremente.
- Admin cria nutricionistas.
- Nutricionista cria pacientes.
- Paciente acessa apenas seus proprios dados.
- Nunca expor `SERVICE_ROLE_KEY` no frontend.

## 6. Rotas do Frontend

```text
/login

/admin
/admin/nutritionists
/admin/users
/admin/settings

/nutritionist
/nutritionist/patients
/nutritionist/patients/new
/nutritionist/patients/:patientId
/nutritionist/patients/:patientId/diet
/nutritionist/patients/:patientId/workout
/nutritionist/patients/:patientId/metrics
/nutritionist/patients/:patientId/conditions
/nutritionist/patients/:patientId/chat

/patient
/patient/diet
/patient/workout
/patient/metrics
/patient/chat
/patient/profile
```

Estrategia:

- `ProtectedRoute`: exige usuario autenticado.
- `RoleRoute`: exige perfil especifico.
- Layout por papel:
  - `AdminLayout`
  - `NutritionistLayout`
  - `PatientLayout`
- Deep links devem validar permissao antes de renderizar dados.

## 7. Rotas do Backend

```text
GET    /api/health

GET    /api/auth/me

GET    /api/admin/profiles
POST   /api/admin/nutritionists
PATCH  /api/admin/profiles/{profile_id}/status

GET    /api/nutritionists/me
GET    /api/nutritionists/patients
POST   /api/nutritionists/patients
GET    /api/nutritionists/patients/{patient_id}
PATCH  /api/nutritionists/patients/{patient_id}

POST   /api/patients/{patient_id}/diets
GET    /api/patients/{patient_id}/diets/active
PATCH  /api/diets/{diet_id}
DELETE /api/diets/{diet_id}

POST   /api/patients/{patient_id}/workouts
GET    /api/patients/{patient_id}/workouts/active
PATCH  /api/workouts/{workout_id}
DELETE /api/workouts/{workout_id}

GET    /api/patients/{patient_id}/main-metrics
POST   /api/patients/{patient_id}/main-metrics
GET    /api/patients/{patient_id}/variable-metrics
POST   /api/patients/{patient_id}/variable-metrics

POST   /api/chat/nutritionist/sessions
GET    /api/chat/nutritionist/sessions?patient_id={patient_id}
GET    /api/chat/nutritionist/sessions/{session_id}/messages
POST   /api/chat/nutritionist/send
POST   /api/chat/patient/sessions
GET    /api/chat/patient/sessions
GET    /api/chat/patient/sessions/{session_id}/messages
POST   /api/chat/patient/send
```

## 8. Gerenciamento de Estado

Camadas:

- Estado de servidor: dados vindos do Supabase/backend.
- Estado de sessao: usuario, perfil, permissao e tokens.
- Estado de UI: tema, sidebar, filtros, modais, abas.
- Estado de formulario: valores, erros, campos dinamicos.

Recomendacao:

- Usar TanStack Query para server state quando o projeto crescer.
- Usar Context API para auth/theme.
- Usar Zustand apenas se o estado global de UI ficar complexo.
- Evitar guardar dados sensiveis em `localStorage`.
- Persistir somente preferencias nao sensiveis, como tema e layout.

Exemplo de separacao:

```text
AuthProvider -> sessao, profile, login, logout
ThemeProvider -> dark/light/system
React Query -> patients, diets, workouts, metrics, chat
Local state -> filtros, dialogs, formularios em andamento
```

## 9. Integracao com Supabase

Frontend:

- Usar anon key publica.
- Usar Supabase Auth.
- Ler dados permitidos via RLS.
- Usar Realtime para chat, metricas e notificacoes.
- Gerar tipos com Supabase CLI:

```bash
npx supabase gen types typescript --project-id <project-ref> > src/types/database.ts
```

Backend:

- Usar service role apenas no servidor.
- Usar backend para:
  - Criar usuarios via admin.
  - Orquestrar IA.
  - Aplicar validacoes sensiveis.
  - Escrever logs de auditoria.
  - Proteger chamadas ao ChatGPT.

Variaveis:

```text
Frontend:
VITE_SUPABASE_URL
VITE_SUPABASE_ANON_KEY
VITE_API_BASE_URL

Backend:
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
OPENAI_API_KEY
OPENAI_BASE_URL
OPENAI_MODEL
```

## 10. Estrategia de Seguranca

Principios:

- RLS sempre habilitado em tabelas com dados de usuario.
- Frontend nunca recebe service role.
- Backend valida JWT em toda rota protegida.
- Permissao checada em dois niveis:
  - Banco via RLS.
  - Backend via policies.
- Logs de auditoria para acoes sensiveis.
- Rate limit para login, chat e endpoints de escrita.
- Sanitizacao de entradas e validacao com Pydantic/Zod.
- Erros sem vazamento de dados internos.
- Segredos apenas em `.env`, nunca commitados.

Dados sensiveis:

- Historico clinico.
- Alergias, doencas, medicamentos.
- Dietas, treinos e metricas.
- Conversas com IA.

Esses dados devem ter acesso minimo necessario.

## 11. Permissoes por Perfil

Admin:

- Ver perfis.
- Criar nutricionistas.
- Ativar/desativar usuarios.
- Ver logs agregados.
- Configurar integracoes.

Nutricionista:

- Ver apenas seus pacientes.
- Criar pacientes.
- Editar dieta, treino, metricas principais e condicoes.
- Ver metricas variaveis.
- Ver historico de chat dos seus pacientes.
- Nao acessar pacientes de outro nutricionista.

Paciente:

- Ver apenas seus dados.
- Ver dieta e treino ativos.
- Criar metricas variaveis.
- Conversar com IA.
- Nao alterar dieta, treino ou metricas principais.
- Nao acessar dados de outros pacientes.

Implementacao:

- `profiles.role` define o papel.
- `patients.nutritionist_id` limita escopo do nutricionista.
- `patients.user_id` limita escopo do paciente.
- Policies RLS devem refletir essas relacoes.

## 12. Fluxo Completo do Chat com IA ChatGPT

> A camada implementada de validação de entrada, contexto, saída, auditoria e proteção contra prompt injection está detalhada em [AI_GUARDRAILS.md](AI_GUARDRAILS.md).
> A execução real, o inventário de tools, as permissões e a confirmação estão detalhados em [AI_ACTION_TOOLS.md](AI_ACTION_TOOLS.md).

Fluxo:

1. Nutricionista ou paciente abre seu ambiente de chat.
2. Frontend usa endpoints separados:
   - Nutricionista: `nutritionist_chats` e `nutritionist_messages`.
   - Paciente: `patient_chats` e `patient_messages`.
3. Frontend assina Realtime apenas na tabela de mensagens do seu escopo.
4. Usuario envia mensagem ao backend:

```text
POST /api/chat/nutritionist/send
POST /api/chat/patient/send
Authorization: Bearer <supabase_jwt>
```

5. Backend valida:
    - Usuario autenticado.
    - Escopo do chat.
    - Ownership da conversa.
    - Nutricionista pertence ao paciente em foco no chat profissional.
    - Paciente acessa apenas seu chat pessoal.
6. Backend salva mensagem na tabela isolada do escopo.
7. Backend busca contexto atualizado:
    - Chat profissional: contexto clinico completo do paciente.
    - Chat pessoal: plano ativo e dados permitidos ao paciente.
    - Historico recente apenas da conversa do mesmo escopo.
8. Backend monta prompt seguro.
9. Orquestrador do agente avalia intencao, entidades e tools permitidas.
10. Tools simples podem executar mutacoes reais no backend; acoes criticas geram confirmacao pendente.
11. Toda tool grava `ai_action_logs` com input, resultado, estado antes/depois e usuario responsavel.
12. Backend chama ChatGPT com o resumo das acoes executadas ou bloqueadas.
13. Backend valida resposta:
     - Nao prescreve nova dieta.
     - Nao altera treino.
     - Nao diagnostica.
     - Orienta procurar profissional quando necessario.
14. Backend salva resposta da IA com `metadata.agent_actions`.
15. Frontend recebe via SSE e/ou Realtime.

Contrato de contexto:

```ts
type AiPatientContext = {
  patient: {
    name: string
    objective: string
    notes: string
  }
  diet: ActiveDiet | null
  workout: ActiveWorkout | null
  mainMetrics: Metric[]
  recentVariableMetrics: Metric[]
  conditions: HealthCondition[]
  recentMessages: ChatMessage[]
  safetyRules: string[]
}
```

Prompt base:

```text
Voce e um assistente de acompanhamento nutricional.
Voce nao substitui nutricionista ou medico.
Responda somente com base no plano cadastrado.
Nao prescreva nova dieta, novo treino, medicamento ou diagnostico.
Se houver sintomas graves, oriente atendimento medico.
Quando faltar dado, diga que o nutricionista precisa avaliar.
```

## 13. Camada de IA

```text
backend/app/services/
  chat_context_service.py
  ai_agent_service.py
  openai_service.py
  supabase_workspace_service.py

backend/app/policies/
  chat_policy.py
```

Responsabilidades:

- `chat_context_service`: busca e normaliza dados permitidos por escopo.
- `ai_agent_service`: interpreta mensagens, escolhe tools, valida risco/escopo e executa acoes auditaveis.
- `openai_service`: encapsula chamada ao ChatGPT pela API da OpenAI.
- `supabase_workspace_service`: concentra queries e mutations protegidas no Supabase.
- `chat_policy`: bloqueia pedidos inseguros e valida escopo quando a regra crescer alem do route/service.

Tools operacionais iniciais:

- `register_injury`
- `register_weight_change`
- `register_progress`
- `add_observation`
- `add_food_to_meal`
- `create_appointment`
- `request_confirmation`

O frontend pode exibir um preview do contexto, mas a fonte da verdade deve ser o backend.

## 14. APIs e Services no Frontend

```text
src/lib/apiClient.ts
src/features/patients/services/patientService.ts
src/features/diets/services/dietService.ts
src/features/workouts/services/workoutService.ts
src/features/metrics/services/metricService.ts
src/features/chat/services/chatService.ts
```

Padrao:

```ts
export async function listPatients() {}
export async function getPatient(patientId: string) {}
export async function createPatient(input: CreatePatientInput) {}
export async function updatePatient(patientId: string, input: UpdatePatientInput) {}
```

Services devem:

- Receber tipos claros.
- Nao manipular UI.
- Lidar com erros padronizados.
- Retornar DTOs normalizados para o dominio.

## 15. Formularios Complexos

Recomendacao:

- React Hook Form para controle.
- Zod para schema e validacao.
- Componentes dinamicos para:
  - Refeicoes e alimentos.
  - Exercicios.
  - Metricas principais.
  - Condicoes clinicas.
  - Medicamentos e alergias.

Estrutura:

```text
components/forms/
  FormField.tsx
  DynamicArrayField.tsx
  FoodListField.tsx
  ExerciseListField.tsx

features/diets/forms/
  DietForm.tsx
  dietSchema.ts

features/workouts/forms/
  WorkoutForm.tsx
  workoutSchema.ts
```

Boas praticas:

- Validacao client-side e server-side.
- Salvamento explicito.
- Estados de loading.
- Confirmacao para exclusao.
- Autosave apenas para rascunhos, nao para prescricoes finais.

## 16. Realtime e Chat

Usos recomendados do Supabase Realtime:

- Novas mensagens no chat.
- Atualizacao de metricas variaveis.
- Alertas de paciente.
- Notificacoes para nutricionista.

Padrao:

```text
Frontend assina:
nutritionist_messages where chat_id = current_chat
patient_messages where chat_id = current_chat

Backend escreve:
nutritionist_messages nutritionist/ai
patient_messages patient/ai

Frontend renderiza:
mensagens recebidas via realtime
```

Cuidados:

- Aplicar RLS tambem para realtime.
- Evitar enviar prompts internos para o cliente.
- Nao usar realtime como autorizacao.
- Revalidar dados apos reconexao.

## 17. Responsividade

Estrategia:

- Mobile-first.
- Sidebar fixa no desktop.
- Navegacao horizontal ou drawer no mobile.
- Tabelas com scroll horizontal e alternativa em cards.
- Formularios em uma coluna no mobile e duas colunas no desktop.
- Cards com densidade moderada para dashboards.
- Evitar textos grandes dentro de componentes compactos.

Breakpoints:

- `sm`: ajustes de formularios.
- `md`: cards em duas colunas.
- `lg`: sidebar e layout de dashboard.
- `xl`: paineis auxiliares e colunas analiticas.

## 18. Dark/Light Mode

Estrategia:

- Usar classe `.dark` no elemento `html`.
- Preferencia salva em storage local.
- Opcao futura: seguir preferencia do sistema.
- Tokens de cor centralizados no Tailwind.
- Componentes devem sempre definir estados light e dark.

Estados obrigatorios:

- Background principal.
- Cards.
- Bordas.
- Texto primario/secundario.
- Inputs.
- Botao primario/secundario.
- Hover/focus.
- Badges por status.

## 19. Componentes Reutilizaveis

Categorias:

- UI base: Button, Input, Select, Dialog, Tabs, Table, Badge.
- Layout: AppShell, Sidebar, Header, PageHeader.
- Dados: StatCard, MetricCard, EmptyState, Skeleton.
- Dominio: PatientCard, DietCard, WorkoutCard, ChatBox.
- Formularios: FormField, DynamicArrayField, FoodListField.

Regras:

- UI base nao conhece Supabase.
- Componentes de dominio recebem props tipadas.
- Services nao importam componentes.
- Hooks conectam dados e telas.
- Componentes devem ser acessiveis, responsivos e previsiveis.

## 20. Arquitetura SaaS Escalavel

Hoje o SaaS pode operar em single-tenant logico, mas deve estar pronto para multi-tenant.

Evolucao recomendada:

```text
organizations
  id
  name
  plan
  status

organization_members
  organization_id
  user_id
  role

nutritionists
  organization_id

patients
  organization_id
```

Beneficios:

- Clinicas com varios nutricionistas.
- Planos pagos por organizacao.
- Permissoes por equipe.
- Auditoria por tenant.
- Relatorios agregados.

Nao e necessario alterar agora se o MVP for um nutricionista por conta, mas essa e a direcao correta para escala.

## 21. Banco de Dados e Supabase

Tabelas atuais esperadas:

- `profiles`
- `nutritionists`
- `patients`
- `patient_health_conditions`
- `patient_main_metrics`
- `patient_variable_metrics`
- `diets`
- `diet_meals`
- `workouts`
- `workout_exercises`
- `nutritionist_chats`
- `nutritionist_messages`
- `patient_chats`
- `patient_messages`
- `activity_logs`

Possiveis tabelas futuras:

- `organizations`
- `organization_members`
- `subscriptions`
- `plans`
- `notifications`
- `patient_files`
- `ai_usage_logs`
- `ai_prompt_versions`
- `audit_logs`

Alteracoes de banco devem ser propostas antes de aplicadas, com:

- Motivo.
- Impacto.
- SQL da migracao.
- Risco.
- Plano de rollback.

## 22. Padroes de Codigo

Frontend:

- TypeScript estrito.
- Componentes pequenos.
- Props tipadas.
- Services separados da UI.
- Nomes descritivos.
- Evitar arquivos gigantes.
- Preferir composicao a abstracao prematura.
- ESLint e build obrigatorios antes de push.

Backend:

- Pydantic para entradas e saidas.
- Services com regras de negocio.
- Repositories para acesso a dados.
- Policies para permissao.
- Logs estruturados.
- Testes para IA, permissoes e acesso a dados.

Commits:

```text
feat: nova funcionalidade
fix: correcao
refactor: melhoria interna
docs: documentacao
chore: tarefas de suporte
test: testes
```

## 23. Estrategia de Manutencao

Curto prazo:

- Separar o `App.tsx` atual em `features` e `components`.
- Conectar Supabase Auth real.
- Gerar tipos do banco.
- Implementar RLS e testar acesso por perfil.
- Mover chat IA para backend.

Medio prazo:

- TanStack Query.
- React Hook Form + Zod.
- Logs de auditoria.
- Realtime no chat.
- Testes automatizados.
- CI no GitHub Actions.

Longo prazo:

- Multi-tenant com organizations.
- Assinaturas.
- Storage de exames.
- Relatorios e graficos.
- Vetores/pgvector para memoria contextual.
- App mobile.

## 24. Roadmap Tecnico Recomendado

1. Refatorar frontend para a estrutura `features`.
2. Implementar AuthProvider com Supabase Auth.
3. Implementar rotas protegidas por perfil.
4. Gerar tipos do Supabase.
5. Criar services reais para patients, diets, workouts e metrics.
6. Implementar backend do chat ChatGPT.
7. Ativar realtime em chat e metricas.
8. Criar testes de permissao.
9. Implementar auditoria.
10. Preparar CI com lint, build e testes.
