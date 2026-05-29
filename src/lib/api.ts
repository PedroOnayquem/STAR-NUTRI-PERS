import type { Session } from '@supabase/supabase-js'
import { USER_MESSAGES, sanitizeUserMessage } from '../constants/messages'
import { getAppConfig } from './runtimeConfig'

export function requireApiBaseUrl() {
  const apiBaseUrl = getAppConfig('VITE_API_BASE_URL')

  if (!apiBaseUrl) {
    throw new Error(USER_MESSAGES.unavailableConfig)
  }

  return apiBaseUrl.replace(/\/$/, '')
}

export function authHeaders(session: Session | null) {
  if (!session?.access_token) {
    throw new Error(USER_MESSAGES.missingSession)
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
    throw new Error(USER_MESSAGES.connectionError)
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

    throw new Error(sanitizeUserMessage(detail, USER_MESSAGES.actionError))
  }

  return body as T
}
