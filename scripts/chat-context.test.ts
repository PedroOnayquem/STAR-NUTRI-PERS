import assert from 'node:assert/strict'
import test from 'node:test'
import { chatMessagesQueryKey, chatSessionsQueryKey } from '../src/features/chat/queryKeys'
import { chatMessagesPath } from '../src/features/chat/services/chatService'

test('historico usa a rota canonica com limit=80 e offset=0', () => {
  assert.equal(
    chatMessagesPath('nutritionist', 'conversation-a', { limit: 80, offset: 0 }),
    '/api/chat/nutritionist/sessions/conversation-a/messages?limit=80&offset=0',
  )
})

test('cache de sessoes e mensagens e isolado por usuario autenticado', () => {
  assert.notDeepEqual(
    chatSessionsQueryKey('nutritionist-user-a', 'nutritionist'),
    chatSessionsQueryKey('nutritionist-user-b', 'nutritionist'),
  )
  assert.notDeepEqual(
    chatMessagesQueryKey('nutritionist-user-a', 'nutritionist', 'conversation-a'),
    chatMessagesQueryKey('nutritionist-user-b', 'nutritionist', 'conversation-a'),
  )
})
