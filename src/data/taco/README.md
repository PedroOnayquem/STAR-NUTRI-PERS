# TACO

Coloque aqui o arquivo oficial da Tabela Brasileira de Composição de Alimentos.

Formatos aceitos:

- CSV
- XLS
- XLSX

Caminhos padrão:

```bash
src/data/taco/taco.csv
src/data/taco/taco.xlsx
src/data/taco/taco.xls
```

Depois de aplicar as migrations no Supabase, execute:

```bash
npx tsx scripts/import-taco.ts
```

Ou informe o caminho manualmente:

```bash
npx tsx scripts/import-taco.ts src/data/taco/taco.xlsx
npx tsx scripts/import-taco.ts src/data/taco/taco.xls
npx tsx scripts/import-taco.ts src/data/taco/taco.csv
```

O script detecta a linha de cabeçalho, normaliza nomes, converte vírgula
decimal, trata campos ausentes como `null` e evita duplicidades usando `code`
ou, quando não houver código, `normalized_name`.
