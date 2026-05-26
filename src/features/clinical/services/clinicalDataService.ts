import { supabase } from '../../../lib/supabase'
import type {
  DietMealRecord,
  DietRecord,
  HealthConditionRecord,
  MetricRecord,
  WorkoutExerciseRecord,
  WorkoutRecord,
} from '../types'

function getClient() {
  if (!supabase) {
    throw new Error('Supabase nao configurado. Confira o arquivo .env.')
  }

  return supabase
}

export async function createDiet(payload: {
  patient_id: string
  nutritionist_id: string
  title: string
  description?: string | null
  calories?: number | null
  protein?: number | null
  carbs?: number | null
  fats?: number | null
  water_goal_ml?: number | null
  is_active?: boolean
}) {
  const client = getClient()
  const { data, error } = await client
    .from('diets')
    .insert(payload)
    .select('*')
    .single<DietRecord>()

  if (error) throw new Error(error.message)
  return data
}

export async function updateDiet(
  dietId: string,
  payload: Partial<Omit<DietRecord, 'id' | 'patient_id' | 'nutritionist_id'>>,
) {
  const client = getClient()
  const { data, error } = await client
    .from('diets')
    .update(payload)
    .eq('id', dietId)
    .select('*')
    .single<DietRecord>()

  if (error) throw new Error(error.message)
  return data
}

export async function deleteDiet(dietId: string) {
  const client = getClient()
  const { error } = await client.from('diets').delete().eq('id', dietId)
  if (error) throw new Error(error.message)
}

export async function duplicateDiet(diet: DietRecord) {
  const copy = await createDiet({
    patient_id: diet.patient_id,
    nutritionist_id: diet.nutritionist_id,
    title: `${diet.title} - copia`,
    description: diet.description,
    calories: diet.calories,
    protein: diet.protein,
    carbs: diet.carbs,
    fats: diet.fats,
    water_goal_ml: diet.water_goal_ml,
    is_active: false,
  })

  if (diet.meals?.length) {
    await upsertDietMeals(
      copy.id,
      diet.meals.map((meal) => ({
        meal_name: meal.meal_name,
        meal_time: meal.meal_time,
        foods: meal.foods,
        notes: meal.notes,
      })),
    )
  }

  return copy
}

export async function upsertDietMeals(
  dietId: string,
  meals: Array<{
    id?: string
    meal_name: string
    meal_time?: string | null
    foods: DietMealRecord['foods']
    notes?: string | null
  }>,
) {
  const client = getClient()
  const rows = meals.map((meal) => ({
    id: meal.id,
    diet_id: dietId,
    meal_name: meal.meal_name,
    meal_time: meal.meal_time || null,
    foods: meal.foods,
    notes: meal.notes || null,
  }))

  const { data, error } = await client
    .from('diet_meals')
    .upsert(rows)
    .select('*')
    .returns<DietMealRecord[]>()

  if (error) throw new Error(error.message)
  return data
}

export async function deleteDietMeal(mealId: string) {
  const client = getClient()
  const { error } = await client.from('diet_meals').delete().eq('id', mealId)
  if (error) throw new Error(error.message)
}

export async function createWorkout(payload: {
  patient_id: string
  nutritionist_id: string
  title: string
  description?: string | null
  frequency_per_week?: number | null
  is_active?: boolean
}) {
  const client = getClient()
  const { data, error } = await client
    .from('workouts')
    .insert(payload)
    .select('*')
    .single<WorkoutRecord>()

  if (error) throw new Error(error.message)
  return data
}

export async function updateWorkout(
  workoutId: string,
  payload: Partial<Omit<WorkoutRecord, 'id' | 'patient_id' | 'nutritionist_id'>>,
) {
  const client = getClient()
  const { data, error } = await client
    .from('workouts')
    .update(payload)
    .eq('id', workoutId)
    .select('*')
    .single<WorkoutRecord>()

  if (error) throw new Error(error.message)
  return data
}

export async function deleteWorkout(workoutId: string) {
  const client = getClient()
  const { error } = await client.from('workouts').delete().eq('id', workoutId)
  if (error) throw new Error(error.message)
}

export async function upsertWorkoutExercises(
  workoutId: string,
  exercises: Array<{
    id?: string
    exercise_name: string
    muscle_group?: string | null
    sets?: number | null
    reps?: string | null
    rest_time?: string | null
    load_info?: string | null
    notes?: string | null
  }>,
) {
  const client = getClient()
  const rows = exercises.map((exercise) => ({
    ...exercise,
    workout_id: workoutId,
  }))

  const { data, error } = await client
    .from('workout_exercises')
    .upsert(rows)
    .select('*')
    .returns<WorkoutExerciseRecord[]>()

  if (error) throw new Error(error.message)
  return data
}

export async function deleteWorkoutExercise(exerciseId: string) {
  const client = getClient()
  const { error } = await client
    .from('workout_exercises')
    .delete()
    .eq('id', exerciseId)

  if (error) throw new Error(error.message)
}

export async function createMainMetric(payload: {
  patient_id: string
  name: string
  value: string
  unit?: string | null
  defined_by?: string | null
}) {
  const client = getClient()
  const { data, error } = await client
    .from('patient_main_metrics')
    .insert(payload)
    .select('*')
    .single<MetricRecord>()

  if (error) throw new Error(error.message)
  return data
}

export async function createVariableMetric(payload: {
  patient_id: string
  name: string
  value: string
  unit?: string | null
  recorded_at?: string | null
}) {
  const client = getClient()
  const { data, error } = await client
    .from('patient_variable_metrics')
    .insert(payload)
    .select('*')
    .single<MetricRecord>()

  if (error) throw new Error(error.message)
  return data
}

export async function deleteMetric(
  table: 'patient_main_metrics' | 'patient_variable_metrics',
  metricId: string,
) {
  const client = getClient()
  const { error } = await client.from(table).delete().eq('id', metricId)
  if (error) throw new Error(error.message)
}

export async function createHealthCondition(payload: {
  patient_id: string
  condition_type: HealthConditionRecord['condition_type']
  title: string
  description: string
  injury_local?: string | null
  notes?: string | null
  origin?: string | null
  recommendations?: string | null
  severity?: string | null
  started_at?: string | null
}) {
  const client = getClient()
  const { data, error } = await client
    .from('patient_health_conditions')
    .insert(payload)
    .select('*')
    .single<HealthConditionRecord>()

  if (error) throw new Error(error.message)
  return data
}

export async function deleteHealthCondition(conditionId: string) {
  const client = getClient()
  const { error } = await client
    .from('patient_health_conditions')
    .delete()
    .eq('id', conditionId)

  if (error) throw new Error(error.message)
}
