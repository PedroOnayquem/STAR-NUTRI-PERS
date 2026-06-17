import { USER_MESSAGES, sanitizeUserMessage } from '../../../constants/messages'
import { supabase } from '../../../lib/supabase'
import type { DietMealItemRecord } from '../../clinical/types'
import type { TacoFoodRecord, TacoSearchResult } from '../types'

const SELECT_COLUMNS = `
  id,code,name,search_name,normalized_name,category,moisture_g,energy_kcal,energy_kj,protein_g,lipid_g,
  cholesterol_mg,carbohydrate_g,fiber_g,ash_g,calcium_mg,magnesium_mg,manganese_mg,
  phosphorus_mg,iron_mg,sodium_mg,potassium_mg,copper_mg,zinc_mg,retinol_mcg,re_mcg,
  rae_mcg,thiamine_mg,riboflavin_mg,pyridoxine_mg,niacin_mg,vitamin_c_mg,created_at,updated_at
`

function getClient() {
  if (!supabase) {
    throw new Error(USER_MESSAGES.unavailableConfig)
  }
  return supabase
}

function throwTacoError(message?: string): never {
  throw new Error(sanitizeUserMessage(message, USER_MESSAGES.actionError))
}

export async function searchTacoFoods({
  category,
  page,
  pageSize,
  query,
}: {
  category?: string | null
  page: number
  pageSize: number
  query: string
}): Promise<TacoSearchResult> {
  const client = getClient()
  const from = Math.max(page - 1, 0) * pageSize
  const to = from + pageSize - 1
  const term = query.trim()

  let request = client
    .from('taco_foods')
    .select(SELECT_COLUMNS, { count: 'exact' })
    .order('name', { ascending: true })
    .range(from, to)

  if (category) {
    request = request.eq('category', category)
  }

  if (term) {
    const raw = cleanSearchTerm(term)
    const normalized = normalizeSearchText(term)
    request = request.or(`name.ilike.%${raw}%,search_name.ilike.%${normalized}%,normalized_name.ilike.%${normalized}%`)
  }

  const { count, data, error } = await request.returns<TacoFoodRecord[]>()
  if (error) throwTacoError(error.message)

  return {
    count: count ?? 0,
    foods: data ?? [],
  }
}

export async function listTacoCategories() {
  const client = getClient()
  const { data, error } = await client
    .from('taco_foods')
    .select('category')
    .not('category', 'is', null)
    .order('category', { ascending: true })

  if (error) throwTacoError(error.message)

  return Array.from(
    new Set(
      (data ?? [])
        .map((item) => item.category)
        .filter((item): item is string => Boolean(item)),
    ),
  )
}

export async function createDietMealItem(payload: {
  carbohydrate_g: number | null
  energy_kcal: number | null
  fiber_g: number | null
  lipid_g: number | null
  meal_id: string
  protein_g: number | null
  quantity_g: number
  sodium_mg: number | null
  taco_food_id: string
}) {
  const client = getClient()
  const { data, error } = await client
    .from('diet_meal_items')
    .insert(payload)
    .select('*')
    .single<DietMealItemRecord>()

  if (error) throwTacoError(error.message)
  return data
}

export function normalizeSearchText(value: string) {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
}

function cleanSearchTerm(value: string) {
  return value.replace(/[%',().]/g, ' ').replace(/\s+/g, ' ').trim()
}
