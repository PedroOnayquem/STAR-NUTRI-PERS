import type { Session } from '@supabase/supabase-js'
import { apiRequest, authHeaders, requireApiBaseUrl } from '../../../lib/api'
import type { ChatMessageRecord, ChatSessionRecord } from '../../clinical/types'
import type { AiReasoningLevel, ChatScope } from '../types'

function chatBasePath(scope: ChatScope) {
  return scope === 'nutritionist' ? '/api/chat/nutritionist' : '/api/chat/patient'
}

export function listChatSessions(
  session: Session | null,
  scope: ChatScope,
  patientId?: string,
) {
  const search = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : ''
  return apiRequest<ChatSessionRecord[]>(
    `${chatBasePath(scope)}/sessions${search}`,
    session,
  )
}

export function createChatSession(
  session: Session | null,
  scope: ChatScope,
  payload: { patientId?: string; title?: string },
) {
  return apiRequest<ChatSessionRecord>(`${chatBasePath(scope)}/sessions`, session, {
    method: 'POST',
    body: JSON.stringify({
      patient_id: payload.patientId,
      title: payload.title,
    }),
  })
}

export function listChatMessages(
  session: Session | null,
  scope: ChatScope,
  sessionId: string,
  options?: { limit?: number; offset?: number },
) {
  const limit = options?.limit ?? 120
  const offset = options?.offset ?? 0
  return apiRequest<ChatMessageRecord[]>(
    `${chatBasePath(scope)}/sessions/${sessionId}/messages?limit=${limit}&offset=${offset}`,
    session,
  )
}

export async function sendChatMessageStream({
  content,
  onDelta,
  onDone,
  onError,
  onSession,
  onAction,
  patientId,
  reasoningLevel,
  scope,
  session,
  sessionId,
}: {
  content: string
  patientId?: string
  reasoningLevel: AiReasoningLevel
  scope: ChatScope
  session: Session | null
  sessionId?: string | null
  onAction?: (payload: unknown) => void
  onDelta: (delta: string) => void
  onError?: (message: string) => void
  onSession?: (sessionId: string) => void
  onDone: (payload: unknown) => void
}) {
  const response = await fetch(`${requireApiBaseUrl()}${chatBasePath(scope)}/send`, {
    method: 'POST',
    headers: authHeaders(session),
    body: JSON.stringify({
      content,
      patient_id: patientId,
      reasoning_level: reasoningLevel,
      session_id: sessionId,
    }),
  }).catch(() => {
    throw new Error(
      `Nao foi possivel conectar ao backend em ${requireApiBaseUrl()}. Rode npm run dev:api.`,
    )
  })

  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.detail ?? 'Nao foi possivel conversar com a IA.')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split('\n\n')
    buffer = events.pop() ?? ''

    for (const eventBlock of events) {
      const lines = eventBlock.split('\n')
      const event = lines
        .find((line) => line.startsWith('event:'))
        ?.replace('event:', '')
        .trim()
      const data = lines
        .find((line) => line.startsWith('data:'))
        ?.replace('data:', '')
        .trim()

      if (!data) continue

      const payload = JSON.parse(data)
      if (event === 'delta') {
        onDelta(payload.content ?? '')
      }
      if (event === 'session') {
        onSession?.(payload.session_id)
      }
      if (event === 'action') {
        onAction?.(payload)
      }
      if (event === 'error') {
        const message = payload.detail ?? 'Erro ao chamar a IA.'
        onError?.(message)
        throw new Error(message)
      }
      if (event === 'done') {
        onDone(payload)
      }
    }
  }
}
