import {
  CalendarDays,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Search,
} from 'lucide-react'
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type RefObject,
  type ReactNode,
} from 'react'
import { createPortal } from 'react-dom'
import { cn } from '../../lib/utils'

export type AppSelectOption<T extends string = string> = {
  label: string
  value: T
  description?: string
}

type PickerBaseProps = {
  disabled?: boolean
  error?: string
  placeholder?: string
}

type CalendarView = 'days' | 'months' | 'years'

const monthOptions = [
  'Jan',
  'Fev',
  'Mar',
  'Abr',
  'Mai',
  'Jun',
  'Jul',
  'Ago',
  'Set',
  'Out',
  'Nov',
  'Dez',
]

export function AppSelect<T extends string>({
  disabled,
  error,
  onChange,
  options,
  placeholder = 'Selecione',
  value,
}: PickerBaseProps & {
  onChange: (value: T) => void
  options: Array<AppSelectOption<T>>
  value: T | ''
}) {
  const selected = options.find((option) => option.value === value)

  return (
    <AppDropdown
      disabled={disabled}
      error={error}
      icon={<ChevronDown size={18} />}
      onChange={onChange}
      options={options}
      placeholder={placeholder}
      selectedLabel={selected?.label}
      value={value}
    />
  )
}

export function AppCombobox<T extends string>({
  disabled,
  error,
  onChange,
  options,
  placeholder = 'Buscar e selecionar',
  value,
}: PickerBaseProps & {
  onChange: (value: T) => void
  options: Array<AppSelectOption<T>>
  value: T | ''
}) {
  const [search, setSearch] = useState('')
  const selected = options.find((option) => option.value === value)
  const filteredOptions = useMemo(() => {
    const term = search.trim().toLowerCase()
    if (!term) return options
    return options.filter((option) =>
      `${option.label} ${option.description ?? ''}`.toLowerCase().includes(term),
    )
  }, [options, search])

  return (
    <AppDropdown
      disabled={disabled}
      error={error}
      header={
        <div className="flex items-center gap-2 rounded-xl border border-cyan-300/15 bg-slate-950/70 px-3 py-2 text-slate-300">
          <Search size={16} />
          <input
            className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-slate-500"
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Buscar"
            value={search}
          />
        </div>
      }
      icon={<ChevronDown size={18} />}
      onChange={(nextValue) => {
        setSearch('')
        onChange(nextValue)
      }}
      options={filteredOptions}
      placeholder={placeholder}
      selectedLabel={selected?.label}
      value={value}
    />
  )
}

export function AppTimePicker({
  disabled,
  end = '22:00',
  error,
  intervalMinutes = 30,
  onChange,
  placeholder = 'Selecionar horário',
  start = '06:00',
  value,
}: PickerBaseProps & {
  end?: string
  intervalMinutes?: number
  onChange: (value: string) => void
  start?: string
  value: string
}) {
  const options = useMemo(
    () =>
      buildTimeOptions(start, end, intervalMinutes).map((time) => ({
        label: time,
        value: time,
      })),
    [end, intervalMinutes, start],
  )

  return (
    <AppDropdown
      disabled={disabled}
      error={error}
      icon={<Clock3 size={18} />}
      onChange={onChange}
      options={options}
      placeholder={placeholder}
      selectedLabel={value || undefined}
      value={value}
    />
  )
}

