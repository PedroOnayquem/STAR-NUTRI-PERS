import type { Session } from '@supabase/supabase-js'
import { USER_MESSAGES, sanitizeUserMessage } from '../../../constants/messages'
import { requireApiBaseUrl } from '../../../lib/api'

export type CreatePatientInput = {
  fullName: string
  email: string
  password: string
  birthDate: string
  gender: string
  objective: string
  notes: string
  importId?: string | null
}

export type CreatedPatient = {
  access_status: 'TRIAL'
  profile_id: string
  patient_id: string
  email: string
  full_name: string
  role: 'patient'
  trial_days: number
  trial_ends_at: string
}

export type BioimpedanceImportResult = {
  import_id: string
  source_type: 'bioimpedance_report' | 'bioimpedance_pdf' | string
  file_type: 'pdf' | 'jpg' | 'jpeg' | 'png'
  mime_type?: string | null
  original_file_name?: string | null
  file_size_bytes?: number | null
  file_path: string | null
  file_count: number
  files: Array<{
    id: string
    file_url: string | null
    file_type: 'pdf' | 'jpg' | 'jpeg' | 'png' | null
    mime_type?: string | null
    original_file_name?: string | null
    file_size_bytes?: number | null
    order_index?: number | null
  }>
  extraction_mode: 'text' | 'ocr' | 'mixed'
  patient: {
    full_name?: string
    gender?: string
    birth_date?: string
    age?: number
    height_cm?: number
    notes?: string
  }
  metrics: Record<string, number>
  measurement: {
    measured_at?: string
  }
  confidence: Record<string, number>
  warnings: string[]
  autofill_fields: Array<'fullName' | 'gender' | 'birthDate' | 'notes'>
}

export async function createPatient(input: CreatePatientInput, session: Session | null) {
  const apiBaseUrl = requireApiBaseUrl()

  if (!session?.access_token) {
    throw new Error(USER_MESSAGES.missingSession)
  }

  let response: Response

  try {
    response = await fetch(`${apiBaseUrl}/api/nutritionists/patients`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${session.access_token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        full_name: input.fullName.trim(),
        email: input.email.trim(),
        password: input.password,
        birth_date: input.birthDate || null,
        gender: input.gender.trim() || null,
        objective: input.objective.trim() || null,
        notes: input.notes.trim() || null,
        import_id: input.importId || null,
      }),
    })
  } catch {
    throw new Error(USER_MESSAGES.connectionError)
  }

  const body = await response.json().catch(() => null)

  if (!response.ok) {
    const detail = Array.isArray(body?.detail)
      ? body.detail
          .map((item: { msg?: string; loc?: string[] }) =>
            item.loc?.length ? `${item.loc.join('.')}: ${item.msg}` : item.msg,
          )
          .join(' | ')
      : body?.detail

    throw new Error(sanitizeUserMessage(detail, 'Não foi possível cadastrar paciente.'))
  }

  return body as CreatedPatient
}

export async function importBioimpedanceReport(files: File | File[], session: Session | null) {
  const apiBaseUrl = requireApiBaseUrl()

  if (!session?.access_token) {
    throw new Error(USER_MESSAGES.missingSession)
  }

  const data = new FormData()
  const selectedFiles = Array.isArray(files) ? files : [files]
  selectedFiles.forEach((file) => data.append('files', file))

  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}/api/nutritionists/patients/import-bioimpedance-report`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${session.access_token}`,
      },
      body: data,
    })
  } catch {
    throw new Error(USER_MESSAGES.connectionError)
  }

  const body = await response.json().catch(() => null)

  if (!response.ok) {
    const detail = Array.isArray(body?.detail)
      ? body.detail
          .map((item: { msg?: string; loc?: string[] }) =>
            item.loc?.length ? `${item.loc.join('.')}: ${item.msg}` : item.msg,
          )
          .join(' | ')
      : body?.detail

    throw new Error(sanitizeUserMessage(detail, 'Não foi possível importar o relatório.'))
  }

  return body as BioimpedanceImportResult
}

export const importBioimpedancePdf = importBioimpedanceReport
