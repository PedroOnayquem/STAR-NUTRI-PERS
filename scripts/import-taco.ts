import { createClient } from '@supabase/supabase-js'
import { existsSync, readFileSync } from 'node:fs'
import { extname, resolve } from 'node:path'
import * as XLSX from 'xlsx'

type TacoFoodInput = {
  ash_g: number | null
  calcium_mg: number | null
  carbohydrate_g: number | null
  category: string | null
  cholesterol_mg: number | null
  code: string | null
  copper_mg: number | null
  energy_kcal: number | null
  energy_kj: number | null
  fiber_g: number | null
  iron_mg: number | null
  lipid_g: number | null
  magnesium_mg: number | null
  manganese_mg: number | null
  moisture_g: number | null
  name: string
  niacin_mg: number | null
  normalized_name: string
  phosphorus_mg: number | null
  potassium_mg: number | null
  protein_g: number | null
  pyridoxine_mg: number | null
  rae_mcg: number | null
  re_mcg: number | null
  retinol_mcg: number | null
  riboflavin_mg: number | null
  search_name: string
  sodium_mg: number | null
  source: 'TACO'
  thiamine_mg: number | null
  vitamin_c_mg: number | null
  zinc_mg: number | null
}

type TacoMappedField = keyof Omit<TacoFoodInput, 'normalized_name' | 'search_name' | 'source'>
type HeaderIndex = Record<TacoMappedField, number | null>
type TabularSource = {
  rows: string[][]
  sourceName: string
}
type ParsedFoods = {
  duplicateRows: number
  foods: TacoFoodInput[]
  ignoredRows: number
  sourceCount: number
}
type UpsertSummary = {
  inserted: number
  updated: number
}

const DEFAULT_INPUTS = [
  'src/data/taco/taco.csv',
  'src/data/taco/taco.xlsx',
  'src/data/taco/taco.xls',
]
const BATCH_SIZE = 250
const SUPPORTED_EXTENSIONS = new Set(['.csv', '.xls', '.xlsx'])
const CORE_NUTRIENT_FIELDS: TacoMappedField[] = [
  'energy_kcal',
  'protein_g',
  'carbohydrate_g',
  'lipid_g',
]

const FIELD_ALIASES: Record<TacoMappedField, string[]> = {
  ash_g: ['cinzas', 'ash'],
  calcium_mg: ['calcio', 'calcium'],
  carbohydrate_g: ['carboidrato', 'carboidratos', 'carbohydrate', 'cho'],
  category: ['categoria', 'grupo', 'group'],
  cholesterol_mg: ['colesterol', 'cholesterol'],
  code: ['codigo', 'cod', 'code', 'numero do alimento', 'n do alimento'],
  copper_mg: ['cobre', 'copper'],
  energy_kcal: ['energia kcal', 'kcal', 'calorias', 'energy kcal'],
  energy_kj: ['energia kj', 'kj', 'energy kj'],
  fiber_g: ['fibra alimentar', 'fibra', 'fiber'],
  iron_mg: ['ferro', 'iron'],
  lipid_g: ['lipideos', 'lipidios', 'gordura', 'gorduras', 'lipids', 'fat'],
  magnesium_mg: ['magnesio', 'magnesium'],
  manganese_mg: ['manganes', 'manganese'],
  moisture_g: ['umidade', 'moisture'],
  name: ['descricao dos alimentos', 'descrição dos alimentos', 'alimento', 'nome', 'description', 'food'],
  niacin_mg: ['niacina', 'niacin'],
  phosphorus_mg: ['fosforo', 'phosphorus'],
  potassium_mg: ['potassio', 'potassium'],
  protein_g: ['proteina', 'proteinas', 'protein'],
  pyridoxine_mg: ['piridoxina', 'vitamina b6', 'pyridoxine'],
  rae_mcg: ['rae'],
  re_mcg: ['re'],
  retinol_mcg: ['retinol'],
  riboflavin_mg: ['riboflavina', 'vitamina b2', 'riboflavin'],
  sodium_mg: ['sodio', 'sodium'],
  thiamine_mg: ['tiamina', 'vitamina b1', 'thiamine'],
  vitamin_c_mg: ['vitamina c', 'ascorbico', 'ascorbic'],
  zinc_mg: ['zinco', 'zinc'],
}

