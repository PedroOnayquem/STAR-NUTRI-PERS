import type { Session } from '@supabase/supabase-js'
import { apiRequest, requireApiBaseUrl } from '../../../lib/api'
import type {
  AdminWorkspace,
  NutritionistDashboard,
  NutritionistWorkspace,
  PatientContext,
} from '../types'

export type NutritionistProfileForm = {
  bio?: string | null
  clinic_name?: string | null
  default_patient_trial_days?: number | null
  image?: File | null
  phone?: string | null
  professional_name?: string | null
  remove_image?: boolean
}

export function getNutritionistWorkspace(session: Session | null) {
  return apiRequest<NutritionistWorkspace>('/api/nutritionists/workspace', session)
}

export function getNutritionistDashboard(session: Session | null) {
  return apiRequest<NutritionistDashboard>('/api/nutritionists/dashboard', session)
}

export async function updateNutritionistProfile(
  session: Session | null,
  payload: NutritionistProfileForm,
) {
  if (!session?.access_token) {
    throw new Error('Sua sessão expirou. Entre novamente para continuar.')
  }

  const formData = new FormData()
  formData.set('professional_name', payload.professional_name ?? '')
  formData.set('clinic_name', payload.clinic_name ?? '')
  if (payload.default_patient_trial_days) {
    formData.set('default_patient_trial_days', String(payload.default_patient_trial_days))
  }
  formData.set('phone', payload.phone ?? '')
  formData.set('bio', payload.bio ?? '')
  formData.set('remove_image', payload.remove_image ? 'true' : 'false')
  if (payload.image) {
    formData.set('image', payload.image)
  }

  const response = await fetch(`${requireApiBaseUrl()}/api/nutritionists/profile`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${session.access_token}`,
    },
    body: formData,
  }).catch(() => {
    throw new Error('Não foi possível conectar ao Star Nutri. Tente novamente em instantes.')
  })

  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = Array.isArray(body?.detail)
      ? body.detail.map((item: { msg?: string }) => item.msg).join(' | ')
      : body?.detail
    throw new Error(detail || 'Não foi possível salvar o perfil do nutricionista.')
  }

  return body as {
    nutritionist: NutritionistWorkspace['nutritionist']
    profile: NutritionistWorkspace['profile']
  }
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

export function activateNutritionistPatient(
  patientId: string,
  session: Session | null,
) {
  return apiRequest<PatientContext['patient']>(
    `/api/nutritionists/patients/${patientId}/activate`,
    session,
    {
      method: 'POST',
      body: JSON.stringify({}),
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
