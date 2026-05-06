import type { AppData, Patient } from '../types'
import { supabase } from '../lib/supabase'

export async function fetchNutritionistPatients(nutritionistId: string) {
  if (!supabase) {
    return []
  }

  const { data, error } = await supabase
    .from('patients')
    .select('*, profiles(full_name, email)')
    .eq('nutritionist_id', nutritionistId)
    .eq('is_active', true)

  if (error) {
    throw error
  }

  return data
}

export function createPatientLocally(data: AppData, patient: Patient): AppData {
  return {
    ...data,
    patients: [patient, ...data.patients],
  }
}
