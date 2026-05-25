import type { Session } from '@supabase/supabase-js'
import { requireApiBaseUrl } from '../../../lib/api'

export type CreatePatientInput = {
  fullName: string
  email: string
  password: string
  birthDate: string
  gender: string
  objective: string
  notes: string
}

export type CreatedPatient = {
  profile_id: string
  patient_id: string
  email: string
  full_name: string
  role: 'patient'
}

export async function createPatient(input: CreatePatientInput, session: Session | null) {
  const apiBaseUrl = requireApiBaseUrl()

  if (!session?.access_token) {
    throw new Error('Sessao de nutricionista nao encontrada.')
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
      }),
    })
  } catch {
    throw new Error(
      `Nao foi possivel conectar ao backend em ${apiBaseUrl}. Verifique se a API do Star Nutri esta no ar.`,
    )
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

    throw new Error(detail ?? 'Nao foi possivel cadastrar paciente.')
  }

  return body as CreatedPatient
}
