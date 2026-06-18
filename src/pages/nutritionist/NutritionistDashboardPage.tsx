import { useQuery } from '@tanstack/react-query'
import {
  AlertTriangle,
  CalendarDays,
  ClipboardCheck,
  Clock3,
  Users,
  Utensils,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { SectionHeader } from '../../components/ui/SectionHeader'
import { Skeleton } from '../../components/ui/Skeleton'
import { useAuth } from '../../features/auth/useAuth'
import { getNutritionistDashboard } from '../../features/clinical/services/workspaceService'
import type {
  DashboardAlert,
  DashboardPatientSummary,
} from '../../features/clinical/types'

const statCards = [
  {
    key: 'active_patients',
    label: 'Com acesso',
    caption: 'Trial ou ativo',
    icon: <Users size={20} />,
  },
  {
    key: 'trial_patients',
    label: 'Em Trial',
    caption: 'período gratuito',
    icon: <Clock3 size={20} />,
  },
  {
    key: 'expired_patients',
    label: 'Expirados',
    caption: 'aguardando ativação',
    icon: <AlertTriangle size={20} />,
  },
  {
    key: 'appointments_today',
    label: 'Consultas hoje',
    caption: 'agendadas para hoje',
    icon: <CalendarDays size={20} />,
  },
  {
    key: 'active_diets',
    label: 'Planos ativos',
    caption: 'dietas em vigor',
    icon: <Utensils size={20} />,
  },
  {
    key: 'important_alerts',
    label: 'Alertas',
    caption: 'pendências relevantes',
    icon: <AlertTriangle size={20} />,
  },
] as const

export function NutritionistDashboardPage() {
  const { session } = useAuth()
  const { data, isLoading, error } = useQuery({
    queryKey: ['nutritionist-dashboard'],
    queryFn: () => getNutritionistDashboard(session),
    enabled: Boolean(session),
  })

  if (isLoading) return <DashboardSkeleton />

  if (error) {
    return <DashboardError error={error} />
  }

  const stats = data?.stats
  const recentPatients = data?.recent_patients ?? []
  const alerts = data?.alerts ?? []

  return (
    <div className="space-y-6">
      <SectionHeader
        description="Resumo rápido da sua rotina e acompanhamento dos pacientes."
        eyebrow={<Badge tone="blue">Rotina clínica</Badge>}
        title="Dashboard do Nutricionista"
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {statCards.map((card) => (
          <SummaryCard
            caption={card.caption}
            icon={card.icon}
            key={card.key}
            label={card.label}
            value={stats?.[card.key] ?? 0}
          />
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_400px]">
        <Card className="overflow-hidden p-0">
          <div className="flex flex-col gap-2 border-b border-slate-200/80 p-5 dark:border-white/10 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-lg font-black">Pacientes recentes</h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Acompanhamentos com movimentação mais recente.
              </p>
            </div>
            <Badge tone="slate">{recentPatients.length} em foco</Badge>
          </div>

          {recentPatients.length === 0 ? (
            <div className="p-5">
              <EmptyState
                description="Quando houver pacientes vinculados, os acompanhamentos mais recentes aparecem aqui."
                icon={<Users size={22} />}
                title="Nenhum paciente em acompanhamento"
              />
            </div>
          ) : (
            <div className="divide-y divide-slate-100 dark:divide-white/10">
              {recentPatients.map((patient) => (
                <RecentPatientRow key={patient.id} patient={patient} />
              ))}
            </div>
          )}
        </Card>

        <Card className="overflow-hidden p-0" variant="glass">
          <div className="border-b border-slate-200/80 p-5 dark:border-white/10">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-black">Alertas e pendências</h2>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                  Itens que merecem atenção hoje.
                </p>
              </div>
              <div className="rounded-xl border border-amber-200/70 bg-amber-50 p-2.5 text-amber-700 dark:border-amber-400/20 dark:bg-amber-400/10 dark:text-amber-300">
                <AlertTriangle size={20} />
              </div>
            </div>
          </div>

          {alerts.length === 0 ? (
            <div className="p-5">
              <EmptyState
                className="min-h-72"
                description="Nenhuma pendencia importante encontrada para os pacientes ativos."
                icon={<ClipboardCheck size={22} />}
                title="Tudo em ordem"
              />
            </div>
          ) : (
            <div className="divide-y divide-slate-100 dark:divide-white/10">
              {alerts.map((alert) => (
                <AlertRow alert={alert} key={alert.id} />
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}

function SummaryCard({
  caption,
  icon,
  label,
  value,
}: {
  caption: string
  icon: ReactNode
  label: string
  value: number
}) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-slate-500 dark:text-slate-400">
            {label}
          </p>
          <strong className="mt-2 block text-3xl font-black tracking-tight text-slate-950 dark:text-white">
            {value}
          </strong>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            {caption}
          </p>
        </div>
        <div className="rounded-xl border border-cyan-200/70 bg-cyan-50 p-2.5 text-cyan-700 dark:border-cyan-400/20 dark:bg-cyan-400/10 dark:text-cyan-300">
          {icon}
        </div>
      </div>
    </Card>
  )
}

function RecentPatientRow({ patient }: { patient: DashboardPatientSummary }) {
  return (
    <Link
      className="grid gap-4 p-5 transition hover:bg-slate-50/80 dark:hover:bg-white/[0.03] md:grid-cols-[minmax(0,1fr)_180px_130px]"
      to={`/nutritionist/patients/${patient.id}`}
    >
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <p className="truncate font-bold text-slate-950 dark:text-white">
            {patient.name}
          </p>
          <Badge tone={patientStatusTone(patient.status)}>{patientStatusLabel(patient)}</Badge>
        </div>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Objetivo: {patient.objective || 'Não informado'}
        </p>
        {patient.alert && (
          <p className="mt-2 inline-flex rounded-full border border-amber-200/70 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700 dark:border-amber-400/20 dark:bg-amber-400/10 dark:text-amber-300">
            {patient.alert}
          </p>
        )}
      </div>

      <MiniInfo
        icon={<Clock3 size={16} />}
        label="Última atualização"
        value={formatRelativeDate(patient.last_update_at)}
      />
      <MiniInfo
        icon={<CalendarDays size={16} />}
        label="Próximo acompanhamento"
        value={
          patient.next_appointment_at
            ? formatDateTime(patient.next_appointment_at)
            : 'Não agendado'
        }
      />
    </Link>
  )
}

function AlertRow({ alert }: { alert: DashboardAlert }) {
  return (
    <Link
      className="block p-5 transition hover:bg-slate-50/80 dark:hover:bg-white/[0.03]"
      to={`/nutritionist/patients/${alert.patient_id}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-bold text-slate-950 dark:text-white">{alert.title}</p>
            <Badge tone={alert.tone}>{alert.patient_name}</Badge>
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-500 dark:text-slate-400">
            {alert.description}
          </p>
        </div>
        {alert.date && (
          <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">
            {formatRelativeDate(alert.date)}
          </span>
        )}
      </div>
    </Link>
  )
}

function MiniInfo({
  icon,
  label,
  value,
}: {
  icon: ReactNode
  label: string
  value: string
}) {
  return (
    <div className="min-w-0 rounded-xl border border-slate-200/70 bg-slate-50/70 px-3 py-2 dark:border-white/10 dark:bg-white/[0.04]">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 dark:text-slate-400">
        {icon}
        <span>{label}</span>
      </div>
      <p className="mt-1 truncate text-sm font-bold text-slate-800 dark:text-slate-100">
        {value}
      </p>
    </div>
  )
}

function patientStatusLabel(patient: DashboardPatientSummary) {
  if (patient.status === 'TRIAL') return `Trial: ${patient.trial_days_remaining} dias`
  if (patient.status === 'ACTIVE') return 'Ativo'
  return 'Expirado'
}

function patientStatusTone(status: DashboardPatientSummary['status']) {
  if (status === 'TRIAL') return 'blue'
  if (status === 'ACTIVE') return 'green'
  return 'red'
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <Skeleton className="h-7 w-32 rounded-full" />
        <Skeleton className="h-10 w-80 max-w-full" />
        <Skeleton className="h-5 w-[30rem] max-w-full" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton className="h-32" key={index} />
        ))}
      </div>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_400px]">
        <Skeleton className="h-[28rem]" />
        <Skeleton className="h-[28rem]" />
      </div>
    </div>
  )
}

function DashboardError({ error }: { error: Error }) {
  return (
    <div className="space-y-6">
      <SectionHeader
        description="Resumo rápido da sua rotina e acompanhamento dos pacientes."
        eyebrow={<Badge tone="red">Indisponível</Badge>}
        title="Dashboard do Nutricionista"
      />
      <Card className="p-6">
        <div className="flex items-start gap-3">
          <div className="rounded-xl border border-rose-200/70 bg-rose-50 p-2.5 text-rose-700 dark:border-rose-400/20 dark:bg-rose-400/10 dark:text-rose-300">
            <AlertTriangle size={20} />
          </div>
          <div>
            <h2 className="font-black">Não foi possível carregar o dashboard</h2>
            <p className="mt-1 text-sm leading-6 text-slate-500 dark:text-slate-400">
              {error.message || 'Tente novamente em alguns instantes.'}
            </p>
          </div>
        </div>
      </Card>
    </div>
  )
}

function formatRelativeDate(value: string | null) {
  if (!value) return 'Sem atualização'

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Sem atualização'

  const diffMs = Date.now() - date.getTime()
  const absDiffMs = Math.abs(diffMs)
  const dayMs = 1000 * 60 * 60 * 24

  if (absDiffMs < 1000 * 60 * 60) return diffMs < 0 ? 'em breve' : 'agora'
  if (absDiffMs < dayMs) {
    const hours = Math.max(1, Math.round(absDiffMs / (1000 * 60 * 60)))
    return diffMs < 0 ? `em ${hours}h` : `há ${hours}h`
  }

  const days = Math.max(1, Math.round(absDiffMs / dayMs))
  if (days === 1) return diffMs < 0 ? 'amanhã' : 'ontem'
  if (days < 30) return diffMs < 0 ? `em ${days} dias` : `há ${days} dias`

  return formatDate(value)
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    month: '2-digit',
  }).format(new Date(value))
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(new Date(value))
}
