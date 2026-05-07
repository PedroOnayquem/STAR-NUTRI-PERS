import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Activity,
  Bot,
  Dumbbell,
  Droplets,
  HeartPulse,
  LineChart as LineChartIcon,
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
import { Input } from '../../components/ui/Input'
import { SectionHeader } from '../../components/ui/SectionHeader'
import { PageSkeleton } from '../../components/ui/Skeleton'
import { StatCard } from '../../components/ui/StatCard'
import { ChatExperience } from '../../features/chat/components/ChatExperience'
import { useAuth } from '../../features/auth/useAuth'
import { createVariableMetric } from '../../features/clinical/services/clinicalDataService'
import { getPatientContext } from '../../features/clinical/services/workspaceService'
import type { PatientContext } from '../../features/clinical/types'

export function PatientWorkspacePage({
  view = 'dashboard',
}: {
  view?: 'dashboard' | 'diet' | 'workout' | 'metrics' | 'evolution' | 'chat' | 'profile'
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
  const title = context.profile?.full_name
    ? `Ola, ${context.profile.full_name.split(' ')[0]}`
    : 'Area do paciente'

  return (
    <div className="space-y-6">
      <SectionHeader
        description="Acompanhe seu plano, atualize metricas e converse com a IA dentro das orientacoes do nutricionista."
        eyebrow={<Badge tone="green">Area do paciente</Badge>}
        title={title}
      />

      {view === 'dashboard' && <PatientDashboard context={context} />}
      {view === 'diet' && <PatientDiet context={context} />}
      {view === 'workout' && <PatientWorkout context={context} />}
      {view === 'metrics' && <PatientMetrics context={context} queryKey={queryKey} />}
      {view === 'evolution' && <Evolution context={context} />}
      {view === 'chat' && (
        <ChatExperience
          externalQueryKey={queryKey}
          patientName={context.profile?.full_name ?? undefined}
        />
      )}
      {view === 'profile' && <Profile context={context} />}
    </div>
  )
}

function PatientDashboard({ context }: { context: PatientContext }) {
  const activeDiet = context.diets.find((diet) => diet.is_active)
  const activeWorkout = context.workouts.find((workout) => workout.is_active)
  const latestWeight = context.variable_metrics.find((metric) =>
    metric.name.toLowerCase().includes('peso'),
  )

  return (
    <>
      <div className="grid gap-4 md:grid-cols-3">
        <StatCard caption="definida pelo nutricionista" icon={<Utensils size={20} />} label="Dieta" value={activeDiet ? 'Ativa' : 'Pendente'} />
        <StatCard caption="plano de treino" icon={<Dumbbell size={20} />} label="Treino" value={activeWorkout ? 'Ativo' : 'Pendente'} />
        <StatCard caption="ultimo registro" icon={<Activity size={20} />} label="Peso" value={latestWeight ? `${latestWeight.value} ${latestWeight.unit ?? ''}` : '-'} />
      </div>
      <div className="mt-6 grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <Card className="p-5" variant="glass">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-emerald-500/10 p-2.5 text-emerald-700 dark:text-emerald-300">
              <HeartPulse size={22} />
            </div>
            <div>
              <h2 className="font-black">Jornada de hoje</h2>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Registre metricas e siga seu plano.
              </p>
            </div>
          </div>
          <div className="mt-6 grid gap-3">
            <MiniStatus label="Metricas registradas" value={context.variable_metrics.length} />
            <MiniStatus label="Condicoes consideradas" value={context.conditions.length} />
            <MiniStatus label="Conversas com IA" value={context.chat_sessions.length} />
          </div>
        </Card>
        <Card className="p-5">
          <h2 className="font-black">Plano ativo</h2>
          <div className="mt-4 space-y-3">
            <PlanLine icon={<Utensils size={18} />} title={activeDiet?.title ?? 'Dieta nao cadastrada'} text={activeDiet?.description ?? 'Aguarde seu nutricionista definir uma dieta.'} />
            <PlanLine icon={<Droplets size={18} />} title="Hidratacao" text={activeDiet?.water_goal_ml ? `${activeDiet.water_goal_ml} ml por dia` : 'Meta nao definida.'} />
            <PlanLine icon={<Dumbbell size={18} />} title={activeWorkout?.title ?? 'Treino nao cadastrado'} text={activeWorkout?.description ?? 'Aguarde seu nutricionista definir um treino.'} />
          </div>
        </Card>
      </div>
    </>
  )
}

function PatientDiet({ context }: { context: PatientContext }) {
  const activeDiet = context.diets.find((diet) => diet.is_active)
  if (!activeDiet) {
    return <EmptyState description="Seu nutricionista ainda nao ativou uma dieta." icon={<Utensils size={22} />} title="Sem dieta ativa" />
  }

  return (
    <Card className="p-5">
      <h2 className="text-xl font-black">{activeDiet.title}</h2>
      <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{activeDiet.description}</p>
      <div className="mt-4 grid gap-2 md:grid-cols-5">
        <MiniStatus label="Kcal" value={activeDiet.calories ?? '-'} />
        <MiniStatus label="Proteina" value={activeDiet.protein ?? '-'} />
        <MiniStatus label="Carbo" value={activeDiet.carbs ?? '-'} />
        <MiniStatus label="Gordura" value={activeDiet.fats ?? '-'} />
        <MiniStatus label="Agua" value={activeDiet.water_goal_ml ?? '-'} />
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
    return <EmptyState description="Seu nutricionista ainda nao ativou um treino." icon={<Dumbbell size={22} />} title="Sem treino ativo" />
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
              {exercise.sets} series - {exercise.reps} reps - descanso {exercise.rest_time}
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
        <h2 className="font-black">Atualizar metricas</h2>
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
    <Card className="p-5">
      <div className="flex items-center gap-2">
        <LineChartIcon size={20} />
        <h2 className="font-black">Evolucao</h2>
      </div>
      <div className={compact ? 'mt-4 h-72' : 'mt-4 h-96'}>
        <ResponsiveContainer height="100%" width="100%">
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

function Profile({ context }: { context: PatientContext }) {
  return (
    <Card className="p-5">
      <h2 className="font-black">Meu perfil</h2>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <MiniStatus label="Nome" value={context.profile?.full_name ?? '-'} />
        <MiniStatus label="Email" value={context.profile?.email ?? '-'} />
        <MiniStatus label="Objetivo" value={context.patient.objective ?? '-'} />
        <MiniStatus label="Nutricionista" value={context.nutritionist?.specialty ?? 'Star Nutri'} />
      </div>
    </Card>
  )
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
