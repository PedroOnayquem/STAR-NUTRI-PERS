import { useMemo, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import {
  Activity,
  AlertTriangle,
  Bot,
  Dumbbell,
  HeartPulse,
  Plus,
  Save,
  Trash2,
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
import { Input, Textarea } from '../../components/ui/Input'
import { SectionHeader } from '../../components/ui/SectionHeader'
import { PageSkeleton } from '../../components/ui/Skeleton'
import { StatCard } from '../../components/ui/StatCard'
import { ChatExperience } from '../../features/chat/components/ChatExperience'
import { useAuth } from '../../features/auth/useAuth'
import {
  createDiet,
  createHealthCondition,
  createMainMetric,
  createVariableMetric,
  createWorkout,
  deleteDiet,
  deleteHealthCondition,
  deleteMetric,
  deleteWorkout,
  duplicateDiet,
  updateDiet,
  updateWorkout,
  upsertDietMeals,
  upsertWorkoutExercises,
} from '../../features/clinical/services/clinicalDataService'
import {
  getNutritionistPatientContext,
  updateNutritionistPatient,
} from '../../features/clinical/services/workspaceService'
import type {
  DietRecord,
  HealthConditionRecord,
  PatientContext,
  WorkoutRecord,
} from '../../features/clinical/types'
import { cn } from '../../lib/utils'

const tabs = [
  { id: 'overview', label: 'Resumo', icon: <HeartPulse size={16} /> },
  { id: 'profile', label: 'Perfil', icon: <Save size={16} /> },
  { id: 'diets', label: 'Dietas', icon: <Utensils size={16} /> },
  { id: 'workouts', label: 'Treinos', icon: <Dumbbell size={16} /> },
  { id: 'metrics', label: 'Metricas', icon: <Activity size={16} /> },
  { id: 'conditions', label: 'Condicoes', icon: <AlertTriangle size={16} /> },
  { id: 'chat', label: 'Chat IA', icon: <Bot size={16} /> },
] as const

type TabId = (typeof tabs)[number]['id']

export function PatientDetailPage() {
  const { patientId } = useParams()
  const { session } = useAuth()
  const [activeTab, setActiveTab] = useState<TabId>('overview')

  const queryKey = ['nutritionist-patient-context', patientId]
  const query = useQuery({
    queryKey,
    queryFn: () => getNutritionistPatientContext(patientId!, session),
    enabled: Boolean(patientId && session),
  })

  if (query.isLoading) return <PageSkeleton />
  if (query.error) throw query.error
  if (!query.data) return null

  const context = query.data
  const patientName = context.profile?.full_name ?? 'Paciente'
  const activeDiet = context.diets.find((diet) => diet.is_active)
  const activeWorkout = context.workouts.find((workout) => workout.is_active)

  return (
    <div className="space-y-6">
      <SectionHeader
        description={context.patient.objective || 'Paciente sem objetivo definido.'}
        eyebrow={<Badge tone={context.patient.is_active ? 'green' : 'amber'}>{context.patient.is_active ? 'Ativo' : 'Inativo'}</Badge>}
        title={patientName}
      />

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard caption="plano nutricional" icon={<Utensils size={20} />} label="Dieta" value={activeDiet ? 'Ativa' : 'Sem dieta'} />
        <StatCard caption="rotina de exercicios" icon={<Dumbbell size={20} />} label="Treino" value={activeWorkout ? 'Ativo' : 'Sem treino'} />
        <StatCard caption="registros recentes" icon={<Activity size={20} />} label="Metricas" value={context.variable_metrics.length} />
      </div>

      <div className="flex gap-2 overflow-x-auto rounded-2xl border border-slate-200 bg-white p-2 dark:border-white/10 dark:bg-white/[0.04]">
        {tabs.map((tab) => (
          <button
            className={cn(
              'inline-flex shrink-0 items-center gap-2 rounded-xl px-3 py-2 text-sm font-bold transition',
              activeTab === tab.id
                ? 'bg-slate-950 text-white dark:bg-white dark:text-slate-950'
                : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-white/10',
            )}
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            type="button"
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'overview' && <OverviewTab context={context} />}
      {activeTab === 'profile' && <ProfileTab context={context} queryKey={queryKey} />}
      {activeTab === 'diets' && <DietsTab context={context} queryKey={queryKey} />}
      {activeTab === 'workouts' && <WorkoutsTab context={context} queryKey={queryKey} />}
      {activeTab === 'metrics' && <MetricsTab context={context} queryKey={queryKey} />}
      {activeTab === 'conditions' && <ConditionsTab context={context} queryKey={queryKey} />}
      {activeTab === 'chat' && (
        <ChatExperience
          externalQueryKey={queryKey}
          patientId={context.patient.id}
          patientName={context.profile?.full_name ?? undefined}
        />
      )}
    </div>
  )
}

function OverviewTab({ context }: { context: PatientContext }) {
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_420px]">
      <Card className="p-5">
        <h2 className="font-black">Historico e observacoes</h2>
        <p className="mt-3 text-sm leading-6 text-slate-600 dark:text-slate-300">
          {context.patient.notes || 'Sem observacoes cadastradas.'}
        </p>
      </Card>
      <Card className="p-5">
        <h2 className="font-black">Condicoes clinicas</h2>
        <div className="mt-4 space-y-2">
          {context.conditions.length === 0 ? (
            <p className="text-sm text-slate-500 dark:text-slate-400">Nenhuma condicao cadastrada.</p>
          ) : (
            context.conditions.slice(0, 5).map((condition) => (
              <Badge key={condition.id} tone="amber">{condition.title}</Badge>
            ))
          )}
        </div>
      </Card>
    </div>
  )
}

function ProfileTab({
  context,
  queryKey,
}: {
  context: PatientContext
  queryKey: unknown[]
}) {
  const { session } = useAuth()
  const queryClient = useQueryClient()
  const [form, setForm] = useState({
    full_name: context.profile?.full_name ?? '',
    phone: context.profile?.phone ?? '',
    birth_date: context.patient.birth_date ?? '',
    gender: context.patient.gender ?? '',
    objective: context.patient.objective ?? '',
    notes: context.patient.notes ?? '',
  })

  const mutation = useMutation({
    mutationFn: () => updateNutritionistPatient(context.patient.id, session, form),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  })

  return (
    <Card className="p-6" variant="glass">
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Nome completo"><Input value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} /></Field>
        <Field label="Telefone"><Input value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} /></Field>
        <Field label="Nascimento"><Input type="date" value={form.birth_date} onChange={(event) => setForm({ ...form, birth_date: event.target.value })} /></Field>
        <Field label="Genero"><Input value={form.gender} onChange={(event) => setForm({ ...form, gender: event.target.value })} /></Field>
        <Field label="Objetivo"><Input value={form.objective} onChange={(event) => setForm({ ...form, objective: event.target.value })} /></Field>
        <div className="md:col-span-2">
          <Field label="Historico e observacoes">
            <Textarea value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} />
          </Field>
        </div>
      </div>
      {mutation.error && <ErrorText>{mutation.error.message}</ErrorText>}
      <Button className="mt-4" disabled={mutation.isPending} onClick={() => mutation.mutate()} variant="premium">
        <Save size={18} />
        {mutation.isPending ? 'Salvando...' : 'Salvar perfil'}
      </Button>
    </Card>
  )
}

