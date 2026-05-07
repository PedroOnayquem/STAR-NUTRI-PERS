import type { Session } from '@supabase/supabase-js'
import { apiRequest } from '../../../lib/api'
import type {
  AdminWorkspace,
  NutritionistWorkspace,
  PatientContext,
} from '../types'

export function getNutritionistWorkspace(session: Session | null) {
  return apiRequest<NutritionistWorkspace>('/api/nutritionists/workspace', session)
}

export function getNutritionistPatientContext(
  patientId: string,
  session: Session | null,
) {
  return apiRequest<PatientContext>(
    `/api/nutritionists/patients/${patientId}/context`,
    session,
  )
}

export function updateNutritionistPatient(
  patientId: string,
  session: Session | null,
  payload: {
    full_name?: string
    phone?: string | null
    birth_date?: string | null
    gender?: string | null
    objective?: string | null
    notes?: string | null
    is_active?: boolean
  },
) {
  return apiRequest<PatientContext['patient']>(
    `/api/nutritionists/patients/${patientId}`,
    session,
    {
      method: 'PATCH',
      body: JSON.stringify(payload),
    },
  )
}

export function deactivateNutritionistPatient(
  patientId: string,
  session: Session | null,
) {
  return apiRequest<{ id: string; is_active: boolean }>(
    `/api/nutritionists/patients/${patientId}`,
    session,
    { method: 'DELETE' },
  )
}

export function getPatientContext(session: Session | null) {
  return apiRequest<PatientContext>('/api/patients/me/context', session)
}

export function getAdminWorkspace(session: Session | null) {
  return apiRequest<AdminWorkspace>('/api/admin/workspace', session)
}
