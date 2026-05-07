import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Bot, Search, Users } from 'lucide-react'
import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { SectionHeader } from '../../components/ui/SectionHeader'
import { PageSkeleton } from '../../components/ui/Skeleton'
import { ChatExperience } from '../../features/chat/components/ChatExperience'
import { useAuth } from '../../features/auth/useAuth'
import { getNutritionistWorkspace } from '../../features/clinical/services/workspaceService'
import { cn } from '../../lib/utils'

export function NutritionistChatPage() {
  const { session } = useAuth()
  const [search, setSearch] = useState('')
  const [selectedPatientId, setSelectedPatientId] = useState<string | null>(null)

  const query = useQuery({
    queryKey: ['nutritionist-workspace'],
    queryFn: () => getNutritionistWorkspace(session),
    enabled: Boolean(session),
  })

  const patients = useMemo(() => {
    const all = query.data?.patients ?? []
    const term = search.trim().toLowerCase()
    if (!term) return all

    return all.filter((patient) => {
      const name = patient.profile?.full_name?.toLowerCase() ?? ''
      const email = patient.profile?.email?.toLowerCase() ?? ''
      const objective = patient.objective?.toLowerCase() ?? ''
      return name.includes(term) || email.includes(term) || objective.includes(term)
    })
  }, [query.data?.patients, search])

  useEffect(() => {
    if (!selectedPatientId && patients[0]?.id) {
      setSelectedPatientId(patients[0].id)
    }
  }, [patients, selectedPatientId])

  if (query.isLoading) return <PageSkeleton />
  if (query.error) throw query.error

  const selectedPatient = query.data?.patients.find(
    (patient) => patient.id === selectedPatientId,
  )

  return (
    <div className="space-y-6">
      <SectionHeader
        description="Selecione um paciente e converse com a IA usando contexto real: dieta, treino, métricas, condições e histórico."
        eyebrow={<Badge tone="blue">Chat IA do nutricionista</Badge>}
        title="Chat clínico com GLM 5"
      />

      <div className="grid gap-4 xl:grid-cols-[340px_1fr]">
        <Card className="overflow-hidden p-0">
          <div className="border-b border-slate-200 p-4 dark:border-white/10">
            <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-2 dark:border-white/10 dark:bg-white/[0.04]">
              <Search size={18} className="text-slate-400" />
              <input
                className="w-full bg-transparent text-sm outline-none placeholder:text-slate-400"
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Buscar paciente"
                value={search}
              />
            </div>
          </div>

          {patients.length === 0 ? (
            <div className="p-4">
              <EmptyState
                description="Cadastre pacientes para liberar o chat clínico por contexto."
                icon={<Users size={22} />}
                title="Sem pacientes"
              />
            </div>
          ) : (
            <div className="max-h-[720px] divide-y divide-slate-100 overflow-y-auto dark:divide-white/10">
              {patients.map((patient) => (
                <button
                  className={cn(
                    'w-full p-4 text-left transition',
                    selectedPatientId === patient.id
                      ? 'bg-slate-950 text-white dark:bg-white dark:text-slate-950'
                      : 'hover:bg-slate-50 dark:hover:bg-white/[0.04]',
                  )}
                  key={patient.id}
                  onClick={() => setSelectedPatientId(patient.id)}
                  type="button"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-black">{patient.profile?.full_name ?? 'Paciente'}</p>
                      <p className={cn(
                        'mt-1 text-sm',
                        selectedPatientId === patient.id
                          ? 'text-white/70 dark:text-slate-600'
                          : 'text-slate-500 dark:text-slate-400',
                      )}>
                        {patient.objective || 'Sem objetivo informado'}
                      </p>
                    </div>
                    <Bot size={17} />
                  </div>
                </button>
              ))}
            </div>
          )}
        </Card>

        {selectedPatient ? (
          <ChatExperience
            externalQueryKey={['nutritionist-workspace']}
            patientId={selectedPatient.id}
            patientName={selectedPatient.profile?.full_name ?? undefined}
          />
        ) : (
          <EmptyState
            description="Escolha um paciente para carregar histórico e conversar com a IA."
            icon={<Bot size={22} />}
            title="Selecione um paciente"
          />
        )}
      </div>
    </div>
  )
}