function DietsTab({
  context,
  queryKey,
}: {
  context: PatientContext
  queryKey: unknown[]
}) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState({
    title: '',
    description: '',
    calories: '',
    protein: '',
    carbs: '',
    fats: '',
    water_goal_ml: '',
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey })
  const createMutation = useMutation({
    mutationFn: () => createDiet({
      patient_id: context.patient.id,
      nutritionist_id: context.patient.nutritionist_id,
      title: form.title,
      description: form.description || null,
      calories: numberOrNull(form.calories),
      protein: numberOrNull(form.protein),
      carbs: numberOrNull(form.carbs),
      fats: numberOrNull(form.fats),
      water_goal_ml: numberOrNull(form.water_goal_ml),
      is_active: context.diets.length === 0,
    }),
    onSuccess: () => {
      setForm({ title: '', description: '', calories: '', protein: '', carbs: '', fats: '', water_goal_ml: '' })
      invalidate()
    },
  })

  return (
    <div className="grid gap-4 xl:grid-cols-[420px_1fr]">
      <Card className="p-5" variant="glass">
        <h2 className="font-black">Criar dieta</h2>
        <div className="mt-4 space-y-3">
          <Field label="Titulo"><Input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} /></Field>
          <Field label="Descricao"><Textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Calorias"><Input value={form.calories} onChange={(event) => setForm({ ...form, calories: event.target.value })} /></Field>
            <Field label="Agua ml"><Input value={form.water_goal_ml} onChange={(event) => setForm({ ...form, water_goal_ml: event.target.value })} /></Field>
            <Field label="Proteina"><Input value={form.protein} onChange={(event) => setForm({ ...form, protein: event.target.value })} /></Field>
            <Field label="Carbo"><Input value={form.carbs} onChange={(event) => setForm({ ...form, carbs: event.target.value })} /></Field>
            <Field label="Gordura"><Input value={form.fats} onChange={(event) => setForm({ ...form, fats: event.target.value })} /></Field>
          </div>
          {createMutation.error && <ErrorText>{createMutation.error.message}</ErrorText>}
          <Button disabled={!form.title || createMutation.isPending} onClick={() => createMutation.mutate()} variant="premium">
            <Plus size={18} />
            Criar dieta
          </Button>
        </div>
      </Card>

      <div className="space-y-4">
        {context.diets.length === 0 ? (
          <EmptyState description="Crie a primeira dieta para liberar visualizacao ao paciente e contexto da IA." icon={<Utensils size={22} />} title="Sem dietas" />
        ) : (
          context.diets.map((diet) => <DietCard diet={diet} key={diet.id} onChange={invalidate} />)
        )}
      </div>
    </div>
  )
}

