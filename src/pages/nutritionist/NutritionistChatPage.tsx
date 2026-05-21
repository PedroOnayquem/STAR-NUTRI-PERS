import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Users } from 'lucide-react'
import { EmptyState } from '../../components/ui/EmptyState'
import { PageSkeleton } from '../../components/ui/Skeleton'
import { ChatExperience } from '../../features/chat/components/ChatExperience'
import { useAuth } from '../../features/auth/useAuth'
import { getNutritionistWorkspace } from '../../features/clinical/services/workspaceService'

export function NutritionistChatPage() {
  const { session } = useAuth()
  const [selectedPatientId, setSelectedPatientId] = useState<string | null>(null)

  const query = useQuery({
    queryKey: ['nutritionist-workspace'],
    queryFn: () => getNutritionistWorkspace(session),
    enabled: Boolean(session),
  })

  const patients = query.data?.patients ?? []

  if (query.isLoading) return <PageSkeleton />
  if (query.error) throw query.error

  if (patients.length === 0) {
    return (
      <EmptyState
        description="Cadastre pacientes para usar o chat com contexto clinico."
        icon={<Users size={22} />}
        title="Nenhum paciente cadastrado"
      />
    )
  }

  const focusedPatientId = patients.some((patient) => patient.id === selectedPatientId)
    ? selectedPatientId
    : patients[0]?.id ?? null

  return (
    <ChatExperience
      externalQueryKey={['nutritionist-workspace']}
      key={focusedPatientId}
      onPatientChange={setSelectedPatientId}
      patientId={focusedPatientId}
      patients={patients}
      patientName={
        patients.find((patient) => patient.id === focusedPatientId)?.profile
          ?.full_name ?? 'Paciente'
      }
    />
  )
}
