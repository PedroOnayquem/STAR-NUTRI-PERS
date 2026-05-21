import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
} from 'react'
import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  Bot,
  BrainCircuit,
  Check,
  ChevronDown,
  CircleAlert,
  CircleCheck,
  Clock,
  Loader2,
  MessageSquarePlus,
  Search,
  Send,
  Sparkles,
  XCircle,
} from 'lucide-react'
import { Button } from '../../../components/ui/Button'
import { Skeleton } from '../../../components/ui/Skeleton'
import { Textarea } from '../../../components/ui/Input'
import { cn } from '../../../lib/utils'
import type {
  ChatMessageRecord,
  ChatSessionRecord,
  PatientRecord,
} from '../../clinical/types'
import { useStarNutriChat } from '../hooks/useStarNutriChat'
import {
  AI_REASONING_LEVELS,
  type AiReasoningLevel,
  type ChatScope,
} from '../types'

type ChatExperienceProps = {
  className?: string
  externalQueryKey?: unknown[]
  onPatientChange?: (patientId: string) => void
  patientId?: string | null
  patientName?: string
  patients?: PatientRecord[]
  scope: ChatScope
}

export function ChatExperience({
  className,
  externalQueryKey,
  onPatientChange,
  patientId,
  patientName,
  patients,
  scope,
}: ChatExperienceProps) {
  const [content, setContent] = useState('')
  const [conversationSearch, setConversationSearch] = useState('')
  const [reasoningLevel, setReasoningLevel] = useState<AiReasoningLevel>('medium')
  const scrollRef = useRef<HTMLDivElement>(null)
  const normalizedPatientId = patientId ?? undefined
  const chat = useStarNutriChat({
    externalQueryKey,
    patientId: normalizedPatientId,
    reasoningLevel,
    scope,
  })

  const patientOptions = useMemo(
    () =>
      (patients ?? []).map((patient) => ({
        email: patient.profile?.email ?? '',
        id: patient.id,
        name: patient.profile?.full_name ?? 'Paciente',
        objective: patient.objective ?? '',
      })),
    [patients],
  )
  const selectedPatient = patientOptions.find((patient) => patient.id === patientId)
  const canSelectPatient = Boolean(onPatientChange && patientOptions.length > 0)
  const selectedPatientName = selectedPatient?.name ?? patientName ?? 'Paciente'
  const isProfessional = scope === 'nutritionist'
  const hasRequiredFocus = !isProfessional || !canSelectPatient || Boolean(patientId)
  const currentSession = chat.sessions.find(
    (session) => session.id === chat.activeSessionId,
  )
  const currentTitle = currentSession?.title || 'Nova conversa'
  const filteredSessions = useMemo(() => {
    const term = conversationSearch.trim().toLowerCase()
    if (!term) return chat.sessions

    return chat.sessions.filter((session) => {
      const title = session.title?.toLowerCase() ?? ''
      const patient = selectedPatientName.toLowerCase()
      const date = formatSessionDate(session).toLowerCase()
      return title.includes(term) || patient.includes(term) || date.includes(term)
    })
  }, [chat.sessions, conversationSearch, selectedPatientName])

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [chat.activeSessionId, chat.messages, chat.streaming])

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextContent = content.trim()
    if (!nextContent || chat.sending || !hasRequiredFocus) return
    setContent('')
    chat.sendMessage(nextContent)
  }

  return (
    <div
      className={cn(
        'h-[calc(100vh-8rem)] min-h-[700px] overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_24px_80px_rgba(15,23,42,0.08)] dark:border-white/10 dark:bg-slate-950 dark:shadow-none',
        className,
      )}
    >
      <div className="grid h-full min-h-0 lg:grid-cols-[292px_minmax(0,1fr)]">
        <ChatSidebar
          canCreate={hasRequiredFocus}
          creating={chat.creatingSession}
          currentSessionId={chat.activeSessionId}
          isLoading={chat.isLoading}
          onCreateSession={chat.createSession}
          onSearch={setConversationSearch}
          onSelectSession={chat.selectSession}
          patientName={isProfessional ? selectedPatientName : 'Chat pessoal'}
          search={conversationSearch}
          sessions={filteredSessions}
        />

        <section className="flex min-h-0 flex-col bg-white dark:bg-slate-950">
          <ChatTopbar
            currentTitle={currentTitle}
            onPatientChange={onPatientChange}
            onReasoningChange={setReasoningLevel}
            patientId={patientId ?? ''}
            patientName={selectedPatientName}
            patients={patientOptions}
            reasoningLevel={reasoningLevel}
            scope={scope}
          />

          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-8">
            <div className="mx-auto flex min-h-full max-w-3xl flex-col">
              {!hasRequiredFocus ? (
                <ChatEmpty
                  description="Escolha um paciente no topo para carregar contexto e historico."
                  title="Selecione um paciente"
                />
              ) : chat.isLoading && !chat.messages.length ? (
                <MessageSkeleton />
              ) : chat.messages.length === 0 && !chat.streaming ? (
                <ChatEmpty
                  description={
                    isProfessional
                      ? 'Pergunte sobre evolucao, aderencia ou pontos de atencao.'
                      : 'Pergunte sobre sua dieta ativa, treino, rotina, compras ou organizacao do dia.'
                  }
                  title={
                    isProfessional
                      ? `Chat profissional para ${selectedPatientName}`
                      : 'Seu chat pessoal com IA'
                  }
                />
              ) : (
                <div className="space-y-6">
                  {chat.messages.map((message) => (
                    <MessageBubble
                      key={message.id}
                      message={message}
                      own={
                        scope === 'patient'
                          ? message.sender === 'patient'
                          : message.sender === 'nutritionist'
                      }
                    />
                  ))}
                  {chat.streaming && (
                    <MessageBubble
                      message={{
                        content: chat.streaming,
                        created_at: new Date().toISOString(),
                        chat_id: chat.activeSessionId || 'new',
                        id: 'streaming',
                        metadata: { agent_actions: chat.streamingActions },
                        sender: 'ai',
                      }}
                      own={false}
                      streaming
                    />
                  )}
                  {chat.sending && !chat.streaming && <TypingBubble />}
                  <div ref={scrollRef} />
                </div>
              )}
            </div>
          </div>

          <form
            className="border-t border-slate-200 bg-white/95 px-4 py-4 backdrop-blur dark:border-white/10 dark:bg-slate-950/95 sm:px-8"
            onSubmit={submit}
          >
            <div className="mx-auto max-w-3xl">
              {chat.error && (
                <p className="mb-3 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700 dark:border-rose-400/20 dark:bg-rose-400/10 dark:text-rose-300">
                  {chat.error}
                </p>
              )}
              <div className="flex items-end gap-2 rounded-3xl border border-slate-200 bg-slate-50 p-2 shadow-sm transition focus-within:border-emerald-400 focus-within:ring-4 focus-within:ring-emerald-500/10 dark:border-white/10 dark:bg-white/[0.04]">
                <Textarea
                  aria-label="Mensagem para a IA"
                  className="min-h-12 resize-none border-0 bg-transparent px-3 py-3 shadow-none focus:ring-0 dark:bg-transparent"
                  disabled={chat.sending || !hasRequiredFocus}
                  onChange={(event) => setContent(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                      event.preventDefault()
                      event.currentTarget.form?.requestSubmit()
                    }
                  }}
                  placeholder={
                    hasRequiredFocus
                      ? isProfessional
                        ? 'Mensagem profissional para o Star Nutri...'
                        : 'Pergunte sobre sua rotina...'
                      : 'Selecione um paciente para conversar'
                  }
                  rows={1}
                  value={content}
                />
                <Button
                  aria-label="Enviar mensagem"
                  disabled={chat.sending || !content.trim() || !hasRequiredFocus}
                  size="icon"
                  type="submit"
                  variant="primary"
                >
                  {chat.sending ? (
                    <Loader2 className="animate-spin" size={18} />
                  ) : (
                    <Send size={18} />
                  )}
                </Button>
              </div>
            </div>
          </form>
        </section>
      </div>
    </div>
  )
}

