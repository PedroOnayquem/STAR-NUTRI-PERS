# Guardrails da IA do Star Nutri

## Arquitetura analisada

O chat continua usando a arquitetura existente: React envia uma mensagem autenticada ao FastAPI, o backend valida o JWT no Supabase Auth, resolve o perfil e o vínculo com o paciente, monta o contexto, executa tools autorizadas, chama a API de IA e persiste a conversa no Supabase.

Componentes principais:

- `src/features/chat/services/chatService.ts`: envia mensagens e interpreta eventos SSE (`session`, `action`, `delta`, `done`, `error`).
- `backend/app/api/routes/chat.py`: orquestra sessão, mensagem, contexto, memória, agente, geração e persistência.
- `backend/app/services/chat_context_service.py`: separa o contexto profissional do contexto pessoal, limita histórico/métricas por nível de raciocínio e mantém memórias resumidas.
- `backend/app/services/ai_agent_service.py`: classifica intenções operacionais, limita tools por papel/escopo, valida o paciente em foco e registra ações.
- `backend/app/services/openai_service.py`: encapsula Chat Completions, streaming, tools e respostas JSON.
- `backend/app/services/supabase_workspace_service.py`: valida identidade, papel e ownership antes de ler ou alterar dados usando a service role somente no servidor.
- `backend/app/services/bioimpedance_import_service.py`: extrai arquivos, faz OCR, normaliza campos e vincula métricas à importação de origem.

### Contexto e isolamento

O nutricionista só recebe contexto de um paciente quando `patients.nutritionist_id` corresponde ao cadastro profissional autenticado. No chat geral, não existe prontuário em foco; buscas por nome são limitadas ao workspace do próprio nutricionista.

O paciente é resolvido exclusivamente por `patients.user_id = usuário autenticado`. Seu prompt pessoal contém plano ativo, treino ativo, métricas permitidas e fontes documentais vinculadas. Notas clínicas privadas e análises profissionais não entram nesse contexto.

Chats e memórias permanecem separados em:

- `nutritionist_chats` / `nutritionist_messages` / memória `nutritionist_professional`;
- `patient_chats` / `patient_messages` / memória `patient_personal`.

RLS oferece defesa em profundidade para leituras pelo Data API. As operações privilegiadas continuam no backend, depois de autorização explícita; nenhuma service role key ou chave da OpenAI é enviada ao frontend.

### Documentos

Arquivos de bioimpedância são privados, extraídos e normalizados no backend. O chat recebe apenas uma visão compacta das fontes autorizadas: identificador, nome, tipo, status, data, campos extraídos, avisos e confiança. Caminhos privados e conteúdo bruto do arquivo não são colocados no prompt do chat.

Valores extraídos pela IA agora precisam aparecer no texto OCR/PDF antes de serem aceitos pela normalização. Instruções contidas no documento são tratadas como dados não confiáveis e não podem redefinir a tarefa de OCR ou extração.

## Posição dos Guardrails no fluxo

```text
Frontend + JWT
      |
      v
Autenticação e autorização do workspace
      |
      v
Validação do contexto (papel, chat, paciente, nutricionista)
      |
      v
Classificação determinística da entrada
      |---- bloqueio seguro -> resposta natural + evento de segurança
      v
Histórico saneado + contexto autorizado delimitado como dados
      |
      v
Agente de tools com allowlist por papel e validação do paciente em foco
      |
      v
Provedor de IA (segredos somente no backend)
      |
      v
Resposta completa em buffer -> validação de saída
      |---- retenção/redação -> resposta segura + evento de segurança
      v
Persistência + SSE para o frontend + atualização da memória
```

## Camadas implementadas

### 1. Validação de contexto e controle de acesso

`AiGuardrailService.evaluate_context` confirma novamente que:

- o papel autenticado corresponde ao endpoint (`nutritionist` ou `patient`);
- o chat pessoal pertence ao paciente autenticado;
- o chat profissional pertence ao nutricionista autenticado;
- o paciente no contexto é o mesmo paciente do chat.

Essa validação acontece antes de qualquer chamada ao provedor ou execução de tool. Ela complementa, sem substituir, as checagens existentes do repository/service e o RLS.

### 2. Classificação de entrada

`AiGuardrailService.evaluate_input` diferencia:

- conversa normal;
- pergunta nutricional;
- consulta de dados do paciente;
- pedido fora do escopo;
- pedido perigoso para a saúde;
- acesso não autorizado a outro paciente;
- prompt injection;
- extração de prompt ou informação interna.

