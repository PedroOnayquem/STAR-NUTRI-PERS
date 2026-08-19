import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Activity,
  AlertTriangle,
  CalendarDays,
  Dumbbell,
  Droplets,
  ExternalLink,
  HeartPulse,
  LineChart as LineChartIcon,
  LockKeyhole,
  MapPin,
  Save,
  Utensils,
} from 'lucide-react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { AppDatePicker } from '../../components/ui/FormControls'
import { Input } from '../../components/ui/Input'
import { SectionHeader } from '../../components/ui/SectionHeader'
import { PageSkeleton } from '../../components/ui/Skeleton'
import { StatCard } from '../../components/ui/StatCard'
import { NutritionistAvatar } from '../../components/nutritionist/NutritionistAvatar'
import { ChatExperience } from '../../features/chat/components/ChatExperience'
import { useAuth } from '../../features/auth/useAuth'
import { createVariableMetric } from '../../features/clinical/services/clinicalDataService'
import {
  getPatientContext,
  updateMyPatientProfile,
} from '../../features/clinical/services/workspaceService'
import type { AppointmentStatus, AppointmentType, PatientAppointmentRecord, PatientContext } from '../../features/clinical/types'

export function PatientWorkspacePage({
  view = 'dashboard',
}: {
  view?: 'dashboard' | 'diet' | 'workout' | 'agenda' | 'metrics' | 'chat' | 'profile'
}) {
  const { session } = useAuth()
  const queryKey = ['patient-context']
  const query = useQuery({
    queryKey,
    queryFn: () => getPatientContext(session),
    enabled: Boolean(session),
  })

  if (query.isLoading) return <PageSkeleton />
  if (query.error) throw query.error
  if (!query.data) return null

  const context = query.data
  const access = context.access ?? {
    can_use_ai_chat: context.patient.access_status !== 'EXPIRED',
    expired_message: context.patient.trial_expired_message ?? null,
    has_premium_access: context.patient.access_status !== 'EXPIRED',
    status: context.patient.access_status,
    trial_days_remaining: context.patient.trial_days_remaining ?? 0,
  }
  const title = context.profile?.full_name
    ? `Olá, ${context.profile.full_name.split(' ')[0]}`
    : 'Área do paciente'

  return (
    <div className="space-y-6">
      <SectionHeader
        description="Acompanhe seu plano, atualize métricas e converse com a IA dentro das orientações do nutricionista."
        eyebrow={<Badge tone={access.status === 'EXPIRED' ? 'red' : access.status === 'TRIAL' ? 'blue' : 'green'}>{patientAccessLabel(access)}</Badge>}
        title={title}
      />

      {access.status === 'EXPIRED' ? (
        <AccessExpiredNotice message={access.expired_message} />
      ) : access.status === 'TRIAL' ? (
        <Card className="border-cyan-200 bg-cyan-50/80 p-4 text-sm font-semibold text-cyan-800 dark:border-cyan-400/20 dark:bg-cyan-400/10 dark:text-cyan-100">
          Você está no período gratuito. Restam {access.trial_days_remaining} {access.trial_days_remaining === 1 ? 'dia' : 'dias'} de acesso.
        </Card>
      ) : null}

      {view === 'dashboard' && <PatientDashboard context={context} />}
      {view === 'diet' && (access.has_premium_access ? <PatientDiet context={context} /> : <PremiumBlocked />)}
      {view === 'workout' && (access.has_premium_access ? <PatientWorkout context={context} /> : <PremiumBlocked />)}
      {view === 'agenda' && <PatientAgenda context={context} />}
      {view === 'metrics' && (access.has_premium_access ? <PatientMetrics context={context} queryKey={queryKey} /> : <PremiumBlocked />)}
      {view === 'chat' && access.can_use_ai_chat && (
        <ChatExperience
          externalQueryKey={queryKey}
          patientName={context.profile?.full_name ?? undefined}
          scope="patient"
        />
      )}
      {view === 'chat' && !access.can_use_ai_chat && <PremiumBlocked />}
      {view === 'profile' && (
        <Profile
          context={context}
          key={patientProfileKey(context)}
          queryKey={queryKey}
        />
      )}
    </div>
  )
}