loadDotEnv('.env')
loadDotEnv('backend/.env')

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error)
  process.exit(1)
})

async function main() {
  const inputPath = resolveInputPath(process.argv[2])
  const supabaseUrl = process.env.SUPABASE_URL || process.env.VITE_SUPABASE_URL
  const serviceRoleKey =
    process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_SERVICE_KEY

  if (!supabaseUrl || !serviceRoleKey) {
    throw new Error('Defina SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY antes de importar a TACO.')
  }

  const sources = readTabularSources(inputPath)
  const parsed = parseFoods(sources)

  if (!parsed.foods.length) {
    throw new Error('Nenhum alimento válido foi encontrado no arquivo TACO.')
  }

  const supabase = createClient(supabaseUrl, serviceRoleKey, {
    auth: { persistSession: false },
  })
  const withCode = parsed.foods.filter((food) => food.code)
  const withoutCode = parsed.foods.filter((food) => !food.code)

  const codeSummary = await upsertFoodsByKey(supabase, withCode, 'code')
  const nameSummary = await upsertFoodsByKey(supabase, withoutCode, 'normalized_name')
  const insertedOrUpdated =
    codeSummary.inserted + codeSummary.updated + nameSummary.inserted + nameSummary.updated

  console.log('Importação concluída.')
  console.log(`Arquivo: ${inputPath}`)
  console.log(`Fontes lidas: ${parsed.sourceCount}`)
  console.log(`Alimentos processados: ${parsed.foods.length}`)
  console.log(`Inseridos/atualizados: ${insertedOrUpdated}`)
  console.log(`Ignorados: ${parsed.ignoredRows + parsed.duplicateRows}`)
  console.log('Erros: 0')
}

function resolveInputPath(inputArg: string | undefined) {
  if (inputArg) {
    const inputPath = resolve(inputArg)
    assertSupportedFile(inputPath)
    if (!existsSync(inputPath)) {
      throw new Error(`Arquivo TACO não encontrado em ${inputPath}.`)
    }
    return inputPath
  }

  const found = DEFAULT_INPUTS.map((path) => resolve(path)).find((path) => existsSync(path))
  if (!found) {
    throw new Error(
      'Nenhum arquivo TACO encontrado. Coloque taco.csv, taco.xls ou taco.xlsx em src/data/taco/',
    )
  }
  assertSupportedFile(found)
  return found
}

function assertSupportedFile(inputPath: string) {
  const extension = extname(inputPath).toLowerCase()
  if (!SUPPORTED_EXTENSIONS.has(extension)) {
    throw new Error(`Formato TACO não suportado: ${extension || 'sem extensão'}. Use CSV, XLS ou XLSX.`)
  }
}

function readTabularSources(inputPath: string): TabularSource[] {
  const extension = extname(inputPath).toLowerCase()
  if (extension === '.csv') {
    return [{ rows: parseCsv(readFileSync(inputPath, 'utf8')), sourceName: inputPath }]
  }

  const workbook = XLSX.readFile(inputPath, {
    cellDates: false,
    raw: false,
  })

  return workbook.SheetNames.map((sheetName) => {
    const worksheet = workbook.Sheets[sheetName]
    const rows = XLSX.utils.sheet_to_json<unknown[]>(worksheet, {
      blankrows: false,
      defval: '',
      header: 1,
      raw: false,
    })

    return {
      rows: rows.map((row) => row.map(cellText)),
      sourceName: sheetName,
    }
  }).filter((source) => source.rows.some((row) => row.some((cell) => cell.trim())))
}