export function AppDatePicker({
  disabled,
  error,
  onChange,
  placeholder = 'Selecionar data',
  value,
}: PickerBaseProps & {
  onChange: (value: string) => void
  value: string
}) {
  const triggerRef = useRef<HTMLButtonElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [position, setPosition] = useState<FloatingPosition | null>(null)
  const [calendarView, setCalendarView] = useState<CalendarView>('days')
  const selectedDate = value ? parseLocalDate(value) : null
  const [visibleMonth, setVisibleMonth] = useState(() => {
    const base = selectedDate ?? new Date()
    return new Date(base.getFullYear(), base.getMonth(), 1)
  })
  const handleOpenChange = useCallback((nextOpen: boolean) => {
    if (nextOpen) {
      const base = value ? parseLocalDate(value) : new Date()
      setCalendarView('days')
      setVisibleMonth(new Date(base.getFullYear(), base.getMonth(), 1))
    }
    setOpen(nextOpen)
  }, [value])

  useFloatingPosition(open, triggerRef, setPosition)
  useDismiss(open, handleOpenChange, triggerRef, popoverRef)

  const days = useMemo(() => buildCalendarDays(visibleMonth), [visibleMonth])
  const yearOptions = useMemo(() => {
    const currentYear = new Date().getFullYear()
    return Array.from({ length: currentYear - 1900 + 1 }, (_, index) => currentYear - index)
  }, [])
  const selectedLabel = selectedDate
    ? selectedDate.toLocaleDateString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
      })
    : ''

  return (
    <>
      <button
        aria-expanded={open}
        className={triggerClassName({ disabled, error })}
        disabled={disabled}
        data-picker="date"
        onClick={() => handleOpenChange(!open)}
        onKeyDown={(event) => handleTriggerKey(event, handleOpenChange)}
        ref={triggerRef}
        type="button"
      >
        <CalendarDays size={18} />
        <span className={cn('min-w-0 flex-1 truncate text-left', !selectedLabel && 'text-slate-500')}>
          {selectedLabel || placeholder}
        </span>
        <ChevronDown
          className={cn('transition duration-200', open && 'rotate-180')}
          size={18}
        />
      </button>

      {open &&
        position &&
        createPortal(
          <div
            className="app-date-popover z-[80] w-[320px] max-w-[calc(100vw-24px)] rounded-2xl border border-emerald-900/10 bg-[#fbfaf6] p-4 text-slate-950 shadow-[0_18px_54px_rgba(15,23,42,0.18),0_2px_8px_rgba(15,23,42,0.08)] dark:border-emerald-200/10 dark:bg-[#fbfaf6] dark:text-slate-950"
            ref={popoverRef}
            role="dialog"
            aria-label="Selecionar data"
            style={{
              left: position.left,
              position: 'fixed',
              top: position.top,
              width: Math.min(320, window.innerWidth - 24),
            }}
          >
            <div className="grid grid-cols-[2.25rem_1fr_2.25rem] items-center gap-2 pb-3">
              <button
                aria-label={
                  calendarView === 'years'
                    ? 'Voltar ao calendário'
                    : calendarView === 'months'
                      ? 'Ano anterior'
                      : 'Mês anterior'
                }
                className="grid h-9 w-9 place-items-center rounded-full border border-slate-200/80 bg-white/80 text-slate-500 shadow-sm transition hover:border-emerald-200 hover:bg-emerald-50 hover:text-emerald-700"
                onClick={() => {
                  if (calendarView === 'years') {
                    setCalendarView('days')
                    return
                  }
                  setVisibleMonth(
                    new Date(
                      visibleMonth.getFullYear() - (calendarView === 'months' ? 1 : 0),
                      visibleMonth.getMonth() - (calendarView === 'days' ? 1 : 0),
                      1,
                    ),
                  )
                }}
                type="button"
              >
                <ChevronLeft size={18} />
              </button>
              <div className="flex min-w-0 items-center justify-center gap-1 text-sm font-black capitalize tracking-normal text-slate-950">
                {calendarView === 'days' ? (
                  <>
                    <button
                      className="rounded-full px-2 py-1 transition hover:bg-emerald-50 hover:text-emerald-700"
                      onClick={() => setCalendarView('months')}
                      type="button"
                    >
                      {visibleMonth.toLocaleDateString('pt-BR', { month: 'long' })}
                    </button>
                    <button
                      className="rounded-full px-2 py-1 transition hover:bg-emerald-50 hover:text-emerald-700"
                      onClick={() => setCalendarView('years')}
                      type="button"
                    >
                      {visibleMonth.getFullYear()}
                    </button>
                  </>
                ) : (
                  <button
                    className="rounded-full px-3 py-1 transition hover:bg-emerald-50 hover:text-emerald-700"
                    onClick={() => setCalendarView(calendarView === 'months' ? 'years' : 'days')}
                    type="button"
                  >
                    {calendarView === 'months' ? visibleMonth.getFullYear() : 'Escolha o ano'}
                  </button>
                )}
              </div>
              {calendarView === 'years' ? (
                <span className="h-9 w-9" aria-hidden="true" />
              ) : (
                <button
                  aria-label={calendarView === 'months' ? 'Próximo ano' : 'Próximo mês'}
                  className="grid h-9 w-9 place-items-center rounded-full border border-slate-200/80 bg-white/80 text-slate-500 shadow-sm transition hover:border-emerald-200 hover:bg-emerald-50 hover:text-emerald-700"
                  onClick={() => {
                    setVisibleMonth(
                      new Date(
                        visibleMonth.getFullYear() + (calendarView === 'months' ? 1 : 0),
                        visibleMonth.getMonth() + (calendarView === 'days' ? 1 : 0),
                        1,
                      ),
                    )
                  }}
                  type="button"
                >
                  <ChevronRight size={18} />
                </button>
              )}
            </div>

            {calendarView === 'days' && (
              <>
                <div className="grid grid-cols-7 gap-1 pb-1 text-center text-[11px] font-black text-slate-500">
                  {['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab'].map((day) => (
                    <span className="grid h-7 place-items-center" key={day}>{day}</span>
                  ))}
                </div>
                <div className="grid grid-cols-7 gap-1">
                  {days.map((day, index) =>
                    day ? (
                      <button
                        aria-label={day.toLocaleDateString('pt-BR')}
                        className={cn(
                          'grid h-9 w-9 place-items-center rounded-xl text-sm font-black text-slate-700 transition duration-150 hover:bg-emerald-50 hover:text-emerald-800',
                          isSameDate(day, new Date()) &&
                            'border border-emerald-200 bg-white text-emerald-700 shadow-sm',
                          selectedDate &&
                            isSameDate(day, selectedDate) &&
                            'bg-emerald-400 text-slate-950 shadow-[0_10px_20px_rgba(16,185,129,0.22)] hover:bg-emerald-400 hover:text-slate-950',
                        )}
                        key={day.toISOString()}
                        onClick={() => {
                          onChange(toDateValue(day))
                          handleOpenChange(false)
                        }}
                        type="button"
                      >
                        {day.getDate()}
                      </button>
                    ) : (
                      <span className="h-9 w-9" key={`empty-${index}`} />
                    ),
                  )}
                </div>
              </>
            )}

            {calendarView === 'months' && (
              <div className="grid grid-cols-3 gap-2 py-1">
                {monthOptions.map((month, index) => {
                  const selectedMonth = selectedDate?.getFullYear() === visibleMonth.getFullYear()
                    && selectedDate?.getMonth() === index
                  const visible = visibleMonth.getMonth() === index
                  return (
                    <button
                      className={cn(
                        'h-11 rounded-xl text-sm font-black text-slate-700 transition hover:bg-emerald-50 hover:text-emerald-800',
                        visible && 'border border-emerald-200 bg-white text-emerald-700 shadow-sm',
                        selectedMonth && 'bg-emerald-400 text-slate-950 shadow-[0_10px_20px_rgba(16,185,129,0.18)] hover:bg-emerald-400 hover:text-slate-950',
                      )}
                      key={month}
                      onClick={() => {
                        setVisibleMonth(new Date(visibleMonth.getFullYear(), index, 1))
                        setCalendarView('days')
                      }}
                      type="button"
                    >
                      {month}
                    </button>
                  )
                })}
              </div>
            )}

            {calendarView === 'years' && (
              <div className="app-date-year-scroll max-h-64 overflow-y-auto pr-1">
                <div className="grid grid-cols-4 gap-2 py-1">
                  {yearOptions.map((year) => {
                    const selectedYear = selectedDate?.getFullYear() === year
                    const visible = visibleMonth.getFullYear() === year
                    const currentYear = new Date().getFullYear() === year
                    return (
                      <button
                        className={cn(
                          'h-10 rounded-xl text-sm font-black text-slate-700 transition hover:bg-emerald-50 hover:text-emerald-800',
                          currentYear && 'border border-slate-200 bg-white shadow-sm',
                          visible && 'border border-emerald-200 bg-white text-emerald-700 shadow-sm',
                          selectedYear && 'bg-emerald-400 text-slate-950 shadow-[0_10px_20px_rgba(16,185,129,0.18)] hover:bg-emerald-400 hover:text-slate-950',
                        )}
                        key={year}
                        onClick={() => {
                          setVisibleMonth(new Date(year, visibleMonth.getMonth(), 1))
                          setCalendarView('months')
                        }}
                        type="button"
                      >
                        {year}
                      </button>
                    )
                  })}
                </div>
              </div>
            )}

            <div className="mt-4 flex items-center justify-between border-t border-slate-200/80 pt-3">
              <span className="text-xs font-bold text-slate-500">
                {calendarView === 'days' && 'Selecione uma data'}
                {calendarView === 'months' && 'Selecione o mês'}
                {calendarView === 'years' && 'Selecione o ano'}
              </span>
              <button
                className="rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-black text-emerald-700 transition hover:bg-emerald-100"
                onClick={() => {
                  const today = new Date()
                  onChange(toDateValue(today))
                  setVisibleMonth(new Date(today.getFullYear(), today.getMonth(), 1))
                  setCalendarView('days')
                  handleOpenChange(false)
                }}
                type="button"
              >
                Hoje
              </button>
            </div>
          </div>,
          document.body,
        )}
    </>
  )
}

