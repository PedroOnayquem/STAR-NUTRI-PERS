import type { Session } from '@supabase/supabase-js'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL as string | undefined

export function requireApiBaseUrl() {
  if (!apiBaseUrl) {
    throw new Error('VITE_API_BASE_URL nao configurado.')
  }

  return apiBaseUrl.replace(/\/$/, '')
}

export function authHeaders(session: Session | null) {
  if (!session?.access_token) {
    throw new Error('Sessao autenticada nao encontrada.')
  }

  return {
    Authorization: `Bearer ${session.access_token}`,
    'Content-Type': 'application/json',
  }
}

export async function apiRequest<T>(
  path: string,
  session: Session | null,
  init?: RequestInit,
) {
  const startedAt = performance.now()
  const method = init?.method ?? 'GET'
  const response = await fetch(`${requireApiBaseUrl()}${path}`, {
    ...init,
    headers: {
      ...authHeaders(session),
      ...init?.headers,
    },
  }).catch(() => {
    throw new Error(
      `Nao foi possivel conectar ao backend em ${requireApiBaseUrl()}. Rode npm run dev:api e mantenha a API aberta na porta 8000.`,
    )
  })
  const elapsed = performance.now() - startedAt
  if (import.meta.env.DEV && elapsed > 450) {
    console.debug(`[perf:api] ${method} ${path} ${Math.round(elapsed)}ms`)
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

    throw new Error(detail ?? 'A requisicao nao pode ser concluida.')
  }

  return body as T
}