A decisão de segurança não depende do próprio modelo. Pedidos legítimos seguem normalmente. Bloqueios retornam texto educado e específico, sem chamar tools ou a OpenAI.

### 3. Proteção contra prompt injection indireto

- A mensagem atual não é mais interpolada dentro da mensagem `developer`; ela é enviada somente com papel `user`.
- O histórico é enviado com papéis `user`/`assistant`, e mensagens antigas que contenham padrões de injection ou extração são omitidas do contexto.
- Contexto, notas, memória e documentos ficam dentro de blocos de dados com regra explícita para nunca executar instruções encontradas nesses campos.
- O prompt do agente de tools aplica a mesma separação antes de decidir ações reais.
- A memória não deve resumir ou preservar prompts, credenciais ou pedidos de elevação de acesso.

### 4. Tools e ações

Pacientes não recebem tools operacionais: o chat pessoal é estritamente somente leitura e usa contexto autorizado recarregado do banco. Nutricionistas usam as tools profissionais; o chat profissional geral mantém um conjunto reduzido. IDs e nomes gerados pelo modelo são comparados ao paciente em foco, e consultas gerais por nome ficam limitadas ao `nutritionist_id` autenticado. O executor trata por padrão toda tool fora da allowlist explícita de leitura como mutação exclusiva do nutricionista.

Uma resposta não pode afirmar que cadastrou, atualizou, agendou ou removeu algo sem uma ação registrada como `executed` e `success=true`.

### 5. Validação de saída

Antes do primeiro `delta`, a resposta completa é validada para detectar:

- credenciais, tokens e marcadores de prompt interno;
- UUIDs fora do contexto autorizado;
- referência a outros pacientes no chat pessoal;
- alegação de ação não executada;
- afirmação sobre exame/arquivo inexistente no contexto;
- medida específica do paciente que não aparece nos dados autorizados;
- valor nutricional exato sem correspondência em dieta ou resultado real de tool.

Se a saída falhar, o texto original não é enviado. O usuário recebe uma substituição natural e o evento é auditado. O buffering aumenta um pouco a latência percebida, mas impede vazamento parcial por streaming.

### 6. Erros do provedor

Chamadas à OpenAI agora têm timeouts finitos e erros públicos genéricos. Corpo bruto de erro, chave, prompt e detalhes do provedor não são devolvidos ao frontend. Logs técnicos guardam apenas status, request ID e modelo.

## Auditoria e métricas

A migration `20260818103558_ai_guardrail_events.sql` cria `public.ai_guardrail_events` com RLS. O backend registra estágio, categoria, ação, severidade, regras acionadas e hash SHA-256. A mensagem completa e o trecho clínico não são duplicados no evento.

Somente administradores autenticados podem ler eventos pela política RLS. Clientes autenticados não podem inserir, atualizar ou apagar. A service role tem apenas `select` e `insert` nessa tabela.

Métricas administrativas:

```http
GET /api/admin/ai-guardrails/metrics?days=30
Authorization: Bearer <supabase_jwt>
```

Períodos permitidos: 7, 30 e 90 dias. A resposta agrega bloqueios, conclusões seguras, saídas retidas, falhas do provedor, categorias, estágios e severidades. O endpoint retorna no máximo 5.000 eventos por janela e informa quando o resultado foi truncado.

## Testes

Os testes cobrem:

1. prompt injection;
2. tentativa de acessar outro paciente;
3. solicitação fora do escopo;
4. pergunta nutricional normal;
5. uso legítimo dos dados do próprio paciente;
6. tentativa de extrair prompt interno;
7. incompatibilidade entre papel e contexto;
8. saída com medida inventada;
9. injection persistida no histórico;
10. valor inventado na extração de arquivo.

Execução:

```bash
python -m unittest discover -s backend/tests -v
```

## Operação e evolução

- Aplicar a migration antes de publicar o backend, pois os eventos usam o Data API e exigem grant explícito.
- Monitorar falsos positivos por categoria e regra, sem afrouxar autorização.
- Expandir padrões com testes de regressão sempre que surgir um novo ataque real.
- Valores nutricionais gerais exatos sem uma fonte conectada são retidos de forma conservadora. Uma futura base curada de referências pode ser adicionada como nova fonte de grounding sem trocar a arquitetura.
- Para consistência de produção, considerar configurar `OPENAI_MODEL` com um snapshot compatível em vez de depender permanentemente de um alias mutável; isso é uma decisão operacional separada destes guardrails.