export function AppDropdown<T extends string>({
  disabled,
  error,
  header,
  icon,
  onChange,
  options,
  placeholder,
  selectedLabel,
  value,
}: PickerBaseProps & {
  header?: ReactNode
  icon?: ReactNode
  onChange: (value: T) => void
  options: Array<AppSelectOption<T>>
  selectedLabel?: string
  value: T | ''
}) {
  const triggerRef = useRef<HTMLButtonElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [position, setPosition] = useState<FloatingPosition | null>(null)

  useFloatingPosition(open, triggerRef, setPosition)
  useDismiss(open, setOpen, triggerRef, popoverRef)

  return (
    <>
      <button
        aria-expanded={open}
        className={triggerClassName({ disabled, error })}
        disabled={disabled}
        onClick={() => setOpen((current) => !current)}
        onKeyDown={(event) => handleTriggerKey(event, setOpen)}
        ref={triggerRef}
        type="button"
      >
        {icon}
        <span className={cn('min-w-0 flex-1 truncate text-left', !selectedLabel && 'text-slate-500')}>
          {selectedLabel || placeholder}
        </span>
        <ChevronDown
          className={cn('transition duration-200', open && 'rotate-180')}
          size={18}
        />
      </button>

      {open &&
        position &&
        createPortal(
          <div
            className="z-[80] max-h-[19rem] overflow-hidden rounded-2xl border border-cyan-300/15 bg-[#07111f]/95 p-2 text-slate-100 shadow-[0_28px_80px_rgba(2,6,23,0.55),0_0_0_1px_rgba(34,211,238,0.04)] backdrop-blur-xl"
            ref={popoverRef}
            role="listbox"
            style={{
              left: position.left,
              minWidth: position.width,
              position: 'fixed',
              top: position.top,
              width: Math.min(Math.max(position.width, 260), window.innerWidth - 24),
            }}
          >
            {header && <div className="p-1 pb-2">{header}</div>}
            <div className="premium-scrollbar max-h-72 overflow-y-auto pr-1">
              {options.length === 0 ? (
                <div className="px-3 py-3 text-sm text-slate-500">Nenhuma opção.</div>
              ) : (
                options.map((option) => {
                  const selected = option.value === value
                  return (
                    <button
                      className={cn(
                        'flex w-full items-start gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition hover:bg-cyan-400/10 hover:text-cyan-100',
                        selected && 'bg-cyan-400/10 text-cyan-100',
                      )}
                      key={option.value}
                      onClick={() => {
                        onChange(option.value)
                        setOpen(false)
                      }}
                      role="option"
                      type="button"
                    >
                      <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full border border-cyan-300/20">
                        {selected && <Check size={13} />}
                      </span>
                      <span className="min-w-0">
                        <span className="block font-bold">{option.label}</span>
                        {option.description && (
                          <span className="mt-0.5 block text-xs leading-5 text-slate-400">
                            {option.description}
                          </span>
                        )}
                      </span>
                    </button>
                  )
                })
              )}
            </div>
          </div>,
          document.body,
        )}
    </>
  )
}

