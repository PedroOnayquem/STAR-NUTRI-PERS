import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import {
  Activity,
  AlertTriangle,
  Bot,
  CalendarDays,
  CalendarPlus,
  Dumbbell,
  ExternalLink,
  HeartPulse,
  Loader2,
  MapPin,
  Pencil,
  Plus,
  Save,
  Search,
  Trash2,
  Utensils,
  X,
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
import { AppDatePicker, AppSelect, AppTimePicker } from '../../components/ui/FormControls'
import { Input, Textarea } from '../../components/ui/Input'
import { SectionHeader } from '../../components/ui/SectionHeader'
import { PageSkeleton } from '../../components/ui/Skeleton'
import { StatCard } from '../../components/ui/StatCard'
import { ChatExperience } from '../../features/chat/components/ChatExperience'
import { useAuth } from '../../features/auth/useAuth'
import {
  createDiet,
  createHealthCondition,
  createPatientAppointment,
  createMainMetric,
  createVariableMetric,
  createWorkout,
  deleteDiet,
  deleteHealthCondition,
  deleteMetric,
  deletePatientAppointment,
  deleteWorkout,
  duplicateDiet,
  updateDiet,
  updatePatientAppointment,
  updateWorkout,
  upsertDietMeals,
  upsertWorkoutExercises,
} from '../../features/clinical/services/clinicalDataService'
import {
  calculateDietTotals,
  calculateFoodNutrients,
  calculateMealTotals,
  dietMealFoodFromTacoFood,
  formatNutrient,
  parseQuantityG,
} from '../../features/taco/nutrition'
import { createDietMealItem, searchTacoFoods } from '../../features/taco/services/tacoService'
import type { TacoFoodRecord } from '../../features/taco/types'
import {
  getPatientImportFileSignedUrls,
  getNutritionistPatientContext,
  updateNutritionistPatient,
} from '../../features/clinical/services/workspaceService'
import type {
  DietRecord,
  DietMealRecord,
  HealthConditionRecord,
  AppointmentStatus,
  AppointmentType,
  PatientContext,
  PatientAppointmentRecord,
  WorkoutRecord,
} from '../../features/clinical/types'
import { cn } from '../../lib/utils'

const tabs = [
  { id: 'overview', label: 'Resumo', icon: <HeartPulse size={16} /> },
  { id: 'profile', label: 'Perfil', icon: <Save size={16} /> },
  { id: 'diets', label: 'Dietas', icon: <Utensils size={16} /> },
  { id: 'workouts', label: 'Treinos', icon: <Dumbbell size={16} /> },
  { id: 'metrics', label: 'Métricas', icon: <Activity size={16} /> },
  { id: 'conditions', label: 'Condições', icon: <AlertTriangle size={16} /> },
  { id: 'agenda', label: 'Agenda', icon: <CalendarDays size={16} /> },
  { id: 'chat', label: 'Chat IA', icon: <Bot size={16} /> },
] as const

type TabId = (typeof tabs)[number]['id']

const healthConditionOptions: Array<{
  label: string
  value: HealthConditionRecord['condition_type']
}> = [
  { label: 'Doença', value: 'disease' },
  { label: 'Alergia', value: 'allergy' },
  { label: 'Restrição alimentar', value: 'food_restriction' },
  { label: 'Lesão', value: 'injury' },
  { label: 'Medicação', value: 'medication' },
  { label: 'Intolerância', value: 'intolerance' },
  { label: 'Observação', value: 'observation' },
]

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
        <StatCard caption="registros recentes" icon={<Activity size={20} />} label="Métricas" value={context.variable_metrics.length} />
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
      {activeTab === 'metrics' && <MetricsTab context={context} queryKey={queryKey} session={session} />}
      {activeTab === 'conditions' && <ConditionsTab context={context} queryKey={queryKey} />}
      {activeTab === 'agenda' && <AgendaTab context={context} queryKey={queryKey} />}
      {activeTab === 'chat' && (
        <ChatExperience
          externalQueryKey={queryKey}
          patientId={context.patient.id}
          patientName={context.profile?.full_name ?? undefined}
          scope="nutritionist"
        />
      )}
    </div>
  )
}

