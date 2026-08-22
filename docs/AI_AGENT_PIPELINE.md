# Pipeline operacional da IA

## Diagnóstico do comportamento anterior

O agente já possuía um loop de até 12 chamadas e conseguia executar mais de uma tool. O problema principal estava depois desse loop: quando qualquer ação era registrada, a rota `_stream_chat_response` chamava `_answer_from_agent_actions` e devolvia diretamente o `summary` da ação. A síntese final pelo modelo era ignorada.

Por isso, `search_taco_foods("arroz")` resultava em “10 alimentos encontrados” e a aplicação tratava essa busca como resposta completa. A tool não era incapaz de retornar dados; o runtime confundia uma etapa intermediária bem-sucedida com o objetivo final do usuário.

Também havia três fragilidades relacionadas:

- a descrição de `search_taco_foods` não deixava explícito que ela apenas descobre candidatos;
- números presentes em resultados ambíguos de busca podiam entrar no conjunto de grounding da validação de saída;
- não existia um resultado único e estruturado para resolver alimento, confiança, quantidade, cálculo e fonte.

## Pipeline atual

O fluxo agora segue:

1. **Entender:** o orquestrador usa a mensagem e o histórico para identificar o resultado final, entidades e parâmetros.
2. **Buscar:** consulta a fonte authoritative adequada — TACO para composição e banco Star Nutri para dados do paciente.
3. **Analisar:** classifica a correspondência como `exact`, `probable`, `ambiguous` ou `not_found`.
4. **Calcular:** conversões nutricionais são executadas deterministicamente no banco para a quantidade em gramas.
5. **Validar:** o guardrail confere se todos os números da resposta existem em uma leitura/cálculo authoritative ou em um total determinístico desses resultados.
6. **Agir:** escritas usam as tools autorizadas e só são confirmadas após sucesso real do banco.
7. **Responder:** a síntese responde ao objetivo do usuário, não ao nome ou ao resumo da tool.

Uma ação intermediária não encerra mais a resposta. O atalho determinístico ficou restrito a confirmação pendente, cancelamento de estado e falha do próprio orquestrador.

## Tools TACO

### `resolve_taco_nutrition` — nova

É a tool preferencial para perguntas sobre calorias, macros ou nutrientes. Ela recebe alimento, quantidade e nutrientes solicitados e retorna:

- `purpose: complete_nutrition_lookup`;
- `resolution`;
- entrada TACO selecionada quando segura;
- candidatos quando ambígua;
- `quantity_g`;
- nutrientes calculados;
- quantidade e base de referência;
- fórmula de conversão;
- fonte, edição, ano e URL.

### `search_taco_foods` — descrição revisada

Serve apenas para localizar candidatos. Não é uma resposta nutricional e não autoriza números na resposta final.

### `get_taco_food` e `calculate_taco_food_nutrients` — descrições revisadas

Continuam disponíveis para fluxos em que uma entrada já está identificada. O novo resolver é preferido para linguagem natural porque reúne resolução conservadora e cálculo.

## Confiança e ambiguidade

- `exact`: ID informado ou uma correspondência exata única;
- `probable`: somente um candidato ou liderança de relevância suficientemente clara;
- `ambiguous`: vários candidatos plausíveis sem vantagem segura;
- `not_found`: nenhuma entrada adequada.

`exact` e `probable` podem ser calculados. `ambiguous` retorna poucas opções e exige esclarecimento. `not_found` informa ausência. Similaridade nunca é silenciosamente promovida a fato.

No catálogo real, “arroz” é ambíguo porque inclui integral/cozido, integral/cru, tipo 1/cozido, tipo 1/cru, tipo 2 e preparações diferentes. O sistema não escolhe uma dessas entradas arbitrariamente. A conversa testada foi:

1. “Quantas calorias tem 150g de arroz segundo a tabela TACO?”
2. IA pede o tipo/preparo.
3. “Considere arroz tipo 1 cozido.”
4. IA mantém os 150 g e responde 192 kcal segundo a TACO.

Uma pergunta já específica — “Quantas calorias tem 150g de arroz tipo 1 cozido segundo a TACO?” — é respondida em uma etapa com 192 kcal.

## Anti-alucinação

O guardrail de saída agora aceita números nutricionais apenas de:

- dieta autorizada presente no contexto;
- `get_taco_food`;
- `calculate_taco_food_nutrients`;
- `resolve_taco_nutrition` com resolução segura;
- alimento TACO realmente adicionado a uma refeição;
- soma determinística, por nutriente, de dois ou mais resultados authoritative.

Resultados de `search_taco_foods` não fundamentam números, pois podem conter várias preparações incompatíveis. Todas as ocorrências de valores nutricionais na resposta são verificadas, não apenas a primeira. Respostas baseadas em TACO precisam identificar a fonte.

Para pacientes, peso, lesões, condições, dietas e treinos precisam vir das tools de leitura do banco. Resultado vazio é apresentado como ausência de registro. Uma sugestão gerada pela IA não pode ser apresentada como dado cadastrado, e uma escrita só pode ser confirmada com `success=true` e `status=executed`.

## Contexto e linguagem natural

O histórico é enviado ao orquestrador. Assim, referências como “e em 150g?” podem reutilizar um alimento explicitamente estabelecido na conversa. As descrições das tools e o prompt foram escritos por objetivo, não como mapa rígido de palavras, permitindo variações de ordem, abreviações e erros de digitação.

## Observabilidade segura

Cada tool continua gerando um registro em `ai_action_logs` com intenção, argumentos sanitizados, resultado, status e código de erro. Ao final, `agent_run` registra:

- intenções identificadas;
- entidades e parâmetros utilizados;
- sequência e status das tools;
- decisão final (`answered`, `clarification_required`, `confirmation_required` ou `failed_safely`);
- resultado do guardrail;
- hashes da mensagem e da resposta.

A mensagem original não é duplicada no trace. O `message_id` aponta para a mensagem autorizada na tabela de chat; isso permite diagnóstico sem copiar texto clínico, e-mails ou outros dados sensíveis para um segundo log. Tokens, senhas e chaves nunca são registrados.

## Testes

A suíte automatizada cobre:

- cálculo de 150 g a partir da base de 100 g;
- alimento exato, provável, ambíguo e inexistente;
- busca isolada sem poder fundamentar kcal;
- duas consultas TACO na mesma pergunta;
- total determinístico de dois alimentos;
- histórico com referência contextual;
- erro de digitação;
- ausência de peso e lesão sem invenção;
- trace seguro sem cópia da mensagem original;
- confirmação e falha de escritas já cobertas pela suíte operacional.

Os scripts de avaliação são:

- `backend/scripts/evaluate_agent_pipeline.py`: OpenAI real + TACO remota, somente leitura;
- `backend/scripts/real_taco_chat_e2e.py`: FastAPI/SSE real com usuário temporário e limpeza obrigatória.

Não foi necessária migration: as tabelas TACO, RPC de cálculo e `ai_action_logs` já suportavam os dados estruturados e o trace. A mudança é de orquestração, serviços e validação.