function DietCard({ diet, onChange }: { diet: DietRecord; onChange: () => void }) {
  const [meal, setMeal] = useState({ meal_name: '', meal_time: '', foods: '', notes: '' })
  const mutation = useMutation({
    mutationFn: () => upsertDietMeals(diet.id, [{
      meal_name: meal.meal_name,
      meal_time: meal.meal_time || null,
      foods: meal.foods.split('\n').filter(Boolean).map((line) => {
        const [name, quantity] = line.split('|')
        return { name: name?.trim() || line.trim(), quantity: quantity?.trim() || '' }
      }),
      notes: meal.notes || null,
    }]),
    onSuccess: () => {
      setMeal({ meal_name: '', meal_time: '', foods: '', notes: '' })
      onChange()
    },
  })

  const deleteMutation = useMutation({ mutationFn: () => deleteDiet(diet.id), onSuccess: onChange })
  const duplicateMutation = useMutation({ mutationFn: () => duplicateDiet(diet), onSuccess: onChange })
  const toggleMutation = useMutation({ mutationFn: () => updateDiet(diet.id, { is_active: !diet.is_active }), onSuccess: onChange })

  return (
    <Card className="p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-black">{diet.title}</h2>
            {diet.is_active && <Badge tone="green">Ativa</Badge>}
          </div>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{diet.description || 'Sem descricao.'}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => toggleMutation.mutate()} size="sm" variant="secondary">{diet.is_active ? 'Desativar' : 'Ativar'}</Button>
          <Button onClick={() => duplicateMutation.mutate()} size="sm" variant="secondary">Duplicar</Button>
          <Button onClick={() => deleteMutation.mutate()} size="sm" variant="destructive"><Trash2 size={15} /></Button>
        </div>
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-5">
        <Mini label="Kcal" value={diet.calories ?? '-'} />
        <Mini label="P" value={diet.protein ?? '-'} />
        <Mini label="C" value={diet.carbs ?? '-'} />
        <Mini label="G" value={diet.fats ?? '-'} />
        <Mini label="Agua" value={diet.water_goal_ml ?? '-'} />
      </div>
      <div className="mt-5 space-y-3">
        <h3 className="font-bold">Refeicoes</h3>
        {(diet.meals ?? []).map((item) => (
          <div className="rounded-2xl border border-slate-200 p-3 text-sm dark:border-white/10" key={item.id}>
            <p className="font-bold">{item.meal_name} {item.meal_time && <span className="text-slate-400">- {item.meal_time}</span>}</p>
            <p className="mt-1 text-slate-500 dark:text-slate-400">{item.foods.map((food) => `${food.name} ${food.quantity}`).join(', ')}</p>
          </div>
        ))}
        <div className="grid gap-2 md:grid-cols-[1fr_130px]">
          <Input placeholder="Refeicao" value={meal.meal_name} onChange={(event) => setMeal({ ...meal, meal_name: event.target.value })} />
          <Input type="time" value={meal.meal_time} onChange={(event) => setMeal({ ...meal, meal_time: event.target.value })} />
          <Textarea className="md:col-span-2" placeholder="Alimentos: arroz | 120g, um por linha" value={meal.foods} onChange={(event) => setMeal({ ...meal, foods: event.target.value })} />
          <Button disabled={!meal.meal_name || mutation.isPending} onClick={() => mutation.mutate()} variant="secondary">Adicionar refeicao</Button>
        </div>
      </div>
    </Card>
  )
}

