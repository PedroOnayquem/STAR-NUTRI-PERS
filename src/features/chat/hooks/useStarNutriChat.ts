import { useCallback, useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { supabase } from '../../../lib/supabase'
import { useAuth } from '../../auth/useAuth'
import type { ChatMessageRecord, ChatSessionRecord } from '../../clinical/types'
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
    () => ['chat-sessions', scope, patientId ?? 'me'],
    [patientId, scope],
  )
  const canUseChat = Boolean(
    session &&
      ((scope === 'nutritionist' && profile?.role === 'nutritionist' && patientId) ||
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
    queryFn: () => listChatMessages(session, scope, activeSessionId!, { limit: 80 }),
    enabled: Boolean(canUseChat && activeSessionId),
  })

  const upsertMessageInCache = useCallback((message: ChatMessageRecord) => {
    queryClient.setQueryData<ChatMessageRecord[]>(['chat-messages', scope, message.chat_id], (current = []) => {
      if (current.some((item) => item.id === message.id)) {
        return current
      }

      return [...current, message].sort((a, b) => a.created_at.localeCompare(b.created_at))
    })
  }, [queryClient, scope])

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
        (payload) => {
          const message = payload.new as ChatMessageRecord
          upsertMessageInCache(message)
          if (message.sender === (scope === 'nutritionist' ? 'nutritionist' : 'patient')) {
            setPendingUserMessage(null)
          }
        },
      )
      .subscribe()

    return () => {
      client.removeChannel(channel)
    }
  }, [activeSessionId, scope, upsertMessageInCache])

  const createSessionMutation = useMutation({
    mutationFn: () => {
      if (!canUseChat) {
        throw new Error('Selecione um paciente para criar uma conversa.')
      }

      return createChatSession(session, scope, {
        patientId,
        title: 'Nova conversa',
      })
    },
    onSuccess: (created) => {
      setError(null)
      setSelectedSessionId(created.id)
      queryClient.setQueryData<ChatSessionRecord[]>(sessionsQueryKey, (current = []) => [
        created,
        ...current.filter((item) => item.id !== created.id),
      ])
      queryClient.setQueryData(['chat-messages', scope, created.id], [])
    },
    onError: (caught) => {
      setError(caught instanceof Error ? caught.message : 'Nao foi possivel criar a conversa.')
    },
  })

  const sendMutation = useMutation({
    mutationFn: async (content: string) => {
      if (!canUseChat) {
        throw new Error('Selecione um paciente para iniciar o chat.')
      }

      setError(null)
      setStreaming('')
      setStreamingActions([])
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
          setSelectedSessionId(sessionId)
          setPendingUserMessage((message) =>
            message ? { ...message, chat_id: sessionId } : message,
          )
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
        onDone: (payload) => {
          const savedMessage = (payload as { message?: ChatMessageRecord })?.message
          if (savedMessage) {
            upsertMessageInCache(savedMessage)
          }
          setPendingUserMessage(null)
          setStreaming('')
          setStreamingActions([])
          queryClient.invalidateQueries({ queryKey: sessionsQueryKey, refetchType: 'inactive' })
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
    createSession: createSessionMutation.mutate,
    creatingSession: createSessionMutation.isPending,
    error,
    isLoading: sessionsQuery.isLoading || messagesQuery.isLoading,
    messages,
    selectSession: setSelectedSessionId,
    sendMessage: sendMutation.mutate,
    sending: sendMutation.isPending,
    sessions: sessionsQuery.data ?? [],
    streaming,
    streamingActions,
  }
}