type FloatingPosition = {
  left: number
  top: number
  width: number
}

function useFloatingPosition(
  open: boolean,
  triggerRef: RefObject<HTMLElement | null>,
  setPosition: (position: FloatingPosition | null) => void,
) {
  useLayoutEffect(() => {
    if (!open || !triggerRef.current) {
      setPosition(null)
      return
    }

    function updatePosition() {
      if (!triggerRef.current) return
      const rect = triggerRef.current.getBoundingClientRect()
      const viewportPadding = 12
      const calendarWidth = 320
      const defaultWidth = Math.min(Math.max(rect.width, 260), window.innerWidth - 24)
      const floatingWidth = triggerRef.current.dataset.picker === 'date'
        ? Math.min(calendarWidth, window.innerWidth - 24)
        : defaultWidth
      const left = Math.min(
        Math.max(rect.left, viewportPadding),
        window.innerWidth - viewportPadding - floatingWidth,
      )

      setPosition({
        left,
        top: Math.min(rect.bottom + 8, window.innerHeight - 96),
        width: rect.width,
      })
    }

    updatePosition()
    window.addEventListener('resize', updatePosition)
    window.addEventListener('scroll', updatePosition, true)
    return () => {
      window.removeEventListener('resize', updatePosition)
      window.removeEventListener('scroll', updatePosition, true)
    }
  }, [open, setPosition, triggerRef])
}

