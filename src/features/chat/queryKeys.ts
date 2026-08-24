import type { ChatScope } from './types'

export function chatSessionsQueryKey(
  actorId: string | null | undefined,
  scope: ChatScope,
  patientId?: string,
) {
  return [
    'chat-sessions',
    actorId ?? 'anonymous',
    scope,
    patientId ?? (scope === 'nutritionist' ? 'general' : 'me'),
  ] as const
}

export function chatMessagesQueryKey(
  actorId: string | null | undefined,
  scope: ChatScope,
  sessionId: string | null | undefined,
) {
  return [
    'chat-messages',
    actorId ?? 'anonymous',
    scope,
    sessionId ?? 'none',
  ] as const
}
