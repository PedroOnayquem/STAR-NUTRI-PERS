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

export function useStarNutriChat({
  patientId,
  externalQueryKey,
}: {
  patientId?: string
  externalQueryKey?: unknown[]
}) {
  const { profile, session } = useAuth()
  const queryClient = useQueryClient()
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [streaming, setStreaming] = useState('')
  const [pendingUserMessage, setPendingUserMessage] = useState<ChatMessageRecord | null>(null)
  const [error, setError] = useState<string | null>(null)

  const sessionsQueryKey = useMemo(
    () => ['chat-sessions', patientId ?? 'me'],
    [patientId],
  )
  const messagesQueryKey = useMemo(
    () => ['chat-messages', activeSessionId],
    [activeSessionId],
  )

  const sessionsQuery = useQuery({
    queryKey: sessionsQueryKey,
    queryFn: () => listChatSessions(session, patientId),
    enabled: Boolean(session),
  })

  useEffect(() => {
    if (!activeSessionId && sessionsQuery.data?.[0]?.id) {
      setActiveSessionId(sessionsQuery.data[0].id)
    }
  }, [activeSessionId, sessionsQuery.data])

  const messagesQuery = useQuery({
    queryKey: messagesQueryKey,
    queryFn: () => listChatMessages(session, activeSessionId!),
    enabled: Boolean(session && activeSessionId),
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
          table: 'chat_messages',
          filter: `session_id=eq.${activeSessionId}`,
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
  }, [activeSessionId, externalQueryKey, queryClient, sessionsQueryKey, messagesQueryKey])

  const createSessionMutation = useMutation({
    mutationFn: () =>
      createChatSession(session, {
        patientId,
        title: 'Nova conversa',
      }),
    onSuccess: (created) => {
      setActiveSessionId(created.id)
      queryClient.invalidateQueries({ queryKey: sessionsQueryKey })
      queryClient.invalidateQueries({ queryKey: ['chat-messages', created.id] })
      if (externalQueryKey) {
        queryClient.invalidateQueries({ queryKey: externalQueryKey })
      }
    },
  })

  const sendMutation = useMutation({
    mutationFn: async (content: string) => {
      setError(null)
      setStreaming('')
      const tempSessionId = activeSessionId || 'new'
      setPendingUserMessage({
        id: `pending-${Date.now()}`,
        session_id: tempSessionId,
        sender: profile?.role === 'nutritionist' ? 'nutritionist' : 'patient',
        content,
        metadata: null,
        created_at: new Date().toISOString(),
      })

      await sendChatMessageStream({
        content,
        patientId,
        session,
        sessionId: activeSessionId,
        onSession: (sessionId) => {
          setActiveSessionId(sessionId)
          setPendingUserMessage((message) =>
            message ? { ...message, session_id: sessionId } : message,
          )
          queryClient.invalidateQueries({ queryKey: ['chat-messages', sessionId] })
          queryClient.invalidateQueries({ queryKey: sessionsQueryKey })
        },
        onDelta: (delta) => setStreaming((current) => current + delta),
        onError: (message) => {
          setError(message)
        },
        onDone: () => {
          setPendingUserMessage(null)
          setStreaming('')
          queryClient.invalidateQueries({ queryKey: sessionsQueryKey })
          queryClient.invalidateQueries({ queryKey: ['chat-messages', activeSessionId] })
          if (externalQueryKey) {
            queryClient.invalidateQueries({ queryKey: externalQueryKey })
          }
        },
      })
    },
    onError: (caught) => {
      setError(caught instanceof Error ? caught.message : 'Erro ao chamar a IA.')
    },
    onSettled: () => {
      setPendingUserMessage(null)
    },
  })

  const messages = useMemo(() => {
    const base = messagesQuery.data ?? []
    const extras: ChatMessageRecord[] = []
    if (pendingUserMessage && pendingUserMessage.session_id === (activeSessionId || 'new')) {
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
    selectSession: setActiveSessionId,
    sendMessage: (content: string) => sendMutation.mutate(content),
    sending: sendMutation.isPending,
    sessions: sessionsQuery.data ?? [],
    streaming,
  }
}