function useDismiss(
  open: boolean,
  setOpen: (open: boolean) => void,
  triggerRef: RefObject<HTMLElement | null>,
  popoverRef: RefObject<HTMLElement | null>,
) {
  useEffect(() => {
    if (!open) return

    function onPointerDown(event: PointerEvent) {
      const target = event.target as Node
      if (
        triggerRef.current?.contains(target) ||
        popoverRef.current?.contains(target)
      ) {
        return
      }
      setOpen(false)
    }

    function onKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }

    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open, popoverRef, setOpen, triggerRef])
}

function handleTriggerKey(
  event: KeyboardEvent<HTMLButtonElement>,
  setOpen: (open: boolean) => void,
) {
  if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    setOpen(true)
  }
}

function triggerClassName({
  disabled,
  error,
}: {
  disabled?: boolean
  error?: string
}) {
  return cn(
    'flex h-11 w-full items-center gap-2 rounded-xl border border-slate-200/80 bg-white/90 px-3.5 py-2 text-sm text-slate-950 shadow-sm outline-none transition-all duration-200 hover:border-cyan-300/40 hover:bg-white focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10 disabled:pointer-events-none disabled:opacity-50 dark:border-cyan-300/15 dark:bg-[#07111f]/82 dark:text-slate-100 dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] dark:hover:border-cyan-300/30 dark:hover:bg-[#0a1628] dark:focus:border-emerald-400 dark:focus:ring-emerald-400/10',
    error && 'border-rose-400/60 focus:border-rose-400 focus:ring-rose-400/10',
    disabled && 'cursor-not-allowed',
  )
}

function buildTimeOptions(start: string, end: string, intervalMinutes: number) {
  const startMinutes = timeToMinutes(start)
  const endMinutes = timeToMinutes(end)
  const options: string[] = []

  for (let minutes = startMinutes; minutes <= endMinutes; minutes += intervalMinutes) {
    options.push(minutesToTime(minutes))
  }

  return options
}

function timeToMinutes(value: string) {
  const [hours, minutes] = value.split(':').map(Number)
  return hours * 60 + minutes
}

function minutesToTime(totalMinutes: number) {
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`
}

function parseLocalDate(value: string) {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day)
}

function toDateValue(date: Date) {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0'),
  ].join('-')
}

function buildCalendarDays(month: Date) {
  const firstDay = new Date(month.getFullYear(), month.getMonth(), 1)
  const lastDay = new Date(month.getFullYear(), month.getMonth() + 1, 0)
  const days: Array<Date | null> = []

  for (let index = 0; index < firstDay.getDay(); index += 1) {
    days.push(null)
  }

  for (let day = 1; day <= lastDay.getDate(); day += 1) {
    days.push(new Date(month.getFullYear(), month.getMonth(), day))
  }

  return days
}

function isSameDate(first: Date, second: Date) {
  return (
    first.getFullYear() === second.getFullYear() &&
    first.getMonth() === second.getMonth() &&
    first.getDate() === second.getDate()
  )
}