function OverviewTab({ context }: { context: PatientContext }) {
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_420px]">
      <Card className="p-5">
        <h2 className="font-black">Histórico e observações</h2>
        <p className="mt-3 text-sm leading-6 text-slate-600 dark:text-slate-300">
          {context.patient.notes || 'Sem observações cadastradas.'}
        </p>
      </Card>
      <Card className="p-5">
        <h2 className="font-black">Condições clínicas</h2>
        <div className="mt-4 space-y-2">
          {context.conditions.length === 0 ? (
            <p className="text-sm text-slate-500 dark:text-slate-400">Nenhuma condição cadastrada.</p>
          ) : (
            context.conditions.slice(0, 5).map((condition) => (
              <Badge key={condition.id} tone="amber">{conditionDisplayTitle(condition)}</Badge>
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
        <Field label="Nascimento"><AppDatePicker value={form.birth_date} onChange={(value) => setForm({ ...form, birth_date: value })} /></Field>
        <Field label="Gênero"><Input value={form.gender} onChange={(event) => setForm({ ...form, gender: event.target.value })} /></Field>
        <Field label="Objetivo"><Input value={form.objective} onChange={(event) => setForm({ ...form, objective: event.target.value })} /></Field>
        <div className="md:col-span-2">
          <Field label="Histórico e observações">
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
          <Field label="Título"><Input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} /></Field>
          <Field label="Descrição"><Textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Calorias"><Input value={form.calories} onChange={(event) => setForm({ ...form, calories: event.target.value })} /></Field>
            <Field label="Água ml"><Input value={form.water_goal_ml} onChange={(event) => setForm({ ...form, water_goal_ml: event.target.value })} /></Field>
            <Field label="Proteína"><Input value={form.protein} onChange={(event) => setForm({ ...form, protein: event.target.value })} /></Field>
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
          <EmptyState description="Crie a primeira dieta para liberar a visualização ao paciente." icon={<Utensils size={22} />} title="Nenhuma dieta cadastrada" />
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
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{diet.description || 'Sem descrição.'}</p>
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
        <Mini label="Água" value={diet.water_goal_ml ?? '-'} />
      </div>
      <div className="mt-5 space-y-3">
        <h3 className="font-bold">Refeições</h3>
        {(diet.meals ?? []).map((item) => (
          <div className="rounded-2xl border border-slate-200 p-3 text-sm dark:border-white/10" key={item.id}>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="font-bold">{item.meal_name} {item.meal_time && <span className="text-slate-400">- {item.meal_time}</span>}</p>
                <p className="mt-1 text-slate-500 dark:text-slate-400">
                  {(item.foods ?? []).length
                    ? item.foods.map((food) => `${food.name} ${food.quantity}`).join(', ')
                    : 'Sem alimentos cadastrados.'}
                </p>
              </div>
              <MealTotals meal={item} />
            </div>
            <TacoMealFoodAdder diet={diet} meal={item} onChange={onChange} />
          </div>
        ))}
        <div className="grid gap-2 md:grid-cols-[1fr_130px]">
          <Input placeholder="Refeição" value={meal.meal_name} onChange={(event) => setMeal({ ...meal, meal_name: event.target.value })} />
          <AppTimePicker value={meal.meal_time} onChange={(value) => setMeal({ ...meal, meal_time: value })} />
          <Textarea className="md:col-span-2" placeholder="Alimentos: arroz | 120g, um por linha" value={meal.foods} onChange={(event) => setMeal({ ...meal, foods: event.target.value })} />
          <Button disabled={!meal.meal_name || mutation.isPending} onClick={() => mutation.mutate()} variant="secondary">Adicionar refeição</Button>
        </div>
      </div>
    </Card>
  )
}

function MealTotals({ meal }: { meal: DietMealRecord }) {
  const totals = calculateMealTotals(meal)
  if (!Object.values(totals).some((value) => value > 0)) return null

  return (
    <div className="grid min-w-[220px] grid-cols-3 gap-1 text-xs">
      <span className="rounded-lg bg-emerald-50 px-2 py-1 font-bold text-emerald-700 dark:bg-emerald-400/10 dark:text-emerald-200">
        {formatNutrient(totals.energy_kcal, 'kcal')}
      </span>
      <span className="rounded-lg bg-slate-100 px-2 py-1 text-slate-600 dark:bg-white/5 dark:text-slate-300">
        P {formatNutrient(totals.protein_g, 'g')}
      </span>
      <span className="rounded-lg bg-slate-100 px-2 py-1 text-slate-600 dark:bg-white/5 dark:text-slate-300">
        C {formatNutrient(totals.carbohydrate_g, 'g')}
      </span>
    </div>
  )
}

function TacoMealFoodAdder({
  diet,
  meal,
  onChange,
}: {
  diet: DietRecord
  meal: DietMealRecord
  onChange: () => void
}) {
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [quantity, setQuantity] = useState('100')
  const [selectedFood, setSelectedFood] = useState<TacoFoodRecord | null>(null)

  useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedQuery(query.trim()), 240)
    return () => window.clearTimeout(timeout)
  }, [query])

  const foodsQuery = useQuery({
    queryKey: ['taco-meal-search', meal.id, debouncedQuery],
    queryFn: () => searchTacoFoods({
      page: 1,
      pageSize: 6,
      query: debouncedQuery,
    }),
    enabled: debouncedQuery.length >= 2,
  })

  const mutation = useMutation({
    mutationFn: async () => {
      const quantityG = parseQuantityG(quantity)
      if (!selectedFood || !quantityG) {
        throw new Error('Selecione um alimento e informe a quantidade em gramas.')
      }

      const nutrients = calculateFoodNutrients(selectedFood, quantityG)
      const createdItem = await createDietMealItem({
        carbohydrate_g: nutrients.carbohydrate_g,
        energy_kcal: nutrients.energy_kcal,
        fiber_g: nutrients.fiber_g,
        lipid_g: nutrients.lipid_g,
        meal_id: meal.id,
        protein_g: nutrients.protein_g,
        quantity_g: quantityG,
        sodium_mg: nutrients.sodium_mg,
        taco_food_id: selectedFood.id,
      })
      const nextFood = dietMealFoodFromTacoFood(selectedFood, quantityG)
      const nextFoods = [...(meal.foods ?? []), nextFood]
      await upsertDietMeals(diet.id, [{
        id: meal.id,
        meal_name: meal.meal_name,
        meal_time: meal.meal_time,
        foods: nextFoods,
        notes: meal.notes,
      }])

      const nextMeals = (diet.meals ?? []).map((item) =>
        item.id === meal.id
          ? {
              ...item,
              foods: nextFoods,
              items: [...(item.items ?? []), createdItem],
            }
          : item,
      )
      const totals = calculateDietTotals(nextMeals)
      await updateDiet(diet.id, {
        calories: Math.round(totals.energy_kcal),
        carbs: totals.carbohydrate_g,
        fats: totals.lipid_g,
        protein: totals.protein_g,
      })
    },
    onSuccess: () => {
      setQuery('')
      setDebouncedQuery('')
      setSelectedFood(null)
      setQuantity('100')
      onChange()
    },
  })

  const results = foodsQuery.data?.foods ?? []

  return (
    <div className="mt-3 rounded-xl border border-dashed border-slate-200 bg-slate-50/70 p-3 dark:border-white/10 dark:bg-white/[0.03]">
      <div className="grid gap-2 lg:grid-cols-[minmax(0,1fr)_120px_auto]">
        <label className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
          <Input
            className="pl-9"
            onChange={(event) => {
              setQuery(event.target.value)
              setSelectedFood(null)
            }}
            placeholder="Buscar alimento TACO"
            value={selectedFood ? selectedFood.name : query}
          />
        </label>
        <Input
          inputMode="decimal"
          onChange={(event) => setQuantity(event.target.value)}
          placeholder="g"
          value={quantity}
        />
        <Button
          disabled={!selectedFood || mutation.isPending}
          onClick={() => mutation.mutate()}
          type="button"
          variant="secondary"
        >
          {mutation.isPending ? <Loader2 className="animate-spin" size={16} /> : <Plus size={16} />}
          TACO
        </Button>
      </div>

      {!selectedFood && debouncedQuery.length >= 2 && (
        <div className="mt-2 overflow-hidden rounded-xl border border-slate-200 bg-white dark:border-white/10 dark:bg-slate-950/80">
          {foodsQuery.isLoading ? (
            <div className="flex items-center gap-2 px-3 py-2 text-xs text-slate-500">
              <Loader2 className="animate-spin" size={14} />
              Buscando
            </div>
          ) : results.length === 0 ? (
            <div className="px-3 py-2 text-xs text-slate-500">Nenhum alimento encontrado.</div>
          ) : (
            results.map((food) => (
              <button
                className="flex w-full items-center justify-between gap-3 border-t border-slate-100 px-3 py-2 text-left text-xs first:border-t-0 hover:bg-emerald-50 dark:border-white/5 dark:hover:bg-emerald-400/10"
                key={food.id}
                onClick={() => {
                  setSelectedFood(food)
                  setQuery(food.name)
                }}
                type="button"
              >
                <span className="min-w-0">
                  <span className="block truncate font-bold">{food.name}</span>
                  <span className="block truncate text-slate-500">{food.category || 'Sem categoria'}</span>
                </span>
                <span className="shrink-0 font-bold text-emerald-600 dark:text-emerald-300">
                  {formatNutrient(food.energy_kcal, 'kcal')}
                </span>
              </button>
            ))
          )}
        </div>
      )}

      {mutation.error && <ErrorText>{mutation.error.message}</ErrorText>}
    </div>
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
          <Field label="Título"><Input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} /></Field>
          <Field label="Descrição"><Textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></Field>
          <Field label="Frequência semanal"><Input value={form.frequency_per_week} onChange={(event) => setForm({ ...form, frequency_per_week: event.target.value })} /></Field>
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
          <p className="mt-1 text-sm text-slate-500">{workout.description || 'Sem descrição.'}</p>
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
            <p className="text-slate-500">{item.sets} séries - {item.reps} reps - descanso {item.rest_time}</p>
          </div>
        ))}
      </div>
      <div className="mt-4 grid gap-2 md:grid-cols-3">
        <Input placeholder="Exercício" value={exercise.exercise_name} onChange={(event) => setExercise({ ...exercise, exercise_name: event.target.value })} />
        <Input placeholder="Grupo muscular" value={exercise.muscle_group} onChange={(event) => setExercise({ ...exercise, muscle_group: event.target.value })} />
        <Input placeholder="Séries" value={exercise.sets} onChange={(event) => setExercise({ ...exercise, sets: event.target.value })} />
        <Input placeholder="Reps" value={exercise.reps} onChange={(event) => setExercise({ ...exercise, reps: event.target.value })} />
        <Input placeholder="Descanso" value={exercise.rest_time} onChange={(event) => setExercise({ ...exercise, rest_time: event.target.value })} />
        <Button disabled={!exercise.exercise_name || mutation.isPending} onClick={() => mutation.mutate()} variant="secondary">Adicionar</Button>
      </div>
    </Card>
  )
}

