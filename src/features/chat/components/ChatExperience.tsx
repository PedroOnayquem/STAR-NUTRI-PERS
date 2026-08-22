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
  Loader2,
  MessageSquarePlus,
  Mic,
  Search,
  Send,
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
  onPatientChange?: (patientId: string | null) => void
  patientId?: string | null
  patientName?: string
  patients?: PatientRecord[]
  scope: ChatScope
}

type PatientOption = {
  email: string
  id: string | null
  isGeneral?: boolean
  name: string
  objective: string
}

const GENERAL_CHAT_OPTION: PatientOption = {
  email: '',
  id: null,
  isGeneral: true,
  name: 'Chat geral',
  objective: 'Sem paciente específico',
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
      const mapped = (patients ?? []).map(
        (patient) =>
          ({
            email: patient.profile?.email ?? '',
            id: patient.id,
            name: patient.profile?.full_name ?? 'Paciente',
            objective: patient.objective ?? '',
          }) satisfies PatientOption,
      )

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
  const patientMenuOptions = useMemo(
    () =>
      isProfessional
        ? [GENERAL_CHAT_OPTION, ...patientOptions]
        : [],
    [isProfessional, patientOptions],
  )
  const selectedPatient = isProfessional
    ? patientMenuOptions.find((patient) => patient.id === patientId) ?? GENERAL_CHAT_OPTION
    : null
  const selectedPatientName = isProfessional
    ? selectedPatient?.name ?? patientName ?? 'Paciente'
    : patientName ?? 'Paciente'
  const focusedPatientId = isProfessional
    ? selectedPatient?.id ?? patientId ?? null
    : null
  const isGeneralProfessionalChat = isProfessional && !patientId
  const hasRequiredFocus = !isProfessional || Boolean(selectedPatient)
  const currentSession = chat.sessions.find(
    (session) => session.id === chat.activeSessionId,
  )
  const currentTitle = currentSession?.title || 'Nova conversa'
  const patientNameById = useMemo(
    () =>
      Object.fromEntries(
        patientOptions.map((patient) => [patient.id, patient.name]),
      ) as Record<string, string>,
    [patientOptions],
  )
  const patientLabelBySessionId = useMemo(
    () =>
      Object.fromEntries(
        chat.sessions.map((session) => {
          const label = !isProfessional
            ? 'Chat pessoal'
            : session.patient_id
              ? patientNameById[session.patient_id] ?? 'Paciente'
              : GENERAL_CHAT_OPTION.name
          return [session.id, label]
        }),
      ),
    [chat.sessions, isProfessional, patientNameById],
  )
  const filteredSessions = useMemo(() => {
    const term = deferredConversationSearch.trim().toLowerCase()
    if (!term) return chat.sessions

    return chat.sessions.filter((session) => {
      const title = session.title?.toLowerCase() ?? ''
      const patient = (
        patientLabelBySessionId[session.id] ??
        (isProfessional ? GENERAL_CHAT_OPTION.name : 'Chat pessoal')
      ).toLowerCase()
      const date = formatSessionDate(session).toLowerCase()
      return title.includes(term) || patient.includes(term) || date.includes(term)
    })
  }, [chat.sessions, deferredConversationSearch, isProfessional, patientLabelBySessionId])

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
        'chat-shell h-[calc(100vh-8rem)] min-h-[680px] overflow-hidden rounded-[28px] border border-[var(--chat-border)]',
        className,
      )}
    >
      <div className="grid h-full min-h-0 lg:grid-cols-[292px_minmax(0,1fr)]">
        <ChatSidebar
          canCreate={hasRequiredFocus}
          createLabel={
            isProfessional
              ? isGeneralProfessionalChat
                ? 'Novo chat geral'
                : 'Novo chat com paciente'
              : 'Novo chat'
          }
          creating={chat.creatingSession}
          currentSessionId={chat.activeSessionId}
          isLoading={chat.isLoading}
          onCreateSession={chat.createSession}
          patientLabelBySessionId={patientLabelBySessionId}
          onSearch={setConversationSearch}
          onSelectSession={chat.selectSession}
          search={conversationSearch}
          sessions={filteredSessions}
        />

        <section className="chat-content flex min-h-0 flex-col">
          <ChatTopbar
            currentTitle={currentTitle}
            onPatientChange={onPatientChange}
            patientId={focusedPatientId}
            patientName={selectedPatientName}
            patients={patientMenuOptions}
            scope={scope}
          />

          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-6 [scrollbar-color:rgba(56,189,248,0.32)_transparent] [scrollbar-width:thin] sm:px-8">
            <div className="mx-auto flex min-h-full max-w-3xl flex-col">
              {!hasRequiredFocus ? (
                <ChatEmpty
                  description="Escolha um paciente no topo para carregar contexto e histórico."
                  title="Selecione um paciente"
                />
              ) : chat.isLoading && !chat.messages.length ? (
                <MessageSkeleton />
              ) : chat.messages.length === 0 && !chat.streaming ? (
                <ChatEmpty
                  description={
                    isProfessional
                      ? isGeneralProfessionalChat
                        ? 'Converse sobre condutas gerais, materiais educativos e organização do consultório sem depender de um paciente específico.'
                        : 'Pergunte sobre evolução, aderência ou pontos de atenção.'
                      : 'Pergunte sobre sua dieta ativa, treino, rotina, compras ou organização do dia.'
                  }
                  title={
                    isProfessional
                      ? isGeneralProfessionalChat
                        ? 'Chat profissional geral'
                        : `Chat profissional para ${selectedPatientName}`
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
                  ? isGeneralProfessionalChat
                    ? 'Digite sua mensagem profissional...'
                    : 'Digite sua mensagem...'
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
  createLabel,
  creating,
  currentSessionId,
  isLoading,
  onCreateSession,
  patientLabelBySessionId,
  onSearch,
  onSelectSession,
  search,
  sessions,
}: {
  canCreate: boolean
  createLabel: string
  creating: boolean
  currentSessionId: string | null
  isLoading: boolean
  onCreateSession: () => void
  patientLabelBySessionId: Record<string, string>
  onSearch: (value: string) => void
  onSelectSession: (sessionId: string) => void
  search: string
  sessions: ChatSessionRecord[]
}) {
  return (
    <aside className="chat-sidebar flex max-h-72 min-h-0 flex-col border-b border-[var(--chat-border)] backdrop-blur-xl lg:max-h-none lg:border-b-0 lg:border-r">
      <div className="space-y-3 p-3">
        <Button
          className="chat-control h-10 w-full justify-start rounded-2xl border border-[var(--chat-border)] shadow-sm hover:border-[var(--chat-border-strong)] hover:text-[var(--chat-text)]"
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
          {createLabel}
        </Button>

        <label className="chat-control chat-muted flex h-10 items-center gap-2 rounded-2xl border border-[var(--chat-border)] px-3 shadow-inner transition focus-within:border-[var(--chat-border-strong)] focus-within:text-[var(--chat-accent-text)] focus-within:ring-2 focus-within:ring-cyan-400/10">
          <Search size={16} />
          <input
            className="chat-text min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-[var(--chat-subtle)]"
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
          <div className="chat-muted mx-1 rounded-2xl border border-dashed border-[var(--chat-border)] bg-[var(--chat-surface)] p-4 text-sm">
            Nenhuma conversa encontrada.
          </div>
        ) : (
          <div className="space-y-1">
            {sessions.map((session) => (
              <button
                className={cn(
                  'group w-full rounded-2xl px-3 py-3 text-left transition',
                  currentSessionId === session.id
                    ? 'bg-[var(--chat-active-background)] text-[var(--chat-text)] shadow-[inset_0_0_0_1px_var(--chat-border-strong),0_12px_36px_var(--chat-glow)]'
                    : 'text-[var(--chat-muted)] hover:bg-[var(--chat-active-background)] hover:text-[var(--chat-text)]',
                )}
                key={session.id}
                onClick={() => onSelectSession(session.id)}
                type="button"
              >
                <span className="block truncate text-sm font-bold">
                  {session.title || 'Nova conversa'}
                </span>
                <span className="chat-subtle mt-1 block truncate text-xs group-hover:text-[var(--chat-muted)]">
                  {patientLabelBySessionId[session.id] ?? GENERAL_CHAT_OPTION.name} -{' '}
                  {formatSessionDate(session)}
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
  onPatientChange?: (patientId: string | null) => void
  patientId: string | null
  patientName: string
  patients: PatientOption[]
  scope: ChatScope
}) {
  const [patientMenuOpen, setPatientMenuOpen] = useState(false)

  return (
    <header className="chat-chrome flex min-h-14 flex-wrap items-center justify-between gap-3 border-b border-[var(--chat-border)] px-4 py-2.5 shadow-sm backdrop-blur-xl sm:px-5">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <div className="min-w-0">
          <h2 className="chat-text truncate text-sm font-semibold">
            {currentTitle}
          </h2>
          <p className="chat-muted truncate text-xs">
            {scope === 'nutritionist' ? 'Chat do nutricionista' : 'Chat do paciente'}
          </p>
        </div>
      </div>

      {scope === 'nutritionist' && (
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
      )}
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
  onChange: (patientId: string | null) => void
  onOpenChange: (open: boolean) => void
  open: boolean
  patientId: string | null
  patients: PatientOption[]
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

  function selectPatient(nextPatientId: string | null) {
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
        className="chat-control group inline-flex h-9 w-full min-w-0 max-w-[min(64vw,20rem)] items-center gap-2 rounded-full border border-[var(--chat-border)] px-3 text-left shadow-sm transition hover:border-[var(--chat-border-strong)] hover:text-[var(--chat-text)] hover:shadow-[0_0_24px_var(--chat-glow)] sm:w-auto sm:max-w-80"
        onClick={() => setOpen(!open)}
        onKeyDown={handleTriggerKeyDown}
        type="button"
      >
        <span className="chat-accent-text flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-cyan-400/10 text-[10px] font-black">
          {selectedPatient?.isGeneral ? 'IA' : getInitials(selectedPatient?.name ?? 'P')}
        </span>
        <span className="block min-w-0 flex-1 truncate text-sm font-medium">
          {selectedPatient?.name ?? 'Selecionar paciente'}
        </span>
        <ChevronDown
          className={cn(
            'chat-accent-text shrink-0 opacity-70 transition group-hover:opacity-100',
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
                className="fixed inset-0 z-40 bg-[var(--chat-menu-overlay)] backdrop-blur-[3px]"
                exit={{ opacity: 0 }}
                initial={{ opacity: 0 }}
                onClick={() => setOpen(false)}
              />
              <motion.div
                animate={isMobile ? { opacity: 1, y: 0 } : { opacity: 1, scale: 1, y: 0 }}
                aria-label="Selecionar paciente"
                aria-modal={isMobile}
                className={cn(
                  'chat-menu fixed z-50 flex overflow-hidden border border-[var(--chat-border)] backdrop-blur-2xl',
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
                <div className="border-b border-[var(--chat-border)] p-3">
                  <label className="chat-control chat-muted flex h-11 items-center gap-2 rounded-xl px-3 ring-1 ring-[var(--chat-border)] transition focus-within:ring-[var(--chat-border-strong)] focus-within:shadow-[0_0_28px_var(--chat-glow)]">
                    <Search size={16} />
                    <input
                      ref={searchRef}
                      className="chat-text min-w-0 flex-1 bg-transparent text-[15px] font-normal outline-none placeholder:text-[var(--chat-subtle)]"
                      onChange={(event) => {
                        setSearch(event.target.value)
                        setActiveIndex(0)
                      }}
                      onKeyDown={handleSearchKeyDown}
                      placeholder="Buscar paciente..."
                      value={search}
                    />
                    {pending && <Loader2 className="chat-muted animate-spin" size={16} />}
                  </label>
                </div>

                <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2 [scrollbar-color:rgba(56,189,248,0.35)_transparent] [scrollbar-width:thin]">
                  {filteredPatients.length === 0 ? (
                    <p className="chat-muted px-3 py-8 text-center text-sm">
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
                              ? 'bg-[var(--chat-active-background)] text-[var(--chat-text)] shadow-[inset_0_0_0_1px_var(--chat-border-strong)]'
                              : active
                                ? 'bg-[var(--chat-active-background)] text-[var(--chat-text)]'
                                : 'text-[var(--chat-muted)] hover:bg-[var(--chat-active-background)] hover:text-[var(--chat-text)]',
                          )}
                          key={patient.id ?? 'general'}
                          onClick={() => selectPatient(patient.id)}
                          onMouseEnter={() => setActiveIndex(index)}
                          type="button"
                        >
                          <span className="chat-accent-text flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-cyan-400/10 text-[10px] font-black">
                            {patient.isGeneral ? 'IA' : getInitials(patient.name)}
                          </span>
                          <span className="min-w-0 flex-1 truncate font-medium">
                            {patient.name}
                          </span>
                          {selected && <Check className="chat-accent-text" size={16} />}
                        </button>
                      )
                    })
                  )}
                </div>

                <div className="border-t border-[var(--chat-border)] p-2">
                  <Link
                    className="chat-muted block rounded-xl px-3 py-3 text-sm font-medium transition hover:bg-[var(--chat-active-background)] hover:text-[var(--chat-text)]"
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
    <div className="chat-control inline-flex h-9 min-w-0 max-w-[min(64vw,20rem)] items-center gap-2 truncate rounded-full border border-[var(--chat-border)] px-3 text-sm font-medium sm:max-w-72">
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
      className="chat-chrome border-t border-[var(--chat-border)] px-3 py-3 shadow-[0_-12px_40px_var(--chat-glow)] backdrop-blur-xl sm:px-8 sm:py-4"
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

        <div className="chat-control rounded-[26px] border border-[var(--chat-border)] p-2 shadow-[var(--chat-panel-shadow)] backdrop-blur-xl transition duration-200 focus-within:border-[var(--chat-border-strong)]">
          <Textarea
            ref={textareaRef}
            aria-label="Mensagem para a IA"
            className="chat-text max-h-40 min-h-10 resize-none border-0 bg-transparent px-3 py-2.5 text-[15px] leading-6 shadow-none placeholder:text-[var(--chat-subtle)] focus:ring-0 dark:bg-transparent"
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
              className="chat-muted flex h-9 w-9 items-center justify-center rounded-full transition hover:bg-[var(--chat-active-background)] hover:text-[var(--chat-accent-text)] hover:shadow-[0_0_22px_var(--chat-glow)] disabled:opacity-40"
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
        aria-label="Nível de raciocínio da IA"
        className="chat-muted group inline-flex h-9 items-center gap-1.5 rounded-full px-3 text-sm font-medium transition hover:bg-[var(--chat-active-background)] hover:text-[var(--chat-accent-text)] hover:shadow-[0_0_22px_var(--chat-glow)]"
        onClick={() => setOpen(!open)}
        type="button"
        title="Raciocínio"
      >
        <BrainCircuit size={17} />
        <span className="hidden min-w-0 truncate sm:block">
          {selected?.shortLabel ?? 'Médio'}
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
              className="fixed inset-0 z-20 bg-[var(--chat-menu-overlay)] backdrop-blur-[1px]"
              exit={{ opacity: 0 }}
              initial={{ opacity: 0 }}
              onClick={() => setOpen(false)}
            />
            <motion.div
              animate={{ opacity: 1, scale: 1, y: 0 }}
              className="chat-menu absolute bottom-full right-0 z-30 mb-2 w-[min(calc(100vw-2rem),300px)] overflow-hidden rounded-2xl border border-[var(--chat-border)] p-1.5 backdrop-blur-xl"
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
                        ? 'bg-[var(--chat-active-background)] text-[var(--chat-text)] shadow-[inset_0_0_0_1px_var(--chat-border-strong)]'
                        : 'text-[var(--chat-muted)] hover:bg-[var(--chat-active-background)] hover:text-[var(--chat-text)]',
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
                    {active && <Check className="chat-accent-text" size={16} />}
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

function getInitials(name: string) {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('') || 'IA'
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

const MessageBubble = memo(function MessageBubble({
  message,
  own,
  streaming,
}: {
  message: ChatMessageRecord
  own: boolean
  streaming?: boolean
}) {
  return (
    <div className={cn('flex', own ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[88%] text-sm leading-7 sm:max-w-[78%]',
          own
            ? 'rounded-[22px] bg-cyan-100 px-4 py-2.5 text-slate-950 shadow-[0_10px_34px_rgba(56,189,248,0.16)]'
            : 'chat-text min-w-0 flex-1',
        )}
      >
        <MarkdownContent content={message.content} />
        {streaming && (
          <span className="mt-2 inline-flex h-2 w-2 animate-pulse rounded-full bg-cyan-300 shadow-[0_0_18px_rgba(34,211,238,0.55)]" />
        )}
      </div>
    </div>
  )
})

function MarkdownContent({ content }: { content: string }) {
  return (
    <div className="max-w-none text-sm leading-7 [&_a]:font-semibold [&_a]:text-cyan-600 dark:[&_a]:text-cyan-300 [&_blockquote]:border-l-2 [&_blockquote]:border-cyan-500/25 [&_blockquote]:pl-4 [&_code]:rounded-md [&_code]:bg-cyan-500/10 [&_code]:px-1.5 [&_code]:py-0.5 [&_h1]:mb-3 [&_h1]:text-xl [&_h1]:font-black [&_h2]:mb-2 [&_h2]:mt-4 [&_h2]:text-lg [&_h2]:font-black [&_li]:my-1 [&_ol]:my-3 [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:my-2 [&_pre]:my-3 [&_pre]:overflow-x-auto [&_pre]:rounded-2xl [&_pre]:border [&_pre]:border-cyan-300/10 [&_pre]:bg-[var(--chat-pre-background)] [&_pre]:p-4 [&_pre]:text-slate-100 [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_table]:my-4 [&_table]:w-full [&_table]:overflow-hidden [&_table]:rounded-2xl [&_table]:text-left [&_td]:border-t [&_td]:border-cyan-500/15 [&_td]:px-3 [&_td]:py-2 [&_th]:bg-cyan-500/10 [&_th]:px-3 [&_th]:py-2 [&_th]:font-bold [&_ul]:my-3 [&_ul]:list-disc [&_ul]:pl-5">
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
        <h3 className="chat-text mt-4 text-lg font-black">
          {title}
        </h3>
        <p className="chat-muted mx-auto mt-2 max-w-md text-sm leading-6">
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