function AccessExpiredNotice({ message }: { message: string | null }) {
  return (
    <Card className="border-rose-200 bg-rose-50 p-5 dark:border-rose-400/20 dark:bg-rose-400/10">
      <div className="flex gap-3">
        <div className="rounded-xl bg-rose-100 p-2.5 text-rose-700 dark:bg-rose-400/10 dark:text-rose-200">
          <AlertTriangle size={20} />
        </div>
        <div>
          <h2 className="font-black text-rose-800 dark:text-rose-100">Período gratuito expirado</h2>
          <p className="mt-1 text-sm leading-6 text-rose-700 dark:text-rose-200">
            {message || 'Entre em contato com seu nutricionista para ativar seu acesso.'}
          </p>
        </div>
      </div>
    </Card>
  )
}

function PremiumBlocked() {
  return (
    <EmptyState
      description="Entre em contato com seu nutricionista para ativar seu acesso completo."
      icon={<LockKeyhole size={22} />}
      title="Acesso bloqueado"
    />
  )
}

function patientAccessLabel(access: { status: 'TRIAL' | 'ACTIVE' | 'EXPIRED'; trial_days_remaining: number }) {
  if (access.status === 'TRIAL') return `Trial: ${access.trial_days_remaining} dias`
  if (access.status === 'ACTIVE') return 'Acesso ativo'
  return 'Trial expirado'
}

function PatientDashboard({ context }: { context: PatientContext }) {
  const activeDiet = context.diets.find((diet) => diet.is_active)
  const activeWorkout = context.workouts.find((workout) => workout.is_active)
  const latestWeight = context.variable_metrics.find((metric) =>
    metric.name.toLowerCase().includes('peso'),
  )
  const nextAppointment = getUpcomingAppointments(context.appointments ?? [])[0]

  return (
    <>
      <div className="grid gap-4 md:grid-cols-3">
        <StatCard caption="definida pelo nutricionista" icon={<Utensils size={20} />} label="Dieta" value={activeDiet ? 'Ativa' : 'Pendente'} />
        <StatCard caption="plano de treino" icon={<Dumbbell size={20} />} label="Treino" value={activeWorkout ? 'Ativo' : 'Pendente'} />
        <StatCard caption="último registro" icon={<Activity size={20} />} label="Peso" value={latestWeight ? `${latestWeight.value} ${latestWeight.unit ?? ''}` : '-'} />
      </div>
      <div className="mt-6 grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <Card className="p-5">
          <div className="flex items-center gap-4">
            <NutritionistAvatar nutritionist={context.nutritionist} />
            <div className="min-w-0">
              <p className="text-sm font-semibold text-slate-500 dark:text-slate-400">
                Nutricionista responsável
              </p>
              <h2 className="mt-1 truncate font-black">
                {context.nutritionist?.professional_name || 'Profissional não informado'}
              </h2>
              <p className="mt-1 truncate text-sm text-slate-500 dark:text-slate-400">
                {context.nutritionist?.clinic_name || context.nutritionist?.specialty || 'Clínica não informada'}
              </p>
            </div>
          </div>
        </Card>
        <Card className="p-5" variant="glass">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-emerald-500/10 p-2.5 text-emerald-700 dark:text-emerald-300">
              <HeartPulse size={22} />
            </div>
            <div>
              <h2 className="font-black">Jornada de hoje</h2>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Registre métricas e siga seu plano.
              </p>
            </div>
          </div>
          <div className="mt-6 grid gap-3">
            <MiniStatus label="Métricas registradas" value={context.variable_metrics.length} />
            <MiniStatus label="Condições consideradas" value={context.conditions.length} />
            <MiniStatus label="Conversas com IA" value={context.patient_chats.length} />
          </div>
        </Card>
        <Card className="p-5">
          <h2 className="font-black">Próximo acompanhamento</h2>
          <div className="mt-4">
            {nextAppointment ? (
              <PatientAppointmentCard appointment={nextAppointment} compact />
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-300 p-5 text-sm text-slate-500 dark:border-white/15 dark:text-slate-400">
                Nenhum acompanhamento agendado.
              </div>
            )}
          </div>
        </Card>
        <Card className="p-5">
          <h2 className="font-black">Plano ativo</h2>
          <div className="mt-4 space-y-3">
            <PlanLine icon={<Utensils size={18} />} title={activeDiet?.title ?? 'Dieta não cadastrada'} text={activeDiet?.description ?? 'Aguarde seu nutricionista definir uma dieta.'} />
            <PlanLine icon={<Droplets size={18} />} title="Hidratação" text={activeDiet?.water_goal_ml ? `${activeDiet.water_goal_ml} ml por dia` : 'Meta não definida.'} />
            <PlanLine icon={<Dumbbell size={18} />} title={activeWorkout?.title ?? 'Treino não cadastrado'} text={activeWorkout?.description ?? 'Aguarde seu nutricionista definir um treino.'} />
          </div>
        </Card>
      </div>
    </>
  )
}