function MetricsTab({
  context,
  queryKey,
  session,
}: {
  context: PatientContext
  queryKey: unknown[]
  session: ReturnType<typeof useAuth>['session']
}) {
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
  const importById = useMemo(
    () => new Map((context.imports ?? []).map((item) => [item.id, item])),
    [context.imports],
  )
  const openImportFileMutation = useMutation({
    mutationFn: (importId: string) => getPatientImportFileSignedUrls(importId, session),
    onSuccess: (data) => {
      data.files
        .filter((file) => file.signed_url)
        .forEach((file) => window.open(file.signed_url!, '_blank', 'noopener,noreferrer'))
    },
  })

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
      <Card className="p-5">
        <h2 className="font-black">Evolução de peso</h2>
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
        <h2 className="font-black">Registrar métricas</h2>
        <div className="mt-4 space-y-3">
          <Input placeholder="Nome" value={metric.name} onChange={(event) => setMetric({ ...metric, name: event.target.value })} />
          <Input placeholder="Valor" value={metric.value} onChange={(event) => setMetric({ ...metric, value: event.target.value })} />
          <Input placeholder="Unidade" value={metric.unit} onChange={(event) => setMetric({ ...metric, unit: event.target.value })} />
          <Button disabled={!metric.name || !metric.value || variableMutation.isPending} onClick={() => variableMutation.mutate()} variant="premium">Adicionar variável</Button>
        </div>
        <div className="mt-6 space-y-3">
          <Input placeholder="Métrica principal" value={main.name} onChange={(event) => setMain({ ...main, name: event.target.value })} />
          <Input placeholder="Valor" value={main.value} onChange={(event) => setMain({ ...main, value: event.target.value })} />
          <Input placeholder="Unidade" value={main.unit} onChange={(event) => setMain({ ...main, unit: event.target.value })} />
          <Button disabled={!main.name || !main.value || mainMutation.isPending} onClick={() => mainMutation.mutate()} variant="secondary">Adicionar principal</Button>
        </div>
      </Card>
      <Card className="p-5 xl:col-span-2">
        <h2 className="font-black">Histórico temporal</h2>
        <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
          {context.variable_metrics.map((item) => {
            const sourceImport = item.source_import_id ? importById.get(item.source_import_id) : null
            const importFiles = sourceImport?.files ?? []
            const fileCount = importFiles.length || (sourceImport?.file_url || sourceImport?.file_path ? 1 : 0)

            return (
              <div className="rounded-2xl border border-slate-200 p-3 text-sm dark:border-white/10" key={item.id}>
                <div className="flex justify-between gap-2">
                  <p className="font-bold">{item.name}</p>
                  <button onClick={() => deleteMetric('patient_variable_metrics', item.id).then(invalidate)} type="button"><Trash2 size={14} /></button>
                </div>
                <p className="mt-1 text-slate-500">{item.value} {item.unit}</p>
                {isBioimpedanceSource(item.source_type) && (
                  <div className="mt-3 rounded-xl border border-cyan-300/15 bg-cyan-400/5 p-2 text-xs text-cyan-100">
                    <p className="font-black">Importada de relatório de bioimpedância</p>
                    <p className="mt-1 text-cyan-100/70">
                      Medição: {new Date(item.recorded_at || item.created_at || '').toLocaleString('pt-BR')}
                    </p>
                    {sourceImport?.created_at && (
                      <p className="mt-1 text-cyan-100/70">
                        Importação: {new Date(sourceImport.created_at).toLocaleDateString('pt-BR')}
                      </p>
                    )}
                    {fileCount > 0 && (
                      <p className="mt-1 text-cyan-100/70">
                        Arquivos: {fileCount}
                      </p>
                    )}
                    {item.source_import_id && fileCount > 0 && (
                      <button
                        className="mt-2 inline-flex items-center gap-1 font-bold text-cyan-200 hover:text-cyan-100"
                        disabled={openImportFileMutation.isPending}
                        onClick={() => openImportFileMutation.mutate(item.source_import_id!)}
                        type="button"
                      >
                        <ExternalLink size={13} />
                        Ver arquivos originais
                      </button>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </Card>
    </div>
  )
}

function ConditionsTab({ context, queryKey }: { context: PatientContext; queryKey: unknown[] }) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<{
    condition_type: HealthConditionRecord['condition_type']
    description: string
    injury_local: string
    severity: string
    title: string
  }>({
    condition_type: 'observation',
    injury_local: '',
    title: '',
    description: '',
    severity: '',
  })
  const invalidate = () => queryClient.invalidateQueries({ queryKey })
  const mutation = useMutation({
    mutationFn: () => createHealthCondition({
      patient_id: context.patient.id,
      condition_type: form.condition_type,
      description: form.description,
      injury_local: form.condition_type === 'injury' ? nullable(form.injury_local) : null,
      severity: nullable(form.severity),
      title: form.condition_type === 'injury' && form.injury_local.trim()
        ? `Lesão - ${form.injury_local.trim()}`
        : form.title,
    }),
    onSuccess: invalidate,
  })

  return (
    <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
      <Card className="p-5" variant="glass">
        <h2 className="font-black">Nova condição</h2>
        <div className="mt-4 space-y-3">
          <AppSelect
            onChange={(value) => setForm({ ...form, condition_type: value })}
            options={healthConditionOptions}
            value={form.condition_type}
          />
          {form.condition_type === 'injury' && (
            <Input placeholder="Local da lesão" value={form.injury_local} onChange={(event) => setForm({ ...form, injury_local: event.target.value })} />
          )}
          <Input placeholder="Título" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />
          <Textarea placeholder="Descrição" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
          <Input placeholder="Severidade" value={form.severity} onChange={(event) => setForm({ ...form, severity: event.target.value })} />
          <Button disabled={!(form.title || form.injury_local) || !form.description || mutation.isPending} onClick={() => mutation.mutate()} variant="premium">Adicionar</Button>
        </div>
      </Card>
      <div className="grid gap-3 md:grid-cols-2">
        {context.conditions.map((condition) => (
          <Card className="p-4" key={condition.id}>
            <div className="flex justify-between gap-3">
              <div>
                <Badge tone="amber">{conditionTypeLabel(condition.condition_type)}</Badge>
                <h3 className="mt-3 font-black">{conditionDisplayTitle(condition)}</h3>
                <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{condition.description}</p>
                <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400">
                  {condition.severity && <span>Gravidade: {condition.severity}</span>}
                  {condition.started_at && <span>Início: {formatDate(condition.started_at)}</span>}
                  {condition.origin && <span>Origem: {condition.origin}</span>}
                </div>
                {condition.notes && (
                  <p className="mt-2 text-xs leading-5 text-slate-500 dark:text-slate-400">
                    Obs.: {condition.notes}
                  </p>
                )}
                {condition.recommendations && (
                  <p className="mt-2 text-xs leading-5 text-slate-500 dark:text-slate-400">
                    Recomendações: {condition.recommendations}
                  </p>
                )}
              </div>
              <button onClick={() => deleteHealthCondition(condition.id).then(invalidate)} type="button"><Trash2 size={16} /></button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}

const appointmentTypes: Array<{ label: string; value: AppointmentType }> = [
  { label: 'Acompanhamento', value: 'acompanhamento' },
  { label: 'Consulta', value: 'consulta' },
  { label: 'Reunião', value: 'reuniao' },
  { label: 'Avaliação', value: 'avaliacao' },
  { label: 'Retorno', value: 'retorno' },
  { label: 'Revisão de dieta', value: 'revisao_dieta' },
  { label: 'Revisão de treino', value: 'revisao_treino' },
  { label: 'Outro', value: 'outro' },
]

const appointmentStatuses: Array<{ label: string; value: AppointmentStatus }> = [
  { label: 'Agendado', value: 'agendado' },
  { label: 'Confirmado', value: 'confirmado' },
  { label: 'Concluído', value: 'concluido' },
  { label: 'Cancelado', value: 'cancelado' },
  { label: 'Faltou', value: 'faltou' },
]

type AppointmentForm = {
  title: string
  type: AppointmentType
  description: string
  date: string
  start_time: string
  end_time: string
  location: string
  meeting_link: string
  status: AppointmentStatus
  notes: string
}

function AgendaTab({
  context,
  queryKey,
}: {
  context: PatientContext
  queryKey: unknown[]
}) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState<PatientAppointmentRecord | null>(null)
  const [isOpen, setIsOpen] = useState(false)
  const [notice, setNotice] = useState<{ tone: 'green' | 'red'; text: string } | null>(null)

  const appointments = context.appointments ?? []
  const today = new Date().toISOString().slice(0, 10)
  const future = appointments
    .filter((appointment) => appointment.date >= today && appointment.status !== 'cancelado')
    .sort(sortAppointmentsAsc)
  const history = appointments
    .filter((appointment) => appointment.date < today || appointment.status === 'cancelado')
    .sort(sortAppointmentsDesc)

  function showNotice(tone: 'green' | 'red', text: string) {
    setNotice({ tone, text })
    window.setTimeout(() => setNotice(null), 3200)
  }

  function invalidate() {
    queryClient.invalidateQueries({ queryKey })
  }

  return (
    <div className="space-y-4">
      {notice && (
        <div
          className={cn(
            'fixed right-4 top-20 z-50 rounded-2xl border px-4 py-3 text-sm font-semibold shadow-xl backdrop-blur',
            notice.tone === 'green'
              ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-300'
              : 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-400/20 dark:bg-rose-400/10 dark:text-rose-300',
          )}
          role="status"
        >
          {notice.text}
        </div>
      )}

      <Card className="p-5" variant="glass">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-lg font-black">Agenda do paciente</h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Acompanhamentos, reunioes e compromissos vinculados ao paciente.
            </p>
          </div>
          <Button
            onClick={() => {
              setEditing(null)
              setIsOpen(true)
            }}
            variant="premium"
          >
            <CalendarPlus size={18} />
            Novo agendamento
          </Button>
        </div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        <AppointmentList
          appointments={future}
          emptyDescription="Novos acompanhamentos apareceráo aqui depois de agendados."
          emptyTitle="Nenhum compromisso futuro"
          onCancel={(appointment) =>
            updatePatientAppointment(appointment.id, { status: 'cancelado' })
              .then(() => {
                showNotice('green', 'Agendamento cancelado.')
                invalidate()
              })
              .catch((error: Error) => showNotice('red', error.message))
          }
          onDelete={(appointment) =>
            deletePatientAppointment(appointment.id)
              .then(() => {
                showNotice('green', 'Agendamento removido.')
                invalidate()
              })
              .catch((error: Error) => showNotice('red', error.message))
          }
          onEdit={(appointment) => {
            setEditing(appointment)
            setIsOpen(true)
          }}
          title="Compromissos futuros"
        />

        <AppointmentList
          appointments={history}
          emptyDescription="Compromissos concluídos, cancelados ou vencidos ficam registrados aqui."
          emptyTitle="Sem histórico"
          onCancel={(appointment) =>
            updatePatientAppointment(appointment.id, { status: 'cancelado' })
              .then(() => {
                showNotice('green', 'Agendamento cancelado.')
                invalidate()
              })
              .catch((error: Error) => showNotice('red', error.message))
          }
          onDelete={(appointment) =>
            deletePatientAppointment(appointment.id)
              .then(() => {
                showNotice('green', 'Agendamento removido.')
                invalidate()
              })
              .catch((error: Error) => showNotice('red', error.message))
          }
          onEdit={(appointment) => {
            setEditing(appointment)
            setIsOpen(true)
          }}
          title="Histórico"
        />
      </div>

      {isOpen && (
        <AppointmentModal
          appointment={editing}
          context={context}
          onClose={() => setIsOpen(false)}
          onError={(message) => showNotice('red', message)}
          onSuccess={(message) => {
            showNotice('green', message)
            setIsOpen(false)
            invalidate()
          }}
        />
      )}
    </div>
  )
}

function AppointmentList({
  appointments,
  emptyDescription,
  emptyTitle,
  onCancel,
  onDelete,
  onEdit,
  title,
}: {
  appointments: PatientAppointmentRecord[]
  emptyDescription: string
  emptyTitle: string
  onCancel: (appointment: PatientAppointmentRecord) => void
  onDelete: (appointment: PatientAppointmentRecord) => void
  onEdit: (appointment: PatientAppointmentRecord) => void
  title: string
}) {
  return (
    <Card className="overflow-hidden p-0">
      <div className="border-b border-slate-200/80 p-5 dark:border-white/10">
        <h3 className="font-black">{title}</h3>
      </div>
      {appointments.length === 0 ? (
        <div className="p-5">
          <EmptyState
            className="min-h-64"
            description={emptyDescription}
            icon={<CalendarDays size={22} />}
            title={emptyTitle}
          />
        </div>
      ) : (
        <div className="divide-y divide-slate-100 dark:divide-white/10">
          {appointments.map((appointment) => (
            <AppointmentCard
              appointment={appointment}
              key={appointment.id}
              onCancel={onCancel}
              onDelete={onDelete}
              onEdit={onEdit}
            />
          ))}
        </div>
      )}
    </Card>
  )
}

function AppointmentCard({
  appointment,
  onCancel,
  onDelete,
  onEdit,
}: {
  appointment: PatientAppointmentRecord
  onCancel: (appointment: PatientAppointmentRecord) => void
  onDelete: (appointment: PatientAppointmentRecord) => void
  onEdit: (appointment: PatientAppointmentRecord) => void
}) {
  return (
    <div className="p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="font-black">{appointment.title}</h4>
            <Badge tone="blue">{appointmentTypeLabel(appointment.type)}</Badge>
            <Badge tone={appointmentStatusTone(appointment.status)}>
              {appointmentStatusLabel(appointment.status)}
            </Badge>
          </div>
          <p className="mt-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
            {formatDate(appointment.date)} · {formatTime(appointment.start_time)}
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
                  Reunião online
                </a>
              )}
            </div>
          )}
          {(appointment.description || appointment.notes) && (
            <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-500 dark:text-slate-400">
              {appointment.description || appointment.notes}
            </p>
          )}
        </div>
        <div className="flex shrink-0 gap-2">
          <Button onClick={() => onEdit(appointment)} size="icon" title="Editar" variant="secondary">
            <Pencil size={16} />
          </Button>
          {appointment.status !== 'cancelado' && (
            <Button onClick={() => onCancel(appointment)} size="icon" title="Cancelar" variant="secondary">
              <X size={16} />
            </Button>
          )}
          <Button onClick={() => onDelete(appointment)} size="icon" title="Remover" variant="destructive">
            <Trash2 size={16} />
          </Button>
        </div>
      </div>
    </div>
  )
}

function AppointmentModal({
  appointment,
  context,
  onClose,
  onError,
  onSuccess,
}: {
  appointment: PatientAppointmentRecord | null
  context: PatientContext
  onClose: () => void
  onError: (message: string) => void
  onSuccess: (message: string) => void
}) {
  const [form, setForm] = useState<AppointmentForm>(() => ({
    title: appointment?.title ?? '',
    type: appointment?.type ?? 'acompanhamento',
    description: appointment?.description ?? '',
    date: appointment?.date ?? new Date().toISOString().slice(0, 10),
    start_time: appointment?.start_time?.slice(0, 5) ?? '',
    end_time: appointment?.end_time?.slice(0, 5) ?? '',
    location: appointment?.location ?? '',
    meeting_link: appointment?.meeting_link ?? '',
    status: appointment?.status ?? 'agendado',
    notes: appointment?.notes ?? '',
  }))
  const [validationError, setValidationError] = useState('')

  const mutation = useMutation({
    mutationFn: () => {
      const error = validateAppointmentForm(form)
      if (error) {
        setValidationError(error)
        throw new Error(error)
      }
      setValidationError('')

      const payload = {
        title: form.title.trim(),
        type: form.type,
        description: nullable(form.description),
        date: form.date,
        start_time: form.start_time,
        end_time: nullable(form.end_time),
        location: nullable(form.location),
        meeting_link: nullable(form.meeting_link),
        status: form.status,
        notes: nullable(form.notes),
      }

      if (appointment) {
        return updatePatientAppointment(appointment.id, payload)
      }

      return createPatientAppointment({
        ...payload,
        patient_id: context.patient.id,
        nutritionist_id: context.patient.nutritionist_id,
      })
    },
    onError: (error) => onError(error.message),
    onSuccess: () =>
      onSuccess(appointment ? 'Agendamento atualizado.' : 'Agendamento criado.'),
  })

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-slate-950/60 p-3 backdrop-blur-sm">
      <div className="flex h-full w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-white/10 bg-white shadow-2xl dark:bg-slate-950">
        <div className="flex items-center justify-between border-b border-slate-200/80 p-5 dark:border-white/10">
          <div>
            <h3 className="text-lg font-black">
              {appointment ? 'Editar agendamento' : 'Novo agendamento'}
            </h3>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Defina data, horário e detalhes do compromisso.
            </p>
          </div>
          <Button onClick={onClose} size="icon" type="button" variant="ghost">
            <X size={18} />
          </Button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Título">
              <Input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />
            </Field>
            <Field label="Tipo">
              <AppSelect
                onChange={(value) => setForm({ ...form, type: value })}
                options={appointmentTypes}
                value={form.type}
              />
            </Field>
            <Field label="Data">
              <AppDatePicker
                value={form.date}
                onChange={(value) => setForm({ ...form, date: value })}
              />
            </Field>
            <Field label="Status">
              <AppSelect
                onChange={(value) => setForm({ ...form, status: value })}
                options={appointmentStatuses}
                value={form.status}
              />
            </Field>
            <Field label="Horário inicial">
              <AppTimePicker
                intervalMinutes={15}
                value={form.start_time}
                onChange={(value) => setForm({ ...form, start_time: value })}
              />
            </Field>
            <Field label="Horário final">
              <AppTimePicker
                intervalMinutes={15}
                placeholder="Opcional"
                value={form.end_time}
                onChange={(value) => setForm({ ...form, end_time: value })}
              />
            </Field>
            <Field label="Local">
              <Input value={form.location} onChange={(event) => setForm({ ...form, location: event.target.value })} />
            </Field>
            <Field label="Link da reunião">
              <Input value={form.meeting_link} onChange={(event) => setForm({ ...form, meeting_link: event.target.value })} />
            </Field>
            <div className="md:col-span-2">
              <Field label="Descrição">
                <Textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
              </Field>
            </div>
            <div className="md:col-span-2">
              <Field label="Observações">
                <Textarea value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} />
              </Field>
            </div>
          </div>
          {validationError && <ErrorText>{validationError}</ErrorText>}
        </div>

        <div className="flex flex-col-reverse gap-2 border-t border-slate-200/80 p-5 dark:border-white/10 sm:flex-row sm:justify-end">
          <Button disabled={mutation.isPending} onClick={onClose} type="button" variant="secondary">
            Cancelar
          </Button>
          <Button disabled={mutation.isPending} onClick={() => mutation.mutate()} type="button" variant="premium">
            {mutation.isPending ? 'Salvando...' : appointment ? 'Salvar alterações' : 'Criar agendamento'}
          </Button>
        </div>
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

function conditionTypeLabel(type: HealthConditionRecord['condition_type']) {
  const labels: Record<HealthConditionRecord['condition_type'], string> = {
    allergy: 'Alergia',
    disease: 'Doença',
    food_restriction: 'Restrição alimentar',
    injury: 'Lesão',
    intolerance: 'Intolerância',
    medication: 'Medicação',
    observation: 'Observação',
  }
  return labels[type]
}

function conditionDisplayTitle(condition: HealthConditionRecord) {
  if (condition.condition_type === 'injury') {
    return condition.injury_local
      ? `Lesão - ${condition.injury_local}`
      : condition.title
  }
  return condition.title
}

function formatDate(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString('pt-BR')
}

function formatTime(value: string) {
  return value.slice(0, 5)
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
  return appointmentTypes.find((item) => item.value === type)?.label ?? 'Outro'
}

function appointmentStatusLabel(status: AppointmentStatus) {
  return appointmentStatuses.find((item) => item.value === status)?.label ?? status
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

function isBioimpedanceSource(sourceType?: string | null) {
  return sourceType === 'bioimpedance_report' || sourceType === 'bioimpedance_pdf'
}

function validateAppointmentForm(form: AppointmentForm) {
  if (form.title.trim().length < 3) {
    return 'Informe um título com pelo menos 3 caracteres.'
  }

  if (!form.date) {
    return 'Informe a data do compromisso.'
  }

  if (!form.start_time) {
    return 'Informe o horário inicial.'
  }

  if (form.end_time && form.end_time <= form.start_time) {
    return 'O horário final deve ser depois do horário inicial.'
  }

  if (form.meeting_link.trim() && !/^https?:\/\//i.test(form.meeting_link.trim())) {
    return 'O link da reunião deve começar com http:// ou https://.'
  }

  return ''
}

function nullable(value: string) {
  const trimmed = value.trim()
  return trimmed ? trimmed : null
}

function numberOrNull(value: string) {
  const normalized = value.replace(',', '.').trim()
  if (!normalized) return null
  const parsed = Number(normalized)
  return Number.isFinite(parsed) ? parsed : null
}
