import type { DietMealFood, DietMealRecord } from '../clinical/types'
import type { TacoCalculatedNutrients, TacoFoodRecord, TacoNutrientTotals } from './types'

export const EMPTY_NUTRIENT_TOTALS: TacoNutrientTotals = {
  carbohydrate_g: 0,
  energy_kcal: 0,
  fiber_g: 0,
  lipid_g: 0,
  protein_g: 0,
  sodium_mg: 0,
}

export function calculateFoodNutrients(
  food: Pick<
    TacoFoodRecord,
    | 'carbohydrate_g'
    | 'energy_kcal'
    | 'fiber_g'
    | 'lipid_g'
    | 'protein_g'
    | 'reference_quantity_g'
    | 'sodium_mg'
  >,
  quantityG: number,
): TacoCalculatedNutrients {
  const factor = safeQuantity(quantityG) / foodReferenceQuantity(food)
  return {
    carbohydrate_g: roundNutrient(food.carbohydrate_g, factor),
    energy_kcal: roundNutrient(food.energy_kcal, factor),
    fiber_g: roundNutrient(food.fiber_g, factor),
    lipid_g: roundNutrient(food.lipid_g, factor),
    protein_g: roundNutrient(food.protein_g, factor),
    sodium_mg: roundNutrient(food.sodium_mg, factor),
  }
}

export function calculateMealTotals(meal: Pick<DietMealRecord, 'foods' | 'items'>) {
  const itemTotals = (meal.items ?? []).reduce<TacoNutrientTotals>((totals, item) => {
    return addTotals(totals, {
      carbohydrate_g: item.carbohydrate_g ?? 0,
      energy_kcal: item.energy_kcal ?? 0,
      fiber_g: item.fiber_g ?? 0,
      lipid_g: item.lipid_g ?? 0,
      protein_g: item.protein_g ?? 0,
      sodium_mg: item.sodium_mg ?? 0,
    })
  }, { ...EMPTY_NUTRIENT_TOTALS })

  const foodTotals = (meal.foods ?? []).reduce<TacoNutrientTotals>((totals, food) => {
    return addTotals(totals, totalsFromDietMealFood(food))
  }, { ...EMPTY_NUTRIENT_TOTALS })

  return hasAnyTotal(itemTotals) ? itemTotals : foodTotals
}

export function calculateDietTotals(meals: Array<Pick<DietMealRecord, 'foods' | 'items'>>) {
  return meals.reduce<TacoNutrientTotals>(
    (totals, meal) => addTotals(totals, calculateMealTotals(meal)),
    { ...EMPTY_NUTRIENT_TOTALS },
  )
}

export function dietMealFoodFromTacoFood(
  food: TacoFoodRecord,
  quantityG: number,
): DietMealFood {
  const totals = calculateFoodNutrients(food, quantityG)
  return {
    carbohydrate_g: totals.carbohydrate_g,
    energy_kcal: totals.energy_kcal,
    fiber_g: totals.fiber_g,
    lipid_g: totals.lipid_g,
    name: food.name,
    protein_g: totals.protein_g,
    quantity: `${formatQuantity(quantityG)}g`,
    quantity_g: quantityG,
    sodium_mg: totals.sodium_mg,
    taco_food_id: food.id,
  }
}

export function parseQuantityG(value: string) {
  const normalized = value.trim().replace(',', '.').toLowerCase()
  const match = normalized.match(/(\d+(?:\.\d+)?)/)
  if (!match) return null

  const amount = Number(match[1])
  if (!Number.isFinite(amount) || amount <= 0) return null
  if (/\bkg\b|quilo/.test(normalized)) return amount * 1000
  return amount
}

export function formatNutrient(value: number | null | undefined, unit = '') {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return '-'
  const formatted = Number(value).toLocaleString('pt-BR', {
    maximumFractionDigits: Number(value) >= 100 ? 0 : 1,
  })
  return unit ? `${formatted} ${unit}` : formatted
}

function totalsFromDietMealFood(food: DietMealFood): TacoNutrientTotals {
  return {
    carbohydrate_g: food.carbohydrate_g ?? food.carbs_g ?? 0,
    energy_kcal: food.energy_kcal ?? food.calories ?? 0,
    fiber_g: food.fiber_g ?? 0,
    lipid_g: food.lipid_g ?? food.fats_g ?? 0,
    protein_g: food.protein_g ?? 0,
    sodium_mg: food.sodium_mg ?? 0,
  }
}

function addTotals(current: TacoNutrientTotals, next: TacoNutrientTotals) {
  return {
    carbohydrate_g: round(current.carbohydrate_g + next.carbohydrate_g),
    energy_kcal: round(current.energy_kcal + next.energy_kcal),
    fiber_g: round(current.fiber_g + next.fiber_g),
    lipid_g: round(current.lipid_g + next.lipid_g),
    protein_g: round(current.protein_g + next.protein_g),
    sodium_mg: round(current.sodium_mg + next.sodium_mg),
  }
}

function hasAnyTotal(totals: TacoNutrientTotals) {
  return Object.values(totals).some((value) => value > 0)
}

function roundNutrient(value: number | null | undefined, factor: number) {
  return value === null || value === undefined ? null : round(value * factor)
}

function round(value: number) {
  return Math.round(value * 100) / 100
}

function safeQuantity(value: number) {
  return Number.isFinite(value) && value > 0 ? value : 0
}

function foodReferenceQuantity(food: { reference_quantity_g?: number }) {
  return Number.isFinite(food.reference_quantity_g) && Number(food.reference_quantity_g) > 0
    ? Number(food.reference_quantity_g)
    : 100
}

function formatQuantity(value: number) {
  return Number.isInteger(value) ? String(value) : String(round(value)).replace('.', ',')
}