function ChatSidebar({
  canCreate,
  creating,
  currentSessionId,
  isLoading,
  onCreateSession,
  onSearch,
  onSelectSession,
  patientName,
  search,
  sessions,
}: {
  canCreate: boolean
  creating: boolean
  currentSessionId: string | null
  isLoading: boolean
  onCreateSession: () => void
  onSearch: (value: string) => void
  onSelectSession: (sessionId: string) => void
  patientName: string
  search: string
  sessions: ChatSessionRecord[]
}) {
  return (
    <aside className="flex max-h-80 min-h-0 flex-col border-b border-slate-200 bg-slate-50/85 dark:border-white/10 dark:bg-white/[0.03] lg:max-h-none lg:border-b-0 lg:border-r">
      <div className="space-y-3 p-3">
        <Button
          className="h-10 w-full justify-start rounded-2xl"
          disabled={!canCreate || creating}
          onClick={onCreateSession}
          type="button"
          variant="primary"
        >
          {creating ? (
            <Loader2 className="animate-spin" size={17} />
          ) : (
            <MessageSquarePlus size={17} />
          )}
          Novo Chat
        </Button>

        <label className="flex h-10 items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 text-slate-500 shadow-sm dark:border-white/10 dark:bg-slate-950/60 dark:text-slate-400">
          <Search size={16} />
          <input
            className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-slate-400"
            onChange={(event) => onSearch(event.target.value)}
            placeholder="Buscar conversas"
            value={search}
          />
        </label>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        {isLoading ? (
          <div className="space-y-2 px-1">
            <Skeleton className="h-16 rounded-2xl" />
            <Skeleton className="h-16 rounded-2xl" />
            <Skeleton className="h-16 rounded-2xl" />
          </div>
        ) : sessions.length === 0 ? (
          <div className="mx-1 rounded-2xl border border-dashed border-slate-300 p-4 text-sm text-slate-500 dark:border-white/15 dark:text-slate-400">
            Nenhuma conversa encontrada.
          </div>
        ) : (
          <div className="space-y-1">
            {sessions.map((session) => (
              <button
                className={cn(
                  'group w-full rounded-2xl px-3 py-3 text-left transition',
                  currentSessionId === session.id
                    ? 'bg-white text-slate-950 shadow-sm ring-1 ring-slate-200 dark:bg-white/10 dark:text-white dark:ring-white/10'
                    : 'text-slate-600 hover:bg-white hover:text-slate-950 dark:text-slate-300 dark:hover:bg-white/[0.07] dark:hover:text-white',
                )}
                key={session.id}
                onClick={() => onSelectSession(session.id)}
                type="button"
              >
                <span className="block truncate text-sm font-bold">
                  {session.title || 'Nova conversa'}
                </span>
                <span className="mt-1 block truncate text-xs text-slate-400">
                  {patientName} · {formatSessionDate(session)}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    </aside>
  )
}

function ChatTopbar({
  currentTitle,
  onPatientChange,
  onReasoningChange,
  patientId,
  patientName,
  patients,
  reasoningLevel,
  scope,
}: {
  currentTitle: string
  onPatientChange?: (patientId: string) => void
  onReasoningChange: (level: AiReasoningLevel) => void
  patientId: string
  patientName: string
  patients: Array<{ email: string; id: string; name: string; objective: string }>
  reasoningLevel: AiReasoningLevel
  scope: ChatScope
}) {
  const [patientMenuOpen, setPatientMenuOpen] = useState(false)
  const [reasoningMenuOpen, setReasoningMenuOpen] = useState(false)
  const selectedReasoning = AI_REASONING_LEVELS.find(
    (level) => level.id === reasoningLevel,
  )

  return (
    <header className="flex min-h-16 flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur dark:border-white/10 dark:bg-slate-950/90 sm:px-5">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-slate-950 text-white dark:bg-white dark:text-slate-950">
          <Bot size={17} />
        </div>
        <div className="min-w-0">
          <h2 className="truncate text-sm font-black text-slate-950 dark:text-white">
            {currentTitle}
          </h2>
          <p className="truncate text-xs text-slate-500 dark:text-slate-400">
            {scope === 'nutritionist'
              ? selectedReasoning?.label ?? 'Pensamento Medio'
              : 'Historico pessoal e privado'}
          </p>
        </div>
      </div>

      <div className="flex w-full min-w-0 flex-nowrap justify-end gap-2 overflow-x-auto pb-1 sm:w-auto sm:flex-1 sm:pb-0">
        {onPatientChange && patients.length > 0 ? (
          <PatientFocusMenu
            onChange={(nextPatientId) => {
              onPatientChange(nextPatientId)
              setPatientMenuOpen(false)
            }}
            onOpenChange={setPatientMenuOpen}
            open={patientMenuOpen}
            patientId={patientId}
            patients={patients}
          />
        ) : (
          <StaticPatientPill patientName={patientName} />
        )}

        {scope === 'nutritionist' && (
          <ReasoningMenu
            onChange={(nextLevel) => {
              onReasoningChange(nextLevel)
              setReasoningMenuOpen(false)
            }}
            onOpenChange={setReasoningMenuOpen}
            open={reasoningMenuOpen}
            reasoningLevel={reasoningLevel}
          />
        )}
      </div>
    </header>
  )
}

function PatientFocusMenu({
  onChange,
  onOpenChange,
  open,
  patientId,
  patients,
}: {
  onChange: (patientId: string) => void
  onOpenChange: (open: boolean) => void
  open: boolean
  patientId: string
  patients: Array<{ email: string; id: string; name: string; objective: string }>
}) {
  const selectedPatient = patients.find((patient) => patient.id === patientId) ?? patients[0]

  return (
    <div className="relative min-w-0 flex-1 sm:flex-none">
      <button
        aria-expanded={open}
        aria-label="Paciente em foco"
        className="group inline-flex h-12 w-full min-w-0 max-w-[min(58vw,20rem)] items-center gap-2 rounded-2xl border border-emerald-200/80 bg-gradient-to-b from-white to-emerald-50/70 px-2.5 py-1.5 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-emerald-300 hover:shadow-md dark:border-emerald-400/20 dark:from-white/[0.08] dark:to-emerald-400/10 sm:w-auto sm:max-w-80"
        onClick={() => onOpenChange(!open)}
        type="button"
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-emerald-500 text-xs font-black text-white shadow-[0_10px_24px_rgba(16,185,129,0.25)]">
          {getInitials(selectedPatient?.name ?? 'P')}
        </span>
        <span className="block min-w-0 flex-1 truncate text-sm font-black text-slate-950 dark:text-white">
          {selectedPatient?.name ?? 'Selecionar paciente'}
        </span>
        <ChevronDown
          className={cn(
            'shrink-0 text-emerald-600 transition dark:text-emerald-300',
            open && 'rotate-180',
          )}
          size={16}
        />
      </button>

      {open && (
        <div className="absolute right-0 z-30 mt-2 w-[min(92vw,380px)] overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_24px_70px_rgba(15,23,42,0.18)] dark:border-white/10 dark:bg-slate-900">
          <div className="max-h-80 overflow-y-auto p-2">
            {patients.map((patient) => {
              const selected = patient.id === patientId
              return (
                <button
                  className={cn(
                    'flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-left transition',
                    selected
                      ? 'bg-emerald-50 text-emerald-950 ring-1 ring-emerald-200 dark:bg-emerald-400/10 dark:text-emerald-100 dark:ring-emerald-400/20'
                      : 'hover:bg-slate-50 dark:hover:bg-white/[0.06]',
                  )}
                  key={patient.id}
                  onClick={() => onChange(patient.id)}
                  type="button"
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-slate-950 text-xs font-black text-white dark:bg-white dark:text-slate-950">
                    {getInitials(patient.name)}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-black">
                      {patient.name}
                    </span>
                    <span className="mt-0.5 block truncate text-xs text-slate-500 dark:text-slate-400">
                      {patient.objective || patient.email || 'Sem objetivo cadastrado'}
                    </span>
                  </span>
                  {selected && <Check className="text-emerald-600" size={17} />}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

function StaticPatientPill({ patientName }: { patientName: string }) {
  return (
    <div className="inline-flex h-12 min-w-0 max-w-[min(58vw,20rem)] items-center gap-2 truncate rounded-2xl border border-slate-200 bg-slate-50 px-3 text-sm font-semibold shadow-sm dark:border-white/10 dark:bg-white/[0.04] sm:max-w-72">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-slate-950 text-xs font-black text-white dark:bg-white dark:text-slate-950">
        {getInitials(patientName)}
      </span>
      <span className="block min-w-0 truncate text-sm font-black">{patientName}</span>
    </div>
  )
}

function ReasoningMenu({
  onChange,
  onOpenChange,
  open,
  reasoningLevel,
}: {
  onChange: (level: AiReasoningLevel) => void
  onOpenChange: (open: boolean) => void
  open: boolean
  reasoningLevel: AiReasoningLevel
}) {
  const selected = AI_REASONING_LEVELS.find((level) => level.id === reasoningLevel)

  return (
    <div className="relative shrink-0">
      <button
        aria-expanded={open}
        aria-label="Nivel de pensamento da IA"
        className="group inline-flex h-12 items-center gap-2 rounded-2xl border border-cyan-200/80 bg-gradient-to-b from-white to-cyan-50/70 px-3 py-1.5 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-cyan-300 hover:shadow-md dark:border-cyan-400/20 dark:from-white/[0.08] dark:to-cyan-400/10"
        onClick={() => onOpenChange(!open)}
        type="button"
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-cyan-500 text-white shadow-[0_10px_24px_rgba(6,182,212,0.22)]">
          <BrainCircuit size={16} />
        </span>
        <span className="block min-w-0 truncate text-sm font-black text-slate-950 dark:text-white">
          {selected?.shortLabel ?? 'Medio'}
        </span>
        <ChevronDown
          className={cn(
            'shrink-0 text-cyan-600 transition dark:text-cyan-300',
            open && 'rotate-180',
          )}
          size={16}
        />
      </button>

      {open && (
        <div className="absolute right-0 z-30 mt-2 w-[min(92vw,340px)] overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_24px_70px_rgba(15,23,42,0.18)] dark:border-white/10 dark:bg-slate-900">
          <div className="p-2">
            {AI_REASONING_LEVELS.map((level) => {
              const active = level.id === reasoningLevel
              return (
                <button
                  className={cn(
                    'flex w-full items-start gap-3 rounded-2xl px-3 py-3 text-left transition',
                    active
                      ? 'bg-cyan-50 text-cyan-950 ring-1 ring-cyan-200 dark:bg-cyan-400/10 dark:text-cyan-100 dark:ring-cyan-400/20'
                      : 'hover:bg-slate-50 dark:hover:bg-white/[0.06]',
                  )}
                  key={level.id}
                  onClick={() => onChange(level.id)}
                  type="button"
                >
                  <span className={cn('mt-1 h-2.5 w-2.5 shrink-0 rounded-full', reasoningDotClass(level.id))} />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-black">{level.label}</span>
                    <span className="mt-0.5 block text-xs leading-5 text-slate-500 dark:text-slate-400">
                      {level.description}
                    </span>
                  </span>
                  {active && <Check className="text-cyan-600" size={17} />}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

function getInitials(name: string) {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('') || 'SN'
}

function reasoningDotClass(level: AiReasoningLevel) {
  if (level === 'low') return 'bg-emerald-400'
  if (level === 'medium') return 'bg-cyan-400'
  if (level === 'high') return 'bg-blue-500'
  return 'bg-violet-500'
}

type AgentAction = {
  error?: string | null
  label?: string
  requires_confirmation?: boolean
  status?: 'executed' | 'skipped' | 'failed' | 'pending_confirmation'
  summary?: string | null
  tool?: string
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
  const actions = getAgentActions(message.metadata)

  return (
    <motion.div
      animate={{ opacity: 1, y: 0 }}
      className={cn('flex gap-3', own ? 'justify-end' : 'justify-start')}
      initial={{ opacity: 0, y: 8 }}
      transition={{ duration: 0.16 }}
    >
      {!own && (
        <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-700 dark:text-emerald-300">
          <Sparkles size={15} />
        </div>
      )}
      <div
        className={cn(
          'max-w-[88%] text-sm leading-7',
          own
            ? 'rounded-3xl bg-slate-950 px-4 py-3 text-white dark:bg-white dark:text-slate-950'
            : 'min-w-0 flex-1 text-slate-700 dark:text-slate-100',
        )}
      >
        <MarkdownContent content={message.content} />
        {!own && actions.length > 0 && <AgentActionList actions={actions} />}
        {streaming && (
          <span className="mt-2 inline-flex h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
        )}
      </div>
    </motion.div>
  )
}

function AgentActionList({ actions }: { actions: AgentAction[] }) {
  return (
    <div className="mt-3 space-y-2">
      {actions.map((action, index) => {
        const status = action.status ?? 'skipped'
        const Icon = actionIcon(status)
        return (
          <div
            className={cn(
              'flex items-start gap-2 rounded-2xl border px-3 py-2 text-xs leading-5',
              actionTone(status),
            )}
            key={`${action.tool ?? 'action'}-${index}`}
          >
            <Icon className="mt-0.5 shrink-0" size={15} />
            <div className="min-w-0">
              <p className="font-black">{action.label ?? action.tool ?? 'Acao do agente'}</p>
              {(action.summary || action.error) && (
                <p className="mt-0.5 text-[11px] leading-5 opacity-80">
                  {action.summary || action.error}
                </p>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function getAgentActions(metadata: ChatMessageRecord['metadata']): AgentAction[] {
  const raw = metadata?.agent_actions
  if (!Array.isArray(raw)) return []
  return raw.filter((item): item is AgentAction => Boolean(item && typeof item === 'object'))
}

function actionIcon(status: AgentAction['status']) {
  if (status === 'executed') return CircleCheck
  if (status === 'pending_confirmation') return Clock
  if (status === 'failed') return XCircle
  return CircleAlert
}

function actionTone(status: AgentAction['status']) {
  if (status === 'executed') {
    return 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-200'
  }
  if (status === 'pending_confirmation') {
    return 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-400/20 dark:bg-amber-400/10 dark:text-amber-200'
  }
  if (status === 'failed') {
    return 'border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-400/20 dark:bg-rose-400/10 dark:text-rose-200'
  }
  return 'border-slate-200 bg-slate-50 text-slate-600 dark:border-white/10 dark:bg-white/[0.04] dark:text-slate-300'
}

function MarkdownContent({ content }: { content: string }) {
  return (
    <div className="max-w-none text-sm leading-7 [&_a]:font-semibold [&_a]:text-emerald-600 dark:[&_a]:text-emerald-300 [&_blockquote]:border-l-2 [&_blockquote]:border-slate-300 [&_blockquote]:pl-4 [&_code]:rounded-md [&_code]:bg-slate-100 [&_code]:px-1.5 [&_code]:py-0.5 dark:[&_code]:bg-white/10 [&_h1]:mb-3 [&_h1]:text-xl [&_h1]:font-black [&_h2]:mb-2 [&_h2]:mt-4 [&_h2]:text-lg [&_h2]:font-black [&_li]:my-1 [&_ol]:my-3 [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:my-2 [&_pre]:my-3 [&_pre]:overflow-x-auto [&_pre]:rounded-2xl [&_pre]:bg-slate-950 [&_pre]:p-4 [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_table]:my-4 [&_table]:w-full [&_table]:overflow-hidden [&_table]:rounded-2xl [&_table]:text-left [&_td]:border-t [&_td]:border-slate-200 [&_td]:px-3 [&_td]:py-2 dark:[&_td]:border-white/10 [&_th]:bg-slate-100 [&_th]:px-3 [&_th]:py-2 [&_th]:font-bold dark:[&_th]:bg-white/10 [&_ul]:my-3 [&_ul]:list-disc [&_ul]:pl-5">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  )
}

function TypingBubble() {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-8 w-8 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-700 dark:text-emerald-300">
        <Sparkles size={15} />
      </div>
      <div className="inline-flex items-center gap-1 rounded-3xl border border-slate-200 bg-white px-4 py-3 dark:border-white/10 dark:bg-white/[0.04]">
        <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.2s]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.1s]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400" />
      </div>
    </div>
  )
}

function MessageSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-20 max-w-xl rounded-3xl" />
      <Skeleton className="ml-auto h-14 max-w-md rounded-3xl" />
      <Skeleton className="h-28 max-w-2xl rounded-3xl" />
    </div>
  )
}

function ChatEmpty({
  description,
  title,
}: {
  description: string
  title: string
}) {
  return (
    <div className="flex flex-1 items-center justify-center py-16 text-center">
      <div>
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-3xl bg-slate-950 text-white dark:bg-white dark:text-slate-950">
          <Bot size={20} />
        </div>
        <h3 className="mt-4 text-lg font-black text-slate-950 dark:text-white">
          {title}
        </h3>
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500 dark:text-slate-400">
          {description}
        </p>
      </div>
    </div>
  )
}

function formatSessionDate(session: ChatSessionRecord) {
  return new Date(session.updated_at || session.created_at).toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
  })
}
