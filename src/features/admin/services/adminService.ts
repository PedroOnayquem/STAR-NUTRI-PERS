import type { Session } from '@supabase/supabase-js'
import { USER_MESSAGES, sanitizeUserMessage } from '../../../constants/messages'
import { requireApiBaseUrl } from '../../../lib/api'

export type CreateNutritionistInput = {
  fullName: string
  email: string
  password: string
  crn: string
  specialty: string
  bio: string
}

export type CreatedNutritionist = {
  profile_id: string
  nutritionist_id: string
  email: string
  full_name: string
  role: 'nutritionist'
}

export async function createNutritionist(
  input: CreateNutritionistInput,
  session: Session | null,
) {
  const apiBaseUrl = requireApiBaseUrl()

  if (!session?.access_token) {
    throw new Error(USER_MESSAGES.missingSession)
  }

  let response: Response

  try {
    response = await fetch(`${apiBaseUrl}/api/admin/nutritionists`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${session.access_token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        full_name: input.fullName.trim(),
        email: input.email.trim(),
        password: input.password,
        crn: input.crn.trim() || null,
        specialty: input.specialty.trim() || null,
        bio: input.bio.trim() || null,
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

    throw new Error(sanitizeUserMessage(detail, 'Não foi possível cadastrar nutricionista.'))
  }

  return body as CreatedNutritionist
}
