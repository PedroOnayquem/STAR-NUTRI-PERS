import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Activity, BarChart3, ShieldCheck, UserPlus, Users } from 'lucide-react'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { Input, Textarea } from '../components/ui/Input'
import { SectionHeader } from '../components/ui/SectionHeader'
import { PageSkeleton } from '../components/ui/Skeleton'
import { StatCard } from '../components/ui/StatCard'
import { useAuth } from '../features/auth/useAuth'
import {
  createNutritionist,
  type CreateNutritionistInput,
} from '../features/admin/services/adminService'
import { getAdminWorkspace } from '../features/clinical/services/workspaceService'

const nutritionistSchema = z.object({
  fullName: z.string().min(3, 'Informe o nome completo.'),
  email: z.string().email('Informe um email valido.'),
  password: z.string().min(6, 'A senha deve ter pelo menos 6 caracteres.'),
  crn: z.string(),
  specialty: z.string(),
  bio: z.string().max(500, 'Maximo de 500 caracteres.'),
})

export function AdminPage() {
  const { session } = useAuth()
  const [tab, setTab] = useState<'overview' | 'nutritionists' | 'users'>('overview')
  const queryClient = useQueryClient()
  const workspaceQuery = useQuery({
    queryKey: ['admin-workspace'],
    queryFn: () => getAdminWorkspace(session),
    enabled: Boolean(session),
  })

  const form = useForm<CreateNutritionistInput>({
    resolver: zodResolver(nutritionistSchema),
    defaultValues: {
      fullName: '',
      email: '',
      password: '',
      crn: '',
      specialty: '',
      bio: '',
    },
  })

  const createMutation = useMutation({
    mutationFn: (payload: CreateNutritionistInput) => createNutritionist(payload, session),
    onSuccess: () => {
      form.reset()
      queryClient.invalidateQueries({ queryKey: ['admin-workspace'] })
    },
  })

  if (workspaceQuery.isLoading) return <PageSkeleton />
  if (workspaceQuery.error) throw workspaceQuery.error

  const workspace = workspaceQuery.data

  return (
    <div className="space-y-6">
      <SectionHeader
        description="Controle operacional do SaaS: usuarios, nutricionistas, pacientes, uso e seguranca."
        eyebrow={<Badge tone="blue">Admin workspace</Badge>}
        title="Painel administrativo"
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard caption="perfis cadastrados" icon={<Users size={20} />} label="Usuarios" value={workspace?.stats.users ?? 0} />
        <StatCard caption="profissionais ativos" icon={<ShieldCheck size={20} />} label="Nutricionistas" value={workspace?.stats.nutritionists ?? 0} />
        <StatCard caption="pacientes totais" icon={<Activity size={20} />} label="Pacientes" value={workspace?.stats.patients ?? 0} />
        <StatCard caption="mensagens salvas" icon={<BarChart3 size={20} />} label="Chat IA" value={workspace?.stats.chat_messages ?? 0} />
      </div>

      <div className="flex gap-2 overflow-x-auto rounded-2xl border border-slate-200 bg-white p-2 dark:border-white/10 dark:bg-white/[0.04]">
        {[
          ['overview', 'Visao geral'],
          ['nutritionists', 'Nutricionistas'],
          ['users', 'Usuarios'],
        ].map(([id, label]) => (
          <button
            className={`rounded-xl px-3 py-2 text-sm font-bold transition ${
              tab === id
                ? 'bg-slate-950 text-white dark:bg-white dark:text-slate-950'
                : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-white/10'
            }`}
            key={id}
            onClick={() => setTab(id as typeof tab)}
            type="button"
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <div className="grid gap-4 xl:grid-cols-3">
          <Card className="p-5">
            <h2 className="font-black">Analytics</h2>
            <div className="mt-4 space-y-3 text-sm text-slate-600 dark:text-slate-300">
              <p>Dietas cadastradas: <strong>{workspace?.stats.diets ?? 0}</strong></p>
              <p>Treinos cadastrados: <strong>{workspace?.stats.workouts ?? 0}</strong></p>
              <p>Pacientes ativos: <strong>{workspace?.stats.active_patients ?? 0}</strong></p>
            </div>
          </Card>
          <Card className="p-5">
            <h2 className="font-black">Assinaturas</h2>
            <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">
              Estrutura preparada para integrar billing e planos. Hoje os dados estao centralizados no workspace admin.
            </p>
          </Card>
          <Card className="p-5">
            <h2 className="font-black">Logs e acesso</h2>
            <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">
              O banco possui tabela de logs. As proximas automacoes podem registrar eventos de CRUD e chat.
            </p>
          </Card>
        </div>
      )}

      {tab === 'nutritionists' && (
        <div className="grid gap-4 xl:grid-cols-[420px_1fr]">
          <Card className="p-5" variant="glass">
            <div className="flex items-center gap-3">
              <div className="rounded-2xl bg-gradient-to-br from-emerald-500 to-cyan-500 p-3 text-white">
                <UserPlus size={20} />
              </div>
              <div>
                <h2 className="font-black">Cadastrar nutricionista</h2>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  Apenas admins criam profissionais.
                </p>
              </div>
            </div>

            <form
              className="mt-5 space-y-3"
              onSubmit={form.handleSubmit((values) => createMutation.mutate(values))}
            >
              <Input placeholder="Nome completo" {...form.register('fullName')} />
              {form.formState.errors.fullName && <ErrorText>{form.formState.errors.fullName.message}</ErrorText>}
              <Input placeholder="Email" type="email" {...form.register('email')} />
              {form.formState.errors.email && <ErrorText>{form.formState.errors.email.message}</ErrorText>}
              <Input placeholder="Senha provisoria" type="password" {...form.register('password')} />
              {form.formState.errors.password && <ErrorText>{form.formState.errors.password.message}</ErrorText>}
              <Input placeholder="CRN" {...form.register('crn')} />
              <Input placeholder="Especialidade" {...form.register('specialty')} />
              <Textarea placeholder="Bio" {...form.register('bio')} />
              {createMutation.error && <ErrorText>{createMutation.error.message}</ErrorText>}
              {createMutation.isSuccess && (
                <p className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm font-semibold text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-300">
                  Nutricionista criado com sucesso.
                </p>
              )}
              <Button disabled={createMutation.isPending} type="submit" variant="premium">
                {createMutation.isPending ? 'Criando...' : 'Criar nutricionista'}
              </Button>
            </form>
          </Card>

          <Card className="p-0">
            <div className="border-b border-slate-200 p-5 dark:border-white/10">
              <h2 className="font-black">Nutricionistas</h2>
            </div>
            {workspace?.nutritionists.length === 0 ? (
              <div className="p-5">
                <EmptyState description="Crie o primeiro nutricionista para liberar a operacao clinica." title="Nenhum nutricionista" />
              </div>
            ) : (
              <div className="divide-y divide-slate-100 dark:divide-white/10">
                {workspace?.nutritionists.map((nutritionist) => {
                  const profile = workspace.profiles.find((item) => item.id === nutritionist.user_id)
                  return (
                    <div className="p-5" key={nutritionist.id}>
                      <p className="font-bold">{profile?.full_name ?? 'Nutricionista'}</p>
                      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{profile?.email}</p>
                      <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{nutritionist.specialty || 'Especialidade nao informada'}</p>
                    </div>
                  )
                })}
              </div>
            )}
          </Card>
        </div>
      )}

      {tab === 'users' && (
        <Card className="overflow-hidden p-0">
          <div className="border-b border-slate-200 p-5 dark:border-white/10">
            <h2 className="font-black">Usuarios e controle de acesso</h2>
          </div>
          <div className="divide-y divide-slate-100 dark:divide-white/10">
            {workspace?.profiles.map((profile) => (
              <div className="flex items-center justify-between gap-4 p-5" key={profile.id}>
                <div>
                  <p className="font-bold">{profile.full_name}</p>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{profile.email}</p>
                </div>
                <Badge tone={profile.role === 'admin' ? 'blue' : profile.role === 'nutritionist' ? 'green' : 'amber'}>
                  {profile.role}
                </Badge>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}

function ErrorText({ children }: { children?: string }) {
  return <p className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm font-semibold text-rose-700 dark:border-rose-400/20 dark:bg-rose-400/10 dark:text-rose-300">{children}</p>
}