function parseFoods(sources: TabularSource[]): ParsedFoods {
  const allFoods: TacoFoodInput[] = []
  let ignoredRows = 0
  let sourcesWithHeader = 0

  for (const source of sources) {
    const header = findHeader(source.rows)
    if (!header) continue

    sourcesWithHeader += 1
    for (const row of source.rows.slice(header.dataStartIndex)) {
      const food = mapRecord(row, header.headerIndex, source.sourceName)
      if (food) allFoods.push(food)
      else if (row.some((cell) => cell.trim())) ignoredRows += 1
    }
  }

  if (!sourcesWithHeader) {
    throw new Error(
      'Não encontrei colunas mínimas no arquivo TACO. É necessário haver coluna de nome e ao menos uma coluna de energia, proteína, carboidrato ou gordura.',
    )
  }

  const deduped = dedupeFoods(allFoods)
  return {
    duplicateRows: deduped.duplicateRows,
    foods: deduped.foods,
    ignoredRows,
    sourceCount: sourcesWithHeader,
  }
}

function findHeader(rows: string[][]) {
  let best:
    | {
        dataStartIndex: number
        headerIndex: HeaderIndex
        score: number
      }
    | null = null

  const maxRowsToScan = Math.min(rows.length, 40)
  for (let rowIndex = 0; rowIndex < maxRowsToScan; rowIndex += 1) {
    for (const useNextRow of [false, true]) {
      if (useNextRow && rowIndex + 1 >= rows.length) continue

      const headers = useNextRow
        ? combineHeaderRows(rows[rowIndex], rows[rowIndex + 1])
        : rows[rowIndex]
      const headerIndex = buildHeaderIndex(headers)
      const coreCount = CORE_NUTRIENT_FIELDS.filter((field) => headerIndex[field] !== null).length
      const mappedCount = Object.values(headerIndex).filter((index) => index !== null).length
      const score = (headerIndex.name !== null ? 100 : 0) + coreCount * 20 + mappedCount

      if (headerIndex.name === null || coreCount === 0) continue
      if (!best || score > best.score) {
        best = {
          dataStartIndex: rowIndex + (useNextRow ? 2 : 1),
          headerIndex,
          score,
        }
      }
    }
  }

  return best
}

function combineHeaderRows(first: string[], second: string[]) {
  const width = Math.max(first.length, second.length)
  return Array.from({ length: width }, (_, index) =>
    cleanText([first[index], second[index]].filter(Boolean).join(' ')) ?? '',
  )
}

function buildHeaderIndex(headers: string[]): HeaderIndex {
  const normalizedHeaders = headers.map(normalizeSearchText)
  return Object.fromEntries(
    Object.entries(FIELD_ALIASES).map(([field, aliases]) => {
      let bestIndex: number | null = null
      let bestScore = 0

      normalizedHeaders.forEach((header, index) => {
        for (const alias of aliases) {
          const score = headerMatchScore(header, normalizeSearchText(alias))
          if (score > bestScore) {
            bestIndex = index
            bestScore = score
          }
        }
      })

      return [field, bestIndex]
    }),
  ) as HeaderIndex
}

function headerMatchScore(header: string, alias: string) {
  if (!header || !alias) return 0
  if (header === alias) return 100
  if (header.includes(alias)) return 80

  const headerTokens = new Set(header.split(' '))
  const aliasTokens = alias.split(' ')
  if (aliasTokens.every((token) => headerTokens.has(token))) return 60
  return 0
}

