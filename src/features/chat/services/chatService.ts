import type { Session } from '@supabase/supabase-js'
import { apiRequest, authHeaders, requireApiBaseUrl } from '../../../lib/api'
import type { ChatMessageRecord, ChatSessionRecord } from '../../clinical/types'

export function listChatSessions(session: Session | null, patientId?: string) {
  const search = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : ''
  return apiRequest<ChatSessionRecord[]>(`/api/chat/sessions${search}`, session)
}

export function createChatSession(
  session: Session | null,
  payload: { patientId?: string; title?: string },
) {
  return apiRequest<ChatSessionRecord>('/api/chat/sessions', session, {
    method: 'POST',
    body: JSON.stringify({
      patient_id: payload.patientId,
      title: payload.title,
    }),
  })
}

export function listChatMessages(session: Session | null, sessionId: string) {
  return apiRequest<ChatMessageRecord[]>(
    `/api/chat/sessions/${sessionId}/messages`,
    session,
  )
}

export async function sendChatMessageStream({
  content,
  onDelta,
  onDone,
  onError,
  onSession,
  patientId,
  session,
  sessionId,
}: {
  content: string
  patientId?: string
  session: Session | null
  sessionId?: string | null
  onDelta: (delta: string) => void
  onError?: (message: string) => void
  onSession?: (sessionId: string) => void
  onDone: (payload: unknown) => void
}) {
  const response = await fetch(`${requireApiBaseUrl()}/api/chat/send`, {
    method: 'POST',
    headers: authHeaders(session),
    body: JSON.stringify({
      content,
      patient_id: patientId,
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
      if (event === 'error') {
        onError?.(payload.detail ?? 'Erro ao chamar a IA.')
      }
      if (event === 'done') {
        onDone(payload)
      }
    }
  }
}
