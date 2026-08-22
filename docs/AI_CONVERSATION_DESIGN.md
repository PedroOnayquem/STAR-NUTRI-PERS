# Experiência conversacional da IA

## Fluxo analisado

O chat salva a mensagem do usuário, executa os guardrails determinísticos de entrada, carrega o histórico autorizado e a memória do mesmo escopo, executa as ferramentas permitidas e só então gera a resposta. A saída passa novamente por guardrails determinísticos antes de ser persistida. As mudanças conversacionais não removem nem flexibilizam nenhuma dessas etapas.

Há dois contextos separados:

- chat pessoal do paciente, sempre somente leitura;
- chat profissional do nutricionista, com ferramentas autorizadas pelo backend e confirmação para ações de maior impacto.

## Personalidade e adaptação

A identidade é sempre a de assistente de IA do Star Nutri, sem fingir ser nutricionista, médico ou pessoa real. O contrato de conversa usa decisões concretas de escrita:

- português brasileiro natural e vocabulário adequado ao público;
- resposta curta para perguntas simples e mensagens casuais;
- detalhes, listas ou tabelas somente quando forem úteis ou pedidos;
- reconhecimento breve e sem julgamento em relatos emocionais;
- reformulação simples quando houver sinal de dúvida;
- uma pergunta focada quando faltar informação indispensável;
- recusas naturais, com limite, motivo essencial e alternativa segura;
- continuidade sem repetir saudações, alertas ou explicações recentes.

O nível de raciocínio controla quanto contexto é verificado, não o comprimento obrigatório da resposta. Segurança e precisão continuam acima das escolhas de estilo.

## Memória com custo controlado

O backend pode consultar até dez conversas recentes dentro do escopo autorizado, mas envia ao modelo no máximo três:

1. a conversa atual;
2. até duas conversas anteriores com sobreposição temática relevante à mensagem atual.

A seleção é local e determinística. Ela normaliza acentos, remove palavras comuns e pontua a sobreposição entre a mensagem atual e título, resumo e fatos-chave. Memórias irrelevantes não são incluídas apenas para preencher o limite. As ações enviadas também ficam limitadas às conversas selecionadas.

O resumo persistido continua compacto e agora diferencia fatos estáveis, preferências de comunicação explicitamente sustentadas, objetivos, decisões, orientações já dadas e pendências. Conversa casual, inferências emocionais e instruções contidas em dados não devem virar memória.

## Controle de repetição

O histórico recente permanece a fonte principal para continuidade. O prompt orienta o modelo a não recitar a memória e a usar `orientacoes_ja_dadas` apenas para evitar repetição. Correções, pedidos explícitos de repetição e alertas de segurança têm precedência.

## Cenários de avaliação

Os testes simulam, entre outros casos:

- “Hoje eu saí da dieta 😔”: acolhimento breve, sem culpa, seguido de próximo passo útil;
- “Não entendi o que é carboidrato”: reformulação simples com exemplo curto;
- pergunta nutricional ambígua: uma pergunta focada, sem inventar dados;
- continuação de assunto: memória atual mais apenas conversas anteriores relevantes;
- tentativa de trocar identidade ou regras: envelope de segurança preservado.

Esses testes verificam o contrato e a montagem de contexto de forma determinística. A qualidade final do modelo deve ser acompanhada periodicamente com uma amostra anonimizada de conversas e rubricas na ordem: segurança, precisão, contexto e naturalidade.

Uma avaliação opcional com o provedor real está em `backend/scripts/evaluate_conversation.py`. Ela usa somente um perfil sintético, não acessa o Supabase e verifica acolhimento, reformulação de dúvida, esclarecimento de ambiguidade e identidade da IA. Execute-a apenas em ambiente autorizado com `OPENAI_API_KEY` configurada.
