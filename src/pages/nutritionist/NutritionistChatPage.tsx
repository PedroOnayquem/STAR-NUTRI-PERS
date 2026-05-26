import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
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

  return (
    <ChatExperience
      externalQueryKey={['nutritionist-workspace']}
      onPatientChange={setSelectedPatientId}
      patientId={selectedPatientId}
      patients={patients}
      patientName={
        patients.find((patient) => patient.id === selectedPatientId)?.profile
          ?.full_name ?? 'Chat geral'
      }
      scope="nutritionist"
    />
  )
}
