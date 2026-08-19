# Monitoramento de arquivos

O Star Nutri registra o ciclo real das importações de bioimpedância nas tabelas
existentes `patient_imports` e `patient_import_files`. A tabela append-only
`patient_import_events` guarda eventos de processamento, vínculo e uso pela IA.

## Métricas

- uploads, formatos, tamanhos, status, falhas e arquivos por lote;
- duração média calculada somente para uploads que tiveram tempo medido;
- falhas recorrentes e importações mais lentas;
- uso pela IA quando métricas com `source_import_id` entram no contexto enviado
  ao modelo. Em lotes com vários arquivos, a atribuição é feita ao lote, pois a
  proveniência histórica não identifica qual arquivo originou cada métrica;
- série diária de arquivos, falhas e usos no contexto da IA.

Registros históricos não recebem tempos fictícios. O `file_count` e o usuário
que fez o upload são preenchidos apenas a partir de relações já existentes.

## Acesso

O endpoint `GET /api/files/monitoring?days=7|30|90` aceita administrador e
nutricionista autenticados. O backend aplica o escopo do nutricionista antes de
consultar com a chave de serviço. No banco, RLS permite ao nutricionista seus
próprios pacientes/importações, ao paciente apenas registros vinculados a ele e
ao administrador a visão global. Clientes autenticados têm somente `SELECT` no
log de eventos; a escrita é exclusiva do backend (`service_role`).
