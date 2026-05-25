import {
  memo,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type FormEvent,
  type KeyboardEvent,
  type RefObject,
} from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion } from 'framer-motion'
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
  Mic,
  Search,
  Send,
  XCircle,
} from 'lucide-react'
import { Link } from 'react-router-dom'
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
  const [reasoningLevel, setReasoningLevel] = useState<AiReasoningLevel>(() =>
    readReasoningPreference('star-nutri:chat-reasoning:draft') ?? 'medium',
  )
  const scrollRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const deferredConversationSearch = useDeferredValue(conversationSearch)
  const normalizedPatientId = patientId ?? undefined
  const isProfessional = scope === 'nutritionist'
  const chat = useStarNutriChat({
    externalQueryKey,
    patientId: normalizedPatientId,
    reasoningLevel: isProfessional ? reasoningLevel : 'medium',
    scope,
  })
  const reasoningStorageKey = isProfessional
    ? `star-nutri:chat-reasoning:${chat.activeSessionId ?? normalizedPatientId ?? 'draft'}`
    : null

  const patientOptions = useMemo(
    () => {
      const mapped = (patients ?? []).map((patient) => ({
        email: patient.profile?.email ?? '',
        id: patient.id,
        name: patient.profile?.full_name ?? 'Paciente',
        objective: patient.objective ?? '',
      }))

      if (mapped.length > 0) return mapped

      return patientName || patientId
        ? [{
            email: '',
            id: patientId ?? 'me',
            name: patientName ?? 'Paciente',
            objective: '',
          }]
        : []
    },
    [patientId, patientName, patients],
  )
  const selectedPatient =
    patientOptions.find((patient) => patient.id === patientId) ?? patientOptions[0]
  const selectedPatientName = selectedPatient?.name ?? patientName ?? 'Paciente'
  const focusedPatientId = selectedPatient?.id ?? patientId ?? ''
  const hasRequiredFocus = !isProfessional || Boolean(patientId)
  const currentSession = chat.sessions.find(
    (session) => session.id === chat.activeSessionId,
  )
  const currentTitle = currentSession?.title || 'Nova conversa'
  const filteredSessions = useMemo(() => {
    const term = deferredConversationSearch.trim().toLowerCase()
    if (!term) return chat.sessions

    return chat.sessions.filter((session) => {
      const title = session.title?.toLowerCase() ?? ''
      const patient = selectedPatientName.toLowerCase()
      const date = formatSessionDate(session).toLowerCase()
      return title.includes(term) || patient.includes(term) || date.includes(term)
    })
  }, [chat.sessions, deferredConversationSearch, selectedPatientName])

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [chat.activeSessionId, chat.messages, chat.streaming])

  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return
    textarea.style.height = '0px'
    textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`
  }, [content])

  useEffect(() => {
    if (!reasoningStorageKey) return
    const saved = readReasoningPreference(reasoningStorageKey)
    if (saved && saved !== reasoningLevel) {
      const timeout = window.setTimeout(() => setReasoningLevel(saved), 0)
      return () => window.clearTimeout(timeout)
    }
    if (!saved) {
      writeReasoningPreference(reasoningStorageKey, reasoningLevel)
    }
  }, [reasoningLevel, reasoningStorageKey])

  function changeReasoningLevel(level: AiReasoningLevel) {
    setReasoningLevel(level)
    writeReasoningPreference('star-nutri:chat-reasoning:draft', level)
    if (reasoningStorageKey) {
      writeReasoningPreference(reasoningStorageKey, level)
    }
  }

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
        'h-[calc(100vh-8rem)] min-h-[680px] overflow-hidden rounded-[28px] border border-[var(--chat-border)] bg-[radial-gradient(circle_at_18%_0%,rgba(34,211,238,0.14),transparent_28%),radial-gradient(circle_at_86%_12%,rgba(16,185,129,0.12),transparent_24%),linear-gradient(145deg,#060818_0%,#0b1020_48%,#0f172a_100%)] text-slate-100 shadow-[0_28px_90px_rgba(2,6,23,0.36),0_0_70px_var(--chat-glow)]',
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

        <section className="flex min-h-0 flex-col bg-[linear-gradient(180deg,rgba(15,23,42,0.42),rgba(2,6,23,0.18))]">
          <ChatTopbar
            currentTitle={currentTitle}
            onPatientChange={onPatientChange}
            patientId={focusedPatientId}
            patientName={selectedPatientName}
            patients={patientOptions}
            scope={scope}
          />

          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-6 [scrollbar-color:rgba(56,189,248,0.32)_transparent] [scrollbar-width:thin] sm:px-8">
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

          <ChatComposer
            content={content}
            disabled={chat.sending || !hasRequiredFocus}
            error={chat.error}
            isProfessional={isProfessional}
            onChange={setContent}
            onReasoningChange={changeReasoningLevel}
            onSubmit={submit}
            placeholder={
              hasRequiredFocus
                ? isProfessional
                  ? 'Mensagem para o Star Nutri...'
                  : 'Pergunte sobre sua rotina...'
                : 'Selecione um paciente para conversar'
            }
            reasoningLevel={reasoningLevel}
            sending={chat.sending}
            textareaRef={textareaRef}
          />
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
    <aside className="flex max-h-72 min-h-0 flex-col border-b border-[var(--chat-border)] bg-[rgba(2,6,23,0.30)] backdrop-blur-xl lg:max-h-none lg:border-b-0 lg:border-r">
      <div className="space-y-3 p-3">
        <Button
          className="h-10 w-full justify-start rounded-2xl border border-cyan-300/15 bg-slate-900/70 text-slate-100 shadow-[0_12px_34px_rgba(2,6,23,0.20)] hover:border-cyan-300/25 hover:bg-slate-800/80 hover:text-white hover:shadow-[0_16px_42px_rgba(56,189,248,0.12)]"
          disabled={!canCreate || creating}
          onClick={onCreateSession}
          type="button"
          variant="secondary"
        >
          {creating ? (
            <Loader2 className="animate-spin" size={17} />
          ) : (
            <MessageSquarePlus size={17} />
          )}
          Novo Chat
        </Button>

        <label className="flex h-10 items-center gap-2 rounded-2xl border border-cyan-300/10 bg-slate-950/35 px-3 text-slate-400 shadow-inner shadow-cyan-950/10 transition focus-within:border-cyan-300/35 focus-within:bg-slate-950/55 focus-within:text-cyan-100 focus-within:ring-2 focus-within:ring-cyan-400/10">
          <Search size={16} />
          <input
            className="min-w-0 flex-1 bg-transparent text-sm text-slate-100 outline-none placeholder:text-slate-500"
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
          <div className="mx-1 rounded-2xl border border-dashed border-cyan-300/15 bg-slate-950/20 p-4 text-sm text-slate-400">
            Nenhuma conversa encontrada.
          </div>
        ) : (
          <div className="space-y-1">
            {sessions.map((session) => (
              <button
                className={cn(
                  'group w-full rounded-2xl px-3 py-3 text-left transition',
                  currentSessionId === session.id
                    ? 'bg-cyan-300/10 text-white shadow-[inset_0_0_0_1px_rgba(34,211,238,0.14),0_12px_36px_rgba(8,47,73,0.16)]'
                    : 'text-slate-400 hover:bg-cyan-300/[0.07] hover:text-slate-100',
                )}
                key={session.id}
                onClick={() => onSelectSession(session.id)}
                type="button"
              >
                <span className="block truncate text-sm font-bold">
                  {session.title || 'Nova conversa'}
                </span>
                <span className="mt-1 block truncate text-xs text-slate-500 group-hover:text-slate-400">
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
  patientId,
  patientName,
  patients,
  scope,
}: {
  currentTitle: string
  onPatientChange?: (patientId: string) => void
  patientId: string
  patientName: string
  patients: Array<{ email: string; id: string; name: string; objective: string }>
  scope: ChatScope
}) {
  const [patientMenuOpen, setPatientMenuOpen] = useState(false)

  return (
    <header className="flex min-h-14 flex-wrap items-center justify-between gap-3 border-b border-[var(--chat-border)] bg-[rgba(6,8,24,0.64)] px-4 py-2.5 shadow-[0_1px_0_rgba(56,189,248,0.05)] backdrop-blur-xl sm:px-5">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <div className="min-w-0">
          <h2 className="truncate text-sm font-semibold text-slate-50">
            {currentTitle}
          </h2>
          <p className="truncate text-xs text-slate-400">
            {scope === 'nutritionist' ? 'Chat do nutricionista' : 'Chat do paciente'}
          </p>
        </div>
      </div>

      <div className="flex w-full min-w-0 flex-nowrap justify-end gap-2 pb-1 sm:w-auto sm:flex-1 sm:pb-0">
        {patients.length > 0 ? (
          <PatientFocusMenu
            onChange={(nextPatientId) => {
              onPatientChange?.(nextPatientId)
              setPatientMenuOpen(false)
            }}
            onOpenChange={setPatientMenuOpen}
            open={patientMenuOpen}
            patientId={patientId}
            patients={patients}
            scope={scope}
          />
        ) : (
          <StaticPatientPill patientName={patientName} />
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
  scope,
}: {
  onChange: (patientId: string) => void
  onOpenChange: (open: boolean) => void
  open: boolean
  patientId: string
  patients: Array<{ email: string; id: string; name: string; objective: string }>
  scope: ChatScope
}) {
  const selectedPatient = patients.find((patient) => patient.id === patientId) ?? patients[0]
  const [search, setSearch] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const [anchorRect, setAnchorRect] = useState<PatientMenuAnchorRect | null>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const { debouncedValue: debouncedSearch, pending } = useDebouncedValue(search, 180)
  const filteredPatients = useMemo(() => {
    const term = debouncedSearch.trim().toLowerCase()
    if (!term) return patients

    return patients.filter((patient) => {
      const haystack = `${patient.name} ${patient.email} ${patient.objective}`.toLowerCase()
      return haystack.includes(term)
    })
  }, [debouncedSearch, patients])
  const fullListPath = scope === 'nutritionist' ? '/nutritionist/patients' : '/patient/profile'
  const isMobile = typeof window !== 'undefined' && window.matchMedia('(max-width: 640px)').matches
  const menuStyle = getPatientMenuStyle(anchorRect, isMobile)

  function setOpen(nextOpen: boolean) {
    if (nextOpen) {
      setAnchorRect(readPatientMenuAnchor(triggerRef.current))
      setSearch('')
      setActiveIndex(Math.max(0, filteredPatients.findIndex((patient) => patient.id === patientId)))
      window.setTimeout(() => searchRef.current?.focus(), 40)
    }
    onOpenChange(nextOpen)
  }

  function selectPatient(nextPatientId: string) {
    onChange(nextPatientId)
    setOpen(false)
  }

  function handleTriggerKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key !== 'ArrowDown' && event.key !== 'Enter' && event.key !== ' ') return
    event.preventDefault()
    setOpen(true)
  }

  function handleSearchKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape') {
      event.preventDefault()
      setOpen(false)
      triggerRef.current?.focus()
      return
    }

    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActiveIndex((current) => Math.min(current + 1, filteredPatients.length - 1))
      return
    }

    if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex((current) => Math.max(current - 1, 0))
      return
    }

    if (event.key === 'Enter' && filteredPatients[activeIndex]) {
      event.preventDefault()
      selectPatient(filteredPatients[activeIndex].id)
    }
  }

  useEffect(() => {
    if (!open) return

    const updatePosition = () => setAnchorRect(readPatientMenuAnchor(triggerRef.current))
    window.addEventListener('resize', updatePosition)
    window.addEventListener('scroll', updatePosition, true)

    return () => {
      window.removeEventListener('resize', updatePosition)
      window.removeEventListener('scroll', updatePosition, true)
    }
  }, [open])

  return (
    <div className="min-w-0 flex-1 sm:flex-none">
      <button
        ref={triggerRef}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label="Paciente em foco"
        className="group inline-flex h-9 w-full min-w-0 max-w-[min(64vw,20rem)] items-center gap-2 rounded-full border border-cyan-300/10 bg-slate-950/35 px-3 text-left text-slate-100 shadow-[0_0_0_1px_rgba(255,255,255,0.02)] transition hover:border-cyan-300/25 hover:bg-cyan-300/[0.08] hover:text-white hover:shadow-[0_0_24px_rgba(56,189,248,0.10)] sm:w-auto sm:max-w-80"
        onClick={() => setOpen(!open)}
        onKeyDown={handleTriggerKeyDown}
        type="button"
      >
        <span className="block min-w-0 flex-1 truncate text-sm font-medium">
          {selectedPatient?.name ?? 'Selecionar paciente'}
        </span>
        <ChevronDown
          className={cn(
            'shrink-0 text-cyan-200/70 transition group-hover:text-cyan-100',
            open && 'rotate-180',
          )}
          size={15}
        />
      </button>

      {createPortal(
        <AnimatePresence>
          {open && (
            <>
              <motion.div
                animate={{ opacity: 1 }}
                className="fixed inset-0 z-40 bg-[#020617]/35 backdrop-blur-[3px]"
                exit={{ opacity: 0 }}
                initial={{ opacity: 0 }}
                onClick={() => setOpen(false)}
              />
              <motion.div
                animate={isMobile ? { opacity: 1, y: 0 } : { opacity: 1, scale: 1, y: 0 }}
                aria-label="Selecionar paciente"
                aria-modal={isMobile}
                className={cn(
                  'fixed z-50 flex overflow-hidden border border-cyan-300/15 bg-[rgba(11,16,32,0.94)] text-slate-100 shadow-[0_24px_80px_rgba(2,6,23,0.56),0_0_70px_rgba(56,189,248,0.16)] backdrop-blur-2xl',
                  isMobile
                    ? 'inset-x-3 bottom-3 max-h-[78vh] flex-col rounded-[24px]'
                    : 'max-h-[520px] flex-col rounded-2xl',
                )}
                exit={isMobile ? { opacity: 0, y: 24 } : { opacity: 0, scale: 0.98, y: -6 }}
                initial={isMobile ? { opacity: 0, y: 24 } : { opacity: 0, scale: 0.98, y: -6 }}
                role="dialog"
                style={menuStyle}
                transition={{ duration: 0.18, ease: 'easeOut' }}
              >
                <div className="border-b border-cyan-300/10 p-3">
                  <label className="flex h-11 items-center gap-2 rounded-xl bg-slate-950/40 px-3 text-slate-300 ring-1 ring-cyan-300/12 transition focus-within:bg-slate-950/65 focus-within:ring-cyan-300/30 focus-within:shadow-[0_0_28px_rgba(56,189,248,0.10)]">
                    <Search size={16} />
                    <input
                      ref={searchRef}
                      className="min-w-0 flex-1 bg-transparent text-[15px] font-normal text-white outline-none placeholder:text-slate-500"
                      onChange={(event) => {
                        setSearch(event.target.value)
                        setActiveIndex(0)
                      }}
                      onKeyDown={handleSearchKeyDown}
                      placeholder="Buscar paciente..."
                      value={search}
                    />
                    {pending && <Loader2 className="animate-spin text-slate-400" size={16} />}
                  </label>
                </div>

                <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2 [scrollbar-color:rgba(56,189,248,0.35)_transparent] [scrollbar-width:thin]">
                  {filteredPatients.length === 0 ? (
                    <p className="px-3 py-8 text-center text-sm text-slate-400">
                      Nenhum paciente encontrado.
                    </p>
                  ) : (
                    filteredPatients.map((patient, index) => {
                      const selected = patient.id === patientId
                      const active = index === activeIndex
                      return (
                        <button
                          className={cn(
                            'flex h-11 w-full items-center gap-2 rounded-xl px-3 text-left text-sm transition duration-150',
                            selected
                              ? 'bg-cyan-300/[0.12] text-white shadow-[inset_0_0_0_1px_rgba(34,211,238,0.14)]'
                              : active
                                ? 'bg-cyan-300/[0.08] text-white'
                                : 'text-slate-300 hover:bg-cyan-300/[0.07] hover:text-white',
                          )}
                          key={patient.id}
                          onClick={() => selectPatient(patient.id)}
                          onMouseEnter={() => setActiveIndex(index)}
                          type="button"
                        >
                          <span className="min-w-0 flex-1 truncate font-medium">
                            {patient.name}
                          </span>
                          {selected && <Check className="text-cyan-200" size={16} />}
                        </button>
                      )
                    })
                  )}
                </div>

                <div className="border-t border-cyan-300/10 p-2">
                  <Link
                    className="block rounded-xl px-3 py-3 text-sm font-medium text-slate-300 transition hover:bg-cyan-300/[0.08] hover:text-white"
                    onClick={() => setOpen(false)}
                    to={fullListPath}
                  >
                    Ver todos os pacientes
                  </Link>
                </div>
              </motion.div>
            </>
          )}
        </AnimatePresence>,
        document.body,
      )}
    </div>
  )
}

function StaticPatientPill({ patientName }: { patientName: string }) {
  return (
    <div className="inline-flex h-9 min-w-0 max-w-[min(64vw,20rem)] items-center gap-2 truncate rounded-full border border-cyan-300/10 bg-slate-950/35 px-3 text-sm font-medium text-slate-100 sm:max-w-72">
      <span className="block min-w-0 truncate">{patientName}</span>
    </div>
  )
}

function ChatComposer({
  content,
  disabled,
  error,
  isProfessional,
  onChange,
  onReasoningChange,
  onSubmit,
  placeholder,
  reasoningLevel,
  sending,
  textareaRef,
}: {
  content: string
  disabled: boolean
  error: string | null
  isProfessional: boolean
  onChange: (value: string) => void
  onReasoningChange: (level: AiReasoningLevel) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  placeholder: string
  reasoningLevel: AiReasoningLevel
  sending: boolean
  textareaRef: RefObject<HTMLTextAreaElement | null>
}) {
  return (
    <form
      className="border-t border-[var(--chat-border)] bg-[rgba(6,8,24,0.70)] px-3 py-3 shadow-[0_-20px_60px_rgba(2,6,23,0.28)] backdrop-blur-xl sm:px-8 sm:py-4"
      onSubmit={onSubmit}
    >
      <div className="mx-auto max-w-3xl">
        <AnimatePresence>
          {error && (
            <motion.p
              animate={{ opacity: 1, y: 0 }}
              className="mb-3 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700 dark:border-rose-400/20 dark:bg-rose-400/10 dark:text-rose-300"
              exit={{ opacity: 0, y: 4 }}
              initial={{ opacity: 0, y: 4 }}
            >
              {error}
            </motion.p>
          )}
        </AnimatePresence>

        <div className="rounded-[26px] border border-cyan-300/14 bg-[rgba(15,23,42,0.76)] p-2 shadow-[0_18px_60px_rgba(2,6,23,0.34),0_0_42px_rgba(56,189,248,0.08)] backdrop-blur-xl transition duration-200 focus-within:border-cyan-300/35 focus-within:bg-[rgba(15,23,42,0.88)] focus-within:shadow-[0_22px_70px_rgba(2,6,23,0.42),0_0_54px_rgba(56,189,248,0.15)]">
          <Textarea
            ref={textareaRef}
            aria-label="Mensagem para a IA"
            className="max-h-40 min-h-10 resize-none border-0 bg-transparent px-3 py-2.5 text-[15px] leading-6 text-slate-100 shadow-none placeholder:text-slate-500 focus:ring-0 dark:bg-transparent"
            disabled={disabled}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                event.currentTarget.form?.requestSubmit()
              }
            }}
            placeholder={placeholder}
            rows={1}
            value={content}
          />

          <div className="mt-1 flex items-center justify-end gap-1.5">
            {isProfessional && (
              <ReasoningMenu
                onChange={onReasoningChange}
                reasoningLevel={reasoningLevel}
              />
            )}
            <button
              aria-label="Microfone"
              className="flex h-9 w-9 items-center justify-center rounded-full text-slate-400 transition hover:bg-cyan-300/[0.09] hover:text-cyan-100 hover:shadow-[0_0_22px_rgba(56,189,248,0.12)] disabled:opacity-40"
              disabled={disabled}
              title="Microfone"
              type="button"
            >
              <Mic size={18} />
            </button>
            <button
              aria-label="Enviar mensagem"
              className="flex h-9 w-9 items-center justify-center rounded-full bg-cyan-100 text-slate-950 shadow-[0_0_28px_rgba(56,189,248,0.22)] transition hover:scale-[1.03] hover:bg-white hover:shadow-[0_0_36px_rgba(56,189,248,0.32)] disabled:scale-100 disabled:bg-slate-700 disabled:text-slate-500 disabled:shadow-none"
              disabled={sending || !content.trim() || disabled}
              title="Enviar"
              type="submit"
            >
              {sending ? (
                <Loader2 className="animate-spin" size={18} />
              ) : (
                <Send size={17} />
              )}
            </button>
          </div>
        </div>
      </div>
    </form>
  )
}

function ReasoningMenu({
  onChange,
  reasoningLevel,
}: {
  onChange: (level: AiReasoningLevel) => void
  reasoningLevel: AiReasoningLevel
}) {
  const [open, setOpen] = useState(false)
  const selected = AI_REASONING_LEVELS.find((level) => level.id === reasoningLevel)

  return (
    <div className="relative shrink-0">
      <button
        aria-expanded={open}
        aria-label="Nivel de pensamento da IA"
        className="group inline-flex h-9 items-center gap-1.5 rounded-full px-3 text-sm font-medium text-slate-400 transition hover:bg-cyan-300/[0.09] hover:text-cyan-100 hover:shadow-[0_0_22px_rgba(56,189,248,0.12)]"
        onClick={() => setOpen(!open)}
        type="button"
        title="Pensamento"
      >
        <BrainCircuit size={17} />
        <span className="hidden min-w-0 truncate sm:block">
          {selected?.shortLabel ?? 'Medio'}
        </span>
        <ChevronDown
          className={cn(
            'shrink-0 transition',
            open && 'rotate-180',
          )}
          size={14}
        />
      </button>

      <AnimatePresence>
        {open && (
          <>
            <motion.div
              animate={{ opacity: 1 }}
              className="fixed inset-0 z-20 bg-[#020617]/20 backdrop-blur-[1px]"
              exit={{ opacity: 0 }}
              initial={{ opacity: 0 }}
              onClick={() => setOpen(false)}
            />
            <motion.div
              animate={{ opacity: 1, scale: 1, y: 0 }}
              className="absolute bottom-full right-0 z-30 mb-2 w-[min(calc(100vw-2rem),300px)] overflow-hidden rounded-2xl border border-cyan-300/15 bg-[rgba(11,16,32,0.94)] p-1.5 text-slate-100 shadow-[0_24px_70px_rgba(2,6,23,0.50),0_0_54px_rgba(56,189,248,0.14)] backdrop-blur-xl"
              exit={{ opacity: 0, scale: 0.98, y: 6 }}
              initial={{ opacity: 0, scale: 0.98, y: 6 }}
              transition={{ duration: 0.16, ease: 'easeOut' }}
            >
              {AI_REASONING_LEVELS.map((level) => {
                const active = level.id === reasoningLevel
                return (
                  <button
                    className={cn(
                      'flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left text-sm transition',
                      active
                        ? 'bg-cyan-300/[0.12] text-white shadow-[inset_0_0_0_1px_rgba(34,211,238,0.14)]'
                        : 'text-slate-300 hover:bg-cyan-300/[0.07] hover:text-white',
                    )}
                    key={level.id}
                    onClick={() => {
                      onChange(level.id)
                      setOpen(false)
                    }}
                    type="button"
                  >
                    <span className={cn('h-2 w-2 shrink-0 rounded-full', reasoningDotClass(level.id))} />
                    <span className="min-w-0 flex-1 truncate font-medium">
                      {level.shortLabel}
                    </span>
                    {active && <Check className="text-cyan-200" size={16} />}
                  </button>
                )
              })}
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}

function reasoningDotClass(level: AiReasoningLevel) {
  if (level === 'low') return 'bg-emerald-400'
  if (level === 'medium') return 'bg-cyan-400'
  if (level === 'high') return 'bg-blue-500'
  return 'bg-violet-500'
}

type PatientMenuAnchorRect = {
  bottom: number
  right: number
}

function readPatientMenuAnchor(trigger: HTMLButtonElement | null): PatientMenuAnchorRect | null {
  const rect = trigger?.getBoundingClientRect()
  if (!rect) return null
  return {
    bottom: rect.bottom,
    right: rect.right,
  }
}

function getPatientMenuStyle(
  anchor: PatientMenuAnchorRect | null,
  isMobile: boolean,
): CSSProperties {
  if (isMobile || typeof window === 'undefined') return {}

  const width = Math.min(420, window.innerWidth - 32)
  const left = anchor
    ? Math.min(Math.max(16, anchor.right - width), window.innerWidth - width - 16)
    : window.innerWidth - width - 16
  const top = anchor ? anchor.bottom + 10 : 72
  const maxHeight = Math.max(320, Math.min(520, window.innerHeight - top - 16))

  return {
    left,
    maxHeight,
    top,
    width,
  }
}

function useDebouncedValue(value: string, delay: number) {
  const [debouncedValue, setDebouncedValue] = useState(value)

  useEffect(() => {
    if (value === debouncedValue) {
      return
    }

    const timeout = window.setTimeout(() => {
      setDebouncedValue(value)
    }, delay)

    return () => window.clearTimeout(timeout)
  }, [debouncedValue, delay, value])

  return { debouncedValue, pending: value !== debouncedValue }
}

function readReasoningPreference(key: string): AiReasoningLevel | null {
  if (typeof window === 'undefined') return null
  const value = window.localStorage.getItem(key)
  return isReasoningLevel(value) ? value : null
}

function writeReasoningPreference(key: string, level: AiReasoningLevel) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(key, level)
}

function isReasoningLevel(value: string | null): value is AiReasoningLevel {
  return value === 'low' || value === 'medium' || value === 'high' || value === 'ultra'
}

type AgentAction = {
  error?: string | null
  label?: string
  requires_confirmation?: boolean
  status?: 'executed' | 'skipped' | 'failed' | 'pending_confirmation'
  summary?: string | null
  tool?: string
}

const MessageBubble = memo(function MessageBubble({
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
    <div className={cn('flex', own ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[88%] text-sm leading-7 sm:max-w-[78%]',
          own
            ? 'rounded-[22px] bg-cyan-100 px-4 py-2.5 text-slate-950 shadow-[0_10px_34px_rgba(56,189,248,0.16)]'
            : 'min-w-0 flex-1 text-slate-100',
        )}
      >
        <MarkdownContent content={message.content} />
        {!own && actions.length > 0 && <AgentActionList actions={actions} />}
        {streaming && (
          <span className="mt-2 inline-flex h-2 w-2 animate-pulse rounded-full bg-cyan-300 shadow-[0_0_18px_rgba(34,211,238,0.55)]" />
        )}
      </div>
    </div>
  )
})

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
    <div className="max-w-none text-sm leading-7 [&_a]:font-semibold [&_a]:text-cyan-300 [&_blockquote]:border-l-2 [&_blockquote]:border-cyan-300/25 [&_blockquote]:pl-4 [&_code]:rounded-md [&_code]:bg-cyan-300/10 [&_code]:px-1.5 [&_code]:py-0.5 [&_h1]:mb-3 [&_h1]:text-xl [&_h1]:font-black [&_h2]:mb-2 [&_h2]:mt-4 [&_h2]:text-lg [&_h2]:font-black [&_li]:my-1 [&_ol]:my-3 [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:my-2 [&_pre]:my-3 [&_pre]:overflow-x-auto [&_pre]:rounded-2xl [&_pre]:border [&_pre]:border-cyan-300/10 [&_pre]:bg-slate-950/75 [&_pre]:p-4 [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_table]:my-4 [&_table]:w-full [&_table]:overflow-hidden [&_table]:rounded-2xl [&_table]:text-left [&_td]:border-t [&_td]:border-cyan-300/10 [&_td]:px-3 [&_td]:py-2 [&_th]:bg-cyan-300/10 [&_th]:px-3 [&_th]:py-2 [&_th]:font-bold [&_ul]:my-3 [&_ul]:list-disc [&_ul]:pl-5">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  )
}

function TypingBubble() {
  return (
    <div className="flex items-center">
      <div className="inline-flex items-center gap-1 rounded-3xl bg-cyan-300/10 px-4 py-3 shadow-[inset_0_0_0_1px_rgba(34,211,238,0.10)]">
        <span className="h-2 w-2 animate-bounce rounded-full bg-cyan-300 [animation-delay:-0.2s]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-cyan-300 [animation-delay:-0.1s]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-cyan-300" />
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
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-3xl bg-cyan-100 text-slate-950 shadow-[0_0_42px_rgba(56,189,248,0.24)]">
          <Bot size={20} />
        </div>
        <h3 className="mt-4 text-lg font-black text-slate-50">
          {title}
        </h3>
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-400">
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
