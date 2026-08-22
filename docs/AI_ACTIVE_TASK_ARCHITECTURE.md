# Estado de tarefa ativa no Chat de IA

## Problema corrigido

O histórico textual era a única memória operacional entre mensagens. Quando a IA
perguntava se um alimento era cru ou cozido, a quantidade original permanecia
somente no texto anterior. Uma continuação curta como `cozido` voltava ao modelo
sem slots estruturados e com todas as ferramentas do nutricionista disponíveis.
Mensagens antigas sobre pacientes ainda presentes na janela de contexto podiam,
então, desviar a seleção para `search_patient_by_name`.

Não havia contaminação global de serviços entre usuários: cada requisição já era
instanciada separadamente e as consultas eram filtradas por usuário e conversa.
Os defeitos eram a ausência de estado operacional, o catálogo de tools amplo e a
falta de serialização de turnos da mesma conversa. No frontend, o stream também
não registrava a sessão de origem, permitindo que a resposta visual aparecesse
na conversa selecionada depois de uma troca rápida de sessão.

## Modelo atual

Cada conversa do nutricionista pode ter uma tarefa ativa em
`ai_conversation_state`. O registro contém:

- domínio e intenção;
- status do ciclo de vida;
- slots já conhecidos;
- slots obrigatórios, ausentes ou ambíguos;
- tools permitidas para o domínio;
- mensagem que iniciou o processamento;
- lease de processamento e versão do estado.

Para TACO, os slots incluem alimento, preparo, quantidade em gramas, fonte e
nutrientes solicitados. Uma resposta curta complementa a tarefa existente sem
apagar os slots anteriores. Uma mudança explícita de assunto cria outra tarefa;
uma continuação genérica como `continue` ou `faça a consulta` não troca o domínio.

Estados principais:

- `active`: há trabalho suficiente para continuar;
- `waiting_user`: falta um esclarecimento e nenhum cálculo inseguro é feito;
- `pending_confirmation`: uma escrita autorizada aguarda confirmação;
- `completed`: o objetivo foi atendido;
- `blocked`: a execução foi negada por lock, domínio ou permissão;
- `cancelled` e `failed`: encerramentos explícitos.

Uma tarefa `completed` permanece disponível como referência contextual, mas não
como lock permanente. Apenas uma continuação referencial pode herdá-la. Evidência
e recuperação entre chats estão detalhadas em `AI_LAYERED_MEMORY.md`.

## Seleção e validação de ferramentas

O registro de tools fornece apenas o subconjunto compatível com o domínio ativo.
O filtro é aplicado antes da chamada ao modelo e novamente no backend no momento
da execução. Assim, uma resposta malformada ou uma escolha indevida do modelo não
consegue atravessar a fronteira de domínio.

Consultas nutricionais unitárias da TACO seguem um caminho determinístico:

1. extrair e persistir os slots;
2. pedir apenas o slot realmente ausente ou ambíguo;
3. resolver a entrada TACO estruturada;
4. calcular proporcionalmente no serviço/banco;
5. responder somente com o resultado e a origem recuperados.

`search_taco_foods` continua sendo descoberta de candidatos e nunca fundamenta
sozinho um valor nutricional. Correspondências ambíguas não são promovidas para
um alimento semelhante sem confirmação.

## Isolamento e concorrência

O estado usa a chave composta de conversa e usuário. As RPCs
`claim_ai_conversation_turn` e `release_ai_conversation_turn` implementam um
lease atômico por conversa. Dois envios simultâneos na mesma conversa não podem
alterar a tarefa em paralelo; o segundo recebe `conversation_turn_in_progress`.
Conversas diferentes continuam independentes.

As RPCs são `SECURITY INVOKER`, com `search_path` vazio, e podem ser executadas
somente por `service_role`. `anon` e `authenticated` não podem gravar diretamente
slots, allowed tools ou locks. O trigger de versão ajuda a detectar a evolução do
registro sem depender de estado em memória do processo.

No frontend, cada stream carrega o ID da sessão que o iniciou. Texto e ações em
andamento só são renderizados enquanto essa sessão continuar selecionada.

## Experiência de esclarecimento

Ambiguidade é exibida como `Aguardando seu esclarecimento`, não como
`Não executado`. Bloqueios de segurança usam um estado próprio. Isso separa uma
pergunta normal da IA de uma falha operacional.

## Cenário de regressão obrigatório

O E2E remoto executa:

1. `Quantas calorias tem 150g de arroz integral segundo a tebela taco?`;
2. valida que a IA pede cru/cozido e persiste `quantity_g=150`;
3. abre outra conversa e confirma que uma busca explícita de paciente fica nela;
4. retorna à primeira conversa e envia `cozido`;
5. valida resolução TACO automática, nenhuma tool de paciente e 186 kcal para
   150 g de `Arroz, integral, cozido`;
6. confirma os traces e remove usuário, conversas e estados temporários.

Além do E2E, os testes unitários cobrem continuidade de slots, troca explícita de
domínio, continuação genérica, isolamento entre conversas, bloqueio de tool fora
do domínio e concorrência na mesma conversa.
