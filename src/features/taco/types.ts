export type TacoFoodRecord = {
  ash_g: number | null
  calcium_mg: number | null
  carbohydrate_g: number | null
  category: string | null
  cholesterol_mg: number | null
  code: string | null
  copper_mg: number | null
  created_at?: string | null
  energy_kcal: number | null
  energy_kj: number | null
  fiber_g: number | null
  id: string
  iron_mg: number | null
  lipid_g: number | null
  magnesium_mg: number | null
  manganese_mg: number | null
  moisture_g: number | null
  name: string
  niacin_mg: number | null
  normalized_name: string | null
  phosphorus_mg: number | null
  potassium_mg: number | null
  protein_g: number | null
  pyridoxine_mg: number | null
  rae_mcg: number | null
  re_mcg: number | null
  retinol_mcg: number | null
  riboflavin_mg: number | null
  search_name: string | null
  sodium_mg: number | null
  thiamine_mg: number | null
  updated_at?: string | null
  vitamin_c_mg: number | null
  zinc_mg: number | null
}

export type TacoNutrientTotals = {
  carbohydrate_g: number
  energy_kcal: number
  fiber_g: number
  lipid_g: number
  protein_g: number
  sodium_mg: number
}

export type TacoSearchResult = {
  count: number
  foods: TacoFoodRecord[]
}
