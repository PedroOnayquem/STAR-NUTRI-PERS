import type { Session } from '@supabase/supabase-js'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL as string | undefined

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
  if (!apiBaseUrl) {
    throw new Error('VITE_API_BASE_URL nao configurado.')
  }

  if (!session?.access_token) {
    throw new Error('Sessao de admin nao encontrada.')
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
    throw new Error(
      `Nao foi possivel conectar ao backend em ${apiBaseUrl}. Rode npm run dev:api e mantenha a API aberta na porta 8000.`,
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

    throw new Error(detail ?? 'Nao foi possivel cadastrar nutricionista.')
  }

  return body as CreatedNutritionist
}