function mapRecord(
  record: string[],
  headerIndex: HeaderIndex,
  sourceName: string,
): TacoFoodInput | null {
  const name = cleanText(read(record, headerIndex.name))
  if (!name) return null

  const normalizedName = normalizeSearchText(name)
  if (!normalizedName) return null

  const food: TacoFoodInput = {
    ash_g: numberValue(read(record, headerIndex.ash_g)),
    calcium_mg: numberValue(read(record, headerIndex.calcium_mg)),
    carbohydrate_g: numberValue(read(record, headerIndex.carbohydrate_g)),
    category: cleanText(read(record, headerIndex.category)) || fallbackCategory(sourceName),
    cholesterol_mg: numberValue(read(record, headerIndex.cholesterol_mg)),
    code: cleanCode(read(record, headerIndex.code)),
    copper_mg: numberValue(read(record, headerIndex.copper_mg)),
    energy_kcal: numberValue(read(record, headerIndex.energy_kcal)),
    energy_kj: numberValue(read(record, headerIndex.energy_kj)),
    fiber_g: numberValue(read(record, headerIndex.fiber_g)),
    iron_mg: numberValue(read(record, headerIndex.iron_mg)),
    lipid_g: numberValue(read(record, headerIndex.lipid_g)),
    magnesium_mg: numberValue(read(record, headerIndex.magnesium_mg)),
    manganese_mg: numberValue(read(record, headerIndex.manganese_mg)),
    moisture_g: numberValue(read(record, headerIndex.moisture_g)),
    name,
    niacin_mg: numberValue(read(record, headerIndex.niacin_mg)),
    normalized_name: normalizedName,
    phosphorus_mg: numberValue(read(record, headerIndex.phosphorus_mg)),
    potassium_mg: numberValue(read(record, headerIndex.potassium_mg)),
    protein_g: numberValue(read(record, headerIndex.protein_g)),
    pyridoxine_mg: numberValue(read(record, headerIndex.pyridoxine_mg)),
    rae_mcg: numberValue(read(record, headerIndex.rae_mcg)),
    re_mcg: numberValue(read(record, headerIndex.re_mcg)),
    retinol_mcg: numberValue(read(record, headerIndex.retinol_mcg)),
    riboflavin_mg: numberValue(read(record, headerIndex.riboflavin_mg)),
    search_name: normalizedName,
    sodium_mg: numberValue(read(record, headerIndex.sodium_mg)),
    source: 'TACO',
    thiamine_mg: numberValue(read(record, headerIndex.thiamine_mg)),
    vitamin_c_mg: numberValue(read(record, headerIndex.vitamin_c_mg)),
    zinc_mg: numberValue(read(record, headerIndex.zinc_mg)),
  }

  const hasNutritionValue = CORE_NUTRIENT_FIELDS.some((field) => food[field] !== null)
  return hasNutritionValue ? food : null
}

function dedupeFoods(foods: TacoFoodInput[]) {
  const byKey = new Map<string, TacoFoodInput>()
  let duplicateRows = 0

  for (const food of foods) {
    const key = food.code ? `code:${food.code}` : `name:${food.normalized_name}`
    if (byKey.has(key)) duplicateRows += 1
    byKey.set(key, food)
  }

  return {
    duplicateRows,
    foods: Array.from(byKey.values()),
  }
}

async function upsertFoodsByKey(
  supabase: any,
  foods: TacoFoodInput[],
  keyField: 'code' | 'normalized_name',
): Promise<UpsertSummary> {
  const summary = { inserted: 0, updated: 0 }
  if (!foods.length) return summary

  for (const batch of chunks(foods, BATCH_SIZE)) {
    const keys = batch.map((food) => food[keyField]).filter((key): key is string => Boolean(key))
    const { data: existingRows, error: lookupError } = await supabase
      .from('taco_foods')
      .select(`id,${keyField}`)
      .in(keyField, keys)

    if (lookupError) {
      throw new Error(`Falha ao buscar alimentos existentes por ${keyField}: ${lookupError.message}`)
    }

    const existingByKey = new Map(
      ((existingRows ?? []) as Array<Record<string, unknown>>).map((row) => [
        String(row[keyField]),
        String(row.id),
      ]),
    )
    const inserts: TacoFoodInput[] = []
    const updates: Array<{ food: TacoFoodInput; id: string }> = []

    for (const food of batch) {
      const existingId = existingByKey.get(food[keyField] ?? '')
      if (existingId) updates.push({ food, id: existingId })
      else inserts.push(food)
    }

    if (inserts.length) {
      const { error } = await supabase.from('taco_foods').insert(inserts)
      if (error) throw new Error(`Falha ao inserir alimentos TACO: ${error.message}`)
      summary.inserted += inserts.length
    }

    for (const { food, id } of updates) {
      const { error } = await supabase.from('taco_foods').update(food).eq('id', id)
      if (error) throw new Error(`Falha ao atualizar ${food.name}: ${error.message}`)
      summary.updated += 1
    }
  }

  return summary
}

