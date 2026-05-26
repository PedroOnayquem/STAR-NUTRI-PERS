import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { supabase } from '../../../lib/supabase'
import { useAuth } from '../../auth/useAuth'
import type { ChatMessageRecord } from '../../clinical/types'
import {
  createChatSession,
  listChatMessages,
  listChatSessions,
  sendChatMessageStream,
} from '../services/chatService'
import type { AiReasoningLevel, ChatScope } from '../types'

export function useStarNutriChat({
  patientId,
  reasoningLevel = 'medium',
  scope,
  externalQueryKey,
}: {
  patientId?: string
  reasoningLevel?: AiReasoningLevel
  scope: ChatScope
  externalQueryKey?: unknown[]
}) {
  const { profile, session } = useAuth()
  const queryClient = useQueryClient()
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [streaming, setStreaming] = useState('')
  const [streamingActions, setStreamingActions] = useState<unknown[]>([])
  const [pendingUserMessage, setPendingUserMessage] = useState<ChatMessageRecord | null>(null)
  const [error, setError] = useState<string | null>(null)

  const sessionsQueryKey = useMemo(
    () => [
      'chat-sessions',
      scope,
      patientId ?? (scope === 'nutritionist' ? 'general' : 'me'),
    ],
    [patientId, scope],
  )
  const canUseChat = Boolean(
    session &&
      ((scope === 'nutritionist' && profile?.role === 'nutritionist') ||
        (scope === 'patient' && profile?.role === 'patient')),
  )

  const sessionsQuery = useQuery({
    queryKey: sessionsQueryKey,
    queryFn: () => listChatSessions(session, scope, patientId),
    enabled: canUseChat,
  })

  const activeSessionId = useMemo(() => {
    const sessions = sessionsQuery.data ?? []
    if (
      selectedSessionId &&
      sessions.some((chatSession) => chatSession.id === selectedSessionId)
    ) {
      return selectedSessionId
    }

    return sessions[0]?.id ?? null
  }, [selectedSessionId, sessionsQuery.data])

  const messagesQueryKey = useMemo(
    () => ['chat-messages', scope, activeSessionId],
    [activeSessionId, scope],
  )

  const messagesQuery = useQuery({
    queryKey: messagesQueryKey,
    queryFn: () => listChatMessages(session, scope, activeSessionId!, { limit: 120 }),
    enabled: Boolean(canUseChat && activeSessionId),
  })

  useEffect(() => {
    if (!supabase || !activeSessionId) return
    const client = supabase

    const channel = client
      .channel(`star-nutri-chat-${activeSessionId}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: scope === 'nutritionist' ? 'nutritionist_messages' : 'patient_messages',
          filter: `chat_id=eq.${activeSessionId}`,
        },
        () => {
          queryClient.invalidateQueries({ queryKey: messagesQueryKey })
          queryClient.invalidateQueries({ queryKey: sessionsQueryKey })
          if (externalQueryKey) {
            queryClient.invalidateQueries({ queryKey: externalQueryKey })
          }
        },
      )
      .subscribe()

    return () => {
      client.removeChannel(channel)
    }
  }, [activeSessionId, externalQueryKey, queryClient, scope, sessionsQueryKey, messagesQueryKey])

  const createSessionMutation = useMutation({
    mutationFn: () => {
      if (!canUseChat) {
        throw new Error('Nao foi possivel criar uma conversa agora.')
      }

      return createChatSession(session, scope, {
        patientId,
        title:
          scope === 'nutritionist' && !patientId
            ? 'Nova conversa geral'
            : 'Nova conversa',
      })
    },
    onSuccess: (created) => {
      setError(null)
      setSelectedSessionId(created.id)
      queryClient.invalidateQueries({ queryKey: sessionsQueryKey })
      queryClient.invalidateQueries({ queryKey: ['chat-messages', scope, created.id] })
      if (externalQueryKey) {
        queryClient.invalidateQueries({ queryKey: externalQueryKey })
      }
    },
    onError: (caught) => {
      setError(caught instanceof Error ? caught.message : 'Nao foi possivel criar a conversa.')
    },
  })

  const sendMutation = useMutation({
    mutationFn: async (content: string) => {
      if (!canUseChat) {
        throw new Error('Nao foi possivel iniciar o chat agora.')
      }

      setError(null)
      setStreaming('')
      setStreamingActions([])
      let resolvedSessionId = activeSessionId
      const tempSessionId = activeSessionId || 'new'
      setPendingUserMessage({
        id: `pending-${Date.now()}`,
        chat_id: tempSessionId,
        sender: scope === 'nutritionist' ? 'nutritionist' : 'patient',
        content,
        metadata: null,
        created_at: new Date().toISOString(),
      })

      await sendChatMessageStream({
        content,
        patientId,
        reasoningLevel,
        scope,
        session,
        sessionId: activeSessionId,
        onSession: (sessionId) => {
          resolvedSessionId = sessionId
          setSelectedSessionId(sessionId)
          setPendingUserMessage((message) =>
            message ? { ...message, chat_id: sessionId } : message,
          )
          queryClient.invalidateQueries({ queryKey: ['chat-messages', scope, sessionId] })
          queryClient.invalidateQueries({ queryKey: sessionsQueryKey })
        },
        onAction: (payload) => {
          setStreamingActions((current) => [...current, payload])
          if (externalQueryKey) {
            queryClient.invalidateQueries({ queryKey: externalQueryKey })
          }
        },
        onDelta: (delta) => setStreaming((current) => current + delta),
        onError: (message) => {
          setError(message)
        },
        onDone: () => {
          setPendingUserMessage(null)
          setStreaming('')
          setStreamingActions([])
          queryClient.invalidateQueries({ queryKey: sessionsQueryKey })
          if (resolvedSessionId) {
            queryClient.invalidateQueries({ queryKey: ['chat-messages', scope, resolvedSessionId] })
          }
          if (externalQueryKey) {
            queryClient.invalidateQueries({ queryKey: externalQueryKey })
          }
        },
      })

      if (resolvedSessionId) {
        queryClient.invalidateQueries({ queryKey: ['chat-messages', scope, resolvedSessionId] })
      }
    },
    onError: (caught) => {
      setError(caught instanceof Error ? caught.message : 'Erro ao chamar a IA.')
    },
    onSettled: () => {
      setPendingUserMessage(null)
      setStreamingActions([])
    },
  })

  const messages = useMemo(() => {
    const base = messagesQuery.data ?? []
    const extras: ChatMessageRecord[] = []
    if (pendingUserMessage && pendingUserMessage.chat_id === (activeSessionId || 'new')) {
      extras.push(pendingUserMessage)
    }
    return [...base, ...extras].sort((a, b) => a.created_at.localeCompare(b.created_at))
  }, [activeSessionId, messagesQuery.data, pendingUserMessage])

  return {
    activeSessionId,
    createSession: () => createSessionMutation.mutate(),
    creatingSession: createSessionMutation.isPending,
    error,
    isLoading: sessionsQuery.isLoading || messagesQuery.isLoading,
    messages,
    selectSession: setSelectedSessionId,
    sendMessage: (content: string) => sendMutation.mutate(content),
    sending: sendMutation.isPending,
    sessions: sessionsQuery.data ?? [],
    streaming,
    streamingActions,
  }
}