function WorkoutsTab({ context, queryKey }: { context: PatientContext; queryKey: unknown[] }) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState({ title: '', description: '', frequency_per_week: '' })
  const invalidate = () => queryClient.invalidateQueries({ queryKey })
  const createMutation = useMutation({
    mutationFn: () => createWorkout({
      patient_id: context.patient.id,
      nutritionist_id: context.patient.nutritionist_id,
      title: form.title,
      description: form.description || null,
      frequency_per_week: numberOrNull(form.frequency_per_week),
      is_active: context.workouts.length === 0,
    }),
    onSuccess: () => {
      setForm({ title: '', description: '', frequency_per_week: '' })
      invalidate()
    },
  })

  return (
    <div className="grid gap-4 xl:grid-cols-[420px_1fr]">
      <Card className="p-5" variant="glass">
        <h2 className="font-black">Criar treino</h2>
        <div className="mt-4 space-y-3">
          <Field label="Titulo"><Input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} /></Field>
          <Field label="Descricao"><Textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></Field>
          <Field label="Frequencia semanal"><Input value={form.frequency_per_week} onChange={(event) => setForm({ ...form, frequency_per_week: event.target.value })} /></Field>
          <Button disabled={!form.title || createMutation.isPending} onClick={() => createMutation.mutate()} variant="premium">Criar treino</Button>
        </div>
      </Card>
      <div className="space-y-4">
        {context.workouts.length === 0 ? (
          <EmptyState description="Crie o treino para o paciente visualizar e para a IA considerar o plano." icon={<Dumbbell size={22} />} title="Sem treinos" />
        ) : (
          context.workouts.map((workout) => <WorkoutCard key={workout.id} workout={workout} onChange={invalidate} />)
        )}
      </div>
    </div>
  )
}

