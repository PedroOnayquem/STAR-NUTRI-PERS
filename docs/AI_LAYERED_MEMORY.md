# Memória contextual em camadas

## Causa raiz corrigida

O chat já armazenava mensagens, resumos por conversa e uma tarefa estruturada.
Entretanto, `AiTaskStateService.from_state` descartava tarefas com status
`completed`. Uma pergunta como `e se for 120g?` era interpretada sem o alimento,
a fonte e o resultado TACO do turno anterior. O extrator encontrava 120 g, mas
corretamente não inventava o alimento ausente e voltava a perguntar por ele.

A correção mantém tarefas concluídas como contexto de referência por até 30 dias,
sem mantê-las como lock operacional indiscriminado. Somente uma mensagem
referencial — por exemplo `e 200g?`, `o mesmo`, `dele` ou `qual tem mais?` — pode
herdar esse estado. Uma mensagem independente inicia uma nova interpretação.

## Camada 1: contexto imediato

As últimas mensagens da conversa continuam ordenadas e limitadas pelo nível de
raciocínio. Elas preservam a linguagem natural e permitem interpretar a pergunta
e a resposta imediatamente anteriores. Não carregam mensagens de outra sessão.

## Camada 2: estado da conversa

`ai_conversation_state` mantém, por `conversation_id + user_id`:

- domínio, intenção e status;
- slots e entidades atualmente referenciadas;
- parâmetros ausentes ou ambíguos;
- tools permitidas;
- evidência autoritativa limitada dos últimos resultados de tools;
- paciente em contexto;
- lock de processamento e versão do estado.

Quando o usuário altera somente a quantidade, os demais parâmetros são herdados.
Quando troca explicitamente o alimento, o `food_id` anterior é removido para não
associar a nova descrição à entrada antiga.

Resultados TACO bem-sucedidos guardam alimento, quantidade, nutrientes,
referência e fonte como `FACT_FROM_TOOL`. Comparações usam somente duas ou mais
evidências do mesmo `food_id`. O modelo não realiza a validação dessa identidade.

## Camada 3: memória persistente entre chats

`ai_conversation_memories` preserva resumos e fatos compactos. A coluna
`search_document` e seu índice GIN permitem busca full-text em português sem
enviar todos os chats ao modelo. A RPC `search_ai_conversation_memories` combina
relevância e recência e limita o resultado.

Toda busca exige correspondência exata de:

- usuário;
- tipo de chat;
- nutricionista;
- paciente, incluindo o caso `NULL` de chat geral.

Em chat geral, um paciente só é usado para recuperação quando o nome identifica
uma única pessoa no índice autorizado do nutricionista. Dois pacientes chamados
Pedro não são escolhidos por aproximação. Dados clínicos atuais continuam vindo
das tabelas estruturadas e das tools de leitura, não dos resumos conversacionais.

## Proveniência e conflitos

A ordem de confiança é:

1. `FACT_FROM_DATABASE`;
2. informação explícita da mensagem atual;
3. `FACT_FROM_TOOL`;
4. `FACT_FROM_CONVERSATION`;
5. `INFERENCE`;
6. `UNKNOWN`.

Resumos gerados recebem `FACT_FROM_CONVERSATION` e `authoritative=false`. Eles
podem ajudar a recuperar um assunto, mas não substituir peso, dieta, lesão ou
qualquer registro mais recente do banco. Falta ou conflito de evidência deve ser
informado, nunca preenchido por inferência.

## Paciente e referências anafóricas

O paciente selecionado na tela permanece a entidade prioritária. Em chat geral,
depois que uma tool identifica e autoriza um paciente, o ID é persistido no estado
da conversa. Uma continuação como `qual o peso dele?` reidrata o contexto pelo ID
e repete a verificação de ownership no backend antes de liberar tools de progresso.

Memória não concede permissões. Paciente, nutricionista e conta continuam sujeitos
às validações existentes, ao task lock e ao escopo das consultas Supabase.

## Auditoria e interface

`ai_action_logs` continua registrando usuário, conversa, paciente, tool,
argumentos sanitizados, resultado, erro, status e agora `duration_ms`. Os traces
permanecem no metadata da mensagem e no backend.

`ChatExperience` deixou de renderizar `agent_actions` como cards técnicos. O
usuário vê somente a resposta conversacional; `Consulta nutricional TACO
concluída` e `Confirmado pelo sistema` não aparecem mais na interface normal.

## Cenário E2E

O teste remoto executa e valida:

1. ambiguidade de arroz integral cru/cozido com 150 g preservados;
2. resposta `cozido` e cálculo de 186 kcal;
3. `e se for 120g?` com o mesmo alimento e 148,8 kcal;
4. `e 200g?` com 248 kcal;
5. `qual tem mais calorias?` usando evidência anterior, sem nova busca de paciente;
6. conversa paralela de paciente isolada;
7. traces seguros, duração e remoção dos dados temporários.
