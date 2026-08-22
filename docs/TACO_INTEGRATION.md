# Integração TACO

## Fonte e fidelidade

O catálogo usa a **Tabela Brasileira de Composição de Alimentos (TACO), 4ª edição ampliada e revisada, 2011**, desenvolvida e coordenada pelo NEPA/UNICAMP. A fonte oficial está na página de [publicações do NEPA](https://nepa.unicamp.br/publicacoes/) e a planilha utilizada é [Taco-4a-Edicao.xlsx](https://nepa.unicamp.br/wp-content/uploads/sites/27/2023/10/Taco-4a-Edicao.xlsx).

Checksum SHA-256 da planilha importada:

```text
a66b8ec528daeabc63bc2b015fc9bd8c6d76b941c2fc0ed93a4311d449302d14
```

Os valores da planilha são referentes a **100 g de parte comestível**. A importação usa o valor publicado/formatado na planilha, sem recalcular médias ocultas do arquivo. Os marcadores originais também são preservados:

- `Tr`: traço; o valor numérico fica `null`, não zero;
- `NA`: não aplicável;
- célula em branco: análise não solicitada, conforme a legenda da fonte;
- `*`/`ND`: não analisado ou não determinado.

Esses estados ficam em `taco_food_nutrients.value_status`, e o texto original em `source_value`.

## Estrutura

- `taco_foods`: identificação, grupo, composição principal, base de referência e origem;
- `taco_food_nutrients`: valores estruturados das três abas oficiais, incluindo ácidos graxos e aminoácidos;
- `taco_import_batches`: edição, ano, URL, arquivo, checksum e contagens da carga;
- `diet_meal_items`: mantém a referência ao alimento e o snapshot proporcional usado na dieta.

A chave idempotente `TACO:2011:<código>` impede duplicação em reimportações. A planilha não é empacotada no frontend; somente os resultados solicitados chegam ao cliente ou à IA.

## Pesquisa e cálculo

`search_taco_foods` combina nome exato normalizado, prefixo, full-text search em português com índice GIN e similaridade `pg_trgm`. A RPC devolve `match_kind`, `relevance` e `total_count`. Similaridade serve apenas para apresentar candidatos: o serviço não seleciona automaticamente um alimento ambíguo.

`calculate_taco_food_nutrients` calcula os valores proporcionalmente à quantidade solicitada usando `reference_quantity_g`. Campos sem valor na fonte continuam `null`.

Exemplo validado no banco:

```text
150 g de Arroz, integral, cozido
Energia: 186 kcal
Proteínas: 3,9 g
Carboidratos: 38,7 g
Fonte: TACO, 4ª edição ampliada e revisada (2011)
```

## IA

A IA recebe apenas os candidatos ou o alimento consultado por meio de `search_taco_foods`, `get_taco_food`, `calculate_taco_food_nutrients` e `add_taco_food_to_meal`. Uma busca ampla, como “arroz”, retorna opções e exige esclarecimento. Um nome exato ou um `food_id` resolve o item. Se não houver correspondência, a ferramenta informa ausência; o modelo não deve inventar composição nem substituir automaticamente por alimento “similar”. Os nutrientes detalhados são carregados somente para o alimento escolhido.

## Importação

1. Baixe a planilha oficial para `data/taco/Taco-4a-Edicao.xlsx` ou informe um caminho explícito.
2. Valide sem escrever: `npm run taco:validate -- data/taco/Taco-4a-Edicao.xlsx`.
3. Configure `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY` em `backend/.env`.
4. Importe: `npm run taco:import -- data/taco/Taco-4a-Edicao.xlsx`.

O importador exige as três abas oficiais e exatamente 597 alimentos. A carga grava lotes de 250 registros e pode ser repetida com segurança.

## Segurança

- RLS está ativa nas tabelas expostas;
- `anon` não lê nem altera o catálogo;
- `authenticated` tem somente `SELECT` no catálogo e nos nutrientes;
- apenas `service_role` registra lotes e altera dados da fonte;
- as RPCs são `SECURITY INVOKER`, têm limites de paginação/quantidade e execução revogada de `public`/`anon`.

## Verificação

```bash
npm run test:taco
npm run lint
npm run build
docker compose run --rm --no-deps backend python -m unittest discover -s backend/tests -v
```

A verificação remota deve confirmar 597 alimentos, 25.296 valores estruturados, 14 grupos e o checksum acima.