function WorkoutCard({ workout, onChange }: { workout: WorkoutRecord; onChange: () => void }) {
  const [exercise, setExercise] = useState({ exercise_name: '', muscle_group: '', sets: '', reps: '', rest_time: '', notes: '' })
  const mutation = useMutation({
    mutationFn: () => upsertWorkoutExercises(workout.id, [{
      exercise_name: exercise.exercise_name,
      muscle_group: exercise.muscle_group || null,
      sets: numberOrNull(exercise.sets),
      reps: exercise.reps || null,
      rest_time: exercise.rest_time || null,
      notes: exercise.notes || null,
    }]),
    onSuccess: () => {
      setExercise({ exercise_name: '', muscle_group: '', sets: '', reps: '', rest_time: '', notes: '' })
      onChange()
    },
  })
  const deleteMutation = useMutation({ mutationFn: () => deleteWorkout(workout.id), onSuccess: onChange })
  const toggleMutation = useMutation({ mutationFn: () => updateWorkout(workout.id, { is_active: !workout.is_active }), onSuccess: onChange })

  return (
    <Card className="p-5">
      <div className="flex justify-between gap-3">
        <div>
          <h2 className="text-lg font-black">{workout.title}</h2>
          <p className="mt-1 text-sm text-slate-500">{workout.description || 'Sem descricao.'}</p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="secondary" onClick={() => toggleMutation.mutate()}>{workout.is_active ? 'Desativar' : 'Ativar'}</Button>
          <Button size="sm" variant="destructive" onClick={() => deleteMutation.mutate()}><Trash2 size={15} /></Button>
        </div>
      </div>
      <div className="mt-4 space-y-2">
        {(workout.exercises ?? []).map((item) => (
          <div className="rounded-2xl border border-slate-200 p-3 text-sm dark:border-white/10" key={item.id}>
            <p className="font-bold">{item.exercise_name}</p>
            <p className="text-slate-500">{item.sets} series - {item.reps} reps - descanso {item.rest_time}</p>
          </div>
        ))}
      </div>
      <div className="mt-4 grid gap-2 md:grid-cols-3">
        <Input placeholder="Exercicio" value={exercise.exercise_name} onChange={(event) => setExercise({ ...exercise, exercise_name: event.target.value })} />
        <Input placeholder="Grupo muscular" value={exercise.muscle_group} onChange={(event) => setExercise({ ...exercise, muscle_group: event.target.value })} />
        <Input placeholder="Series" value={exercise.sets} onChange={(event) => setExercise({ ...exercise, sets: event.target.value })} />
        <Input placeholder="Reps" value={exercise.reps} onChange={(event) => setExercise({ ...exercise, reps: event.target.value })} />
        <Input placeholder="Descanso" value={exercise.rest_time} onChange={(event) => setExercise({ ...exercise, rest_time: event.target.value })} />
        <Button disabled={!exercise.exercise_name || mutation.isPending} onClick={() => mutation.mutate()} variant="secondary">Adicionar</Button>
      </div>
    </Card>
  )
}

