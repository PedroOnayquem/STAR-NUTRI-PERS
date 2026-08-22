import { createClient, type SupabaseClient } from '@supabase/supabase-js'
import { createHash } from 'node:crypto'
import * as fs from 'node:fs'
import { existsSync, readFileSync } from 'node:fs'
import { extname, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import * as XLSX from 'xlsx'

XLSX.set_fs(fs)

export const TACO_SOURCE = {
  edition: '4ª edição ampliada e revisada',
  fileName: 'Taco-4a-Edicao.xlsx',
  name: 'TACO',
  publicationYear: 2011,
  referenceBasis: '100 g de parte comestível',
  referenceQuantityG: 100,
  url: 'https://nepa.unicamp.br/wp-content/uploads/sites/27/2023/10/Taco-4a-Edicao.xlsx',
} as const

type TacoFoodInput = {
  ash_g: number | null
  calcium_mg: number | null
  carbohydrate_g: number | null
  category: string | null
  cholesterol_mg: number | null
  code: string
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
  publication_year: number
  pyridoxine_mg: number | null
  rae_mcg: number | null
  re_mcg: number | null
  reference_basis: string
  reference_quantity_g: number
  retinol_mcg: number | null
  riboflavin_mg: number | null
  search_name: string
  sodium_mg: number | null
  source: string
  source_edition: string
  source_key: string
  source_url: string
  thiamine_mg: number | null
  vitamin_c_mg: number | null
  zinc_mg: number | null
}

type NutrientDefinition = { code: string; column: number; name: string; unit: string }

export type TacoNutrientInput = {
  amount: number | null
  nutrient_code: string
  nutrient_name: string
  source_key: string
  source_sheet: string
  source_value: string | null
  unit: string
  value_status: 'measured' | 'trace' | 'not_applicable' | 'not_analyzed' | 'missing'
}

export type ParsedTacoWorkbook = { foods: TacoFoodInput[]; nutrients: TacoNutrientInput[] }

const DEFAULT_INPUTS = [
  'data/taco/Taco-4a-Edicao.xlsx',
  'data/taco/taco.xlsx',
  'data/taco/taco.xls',
]
const BATCH_SIZE = 250
const SUPPORTED_EXTENSIONS = new Set(['.xls', '.xlsx'])

const CORE_NUTRIENTS: NutrientDefinition[] = [
  { code: 'moisture_g', column: 2, name: 'Umidade', unit: 'g' },
  { code: 'energy_kcal', column: 3, name: 'Energia', unit: 'kcal' },
  { code: 'energy_kj', column: 4, name: 'Energia', unit: 'kJ' },
  { code: 'protein_g', column: 5, name: 'Proteína', unit: 'g' },
  { code: 'lipid_g', column: 6, name: 'Lipídeos', unit: 'g' },
  { code: 'cholesterol_mg', column: 7, name: 'Colesterol', unit: 'mg' },
  { code: 'carbohydrate_g', column: 8, name: 'Carboidrato', unit: 'g' },
  { code: 'fiber_g', column: 9, name: 'Fibra alimentar', unit: 'g' },
  { code: 'ash_g', column: 10, name: 'Cinzas', unit: 'g' },
  { code: 'calcium_mg', column: 11, name: 'Cálcio', unit: 'mg' },
  { code: 'magnesium_mg', column: 12, name: 'Magnésio', unit: 'mg' },
  { code: 'manganese_mg', column: 14, name: 'Manganês', unit: 'mg' },
  { code: 'phosphorus_mg', column: 15, name: 'Fósforo', unit: 'mg' },
  { code: 'iron_mg', column: 16, name: 'Ferro', unit: 'mg' },
  { code: 'sodium_mg', column: 17, name: 'Sódio', unit: 'mg' },
  { code: 'potassium_mg', column: 18, name: 'Potássio', unit: 'mg' },
  { code: 'copper_mg', column: 19, name: 'Cobre', unit: 'mg' },
  { code: 'zinc_mg', column: 20, name: 'Zinco', unit: 'mg' },
  { code: 'retinol_mcg', column: 21, name: 'Retinol', unit: 'mcg' },
  { code: 're_mcg', column: 22, name: 'RE', unit: 'mcg' },
  { code: 'rae_mcg', column: 23, name: 'RAE', unit: 'mcg' },
  { code: 'thiamine_mg', column: 24, name: 'Tiamina', unit: 'mg' },
  { code: 'riboflavin_mg', column: 25, name: 'Riboflavina', unit: 'mg' },
  { code: 'pyridoxine_mg', column: 26, name: 'Piridoxina', unit: 'mg' },
  { code: 'niacin_mg', column: 27, name: 'Niacina', unit: 'mg' },
  { code: 'vitamin_c_mg', column: 28, name: 'Vitamina C', unit: 'mg' },
]

const FATTY_ACIDS: NutrientDefinition[] = [
  { code: 'saturated_fat_g', column: 2, name: 'Ácidos graxos saturados', unit: 'g' },
  { code: 'monounsaturated_fat_g', column: 3, name: 'Ácidos graxos monoinsaturados', unit: 'g' },
  { code: 'polyunsaturated_fat_g', column: 4, name: 'Ácidos graxos poli-insaturados', unit: 'g' },
  ...[
    ['fatty_acid_12_0_g', 5, '12:0'], ['fatty_acid_14_0_g', 6, '14:0'],
    ['fatty_acid_16_0_g', 7, '16:0'], ['fatty_acid_18_0_g', 8, '18:0'],
    ['fatty_acid_20_0_g', 9, '20:0'], ['fatty_acid_22_0_g', 10, '22:0'],
    ['fatty_acid_24_0_g', 11, '24:0'], ['fatty_acid_14_1_g', 13, '14:1'],
    ['fatty_acid_16_1_g', 14, '16:1'], ['fatty_acid_18_1_g', 15, '18:1'],
    ['fatty_acid_20_1_g', 16, '20:1'], ['fatty_acid_18_2_n6_g', 17, '18:2 n-6'],
    ['fatty_acid_18_3_n3_g', 18, '18:3 n-3'], ['fatty_acid_20_4_g', 19, '20:4'],
    ['fatty_acid_20_5_g', 20, '20:5'], ['fatty_acid_22_5_g', 21, '22:5'],
    ['fatty_acid_22_6_g', 22, '22:6'], ['fatty_acid_18_1t_g', 23, '18:1 trans'],
    ['fatty_acid_18_2t_g', 24, '18:2 trans'],
  ].map(([code, column, name]) => ({ code: String(code), column: Number(column), name: String(name), unit: 'g' })),
]

const AMINO_ACIDS: NutrientDefinition[] = [
  ...[
    ['tryptophan_g', 2, 'Triptofano'], ['threonine_g', 3, 'Treonina'],
    ['isoleucine_g', 4, 'Isoleucina'], ['leucine_g', 5, 'Leucina'],
    ['lysine_g', 6, 'Lisina'], ['methionine_g', 7, 'Metionina'],
    ['cystine_g', 8, 'Cistina'], ['phenylalanine_g', 9, 'Fenilalanina'],
    ['tyrosine_g', 10, 'Tirosina'], ['valine_g', 12, 'Valina'],
    ['arginine_g', 13, 'Arginina'], ['histidine_g', 14, 'Histidina'],
    ['alanine_g', 15, 'Alanina'], ['aspartic_acid_g', 16, 'Ácido aspártico'],
    ['glutamic_acid_g', 17, 'Ácido glutâmico'], ['glycine_g', 18, 'Glicina'],
    ['proline_g', 19, 'Prolina'], ['serine_g', 20, 'Serina'],
  ].map(([code, column, name]) => ({ code: String(code), column: Number(column), name: String(name), unit: 'g' })),
]

export function parseOfficialTacoWorkbook(inputPath: string): ParsedTacoWorkbook {
  const workbook = XLSX.readFile(inputPath, { cellDates: false, raw: false })
  const mainSheetName = workbook.SheetNames.find((name) => normalizeSearchText(name).startsWith('cmvcol'))
  const fattySheetName = workbook.SheetNames.find((name) => normalizeSearchText(name).startsWith('agtaco'))
  const aminoSheetName = workbook.SheetNames.find((name) => normalizeSearchText(name).startsWith('aminoacidos'))
  if (!mainSheetName || !fattySheetName || !aminoSheetName) {
    throw new Error('A planilha não possui as três abas oficiais esperadas da TACO 4ª edição.')
  }

  const foods: TacoFoodInput[] = []
  const nutrients: TacoNutrientInput[] = []
  let category: string | null = null
  for (const row of sheetRows(workbook, mainSheetName)) {
    const code = foodCode(row[0])
    const name = cleanText(row[1])
    if (!code || !name) {
      if (isCategoryRow(row)) category = cleanText(row[0])
      continue
    }
    const normalizedName = normalizeSearchText(name)
    const values = Object.fromEntries(CORE_NUTRIENTS.map((item) => [item.code, numericValue(row[item.column])]))
    const sourceKey = `${TACO_SOURCE.name}:${TACO_SOURCE.publicationYear}:${code}`
    foods.push({
      ...values,
      category,
      code,
      name,
      normalized_name: normalizedName,
      publication_year: TACO_SOURCE.publicationYear,
      reference_basis: TACO_SOURCE.referenceBasis,
      reference_quantity_g: TACO_SOURCE.referenceQuantityG,
      search_name: normalizedName,
      source: TACO_SOURCE.name,
      source_edition: TACO_SOURCE.edition,
      source_key: sourceKey,
      source_url: TACO_SOURCE.url,
    } as TacoFoodInput)
    nutrients.push(...nutrientsFromRow(row, sourceKey, mainSheetName, CORE_NUTRIENTS))
  }

  const foodKeys = new Set(foods.map((food) => food.source_key))
  nutrients.push(...parseAdditionalSheet(workbook, fattySheetName, FATTY_ACIDS, foodKeys))
  nutrients.push(...parseAdditionalSheet(workbook, aminoSheetName, AMINO_ACIDS, foodKeys))
  if (foods.length !== 597) {
    throw new Error(`A planilha oficial deveria conter 597 alimentos; foram encontrados ${foods.length}.`)
  }
  return { foods, nutrients }
}

async function main() {
  const { dryRun, inputPath } = parseArguments(process.argv.slice(2))
  const parsed = parseOfficialTacoWorkbook(inputPath)
  const checksum = createHash('sha256').update(readFileSync(inputPath)).digest('hex')
  if (dryRun) {
    printSummary(inputPath, checksum, parsed, 'Validação concluída; nenhuma escrita foi realizada.')
    return
  }

  loadDotEnv('.env')
  loadDotEnv('backend/.env')
  const supabaseUrl = process.env.SUPABASE_URL || process.env.VITE_SUPABASE_URL
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_SERVICE_KEY
  if (!supabaseUrl || !serviceRoleKey) {
    throw new Error('Defina SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY antes de importar a TACO.')
  }

  const supabase = createClient(supabaseUrl, serviceRoleKey, { auth: { persistSession: false } })
  const batchId = await upsertImportBatch(supabase, checksum)
  await upsertFoods(supabase, parsed.foods, batchId)
  const ids = await loadFoodIds(supabase, parsed.foods.map((food) => food.source_key))
  await upsertNutrients(supabase, parsed.nutrients, ids)
  const { error } = await supabase.from('taco_import_batches').update({
    food_count: parsed.foods.length,
    imported_at: new Date().toISOString(),
    nutrient_value_count: parsed.nutrients.length,
  }).eq('id', batchId)
  if (error) throw new Error(`Falha ao finalizar lote TACO: ${error.message}`)
  printSummary(inputPath, checksum, parsed, 'Importação concluída.')
}

function parseAdditionalSheet(
  workbook: XLSX.WorkBook,
  sheetName: string,
  definitions: NutrientDefinition[],
  foodKeys: Set<string>,
) {
  const result: TacoNutrientInput[] = []
  for (const row of sheetRows(workbook, sheetName)) {
    const code = foodCode(row[0])
    if (!code || !cleanText(row[1])) continue
    const sourceKey = `${TACO_SOURCE.name}:${TACO_SOURCE.publicationYear}:${code}`
    if (foodKeys.has(sourceKey)) result.push(...nutrientsFromRow(row, sourceKey, sheetName, definitions))
  }
  return result
}

function nutrientsFromRow(
  row: string[], sourceKey: string, sourceSheet: string, definitions: NutrientDefinition[],
) {
  return definitions.map<TacoNutrientInput>((definition) => {
    const sourceValue = cleanText(row[definition.column])
    return {
      amount: numericValue(sourceValue),
      nutrient_code: definition.code,
      nutrient_name: definition.name,
      source_key: sourceKey,
      source_sheet: sourceSheet,
      source_value: sourceValue,
      unit: definition.unit,
      value_status: valueStatus(sourceValue),
    }
  })
}

async function upsertImportBatch(supabase: SupabaseClient, checksum: string) {
  const { data, error } = await supabase.from('taco_import_batches').upsert({
    publication_year: TACO_SOURCE.publicationYear,
    reference_basis: TACO_SOURCE.referenceBasis,
    source_edition: TACO_SOURCE.edition,
    source_file_name: TACO_SOURCE.fileName,
    source_file_sha256: checksum,
    source_name: TACO_SOURCE.name,
    source_url: TACO_SOURCE.url,
  }, { onConflict: 'source_name,source_edition,source_file_sha256' }).select('id').single<{ id: string }>()
  if (error) throw new Error(`Falha ao registrar origem TACO: ${error.message}`)
  return data.id
}

async function upsertFoods(supabase: SupabaseClient, foods: TacoFoodInput[], batchId: string) {
  for (const batch of chunks(foods, BATCH_SIZE)) {
    const { error } = await supabase.from('taco_foods').upsert(
      batch.map((food) => ({ ...food, import_batch_id: batchId })),
      { onConflict: 'source_key' },
    )
    if (error) throw new Error(`Falha ao importar alimentos TACO: ${error.message}`)
  }
}

async function loadFoodIds(supabase: SupabaseClient, sourceKeys: string[]) {
  const result = new Map<string, string>()
  for (const batch of chunks(sourceKeys, BATCH_SIZE)) {
    const { data, error } = await supabase.from('taco_foods').select('id,source_key').in('source_key', batch)
    if (error) throw new Error(`Falha ao relacionar nutrientes TACO: ${error.message}`)
    for (const row of (data ?? []) as Array<{ id: string; source_key: string }>) result.set(row.source_key, row.id)
  }
  if (result.size !== sourceKeys.length) throw new Error('Nem todos os alimentos importados receberam um identificador.')
  return result
}

async function upsertNutrients(
  supabase: SupabaseClient, nutrients: TacoNutrientInput[], foodIds: Map<string, string>,
) {
  for (const batch of chunks(nutrients, BATCH_SIZE)) {
    const rows = batch.map(({ source_key, ...nutrient }) => ({ ...nutrient, food_id: foodIds.get(source_key) }))
    const { error } = await supabase.from('taco_food_nutrients').upsert(rows, {
      onConflict: 'food_id,nutrient_code',
    })
    if (error) throw new Error(`Falha ao importar nutrientes detalhados: ${error.message}`)
  }
}

function parseArguments(args: string[]) {
  const dryRun = args.includes('--dry-run')
  const explicitPath = args.find((argument) => !argument.startsWith('--'))
  const inputPath = explicitPath ? resolve(explicitPath) : DEFAULT_INPUTS.map(resolve).find(existsSync)
  if (!inputPath) throw new Error('Arquivo TACO não encontrado em data/taco/. Informe o caminho da planilha oficial.')
  if (!SUPPORTED_EXTENSIONS.has(extname(inputPath).toLowerCase())) throw new Error('Use a planilha oficial XLS ou XLSX da TACO.')
  if (!existsSync(inputPath)) throw new Error(`Arquivo TACO não encontrado em ${inputPath}.`)
  return { dryRun, inputPath }
}

function sheetRows(workbook: XLSX.WorkBook, sheetName: string) {
  return XLSX.utils.sheet_to_json<unknown[]>(workbook.Sheets[sheetName], {
    blankrows: false, defval: '', header: 1, raw: false,
  }).map((row) => row.map((value) => String(value ?? '').trim()))
}

function isCategoryRow(row: string[]) {
  const first = cleanText(row[0])
  return Boolean(first && !cleanText(row[1]) && !/^(número do|alimento|legenda|\*|†)/i.test(first))
}

function foodCode(value: unknown) {
  const text = cleanText(String(value ?? ''))
  return text && /^\d+(?:\.0+)?$/.test(text) ? text.replace(/\.0+$/, '') : null
}

function numericValue(value: unknown) {
  let text = String(value ?? '').trim()
  if (!text || /^(-|na|n\/a|nd|tr|trace|\*)$/i.test(text)) return null
  text = text.replace(/\s+/g, '')
  const comma = text.lastIndexOf(',')
  const dot = text.lastIndexOf('.')
  if (comma >= 0 && dot >= 0) text = comma > dot ? text.replace(/\./g, '').replace(',', '.') : text.replace(/,/g, '')
  else text = text.replace(',', '.')
  const match = text.match(/-?\d+(?:\.\d+)?/)
  return match ? Number(match[0]) : null
}

function valueStatus(value: string | null): TacoNutrientInput['value_status'] {
  if (!value) return 'not_analyzed'
  if (/^(tr|trace)$/i.test(value)) return 'trace'
  if (/^(na|n\/a)$/i.test(value)) return 'not_applicable'
  if (/^(nd|-|\*)$/i.test(value)) return 'not_analyzed'
  return numericValue(value) === null ? 'missing' : 'measured'
}

export function normalizeSearchText(value: string) {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()
}

function cleanText(value: string | null | undefined) {
  const text = String(value ?? '').replace(/\s+/g, ' ').trim()
  return text || null
}

function chunks<T>(items: T[], size: number) {
  return Array.from({ length: Math.ceil(items.length / size) }, (_, index) => items.slice(index * size, (index + 1) * size))
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

function printSummary(inputPath: string, checksum: string, parsed: ParsedTacoWorkbook, message: string) {
  console.log(message)
  console.log(`Arquivo: ${inputPath}`)
  console.log(`SHA-256: ${checksum}`)
  console.log(`Alimentos: ${parsed.foods.length}`)
  console.log(`Valores estruturados: ${parsed.nutrients.length}`)
}

const invokedPath = process.argv[1] ? pathToFileURL(resolve(process.argv[1])).href : ''
if (import.meta.url === invokedPath) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : error)
    process.exitCode = 1
  })
}