function parseCsv(input: string) {
  const normalized = input.replace(/^\uFEFF/, '')
  const firstLine = normalized.split(/\r?\n/, 1)[0] ?? ''
  const delimiter = firstLine.includes(';') ? ';' : ','
  const rows: string[][] = []
  let current = ''
  let row: string[] = []
  let quoted = false

  for (let index = 0; index < normalized.length; index += 1) {
    const char = normalized[index]
    const next = normalized[index + 1]

    if (char === '"' && quoted && next === '"') {
      current += '"'
      index += 1
      continue
    }

    if (char === '"') {
      quoted = !quoted
      continue
    }

    if (!quoted && char === delimiter) {
      row.push(current)
      current = ''
      continue
    }

    if (!quoted && (char === '\n' || char === '\r')) {
      if (char === '\r' && next === '\n') index += 1
      row.push(current)
      if (row.some((cell) => cell.trim())) rows.push(row)
      row = []
      current = ''
      continue
    }

    current += char
  }

  row.push(current)
  if (row.some((cell) => cell.trim())) rows.push(row)
  return rows
}

function read(record: string[], index: number | null) {
  return index === null ? '' : record[index] ?? ''
}

function cleanCode(value: string) {
  const text = cleanText(value)
  if (!text) return null
  return text.replace(/\.0+$/, '')
}

function cleanText(value: string | null | undefined) {
  const text = String(value ?? '').replace(/\s+/g, ' ').trim()
  return text || null
}

function numberValue(value: string) {
  let text = value.trim()
  if (!text || /^(-|na|n\/a|nd|tr|trace|\*)$/i.test(text)) return null

  text = text.replace(/\s+/g, '')
  const commaIndex = text.lastIndexOf(',')
  const dotIndex = text.lastIndexOf('.')
  if (commaIndex >= 0 && dotIndex >= 0) {
    text = commaIndex > dotIndex
      ? text.replace(/\./g, '').replace(',', '.')
      : text.replace(/,/g, '')
  } else {
    text = text.replace(',', '.')
  }

  const match = text.match(/-?\d+(?:\.\d+)?/)
  return match ? Number(match[0]) : null
}

function normalizeSearchText(value: string) {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
}

function fallbackCategory(sourceName: string) {
  const normalized = normalizeSearchText(sourceName)
  if (!normalized || ['planilha1', 'sheet1', 'taco'].includes(normalized)) return null
  return cleanText(sourceName)
}

function cellText(value: unknown) {
  if (value === null || value === undefined) return ''
  return String(value)
}

function chunks<T>(items: T[], size: number) {
  const result: T[][] = []
  for (let index = 0; index < items.length; index += size) {
    result.push(items.slice(index, index + size))
  }
  return result
}

function loadDotEnv(path: string) {
  const fullPath = resolve(path)
  if (!existsSync(fullPath)) return

  for (const line of readFileSync(fullPath, 'utf8').split(/\r?\n/)) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('=')) continue
    const [key, ...parts] = trimmed.split('=')
    process.env[key.trim()] ||= parts.join('=').trim().replace(/^["']|["']$/g, '')
  }
}