function PatientAgenda({ context }: { context: PatientContext }) {
  const appointments = context.appointments ?? []
  const upcoming = getUpcomingAppointments(appointments)
  const history = appointments
    .filter((appointment) => !upcoming.some((item) => item.id === appointment.id))
    .slice()
    .sort(sortAppointmentsDesc)

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
      <Card className="overflow-hidden p-0">
        <div className="border-b border-slate-200/80 p-5 dark:border-white/10">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-cyan-400/10 p-2.5 text-cyan-700 dark:text-cyan-300">
              <CalendarDays size={22} />
            </div>
            <div>
              <h2 className="font-black">Próximos agendamentos</h2>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Compromissos marcados pelo seu nutricionista.
              </p>
            </div>
          </div>
        </div>
        {upcoming.length === 0 ? (
          <div className="p-5">
            <EmptyState
              description="Quando seu nutricionista marcar um compromisso, ele aparecerá aqui automaticamente."
              icon={<CalendarDays size={22} />}
              title="Nenhum acompanhamento agendado"
            />
          </div>
        ) : (
          <div className="divide-y divide-slate-100 dark:divide-white/10">
            {upcoming.map((appointment) => (
              <PatientAppointmentCard appointment={appointment} key={appointment.id} />
            ))}
          </div>
        )}
      </Card>

      <Card className="overflow-hidden p-0" variant="glass">
        <div className="border-b border-slate-200/80 p-5 dark:border-white/10">
          <h2 className="font-black">Histórico</h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Consultas concluidas, vencidas ou canceladas.
          </p>
        </div>
        {history.length === 0 ? (
          <div className="p-5 text-sm text-slate-500 dark:text-slate-400">
            Nenhum compromisso anterior.
          </div>
        ) : (
          <div className="premium-scrollbar max-h-[34rem] overflow-y-auto divide-y divide-slate-100 dark:divide-white/10">
            {history.map((appointment) => (
              <PatientAppointmentCard appointment={appointment} compact key={appointment.id} />
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}

function PatientAppointmentCard({
  appointment,
  compact = false,
}: {
  appointment: PatientAppointmentRecord
  compact?: boolean
}) {
  return (
    <div className={compact ? 'p-4' : 'p-5'}>
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-black">{appointment.title}</h3>
        <Badge tone="blue">{appointmentTypeLabel(appointment.type)}</Badge>
        <Badge tone={appointmentStatusTone(appointment.status)}>
          {appointmentStatusLabel(appointment.status)}
        </Badge>
      </div>
      <p className="mt-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
        {formatDate(appointment.date)} as {formatTime(appointment.start_time)}
        {appointment.end_time ? ` - ${formatTime(appointment.end_time)}` : ''}
      </p>
      {(appointment.location || appointment.meeting_link) && (
        <div className="mt-2 flex flex-wrap gap-3 text-sm text-slate-500 dark:text-slate-400">
          {appointment.location && (
            <span className="inline-flex items-center gap-1.5">
              <MapPin size={15} />
              {appointment.location}
            </span>
          )}
          {appointment.meeting_link && (
            <a
              className="inline-flex items-center gap-1.5 font-semibold text-cyan-600 dark:text-cyan-300"
              href={appointment.meeting_link}
              rel="noreferrer"
              target="_blank"
            >
              <ExternalLink size={15} />
              Link da reunião
            </a>
          )}
        </div>
      )}
      {(appointment.description || appointment.notes) && (
        <p className="mt-2 text-sm leading-6 text-slate-500 dark:text-slate-400">
          {appointment.description || appointment.notes}
        </p>
      )}
    </div>
  )
}

function PatientDiet({ context }: { context: PatientContext }) {
  const activeDiet = context.diets.find((diet) => diet.is_active)
  if (!activeDiet) {
    return <EmptyState description="Seu nutricionista ainda não ativou uma dieta." icon={<Utensils size={22} />} title="Sem dieta ativa" />
  }

  return (
    <Card className="p-5">
      <h2 className="text-xl font-black">{activeDiet.title}</h2>
      <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{activeDiet.description}</p>
      <div className="mt-4 grid gap-2 md:grid-cols-5">
        <MiniStatus label="Kcal" value={activeDiet.calories ?? '-'} />
        <MiniStatus label="Proteína" value={activeDiet.protein ?? '-'} />
        <MiniStatus label="Carbo" value={activeDiet.carbs ?? '-'} />
        <MiniStatus label="Gordura" value={activeDiet.fats ?? '-'} />
        <MiniStatus label="Água" value={activeDiet.water_goal_ml ?? '-'} />
      </div>
      <div className="mt-6 grid gap-3">
        {(activeDiet.meals ?? []).map((meal) => (
          <div className="rounded-2xl border border-slate-200 p-4 dark:border-white/10" key={meal.id}>
            <h3 className="font-black">{meal.meal_name} {meal.meal_time && <span className="text-sm text-slate-400">- {meal.meal_time}</span>}</h3>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
              {meal.foods.map((food) => `${food.name} ${food.quantity}`).join(', ')}
            </p>
            {meal.notes && <p className="mt-2 text-sm text-slate-500">{meal.notes}</p>}
          </div>
        ))}
      </div>
    </Card>
  )
}

function PatientWorkout({ context }: { context: PatientContext }) {
  const activeWorkout = context.workouts.find((workout) => workout.is_active)
  if (!activeWorkout) {
    return <EmptyState description="Seu nutricionista ainda não ativou um treino." icon={<Dumbbell size={22} />} title="Sem treino ativo" />
  }

  return (
    <Card className="p-5">
      <h2 className="text-xl font-black">{activeWorkout.title}</h2>
      <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{activeWorkout.description}</p>
      <div className="mt-6 grid gap-3">
        {(activeWorkout.exercises ?? []).map((exercise) => (
          <div className="rounded-2xl border border-slate-200 p-4 dark:border-white/10" key={exercise.id}>
            <h3 className="font-black">{exercise.exercise_name}</h3>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
              {exercise.sets} séries - {exercise.reps} reps - descanso {exercise.rest_time}
            </p>
            {exercise.notes && <p className="mt-2 text-sm text-slate-500">{exercise.notes}</p>}
          </div>
        ))}
      </div>
    </Card>
  )
}

function PatientMetrics({ context, queryKey }: { context: PatientContext; queryKey: unknown[] }) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState({ name: 'peso', value: '', unit: 'kg' })
  const mutation = useMutation({
    mutationFn: () => createVariableMetric({
      patient_id: context.patient.id,
      name: form.name,
      value: form.value,
      unit: form.unit,
      recorded_at: new Date().toISOString(),
    }),
    onSuccess: () => {
      setForm({ ...form, value: '' })
      queryClient.invalidateQueries({ queryKey })
    },
  })

  return (
    <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
      <Card className="p-5" variant="glass">
        <h2 className="font-black">Atualizar métricas</h2>
        <div className="mt-4 space-y-3">
          <Input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
          <Input placeholder="Valor" value={form.value} onChange={(event) => setForm({ ...form, value: event.target.value })} />
          <Input placeholder="Unidade" value={form.unit} onChange={(event) => setForm({ ...form, unit: event.target.value })} />
          <Button disabled={!form.name || !form.value || mutation.isPending} onClick={() => mutation.mutate()} variant="premium">
            <Save size={18} />
            Registrar
          </Button>
        </div>
      </Card>
      <Evolution context={context} compact />
    </div>
  )
}

function Evolution({ context, compact = false }: { context: PatientContext; compact?: boolean }) {
  const data = useMemo(() => context.variable_metrics
    .filter((metric) => metric.name.toLowerCase().includes('peso'))
    .slice()
    .reverse()
    .map((metric) => ({
      date: new Date(metric.recorded_at || metric.created_at || '').toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }),
      value: Number(metric.value.replace(',', '.')) || 0,
    })), [context.variable_metrics])

  return (
    <Card className="min-w-0 p-5">
      <div className="flex items-center gap-2">
        <LineChartIcon size={20} />
        <h2 className="font-black">Evolução</h2>
      </div>
      <div className={compact ? 'mt-4 h-72 min-w-0' : 'mt-4 h-96 min-w-0'}>
        <ResponsiveContainer
          height="100%"
          initialDimension={{ width: 640, height: compact ? 288 : 384 }}
          minHeight={0}
          minWidth={0}
          width="100%"
        >
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip />
            <Line dataKey="value" stroke="#10b981" strokeWidth={3} type="monotone" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}

function Profile({ context, queryKey }: { context: PatientContext; queryKey: unknown[] }) {
  const { session } = useAuth()
  const queryClient = useQueryClient()
  const [saved, setSaved] = useState(false)
  const [form, setForm] = useState(() => ({
    birth_date: context.patient.birth_date ?? '',
    full_name: context.profile?.full_name ?? '',
    gender: context.patient.gender ?? '',
    objective: context.patient.objective ?? '',
    phone: context.profile?.phone ?? '',
  }))

  const mutation = useMutation({
    mutationFn: () =>
      updateMyPatientProfile(session, {
        birth_date: nullable(form.birth_date),
        full_name: form.full_name.trim(),
        gender: nullable(form.gender),
        objective: nullable(form.objective),
        phone: nullable(form.phone),
      }),
    onSuccess: () => {
      setSaved(true)
      queryClient.invalidateQueries({ queryKey })
      window.setTimeout(() => setSaved(false), 2400)
    },
  })

  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-black">Meu perfil</h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Mantenha seus dados básicos atualizados.
          </p>
        </div>
        <Button
          disabled={mutation.isPending || form.full_name.trim().length < 3}
          onClick={() => mutation.mutate()}
          variant="premium"
        >
          <Save size={18} />
          {mutation.isPending ? 'Salvando...' : 'Salvar perfil'}
        </Button>
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-2">
        <Field label="Nome completo">
          <Input
            value={form.full_name}
            onChange={(event) => setForm({ ...form, full_name: event.target.value })}
          />
        </Field>
        <Field label="Telefone">
          <Input
            inputMode="tel"
            placeholder="(00) 00000-0000"
            value={form.phone}
            onChange={(event) => setForm({ ...form, phone: event.target.value })}
          />
        </Field>
        <Field label="Data de nascimento">
          <AppDatePicker
            value={form.birth_date}
            onChange={(value) => setForm({ ...form, birth_date: value })}
          />
        </Field>
        <Field label="Gênero">
          <Input
            placeholder="Ex.: feminino, masculino, prefiro não informar"
            value={form.gender}
            onChange={(event) => setForm({ ...form, gender: event.target.value })}
          />
        </Field>
        <Field label="Objetivo">
          <Input
            placeholder="Ex.: ganho de massa, saúde, performance"
            value={form.objective}
            onChange={(event) => setForm({ ...form, objective: event.target.value })}
          />
        </Field>
        <Field label="E-mail">
          <Input disabled value={context.profile?.email ?? ''} />
        </Field>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <MiniStatus label="Nutricionista" value={context.nutritionist?.specialty ?? 'Star Nutri'} />
        <MiniStatus label="Status" value={context.patient.is_active ? 'Ativo' : 'Inativo'} />
      </div>

      {saved && (
        <p className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-200">
          Perfil atualizado com sucesso.
        </p>
      )}
      {mutation.error && (
        <p className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700 dark:border-rose-400/20 dark:bg-rose-400/10 dark:text-rose-200">
          {mutation.error instanceof Error ? mutation.error.message : 'Não foi possível salvar.'}
        </p>
      )}
    </Card>
  )
}

function Field({
  children,
  label,
}: {
  children: React.ReactNode
  label: string
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-xs font-black uppercase text-slate-400">
        {label}
      </span>
      {children}
    </label>
  )
}

function nullable(value: string) {
  const trimmed = value.trim()
  return trimmed ? trimmed : null
}

function patientProfileKey(context: PatientContext) {
  return JSON.stringify([
    context.patient.id,
    context.patient.birth_date,
    context.patient.gender,
    context.patient.objective,
    context.profile?.full_name,
    context.profile?.phone,
  ])
}

function formatDate(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString('pt-BR')
}

function formatTime(value: string) {
  return value.slice(0, 5)
}

function getUpcomingAppointments(appointments: PatientAppointmentRecord[]) {
  const today = new Date().toISOString().slice(0, 10)
  return appointments
    .filter((appointment) => appointment.date >= today && appointment.status !== 'cancelado')
    .slice()
    .sort(sortAppointmentsAsc)
}

function sortAppointmentsAsc(
  first: PatientAppointmentRecord,
  second: PatientAppointmentRecord,
) {
  return `${first.date}T${first.start_time}`.localeCompare(
    `${second.date}T${second.start_time}`,
  )
}

function sortAppointmentsDesc(
  first: PatientAppointmentRecord,
  second: PatientAppointmentRecord,
) {
  return sortAppointmentsAsc(second, first)
}

function appointmentTypeLabel(type: AppointmentType) {
  const labels: Record<AppointmentType, string> = {
    acompanhamento: 'Acompanhamento',
    consulta: 'Consulta',
    reuniao: 'Reunião',
    avaliacao: 'Avaliação',
    retorno: 'Retorno',
    revisao_dieta: 'Revisão de dieta',
    revisao_treino: 'Revisão de treino',
    outro: 'Outro',
  }
  return labels[type]
}

function appointmentStatusLabel(status: AppointmentStatus) {
  const labels: Record<AppointmentStatus, string> = {
    agendado: 'Agendado',
    confirmado: 'Confirmado',
    concluido: 'Concluído',
    cancelado: 'Cancelado',
    faltou: 'Faltou',
  }
  return labels[status]
}

function appointmentStatusTone(status: AppointmentStatus) {
  const tones: Record<AppointmentStatus, 'green' | 'blue' | 'amber' | 'red' | 'slate'> = {
    agendado: 'blue',
    confirmado: 'green',
    concluido: 'slate',
    cancelado: 'red',
    faltou: 'amber',
  }
  return tones[status]
}

function MiniStatus({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white/70 p-4 dark:border-white/10 dark:bg-white/[0.04]">
      <p className="text-xs font-black uppercase text-slate-400">{label}</p>
      <p className="mt-1 font-black">{value}</p>
    </div>
  )
}

function PlanLine({ icon, text, title }: { icon: React.ReactNode; text: string; title: string }) {
  return (
    <div className="flex gap-4 rounded-2xl border border-slate-200 p-4 dark:border-white/10">
      <div className="rounded-xl bg-slate-100 p-2 text-slate-700 dark:bg-white/10 dark:text-slate-200">
        {icon}
      </div>
      <div>
        <p className="font-bold">{title}</p>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{text}</p>
      </div>
    </div>
  )
}
