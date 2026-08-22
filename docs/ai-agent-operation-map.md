# Star Nutri AI agent operation map

This inventory was produced from the backend routes/services, frontend mutation
services, Supabase calls and migrations on 2026-08-19. The backend remains the
authority even where a legacy screen still calls the Supabase Data API directly.

| Entity | Operations found | Existing implementation | Required permission | Agent support |
|---|---|---|---|---|
| Patient | create, update profile/objective/notes, activate, deactivate | `SupabaseUserService`, `SupabaseWorkspaceService.update_patient*` | admin creates nutritionist; owning nutritionist creates/updates/deactivates; patient can update limited own fields | read, update profile/birth date |
| Diet | create, update, activate/deactivate, duplicate, delete | frontend `clinicalDataService`; backend `SupabaseWorkspaceService` | owning nutritionist; patient read only while access is valid | atomic create, safe field update |
| Diet meal | create/upsert, update foods, delete | frontend `clinicalDataService`; backend workspace meal methods | nutritionist owning parent diet | add food/TACO food; full destructive CRUD remains UI-only |
| TACO meal item | create | frontend `tacoService`; backend workspace TACO methods | nutritionist owning parent diet | search, calculate and add |
| Workout (UI model) | create, update, activate/deactivate, delete | frontend `clinicalDataService`; backend workspace mirror methods | owning nutritionist; patient read only while access is valid | created atomically as training mirror |
| Structured training | create plan/days/exercises, append observation | backend workspace + `create_ai_training_plan` RPC | owning nutritionist; patient read gated by premium access | atomic create, confirmed atomic replacement, observation |
| Metrics/progress | create main/variable, delete; patient can add own variable metric | frontend `clinicalDataService`; backend workspace metric methods | owning nutritionist; patient limited to own variable metric | read, register weight, register arbitrary progress |
| Health conditions | create/delete, structured injury fields | frontend `clinicalDataService`; backend workspace condition methods | owning nutritionist; patient read own | read, register injury/observation |
| Appointments | create/update/cancel/delete | frontend `clinicalDataService`; backend workspace appointment methods | owning nutritionist | create |
| Nutritionist profile/images | update profile, upload/replace avatar | backend profile route/workspace service | authenticated owner | not exposed to patient agent |
| Patient imports/files | upload/import, create derived metrics, signed URL | bioimpedance and monitoring services | owning nutritionist; patient has restricted read | intentionally not exposed to agent (binary input and clinical review required) |
| Notifications | mark one/all read | frontend `clinicalDataService`, Supabase RLS | authenticated recipient | not operational patient-data tooling |
| Chat/session/memory | create sessions/messages, title, memory/state | chat/context/workspace services | authenticated actor in scoped chat | internal orchestration only |
| Auth/users | create users, change temporary password, recovery | auth/admin services | admin or authenticated self depending on operation | never exposed to the clinical agent |

## Deliberately unsupported requests

The database currently has no first-class workout-completion or measurement-set
entity. The agent must not invent one. It can record a named progress metric or an
observation when the nutritionist explicitly chooses that existing representation.
Files, account/role changes, billing/access changes and administrative operations
are not agent tools.

## Architecture boundary

`AgentToolRegistry` discovers schemas and dispatch metadata from domain modules in
`backend/app/agent_tools`. Handlers call `SupabaseWorkspaceService`, the existing
backend data/business boundary. Every write is checked again against authenticated
role, chat scope, nutritionist identity and focused patient before persistence.
High-impact tools are intercepted by registry metadata and stored as a pending
operation; a model-generated claim cannot bypass confirmation.