function MetricsTab({ context, queryKey }: { context: PatientContext; queryKey: unknown[] }) {
  const queryClient = useQueryClient()
  const chartData = useMemo(() => context.variable_metrics
    .filter((metric) => metric.name.toLowerCase().includes('peso'))
    .slice()
    .reverse()
    .map((metric) => ({
      date: new Date(metric.recorded_at || metric.created_at || '').toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }),
      value: Number(metric.value.replace(',', '.')) || 0,
    })), [context.variable_metrics])
  const [metric, setMetric] = useState({ name: 'peso', value: '', unit: 'kg' })
  const [main, setMain] = useState({ name: '', value: '', unit: '' })
  const invalidate = () => queryClient.invalidateQueries({ queryKey })
  const variableMutation = useMutation({ mutationFn: () => createVariableMetric({ patient_id: context.patient.id, ...metric }), onSuccess: invalidate })
  const mainMutation = useMutation({ mutationFn: () => createMainMetric({ patient_id: context.patient.id, defined_by: context.patient.nutritionist_id, ...main }), onSuccess: invalidate })

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
      <Card className="p-5">
        <h2 className="font-black">Evolucao de peso</h2>
        <div className="mt-4 h-80">
          <ResponsiveContainer height="100%" width="100%">
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Line dataKey="value" stroke="#10b981" strokeWidth={3} type="monotone" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>
      <Card className="p-5" variant="glass">
        <h2 className="font-black">Registrar metricas</h2>
        <div className="mt-4 space-y-3">
          <Input placeholder="Nome" value={metric.name} onChange={(event) => setMetric({ ...metric, name: event.target.value })} />
          <Input placeholder="Valor" value={metric.value} onChange={(event) => setMetric({ ...metric, value: event.target.value })} />
          <Input placeholder="Unidade" value={metric.unit} onChange={(event) => setMetric({ ...metric, unit: event.target.value })} />
          <Button disabled={!metric.name || !metric.value || variableMutation.isPending} onClick={() => variableMutation.mutate()} variant="premium">Adicionar variavel</Button>
        </div>
        <div className="mt-6 space-y-3">
          <Input placeholder="Metrica principal" value={main.name} onChange={(event) => setMain({ ...main, name: event.target.value })} />
          <Input placeholder="Valor" value={main.value} onChange={(event) => setMain({ ...main, value: event.target.value })} />
          <Input placeholder="Unidade" value={main.unit} onChange={(event) => setMain({ ...main, unit: event.target.value })} />
          <Button disabled={!main.name || !main.value || mainMutation.isPending} onClick={() => mainMutation.mutate()} variant="secondary">Adicionar principal</Button>
        </div>
      </Card>
      <Card className="p-5 xl:col-span-2">
        <h2 className="font-black">Historico temporal</h2>
        <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
          {context.variable_metrics.map((item) => (
            <div className="rounded-2xl border border-slate-200 p-3 text-sm dark:border-white/10" key={item.id}>
              <div className="flex justify-between gap-2">
                <p className="font-bold">{item.name}</p>
                <button onClick={() => deleteMetric('patient_variable_metrics', item.id).then(invalidate)} type="button"><Trash2 size={14} /></button>
              </div>
              <p className="mt-1 text-slate-500">{item.value} {item.unit}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}

function ConditionsTab({ context, queryKey }: { context: PatientContext; queryKey: unknown[] }) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<{ condition_type: HealthConditionRecord['condition_type']; title: string; description: string; severity: string }>({
    condition_type: 'observation',
    title: '',
    description: '',
    severity: '',
  })
  const invalidate = () => queryClient.invalidateQueries({ queryKey })
  const mutation = useMutation({ mutationFn: () => createHealthCondition({ patient_id: context.patient.id, ...form }), onSuccess: invalidate })

  return (
    <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
      <Card className="p-5" variant="glass">
        <h2 className="font-black">Nova condicao</h2>
        <div className="mt-4 space-y-3">
          <select className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm dark:border-white/10 dark:bg-slate-950" value={form.condition_type} onChange={(event) => setForm({ ...form, condition_type: event.target.value as HealthConditionRecord['condition_type'] })}>
            <option value="disease">Doenca</option>
            <option value="allergy">Alergia</option>
            <option value="food_restriction">Restricao alimentar</option>
            <option value="injury">Lesao</option>
            <option value="medication">Medicacao</option>
            <option value="intolerance">Intolerancia</option>
            <option value="observation">Observacao</option>
          </select>
          <Input placeholder="Titulo" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />
          <Textarea placeholder="Descricao" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
          <Input placeholder="Severidade" value={form.severity} onChange={(event) => setForm({ ...form, severity: event.target.value })} />
          <Button disabled={!form.title || !form.description || mutation.isPending} onClick={() => mutation.mutate()} variant="premium">Adicionar</Button>
        </div>
      </Card>
      <div className="grid gap-3 md:grid-cols-2">
        {context.conditions.map((condition) => (
          <Card className="p-4" key={condition.id}>
            <div className="flex justify-between gap-3">
              <div>
                <Badge tone="amber">{condition.condition_type}</Badge>
                <h3 className="mt-3 font-black">{condition.title}</h3>
                <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{condition.description}</p>
              </div>
              <button onClick={() => deleteHealthCondition(condition.id).then(invalidate)} type="button"><Trash2 size={16} /></button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}

function Field({ children, label }: { children: ReactNode; label: string }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-semibold text-slate-700 dark:text-slate-200">{label}</span>
      {children}
    </label>
  )
}

function Mini({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl bg-slate-50 p-3 text-sm dark:bg-white/[0.04]">
      <p className="text-xs font-black uppercase text-slate-400">{label}</p>
      <p className="mt-1 font-black">{value}</p>
    </div>
  )
}

function ErrorText({ children }: { children: ReactNode }) {
  return <p className="mt-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm font-semibold text-rose-700 dark:border-rose-400/20 dark:bg-rose-400/10 dark:text-rose-300">{children}</p>
}

function numberOrNull(value: string) {
  const normalized = value.replace(',', '.').trim()
  if (!normalized) return null
  const parsed = Number(normalized)
  return Number.isFinite(parsed) ? parsed : null
}
