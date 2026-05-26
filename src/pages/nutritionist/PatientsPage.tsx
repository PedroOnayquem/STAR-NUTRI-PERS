import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Link, useNavigate } from 'react-router-dom'
import { Mail, Plus, Search, UserPlus, Users } from 'lucide-react'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { Input, Textarea } from '../../components/ui/Input'
import { SectionHeader } from '../../components/ui/SectionHeader'
import { PageSkeleton } from '../../components/ui/Skeleton'
import { useAuth } from '../../features/auth/useAuth'
import { getNutritionistWorkspace } from '../../features/clinical/services/workspaceService'
import {
  createPatient,
  type CreatePatientInput,
} from '../../features/nutritionist/services/patientService'
import { useDeferredValue, useMemo, useState } from 'react'

const patientSchema = z.object({
  fullName: z.string().min(3, 'Informe o nome completo.'),
  email: z.string().email('Informe um email valido.'),
  password: z.string().min(6, 'A senha deve ter pelo menos 6 caracteres.'),
  birthDate: z.string(),
  gender: z.string(),
  objective: z.string(),
  notes: z.string().max(1000, 'Maximo de 1000 caracteres.'),
})

export function PatientsPage({ mode = 'list' }: { mode?: 'list' | 'create' }) {
  const { session } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search)

  const workspaceQuery = useQuery({
    queryKey: ['nutritionist-workspace'],
    queryFn: () => getNutritionistWorkspace(session),
    enabled: Boolean(session),
  })

  const form = useForm<CreatePatientInput>({
    resolver: zodResolver(patientSchema),
    defaultValues: {
      fullName: '',
      email: '',
      password: '',
      birthDate: '',
      gender: '',
      objective: '',
      notes: '',
    },
  })

  const createMutation = useMutation({
    mutationFn: (payload: CreatePatientInput) => createPatient(payload, session),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ['nutritionist-workspace'] })
      navigate(`/nutritionist/patients/${created.patient_id}`)
    },
  })

  const patients = useMemo(() => {
    const all = workspaceQuery.data?.patients ?? []
    const term = deferredSearch.trim().toLowerCase()
    if (!term) return all

    return all.filter((patient) => {
      const name = patient.profile?.full_name?.toLowerCase() ?? ''
      const email = patient.profile?.email?.toLowerCase() ?? ''
      const objective = patient.objective?.toLowerCase() ?? ''
      return name.includes(term) || email.includes(term) || objective.includes(term)
    })
  }, [deferredSearch, workspaceQuery.data?.patients])

  if (workspaceQuery.isLoading) return <PageSkeleton />
  if (workspaceQuery.error) throw workspaceQuery.error

  if (mode === 'create') {
    return (
      <div className="space-y-6">
        <SectionHeader
          description="O nutricionista cria a conta do paciente. O paciente recebe email/senha e acessa a area dele."
          eyebrow={<Badge tone="green">Novo paciente</Badge>}
          title="Cadastrar paciente"
        />

        <Card className="p-6" variant="glass">
          <form
            className="grid gap-4 md:grid-cols-2"
            onSubmit={form.handleSubmit((values) => createMutation.mutate(values))}
          >
            <Field error={form.formState.errors.fullName?.message} label="Nome completo">
              <Input placeholder="Lucas Andrade" {...form.register('fullName')} />
            </Field>
            <Field error={form.formState.errors.email?.message} label="Email">
              <Input placeholder="paciente@email.com" type="email" {...form.register('email')} />
            </Field>
            <Field error={form.formState.errors.password?.message} label="Senha provisoria">
              <Input type="password" {...form.register('password')} />
            </Field>
            <Field error={form.formState.errors.birthDate?.message} label="Data de nascimento">
              <Input type="date" {...form.register('birthDate')} />
            </Field>
            <Field error={form.formState.errors.gender?.message} label="Genero">
              <Input placeholder="Feminino, masculino..." {...form.register('gender')} />
            </Field>
            <Field error={form.formState.errors.objective?.message} label="Objetivo">
              <Input placeholder="Emagrecimento, hipertrofia..." {...form.register('objective')} />
            </Field>
            <div className="md:col-span-2">
              <Field error={form.formState.errors.notes?.message} label="Historico e observacoes">
                <Textarea
                  placeholder="Rotina, restricoes, preferencias, historico clinico inicial..."
                  {...form.register('notes')}
                />
              </Field>
            </div>

            {createMutation.error && (
              <p className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm font-semibold text-rose-700 dark:border-rose-400/20 dark:bg-rose-400/10 dark:text-rose-300 md:col-span-2">
                {createMutation.error.message}
              </p>
            )}

            <div className="flex gap-2 md:col-span-2">
              <Button disabled={createMutation.isPending} type="submit" variant="premium">
                <UserPlus size={18} />
                {createMutation.isPending ? 'Cadastrando...' : 'Cadastrar paciente'}
              </Button>
              <Button asChild type="button" variant="secondary">
                <Link to="/nutritionist/patients">Cancelar</Link>
              </Button>
            </div>
          </form>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <SectionHeader
        actions={
          <Button asChild variant="premium">
            <Link to="/nutritionist/patients/new">
              <Plus size={18} />
              Novo paciente
            </Link>
          </Button>
        }
        description="Busque, abra detalhes, edite dados clinicos e gerencie planos reais."
        eyebrow={<Badge tone="blue">Gestao de pacientes</Badge>}
        title="Pacientes"
      />

      <Card className="p-4">
        <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-2 dark:border-white/10 dark:bg-white/[0.04]">
          <Search size={18} className="text-slate-400" />
          <input
            className="w-full bg-transparent text-sm outline-none placeholder:text-slate-400"
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Buscar por nome, email ou objetivo"
            value={search}
          />
        </div>
      </Card>

      {patients.length === 0 ? (
        <EmptyState
          action={
            <Button asChild variant="premium">
              <Link to="/nutritionist/patients/new">Cadastrar paciente</Link>
            </Button>
          }
          description="Os pacientes cadastrados pelo nutricionista aparecem aqui com dados reais do Supabase."
          icon={<Users size={24} />}
          title="Nenhum paciente encontrado"
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {patients.map((patient) => (
            <Link key={patient.id} to={`/nutritionist/patients/${patient.id}`}>
              <Card className="h-full p-5 transition hover:-translate-y-0.5 hover:shadow-xl">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h2 className="text-lg font-black">{patient.profile?.full_name ?? 'Paciente'}</h2>
                    <p className="mt-1 flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                      <Mail size={15} />
                      {patient.profile?.email}
                    </p>
                  </div>
                  <Badge tone={patient.is_active ? 'green' : 'amber'}>
                    {patient.is_active ? 'Ativo' : 'Inativo'}
                  </Badge>
                </div>
                <p className="mt-4 text-sm leading-6 text-slate-600 dark:text-slate-300">
                  {patient.objective || 'Objetivo ainda nao informado.'}
                </p>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

function Field({
  children,
  error,
  label,
}: {
  children: React.ReactNode
  error?: string
  label: string
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-semibold text-slate-700 dark:text-slate-200">
        {label}
      </span>
      {children}
      {error && <span className="mt-1.5 block text-xs font-semibold text-rose-600">{error}</span>}
    </label>
  )
}
