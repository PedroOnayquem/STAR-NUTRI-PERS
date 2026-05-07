import { useEffect, useRef, useState, type FormEvent } from 'react'
import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  Bot,
  Loader2,
  MessageSquarePlus,
  Send,
  Sparkles,
  Wifi,
} from 'lucide-react'
import { Button } from '../../../components/ui/Button'
import { Card } from '../../../components/ui/Card'
import { EmptyState } from '../../../components/ui/EmptyState'
import { Skeleton } from '../../../components/ui/Skeleton'
import { Textarea } from '../../../components/ui/Input'
import { cn } from '../../../lib/utils'
import { useAuth } from '../../auth/useAuth'
import type { ChatMessageRecord } from '../../clinical/types'
import { useStarNutriChat } from '../hooks/useStarNutriChat'

export function ChatExperience({
  externalQueryKey,
  patientId,
  patientName,
}: {
  externalQueryKey?: unknown[]
  patientId?: string
  patientName?: string
}) {
  const { profile } = useAuth()
  const [content, setContent] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)
  const chat = useStarNutriChat({ patientId, externalQueryKey })

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [chat.activeSessionId, chat.messages, chat.streaming])

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextContent = content.trim()
    if (!nextContent || chat.sending) return
    setContent('')
    chat.sendMessage(nextContent)
  }

  const assistantTitle = patientName
    ? `Assistente GLM 5 sobre ${patientName}`
    : 'Assistente Star Nutri GLM 5'

  return (
    <Card className="grid min-h-[720px] overflow-hidden p-0 lg:grid-cols-[300px_1fr]">
      <aside className="border-b border-slate-200 bg-slate-50/90 p-4 dark:border-white/10 dark:bg-white/[0.03] lg:border-b-0 lg:border-r">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-black uppercase text-emerald-600 dark:text-emerald-300">
              Conversas
            </p>
            <h2 className="mt-1 font-black">Histórico</h2>
          </div>
          <div className="flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-1 text-xs font-black text-emerald-700 dark:text-emerald-300">
            <Wifi size={13} />
            realtime
          </div>
        </div>

        <Button
          className="mt-4 w-full"
          disabled={chat.creatingSession}
          onClick={chat.createSession}
          type="button"
          variant="premium"
        >
          <MessageSquarePlus size={17} />
          Nova conversa
        </Button>

        <div className="mt-4 space-y-2">
          {chat.isLoading && (
            <>
              <Skeleton className="h-16" />
              <Skeleton className="h-16" />
            </>
          )}

          {!chat.isLoading && chat.sessions.length === 0 && (
            <button
              className="flex w-full items-center gap-3 rounded-2xl border border-dashed border-slate-300 p-3 text-left text-sm font-semibold text-slate-500 dark:border-white/15 dark:text-slate-400"
              onClick={chat.createSession}
              type="button"
            >
              <MessageSquarePlus size={17} />
              Criar primeira conversa
            </button>
          )}

          {chat.sessions.map((chatSession) => (
            <button
              className={cn(
                'w-full rounded-2xl px-3 py-3 text-left text-sm transition',
                chat.activeSessionId === chatSession.id
                  ? 'bg-slate-950 text-white shadow-lg dark:bg-white dark:text-slate-950'
                  : 'bg-white text-slate-600 hover:bg-slate-100 dark:bg-white/[0.04] dark:text-slate-300 dark:hover:bg-white/10',
              )}
              key={chatSession.id}
              onClick={() => chat.selectSession(chatSession.id)}
              type="button"
            >
              <span className="block truncate font-bold">
                {chatSession.title || 'Acompanhamento IA'}
              </span>
              <span className="mt-1 block text-xs opacity-70">
                {new Date(chatSession.updated_at || chatSession.created_at).toLocaleString('pt-BR')}
              </span>
            </button>
          ))}
        </div>
      </aside>

      <section className="flex min-h-[720px] flex-col">
        <div className="border-b border-slate-200 p-4 dark:border-white/10">
          <div className="flex items-center gap-3">
            <div className="rounded-2xl bg-gradient-to-br from-emerald-500 to-cyan-500 p-3 text-white">
              <Bot size={20} />
            </div>
            <div>
              <h2 className="font-black">{assistantTitle}</h2>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Usa dieta, treino, métricas, condições clínicas e histórico real do Supabase.
              </p>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto bg-[radial-gradient(circle_at_top_left,rgba(16,185,129,0.08),transparent_30%)] p-4">
          {chat.messages.length === 0 && !chat.streaming ? (
            <EmptyState
              description={
                profile?.role === 'nutritionist'
                  ? 'Pergunte sobre evolução, aderência, pontos de atenção ou resumo do plano atual deste paciente.'
                  : 'Pergunte sobre dieta, treino, água, sono, rotina ou aderência. A IA vai respeitar o plano definido.'
              }
              icon={<Sparkles size={22} />}
              title="Comece uma conversa segura"
            />
          ) : (
            <div className="mx-auto max-w-3xl space-y-4">
              {chat.messages.map((message) => (
                <MessageBubble
                  key={message.id}
                  message={message}
                  own={
                    profile?.role === 'patient'
                      ? message.sender === 'patient'
                      : message.sender === 'nutritionist'
                  }
                />
              ))}
              {chat.streaming && (
                <MessageBubble
                  message={{
                    id: 'streaming',
                    session_id: chat.activeSessionId || 'new',
                    sender: 'ai',
                    content: chat.streaming,
                    metadata: null,
                    created_at: new Date().toISOString(),
                  }}
                  own={false}
                  streaming
                />
              )}
              {chat.sending && !chat.streaming && (
                <div className="flex justify-start">
                  <div className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-500 dark:border-white/10 dark:bg-white/[0.04]">
                    <Loader2 className="animate-spin" size={16} />
                    IA analisando contexto clínico...
                  </div>
                </div>
              )}
              <div ref={scrollRef} />
            </div>
          )}
        </div>

        <form
          className="border-t border-slate-200 bg-white/90 p-4 backdrop-blur dark:border-white/10 dark:bg-slate-950/85"
          onSubmit={submit}
        >
          {chat.error && (
            <p className="mb-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm font-semibold text-rose-700 dark:border-rose-400/20 dark:bg-rose-400/10 dark:text-rose-300">
              {chat.error}
            </p>
          )}
          <div className="mx-auto flex max-w-3xl items-end gap-2">
            <Textarea
              className="min-h-24 resize-none"
              onChange={(event) => setContent(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  event.currentTarget.form?.requestSubmit()
                }
              }}
              placeholder="Escreva sua mensagem..."
              value={content}
            />
            <Button disabled={chat.sending || !content.trim()} size="icon" type="submit" variant="premium">
              {chat.sending ? <Loader2 className="animate-spin" size={18} /> : <Send size={18} />}
            </Button>
          </div>
        </form>
      </section>
    </Card>
  )
}

function MessageBubble({
  message,
  own,
  streaming,
}: {
  message: ChatMessageRecord
  own: boolean
  streaming?: boolean
}) {
  return (
    <motion.div
      animate={{ opacity: 1, y: 0 }}
      className={cn('flex', own ? 'justify-end' : 'justify-start')}
      initial={{ opacity: 0, y: 8 }}
      transition={{ duration: 0.18 }}
    >
      <div
        className={cn(
          'max-w-[86%] rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm',
          own
            ? 'bg-slate-950 text-white dark:bg-white dark:text-slate-950'
            : 'border border-slate-200 bg-white text-slate-700 dark:border-white/10 dark:bg-white/[0.04] dark:text-slate-200',
        )}
      >
        <div className="prose prose-sm max-w-none dark:prose-invert prose-p:my-2 prose-ul:my-2 prose-li:my-0 prose-pre:rounded-xl prose-pre:bg-slate-950 prose-code:rounded prose-code:bg-slate-100 prose-code:px-1 prose-code:py-0.5 dark:prose-code:bg-white/10">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
        </div>
        {streaming && (
          <span className="mt-2 inline-flex h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
        )}
      </div>
    </motion.div>
  )
}
