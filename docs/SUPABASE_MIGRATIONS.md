# Histórico de migrations do Supabase

## Estado conhecido em 2026-08-19

O schema remoto nasceu antes do histórico SQL atualmente versionado. Por isso,
os timestamps das migrations antigas locais e remotas divergem, e a primeira
migration local já depende de tabelas, enums e helpers que ela mesma não cria.

Consequências:

- não execute `supabase db reset` esperando recriar o projeto do zero;
- não use `supabase db push` para tentar reconciliar automaticamente o legado;
- não apague nem marque migrations remotas antigas como `reverted`;
- `supabase migration fetch` deve ser executado apenas em uma cópia descartável,
  pois substitui o conteúdo de `supabase/migrations`.

As migrations novas abaixo foram aplicadas e verificadas individualmente no
remoto, e os timestamps correspondem nos dois lados:

- `20260602100000_patient_trial_access.sql`
- `20260818103558_ai_guardrail_events.sql`
- `20260819120000_harden_ai_action_scope.sql`
- `20260819124237_harden_auth_metadata_and_profile_privileges.sql`
- `20260819130000_merge_nutritionist_update_policies.sql`
- `20260819131500_gate_structured_training_by_patient_access.sql`

## Reconciliação segura

Antes de habilitar novamente um fluxo normal de `db push`:

1. recupere as migrations remotas em um diretório descartável;
2. arquive separadamente o SQL legado local e remoto;
3. gere um dump somente de schema de `public`, sem dados clínicos;
4. acrescente ao baseline os dois buckets e as policies customizadas de
   `storage.objects`;
5. represente os timestamps remotos antigos com migrations-sentinela vazias;
6. valide o baseline com `supabase db reset` em uma stack local limpa;
7. compare o resultado com o remoto e só marque o baseline como aplicado quando
   o diff de schema estiver vazio.

O dump de schema não inclui automaticamente configuração e dados do Storage.
Também não existe seed da tabela `taco_foods`; o importador continua em
`scripts/import-taco.ts` e deve ser executado explicitamente quando os dados
TACO estiverem disponíveis.
