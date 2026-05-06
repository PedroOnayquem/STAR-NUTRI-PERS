import {
  Activity,
  Bot,
  CheckCircle2,
  Plus,
  Search,
  ShieldCheck,
  Users,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { ChatBox } from './components/chat/ChatBox'
import { AppShell } from './components/layout/AppShell'
import { DietPanel } from './components/patient/DietPanel'
import { PatientSummary } from './components/patient/PatientSummary'
import { WorkoutPanel } from './components/patient/WorkoutPanel'
import { Badge } from './components/ui/Badge'
import { Button } from './components/ui/Button'
import { Card } from './components/ui/Card'
import { Input, Textarea } from './components/ui/Input'
import { StatCard } from './components/ui/StatCard'
import { initialData } from './data/mockData'
import type {
  AppData,
  Diet,
  Patient,
  PatientMetric,
  Profile,
  UserRole,
  Workout,
} from './types'

const defaultProfile = initialData.profiles[1]

function App() {
  const [data, setData] = useState<AppData>(initialData)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [activeView, setActiveView] = useState('dashboard')
  const [selectedPatientId, setSelectedPatientId] = useState('patient-1')
  const [isDark, setIsDark] = useState(false)

  function loginAs(role: UserRole) {
    const nextProfile =
      data.profiles.find((item) => item.role === role) ?? defaultProfile
    setProfile(nextProfile)
    setActiveView(role === 'patient' ? 'patient-home' : role === 'admin' ? 'admin' : 'dashboard')
  }

  function toggleTheme() {
    setIsDark((current) => {
      document.documentElement.classList.toggle('dark', !current)
      return !current
    })
  }

  if (!profile) {
    return <LoginPage onLogin={loginAs} isDark={isDark} onToggleTheme={toggleTheme} />
  }

  const patient =
    profile.role === 'patient'
      ? data.patients.find((item) => item.userId === profile.id) ?? data.patients[0]
      : data.patients.find((item) => item.id === selectedPatientId) ?? data.patients[0]

  return (
    <AppShell
      activeView={activeView}
      isDark={isDark}
      onLogout={() => setProfile(null)}
      onNavigate={setActiveView}
      onToggleTheme={toggleTheme}
      profile={profile}
    >
      {profile.role === 'admin' && (
        <AdminDashboard data={data} onLoginAs={loginAs} />
      )}

      {profile.role === 'nutritionist' && (
        <NutritionistArea
          activeView={activeView}
          data={data}
          onCreateDiet={(diet) =>
            setData((current) => ({ ...current, diets: [diet, ...current.diets] }))
          }
          onCreatePatient={(newPatient) =>
            setData((current) => ({
              ...current,
              patients: [newPatient, ...current.patients],
            }))
          }
          onCreateWorkout={(workout) =>
            setData((current) => ({
              ...current,
              workouts: [workout, ...current.workouts],
            }))
          }
          onSelectPatient={(id) => {
            setSelectedPatientId(id)
            setActiveView('patients')
          }}
          onUpdateData={setData}
          patient={patient}
          selectedPatientId={selectedPatientId}
        />
      )}

      {profile.role === 'patient' && (
        <PatientArea
          activeView={activeView}
          data={data}
          onUpdateData={setData}
          patient={patient}
        />
      )}
    </AppShell>
  )
}

function LoginPage({
  onLogin,
  isDark,
  onToggleTheme,
}: {
  onLogin: (role: UserRole) => void
  isDark: boolean
  onToggleTheme: () => void
}) {
  const [role, setRole] = useState<UserRole>('nutritionist')

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950 dark:bg-slate-950 dark:text-white">
      <div className="grid min-h-screen lg:grid-cols-[0.95fr_1.05fr]">
        <section className="flex flex-col justify-between bg-slate-950 px-6 py-8 text-white sm:px-10">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500 text-sm font-black">
                SN
              </div>
              <div>
                <p className="font-black">Star Nutri</p>
                <p className="text-xs text-slate-300">SaaS nutricional com IA</p>
              </div>
            </div>
            <Button onClick={onToggleTheme} type="button" variant="secondary">
              {isDark ? 'Claro' : 'Escuro'}
            </Button>
          </div>

          <div className="my-16 max-w-xl">
            <Badge tone="green">GLM 5.0 ready</Badge>
            <h1 className="mt-6 text-4xl font-black leading-tight sm:text-6xl">
              Gestao nutricional com IA, dados clinicos e acompanhamento real.
            </h1>
            <p className="mt-6 text-lg leading-8 text-slate-300">
              Nutricionistas organizam pacientes, dietas, treinos, metricas e
              individualidades. Pacientes acompanham o plano e conversam com uma
              IA limitada ao protocolo definido.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            {['Supabase Auth', 'RLS preparado', 'Contexto clinico'].map((item) => (
              <div className="rounded-lg bg-white/10 p-4" key={item}>
                <CheckCircle2 className="text-emerald-300" size={18} />
                <p className="mt-3 text-sm font-bold">{item}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="flex items-center justify-center px-6 py-10">
          <Card className="w-full max-w-md p-6">
            <h2 className="text-2xl font-black">Entrar na plataforma</h2>
            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
              Fluxo preparado para Supabase Auth. Nesta previa, escolha um
              perfil para navegar pelo produto.
            </p>

            <div className="mt-6 space-y-4">
              <Input defaultValue="nutri@starnutri.com" type="email" />
              <Input defaultValue="demo-star-nutri" type="password" />

              <div className="grid grid-cols-3 gap-2">
                {(['admin', 'nutritionist', 'patient'] as UserRole[]).map((item) => (
                  <button
                    className={`rounded-lg border px-3 py-2 text-sm font-bold transition ${
                      role === item
                        ? 'border-emerald-600 bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                        : 'border-slate-200 text-slate-600 dark:border-slate-700 dark:text-slate-300'
                    }`}
                    key={item}
                    onClick={() => setRole(item)}
                    type="button"
                  >
                    {roleLabel(item)}
                  </button>
                ))}
              </div>

              <Button className="w-full" onClick={() => onLogin(role)} type="button">
                Entrar como {roleLabel(role)}
              </Button>
            </div>
          </Card>
        </section>
      </div>
    </main>
  )
}

function NutritionistArea({
  activeView,
  data,
  patient,
  selectedPatientId,
  onSelectPatient,
  onCreatePatient,
  onCreateDiet,
  onCreateWorkout,
  onUpdateData,
}: {
  activeView: string
  data: AppData
  patient: Patient
  selectedPatientId: string
  onSelectPatient: (id: string) => void
  onCreatePatient: (patient: Patient) => void
  onCreateDiet: (diet: Diet) => void
  onCreateWorkout: (workout: Workout) => void
  onUpdateData: (data: AppData) => void
}) {
  const patientBundle = usePatientBundle(data, patient.id)

  if (activeView === 'patients') {
    return (
      <PatientDetails
        data={data}
        onCreateDiet={onCreateDiet}
        onCreateWorkout={onCreateWorkout}
        onUpdateData={onUpdateData}
        patient={patient}
      />
    )
  }

  if (activeView === 'diet') {
    return (
      <Page title="Dietas" description="Cadastro e visualizacao do plano alimentar ativo.">
        <DietPanel
          diet={patientBundle.diet}
          onCreateDiet={() => onCreateDiet(makeDemoDiet(patient.id))}
        />
      </Page>
    )
  }

  if (activeView === 'workout') {
    return (
      <Page title="Treinos" description="Treino ativo com exercicios e parametros.">
        <WorkoutPanel
          onCreateWorkout={() => onCreateWorkout(makeDemoWorkout(patient.id))}
          workout={patientBundle.workout}
        />
      </Page>
    )
  }

  if (activeView === 'metrics') {
    return (
      <MetricsPage
        data={data}
        onUpdateData={onUpdateData}
        patient={patient}
        readonlyMain={false}
      />
    )
  }

  if (activeView === 'chat') {
    return (
      <Page
        title="Chat com IA"
        description="Arquitetura preparada para enviar contexto completo ao GLM 5.0."
      >
        <ChatBox
          conditions={patientBundle.conditions}
          diet={patientBundle.diet}
          mainMetrics={patientBundle.mainMetrics}
          messages={data.chatMessages}
          onMessagesChange={(messages) => onUpdateData({ ...data, chatMessages: messages })}
          patient={patient}
          variableMetrics={patientBundle.variableMetrics}
          workout={patientBundle.workout}
        />
      </Page>
    )
  }

  return (
    <Page
      title="Dashboard do nutricionista"
      description="Acompanhe aderencia, pendencias e evolucao dos pacientes."
      action={
        <Button onClick={() => onCreatePatient(makeDemoPatient())} type="button">
          <Plus size={18} />
          Cadastrar paciente
        </Button>
      }
    >
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          caption="ativos na base"
          icon={<Users size={20} />}
          label="Pacientes"
          value={String(data.patients.length)}
        />
        <StatCard
          caption="planos alimentares"
          icon={<CheckCircle2 size={20} />}
          label="Dietas ativas"
          value={String(data.diets.filter((diet) => diet.isActive).length)}
        />
        <StatCard
          caption="registros recentes"
          icon={<Activity size={20} />}
          label="Metricas"
          value={String(data.variableMetrics.length)}
        />
        <StatCard
          caption="conversas monitoradas"
          icon={<Bot size={20} />}
          label="Chat IA"
          value={String(data.chatMessages.length)}
        />
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-[1fr_360px]">
        <PatientList
          onSelect={onSelectPatient}
          patients={data.patients}
          selectedPatientId={selectedPatientId}
        />
        <Card className="p-5">
          <h3 className="font-bold">Pendencias inteligentes</h3>
          <div className="mt-4 space-y-3">
            {data.patients.map((item) => {
              const hasDiet = data.diets.some((diet) => diet.patientId === item.id)
              return (
                <button
                  className="w-full rounded-lg bg-slate-50 p-3 text-left text-sm transition hover:bg-slate-100 dark:bg-slate-950 dark:hover:bg-slate-800"
                  key={item.id}
                  onClick={() => onSelectPatient(item.id)}
                  type="button"
                >
                  <p className="font-bold">{item.fullName}</p>
                  <p className="mt-1 text-slate-500 dark:text-slate-400">
                    {hasDiet ? 'Plano alimentar ativo' : 'Sem dieta ativa cadastrada'}
                  </p>
                </button>
              )
            })}
          </div>
        </Card>
      </div>
    </Page>
  )
}

function PatientDetails({
  data,
  patient,
  onCreateDiet,
  onCreateWorkout,
  onUpdateData,
}: {
  data: AppData
  patient: Patient
  onCreateDiet: (diet: Diet) => void
  onCreateWorkout: (workout: Workout) => void
  onUpdateData: (data: AppData) => void
}) {
  const [tab, setTab] = useState('resumo')
  const bundle = usePatientBundle(data, patient.id)

  return (
    <Page title={patient.fullName} description="Detalhes, plano e historico do paciente.">
      <div className="mb-5 flex gap-2 overflow-x-auto">
        {['resumo', 'dieta', 'treino', 'metricas', 'condicoes', 'chat'].map((item) => (
          <button
            className={`rounded-lg px-4 py-2 text-sm font-bold ${
              tab === item
                ? 'bg-emerald-600 text-white'
                : 'bg-white text-slate-600 dark:bg-slate-900 dark:text-slate-300'
            }`}
            key={item}
            onClick={() => setTab(item)}
            type="button"
          >
            {item}
          </button>
        ))}
      </div>

      {tab === 'resumo' && <PatientSummary patient={patient} {...bundle} />}
      {tab === 'dieta' && (
        <DietPanel
          diet={bundle.diet}
          onCreateDiet={() => onCreateDiet(makeDemoDiet(patient.id))}
        />
      )}
      {tab === 'treino' && (
        <WorkoutPanel
          onCreateWorkout={() => onCreateWorkout(makeDemoWorkout(patient.id))}
          workout={bundle.workout}
        />
      )}
      {tab === 'metricas' && (
        <MetricsPage data={data} onUpdateData={onUpdateData} patient={patient} readonlyMain={false} />
      )}
      {tab === 'condicoes' && (
        <ConditionsPage data={data} onUpdateData={onUpdateData} patient={patient} />
      )}
      {tab === 'chat' && (
        <ChatBox
          conditions={bundle.conditions}
          diet={bundle.diet}
          mainMetrics={bundle.mainMetrics}
          messages={data.chatMessages}
          onMessagesChange={(messages) => onUpdateData({ ...data, chatMessages: messages })}
          patient={patient}
          variableMetrics={bundle.variableMetrics}
          workout={bundle.workout}
        />
      )}
    </Page>
  )
}

function PatientArea({
  activeView,
  data,
  patient,
  onUpdateData,
}: {
  activeView: string
  data: AppData
  patient: Patient
  onUpdateData: (data: AppData) => void
}) {
  const bundle = usePatientBundle(data, patient.id)

  if (activeView === 'patient-metrics') {
    return <MetricsPage data={data} onUpdateData={onUpdateData} patient={patient} readonlyMain />
  }

  if (activeView === 'patient-chat') {
    return (
      <Page title="Chat com IA" description="Tire duvidas sem sair do plano definido.">
        <ChatBox
          conditions={bundle.conditions}
          diet={bundle.diet}
          mainMetrics={bundle.mainMetrics}
          messages={data.chatMessages}
          onMessagesChange={(messages) => onUpdateData({ ...data, chatMessages: messages })}
          patient={patient}
          variableMetrics={bundle.variableMetrics}
          workout={bundle.workout}
        />
      </Page>
    )
  }

  return (
    <Page title={`Ola, ${patient.fullName}`} description={patient.objective}>
      <div className="grid gap-4 xl:grid-cols-[1fr_0.9fr]">
        <DietPanel diet={bundle.diet} readonly />
        <WorkoutPanel workout={bundle.workout} readonly />
      </div>
    </Page>
  )
}

function AdminDashboard({
  data,
  onLoginAs,
}: {
  data: AppData
  onLoginAs: (role: UserRole) => void
}) {
  return (
    <Page title="Painel administrativo" description="Usuarios, permissoes e status da operacao.">
      <div className="grid gap-4 md:grid-cols-3">
        <StatCard
          caption="perfis cadastrados"
          icon={<ShieldCheck size={20} />}
          label="Usuarios"
          value={String(data.profiles.length)}
        />
        <StatCard
          caption="contas profissionais"
          icon={<Users size={20} />}
          label="Nutricionistas"
          value={String(data.nutritionists.length)}
        />
        <StatCard
          caption="modelo configurado"
          icon={<Bot size={20} />}
          label="IA"
          value="GLM 5.0"
        />
      </div>

      <Card className="mt-6 p-5">
        <h3 className="font-bold">Acesso rapido de demonstracao</h3>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={() => onLoginAs('nutritionist')} type="button">
            Ver como nutricionista
          </Button>
          <Button onClick={() => onLoginAs('patient')} type="button" variant="secondary">
            Ver como paciente
          </Button>
        </div>
      </Card>
    </Page>
  )
}

function PatientList({
  patients,
  selectedPatientId,
  onSelect,
}: {
  patients: Patient[]
  selectedPatientId: string
  onSelect: (id: string) => void
}) {
  const [query, setQuery] = useState('')
  const filtered = patients.filter((patient) =>
    `${patient.fullName} ${patient.objective}`.toLowerCase().includes(query.toLowerCase()),
  )

  return (
    <Card className="p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h3 className="font-bold">Pacientes</h3>
        <div className="relative sm:w-72">
          <Search className="absolute left-3 top-2.5 text-slate-400" size={18} />
          <Input
            className="pl-10"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Buscar paciente"
            value={query}
          />
        </div>
      </div>

      <div className="mt-4 grid gap-3">
        {filtered.map((patient) => (
          <button
            className={`rounded-lg border p-4 text-left transition ${
              selectedPatientId === patient.id
                ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-950'
                : 'border-slate-200 bg-white hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:hover:bg-slate-800'
            }`}
            key={patient.id}
            onClick={() => onSelect(patient.id)}
            type="button"
          >
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="font-bold">{patient.fullName}</p>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                  {patient.objective}
                </p>
              </div>
              <Badge tone="green">ativo</Badge>
            </div>
          </button>
        ))}
      </div>
    </Card>
  )
}

function MetricsPage({
  data,
  patient,
  onUpdateData,
  readonlyMain,
}: {
  data: AppData
  patient: Patient
  onUpdateData: (data: AppData) => void
  readonlyMain: boolean
}) {
  const [metricName, setMetricName] = useState('Agua consumida')
  const [metricValue, setMetricValue] = useState('')
  const [metricUnit, setMetricUnit] = useState('ml')
  const bundle = usePatientBundle(data, patient.id)

  function addVariableMetric() {
    if (!metricName.trim() || !metricValue.trim()) {
      return
    }
    const nextMetric: PatientMetric = {
      id: crypto.randomUUID(),
      patientId: patient.id,
      name: metricName,
      value: metricValue,
      unit: metricUnit,
      recordedAt: new Date().toISOString(),
    }
    onUpdateData({
      ...data,
      variableMetrics: [nextMetric, ...data.variableMetrics],
    })
    setMetricValue('')
  }

  return (
    <Page title="Metricas" description="Metricas principais e registros variaveis do paciente.">
      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <Card className="p-5">
          <h3 className="font-bold">Metricas principais</h3>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {readonlyMain
              ? 'Definidas pelo nutricionista e visiveis para voce.'
              : 'Definidas pelo nutricionista para orientar plano e IA.'}
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {bundle.mainMetrics.map((metric) => (
              <div className="rounded-lg bg-slate-50 p-4 dark:bg-slate-950" key={metric.id}>
                <p className="text-sm font-semibold text-slate-500 dark:text-slate-400">
                  {metric.name}
                </p>
                <p className="mt-2 text-xl font-bold">
                  {metric.value} {metric.unit}
                </p>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-5">
          <h3 className="font-bold">Novo registro variavel</h3>
          <div className="mt-4 space-y-3">
            <Input
              onChange={(event) => setMetricName(event.target.value)}
              placeholder="Nome"
              value={metricName}
            />
            <Input
              onChange={(event) => setMetricValue(event.target.value)}
              placeholder="Valor"
              value={metricValue}
            />
            <Input
              onChange={(event) => setMetricUnit(event.target.value)}
              placeholder="Unidade"
              value={metricUnit}
            />
            <Button className="w-full" onClick={addVariableMetric} type="button">
              <Plus size={18} />
              Registrar
            </Button>
          </div>
        </Card>
      </div>

      <Card className="mt-4 p-5">
        <h3 className="font-bold">Historico recente</h3>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {bundle.variableMetrics.map((metric) => (
            <div className="rounded-lg border border-slate-200 p-4 dark:border-slate-800" key={metric.id}>
              <p className="text-sm font-semibold">{metric.name}</p>
              <p className="mt-2 text-xl font-bold">
                {metric.value} {metric.unit}
              </p>
              <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                {metric.recordedAt ? new Date(metric.recordedAt).toLocaleString('pt-BR') : 'Agora'}
              </p>
            </div>
          ))}
        </div>
      </Card>
    </Page>
  )
}

function ConditionsPage({
  data,
  patient,
  onUpdateData,
}: {
  data: AppData
  patient: Patient
  onUpdateData: (data: AppData) => void
}) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const bundle = usePatientBundle(data, patient.id)

  function addCondition() {
    if (!title.trim() || !description.trim()) {
      return
    }
    onUpdateData({
      ...data,
      conditions: [
        {
          id: crypto.randomUUID(),
          patientId: patient.id,
          conditionType: 'observation',
          title,
          description,
          severity: 'observacao',
        },
        ...data.conditions,
      ],
    })
    setTitle('')
    setDescription('')
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
      <Card className="p-5">
        <h3 className="font-bold">Individualidades do paciente</h3>
        <div className="mt-4 grid gap-3">
          {bundle.conditions.map((condition) => (
            <div className="rounded-lg border border-slate-200 p-4 dark:border-slate-800" key={condition.id}>
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="amber">{condition.conditionType}</Badge>
                <p className="font-bold">{condition.title}</p>
              </div>
              <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
                {condition.description}
              </p>
            </div>
          ))}
        </div>
      </Card>
      <Card className="p-5">
        <h3 className="font-bold">Nova observacao</h3>
        <div className="mt-4 space-y-3">
          <Input onChange={(event) => setTitle(event.target.value)} placeholder="Titulo" value={title} />
          <Textarea
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Descricao"
            value={description}
          />
          <Button className="w-full" onClick={addCondition} type="button">
            <Plus size={18} />
            Adicionar
          </Button>
        </div>
      </Card>
    </div>
  )
}

function Page({
  title,
  description,
  action,
  children,
}: {
  title: string
  description: string
  action?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <div>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-black tracking-normal sm:text-3xl">{title}</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500 dark:text-slate-400">
            {description}
          </p>
        </div>
        {action}
      </div>
      {children}
    </div>
  )
}

function usePatientBundle(data: AppData, patientId: string) {
  return useMemo(
    () => ({
      diet: data.diets.find((diet) => diet.patientId === patientId && diet.isActive),
      workout: data.workouts.find(
        (workout) => workout.patientId === patientId && workout.isActive,
      ),
      mainMetrics: data.mainMetrics.filter((metric) => metric.patientId === patientId),
      variableMetrics: data.variableMetrics.filter(
        (metric) => metric.patientId === patientId,
      ),
      conditions: data.conditions.filter((condition) => condition.patientId === patientId),
    }),
    [data, patientId],
  )
}

function makeDemoPatient(): Patient {
  const id = crypto.randomUUID()
  return {
    id,
    userId: `user-${id}`,
    nutritionistId: 'nutritionist-1',
    fullName: 'Novo paciente',
    email: `paciente-${id.slice(0, 4)}@example.com`,
    birthDate: '1992-01-01',
    gender: 'Nao informado',
    objective: 'Definir objetivo nutricional',
    notes: 'Paciente criado em modo demo. Edicao completa sera ligada ao Supabase.',
    isActive: true,
  }
}

function makeDemoDiet(patientId: string): Diet {
  return {
    id: crypto.randomUUID(),
    patientId,
    nutritionistId: 'nutritionist-1',
    title: 'Plano alimentar inicial',
    description: 'Estrutura base cadastrada pelo nutricionista.',
    calories: 2100,
    protein: 150,
    carbs: 230,
    fats: 65,
    waterGoalMl: 2800,
    isActive: true,
    meals: [
      {
        id: crypto.randomUUID(),
        mealName: 'Refeicao principal',
        mealTime: '12:30',
        foods: [
          { name: 'Proteina magra', quantity: '150g' },
          { name: 'Carboidrato base', quantity: '120g' },
          { name: 'Vegetais', quantity: 'livre' },
        ],
      },
    ],
  }
}

function makeDemoWorkout(patientId: string): Workout {
  return {
    id: crypto.randomUUID(),
    patientId,
    nutritionistId: 'nutritionist-1',
    title: 'Treino inicial',
    description: 'Rotina base de adaptacao.',
    frequencyPerWeek: 3,
    isActive: true,
    exercises: [
      {
        id: crypto.randomUUID(),
        exerciseName: 'Treino full body',
        muscleGroup: 'Geral',
        sets: 3,
        reps: '10-12',
        restTime: '60s',
      },
    ],
  }
}

function roleLabel(role: UserRole) {
  return role === 'admin' ? 'Admin' : role === 'nutritionist' ? 'Nutricionista' : 'Paciente'
}

export default App
