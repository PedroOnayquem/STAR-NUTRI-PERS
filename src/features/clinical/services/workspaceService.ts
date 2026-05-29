import type { Session } from '@supabase/supabase-js'
import { apiRequest } from '../../../lib/api'
import type {
  AdminWorkspace,
  NutritionistDashboard,
  NutritionistWorkspace,
  PatientContext,
} from '../types'

export function getNutritionistWorkspace(session: Session | null) {
  return apiRequest<NutritionistWorkspace>('/api/nutritionists/workspace', session)
}

export function getNutritionistDashboard(session: Session | null) {
  return apiRequest<NutritionistDashboard>('/api/nutritionists/dashboard', session)
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

export function getPatientImportSignedUrl(importId: string, session: Session | null) {
  return apiRequest<{ signed_url: string }>(
    `/api/nutritionists/imports/${importId}/signed-url`,
    session,
  )
}

export function getPatientImportFileSignedUrls(importId: string, session: Session | null) {
  return apiRequest<{
    files: Array<{
      id: string
      signed_url: string | null
      original_file_name?: string | null
      file_type?: string | null
      order_index?: number | null
    }>
  }>(`/api/nutritionists/imports/${importId}/files/signed-urls`, session)
}

export function getPatientContext(session: Session | null) {
  return apiRequest<PatientContext>('/api/patients/me/context', session)
}

export function updateMyPatientProfile(
  session: Session | null,
  payload: {
    full_name?: string
    phone?: string | null
    birth_date?: string | null
    gender?: string | null
    objective?: string | null
  },
) {
  return apiRequest<PatientContext['patient']>('/api/patients/me/profile', session, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function getAdminWorkspace(session: Session | null) {
  return apiRequest<AdminWorkspace>('/api/admin/workspace', session)
}
