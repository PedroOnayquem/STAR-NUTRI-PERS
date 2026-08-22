import { USER_MESSAGES, sanitizeUserMessage } from '../../../constants/messages'
import { supabase } from '../../../lib/supabase'
import type { DietMealItemRecord } from '../../clinical/types'
import type { TacoFoodRecord, TacoSearchResult } from '../types'

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
  const offset = Math.max(page - 1, 0) * pageSize
  const { data: rawData, error } = await client.rpc('search_taco_foods', {
    p_category: category || null,
    p_limit: pageSize,
    p_offset: offset,
    p_query: query.trim(),
  })
  if (error) throwTacoError(error.message)
  const data = (rawData ?? []) as unknown as TacoFoodRecord[]

  return {
    count: Number(data?.[0]?.total_count ?? 0),
    foods: data ?? [],
  }
}

export async function listTacoCategories() {
  const client = getClient()
  const { data: rawData, error } = await client.rpc('list_taco_categories')

  if (error) throwTacoError(error.message)
  const data = (rawData ?? []) as unknown as Array<{ category: string | null }>

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
