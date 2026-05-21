import { useQuery } from '@tanstack/react-query'
import { Activity, Bot, ClipboardList, Plus, TrendingUp, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { SectionHeader } from '../../components/ui/SectionHeader'
import { PageSkeleton } from '../../components/ui/Skeleton'
import { StatCard } from '../../components/ui/StatCard'
import { useAuth } from '../../features/auth/useAuth'
import { getNutritionistWorkspace } from '../../features/clinical/services/workspaceService'

export function NutritionistDashboardPage() {
  const { session } = useAuth()
  const { data, isLoading, error } = useQuery({
    queryKey: ['nutritionist-workspace'],
    queryFn: () => getNutritionistWorkspace(session),
    enabled: Boolean(session),
  })

  if (isLoading) return <PageSkeleton />
  if (error) throw error

  const patients = data?.patients ?? []
  const activePatients = patients.filter((patient) => patient.is_active !== false)

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
        description="Acompanhe pacientes, planos e sinais de aderencia usando dados reais do Supabase."
        eyebrow={<Badge tone="blue">Workspace clinico</Badge>}
        title="Dashboard do nutricionista"
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard caption="ativos no workspace" icon={<Users size={20} />} label="Pacientes" value={activePatients.length} />
        <StatCard caption="cadastros totais" icon={<ClipboardList size={20} />} label="Registros" value={patients.length} />
        <StatCard caption="via backend seguro" icon={<Bot size={20} />} label="Chat IA" value="ChatGPT" />
        <StatCard caption="dados em tempo real" icon={<Activity size={20} />} label="Supabase" value="RLS" />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_420px]">
        <Card className="overflow-hidden p-0">
          <div className="border-b border-slate-200/80 p-5 dark:border-white/10">
            <h2 className="text-lg font-black">Pacientes recentes</h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Lista real criada pelo fluxo nutricionista para paciente.
            </p>
          </div>
          {patients.length === 0 ? (
            <div className="p-5">
              <EmptyState
                action={
                  <Button asChild variant="premium">
                    <Link to="/nutritionist/patients/new">Cadastrar primeiro paciente</Link>
                  </Button>
                }
                description="Quando voce cadastrar pacientes, eles aparecem aqui com acesso ao perfil, dieta, treino, metricas e chat."
                icon={<Users size={22} />}
                title="Nenhum paciente ainda"
              />
            </div>
          ) : (
            <div className="divide-y divide-slate-100 dark:divide-white/10">
              {patients.slice(0, 6).map((patient) => (
                <Link
                  className="flex items-center justify-between gap-4 p-5 transition hover:bg-slate-50/80 dark:hover:bg-white/[0.03]"
                  key={patient.id}
                  to={`/nutritionist/patients/${patient.id}`}
                >
                  <div>
                    <p className="font-bold">{patient.profile?.full_name ?? 'Paciente'}</p>
                    <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                      {patient.objective || 'Objetivo nao informado'}
                    </p>
                  </div>
                  <Badge tone={patient.is_active ? 'green' : 'amber'}>
                    {patient.is_active ? 'Ativo' : 'Inativo'}
                  </Badge>
                </Link>
              ))}
            </div>
          )}
        </Card>

        <Card className="p-5" variant="glass">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-slate-950 p-2.5 text-white dark:bg-white dark:text-slate-950">
              <TrendingUp size={20} />
            </div>
            <div>
              <h2 className="font-black">Operacao preparada</h2>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Fluxos reais conectados ao banco.
              </p>
            </div>
          </div>
          <div className="mt-5 space-y-3 text-sm text-slate-600 dark:text-slate-300">
            <p>Pacientes sao criados pelo backend com Supabase Auth.</p>
            <p>Dietas, treinos, metricas e condicoes usam RLS do Supabase.</p>
            <p>O chat monta contexto completo no backend antes de chamar o ChatGPT.</p>
          </div>
        </Card>
      </div>
    </div>
  )
}
